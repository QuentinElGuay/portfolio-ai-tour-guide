import asyncio
import base64
import logging
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import gradio as gr

from ai_tour_guide.app.agent.identity import FRENCH_EXPRESSIONS
from ai_tour_guide.app.agent.source_formatting import format_pages
from ai_tour_guide.app.chat.backends import (
    ChatService,
    DemoChatService,
    HttpChatService,
    create_chat_service,
)
from ai_tour_guide.app.chat.models import (
    FREE_TEXT_INPUT_ID,
    ChatHistoryItem,
    ConversationResponse,
    Emotion,
    Role,
)

logger = logging.getLogger(__name__)

FEEDBACK_ACKNOWLEDGEMENT = 'Thanks for your feedback!'
INVALID_SOURCE_ERROR = 'The chat response has an invalid source.'
CHAT_SERVICE_ERROR_MESSAGE = (
    "Oh là là! I'm having a little trouble reaching the travel service right now. "
    'Please try again in a short while.'
)
EMOTICONS_ENABLED = False
ASSISTANT_LABEL_PLACEHOLDER = '__assistant_label__'

AVATAR_IMAGES = (
    Path(__file__).parent / 'assets' / 'avatars' / 'user.png',
    Path(__file__).parent / 'assets' / 'avatars' / 'bot.png',
)
EMOTICON_IMAGES = {
    emotion: Path(__file__).parent / 'assets' / 'emoticons' / f'{emotion.value}.png'
    for emotion in Emotion
    if emotion is not Emotion.NEUTRAL
}

CHAT_CSS = """
.llm-info {
    color: #94a3b8;
    font-size: 0.85rem;
    margin: 0.25rem auto 0;
    text-align: center;
}

#chat .message-buttons-left {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
}

#chat {
    max-height: none;
    overflow-y: hidden !important;
}

/* Gradio autoscrolls bubble-wrap, so it is the sole scroll owner. */
#chat .panel-wrap {
    overflow-y: visible !important;
}

#chat [role="log"] {
    overflow: visible !important;
}

#chat .bubble-wrap {
    height: 100% !important;
    overflow-y: auto !important;
}

#chat .message.bot .message-content {
    background: transparent !important;
    border-radius: 16px !important;
}

#chat .message.bot {
    margin-left: 0.5rem !important;
    padding: 0.25rem 0.5rem !important;
}

#chat .message.bot::before,
#chat .message.user::before {
    color: #334155;
    display: block;
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 0.25rem;
}

#chat .message.bot::before {
    content: "__assistant_label__";
}

#chat .message.user::before {
    content: "You";
}

#chat .message.user .message-content {
    background: transparent !important;
    border-radius: 16px !important;
}

#chat .message {
    margin-bottom: 0.75rem;
}

#chat .avatar-container,
#chat .avatar-container img {
    height: 80px !important;
    width: 80px !important;
}

#chat img.chat-emoticon {
    display: inline-block !important;
    height: 30px !important;
    max-height: 30px !important;
    max-width: 30px !important;
    object-fit: contain;
    vertical-align: middle;
    width: 30px !important;
}

#chat .message-buttons-left::before {
    content: "Was this answer helpful?";
    margin-right: 0.25rem;
    white-space: nowrap;
}

#chat .message-buttons-left button[aria-label="Liked"],
#chat .message-buttons-left button[aria-label="clicked like"] {
    background: #dcfce7 !important;
    color: #15803d !important;
}

#chat .message-buttons-left button[aria-label="Disliked"],
#chat .message-buttons-left button[aria-label="clicked dislike"] {
    background: #fee2e2 !important;
    color: #b91c1c !important;
}

@media (max-width: 480px) {
    #chat .message-buttons-left::before {
        flex-basis: 100%;
    }
}
"""


def placeholder_request_id(assistant_message_index: int) -> str:
    """Return the temporary request ID used until the API exposes one to chat."""
    return f'TODO: request_id:{assistant_message_index}'


def select_feedback(
    request_ids: Mapping[Any, Any], data: gr.LikeData
) -> dict[str, object] | None:
    """Resolve a Gradio like event to the selected message and rating."""
    if not isinstance(data.index, int):
        return None
    if not isinstance(data.liked, bool):
        return None

    request_id = request_ids.get(data.index)
    if not isinstance(request_id, str):
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
    service: ChatService,
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
    await service.submit_feedback(request_id, helpful)


