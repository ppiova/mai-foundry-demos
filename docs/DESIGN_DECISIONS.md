# Design decisions and teaching boundaries

This is an explainable demo, not an infrastructure controller or production agent
platform. These choices support the [Thinking workshop](THINKING_WORKSHOP.md);
they describe the current code, not a roadmap or a participant study.

## 1. Visible REST contracts, with an identity SDK

[`mai/client.py`](../mai/client.py) calls Foundry and Speech over HTTPS using
`requests`. REST keeps the native `/mai/v1` routes, multipart image requests,
Speech SSML, SSE assembly, tool-call deltas, and service errors visible. It makes
the documented request contract easy to compare with the implementation.

**Tradeoff:** this repository owns transport and stream parsing that an inference
SDK might otherwise manage. More code here is not evidence that REST is always
better, faster, or more reliable. An SDK is a reasonable alternative when its
supported API version, fields, and retry behavior fit the application. Validate
those contracts before replacing the transport.

**Not SDK-free:** [`mai/auth.py`](../mai/auth.py) uses `azure-identity` for Entra
credentials. Foundry and Speech have different token audiences; TTS has its own
regional endpoint and token wrapper. See [API_VERIFIED.md](API_VERIFIED.md) for
sources and dated verification, rather than treating SDK defaults as evidence.

## 2. Local domain logic, independent of Streamlit

[`agents/estate.py`](../agents/estate.py) loads fictional JSON and exposes two
read-only arithmetic tools. [`agents/decision.py`](../agents/decision.py) owns the
loop; [`agents/plan.py`](../agents/plan.py) owns validation and factual rendering.
[`demos/thinking_agent.py`](../demos/thinking_agent.py) is the view.

**Benefit:** the constraints and failure cases can be exercised without a UI,
credentials, Azure resources, or model requests. The model can choose tool calls,
but the dispatch code validates their names and argument shapes. There is no
shell-execution, deployment, deletion, or migration tool.

**Limit:** passing local validation says nothing about real resource inventory,
regional model availability, or Azure pricing. The estate's regional cost indices
are fictional, not recommendations for choosing an Azure inference region.

## 3. Validate the whole proposal, then render facts

Tool calculations use the original estate. Two moves that each fit separately
can exceed capacity together; only a cumulative check can catch that.
`validate_plan` checks action shape, known apps/regions, protected/non-migratable
moves, duplicates, same-region no-ops, idle decommissions, dangling dependencies,
capacity, and the savings floor.

For an accepted LIVE proposal, factual tables and amounts are generated from
validated typed data, not the model's Markdown claims. Streaming text in the UI
is provisional until final validation replaces it.

**Limit:** the validator is not a real migration approval process. It does not
prove optimality, validate the truth of risk prose, model all operational
dependencies, assess data residency or downtime, or authorize actions. Human
review and substantially broader controls would be needed for a real system.

## 4. Fallback supports teaching continuity, not evidence substitution

The fallback planner is greedy and deterministic. It runs against the same
fixtures and passes through the same validator. Its `source="fallback"` and empty
model tool trace are part of the lesson, not defects to hide.

| Situation | Correct policy for this sample |
|---|---|
| Offline rehearsal or explaining local constraints | Use explicitly labelled FALLBACK. |
| An API fails during a presentation | Demo mode can continue with labelled fallback; say the live capability was not established. |
| API/auth preflight, model measurement, or a live-success claim | Use strict mode and reject fallback as a successful result. |
| A model plan is invalid or lacks machine-checkable JSON | Show the rejection and label the replacement offline plan; never use the unsafe proposal. |
| A safety/policy block occurs | Treat it as a failed live attempt, not permission to circumvent the service's decision. |
| A real operational decision or production action | Do not use the sample's fallback as an authority to proceed. |

**Important implementation detail:** strict mode raises configuration and
transport/API failures, but `_finish_live` still replaces missing/invalid model
plans with fallback. Separately, a configured resource key can replace failed
Entra token acquisition even in strict mode. A verification caller must check
`source`, `validation.ok`, and auth fallback; keyless-only tests must remove keys.

The initial sidebar/readiness state checks configuration, not service health.
Only the outcome of an actual request can supply live evidence. This is why the
[verification record](API_VERIFIED.md) distinguishes offline coverage from
dated live observations, including the quota-blocked Thinking keyless check.

## 5. Bound the experiment without pretending to bound every cost

The default Thinking loop uses eight rounds and up to two final-answer retries.
It withholds tools on its last round and on retries, but it does not set a
completion-token cap or an end-to-end spending limit. The latest reported stats
are not an aggregate billing ledger across all rounds.

Rehearse offline, decide the number of LIVE attempts in advance, configure only
the intended services, and stop on failed acceptance checks. For an experiment
that requires enforced token/spending ceilings, add and test those controls
before running it, or stay offline.

The infrastructure uses `GlobalStandard` consumption-based deployments, not
reserved Provisioned PTUs. TPM quota is not a fixed recurring bill, and image
and Speech meters should not be inferred from chat pricing. See the
[per-service pricing references](../README.md#costs) and Microsoft's
[deployment-type guide](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/deployment-types).
No prices, model-quality scores, or workshop-effectiveness metrics are asserted
here.
