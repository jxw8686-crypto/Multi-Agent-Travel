# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

OpenHarness 是 Claude Code 的开源 Python（≥3.10）移植版——一个 AI 驱动的 CLI 编程助手。本仓库包含两个应用：

- **`oh` / `openharness`** — agent harness（智能体 harness 层）：提供工具集、技能系统、权限控制、多智能体协调等基础设施
  - 所谓 harness，就是把 LLM 包起来让它能干活的那层壳——模型负责"想"，harness 负责"动手"（读写文件、执行命令、访问网络...）
- **`ohmo`** — 基于 harness 构建的个人 AI 助手，带消息渠道网关（飞书 / Slack / Telegram / Discord），可以在这些 IM 里跟你的 agent 聊天、让它写代码开 PR

PyPI 包名：`openharness-ai`（当前版本 0.1.9）。

## 构建与测试命令

```bash
uv sync --extra dev          # 安装全部依赖，包括 dev 依赖
uv run ruff check src tests scripts   # 代码检查（lint）
uv run pytest -q                       # 运行全部 114 个单元+集成测试
uv run pytest -q -k "test_name"       # 按名称筛选运行单个测试
uv run mypy src/openharness           # 类型检查（CI 尚未强制要求）

# 前端（React/Ink 终端 UI）
cd frontend/terminal && npm ci        # 安装前端依赖
cd frontend/terminal && npx tsc --noEmit  # 前端类型检查

# E2E 测试脚本（需要真实模型调用，不走 mock）
python scripts/test_harness_features.py
python scripts/test_real_skills_plugins.py
python scripts/test_cli_flags.py
python scripts/test_tui_interactions.py
python scripts/test_react_tui_redesign.py
python scripts/test_docker_sandbox_e2e.py
```

Python 包无需单独的构建步骤——使用 hatchling 构建后端，配置在 `pyproject.toml`。

## 架构详解

### 入口点（Entry points）

- **`src/openharness/cli.py`** — 主 CLI，基于 typer 框架。`main()` 回调函数根据参数分发到不同模式：
  - 无参数 → 启动交互式 REPL（`run_repl`）
  - `-p "prompt"` → 单次问答模式（`run_print_mode`），输出可选 `text` / `json` / `stream-json` 格式
  - `--dry-run` → 预览模式，解析配置但不调模型、不执行工具，返回 `ready` / `warning` / `blocked` 就绪判断
  - `--continue` / `--resume` → 恢复历史会话
  - `--task-worker` → 无头 worker 模式，供后台子 agent 使用
  - 同时注册了 5 个子命令组：`oh mcp`、`oh plugin`、`oh auth`、`oh provider`、`oh config`、`oh cron`、`oh autopilot`
- **`ohmo/cli.py`** — ohmo 的 CLI 入口，提供 `ohmo init`（初始化工作区）、`ohmo config`（配置渠道和模型）、`ohmo gateway`（网关管理）、`ohmo memory`（记忆管理）
- **`src/openharness/ui/app.py`** — `run_repl()`、`run_print_mode()`、`run_task_worker()` 的具体实现，负责组装完整运行时上下文并交给 UI 层

### 核心 Agent 循环（`src/openharness/engine/`）

这是整个 harness 的心脏。核心逻辑在 `query.py:run_query()`：

```
用户输入 → 组装 messages + tool schemas → 发请求给 LLM
  → 流式接收文本增量（text delta）和工具调用块（tool_use block）
  → 遇到 tool_use：权限检查 → PreToolUse hook → 执行工具 → PostToolUse hook → 把 ToolResult 追加到消息列表
  → 循环，直到模型不再请求工具 或 达到 max_turns 上限
```

关键模块：

- **`query_engine.py`** — `QueryEngine` 类，持有会话历史、费用追踪器（`CostTracker`）、`max_turns` 上限。对外暴露 `submit_message()` 和 `continue_pending()` 两个主要方法。每次用户回合结束后触发自动记忆提取（`_extract_durable_memories`）和 auto-dream 后台任务（`_schedule_auto_dream`）
- **`query.py`** — `run_query()` 协程，是实际的循环实现。包含自动压缩逻辑：当估算 token 数超过 `auto_compact_threshold_tokens` 阈值时，截断旧消息并在最前面插入压缩后的摘要，保留任务状态和工具元数据跨越压缩边界
- **`messages.py`** — `ConversationMessage` 及其子块类型（`TextBlock`、`ToolUseBlock`、`ToolResultBlock`、`ImageBlock`）
- **`stream_events.py`** — 定义流式事件类型：`AssistantTextDelta`（文本增量）、`AssistantTurnComplete`（回合结束）、`ToolExecutionStarted`/`ToolExecutionCompleted`（工具执行生命周期）、`CompactProgressEvent`（压缩进度）、`ErrorEvent` 等
- **`cost_tracker.py`** — 累计 token 用量和费用

### 工具系统（`src/openharness/tools/`）

所有工具都继承 `tools/base.py` 中的 `BaseTool` 抽象类：

