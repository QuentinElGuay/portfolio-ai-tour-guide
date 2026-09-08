"""Deprecated compatibility helpers; flow definitions live in ``agent.flow``."""

from ai_tour_guide.app.agent.flow import FLOW_QUESTIONS, FLOW_TRANSITIONS, FlowStep

DESTINATION_CATALOG_QUESTION = FLOW_QUESTIONS['destinations']
MAIN_MENU = ('identity', 'destinations')


def question_for_option_id(option_id: str) -> str | None:
    """Resolve an internal option for legacy agent adapters."""
    return FLOW_QUESTIONS.get(option_id)


def normalize_option_id(option_id: str | None) -> str | None:
    """Accept only chat-service option IDs for legacy agent adapters."""
    return option_id if option_id in FLOW_QUESTIONS else None


def next_option_ids(option_id: str) -> tuple[str, ...]:
    """Return chat-service transitions for legacy agent adapters."""
    transitions = {
        input_id: next_step
        for step in FlowStep
        for input_id, next_step in FLOW_TRANSITIONS.get(step, {}).items()
    }
    return tuple(input_id for input_id in transitions if input_id == option_id)


__all__ = [
    'DESTINATION_CATALOG_QUESTION',
    'MAIN_MENU',
    'next_option_ids',
    'normalize_option_id',
    'question_for_option_id',
]
