"""Defects found by the publication audit, each with the failure it prevents.

Every test here corresponds to a way the client could report success while doing
something other than what was asked. That is the failure mode this repository can
least afford, because the whole LIVE/FALLBACK story rests on the badge being true.
"""

from __future__ import annotations

import io
from unittest.mock import Mock

import pytest
import requests
from PIL import Image

from mai.client import MAIClient, _require_https, _validate_image
from mai.config import Config

ENDPOINT = "https://example.services.ai.azure.com"


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buf, "PNG")
    return buf.getvalue()


def _http_error(status: int) -> requests.HTTPError:
    response = Mock()
    response.status_code = status
    return requests.HTTPError(response=response)


class _Fails:
    """A post() that always raises the given HTTP status, counting attempts."""

    def __init__(self, status: int):
        self.status = status
        self.models: list[str] = []

    def __call__(self, url, **kwargs):
        self.models.append(kwargs["json"]["model"])
        raise _http_error(self.status)


# ── strict mode must not answer with a different deployment ──────────────────
def test_strict_mode_does_not_swap_to_another_deployment(monkeypatch):
    """A generation deployment that does not exist has to fail, not be substituted.

    Otherwise scripts/live_smoke.py certifies a configuration whose generation
    deployment is missing, which is the exact opposite of what a preflight is for.
    """
    post = _Fails(404)
    monkeypatch.setattr("mai.client.requests.post", post)
    client = MAIClient(
        Config(
            image_endpoint=ENDPOINT,
            image_api_key="k",
            image_gen_deployment="MAI-Image-2.5-Flash",
            image_edit_deployment="MAI-Image-2.5",
            execution_mode="strict",
            auth_mode="key",
        )
    )
    with pytest.raises(requests.HTTPError):
        client.generate_image("a red circle", 768, 768)
    assert post.models == ["MAI-Image-2.5-Flash"], (
        f"strict mode retried on another deployment: {post.models}"
    )


def test_demo_mode_still_swaps_because_a_running_demo_is_the_point(monkeypatch):
    post = _Fails(404)
    monkeypatch.setattr("mai.client.requests.post", post)
    client = MAIClient(
        Config(
            image_endpoint=ENDPOINT,
            image_api_key="k",
            image_gen_deployment="MAI-Image-2.5-Flash",
            image_edit_deployment="MAI-Image-2.5",
            auth_mode="key",
        )
    )
    result = client.generate_image("a red circle", 768, 768)
    assert post.models == ["MAI-Image-2.5-Flash", "MAI-Image-2.5"]
    assert result.source == "fallback"


def test_the_size_rung_survives_in_strict_mode(monkeypatch):
    """Retrying at 768x768 corrects the request; it does not change the target."""
    post = _Fails(413)
    monkeypatch.setattr("mai.client.requests.post", post)
    client = MAIClient(
        Config(
            image_endpoint=ENDPOINT,
            image_api_key="k",
            execution_mode="strict",
            auth_mode="key",
        )
    )
    with pytest.raises(requests.HTTPError):
        client.generate_image("a red circle", 1024, 1024)
    assert len(post.models) == 2  # 1024 then 768, same deployment both times


def test_a_result_reports_which_deployment_was_asked_for(monkeypatch):
    """live_smoke compares these two, so a substitution can never read as a pass."""
    monkeypatch.setattr("mai.client.requests.post", _Fails(500))
    client = MAIClient(
        Config(image_endpoint=ENDPOINT, image_api_key="k", auth_mode="key"),
    )
    result = client.generate_image("a red circle", 768, 768)
    assert result.meta["requested_model"] == result.meta["model"]


# ── credentials never travel over plaintext ──────────────────────────────────
@pytest.mark.parametrize(
    "url",
    [
        "http://example.services.ai.azure.com/mai/v1/chat/completions",
        "example.services.ai.azure.com/mai/v1/chat/completions",
        "ftp://example.services.ai.azure.com",
    ],
)
def test_non_https_endpoints_are_refused(url):
    with pytest.raises(ValueError, match="non-HTTPS"):
        _require_https(url)


def test_https_is_accepted_case_insensitively():
    assert _require_https("HTTPS://example.com/x") == "HTTPS://example.com/x"


def test_a_plaintext_endpoint_never_reaches_the_network(monkeypatch):
    post = Mock()
    monkeypatch.setattr("mai.client.requests.post", post)
    client = MAIClient(
        Config(
            foundry_endpoint="http://example.services.ai.azure.com",
            foundry_api_key="k",
            auth_mode="key",
        )
    )
    with pytest.raises(ValueError, match="non-HTTPS"):
        client.chat_completion([{"role": "user", "content": "hi"}])
    post.assert_not_called()


# ── a file that is not an image fails cleanly ────────────────────────────────
def test_a_real_png_is_detected_despite_a_useless_content_type():
    assert _validate_image(_png(), "application/octet-stream") == "image/png"


def test_bytes_that_are_not_an_image_raise_instead_of_crashing():
    """Previously this reached PIL inside the fallback and escaped as UnidentifiedImageError."""
    with pytest.raises(ValueError, match="Unsupported image format"):
        _validate_image(b"definitely not a picture", "image/png")


def test_an_empty_upload_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        _validate_image(b"", "image/png")


def test_edit_image_rejects_a_malformed_upload_without_reaching_the_service(monkeypatch):
    post = Mock()
    monkeypatch.setattr("mai.client.requests.post", post)
    client = MAIClient(Config(image_endpoint=ENDPOINT, image_api_key="k", auth_mode="key"))
    with pytest.raises(ValueError, match="Unsupported image format"):
        client.edit_image(b"not-an-image", "make it blue", mime="image/png")
    post.assert_not_called()


def test_a_lying_content_type_does_not_decide_the_upload(monkeypatch):
    """The browser said JPEG; the bytes say PNG. The bytes win."""
    captured = {}

    def post(url, **kwargs):
        captured.update(kwargs["files"])
        raise _http_error(500)

    monkeypatch.setattr("mai.client.requests.post", post)
    client = MAIClient(Config(image_endpoint=ENDPOINT, image_api_key="k", auth_mode="key"))
    client.edit_image(_png(), "make it blue", mime="image/jpeg")
    assert captured["image"][2] == "image/png"
