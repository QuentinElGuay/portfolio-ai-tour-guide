import asyncio
from unittest.mock import AsyncMock, MagicMock

import gradio as gr

from ai_tour_guide.agent.chat.app import (
    CHAT_CSS,
    FEEDBACK_ACKNOWLEDGEMENT,
    create_app,
    placeholder_request_id,
    select_feedback,
    submit_feedback,
    update_feedback_values,
)
from ai_tour_guide.agent.chat.backends import DemoBackend
from ai_tour_guide.agent.chat.models import ChatHistoryItem


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
    assert chatbot.feedback_options == ('Like', 'Dislike')
    assert '.message-buttons-left button[aria-label="Liked"]' in CHAT_CSS
    assert '.message-buttons-left button[aria-label="Disliked"]' in CHAT_CSS
    assert FEEDBACK_ACKNOWLEDGEMENT == 'Thanks for your feedback!'
    dependencies = app.config.get('dependencies', [])
    assert any(
        dependency['api_name'] == 'on_like'
        and dependency['show_progress'] == 'hidden'
        and len(dependency['outputs']) == 2
        for dependency in dependencies
    )
    assert any(
        dependency['api_name'] == '_submit_fn' and dependency['show_progress'] == 'full'
        for dependency in dependencies
    )


def test_placeholder_request_ids_are_unique_per_assistant_message() -> None:
    """Verify that placeholder request ids are unique per assistant message."""
    assert placeholder_request_id(1) == 'TODO: request_id:1'
    assert placeholder_request_id(2) == 'TODO: request_id:2'
    assert placeholder_request_id(1) != placeholder_request_id(2)


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
