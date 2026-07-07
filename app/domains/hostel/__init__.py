"""Hostel / Nurse Accommodation Partner module (AJA Care and future partners).

Additive domain module per the portal modularization strategy:
- server.py stays the only HTTP entrypoint; it forwards matching paths here.
- No import-time side effects; server.py injects shared helpers via configure().
- Schema is additive and idempotent (ensure_schema), seeded with AJA Care.
"""
from .core import configure
from .schema import ensure_schema
from .routes import handle_get, handle_post, matches_path

__all__ = ['configure', 'ensure_schema', 'handle_get', 'handle_post', 'matches_path']
