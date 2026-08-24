"""Offline smoke tests — everything runs in FALLBACK mode (see conftest.py).

They exercise the deterministic fallbacks and pure logic so the suite needs no
credentials and no network. The LIVE paths are thin HTTP wrappers over the same
result types, verified separately against a real deployment.
"""

import importlib
import re

import pytest

from mai import MAIClient, build_ssml, get_config
from mai.fallback import ENTITIES

MODULES = [
    "mai",
    "mai.config",
    "mai.client",
    "mai.ssml",
    "mai.fallback",
    "demos.thinking_agent",
    "demos.image_edit",
    "demos.transcribe_bias",
    "demos.voice_personalities",
    "demos.image_speed",
    "demos.multimodal_campaign",
]

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture(scope="session")
def client():
    return MAIClient()


def test_all_modules_import():
    for module in MODULES:
        importlib.import_module(module)


def test_config_is_fallback():
    cfg = get_config()
    assert cfg.foundry_ready is False
    assert cfg.image_ready is False
    assert cfg.speech_ready is False


def test_base_image_builds():
    from assets.build_assets import main as build

    path = build()
    assert path.exists() and path.stat().st_size > 1000


def test_thinking_fallback_plan(client):
    from demos import thinking_agent as ta

    run = ta.run_agent(client)
    assert run.source == "fallback"
    pct = float(re.search(r"([0-9]+\.[0-9])% monthly cost reduction", run.plan_markdown).group(1))
    assert pct >= 20.0
    # The plan must not leave any region above the capacity ceiling.
    assert "⚠️" not in run.plan_markdown.split("Tradeoffs")[0]


def test_estate_tools_enforce_constraints():
    from demos.thinking_agent import CloudEstate

    estate = CloudEstate()
    assert estate.get_region_capacity("eastus")["utilization_pct"] > 70
    assert estate.calculate_migration_cost(["catalog-svc"], "southindia")["monthly_savings"] > 0

    tier1 = estate.calculate_migration_cost(["payments-core"], "southindia")
    assert tier1["monthly_savings"] == 0
    assert tier1["errors"]


def test_image_fallbacks_return_png(client):
    from demos.image_edit import BASE_IMAGE, ensure_base_image

    ensure_base_image()
    edited = client.edit_image(BASE_IMAGE.read_bytes(), "make it sunset")
    assert edited.source == "fallback"
    assert edited.data[:8] == PNG_MAGIC

    generated = client.generate_image("a red mug on a white background")
    assert generated.data[:8] == PNG_MAGIC


def test_transcribe_entity_biasing(client):
    baseline = client.transcribe(b"", phrases=None)
    biased = client.transcribe(b"", phrases=ENTITIES)
    assert baseline.data != biased.data
    assert "Fabrikam XQ-17" in biased.data
    assert "Fabrikam XQ-17" not in baseline.data


def test_ssml_style_resolution():
    ssml_es, note_es = build_ssml("hola", voice="es-ES-Marta:MAI-Voice-2", style="empathy")
    assert "style='empathy'" in ssml_es and note_es is None

    ssml_en, note_en = build_ssml("hi", voice="en-US-Ethan:MAI-Voice-2", style="empathy")
    assert "empathy" not in ssml_en and note_en is not None


def test_finale_brief_fallback(client):
    from demos.multimodal_campaign import generate_brief

    brief, source, _ = generate_brief(client, "Launch a smart backpack.")
    assert source == "fallback"
    assert all(
        k in brief for k in ("campaign_name", "tagline", "hero_image_prompt", "voiceover_script")
    )
