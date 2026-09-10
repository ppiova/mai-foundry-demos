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

> **Note for the maintainer.** If this repository moves to a Microsoft-owned
> organization, replace this section with the standard Microsoft Security Response
> Center policy: reports then go to [MSRC](https://msrc.microsoft.com/create-report)
> or secure@microsoft.com, and the [Microsoft Bug Bounty](https://aka.ms/opensource/security/bounty)
> terms apply.

## What this sample does with credentials

This is demonstration code. Read this before pointing it at anything you care about.

- **Keyless by default.** `MAI_AUTH_MODE=entra` authenticates with Microsoft Entra
  ID and Azure RBAC. No secret is needed, and `infra/main.bicep` deploys with
  `disableLocalAuth = true`, so the account issues no usable keys.
- **Keys are opt-in.** `MAI_AUTH_MODE=key` reads resource keys from the
  environment. `.env` is gitignored and must never be committed. Nothing in this
  repository writes a key to disk or logs one.
- **No secret is printed, but error text is.** Tokens and keys never reach the UI.
  The text of a failed call does, verbatim, so the presenter can see why a demo
  degraded: that can include the endpoint and Entra diagnostic detail. The endpoint
  is not a secret, it is a Bicep output the operator typed in, and burying the cause
  of a fallback would make the on-stage story worse. Run this on a local or
  otherwise trusted host, not on a shared one.
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

Every push and pull request runs:

| Check | Covers |
|---|---|
| CodeQL (`security-and-quality`) | Static analysis of the Python source, weekly as well as per change |
| PSRule for Azure | The Bicep infrastructure against the Azure Well-Architected rules |
| Dependabot | Weekly version updates for pip and GitHub Actions |
| Secret scanning with push protection | The full history, and any push containing a recognized secret |

Secret scanning and push protection are repository settings rather than workflows,
and both are enabled.

Two settings are not yet enabled, and each unlocks a further check:

- **Dependency graph**, which `actions/dependency-review-action` needs to block a
  pull request that introduces a vulnerable or incompatibly licensed dependency.
- **Dependabot security updates**, which opens a pull request when an advisory
  affects a dependency in use, separate from the weekly version updates.

`ps-rule.yaml` excludes two rules, `Azure.Cognitive.PublicAccess` and
`Azure.Cognitive.PrivateEndpoints`, with the reasoning recorded in that file. A
sample a presenter runs from a laptop cannot sit behind a private endpoint. The
exposure those rules address is mitigated instead by deploying with
`disableLocalAuth = true`, which leaves no key to steal, and by scoping access to
two RBAC role assignments.

## Supported versions

Only the default branch is maintained. Fixes are not backported to tags.
