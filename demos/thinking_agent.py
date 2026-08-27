"""Demo 1 — MAI-Thinking-1 "Enterprise Decision Agent".

The model is given a cloud estate (18 apps) and two LOCAL tools:

    get_region_capacity(region)
    calculate_migration_cost(app_names, target_region)

It must build a migration plan that cuts cost 20% without moving Tier-1 apps and
without any region exceeding 70% capacity — reasoning, deciding which tools to
call, then producing the plan. This shows multi-step problem solving, not just a
hard question.

Live path  : real MAI-Thinking-1 tool-calling loop.
Fallback   : a deterministic greedy planner over the same data (so rehearsal and
             on-stage failures still produce a correct, data-driven plan).
"""

from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import streamlit as st

from mai import MAIClient

DATA = Path(__file__).resolve().parent.parent / "assets" / "data"


# ─────────────────────────────────────────────────────────────────────────────
# Data model + the two local tools
# ─────────────────────────────────────────────────────────────────────────────
class CloudEstate:
    def __init__(self):
        estate = json.loads((DATA / "cloud_estate.json").read_text(encoding="utf-8"))
        regions = json.loads((DATA / "region_capacity.json").read_text(encoding="utf-8"))
        self.objective: str = estate["objective"]
        self.apps: dict[str, dict] = {a["name"]: dict(a) for a in estate["applications"]}
        self.regions: dict[str, dict] = regions["regions"]
        self.ceiling: float = regions["capacity_ceiling_pct"]

    # -- capacity helpers ------------------------------------------------------
    def ceiling_units(self, region: str) -> float:
        return self.regions[region]["capacity_units_total"] * self.ceiling / 100.0

    def used_units(
        self,
        region: str,
        assignments: dict[str, str] | None = None,
        decommissioned: set[str] | None = None,
    ) -> float:
        decommissioned = decommissioned or set()
        used = self.regions[region]["baseline_overhead_units"]
        for name, app in self.apps.items():
            if name in decommissioned:
                continue
            reg = (assignments or {}).get(name, app["region"])
            if reg == region:
                used += app["capacity_units"]
        return used

    def utilization(self, region: str, assignments=None, decommissioned=None) -> float:
        total = self.regions[region]["capacity_units_total"]
        return 100.0 * self.used_units(region, assignments, decommissioned) / total

    def effective_cost(self, name: str, region: str) -> float:
        app = self.apps[name]
        src_idx = self.regions[app["region"]]["cost_index"]
        tgt_idx = self.regions[region]["cost_index"]
        return app["monthly_cost"] * (tgt_idx / src_idx)

    def baseline_cost(self) -> float:
        return sum(a["monthly_cost"] for a in self.apps.values())

    # -- TOOL: get_region_capacity --------------------------------------------
    def get_region_capacity(self, region: str) -> dict:
        if region not in self.regions:
            return {"error": f"Unknown region '{region}'. Valid: {list(self.regions)}"}
        r = self.regions[region]
        used = self.used_units(region)
        total = r["capacity_units_total"]
        return {
            "region": region,
            "display_name": r["display_name"],
            "cost_index": r["cost_index"],
            "capacity_units_total": total,
            "used_units": round(used, 1),
            "utilization_pct": round(100.0 * used / total, 1),
            "capacity_ceiling_pct": self.ceiling,
            "headroom_units_to_ceiling": round(self.ceiling_units(region) - used, 1),
        }

    # -- TOOL: calculate_migration_cost ---------------------------------------
    def calculate_migration_cost(self, app_names: list[str], target_region: str) -> dict:
        if target_region not in self.regions:
            return {"error": f"Unknown target_region '{target_region}'."}
        details, errors = [], []
        monthly_before = monthly_after = one_time = 0.0
        added_units = 0
        for name in app_names:
            app = self.apps.get(name)
            if not app:
                errors.append(f"Unknown app '{name}'.")
                continue
            if app["tier"] == 1 or not app["can_migrate"]:
                errors.append(f"'{name}' is Tier-{app['tier']} / non-migratable and cannot move.")
                continue
            before = app["monthly_cost"]
            after = self.effective_cost(name, target_region)
            monthly_before += before
            monthly_after += after
            one_time += before * 0.5  # simple one-time migration estimate
            added_units += app["capacity_units"]
            details.append(
                {
                    "app": name,
                    "from": app["region"],
                    "monthly_before": round(before),
                    "monthly_after": round(after),
                    "monthly_saved": round(before - after),
                }
            )
        resulting_used = self.used_units(target_region) + added_units
        total = self.regions[target_region]["capacity_units_total"]
        resulting_util = 100.0 * resulting_used / total
        return {
            "target_region": target_region,
            "apps": details,
            "errors": errors,
            "monthly_cost_before": round(monthly_before),
            "monthly_cost_after": round(monthly_after),
            "monthly_savings": round(monthly_before - monthly_after),
            "one_time_migration_cost": round(one_time),
            "resulting_target_utilization_pct": round(resulting_util, 1),
            "within_capacity_ceiling": resulting_util <= self.ceiling,
        }

    def dispatch(self, name: str, args: dict) -> dict:
        if name == "get_region_capacity":
            return self.get_region_capacity(args.get("region", ""))
        if name == "calculate_migration_cost":
            return self.calculate_migration_cost(
                args.get("app_names", []), args.get("target_region", "")
            )
        return {"error": f"Unknown tool '{name}'."}

    def summary_for_prompt(self) -> dict:
        return {
            "objective": self.objective,
            "capacity_ceiling_pct": self.ceiling,
            "regions": {
                k: {
                    "cost_index": v["cost_index"],
                    "capacity_units_total": v["capacity_units_total"],
                }
                for k, v in self.regions.items()
            },
            "applications": [
                {
                    k: a[k]
                    for k in (
                        "name",
                        "tier",
                        "region",
                        "monthly_cost",
                        "capacity_units",
                        "can_migrate",
                        "idle_candidate",
                        "dependencies",
                    )
                }
                for a in self.apps.values()
            ],
        }


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_region_capacity",
            "description": "Return current capacity, utilization %, headroom to the 70% ceiling, and cost index for a region.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "enum": ["eastus", "westeurope", "southindia", "uaenorth"],
                    }
                },
                "required": ["region"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_migration_cost",
            "description": "Estimate monthly savings, one-time cost, and the resulting target-region utilization for moving a set of apps to a target region. Rejects Tier-1 / non-migratable apps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_names": {"type": "array", "items": {"type": "string"}},
                    "target_region": {
                        "type": "string",
                        "enum": ["eastus", "westeurope", "southindia", "uaenorth"],
                    },
                },
                "required": ["app_names", "target_region"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are an enterprise cloud FinOps decision agent. You are given a cloud estate "
    "and two tools. Reason step by step, call the tools to verify capacity and cost "
    "before committing to moves, and respect every hard constraint:\n"
    "  1) Do NOT move any Tier-1 application.\n"
    "  2) No region may exceed the capacity ceiling (70%).\n"
    "  3) Achieve at least a 20% reduction in total monthly cost. Aim for 23-25% "
    "so a marginal estimate never lands under the 20% floor.\n"
    "Prefer decommissioning idle_candidate dev/test workloads and moving low-tier "
    "workloads to cheaper regions with headroom. When done, output a clear Markdown "
    "plan: a summary line with baseline vs new monthly cost and % saved, a table of "
    "moves/decommissions, the resulting per-region utilization, and a short "
    "'Tradeoffs & risks' section (mention dependencies and one-time migration cost).\n"
    "Finally, append a fenced ```json block with the machine-checkable plan:\n"
    '{"moves": [{"app": "<name>", "target_region": "<region>"}], '
    '"decommissions": ["<name>"], "risks": ["<short note>"]}\n'
    "It must list every action exactly once and match the table above."
)


