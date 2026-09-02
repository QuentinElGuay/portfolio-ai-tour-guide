"""Provider-neutral, one-turn travel-agent boundary."""

from collections.abc import Awaitable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from inspect import isawaitable
from typing import Literal, Protocol, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from ai_tour_guide.app.agent.llm.clients import GenerationError, LLMClient
from ai_tour_guide.app.agent.rag.models import GeneratedAnswer, LLMCitation
from ai_tour_guide.app.agent.rag.tools import (
    RetrievalStatus,
    TourismEvidence,
    TourismSearchQuery,
    TourismSearchResult,
    search_tourism_knowledge_base,
)
from ai_tour_guide.app.agent.responses import INSUFFICIENT_CONTEXT_ANSWER
from ai_tour_guide.app.chat.models import Message, Role

MAX_SEARCH_RETRIES = 1


class TravelAgentAction(StrEnum):
    """Actions the turn-level agent is allowed to execute."""

    SEARCH_KNOWLEDGE_BASE = 'search_knowledge_base'
    REFORMULATE_SEARCH = 'reformulate_search'
    ANSWER_FROM_CONTEXT = 'answer_from_context'
    REFUSE = 'refuse'


class TravelAgentStatus(StrEnum):
    """Public operational outcomes of one agent turn."""

    ANSWERED = 'answered'
    REFUSED = 'refused'
    NO_EVIDENCE = 'no_evidence'
    RETRIEVAL_ERROR = 'retrieval_error'
    GENERATION_ERROR = 'generation_error'


@dataclass(frozen=True, slots=True)
class TravelAgentTrace:
    """Operational trace data without private model reasoning."""

    intent: str
    actions: tuple[TravelAgentAction, ...]
    queries: tuple[str, ...]
    tool_call_count: int
    evidence_sufficient: bool
    retries: int
    final_status: TravelAgentStatus


@dataclass(frozen=True, slots=True)
class TravelAgentResult:
    """Structured result of one bounded answer-producing turn."""

    answer: str
    status: TravelAgentStatus
    generated: GeneratedAnswer | None
    citations: tuple[LLMCitation, ...] = ()
    trace: TravelAgentTrace = field(
        default_factory=lambda: TravelAgentTrace(
            intent='unknown',
            actions=(),
            queries=(),
            tool_call_count=0,
            evidence_sufficient=False,
            retries=0,
            final_status=TravelAgentStatus.REFUSED,
        )
    )


class TravelAgentState(TypedDict, total=False):
    """State exchanged by the bounded turn-level agent subgraph."""

    question: str
    intent: str
    planned_action: str
    tool_calls: int
    evidence: tuple[TourismEvidence, ...]
    retry_count: int
    answer: str
    citations: tuple[LLMCitation, ...]
    final_status: TravelAgentStatus
    result: TravelAgentResult
    queries: list[str]
    next_query: str | None
    next_step: Literal['search', 'plan', 'answer', 'terminal']
    search_result: TourismSearchResult
    actions: list[TravelAgentAction]


class TourismSearch(Protocol):
    def __call__(
        self, query: TourismSearchQuery
    ) -> TourismSearchResult | Awaitable[TourismSearchResult]:
        """Search the approved tourism knowledge base."""
        ...


def _context_messages(
    question: str, result: TourismSearchResult
) -> tuple[Message, ...]:
    evidence = '\n\n'.join(
        f'[{item.title}, pages {", ".join(map(str, item.pages))}]\n{item.text}'
        for item in result.evidence
    )
    return (
        Message(
            role=Role.SYSTEM,
            content=(
                'Answer using only the supplied tourism evidence. If it does not '
                'support the answer, say so. Evidence:\n' + evidence
            ),
        ),
        Message(role=Role.USER, content=question),
    )


