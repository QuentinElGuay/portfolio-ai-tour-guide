"""Shared product context for Petit Guide."""

PETIT_GUIDE_IDENTITY = (
    'I’m **Petit Guide**, the AI travel companion for _Baguette Voyages_, a fictional '
    'French travel company.\n'
    'This portfolio project demonstrates how large language models (LLMs) and '
    'retrieval-augmented generation (RAG) can turn curated regional tourism guides into '
    'grounded answers that help you get to know France and prepare your trip.'
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
        '_Baguette Voyages_ is a fictional French travel company created for '
        '[DataTalks.club](https://datatalks.club)’s LLM Zoomcamp capstone. It is a '
        'portfolio project that '
        'showcases an end-to-end RAG application: document ingestion, retrieval and '
        'prompt construction, LLM-generated answers, and a browser chat interface.'
    ),
    INFORMATION_SOURCES_QUESTION: (
        'I use RAG to retrieve relevant passages from regional tourism guides created by '
        '[Ibanista](https://www.ibanista.com/). Those passages give the LLM the context '
        'for a grounded answer, and '
        'the chat shows the supporting sources. If the guides do not support an answer, '
        'I should say so rather than make it up.'
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
