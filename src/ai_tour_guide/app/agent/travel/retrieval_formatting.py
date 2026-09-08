"""User-facing formatting for retrieval-only evidence."""

from collections.abc import Sequence

from ai_tour_guide.knowledge_base.retrieval.tool import TourismEvidence

NO_RELEVANT_SECTIONS_ANSWER = (
    'I could not find relevant sections for that question in the available travel '
    'guides.'
)


def format_retrieval_evidence(evidence: Sequence[TourismEvidence]) -> str:
    """Render logical search contexts as readable Markdown with citations."""
    items = tuple(evidence)
    if not items:
        return NO_RELEVANT_SECTIONS_ANSWER

    result_label = 'section' if len(items) == 1 else 'sections'
    rendered = [f'🔎 {len(items)} relevant {result_label} found']
    for position, item in enumerate(items, start=1):
        section_title = item.section_path[-1] if item.section_path else item.title
        source = f'{item.title} · {section_title}'
        if item.pages:
            page_numbers = ', '.join(str(page) for page in item.pages)
            source = f'{source} (p. {page_numbers})'
        quoted_text = '\n\n'.join(
            f'*“{paragraph.strip()}”*'
            for paragraph in item.text.split('\n\n')
            if paragraph.strip()
        )
        rendered.extend(
            [
                f'{position}. {source}',
                quoted_text,
            ]
        )
    return '\n\n'.join(rendered)


__all__ = ['NO_RELEVANT_SECTIONS_ANSWER', 'format_retrieval_evidence']
