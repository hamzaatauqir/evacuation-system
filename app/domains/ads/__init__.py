"""Website Advertisements module — admin-managed homepage popup + banner.

Additive domain module per the portal modularization strategy (mirrors
app/domains/hostel):
- server.py stays the only HTTP entrypoint; it forwards matching paths here.
- No import-time side effects; server.py injects shared helpers via configure().
- Schema is additive and idempotent (ensure_schema).
- Management is strictly admin-role only; the public surfaces are the homepage
  payload (public_payload_json), the read-only public JSON API consumed by the
  React site (public_payload_api), and the /ads/media/* image route.
"""
from .core import configure
from .schema import ensure_schema
from .routes import handle_get, handle_post, matches_path
from .service import public_payload_api, public_payload_json

__all__ = ['configure', 'ensure_schema', 'handle_get', 'handle_post',
           'matches_path', 'public_payload_api', 'public_payload_json']
