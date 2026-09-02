"""Backend-owned deterministic conversation flow definitions."""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from ai_tour_guide.app.agent.identity import (
    BACK_TO_MAIN_MENU_QUESTION,
    BON_VOYAGE_QUESTION,
    INFORMATION_SOURCES_QUESTION,
    TELL_ME_ABOUT_YOU_QUESTION,
)
from ai_tour_guide.app.chat.models import (
    FREE_TEXT_INPUT_ID,
    ConversationButton,
)


class FlowStep(StrEnum):
    """Stable user-facing stages used for conversation analytics."""

    MAIN_MENU = 'main_menu'
    WELCOME = 'welcome'
    IDENTITY = 'identity'
    DESTINATIONS = 'destinations'
    BON_VOYAGE = 'bon_voyage'
    INFORMATION_SOURCES = 'information_sources'
    TERMINAL = 'terminal'


DEFAULT_FLOW_STEP = FlowStep.MAIN_MENU
type FlowInputId = str


@dataclass(frozen=True, slots=True)
class FlowAction:
    """A stable backend action and its client-facing label."""

    input_id: FlowInputId
    label: str

    def button(self) -> ConversationButton:
        return ConversationButton(input_id=self.input_id, label=self.label)


@dataclass(frozen=True, slots=True)
class FlowDefinition:
    """One conversation step with deterministic actions and text policy."""

    step_id: FlowStep
    buttons: tuple[FlowAction, ...] = ()
    accepts_free_text: bool = True

    def rendered_buttons(self) -> list[ConversationButton]:
        return [action.button() for action in self.buttons]


FLOW_DEFINITIONS: Final = MappingProxyType(
    {
        FlowStep.WELCOME: FlowDefinition(
            FlowStep.WELCOME,
            (
                FlowAction('identity', 'Tell me about you'),
                FlowAction('destinations', 'What destinations are covered?'),
            ),
        ),
        FlowStep.MAIN_MENU: FlowDefinition(
            FlowStep.MAIN_MENU,
            (
                FlowAction('identity', 'Tell me about you'),
                FlowAction('destinations', 'What destinations are covered?'),
            ),
        ),
        FlowStep.IDENTITY: FlowDefinition(
            FlowStep.IDENTITY,
            (
                FlowAction('bon_voyage', 'What is Bon Voyage?'),
                FlowAction(
                    'information_sources', 'Where does your information come from?'
                ),
                FlowAction('main_menu', 'Back to the main menu'),
            ),
        ),
        FlowStep.DESTINATIONS: FlowDefinition(
            FlowStep.DESTINATIONS,
            (FlowAction('main_menu', 'Back to the main menu'),),
        ),
        FlowStep.BON_VOYAGE: FlowDefinition(
            FlowStep.BON_VOYAGE,
            (FlowAction('main_menu', 'Back to the main menu'),),
        ),
        FlowStep.INFORMATION_SOURCES: FlowDefinition(
            FlowStep.INFORMATION_SOURCES,
            (FlowAction('main_menu', 'Back to the main menu'),),
        ),
        FlowStep.TERMINAL: FlowDefinition(
            FlowStep.TERMINAL, (), accepts_free_text=False
        ),
    }
)

FLOW_QUESTIONS: Final = MappingProxyType(
    {
        'identity': TELL_ME_ABOUT_YOU_QUESTION,
        'destinations': 'What destinations are covered?',
        'bon_voyage': BON_VOYAGE_QUESTION,
        'information_sources': INFORMATION_SOURCES_QUESTION,
        'main_menu': BACK_TO_MAIN_MENU_QUESTION,
    }
)

FLOW_TRANSITIONS: Final = MappingProxyType(
    {
        FlowStep.WELCOME: MappingProxyType(
            {
                'identity': FlowStep.IDENTITY,
                'destinations': FlowStep.DESTINATIONS,
            }
        ),
        FlowStep.MAIN_MENU: MappingProxyType(
            {
                'identity': FlowStep.IDENTITY,
                'destinations': FlowStep.DESTINATIONS,
            }
        ),
        FlowStep.IDENTITY: MappingProxyType(
            {
                'bon_voyage': FlowStep.BON_VOYAGE,
                'information_sources': FlowStep.INFORMATION_SOURCES,
                'main_menu': FlowStep.MAIN_MENU,
            }
        ),
        FlowStep.DESTINATIONS: MappingProxyType({'main_menu': FlowStep.MAIN_MENU}),
        FlowStep.BON_VOYAGE: MappingProxyType({'main_menu': FlowStep.MAIN_MENU}),
        FlowStep.INFORMATION_SOURCES: MappingProxyType(
            {'main_menu': FlowStep.MAIN_MENU}
        ),
    }
)


def flow_definition(step_id: str | FlowStep) -> FlowDefinition:
    """Return the backend definition for a stable public step ID."""
    return FLOW_DEFINITIONS[FlowStep(step_id)]


def transition_for(
    step_id: str | FlowStep,
    input_id: FlowInputId,
    *,
    text: str | None = None,
) -> FlowStep | None:
    """Resolve a validated guided action, or preserve the step for free text."""
    step = FlowStep(step_id)
    if input_id == FREE_TEXT_INPUT_ID:
        return step if flow_definition(step).accepts_free_text and text else None
    return FLOW_TRANSITIONS.get(step, {}).get(input_id)


def flow_step_for_option(
    option_id: str | None, current_step: FlowStep = DEFAULT_FLOW_STEP
) -> FlowStep:
    """Resolve a guided option while keeping free-text routing internal."""
    if option_id in {'identity', 'bon_voyage', 'information_sources'}:
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
            'bon_voyage',
            'information_sources',
            'destinations',
            'main_menu',
        }
        else 'free_text'
    )


__all__ = [
    'DEFAULT_FLOW_STEP',
    'FLOW_DEFINITIONS',
    'FLOW_QUESTIONS',
    'FLOW_TRANSITIONS',
    'FlowAction',
    'FlowDefinition',
    'FlowInputId',
    'FlowStep',
    'flow_definition',
    'flow_step_for_option',
    'input_type_for_option',
    'transition_for',
]
