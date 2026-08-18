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

CHAT_CSS = """
#rag-chat .message-row.bot .feedback {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
}

#rag-chat .message-row.bot .feedback::before {
    content: "Was this answer helpful?";
    margin-right: 0.25rem;
    white-space: nowrap;
}

@media (max-width: 480px) {
    #rag-chat .message-row.bot .feedback::before {
        flex-basis: 100%;
    }
}
"""


def placeholder_request_id(assistant_message_index: int) -> str:
    """Return the temporary request ID used until the API exposes one to chat."""
    return f'TODO: request_id:{assistant_message_index}'


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


async def submit_feedback(
    request_ids: dict[int, str], backend: ChatBackend, data: gr.LikeData
) -> None:
    """Forward valid feedback for the assistant message that was selected."""
    if not isinstance(data.index, int):
        return
    if not isinstance(data.liked, bool):
        return

    request_id = request_ids.get(data.index)
    if request_id is None:
        return

    await backend.submit_feedback(request_id, data.liked)


def create_app(backend: ChatBackend | None = None) -> gr.Blocks:
    """Create the UI with an injected backend or its development fallback."""
    selected_backend = backend or DemoBackend()

    async def respond(
        message: str,
        history: list[ChatHistoryItem],
        request_ids: dict[int, str],
    ) -> tuple[str, dict[int, str]]:
        messages = normalize_history(history)
        messages.append({'role': Role.USER, 'content': message})
        assistant_message_index = len(history) + 1

        try:
            reply = _render_response(await selected_backend.ask(messages))
        except RuntimeError as exc:
            reply = f'**Backend error:** {exc}'

        updated_request_ids = dict(request_ids)
        updated_request_ids[assistant_message_index] = placeholder_request_id(
            assistant_message_index
        )
        return reply, updated_request_ids

    async def on_like(request_ids: dict[int, str], data: gr.LikeData) -> None:
        """Adapt Gradio's event payload to the shared feedback handler."""
        await submit_feedback(request_ids, selected_backend, data)

    with gr.Blocks() as app:
        request_ids = gr.State({})
        chatbot = gr.Chatbot(
            elem_id='rag-chat',
            feedback_options=('Like', 'Dislike'),
            height=560,
            placeholder=(
                '<h2>Explore Brittany</h2>'
                '<p>Ask a question grounded in the tourism guide.</p>'
            ),
        )
        gr.ChatInterface(
            fn=respond,
            chatbot=chatbot,
            additional_inputs=request_ids,
            additional_outputs=request_ids,
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
                ['What are the main places to visit in Brittany?'],
                ['What is special about Breton culture?'],
            ],
            cache_examples=False,
        )
        chatbot.like(
            on_like,
            inputs=request_ids,
            outputs=None,
            api_visibility='private',
            show_progress='hidden',
        )

    return app


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
        css=CHAT_CSS,
    )


if __name__ == '__main__':
    main()
