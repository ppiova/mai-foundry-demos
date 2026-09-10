"""Migration plans: the typed shape, the deterministic check, and the rendering.

The model *proposes*; this module *decides*. Everything reported as fact, the
savings, the utilizations, the constraint compliance, is recomputed here from the
estate, never taken from the model's prose.

Kept free of any UI framework so the validator can be tested, and reused, without
one. That is the whole point of the split.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .estate import CloudEstate


@dataclass(frozen=True)
class PlanMove:
    app: str
    target_region: str


@dataclass(frozen=True)
class MigrationPlan:
    moves: tuple[PlanMove, ...]
    decommissions: tuple[str, ...]
    risks: tuple[str, ...] = ()

    @classmethod
    def from_validated_mapping(cls, proposal: dict) -> MigrationPlan:
        """Create typed data only after ``validate_plan`` accepts the raw mapping."""
        risks = proposal.get("risks", [])
        return cls(
            moves=tuple(PlanMove(item["app"], item["target_region"]) for item in proposal["moves"]),
            decommissions=tuple(proposal["decommissions"]),
            risks=tuple(risks) if isinstance(risks, list) else (),
        )

    def validation_inputs(self) -> tuple[list[dict], list[str]]:
        return (
            [{"app": move.app, "target_region": move.target_region} for move in self.moves],
            list(self.decommissions),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic plan validation
#
# `calculate_migration_cost` scores each proposal against the untouched baseline,
# so two moves that are individually fine can still breach the 70% ceiling once
# combined. That is why the whole plan is validated here, not move by move.
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class PlanValidation:
    ok: bool
    violations: list[str] = field(default_factory=list)
    baseline_cost: float = 0.0
    new_cost: float = 0.0
    saved: float = 0.0
    saved_pct: float = 0.0
    one_time_cost: float = 0.0
    utilization: dict[str, float] = field(default_factory=dict)  # unrounded percentages
    ceiling: float = 70.0
    moved: int = 0
    decommissioned: int = 0
    risks: tuple[str, ...] = ()

    def over_ceiling(self, ceiling: float | None = None) -> int:
        """Regions above the ceiling.

        ``utilization`` is stored unrounded on purpose: rounding to 1dp first would
        let 70.04% display as 70.0% and slip past a ``> ceiling`` test, undercounting
        breaches that ``violations`` already recorded.
        """
        limit = self.ceiling if ceiling is None else ceiling
        return sum(1 for v in self.utilization.values() if v > limit)


def validate_plan(
    estate: CloudEstate,
    moves: list[dict],
    decommissions: list[str],
    min_savings_pct: float = 20.0,
    risks: object = None,
) -> PlanValidation:
    """Check a proposed plan against every hard constraint, cumulatively.

    ``moves``/``decommissions`` come straight from model-produced JSON, so their
    shape is untrusted: anything malformed is reported as a validation failure
    rather than raised, which would otherwise collapse the whole run into the
    fallback instead of showing *why* the proposal was rejected.
    """
    violations: list[str] = []
    assignments: dict[str, str] = {}
    decommissioned: set[str] = set()
    seen: set[str] = set()
    normalized_risks: list[str] = []

    if risks is not None:
        if not isinstance(risks, list):
            violations.append(f"'risks' must be a list, got {type(risks).__name__}.")
        else:
            for risk in risks:
                if not isinstance(risk, str) or not risk.strip():
                    violations.append("Risk entries must be non-empty strings.")
                else:
                    normalized_risks.append(risk.strip())

    if not isinstance(decommissions, list):
        violations.append(f"'decommissions' must be a list, got {type(decommissions).__name__}.")
        decommissions = []
    if not isinstance(moves, list):
        violations.append(f"'moves' must be a list, got {type(moves).__name__}.")
        moves = []

    for name in decommissions:
        if not isinstance(name, str):
            violations.append(f"Decommission entries must be app names, got {name!r}.")
            continue
        app = estate.apps.get(name)
        if not app:
            violations.append(f"Unknown application '{name}' in decommissions.")
            continue
        if name in seen:
            violations.append(f"'{name}' appears more than once in the plan.")
            continue
        seen.add(name)
        if app["tier"] == 1:
            violations.append(f"'{name}' is Tier-1 and must not be decommissioned.")
            continue
        if not app.get("idle_candidate"):
            violations.append(f"'{name}' is active and is not an idle decommission candidate.")
            continue
        decommissioned.add(name)

    for mv in moves:
        if not isinstance(mv, dict):
            violations.append(f"Move entries must be objects, got {mv!r}.")
            continue
        name = mv.get("app")
        target = mv.get("target_region")
        if not isinstance(name, str):
            violations.append(f"Move is missing a valid 'app' name: {mv!r}.")
            continue
        app = estate.apps.get(name)
        if not app:
            violations.append(f"Unknown application '{name}' in moves.")
            continue
        if name in seen:
            violations.append(f"'{name}' appears more than once in the plan.")
            continue
        seen.add(name)
        if not isinstance(target, str):
            # `x in dict` hashes x, so a dict/list target would raise TypeError.
            violations.append(f"Move for '{name}' has an invalid 'target_region': {target!r}.")
            continue
        if target not in estate.regions:
            violations.append(f"Unknown target region '{target}' for '{name}'.")
            continue
        if app["tier"] == 1:
            violations.append(f"'{name}' is Tier-1 and must not be moved.")
            continue
        if not app["can_migrate"]:
            violations.append(f"'{name}' is flagged as non-migratable.")
            continue
        if target == app["region"]:
            violations.append(
                f"'{name}' is already in '{target}'; same-region moves are not actions."
            )
            continue
        assignments[name] = target

    # Cumulative capacity — the check a per-proposal tool call cannot make.
    utilization: dict[str, float] = {}
    for region in estate.regions:
        util = estate.utilization(region, assignments, decommissioned)
        utilization[region] = util
        if util > estate.ceiling:
            violations.append(
                f"Region '{region}' ends at {util:.1f}%, above the {estate.ceiling:.0f}% ceiling."
            )

    # Dependencies of a decommissioned app must not be left dangling.
    for name, app in estate.apps.items():
        if name in decommissioned:
            continue
        for dep in app.get("dependencies", []):
            if dep in decommissioned:
                violations.append(f"'{name}' depends on decommissioned '{dep}'.")

    baseline = estate.baseline_cost()
    saved = 0.0
    one_time = 0.0
    for name in decommissioned:
        saved += estate.apps[name]["monthly_cost"]
    for name, target in assignments.items():
        saved += estate.apps[name]["monthly_cost"] - estate.effective_cost(name, target)
        one_time += estate.apps[name]["monthly_cost"] * 0.5

    saved_pct = 100.0 * saved / baseline if baseline else 0.0
    if saved_pct < min_savings_pct:
        violations.append(
            f"Savings {saved_pct:.2f}% fall short of the {min_savings_pct:.0f}% target."
        )

    return PlanValidation(
        ok=not violations,
        violations=violations,
        baseline_cost=baseline,
        new_cost=baseline - saved,
        saved=saved,
        saved_pct=saved_pct,
        one_time_cost=one_time,
        utilization=utilization,
        ceiling=estate.ceiling,
        moved=len(assignments),
        decommissioned=len(decommissioned),
        risks=tuple(normalized_risks),
    )


def extract_structured_plan(text: str) -> dict | None:
    """Pull the trailing ```json {...}``` plan out of the model's answer, if present."""
    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    for block in reversed(blocks):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and ("moves" in data or "decommissions" in data):
            return data
    return None


