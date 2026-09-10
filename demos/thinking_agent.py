"""Demo 1 — MAI-Thinking-1 "Enterprise Decision Agent".

The model is given a cloud estate (18 apps) and two LOCAL tools:

    get_region_capacity(region)
    calculate_migration_cost(app_names, target_region)

It must build a migration plan that cuts cost 20% without moving Tier-1 apps and
without any region exceeding 70% capacity, reasoning, deciding which tools to
call, then producing the plan. This shows multi-step problem solving, not just a
hard question.

Live path  : real MAI-Thinking-1 tool-calling loop.
Fallback   : a deterministic greedy planner over the same data (so rehearsal and
             on-stage failures still produce a correct, data-driven plan).

This module is the view. The estate, the validator and the agent loop live in
``agents/``, so the rules of the demo can be tested without Streamlit.
"""

from __future__ import annotations

import json

import streamlit as st

from agents import CloudEstate, run_agent
from mai import MAIClient


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
