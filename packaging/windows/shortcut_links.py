"""Native Windows Shell Link migration used by the standalone update helper."""
from __future__ import annotations

import ctypes
import os
import uuid
from contextlib import nullcontext
from pathlib import Path
from typing import Callable, Iterable


class ShortcutError(OSError):
    pass


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, value: str) -> "GUID":
        raw = uuid.UUID(value).bytes_le
        return cls.from_buffer_copy(raw)


class WIN32_FIND_DATAW(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", ctypes.c_uint32),
        ("ftCreationTime", ctypes.c_uint32 * 2),
        ("ftLastAccessTime", ctypes.c_uint32 * 2),
        ("ftLastWriteTime", ctypes.c_uint32 * 2),
        ("nFileSizeHigh", ctypes.c_uint32),
        ("nFileSizeLow", ctypes.c_uint32),
        ("dwReserved0", ctypes.c_uint32),
        ("dwReserved1", ctypes.c_uint32),
        ("cFileName", ctypes.c_wchar * 260),
        ("cAlternateFileName", ctypes.c_wchar * 14),
    ]


CLSID_SHELL_LINK = GUID.parse("00021401-0000-0000-C000-000000000046")
IID_ISHELL_LINK_W = GUID.parse("000214F9-0000-0000-C000-000000000046")
IID_IPERSIST_FILE = GUID.parse("0000010B-0000-0000-C000-000000000046")

FOLDER_DESKTOP = GUID.parse("B4BFCC3A-DB2C-424C-B029-7FE99A87C641")
FOLDER_PROGRAMS = GUID.parse("A77F5D77-2E2B-44C3-A6A2-ABA601054A51")
FOLDER_ROAMING_APP_DATA = GUID.parse("3EB685DB-65F9-4CF6-A03A-E3EF65729F3D")


def _failed(hresult: int) -> bool:
    return ctypes.c_long(hresult).value < 0


def _check(hresult: int, operation: str) -> None:
    if _failed(hresult):
        raise ShortcutError(f"{operation} failed with HRESULT 0x{hresult & 0xFFFFFFFF:08X}")


def _method(pointer: ctypes.c_void_p, index: int, restype, *argtypes):
    vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    address = vtable[index]
    prototype = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return prototype(address)


class _ComApartment:
    def __init__(self):
        self._uninitialize = False

    def __enter__(self):
        if os.name != "nt":
            raise ShortcutError("Windows Shell Links are available only on Windows")
        ole32 = ctypes.OleDLL("ole32")
        result = int(ole32.CoInitializeEx(None, 0x2))
        # S_OK and S_FALSE both require a balancing CoUninitialize. A thread
        # already initialized in another apartment can still use its existing
        # apartment for these in-proc shell objects.
        if result in (0, 1):
            self._uninitialize = True
        elif result != -2147417850:  # RPC_E_CHANGED_MODE
            _check(result, "CoInitializeEx")
        return self

    def __exit__(self, *_args):
        if self._uninitialize:
            ctypes.OleDLL("ole32").CoUninitialize()


class ShellLink:
    """Small IShellLinkW/IPersistFile wrapper that preserves untouched fields."""

    def __init__(self, path: Path):
        if os.name != "nt":
            raise ShortcutError("Windows Shell Links are available only on Windows")
        self.path = Path(path).resolve()
        self._link = ctypes.c_void_p()
        self._persist = ctypes.c_void_p()
        ole32 = ctypes.OleDLL("ole32")
        co_create = ole32.CoCreateInstance
        co_create.argtypes = (
            ctypes.POINTER(GUID),
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(GUID),
            ctypes.POINTER(ctypes.c_void_p),
        )
        co_create.restype = ctypes.c_long
        _check(
            int(
                co_create(
                    ctypes.byref(CLSID_SHELL_LINK),
                    None,
                    0x1,
                    ctypes.byref(IID_ISHELL_LINK_W),
                    ctypes.byref(self._link),
                )
            ),
            "CoCreateInstance(CLSID_ShellLink)",
        )
        try:
            query_interface = _method(
                self._link,
                0,
                ctypes.c_long,
                ctypes.POINTER(GUID),
                ctypes.POINTER(ctypes.c_void_p),
            )
            _check(
                int(query_interface(self._link, ctypes.byref(IID_IPERSIST_FILE), ctypes.byref(self._persist))),
                "QueryInterface(IPersistFile)",
            )
            load = _method(self._persist, 5, ctypes.c_long, ctypes.c_wchar_p, ctypes.c_uint32)
            _check(int(load(self._persist, str(self.path), 0)), "IPersistFile.Load")
        except Exception:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    @staticmethod
    def _release(pointer: ctypes.c_void_p) -> None:
        if pointer and pointer.value:
            release = _method(pointer, 2, ctypes.c_ulong)
            release(pointer)
            pointer.value = None

    def close(self) -> None:
        self._release(self._persist)
        self._release(self._link)

    def target(self) -> str:
        buffer = ctypes.create_unicode_buffer(32768)
        find_data = WIN32_FIND_DATAW()
        get_path = _method(
            self._link,
            3,
            ctypes.c_long,
            ctypes.c_wchar_p,
            ctypes.c_int,
            ctypes.POINTER(WIN32_FIND_DATAW),
            ctypes.c_uint32,
        )
        _check(
            int(get_path(self._link, buffer, len(buffer), ctypes.byref(find_data), 0)),
            "IShellLinkW.GetPath",
        )
        return buffer.value

    def set_target(self, value: Path) -> None:
        set_path = _method(self._link, 20, ctypes.c_long, ctypes.c_wchar_p)
        _check(int(set_path(self._link, str(Path(value)))), "IShellLinkW.SetPath")

    def icon(self) -> tuple[str, int]:
        buffer = ctypes.create_unicode_buffer(32768)
        index = ctypes.c_int()
        get_icon = _method(
            self._link,
            16,
            ctypes.c_long,
            ctypes.c_wchar_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        )
        _check(
            int(get_icon(self._link, buffer, len(buffer), ctypes.byref(index))),
            "IShellLinkW.GetIconLocation",
        )
        return buffer.value, int(index.value)

    def set_icon(self, value: Path, index: int) -> None:
        set_icon = _method(self._link, 17, ctypes.c_long, ctypes.c_wchar_p, ctypes.c_int)
        _check(int(set_icon(self._link, str(Path(value)), int(index))), "IShellLinkW.SetIconLocation")

    def save(self) -> None:
        save = _method(self._persist, 6, ctypes.c_long, ctypes.c_wchar_p, ctypes.c_int)
        _check(int(save(self._persist, str(self.path), 1)), "IPersistFile.Save")


