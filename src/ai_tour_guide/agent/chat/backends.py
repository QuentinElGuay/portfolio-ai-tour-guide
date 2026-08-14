from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Protocol

import httpx

from ai_tour_guide.agent.chat.models import Message
from ai_tour_guide.agent.responses import NO_BACKEND_AVAILABLE_ANSWER

SUPPORTED_ASK_RESPONSE_SCHEMA_VERSION = 1


def create_backend() -> ChatBackend:
    api_url = os.getenv('CHAT_API_URL')
    if api_url:
        return HttpChatBackend(api_url=api_url)
    return DemoBackend()


class ChatBackend(Protocol):
    async def ask(self, messages: Sequence[Message]) -> dict[str, object]: ...


class DemoBackend:
    """Development fallback with the same payload contract as the API."""

    async def ask(self, messages: Sequence[Message]) -> dict[str, object]:
        return {
            'schema_version': SUPPORTED_ASK_RESPONSE_SCHEMA_VERSION,
            'answer': NO_BACKEND_AVAILABLE_ANSWER,
            'sources': [],
        }


class HttpChatBackend:
    def __init__(self, api_url: str, timeout_seconds: float = 60.0) -> None:
        self.api_url = api_url
        self.timeout = httpx.Timeout(timeout_seconds)

    async def ask(self, messages: Sequence[Message]) -> dict[str, object]:
        question = next(
            (
                message['content']
                for message in reversed(messages)
                if message['role'] == 'user'
            ),
            '',
        )
        if not question.strip():
            raise RuntimeError('The conversation does not contain a user question.')
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.api_url, json={'question': question})
                response.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError('Unable to connect to the chat API.') from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f'The chat API returned HTTP {exc.response.status_code}.'
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f'Chat API request failed: {exc}') from exc
        try:
            payload = response.json()
            answer = payload['answer']
            sources = payload.get('sources', [])

            if not isinstance(payload, dict):
                raise TypeError

            if payload.get('schema_version') != SUPPORTED_ASK_RESPONSE_SCHEMA_VERSION:
                raise RuntimeError(
                    'The chat API returned an unsupported schema version.'
                )

            if not isinstance(payload.get('answer'), str) or not isinstance(
                payload.get('sources'), list
            ):
                raise TypeError

        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError(
                "Invalid API response. Expected {'answer': '...', 'sources': [...]}."
            ) from exc

        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError('The chat API returned an empty response.')
        if not isinstance(sources, list):
            raise RuntimeError(  # noqa: TRY004
                'The chat API returned invalid sources.'
            )

        return _format_answer(answer, sources)


def _format_answer(answer: str, sources: list[object]) -> str:
    source_pages: dict[str, set[int]] = {}
    sources_without_pages: list[str] = []

    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get('title'), str):
            raise RuntimeError(  # noqa: TRY004
                'The chat API returned an invalid source.'
            )

        title = source['title']
        page_start = source.get('page_start')
        page_end = source.get('page_end')
        if isinstance(page_start, int) and isinstance(page_end, int):
            pages = source_pages.setdefault(title, set())
            pages.update(range(page_start, page_end + 1))
        elif isinstance(page_start, int):
            source_pages.setdefault(title, set()).add(page_start)
        elif title not in source_pages and title not in sources_without_pages:
            sources_without_pages.append(title)

    formatted_sources = [
        f'{title} ({_format_pages(sorted(pages))})'
        for title, pages in source_pages.items()
    ]
    formatted_sources.extend(sources_without_pages)

    if not formatted_sources:
        return answer

    return f'{answer}\n\n**Sources**\n\n' + '\n'.join(formatted_sources)


# TODO: page formatting should be shared with ai_tour_guide.agent.cli.ask_command
# See src/ai_tour_guide/agent/source_formatting.py
def _format_pages(pages: list[int]) -> str:
    page_numbers = [str(page) for page in pages]
    if len(page_numbers) == 1:
        return f'page {page_numbers[0]}'
    if len(page_numbers) == 2:
        return f'pages {page_numbers[0]} and {page_numbers[1]}'

    return f'pages {", ".join(page_numbers[:-1])} and {page_numbers[-1]}'
