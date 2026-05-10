import uvicorn
from ccswitch.config import load_config


def main():
    config = load_config()
    uvicorn.run(
        "ccswitch.server:app",
        host=config.proxy_host,
        port=config.proxy_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
