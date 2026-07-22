"""Read-only platform discovery and explicit launch helpers for Forza Horizon."""

from __future__ import annotations

import logging
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from types import MappingProxyType

from .process_watch import ProcessScanError, find_game_process

log = logging.getLogger("fhds.forza_launch")


@dataclass(frozen=True, slots=True)
class ForzaGame:
    key: str
    short_name: str
    full_name: str
    steam_app_id: str
    xbox_product_id: str
    executable_name: str

    @property
    def steam_run_uri(self) -> str:
        return f"steam://run/{self.steam_app_id}"

    @property
    def xbox_app_uri(self) -> str:
        return f"msxbox://game/?productId={self.xbox_product_id}"

    @property
    def install_path_field(self) -> str:
        return f"{self.key}_install_path"


@dataclass(frozen=True, slots=True)
class ForzaInstall:
    game: ForzaGame
    root: Path
    source: str
    steam_language: str = ""


@dataclass(frozen=True, slots=True)
class XboxStartApp:
    name: str
    aumid: str


@dataclass(frozen=True, slots=True)
class XboxLaunchResult:
    direct: bool
    target: str


class ForzaLaunchError(RuntimeError):
    pass


_GAME_DEFINITIONS = (
    ForzaGame(
        "fh4", "FH4", "Forza Horizon 4", "1293830", "9PNJXVCVWD4K",
        "ForzaHorizon4.exe",
    ),
    ForzaGame(
        "fh5", "FH5", "Forza Horizon 5", "1551360", "9NKX70BBCDRN",
        "ForzaHorizon5.exe",
    ),
    ForzaGame(
        "fh6", "FH6", "Forza Horizon 6", "2483190", "9N431PX143P8",
        "ForzaHorizon6.exe",
    ),
)
FORZA_GAMES = MappingProxyType({game.key: game for game in _GAME_DEFINITIONS})
FORZA_GAME_KEYS = tuple(FORZA_GAMES)
DEFAULT_FORZA_GAME_KEY = "fh6"

_GAMING_ROOT_MAGIC = b"RGBX"
_GAMING_ROOT_HEADER_SIZE = 8
_MAX_GAMING_ROOT_BYTES = 4096
_MAX_XBOX_LIBRARY_CHILDREN = 512