def _md_escape_dollars(text: str) -> str:
    """Escape ``$`` so Streamlit does not parse model-authored amounts as LaTeX."""
    return text.replace("$", r"\$")


def render_validated_plan(
    estate: CloudEstate, proposal: MigrationPlan, validation: PlanValidation
) -> str:
    """Render factual Markdown exclusively from the validated proposal and estate."""
    rows = ["| Action | Application | Region |", "|---|---|---|"]
    for move in proposal.moves:
        rows.append(f"| Move | {move.app} | {move.target_region} |")
    for name in proposal.decommissions:
        rows.append(f"| Decommission | {name} | {estate.apps[name]['region']} |")
    utilization = ["| Region | Final utilization |", "|---|---:|"]
    for region, value in validation.utilization.items():
        utilization.append(f"| {region} | {value:.1f}% |")
    risk_lines = [f"- {_md_escape_dollars(risk)}" for risk in proposal.risks]
    if not risk_lines:
        risk_lines = ["- Review dependencies and migration sequencing before execution."]
    return "\n".join(
        [
            "## Validated migration plan",
            "",
            f"Baseline **\\${validation.baseline_cost:,.0f}/month** → "
            f"**\\${validation.new_cost:,.0f}/month** "
            f"(**{validation.saved_pct:.1f}% monthly cost reduction**).",
            "",
            *rows,
            "",
            "### Resulting regional utilization",
            "",
            *utilization,
            "",
            f"Estimated one-time migration cost: **\\${validation.one_time_cost:,.0f}**.",
            "",
            "### Tradeoffs & risks",
            "",
            *risk_lines,
        ]
    )


