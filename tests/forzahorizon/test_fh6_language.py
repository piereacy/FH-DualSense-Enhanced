from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from modules.forzahorizon import fh6_language as language
from modules.config import preferences
from modules.config.settings import Settings


CHINESE = "询问安娜 自动驾驶已开启 设置路线 前往目的地 关闭自动驾驶 是否继续 比赛模式 警告"
ENGLISH = "Ask ANNA Auto Drive enabled set a route destination disable continue race mode warning"


@pytest.fixture(autouse=True)
def _windows_feature(monkeypatch):
    monkeypatch.setattr(language, "is_windows_steam_supported", lambda: True)


def _write_language_zip(path: Path, text: str) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("AccessibilityAutoDrive.str", (text + " ") * 12)
        archive.writestr("MenuOne.str", (text + " ") * 4)
        archive.writestr("MenuTwo.str", (text + " ") * 4)


def _game(tmp_path: Path, *, steam_language: str = "english") -> language.FH6Install:
    root = tmp_path / "ForzaHorizon6"
    tables = root / language.TABLES_RELATIVE
    tables.mkdir(parents=True)
    (root / language.GAME_EXE).write_bytes(b"MZ")
    _write_language_zip(tables / language.CHS_NAME, CHINESE)
    _write_language_zip(tables / language.EN_NAME, ENGLISH)
    install = language.validate_game_root(
        root,
        source="test",
        steam_language=steam_language,
    )
    assert install is not None
    return install


def test_discovers_fh6_from_a_non_system_steam_library(tmp_path):
    steam = tmp_path / "Steam"
    other_library = tmp_path / "OtherDrive" / "SteamLibrary"
    install = _game(other_library / "steamapps" / "common")
    (steam / "steamapps").mkdir(parents=True)
    escaped = str(other_library).replace("\\", "\\\\")
    (steam / "steamapps" / "libraryfolders.vdf").write_text(
        '"libraryfolders"\n{\n  "1"\n  {\n'
        f'    "path" "{escaped}"\n'
        '  }\n}\n',
        encoding="utf-8",
    )
    manifest = other_library / "steamapps" / f"appmanifest_{language.FH6_APP_ID}.acf"
    manifest.write_text(
        '"AppState"\n{\n'
        f'  "appid" "{language.FH6_APP_ID}"\n'
        '  "installdir" "ForzaHorizon6"\n'
        '  "UserConfig"\n  {\n    "language" "english"\n  }\n}\n',
        encoding="utf-8",
    )

    found = language.discover_fh6_install(
        steam_roots=[steam],
        uninstall_locations=[],
        running_executables=[],
    )

    assert found is not None
    assert found.root == install.root
    assert found.steam_language == "english"
    assert found.source == "Steam manifest"


def test_read_only_discovery_and_inspection_never_rename_archives(tmp_path):
    install = _game(tmp_path)
    before = {
        path.name: path.read_bytes()
        for path in install.string_tables.iterdir()
    }

    found = language.discover_fh6_install(
        cached_path=install.root,
        steam_roots=[],
        uninstall_locations=[],
        running_executables=[],
    )
    inspection = language.inspect_language_state(found)
    summary = language.summarize_fh6_languages(inspection)

    assert inspection.state is language.FH6LanguageState.NATIVE
    assert summary == language.FH6LanguageSummary(
        game_language="",
        display_language=language.ArchiveLanguage.UNKNOWN,
        voice_language="",
    )
    assert {
        path.name: path.read_bytes()
        for path in install.string_tables.iterdir()
    } == before


def _summary_inspection(state, steam_language="english"):
    install = language.FH6Install(
        Path("C:/Game"),
        Path("C:/Game/StringTables"),
        "test",
        steam_language,
    )
    return language.LanguageInspection(state, install)


def test_language_summary_distinguishes_native_and_swapped_text_from_voice():
    native = language.summarize_fh6_languages(
        _summary_inspection(language.FH6LanguageState.NATIVE)
    )
    swapped = language.summarize_fh6_languages(
        _summary_inspection(language.FH6LanguageState.SWAPPED)
    )

    assert native == language.FH6LanguageSummary(
        "english",
        language.ArchiveLanguage.ENGLISH,
        "english",
    )
    assert swapped == language.FH6LanguageSummary(
        "english",
        language.ArchiveLanguage.CHINESE,
        "english",
    )


