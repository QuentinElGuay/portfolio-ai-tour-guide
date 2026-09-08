"""Tests for explicit agent-type and product-layer compatibility."""

import pytest
from pydantic import SecretStr

from ai_tour_guide.app.agent.configuration import (
    AgentType,
    ProductConfigurationError,
    ProductLayer,
    resolve_product_configuration,
    validate_product_configuration,
)
from ai_tour_guide.app.llm.settings import AgentsSettings, LLMProvider


@pytest.mark.parametrize(
    ('agent_type', 'product_layer', 'provider', 'has_api_key', 'knowledge_base'),
    [
        (AgentType.DETERMINISTIC, ProductLayer.DEMO, 'baguette-llm', False, False),
        (
            AgentType.DETERMINISTIC,
            ProductLayer.RETRIEVAL,
            'baguette-llm',
            False,
            True,
        ),
        (AgentType.LLM, ProductLayer.RAG, 'openai', True, False),
        (AgentType.LLM, ProductLayer.AGENT, 'gemini', True, True),
        (AgentType.LLM, ProductLayer.BASELINE, 'openai', True, None),
    ],
)
def test_validate_product_configuration_accepts_supported_combinations(
    agent_type: AgentType,
    product_layer: ProductLayer,
    provider: str,
    has_api_key: bool,
    knowledge_base: bool | None,
) -> None:
    """Verify each supported layer has an intentional agent configuration."""
    validate_product_configuration(
        agent_type=agent_type,
        product_layer=product_layer,
        llm_provider=provider,
        has_llm_api_key=has_api_key,
        knowledge_base_available=knowledge_base,
    )


@pytest.mark.parametrize(
    ('agent_type', 'product_layer', 'message'),
    [
        (AgentType.LLM, ProductLayer.DEMO, "'demo' layer requires a deterministic"),
        (
            AgentType.DETERMINISTIC,
            ProductLayer.RAG,
            "'rag' layer requires a llm",
        ),
    ],
)
def test_validate_product_configuration_rejects_layer_agent_type_mismatches(
    agent_type: AgentType, product_layer: ProductLayer, message: str
) -> None:
    """Verify an explicit layer never silently changes the requested agent type."""
    with pytest.raises(ProductConfigurationError, match=message):
        validate_product_configuration(
            agent_type=agent_type,
            product_layer=product_layer,
            llm_provider='baguette-llm',
            has_llm_api_key=False,
        )


@pytest.mark.parametrize(
    ('agent_type', 'product_layer', 'provider', 'has_api_key', 'message'),
    [
        (
            AgentType.LLM,
            ProductLayer.RAG,
            'baguette-llm',
            False,
            'LLM agent requires an OpenAI or Gemini provider',
        ),
        (
            AgentType.LLM,
            ProductLayer.AGENT,
            'gemini',
            False,
            'LLM agent requires AGENT_LLM_API_KEY',
        ),
    ],
)
def test_validate_product_configuration_rejects_provider_incompatibilities(
    agent_type: AgentType,
    product_layer: ProductLayer,
    provider: str,
    has_api_key: bool,
    message: str,
) -> None:
    """Verify the configured provider can serve the selected agent type."""
    with pytest.raises(ProductConfigurationError, match=message):
        validate_product_configuration(
            agent_type=agent_type,
            product_layer=product_layer,
            llm_provider=provider,
            has_llm_api_key=has_api_key,
        )


def test_retrieval_layer_requires_an_available_knowledge_base() -> None:
    """Verify an explicit retrieval layer fails instead of degrading silently."""
    with pytest.raises(
        ProductConfigurationError,
        match="'retrieval' layer requires an available knowledge base",
    ):
        validate_product_configuration(
            agent_type=AgentType.DETERMINISTIC,
            product_layer=ProductLayer.RETRIEVAL,
            llm_provider='baguette-llm',
            has_llm_api_key=False,
            knowledge_base_available=False,
        )


