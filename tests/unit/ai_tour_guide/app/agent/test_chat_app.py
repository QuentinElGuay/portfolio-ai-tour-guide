import asyncio
import os
import subprocess
import sys
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import gradio as gr
import pytest

from ai_tour_guide.app.chat.app import (
    CHAT_CSS,
    CHAT_SERVICE_ERROR_MESSAGE,
    EMOTICONS_ENABLED,
    FEEDBACK_ACKNOWLEDGEMENT,
    _italicize_french_expressions,
    _render_response,
    chat_css,
    create_app,
    is_demo_mode,
    main,
    placeholder_request_id,
    select_feedback,
    start_client_chat,
    submit_feedback,
    update_feedback_values,
)
from ai_tour_guide.app.chat.backends import DemoChatService
from ai_tour_guide.app.chat.models import ChatHistoryItem
from ai_tour_guide.app.services.demo.questions import DEMO_WELCOME_MESSAGE


def _like_data(index: object, liked: object) -> gr.LikeData:
    data = MagicMock(spec=gr.LikeData)
    data.index = index
    data.liked = liked
    return data


def _registered_function(app: gr.Blocks, name: str) -> Callable[..., Any]:
    """Return a registered Gradio callback whose presence is required by the test."""
    block_function = next(
        (function for function in app.fns.values() if function.name == name),
        None,
    )
    assert block_function is not None
    assert block_function.fn is not None
    return block_function.fn


@patch('ai_tour_guide.app.chat.app.create_app')
@patch(
    'ai_tour_guide.app.chat.app.create_chat_service',
    return_value=DemoChatService(),
)
def test_main_hides_gradio_footer(
    create_chat_service: MagicMock,
    create_app: MagicMock,
) -> None:
    """Hide Gradio footer controls that are irrelevant to this app."""
    app = MagicMock()
    create_app.return_value = app

    main()

    create_chat_service.assert_called_once_with()
    app.launch.assert_called_once()
    assert app.launch.call_args.kwargs['footer_links'] == []


def test_create_app_configures_chatbot_feedback_and_like_event() -> None:
    """Verify that create app configures chatbot feedback and like event."""
    app = create_app(DemoChatService())

    chatbot = next(
        component
        for component in app.blocks.values()
        if isinstance(component, gr.Chatbot)
    )

    assert chatbot.elem_id == 'chat'
    assert app.config['title'] == 'Bon Voyage'
    llm_labels = [
        component
        for component in app.blocks.values()
        if isinstance(component, gr.Markdown) and component.elem_classes == ['llm-info']
    ]
    assert len(llm_labels) == 1
    assert llm_labels[0].value == ''
    assert chatbot.height == 'calc(100vh - 250px)'
    assert chatbot.value == []
    assert chatbot.placeholder == (
        '<h2>Starting your conversation with Petit Guide…</h2>'
        '<p>Please wait a moment.</p>'
    )
    avatar_images = chatbot.avatar_images
    assert avatar_images is not None
    user_avatar = avatar_images[0]
    bot_avatar = avatar_images[1]
    assert user_avatar is not None
    assert bot_avatar is not None
    assert user_avatar['path'].endswith('/user.png')
    assert bot_avatar['path'].endswith('/bot.png')
    assert chatbot.feedback_options == ('Like', 'Dislike')
    textbox = next(
        component
        for component in app.blocks.values()
        if isinstance(component, gr.Textbox)
    )
    assert list(app.blocks).index(chatbot._id) < list(app.blocks).index(textbox._id)
    assert '.message-buttons-left button[aria-label="Liked"]' in CHAT_CSS
    assert '.message-buttons-left button[aria-label="Disliked"]' in CHAT_CSS
    assert '#chat .avatar-container' in CHAT_CSS
    assert 'height: 80px' in CHAT_CSS
    assert '#chat .message.bot' in CHAT_CSS
    assert 'margin-left: 0.5rem !important' in CHAT_CSS
    assert 'padding: 0.25rem 0.5rem !important' in CHAT_CSS
    assert 'max-height: none' in CHAT_CSS
    assert '#chat .panel-wrap' in CHAT_CSS
    assert 'overflow-y: visible' in CHAT_CSS
    assert '#chat .bubble-wrap' in CHAT_CSS
    assert 'height: 100%' in CHAT_CSS
    assert '#chat [role="log"]' in CHAT_CSS
    assert 'content: "__assistant_label__"' in CHAT_CSS
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
        dependency['api_name'] == 'respond' and dependency['show_progress'] == 'minimal'
        for dependency in dependencies
    )
    assert any(
        dependency['api_name'] == 'initialize_client'
        and dependency['show_progress'] == 'hidden'
        and len(dependency['outputs']) == 3
        for dependency in dependencies
    )


