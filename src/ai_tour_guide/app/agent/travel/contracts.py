"""Provider-neutral contracts for travel-agent turns."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from ai_tour_guide.app.agent.flow import FlowStep


class TravelAgentStatus(StrEnum):
    """Public outcomes for a travel-agent turn."""

    ANSWERED = 'answered'
    REFUSED = 'refused'
    FAILED = 'failed'


@dataclass(frozen=True, slots=True)
class TravelTurnContext:
    """Conversation information supplied to one travel-agent turn."""

    session_id: str
    flow_step: FlowStep


@dataclass(frozen=True, slots=True)
class TravelTurnTrace:
    """Safe operational metadata emitted by a travel agent."""

    intent: str
    actions: tuple[str, ...] = ()
    tool_inputs: tuple[str, ...] = ()
    evidence_sufficient: bool = False


@dataclass(frozen=True, slots=True)
class TravelTurnResult:
    """Provider-neutral response produced by a travel agent."""

    answer: str
    status: TravelAgentStatus
    request_id: UUID | None = None
    sources: tuple[Mapping[str, object], ...] = ()
    trace: TravelTurnTrace = field(
        default_factory=lambda: TravelTurnTrace(intent='travel_question')
    )
    metadata: Mapping[str, object] = field(default_factory=dict)
    persistence_payload: Mapping[str, object] | None = None
    error_message: str | None = None


class TravelAgent(Protocol):
    """Answer one travel question independently of UI and provider details."""

    async def answer(
        self, question: str, context: TravelTurnContext
    ) -> TravelTurnResult:
        """Resolve one travel-agent turn."""
        ...


__all__ = [
    'TravelAgent',
    'TravelAgentStatus',
    'TravelTurnContext',
    'TravelTurnResult',
    'TravelTurnTrace',
]
