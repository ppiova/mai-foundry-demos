from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from demos.multimodal_campaign import Campaign, _parse_json, generate_brief
from demos.thinking_agent import CloudEstate, execute_tool_call, run_agent
from mai.client import MAIClient, audio_extension_for_mime
from mai.config import Config


def test_service_specific_timeouts_are_independent():
    cfg = Config(
        thinking_connect_timeout=1,
        thinking_read_timeout=301,
        image_connect_timeout=2,
        image_read_timeout=102,
        transcribe_connect_timeout=3,
        transcribe_read_timeout=203,
        voice_connect_timeout=4,
        voice_read_timeout=94,
    )
    assert cfg.thinking_timeout == (1, 301)
    assert cfg.image_timeout == (2, 102)
    assert cfg.transcribe_timeout == (3, 203)
    assert cfg.voice_timeout == (4, 94)


def test_invalid_execution_mode_is_rejected():
    with pytest.raises(ValueError, match="demo.*strict"):
        Config(execution_mode="sometimes")


def test_execution_mode_is_case_insensitive():
    cfg = Config(execution_mode=" STRICT ")
    assert cfg.execution_mode == "strict"
    assert cfg.strict


def test_image_only_configuration_counts_as_a_live_service():
    cfg = Config(image_endpoint="https://image.example", image_api_key="key")
    assert cfg.image_ready
    assert cfg.any_service_ready
    assert not cfg.foundry_ready


def test_empty_and_unsupported_audio_are_rejected():
    client = MAIClient(Config())
    with pytest.raises(ValueError, match="empty"):
        client.transcribe(b"", filename="clip.wav", mime="audio/wav")
    with pytest.raises(ValueError, match="Unsupported"):
        client.transcribe(b"bytes", filename="clip.ogg", mime="audio/ogg")


class _TranscriptResponse:
    content = b"mp3 bytes"

    def raise_for_status(self):
        return None

    def json(self):
        return {"combinedPhrases": [{"text": "recognized"}]}


def test_uploaded_audio_mime_is_preserved(monkeypatch):
    post = Mock(return_value=_TranscriptResponse())
    monkeypatch.setattr("mai.client.requests.post", post)
    client = MAIClient(
        Config(speech_endpoint="https://speech.example", speech_key="key", speech_region="eastus")
    )
    result = client.transcribe(b"mp3 bytes", filename="voice.mp3", mime="audio/mpeg")
    assert result.data == "recognized"
    assert post.call_args.kwargs["files"]["audio"][2] == "audio/mpeg"
    assert result.meta["mime"] == "audio/mpeg"


def test_generic_audio_mime_falls_back_to_supported_extension_mime(monkeypatch):
    post = Mock(return_value=_TranscriptResponse())
    monkeypatch.setattr("mai.client.requests.post", post)
    client = MAIClient(Config(speech_endpoint="https://speech.example", speech_key="key"))
    result = client.transcribe(
        b"mp3 bytes",
        filename="voice.mp3",
        mime="application/octet-stream",
    )
    assert post.call_args.kwargs["files"]["audio"][2] == "audio/mpeg"
    assert result.meta["mime"] == "audio/mpeg"


@pytest.mark.parametrize(
    ("mime", "extension"),
    [
        ("audio/mpeg", ".mp3"),
        ("audio/mp3", ".mp3"),
        ("audio/wav", ".wav"),
        ("audio/x-wav", ".wav"),
        ("audio/flac", ".flac"),
        ("audio/x-flac", ".flac"),
    ],
)
def test_audio_extension_matches_actual_mime(mime, extension):
    assert audio_extension_for_mime(mime) == extension


def test_voice_mp3_response_uses_audio_mpeg_metadata(monkeypatch):
    monkeypatch.setattr("mai.client.requests.post", Mock(return_value=_TranscriptResponse()))
    client = MAIClient(Config(speech_key="key", speech_region="eastus"))
    result = client.synthesize("hello")
    assert result.source == "live"
    assert result.data == b"mp3 bytes"
    assert result.meta["mime"] == "audio/mpeg"
    assert "sample" + audio_extension_for_mime(result.meta["mime"]) == "sample.mp3"


