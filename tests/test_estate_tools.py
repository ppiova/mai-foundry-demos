import json

import pytest

from agents import CloudEstate, execute_tool_call


@pytest.mark.parametrize(
    "app_names",
    [
        ["order-api"] * 7,
        ["order-api", "catalog-svc", "order-api"],
    ],
)
def test_duplicate_applications_are_rejected_before_calculating(app_names):
    estate = CloudEstate()
    result = estate.calculate_migration_cost(app_names, "southindia")
    assert "Duplicate" in result["error"]
    assert "monthly_savings" not in result
    assert "resulting_target_utilization_pct" not in result


def test_tool_dispatch_surfaces_duplicate_arguments_to_the_agent():
    _, _, result = execute_tool_call(
        CloudEstate(),
        {
            "id": "call-duplicate",
            "function": {
                "name": "calculate_migration_cost",
                "arguments": json.dumps(
                    {"app_names": ["order-api", "order-api"], "target_region": "southindia"}
                ),
            },
        },
    )
    assert "Duplicate" in result["error"]


def test_unique_applications_are_counted_once():
    result = CloudEstate().calculate_migration_cost(["order-api"], "southindia")
    assert result["errors"] == []
    assert result["monthly_savings"] == 3600
    assert result["resulting_target_utilization_pct"] == 31.7
    assert result["within_capacity_ceiling"]


def test_same_region_move_does_not_double_count_existing_capacity():
    estate = CloudEstate()
    region = estate.apps["order-api"]["region"]
    result = estate.calculate_migration_cost(["order-api"], region)
    assert "already in" in result["errors"][0]
    assert result["apps"] == []
    assert result["monthly_savings"] == result["one_time_migration_cost"] == 0
    assert result["resulting_target_utilization_pct"] == round(estate.utilization(region), 1)
