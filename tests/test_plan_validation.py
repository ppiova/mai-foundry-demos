"""Tests for the deterministic plan validator.

The agent demo's whole point is "the model proposes, deterministic code decides".
These tests cover the failure modes a per-proposal tool call cannot catch —
above all *cumulative* capacity, where two individually-valid moves overflow a
region once combined.
"""

from __future__ import annotations

import json

from demos.thinking_agent import (
    CloudEstate,
    MigrationPlan,
    _finish_live,
    extract_structured_plan,
    fallback_plan,
    validate_plan,
)


def _estate() -> CloudEstate:
    return CloudEstate()


def test_fallback_plan_passes_its_own_validation():
    """The deterministic planner must satisfy the constraints it plans against."""
    estate = _estate()
    run = fallback_plan(estate)
    assert run.source == "fallback"
    assert "cost reduction" in run.plan_markdown
    # The offline planner is held to the same bar as the model: same validator.
    assert run.validation is not None, "fallback plan should be validated too"
    assert run.validation.ok, run.validation.violations
    assert run.validation.saved_pct >= 20
    assert run.validation.over_ceiling() == 0


def test_tier1_move_is_rejected():
    estate = _estate()
    result = validate_plan(estate, [{"app": "payments-core", "target_region": "southindia"}], [])
    assert not result.ok
    assert any("Tier-1" in v for v in result.violations)


def test_tier1_decommission_is_rejected():
    result = validate_plan(_estate(), [], ["payments-core"])
    assert not result.ok
    assert any("Tier-1" in v for v in result.violations)


def test_active_workload_decommission_is_rejected():
    result = validate_plan(_estate(), [], ["catalog-svc"])
    assert not result.ok
    assert any("active" in v and "idle" in v for v in result.violations)


def test_same_region_move_is_rejected():
    result = validate_plan(_estate(), [{"app": "order-api", "target_region": "eastus"}], [])
    assert not result.ok
    assert any("same-region" in v for v in result.violations)


def test_unknown_app_and_region_are_rejected():
    estate = _estate()
    result = validate_plan(
        estate,
        [
            {"app": "does-not-exist", "target_region": "southindia"},
            {"app": "order-api", "target_region": "mars"},
        ],
        [],
    )
    assert not result.ok
    assert any("Unknown application" in v for v in result.violations)
    assert any("Unknown target region" in v for v in result.violations)


def test_duplicate_app_is_rejected():
    estate = _estate()
    result = validate_plan(
        estate,
        [{"app": "order-api", "target_region": "southindia"}],
        ["order-api"],
    )
    assert not result.ok
    assert any("more than once" in v for v in result.violations)


def test_cumulative_capacity_breach_is_caught():
    """Individually fine, collectively over the ceiling — the key failure mode."""
    estate = _estate()
    target = "uaenorth"
    ceiling_units = estate.ceiling_units(target)
    used = estate.used_units(target)

    # Greedily pile movable apps into one small region until it must overflow.
    moves, projected = [], used
    for name, app in estate.apps.items():
        if app["tier"] == 1 or not app["can_migrate"] or app["region"] == target:
            continue
        moves.append({"app": name, "target_region": target})
        projected += app["capacity_units"]
        if projected > ceiling_units:
            break

    assert projected > ceiling_units, "test setup should exceed the ceiling"
    result = validate_plan(estate, moves, [])
    assert not result.ok
    assert any("above the" in v and target in v for v in result.violations)
    assert result.over_ceiling(estate.ceiling) >= 1


def test_dangling_dependency_is_caught():
    estate = _estate()
    # Isolate the dependency check from the separate idle-candidate guard.
    estate.apps["catalog-svc"]["idle_candidate"] = True
    dependents = [n for n, a in estate.apps.items() if "catalog-svc" in a.get("dependencies", [])]
    assert dependents, "fixture should have apps depending on catalog-svc"
    result = validate_plan(estate, [], ["catalog-svc"])
    assert any("depends on decommissioned" in v for v in result.violations)


def test_risks_require_a_list_of_nonempty_strings():
    estate = _estate()
    plan = fallback_plan(estate).proposal
    moves, decommissions = plan.validation_inputs()

    string_result = validate_plan(estate, moves, decommissions, risks="single risk")
    assert not string_result.ok
    assert string_result.risks == ()
    assert any("'risks' must be a list" in v for v in string_result.violations)

    entries_result = validate_plan(estate, moves, decommissions, risks=["", 4, " valid "])
    assert not entries_result.ok
    assert entries_result.risks == ("valid",)
    assert sum("non-empty strings" in v for v in entries_result.violations) == 2


def test_valid_risks_are_normalized_without_character_iteration():
    estate = _estate()
    plan = fallback_plan(estate).proposal
    moves, decommissions = plan.validation_inputs()
    result = validate_plan(estate, moves, decommissions, risks=["  sequence carefully  "])
    assert result.ok, result.violations
    assert result.risks == ("sequence carefully",)


def test_savings_shortfall_is_reported():
    estate = _estate()
    result = validate_plan(estate, [], ["dev-sandbox"])  # ~2.8% only
    assert not result.ok
    assert any("fall short" in v for v in result.violations)
    assert 0 < result.saved_pct < 20


