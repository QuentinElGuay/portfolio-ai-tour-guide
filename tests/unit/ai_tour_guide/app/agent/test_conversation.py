import asyncio
from typing import cast
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from ai_tour_guide.app.agent.conversation import (
    ConversationState,
    OuterConversationState,
    build_conversation_graph,
    build_outer_conversation_graph,
    welcome_message_for_provider,
)
from ai_tour_guide.app.agent.demo_questions import DEMO_WELCOME_MESSAGE
from ai_tour_guide.app.agent.llm.settings import LLMProvider
from ai_tour_guide.app.agent.rag.models import GeneratedAnswer, RAGResult
from ai_tour_guide.app.agent.responses import EMPTY_KNOWLEDGE_BASE_NOTICE
from ai_tour_guide.knowledge_base.retrieval.models import RetrievedContext
from ai_tour_guide.knowledge_base.search import SearchMode


def test_conversation_greeting_matches_the_selected_provider() -> None:
    """Verify that conversation startup owns the demo disclosure."""
    assert (
        welcome_message_for_provider(
            LLMProvider.BAGUETTE_LLM, knowledge_base_is_empty=True
        )
        == DEMO_WELCOME_MESSAGE
    )
    assert EMPTY_KNOWLEDGE_BASE_NOTICE in welcome_message_for_provider(
        LLMProvider.OPENAI, knowledge_base_is_empty=True
    )
    assert EMPTY_KNOWLEDGE_BASE_NOTICE not in welcome_message_for_provider(
        LLMProvider.OPENAI, knowledge_base_is_empty=False
    )


@patch(
    'ai_tour_guide.app.agent.conversation.answer_question_async', new_callable=AsyncMock
)
def test_conversation_graph_returns_the_rag_result(
    answer_question_async: AsyncMock,
) -> None:
    """Return a request result without storing it in graph state."""
    result = RAGResult(
        question='Where should I go?',
        mode=SearchMode.HYBRID,
        k=5,
        messages=(),
        generated=GeneratedAnswer('Visit Brittany.'),
        contexts=(cast(RetrievedContext, object.__new__(RetrievedContext)),),
    )
    answer_question_async.return_value = result
    captured_results: list[RAGResult] = []
    graph = build_conversation_graph(
        AsyncMock(),
        engine=None,
        strategy=None,
        checkpointer=MemorySaver(),
        on_result=captured_results.append,
    )
    request: ConversationState = {
        'messages': [HumanMessage(content=result.question)],
    }

    state = asyncio.run(
        graph.ainvoke(request, config={'configurable': {'thread_id': 'session-1'}})
    )

    assert captured_results == [result]
    assert isinstance(state['messages'][-1], AIMessage)
    assert state['messages'][-1].content == 'Visit Brittany.'

    asyncio.run(
        graph.ainvoke(
            {
                'messages': [HumanMessage(content='What about it?')],
            },
            config={'configurable': {'thread_id': 'session-1'}},
        )
    )

    assert answer_question_async.await_args_list[-1].args[0] == (
        'What about it?\n\nConversation context: the previous user question was '
        'Where should I go?'
    )


def test_outer_conversation_graph_checkpoints_step_and_response() -> None:
    async def answer_turn(
        question: str, session_id: str, flow_step: object
    ) -> RAGResult:
        del session_id, flow_step
        return RAGResult(
            question=question,
            mode=SearchMode.HYBRID,
            k=5,
            messages=(),
            generated=GeneratedAnswer('Grounded answer.'),
        )

    graph = build_outer_conversation_graph(
        checkpointer=MemorySaver(),
        answer_turn=answer_turn,
        list_destination_names=lambda: ('Brittany',),
    )
    session_id = '12345678-1234-5678-1234-567812345678'

    start = asyncio.run(
        graph.ainvoke(
            cast(
                OuterConversationState,
                {'session_id': session_id, 'messages': []},
            ),
            config={'configurable': {'thread_id': session_id}},
        )
    )
    guided = asyncio.run(
        graph.ainvoke(
            cast(
                OuterConversationState,
                {
                    'latest_request': {
                        'session_id': session_id,
                        'expected_step_id': 'welcome',
                        'input_id': 'identity',
                        'text': None,
                    }
                },
            ),
            config={'configurable': {'thread_id': session_id}},
        )
    )

    assert start['latest_response']['step_id'] == 'welcome'
    assert guided['latest_response']['step_id'] == 'identity'
    assert guided['latest_response']['message']
