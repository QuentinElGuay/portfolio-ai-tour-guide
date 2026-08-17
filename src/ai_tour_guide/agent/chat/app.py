from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence

import gradio as gr

from ai_tour_guide.agent.chat.backends import (
    ChatBackend,
    DemoBackend,
    HttpChatBackend,
    create_backend,
)
from ai_tour_guide.agent.chat.models import ChatHistoryItem, Message, Role
from ai_tour_guide.agent.source_formatting import format_pages


def normalize_history(history: Sequence[ChatHistoryItem]) -> list[Message]:
    messages: list[Message] = []

    for item in history:
        try:
            role = Role(item['role'])
        except ValueError:
            continue

        content = item['content']
        if isinstance(content, str):
            messages.append({'role': role, 'content': content})

    return messages


def create_app(backend: ChatBackend | None = None) -> gr.ChatInterface:
    """Create the UI with an injected backend or its development fallback."""
    selected_backend = backend or DemoBackend()

    async def respond(
        message: str,
        history: list[ChatHistoryItem],
    ) -> str:
        messages = normalize_history(history)
        messages.append({'role': Role.USER, 'content': message})

        try:
            return _render_response(await selected_backend.ask(messages))
        except RuntimeError as exc:
            return f'**Backend error:** {exc}'

    return gr.ChatInterface(
        fn=respond,
        chatbot=gr.Chatbot(
            height=560,
            placeholder=(
                '<h2>Explore Brittany</h2>'
                '<p>Ask a question grounded in the tourism guide.</p>'
            ),
        ),
        textbox=gr.Textbox(
            placeholder='Write a message...',
            container=False,
            autofocus=True,
        ),
        title=os.getenv('CHAT_TITLE', 'AI TOUR GUIDE'),
        description=(
            'Ask questions about Brittany and receive answers grounded in the guide.'
        ),
        examples=[
            'What are the main places to visit in Brittany?',
            'What is special about Breton culture?',
        ],
        cache_examples=False,
    )


def _render_response(payload: dict[str, object]) -> str:
    """Default display only; source selection is already complete in RAG."""
    answer = payload['answer']
    if not isinstance(answer, str):
        raise TypeError('The chat response has no answer.')
    rendered = [answer]
    sources = payload.get('sources', [])
    if not isinstance(sources, list):
        raise TypeError('The chat response has invalid sources.')
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get('title'), str):
            raise TypeError('The chat response has an invalid source.')
        pages = source.get('pages', [])
        if not isinstance(pages, list) or not all(
            isinstance(page, int) for page in pages
        ):
            raise RuntimeError('The chat response has invalid source pages.')
        suffix = f', {format_pages(pages)}' if pages else ''
        rendered.append(f'({source["title"]}{suffix})')
    return '\n'.join(rendered)


def main() -> None:
    backend = create_backend()
    if isinstance(backend, HttpChatBackend):
        try:
            asyncio.run(backend.check_ready())
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
    app = create_app(backend)
    app.launch(
        server_name=os.getenv('CHAT_HOST', '127.0.0.1'),
        server_port=int(os.getenv('CHAT_PORT', '7860')),
        show_error=True,
    )


if __name__ == '__main__':
    main()
