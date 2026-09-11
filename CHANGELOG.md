# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Breaking

- **Authentication defaults to keyless.** `MAI_AUTH_MODE` now defaults to `entra`,
  so requests are authorized with Microsoft Entra ID and Azure RBAC. An existing
  `.env` holding only `MAI_*_API_KEY` values still works, because a configured key
  takes over when no identity resolves, but the run is no longer keyless and the
  sidebar says so. Set `MAI_AUTH_MODE=key` to pin the previous behavior.
- **`infra/main.bicep` deploys with `disableLocalAuth = true`.** A default
  deployment now issues no usable keys at all. Deploy with
  `disableLocalAuth = false` if you need the key path.
- **`thinkingCapacity` defaults to 10 instead of 50.** 50 commonly exceeded the
  per-subscription, per-region quota on a fresh subscription, so the first
  deployment failed with `InsufficientQuota`. Raise it if you have the quota.
- **`LICENSE` is now `LICENSE.md`.**

### Added

- Keyless authentication with Microsoft Entra ID (`mai/auth.py`), resolved per
  service, with the two token audiences and the `aad#{resourceId}#{token}` form
  that the text to speech path requires.
- RBAC role assignments in the Bicep template: Cognitive Services User for model
  inference, Cognitive Services Speech User for the Speech APIs.
- `agents/`, holding the estate, the plan validator and the agent loop, so the
  rules of the decision demo can be exercised without Streamlit.
- Governance: `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SUPPORT.md`, issue and pull request templates, `CODEOWNERS`, Dependabot.
- CodeQL and PSRule for Azure in CI, with the rule exclusions and their reasoning
  recorded in `ps-rule.yaml`.
- `constraints.txt`, pinning the versions a presented run was verified with.
- Synthetic voice disclosure wherever audio is played, consent captions on the
  audio uploaders, and AI-generated captions on the image surfaces.
- Region guidance in `infra/README.md`: only four regions serve both
  MAI-Transcribe and MAI voices, and a Speech resource outside them fails
  silently rather than loudly.

### Fixed

- Strict mode no longer answers from a different image deployment than the one
  requested, which had let `scripts/live_smoke.py` report PASS for a generation
  deployment that does not exist.
- Endpoints must be HTTPS. A `http://` or schemeless endpoint previously sent a
  credential in cleartext with no visible symptom.
- A malformed image upload now fails with a clear error instead of escaping as
  `UnidentifiedImageError`, and the uploaded content type comes from the bytes
  rather than from what the browser claimed.
- The sidebar reports the authentication path per service. It previously showed
  LIVE next to "key missing" and told users to add keys on the keyless path.
- `.github/workflows/live-smoke.yml` signs in with federated credentials and pins
  `MAI_AUTH_MODE=entra`, so it exercises the keyless path instead of silently
  falling through to a key.
- The transcribe demo no longer asserts model behavior about two canned strings
  when it runs offline.

### Changed

- `docs/API_VERIFIED.md` records three differences found between it and the
  current Microsoft Learn page for MAI-Transcribe: diarization is supported,
  `transcribeStyle` defaults to `verbatim`, and the parameter is nested under
  `modelOptions` for Transcribe-2. Recorded as drift with the open questions
  stated, pending a live run.
- README restructured to the section layout a published sample is expected to
  carry, with the security, responsible AI, and trademark notices.
- CI runs on Python 3.11 and 3.13.

## [1.1.1] - 2026-08-28

### Fixed

- A healthy live reasoning run no longer degrades to FALLBACK.
- Dollar amounts in model-authored text no longer render as LaTeX.

### Added

- `docs/IMAGE_PRESERVATION.md`, measuring what the image edit actually preserved,
  with the script that reproduces the numbers.

## [1.1.0] - 2026-08-28

### Added

- The live verification rounds recorded in the README and `docs/API_VERIFIED.md`.

## [1.0.2] - 2026-08-27

### Fixed

- Documentation corrections following the first live validation.

## [1.0.1] - 2026-08-27

### Fixed

- Follow-up corrections to the initial release.

## [1.0.0] - 2026-08-27

### Added

- Initial release: four MAI capability demos plus a multimodal finale, the
  LIVE and FALLBACK execution model, the Bicep template, and the offline suite.

[Unreleased]: https://github.com/ppiova/mai-foundry-demos/compare/v1.1.1...HEAD
[1.1.1]: https://github.com/ppiova/mai-foundry-demos/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/ppiova/mai-foundry-demos/compare/v1.0.2...v1.1.0
[1.0.2]: https://github.com/ppiova/mai-foundry-demos/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/ppiova/mai-foundry-demos/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/ppiova/mai-foundry-demos/releases/tag/v1.0.0
