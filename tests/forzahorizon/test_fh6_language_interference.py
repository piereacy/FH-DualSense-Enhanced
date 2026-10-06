from pathlib import Path
from zipfile import ZipFile

import pytest

from modules.forzahorizon import fh6_language as language

CHINESE = "自动驾驶已经开启 请设置路线并前往目的地 是否继续当前比赛模式"
ENGLISH = "Automatic driving enabled please set your route and continue towards the destination"


def _write_archive(path: Path, text: str, revision: str = "original") -> bytes:
    with ZipFile(path, "w") as archive:
        archive.writestr("AccessibilityAutoDrive.str", (text + " ") * 12)
        archive.writestr("revision.txt", revision)
    return path.read_bytes()


@pytest.fixture
def install(tmp_path, monkeypatch):
    monkeypatch.setattr(language, "is_windows_steam_supported", lambda: True)
    monkeypatch.setattr(language, "is_fh6_running", lambda _install=None: False)
    tables = tmp_path / language.TABLES_RELATIVE
    tables.mkdir(parents=True)
    (tmp_path / language.GAME_EXE).write_bytes(b"MZ")
    _write_archive(tables / language.CHS_NAME, CHINESE)
    _write_archive(tables / language.EN_NAME, ENGLISH)
    result = language.validate_game_root(tmp_path, steam_language="english")
    assert result is not None
    return result


@pytest.mark.parametrize("restore", [False, True])
def test_swap_rejects_external_source_change_and_preserves_new_bytes(
    install, monkeypatch, restore,
):
    if restore:
        language.enable_chinese_text_english_voice(install)
    chs = install.string_tables / language.CHS_NAME
    en = install.string_tables / language.EN_NAME
    original_chs = chs.read_bytes()
    external_bytes = b""
    checks = 0

    def update_before_second_move(_install):
        nonlocal checks, external_bytes
        checks += 1
        if checks == 3:
            external_bytes = _write_archive(
                en, CHINESE if restore else ENGLISH, "external update",
            )

    monkeypatch.setattr(language, "_guard_not_running", update_before_second_move)
    action = language.restore_native_language if restore else language.enable_chinese_text_english_voice
    with pytest.raises(language.FH6LanguageError):
        action(install)

    assert external_bytes
    assert en.read_bytes() == external_bytes
    assert chs.read_bytes() == original_chs
    assert not (install.string_tables / language.TEMP_NAME).exists()


@pytest.mark.parametrize("action", ["enable", "restore", "repair"])
def test_rollback_does_not_move_externally_replaced_destination(
    install, monkeypatch, action,
):
    chs = install.string_tables / language.CHS_NAME
    en = install.string_tables / language.EN_NAME
    temp = install.string_tables / language.TEMP_NAME
    if action == "restore":
        language.enable_chinese_text_english_voice(install)
    if action == "repair":
        chs.rename(temp)
        en.rename(chs)
    original_preserved = (temp if action == "repair" else chs).read_bytes()
    destination_to_replace = en if action == "repair" else chs
    external_bytes = b""
    rename = language._rename
    calls = 0

    def replace_after_move_then_fail(source, destination):
        nonlocal calls, external_bytes
        calls += 1
        failed_step = 2 if action == "repair" else 3
        if calls == failed_step:
            raise PermissionError("injected failure after an external update")
        rename(source, destination)
        if destination == destination_to_replace and not external_bytes:
            external_bytes = _write_archive(destination, ENGLISH, "external update")

    monkeypatch.setattr(language, "_rename", replace_after_move_then_fail)
    operation = {
        "enable": language.enable_chinese_text_english_voice,
        "restore": language.restore_native_language,
        "repair": language.repair_native_language,
    }[action]
    with pytest.raises(language.FH6LanguageError):
        operation(install)

    assert external_bytes
    assert destination_to_replace.read_bytes() == external_bytes
    assert temp.read_bytes() == original_preserved


