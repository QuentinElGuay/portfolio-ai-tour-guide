# Gradio Chat MVP

A minimal local chat UI for an LLM portfolio.

It includes:

- a new-message input;
- visible conversation history;
- Markdown and code-block rendering;
- a clear-chat button;
- a swappable backend;
- an HTTP adapter for a separate Python API.

## Run locally

With `uv`:

```bash
uv sync
uv run chat-ui
```

Or with `pip`:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
chat-ui
```

Open <http://127.0.0.1:7860>.

By default, the app uses a small demo backend so it works without an LLM
provider or API key.

## Connect your Python backend

Configure the endpoint:

```bash
# Linux/macOS
export CHAT_API_URL=http://localhost:8000/chat

# PowerShell
$env:CHAT_API_URL = "http://localhost:8000/chat"

uv run chat-ui
```

The UI sends:

```json
{
  "messages": [
    {"role": "user", "content": "Previous question"},
    {"role": "assistant", "content": "Previous answer"},
    {"role": "user", "content": "Current question"}
  ]
}
```

The API should return:

```json
{
  "message": {
    "role": "assistant",
    "content": "The generated answer"
  }
}
```

A minimal FastAPI endpoint could be:

```python
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


class ChatResponse(BaseModel):
    message: Message


app = FastAPI()


@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    latest_message = request.messages[-1].content

    # Replace this with your provider or application service.
    answer = f"Your backend received: {latest_message}"

    return ChatResponse(
        message=Message(role="assistant", content=answer)
    )
```

## Project structure

```text
.
├── pyproject.toml
└── src/
    └── ai_tour_guide.agent.chat/
        ├── app.py
        ├── backends.py
        └── models.py
```
