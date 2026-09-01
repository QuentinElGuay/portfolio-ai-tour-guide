"""Declarative navigation for guided chat prompts."""

from dataclasses import dataclass

from ai_tour_guide.agent.identity import (
    BACK_TO_MAIN_MENU_QUESTION,
    BAGUETTE_VOYAGES_QUESTION,
    INFORMATION_SOURCES_QUESTION,
    TELL_ME_ABOUT_YOU_QUESTION,
)

DESTINATION_CATALOG_QUESTION = 'What destinations are covered?'


@dataclass(frozen=True, slots=True)
class NavigationOption:
    """A stable prompt identity, display label, and submitted question."""

    id: str
    label: str
    question: str


OPTIONS = {
    'identity': NavigationOption(
        'identity', 'Tell me about you', TELL_ME_ABOUT_YOU_QUESTION
    ),
    'baguette_voyages': NavigationOption(
        'baguette_voyages', 'What is Baguette Voyages?', BAGUETTE_VOYAGES_QUESTION
    ),
    'information_sources': NavigationOption(
        'information_sources',
        'Where does your information come from?',
        INFORMATION_SOURCES_QUESTION,
    ),
    'destinations': NavigationOption(
        'destinations', 'What destinations are covered?', DESTINATION_CATALOG_QUESTION
    ),
    'main_menu': NavigationOption(
        'main_menu', 'Back to the main menu', BACK_TO_MAIN_MENU_QUESTION
    ),
}
MAIN_MENU = ('identity', 'destinations')
FOLLOW_UPS = {
    'identity': ('baguette_voyages', 'information_sources', 'main_menu'),
    'baguette_voyages': ('identity', 'information_sources', 'main_menu'),
    'information_sources': ('identity', 'baguette_voyages', 'main_menu'),
    'main_menu': MAIN_MENU,
}
QUESTION_TO_ID = {option.question: option.id for option in OPTIONS.values()}


def options_for_ids(option_ids: tuple[str, ...]) -> tuple[NavigationOption, ...]:
    """Resolve graph-selected option IDs into display options."""
    return tuple(OPTIONS[option_id] for option_id in option_ids)


def question_for_option_id(option_id: str) -> str | None:
    """Return the canonical question for a guided option ID."""
    option = OPTIONS.get(option_id)
    return option.question if option is not None else None


def normalize_option_id(option_id: str | None) -> str | None:
    """Accept only graph-owned option IDs at a client boundary."""
    return option_id if option_id in OPTIONS else None


def option_id_for_question(question: str) -> str | None:
    """Resolve a canonical displayed question into its guided option ID."""
    return QUESTION_TO_ID.get(question)


def next_option_ids(option_id: str) -> tuple[str, ...]:
    """Return graph-owned transitions for a guided option."""
    return tuple(FOLLOW_UPS.get(option_id, ()))


__all__ = [
    'DESTINATION_CATALOG_QUESTION',
    'MAIN_MENU',
    'OPTIONS',
    'NavigationOption',
    'next_option_ids',
    'normalize_option_id',
    'option_id_for_question',
    'options_for_ids',
    'question_for_option_id',
]