def get_forza_game(game: str | ForzaGame) -> ForzaGame:
    if isinstance(game, ForzaGame):
        return game
    key = str(game).strip().casefold()
    try:
        return FORZA_GAMES[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported Forza Horizon game key: {game!r}") from exc


def is_windows_steam_supported() -> bool:
    return sys.platform.startswith("win")


def _normalize_app_name(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _decode_start_apps(payload: str) -> tuple[XboxStartApp, ...]:
    if not payload.strip():
        return ()
    try:
        decoded = json.loads(payload.lstrip("\ufeff"))
    except (TypeError, json.JSONDecodeError):
        return ()
    rows = decoded if isinstance(decoded, list) else [decoded]
    result: list[XboxStartApp] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("Name", "")).strip()
        aumid = str(row.get("AppID", row.get("AppId", ""))).strip()
        if name and aumid:
            result.append(XboxStartApp(name, aumid))
    return tuple(result)


def xbox_start_apps(
    *,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> tuple[XboxStartApp, ...]:
    """Read Start-menu AUMIDs without changing package or Xbox state."""
    if not is_windows_steam_supported():
        return ()
    command = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
        "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"
    )
    try:
        completed = run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            capture_output=True,
            check=False,
            encoding="utf-8-sig",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        log.exception("Could not enumerate Xbox App launch identities")
        return ()
    if completed.returncode != 0:
        log.warning(
            "Get-StartApps failed (%s): %s",
            completed.returncode,
            completed.stderr.strip(),
        )
        return ()
    return _decode_start_apps(completed.stdout)


def discover_xbox_aumid(
    game: str | ForzaGame,
    *,
    entries: Iterable[XboxStartApp] | None = None,
) -> str:
    """Find the installed game's current-user launch identity by display name."""
    definition = get_forza_game(game)
    target = _normalize_app_name(definition.full_name)
    candidates: list[tuple[int, int, str]] = []
    for entry in xbox_start_apps() if entries is None else entries:
        # Desktop/Steam Start entries can share the same display name. Xbox
        # App MSIX/GDK identities use the PackageFamilyName!Application form.
        if "!" not in entry.aumid:
            continue
        name = _normalize_app_name(entry.name)
        if name == target:
            score = 0
        elif name.startswith(target):
            score = 1
        elif target in name:
            score = 2
        else:
            continue
        candidates.append((score, len(name), entry.aumid))
    return min(candidates)[2] if candidates else ""


def _vdf_unescape(value: str) -> str:
    return value.replace(r"\\", "\\").replace(r'\"', '"')


def _quoted_value(text: str, key: str) -> str:
    match = re.search(
        rf'"{re.escape(key)}"\s*"([^"\r\n]*)"',
        text,
        flags=re.IGNORECASE,
    )
    return _vdf_unescape(match.group(1)).strip() if match else ""


def _read_vdf(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def _unique_paths(paths: Iterable[str | os.PathLike]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for raw in paths:
        if not raw:
            continue
        path = Path(raw).expanduser()
        key = os.path.normcase(os.path.normpath(str(path)))
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _decode_gaming_root(payload: bytes) -> str:
    """Decode the bounded Xbox `.GamingRoot` drive marker payload."""
    if (
        len(payload) <= _GAMING_ROOT_HEADER_SIZE
        or payload[:4] != _GAMING_ROOT_MAGIC
        or int.from_bytes(payload[4:8], "little") <= 0
    ):
        return ""
    try:
        value = payload[_GAMING_ROOT_HEADER_SIZE:].decode("utf-16-le")
    except UnicodeDecodeError:
        return ""
    return value.split("\0", 1)[0].strip()


def _gaming_root_library(drive_root: Path) -> Path | None:
    marker = drive_root / ".GamingRoot"
    try:
        with marker.open("rb") as stream:
            payload = stream.read(_MAX_GAMING_ROOT_BYTES + 1)
    except OSError:
        return None
    if len(payload) > _MAX_GAMING_ROOT_BYTES:
        return None
    value = _decode_gaming_root(payload)
    if not value or any(ord(character) < 32 for character in value):
        return None
    relative = Path(value)
    if (
        relative.is_absolute()
        or relative.anchor
        or relative.drive
        or any(part in ("", ".", "..") for part in relative.parts)
    ):
        return None
    try:
        resolved_drive = drive_root.resolve()
        candidate = (resolved_drive / relative).resolve()
    except OSError:
        return None
    if candidate == resolved_drive or resolved_drive not in candidate.parents:
        return None
    return candidate


def windows_local_drive_roots() -> list[Path]:
    """Enumerate local fixed/removable drive roots without spawning PowerShell."""
    if not is_windows_steam_supported():
        return []
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_logical_drives = kernel32.GetLogicalDrives
        get_logical_drives.argtypes = []
        get_logical_drives.restype = ctypes.c_uint32
        get_drive_type = kernel32.GetDriveTypeW
        get_drive_type.argtypes = [ctypes.c_wchar_p]
        get_drive_type.restype = ctypes.c_uint
        mask = int(get_logical_drives())
    except (AttributeError, OSError):
        log.exception("Could not enumerate local Windows drive roots")
        return []

    roots: list[Path] = []
    for index in range(26):
        if not mask & (1 << index):
            continue
        root = f"{chr(ord('A') + index)}:\\"
        # DRIVE_REMOVABLE=2, DRIVE_FIXED=3. Network and optical drives are
        # deliberately excluded so discovery cannot block on remote media.
        if int(get_drive_type(root)) in (2, 3):
            roots.append(Path(root))
    return roots


def xbox_library_roots(
    *,
    drive_roots: Iterable[str | os.PathLike] | None = None,
) -> list[Path]:
    """Return existing Xbox flat-file library roots from bounded drive hints."""
    drives = windows_local_drive_roots() if drive_roots is None else drive_roots
    candidates: list[Path] = []
    for drive in _unique_paths(drives):
        configured = _gaming_root_library(drive)
        if configured is not None:
            candidates.append(configured)
        candidates.append(drive / "XboxGames")

    libraries: list[Path] = []
    for candidate in _unique_paths(candidates):
        try:
            if candidate.is_dir():
                libraries.append(candidate)
        except OSError:
            continue
    return libraries


def _xbox_install_candidates(library: Path, game: ForzaGame) -> list[Path]:
    preferred = [library, library / game.full_name, library / game.short_name]
    children: list[Path] = []
    try:
        for child in islice(library.iterdir(), _MAX_XBOX_LIBRARY_CHILDREN):
            try:
                if child.is_dir():
                    children.append(child)
            except OSError:
                continue
    except OSError:
        return _unique_paths(preferred)

    target = _normalize_app_name(game.full_name)

    def score(path: Path) -> tuple[int, int, str]:
        name = _normalize_app_name(path.name)
        if name == target:
            rank = 0
        elif target in name or "forzahorizon" in name:
            rank = 1
        else:
            rank = 2
        return rank, len(name), name

    children.sort(key=score)
    return _unique_paths(preferred + children)


def discover_xbox_forza_install(
    game: str | ForzaGame,
    cached_path: str | os.PathLike = "",
    *,
    drive_roots: Iterable[str | os.PathLike] | None = None,
    library_roots: Iterable[str | os.PathLike] | None = None,
    required_directories: Iterable[str | os.PathLike] = (),
) -> ForzaInstall | None:
    """Discover one validated Xbox App flat-file install without recursion."""
    if (
        drive_roots is None
        and library_roots is None
        and not is_windows_steam_supported()
    ):
        return None
    definition = get_forza_game(game)
    required = tuple(required_directories)
    if cached_path:
        cached = validate_forza_root(
            definition,
            cached_path,
            source="Cached Xbox App path",
            required_directories=required,
        )
        if cached is not None:
            return cached

    libraries = (
        xbox_library_roots(drive_roots=drive_roots)
        if library_roots is None
        else _unique_paths(library_roots)
    )
    for library in libraries:
        try:
            if not library.is_dir():
                continue
            resolved_library = library.resolve()
        except OSError:
            continue
        for candidate in _xbox_install_candidates(library, definition):
            install = validate_forza_root(
                definition,
                candidate,
                source="Xbox App library",
                required_directories=required,
            )
            if install is not None and (
                install.root == resolved_library
                or resolved_library in install.root.parents
            ):
                return install
    return None


def steam_roots_from_registry() -> list[Path]:
    if not is_windows_steam_supported():
        return []
    try:
        import winreg
    except ImportError:
        return []
    locations = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", ("SteamPath", "SteamExe")),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", ("InstallPath",)),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", ("InstallPath",)),
    )
    roots: list[Path] = []
    for hive, key_name, values in locations:
        try:
            with winreg.OpenKey(hive, key_name) as key:
                for value_name in values:
                    try:
                        value = str(winreg.QueryValueEx(key, value_name)[0]).strip()
                    except OSError:
                        continue
                    if value:
                        path = Path(value)
                        roots.append(path.parent if path.suffix.lower() == ".exe" else path)
        except OSError:
            continue
    return _unique_paths(roots)


def steam_library_paths(steam_root: Path) -> list[Path]:
    libraries = [steam_root]
    text = _read_vdf(steam_root / "steamapps" / "libraryfolders.vdf")
    libraries.extend(
        Path(_vdf_unescape(value))
        for value in re.findall(r'"path"\s*"([^"\r\n]+)"', text, flags=re.IGNORECASE)
    )
    for value in re.findall(r'^\s*"\d+"\s*"([^"\r\n]+)"', text, flags=re.MULTILINE):
        candidate = _vdf_unescape(value)
        if re.match(r"^[A-Za-z]:[\\/]", candidate) or candidate.startswith("/"):
            libraries.append(Path(candidate))
    return _unique_paths(libraries)


def uninstall_locations_from_registry(game: str | ForzaGame) -> list[Path]:
    definition = get_forza_game(game)
    if not is_windows_steam_supported():
        return []
    try:
        import winreg
    except ImportError:
        return []
    subkey = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App "
        f"{definition.steam_app_id}"
    )
    locations: list[Path] = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (
            0,
            getattr(winreg, "KEY_WOW64_32KEY", 0),
            getattr(winreg, "KEY_WOW64_64KEY", 0),
        ):
            try:
                with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | view) as key:
                    value = str(winreg.QueryValueEx(key, "InstallLocation")[0]).strip()
            except OSError:
                continue
            if value:
                locations.append(Path(value))
    return _unique_paths(locations)


