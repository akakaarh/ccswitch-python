# ccswitch-python

English | [中文](README.zh-CN.md)

A local proxy that translates OpenAI's Responses API to Chat Completions API, enabling Codex CLI to work with any OpenAI-compatible backend.

## How It Works

```
Codex ──Responses API──> localhost:11435 ──Chat Completions──> Any backend
```

## Quick Start

```bash
# Clone and install
git clone https://github.com/YOUR_USERNAME/ccswitch-python.git
cd ccswitch-python
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your API_KEY and API_BASE_URL

# Run
python -m ccswitch
```

## Codex CLI Setup

Add to `~/.codex/config.toml`:

```toml
[model_providers.ccswitch]
base_url = "http://127.0.0.1:11435/v1"
wire_api = "responses"
```

Then run: `codex --profile ccswitch`

## Configuration

| Variable | Default | Description |
|---|---|---|
| `API_KEY` | (required) | Backend API key |
| `API_BASE_URL` | `https://api.openai.com` | Backend base URL |
| `PROXY_HOST` | `127.0.0.1` | Listen address |
| `PROXY_PORT` | `11435` | Listen port |
| `DEFAULT_MODEL` | `gpt-4o-mini` | Default model |
| `SIMPLIFY_INSTRUCTIONS` | `false` | Simplify system prompt (reduces hallucinations for weaker models) |

## Supported Backends

Any OpenAI-compatible Chat Completions API:
- OpenAI
- DeepSeek
- mimo (via compatible endpoint)
- Ollama (with OpenAI compatibility mode)
- vLLM, LiteLLM, etc.

## Testing

```bash
pip install -e ".[dev]"
pytest -v
```

## License

MIT
