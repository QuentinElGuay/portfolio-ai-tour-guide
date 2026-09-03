"""Tests for Petit Guide's fixed identity answers."""

from ai_tour_guide.app.agent.identity import (
    BON_VOYAGE_QUESTION,
    FRENCH_EXPRESSION_GUIDANCE,
    FRENCH_EXPRESSIONS,
    IDENTITY_ANSWERS,
    INFORMATION_SOURCES_QUESTION,
    PETIT_GUIDE_PERSONALITY,
    TELL_ME_ABOUT_YOU_QUESTION,
)


def test_identity_answers_explain_the_portfolio_rag_project() -> None:
    """Identity prompts describe the project and its grounded-answer approach."""
    about = IDENTITY_ANSWERS[TELL_ME_ABOUT_YOU_QUESTION]
    company = IDENTITY_ANSWERS[BON_VOYAGE_QUESTION]
    sources = IDENTITY_ANSWERS[INFORMATION_SOURCES_QUESTION]

    assert 'portfolio project' in about
    assert 'large language models (LLMs)' in about
    assert 'retrieval-augmented generation (RAG)' in about
    assert 'LLM Zoomcamp capstone' in company
    assert 'document ingestion' in company
    assert '[DataTalks.club](https://datatalks.club)' in company
    assert '[Ibanista](https://www.ibanista.com/)' in sources
    assert 'supporting sources' in sources


def test_petit_guide_has_explicit_playful_preferences() -> None:
    """Keep Petit Guide's personality specific and grounded."""
    assert 'Brittany' in PETIT_GUIDE_PERSONALITY
    assert 'scenic train rides' in PETIT_GUIDE_PERSONALITY
    assert 'coastal walks' in PETIT_GUIDE_PERSONALITY
    assert 'fresh baguette' in PETIT_GUIDE_PERSONALITY
    assert 'buttery croissant' in PETIT_GUIDE_PERSONALITY
    assert 'galette' in PETIT_GUIDE_PERSONALITY
    assert 'avec modération' in PETIT_GUIDE_PERSONALITY
    assert 'excellent choice' in PETIT_GUIDE_PERSONALITY
    assert 'always use the first person' in PETIT_GUIDE_PERSONALITY
    assert 'only when introducing yourself' in PETIT_GUIDE_PERSONALITY
    assert 'never as objective facts' in PETIT_GUIDE_PERSONALITY
    assert 'Keep your private life private' in PETIT_GUIDE_PERSONALITY
    assert 'politely refuse indecent or sexually suggestive offers' in (
        PETIT_GUIDE_PERSONALITY
    )


def test_french_expression_guidance_is_shared_with_the_chat_ui() -> None:
    """Keep the UI expression inventory aligned with prompt guidance."""
    assert FRENCH_EXPRESSIONS == tuple(FRENCH_EXPRESSION_GUIDANCE)
    assert 'Voilà!' in FRENCH_EXPRESSIONS
    assert 'Salut!' in FRENCH_EXPRESSIONS
