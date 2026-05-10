# ccswitch-python

[English](README.en.md) | 中文

一个本地代理，将 OpenAI 的 Responses API 转换为 Chat Completions API，使 Codex CLI 能够对接任意 OpenAI 兼容后端。

## 工作原理

```
Codex ──Responses API──> localhost:11435 ──Chat Completions──> 任意后端
```

## 快速开始

```bash
# 克隆并安装
git clone https://github.com/akakaarh/ccswitch-python.git
cd ccswitch-python
pip install -e ".[dev]"

# 配置
cp .env.example .env
# 编辑 .env，填入你的 API_KEY 和 API_BASE_URL

# 启动
python -m ccswitch
```

## Codex CLI 配置

在 `~/.codex/config.toml` 中添加：

```toml
[model_providers.ccswitch]
base_url = "http://127.0.0.1:11435/v1"
wire_api = "responses"
```

然后运行：`codex --profile ccswitch`

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `API_KEY` | （必填） | 后端 API Key |
| `API_BASE_URL` | `https://api.openai.com` | 后端地址 |
| `PROXY_HOST` | `127.0.0.1` | 监听地址 |
| `PROXY_PORT` | `11435` | 监听端口 |
| `DEFAULT_MODEL` | `gpt-4o-mini` | 默认模型 |
| `SIMPLIFY_INSTRUCTIONS` | `false` | 简化系统提示词（减少弱模型幻觉） |

## 支持的后端

任何 OpenAI 兼容的 Chat Completions API：
- OpenAI
- DeepSeek
- mimo（小米大模型）
- Ollama（需开启 OpenAI 兼容模式）
- vLLM、LiteLLM 等

## 运行测试

```bash
pip install -e ".[dev]"
pytest -v
```

## 许可证

MIT
