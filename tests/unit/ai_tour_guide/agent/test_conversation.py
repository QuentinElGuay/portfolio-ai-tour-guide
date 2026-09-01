import asyncio
from typing import cast
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from ai_tour_guide.agent.conversation import ConversationState, build_conversation_graph
from ai_tour_guide.agent.rag.models import GeneratedAnswer, RAGResult
from ai_tour_guide.knowledge_base.retrieval.models import RetrievedContext
from ai_tour_guide.knowledge_base.search import SearchMode


@patch('ai_tour_guide.agent.conversation.answer_question_async', new_callable=AsyncMock)
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
