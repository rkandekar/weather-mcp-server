FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

# MCP servers speak JSON-RPC over stdio, so this container must be run with
# `docker run -i` (stdin kept open) for a client to talk to it. There is no
# network port to expose.
ENTRYPOINT ["weather-mcp"]
