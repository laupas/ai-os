from claude_agent_sdk.types import StreamEvent

from aios.engine.text_stream_mapper import TextStreamMapper


def _event(event: dict, parent: str | None = None) -> StreamEvent:
    return StreamEvent(uuid="u", session_id="s", event=event, parent_tool_use_id=parent)


def test_a_new_message_restarts_the_stream() -> None:
    delta = TextStreamMapper().delta(_event({"type": "message_start", "message": {}}))
    assert delta is not None and delta.restart and delta.text == ""


def test_a_text_delta_is_passed_on() -> None:
    delta = TextStreamMapper().delta(
        _event({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hi"}})
    )
    assert delta is not None and delta.text == "hi" and not delta.restart


def test_tool_input_and_subagent_text_are_not_the_reply() -> None:
    mapper = TextStreamMapper()
    tool_input = _event(
        {"type": "content_block_delta", "delta": {"type": "input_json_delta", "partial_json": "{"}}
    )
    subagent = _event(
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "x"}}, parent="t1"
    )
    assert mapper.delta(tool_input) is None
    assert mapper.delta(subagent) is None
