# Two stages. Node builds the page. The run image has no Node.
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web ./
# `npm run build` type-checks against the committed src/api.gen.ts. It does not call Python.
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
COPY --from=web /web/dist ./web/dist

ENV PATH="/app/.venv/bin:$PATH"
CMD ["saasx2x", "worker"]
# One image, two services. `worker` and `web` differ in the command only.
# Add `web/node_modules` and `web/dist` to .dockerignore.