async def start_client_chat(
    service: ChatService,
) -> tuple[dict[object, object], list[ChatHistoryItem], str]:
    """Start and render an independent conversation for one Gradio client."""
    response = await service.start_chat()
    request_ids: dict[object, object] = {
        'session_id': str(response.session_id),
        'step_id': str(response.step_id),
        'buttons': [button.model_dump() for button in response.buttons],
    }
    welcome = cast(
        ChatHistoryItem,
        {
            'role': 'assistant',
            'content': response.message,
            'options': [
                {'label': button.label, 'value': button.label}
                for button in response.buttons
            ],
        },
    )
    llm_label = (
        f'Model: `{response.llm.provider} - {response.llm.model}`'
        if response.llm is not None
        else ''
    )
    return request_ids, [welcome], llm_label


def chat_css(*, demo_mode: bool) -> str:
    """Return chat styling with the assistant label for the selected service."""
    assistant_label = 'Petit Guide (demo mode)' if demo_mode else 'Petit Guide'
    return CHAT_CSS.replace(ASSISTANT_LABEL_PLACEHOLDER, assistant_label)


def is_demo_mode() -> bool:
    """Return whether the configured LLM is the deterministic demo provider."""
    return os.getenv('AGENT_LLM_PROVIDER') == 'baguette-llm'


