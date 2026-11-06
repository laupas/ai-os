# The web console (web/): React, built once here and served by ai-os as static files.
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/laupas/ai-os" \
      org.opencontainers.image.description="ai-os v2: chat channels, senders and approvals around Claude agents"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    AIOS_DATA_DIR=/data \
    AIOS_REPO_DIR=/app \
    # Agent session transcripts live with the rest of the data, so a resumed
    # conversation survives the container being recreated.
    CLAUDE_CONFIG_DIR=/data/claude

# The Agent SDK wheel bundles Claude Code itself. Node.js is only for the external
# MCP servers in config.yaml, which start through `npx`; they can be slow to start
# the first time, hence the longer MCP timeout.
ENV MCP_TIMEOUT=120000
RUN apt-get update \
 && apt-get install -y --no-install-recommends nodejs npm ca-certificates git openssh-client \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.7.8 /uv /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY aios ./aios
COPY agents ./agents
COPY .claude ./.claude
COPY skills ./skills
COPY node ./node
COPY --from=web /web/dist ./aios/web/static
RUN uv sync --frozen --no-dev \
 # Files copied from the Google Drive mount are mode 0600; without this the
 # non-root user below cannot read its own code.
 && chmod -R a+rX /app \
 # The CLI reads skills only from .claude/skills: they are the configuration
 # repository's skills/, which the console changes and /app could not hold.
 && ln -s /data/config/skills /app/.claude/skills

RUN useradd --create-home --uid 1000 aios && mkdir /data && chown aios:aios /data
USER aios

CMD ["python", "-m", "aios"]
