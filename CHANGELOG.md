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
  available quota, so the first deployment failed with `InsufficientQuota`.
  The 2026-09-11 observation found subscription-wide quota for this model;
  raise capacity only if you have headroom.
- **`LICENSE` is now `LICENSE.md`.**

### Added

- A 45-minute Thinking workshop with offline exercises, expected results and
  facilitator notes, plus a guide to the sample's design decisions.
- Learning objectives, Bash and PowerShell onboarding, a Codespaces entry point,
  and a question template for learning and setup feedback.
- A verification matrix distinguishing historical live evidence, offline
  contracts, current smoke coverage and untested scenarios.
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

- Changing the Voice demo language updates its default text and voice.
- Uploaded and generated audio have explicit, separate state; removing an upload
  no longer silently reuses it, and generating TTS cannot be overwritten by an
  old selected upload.
- Transcription comparisons label each result's source and identify mixed
  LIVE/FALLBACK output without claiming both transcripts are canned.
- Incomplete Thinking streams without a completion marker raise instead of
  returning partial messages as complete responses.
- The live smoke reports failures for configured but untested transcription,
  requires the configured image deployment, and continues reporting other
  service failures rather than aborting at the first exception.
- Migration estimates reject duplicate application names and do not double-count
  capacity for same-region moves.
- Keyless TTS readiness requires a region, matching the regional host corrected
  and live-verified in PR #14.
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

- Sample presentation now follows the companion Foundry throttling repository:
  metadata, workflow badges, author attribution, an evidence-first overview,
  guided document navigation, and explicit independent-community ownership.
- Contribution, conduct, and security policies describe the current maintainer
  and reporting routes instead of hypothetical Microsoft ownership.
- Cost guidance distinguishes consumption billing from reserved capacity and
  quota, without quoting unverified prices.
- The verification ledger incorporates the 2026-09-11 live observations from
  PR #14. Thinking keyless remains unverified; Transcribe-1.5's verbatim behavior
  is no longer presented as an unresolved question.
- `docs/API_VERIFIED.md` records the Transcribe documentation drift and its
  2026-09-11 follow-up: the tested 1.5 default matched explicit `verbatim`,
  flat `clean` was rejected, and the nested `modelOptions` path belongs to
  Transcribe-2. Diarization was not exercised.
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
