# Streamable-HTTP image: MCP at :8080/mcp, health at :8080/health.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 \
    XDG_CACHE_HOME=/tmp/cache UV_PROJECT_ENVIRONMENT=/opt/venv PATH=/opt/venv/bin:$PATH
# ponytail: single process only; the DuckDB cache holds a file lock.

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-cache && useradd -r app
USER app

EXPOSE 8080
# Supply ATTAINS_API_KEY at runtime; never bake it into the image.
CMD ["python", "-m", "watershed_evidence_mcp.server"]
