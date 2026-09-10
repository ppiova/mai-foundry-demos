"""The agent loop: the live tool-calling run, and the deterministic planner.

Two paths to the same shape. The live path streams MAI-Thinking-1, executes the
tool calls it asks for, and validates whatever it proposes. The fallback path is a
greedy planner over the same estate, so a rehearsal with no credentials, or a
failure on stage, still produces a correct, data-driven plan rather than nothing.

Both return an `AgentRun` carrying `source`, so the caller can label which one ran.
No UI framework here either: `run_agent` reports progress by yielding events.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass, field

from mai import MAIClient

from .estate import SYSTEM_PROMPT, TOOLS_SCHEMA, CloudEstate
from .plan import (
    MigrationPlan,
    PlanMove,
    PlanValidation,
    _all_within_ceiling,
    _render_plan_markdown,
    extract_structured_plan,
    render_validated_plan,
    validate_plan,
)


@dataclass
class AgentRun:
    source: str
    plan_markdown: str
    trace: list = field(default_factory=list)  # list of (tool, args, result)
    error: str | None = None
    elapsed: float = 0.0
    validation: PlanValidation | None = None  # deterministic check of the proposal
    rejected_validation: PlanValidation | None = None  # unsafe model proposal, if any
    proposal: MigrationPlan | dict | None = None
    stats: dict = field(default_factory=dict)  # usage / finish_reason / request_id


# ─────────────────────────────────────────────────────────────────────────────
# Live agent loop
# ─────────────────────────────────────────────────────────────────────────────
def _tool_summary(fn: str, result: dict) -> str:
    if result.get("error") or result.get("errors"):
        return "⚠️ " + str(result.get("error") or result.get("errors"))
    if fn == "get_region_capacity":
        return f"{result.get('display_name')}: {result.get('utilization_pct')}% used, {result.get('headroom_units_to_ceiling')}u headroom"
    if fn == "calculate_migration_cost":
        return f"save ${result.get('monthly_savings'):,}/mo → target {result.get('resulting_target_utilization_pct')}% ({'ok' if result.get('within_capacity_ceiling') else 'over'})"
    return ""


_KNOWN_TOOLS = {item["function"]["name"] for item in TOOLS_SCHEMA}


def execute_tool_call(estate: CloudEstate, tool_call: dict) -> tuple[str, dict, dict]:
    """Validate an untrusted model tool call before dispatching any local function."""
    function = tool_call.get("function") if isinstance(tool_call, dict) else None
    call_id = tool_call.get("id") if isinstance(tool_call, dict) else None
    if not isinstance(call_id, str) or not call_id.strip():
        return "invalid_tool_call", {}, {"error": "Malformed tool call: missing non-empty id."}
    if not isinstance(function, dict):
        return "invalid_tool_call", {}, {"error": "Malformed tool call: missing function."}
    name = function.get("name")
    if not isinstance(name, str) or name not in _KNOWN_TOOLS:
        label = name if isinstance(name, str) and name else "invalid_tool_call"
        return label, {}, {"error": f"Unknown tool '{label}' was not executed."}
    raw_args = function.get("arguments") or "{}"
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except json.JSONDecodeError:
        return name, {}, {"error": "Malformed tool arguments: expected a JSON object."}
    if not isinstance(args, dict):
        return name, {}, {"error": "Malformed tool arguments: expected a JSON object."}
    if name == "get_region_capacity" and not isinstance(args.get("region"), str):
        return name, {}, {"error": "Malformed tool arguments: 'region' must be a string."}
    if name == "calculate_migration_cost" and (
        not isinstance(args.get("target_region"), str)
        or not isinstance(args.get("app_names"), list)
        or not all(isinstance(item, str) for item in args.get("app_names", []))
    ):
        return (
            name,
            {},
            {"error": "Malformed tool arguments: expected string app_names and target_region."},
        )
    return name, args, estate.dispatch(name, args)


FINAL_ANSWER_NUDGE = (
    "You have every tool result you need. Output the final plan now: the Markdown "
    "sections described in your instructions, ending with the fenced json block. "
    "Do not call any more tools."
)


def _stream_turn(
    client: MAIClient, messages: list[dict], tools: list[dict] | None, emit
) -> tuple[dict, str, dict]:
    """Stream one assistant turn; return its message, streamed text, and stats."""
    msg, produced, stats = None, "", {}
    for kind, val in client.chat_completion_stream(
        messages, tools=tools, reasoning_display="encrypted"
    ):
        if kind == "content":
            produced += val
            emit("delta", text=val)
        elif kind == "stats":
            stats.update(val)
            emit("stats", **val)
        elif kind == "message":
            msg = val
    if not isinstance(msg, dict):
        raise RuntimeError("Thinking stream ended without an assistant message")
    return msg, produced, stats


def run_agent(
    client: MAIClient, max_rounds: int = 8, final_retries: int = 2, on_event=None
) -> AgentRun:
    """Live streaming agent loop. ``on_event(kind, **kw)`` receives:
    ``round`` (n), ``tool`` (name, args, result, summary), ``delta`` (text)."""
    import time

    def emit(kind, **kw):
        if on_event:
            with contextlib.suppress(Exception):
                on_event(kind, **kw)

    estate = CloudEstate()
    if not client.thinking_ready():
        if client.cfg.strict:
            raise RuntimeError("Thinking service is not configured")
        return fallback_plan(estate)

    t0 = time.time()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "Cloud estate:\n"
            + json.dumps(estate.summary_for_prompt())
            + "\n\nBuild the migration plan.",
        },
    ]
    trace = []
    stats: dict = {}
    answer, produced = "", ""
    try:
        for rnd in range(1, max_rounds + 1):
            emit("round", n=rnd)
            # `reasoning_display="encrypted"` returns an opaque reasoning blob that we
            # append back untouched, so the model keeps its reasoning state across
            # tool rounds without ever exposing the chain of thought. Withholding the
            # tools on the last round forces the model to commit to an answer.
            tools = TOOLS_SCHEMA if rnd < max_rounds else None
            msg, produced, turn_stats = _stream_turn(client, messages, tools, emit)
            stats.update(turn_stats)
            messages.append(msg)
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                answer = msg.get("content") or produced or ""
                break
            for tc in tool_calls:
                fn, args, result = execute_tool_call(estate, tc)
                trace.append((fn, args, result))
                emit("tool", name=fn, args=args, result=result, summary=_tool_summary(fn, result))
                call_id = tc.get("id") if isinstance(tc, dict) else None
                if not isinstance(call_id, str) or not call_id.strip():
                    raise ValueError(result.get("error", "Malformed tool call id"))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": fn,
                        "content": json.dumps(result),
                    }
                )
        else:
            answer = produced

        # A reasoning model can end a turn with reasoning only and no content, or
        # with prose that omits the machine-checkable block. Ask again, without
        # tools, rather than dropping to the deterministic planner on the first miss.
        for attempt in range(1, final_retries + 1):
            if extract_structured_plan(answer):
                break
            emit("retry", n=attempt, chars=len(answer))
            messages.append({"role": "user", "content": FINAL_ANSWER_NUDGE})
            msg, produced, turn_stats = _stream_turn(client, messages, None, emit)
            stats.update(turn_stats)
            messages.append(msg)
            retried = msg.get("content") or produced or ""
            if retried.strip():
                answer = retried

        return _finish_live(estate, answer, trace, time.time() - t0, stats)
    except Exception as exc:
        if client.cfg.strict:
            raise
        run = fallback_plan(estate)
        run.error = str(exc)
        run.elapsed = time.time() - t0
        return run


def _finish_live(
    estate: CloudEstate, answer: str, trace: list, elapsed: float, stats: dict
) -> AgentRun:
    """Wrap a live answer, validating the structured plan when the model supplied one."""
    proposal = extract_structured_plan(answer)
    if proposal:
        # Use a default only when the key is absent: `or []` would normalise a
        # malformed-but-falsy value ({}, null, "") into an empty list and slip it
        # past the shape checks in validate_plan().
        validation = validate_plan(
            estate,
            proposal.get("moves", []),
            proposal.get("decommissions", []),
            risks=proposal.get("risks"),
        )
        if validation.ok:
            structured = MigrationPlan.from_validated_mapping(
                {
                    "moves": proposal.get("moves", []),
                    "decommissions": proposal.get("decommissions", []),
                    "risks": list(validation.risks),
                }
            )
            return AgentRun(
                "live",
                render_validated_plan(estate, structured, validation),
                trace,
                elapsed=elapsed,
                validation=validation,
                proposal=structured,
                stats=stats,
            )
        safe = fallback_plan(estate)
        safe.error = "Model plan rejected by deterministic validation."
        safe.elapsed = elapsed
        safe.trace = trace
        safe.rejected_validation = validation
        safe.stats = stats
        return safe

    safe = fallback_plan(estate)
    safe.error = "Model response did not contain a machine-checkable plan."
    safe.elapsed = elapsed
    safe.trace = trace
    safe.stats = stats
    return safe


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic fallback planner (same constraints, greedy)
# ─────────────────────────────────────────────────────────────────────────────
def fallback_plan(estate: CloudEstate) -> AgentRun:
    baseline = estate.baseline_cost()
    target_savings = 0.20 * baseline
    assignments: dict[str, str] = {}
    decommissioned: set[str] = set()
    moves: list[dict] = []
    saved = 0.0

    # 1) Decommission idle dev/test workloads (full savings + frees capacity).
    decomm_rows = []
    for name, app in estate.apps.items():
        if app.get("idle_candidate") and app["can_migrate"] and app["tier"] != 1:
            decommissioned.add(name)
            saved += app["monthly_cost"]
            decomm_rows.append(
                {"app": name, "region": app["region"], "monthly_saved": app["monthly_cost"]}
            )

    # 2) Move remaining movable apps to cheaper regions with headroom.
    movable = [
        n
        for n, a in estate.apps.items()
        if a["tier"] != 1 and a["can_migrate"] and n not in decommissioned
    ]
    for target in ("southindia", "uaenorth"):
        ceiling_u = estate.ceiling_units(target)
        used_u = estate.used_units(target, assignments, decommissioned)
        candidates = [n for n in movable if n not in assignments]
        # densest savings-per-unit first
        candidates.sort(
            key=lambda n: (
                (estate.apps[n]["monthly_cost"] - estate.effective_cost(n, target))
                / estate.apps[n]["capacity_units"]
            ),
            reverse=True,
        )
        for n in candidates:
            app = estate.apps[n]
            u = app["capacity_units"]
            s = app["monthly_cost"] - estate.effective_cost(n, target)
            if s <= 0:
                continue
            if used_u + u <= ceiling_u:
                assignments[n] = target
                used_u += u
                saved += s
                moves.append(
                    {
                        "app": n,
                        "from": app["region"],
                        "to": target,
                        "monthly_before": round(app["monthly_cost"]),
                        "monthly_after": round(estate.effective_cost(n, target)),
                        "monthly_saved": round(s),
                    }
                )
            if saved >= target_savings and _all_within_ceiling(estate, assignments, decommissioned):
                break
        if saved >= target_savings and _all_within_ceiling(estate, assignments, decommissioned):
            break

    md = _render_plan_markdown(
        estate, baseline, saved, moves, decomm_rows, assignments, decommissioned
    )
    # Hold the offline planner to the same bar as the model: both paths are
    # checked by the same validator, so the badge never claims more than was proven.
    proposal = MigrationPlan(
        moves=tuple(PlanMove(m["app"], m["to"]) for m in moves),
        decommissions=tuple(r["app"] for r in decomm_rows),
    )
    validation = validate_plan(estate, *proposal.validation_inputs())
    return AgentRun("fallback", md, trace=[], error=None, validation=validation, proposal=proposal)
