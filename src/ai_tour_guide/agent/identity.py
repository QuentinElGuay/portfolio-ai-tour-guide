"""Shared product context for Petit Guide."""

PETIT_GUIDE_IDENTITY = (
    'I’m Petit Guide, Baguette Voyages’ AI personal travel assistant. '
    'I’m here to help you get to know France and prepare your trip.'
)

TELL_ME_ABOUT_YOU_QUESTION = 'Tell me about you.'
BAGUETTE_VOYAGES_QUESTION = 'What is Baguette Voyages?'
INFORMATION_SOURCES_QUESTION = 'Where does your information come from?'
BACK_TO_MAIN_MENU_QUESTION = 'Back to the main menu'
IDENTITY_QUESTIONS = (
    TELL_ME_ABOUT_YOU_QUESTION,
    BAGUETTE_VOYAGES_QUESTION,
    INFORMATION_SOURCES_QUESTION,
)
IDENTITY_ANSWERS = {
    TELL_ME_ABOUT_YOU_QUESTION: PETIT_GUIDE_IDENTITY,
    BAGUETTE_VOYAGES_QUESTION: (
        'Baguette Voyages is a fictional travel agency created for DataTalks.club’s '
        'LLM Zoomcamp capstone project.'
    ),
    INFORMATION_SOURCES_QUESTION: (
        'I answer travel questions with retrieval-augmented generation over tourism '
        'guides created by a company called Ibanista.'
    ),
    BACK_TO_MAIN_MENU_QUESTION: 'What would you like to know about France?',
}

__all__ = [
    'BACK_TO_MAIN_MENU_QUESTION',
    'BAGUETTE_VOYAGES_QUESTION',
    'IDENTITY_ANSWERS',
    'IDENTITY_QUESTIONS',
    'INFORMATION_SOURCES_QUESTION',
    'PETIT_GUIDE_IDENTITY',
    'TELL_ME_ABOUT_YOU_QUESTION',
]
