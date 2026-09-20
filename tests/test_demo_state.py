"""Exercise speech UI transitions with real widgets and mocked, offline services."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
import streamlit as st
from PIL import Image
from streamlit.testing.v1 import AppTest

from demos import multimodal_campaign
from demos._notices import SYNTHETIC_VOICE
from mai import MAIClient, MAIResult
from mai.config import Config
from mai.fallback import ENTITIES

APP = str(Path(__file__).resolve().parent.parent / "app.py")
UPLOAD = ("recording.flac", b"uploaded audio", "audio/flac")


@pytest.fixture
def ui(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("UI regressions must never access the network")

    monkeypatch.setattr("requests.sessions.Session.request", no_network)
    client = Mock(spec=MAIClient)
    client.cfg = Config()
    client.auth_fallback = None
    client.synthesize.return_value = MAIResult(
        "fallback", b"generated audio", meta={"mime": "audio/wav"}
    )
    client.transcribe.return_value = MAIResult("fallback", "Recognized brief.")
    client.generate_image.return_value = MAIResult("fallback", Image.new("RGB", (2, 2)))
    campaign = multimodal_campaign.Campaign("Launch", "Go", "Brief", "Image prompt", "Voice-over")
    brief = Mock(return_value=(campaign, "fallback", None))
    monkeypatch.setattr(multimodal_campaign, "generate_brief", brief)
    monkeypatch.setattr("mai.MAIClient", Mock(return_value=client))
    st.cache_resource.clear()
    try:
        app = AppTest.from_file(APP, default_timeout=30).run()
        assert app.exception == []
        yield app, client, brief
        assert app.exception == []
    finally:
        st.cache_resource.clear()


def _tab(app, prefix):
    return app.tabs[2 if prefix == "tr" else 3]


def _generate(app, prefix):
    return app.button(key="tr_gen" if prefix == "tr" else "mm_tts").click().run()


def _run(app, prefix):
    return app.button(key=f"{prefix}_run").click().run()


def _assert_transcribed(client, audio, filename, mime, count):
    assert client.transcribe.call_count == count
    for call in client.transcribe.call_args_list:
        assert call.args == (audio,)
        assert call.kwargs["filename"] == filename
        assert call.kwargs["mime"] == mime


@pytest.mark.parametrize("prefix", ["tr", "mm"])
def test_tts_and_upload_remain_independently_selectable_across_reruns(ui, prefix):
    app, client, _ = ui
    app.file_uploader(key=f"{prefix}_up").set_value(UPLOAD).run()
    assert app.radio(key=f"{prefix}_source").value == "upload"
    assert SYNTHETIC_VOICE not in [item.value for item in _tab(app, prefix).caption]

    _generate(app, prefix)
    app.run()
    assert app.radio(key=f"{prefix}_source").value == "tts"
    assert SYNTHETIC_VOICE in [item.value for item in _tab(app, prefix).caption]
    stem = "sample" if prefix == "tr" else "brief"
    count = 2 if prefix == "tr" else 1
    _run(app, prefix)
    _assert_transcribed(client, b"generated audio", stem + ".wav", "audio/wav", count)

    client.transcribe.reset_mock()
    app.radio(key=f"{prefix}_source").set_value("upload").run()
    app.run()
    _run(app, prefix)
    _assert_transcribed(client, UPLOAD[1], UPLOAD[0], UPLOAD[2], count)

    client.transcribe.reset_mock()
    app.radio(key=f"{prefix}_source").set_value("tts").run()
    _run(app, prefix)
    _assert_transcribed(client, b"generated audio", stem + ".wav", "audio/wav", count)


@pytest.mark.parametrize("prefix", ["tr", "mm"])
def test_clearing_active_upload_never_reuses_upload_or_old_tts(ui, prefix):
    app, client, brief = ui
    _generate(app, prefix)
    app.file_uploader(key=f"{prefix}_up").set_value(UPLOAD).run()
    if prefix == "mm":
        app.text_area(key="mm_brief").set_value("A completely new typed brief.").run()
    app.file_uploader(key=f"{prefix}_up").clear().run()
    assert app.session_state[f"{prefix}_upload_audio"] is None
    assert len(_tab(app, prefix).get("audio")) == 0
    _run(app, prefix)
    client.transcribe.assert_not_called()
    if prefix == "mm":
        assert app.radio(key="mm_source").value == "text"
        brief.assert_called_once_with(client, "A completely new typed brief.")
    else:
        assert app.radio(key="tr_source").value == "upload"
        assert "non-empty audio" in _tab(app, prefix).error[0].value


@pytest.mark.parametrize("prefix", ["tr", "mm"])
def test_clearing_inactive_upload_preserves_explicit_tts_choice(ui, prefix):
    app, client, _ = ui
    app.file_uploader(key=f"{prefix}_up").set_value(UPLOAD).run()
    _generate(app, prefix)
    app.file_uploader(key=f"{prefix}_up").clear().run()
    assert app.radio(key=f"{prefix}_source").value == "tts"
    _run(app, prefix)
    stem = "sample" if prefix == "tr" else "brief"
    _assert_transcribed(
        client, b"generated audio", stem + ".wav", "audio/wav", 2 if prefix == "tr" else 1
    )


@pytest.mark.parametrize("prefix", ["tr", "mm"])
def test_replacing_upload_activates_new_bytes_and_preserves_metadata(ui, prefix):
    app, client, _ = ui
    app.file_uploader(key=f"{prefix}_up").set_value(UPLOAD).run()
    _generate(app, prefix)
    app.file_uploader(key=f"{prefix}_up").set_value(
        ("new.mp3", b"replacement audio", "audio/mpeg")
    ).run()
    # Reading a file elsewhere must not make the next UI run see an empty upload.
    app.session_state[f"{prefix}_up"].read()
    app.run()
    assert app.radio(key=f"{prefix}_source").value == "upload"
    _run(app, prefix)
    _assert_transcribed(
        client, b"replacement audio", "new.mp3", "audio/mpeg", 2 if prefix == "tr" else 1
    )


@pytest.mark.parametrize("prefix", ["tr", "mm"])
def test_reuploading_same_file_is_a_new_selection_not_a_rerun(ui, prefix):
    app, client, _ = ui
    app.file_uploader(key=f"{prefix}_up").set_value(UPLOAD).run()
    _generate(app, prefix)
    app.file_uploader(key=f"{prefix}_up").set_value(UPLOAD).run()
    assert app.radio(key=f"{prefix}_source").value == "upload"
    _run(app, prefix)
    _assert_transcribed(client, UPLOAD[1], UPLOAD[0], UPLOAD[2], 2 if prefix == "tr" else 1)


@pytest.mark.parametrize("prefix", ["tr", "mm"])
@pytest.mark.parametrize("empty_audio", [None, b""])
def test_empty_tts_replacement_clears_old_audio_and_does_not_use_upload(ui, prefix, empty_audio):
    app, client, brief = ui
    _generate(app, prefix)
    app.file_uploader(key=f"{prefix}_up").set_value(UPLOAD).run()
    client.synthesize.return_value = MAIResult("fallback", empty_audio)
    _generate(app, prefix)
    assert app.session_state[f"{prefix}_tts_audio"] is None
    assert app.radio(key=f"{prefix}_source").value == "tts"
    assert _tab(app, prefix).warning
    assert len(_tab(app, prefix).get("audio")) == 0
    _run(app, prefix)
    client.transcribe.assert_not_called()
    brief.assert_not_called()
    assert "non-empty audio" in _tab(app, prefix).error[0].value


@pytest.mark.parametrize("prefix", ["tr", "mm"])
def test_empty_upload_blocks_selected_audio_path(ui, prefix):
    app, client, brief = ui
    app.file_uploader(key=f"{prefix}_up").set_value(("empty.wav", b"", "audio/wav")).run()
    assert app.radio(key=f"{prefix}_source").value == "upload"
    _run(app, prefix)
    client.transcribe.assert_not_called()
    brief.assert_not_called()
    assert "non-empty audio" in _tab(app, prefix).error[0].value


def test_campaign_can_use_current_text_while_upload_is_still_present(ui):
    app, client, brief = ui
    app.file_uploader(key="mm_up").set_value(UPLOAD).run()
    app.radio(key="mm_source").set_value("text").run()
    app.text_area(key="mm_brief").set_value("Launch a reusable notebook.").run()
    app.run()
    _run(app, "mm")
    client.transcribe.assert_not_called()
    brief.assert_called_once_with(client, "Launch a reusable notebook.")


def test_editing_campaign_text_invalidates_generated_speech_until_regenerated(ui):
    app, client, brief = ui
    _generate(app, "mm")
    app.text_area(key="mm_brief").set_value("An updated brief.").run()
    assert app.radio(key="mm_source").value == "text"
    assert app.session_state["mm_tts_audio"] is None
    _run(app, "mm")
    client.transcribe.assert_not_called()
    brief.assert_called_once_with(client, "An updated brief.")

    client.synthesize.reset_mock()
    _generate(app, "mm")
    client.synthesize.assert_called_once_with("An updated brief.", voice="en-US-Ethan:MAI-Voice-2")
    assert app.radio(key="mm_source").value == "tts"


@pytest.mark.parametrize(
    ("sources", "status"),
    [
        (("live", "live"), "🟢 LIVE"),
        (("fallback", "fallback"), "🟡 FALLBACK (simulated)"),
        (("live", "fallback"), "🟠 MIXED — LIVE + FALLBACK"),
        (("fallback", "live"), "🟠 MIXED — LIVE + FALLBACK"),
    ],
)
def test_transcribe_provenance_is_per_column_and_aggregate_matches_both_results(
    ui, sources, status
):
    app, client, _ = ui
    client.transcribe.side_effect = [
        MAIResult(
            source,
            f"Transcript {i}: KEDA",
            elapsed=i + 0.5,
            error=f"failure-{i}" if source == "fallback" else None,
        )
        for i, source in enumerate(sources)
    ]
    app.file_uploader(key="tr_up").set_value(UPLOAD).run()
    app.toggle(key="tr_verbatim").set_value(True).run()
    _run(app, "tr")
    tab = _tab(app, "tr")
    assert f"**Comparison: {status}**" in [item.value for item in tab.markdown]
    for i, (column, source) in enumerate(zip(tab.columns[-2:], sources, strict=True)):
        badge = "🟢 LIVE" if source == "live" else "🟡 FALLBACK"
        assert f"**{badge}** · {i + 0.5:.1f}s" in [item.value for item in column.markdown]
        assert len(column.info) == (source == "fallback")
        assert len(column.warning) == (source == "fallback")
        if source == "fallback":
            assert "canned" in column.info[0].value
            assert "not measured from this audio" in column.info[0].value
            assert f"failure-{i}" in column.warning[0].value
    assert len(tab.success) == (sources == ("live", "live"))
    mixed = sources[0] != sources[1]
    assert any("Mixed provenance" in item.value for item in tab.warning) == mixed
    assert any("always verbatim; this has no effect live" in item.value for item in tab.caption)
    for call in client.transcribe.call_args_list:
        assert call.kwargs["verbatim"] is True
        assert call.kwargs["locales"] == ["en"]
    assert client.transcribe.call_args_list[0].kwargs["phrases"] is None
    assert client.transcribe.call_args_list[1].kwargs["phrases"] == ENTITIES