@pytest.mark.parametrize("repair", [False, True])
def test_content_classification_is_bound_to_the_verified_bytes(
    install, monkeypatch, repair,
):
    chs = install.string_tables / language.CHS_NAME
    en = install.string_tables / language.EN_NAME
    temp = install.string_tables / language.TEMP_NAME
    if repair:
        chs.rename(temp)
    before = {path.name: path.read_bytes() for path in install.string_tables.iterdir()}
    classify = language.classify_archive
    replacement = b""

    def update_after_classification(path, *, full_check=False):
        nonlocal replacement
        identity = classify(path, full_check=full_check)
        if path == en and full_check:
            replacement = _write_archive(en, ENGLISH, "updated during ZIP validation")
        return identity

    monkeypatch.setattr(language, "classify_archive", update_after_classification)
    operation = language.repair_native_language if repair else language.enable_chinese_text_english_voice
    with pytest.raises(language.FH6LanguageError, match="changed during operation"):
        operation(install)

    before[language.EN_NAME] = replacement
    assert replacement
    assert {path.name: path.read_bytes() for path in install.string_tables.iterdir()} == before


def test_repair_preserves_source_replaced_after_its_first_move(install, monkeypatch):
    chs = install.string_tables / language.CHS_NAME
    en = install.string_tables / language.EN_NAME
    temp = install.string_tables / language.TEMP_NAME
    original_english = en.read_bytes()
    chs.rename(temp)
    en.rename(chs)
    rename = language._rename
    replacement = b""

    def update_after_first_move(source, destination):
        nonlocal replacement
        rename(source, destination)
        if destination == en:
            replacement = _write_archive(temp, CHINESE, "external update")

    monkeypatch.setattr(language, "_rename", update_after_first_move)
    with pytest.raises(language.FH6LanguageError, match="changed during operation"):
        language.repair_native_language(install)

    assert replacement
    assert temp.read_bytes() == replacement
    assert chs.read_bytes() == original_english
    assert not en.exists()


@pytest.mark.parametrize("after_first_move", [False, True])
def test_repair_preserves_an_external_third_archive(install, monkeypatch, after_first_move):
    chs = install.string_tables / language.CHS_NAME
    en = install.string_tables / language.EN_NAME
    temp = install.string_tables / language.TEMP_NAME
    chs.rename(temp)
    en.rename(chs)
    original_chinese = temp.read_bytes()
    original_english = chs.read_bytes()
    checks = 0
    replacement = b""
    destination = chs if after_first_move else en

    def create_missing_archive(_install):
        nonlocal checks, replacement
        checks += 1
        if checks == (3 if after_first_move else 2):
            replacement = _write_archive(destination, ENGLISH, "external third archive")

    monkeypatch.setattr(language, "_guard_not_running", create_missing_archive)
    with pytest.raises(language.FH6LanguageError):
        language.repair_native_language(install)

    assert replacement
    assert destination.read_bytes() == replacement
    assert temp.read_bytes() == original_chinese
    assert (en if after_first_move else chs).read_bytes() == original_english


def test_repair_failure_still_rolls_back_unchanged_archives(install, monkeypatch):
    chs = install.string_tables / language.CHS_NAME
    en = install.string_tables / language.EN_NAME
    temp = install.string_tables / language.TEMP_NAME
    chs.rename(temp)
    en.rename(chs)
    before = {path.name: path.read_bytes() for path in install.string_tables.iterdir()}
    rename = language._rename
    calls = 0

    def fail_second_move_once(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise PermissionError("injected second move failure")
        rename(source, destination)

    monkeypatch.setattr(language, "_rename", fail_second_move_once)
    with pytest.raises(language.FH6LanguageError, match="recovery failed"):
        language.repair_native_language(install)

    assert {path.name: path.read_bytes() for path in install.string_tables.iterdir()} == before
    assert language.inspect_language_state(install).can_repair
