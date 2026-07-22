from pathlib import Path

import pytest

from modules.config import preferences
from modules.config.settings import Settings
from modules.forzahorizon import game_launch
from modules.forzahorizon.process_watch import GameProcess


def _game_root(tmp_path: Path, key: str) -> Path:
    definition = game_launch.get_forza_game(key)
    root = tmp_path / definition.full_name.replace(" ", "")
    root.mkdir(parents=True)
    (root / definition.executable_name).write_bytes(b"MZ")
    return root


def test_registry_has_all_supported_steam_games_and_stable_default():
    assert game_launch.DEFAULT_FORZA_GAME_KEY == "fh6"
    assert game_launch.FORZA_GAME_KEYS == ("fh4", "fh5", "fh6")
    assert {
        key: (game.steam_app_id, game.xbox_product_id, game.executable_name)
        for key, game in game_launch.FORZA_GAMES.items()
    } == {
        "fh4": ("1293830", "9PNJXVCVWD4K", "ForzaHorizon4.exe"),
        "fh5": ("1551360", "9NKX70BBCDRN", "ForzaHorizon5.exe"),
        "fh6": ("2483190", "9N431PX143P8", "ForzaHorizon6.exe"),
    }


@pytest.mark.parametrize("key", game_launch.FORZA_GAME_KEYS)
def test_discovers_each_game_from_a_steam_library_manifest(tmp_path, key):
    definition = game_launch.get_forza_game(key)
    steam = tmp_path / "Steam"
    library = tmp_path / f"Library-{key}"
    root = _game_root(library / "steamapps" / "common", key)
    (steam / "steamapps").mkdir(parents=True)
    escaped = str(library).replace("\\", "\\\\")
    (steam / "steamapps" / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n  "1" {{ "path" "{escaped}" }}\n}}\n',
        encoding="utf-8",
    )
    (library / "steamapps").mkdir(parents=True, exist_ok=True)
    (library / "steamapps" / f"appmanifest_{definition.steam_app_id}.acf").write_text(
        '"AppState"\n{\n'
        f'  "appid" "{definition.steam_app_id}"\n'
        f'  "installdir" "{root.name}"\n'
        '  "UserConfig" { "language" "english" }\n}\n',
        encoding="utf-8",
    )

    install = game_launch.discover_forza_install(
        key,
        steam_roots=[steam],
        uninstall_locations=[],
        running_executables=[],
    )

    assert install is not None
    assert install.game is definition
    assert install.root == root.resolve()
    assert install.source == "Steam manifest"
    assert install.steam_language == "english"


def test_path_validation_rejects_another_forza_generation(tmp_path):
    fh4 = _game_root(tmp_path, "fh4")

    assert game_launch.validate_forza_root("fh4", fh4) is not None
    assert game_launch.validate_forza_root("fh5", fh4) is None


def test_exact_process_detection_distinguishes_each_generation(tmp_path, monkeypatch):
    root = _game_root(tmp_path, "fh5")
    calls = []

    def find(_needles, *, exact_name, strict=False):
        calls.append(exact_name)
        if exact_name == "ForzaHorizon5.exe":
            return GameProcess(exact_name, str(root / exact_name), 55)
        return None

    monkeypatch.setattr(game_launch, "find_game_process", find)

    assert game_launch.is_forza_game_running("fh5") is True
    assert game_launch.is_forza_game_running("fh4") is False
    assert calls == ["ForzaHorizon5.exe", "ForzaHorizon4.exe"]


@pytest.mark.parametrize("key", game_launch.FORZA_GAME_KEYS)
def test_launch_uses_selected_game_steam_uri(tmp_path, monkeypatch, key):
    root = _game_root(tmp_path, key)
    install = game_launch.validate_forza_root(key, root)
    assert install is not None
    opened = []
    monkeypatch.setattr(game_launch, "is_windows_steam_supported", lambda: True)
    monkeypatch.setattr(
        game_launch, "is_forza_game_running", lambda *_args, **_kwargs: False
    )

    game_launch.launch_forza_via_steam(install, open_uri=opened.append)

    assert opened == [install.game.steam_run_uri]


