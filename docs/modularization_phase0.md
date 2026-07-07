# Modularization Phase 0

Phase 0 adds a safety baseline only. It does not modularize the application.

What was added:
- `tests/smoke/routes.py` is a stdlib-only smoke runner for key public pages, protected admin pages, and protected/public API endpoints.
- `tests/route_inventory.txt` is a snapshot of the current route and route-gate branches in `server.py`.
- This note documents how to run the baseline checks and what stays frozen for now.

How to run the baseline:
1. `python3 -m py_compile server.py`
2. Start the app on port `8080` if it is not already running: `python3 server.py`
3. `python3 tests/smoke/routes.py http://localhost:8080`

Smoke test behavior:
- `5xx` responses are failures.
- Expected statuses are limited to `200`, `302`, `401`, and `403`, depending on the route.
- The smoke suite does not log in and does not perform authenticated mutations.

Do not change yet:
- Do not refactor `server.py`.
- Do not move functions.
- Do not change routes.
- Do not change database schema.
- Do not change auth or session logic.

Phase 0 exit condition:
- `server.py` compiles.
- The smoke suite runs cleanly against `http://localhost:8080`.
- The route inventory is available as a baseline for later modularization diffs.