@pytest.mark.parametrize(
    "state",
    (
        language.FH6LanguageState.RECOVERY_REQUIRED,
        language.FH6LanguageState.MISSING,
        language.FH6LanguageState.UNKNOWN,
        language.FH6LanguageState.CORRUPT,
    ),
)
def test_language_summary_does_not_guess_display_language_for_unsafe_states(state):
    summary = language.summarize_fh6_languages(_summary_inspection(state))

    assert summary.game_language == "english"
    assert summary.display_language is language.ArchiveLanguage.UNKNOWN
    assert summary.voice_language == "english"


def test_language_summary_normalizes_other_tokens_and_preserves_unknowns():
    other = language.summarize_fh6_languages(
        _summary_inspection(language.FH6LanguageState.NATIVE, "  SChinese  ")
    )
    unknown = language.summarize_fh6_languages(
        language.LanguageInspection(language.FH6LanguageState.NOT_FOUND, None)
    )

    assert other == language.FH6LanguageSummary(
        "schinese",
        language.ArchiveLanguage.UNKNOWN,
        "schinese",
    )
    assert unknown == language.FH6LanguageSummary(
        "",
        language.ArchiveLanguage.UNKNOWN,
        "",
    )


def test_detects_native_and_swapped_content_from_zip_payloads(tmp_path, monkeypatch):
    install = _game(tmp_path)
    monkeypatch.setattr(language, "is_fh6_running", lambda _install=None: False)

    assert language.inspect_language_state(install).state is language.FH6LanguageState.NATIVE

    enabled = language.enable_chinese_text_english_voice(install)
    assert enabled.state is language.FH6LanguageState.SWAPPED
    assert language.classify_archive(install.string_tables / language.CHS_NAME) is (
        language.ArchiveLanguage.ENGLISH
    )
    assert language.classify_archive(install.string_tables / language.EN_NAME) is (
        language.ArchiveLanguage.CHINESE
    )

    restored = language.restore_native_language(install)
    assert restored.state is language.FH6LanguageState.NATIVE
    assert not (install.string_tables / language.TEMP_NAME).exists()


def test_enable_requires_closed_game_and_verified_english_steam_language(tmp_path, monkeypatch):
    install = _game(tmp_path)
    monkeypatch.setattr(language, "is_fh6_running", lambda _install=None: True)
    with pytest.raises(language.FH6LanguageError, match="Close Forza"):
        language.enable_chinese_text_english_voice(install)

    monkeypatch.setattr(language, "is_fh6_running", lambda _install=None: False)
    unsupported = language.FH6Install(
        install.root,
        install.string_tables,
        install.source,
        "schinese",
    )
    with pytest.raises(language.FH6LanguageError, match="Steam language to English"):
        language.enable_chinese_text_english_voice(unsupported)

    unknown = language.FH6Install(
        install.root,
        install.string_tables,
        install.source,
        "",
    )
    with pytest.raises(language.FH6LanguageError, match="could not be verified"):
        language.enable_chinese_text_english_voice(unknown)
    assert language.enable_chinese_text_english_voice(
        unknown,
        allow_unknown_steam_language=True,
    ).state is language.FH6LanguageState.SWAPPED


def test_failed_second_rename_rolls_back_to_native_state(tmp_path, monkeypatch):
    install = _game(tmp_path)
    monkeypatch.setattr(language, "is_fh6_running", lambda _install=None: False)
    real_rename = language._rename
    call_count = 0

    def fail_once(source, destination):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise PermissionError("blocked")
        real_rename(source, destination)

    monkeypatch.setattr(language, "_rename", fail_once)
    with pytest.raises(language.FH6LanguageError, match="swap failed"):
        language.enable_chinese_text_english_voice(install)

    assert language.inspect_language_state(install).state is language.FH6LanguageState.NATIVE
    assert not (install.string_tables / language.TEMP_NAME).exists()


@pytest.mark.parametrize("interrupted_after", [1, 2])
def test_explicit_repair_recovers_each_interrupted_swap_position(
    tmp_path,
    monkeypatch,
    interrupted_after,
):
    install = _game(tmp_path)
    monkeypatch.setattr(language, "is_fh6_running", lambda _install=None: False)
    chs = install.string_tables / language.CHS_NAME
    en = install.string_tables / language.EN_NAME
    temp = install.string_tables / language.TEMP_NAME
    chs.rename(temp)
    if interrupted_after == 2:
        en.rename(chs)

    inspection = language.inspect_language_state(install)
    assert inspection.state is language.FH6LanguageState.RECOVERY_REQUIRED
    assert inspection.can_repair is True

    repaired = language.repair_native_language(install)
    assert repaired.state is language.FH6LanguageState.NATIVE
    assert not temp.exists()