class TravelAgent:
    """Produce one bounded, source-grounded answer independently of UI and API flow."""

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        search_tool: TourismSearch = search_tourism_knowledge_base,
        max_search_retries: int = MAX_SEARCH_RETRIES,
    ) -> None:
        if max_search_retries < 0:
            raise ValueError('max_search_retries must be non-negative')
        self._llm_client = llm_client
        self._search_tool = search_tool
        self._max_search_retries = max_search_retries

    async def answer(self, question: str) -> TravelAgentResult:
        """Run the bounded LangGraph turn-level workflow."""
        graph = build_travel_agent_graph(self)
        state = await graph.ainvoke({'question': question})
        return cast(TravelAgentResult, state['result'])

    @staticmethod
    def _refusal(
        intent: str,
        queries: list[str] | tuple[str, ...],
        actions: Sequence[TravelAgentAction] = (),
        retries: int = 0,
    ) -> TravelAgentResult:
        return TravelAgent._result(
            INSUFFICIENT_CONTEXT_ANSWER,
            TravelAgentStatus.REFUSED,
            None,
            [*actions, TravelAgentAction.REFUSE],
            queries,
            retries,
            False,
            intent=intent,
        )

    @staticmethod
    def _result(
        answer: str,
        status: TravelAgentStatus,
        generated: GeneratedAnswer | None,
        actions: Sequence[TravelAgentAction],
        queries: Sequence[str],
        retries: int,
        evidence_sufficient: bool,
        *,
        intent: str = 'travel_question',
    ) -> TravelAgentResult:
        trace = TravelAgentTrace(
            intent=intent,
            actions=tuple(actions),
            queries=tuple(queries),
            tool_call_count=len(queries),
            evidence_sufficient=evidence_sufficient,
            retries=retries,
            final_status=status,
        )
        return TravelAgentResult(
            answer=answer,
            status=status,
            generated=generated,
            citations=generated.citations if generated else (),
            trace=trace,
        )


