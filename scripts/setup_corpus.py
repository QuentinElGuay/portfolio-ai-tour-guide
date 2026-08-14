"""CLI wrapper for loading the current corpus into the knowledge base."""

import argparse
from pathlib import Path

from ai_tour_guide.knowledge_base.corpus import DEFAULT_CORPUS_ROOT, load_corpus


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Replace the knowledge base with a corpus.'
    )
    parser.add_argument('--root', type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument(
        '--schema',
        choices=('public', 'test', 'evaluation'),
        default='public',
        help='Database schema to initialize and load.',
    )
    parser.add_argument(
        '--allow-destructive',
        action='store_true',
        help='Acknowledge that current knowledge-base rows will be deleted.',
    )
    args = parser.parse_args()

    if not args.allow_destructive:
        raise SystemExit('Refusing to reset the database without --allow-destructive')

    # TODO: Add a project-specific guard that proves DB_NAME points to an
    # isolated test/evaluation database before destructive operations.
    path = load_corpus(root=args.root, schema_name=args.schema)
    print(path)


if __name__ == '__main__':
    main()
