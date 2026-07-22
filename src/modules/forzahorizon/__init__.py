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
from .game_launch import (
    DEFAULT_FORZA_GAME_KEY,
    FORZA_GAME_KEYS,
    FORZA_GAMES,
    ForzaGame,
    ForzaInstall,
    ForzaLaunchError,
    XboxLaunchResult,
    XboxStartApp,
    discover_xbox_aumid,
    discover_xbox_forza_install,
    discover_forza_install,
    get_forza_game,
    is_forza_game_running,
    is_windows_steam_supported,
    launch_forza_via_steam,
    launch_forza_via_xbox_app,
    validate_forza_root,
    windows_local_drive_roots,
    xbox_library_roots,
)
from .fh6_language import (
    ArchiveLanguage,
    FH6Install,
    FH6LanguageSummary,
    FH6LanguageError,
    FH6LanguageState,
    LanguageInspection,
    SteamLanguageState,
    discover_fh6_install,
    discover_xbox_fh6_install,
    enable_chinese_text_english_voice,
    inspect_language_state,
    is_fh6_running,
    launch_fh6_via_steam,
    repair_native_language,
    restore_native_language,
    summarize_fh6_languages,
    validate_game_root,
)
from .collision import CollisionDetector, CollisionSignal
from .lighting import LightingController
from .redline import RedlineDetector, RedlineState, predict_redline_rpm
from .controller_icons import (
    ControllerIconInspection,
    ControllerIconModError,
    ControllerIconState,
    inspect_controller_icons,
    install_controller_icons,
    restore_controller_icons,
    validate_controller_icon_root,
)

__all__ = [
    "UDPListener", "TelemetryPhase", "TelemetrySnapshot", "parse_packet", "PACKET_SIZE", "Controller",
    "TriggerAnimations", "GameProcess", "ProcessWatcher", "find_game_process", "CollisionDetector",
    "DEFAULT_FORZA_GAME_KEY", "FORZA_GAME_KEYS", "FORZA_GAMES", "ForzaGame",
    "ForzaInstall", "ForzaLaunchError", "discover_forza_install", "get_forza_game",
    "XboxLaunchResult", "XboxStartApp", "discover_xbox_aumid",
    "discover_xbox_forza_install", "windows_local_drive_roots", "xbox_library_roots",
    "is_forza_game_running", "is_windows_steam_supported", "launch_forza_via_steam",
    "launch_forza_via_xbox_app",
    "validate_forza_root",
    "ArchiveLanguage", "FH6Install", "FH6LanguageSummary", "FH6LanguageError", "FH6LanguageState",
    "LanguageInspection", "SteamLanguageState", "discover_fh6_install",
    "discover_xbox_fh6_install",
    "enable_chinese_text_english_voice", "inspect_language_state",
    "is_fh6_running", "is_windows_steam_supported", "launch_fh6_via_steam",
    "repair_native_language", "restore_native_language", "summarize_fh6_languages",
    "validate_game_root",
    "CollisionSignal", "LightingController", "RedlineDetector", "RedlineState",
    "predict_redline_rpm",
    "ControllerIconInspection", "ControllerIconModError", "ControllerIconState",
    "inspect_controller_icons", "install_controller_icons", "restore_controller_icons",
    "validate_controller_icon_root",
]
