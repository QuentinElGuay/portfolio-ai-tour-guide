"""Shared product context for Petit Guide and Bon Voyage."""

WELCOME_MESSAGE = (
    'Welcome to _Bon Voyage_ travel agency. How can I help you prepare your trip?'
)

PETIT_GUIDE_IDENTITY = (
    'Hi, I’m **Petit Guide**, _Bon Voyage_’s AI travel companion for French destinations '
    'covered by currently indexed regional tourism guides.\n'
    'My goal in this portfolio project is to demonstrate how large language models (LLMs) and '
    'retrieval-augmented generation (RAG) can turn curated regional tourism guides into '
    'grounded answers that help you get to know France and prepare your trip.'
)

TELL_ME_ABOUT_YOU_QUESTION = 'Tell me about you.'
DESTINATIONS_QUESTION = 'What destinations are covered?'
BON_VOYAGE_QUESTION = 'What is Bon Voyage?'
INFORMATION_SOURCES_QUESTION = 'Where does your information come from?'
BACK_TO_MAIN_MENU_QUESTION = 'Back to the main menu'
IDENTITY_QUESTIONS = (
    TELL_ME_ABOUT_YOU_QUESTION,
    BON_VOYAGE_QUESTION,
    INFORMATION_SOURCES_QUESTION,
)
IDENTITY_ANSWERS = {
    TELL_ME_ABOUT_YOU_QUESTION: PETIT_GUIDE_IDENTITY,
    BON_VOYAGE_QUESTION: (
        '_Bon Voyage_ is a fictional AI travel agency created for the '
        '[DataTalks.club](https://datatalks.club)’s LLM Zoomcamp capstone project. \n'
        'The goal of this project is to showcase an end-to-end RAG application: '
        'document ingestion, retrieval and prompt construction, LLM-generated answers, '
        'and a browser chat interface.'
    ),
    INFORMATION_SOURCES_QUESTION: (
        'I use RAG to retrieve relevant passages from regional tourism guides created by '
        '[Ibanista](https://www.ibanista.com/), a relocation company. Those passages '
        'give the LLM the context for a grounded answer, and the chat shows the supporting '
        'sources. If the guides do not support an answer, I should say so rather than make it up.'
    ),
    BACK_TO_MAIN_MENU_QUESTION: 'What would you like to know about France?',
}

__all__ = [
    'BACK_TO_MAIN_MENU_QUESTION',
    'BON_VOYAGE_QUESTION',
    'DESTINATIONS_QUESTION',
    'IDENTITY_ANSWERS',
    'IDENTITY_QUESTIONS',
    'INFORMATION_SOURCES_QUESTION',
    'PETIT_GUIDE_IDENTITY',
    'TELL_ME_ABOUT_YOU_QUESTION',
    'WELCOME_MESSAGE',
]
