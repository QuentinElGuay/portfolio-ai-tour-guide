import asyncio
import base64
import logging
import os
import re
from collections.abc import Sequence
from pathlib import Path

import gradio as gr

from ai_tour_guide.agent.chat.backends import (
    STARTER_QUESTIONS as _STARTER_QUESTIONS,
)
from ai_tour_guide.agent.chat.backends import (
    ChatBackend,
    DemoBackend,
    HttpChatBackend,
    create_backend,
)
from ai_tour_guide.agent.chat.models import ChatHistoryItem, Emotion, Message, Role
from ai_tour_guide.agent.chat.navigation import (
    option_id_for_question,
    options_for_ids,
)
from ai_tour_guide.agent.source_formatting import format_pages

logger = logging.getLogger(__name__)

# Backward-compatible import for callers that used the old app-level symbol.
STARTER_QUESTIONS = _STARTER_QUESTIONS

FEEDBACK_ACKNOWLEDGEMENT = 'Thanks for your feedback!'
EMOTICONS_ENABLED = False

# Welcome messages and starter questions shown when a chat session starts.
WELCOME_MESSAGE = (
    '_Salut_! I’m **Petit Guide**. How can I help you prepare your trip to France? '
    'Select a suggested question or ask about our destinations at any time.'
)


DEMO_WELCOME_NOTICE = (
    '\n\n> **Demo mode:** This is a limited experience with prepared Brittany questions. '
    'It accepts modest spelling and punctuation variations.'
)
DEMO_WELCOME_MESSAGE = (
    WELCOME_MESSAGE.replace('France', 'Brittany') + DEMO_WELCOME_NOTICE
)
AVATAR_IMAGES = (
    Path(__file__).parent / 'assets' / 'avatars' / 'user.png',
    Path(__file__).parent / 'assets' / 'avatars' / 'bot.png',
)
FRENCH_EXPRESSIONS = (
    'Oh là là!',
    'Voilà!',
    'Bon appétit!',
    'En route!',
    'Touché!',
    'Salut!',
)
EMOTICON_IMAGES = {
    emotion: Path(__file__).parent / 'assets' / 'emoticons' / f'{emotion.value}.png'
    for emotion in Emotion
    if emotion is not Emotion.NEUTRAL
}

CHAT_CSS = """
#rag-chat .message-buttons-left {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
}

#rag-chat {
    max-height: none;
    overflow-y: hidden !important;
}

/* Gradio autoscrolls bubble-wrap, so it is the sole scroll owner. */
#rag-chat .panel-wrap {
    overflow-y: visible !important;
}

#rag-chat [role="log"] {
    overflow: visible !important;
}

#rag-chat .bubble-wrap {
    height: 100% !important;
    overflow-y: auto !important;
}

#rag-chat .message.bot .message-content {
    background: transparent !important;
    border-radius: 16px !important;
}

#rag-chat .message.bot {
    margin-left: 0.5rem !important;
    padding: 0.25rem 0.5rem !important;
}

#rag-chat .message.bot::before,
#rag-chat .message.user::before {
    color: #334155;
    display: block;
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 0.25rem;
}

#rag-chat .message.bot::before {
    content: "Petit Guide";
}

#rag-chat .message.user::before {
    content: "You";
}

#rag-chat .message.user .message-content {
    background: transparent !important;
    border-radius: 16px !important;
}

#rag-chat .message {
    margin-bottom: 0.75rem;
}

#rag-chat .avatar-container,
#rag-chat .avatar-container img {
    height: 80px !important;
    width: 80px !important;
}

#rag-chat img.chat-emoticon {
    display: inline-block !important;
    height: 30px !important;
    max-height: 30px !important;
    max-width: 30px !important;
    object-fit: contain;
    vertical-align: middle;
    width: 30px !important;
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
    welcome_message = WELCOME_MESSAGE
    if isinstance(selected_backend, DemoBackend):
        welcome_message = DEMO_WELCOME_MESSAGE

    async def respond(
        message: str,
        history: list[ChatHistoryItem],
        request_ids: dict[int, str],
    ) -> tuple[str | dict[str, object], dict[int, str]]:
        logger.info('chat question received: question=%r', message)
        option_id = option_id_for_question(message)
        display_question = message
        messages = normalize_history(history)
        messages.append({'role': Role.USER, 'content': display_question})
        assistant_message_index = len(history) + 1

        payload: dict[str, object] = {}
        try:
            payload = await selected_backend.ask(messages, option_id=option_id)
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
        option_ids = payload.get('next_option_ids', [])
        options = (
            options_for_ids(tuple(option_ids)) if isinstance(option_ids, list) else ()
        )
        return (
            {
                'content': reply,
                'options': [
                    {'label': option.label, 'value': option.question}
                    for option in options
                ],
            }
            if options
            else reply,
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

    with gr.Blocks(title='Baguette Voyages') as app:
        request_ids = gr.State({})
        feedback_values = gr.State([])
        textbox = gr.Textbox(
            placeholder='Write a message and press enter to ask a question.',
            container=False,
            autofocus=True,
        )
        chatbot = gr.Chatbot(
            elem_id='rag-chat',
            avatar_images=AVATAR_IMAGES,
            feedback_options=('Like', 'Dislike'),
            feedback_value=[],
            height='calc(100vh - 250px)',
            value=[
                {
                    'role': 'assistant',
                    'content': welcome_message,
                    'options': [
                        {'label': option.label, 'value': option.question}
                        for option in options_for_ids(('identity', 'destinations'))
                    ],
                },
            ],
            placeholder=(
                '<h2>Prepare your trip to France with Petit Guide</h2>'
                "<p>We'll answer your questions based on our famous travel guides.</p>"
            ),
        )
        gr.ChatInterface(
            fn=respond,
            chatbot=chatbot,
            additional_inputs=request_ids,
            additional_outputs=request_ids,
            textbox=textbox,
            show_progress='minimal',
            title=os.getenv('CHAT_TITLE', 'Baguette Voyages'),
            description=(
                "We'll answer your questions based on our famous travel guides."
            ),
            examples=[],
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
    rendered = [_italicize_french_expressions(answer)]
    emotion = Emotion(payload.get('emotion', Emotion.NEUTRAL))
    if EMOTICONS_ENABLED and emotion is not Emotion.NEUTRAL:
        emoticon = base64.b64encode(EMOTICON_IMAGES[emotion].read_bytes()).decode(
            'ascii'
        )
        rendered[0] += ' ' + (
            f'<img class="chat-emoticon" src="data:image/png;base64,{emoticon}" '
            f'alt="{emotion.value} emoticon" width="30" height="30">'
        )
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


def _italicize_french_expressions(answer: str) -> str:
    """Italicize the approved French expressions used by the assistant."""
    for expression in FRENCH_EXPRESSIONS:
        answer = re.sub(
            rf'(?<!\*){re.escape(expression)}(?!\*)',
            f'*{expression}*',
            answer,
        )
    return answer


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
