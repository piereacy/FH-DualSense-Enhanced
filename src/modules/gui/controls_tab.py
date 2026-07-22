"""Complete adaptive-trigger feedback page."""

from modules.feedback_schema import (
    TRIGGER_EXPERIMENTAL_SECTIONS,
    TRIGGER_SETTING_SECTIONS,
    TRIGGER_SWITCH_SECTIONS,
)

from .settings_tab import SettingsTab
from .settings_tab import responsive_column_count as responsive_column_count


class ControlsTab(SettingsTab):
    """L2/R2 switches, tuning and experimental controls in one page."""

    SWITCH_SECTIONS = TRIGGER_SWITCH_SECTIONS
    SECTIONS = TRIGGER_SETTING_SECTIONS
    EXPERIMENTAL_SECTIONS = TRIGGER_EXPERIMENTAL_SECTIONS
    SHOW_RESET = False
    SHOW_EXPERIMENTAL = True
    PAGE_TITLE = "Trigger feedback"
    PAGE_SUBTITLE = "L2/R2 switches and tuning. Changes save instantly."
