import json
import logging
import uuid

logger = logging.getLogger(__name__)


def _sse(event_type: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


class SseTranslator:
    """Translates Chat Completions SSE to Responses API SSE."""

    def __init__(self, response_id: str | None = None, model: str = "unknown"):
        self.response_id = response_id or f"resp_{uuid.uuid4().hex[:12]}"
        self.model = model
        self._started = False
        self._state = "IDLE"  # IDLE | TEXT | TOOL_CALL | DONE
        self._output_index = 0
        self._output_items: list[dict] = []
        self._current_text = ""
        self._current_item_id = ""
        self._current_tool_calls: dict[int, dict] = {}
        self._usage: dict | None = None
        self._item_id_counter = 0

    def _next_item_id(self, prefix: str = "msg") -> str:
        self._item_id_counter += 1
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    def _ensure_started(self) -> list[str]:
        if self._started:
            return []
        self._started = True
        resp = self._make_response("in_progress")
        return [
            _sse("response.created", {"type": "response.created", "response": resp}),
            _sse("response.in_progress", {"type": "response.in_progress", "response": resp}),
        ]

    def _make_response(self, status: str) -> dict:
        return {
            "id": self.response_id,
            "object": "response",
            "status": status,
            "model": self.model,
            "output": list(self._output_items),
            "usage": self._usage or {},
        }

    async def feed(self, line: str) -> list[str]:
        """Process one SSE line from Chat Completions stream."""
        line = line.strip()
        if not line:
            return []
        if line == "data: [DONE]":
            return []

        if not line.startswith("data: "):
            return []

        try:
            chunk = json.loads(line[6:])
        except json.JSONDecodeError:
            logger.warning("Failed to parse SSE chunk: %s", line)
            return []

        if "usage" in chunk:
            self._usage = chunk["usage"]

        choices = chunk.get("choices", [])
        if not choices:
            return []

        delta = choices[0].get("delta", {})
        finish_reason = choices[0].get("finish_reason")

        events = []

        if "content" in delta and delta["content"]:
            events.extend(self._handle_text_delta(delta["content"]))

        if "tool_calls" in delta:
            events.extend(self._handle_tool_calls_delta(delta["tool_calls"]))

        if finish_reason:
            events.extend(self._flush_on_finish(finish_reason))

        return events

    def _handle_text_delta(self, text: str) -> list[str]:
        events = self._ensure_started()

        if self._state != "TEXT":
            events.extend(self._flush_tool_calls())
            self._state = "TEXT"
            self._current_text = ""
            item_id = self._next_item_id("msg")
            self._current_item_id = item_id
            item = {"type": "message", "id": item_id, "status": "in_progress", "role": "assistant", "content": []}
            events.append(_sse("response.output_item.added", {"type": "response.output_item.added", "output_index": self._output_index, "item": item}))
            events.append(_sse("response.content_part.added", {"type": "response.content_part.added", "item_id": item_id, "output_index": self._output_index, "content_index": 0, "part": {"type": "output_text", "text": "", "annotations": []}}))

        self._current_text += text
        events.append(_sse("response.output_text.delta", {"type": "response.output_text.delta", "item_id": self._current_item_id, "output_index": self._output_index, "content_index": 0, "delta": text}))
        return events

    def _handle_tool_calls_delta(self, tool_calls: list[dict]) -> list[str]:
        events = self._ensure_started()

        for tc in tool_calls:
            idx = tc.get("index", 0)
            if idx not in self._current_tool_calls:
                events.extend(self._flush_text())
                self._state = "TOOL_CALL"
                item_id = self._next_item_id("fc")
                self._current_tool_calls[idx] = {
                    "id": tc.get("id", ""),
                    "name": tc.get("function", {}).get("name", ""),
                    "arguments": "",
                    "item_id": item_id,
                    "added_emitted": False,
                }

            call = self._current_tool_calls[idx]

            if tc.get("id"):
                call["id"] = tc["id"]
            if tc.get("function", {}).get("name"):
                call["name"] = tc["function"]["name"]
            args_delta = tc.get("function", {}).get("arguments", "")
            if args_delta:
                call["arguments"] += args_delta
                if not call["added_emitted"]:
                    call["added_emitted"] = True
                    item = {"type": "function_call", "id": call["item_id"], "call_id": call["id"], "name": call["name"], "arguments": "", "status": "in_progress"}
                    events.append(_sse("response.output_item.added", {"type": "response.output_item.added", "output_index": self._output_index, "item": item}))
                events.append(_sse("response.function_call_arguments.delta", {"type": "response.function_call_arguments.delta", "item_id": call["item_id"], "output_index": self._output_index, "delta": args_delta}))

        return events

    def _flush_text(self) -> list[str]:
        if self._state != "TEXT":
            return []
        events = []
        events.append(_sse("response.output_text.done", {"type": "response.output_text.done", "item_id": self._current_item_id, "output_index": self._output_index, "content_index": 0, "text": self._current_text}))
        events.append(_sse("response.content_part.done", {"type": "response.content_part.done", "item_id": self._current_item_id, "output_index": self._output_index, "content_index": 0, "part": {"type": "output_text", "text": self._current_text, "annotations": []}}))
        item = {"type": "message", "id": self._current_item_id, "status": "completed", "role": "assistant", "content": [{"type": "output_text", "text": self._current_text, "annotations": []}]}
        events.append(_sse("response.output_item.done", {"type": "response.output_item.done", "output_index": self._output_index, "item": item}))
        self._output_items.append(item)
        self._output_index += 1
        self._current_text = ""
        self._state = "IDLE"
        return events

    def _flush_tool_calls(self) -> list[str]:
        if self._state != "TOOL_CALL":
            return []
        events = []
        for idx in sorted(self._current_tool_calls.keys()):
            call = self._current_tool_calls[idx]
            if not call["added_emitted"]:
                call["added_emitted"] = True
                item = {"type": "function_call", "id": call["item_id"], "call_id": call["id"], "name": call["name"], "arguments": call["arguments"], "status": "in_progress"}
                events.append(_sse("response.output_item.added", {"type": "response.output_item.added", "output_index": self._output_index, "item": item}))
            events.append(_sse("response.function_call_arguments.done", {"type": "response.function_call_arguments.done", "item_id": call["item_id"], "output_index": self._output_index, "arguments": call["arguments"]}))
            item = {"type": "function_call", "id": call["item_id"], "call_id": call["id"], "name": call["name"], "arguments": call["arguments"], "status": "completed"}
            events.append(_sse("response.output_item.done", {"type": "response.output_item.done", "output_index": self._output_index, "item": item}))
            self._output_items.append(item)
            self._output_index += 1
        self._current_tool_calls.clear()
        self._state = "IDLE"
        return events

    def _flush_on_finish(self, finish_reason: str) -> list[str]:
        if finish_reason == "stop":
            return self._flush_text()
        elif finish_reason == "tool_calls":
            return self._flush_tool_calls()
        return []

    async def done(self) -> list[str]:
        """Called after stream ends. Emits response.completed."""
        events = []
        events.extend(self._flush_text())
        events.extend(self._flush_tool_calls())
        resp = self._make_response("completed")
        events.append(_sse("response.completed", {"type": "response.completed", "response": resp}))
        self._state = "DONE"
        return events
