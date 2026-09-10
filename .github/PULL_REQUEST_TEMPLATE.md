## What this changes

<!-- One or two sentences. What and why. -->

## Checklist

- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `pytest` passes (the suite is offline; no credentials required)
- [ ] Tests cover the changed logic, and stay hermetic (no network, no real identity)
- [ ] No secret in code, tests, fixtures, screenshots, or commit messages

## If this changes how a service is called

- [ ] `docs/API_VERIFIED.md` is updated in this pull request
- [ ] The Microsoft Learn source is linked there
- [ ] The verification status is stated honestly: documentation-derived, or
      confirmed against a live endpoint (and if so, when)