@dataclass(frozen=True)
class PlanMove:
    app: str
    target_region: str


@dataclass(frozen=True)
class MigrationPlan:
    moves: tuple[PlanMove, ...]
    decommissions: tuple[str, ...]
    risks: tuple[str, ...] = ()

    @classmethod
    def from_validated_mapping(cls, proposal: dict) -> MigrationPlan:
        """Create typed data only after ``validate_plan`` accepts the raw mapping."""
        risks = proposal.get("risks", [])
        return cls(
            moves=tuple(PlanMove(item["app"], item["target_region"]) for item in proposal["moves"]),
            decommissions=tuple(proposal["decommissions"]),
            risks=tuple(risks) if isinstance(risks, list) else (),
        )

    def validation_inputs(self) -> tuple[list[dict], list[str]]:
        return (
            [{"app": move.app, "target_region": move.target_region} for move in self.moves],
            list(self.decommissions),
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
# Deterministic plan validation
#
# The model *proposes*; this code *decides*. `calculate_migration_cost` scores each
# proposal against the untouched baseline, so two moves that are individually fine
# can still breach the 70% ceiling once combined. Everything the UI reports as fact
# — savings, utilization, constraint compliance — is recomputed here from the
# estate, never taken from the model's prose.
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class PlanValidation:
    ok: bool
    violations: list[str] = field(default_factory=list)
    baseline_cost: float = 0.0
    new_cost: float = 0.0
    saved: float = 0.0
    saved_pct: float = 0.0
    one_time_cost: float = 0.0
    utilization: dict[str, float] = field(default_factory=dict)  # unrounded percentages
    ceiling: float = 70.0
    moved: int = 0
    decommissioned: int = 0
    risks: tuple[str, ...] = ()

    def over_ceiling(self, ceiling: float | None = None) -> int:
        """Regions above the ceiling.

        ``utilization`` is stored unrounded on purpose: rounding to 1dp first would
        let 70.04% display as 70.0% and slip past a ``> ceiling`` test, undercounting
        breaches that ``violations`` already recorded.
        """
        limit = self.ceiling if ceiling is None else ceiling
        return sum(1 for v in self.utilization.values() if v > limit)


def validate_plan(
    estate: CloudEstate,
    moves: list[dict],
    decommissions: list[str],
    min_savings_pct: float = 20.0,
    risks: object = None,
) -> PlanValidation:
    """Check a proposed plan against every hard constraint, cumulatively.

    ``moves``/``decommissions`` come straight from model-produced JSON, so their
    shape is untrusted: anything malformed is reported as a validation failure
    rather than raised, which would otherwise collapse the whole run into the
    fallback instead of showing *why* the proposal was rejected.
    """
    violations: list[str] = []
    assignments: dict[str, str] = {}
    decommissioned: set[str] = set()
    seen: set[str] = set()
    normalized_risks: list[str] = []

    if risks is not None:
        if not isinstance(risks, list):
            violations.append(f"'risks' must be a list, got {type(risks).__name__}.")
        else:
            for risk in risks:
                if not isinstance(risk, str) or not risk.strip():
                    violations.append("Risk entries must be non-empty strings.")
                else:
                    normalized_risks.append(risk.strip())

    if not isinstance(decommissions, list):
        violations.append(f"'decommissions' must be a list, got {type(decommissions).__name__}.")
        decommissions = []
    if not isinstance(moves, list):
        violations.append(f"'moves' must be a list, got {type(moves).__name__}.")
        moves = []

    for name in decommissions:
        if not isinstance(name, str):
            violations.append(f"Decommission entries must be app names, got {name!r}.")
            continue
        app = estate.apps.get(name)
        if not app:
            violations.append(f"Unknown application '{name}' in decommissions.")
            continue
        if name in seen:
            violations.append(f"'{name}' appears more than once in the plan.")
            continue
        seen.add(name)
        if app["tier"] == 1:
            violations.append(f"'{name}' is Tier-1 and must not be decommissioned.")
            continue
        if not app.get("idle_candidate"):
            violations.append(f"'{name}' is active and is not an idle decommission candidate.")
            continue
        decommissioned.add(name)

    for mv in moves:
        if not isinstance(mv, dict):
            violations.append(f"Move entries must be objects, got {mv!r}.")
            continue
        name = mv.get("app")
        target = mv.get("target_region")
        if not isinstance(name, str):
            violations.append(f"Move is missing a valid 'app' name: {mv!r}.")
            continue
        app = estate.apps.get(name)
        if not app:
            violations.append(f"Unknown application '{name}' in moves.")
            continue
        if name in seen:
            violations.append(f"'{name}' appears more than once in the plan.")
            continue
        seen.add(name)
        if not isinstance(target, str):
            # `x in dict` hashes x, so a dict/list target would raise TypeError.
            violations.append(f"Move for '{name}' has an invalid 'target_region': {target!r}.")
            continue
        if target not in estate.regions:
            violations.append(f"Unknown target region '{target}' for '{name}'.")
            continue
        if app["tier"] == 1:
            violations.append(f"'{name}' is Tier-1 and must not be moved.")
            continue
        if not app["can_migrate"]:
            violations.append(f"'{name}' is flagged as non-migratable.")
            continue
        if target == app["region"]:
            violations.append(
                f"'{name}' is already in '{target}'; same-region moves are not actions."
            )
            continue
        assignments[name] = target

    # Cumulative capacity — the check a per-proposal tool call cannot make.
    utilization: dict[str, float] = {}
    for region in estate.regions:
        util = estate.utilization(region, assignments, decommissioned)
        utilization[region] = util
        if util > estate.ceiling:
            violations.append(
                f"Region '{region}' ends at {util:.1f}%, above the {estate.ceiling:.0f}% ceiling."
            )

    # Dependencies of a decommissioned app must not be left dangling.
    for name, app in estate.apps.items():
        if name in decommissioned:
            continue
        for dep in app.get("dependencies", []):
            if dep in decommissioned:
                violations.append(f"'{name}' depends on decommissioned '{dep}'.")

    baseline = estate.baseline_cost()
    saved = 0.0
    one_time = 0.0
    for name in decommissioned:
        saved += estate.apps[name]["monthly_cost"]
    for name, target in assignments.items():
        saved += estate.apps[name]["monthly_cost"] - estate.effective_cost(name, target)
        one_time += estate.apps[name]["monthly_cost"] * 0.5

    saved_pct = 100.0 * saved / baseline if baseline else 0.0
    if saved_pct < min_savings_pct:
        violations.append(
            f"Savings {saved_pct:.2f}% fall short of the {min_savings_pct:.0f}% target."
        )

    return PlanValidation(
        ok=not violations,
        violations=violations,
        baseline_cost=baseline,
        new_cost=baseline - saved,
        saved=saved,
        saved_pct=saved_pct,
        one_time_cost=one_time,
        utilization=utilization,
        ceiling=estate.ceiling,
        moved=len(assignments),
        decommissioned=len(decommissioned),
        risks=tuple(normalized_risks),
    )


def extract_structured_plan(text: str) -> dict | None:
    """Pull the trailing ```json {...}``` plan out of the model's answer, if present."""
    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    for block in reversed(blocks):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and ("moves" in data or "decommissions" in data):
            return data
    return None


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


def _md_escape_dollars(text: str) -> str:
    """Escape ``$`` so Streamlit does not parse model-authored amounts as LaTeX."""
    return text.replace("$", r"\$")


def render_validated_plan(
    estate: CloudEstate, proposal: MigrationPlan, validation: PlanValidation
) -> str:
    """Render factual Markdown exclusively from the validated proposal and estate."""
    rows = ["| Action | Application | Region |", "|---|---|---|"]
    for move in proposal.moves:
        rows.append(f"| Move | {move.app} | {move.target_region} |")
    for name in proposal.decommissions:
        rows.append(f"| Decommission | {name} | {estate.apps[name]['region']} |")
    utilization = ["| Region | Final utilization |", "|---|---:|"]
    for region, value in validation.utilization.items():
        utilization.append(f"| {region} | {value:.1f}% |")
    risk_lines = [f"- {_md_escape_dollars(risk)}" for risk in proposal.risks]
    if not risk_lines:
        risk_lines = ["- Review dependencies and migration sequencing before execution."]
    return "\n".join(
        [
            "## Validated migration plan",
            "",
            f"Baseline **\\${validation.baseline_cost:,.0f}/month** → "
            f"**\\${validation.new_cost:,.0f}/month** "
            f"(**{validation.saved_pct:.1f}% monthly cost reduction**).",
            "",
            *rows,
            "",
            "### Resulting regional utilization",
            "",
            *utilization,
            "",
            f"Estimated one-time migration cost: **\\${validation.one_time_cost:,.0f}**.",
            "",
            "### Tradeoffs & risks",
            "",
            *risk_lines,
        ]
    )


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


def _all_within_ceiling(estate, assignments, decommissioned) -> bool:
    return all(
        estate.utilization(r, assignments, decommissioned) <= estate.ceiling for r in estate.regions
    )


def _render_plan_markdown(
    estate, baseline, saved, moves, decomm_rows, assignments, decommissioned
) -> str:
    pct = 100.0 * saved / baseline
    lines = [
        f"### Migration plan — {pct:.1f}% monthly cost reduction",
        f"**Baseline:** \\${baseline:,.0f}/mo → **New:** \\${baseline - saved:,.0f}/mo "
        f"(**−\\${saved:,.0f}**, {pct:.1f}%). Constraints: no Tier-1 moved, all regions ≤ {estate.ceiling:.0f}%.",
        "",
    ]
    if decomm_rows:
        lines += [
            "**Decommission idle dev/test workloads**",
            "",
            "| App | Region | Monthly saved |",
            "|---|---|--:|",
        ]
        lines += [
            f"| {r['app']} | {r['region']} | \\${r['monthly_saved']:,} |" for r in decomm_rows
        ]
        lines.append("")
    if moves:
        lines += [
            "**Move low-tier workloads to cheaper regions with headroom**",
            "",
            "| App | From → To | Before | After | Saved |",
            "|---|---|--:|--:|--:|",
        ]
        lines += [
            f"| {m['app']} | {m['from']} → {m['to']} | \\${m['monthly_before']:,} | "
            f"\\${m['monthly_after']:,} | \\${m['monthly_saved']:,} |"
            for m in moves
        ]
        lines.append("")
    # Resulting utilization
    lines += [
        "**Resulting region utilization**",
        "",
        "| Region | Before | After | Ceiling |",
        "|---|--:|--:|--:|",
    ]
    for r in estate.regions:
        before = estate.utilization(r)
        after = estate.utilization(r, assignments, decommissioned)
        flag = "✅" if after <= estate.ceiling else "⚠️"
        lines.append(f"| {r} | {before:.0f}% | {after:.0f}% {flag} | {estate.ceiling:.0f}% |")
    lines += [
        "",
        "**Tradeoffs & risks**",
        "- Moves incur a one-time migration cost (~50% of one month per app) and brief cutover risk.",
        "- Dependency chains stay intra-region where possible; verify latency for `recommendation-engine`→`catalog-svc` after the move.",
        "- Decommissioning `dev-sandbox`/`staging-cluster` assumes no active release train depends on them this cycle.",
        "- Tier-1 (`payments-core`, `identity-service`, `ledger-db`, `fraud-realtime`) untouched by design.",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit UI
# ─────────────────────────────────────────────────────────────────────────────
def render(client: MAIClient) -> None:
    estate = CloudEstate()
    st.subheader("🧠 MAI-Thinking-1 — Enterprise Decision Agent")
    st.caption(estate.objective)

    mode = (
        "🟢 LIVE (function calling)"
        if client.thinking_ready()
        else "🟡 FALLBACK (deterministic planner)"
    )
    st.info(f"Mode: **{mode}**  ·  tools: `get_region_capacity`, `calculate_migration_cost`")

    with st.expander("Cloud estate (18 applications)", expanded=False):
        st.dataframe(list(estate.apps.values()), width="stretch", hide_index=True)

    if st.button("▶ Run decision agent", type="primary", key="thinking_run"):
        is_live = client.thinking_ready()
        status = st.status(
            "Reasoning and calling tools…" if is_live else "Planning…", expanded=is_live
        )
        plan_ph = st.empty()
        state = {"buf": ""}

        def on_event(kind, **kw):
            if kind == "round":
                state["buf"] = ""
                plan_ph.markdown("")
                status.write(f"🧠 Reasoning — round {kw['n']}…")
            elif kind == "tool":
                status.write(
                    f"🔧 `{kw['name']}({json.dumps(kw['args'])})` → {kw.get('summary', '')}"
                )
            elif kind == "retry":
                state["buf"] = ""
                plan_ph.markdown("")
                status.write(
                    f"↻ No machine-checkable plan yet ({kw['chars']} chars) "
                    f"— asking again ({kw['n']})…"
                )
            elif kind == "delta":
                state["buf"] += kw["text"]
                plan_ph.markdown(state["buf"])

        run = run_agent(client, on_event=on_event)
        badge = "🟢 LIVE" if run.source == "live" else "🟡 FALLBACK"
        status.update(
            label=f"{badge} · {run.elapsed:.0f}s · {len(run.trace)} tool calls",
            state="complete",
            expanded=False,
        )
        if run.error:
            st.warning(
                f"Live call failed → fell back to the deterministic planner. Detail: {run.error}"
            )
        plan_ph.markdown(run.plan_markdown)

        if run.rejected_validation is not None:
            st.error(
                "The model proposal was rejected; the safe deterministic plan is shown instead."
            )
            for violation in run.rejected_validation.violations:
                st.markdown(f"- {violation}")

        # The model proposes; this panel reports what deterministic code verified.
        if run.validation is not None:
            v = run.validation
            st.markdown(
                "#### ✅ Deterministic validation" if v.ok else "#### ❌ Deterministic validation"
            )
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Verified savings", f"{v.saved_pct:.1f}%", f"-${v.saved:,.0f}/mo")
            c2.metric("Apps moved", v.moved)
            c3.metric("Decommissioned", v.decommissioned)
            c4.metric("Regions over ceiling", v.over_ceiling())
            if v.ok:
                origin = (
                    "Model proposal received"
                    if run.source == "live"
                    else "Offline planner proposal"
                )
                st.success(
                    f"{origin} · every hard constraint re-checked in code · numbers above are recomputed, not quoted."
                )
            else:
                st.error("The proposal failed deterministic validation:")
                for violation in v.violations:
                    st.markdown(f"- {violation}")
        elif run.source == "live":
            st.info(
                "The model returned prose without a machine-checkable `json` plan, so the numbers above are unverified."
            )

        if run.trace:
            with st.expander(f"🔧 Tool-call trace ({len(run.trace)} calls)", expanded=False):
                for i, (fn, args, res) in enumerate(run.trace, 1):
                    st.markdown(f"**{i}. `{fn}`** — args `{json.dumps(args)}`")
                    st.json(res, expanded=False)