def test_launch_refuses_when_the_process_table_cannot_be_verified(tmp_path, monkeypatch):
    root = _game_root(tmp_path, "fh6")
    install = game_launch.validate_forza_root("fh6", root)
    assert install is not None
    monkeypatch.setattr(game_launch, "is_windows_steam_supported", lambda: True)
    monkeypatch.setattr(
        game_launch,
        "is_forza_game_running",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            game_launch.ProcessScanError("process table unavailable")
        ),
    )

    with pytest.raises(game_launch.ForzaLaunchError, match="Could not verify"):
        game_launch.launch_forza_via_steam(install, open_uri=lambda _uri: None)


def test_decode_start_apps_accepts_single_or_multiple_json_rows():
    assert game_launch._decode_start_apps(
        '{"Name":"Forza Horizon 6","AppID":"Package!Game"}'
    ) == (game_launch.XboxStartApp("Forza Horizon 6", "Package!Game"),)
    assert game_launch._decode_start_apps(
        '[{"Name":"Other","AppID":"Other!App"},'
        '{"Name":"Forza Horizon 5 Standard Edition","AppID":"FH5!Game"}]'
    )[1].aumid == "FH5!Game"


def test_xbox_aumid_discovery_uses_the_selected_generation():
    entries = (
        game_launch.XboxStartApp("Forza Horizon 4", "FH4!Game"),
        game_launch.XboxStartApp("Forza Horizon 5 Standard Edition", "FH5!Game"),
        game_launch.XboxStartApp("Forza Horizon 6", "FH6!Game"),
    )

    assert game_launch.discover_xbox_aumid("fh5", entries=entries) == "FH5!Game"


def test_xbox_aumid_discovery_ignores_same_named_steam_shortcut():
    entries = (
        game_launch.XboxStartApp("Forza Horizon 6", "Steam App 2483190"),
        game_launch.XboxStartApp("Forza Horizon 6", "XboxPackage!Game"),
    )

    assert game_launch.discover_xbox_aumid("fh6", entries=entries) == "XboxPackage!Game"


def test_xbox_launch_activates_installed_aumid(monkeypatch):
    opened = []
    monkeypatch.setattr(game_launch, "is_windows_steam_supported", lambda: True)
    monkeypatch.setattr(
        game_launch, "is_forza_game_running", lambda *_args, **_kwargs: False
    )

    result = game_launch.launch_forza_via_xbox_app(
        "fh4",
        entries=(game_launch.XboxStartApp("Forza Horizon 4", "FH4!Game"),),
        open_target=opened.append,
    )

    assert result.direct is True
    assert opened == [r"shell:AppsFolder\FH4!Game"]


def test_xbox_launch_falls_back_to_selected_product_page(monkeypatch):
    opened = []
    monkeypatch.setattr(game_launch, "is_windows_steam_supported", lambda: True)
    monkeypatch.setattr(
        game_launch, "is_forza_game_running", lambda *_args, **_kwargs: False
    )

    result = game_launch.launch_forza_via_xbox_app(
        "fh6",
        entries=(),
        open_target=opened.append,
    )

    assert result.direct is False
    assert opened == ["msxbox://game/?productId=9N431PX143P8"]


def test_invalid_game_key_is_never_silently_changed_to_fh6():
    with pytest.raises(ValueError, match="Unsupported Forza Horizon game key"):
        game_launch.get_forza_game("fh7")


def test_game_selection_and_install_caches_are_global_not_profile_fields():
    settings = Settings(
        preferred_forza_game="fh4",
        fh4_install_path="D:/Steam/FH4",
        fh5_install_path="E:/Steam/FH5",
        fh6_install_path="F:/Steam/FH6",
        fh6_xbox_install_path="G:/Xbox/FH6",
    )
    expected = {
        "preferred_forza_game",
        "fh4_install_path",
        "fh5_install_path",
        "fh6_install_path",
        "fh6_xbox_install_path",
    }

    assert expected <= preferences.GLOBAL_FIELDS
    assert expected <= preferences._global_fields(settings).keys()
    assert expected.isdisjoint(preferences._profile_fields(settings))