def _all_within_ceiling(estate, assignments, decommissioned) -> bool:
    return all(
        estate.utilization(r, assignments, decommissioned) <= estate.ceiling for r in estate.regions
    )


def _render_plan_markdown(
    estate, baseline, saved, moves, decomm_rows, assignments, decommissioned
) -> str:
    pct = 100.0 * saved / baseline
    lines = [
        f"### Migration plan — {pct:.1f}% monthly cost reduction",
        f"**Baseline:** \\${baseline:,.0f}/mo → **New:** \\${baseline - saved:,.0f}/mo "
        f"(**−\\${saved:,.0f}**, {pct:.1f}%). Constraints: no Tier-1 moved, all regions ≤ {estate.ceiling:.0f}%.",
        "",
    ]
    if decomm_rows:
        lines += [
            "**Decommission idle dev/test workloads**",
            "",
            "| App | Region | Monthly saved |",
            "|---|---|--:|",
        ]
        lines += [
            f"| {r['app']} | {r['region']} | \\${r['monthly_saved']:,} |" for r in decomm_rows
        ]
        lines.append("")
    if moves:
        lines += [
            "**Move low-tier workloads to cheaper regions with headroom**",
            "",
            "| App | From → To | Before | After | Saved |",
            "|---|---|--:|--:|--:|",
        ]
        lines += [
            f"| {m['app']} | {m['from']} → {m['to']} | \\${m['monthly_before']:,} | "
            f"\\${m['monthly_after']:,} | \\${m['monthly_saved']:,} |"
            for m in moves
        ]
        lines.append("")
    # Resulting utilization
    lines += [
        "**Resulting region utilization**",
        "",
        "| Region | Before | After | Ceiling |",
        "|---|--:|--:|--:|",
    ]
    for r in estate.regions:
        before = estate.utilization(r)
        after = estate.utilization(r, assignments, decommissioned)
        flag = "✅" if after <= estate.ceiling else "⚠️"
        lines.append(f"| {r} | {before:.0f}% | {after:.0f}% {flag} | {estate.ceiling:.0f}% |")
    lines += [
        "",
        "**Tradeoffs & risks**",
        "- Moves incur a one-time migration cost (~50% of one month per app) and brief cutover risk.",
        "- Dependency chains stay intra-region where possible; verify latency for `recommendation-engine`→`catalog-svc` after the move.",
        "- Decommissioning `dev-sandbox`/`staging-cluster` assumes no active release train depends on them this cycle.",
        "- Tier-1 (`payments-core`, `identity-service`, `ledger-db`, `fraud-realtime`) untouched by design.",
    ]
    return "\n".join(lines)
