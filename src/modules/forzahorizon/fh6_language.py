"""Windows Steam FH6 language archive discovery and explicit safe swapping."""

from __future__ import annotations

import logging
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .process_watch import find_game_process

log = logging.getLogger("fhds.fh6_language")

FH6_APP_ID = "2483190"
STEAM_RUN_URI = f"steam://run/{FH6_APP_ID}"
GAME_EXE = "ForzaHorizon6.exe"
TABLES_RELATIVE = Path("media") / "Stripped" / "StringTables"
CHS_NAME = "CHS.zip"
EN_NAME = "EN.zip"
TEMP_NAME = "CHS.zip.fhds-swap.tmp"


class SteamLanguageState(StrEnum):
    ENGLISH = "english"
    OTHER = "other"
    UNKNOWN = "unknown"


class ArchiveLanguage(StrEnum):
    CHINESE = "chinese"
    ENGLISH = "english"
    UNKNOWN = "unknown"


class FH6LanguageState(StrEnum):
    NOT_FOUND = "not_found"
    NATIVE = "native"
    SWAPPED = "swapped"
    RECOVERY_REQUIRED = "recovery_required"
    MISSING = "missing"
    UNKNOWN = "unknown"
    CORRUPT = "corrupt"


@dataclass(frozen=True, slots=True)
class FH6Install:
    root: Path
    string_tables: Path
    source: str
    steam_language: str = ""

    @property
    def steam_language_state(self) -> SteamLanguageState:
        language = self.steam_language.strip().casefold()
        if language == "english":
            return SteamLanguageState.ENGLISH
        if language:
            return SteamLanguageState.OTHER
        return SteamLanguageState.UNKNOWN


@dataclass(frozen=True, slots=True)
class LanguageInspection:
    state: FH6LanguageState
    install: FH6Install | None
    chs_language: ArchiveLanguage = ArchiveLanguage.UNKNOWN
    en_language: ArchiveLanguage = ArchiveLanguage.UNKNOWN
    temp_language: ArchiveLanguage = ArchiveLanguage.UNKNOWN
    detail: str = ""

    @property
    def can_repair(self) -> bool:
        if self.state is not FH6LanguageState.RECOVERY_REQUIRED:
            return False
        identities = (self.chs_language, self.en_language, self.temp_language)
        return identities.count(ArchiveLanguage.CHINESE) == 1 and identities.count(
            ArchiveLanguage.ENGLISH
        ) == 1


class FH6LanguageError(RuntimeError):
    pass


class InvalidArchiveError(FH6LanguageError):
    pass


def is_windows_steam_supported() -> bool:
    return sys.platform.startswith("win")


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


def _unique_paths(paths) -> list[Path]:
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


def steam_roots_from_registry() -> list[Path]:
    if not sys.platform.startswith("win"):
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
    # Legacy Steam format: "1" "D:\\SteamLibrary".
    for value in re.findall(r'^\s*"\d+"\s*"([^"\r\n]+)"', text, flags=re.MULTILINE):
        candidate = _vdf_unescape(value)
        if re.match(r"^[A-Za-z]:[\\/]", candidate) or candidate.startswith("/"):
            libraries.append(Path(candidate))
    return _unique_paths(libraries)


def uninstall_locations_from_registry() -> list[Path]:
    if not sys.platform.startswith("win"):
        return []
    try:
        import winreg
    except ImportError:
        return []
    subkey = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {FH6_APP_ID}"
    locations: list[Path] = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (0, getattr(winreg, "KEY_WOW64_32KEY", 0), getattr(winreg, "KEY_WOW64_64KEY", 0)):
            try:
                with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | view) as key:
                    value = str(winreg.QueryValueEx(key, "InstallLocation")[0]).strip()
            except OSError:
                continue
            if value:
                locations.append(Path(value))
    return _unique_paths(locations)


def validate_game_root(
    root: str | os.PathLike,
    *,
    source: str = "Manual",
    steam_language: str = "",
) -> FH6Install | None:
    path = Path(root).expanduser()
    if path.name.casefold() == GAME_EXE.casefold():
        path = path.parent
    try:
        resolved = path.resolve()
        tables = (resolved / TABLES_RELATIVE).resolve()
    except OSError:
        return None
    if not (resolved / GAME_EXE).is_file() or not tables.is_dir():
        return None
    return FH6Install(
        root=resolved,
        string_tables=tables,
        source=source,
        steam_language=steam_language,
    )


