"""The cloud estate the decision agent reasons over, and the two tools it calls.

Pure data and arithmetic. No HTTP, no UI framework, no model. The tools are
ordinary methods: `get_region_capacity` and `calculate_migration_cost` are what
the model is allowed to ask, and `TOOLS_SCHEMA` is how they are described to it.

The numbers here are the ground truth the model's proposal gets scored against.
Nothing in this module trusts model output.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "assets" / "data"


# ─────────────────────────────────────────────────────────────────────────────
# Data model + the two local tools
# ─────────────────────────────────────────────────────────────────────────────
class CloudEstate:
    def __init__(self):
        estate = json.loads((DATA / "cloud_estate.json").read_text(encoding="utf-8"))
        regions = json.loads((DATA / "region_capacity.json").read_text(encoding="utf-8"))
        self.objective: str = estate["objective"]
        self.apps: dict[str, dict] = {a["name"]: dict(a) for a in estate["applications"]}
        self.regions: dict[str, dict] = regions["regions"]
        self.ceiling: float = regions["capacity_ceiling_pct"]

    # -- capacity helpers ------------------------------------------------------
    def ceiling_units(self, region: str) -> float:
        return self.regions[region]["capacity_units_total"] * self.ceiling / 100.0

    def used_units(
        self,
        region: str,
        assignments: dict[str, str] | None = None,
        decommissioned: set[str] | None = None,
    ) -> float:
        decommissioned = decommissioned or set()
        used = self.regions[region]["baseline_overhead_units"]
        for name, app in self.apps.items():
            if name in decommissioned:
                continue
            reg = (assignments or {}).get(name, app["region"])
            if reg == region:
                used += app["capacity_units"]
        return used

    def utilization(self, region: str, assignments=None, decommissioned=None) -> float:
        total = self.regions[region]["capacity_units_total"]
        return 100.0 * self.used_units(region, assignments, decommissioned) / total

    def effective_cost(self, name: str, region: str) -> float:
        app = self.apps[name]
        src_idx = self.regions[app["region"]]["cost_index"]
        tgt_idx = self.regions[region]["cost_index"]
        return app["monthly_cost"] * (tgt_idx / src_idx)

    def baseline_cost(self) -> float:
        return sum(a["monthly_cost"] for a in self.apps.values())

    # -- TOOL: get_region_capacity --------------------------------------------
    def get_region_capacity(self, region: str) -> dict:
        if region not in self.regions:
            return {"error": f"Unknown region '{region}'. Valid: {list(self.regions)}"}
        r = self.regions[region]
        used = self.used_units(region)
        total = r["capacity_units_total"]
        return {
            "region": region,
            "display_name": r["display_name"],
            "cost_index": r["cost_index"],
            "capacity_units_total": total,
            "used_units": round(used, 1),
            "utilization_pct": round(100.0 * used / total, 1),
            "capacity_ceiling_pct": self.ceiling,
            "headroom_units_to_ceiling": round(self.ceiling_units(region) - used, 1),
        }

    # -- TOOL: calculate_migration_cost ---------------------------------------
    def calculate_migration_cost(self, app_names: list[str], target_region: str) -> dict:
        if target_region not in self.regions:
            return {"error": f"Unknown target_region '{target_region}'."}
        if len(app_names) != len(set(app_names)):
            return {"error": "Duplicate application names are not allowed; list each app once."}
        details, errors = [], []
        monthly_before = monthly_after = one_time = 0.0
        added_units = 0
        for name in app_names:
            app = self.apps.get(name)
            if not app:
                errors.append(f"Unknown app '{name}'.")
                continue
            if app["tier"] == 1 or not app["can_migrate"]:
                errors.append(f"'{name}' is Tier-{app['tier']} / non-migratable and cannot move.")
                continue
            if app["region"] == target_region:
                errors.append(f"'{name}' is already in '{target_region}'; no migration is needed.")
                continue
            before = app["monthly_cost"]
            after = self.effective_cost(name, target_region)
            monthly_before += before
            monthly_after += after
            one_time += before * 0.5  # simple one-time migration estimate
            added_units += app["capacity_units"]
            details.append(
                {
                    "app": name,
                    "from": app["region"],
                    "monthly_before": round(before),
                    "monthly_after": round(after),
                    "monthly_saved": round(before - after),
                }
            )
        resulting_used = self.used_units(target_region) + added_units
        total = self.regions[target_region]["capacity_units_total"]
        resulting_util = 100.0 * resulting_used / total
        return {
            "target_region": target_region,
            "apps": details,
            "errors": errors,
            "monthly_cost_before": round(monthly_before),
            "monthly_cost_after": round(monthly_after),
            "monthly_savings": round(monthly_before - monthly_after),
            "one_time_migration_cost": round(one_time),
            "resulting_target_utilization_pct": round(resulting_util, 1),
            "within_capacity_ceiling": resulting_util <= self.ceiling,
        }

    def dispatch(self, name: str, args: dict) -> dict:
        if name == "get_region_capacity":
            return self.get_region_capacity(args.get("region", ""))
        if name == "calculate_migration_cost":
            return self.calculate_migration_cost(
                args.get("app_names", []), args.get("target_region", "")
            )
        return {"error": f"Unknown tool '{name}'."}

    def summary_for_prompt(self) -> dict:
        return {
            "objective": self.objective,
            "capacity_ceiling_pct": self.ceiling,
            "regions": {
                k: {
                    "cost_index": v["cost_index"],
                    "capacity_units_total": v["capacity_units_total"],
                }
                for k, v in self.regions.items()
            },
            "applications": [
                {
                    k: a[k]
                    for k in (
                        "name",
                        "tier",
                        "region",
                        "monthly_cost",
                        "capacity_units",
                        "can_migrate",
                        "idle_candidate",
                        "dependencies",
                    )
                }
                for a in self.apps.values()
            ],
        }


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_region_capacity",
            "description": "Return current capacity, utilization %, headroom to the 70% ceiling, and cost index for a region.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "enum": ["eastus", "westeurope", "southindia", "uaenorth"],
                    }
                },
                "required": ["region"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_migration_cost",
            "description": "Estimate monthly savings, one-time cost, and the resulting target-region utilization for moving a set of apps to a target region. Rejects duplicate names, same-region moves, and Tier-1 / non-migratable apps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_names": {"type": "array", "items": {"type": "string"}},
                    "target_region": {
                        "type": "string",
                        "enum": ["eastus", "westeurope", "southindia", "uaenorth"],
                    },
                },
                "required": ["app_names", "target_region"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are an enterprise cloud FinOps decision agent. You are given a cloud estate "
    "and two tools. Reason step by step, call the tools to verify capacity and cost "
    "before committing to moves, and respect every hard constraint:\n"
    "  1) Do NOT move any Tier-1 application.\n"
    "  2) No region may exceed the capacity ceiling (70%).\n"
    "  3) Achieve at least a 20% reduction in total monthly cost. Aim for 23-25% "
    "so a marginal estimate never lands under the 20% floor.\n"
    "Prefer decommissioning idle_candidate dev/test workloads and moving low-tier "
    "workloads to cheaper regions with headroom. When done, output a clear Markdown "
    "plan: a summary line with baseline vs new monthly cost and % saved, a table of "
    "moves/decommissions, the resulting per-region utilization, and a short "
    "'Tradeoffs & risks' section (mention dependencies and one-time migration cost).\n"
    "Finally, append a fenced ```json block with the machine-checkable plan:\n"
    '{"moves": [{"app": "<name>", "target_region": "<region>"}], '
    '"decommissions": ["<name>"], "risks": ["<short note>"]}\n'
    "It must list every action exactly once and match the table above."
)
