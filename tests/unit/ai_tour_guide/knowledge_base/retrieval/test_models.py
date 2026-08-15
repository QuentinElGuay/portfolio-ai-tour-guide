"""Skeleton tests for temporary LLM context contracts."""


def test_retrieved_context_keeps_triggering_search_results_and_context_sources() -> None:
    """Construct ``RetrievedContext`` for one expanded section.

    Required fixtures: multiple SearchResults pointing to the same section plus SourceMetadata for every
    sibling chunk actually included in context text.
    Expected verification: search_results explain why the section was selected, while sources describe all
    evidence the LLM can cite after expansion.
    """
    pass
