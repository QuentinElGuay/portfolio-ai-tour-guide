from ai_tour_guide.domain.sections import compute_section_id
from ai_tour_guide.ingestion.chunking import chunk_document


def test_section_id_uses_heading_levels_not_section_path_positions() -> None:
    heading_path = (
        (1, 'The region and its departments'),
        (2, 'Departments of Brittany'),
        (3, 'Key features of each departments'),
    )

    section_id = compute_section_id(
        heading_path,
        min_depth=1,
        max_depth=2,
    )
    descendant_id = compute_section_id(
        heading_path,
        min_depth=1,
        max_depth=2,
    )

    assert section_id == descendant_id
    assert section_id is not None


def test_chunks_share_section_id_and_have_local_indexes() -> None:
    document = {
        'metadata': {'title': 'Guide to Brittany'},
        'sections': [
            {
                'title': 'The region and its departments',
                'level': 1,
                'paragraphs': [],
                'subsections': [
                    {
                        'title': 'Departments of Brittany',
                        'level': 2,
                        'paragraphs': [{'text': 'Introductory text.'}],
                        'subsections': [
                            {
                                'title': 'Key features',
                                'level': 3,
                                'paragraphs': [{'text': 'Department details.'}],
                                'subsections': [],
                            },
                        ],
                    },
                ],
            },
        ],
    }

    chunks = chunk_document(
        document,
        target_chars=100,
        max_chars=200,
        min_depth=1,
        max_depth=2,
    )

    assert len(chunks) == 2
    assert chunks[0].section_id == chunks[1].section_id
    assert [chunk.section_chunk_index for chunk in chunks] == [0, 1]
