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
    "  3) Achieve at least a 20% reduction in total monthly cost.\n"
    "Prefer decommissioning idle_candidate dev/test workloads and moving low-tier "
    "workloads to cheaper regions with headroom. When done, output a clear Markdown "
    "plan: a summary line with baseline vs new monthly cost and % saved, a table of "
    "moves/decommissions, the resulting per-region utilization, and a short "
    "'Tradeoffs & risks' section (mention dependencies and one-time migration cost)."
)


@dataclass
class AgentRun:
    source: str
    plan_markdown: str
    trace: list = field(default_factory=list)  # list of (tool, args, result)
    error: str | None = None
    elapsed: float = 0.0


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


def run_agent(client: MAIClient, max_rounds: int = 6, on_event=None) -> AgentRun:
    """Live streaming agent loop. ``on_event(kind, **kw)`` receives:
    ``round`` (n), ``tool`` (name, args, result, summary), ``delta`` (text)."""
    import time

    def emit(kind, **kw):
        if on_event:
            with contextlib.suppress(Exception):
                on_event(kind, **kw)

    estate = CloudEstate()
    if not client.thinking_ready():
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
    try:
        for rnd in range(1, max_rounds + 1):
            emit("round", n=rnd)
            msg, produced = None, ""
            stream = (
                client.chat_completion_stream(messages, tools=TOOLS_SCHEMA, tool_choice="auto")
                if rnd < max_rounds
                else client.chat_completion_stream(messages)
            )
            for kind, val in stream:
                if kind == "content":
                    produced += val
                    emit("delta", text=val)
                elif kind == "message":
                    msg = val
            messages.append(msg)
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                return AgentRun(
                    "live", msg.get("content") or produced or "", trace, elapsed=time.time() - t0
                )
            for tc in tool_calls:
                fn = tc["function"]["name"]
                args = json.loads(tc["function"].get("arguments") or "{}")
                result = estate.dispatch(fn, args)
                trace.append((fn, args, result))
                emit("tool", name=fn, args=args, result=result, summary=_tool_summary(fn, result))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": fn,
                        "content": json.dumps(result),
                    }
                )
        return AgentRun("live", produced or "", trace, elapsed=time.time() - t0)
    except Exception as exc:
        run = fallback_plan(estate)
        run.error = str(exc)
        run.elapsed = time.time() - t0
        return run


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
    return AgentRun("fallback", md, trace=[], error=None)


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
        f"**Baseline:** ${baseline:,.0f}/mo → **New:** ${baseline - saved:,.0f}/mo "
        f"(**−${saved:,.0f}**, {pct:.1f}%). Constraints: no Tier-1 moved, all regions ≤ {estate.ceiling:.0f}%.",
        "",
    ]
    if decomm_rows:
        lines += [
            "**Decommission idle dev/test workloads**",
            "",
            "| App | Region | Monthly saved |",
            "|---|---|--:|",
        ]
        lines += [f"| {r['app']} | {r['region']} | ${r['monthly_saved']:,} |" for r in decomm_rows]
        lines.append("")
    if moves:
        lines += [
            "**Move low-tier workloads to cheaper regions with headroom**",
            "",
            "| App | From → To | Before | After | Saved |",
            "|---|---|--:|--:|--:|",
        ]
        lines += [
            f"| {m['app']} | {m['from']} → {m['to']} | ${m['monthly_before']:,} | "
            f"${m['monthly_after']:,} | ${m['monthly_saved']:,} |"
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
        if run.trace:
            with st.expander(f"🔧 Tool-call trace ({len(run.trace)} calls)", expanded=False):
                for i, (fn, args, res) in enumerate(run.trace, 1):
                    st.markdown(f"**{i}. `{fn}`** — args `{json.dumps(args)}`")
                    st.json(res, expanded=False)
