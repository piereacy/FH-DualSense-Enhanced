"""Build-selectable GUI shells with one shared backend and page set."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GuiVariant:
    key: str
    label: str
    navigation: str
    sidebar_width: int
    window_width: int
    compact_nav: bool = False


VARIANTS = {
    "console": GuiVariant("console", "Miku Console", "side", 204, 1040),
    "stage": GuiVariant("stage", "Miku Stage", "top", 0, 1120),
    "studio": GuiVariant("studio", "Miku Studio", "side", 112, 1080, True),
}


def _bundled_variant_file() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "data" / "ui_variant.txt"
    return Path(__file__).resolve().parents[2] / "data" / "ui_variant.txt"


def current_variant() -> GuiVariant:
    key = os.environ.get("FHDS_UI_VARIANT", "").strip().lower()
    if not key:
        try:
            key = _bundled_variant_file().read_text(encoding="utf-8").strip().lower()
        except OSError:
            key = "console"
    return VARIANTS.get(key, VARIANTS["console"])