def validate_forza_root(
    game: str | ForzaGame,
    root: str | os.PathLike,
    *,
    source: str = "Manual",
    steam_language: str = "",
    required_directories: Iterable[str | os.PathLike] = (),
) -> ForzaInstall | None:
    definition = get_forza_game(game)
    path = Path(root).expanduser()
    if path.name.casefold() == definition.executable_name.casefold():
        path = path.parent
    # Xbox App commonly presents the user with the game wrapper while the
    # directly modifiable flat-file payload lives in its Content child. Accept
    # either exact selection without recursively searching unrelated folders.
    candidates = (path, path / "Content")
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            identity = str(resolved).casefold()
            if identity in seen:
                continue
            seen.add(identity)
            required = tuple(
                (resolved / Path(relative)).resolve()
                for relative in required_directories
            )
        except OSError:
            continue
        if not (resolved / definition.executable_name).is_file():
            continue
        if any(
            directory.parent != resolved and resolved not in directory.parents
            for directory in required
        ):
            continue
        if any(not directory.is_dir() for directory in required):
            continue
        return ForzaInstall(
            game=definition,
            root=resolved,
            source=source,
            steam_language=steam_language,
        )
    return None


def _manifest_install(
    game: ForzaGame,
    library: Path,
    required_directories: tuple[str | os.PathLike, ...],
) -> ForzaInstall | None:
    manifest = library / "steamapps" / f"appmanifest_{game.steam_app_id}.acf"
    text = _read_vdf(manifest)
    if not text:
        return None
    install_dir = _quoted_value(text, "installdir")
    if not install_dir:
        return None
    return validate_forza_root(
        game,
        library / "steamapps" / "common" / install_dir,
        source="Steam manifest",
        steam_language=_quoted_value(text, "language").casefold(),
        required_directories=required_directories,
    )