```python
class BaseTool(ABC):
    name: str                # 工具名称，LLM 据此调用
    description: str         # 工具描述，写入 system prompt
    input_model: type[BaseModel]  # Pydantic v2 模型，定义输入参数 schema

    async def execute(self, arguments, context) -> ToolResult: ...
    def is_read_only(self, arguments) -> bool: ...  # 声明是否只读，权限系统据此判断
    def to_api_schema(self) -> dict: ...  # 生成 JSON Schema 给 LLM
```

`ToolRegistry` 是工具注册表，按名称索引。默认注册表由 `tools/__init__.py:create_default_tool_registry()` 创建，注册了 43+ 个工具。

工具分类：

| 类别 | 工具 | 说明 |
|------|------|------|
| **文件 I/O** | Bash, Read, Write, Edit, Glob, Grep, NotebookEdit | 文件读写、shell 执行，均有权限检查 |
| **Agent/Team** | Agent, SendMessage, TeamCreate/TeamDelete | 子 agent 生成和消息传递 |
| **Task** | TaskCreate/Get/List/Update/Stop/Output | 后台任务生命周期管理 |
| **MCP** | MCPTool, ListMcpResources, ReadMcpResource | 调用外部 MCP 服务器提供的工具 |
| **Cron** | CronCreate/List/Delete/Toggle | 定时任务注册和管理 |
| **Web** | WebFetch, WebSearch | 网页抓取和搜索 |
| **Meta** | Skill, Config, Sleep, AskUserQuestion, Brief | 元操作：加载技能、读写配置、等待、询问用户 |
| **Mode** | EnterPlanMode, ExitPlanMode, EnterWorktree, ExitWorktree | 工作模式切换 |

### 技能系统（`src/openharness/skills/`）

技能是按需加载的 Markdown 文件，带 YAML frontmatter 元数据。模型在 system prompt 中看到可用技能列表（名称 + 描述）；当需要时，通过 `/skill-name` 斜杠命令或 `Skill` 工具加载完整内容注入上下文。

加载器在 `skills/loader.py`，注册表在 `skills/registry.py`。发现路径按优先级从高到低：

1. **bundled** — 包内预置技能（`skills/bundled/` 目录，打包时 `force-include` 进 wheel）
2. **plugin** — 插件携带的技能
3. **user** — 用户级：`~/.openharness/skills/<skill>/SKILL.md`，`~/.claude/skills/<skill>/SKILL.md`，`~/.agents/skills/<skill>/SKILL.md`
4. **project** — 项目级：从当前工作目录向上遍历到 git 根目录，在 `.openharness/skills/`、`.claude/skills/`、`.agents/skills/` 中查找

