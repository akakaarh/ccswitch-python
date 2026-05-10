import json
import pytest
from ccswitch.sse import SseTranslator


def parse_sse_events(raw: str) -> list[tuple[str, dict]]:
    """Parse raw SSE text into list of (event_type, data_dict)."""
    events = []
    current_event = None
    for line in raw.split("\n"):
        if line.startswith("event: "):
            current_event = line[len("event: "):]
        elif line.startswith("data: "):
            data = json.loads(line[len("data: "):])
            events.append((current_event, data))
    return events


@pytest.mark.asyncio
async def test_text_streaming():
    translator = SseTranslator(response_id="resp_1", model="gpt-4o")

    lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12}}',
        "data: [DONE]",
    ]

    all_events = []
    for line in lines:
        events = await translator.feed(line)
        all_events.extend(events)

    done_events = await translator.done()
    all_events.extend(done_events)

    raw = "".join(all_events)
    parsed = parse_sse_events(raw)

    event_types = [e[0] for e in parsed]
    assert "response.created" in event_types
    assert "response.in_progress" in event_types
    assert "response.output_item.added" in event_types
    assert "response.content_part.added" in event_types
    assert "response.output_text.delta" in event_types
    assert "response.output_text.done" in event_types
    assert "response.content_part.done" in event_types
    assert "response.output_item.done" in event_types
    assert "response.completed" in event_types

    deltas = [e[1]["delta"] for e in parsed if e[0] == "response.output_text.delta"]
    assert deltas == ["Hello", " world"]

    text_done = [e for e in parsed if e[0] == "response.output_text.done"][0]
    assert text_done[1]["text"] == "Hello world"


@pytest.mark.asyncio
async def test_tool_call_streaming():
    translator = SseTranslator(response_id="resp_2", model="gpt-4o")

    lines = [
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_123","function":{"name":"get_weather","arguments":""}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"city\\":"}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"Beijing\\"}"}}]}}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
        "data: [DONE]",
    ]

    all_events = []
    for line in lines:
        events = await translator.feed(line)
        all_events.extend(events)
    done_events = await translator.done()
    all_events.extend(done_events)

    raw = "".join(all_events)
    parsed = parse_sse_events(raw)

    event_types = [e[0] for e in parsed]
    assert "response.output_item.added" in event_types
    assert "response.function_call_arguments.delta" in event_types
    assert "response.function_call_arguments.done" in event_types
    assert "response.output_item.done" in event_types
    assert "response.completed" in event_types

    args_done = [e for e in parsed if e[0] == "response.function_call_arguments.done"][0]
    assert args_done[1]["arguments"] == '{"city":"Beijing"}'

    item_done = [e for e in parsed if e[0] == "response.output_item.done"][0]
    assert item_done[1]["item"]["name"] == "get_weather"
    assert item_done[1]["item"]["call_id"] == "call_123"


@pytest.mark.asyncio
async def test_empty_stream():
    translator = SseTranslator(response_id="resp_3", model="gpt-4o")
    done_events = await translator.done()
    raw = "".join(done_events)
    parsed = parse_sse_events(raw)
    event_types = [e[0] for e in parsed]
    assert "response.completed" in event_types
    completed = [e for e in parsed if e[0] == "response.completed"][0]
    assert completed[1]["response"]["output"] == []
