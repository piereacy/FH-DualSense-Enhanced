"""Explicit, reversible FH6 DualSense controller-icon MOD installation."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from modules.config import paths

from .game_launch import is_forza_game_running

log = logging.getLogger("fhds.controller_icons")

MOD_VERSION = "2.1.1"
MOD_SHA256 = "9677e50bf04276a9606956819d7760588ea7b986cfafebc70396f35630c53a61"
MOD_AUTHOR = "@hotline1337"
MOD_URL = "https://www.nexusmods.com/forzahorizon6/mods/2"
TARGETS = (
    Path("media/UI/Textures/Data_Bound/ControllerIcons.zip"),
    Path("media/UI/Textures/HiRes/Data_Bound/ControllerIcons.zip"),
)


class ControllerIconState(str, Enum):
    NOT_FOUND = "not_found"
    READY = "ready"
    INSTALLED = "installed"
    PARTIAL = "partial"
    ASSET_ERROR = "asset_error"


@dataclass(frozen=True, slots=True)
class ControllerIconInspection:
    root: Path | None
    state: ControllerIconState
    has_backup: bool = False
    detail: str = ""


class ControllerIconModError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_controller_icon_root(root: str | os.PathLike) -> Path | None:
    candidate = Path(root).expanduser()
    if candidate.name.casefold() == "forzahorizon6.exe":
        candidate = candidate.parent
    try:
        resolved = candidate.resolve()
        targets = tuple((resolved / relative).resolve() for relative in TARGETS)
    except OSError:
        return None
    if any(target.parent != resolved and resolved not in target.parents for target in targets):
        return None
    if not all(target.is_file() for target in targets):
        return None
    # Steam and current Xbox App packages both expose this game executable.
    if not (resolved / "ForzaHorizon6.exe").is_file():
        return None
    return resolved


def _backup_dir(root: Path, data_dir: Path) -> Path:
    identity = hashlib.sha256(str(root).casefold().encode("utf-8")).hexdigest()[:16]
    return data_dir / "controller_icon_backups" / identity


def _backup_path(backup_dir: Path, index: int) -> Path:
    return backup_dir / f"original_{index}.zip"


def _manifest_path(backup_dir: Path) -> Path:
    return backup_dir / "manifest.json"


def _read_manifest(root: Path, backup_dir: Path) -> dict | None:
    try:
        manifest = json.loads(_manifest_path(backup_dir).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(manifest, dict) or manifest.get("root") != str(root):
        return None
    originals = manifest.get("original_sha256")
    if not isinstance(originals, list) or len(originals) != len(TARGETS):
        return None
    for index, expected in enumerate(originals):
        backup = _backup_path(backup_dir, index)
        try:
            if not backup.is_file() or _sha256(backup) != expected:
                return None
        except OSError:
            return None
    return manifest


def _asset_hash(asset_path: Path) -> str:
    try:
        actual = _sha256(asset_path)
    except OSError as exc:
        raise ControllerIconModError(f"Bundled controller-icon MOD is unavailable: {exc}") from exc
    if actual != MOD_SHA256:
        raise ControllerIconModError("Bundled controller-icon MOD failed SHA-256 verification")
    return actual


def inspect_controller_icons(
    root: str | os.PathLike | None,
    *,
    data_dir: Path = paths.DATA,
    asset_path: Path = paths.CONTROLLER_ICON_MOD,
) -> ControllerIconInspection:
    if not root or (validated := validate_controller_icon_root(root)) is None:
        return ControllerIconInspection(None, ControllerIconState.NOT_FOUND)
    backup_dir = _backup_dir(validated, data_dir)
    has_backup = _read_manifest(validated, backup_dir) is not None
    try:
        mod_hash = _asset_hash(asset_path)
        matches = [
            _sha256(validated / relative) == mod_hash
            for relative in TARGETS
        ]
    except (OSError, ControllerIconModError) as exc:
        return ControllerIconInspection(
            validated,
            ControllerIconState.ASSET_ERROR,
            has_backup,
            str(exc),
        )
    if all(matches):
        state = ControllerIconState.INSTALLED
    elif any(matches):
        state = ControllerIconState.PARTIAL
    else:
        state = ControllerIconState.READY
    return ControllerIconInspection(validated, state, has_backup)


def _atomic_copy(source: Path, target: Path) -> None:
    temporary = target.with_name(f".{target.name}.fhds-tmp")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_bytes(payload: bytes, target: Path) -> None:
    temporary = target.with_name(f".{target.name}.fhds-tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _write_backup(root: Path, backup_dir: Path) -> dict:
    backup_dir.mkdir(parents=True, exist_ok=True)
    hashes: list[str] = []
    for index, relative in enumerate(TARGETS):
        source = root / relative
        backup = _backup_path(backup_dir, index)
        _atomic_copy(source, backup)
        hashes.append(_sha256(backup))
    manifest = {
        "version": 1,
        "root": str(root),
        "mod_version": MOD_VERSION,
        "mod_sha256": MOD_SHA256,
        "original_sha256": hashes,
    }
    manifest_path = _manifest_path(backup_dir)
    temporary = manifest_path.with_suffix(".json.tmp")
    try:
        temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        os.replace(temporary, manifest_path)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest


def _ensure_game_closed(game_running: Callable[[], bool]) -> None:
    try:
        running = game_running()
    except Exception as exc:
        raise ControllerIconModError(f"Could not verify whether FH6 is running: {exc}") from exc
    if running:
        raise ControllerIconModError("Close FH6 before changing controller icon files")


def _restore_from_manifest(root: Path, backup_dir: Path, manifest: dict) -> None:
    targets = [root / relative for relative in TARGETS]
    previous = [target.read_bytes() for target in targets]
    try:
        for index, target in enumerate(targets):
            _atomic_copy(_backup_path(backup_dir, index), target)
    except OSError as exc:
        for payload, target in zip(previous, targets, strict=True):
            try:
                _atomic_bytes(payload, target)
            except OSError:
                log.exception("Controller-icon rollback failed for %s", target)
        raise ControllerIconModError(f"Could not restore original controller icons: {exc}") from exc
    restored = [_sha256(target) for target in targets]
    if restored != manifest["original_sha256"]:
        raise ControllerIconModError("Restored controller icons failed verification")


def install_controller_icons(
    root: str | os.PathLike,
    *,
    data_dir: Path = paths.DATA,
    asset_path: Path = paths.CONTROLLER_ICON_MOD,
    game_running: Callable[[], bool] = lambda: is_forza_game_running("fh6"),
) -> ControllerIconInspection:
    validated = validate_controller_icon_root(root)
    if validated is None:
        raise ControllerIconModError("The selected folder is not a valid FH6 installation")
    _ensure_game_closed(game_running)
    mod_hash = _asset_hash(asset_path)
    targets = [validated / relative for relative in TARGETS]
    current_hashes = [_sha256(target) for target in targets]
    if all(value == mod_hash for value in current_hashes):
        return inspect_controller_icons(validated, data_dir=data_dir, asset_path=asset_path)

    backup_dir = _backup_dir(validated, data_dir)
    manifest = _read_manifest(validated, backup_dir)
    partial = any(value == mod_hash for value in current_hashes)
    if partial:
        if manifest is None:
            raise ControllerIconModError(
                "Only one icon archive is modified and no complete original backup exists"
            )
        _restore_from_manifest(validated, backup_dir, manifest)
        current_hashes = manifest["original_sha256"]

    # A game update can replace native files after a previous install. Refresh
    # the backup only when both current files are clearly native.
    if manifest is None or current_hashes != manifest["original_sha256"]:
        manifest = _write_backup(validated, backup_dir)

    try:
        for target in targets:
            _atomic_copy(asset_path, target)
    except OSError as exc:
        try:
            _restore_from_manifest(validated, backup_dir, manifest)
        except ControllerIconModError:
            log.exception("Controller-icon install rollback failed")
        raise ControllerIconModError(f"Could not install controller icons: {exc}") from exc
    if any(_sha256(target) != mod_hash for target in targets):
        _restore_from_manifest(validated, backup_dir, manifest)
        raise ControllerIconModError("Installed controller icons failed verification")
    return inspect_controller_icons(validated, data_dir=data_dir, asset_path=asset_path)


def restore_controller_icons(
    root: str | os.PathLike,
    *,
    data_dir: Path = paths.DATA,
    asset_path: Path = paths.CONTROLLER_ICON_MOD,
    game_running: Callable[[], bool] = lambda: is_forza_game_running("fh6"),
) -> ControllerIconInspection:
    validated = validate_controller_icon_root(root)
    if validated is None:
        raise ControllerIconModError("The selected folder is not a valid FH6 installation")
    _ensure_game_closed(game_running)
    backup_dir = _backup_dir(validated, data_dir)
    manifest = _read_manifest(validated, backup_dir)
    if manifest is None:
        raise ControllerIconModError("No verified original controller-icon backup is available")
    _restore_from_manifest(validated, backup_dir, manifest)
    return inspect_controller_icons(validated, data_dir=data_dir, asset_path=asset_path)
