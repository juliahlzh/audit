"""Vercel FastAPI entrypoint.

Keeping the entrypoint at the repository root lets Vercel's FastAPI runtime
forward the original request path (for example ``/login``) to the application.
"""

from app.main import app


__all__ = ["app"]
