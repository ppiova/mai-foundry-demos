"""Domain logic for the demo agents, deliberately independent of the UI.

`demos/` renders; this package decides. Importing the plan validator used to drag
in Streamlit, which made the rules of the demo untestable without the framework
that displays them.
"""

from __future__ import annotations

from .decision import AgentRun, execute_tool_call, fallback_plan, run_agent
from .estate import SYSTEM_PROMPT, TOOLS_SCHEMA, CloudEstate
from .plan import (
    MigrationPlan,
    PlanMove,
    PlanValidation,
    extract_structured_plan,
    render_validated_plan,
    validate_plan,
)

__all__ = [
    "SYSTEM_PROMPT",
    "TOOLS_SCHEMA",
    "AgentRun",
    "CloudEstate",
    "MigrationPlan",
    "PlanMove",
    "PlanValidation",
    "execute_tool_call",
    "extract_structured_plan",
    "fallback_plan",
    "render_validated_plan",
    "run_agent",
    "validate_plan",
]
