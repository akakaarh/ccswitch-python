from ccswitch.translate import translate_content, translate_messages, translate_tools, translate_request
from ccswitch.config import Config


# --- translate_content ---

def test_translate_content_input_text():
    parts = [{"type": "input_text", "text": "hello"}]
    result = translate_content(parts)
    assert result == [{"type": "text", "text": "hello"}]


def test_translate_content_output_text():
    parts = [{"type": "output_text", "text": "world"}]
    result = translate_content(parts)
    assert result == [{"type": "text", "text": "world"}]


def test_translate_content_string():
    result = translate_content("hello")
    assert result == "hello"


def test_translate_content_passthrough():
    parts = [{"type": "input_image", "image_url": "http://example.com/img.png"}]
    result = translate_content(parts)
    assert result == [{"type": "input_image", "image_url": "http://example.com/img.png"}]


# --- translate_messages ---

def test_translate_user_message():
    items = [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]}]
    result = translate_messages(items)
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert result[0]["content"] == [{"type": "text", "text": "hi"}]


def test_translate_developer_to_system():
    items = [{"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "be good"}]}]
    result = translate_messages(items)
    assert result[0]["role"] == "system"


def test_translate_assistant_message():
    items = [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "ok"}]}]
    result = translate_messages(items)
    assert result[0]["role"] == "assistant"
    assert result[0]["content"] == [{"type": "text", "text": "ok"}]


def test_translate_string_content():
    items = [{"type": "message", "role": "user", "content": "hello"}]
    result = translate_messages(items)
    assert result[0]["content"] == "hello"


def test_translate_no_role_defaults_to_user():
    items = [{"type": "message", "content": [{"type": "input_text", "text": "hi"}]}]
    result = translate_messages(items)
    assert result[0]["role"] == "user"


def test_translate_function_call_appends_to_assistant():
    items = [
        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "let me check"}]},
        {"type": "function_call", "call_id": "call_1", "name": "get_weather", "arguments": '{"city":"Beijing"}'},
    ]
    result = translate_messages(items)
    assert len(result) == 1
    assert result[0]["role"] == "assistant"
    assert len(result[0]["tool_calls"]) == 1
    assert result[0]["tool_calls"][0]["id"] == "call_1"
    assert result[0]["tool_calls"][0]["function"]["name"] == "get_weather"


def test_translate_function_call_creates_assistant_if_needed():
    items = [
        {"type": "function_call", "call_id": "call_1", "name": "search", "arguments": '{"q":"test"}'},
    ]
    result = translate_messages(items)
    assert len(result) == 1
    assert result[0]["role"] == "assistant"
    assert result[0]["content"] is None
    assert result[0]["tool_calls"][0]["id"] == "call_1"


def test_translate_function_call_output():
    items = [
        {"type": "function_call_output", "call_id": "call_1", "output": "sunny"},
    ]
    result = translate_messages(items)
    assert result[0]["role"] == "tool"
    assert result[0]["tool_call_id"] == "call_1"
    assert result[0]["content"] == "sunny"


def test_translate_local_shell_call_output():
    items = [
        {"type": "local_shell_call_output", "id": "shell_1", "output": "file.txt"},
    ]
    result = translate_messages(items)
    assert result[0]["role"] == "tool"
    assert result[0]["tool_call_id"] == "shell_1"


def test_translate_multiple_function_calls():
    items = [
        {"type": "function_call", "call_id": "call_1", "name": "a", "arguments": "{}"},
        {"type": "function_call", "call_id": "call_2", "name": "b", "arguments": "{}"},
    ]
    result = translate_messages(items)
    assert len(result) == 1
    assert len(result[0]["tool_calls"]) == 2


# --- translate_tools ---

def test_translate_tools_flat_to_nested():
    tools = [{"type": "function", "name": "get_weather", "description": "Get weather", "parameters": {"type": "object"}}]
    result = translate_tools(tools)
    assert len(result) == 1
    assert result[0]["type"] == "function"
    assert result[0]["function"]["name"] == "get_weather"
    assert result[0]["function"]["description"] == "Get weather"
    assert result[0]["function"]["parameters"] == {"type": "object"}


def test_translate_tools_filters_non_function():
    tools = [
        {"type": "function", "name": "foo", "description": "d", "parameters": {}},
        {"type": "local_shell"},
        {"type": "file_search", "vector_store_ids": ["vs1"]},
    ]
    result = translate_tools(tools)
    assert len(result) == 1
    assert result[0]["function"]["name"] == "foo"


def test_translate_tools_empty():
    assert translate_tools([]) == []
    assert translate_tools(None) is None


# --- translate_request ---

def make_config(**kwargs):
    defaults = {"api_key": "test", "api_base_url": "http://localhost", "proxy_host": "127.0.0.1", "proxy_port": 11435, "default_model": "gpt-4o-mini"}
    defaults.update(kwargs)
    return Config(**defaults)


def test_translate_request_basic():
    body = {
        "model": "gpt-4o",
        "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}],
        "stream": True,
    }
    result = translate_request(body, make_config())
    assert result["model"] == "gpt-4o-mini"  # always uses config.default_model
    assert result["stream"] is True
    assert result["messages"][0]["role"] == "user"
    assert result["messages"][0]["content"] == [{"type": "text", "text": "hello"}]


def test_translate_request_instructions():
    body = {
        "instructions": "You are helpful",
        "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]}],
    }
    result = translate_request(body, make_config())
    assert result["messages"][0]["role"] == "system"
    assert result["messages"][0]["content"] == "You are helpful"
    assert result["messages"][1]["role"] == "user"


def test_translate_request_string_input():
    body = {"input": "hello"}
    result = translate_request(body, make_config())
    assert len(result["messages"]) == 1
    assert result["messages"][0]["role"] == "user"
    assert result["messages"][0]["content"] == "hello"


def test_translate_request_default_model():
    body = {"input": "hello"}
    result = translate_request(body, make_config(default_model="my-model"))
    assert result["model"] == "my-model"


def test_translate_request_max_output_tokens_renamed():
    body = {"input": "hi", "max_output_tokens": 100}
    result = translate_request(body, make_config())
    assert result["max_tokens"] == 100
    assert "max_output_tokens" not in result


def test_translate_request_stream_forced():
    body = {"input": "hi", "stream": False}
    result = translate_request(body, make_config())
    assert result["stream"] is True