def _manifest_install(library: Path) -> FH6Install | None:
    manifest = library / "steamapps" / f"appmanifest_{FH6_APP_ID}.acf"
    text = _read_vdf(manifest)
    if not text:
        return None
    install_dir = _quoted_value(text, "installdir")
    if not install_dir:
        return None
    language = _quoted_value(text, "language").casefold()
    return validate_game_root(
        library / "steamapps" / "common" / install_dir,
        source="Steam manifest",
        steam_language=language,
    )


def discover_fh6_install(
    cached_path: str | os.PathLike = "",
    *,
    steam_roots: list[Path] | None = None,
    uninstall_locations: list[Path] | None = None,
    running_executables: list[Path] | None = None,
    manual_path: str | os.PathLike = "",
) -> FH6Install | None:
    if not is_windows_steam_supported():
        return None
    roots = steam_roots_from_registry() if steam_roots is None else steam_roots
    for root in _unique_paths(roots):
        for library in steam_library_paths(root):
            install = _manifest_install(library)
            if install is not None:
                return install

    if cached_path:
        install = validate_game_root(cached_path, source="Cached path")
        if install is not None:
            return install

    locations = (
        uninstall_locations_from_registry()
        if uninstall_locations is None
        else uninstall_locations
    )
    for location in _unique_paths(locations):
        install = validate_game_root(location, source="Steam uninstall registry")
        if install is not None:
            return install

    if running_executables is None:
        process = find_game_process((), exact_name=GAME_EXE)
        running_executables = [Path(process.exe)] if process and process.exe else []
    for executable in _unique_paths(running_executables):
        install = validate_game_root(executable, source="Running game")
        if install is not None:
            return install

    if manual_path:
        return validate_game_root(manual_path, source="Manual")
    return None


def is_fh6_running(install: FH6Install | None = None) -> bool:
    process = find_game_process((), exact_name=GAME_EXE)
    if process is None:
        return False
    if install is None or not process.exe:
        return True
    try:
        return Path(process.exe).resolve() == (install.root / GAME_EXE).resolve()
    except OSError:
        return True


def _archive_paths(install: FH6Install) -> tuple[Path, Path, Path]:
    tables = install.string_tables.resolve()
    paths = tuple((tables / name).resolve() for name in (CHS_NAME, EN_NAME, TEMP_NAME))
    if any(path.parent != tables for path in paths):
        raise FH6LanguageError("Language archive path escaped StringTables")
    return paths  # type: ignore[return-value]


def classify_archive(path: Path, *, full_check: bool = False) -> ArchiveLanguage:
    try:
        with zipfile.ZipFile(path) as archive:
            if full_check:
                bad_entry = archive.testzip()
                if bad_entry:
                    raise InvalidArchiveError(f"Corrupt ZIP entry: {bad_entry}")
            entries = [
                info for info in archive.infolist()
                if info.filename.lower().endswith(".str") and 128 <= info.file_size <= 131072
            ]
            preferred = [
                info for info in entries
                if Path(info.filename).name.casefold() == "accessibilityautodrive.str"
            ]
            remaining = sorted(
                (info for info in entries if info not in preferred),
                key=lambda info: (info.file_size, info.filename.casefold()),
            )
            samples = (preferred + remaining)[:8]
            payload = b"".join(archive.read(info)[:65536] for info in samples)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise InvalidArchiveError(f"Could not read {path.name}: {exc}") from exc
    text = payload.decode("utf-8", errors="ignore")
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", text))
    latin_words = len(re.findall(r"\b[A-Za-z]{3,}\b", text))
    if cjk_count >= 8:
        return ArchiveLanguage.CHINESE
    if cjk_count == 0 and latin_words >= 8:
        return ArchiveLanguage.ENGLISH
    return ArchiveLanguage.UNKNOWN


