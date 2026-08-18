import asyncio
from unittest.mock import AsyncMock, MagicMock

import gradio as gr

from ai_tour_guide.agent.chat.app import (
    create_app,
    placeholder_request_id,
    submit_feedback,
)
from ai_tour_guide.agent.chat.backends import DemoBackend


def _like_data(index: object, liked: object) -> gr.LikeData:
    data = MagicMock(spec=gr.LikeData)
    data.index = index
    data.liked = liked
    return data


def test_create_app_configures_chatbot_feedback_and_like_event() -> None:
    app = create_app(DemoBackend())

    chatbot = next(
        component
        for component in app.blocks.values()
        if isinstance(component, gr.Chatbot)
    )

    assert chatbot.elem_id == 'rag-chat'
    assert chatbot.feedback_options == ('Like', 'Dislike')
    assert any(
        dependency['api_name'] == 'on_like'
        and dependency['show_progress'] == 'hidden'
        and dependency['outputs'] == []
        for dependency in app.config['dependencies']
    )


def test_placeholder_request_ids_are_unique_per_assistant_message() -> None:
    assert placeholder_request_id(1) == 'TODO: request_id:1'
    assert placeholder_request_id(2) == 'TODO: request_id:2'
    assert placeholder_request_id(1) != placeholder_request_id(2)


def test_submit_feedback_forwards_like_and_dislike_events() -> None:
    backend = MagicMock()
    backend.submit_feedback = AsyncMock()
    request_ids = {1: 'TODO: request_id:1', 3: 'TODO: request_id:3'}

    asyncio.run(submit_feedback(request_ids, backend, _like_data(1, True)))
    asyncio.run(submit_feedback(request_ids, backend, _like_data(3, False)))

    assert backend.submit_feedback.await_args_list[0].args == (
        'TODO: request_id:1',
        True,
    )
    assert backend.submit_feedback.await_args_list[1].args == (
        'TODO: request_id:3',
        False,
    )


def test_submit_feedback_ignores_invalid_events() -> None:
    backend = MagicMock()
    backend.submit_feedback = AsyncMock()
    request_ids = {1: 'TODO: request_id:1'}

    for data in (
        _like_data((1, 0), True),
        _like_data(1, None),
        _like_data(2, True),
    ):
        asyncio.run(submit_feedback(request_ids, backend, data))

    backend.submit_feedback.assert_not_awaited()
