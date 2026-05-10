import logging
from aiohttp import web
from ccswitch.config import load_config
from ccswitch.server import create_app


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config()
    app = create_app()
    print(f"ccswitch proxy starting on {config.proxy_host}:{config.proxy_port}")
    print(f"Backend: {config.api_base_url} (model: {config.default_model})")
    web.run_app(app, host=config.proxy_host, port=config.proxy_port)


if __name__ == "__main__":
    main()