def test_start_client_chat_creates_an_independent_demo_session() -> None:
    """Verify that every Gradio client receives its own chat-service session."""
    service = DemoChatService()
    first_state, first_history, first_llm_label = asyncio.run(
        start_client_chat(service)
    )
    second_state, second_history, second_llm_label = asyncio.run(
        start_client_chat(service)
    )

    assert first_state['session_id'] != second_state['session_id']
    assert first_state['step_id'] == second_state['step_id'] == 'welcome'
    assert first_history[0]['content'] == DEMO_WELCOME_MESSAGE
    assert first_history[0].get('options') == [
        {'label': 'Tell me about you', 'value': 'Tell me about you'},
        {
            'label': 'What destinations are covered?',
            'value': 'What destinations are covered?',
        },
    ]
    assert second_history == first_history
    assert (
        first_llm_label
        == second_llm_label
        == ('Model: `baguette-llm - mini-croissant-1.0`')
    )


def test_first_option_keeps_the_backend_welcome_in_history() -> None:
    """Keep the welcome and render the user option before the service response."""
    app = create_app(DemoChatService())
    initialize_client = _registered_function(app, 'initialize_client')
    respond = _registered_function(app, 'respond')
    add_user_message = _registered_function(app, 'add_user_message')
    request_ids, history, _ = asyncio.run(initialize_client())

    _, history_with_user, pending_message = add_user_message(
        'Tell me about you', history
    )
    _, updated_history, _ = asyncio.run(
        respond(pending_message, history_with_user, request_ids)
    )

    assert history_with_user[0]['content'] == DEMO_WELCOME_MESSAGE
    assert history_with_user[1] == {
        'role': 'user',
        'content': 'Tell me about you',
    }
    assert updated_history[:2] == history_with_user
    assert 'Petit Guide' in str(updated_history[2]['content'])


def test_chat_css_uses_a_demo_label_only_for_the_demo_service() -> None:
    """Verify that demo mode is shown in the assistant label."""
    assert 'content: "Petit Guide (demo mode)"' in chat_css(demo_mode=True)
    assert 'content: "Petit Guide"' in chat_css(demo_mode=False)


def test_is_demo_mode_uses_the_configured_llm_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('AGENT_LLM_PROVIDER', 'baguette-llm')
    assert is_demo_mode() is True

    monkeypatch.setenv('AGENT_LLM_PROVIDER', 'openai')
    assert is_demo_mode() is False


def test_chat_app_import_does_not_require_embedding_settings(tmp_path) -> None:
    """Keep the lightweight chat process independent of RAG configuration."""
    environment = dict(os.environ)
    environment.pop('EMBEDDING_DIMENSIONS', None)
    environment.pop('EMBEDDING_MODEL_NAME', None)

    result = subprocess.run(
        [sys.executable, '-c', 'import ai_tour_guide.app.chat.app'],
        check=False,
        capture_output=True,
        cwd=tmp_path,
        env=environment,
        text=True,
    )

    assert result.returncode == 0, result.stderr


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


def test_italicize_all_registered_french_expressions() -> None:
    """Keep every shared French expression formatted in italics by the UI."""
    from ai_tour_guide.app.agent.identity import FRENCH_EXPRESSIONS

    rendered = _italicize_french_expressions(' '.join(FRENCH_EXPRESSIONS))

    assert rendered == ' '.join(f'*{expression}*' for expression in FRENCH_EXPRESSIONS)


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
    service = MagicMock()
    service.submit_feedback = AsyncMock()
    request_ids = {1: 'TODO: request_id:1', 3: 'TODO: request_id:3'}

    first = select_feedback(request_ids, _like_data(1, True))
    second = select_feedback(request_ids, _like_data(3, False))
    asyncio.run(submit_feedback(first, service))
    asyncio.run(submit_feedback(second, service))

    assert service.submit_feedback.await_args_list[0].args == (
        'TODO: request_id:1',
        True,
    )
    assert service.submit_feedback.await_args_list[1].args == (
        'TODO: request_id:3',
        False,
    )


def test_submit_feedback_ignores_invalid_events() -> None:
    """Verify that submit feedback ignores invalid events."""
    service = MagicMock()
    service.submit_feedback = AsyncMock()
    request_ids = {1: 'TODO: request_id:1'}

    for data in (
        _like_data((1, 0), True),
        _like_data(1, None),
        _like_data(2, True),
    ):
        selection = select_feedback(request_ids, data)
        asyncio.run(submit_feedback(selection, service))

    service.submit_feedback.assert_not_awaited()


def test_chat_service_error_message_does_not_expose_transport_details() -> None:
    """Keep client-side chat-service failures safe and human-oriented."""
    assert 'Backend error' not in CHAT_SERVICE_ERROR_MESSAGE
    assert 'Chat API request failed' not in CHAT_SERVICE_ERROR_MESSAGE
    assert "I'm" in CHAT_SERVICE_ERROR_MESSAGE