def inspect_language_state(install: FH6Install | None) -> LanguageInspection:
    if install is None:
        return LanguageInspection(FH6LanguageState.NOT_FOUND, None)
    try:
        chs, en, temp = _archive_paths(install)
    except (OSError, FH6LanguageError) as exc:
        return LanguageInspection(FH6LanguageState.UNKNOWN, install, detail=str(exc))
    existing = [path for path in (chs, en, temp) if path.is_file()]
    if temp.is_file():
        identities: dict[Path, ArchiveLanguage] = {}
        try:
            for path in existing:
                identities[path] = classify_archive(path)
        except InvalidArchiveError as exc:
            return LanguageInspection(FH6LanguageState.CORRUPT, install, detail=str(exc))
        state = (
            FH6LanguageState.RECOVERY_REQUIRED
            if len(existing) == 2
            and set(identities.values()) == {
                ArchiveLanguage.CHINESE,
                ArchiveLanguage.ENGLISH,
            }
            else FH6LanguageState.UNKNOWN
        )
        return LanguageInspection(
            state,
            install,
            identities.get(chs, ArchiveLanguage.UNKNOWN),
            identities.get(en, ArchiveLanguage.UNKNOWN),
            identities.get(temp, ArchiveLanguage.UNKNOWN),
            "Interrupted language swap detected",
        )
    if not chs.is_file() or not en.is_file():
        return LanguageInspection(
            FH6LanguageState.MISSING,
            install,
            detail="CHS.zip or EN.zip is missing",
        )
    try:
        chs_language = classify_archive(chs)
        en_language = classify_archive(en)
    except InvalidArchiveError as exc:
        return LanguageInspection(FH6LanguageState.CORRUPT, install, detail=str(exc))
    if (chs_language, en_language) == (
        ArchiveLanguage.CHINESE,
        ArchiveLanguage.ENGLISH,
    ):
        state = FH6LanguageState.NATIVE
    elif (chs_language, en_language) == (
        ArchiveLanguage.ENGLISH,
        ArchiveLanguage.CHINESE,
    ):
        state = FH6LanguageState.SWAPPED
    else:
        state = FH6LanguageState.UNKNOWN
    return LanguageInspection(state, install, chs_language, en_language)


def _validated_install(install: FH6Install) -> FH6Install:
    if not is_windows_steam_supported():
        raise FH6LanguageError("FH6 integration supports Windows Steam only")
    validated = validate_game_root(
        install.root,
        source=install.source,
        steam_language=install.steam_language,
    )
    if validated is None or validated.string_tables != install.string_tables.resolve():
        raise FH6LanguageError("FH6 installation path is no longer valid")
    return validated


def _guard_not_running(install: FH6Install) -> None:
    if is_fh6_running(install):
        raise FH6LanguageError("Close Forza Horizon 6 before changing language archives")


def _open_steam_uri(uri: str) -> None:
    opener = getattr(os, "startfile", None)
    if opener is None:
        raise OSError("Windows URI handler is unavailable")
    opener(uri)


def launch_fh6_via_steam(install: FH6Install) -> None:
    """Ask Steam to launch the validated FH6 install without invoking a shell."""
    validated = _validated_install(install)
    if is_fh6_running(validated):
        raise FH6LanguageError("FH6 is already running")
    try:
        _open_steam_uri(STEAM_RUN_URI)
    except OSError as exc:
        raise FH6LanguageError(f"Could not ask Steam to launch FH6: {exc}") from exc


def _rename(source: Path, destination: Path) -> None:
    source.rename(destination)


def _perform_three_step_swap(install: FH6Install) -> None:
    chs, en, temp = _archive_paths(install)
    completed: list[tuple[Path, Path]] = []
    steps = ((chs, temp), (en, chs), (temp, en))
    try:
        for source, destination in steps:
            _guard_not_running(install)
            if not source.is_file() or destination.exists():
                raise FH6LanguageError(
                    f"Unsafe swap state before {source.name} -> {destination.name}"
                )
            _rename(source, destination)
            completed.append((source, destination))
    except Exception as exc:
        rollback_errors: list[str] = []
        for source, destination in reversed(completed):
            try:
                if destination.is_file() and not source.exists():
                    _rename(destination, source)
            except Exception as rollback_exc:
                rollback_errors.append(str(rollback_exc))
        detail = f"Language archive swap failed: {exc}"
        if rollback_errors:
            detail += "; rollback failed: " + "; ".join(rollback_errors)
        raise FH6LanguageError(detail) from exc


