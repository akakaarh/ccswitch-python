import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Config:
    api_key: str
    api_base_url: str
    proxy_host: str
    proxy_port: int
    default_model: str
    simplify_instructions: bool = False


def load_config() -> Config:
    load_dotenv()
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise ValueError("API_KEY environment variable is required")
    return Config(
        api_key=api_key,
        api_base_url=os.getenv("API_BASE_URL", "https://api.openai.com"),
        proxy_host=os.getenv("PROXY_HOST", "127.0.0.1"),
        proxy_port=int(os.getenv("PROXY_PORT", "11435")),
        default_model=os.getenv("DEFAULT_MODEL", "gpt-4o-mini"),
        simplify_instructions=os.getenv("SIMPLIFY_INSTRUCTIONS", "").lower() in ("1", "true", "yes"),
    )
