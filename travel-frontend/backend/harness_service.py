"""
OpenHarness 运行时服务封装。

负责初始化 OpenHarness 运行时、加载 travel-assistant 插件、
管理会话生命周期、提供流式消息接口。

启动时自动读取 SKILL.md 内容，注入到系统提示中，
使模型无需手动输入 /travel-assistant:travel 即可自动执行旅行规划工作流。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncIterator

from openharness.ui.runtime import build_runtime, start_runtime, close_runtime, RuntimeBundle
from openharness.engine.stream_events import StreamEvent
from openharness.engine.query_engine import QueryEngine
from openharness.permissions.checker import PermissionChecker


class HarnessService:
    """OpenHarness 运行时服务管理器。

    在服务启动时初始化一次，后续每个 WebSocket 会话
    创建独立的 QueryEngine 实例以隔离对话上下文。

    自动加载 travel-assistant 技能内容并注入系统提示，
    前端无需手动输入斜杠命令。
    """

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root or Path(__file__).resolve().parent.parent.parent
        self._bundle: RuntimeBundle | None = None
        self._lock = asyncio.Lock()
        self._skill_content: str = ""
        self._mcp_tool_hints: str = ""

    # ------------------------------------------------------------------
    # 技能内容加载
    # ------------------------------------------------------------------

    def _load_skill_content(self) -> str:
        """读取 travel-assistant 的 SKILL.md 内容。"""
        skill_path = (
            self.project_root
            / ".openharness"
            / "plugins"
            / "travel-assistant"
            / "skills"
            / "travel-assistant"
            / "SKILL.md"
        )
        if skill_path.exists():
            content = skill_path.read_text(encoding="utf-8")
            # 去掉 YAML frontmatter（--- 之间的内容）
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip()
            print(f"[HarnessService] 已加载技能内容 ({len(content)} 字符)")
            return content
        print(f"[HarnessService] [WARN] 未找到 SKILL.md: {skill_path}")
        return ""

    def _build_travel_system_prompt(self, base_prompt: str) -> str:
        """构建包含旅行助手工作流的自定义系统提示。

        使用 multi-agent 架构：travel-coordinator 作为调度者，
        并行启动 service-searcher、route-planner、local-guide 三个子 Agent，
        各自使用专属 MCP 工具查询，最后由 coordinator 汇总报告。
        """
        if not self._skill_content:
            return base_prompt

        tool_hints = self._mcp_tool_hints

        travel_instructions = f"""

---
# 铁律（违反复核）

你只能做这三件事，不能做别的：
1. 调 `parse_travel_preferences` 解析偏好
2. 同一轮并行发出 3 个 `agent` 调用（抄下面模板）
3. 等子 Agent 全部完成后，用 `task_output` 读结果 → 汇总报告

**你没有 mcp__ 工具！所有 mcp__ 开头的工具都在子 Agent 手里，你调不了！**
**禁止直接调 mcp__gaode__* / mcp__tuniu-travel__* / mcp__mcp_12306-mcp__* 等等！**
**禁止 web_search！禁止在调 agent 之前自己去查天气/酒店/火车票！**

## agent 调用模板（直接抄，改 {{}} 部分）

第一轮（parse_travel_preferences 之后立即发出，不要做别的事）：

agent(description="搜索酒店机票火车票", subagent_type="travel-assistant:service-searcher",
prompt="目的地：{{destination}}，出发地：{{origin}}，日期：{{date_start}}至{{date_end}}。人数：{{travelers}}，偏好：{{preference}}。1)途牛hotel_search搜酒店→hotel_detail查top2 2)途牛flight_search搜机票→flight_cabin_detail查top2 3)12306 get-stations-code-in-city(出发+目的两城)→get-tickets(limitedNum=5)。余票房态不能留空。")

agent(description="规划路线和天气", subagent_type="travel-assistant:route-planner",
prompt="从{{origin}}到{{destination}}，日期{{date_start}}，偏好{{preference}}。查路线距离耗时+天气。")

agent(description="搜索美食景点门票", subagent_type="travel-assistant:local-guide",
prompt="推荐{{destination}} Top5美食和Top5景点。收费景点用mcp__tuniu-travel__ticket_query查门票价。")

