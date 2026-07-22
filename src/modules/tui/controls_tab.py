"""Complete adaptive-trigger feedback page for the Console frontend."""

from modules.feedback_schema import (
    TRIGGER_EXPERIMENTAL_SECTIONS,
    TRIGGER_SETTING_SECTIONS,
    TRIGGER_SWITCH_SECTIONS,
)

from .settings_tab import SettingsTab


class ControlsTab(SettingsTab):
    SWITCH_SECTIONS = TRIGGER_SWITCH_SECTIONS
    SECTIONS = TRIGGER_SETTING_SECTIONS
    EXPERIMENTAL_SECTIONS = TRIGGER_EXPERIMENTAL_SECTIONS
    SHOW_RESET = False
    SHOW_EXPERIMENTAL = True
