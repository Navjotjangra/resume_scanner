"""Architecture rule: no tkinter outside scanner/gui/."""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scanner"


def test_no_tkinter_outside_gui():
    """No scanner/*.py outside scanner/gui may import tkinter."""
    violations = []
    for py_file in sorted(SCANNER.rglob("*.py")):
        if py_file.parent.name == "gui":
            continue
        text = py_file.read_text(encoding="utf-8")
        if "tkinter" in text:
            violations.append(str(py_file.relative_to(ROOT)))
    assert not violations, f"tkinter imported outside gui/: {violations}"
