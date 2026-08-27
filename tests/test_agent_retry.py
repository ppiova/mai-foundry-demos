"""The live loop must not surrender the first time a turn comes back without a plan.

MAI-Thinking-1 sometimes ends a turn with reasoning only and no content, which used
to drop the run straight to the deterministic planner and label a perfectly healthy
live call as FALLBACK.
"""

from __future__ import annotations

import json
from unittest.mock import Mock

from demos.thinking_agent import CloudEstate, fallback_plan, run_agent
from mai.config import Config


def _valid_answer() -> str:
    """A model answer carrying a plan that passes deterministic validation."""
    estate = CloudEstate()
    moves, decommissions = fallback_plan(estate).proposal.validation_inputs()
    payload = json.dumps(
        {
            "moves": moves,
            "decommissions": list(decommissions),
            "risks": ["Verify dependencies before cutover"],
        }
    )
    return "## Migration plan\n\n```json\n" + payload + "\n```"


def _client_returning(turns: list[str]) -> Mock:
    """A configured client whose stream yields each queued answer in order."""

    def fake_stream(messages, tools=None, reasoning_display=None):
        content = turns.pop(0)
        if content:
            yield ("content", content)
        yield ("message", {"role": "assistant", "content": content})

    client = Mock()
    client.thinking_ready.return_value = True
    client.cfg = Config(execution_mode="demo")
    client.chat_completion_stream = fake_stream
    return client


def test_empty_final_answer_is_retried_instead_of_falling_back():
    client = _client_returning(["", _valid_answer()])
    kinds = []

    run = run_agent(client, on_event=lambda kind, **kw: kinds.append(kind))

    assert run.source == "live", run.error
    assert run.validation is not None and run.validation.ok
    assert run.error is None
    assert "retry" in kinds


def test_answer_without_a_json_block_is_retried():
    prose_only = "Move some workloads to cheaper regions and decommission the idle ones."
    client = _client_returning([prose_only, _valid_answer()])

    run = run_agent(client)

    assert run.source == "live", run.error
    assert run.validation is not None and run.validation.ok


def test_retries_are_bounded_and_still_degrade_visibly():
    """When every attempt comes back empty the run degrades, and says so."""
    client = _client_returning(["", "", ""])
    kinds = []

    run = run_agent(client, final_retries=2, on_event=lambda kind, **kw: kinds.append(kind))

    assert run.source == "fallback"
    assert "did not contain a machine-checkable plan" in run.error
    assert kinds.count("retry") == 2


def test_final_round_withholds_tools_so_the_model_must_commit():
    """The last round must be called without tools, whatever the round budget is."""
    seen_tools = []

    def fake_stream(messages, tools=None, reasoning_display=None):
        seen_tools.append(tools)
        yield ("message", {"role": "assistant", "content": _valid_answer()})

    client = Mock()
    client.thinking_ready.return_value = True
    client.cfg = Config(execution_mode="demo")
    client.chat_completion_stream = fake_stream

    run = run_agent(client, max_rounds=1)

    assert run.source == "live", run.error
    assert seen_tools == [None]
