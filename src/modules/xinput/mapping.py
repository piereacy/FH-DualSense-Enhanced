"""Validated, persisted digital-button mapping for the Xbox App bridge."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MappingTarget:
    key: str
    label: str


@dataclass(frozen=True, slots=True)
class MappingSource:
    key: str
    setting: str
    label: str
    default_target: str


MAPPING_TARGETS = (
    MappingTarget("off", "Disabled"),
    MappingTarget("a", "A"),
    MappingTarget("b", "B"),
    MappingTarget("x", "X"),
    MappingTarget("y", "Y"),
    MappingTarget("left_shoulder", "Left shoulder"),
    MappingTarget("right_shoulder", "Right shoulder"),
    MappingTarget("back", "View / Back"),
    MappingTarget("start", "Menu / Start"),
    MappingTarget("left_thumb", "Left stick click"),
    MappingTarget("right_thumb", "Right stick click"),
    MappingTarget("guide", "Guide"),
    MappingTarget("dpad_up", "D-pad up"),
    MappingTarget("dpad_down", "D-pad down"),
    MappingTarget("dpad_left", "D-pad left"),
    MappingTarget("dpad_right", "D-pad right"),
)

MAPPING_SOURCE_GROUPS = (
    (
        "Face buttons",
        (
            MappingSource("cross", "xinput_mapping_cross", "Cross", "a"),
            MappingSource("circle", "xinput_mapping_circle", "Circle", "b"),
            MappingSource("square", "xinput_mapping_square", "Square", "x"),
            MappingSource("triangle", "xinput_mapping_triangle", "Triangle", "y"),
        ),
    ),
    (
        "Shoulder and system buttons",
        (
            MappingSource("l1", "xinput_mapping_l1", "L1", "left_shoulder"),
            MappingSource("r1", "xinput_mapping_r1", "R1", "right_shoulder"),
            MappingSource("create", "xinput_mapping_create", "Create", "back"),
            MappingSource("options", "xinput_mapping_options", "Options", "start"),
            MappingSource("l3", "xinput_mapping_l3", "L3", "left_thumb"),
            MappingSource("r3", "xinput_mapping_r3", "R3", "right_thumb"),
            MappingSource("ps", "xinput_mapping_ps", "PS", "guide"),
        ),
    ),
    (
        "D-pad",
        (
            MappingSource("dpad_up", "xinput_mapping_dpad_up", "D-pad up", "dpad_up"),
            MappingSource(
                "dpad_down", "xinput_mapping_dpad_down", "D-pad down", "dpad_down"
            ),
            MappingSource(
                "dpad_left", "xinput_mapping_dpad_left", "D-pad left", "dpad_left"
            ),
            MappingSource(
                "dpad_right", "xinput_mapping_dpad_right", "D-pad right", "dpad_right"
            ),
        ),
    ),
    (
        "Touchpad",
        (
            MappingSource(
                "touchpad_left",
                "xinput_mapping_touchpad_left",
                "Touchpad left click",
                "back",
            ),
            MappingSource(
                "touchpad_right",
                "xinput_mapping_touchpad_right",
                "Touchpad right click",
                "start",
            ),
        ),
    ),
)

MAPPING_SOURCES = tuple(
    source
    for _group, sources in MAPPING_SOURCE_GROUPS
    for source in sources
)
MAPPING_SOURCE_BY_KEY = {source.key: source for source in MAPPING_SOURCES}
MAPPING_SOURCE_BY_SETTING = {source.setting: source for source in MAPPING_SOURCES}
MAPPING_TARGET_BY_KEY = {target.key: target for target in MAPPING_TARGETS}
MAPPING_SETTING_FIELDS = frozenset(MAPPING_SOURCE_BY_SETTING)
_SOURCE_INDEX = {source.key: index for index, source in enumerate(MAPPING_SOURCES)}


@dataclass(frozen=True, slots=True)
class XInputButtonMapping:
    """An immutable target key for every supported physical digital input."""

    targets: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.targets) != len(MAPPING_SOURCES):
            raise ValueError("XInput mapping must define every button source")
        invalid = set(self.targets).difference(MAPPING_TARGET_BY_KEY)
        if invalid:
            raise ValueError(f"Unknown XInput mapping target: {sorted(invalid)!r}")

    def target_for(self, source_key: str) -> str:
        return self.targets[_SOURCE_INDEX[source_key]]


DEFAULT_BUTTON_MAPPING = XInputButtonMapping(
    tuple(source.default_target for source in MAPPING_SOURCES)
)


def normalize_mapping_target(value: object, default: str) -> str:
    """Return a known target key, falling back to this source's safe default."""
    normalized = str(value).strip().casefold()
    return normalized if normalized in MAPPING_TARGET_BY_KEY else default


def configured_mapping_from_settings(settings) -> XInputButtonMapping:
    """Read the saved custom mapping, repairing invalid values in memory only."""
    return XInputButtonMapping(
        tuple(
            normalize_mapping_target(
                getattr(settings, source.setting, source.default_target),
                source.default_target,
            )
            for source in MAPPING_SOURCES
        )
    )


def active_mapping_from_settings(settings) -> XInputButtonMapping:
    """Use the custom map only behind its explicit experimental opt-in."""
    if not bool(getattr(settings, "enable_custom_xinput_mapping", False)):
        return DEFAULT_BUTTON_MAPPING
    return configured_mapping_from_settings(settings)


def normalize_mapping_settings(settings) -> bool:
    """Canonicalize persisted target strings so UI refreshes remain valid."""
    changed = False
    for source in MAPPING_SOURCES:
        current = getattr(settings, source.setting, source.default_target)
        normalized = normalize_mapping_target(current, source.default_target)
        if current != normalized:
            setattr(settings, source.setting, normalized)
            changed = True
    return changed


def reset_mapping_settings(settings) -> bool:
    """Restore Steam-style defaults while leaving the opt-in switch unchanged."""
    changed = False
    for source in MAPPING_SOURCES:
        if getattr(settings, source.setting, None) != source.default_target:
            setattr(settings, source.setting, source.default_target)
            changed = True
    return changed
