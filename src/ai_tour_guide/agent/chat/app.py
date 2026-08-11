from __future__ import annotations

import os
from collections.abc import Sequence

import gradio as gr

from ai_tour_guide.agent.chat.backends import (
    ChatBackend,
    create_backend,
)
from ai_tour_guide.agent.chat.models import Message


def normalize_history(history: Sequence[dict[str, object]]) -> list[Message]:
    messages: list[Message] = []

    for item in history:
        role = item.get('role')
        content = item.get('content')

        if role not in {'user', 'assistant', 'system'}:
            continue

        if isinstance(content, str):
            messages.append({'role': role, 'content': content})

    return messages


def create_app(backend: ChatBackend | None = None) -> gr.ChatInterface:
    selected_backend = backend or create_backend()

    async def respond(
        message: str,
        history: list[dict[str, object]],
    ) -> str:
        messages = normalize_history(history)
        messages.append({'role': 'user', 'content': message})

        try:
            return await selected_backend.generate(messages)
        except RuntimeError as exc:
            return f'**Backend error:** {exc}'

    return gr.ChatInterface(
        fn=respond,
        chatbot=gr.Chatbot(
            height=560,
            placeholder=(
                '<h2>Start a conversation</h2>'
                '<p>Send a message to test the chat application.</p>'
            ),
        ),
        textbox=gr.Textbox(
            placeholder='Write a message...',
            container=False,
            autofocus=True,
        ),
        title=os.getenv('CHAT_TITLE', 'AI TOUR GUIDE'),
        description=(
            'A minimal Gradio interface connected to a replaceable Python chat backend.'
        ),
        examples=[
            'What can this portfolio application do?',
            'Show me a small Python example.',
        ],
        cache_examples=False,
    )


def main() -> None:
    app = create_app()
    app.launch(
        server_name=os.getenv('CHAT_HOST', '127.0.0.1'),
        server_port=int(os.getenv('CHAT_PORT', '7860')),
        show_error=True,
    )


if __name__ == '__main__':
    main()
