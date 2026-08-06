FROM python:3.14.6-slim-bookworm

# Pin uv for reproducible builds.
COPY --from=ghcr.io/astral-sh/uv:0.12.2 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install dependencies separately so source-code changes do not invalidate
# the dependency layer.
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
        --locked \
        --no-dev \
        --no-install-project

# Copy the application and install the project itself.
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
        --locked \
        --no-dev \
        --no-editable

# Run as a non-root user.
RUN useradd \
        --create-home \
        --uid 10001 \
        appuser \
    && chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "ai_tour_guide.ingestion.cli"]
