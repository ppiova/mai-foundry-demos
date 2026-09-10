"""Keyless (Microsoft Entra ID) authentication.

The rest of the suite runs with ``MAI_AUTH_MODE=key`` (see conftest) so it never
reaches for a real identity. These tests drive the keyless path explicitly with a
stub credential, so they assert the wire format without touching Azure.

What matters here is that the two audiences stay separate, that the text to
speech path gets the ``aad#{resourceId}#{token}`` form it requires, and that a
resource key still rescues a call when no identity resolves.
"""

from __future__ import annotations

import time
from unittest.mock import Mock

import pytest

from mai.auth import FOUNDRY_SCOPE, SPEECH_SCOPE, EntraUnavailableError, TokenProvider
from mai.client import MAIClient
from mai.config import Config

RESOURCE_ID = (
    "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg"
    "/providers/Microsoft.CognitiveServices/accounts/speech"
)


class _StubToken:
    def __init__(self, token: str, expires_on: float):
        self.token = token
        self.expires_on = expires_on


class _StubCredential:
    """Records every scope it is asked for, so tests can assert the audience."""

    def __init__(self, lifetime: float = 3600.0):
        self.scopes: list[str] = []
        self.lifetime = lifetime

    def get_token(self, scope: str, **kwargs) -> _StubToken:
        self.scopes.append(scope)
        return _StubToken(f"token-for-{scope}", time.time() + self.lifetime)


class _FailingCredential:
    def get_token(self, scope: str, **kwargs):
        raise RuntimeError("no identity in this environment")


@pytest.fixture
def entra(monkeypatch):
    """Enable the keyless path without requiring azure-identity to be importable."""
    monkeypatch.setattr("mai.config.entra_available", lambda: True)


def _client(cfg: Config, credential=None) -> tuple[MAIClient, _StubCredential]:
    credential = credential or _StubCredential()
    return MAIClient(cfg, tokens=TokenProvider(credential)), credential


def _sent_headers(post: Mock) -> dict:
    return post.call_args.kwargs["headers"]


# ── audiences ────────────────────────────────────────────────────────────────
def test_foundry_uses_the_ai_azure_audience(entra):
    cfg = Config(auth_mode="entra", foundry_endpoint="https://r.services.ai.azure.com")
    client, credential = _client(cfg)
    assert client._foundry_auth("") == {"Authorization": f"Bearer token-for-{FOUNDRY_SCOPE}"}
    assert credential.scopes == [FOUNDRY_SCOPE]


def test_speech_uses_the_cognitiveservices_audience(entra):
    cfg = Config(auth_mode="entra", speech_endpoint="https://r.cognitiveservices.azure.com")
    client, credential = _client(cfg)
    assert client._speech_auth() == {"Authorization": f"Bearer token-for-{SPEECH_SCOPE}"}
    assert credential.scopes == [SPEECH_SCOPE]


def test_the_two_audiences_are_not_shared(entra):
    cfg = Config(
        auth_mode="entra",
        foundry_endpoint="https://r.services.ai.azure.com",
        speech_endpoint="https://r.cognitiveservices.azure.com",
    )
    client, credential = _client(cfg)
    client._foundry_auth("")
    client._speech_auth()
    assert credential.scopes == [FOUNDRY_SCOPE, SPEECH_SCOPE]


# ── text to speech: the aad# composite ───────────────────────────────────────
def test_tts_wraps_the_token_with_the_resource_id(entra):
    cfg = Config(
        auth_mode="entra",
        speech_endpoint="https://r.cognitiveservices.azure.com",
        speech_resource_id=RESOURCE_ID,
    )
    client, _ = _client(cfg)
    assert client._tts_auth() == {
        "Authorization": f"Bearer aad#{RESOURCE_ID}#token-for-{SPEECH_SCOPE}"
    }


def test_keyless_tts_targets_the_resource_host_not_the_regional_one(entra):
    cfg = Config(
        auth_mode="entra",
        speech_endpoint="https://r.cognitiveservices.azure.com",
        speech_resource_id=RESOURCE_ID,
        speech_region="eastus",
    )
    assert cfg.tts_url == "https://r.cognitiveservices.azure.com/cognitiveservices/v1"


