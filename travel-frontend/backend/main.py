"""
旅行助手 Web 服务入口。

提供 FastAPI + WebSocket 端点，接收前端对话消息，
调用 OpenHarness 引擎进行流式响应。
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# Windows 控制台 GBK 编码兼容：强制使用 UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# 确保 openharness 源码在 Python 路径中
_OH_SRC = Path(__file__).resolve().parent.parent.parent / "src"
if _OH_SRC.exists() and str(_OH_SRC) not in sys.path:
    sys.path.insert(0, str(_OH_SRC))

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from harness_service import harness_service
from event_bridge import stream_event_to_message

# 加载 .env 文件
load_dotenv()

# 项目根目录（travel-frontend 的父目录，即 .openharness 所在目录）
PROJECT_ROOT = Path(
    os.getenv("PROJECT_ROOT", Path(__file__).resolve().parent.parent.parent)
)


# --- FastAPI 生命周期 ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的生命周期管理。"""
    # 启动：初始化 OpenHarness 运行时
    print("=" * 60)
    print("[Harness] 智能旅行助手后端服务启动中...")
    print("=" * 60)
    try:
        await harness_service.initialize()
        print("[OK] OpenHarness 运行时就绪")
    except Exception as e:
        print(f"[WARN] OpenHarness 初始化失败: {e}")
        print("   服务将以降级模式运行（模拟响应）")
        traceback.print_exc()
    yield
    # 关闭：清理资源
    await harness_service.shutdown()
    print("[OK] 服务已关闭")


# --- FastAPI 应用 ---

