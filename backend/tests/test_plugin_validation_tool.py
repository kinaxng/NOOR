from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATE_SCRIPT = REPO_ROOT / "tools" / "noor_plugin" / "validate.py"


def test_official_plugin_manifest_types_and_capabilities_are_known() -> None:
    result = subprocess.run(
        [
            "python3",
            str(VALIDATE_SCRIPT),
            str(REPO_ROOT / "plugins"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    unknown_type = [line for line in result.stdout.splitlines() if "PLUGIN_TYPE_UNKNOWN" in line]
    unknown_capability = [line for line in result.stdout.splitlines() if "CAPABILITY_UNKNOWN" in line]
    css_prefix = [line for line in result.stdout.splitlines() if "CSS_PREFIX_MISSING" in line]
    assert not unknown_type, "\n".join(unknown_type)
    assert not unknown_capability, "\n".join(unknown_capability)
    assert not css_prefix, "\n".join(css_prefix)
