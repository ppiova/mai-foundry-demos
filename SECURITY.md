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
- **No secret is ever printed.** Error text from failed calls is surfaced in the
  UI; tokens and keys are not.
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

## Supported versions

Only the default branch is maintained. Fixes are not backported to tags.