app = FastAPI(
    title="智能旅行助手 API",
    description="基于 OpenHarness 多 Agent 框架的出行规划服务",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置（允许前端开发服务器跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 辅助函数 ---


def _safe_str(value: Any) -> str:
    """安全地将表单值转为字符串（处理 int/None/str 等类型）。"""
    if value is None:
        return ""
    return str(value).strip()


def build_travel_prompt(message: str, form_data: dict[str, Any] | None = None, tool_hints: str = "") -> str:
    """根据用户消息和表单数据构建完整的旅行规划 prompt。

    如果有表单数据，将其拼接到自然语言描述中；
    如果表单数据完整，直接生成结构化请求；
    否则透传用户原始消息。

    tool_hints: 来自 HarnessService 的动态 MCP 工具清单，
    确保模型使用的工具名与实际注册完全一致。
    """
    if not form_data:
        return message

    # 检查表单是否有关键信息
    has_departure = _safe_str(form_data.get("departure"))
    has_destination = _safe_str(form_data.get("destination"))

    if not has_departure and not has_destination:
        # 表单基本为空，直接使用消息
        return message

    # 构建结构化 prompt
    parts: list[str] = []

    # 出发地和目的地
    if has_departure and has_destination:
        parts.append(f"从{has_departure}到{has_destination}")
    elif has_destination:
        parts.append(f"去{has_destination}")

    # 日期
    date = _safe_str(form_data.get("date"))
    if date:
        parts.append(f"出发日期{date}")

    # 天数
    days = _safe_str(form_data.get("days"))
    if days:
        parts.append(f"玩{days}天")

    # 人数
    people = _safe_str(form_data.get("people"))
    if people:
        parts.append(f"{people}人")

    # 预算
    budget = _safe_str(form_data.get("budget"))
    if budget:
        parts.append(f"预算{budget}元")

    # 偏好
    preference = _safe_str(form_data.get("preference"))
    if preference:
        pref_map = {
            "comfort": "要舒适的",
            "cheap": "要便宜的",
            "fast": "要最快的",
            "unlimited": "预算不限",
            "balanced": "",
        }
        pref_text = pref_map.get(preference, "")
        if pref_text:
            parts.append(pref_text)

    # 酒店品牌
    hotel_brand = _safe_str(form_data.get("hotel_brand"))
    if hotel_brand:
        parts.append(f"偏好{hotel_brand}酒店")

    # 酒店位置偏好（自由文本，直接拼接）
    hotel_location = _safe_str(form_data.get("hotel_location"))
    if hotel_location:
        parts.append(f"酒店位置要求：{hotel_location}")

    # 拼接基础 prompt
    base_prompt = "，".join(parts) + "。"

    # 如果用户还有额外描述，追加
    if message.strip() and message.strip() != base_prompt.strip("。"):
        base_prompt += f" 额外要求：{message}"

    # 在 prompt 前面注入动态工具名（基于实际注册的工具，确保名称完全匹配）
    if tool_hints:
        tool_reminder = (
            "[工具名清单 - 必须原样使用以下确切名称，不要编造]\n"
            f"{tool_hints}\n"
        )
    else:
        # 降级：没有 MCP 工具时的提示
        tool_reminder = (
            "[⚠️ 当前无可用的 MCP 工具]\n"
            "请基于你的常识给出旅行建议，标注以下为参考信息，建议访问 12306.cn / tuniu.com 查询实时数据\n\n"
        )
    return tool_reminder + base_prompt


# --- HTTP 端点 ---


@app.get("/health")
async def health_check():
    """健康检查端点。"""
    return {
        "status": "ok",
        "harness_ready": harness_service.is_ready,
    }


@app.get("/api/status")
async def api_status():
    """获取服务状态详情。"""
    if not harness_service.is_ready:
        return {
            "status": "initializing",
            "model": "N/A",
            "message": "OpenHarness 运行时尚未就绪",
        }

    bundle = harness_service._bundle
    return {
        "status": "ready",
        "model": bundle.engine.model if bundle else "N/A",
        "session_id": bundle.session_id if bundle else "N/A",
    }


# --- WebSocket 端点 ---


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket 连接端点。

    每个连接创建一个独立的 QueryEngine 会话，
    支持多轮对话，对话历史在连接期间保持。
    """
    await ws.accept()
    print(f"[WebSocket] 新连接: {ws.client}")

    # 创建独立会话引擎
    engine = None
    if harness_service.is_ready:
        try:
            engine = await harness_service.create_session_engine()
            print(f"[WebSocket] 会话引擎已创建")
        except Exception as e:
            print(f"[WebSocket] 创建会话引擎失败: {e}")
            traceback.print_exc()
            await ws.send_json({
                "type": "error",
                "message": f"创建 AI 会话失败: {e}",
            })

    # 发送连接确认
    await ws.send_json({
        "type": "status",
        "content": "ready" if engine else "degraded",
        "message": "连接成功，可以开始对话" if engine else "AI 服务未就绪，将使用模拟响应",
    })

    turn_count = 0

    try:
        while True:
            # 接收前端消息
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({
                    "type": "error",
                    "message": "消息格式错误，请发送有效的 JSON",
                })
                continue

            msg_type = data.get("type", "chat")
            if msg_type != "chat":
                continue

            message = data.get("message", "").strip()
            form_data = data.get("form_data", None)

            if not message and not form_data:
                await ws.send_json({
                    "type": "error",
                    "message": "请输入出行需求或填写出行信息",
                })
                continue

            # 构建 prompt（传入动态 MCP 工具清单）
            prompt = build_travel_prompt(
                message, form_data,
                tool_hints=harness_service._mcp_tool_hints if harness_service.is_ready else "",
            )
            print(f"[WebSocket] 收到消息: {prompt[:100]}...")

            turn_count += 1

            if engine is not None:
                # === 真实 OpenHarness 引擎模式 ===
                try:
                    async for event in harness_service.submit_message(engine, prompt):
                        msg = stream_event_to_message(event, turn=turn_count)
                        if msg is not None:
                            await ws.send_json(msg)
                except Exception as e:
                    print(f"[WebSocket] 引擎错误: {e}")
                    traceback.print_exc()
                    await ws.send_json({
                        "type": "error",
                        "message": f"AI 处理出错: {e}",
                    })
            else:
                # === 降级模式：模拟响应（OpenHarness 未就绪时） ===
                await _send_mock_response(ws, prompt, turn_count)

            # 回合结束
            await ws.send_json({
                "type": "done",
                "turn": turn_count,
            })

    except WebSocketDisconnect:
        print(f"[WebSocket] 连接断开: {ws.client}")
    except Exception as e:
        print(f"[WebSocket] 异常: {e}")
        traceback.print_exc()
        try:
            await ws.send_json({
                "type": "error",
                "message": f"服务异常: {e}",
            })
        except Exception:
            pass
    finally:
        # 清理会话引擎（可选：保留以便重连后恢复对话）
        print(f"[WebSocket] 会话结束，共 {turn_count} 轮对话")


async def _send_mock_response(ws: WebSocket, prompt: str, turn: int) -> None:
    """降级模式：发送模拟的旅行规划响应。"""
    import asyncio

    # 模拟思考过程
    await ws.send_json({
        "type": "thinking",
        "stage": "parsing",
        "content": "正在解析出行偏好...",
    })
    await asyncio.sleep(0.3)

    await ws.send_json({
        "type": "tool_start",
        "tool_name": "parse_travel_preferences",
        "input": {"raw_input": prompt},
    })
    await asyncio.sleep(0.2)

    await ws.send_json({
        "type": "tool_end",
        "tool_name": "parse_travel_preferences",
        "output": "偏好类型: 舒适, 检测到目的地",
        "is_error": False,
        "status": "done",
    })

    await ws.send_json({
        "type": "agent_start",
        "agent_name": "service-searcher",
        "task": "搜索酒店和机票...",
    })
    await ws.send_json({
        "type": "agent_start",
        "agent_name": "route-planner",
        "task": "规划路线...",
    })
    await ws.send_json({
        "type": "agent_start",
        "agent_name": "local-guide",
        "task": "搜索美食和景点...",
    })

    await asyncio.sleep(0.5)

    await ws.send_json({
        "type": "agent_end",
        "agent_name": "service-searcher",
        "summary": "找到酒店和交通信息",
        "is_error": False,
    })
    await ws.send_json({
        "type": "agent_end",
        "agent_name": "route-planner",
        "summary": "路线规划完成",
        "is_error": False,
    })
    await ws.send_json({
        "type": "agent_end",
        "agent_name": "local-guide",
        "summary": "美食景点推荐完成",
        "is_error": False,
    })

    # 模拟流式文本输出
    mock_report = """
## 🗺️ 旅行规划报告

### 📋 行程概览
| 项目 | 详情 |
|------|------|
| 出发地 | 自动检测 |
| 目的地 | 自动检测 |
| 行程天数 | 待确认 |
| 出行偏好 | 舒适型 |

### 🏨 酒店推荐
> ⚠️ 当前为离线模式，无法获取实时数据。请确保 OpenHarness 运行时已正确配置。

### 🚄 交通方案
> ⚠️ MCP 服务（途牛/12306/高德）未连接，请在配置后重试。

### 🎯 景点推荐
> ⚠️ 请检查 `.openharness/plugins/travel-assistant/mcp.json` 中的 MCP 服务器配置。

---

💡 **提示**：当前显示的是降级模式响应。要获取真实 AI 规划，请：
1. 确保已安装 `openharness-ai` 包
2. 配置有效的 LLM API Key（`ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY`）
3. 启动并配置 MCP 服务器（途牛/12306/高德）
"""

    # 逐段发送（模拟流式效果）
    chunks = mock_report.split("\n")
    for line in chunks:
        await ws.send_json({
            "type": "text_delta",
            "content": line + "\n",
            "turn": turn,
        })
        await asyncio.sleep(0.05)

    await ws.send_json({
        "type": "turn_complete",
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "turn": turn,
    })


# --- 入口 ---

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8001"))

    print(f"[OK] 启动服务: http://{host}:{port}")
    print(f"[OK] WebSocket: ws://{host}:{port}/ws")
    print(f"[OK] 健康检查: http://{host}:{port}/health")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