def enable_chinese_text_english_voice(
    install: FH6Install,
    *,
    allow_unknown_steam_language: bool = False,
) -> LanguageInspection:
    install = _validated_install(install)
    if install.steam_language_state is SteamLanguageState.OTHER:
        raise FH6LanguageError("Set the FH6 Steam language to English first")
    if (
        install.steam_language_state is SteamLanguageState.UNKNOWN
        and not allow_unknown_steam_language
    ):
        raise FH6LanguageError("Steam language could not be verified as English")
    _guard_not_running(install)
    inspection = inspect_language_state(install)
    if inspection.state is not FH6LanguageState.NATIVE:
        raise FH6LanguageError(f"Expected native archive state, found {inspection.state.value}")
    chs, en, _temp = _archive_paths(install)
    if classify_archive(chs, full_check=True) is not ArchiveLanguage.CHINESE:
        raise FH6LanguageError("CHS.zip could not be verified as Chinese")
    if classify_archive(en, full_check=True) is not ArchiveLanguage.ENGLISH:
        raise FH6LanguageError("EN.zip could not be verified as English")
    _perform_three_step_swap(install)
    result = inspect_language_state(install)
    if result.state is not FH6LanguageState.SWAPPED:
        raise FH6LanguageError("Archive swap completed but the resulting state is unknown")
    return result


def restore_native_language(install: FH6Install) -> LanguageInspection:
    install = _validated_install(install)
    _guard_not_running(install)
    inspection = inspect_language_state(install)
    if inspection.state is not FH6LanguageState.SWAPPED:
        raise FH6LanguageError(f"Expected swapped archive state, found {inspection.state.value}")
    chs, en, _temp = _archive_paths(install)
    if classify_archive(chs, full_check=True) is not ArchiveLanguage.ENGLISH:
        raise FH6LanguageError("CHS.zip could not be verified as English")
    if classify_archive(en, full_check=True) is not ArchiveLanguage.CHINESE:
        raise FH6LanguageError("EN.zip could not be verified as Chinese")
    _perform_three_step_swap(install)
    result = inspect_language_state(install)
    if result.state is not FH6LanguageState.NATIVE:
        raise FH6LanguageError("Restore completed but the resulting state is unknown")
    return result


def repair_native_language(install: FH6Install) -> LanguageInspection:
    install = _validated_install(install)
    _guard_not_running(install)
    inspection = inspect_language_state(install)
    if not inspection.can_repair:
        raise FH6LanguageError("Interrupted swap cannot be repaired safely")
    chs, en, temp = _archive_paths(install)
    identities = {
        path: classify_archive(path, full_check=True)
        for path in (chs, en, temp)
        if path.is_file()
    }
    chinese = next(path for path, language in identities.items() if language is ArchiveLanguage.CHINESE)
    english = next(path for path, language in identities.items() if language is ArchiveLanguage.ENGLISH)
    moves: list[tuple[Path, Path]] = []
    if not chs.exists():
        moves.append((chinese, chs))
        if chinese == en:
            moves.append((english, en))
    elif not en.exists():
        moves.append((english, en))
        if english == chs:
            moves.append((chinese, chs))
    else:
        raise FH6LanguageError("Recovery temporary file is not in a safe two-file state")
    completed: list[tuple[Path, Path]] = []
    try:
        for source, destination in moves:
            _guard_not_running(install)
            if not source.is_file() or destination.exists():
                raise FH6LanguageError(
                    f"Unsafe recovery state before {source.name} -> {destination.name}"
                )
            _rename(source, destination)
            completed.append((source, destination))
    except Exception as exc:
        for source, destination in reversed(completed):
            try:
                if destination.is_file() and not source.exists():
                    _rename(destination, source)
            except Exception:
                log.exception("FH6 language recovery rollback failed")
        raise FH6LanguageError(f"Language archive recovery failed: {exc}") from exc
    result = inspect_language_state(install)
    if result.state is not FH6LanguageState.NATIVE:
        raise FH6LanguageError("Recovery completed but native state was not restored")
    return result
