"""CLI wrapper for loading a versioned corpus into the knowledge base."""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_tour_guide.knowledge_base.corpus import DEFAULT_CORPUS_ROOT, load_corpus


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace the knowledge base with a corpus.")
    parser.add_argument("version", type=int, help="Positive corpus version number.")
    parser.add_argument("--root", type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument(
        "--allow-destructive",
        action="store_true",
        help="Acknowledge that current knowledge-base rows will be deleted.",
    )
    args = parser.parse_args()

    if not args.allow_destructive:
        raise SystemExit("Refusing to reset the database without --allow-destructive")

    # TODO: Add a project-specific guard that proves DB_NAME points to an
    # isolated test/evaluation database before destructive operations.
    path = load_corpus(args.version, root=args.root)
    print(path)


if __name__ == "__main__":
    main()
