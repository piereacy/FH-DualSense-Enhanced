"""Forza Horizon backend: UDP telemetry listener + game-aware trigger logic."""
from .udp_listener import (
    PACKET_SIZE,
    TelemetryPhase,
    TelemetrySnapshot,
    UDPListener,
    parse_packet,
)
from .effects import Controller, TriggerAnimations
from .process_watch import GameProcess, ProcessWatcher, find_game_process
from .fh6_language import (
    ArchiveLanguage,
    FH6Install,
    FH6LanguageError,
    FH6LanguageState,
    LanguageInspection,
    SteamLanguageState,
    discover_fh6_install,
    enable_chinese_text_english_voice,
    inspect_language_state,
    is_fh6_running,
    is_windows_steam_supported,
    launch_fh6_via_steam,
    repair_native_language,
    restore_native_language,
    validate_game_root,
)
from .collision import CollisionDetector, CollisionSignal
from .lighting import LightingController

__all__ = [
    "UDPListener", "TelemetryPhase", "TelemetrySnapshot", "parse_packet", "PACKET_SIZE", "Controller",
    "TriggerAnimations", "GameProcess", "ProcessWatcher", "find_game_process", "CollisionDetector",
    "ArchiveLanguage", "FH6Install", "FH6LanguageError", "FH6LanguageState",
    "LanguageInspection", "SteamLanguageState", "discover_fh6_install",
    "enable_chinese_text_english_voice", "inspect_language_state",
    "is_fh6_running", "is_windows_steam_supported", "launch_fh6_via_steam",
    "repair_native_language", "restore_native_language", "validate_game_root",
    "CollisionSignal", "LightingController",
]