def test_agent_settings_read_capability_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify capability flags can be configured at the boundary."""
    monkeypatch.setenv('AGENT_LLM_PROVIDER', LLMProvider.BAGUETTE_LLM.value)
    monkeypatch.setenv('APP_ENABLE_LLM', '0')
    monkeypatch.setenv('APP_ENABLE_RETRIEVAL', '1')

    settings = AgentsSettings(model='test-model')

    assert settings.enable_llm is False
    assert settings.enable_retrieval is True
    assert settings.llm_provider is LLMProvider.BAGUETTE_LLM


def test_defaults_select_llm_rag_when_an_api_key_is_available() -> None:
    settings = AgentsSettings(
        model='test-model',
        api_key=SecretStr('secret'),
        llm_provider=LLMProvider.OPENAI,
    )

    resolved = resolve_product_configuration(settings)

    assert resolved.agent_type is AgentType.LLM
    assert resolved.product_layer is ProductLayer.RAG
    assert resolved.automatic_fallback is False


def test_defaults_downgrade_to_deterministic_retrieval_without_an_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv('AGENT_LLM_API_KEY', raising=False)
    settings = AgentsSettings(
        model='test-model',
        llm_provider=LLMProvider.OPENAI,
        api_key=SecretStr(''),
    )

    resolved = resolve_product_configuration(settings)

    assert resolved.agent_type is AgentType.DETERMINISTIC
    assert resolved.product_layer is ProductLayer.RETRIEVAL
    assert resolved.automatic_fallback is True


def test_missing_llm_api_key_downgrades_dynamically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv('AGENT_LLM_API_KEY', raising=False)
    settings = AgentsSettings(
        model='test-model',
        llm_provider=LLMProvider.OPENAI,
        api_key=SecretStr(''),
        agent_type=AgentType.LLM,
        product_layer=ProductLayer.RAG,
    )

    resolved = resolve_product_configuration(settings)

    assert resolved.agent_type is AgentType.DETERMINISTIC
    assert resolved.product_layer is ProductLayer.RETRIEVAL


def test_capability_flags_default_to_enabled() -> None:
    settings = AgentsSettings(model='test-model', api_key=SecretStr(''))

    assert settings.enable_llm is True
    assert settings.enable_retrieval is True


def test_disabling_llm_selects_deterministic_retrieval() -> None:
    settings = AgentsSettings(
        model='test-model',
        api_key=SecretStr('secret'),
        enable_llm=False,
        enable_retrieval=True,
    )

    resolved = resolve_product_configuration(settings)

    assert resolved.agent_type is AgentType.DETERMINISTIC
    assert resolved.product_layer is ProductLayer.RETRIEVAL


def test_disabling_both_capabilities_selects_simple_demo() -> None:
    settings = AgentsSettings(
        model='test-model',
        api_key=SecretStr('secret'),
        enable_llm=False,
        enable_retrieval=False,
    )

    resolved = resolve_product_configuration(settings)

    assert resolved.agent_type is AgentType.DETERMINISTIC
    assert resolved.product_layer is ProductLayer.DEMO


def test_disabling_retrieval_selects_llm_without_rag() -> None:
    settings = AgentsSettings(
        model='test-model',
        api_key=SecretStr('secret'),
        enable_llm=True,
        enable_retrieval=False,
    )

    resolved = resolve_product_configuration(settings)

    assert resolved.agent_type is AgentType.LLM
    assert resolved.product_layer is ProductLayer.BASELINE


def test_disabled_retrieval_downgrades_dynamically() -> None:
    settings = AgentsSettings(
        model='test-model',
        api_key=SecretStr('secret'),
        product_layer=ProductLayer.RAG,
        enable_retrieval=False,
    )

    resolved = resolve_product_configuration(settings)

    assert resolved.agent_type is AgentType.LLM
    assert resolved.product_layer is ProductLayer.BASELINE
