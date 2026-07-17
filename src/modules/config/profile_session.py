"""Ephemeral GUI-session tracking for the persistent Default profile."""

from __future__ import annotations

from copy import deepcopy

from . import preferences, profiles


class ProfileSession:
    """Track whether Default gained unsaved-to-a-named-profile tuning changes."""

    def __init__(self, settings):
        store = profiles.load_profiles()
        default = store["profiles"].get(preferences.DEFAULT_PROFILE_NAME)
        baseline = preferences._profile_fields(type(settings)())
        if isinstance(default, dict):
            baseline.update(default)
        else:
            baseline.update(preferences._profile_fields(settings))
        self._baseline = deepcopy(baseline)

    def needs_named_save(self, settings) -> bool:
        store = profiles.load_profiles()
        if store["active"] != preferences.DEFAULT_PROFILE_NAME:
            return False
        return preferences._profile_fields(settings) != self._baseline

    def accept_current_default(self, settings) -> None:
        self._baseline = deepcopy(preferences._profile_fields(settings))