def test_unknown_or_corrupt_archives_are_never_swapped(tmp_path, monkeypatch):
    install = _game(tmp_path)
    monkeypatch.setattr(language, "is_fh6_running", lambda _install=None: False)
    (install.string_tables / language.CHS_NAME).write_bytes(b"not a zip")

    inspection = language.inspect_language_state(install)
    assert inspection.state is language.FH6LanguageState.CORRUPT
    with pytest.raises(language.FH6LanguageError):
        language.enable_chinese_text_english_voice(install)


def test_non_windows_runtime_never_discovers_or_mutates(tmp_path, monkeypatch):
    install = _game(tmp_path)
    monkeypatch.setattr(language, "is_windows_steam_supported", lambda: False)

    assert language.discover_fh6_install(
        cached_path=install.root,
        steam_roots=[],
        uninstall_locations=[],
        running_executables=[],
    ) is None
    with pytest.raises(language.FH6LanguageError, match="Windows Steam only"):
        language.enable_chinese_text_english_voice(install)


def test_launch_fh6_revalidates_install_and_uses_exact_steam_uri(tmp_path, monkeypatch):
    install = _game(tmp_path)
    opened = []
    monkeypatch.setattr(language, "is_fh6_running", lambda _install=None: False)
    monkeypatch.setattr(language, "_open_steam_uri", opened.append)

    language.launch_fh6_via_steam(install)

    assert opened == ["steam://run/2483190"]


def test_launch_fh6_refuses_running_invalid_and_non_windows_installs(tmp_path, monkeypatch):
    install = _game(tmp_path)
    opened = []
    monkeypatch.setattr(language, "_open_steam_uri", opened.append)
    monkeypatch.setattr(language, "is_fh6_running", lambda _install=None: True)
    with pytest.raises(language.FH6LanguageError, match="already running"):
        language.launch_fh6_via_steam(install)

    monkeypatch.setattr(language, "is_fh6_running", lambda _install=None: False)
    (install.root / language.GAME_EXE).unlink()
    with pytest.raises(language.FH6LanguageError, match="no longer valid"):
        language.launch_fh6_via_steam(install)

    replacement = _game(tmp_path / "replacement")
    monkeypatch.setattr(language, "is_windows_steam_supported", lambda: False)
    with pytest.raises(language.FH6LanguageError, match="Windows Steam only"):
        language.launch_fh6_via_steam(replacement)
    assert opened == []


def test_launch_fh6_reports_uri_handler_failure(tmp_path, monkeypatch):
    install = _game(tmp_path)
    monkeypatch.setattr(language, "is_fh6_running", lambda _install=None: False)

    def fail(_uri):
        raise OSError("no Steam handler")

    monkeypatch.setattr(language, "_open_steam_uri", fail)
    with pytest.raises(language.FH6LanguageError, match="no Steam handler"):
        language.launch_fh6_via_steam(install)


def test_fh6_install_cache_is_global_and_never_profile_scoped():
    settings = Settings(fh6_install_path="D:/SteamLibrary/steamapps/common/ForzaHorizon6")

    assert "fh6_install_path" in preferences.GLOBAL_FIELDS
    assert preferences._global_fields(settings)["fh6_install_path"] == settings.fh6_install_path
    assert "fh6_install_path" not in preferences._profile_fields(settings)


def test_gui_and_tui_only_invoke_language_mutation_from_explicit_actions():
    root = Path(__file__).resolve().parents[2]
    gui_system = (root / "src/modules/gui/system_tab.py").read_text(encoding="utf-8")
    tui_system = (root / "src/modules/tui/system_tab.py").read_text(encoding="utf-8")
    gui = (root / "src/modules/gui/fh6_utilities_tab.py").read_text(encoding="utf-8")
    tui = (root / "src/modules/tui/fh6_utilities_tab.py").read_text(encoding="utf-8")
    core = (root / "src/modules/forzahorizon/fh6_language.py").read_text(encoding="utf-8")

    for source in (gui, tui):
        assert "Enable Chinese text + English voice" in source
        assert "enable_chinese_text_english_voice" in source
        assert "restore_native_language" in source
        assert "repair_native_language" in source
    for source in (gui_system, tui_system):
        assert "enable_chinese_text_english_voice" not in source
        assert "restore_native_language" not in source
        assert "repair_native_language" not in source
    assert "Program Files" not in core
    assert "C:\\\\" not in core