def create_app(service: ChatService | None = None) -> gr.Blocks:
    """Create the UI with an injected chat service or its development fallback."""
    selected_service = service or DemoChatService()

    async def initialize_client() -> tuple[
        dict[object, object], list[ChatHistoryItem], str
    ]:
        """Create a conversation when a browser client loads the interface."""
        return await start_client_chat(selected_service)

    def add_user_message(
        message: str,
        history: list[ChatHistoryItem],
    ) -> tuple[str, list[ChatHistoryItem], str]:
        """Render the user's message before the chat service begins its response."""
        return (
            '',
            [*history, {'role': Role.USER, 'content': message}],
            message,
        )

    async def respond(
        message: str,
        history: list[ChatHistoryItem],
        request_ids: dict[object, object],
    ) -> tuple[str, list[ChatHistoryItem], dict[object, object]]:
        logger.info('chat question received: question=%r', message)
        display_question = message
        assistant_message_index = len(history)

        response = None
        try:
            buttons = request_ids.get('buttons', [])
            if not isinstance(buttons, list):
                buttons = []
            buttons = cast(list[dict[str, object]], buttons)
            selected_button = next(
                (
                    button
                    for button in buttons
                    if isinstance(button, dict)
                    and message in (button.get('input_id'), button.get('label'))
                ),
                None,
            )
            input_id = (
                cast(str, selected_button['input_id'])
                if selected_button is not None
                else FREE_TEXT_INPUT_ID
            )
            response = await selected_service.send_message(
                cast(str, request_ids['session_id']),
                cast(str, request_ids['step_id']),
                input_id,
                None if input_id != FREE_TEXT_INPUT_ID else display_question,
            )
            reply = _render_conversation_response(response)
        except RuntimeError:
            logger.exception('Chat service request failed')
            reply = CHAT_SERVICE_ERROR_MESSAGE
            request_id = placeholder_request_id(assistant_message_index)
        else:
            response_request_id = response.message_id
            request_id = (
                str(response_request_id)
                if response_request_id is not None
                else placeholder_request_id(assistant_message_index)
            )

        updated_request_ids = dict(request_ids)
        updated_request_ids[assistant_message_index] = request_id
        if response is not None:
            updated_request_ids.update(
                {
                    'session_id': str(response.session_id),
                    'step_id': str(response.step_id),
                    'buttons': [button.model_dump() for button in response.buttons],
                }
            )
        options = cast(list[dict[str, object]], updated_request_ids.get('buttons', []))
        assistant_message = cast(
            ChatHistoryItem,
            {
                'role': Role.ASSISTANT,
                'content': reply,
                'options': [
                    {'label': button['label'], 'value': button['label']}
                    for button in options
                    if isinstance(button, dict)
                    and isinstance(button.get('label'), str)
                    and isinstance(button.get('input_id'), str)
                ],
            },
        )
        return (
            '',
            [*history, assistant_message],
            updated_request_ids,
        )

    def add_selected_option(
        history: list[ChatHistoryItem],
        data: gr.SelectData,
    ) -> tuple[str, list[ChatHistoryItem], str]:
        """Render a selected chat-service option as a normal user message."""
        if not isinstance(data.value, str):
            return '', history, ''
        return add_user_message(data.value, history)

    async def on_like(
        request_ids: dict[object, object],
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
        await submit_feedback(selection, selected_service)
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

    with gr.Blocks(title='Bon Voyage') as app:
        gr.Markdown(f'# {os.getenv("CHAT_TITLE", "Bon Voyage")}')
        gr.Markdown(
            "We'll answer your questions based on the travel guides _de la maison_."
        )
        request_ids = gr.State({})
        feedback_values = gr.State([])
        pending_message = gr.State('')
        chatbot = gr.Chatbot(
            elem_id='chat',
            avatar_images=AVATAR_IMAGES,
            feedback_options=('Like', 'Dislike'),
            feedback_value=[],
            height='calc(100vh - 250px)',
            value=[],
            placeholder=(
                '<h2>Starting your conversation with Petit Guide…</h2>'
                '<p>Please wait a moment.</p>'
            ),
        )
        textbox = gr.Textbox(
            placeholder='Write a message and press enter to ask a question.',
            container=False,
            autofocus=True,
        )
        llm_info = gr.Markdown('', elem_classes=['llm-info'])
        app.load(  # pyright: ignore[reportAttributeAccessIssue]
            initialize_client,
            outputs=[request_ids, chatbot, llm_info],
            api_visibility='private',
            show_progress='hidden',
        )
        textbox.submit(  # pyright: ignore[reportAttributeAccessIssue]
            add_user_message,
            inputs=[textbox, chatbot],
            outputs=[textbox, chatbot, pending_message],
            api_visibility='private',
            queue=False,
            show_progress='hidden',
        ).then(
            respond,
            inputs=[pending_message, chatbot, request_ids],
            outputs=[textbox, chatbot, request_ids],
            api_visibility='private',
            show_progress='minimal',
        )
        chatbot.option_select(  # pyright: ignore[reportAttributeAccessIssue]
            add_selected_option,
            inputs=[chatbot],
            outputs=[textbox, chatbot, pending_message],
            api_visibility='private',
            queue=False,
            show_progress='hidden',
        ).then(
            respond,
            inputs=[pending_message, chatbot, request_ids],
            outputs=[textbox, chatbot, request_ids],
            api_visibility='private',
            show_progress='minimal',
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
    """Default display only; source selection is already complete upstream."""
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
            raise TypeError(INVALID_SOURCE_ERROR)
        pages = source.get('pages', [])
        if not isinstance(pages, list) or not all(
            isinstance(page, int) for page in pages
        ):
            raise RuntimeError('The chat response has invalid source pages.')
        suffix = f', {format_pages(pages)}' if pages else ''
        rendered.append(f'({source["title"]}{suffix})')
    return '\n'.join(rendered)


def _render_conversation_response(response: object) -> str:
    """Render a server response without interpreting its flow state."""
    if not isinstance(response, ConversationResponse):
        raise TypeError('The chat response has an invalid shape.')
    rendered = [_italicize_french_expressions(response.message)]
    for source in response.sources:
        title = source.get('title')
        pages = source.get('pages', [])
        if not isinstance(title, str) or not isinstance(pages, list):
            raise TypeError(INVALID_SOURCE_ERROR)
        suffix = f', {format_pages(pages)}' if pages else ''
        rendered.append(f'({title}{suffix})')
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
    service = create_chat_service()
    if isinstance(service, HttpChatService):
        try:
            asyncio.run(service.check_ready())
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
    app = create_app(service)
    app.launch(
        server_name=os.getenv('CHAT_HOST', '127.0.0.1'),
        server_port=int(os.getenv('CHAT_PORT', '7860')),
        show_error=True,
        css=chat_css(demo_mode=is_demo_mode()),
        footer_links=[],
    )


if __name__ == '__main__':
    main()
