# Slice 2 Dockerfile. Two stages. Node is in the build stage only.
# The final image is the slice 1 image plus web/dist. It has no Node.

FROM node:22-slim AS page
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# `prebuild` runs the TypeScript generator on the committed
# src/generated/dashboard.schema.json, so this stage needs no Python.
RUN npm run build

FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
RUN uv sync --frozen --no-dev
# web.DIST_DIR is <repo>/web/dist, the same rule as store.MIGRATIONS_DIR.
COPY --from=page /web/dist ./web/dist
ENV PATH="/app/.venv/bin:$PATH"
CMD ["saasx2x", "worker"]
