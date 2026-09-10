"""The Streamlit entry point renders without raising.

app.py is what a presenter actually runs, and until now nothing imported it. The
sidebar in particular reports service readiness and authentication, and it is the
first thing on screen, so a regression there is a regression in front of an
audience.

These run in FALLBACK with no credentials (conftest clears the environment), so
they exercise the offline path only. That is deliberate: a test that reached a
real service would not run in CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mai.config import Config

pytest.importorskip("streamlit.testing.v1", reason="Streamlit testing API not available")

from streamlit.testing.v1 import AppTest  # noqa: E402

TIMEOUT = 30

# AppTest resolves a relative path against the calling file, which would look for
# tests/app.py. Point at the real entry point.
APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _run() -> AppTest:
    app = AppTest.from_file(APP, default_timeout=TIMEOUT)
    app.run()
    return app


def test_the_app_renders_without_raising():
    app = _run()
    assert app.exception == []


def test_every_demo_tab_is_present():
    app = _run()
    labels = [label for tab in app.tabs for label in ([tab.label] if tab.label else [])]
    assert len(labels) == 7, labels
    for expected in ("Thinking", "Image-2.5", "Transcribe", "Finale", "Voice-2", "Image-Flash"):
        assert any(expected in label for label in labels), (expected, labels)


def test_unconfigured_run_says_fallback_and_never_claims_live():
    """The regression this file exists for: a green LIVE row next to a missing credential."""
    app = _run()
    body = " ".join(str(el.value) for el in app.sidebar.markdown) + " ".join(
        str(el.value) for el in app.sidebar.caption
    )
    assert "FALLBACK" in body
    assert "configured for LIVE" not in body


def test_the_offline_hint_matches_the_authentication_mode():
    """Telling someone to add keys when the app is keyless sends them the wrong way."""
    app = _run()
    captions = " ".join(str(el.value) for el in app.sidebar.caption)
    info = " ".join(str(el.value) for el in app.sidebar.info)
    hint = captions + info
    if Config().keyless_enabled:
        assert "az login" in hint
    else:
        assert "keys" in hint