def discover_forza_install(
    game: str | ForzaGame,
    cached_path: str | os.PathLike = "",
    *,
    steam_roots: list[Path] | None = None,
    uninstall_locations: list[Path] | None = None,
    running_executables: list[Path] | None = None,
    manual_path: str | os.PathLike = "",
    required_directories: Iterable[str | os.PathLike] = (),
) -> ForzaInstall | None:
    """Discover one validated Steam installation without modifying the game."""
    definition = get_forza_game(game)
    required = tuple(required_directories)
    roots = steam_roots_from_registry() if steam_roots is None else steam_roots
    for root in _unique_paths(roots):
        for library in steam_library_paths(root):
            install = _manifest_install(definition, library, required)
            if install is not None:
                return install

    if cached_path:
        install = validate_forza_root(
            definition,
            cached_path,
            source="Cached path",
            required_directories=required,
        )
        if install is not None:
            return install

    locations = (
        uninstall_locations_from_registry(definition)
        if uninstall_locations is None
        else uninstall_locations
    )
    for location in _unique_paths(locations):
        install = validate_forza_root(
            definition,
            location,
            source="Steam uninstall registry",
            required_directories=required,
        )
        if install is not None:
            return install

    if running_executables is None:
        process = find_game_process((), exact_name=definition.executable_name)
        running_executables = [Path(process.exe)] if process and process.exe else []
    for executable in _unique_paths(running_executables):
        install = validate_forza_root(
            definition,
            executable,
            source="Running game",
            required_directories=required,
        )
        if install is not None:
            return install

    if manual_path:
        return validate_forza_root(
            definition,
            manual_path,
            source="Manual",
            required_directories=required,
        )
    return None


