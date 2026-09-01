from ai_tour_guide.agent.flow import (
    DEFAULT_FLOW_STEP,
    FlowStep,
    flow_step_for_option,
    input_type_for_option,
)


def test_free_text_keeps_the_checkpointed_flow_step() -> None:
    assert flow_step_for_option(None, FlowStep.IDENTITY) is FlowStep.IDENTITY
    assert flow_step_for_option('untrusted-value', FlowStep.DESTINATIONS) is (
        FlowStep.DESTINATIONS
    )


def test_guided_options_resolve_backend_owned_steps() -> None:
    assert flow_step_for_option('identity') is FlowStep.IDENTITY
    assert flow_step_for_option('destinations') is FlowStep.DESTINATIONS
    assert flow_step_for_option('main_menu') is DEFAULT_FLOW_STEP


def test_input_type_distinguishes_guided_and_free_text_turns() -> None:
    assert input_type_for_option('identity') == 'guided'
    assert input_type_for_option(None) == 'free_text'
    assert input_type_for_option('untrusted-value') == 'free_text'
