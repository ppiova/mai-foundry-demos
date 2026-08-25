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