def is_forza_game_running(
    game: str | ForzaGame,
    install: ForzaInstall | object | None = None,
    *,
    strict: bool = False,
) -> bool:
    definition = get_forza_game(game)
    process = find_game_process(
        (),
        exact_name=definition.executable_name,
        strict=strict,
    )
    if process is None:
        return False
    root = getattr(install, "root", None)
    if root is None or not process.exe:
        return True
    try:
        return Path(process.exe).resolve() == (Path(root) / definition.executable_name).resolve()
    except OSError:
        return True


def _open_steam_uri(uri: str) -> None:
    opener = getattr(os, "startfile", None)
    if opener is None:
        raise OSError("Windows URI handler is unavailable")
    opener(uri)


def _ensure_not_running(
    game: str | ForzaGame,
    install: ForzaInstall | object | None = None,
) -> None:
    definition = get_forza_game(game)
    try:
        running = is_forza_game_running(definition, install, strict=True)
    except ProcessScanError as exc:
        raise ForzaLaunchError(
            f"Could not verify whether {definition.short_name} is running: {exc}"
        ) from exc
    if running:
        raise ForzaLaunchError(f"{definition.short_name} is already running")


def launch_forza_via_steam(
    install: ForzaInstall,
    *,
    open_uri: Callable[[str], None] | None = None,
) -> None:
    """Ask Steam to launch one validated game without invoking a shell."""
    if not is_windows_steam_supported():
        raise ForzaLaunchError("Forza Horizon launch supports Windows Steam only")
    validated = validate_forza_root(
        install.game,
        install.root,
        source=install.source,
        steam_language=install.steam_language,
    )
    if validated is None:
        raise ForzaLaunchError(f"{install.game.short_name} installation is no longer valid")
    _ensure_not_running(install.game, validated)
    try:
        (open_uri or _open_steam_uri)(install.game.steam_run_uri)
    except OSError as exc:
        raise ForzaLaunchError(
            f"Could not ask Steam to launch {install.game.short_name}: {exc}"
        ) from exc


def launch_forza_via_xbox_app(
    game: str | ForzaGame,
    *,
    entries: Iterable[XboxStartApp] | None = None,
    open_target: Callable[[str], None] | None = None,
) -> XboxLaunchResult:
    """Launch an installed Xbox game by AUMID, or open its Xbox product page.

    GDK/MSIXVC packages must be activated through their registered identity;
    directly starting the executable bypasses Gaming Services. If Windows does
    not expose an installed AUMID, the explicit fallback opens the matching
    product page in Xbox App so the user can install or press Play there.
    """
    definition = get_forza_game(game)
    if not is_windows_steam_supported():
        raise ForzaLaunchError("Forza Horizon launch supports Windows only")
    _ensure_not_running(definition)
    aumid = discover_xbox_aumid(definition, entries=entries)
    target = f"shell:AppsFolder\\{aumid}" if aumid else definition.xbox_app_uri
    try:
        (open_target or _open_steam_uri)(target)
    except OSError as exc:
        raise ForzaLaunchError(
            f"Could not ask Xbox App to open {definition.short_name}: {exc}"
        ) from exc
    return XboxLaunchResult(direct=bool(aumid), target=target)
