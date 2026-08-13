"""CLI wrapper for exporting the current knowledge-base corpus."""

import argparse
from pathlib import Path

from ai_tour_guide.knowledge_base.corpus import DEFAULT_CORPUS_ROOT, export_corpus


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Export the knowledge base as a corpus.'
    )
    parser.add_argument('--root', type=Path, default=DEFAULT_CORPUS_ROOT)
    args = parser.parse_args()
    path = export_corpus(root=args.root)
    print(path)


if __name__ == '__main__':
    main()
