import json
import logging
import uuid

import aiohttp
from aiohttp import web
import httpx

from ccswitch.config import Config, load_config
from ccswitch.translate import translate_request
from ccswitch.sse import SseTranslator

logger = logging.getLogger(__name__)

try:
    config = load_config()
except ValueError as e:
    logger.error("Configuration error: %s", e)
    config = None


def _error_sse(code: str, message: str) -> str:
    data = json.dumps({"type": "error", "code": code, "message": message})
    return f"event: error\ndata: {data}\n\n"


async def handle_responses(request: web.Request) -> web.StreamResponse:
    """Main proxy endpoint: POST /v1/responses"""
    if config is None:
        return web.Response(status=500, text="Server not configured")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.Response(status=400, text="Invalid JSON")

    chat_body = translate_request(body, config)
    backend_url = f"{config.api_base_url.rstrip('/')}/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
    await response.prepare(request)

    response_id = f"resp_{uuid.uuid4().hex[:12]}"
    model = chat_body.get("model", config.default_model)
    translator = SseTranslator(response_id=response_id, model=model)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            async with client.stream(
                "POST",
                backend_url,
                json=chat_body,
                headers=headers,
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    try:
                        error_data = json.loads(error_body)
                        msg = error_data.get("error", {}).get("message", error_body.decode())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        msg = str(error_body)
                    await response.write(_error_sse("backend_error", f"Backend {resp.status_code}: {msg}").encode())
                    await response.write_eof()
                    return response

                async for line in resp.aiter_lines():
                    events = await translator.feed(line)
                    for event in events:
                        await response.write(event.encode())

        done_events = await translator.done()
        for event in done_events:
            await response.write(event.encode())

    except httpx.ConnectError:
        await response.write(_error_sse("connection_error", f"Cannot connect to {config.api_base_url}").encode())
    except httpx.TimeoutException:
        await response.write(_error_sse("timeout", "Backend request timed out").encode())
    except Exception as e:
        logger.exception("Unexpected error")
        await response.write(_error_sse("internal_error", str(e)).encode())

    await response.write_eof()
    return response


async def handle_models(request: web.Request) -> web.Response:
    data = {
        "object": "list",
        "data": [{"id": config.default_model if config else "default", "object": "model", "owned_by": "ccswitch"}],
    }
    return web.json_response(data)


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "ccswitch"})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/v1/responses", handle_responses)
    app.router.add_post("/responses", handle_responses)
    app.router.add_get("/v1/models", handle_models)
    app.router.add_get("/", handle_health)
    return app


app = create_app()
