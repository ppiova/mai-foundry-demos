# Thinking workshop: the model proposes, code validates

A **45-minute, offline-first** lab using the actual **Thinking · Decision Agent**
demo. You will inspect a fictional cloud estate, reproduce its deterministic plan,
and reject an unsafe proposal. You will **not execute a migration**.

**Audience:** developers and cloud architects comfortable reading basic Python
and JSON; no agent framework or Azure account is required.

**Learning goals:** by the end, you should be able to:

1. Trace the UI → agent → local tools → validator → rendered-result flow.
2. Explain why two individually acceptable tool results can form an invalid plan.
3. Distinguish a validated offline plan from evidence of live model behavior.
4. Choose when fallback is useful and when a check must fail instead.
5. Name the costs and limits that require review before an optional LIVE run.

These are learning goals, not measured participant outcomes. This guide does not
claim that a workshop was tested with human participants or that a model achieves
a particular success rate.

> **Safety boundary:** all apps, costs, and regional capacity in `assets/data`
> are fictional. The tools perform local reads and arithmetic; no tool moves or
> deletes Azure resources. A passing validator means "satisfies these encoded
> fixture constraints," not "safe or economical to migrate a real estate."

## Prepare before the 45 minutes

- Follow the [README's Bash or PowerShell offline setup](../README.md#run-it-offline-first),
  including the explicit environment overrides. Download dependencies before
  disconnecting. Codespaces needs connectivity even when inference is offline.
- Keep the repository root as your working directory. Use Python 3.11+ and the
  same virtual environment for both the app and the exercises.
- Keep one terminal running Streamlit and open a second terminal at the repository
  root for the Python exercises. Activate the virtual environment there too.
- Record the revision with `git rev-parse --short HEAD` and the Python version
  with `python --version`. Do not record `.env` contents or credentials.
- Open the app at `http://localhost:8501`, or the forwarded port in Codespaces.
  The [existing screenshot](../assets/images/demo-ui-screenshot.png) shows the
  layout; badges in your own run determine its provenance.

**Do not rely on `MAI_AUTH_MODE=key` plus `MAI_EXECUTION_MODE=demo` alone.**
Configured endpoints and keys can still make LIVE calls. The README explicitly
overrides all three service endpoints and their keys with single-space values:
configuration strips them to empty, but `.env` cannot overwrite them. Keep those
overrides in the terminal that starts the app, and confirm every service shows
FALLBACK before clicking a run button. No new execution-mode flag is needed.

If setup takes longer, complete it first rather than spending the lab on Azure
provisioning. **The complete core lab works without LIVE.**

## Agenda and facilitator notes

| Minutes | Activity | Checkpoint / facilitator cue |
|---|---|---|
| 0–5 | State the objective and inspect the estate | Ask what the badge can and cannot prove; point out the four Tier-1 apps. |
| 5–12 | Run the offline UI and reproduce its plan | Require `FALLBACK` and a passing deterministic validation, not "the model reasoned." |
| 12–20 | Inspect the two local tools | Have learners predict UAE North headroom before seeing the calculation. |
| 20–30 | Combine moves, then break a protected-app rule | Ask for a prediction first; discuss every reported violation, not only capacity. |
| 30–37 | Trace the real implementation and its limits | Separate API errors, invalid proposals, and authentication substitution. |
| 37–42 | Offline evidence review **or** prearranged LIVE comparison | Default to offline. Do not spend the session waiting for quota or RBAC changes. |
| 42–45 | Exit check and optional feedback | Ask for one claim supported by evidence and one claim the run cannot support. |

Facilitators: demonstrate from a clean, pinned environment; allow pairs to share a
screen; read badge text aloud rather than relying on color. Show the source file
links below. Never improvise a successful LIVE response or relabel fallback to
keep the schedule. If a prearranged LIVE run exceeds the five-minute discussion
slot, stop attempting it and use the offline evidence review.

## 1. Observe the actual demo (0–12 minutes)

Open **🧠 Thinking · Decision Agent**, expand **Cloud estate (18 applications)**,
and locate the objective:

- at least **20%** monthly savings;
- no Tier-1 application moved;
- no region above the **70%** capacity ceiling.

Click **▶ Run decision agent**. With the README's offline overrides, the final
status must say **🟡 FALLBACK**, with **0 tool calls**. The offline planner directly
uses local methods; it does not simulate a model choosing tools.

For the unchanged bundled fixtures, expect:

| Output | Deterministic expected value |
|---|---|
| Baseline monthly cost | $177,000 (fictional) |
| New monthly cost | $140,704 rounded (fictional) |
| Verified savings | 20.5%, about $36,296/month (fictional) |
| Apps moved / decommissioned | 6 / 3 |
| Regions over ceiling | 0 |
| Final utilization: East US / West Europe | 67.7% / 34.3% |
| Final utilization: South India / UAE North | 63.3% / 33.3% |

The six moves send `catalog-svc`, `notification-hub`, `billing-reports`,
`order-api`, `recommendation-engine`, and `data-lake-etl` to `southindia`.
The three decommissions are `dev-sandbox`, `staging-cluster`, and `log-archive`.
These are results of the **greedy fallback algorithm**, not a reference model
answer or proof of an optimal plan.

In the second terminal, start the Python REPL with `python`. Paste the following
blocks into that same REPL as you progress (no shell-specific heredoc is needed).
These offline blocks call only the repository's local domain functions:

```python
from agents import CloudEstate, fallback_plan, validate_plan

estate = CloudEstate()
run = fallback_plan(estate)
v = run.validation
assert run.source == "fallback"
assert v is not None and v.ok, v
print(run.source, v.moved, v.decommissioned, v.over_ceiling())
print(round(v.baseline_cost), round(v.new_cost), round(v.saved_pct, 1))
print({region: round(value, 1) for region, value in v.utilization.items()})
```

Expected output:

```text
fallback 6 3 0
177000 140704 20.5
{'eastus': 67.7, 'westeurope': 34.3, 'southindia': 63.3, 'uaenorth': 33.3}
```

**Explain it:** [`fallback_plan`](../agents/decision.py) decommissions eligible
idle workloads, then tries lower-cost destinations in a fixed order, ranking
candidate moves by savings per capacity unit. It stops once the savings and
regional constraints are satisfied. It validates its own proposal with the same
function used for model proposals.

## 2. Inspect tool evidence (12–20 minutes)

Read [`CloudEstate`](../agents/estate.py) and its `TOOLS_SCHEMA`. The only two
model-callable tools are `get_region_capacity` and `calculate_migration_cost`.
Their names describe calculations, not Azure operations.

Predict the headroom for UAE North. Its fixture has 60 total units, a 70% ceiling,
and 20 units of baseline overhead: `60 × 0.70 − 20 = 22`.

```python
capacity = estate.get_region_capacity("uaenorth")
print(capacity["used_units"], capacity["headroom_units_to_ceiling"])
first = estate.calculate_migration_cost(["analytics-warehouse"], "uaenorth")
second = estate.calculate_migration_cost(["ml-training-pool"], "uaenorth")
print(first["resulting_target_utilization_pct"], first["within_capacity_ceiling"])
print(second["resulting_target_utilization_pct"], second["within_capacity_ceiling"])
```

Expected output:

```text
20 22.0
60.0 True
58.3 True
```

Both tool calls start from the **unchanged baseline**. They do not reserve
capacity or remember the other proposal. A tool's `within_capacity_ceiling=True`
only answers that tool calculation; it does not certify a complete plan.

## 3. Reject a plausible but invalid plan (20–30 minutes)

**Predict first:** can the two proposed moves coexist under the 70% ceiling?

```python
combined = [
    {"app": "analytics-warehouse", "target_region": "uaenorth"},
    {"app": "ml-training-pool", "target_region": "uaenorth"},
]
check = validate_plan(estate, combined, [])
print(check.ok, check.utilization["uaenorth"], round(check.saved_pct, 2))
print("\n".join(check.violations))
```

Expected output:

```text
False 85.0 2.39
Region 'uaenorth' ends at 85.0%, above the 70% ceiling.
Savings 2.39% fall short of the 20% target.
```

The final load is `20 + 16 + 15 = 51` units, or **85%** of 60. The savings floor
also fails. Deleting a warning from a Markdown explanation cannot fix either.

Now start from the valid fallback proposal and add a Tier-1 move:

```python
moves, decommissions = run.proposal.validation_inputs()
unsafe = validate_plan(
    estate,
    moves + [{"app": "payments-core", "target_region": "southindia"}],
    decommissions,
)
print(unsafe.ok)
print("\n".join(unsafe.violations))
```

Expected output:

```text
False
'payments-core' is Tier-1 and must not be moved.
```

`validate_plan` rejects the protected move rather than applying it to the
arithmetic. This is why you must inspect **`ok` and `violations`**, not accept a
proposal solely because its recomputed savings still look good.

**Optional extension:** pass `["catalog-svc"]` as the decommission list on a fresh
plan and find the active-workload violation. Read the dependency test in
[`test_plan_validation.py`](../tests/test_plan_validation.py): it deliberately
marks a fixture app idle **in memory** to isolate the dangling-dependency rule.
Do not edit the shared JSON files during the core lab.

## 4. Trace the implementation, not a story about it (30–37 minutes)

Open these files in order:

| Stage | Code | What actually happens |
|---|---|---|
| Display and run | [`demos/thinking_agent.py`](../demos/thinking_agent.py) | The button calls `run_agent`; streamed text is provisional, then replaced by the final rendered result. |
| Decide the route | [`agents/decision.py`](../agents/decision.py) | If Thinking is not configured, demo mode uses `fallback_plan`; strict mode raises. |
| LIVE conversation | [`mai/client.py`](../mai/client.py) | REST/SSE receives assistant text and tool requests. Opaque encrypted reasoning state is carried forward, not displayed. |
| Tool boundary | `execute_tool_call` in [`agents/decision.py`](../agents/decision.py) | Checks the tool name, call ID, and argument shape before dispatch to local arithmetic. |
| Whole-plan check | [`agents/plan.py`](../agents/plan.py) | Extracts fenced JSON, rejects invalid actions, and recomputes cumulative capacity and savings. |
| Final result | `_finish_live` in [`agents/decision.py`](../agents/decision.py) | Accepted model plans are rendered from validated data; missing/invalid plans produce a labelled fallback. |

Discuss these boundaries:

- A model-provided dollar amount is not ground truth. Accepted LIVE plan numbers
  are rendered from the fixture and validator, not copied from model prose.
- `risks` are checked for shape (non-empty strings), **not factual accuracy**.
  The validator does not check latency, residency, contracts, rollback readiness,
  every operational dependency, or whether the plan is globally optimal.
- Default agent limits are **8 rounds plus up to 2 final-answer retries**.
  Tools are withheld on the last round and final retries. The app does not set
  `max_completion_tokens` for this loop. A read timeout is not a total-run or
  cost limit; tool calls per model response are not bounded by the round count.
- Strict mode makes configuration/transport/API failures fail visibly. It does
  **not** disable `_finish_live`'s replacement of an invalid or unstructured plan,
  nor the configured-key safety net for failed Entra token acquisition.
- Therefore **strict + no exception is insufficient evidence of success**.
  Inspect final `source`, `validation.ok`, rejection details, and actual auth
  fallback state.

For the transport tradeoff and when not to degrade, read
[Design decisions](DESIGN_DECISIONS.md).

## 5. Offline evidence review (37–42 minutes, default)

No further network calls are needed. Ask:

1. Which result above came from a model? **None.**
2. Why did the combined proposal fail when both tool calculations passed?
   **Each tool used the baseline; the validator evaluated the whole proposal.**
3. Does "20.5% verified savings" estimate the Azure bill for this demo?
   **No. It is a calculation over a fictional migration estate.**
4. Does a green configuration indicator prove live authentication?
   **No. It checks readiness, not a successful service response.**

For maintainers with the development tools installed, the corresponding offline
regression checks can be run after leaving the REPL with `exit()`:

```text
python -m pytest tests/test_plan_validation.py tests/test_agent_retry.py tests/test_domain_independence.py
```

Install development tools only into the project virtual environment as described
in [CONTRIBUTING.md](../CONTRIBUTING.md). A passing offline test is not live API
verification.

## Optional LIVE branch

This can **replace** the 37–42 minute evidence review only when prearranged, or be
done after the workshop. It is not required for any core exercise. LIVE output
varies; there is no promised tool sequence, wording, latency, or savings figure.

### Preflight before the session

1. Obtain permission to use an existing supported Thinking deployment, with quota
   and the required role. Do not provision resources or change role assignments
   during the lab. Read the [verification record](API_VERIFIED.md): the
   2026-09-11 check did **not** prove Thinking keyless live success because quota
   blocked it. Model availability is not proof of quota availability.
2. Follow the README's [LIVE setup](../README.md#go-live) in a **new terminal**.
   Configure only Thinking if that is the intended scope. Leave Image and Speech
   unconfigured, and clear all keys in both `.env` and environment for a
   keyless-only experiment. Set `MAI_EXECUTION_MODE=strict`.
3. Review [actual service pricing](../README.md#costs). Agree a small attempt
   budget (for example, one preflight and one agent run), and stop on failure
   instead of retrying indefinitely. This is a human limit, not an app-enforced
   spending cap. Reduce scope or stay offline if an enforceable token/cost ceiling
   is required.
4. Run `python scripts/live_smoke.py --allow-partial` in Bash, or
   `python scripts\live_smoke.py --allow-partial` in PowerShell.
   It checks **all configured services**, not just Thinking. Its chat/stream
   checks do not exercise the complete migration-plan loop; image generation
   does not verify editing, and basic voice synthesis does not verify styles.
   Configured Transcribe **fails** if Voice does not provide LIVE audio, even
   in partial mode. Partial does not mean skipping configured services to pass.

### Accept or reject the LIVE evidence

Run the decision-agent UI once. Require the **final** LIVE badge, no
authentication-substitution warning, and a passing deterministic validation.
Do not infer keyless success merely from the initial mode label.
Inspect the tool trace too: only claim that the model used a particular tool if
that request and its result appear in the trace. A valid LIVE plan alone does
not prove which tools, if any, the model chose to call.

For a code-level, keyless-only check instead of that UI run, start a **new Python
REPL** in the configured strict terminal. **This block makes billable network
requests; none of the earlier Python blocks does.**

```python
from agents import run_agent
from mai import MAIClient

client = MAIClient()
assert client.cfg.strict, "Use MAI_EXECUTION_MODE=strict"
assert client.cfg.keyless_enabled, "This check is specifically for Entra"
assert not client.cfg.foundry_api_key, "Remove the configured key safety net"
live_run = run_agent(client)
print("source:", live_run.source)
print("validation_ok:", bool(live_run.validation and live_run.validation.ok))
print("auth_fallback_used:", bool(client.auth_fallback))
assert live_run.source == "live", "Fallback is not a successful LIVE check"
assert live_run.validation is not None and live_run.validation.ok
assert not client.auth_fallback, "A resource key is not keyless evidence"
```

The **acceptance criteria**, not a claimed observed result, are `source: live`,
`validation_ok: True`, and `auth_fallback_used: False`. On error, rejection, or
fallback, record "LIVE not established" and return to the offline branch.
Do not publish tokens, opaque reasoning state, full headers, or raw resource IDs.

Record only the revision, date, model/deployment version if known, selected
mode/auth path, final provenance, pass/fail, and a redacted explanation. A single
success is not a benchmark, a reliability guarantee, or production approval.

## Exit check and next step (42–45 minutes)

Write three sentences, locally or in your own notes:

1. One concrete constraint you verified and the code or output supporting it.
2. One thing fallback cannot establish about the real model or authentication.
3. One unmodeled risk that would prevent executing this plan in a real estate.

Stop the local app with **Ctrl+C** and exit the REPL. No Azure cleanup is needed
for offline work. If you separately created demo resources, follow the cautious
[infrastructure cleanup guidance](../infra/README.md#tear-down).

Optional feedback is welcome in English or Spanish through the
[learning question template](https://github.com/ppiova/mai-foundry-demos/issues/new?template=question.yml).
Tell us the step, expected observation, actual observation, and what would have
made the explanation clearer. There is no requirement to file an issue or share
participant information; see [SUPPORT.md](../SUPPORT.md).
