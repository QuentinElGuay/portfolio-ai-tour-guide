# syntax=docker/dockerfile:1.7

FROM python:3.14.6-slim-bookworm

ARG EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5

# Pin uv for reproducible builds.
COPY --from=ghcr.io/astral-sh/uv:0.12.2 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HOME=/home/appuser \
    PATH="/app/.venv/bin:$PATH" \
    EMBEDDING_MODEL_NAME=${EMBEDDING_MODEL_NAME} \
    EMBEDDING_CACHE_DIR=/app/.cache/fastembed

# Create the runtime user and an owned application directory before installing.
# This avoids a slow recursive chown of the virtual environment.
RUN useradd \
        --create-home \
        --uid 10001 \
        appuser \
    && install -d \
        --owner=10001 \
        --group=10001 \
        /app

USER appuser
WORKDIR /app

# Install dependencies separately so source changes reuse this layer.
COPY --chown=10001:10001 pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/home/appuser/.cache/uv,uid=10001,gid=10001 \
    uv sync \
        --locked \
        --no-dev \
        --no-install-project

# Embed the configured model in the image so query containers need no runtime
# download. Rebuild with a new model setting to update the model artifacts.
RUN python -c "import os; from fastembed import TextEmbedding; TextEmbedding(model_name=os.environ['EMBEDDING_MODEL_NAME'], cache_dir=os.environ['EMBEDDING_CACHE_DIR'])"

# Copy and install the application itself.
COPY --chown=10001:10001 src ./src

RUN --mount=type=cache,target=/home/appuser/.cache/uv,uid=10001,gid=10001 \
    uv sync \
        --locked \
        --no-dev \
        --no-editable

EXPOSE 8000

CMD ["python", "-m", "ai_tour_guide.agent"]
