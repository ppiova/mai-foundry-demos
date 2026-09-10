"""Microsoft Entra ID (keyless) authentication for the MAI demos.

Keyless is the default. No API key ever has to be written to ``.env``, secrets
never reach the repository, and access is governed by Azure RBAC instead. Keys
remain supported as an explicit opt-out (``MAI_AUTH_MODE=key``) for environments
where no Entra identity is available.

Two token audiences are involved here, and they are **not** interchangeable:

* Foundry model inference (Thinking, Image) -> ``https://ai.azure.com/.default``
  with the **Cognitive Services User** role on the Foundry resource.
* Speech (Transcribe, Voice) -> ``https://cognitiveservices.azure.com/.default``
  with the **Cognitive Services Speech User** role on the Speech resource.

Speech additionally requires a custom subdomain on the resource, and the
``cognitiveservices/v1`` text-to-speech path expects the token wrapped as
``aad#{resourceId}#{token}``. Sources are recorded in docs/API_VERIFIED.md.

``DefaultAzureCredential`` resolves a managed identity when the app runs in
Azure, and the developer's ``az login`` / Visual Studio Code identity locally, so
the same code path works in both places.
"""

from __future__ import annotations

import time
from functools import lru_cache

# Token audiences. Foundry model inference and Speech are different audiences;
# sending one where the other is expected fails with a 401.
FOUNDRY_SCOPE = "https://ai.azure.com/.default"
SPEECH_SCOPE = "https://cognitiveservices.azure.com/.default"

# Refresh this long before the token actually expires, so a long-running
# reasoning call cannot start with a token that dies mid-request.
_EXPIRY_MARGIN_SECONDS = 300


class EntraUnavailableError(RuntimeError):
    """No Microsoft Entra token could be obtained.

    Raised when ``azure-identity`` is not installed or when no identity can be
    resolved. In ``demo`` execution mode the caller degrades to FALLBACK exactly
    as it does for a rejected key; in ``strict`` mode it propagates.
    """


@lru_cache(maxsize=1)
def entra_available() -> bool:
    """True when ``azure-identity`` is importable.

    Only the import is checked. Whether an identity actually resolves is a
    network question, and answering it here would make importing the config
    block on Azure. A missing identity surfaces on the first call instead, where
    the existing degrade-or-raise policy already applies.
    """
    try:
        import azure.identity  # noqa: F401
    except ImportError:
        return False
    return True


class TokenProvider:
    """Cache one Entra token per scope, refreshed shortly before expiry.

    One ``DefaultAzureCredential`` is shared across scopes: building it is the
    expensive part, and it is safe to reuse.
    """

    def __init__(self, credential=None):
        self._credential = credential
        self._tokens: dict[str, tuple[str, float]] = {}

    def _get_credential(self):
        if self._credential is None:
            try:
                from azure.identity import DefaultAzureCredential
            except ImportError as exc:
                raise EntraUnavailableError(
                    "Keyless authentication needs the azure-identity package "
                    "(pip install -r requirements.txt), or set MAI_AUTH_MODE=key."
                ) from exc
            self._credential = DefaultAzureCredential()
        return self._credential

    def token(self, scope: str) -> str:
        cached = self._tokens.get(scope)
        if cached and cached[1] - _EXPIRY_MARGIN_SECONDS > time.time():
            return cached[0]
        credential = self._get_credential()
        try:
            access = credential.get_token(scope)
        except Exception as exc:  # credential chain exhausted, no identity, ...
            raise EntraUnavailableError(
                f"Could not acquire a Microsoft Entra token for {scope}. "
                "Sign in with `az login`, or set MAI_AUTH_MODE=key to use resource keys. "
                f"({exc})"
            ) from exc
        self._tokens[scope] = (access.token, float(access.expires_on))
        return access.token

    def bearer(self, scope: str) -> str:
        return f"Bearer {self.token(scope)}"

    def speech_bearer(self, resource_id: str) -> str:
        """Authorization value for the ``cognitiveservices/v1`` speech paths.

        Those paths do not take a bare Entra token: it must be combined with the
        ARM resource ID as ``aad#{resourceId}#{token}``.
        """
        if not resource_id:
            raise EntraUnavailableError(
                "Keyless text to speech needs MAI_SPEECH_RESOURCE_ID (the ARM resource ID "
                "of the Speech resource). See .env.example."
            )
        return f"Bearer aad#{resource_id}#{self.token(SPEECH_SCOPE)}"
