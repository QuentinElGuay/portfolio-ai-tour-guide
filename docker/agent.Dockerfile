# syntax=docker/dockerfile:1.7

FROM ai-tour-guide-base

# Copy and install the application itself.
COPY --chown=10001:10001 src ./src
COPY --chown=10001:10001 fixtures/demo_dataset.jsonl ./fixtures/demo_dataset.jsonl

RUN --mount=type=cache,target=/home/appuser/.cache/uv,uid=10001,gid=10001 \
    uv sync \
        --locked \
        --no-dev \
        --no-editable

EXPOSE 8000 7860

CMD ["python", "-m", "uvicorn", "ai_tour_guide.agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
