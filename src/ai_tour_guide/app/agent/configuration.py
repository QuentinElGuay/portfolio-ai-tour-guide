"""Explicit product-layer and agent-type compatibility rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_tour_guide.app.llm.settings import AgentsSettings


class AgentType(StrEnum):
    """Execution style used to answer travel questions."""

    DETERMINISTIC = 'deterministic'
    LLM = 'llm'


class ProductLayer(StrEnum):
    """Portfolio capability intentionally exposed by an application run."""

    DEMO = 'demo'
    RETRIEVAL = 'retrieval'
    RAG = 'rag'
    AGENT = 'agent'
    BASELINE = 'baseline'


class ProductConfigurationError(ValueError):
    """Raised when an explicit product layer cannot be served safely."""


@dataclass(frozen=True, slots=True)
class ResolvedProductConfiguration:
    """Effective agent and product layer selected at the application boundary."""

    agent_type: AgentType
    product_layer: ProductLayer
    automatic_fallback: bool = False


_EXPECTED_AGENT_TYPES = {
    ProductLayer.DEMO: AgentType.DETERMINISTIC,
    ProductLayer.RETRIEVAL: AgentType.DETERMINISTIC,
    ProductLayer.RAG: AgentType.LLM,
    ProductLayer.AGENT: AgentType.LLM,
    ProductLayer.BASELINE: AgentType.LLM,
}


def validate_product_configuration(
    *,
    agent_type: AgentType,
    product_layer: ProductLayer,
    llm_provider: str,
    has_llm_api_key: bool,
    knowledge_base_available: bool | None = None,
) -> None:
    """Reject configuration combinations that cannot serve their requested layer.

    ``knowledge_base_available`` is optional because the configuration boundary can be
    evaluated before a database connection is attempted. Callers that know its value
    must provide it so an explicit retrieval layer fails rather than silently falling
    back to a different experience.
    """
    expected_agent_type = _EXPECTED_AGENT_TYPES[product_layer]
    if agent_type is not expected_agent_type:
        raise ProductConfigurationError(
            f"The '{product_layer.value}' layer requires a "
            f'{expected_agent_type.value} agent.'
        )

    if agent_type is AgentType.LLM and llm_provider == 'baguette-llm':
        raise ProductConfigurationError(
            'An LLM agent requires an OpenAI or Gemini provider.'
        )
    elif agent_type is AgentType.LLM and not has_llm_api_key:
        raise ProductConfigurationError('An LLM agent requires AGENT_LLM_API_KEY.')

    if product_layer is ProductLayer.RETRIEVAL and knowledge_base_available is False:
        raise ProductConfigurationError(
            "The 'retrieval' layer requires an available knowledge base."
        )


def resolve_product_configuration(
    settings: AgentsSettings,
    *,
    knowledge_base_available: bool | None = None,
) -> ResolvedProductConfiguration:
    """Resolve the effective execution mode from capabilities and availability.

    Agent type and product layer are derived values. The capability flags are the
    only runtime controls: unavailable LLM capability downgrades to deterministic
    execution, and disabled retrieval downgrades to conversational execution.
    """
    has_llm_api_key = bool(settings.api_key.get_secret_value().strip())
    llm_available = (
        settings.enable_llm
        and settings.llm_provider.value != 'baguette-llm'
        and has_llm_api_key
    )
    if llm_available:
        return ResolvedProductConfiguration(
            AgentType.LLM,
            ProductLayer.RAG if settings.enable_retrieval else ProductLayer.BASELINE,
        )
    return ResolvedProductConfiguration(
        AgentType.DETERMINISTIC,
        ProductLayer.RETRIEVAL if settings.enable_retrieval else ProductLayer.DEMO,
        automatic_fallback=not settings.enable_llm or not has_llm_api_key,
    )


__all__ = [
    'AgentType',
    'ProductConfigurationError',
    'ProductLayer',
    'ResolvedProductConfiguration',
    'resolve_product_configuration',
    'validate_product_configuration',
]
