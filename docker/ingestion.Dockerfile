# syntax=docker/dockerfile:1.7

FROM ai-tour-guide-base

# The ingestion pipeline retains optional debug artifacts here.
RUN mkdir -p /app/data

# Copy and install the application itself.
COPY --chown=10001:10001 src ./src

RUN --mount=type=cache,target=/home/appuser/.cache/uv,uid=10001,gid=10001 \
    uv sync \
        --locked \
        --no-dev \
        --no-editable

CMD ["python", "-m", "ai_tour_guide.ingestion.cli"]
