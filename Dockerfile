# Minimal image that can run ingestion, dbt and the MCP server.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install -U pip && pip install -e ".[orchestration]"

# App code (dbt project, orchestration, scripts).
COPY dbt ./dbt
COPY orchestration ./orchestration
COPY scripts ./scripts

# Default: start the MCP server over stdio.
CMD ["wc-mcp"]
