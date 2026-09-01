"""Semantic conversation steps owned by the backend graph."""

from enum import StrEnum


class FlowStep(StrEnum):
    """Stable user-facing stages used for conversation analytics."""

    MAIN_MENU = 'main_menu'
    IDENTITY = 'identity'
    DESTINATIONS = 'destinations'


DEFAULT_FLOW_STEP = FlowStep.MAIN_MENU


def flow_step_for_option(
    option_id: str | None, current_step: FlowStep = DEFAULT_FLOW_STEP
) -> FlowStep:
    """Resolve a guided option while keeping free-text routing internal."""
    if option_id in {'identity', 'baguette_voyages', 'information_sources'}:
        return FlowStep.IDENTITY
    if option_id == 'destinations':
        return FlowStep.DESTINATIONS
    if option_id == 'main_menu':
        return FlowStep.MAIN_MENU
    return current_step


def input_type_for_option(option_id: str | None) -> str:
    """Classify a turn for analytics without exposing graph control."""
    return (
        'guided'
        if option_id
        in {
            'identity',
            'baguette_voyages',
            'information_sources',
            'destinations',
            'main_menu',
        }
        else 'free_text'
    )


__all__ = [
    'DEFAULT_FLOW_STEP',
    'FlowStep',
    'flow_step_for_option',
    'input_type_for_option',
]
