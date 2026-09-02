from uuid import UUID

import pytest
from pydantic import ValidationError

from ai_tour_guide.app.chat.models import (
    FREE_TEXT_INPUT_ID,
    ChatErrorCode,
    ChatErrorResponse,
    ChatFeedbackRequest,
    ChatFeedbackResponse,
    ChatMessageRequest,
    ConversationButton,
    ConversationResponse,
)


def test_chat_models_round_trip_json() -> None:
    session_id = UUID('12345678-1234-5678-1234-567812345678')
    response = ConversationResponse(
        session_id=session_id,
        step_id='welcome',
        message='Welcome.',
        buttons=[ConversationButton(input_id='destinations', label='Destinations')],
    )
    request = ChatMessageRequest(
        session_id=session_id,
        expected_step_id='welcome',
        input_id=FREE_TEXT_INPUT_ID,
        text='  What should I visit?  ',
    )
    feedback = ChatFeedbackResponse(message_id=UUID(int=1))

    assert (
        ConversationResponse.model_validate_json(response.model_dump_json()) == response
    )
    assert request.text == 'What should I visit?'
    assert (
        ChatFeedbackResponse.model_validate_json(feedback.model_dump_json()) == feedback
    )


def test_free_text_requires_non_empty_text() -> None:
    with pytest.raises(ValidationError, match='text must be non-empty'):
        ChatMessageRequest(
            session_id=UUID(int=0),
            expected_step_id='welcome',
            input_id=FREE_TEXT_INPUT_ID,
        )


def test_feedback_and_safe_error_models_serialize() -> None:
    feedback = ChatFeedbackRequest(
        message_id=UUID(int=1), helpful=True, comment='  Helpful. '
    )
    error = ChatErrorResponse(
        code=ChatErrorCode.STALE_STEP, message='The conversation has moved on.'
    )

    assert feedback.comment == 'Helpful.'
    assert feedback.model_dump(mode='json')['message_id'] == str(UUID(int=1))
    assert error.model_dump(mode='json') == {
        'code': 'stale_expected_step_id',
        'message': 'The conversation has moved on.',
    }
