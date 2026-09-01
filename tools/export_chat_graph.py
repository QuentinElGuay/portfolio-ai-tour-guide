"""Export the chat agent workflow as a Mermaid diagram."""

from argparse import ArgumentParser
from pathlib import Path
from unittest.mock import MagicMock

from ai_tour_guide.agent.rag.agent_workflow import build_agent_graph


def export_chat_graph(output: Path) -> Path:
    """Write the compiled chat workflow's Mermaid diagram to *output*."""
    graph = build_agent_graph(MagicMock(), engine=None, strategy=None)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(graph.get_graph().draw_mermaid(), encoding='utf-8')
    return output


def main() -> None:
    parser = ArgumentParser(description='Export the chat workflow as Mermaid.')
    parser.add_argument('--output', type=Path, default=Path('tmp/chat-graph.mmd'))
    args = parser.parse_args()
    print(export_chat_graph(args.output))


if __name__ == '__main__':
    main()
