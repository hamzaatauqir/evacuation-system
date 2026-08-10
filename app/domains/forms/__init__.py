"""Embassy Forms Library — staff-managed public downloadable forms.

Additive domain module per the portal modularization strategy (mirrors
app/domains/ads):
- server.py stays the only HTTP entrypoint; it forwards matching paths here.
- No import-time side effects; server.py injects shared helpers via configure().
- Schema is additive and idempotent (ensure_schema).
- Management requires an authenticated staff session plus an in-handler role
  check (admin or operator; archive/categories/audit are admin-only).
- Public surfaces are /forms, /api/public/forms and /forms/download/<id>, all
  unauthenticated and read-only.

Owner decisions locked 2026-08-10: PDF only, and nothing is ever hard-deleted.
"""
from .core import configure
from .schema import ensure_schema
from .routes import handle_get, handle_post, matches_path
from .service import public_payload_api

__all__ = ['configure', 'ensure_schema', 'handle_get', 'handle_post',
           'matches_path', 'public_payload_api']
