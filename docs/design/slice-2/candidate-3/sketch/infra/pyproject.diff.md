# pyproject.toml changes (as a list, not a patch)

dependencies  : add `fastapi>=0.115`, `uvicorn>=0.34`
dev group     : add `httpx>=0.28` (FastAPI TestClient)
ruff banned-api: no change. `psycopg` stays banned outside store.py. `fastapi` and `uvicorn` have no ban.
Run `uv lock` and commit `uv.lock`.
