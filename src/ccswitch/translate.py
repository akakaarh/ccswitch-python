import logging
from typing import Any

logger = logging.getLogger(__name__)

CONTENT_TYPE_MAP = {
    "input_text": "text",
    "output_text": "text",
}


def translate_content(content: Any) -> Any:
    """Translate Responses API content to Chat Completions format."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return content
    result = []
    for part in content:
        if not isinstance(part, dict):
            result.append(part)
            continue
        new_part = dict(part)
        old_type = part.get("type")
        if old_type in CONTENT_TYPE_MAP:
            new_part["type"] = CONTENT_TYPE_MAP[old_type]
        result.append(new_part)
    return result


def _append_function_call(messages: list[dict], item: dict) -> None:
    """Append a function_call item to the last assistant message's tool_calls."""
    call_id = item.get("call_id", "")
    name = item.get("name", "")
    arguments = item.get("arguments", "{}")

    tool_call = {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }

    if messages and messages[-1].get("role") == "assistant":
        msg = messages[-1]
        if msg.get("tool_calls") is None:
            msg["tool_calls"] = []
        msg["tool_calls"].append(tool_call)
    else:
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [tool_call],
        })


def translate_messages(items: list[dict]) -> list[dict]:
    """Translate Responses API input items to Chat Completions messages."""
    messages = []
    for item in items:
        item_type = item.get("type")

        if item_type == "message":
            role = item.get("role", "user")
            if role == "developer":
                role = "system"
            messages.append({
                "role": role,
                "content": translate_content(item.get("content")),
            })

        elif item_type in ("function_call", "local_shell_call"):
            _append_function_call(messages, item)

        elif item_type in ("function_call_output", "local_shell_call_output", "custom_tool_call_output"):
            call_id = item.get("call_id") or item.get("id", "")
            output = item.get("output", "")
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": translate_content(output) if isinstance(output, list) else output,
            })

        else:
            logger.warning("Unknown input item type: %s, skipping", item_type)

    return messages


def translate_tools(tools: list[dict] | None) -> list[dict] | None:
    """Convert Responses API flat tool defs to Chat Completions nested format."""
    if not tools:
        return tools
    result = []
    for tool in tools:
        if tool.get("type") != "function":
            continue
        result.append({
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {}),
            },
        })
    return result


def translate_request(body: dict, config: Any) -> dict:
    """Convert a full Responses API request to Chat Completions format."""
    messages = []

    # Instructions → system message
    instructions = body.get("instructions")
    if instructions:
        messages.append({"role": "system", "content": instructions})

    # Input → messages
    raw_input = body.get("input", [])
    if isinstance(raw_input, str):
        raw_input = [{"type": "message", "role": "user", "content": raw_input}]
    messages.extend(translate_messages(raw_input))

    # Build Chat Completions request
    result = {
        "model": config.default_model,
        "messages": messages,
        "stream": True,
    }

    # Tools
    tools = translate_tools(body.get("tools"))
    if tools:
        result["tools"] = tools

    # Pass-through fields
    for field in ("temperature", "top_p", "tool_choice"):
        if field in body:
            result[field] = body[field]

    # Renamed fields
    if "max_output_tokens" in body:
        result["max_tokens"] = body["max_output_tokens"]

    return result