兼容 [anthropics/skills](https://github.com/anthropics/skills) 的 SKILL.md 目录布局。

### 插件系统（`src/openharness/plugins/`）

兼容 Claude Code 插件格式。每个插件是一个目录，包含：

```
my-plugin/
  .claude-plugin/plugin.json   # 插件清单（name, version, description）
  commands/*.md                # 斜杠命令定义
  hooks/hooks.json             # 事件钩子配置
  agents/*.md                  # 自定义 agent 类型
  skills/                      # 插件自带的技能
  mcp_servers/                 # 插件自带的 MCP 服务器
```

插件加载器在 `plugins/loader.py`，安装器在 `plugins/installer.py`。加载来源：bundled → user（`~/.openharness/plugins/`）→ project（`.openharness/plugins/`）。

### 权限系统（`src/openharness/permissions/`）

三种权限模式：

- **`default`**（默认）—— 写操作和执行命令前询问用户
- **`plan`**（计划模式）—— 阻止所有写操作，仅允许读取，适合大规模重构前的审查
- **`full_auto`**（全自动）—— 允许一切，适用于沙箱环境

`PermissionChecker` 在每次工具调用前检查：
- 路径规则（glob 模式匹配，可配置 allow/deny）
- 禁止命令列表（如 `rm -rf /`）
- 允许/禁止工具名单

权限模式可运行时通过 `/permissions` 切换。

### Hooks 系统（`src/openharness/hooks/`）

事件驱动的钩子系统。`HookExecutor` 管理来自 settings、插件、项目配置的 hook 注册。核心事件类型：

- `PreToolUse` / `PostToolUse` — 工具调用前后，可干预或记录
- `UserPromptSubmit` — 用户提交 prompt 时
- `Notification` — 通知事件
- `Stop` — 会话结束时

Hook 定义支持匹配条件（如仅匹配特定工具名），可配置为阻塞式（影响执行）或通知式（仅记录）。支持热重载（`hooks/hot_reload.py` 通过 `watchfiles` 监控文件变更）。

### MCP 协议客户端（`src/openharness/mcp/`）

Model Context Protocol 客户端，支持两种传输方式：

- **stdio** — 启动子进程，通过标准输入输出通信
- **HTTP/WS** — 通过网络连接，支持自动重连

`client.py` 管理服务器生命周期（启动、健康检查、断线重连）。MCP 工具被包装为 `MCPTool` 实例，合并到工具注册表中，对 LLM 透明——LLM 分不清哪个工具是内置的、哪个来自 MCP。

`config.py` 负责加载和验证 MCP 服务器配置（来自 settings.json 和插件）。

### 多 Agent 协调（`src/openharness/coordinator/`、`src/openharness/swarm/`、`src/openharness/tasks/`）

- **`coordinator/`** — 子 agent 生成的核心逻辑。`agent_definitions.py` 定义可用的 agent 类型，`coordinator_mode.py` 提供协调器上下文（当前 worker 的工具上下文等）。子 agent 通过 `Agent` 工具创建，每个子 agent 运行在独立的无头 worker 进程（`oh --task-worker`）中
- **`swarm/`** — 更高级的 swarm 协调原语，支持多 agent 编队
- **`tasks/`** — 后台任务管理，包括任务队列、状态追踪、输出捕获

### UI 层（`src/openharness/ui/`）

两套 TUI 后端：

- **React/Ink**（主 UI，默认）—— Node.js 进程由 `react_launcher.py` 启动，通过 stdin/stdout 走 JSON-RPC 协议（`protocol.py` 定义消息格式）与 Python 后端通信。前端代码在 `frontend/terminal/src/`（React + Ink 渲染终端 UI）
  - `backend_host.py` — Python 端的结构化后端 host，处理来自前端的事件
  - `permission_dialog.py` / `input.py` / `output.py` — TUI 中的交互组件逻辑
- **Textual**（回退 UI）—— Python 原生 TUI，在 `textual_app.py` 中。当无法启动 Node.js 时自动回退到此

`runtime.py` 中的 `RuntimeBundle` 是整个运行时上下文的容器——把 settings、API client、工具注册表、技能注册表、插件列表、MCP 服务器、hook executor、权限检查器全部组装好，交给 UI 层消费。

### 配置系统（`src/openharness/config/`）

- **`settings.py`** — `Settings` pydantic 模型，包含所有可配置项。配置优先级：CLI 参数 > 环境变量（`ANTHROPIC_API_KEY`、`OPENHARNESS_MODEL` 等）> `~/.openharness/settings.json` > 硬编码默认值。`AuthManager`（`auth/manager.py`）管理 provider profile，支持 profile 级别的凭证绑定
- **`paths.py`** — 统一管理各数据目录路径（配置、日志、缓存等）
- **`schema.py`** — 配置文件的 JSON Schema 定义

关键子模块：
- **`auth/`** — 多 provider 认证流程（API key、OAuth device flow、外部 CLI 凭证绑定）
- **`api/`** — LLM provider 客户端实现（Anthropic、OpenAI 兼容、Copilot、Codex CLI 桥接、Moonshot/Kimi、DashScope 等）

### 沙箱（`src/openharness/sandbox/`）

基于 Docker 的执行沙箱：

- **`adapter.py`** — 工具调用代理层，把 Bash/Read/Write/Edit 等操作转发到容器内执行，同时验证路径不会逃逸
- **`session.py`** — 容器生命周期管理（创建、启动、停止、清理）
- **`docker_backend.py`** / **`docker_image.py`** — Docker 后端实现和镜像管理
- **`path_validator.py`** — 路径安全校验，防止沙箱逃逸

### Ohmo 个人 Agent（`ohmo/`）

ohmo 是基于 harness 构建的独立应用，有自己的工作区（`~/.ohmo/`）：

- `soul.md` — agent 长期性格和行为定义
- `identity.md` — agent 身份
- `user.md` — 用户画像和偏好
- `BOOTSTRAP.md` — 首次运行的引导语
- `memory/` — 个人记忆存储
- `gateway.json` — provider 和渠道配置

`ohmo/gateway/` 包含 gateway 服务实现，负责连接 IM 渠道（飞书、Slack、Telegram、Discord）和 agent 之间的消息路由。

### 关键共享类型

- **`ConversationMessage`**（`engine/messages.py`）—— 标准化消息结构，内容为 block 列表：`TextBlock`（纯文本）、`ToolUseBlock`（工具调用）、`ToolResultBlock`（工具返回结果）、`ImageBlock`（多模态图片）
- **`StreamEvent`** 及其子类（`engine/stream_events.py`）—— 一次查询回合中产生的所有事件的类型化表示
- **`ToolExecutionContext`** / **`ToolResult`**（`tools/base.py`）—— 工具执行的共享上下文和结果约定

## 代码规范

- 行长度上限：100（ruff 配置）
- Python 目标版本：3.11（ruff + mypy 统一设定）
- 所有工具输入使用 Pydantic v2 模型校验
- 全程异步——所有工具执行和 API 调用均为 `async`
- 所有源文件开头必须有 `from __future__ import annotations`
- 测试文件与源码模块一一对应，放在 `tests/` 下同名子目录
- E2E 测试脚本放在 `scripts/` 目录，使用真实 LLM 调用，标记 `@pytest.mark.real_model`
