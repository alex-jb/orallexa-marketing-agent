# syntax=docker/dockerfile:1.6
# Multi-stage build for the Orallexa Marketing Agent.
# - Stage 1 (builder): install all deps including optional extras
# - Stage 2 (runtime): copy only the venv + source, slim final image (~150MB)

FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY marketing_agent ./marketing_agent
COPY scripts ./scripts

RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install -r requirements.txt \
 && /opt/venv/bin/pip install -e .

# ─── runtime ─────────────────────────────────────────────
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    MARKETING_AGENT_LOG=json \
    MARKETING_AGENT_LOG_LEVEL=info

# Non-root user for the runtime
RUN groupadd -r agent && useradd -r -g agent -u 1000 -m -d /home/agent agent

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

WORKDIR /app
USER agent

# Default invocation: print help. Override with: docker run ... <args>
ENTRYPOINT ["python", "-m", "marketing_agent"]
CMD ["--help"]
