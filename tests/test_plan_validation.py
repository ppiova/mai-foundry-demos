"""Tests for the deterministic plan validator.

The agent demo's whole point is "the model proposes, deterministic code decides".
These tests cover the failure modes a per-proposal tool call cannot catch —
above all *cumulative* capacity, where two individually-valid moves overflow a
region once combined.
"""

from __future__ import annotations

from demos.thinking_agent import (
    CloudEstate,
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
    # ledger-db is Tier-1, so decommission a dependency target that others rely on.
    dependents = [n for n, a in estate.apps.items() if "catalog-svc" in a.get("dependencies", [])]
    assert dependents, "fixture should have apps depending on catalog-svc"
    result = validate_plan(estate, [], ["catalog-svc"])
    assert any("depends on decommissioned" in v for v in result.violations)


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