def _known_folder(folder_id: GUID) -> Path | None:
    if os.name != "nt":
        return None
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    get_path = shell32.SHGetKnownFolderPath
    get_path.argtypes = (
        ctypes.POINTER(GUID),
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_wchar_p),
    )
    get_path.restype = ctypes.c_long
    value = ctypes.c_wchar_p()
    result = int(get_path(ctypes.byref(folder_id), 0, None, ctypes.byref(value)))
    if _failed(result):
        return None
    try:
        return Path(value.value).resolve() if value.value else None
    finally:
        free = ctypes.OleDLL("ole32").CoTaskMemFree
        free.argtypes = (ctypes.c_void_p,)
        free.restype = None
        free(value)


def known_shortcut_paths() -> tuple[Path, ...]:
    roots: list[Path] = []
    for folder in (FOLDER_DESKTOP, FOLDER_PROGRAMS):
        path = _known_folder(folder)
        if path is not None:
            roots.append(path)
    roaming = _known_folder(FOLDER_ROAMING_APP_DATA)
    if roaming is not None:
        pinned = roaming / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned"
        roots.extend((pinned / "TaskBar", pinned / "ImplicitAppShortcuts"))

    found: dict[str, Path] = {}
    for root in roots:
        try:
            for shortcut in root.rglob("*.lnk"):
                found.setdefault(os.path.normcase(str(shortcut.resolve())), shortcut.resolve())
        except OSError as exc:
            # If a known shortcut location cannot be enumerated, deleting the
            # old executable could silently strand a link we never inspected.
            raise ShortcutError(f"could not enumerate shortcut directory: {root}") from exc
    return tuple(found[key] for key in sorted(found))


def _normalized(value: str | Path) -> str:
    text = os.path.expandvars(str(value)).strip()
    if not text:
        return ""
    return os.path.normcase(os.path.normpath(os.path.abspath(text)))


def _notify_changed(path: Path) -> None:
    if os.name != "nt":
        return
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    notify = shell32.SHChangeNotify
    notify.argtypes = (ctypes.c_long, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p)
    notify.restype = None
    wide_path = ctypes.c_wchar_p(str(path))
    notify(
        0x00002000,
        0x0005,
        ctypes.cast(wide_path, ctypes.c_void_p),
        None,
    )


def migrate_shortcuts(
    old: Path,
    new: Path,
    *,
    candidates: Iterable[Path] | None = None,
    link_factory: Callable[[Path], object] | None = None,
    notifier: Callable[[Path], None] | None = None,
) -> tuple[list[str], list[str]]:
    """Migrate exact old-EXE targets and return successful/failed matched links."""
    old = Path(old).resolve()
    new = Path(new).resolve()
    candidate_paths = tuple(known_shortcut_paths() if candidates is None else candidates)
    factory = ShellLink if link_factory is None else link_factory
    notify = _notify_changed if notifier is None else notifier
    migrated: list[str] = []
    failed: list[str] = []
    apartment = _ComApartment() if link_factory is None else nullcontext()
    with apartment:
        for candidate in candidate_paths:
            candidate = Path(candidate).resolve()
            matched = False
            icon_changed = False
            try:
                with factory(candidate) as link:
                    if _normalized(link.target()) != _normalized(old):
                        continue
                    matched = True
                    icon_path, icon_index = link.icon()
                    icon_changed = _normalized(icon_path) == _normalized(old)
                    link.set_target(new)
                    if icon_changed:
                        link.set_icon(new, icon_index)
                    link.save()
                with factory(candidate) as verified:
                    if _normalized(verified.target()) != _normalized(new):
                        raise ShortcutError("saved shortcut target did not verify")
                    if icon_changed and _normalized(verified.icon()[0]) != _normalized(new):
                        raise ShortcutError("saved shortcut icon did not verify")
                notify(candidate)
                migrated.append(str(candidate))
            except Exception:
                if matched:
                    failed.append(str(candidate))
    return migrated, failed
