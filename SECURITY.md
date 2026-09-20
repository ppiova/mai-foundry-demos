# Security

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Report them privately through
[GitHub's private vulnerability reporting](https://github.com/ppiova/mai-foundry-demos/security/advisories/new)
on this repository. You should receive an acknowledgement within three business days.

Include as much of the following as you can, so the issue can be reproduced quickly:

- Type of issue (for example: credential exposure, injection, insecure default)
- Full paths of the source files involved
- The affected commit or tag
- Any special configuration needed to reproduce it
- Step-by-step reproduction instructions
- Proof-of-concept or exploit code, if available
- The impact, including how an attacker might exploit it

This is an independent community repository. Its maintainer handles reports
through the private route above; this is not a Microsoft support or bug-bounty
channel. For a vulnerability in a Microsoft product rather than this sample,
follow [Microsoft's reporting guidance](https://msrc.microsoft.com/create-report).

## What this sample does with credentials

This is demonstration code. Read this before pointing it at anything you care about.

- **Entra preferred by default.** `MAI_AUTH_MODE=entra` prefers Microsoft Entra
  ID and Azure RBAC. No secret is needed, and `infra/main.bicep` deploys with
  `disableLocalAuth = true`, so the account issues no usable keys.
- **Configured keys are a safety net.** Keys can be used in explicit `key`
  mode, when Entra token acquisition fails, or when a service's keyless
  prerequisites are missing. This also applies in strict mode. Leave keys empty
  in both `.env` and the environment for a keyless-only check. `.env` is
  gitignored and must never be committed.
- **Error text can identify your environment.** The application does not
  intentionally display authorization headers, but it does show exception text
  from failed calls, including endpoints and Entra diagnostics. Do not assume
  that provider error messages are sanitized. Review them before sharing logs
  or screenshots, and run this on a local or otherwise trusted host, not an
  anonymous or shared public service.
- **Public network access.** The Bicep template sets `publicNetworkAccess: 'Enabled'`
  for a self-contained demo. Production deployments should use private endpoints.
- **No content filtering configuration is included.** The deployed models use the
  service defaults. Review them for your own use case.

## Responsible AI

The demos generate text, images, and speech with preview models. Outputs are not
reviewed, filtered, or fact-checked beyond the service defaults, and the sample
data (a fictional cloud estate, a fictional product brand) exists only to make the
demos legible. Assess the risks of any system you build from this code, and comply
with the applicable laws and safety standards for your use case.

## Automated checks

The repository combines workflows and GitHub platform settings:

| Check | Trigger / coverage |
|---|---|
| CodeQL (`security-and-quality`) | Python analysis on pull requests, pushes to `main`, and the scheduled run |
| PSRule for Azure | Infrastructure checks in CI on pull requests and pushes to `main` |
| Dependabot version updates | Scheduled update proposals for pip and GitHub Actions |
| Secret scanning and push protection | GitHub platform features for supported secret patterns; not proof that every sensitive value will be detected |

Secret scanning and push protection are repository settings rather than workflows,
and both were enabled when checked on 2026-09-20. Dependabot security updates
were disabled at that check; they are separate from scheduled version updates.
Recheck settings instead of treating this dated observation as a permanent guarantee.

Dependency review is not part of the current CI workflow. Adding
`actions/dependency-review-action` would also require the dependency graph and
appropriate repository settings; do not infer coverage from Dependabot PRs alone.

`ps-rule.yaml` excludes two rules, `Azure.Cognitive.PublicAccess` and
`Azure.Cognitive.PrivateEndpoints`, with the reasoning recorded in that file. A
sample a presenter runs from a laptop cannot sit behind a private endpoint. The
exposure those rules address is mitigated instead by deploying with
`disableLocalAuth = true`, which leaves no key to steal, and by scoping access to
two RBAC role assignments.

## Supported versions

Only the default branch is maintained. Fixes are not backported to tags.