def build_travel_agent_graph(agent: TravelAgent):
    """Build the checkpoint-free, bounded graph for one answer turn."""

    def refusal(
        state: TravelAgentState,
        *,
        status: TravelAgentStatus = TravelAgentStatus.REFUSED,
        intent: str = 'unsupported_question',
    ) -> dict[str, object]:
        queries = state.get('queries', [])
        result = agent._result(
            INSUFFICIENT_CONTEXT_ANSWER,
            status,
            None,
            [*state.get('actions', ()), TravelAgentAction.REFUSE],
            queries,
            state.get('retry_count', 0),
            bool(state.get('evidence')),
            intent=intent,
        )
        return {
            'answer': result.answer,
            'citations': result.citations,
            'final_status': result.status,
            'result': result,
        }

    async def plan(
        state: TravelAgentState,
    ) -> Command[Literal['search', 'terminal']]:
        question = state.get('question')
        if question is None:
            raise ValueError('TravelAgent graph requires a question.')
        normalized = question.strip()
        if not normalized:
            return Command(
                update=refusal(state, intent='empty_question'), goto='terminal'
            )
        queries = state.get('queries', [])
        try:
            query = await agent._llm_client.choose_search_query(
                normalized,
                previous_queries=tuple(queries),
                has_context=bool(state.get('evidence')),
            )
        except GenerationError:
            return Command(
                update=refusal(state, status=TravelAgentStatus.GENERATION_ERROR),
                goto='terminal',
            )
        if not query or not query.strip() or query.strip() in queries:
            return Command(update=refusal(state), goto='terminal')
        action = (
            TravelAgentAction.SEARCH_KNOWLEDGE_BASE
            if not queries
            else TravelAgentAction.REFORMULATE_SEARCH
        )
        return Command(
            update={
                'next_query': query.strip(),
                'actions': [*state.get('actions', ()), action],
            },
            goto='search',
        )

    async def search(state: TravelAgentState) -> dict[str, object]:
        query = state.get('next_query')
        if query is None:
            return {}
        search_result = agent._search_tool(TourismSearchQuery(query))
        if isawaitable(search_result):
            search_result = cast(TourismSearchResult, await search_result)
        return {
            'queries': [*state.get('queries', []), query],
            'tool_calls': len(state.get('queries', [])) + 1,
            'search_result': search_result,
            'evidence': search_result.evidence,
            'next_query': None,
        }

    async def evaluate(
        state: TravelAgentState,
    ) -> Command[Literal['plan', 'answer', 'terminal']]:
        search_result = state.get('search_result')
        if search_result is None:
            return Command(
                update=refusal(state, status=TravelAgentStatus.RETRIEVAL_ERROR),
                goto='terminal',
            )
        if search_result.status is RetrievalStatus.ERROR:
            return Command(
                update=refusal(state, status=TravelAgentStatus.RETRIEVAL_ERROR),
                goto='terminal',
            )
        if search_result.evidence:
            return Command(
                update={'planned_action': TravelAgentAction.ANSWER_FROM_CONTEXT.value},
                goto='answer',
            )
        if state.get('retry_count', 0) < agent._max_search_retries:
            return Command(
                update={
                    'retry_count': state.get('retry_count', 0) + 1,
                    'planned_action': TravelAgentAction.REFORMULATE_SEARCH.value,
                },
                goto='plan',
            )
        return Command(
            update=refusal(state, status=TravelAgentStatus.NO_EVIDENCE),
            goto='terminal',
        )

    async def answer(state: TravelAgentState) -> dict[str, object]:
        question = state.get('question')
        search_result = state.get('search_result')
        if question is None or search_result is None:
            raise ValueError('Answer node requires a question and search result.')
        try:
            generated = await agent._llm_client.answer_question(
                _context_messages(question, search_result)
            )
        except GenerationError:
            return refusal(
                state,
                status=TravelAgentStatus.GENERATION_ERROR,
            )
        citations = _validated_citations(generated.citations, search_result)
        generated = GeneratedAnswer(
            answer=generated.answer,
            citations=citations,
            emotion=generated.emotion,
            llm_metadata=generated.llm_metadata,
            raw_provider_response=generated.raw_provider_response,
        )
        result = agent._result(
            generated.answer,
            TravelAgentStatus.ANSWERED,
            generated,
            [*state.get('actions', ()), TravelAgentAction.ANSWER_FROM_CONTEXT],
            state.get('queries', []),
            state.get('retry_count', 0),
            True,
        )
        return {
            'answer': generated.answer,
            'citations': result.citations,
            'final_status': result.status,
            'result': result,
        }

    graph = StateGraph(TravelAgentState)
    graph.add_node('plan', plan, destinations=('search', 'terminal'))
    graph.add_node('search', search)
    graph.add_node('evaluate', evaluate, destinations=('plan', 'answer', 'terminal'))
    graph.add_node('answer', answer)

    async def terminal(state: TravelAgentState) -> dict[str, object]:
        del state
        return {}

    graph.add_node('terminal', terminal)
    graph.add_edge(START, 'plan')
    graph.add_edge('search', 'evaluate')
    graph.add_edge('answer', END)
    graph.add_edge('terminal', END)
    return graph.compile()


def _validated_citations(
    citations: tuple[LLMCitation, ...], result: TourismSearchResult
) -> tuple[LLMCitation, ...]:
    """Keep only citations supported by the returned evidence."""
    supported = {
        (item.source_url, item.version): set(item.pages) for item in result.evidence
    }
    valid: list[LLMCitation] = []
    for citation in citations:
        pages = supported.get((citation.source_url, citation.version))
        if pages is None:
            continue
        if citation.page_start is None or citation.page_end is None:
            valid.append(citation)
            continue
        if any(
            page in pages for page in range(citation.page_start, citation.page_end + 1)
        ):
            valid.append(citation)
    return tuple(valid)


__all__ = [
    'MAX_SEARCH_RETRIES',
    'TravelAgent',
    'TravelAgentAction',
    'TravelAgentResult',
    'TravelAgentState',
    'TravelAgentStatus',
    'TravelAgentTrace',
    'build_travel_agent_graph',
]
