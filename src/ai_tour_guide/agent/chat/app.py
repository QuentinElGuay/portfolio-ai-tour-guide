import asyncio
import logging
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

logger = logging.getLogger(__name__)

FEEDBACK_ACKNOWLEDGEMENT = 'Thanks for your feedback!'

CHAT_CSS = """
#rag-chat .message-buttons-left {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
}

#rag-chat {
    max-height: calc(100vh - 250px);
}

#rag-chat .message-buttons-left::before {
    content: "Was this answer helpful?";
    margin-right: 0.25rem;
    white-space: nowrap;
}

#rag-chat .message-buttons-left button[aria-label="Liked"],
#rag-chat .message-buttons-left button[aria-label="clicked like"] {
    background: #dcfce7 !important;
    color: #15803d !important;
}

#rag-chat .message-buttons-left button[aria-label="Disliked"],
#rag-chat .message-buttons-left button[aria-label="clicked dislike"] {
    background: #fee2e2 !important;
    color: #b91c1c !important;
}

@media (max-width: 480px) {
    #rag-chat .message-buttons-left::before {
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


def select_feedback(
    request_ids: dict[int, str], data: gr.LikeData
) -> dict[str, object] | None:
    """Resolve a Gradio like event to the selected message and rating."""
    if not isinstance(data.index, int):
        return None
    if not isinstance(data.liked, bool):
        return None

    request_id = request_ids.get(data.index)
    if request_id is None:
        return None

    return {'request_id': request_id, 'helpful': data.liked}


def update_feedback_values(
    history: Sequence[ChatHistoryItem],
    feedback_values: Sequence[str | None],
    message_index: int,
    helpful: bool,
) -> list[str | None]:
    """Return native Gradio feedback values with the selected answer updated."""
    assistant_indexes = [
        index for index, item in enumerate(history) if item['role'] == Role.ASSISTANT
    ]
    try:
        feedback_index = assistant_indexes.index(message_index)
    except ValueError:
        return list(feedback_values)

    updated_values = list(feedback_values[: len(assistant_indexes)])
    updated_values.extend([None] * (len(assistant_indexes) - len(updated_values)))
    updated_values[feedback_index] = 'Like' if helpful else 'Dislike'
    return updated_values


async def submit_feedback(
    selection: dict[str, object] | None,
    backend: ChatBackend,
) -> None:
    """Submit a valid thumbs up or thumbs down selection."""
    if not isinstance(selection, dict):
        return
    request_id = selection.get('request_id')
    helpful = selection.get('helpful')
    if not isinstance(request_id, str) or not isinstance(helpful, bool):
        return

    logger.info(
        'chat feedback submitted: request_id=%s helpful=%s',
        request_id,
        helpful,
    )
    await backend.submit_feedback(request_id, helpful)


def create_app(backend: ChatBackend | None = None) -> gr.Blocks:
    """Create the UI with an injected backend or its development fallback."""
    selected_backend = backend or DemoBackend()

    async def respond(
        message: str,
        history: list[ChatHistoryItem],
        request_ids: dict[int, str],
    ) -> tuple[str, dict[int, str]]:
        logger.info('chat question received: question=%r', message)
        messages = normalize_history(history)
        messages.append({'role': Role.USER, 'content': message})
        assistant_message_index = len(history) + 1

        try:
            payload = await selected_backend.ask(messages)
            reply = _render_response(payload)
        except RuntimeError as exc:
            reply = f'**Backend error:** {exc}'
            request_id = placeholder_request_id(assistant_message_index)
        else:
            response_request_id = payload.get('request_id')
            request_id = (
                response_request_id
                if isinstance(response_request_id, str)
                else placeholder_request_id(assistant_message_index)
            )

        updated_request_ids = dict(request_ids)
        updated_request_ids[assistant_message_index] = request_id
        return (
            reply,
            updated_request_ids,
        )

    async def on_like(
        request_ids: dict[int, str],
        history: list[ChatHistoryItem],
        feedback_values: list[str | None],
        data: gr.LikeData,
    ) -> tuple[dict[str, object], list[str | None]]:
        """Adapt Gradio's event payload to the shared feedback handler."""
        if not isinstance(data.index, int) or not isinstance(data.liked, bool):
            return gr.update(), feedback_values
        selection = select_feedback(request_ids, data)
        if selection is None:
            return gr.update(), feedback_values
        await submit_feedback(selection, selected_backend)
        logger.info(
            'chat feedback selected: request_id=%s helpful=%s',
            selection['request_id'],
            selection['helpful'],
        )
        updated_feedback_values = update_feedback_values(
            history,
            feedback_values,
            data.index,
            data.liked,
        )
        gr.Info(FEEDBACK_ACKNOWLEDGEMENT)
        return (
            gr.update(feedback_value=updated_feedback_values),
            updated_feedback_values,
        )

    with gr.Blocks() as app:
        request_ids = gr.State({})
        feedback_values = gr.State([])
        textbox = gr.Textbox(
            placeholder='Write a message...',
            container=False,
            autofocus=True,
        )
        chatbot = gr.Chatbot(
            elem_id='rag-chat',
            feedback_options=('Like', 'Dislike'),
            feedback_value=[],
            height=400,
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
            textbox=textbox,
            show_progress='full',
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
        # Gradio exposes this runtime event, but its published type information omits it.
        chatbot.like(  # pyright: ignore[reportAttributeAccessIssue]
            on_like,
            inputs=[request_ids, chatbot, feedback_values],
            outputs=[chatbot, feedback_values],
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
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
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
