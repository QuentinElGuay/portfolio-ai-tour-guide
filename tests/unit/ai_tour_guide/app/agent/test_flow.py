from ai_tour_guide.app.agent.flow import (
    FLOW_DEFINITIONS,
    FlowStep,
    flow_definition,
    transition_for,
)


def test_backend_flow_exposes_stable_buttons_and_transitions() -> None:
    welcome = flow_definition(FlowStep.WELCOME)

    assert [button.input_id for button in welcome.rendered_buttons()] == [
        'identity',
        'destinations',
    ]
    assert [
        button.label
        for button in flow_definition(FlowStep.BON_VOYAGE).rendered_buttons()
    ] == [
        'Tell me about you',
        'Where does your information come from?',
    ]
    assert [
        button.label
        for button in flow_definition(FlowStep.INFORMATION_SOURCES).rendered_buttons()
    ] == [
        'What is Bon Voyage?',
        'Where does your information come from?',
    ]
    assert transition_for(FlowStep.WELCOME, 'identity') is FlowStep.IDENTITY
    assert transition_for(FlowStep.IDENTITY, 'bon_voyage') is FlowStep.BON_VOYAGE
    assert transition_for(FlowStep.BON_VOYAGE, 'identity') is FlowStep.IDENTITY
    assert (
        transition_for(FlowStep.BON_VOYAGE, 'information_sources')
        is FlowStep.INFORMATION_SOURCES
    )
    assert (
        transition_for(FlowStep.INFORMATION_SOURCES, 'bon_voyage')
        is FlowStep.BON_VOYAGE
    )
    assert (
        transition_for(FlowStep.INFORMATION_SOURCES, 'information_sources')
        is FlowStep.INFORMATION_SOURCES
    )
    assert transition_for(FlowStep.IDENTITY, 'destinations') is None


def test_free_text_is_allowed_only_with_text_and_terminal_buttons_are_explicit() -> (
    None
):
    assert transition_for(FlowStep.IDENTITY, 'FREE_TEXT', text='Where?') is (
        FlowStep.IDENTITY
    )
    assert transition_for(FlowStep.IDENTITY, 'FREE_TEXT') is None
    assert flow_definition(FlowStep.BON_VOYAGE).buttons
    assert flow_definition(FlowStep.TERMINAL).buttons == ()
    assert not flow_definition(FlowStep.TERMINAL).accepts_free_text
    assert all(step_id in FLOW_DEFINITIONS for step_id in FlowStep)
