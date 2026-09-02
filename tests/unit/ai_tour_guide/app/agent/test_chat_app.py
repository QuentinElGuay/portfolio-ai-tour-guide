import asyncio
from unittest.mock import AsyncMock, MagicMock

import gradio as gr

from ai_tour_guide.app.chat.app import (
    CHAT_CSS,
    DEMO_WELCOME_MESSAGE,
    EMOTICONS_ENABLED,
    FEEDBACK_ACKNOWLEDGEMENT,
    _italicize_french_expressions,
    _render_response,
    create_app,
    placeholder_request_id,
    select_feedback,
    submit_feedback,
    update_feedback_values,
)
from ai_tour_guide.app.chat.backends import DemoBackend
from ai_tour_guide.app.chat.models import ChatHistoryItem


def _like_data(index: object, liked: object) -> gr.LikeData:
    data = MagicMock(spec=gr.LikeData)
    data.index = index
    data.liked = liked
    return data


def test_create_app_configures_chatbot_feedback_and_like_event() -> None:
    """Verify that create app configures chatbot feedback and like event."""
    app = create_app(DemoBackend())

    chatbot = next(
        component
        for component in app.blocks.values()
        if isinstance(component, gr.Chatbot)
    )

    assert chatbot.elem_id == 'rag-chat'
    assert app.config['title'] == 'Bon Voyage'
    assert chatbot.height == 'calc(100vh - 250px)'
    assert chatbot.value[0]['role'] == 'assistant'
    assert chatbot.value[0]['content'][0]['text'] == DEMO_WELCOME_MESSAGE
    assert len(chatbot.value) == 1
    avatar_images = chatbot.avatar_images
    assert avatar_images is not None
    user_avatar = avatar_images[0]
    bot_avatar = avatar_images[1]
    assert user_avatar is not None
    assert bot_avatar is not None
    assert user_avatar['path'].endswith('/user.png')
    assert bot_avatar['path'].endswith('/bot.png')
    assert chatbot.feedback_options == ('Like', 'Dislike')
    assert '.message-buttons-left button[aria-label="Liked"]' in CHAT_CSS
    assert '.message-buttons-left button[aria-label="Disliked"]' in CHAT_CSS
    assert '#rag-chat .avatar-container' in CHAT_CSS
    assert 'height: 80px' in CHAT_CSS
    assert '#rag-chat .message.bot' in CHAT_CSS
    assert 'margin-left: 0.5rem !important' in CHAT_CSS
    assert 'padding: 0.25rem 0.5rem !important' in CHAT_CSS
    assert 'max-height: none' in CHAT_CSS
    assert '#rag-chat .panel-wrap' in CHAT_CSS
    assert 'overflow-y: visible' in CHAT_CSS
    assert '#rag-chat .bubble-wrap' in CHAT_CSS
    assert 'height: 100%' in CHAT_CSS
    assert '#rag-chat [role="log"]' in CHAT_CSS
    assert 'content: "Petit Guide"' in CHAT_CSS
    assert 'content: "You"' in CHAT_CSS
    assert FEEDBACK_ACKNOWLEDGEMENT == 'Thanks for your feedback!'
    dependencies = app.config.get('dependencies', [])
    assert any(
        dependency['api_name'] == 'on_like'
        and dependency['show_progress'] == 'hidden'
        and len(dependency['outputs']) == 2
        for dependency in dependencies
    )
    assert any(
        dependency['api_name'] == '_submit_fn'
        and dependency['show_progress'] == 'minimal'
        for dependency in dependencies
    )


def test_create_app_explains_demo_limitations() -> None:
    """Verify that demo mode is disclosed in the initial welcome message."""
    app = create_app(DemoBackend())
    chatbot = next(
        component
        for component in app.blocks.values()
        if isinstance(component, gr.Chatbot)
    )

    welcome = chatbot.value[0]['content'][0]['text']
    assert welcome == DEMO_WELCOME_MESSAGE
    assert 'Bon Voyage' in welcome
    assert 'Brittany questions' in welcome
    assert chatbot.value[0]['options'] == [
        {'value': 'identity', 'label': 'Tell me about you'},
        {'value': 'destinations', 'label': 'What destinations are covered?'},
    ]


def test_placeholder_request_ids_are_unique_per_assistant_message() -> None:
    """Verify that placeholder request ids are unique per assistant message."""
    assert placeholder_request_id(1) == 'TODO: request_id:1'
    assert placeholder_request_id(2) == 'TODO: request_id:2'
    assert placeholder_request_id(1) != placeholder_request_id(2)


def test_render_response_omits_the_neutral_emoticon() -> None:
    """Verify that neutral answers do not render an emoticon."""
    rendered = _render_response(
        {'answer': 'The coast is beautiful.', 'sources': [], 'emotion': 'neutral'}
    )

    assert rendered == 'The coast is beautiful.'


def test_render_response_adds_special_emoticon_after_answer() -> None:
    """Verify that special emotions are currently disabled in the chat UI."""
    rendered = _render_response(
        {'answer': 'The coast is beautiful.', 'sources': [], 'emotion': 'happy'}
    )

    assert EMOTICONS_ENABLED is False
    assert rendered == 'The coast is beautiful.'


def test_italicize_french_expressions() -> None:
    """Verify that approved French expressions are rendered in italics."""
    assert _italicize_french_expressions('Voilà! En route!') == '*Voilà!* *En route!*'
    assert _italicize_french_expressions('*Voilà!*') == '*Voilà!*'


def test_update_feedback_values_preserves_previous_ratings() -> None:
    """Verify that update feedback values preserves previous ratings."""
    history: list[ChatHistoryItem] = [
        {'role': 'user', 'content': 'First question'},
        {'role': 'assistant', 'content': 'First answer'},
        {'role': 'user', 'content': 'Second question'},
        {'role': 'assistant', 'content': 'Second answer'},
    ]

    assert update_feedback_values(history, ['Like'], 3, False) == [
        'Like',
        'Dislike',
    ]


def test_submit_feedback_forwards_like_and_dislike_events() -> None:
    """Verify that submit feedback forwards like and dislike events."""
    backend = MagicMock()
    backend.submit_feedback = AsyncMock()
    request_ids = {1: 'TODO: request_id:1', 3: 'TODO: request_id:3'}

    first = select_feedback(request_ids, _like_data(1, True))
    second = select_feedback(request_ids, _like_data(3, False))
    asyncio.run(submit_feedback(first, backend))
    asyncio.run(submit_feedback(second, backend))

    assert backend.submit_feedback.await_args_list[0].args == (
        'TODO: request_id:1',
        True,
    )
    assert backend.submit_feedback.await_args_list[1].args == (
        'TODO: request_id:3',
        False,
    )


def test_submit_feedback_ignores_invalid_events() -> None:
    """Verify that submit feedback ignores invalid events."""
    backend = MagicMock()
    backend.submit_feedback = AsyncMock()
    request_ids = {1: 'TODO: request_id:1'}

    for data in (
        _like_data((1, 0), True),
        _like_data(1, None),
        _like_data(2, True),
    ):
        selection = select_feedback(request_ids, data)
        asyncio.run(submit_feedback(selection, backend))

    backend.submit_feedback.assert_not_awaited()
