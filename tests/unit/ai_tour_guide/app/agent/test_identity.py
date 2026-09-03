"""Tests for Petit Guide's fixed identity answers."""

from ai_tour_guide.app.agent.identity import (
    BON_VOYAGE_IDENTITY,
    BON_VOYAGE_QUESTION,
    FRENCH_EXPRESSION_GUIDANCE,
    FRENCH_EXPRESSIONS,
    IDENTITY_ANSWERS,
    INFORMATION_SOURCES_QUESTION,
    PETIT_GUIDE_IDENTITY,
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
    assert company == BON_VOYAGE_IDENTITY
    assert '[Ibanista](https://www.ibanista.com/)' in sources
    assert 'supporting sources' in sources


def test_petit_guide_identity_contains_facts_not_personality_traits() -> None:
    """Keep the fixed identity answer focused on role and project context."""
    assert 'AI travel assistant' in PETIT_GUIDE_IDENTITY
    assert 'currently indexed regional tourism guides' in PETIT_GUIDE_IDENTITY
    assert 'large language models (LLMs)' in PETIT_GUIDE_IDENTITY
    assert 'retrieval-augmented generation (RAG)' in PETIT_GUIDE_IDENTITY
    assert 'soft spot' not in PETIT_GUIDE_IDENTITY
    assert 'playful' not in PETIT_GUIDE_IDENTITY
    assert 'avec modération' not in PETIT_GUIDE_IDENTITY


def test_french_expression_guidance_is_shared_with_the_chat_ui() -> None:
    """Keep the UI expression inventory aligned with prompt guidance."""
    assert FRENCH_EXPRESSIONS == tuple(FRENCH_EXPRESSION_GUIDANCE)
    assert 'Voilà!' in FRENCH_EXPRESSIONS
    assert 'Salut!' in FRENCH_EXPRESSIONS
