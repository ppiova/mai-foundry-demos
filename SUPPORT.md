# Support

## How to get help

This project is a sample, maintained on a best-effort basis. There is no SLA.

- **Bugs and feature requests:** open an [issue](https://github.com/ppiova/mai-foundry-demos/issues),
  using the templates. Search existing issues first.
- **Learning questions or workshop feedback:** use the
  [question template](https://github.com/ppiova/mai-foundry-demos/issues/new?template=question.yml).
  English and Spanish are welcome. A confusing step or a missing expected result
  is useful feedback; you do not need a code fix to participate.
- **Security issues:** do not open an issue. Follow [SECURITY.md](SECURITY.md).

Start with the [offline setup](README.md#run-it-offline-first) or the
[45-minute Thinking workshop](docs/THINKING_WORKSHOP.md). Neither requires an Azure
account. This is an educational sample, not a supported production system.

## Before you file

For a learning question, report the **step, revision, expected observation, and
actual observation**. A LIVE run is not a prerequisite for asking for help.
An issue is optional; do not send participant names, recordings, or personal data.

For a code problem, activate the project's virtual environment and use the
offline checks in [CONTRIBUTING.md](CONTRIBUTING.md). Failure there is a useful
local reproduction, not proof of an Azure service problem.

```text
python -m pytest
```

For an **authorized LIVE investigation only**, review costs and the intended
services before running preflight. In a fresh terminal configured for LIVE:

**Bash:**

```bash
MAI_EXECUTION_MODE=strict python scripts/live_smoke.py
```

**PowerShell:**

```powershell
$env:MAI_EXECUTION_MODE = "strict"
python scripts\live_smoke.py
```

By default all four services are required. Append `--allow-partial` only when
intentionally checking a subset; it still calls every configured service.
Transcription in this smoke script needs live audio from the Voice check.
If Transcribe is configured and that LIVE audio is unavailable, Transcribe
**fails**, even with `--allow-partial`; it is not silently skipped to produce
a passing result. No supplied audio file is required by this script.

A smoke pass covers only the checks it runs: image generation is not image
editing, basic voice synthesis is not style validation, and chat/tool transport
is not a complete migration-plan run. Consult the
[verification matrix](docs/API_VERIFIED.md) before drawing broader conclusions.

Share only a **redacted summary**: PASS/FAIL/SKIP, model family, date, selected
execution/auth mode, and relevant sanitized error text. Do not paste `.env`,
keys, bearer tokens, request headers, encrypted reasoning state, subscription or
resource IDs, tenant/user identifiers, or private endpoint names. Inspect any
screenshot before uploading it. Never attach an unreviewed diagnostic log.

## When FALLBACK is unexpected

A demo showing 🟡 FALLBACK when you expected 🟢 LIVE is usually one of:

- offline environment overrides from the README still active (restart in a new
  terminal and restart Streamlit; the configuration/client is cached)
- `MAI_EXECUTION_MODE=demo` permitting a failed API call to become fallback;
  `demo` itself is not an offline-only switch
- role assignments still propagating (allow five minutes after deployment)
- no signed-in identity (`az login`) and no key configured
- the Speech resource has no custom subdomain, which keyless Speech requires
- `MAI_SPEECH_RESOURCE_ID` missing, which keyless text to speech requires
- `MAI_SPEECH_REGION` mismatching the resource (TTS uses the regional host with
  both keys and Entra)
- the model is not deployed, or not available in that region
- Thinking quota unavailable; the recorded quota is subscription-global, so
  switching regions does not necessarily help
- a model proposal failing deterministic plan validation, or never returning
  the required machine-checkable plan

Read the **final result badge and warnings**, not just the initial configuration
indicator. Strict mode prevents transport/API fallback, but a rejected Thinking
plan can still be replaced by the offline planner. A passing validator proves the
encoded constraints, not that a real model produced the proposal.

## When a LIVE result is not keyless evidence

`MAI_AUTH_MODE=entra` prefers Entra; it does not prohibit keys. A configured key
can cover failed token acquisition, and Speech can use a key when its keyless
prerequisites are missing. This also applies in strict mode.

For a keyless-only test, remove keys from both `.env` and environment, confirm
the intended signed-in identity and role assignments, restart the app, and
inspect authentication-fallback warnings. The
[API verification record](docs/API_VERIFIED.md) separates live evidence from
offline tests. In particular, the 2026-09-11 checks did not establish Thinking
keyless live success because quota blocked that check. Do not treat another
service's success as proof of this path.

## Support for Microsoft products

This repository does not provide support for Microsoft Foundry, Azure Speech, or
the MAI models themselves. For those, use
[Microsoft Learn](https://learn.microsoft.com/azure/ai-foundry/) or
[Azure support](https://azure.microsoft.com/support/).
