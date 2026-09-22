"""Public entry point: uvicorn bot:app --host 0.0.0.0 --port 8080."""
from vera.api import create_app
from vera.composer import compose

app = create_app()
__all__ = ["app", "compose", "create_app"]
