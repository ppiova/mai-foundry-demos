from __future__ import annotations

from unittest.mock import Mock

import pytest

from mai.client import MAIResult
from mai.config import Config
from scripts.live_smoke import main, missing_services


def _full_config(**overrides) -> Config:
    values = {
        "foundry_endpoint": "https://foundry.example",
        "foundry_api_key": "key",
        "image_endpoint": "https://image.example",
        "image_api_key": "key",
        "speech_endpoint": "https://speech.example",
        "speech_key": "key",
        "speech_region": "eastus",
        "execution_mode": "strict",
    }
    values.update(overrides)
    return Config(**values)


@pytest.mark.parametrize(
    ("overrides", "missing"),
    [
        ({"foundry_api_key": ""}, "Thinking-1"),
        ({"image_api_key": ""}, "Image"),
        ({"speech_region": ""}, "Voice-2"),
        ({"speech_endpoint": ""}, "Transcribe-1.5"),
    ],
)
def test_full_smoke_fails_before_network_when_a_service_is_missing(overrides, missing):
    client = Mock()
    client.cfg = _full_config(**overrides)
    assert missing in missing_services(client.cfg)
    assert main(client=client) == 1
    client.chat_completion.assert_not_called()


def _passing_client(**overrides):
    client = Mock()
    client.cfg = _full_config(**overrides)
    client.chat_completion.return_value = {"choices": [{"message": {"content": "OK"}}]}
    client.chat_completion_stream.return_value = [
        (
            "message",
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "get_region_capacity", "arguments": "{}"},
                    }
                ],
            },
        )
    ]
    client.generate_image.return_value = MAIResult(
        "live",
        b"png",
        {
            "model": client.cfg.image_gen_deployment,
            "requested_model": client.cfg.image_gen_deployment,
        },
    )
    client.synthesize.return_value = MAIResult("live", b"mp3", {"mime": "audio/mpeg"})
    client.transcribe.return_value = MAIResult("live", "transcript")
    return client


def test_full_smoke_checks_every_service_and_uses_audio_metadata():
    client = _passing_client()
    assert missing_services(client.cfg) == []
    assert main(client=client) == 0
    assert client.chat_completion.call_args.kwargs["max_completion_tokens"] == 4096
    assert client.chat_completion_stream.call_args.kwargs["max_completion_tokens"] == 4096
    assert client.transcribe.call_args.kwargs["filename"] == "smoke.mp3"
    assert client.transcribe.call_args.kwargs["mime"] == "audio/mpeg"


def test_partial_smoke_fails_if_configured_transcribe_is_not_exercised(capsys):
    client = _passing_client(speech_region="")
    assert client.cfg.transcribe_ready
    assert not client.cfg.speech_ready
    assert main(client=client, allow_partial=True) == 1
    assert "[FAIL] Transcribe-1.5" in capsys.readouterr().out
    client.transcribe.assert_not_called()


def test_partial_smoke_passes_when_all_configured_services_are_exercised():
    client = _passing_client(image_endpoint="", speech_endpoint="", speech_key="")
    assert main(client=client, allow_partial=True) == 0
    client.generate_image.assert_not_called()
    client.synthesize.assert_not_called()
    client.transcribe.assert_not_called()


def test_partial_smoke_with_no_services_is_not_a_pass():
    client = _passing_client(
        foundry_endpoint="", image_endpoint="", speech_endpoint="", speech_key=""
    )
    assert main(client=client, allow_partial=True) == 1


@pytest.mark.parametrize(
    ("method", "label"),
    [
        ("generate_image", "Image generation"),
        ("synthesize", "Voice-2 synthesis"),
        ("transcribe", "Transcribe-1.5"),
    ],
)
def test_strict_failures_are_reported_instead_of_aborting_the_report(method, label, capsys):
    client = _passing_client()
    getattr(client, method).side_effect = RuntimeError("service unavailable")
    assert main(client=client) == 1
    output = capsys.readouterr().out
    assert f"[FAIL] {label} service unavailable" in output
    assert "FAILED:" in output
    client.synthesize.assert_called_once()


def test_fallback_tts_is_not_used_as_live_round_trip_audio(capsys):
    client = _passing_client(execution_mode="demo")
    client.synthesize.return_value = MAIResult("fallback", b"wav", {"mime": "audio/wav"})
    assert main(client=client) == 1
    output = capsys.readouterr().out
    assert "[FAIL] Voice-2 synthesis" in output
    assert "[FAIL] Transcribe-1.5" in output
    client.transcribe.assert_not_called()


@pytest.mark.parametrize(
    "meta",
    [
        {},
        {"model": "other", "requested_model": "other"},
        {"model": "other", "requested_model": "MAI-Image-2.5-Flash"},
    ],
)
def test_image_success_requires_the_configured_deployment(meta, capsys):
    client = _passing_client()
    client.generate_image.return_value = MAIResult("live", b"png", meta)
    assert main(client=client) == 1
    assert "[FAIL] Image generation" in capsys.readouterr().out
