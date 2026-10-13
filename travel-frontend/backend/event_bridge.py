"""
StreamEvent → WebSocket JSON 消息转换器。

将 OpenHarness 引擎产生的 StreamEvent 转换为前端可消费的 JSON 格式，
增加对子 Agent 启停、思考阶段的语义标注。
"""

from __future__ import annotations

import json
from typing import Any

from openharness.engine.stream_events import (
    StreamEvent,
    AssistantTextDelta,
    AssistantTurnComplete,
    ToolExecutionStarted,
    ToolExecutionCompleted,
    ErrorEvent,
    StatusEvent,
    CompactProgressEvent,
)


def _serialize_value(value: Any) -> Any:
    """将工具输入/输出中的复杂对象转为可 JSON 序列化的格式。"""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    return str(value)


def _truncate_output(output: str, max_length: int = 2000) -> str:
    """截断过长的工具输出，避免 WebSocket 消息过大。"""
    if len(output) > max_length:
        return output[:max_length] + f"\n... [已截断，原长度 {len(output)} 字符]"
    return output


def stream_event_to_message(
    event: StreamEvent, turn: int = 0
) -> dict[str, Any] | None:
    """将单个 StreamEvent 转换为 WebSocket JSON 消息。

    返回 None 表示该事件无需发送给前端。
    """

    # --- 流式文本增量 ---
    if isinstance(event, AssistantTextDelta):
        text = event.text
        if not text:
            return None
        return {
            "type": "text_delta",
            "content": text,
            "turn": turn,
        }

    # --- 工具调用开始 ---
    if isinstance(event, ToolExecutionStarted):
        tool_name = event.tool_name
        tool_input = _serialize_value(event.tool_input)

        # 检测 Agent 工具调用 → 子 Agent 启动
        if tool_name == "agent":
            sub_agent_name = _extract_agent_name(tool_input)
            return {
                "type": "agent_start",
                "agent_name": sub_agent_name,
                "tool_name": tool_name,
                "input": tool_input,
                "turn": turn,
            }

        # 检测 Skill 工具调用
        if tool_name == "skill":
            skill_name = tool_input.get("name", "unknown") if isinstance(tool_input, dict) else str(tool_input)
            return {
                "type": "thinking",
                "stage": "skill_load",
                "content": f"正在加载技能: {skill_name}",
                "tool_name": tool_name,
                "turn": turn,
            }

        return {
            "type": "tool_start",
            "tool_name": tool_name,
            "input": tool_input,
            "turn": turn,
        }

    # --- 工具调用完成 ---
    if isinstance(event, ToolExecutionCompleted):
        tool_name = event.tool_name
        output = _truncate_output(event.output or "")
        is_error = event.is_error

        # 检测 Agent 工具完成 → 子 Agent 结束
        if tool_name == "agent":
            return {
                "type": "agent_end",
                "tool_name": tool_name,
                "summary": output[:500] if output else "",
                "is_error": is_error,
                "turn": turn,
            }

        # Skill 加载完成
        if tool_name == "skill":
            return {
                "type": "thinking",
                "stage": "skill_loaded",
                "content": "技能加载完成，开始执行...",
                "tool_name": tool_name,
                "turn": turn,
            }

        status = "error" if is_error else "done"
        return {
            "type": "tool_end",
            "tool_name": tool_name,
            "output": output,
            "is_error": is_error,
            "status": status,
            "turn": turn,
        }

    # --- 回合完成 ---
    if isinstance(event, AssistantTurnComplete):
        usage = event.usage
        return {
            "type": "turn_complete",
            "usage": {
                "input_tokens": usage.input_tokens if usage else 0,
                "output_tokens": usage.output_tokens if usage else 0,
            },
            "turn": turn,
        }

    # --- 错误事件 ---
    if isinstance(event, ErrorEvent):
        return {
            "type": "error",
            "message": event.message,
            "recoverable": event.recoverable,
        }

    # --- 状态事件（转为 thinking 类型）---
    if isinstance(event, StatusEvent):
        return {
            "type": "thinking",
            "stage": "status",
            "content": event.message,
        }

    # --- 压缩进度事件（转为 thinking 类型）---
    if isinstance(event, CompactProgressEvent):
        return {
            "type": "thinking",
            "stage": "compact",
            "content": event.message,
        }

    return None


def _extract_agent_name(tool_input: dict[str, Any]) -> str:
    """从 Agent 工具的输入参数中提取子 Agent 名称。"""
    if isinstance(tool_input, dict):
        # agent_type 或 type 字段通常包含 agent 名称
        for key in ("agent_type", "type", "name", "subagent_type"):
            if key in tool_input:
                return str(tool_input[key])
        # description 字段包含任务描述，取前 30 字符
        if "description" in tool_input:
            desc = str(tool_input["description"])
            return desc[:30] + ("..." if len(desc) > 30 else "")
    return "unknown"
