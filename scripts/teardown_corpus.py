"""CLI wrapper for clearing the configured knowledge base."""

import argparse

from ai_tour_guide.knowledge_base.corpus import clear_knowledge_base


def main() -> None:
    parser = argparse.ArgumentParser(description='Clear the configured knowledge base.')
    parser.add_argument(
        '--allow-destructive',
        action='store_true',
        help='Acknowledge that all knowledge-base rows will be deleted.',
    )
    args = parser.parse_args()

    if not args.allow_destructive:
        raise SystemExit(
            'Refusing to truncate the database without --allow-destructive'
        )

    # TODO: Add a project-specific guard that proves DB_NAME points to an
    # isolated test/evaluation database before destructive operations.
    clear_knowledge_base()


if __name__ == '__main__':
    main()
