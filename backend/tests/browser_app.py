"""TEST ONLY: real HTTP gateway and rendering with explicitly synthetic AI output.

Run two Uvicorn factories on loopback:
  tests.rag_browser_app:create_gateway (port 9001)
  tests.rag_browser_app:create_backend (port 8000)
Never use these factories for production or as a real gateway fallback.
"""

import os
from pathlib import Path

from pydantic import SecretStr

from tip.app import create_app
from tip.config import Settings
from tip.documents import mermaid_renderer_configured
from .test_rag_replacement import synthetic_gateway_app


def create_gateway():
    return synthetic_gateway_app([], diagram_enabled=mermaid_renderer_configured())


def create_backend():
    return create_app(Settings(
        _env_file=None,
        data_dir=Path(os.environ["TIP_BROWSER_DATA_DIR"]),
        graph_backend="kuzu",
        gateway_url="http://127.0.0.1:9001/ai-gateway/v1/chat/completions",
        gateway_app_consumer_key=SecretStr("synthetic-consumer"),
        gateway_hmac_secret=SecretStr("synthetic-secret"),
    ))