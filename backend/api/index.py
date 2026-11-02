"""Vercel Serverless Function entry point for SafeSpace Intelligence FastAPI backend."""

import sys
from pathlib import Path

# Add the backend project root to sys.path so app packages import cleanly in serverless environment
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.main import app  # noqa: E402

# Vercel's Python runtime discovers the ASGI/WSGI callable named 'app'
__all__ = ["app"]
