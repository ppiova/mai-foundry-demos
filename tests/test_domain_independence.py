"""The domain must not depend on the UI framework.

This is the property the ``agents/`` package exists for, and it is the kind of
thing that regresses silently: one convenience import of ``streamlit`` inside a
validator, and the rules of the demo are untestable without the framework that
displays them again.

Checked in a subprocess because the assertion is about what an import *pulls in*,
and by the time the rest of this suite runs, Streamlit is already loaded.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROBE = """
import sys
import agents
import agents.decision
import agents.estate
import agents.plan
print(",".join(sorted(m for m in sys.modules if m.split(".")[0] == "streamlit")))
"""


def test_importing_the_domain_does_not_import_streamlit():
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    leaked = result.stdout.strip()
    assert not leaked, f"agents/ pulled in the UI framework: {leaked}"