def test_tts_without_a_resource_id_stays_on_the_key_and_regional_host(entra):
    """Keyless TTS is impossible without the resource ID, so it must not be claimed."""
    cfg = Config(
        auth_mode="entra",
        speech_endpoint="https://r.cognitiveservices.azure.com",
        speech_key="k",
        speech_region="eastus",
    )
    assert not cfg.voice_keyless
    assert cfg.tts_url == "https://eastus.tts.speech.microsoft.com/cognitiveservices/v1"
    client, _ = _client(cfg)
    assert client._tts_auth() == {"Ocp-Apim-Subscription-Key": "k"}


def test_transcription_stays_keyless_even_without_the_resource_id(entra):
    """Only cognitiveservices/v1 needs the composite; transcription takes a bare token."""
    cfg = Config(auth_mode="entra", speech_endpoint="https://r.cognitiveservices.azure.com")
    assert cfg.transcribe_keyless
    assert not cfg.voice_keyless


# ── token caching ────────────────────────────────────────────────────────────
def test_a_token_is_reused_until_it_nears_expiry(entra):
    cfg = Config(auth_mode="entra", foundry_endpoint="https://r.services.ai.azure.com")
    client, credential = _client(cfg)
    for _ in range(3):
        client._foundry_auth("")
    assert credential.scopes == [FOUNDRY_SCOPE]


def test_a_token_close_to_expiry_is_refreshed(entra):
    """A 60s token is inside the refresh margin, so every call must re-acquire."""
    cfg = Config(auth_mode="entra", foundry_endpoint="https://r.services.ai.azure.com")
    client, credential = _client(cfg, credential=_StubCredential(lifetime=60))
    client._foundry_auth("")
    client._foundry_auth("")
    assert credential.scopes == [FOUNDRY_SCOPE, FOUNDRY_SCOPE]


# ── degradation ──────────────────────────────────────────────────────────────
def test_a_configured_key_rescues_a_failed_token(entra):
    cfg = Config(auth_mode="entra", foundry_endpoint="https://r.services.ai.azure.com")
    client, _ = _client(cfg, credential=_FailingCredential())
    assert client._foundry_auth("fallback-key") == {"api-key": "fallback-key"}


def test_without_a_key_a_failed_token_is_raised(entra):
    cfg = Config(auth_mode="entra", foundry_endpoint="https://r.services.ai.azure.com")
    client, _ = _client(cfg, credential=_FailingCredential())
    with pytest.raises(EntraUnavailableError, match="az login"):
        client._foundry_auth("")


def test_a_missing_resource_id_is_a_clear_error_not_a_malformed_header():
    provider = TokenProvider(_StubCredential())
    with pytest.raises(EntraUnavailableError, match="MAI_SPEECH_RESOURCE_ID"):
        provider.speech_bearer("")


def test_keyless_is_off_when_azure_identity_is_missing(monkeypatch):
    monkeypatch.setattr("mai.config.entra_available", lambda: False)
    cfg = Config(auth_mode="entra", foundry_endpoint="https://r.services.ai.azure.com")
    assert not cfg.keyless_enabled
    assert not cfg.foundry_ready  # no key either, so nothing to fall back on


def test_invalid_auth_mode_is_rejected():
    with pytest.raises(ValueError, match="entra.*key"):
        Config(auth_mode="passwords")


def test_auth_mode_is_case_insensitive():
    cfg = Config(auth_mode=" KEY ")
    assert cfg.auth_mode == "key"
    assert not cfg.keyless_enabled


# ── no key ever leaks onto the wire when keyless is in use ───────────────────
def test_keyless_requests_carry_no_key_header(entra, monkeypatch):
    post = Mock(return_value=Mock(raise_for_status=Mock(), json=Mock(return_value={"ok": 1})))
    monkeypatch.setattr("mai.client.requests.post", post)
    cfg = Config(
        auth_mode="entra",
        foundry_endpoint="https://r.services.ai.azure.com",
        foundry_api_key="unused-key",
    )
    client, _ = _client(cfg)
    client.chat_completion([{"role": "user", "content": "hi"}])
    headers = _sent_headers(post)
    assert headers["Authorization"].startswith("Bearer ")
    assert "api-key" not in headers
    assert "unused-key" not in str(headers)
