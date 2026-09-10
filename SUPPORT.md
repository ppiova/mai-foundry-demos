# Support

## How to get help

This project is a sample, maintained on a best-effort basis. There is no SLA.

- **Bugs and feature requests:** open an [issue](https://github.com/ppiova/mai-foundry-demos/issues),
  using the templates. Search existing issues first.
- **Questions about the code:** open an issue with the question template.
- **Security issues:** do not open an issue. Follow [SECURITY.md](SECURITY.md).

## Before you file

Most reports come down to configuration rather than code. Two checks answer most
of them:

```bash
# 1. Does the offline suite pass? If not, the problem is local, not in Azure.
pytest

# 2. Do the live services actually answer for your resource?
MAI_EXECUTION_MODE=strict python scripts/live_smoke.py
```

The smoke script prints which authentication mode is in use and which services are
configured. Include its output in your report.

A demo showing 🟡 FALLBACK when you expected 🟢 LIVE is usually one of:

- role assignments still propagating (allow five minutes after deployment)
- no signed-in identity (`az login`) and no key configured
- the Speech resource has no custom subdomain, which keyless Speech requires
- `MAI_SPEECH_RESOURCE_ID` missing, which keyless text to speech requires
- the model is not deployed, or not available in that region

## Support for Microsoft products

This repository does not provide support for Microsoft Foundry, Azure Speech, or
the MAI models themselves. For those, use
[Microsoft Learn](https://learn.microsoft.com/azure/ai-foundry/) or
[Azure support](https://azure.microsoft.com/support/).