def test_valid_plan_reports_recomputed_numbers():
    """A plan that meets every constraint validates, with numbers derived from data."""
    estate = _estate()
    moves = [
        {"app": "catalog-svc", "target_region": "southindia"},
        {"app": "notification-hub", "target_region": "southindia"},
        {"app": "billing-reports", "target_region": "southindia"},
        {"app": "order-api", "target_region": "southindia"},
        {"app": "recommendation-engine", "target_region": "southindia"},
        {"app": "data-lake-etl", "target_region": "southindia"},
        {"app": "inventory-sync", "target_region": "southindia"},
        {"app": "ml-training-pool", "target_region": "uaenorth"},
        {"app": "media-transcode", "target_region": "uaenorth"},
    ]
    decommissions = ["dev-sandbox", "staging-cluster", "log-archive"]
    result = validate_plan(estate, moves, decommissions)
    assert result.ok, result.violations
    assert result.saved_pct >= 20
    assert result.moved == len(moves)
    assert result.decommissioned == len(decommissions)
    # Savings are recomputed, never taken from the model's prose.
    assert abs((result.baseline_cost - result.new_cost) - result.saved) < 1e-6
    assert result.over_ceiling(estate.ceiling) == 0


def test_live_markdown_is_rendered_from_typed_validated_data():
    estate = _estate()
    offline = fallback_plan(estate)
    moves, decommissions = offline.proposal.validation_inputs()
    answer = (
        "Claimed total: $1/month and 99.9% saved.\n```json\n"
        + json.dumps({"moves": moves, "decommissions": decommissions})
        + "\n```"
    )
    run = _finish_live(estate, answer, [], 0.0, {})
    assert run.source == "live"
    assert isinstance(run.proposal, MigrationPlan)
    assert "$1/month" not in run.plan_markdown
    assert f"${run.validation.new_cost:,.0f}/month" in run.plan_markdown


# ── structured-plan extraction ──────────────────────────────────────────────────
def test_extract_structured_plan_reads_trailing_json_block():
    text = """Here is the plan.

| App | Move |
|---|---|

```json
{"moves": [{"app": "order-api", "target_region": "southindia"}], "decommissions": ["dev-sandbox"]}
```
"""
    plan = extract_structured_plan(text)
    assert plan["moves"][0]["app"] == "order-api"
    assert plan["decommissions"] == ["dev-sandbox"]


def test_extract_structured_plan_returns_none_without_a_plan():
    assert extract_structured_plan("Just prose, no JSON here.") is None
    assert extract_structured_plan('```json\n{"unrelated": 1}\n```') is None


# ── malformed model output must fail validation, not crash the run ──────────────
def test_malformed_moves_are_reported_not_raised():
    """Model-produced JSON is untrusted: bad shapes become violations, not errors."""
    estate = _estate()
    for bad_moves in ("oops", {"app": "order-api"}, 42):
        result = validate_plan(estate, bad_moves, [])
        assert not result.ok
        assert any("'moves' must be a list" in v for v in result.violations)


def test_non_object_move_entries_are_reported():
    estate = _estate()
    result = validate_plan(estate, ["order-api", None, 7], [])
    assert not result.ok
    assert sum("Move entries must be objects" in v for v in result.violations) == 3


def test_move_without_valid_app_name_is_reported():
    estate = _estate()
    result = validate_plan(estate, [{"target_region": "southindia"}, {"app": 5}], [])
    assert not result.ok
    assert sum("missing a valid 'app' name" in v for v in result.violations) == 2


def test_malformed_decommissions_are_reported_not_raised():
    estate = _estate()
    result = validate_plan(estate, [], "dev-sandbox")
    assert not result.ok
    assert any("'decommissions' must be a list" in v for v in result.violations)

    # A dict entry would be unhashable and blow up a naive lookup.
    result = validate_plan(estate, [], [{"app": "dev-sandbox"}, None])
    assert not result.ok
    assert sum("must be app names" in v for v in result.violations) == 2


def test_over_ceiling_does_not_round_a_breach_away():
    """Utilization is stored unrounded so a 70.04% breach can't display as 70.0%."""
    estate = _estate()
    result = validate_plan(estate, [], [])
    result.utilization = {"eastus": 70.04, "westeurope": 70.0}
    result.ceiling = 70.0
    assert result.over_ceiling() == 1


def test_validation_carries_the_estate_ceiling():
    estate = _estate()
    result = validate_plan(estate, [], [])
    assert result.ceiling == estate.ceiling


def test_non_string_target_region_is_reported_not_raised():
    """`x in dict` hashes x, so a dict/list target would raise TypeError."""
    estate = _estate()
    result = validate_plan(
        estate,
        [
            {"app": "order-api", "target_region": {}},
            {"app": "search-index", "target_region": ["southindia"]},
            {"app": "inventory-sync", "target_region": None},
        ],
        [],
    )
    assert not result.ok
    assert sum("invalid 'target_region'" in v for v in result.violations) == 3


def test_falsy_malformed_plan_is_not_normalised_away():
    """A live proposal with `decommissions: {}` must fail the shape check.

    Reading it with `or []` would turn the malformed value into an empty list and
    let the plan report ok, bypassing the guard entirely.
    """
    from demos.thinking_agent import _finish_live

    estate = _estate()
    answer = (
        "Plan.\n\n```json\n"
        '{"moves": [{"app": "catalog-svc", "target_region": "southindia"}], '
        '"decommissions": {}}'
        "\n```\n"
    )
    run = _finish_live(estate, answer, [], 0.0, {})
    assert run.source == "fallback"
    assert run.validation is not None and run.validation.ok
    assert run.rejected_validation is not None
    assert any("'decommissions' must be a list" in v for v in run.rejected_validation.violations)


def test_absent_keys_still_default_cleanly():
    """Omitting a key is legitimate — only present-but-malformed values must fail."""
    from demos.thinking_agent import _finish_live

    estate = _estate()
    answer = '```json\n{"moves": [{"app": "catalog-svc", "target_region": "southindia"}]}\n```'
    run = _finish_live(estate, answer, [], 0.0, {})
    assert run.validation is not None
    assert not any("must be a list" in v for v in run.validation.violations)
