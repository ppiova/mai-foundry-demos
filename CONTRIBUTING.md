# Contributing

Thanks for your interest. This is a demonstration and learning repository:
someone should be able to rehearse offline, understand what the code proves,
and opt into a clearly labelled LIVE run. We value small, reproducible
improvements that make that journey clearer without turning the sample into a
production framework.

This is an independent community project, not a Microsoft-owned repository.

## Editorial conventions

Use **US English** for the canonical documentation, code comments, prompts, and
UI text. The short Spanish orientation and questions in Spanish are welcome;
keep one canonical technical explanation rather than maintaining divergent copies.

Lead with the learning goal, then provide a runnable example, expected observation,
and limits on what it proves. Link service-specific claims to Microsoft Learn
through [the API verification record](docs/API_VERIFIED.md). Clearly distinguish
documented contracts, local implementation choices, and dated live observations.

Prefer links to the existing workshop, design guide, and verification record over
duplicating them. Use real workflow badges and recorded evidence; neither a badge
nor a Microsoft product name implies Microsoft ownership, endorsement, or support.
Keep changes focused on one learning or reliability improvement.

## Small contributions that help

You do not need an Azure subscription to contribute. For example:

- Clarify one confusing Bash or PowerShell setup step and describe how you
  checked it on your OS.
- Improve an expected observation in the
  [Thinking workshop](docs/THINKING_WORKSHOP.md), linking the relevant domain
  function or fixture rather than inventing a model result.
- Add an offline regression test for one malformed tool argument, invalid plan,
  or missing configuration; keep the case small and explain the invariant.
- Correct a Microsoft Learn link or distinguish "documented", "offline tested",
  and "verified live on this date" in the API record.
- Suggest clearer badge text, accessible instructions, or a short Spanish
  explanation where the learning path is unclear.

For a documentation-only PR, check links, headings, commands, and expected
observations; a prose edit does not require deploying Azure or running unrelated
tests. For a larger behavior change, explain the teaching goal and tradeoffs
before investing in a broad rewrite.

## Feedback without a pull request

Use the [learning question template](https://github.com/ppiova/mai-foundry-demos/issues/new?template=question.yml)
if you want to share feedback: the step you tried, revision, expected result,
actual result, and one suggested clarification are enough. English and Spanish
are welcome. No LIVE check, participant identity, attendance count, or evidence of
having run a group workshop is required. Do not claim a workshop, benchmark, or
user study occurred unless it actually did.

Please search existing issues first. You may also simply use the lab privately;
filing feedback is optional. See [SUPPORT.md](SUPPORT.md) for what to redact.

## Before you open a pull request

For code changes, use the virtual environment from the
[Bash/PowerShell setup](README.md#run-it-offline-first). Run the smallest relevant
offline test while iterating, then run the CI checks before submitting:

```bash
python -m pip install -r requirements.txt -c constraints.txt
python -m pip install ruff pytest
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

These commands also work in an activated PowerShell virtual environment. If
activation is blocked, use `.\.venv\Scripts\python.exe` instead of `python`.
Dependencies need to be downloaded before disconnecting; the tests themselves
are offline and require no credentials. The runtime constraints pin direct
dependencies; CI also checks the supported dependency ranges.

For changes limited to the Thinking domain, a useful focused check is:

```text
python -m pytest tests/test_plan_validation.py tests/test_agent_retry.py tests/test_domain_independence.py
```

In the PR, state what changed, which checks you ran, and what remains unverified.
Never run a billable LIVE check merely to make a docs-only PR look complete.

## House rules

- **The API surface is documented first.** [`docs/API_VERIFIED.md`](docs/API_VERIFIED.md)
  is the source of truth for everything in `mai/`. If you change how a service is
  called, update that file in the same pull request, with the Microsoft Learn link
  you used. Say plainly whether you verified it against a live endpoint or only
  against documentation. An unverified claim recorded as verified is worse than no
  claim.
- **Fallback output is always labelled.** Every result carries `source`
  (`live` or `fallback`) and the UI badges it. Never present deterministic offline
  output as real model output.
- **No secrets, ever.** Not in code, tests, fixtures, screenshots, or commit
  messages. Entra is preferred; configured keys may act as a safety net even
  in strict mode, so remove them when claiming a keyless-only check. If a
  secret is exposed, rotate it and follow [SECURITY.md](SECURITY.md) privately.
- **Tests for changed logic.** New behavior in `mai/` needs a test that fails
  without it. Tests must stay offline and hermetic: no network, no real identity,
  no dependence on who is logged in to Azure.
- **Keep the demos short.** Each one exists to make a single point in a few
  minutes. Features that make a demo longer or harder to explain are usually the
  wrong trade.
- **Keep evidence honest.** Fictional estate savings are not Azure billing
  estimates. A fallback plan is not model reasoning, a successful API call is
  not a production readiness review, and learning goals are not measured
  participant outcomes.

## Reporting bugs and asking for features

Use the issue templates. For anything security related, follow
[SECURITY.md](SECURITY.md) instead of opening a public issue.

## Licensing of contributions

Contributions are accepted under this repository's [MIT License](LICENSE.md).
By submitting a pull request, you confirm that you have the right to contribute
the material under those terms. This community repository does not currently
require a Contributor License Agreement or use Microsoft's CLA bot.
