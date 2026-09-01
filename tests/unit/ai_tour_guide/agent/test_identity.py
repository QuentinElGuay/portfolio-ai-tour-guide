"""Tests for Petit Guide's fixed identity answers."""

from ai_tour_guide.agent.identity import (
    BAGUETTE_VOYAGES_QUESTION,
    IDENTITY_ANSWERS,
    INFORMATION_SOURCES_QUESTION,
    TELL_ME_ABOUT_YOU_QUESTION,
)


def test_identity_answers_explain_the_portfolio_rag_project() -> None:
    """Identity prompts describe the project and its grounded-answer approach."""
    about = IDENTITY_ANSWERS[TELL_ME_ABOUT_YOU_QUESTION]
    company = IDENTITY_ANSWERS[BAGUETTE_VOYAGES_QUESTION]
    sources = IDENTITY_ANSWERS[INFORMATION_SOURCES_QUESTION]

    assert 'portfolio project' in about
    assert 'large language models (LLMs)' in about
    assert 'retrieval-augmented generation (RAG)' in about
    assert 'LLM Zoomcamp capstone' in company
    assert 'document ingestion' in company
    assert '[DataTalks.club](https://datatalks.club)' in company
    assert '[Ibanista](https://www.ibanista.com/)' in sources
    assert 'supporting sources' in sources
