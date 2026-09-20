# Upgrading from v1.1.1 to v2.0.0

Keep your demo repeatable while choosing authentication explicitly. The
[v2.0.0 release](../CHANGELOG.md#200---2026-09-20) changes authentication and
deployment defaults, which is why it is a major version. A stable repository
release does not make the selected preview services generally available or
establish production readiness or model quality.

## Review configuration before going LIVE

Preserve your existing `.env` and any customized Bicep parameters; compare them
with [`.env.example`](../.env.example) and
[`infra/main.bicep`](../infra/main.bicep) rather than overwriting them. Never
commit credentials. Refresh the virtual environment using the
[README setup](../README.md#run-it-offline-first) for this revision.

| Change | Action for an existing installation |
|---|---|
| `MAI_AUTH_MODE` defaults to `entra` | Choose Entra deliberately, or set `MAI_AUTH_MODE=key` explicitly to preserve the previous resource-key mode. Endpoints and deployment names remain per-service settings. |
| Bicep defaults to `disableLocalAuth = true` | Keep this keyless posture unless you explicitly require resource keys. Key mode, including key fallback, needs a resource that permits local authentication (`disableLocalAuth = false`); changing the app setting alone does not enable keys on the resource. |
| `thinkingCapacity` defaults to `10`, previously `50` | Review saved overrides and check current model availability and quota before deploying. A lower default does not guarantee headroom or availability. |
| `LICENSE` is now `LICENSE.md` | Update scripts, packaging rules, and links that refer to the old filename. The project remains [MIT-licensed](../LICENSE.md). |

Updating the checkout does not change an existing Azure resource. Before any
optional redeployment, review the effective parameters: an old explicit value
still overrides a new template default.

For Entra, follow the [authentication prerequisites](../README.md#authentication)
and [infrastructure access model](../infra/README.md#access-model). In particular,
use the intended identity and RBAC assignments; Speech has additional resource
metadata requirements. `MAI_AUTH_MODE=entra` is a preference, **not a guarantee
that a call is keyless**. A configured key can take over when token acquisition
fails, even in strict mode. A service whose keyless prerequisites are absent can
also use its configured key. Do not enable local authentication just to silence
an Entra failure.

The [quota guidance](../infra/README.md#quota) records subscription-wide Thinking
quota on 2026-09-11. Lowering capacity or switching regions did not solve
exhausted quota in that observation. If you only need Image and Speech, set
`deployThinkingModel = false` and leave `MAI_FOUNDRY_ENDPOINT` unconfigured so the
app does not try to call an undeployed Thinking model. Configure Image and Speech
independently, after checking their own availability.

## Verify offline first

Follow the [README's offline route](../README.md#run-it-offline-first), then the
[Thinking workshop](THINKING_WORKSHOP.md). Use its explicit endpoint and key
overrides even if you already have a working `.env`: `MAI_EXECUTION_MODE=demo`
alone still calls configured services. No Azure sign-in, deployment, or inference
is required for this route; download Python dependencies before disconnecting.

For the unchanged fictional estate, expect a labeled FALLBACK plan with passing
deterministic validation, **20.5%** savings, **6** moves, **3** decommissions, and
**0** regions over the ceiling. This verifies the local teaching path, not model
reasoning, Azure pricing, or authentication.

## If you choose to verify LIVE

Use a fresh terminal and follow [Go LIVE](../README.md#go-live) and
[Verify](../README.md#verify) only after reviewing permissions, availability,
quota, and [costs](../README.md#costs). These optional calls can incur charges.

- `any_service_ready` and the sidebar's **configured for LIVE** indicators check
  configuration, not token acquisition, deployed-model availability, or service
  health. They are not evidence of a successful request.
- For a keyless-only check, select `MAI_AUTH_MODE=entra` and remove
  `MAI_FOUNDRY_API_KEY`, `MAI_IMAGE_API_KEY`, and `MAI_SPEECH_KEY` from both
  `.env` and the process environment. Inspect the final result's `source` and
  the client's `auth_fallback` warning: `source="live"` can also mean a real
  request authenticated with a key. The absence of that warning is not proof of
  Entra use.
- Use `MAI_EXECUTION_MODE=strict` for live verification, but check the final
  Thinking result for `source="live"` and `validation.ok`. Strict mode raises
  configuration and transport/API failures; the agent still substitutes its
  deterministic plan when the final model proposal is invalid or lacks
  machine-checkable JSON. This existing behavior is not a v2.0.0 regression.
  Reject that FALLBACK result as evidence of model success.

## Known limits and evidence

The [verification matrix](API_VERIFIED.md#verification-at-a-glance) preserves the
**2026-09-11** Image and Speech keyless observations. **Thinking keyless remains
unverified because quota blocked that run.** This release preparation adds no
new live Azure verification. The earlier `v1.1.1` results and its linked field
report predate keyless support and cannot establish current Entra behavior.

The [authentication record](API_VERIFIED.md#0-authentication) also documents
`DefaultAzureCredential` selecting an unintended identity; a successful sign-in
alone does not establish which identity the app uses. The smoke script covers
selected API operations, not a full decision-agent plan or model-quality
benchmark. The UI agent has no configured completion-token or spending cap.

See [design decisions](DESIGN_DECISIONS.md) for the validation, fallback, and
cost boundaries. Passing local checks or a live request offers no production,
model-quality, or cost guarantee. This remains an independent community sample,
not a Microsoft-endorsed or Microsoft-supported product.