def test_fallback_wave_audio_is_named_wav(monkeypatch):
    monkeypatch.setattr("mai.client.fallback.synthesize", Mock(return_value=(b"wav", "audio/wav")))
    result = MAIClient(Config()).synthesize("hello")
    assert result.meta["mime"] == "audio/wav"
    assert "sample" + audio_extension_for_mime(result.meta["mime"]) == "sample.wav"


def test_transcript_parse_failure_raises_in_strict_mode(monkeypatch):
    post = Mock(return_value=_TranscriptResponse())
    post.return_value.json = Mock(return_value={"requestId": "private-value"})
    monkeypatch.setattr("mai.client.requests.post", post)
    client = MAIClient(
        Config(
            speech_endpoint="https://speech.example",
            speech_key="key",
            execution_mode="strict",
        )
    )
    with pytest.raises(ValueError, match="recognizable transcript") as excinfo:
        client.transcribe(b"wav bytes", filename="voice.wav", mime="audio/wav")
    assert "private-value" not in str(excinfo.value)


def test_campaign_schema_requires_nonempty_strings():
    complete = {
        "campaign_name": "Launch",
        "tagline": "Go",
        "creative_brief": "A brief",
        "hero_image_prompt": "A prompt",
        "voiceover_script": "A script",
    }
    assert isinstance(_parse_json(json.dumps(complete)), Campaign)
    complete["tagline"] = ""
    with pytest.raises(ValueError, match="tagline"):
        _parse_json(json.dumps(complete))


def test_campaign_uses_reasoning_safe_completion_budget(monkeypatch):
    payload = {
        "campaign_name": "Launch",
        "tagline": "Go",
        "creative_brief": "A brief",
        "hero_image_prompt": "A prompt",
        "voiceover_script": "A script",
    }
    client = MAIClient(Config(foundry_endpoint="https://foundry.example", foundry_api_key="key"))
    completion = Mock(return_value={"choices": [{"message": {"content": json.dumps(payload)}}]})
    monkeypatch.setattr(client, "chat_completion", completion)
    campaign, source, error = generate_brief(client, "Launch")
    assert campaign.campaign_name == "Launch"
    assert source == "live" and error is None
    assert completion.call_args.kwargs["max_completion_tokens"] == 8192


def test_unknown_and_malformed_tools_are_not_dispatched(monkeypatch):
    estate = CloudEstate()
    dispatch = Mock(side_effect=AssertionError("must not execute"))
    monkeypatch.setattr(estate, "dispatch", dispatch)

    _, _, unknown = execute_tool_call(
        estate, {"id": "call-1", "function": {"name": "delete_everything", "arguments": "{}"}}
    )
    _, _, malformed = execute_tool_call(
        estate, {"id": "call-2", "function": {"name": "get_region_capacity", "arguments": "{"}}
    )

    assert "not executed" in unknown["error"]
    assert "Malformed" in malformed["error"]
    dispatch.assert_not_called()


def test_missing_tool_call_id_is_a_controlled_error(monkeypatch):
    estate = CloudEstate()
    dispatch = Mock(side_effect=AssertionError("must not execute"))
    monkeypatch.setattr(estate, "dispatch", dispatch)
    name, args, result = execute_tool_call(
        estate, {"function": {"name": "get_region_capacity", "arguments": '{"region":"eastus"}'}}
    )
    assert name == "invalid_tool_call"
    assert args == {}
    assert "missing non-empty id" in result["error"]
    dispatch.assert_not_called()


def test_strict_mode_never_uses_agent_or_campaign_fallbacks():
    client = MAIClient(Config(execution_mode="strict"))
    with pytest.raises(RuntimeError, match="not configured"):
        run_agent(client)
    with pytest.raises(RuntimeError, match="not configured"):
        generate_brief(client, "Launch a product")
