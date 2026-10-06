"""Ephemeral GUI-session tracking for the persistent Default profile."""

from __future__ import annotations

from copy import deepcopy

from . import preferences, profiles


class ProfileSession:
    """Track whether Default gained unsaved-to-a-named-profile tuning changes."""

    def __init__(self, settings):
        store = profiles.load_profiles(settings)
        default = store["profiles"].get(preferences.DEFAULT_PROFILE_NAME)
        normalized = type(settings)()
        if store["active"] == preferences.DEFAULT_PROFILE_NAME:
            baseline = preferences._profile_fields(settings)
        else:
            if isinstance(default, dict):
                preferences._apply_snap(
                    normalized, default, preferences._profile_fields(normalized)
                )
            baseline = preferences._profile_fields(normalized)
        self._baseline = deepcopy(baseline)

    def needs_named_save(self, settings) -> bool:
        if profiles.active_name(settings) != preferences.DEFAULT_PROFILE_NAME:
            return False
        return preferences._profile_fields(settings) != self._baseline

    def accept_current_default(self, settings) -> None:
        if profiles.active_name(settings) == preferences.DEFAULT_PROFILE_NAME:
            baseline = preferences._profile_fields(settings)
        else:
            store = profiles.load_profiles(settings)
            normalized = type(settings)()
            default = store["profiles"].get(preferences.DEFAULT_PROFILE_NAME, {})
            preferences._apply_snap(normalized, default, preferences._profile_fields(normalized))
            baseline = preferences._profile_fields(normalized)
        self._baseline = deepcopy(baseline)
