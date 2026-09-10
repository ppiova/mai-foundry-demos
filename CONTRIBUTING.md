# Contributing

Thanks for your interest. This is a demonstration repository: the goal is that
someone can clone it and run four MAI capabilities live, on stage, without
surprises. Changes are judged against that.

## Before you open a pull request

Run what CI runs. The whole suite is offline and needs no credentials:

```bash
pip install -r requirements.txt
pip install ruff pytest
ruff check .
ruff format --check .
pytest
```

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
  messages. Keyless is the default path; keys are an opt-in. If you think you
  committed one, say so immediately and rotate it.
- **Tests for changed logic.** New behavior in `mai/` needs a test that fails
  without it. Tests must stay offline and hermetic: no network, no real identity,
  no dependence on who is logged in to Azure.
- **Keep the demos short.** Each one exists to make a single point in a few
  minutes. Features that make a demo longer or harder to explain are usually the
  wrong trade.

## Reporting bugs and asking for features

Use the issue templates. For anything security related, follow
[SECURITY.md](SECURITY.md) instead of opening a public issue.

## Contributor License Agreement

> **Note for the maintainer.** If this repository moves to a Microsoft-owned
> organization, add the standard Microsoft CLA section here: contributions require
> agreeing to the [Microsoft CLA](https://cla.opensource.microsoft.com), and the
> CLA bot annotates pull requests automatically. It does not apply while the
> repository is personally owned.
