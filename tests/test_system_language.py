from modules.config import system_language


def test_language_tag_mapping_covers_every_supported_family():
    assert system_language.map_language_tag("zh-CN") == "zh"
    assert system_language.map_language_tag("zh-Hans-SG") == "zh"
    assert system_language.map_language_tag("zh-TW") == "zh_tw"
    assert system_language.map_language_tag("zh-Hant-HK") == "zh_tw"
    assert system_language.map_language_tag("ja-JP") == "ja"
    assert system_language.map_language_tag("de_DE") == "de"
    assert system_language.map_language_tag("ru-RU") == "ru"
    assert system_language.map_language_tag("tr-TR") == "tr"
    assert system_language.map_language_tag("fr-FR") == "en"
    assert system_language.map_language_tag(None) == "en"


def test_detect_system_language_uses_windows_display_language(monkeypatch):
    monkeypatch.setattr(system_language.sys, "platform", "win32")
    monkeypatch.setattr(system_language, "_windows_language_tag", lambda: "ja-JP")

    assert system_language.detect_system_language() == "ja"