## 报告模板
```
# 🧳 {{destination}}出行方案
## 📋 行程概览 | 出发地→目的地 / 日期 / 天数 / 人数 / 偏好
## 🏨 酒店推荐（附途牛 hotel_create_order 预订方式）
## 🚄✈️ 交通方案（火车票附 https://www.12306.cn，机票附途牛 flight_save_order）
## 🎯 景点门票 | 🍜 美食推荐
## 💡 推荐组合方案（酒店+交通+门票=总价，表格）
```
每条标注余票/房态，不能留空（无数据写"暂无"）。
"""
        return base_prompt + travel_instructions

    # ------------------------------------------------------------------
    # MCP 连接诊断 + 动态工具提示
    # ------------------------------------------------------------------

    def _diagnose_mcp_connections(self) -> None:
        """输出 MCP 服务器连接状态诊断信息。"""
        if self._bundle is None:
            return
        mcp_manager = self._bundle.mcp_manager
        statuses = mcp_manager.list_statuses()
        print("[HarnessService] --- MCP 连接状态 ---")
        for status in statuses:
            icon = "[OK]" if status.state == "connected" else "[FAIL]"
            detail = f" - {status.detail}" if status.detail else ""
            print(f"  {icon} {status.name}: {status.state}{detail}")
        connected = sum(1 for s in statuses if s.state == "connected")
        failed = sum(1 for s in statuses if s.state == "failed")
        print(f"[HarnessService] MCP 总计: {connected} 已连接 / {failed} 失败 / {len(statuses)} 总数")

    def _build_dynamic_tool_hints(self) -> str:
        """根据实际注册的 MCP 工具动态生成工具名提示。

        遍历工具注册表，找出所有 mcp__ 开头的工具，
        按 MCP 服务器分组生成提示，确保工具名与实际注册名完全一致。
        """
        if self._bundle is None:
            return ""

        registry = self._bundle.tool_registry
        # 收集所有 mcp__ 开头的工具，按服务器名分组
        mcp_tools: dict[str, list[tuple[str, str]]] = {}  # server_name -> [(tool_full_name, description)]
        for tool_instance in registry.list_tools():
            tool_name = tool_instance.name
            if not tool_name.startswith("mcp__"):
                continue
            # 工具名格式: mcp__<server>__<tool>
            parts = tool_name.split("__", 1)
            server_name = parts[1] if len(parts) > 1 else "unknown"
            # 进一步拆分 server 和 tool 名
            if "__" in server_name:
                server, _tool = server_name.rsplit("__", 1)
            else:
                server = server_name
            desc = getattr(tool_instance, "description", "") or ""
            # 截断描述（只取第一句）
            desc_short = desc.split("。")[0].split(".")[0][:80]
            if server not in mcp_tools:
                mcp_tools[server] = []
            mcp_tools[server].append((tool_name, desc_short))

        if not mcp_tools:
            return (
                "\n[⚠️ 警告] 当前没有可用的 MCP 工具！\n"
                "请检查 MCP 服务器配置（mcp.json）和依赖是否安装。\n"
                "在此状态下，请基于模型常识回答问题，不要尝试调用 MCP 工具。\n"
            )

        lines = [
            "\n[可用 MCP 工具清单 — 必须使用以下确切名称调用，不得编造]\n",
        ]
        for server, tools in sorted(mcp_tools.items()):
            lines.append(f"## {server}")
            for tool_name, desc in tools:
                lines.append(f"  - {tool_name}: {desc}")
        lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 运行时生命周期
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """初始化 OpenHarness 运行时（启动时调用一次）。"""
        async with self._lock:
            if self._bundle is not None:
                return

            # 1. 加载技能内容
            self._skill_content = self._load_skill_content()

            plugin_root = str(
                self.project_root / ".openharness" / "plugins" / "travel-assistant"
            )

            print(f"[HarnessService] 正在初始化 OpenHarness 运行时...")
            print(f"[HarnessService] 项目根目录: {self.project_root}")
            print(f"[HarnessService] 插件目录: {plugin_root}")

            # 2. 构建运行时（先不用自定义 system_prompt，
            #    因为 build_runtime 内部会调用 build_runtime_system_prompt，
            #    我们在 create_session_engine 时再注入旅行助手指令）
            self._bundle = await build_runtime(
                cwd=str(self.project_root),
                extra_plugin_roots=(plugin_root,),
                permission_mode="full_auto",
                max_turns=50,
            )
            await start_runtime(self._bundle)
            print(f"[HarnessService] 运行时初始化完成，模型: {self._bundle.engine.model}")

            # 3. 诊断 MCP 连接状态
            self._diagnose_mcp_connections()

            # 4. 构建动态工具提示
            self._mcp_tool_hints = self._build_dynamic_tool_hints()

    async def create_session_engine(self) -> QueryEngine:
        """为新的 WebSocket 会话创建独立的 QueryEngine。

        复用已初始化的 tool_registry、api_client、permission_checker 等，
        但使用独立的对话历史和上下文。
        系统提示会被注入旅行助手工作流指令。
        """
        if self._bundle is None:
            await self.initialize()

        bundle = self._bundle
        settings = bundle.current_settings()

        # 注入旅行助手指令到系统提示
        custom_system_prompt = self._build_travel_system_prompt(
            bundle.engine.system_prompt
        )

        engine = QueryEngine(
            api_client=bundle.api_client,
            tool_registry=bundle.tool_registry,
            permission_checker=PermissionChecker(settings.permission),
            cwd=bundle.cwd,
            model=bundle.engine.model,
            system_prompt=custom_system_prompt,
            max_tokens=8192,
            max_turns=50,
            hook_executor=bundle.hook_executor,
            settings=settings,
            tool_metadata={
                "mcp_manager": bundle.mcp_manager,
                "extra_skill_dirs": (),
                "extra_plugin_roots": bundle.extra_plugin_roots,
                "session_id": bundle.session_id,
                "permission_mode": "full_auto",
                "read_file_state": [],
                "invoked_skills": ["travel-assistant"],
            },
        )
        return engine

    async def submit_message(
        self, engine: QueryEngine, prompt: str
    ) -> AsyncIterator[StreamEvent]:
        """提交用户消息到指定引擎并流式返回事件。"""
        async for event in engine.submit_message(prompt):
            yield event

    async def shutdown(self) -> None:
        """关闭 OpenHarness 运行时（带超时保护，避免 MCP 断开卡住）。"""
        if self._bundle is None:
            return
        print("[HarnessService] 正在关闭运行时...")
        try:
            await asyncio.wait_for(close_runtime(self._bundle), timeout=5.0)
        except asyncio.TimeoutError:
            print("[HarnessService] [WARN] 关闭超时（5s），强制退出")
        except asyncio.CancelledError:
            print("[HarnessService] [WARN] 关闭被取消（MCP 清理异常），已忽略")
        except Exception as e:
            print(f"[HarnessService] [WARN] 关闭时出错（已忽略）: {e}")
        finally:
            self._bundle = None
            print("[HarnessService] 运行时已关闭")

    @property
    def is_ready(self) -> bool:
        """运行时是否已初始化完成。"""
        return self._bundle is not None


# 全局单例
harness_service = HarnessService()
