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


def test_full_smoke_checks_every_service_and_uses_audio_metadata():
    client = Mock()
    client.cfg = _full_config()
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
    client.generate_image.return_value = MAIResult("live", b"png")
    client.synthesize.return_value = MAIResult("live", b"mp3", {"mime": "audio/mpeg"})
    client.transcribe.return_value = MAIResult("live", "transcript")

    assert missing_services(client.cfg) == []
    assert main(client=client) == 0
    assert client.chat_completion.call_args.kwargs["max_completion_tokens"] == 4096
    assert client.chat_completion_stream.call_args.kwargs["max_completion_tokens"] == 4096
    assert client.transcribe.call_args.kwargs["filename"] == "smoke.mp3"
    assert client.transcribe.call_args.kwargs["mime"] == "audio/mpeg"
