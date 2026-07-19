from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_system_tab_does_not_read_inherited_settings_before_super_init():
    """Frozen GUI construction must not depend on SettingsTab fields too early."""
    source = (ROOT / "src/modules/gui/system_tab.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    system_tab = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SystemTab"
    )
    init = next(
        node
        for node in system_tab.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    super_line = next(
        node.lineno
        for node in ast.walk(init)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "__init__"
        and isinstance(node.func.value, ast.Call)
        and isinstance(node.func.value.func, ast.Name)
        and node.func.value.func.id == "super"
    )
    early_settings_reads = [
        node.lineno
        for node in ast.walk(init)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and node.attr == "settings"
        and node.lineno < super_line
    ]
    assert early_settings_reads == []
