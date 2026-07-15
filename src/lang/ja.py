# -*- coding: utf-8 -*-
"""日本語 (Japanese) catalog. Keys are the English source strings."""

NAME = "日本語"

STRINGS = {
    "About and licenses": "このアプリについてとライセンス",
    # --- body haptics ---
    "Body haptics": "ボディハプティクス",
    "Enable body haptics": "ボディハプティクスを有効化",
    ("Uses the same haptic mix over USB and Bluetooth; only the transport path differs. "
     "Disable in-game vibration only if you feel competing or doubled output."):
        "USB と Bluetooth は同じ触覚ミックスを使用し、異なるのは転送経路だけです。"
        "出力が競合している、または二重になっていると感じる場合にのみ、"
        "ゲーム内振動を無効にしてください。",
    "Master intensity": "全体の強度",
    "Engine intensity": "エンジンの強度",
    "Road texture intensity": "路面テクスチャの強度",
    "Impact and suspension intensity": "衝撃とサスペンションの強度",
    "Slip and ABS intensity": "スリップとABSの強度",
    "Slip threshold": "スリップしきい値",

    # --- chrome / tabs ---
    "Controls": "操作",
    "Profiles": "プロファイル",
    "Settings": "設定",
    "System": "システム",
    "Language": "言語",
    "Logs": "ログ",
    "Quit": "終了",
    "♥ Sponsor": "♥ 支援",
    "Changelog": "変更履歴",
    "connected": "接続済み",
    "waiting": "待機中",
    "active": "使用中",
    "(none)": "（なし）",
    "Backend failed: {error}": "バックエンドの起動に失敗しました: {error}",
    "Profile: {name}": "プロファイル: {name}",
    "Active: {name}": "使用中: {name}",

    # --- controls tab (per-trigger effect switches) ---
    "Shift thump": "シフトショック",
    "ABS rumble": "ABS 振動",
    "Static brake wall": "ブレーキの固定ウォール",
    "Brake stiffness": "ブレーキの硬さ",
    "Handbrake stiffness bonus": "ハンドブレーキの追加の硬さ",
    "Idle buzz": "アイドリング振動",
    "Throttle stiffness": "アクセルの硬さ",

    # --- settings tab sections ---
    "Pedal dead zones": "ペダルのデッドゾーン",
    "Left trigger - Brake force": "左トリガー - ブレーキの強さ",
    "Left trigger - Static wall (optional)": "左トリガー - 固定ウォール（任意）",
    "Right trigger - Gas force": "右トリガー - アクセルの強さ",
    "ABS (anti-lock brake) rumble": "ABS（アンチロックブレーキ）振動",
    "Idle buzz": "アイドリング振動",
    "Gear shift thump": "シフトショック",

    # --- settings tab fields ---
    "Gas trigger dead zone": "アクセルトリガーのデッドゾーン",
    "Brake trigger dead zone": "ブレーキトリガーのデッドゾーン",
    "Resting stiffness": "待機時の硬さ",
    "Hard-press stiffness": "深押し時の硬さ",
    "Stiffness curve shape": "硬さカーブの形状",
    "Handbrake extra stiffness": "ハンドブレーキの追加の硬さ",
    "Wall position on the trigger": "トリガー上のウォール位置",
    "Wall hardness": "ウォールの硬さ",
    "Only when braking harder than": "ブレーキ強度が次を超えるときのみ",
    "Only when faster than (km/h)": "速度が次を超えるときのみ (km/h)",
    "Wheel slip sensitivity": "ホイールスリップ感度",
    "Tire grip sensitivity": "タイヤグリップ感度",
    "Rumble speed (Hz)": "振動の速さ (Hz)",
    "Rumble strength": "振動の強さ",
    "Fire near redline at": "レッドライン付近で発動",
    "Buzz speed (Hz)": "振動の速さ (Hz)",
    "Buzz strength": "振動の強さ",
    "Buzz hold time (ms)": "振動の保持時間 (ms)",
    "Idle strength": "アイドリングの強さ",
    "Thump speed (Hz)": "ショックの速さ (Hz)",
    "Thump strength": "ショックの強さ",
    "Thump length (ms)": "ショックの長さ (ms)",

    # --- settings tab buttons / hints ---
    "Reset to defaults": "デフォルトに戻す",
    "Click again to confirm reset": "もう一度クリックしてリセットを確定",
    "In Forza HUD: host 127.0.0.1 (try ::1 if it fails).":
        "Forza HUD で host を 127.0.0.1 に設定（うまくいかなければ ::1 を試す）。",
    "Forward telemetry": "テレメトリを転送",
    "Mirror every received packet to another app (e.g. SimHub) without taking the port from it.":
        "受信した各パケットを別のアプリ（例: SimHub）にミラーします。ポートを奪いません。",
    "Forward to": "転送先",
    "host:port targets, comma-separated. Default 127.0.0.1:5301.":
        "host:port 形式の宛先（カンマ区切り）。既定値 127.0.0.1:5301。",
    "UDP port {port} is in use. Close the other listener or change the port in the System tab.":
        "UDP ポート {port} は使用中です。他のリスナーを閉じるか、システムタブでポートを変更してください。",

    # --- system tab sections / fields ---
    "Forza telemetry (applies on next launch)": "Forza テレメトリ（次回起動時に適用）",
    "Startup pulse": "起動時の振動",
    "Reconnect": "再接続",
    "Application behavior": "アプリの動作",
    "Game detection": "ゲーム検出",
    "UDP port": "UDP ポート",
    "Startup buzz strength": "起動時の振動の強さ",
    "Auto-reconnect when controller drops": "コントローラー切断時に自動再接続",
    "Reconnect check interval (s)": "再接続の確認間隔 (秒)",
    "Auto-exit when the game closes": "ゲーム終了時に自動終了",
    "Close the app when the game closes": "ゲーム終了時にアプリも終了",
    "Move the app to the tray when minimized": "最小化時にアプリをトレイへ移動",
    "Game-watch check interval (s)": "ゲーム監視の確認間隔 (秒)",

    # --- DSX ---
    "DSX": "DSX",
    "DSX integration": "DSX 連携",
    "Send triggers to DualSenseX over UDP. Takes effect immediately.":
        "UDP 経由でトリガーを DualSenseX に送信。即座に反映されます。",
    "DSX connection": "DSX 接続",
    "Host": "ホスト",
    "Port": "ポート",
    "Default 127.0.0.1. Match the host in DSX settings.":
        "デフォルト 127.0.0.1。DSX 設定のホストと一致させる必要があります。",
    "Default 6969. Match the port in DSX settings.":
        "デフォルト 6969。DSX 設定のポートと一致させる必要があります。",
    "DSX is active - controller managed by DSX. Disable DSX to select a controller here.":
        "DSX が有効 - コントローラーは DSX が管理中。コントローラーを選択するには DSX を無効にしてください。",
    "DSX: active": "DSX: 有効",
    "DSX: off": "DSX: オフ",

    # --- system tab controller block ---
    "Controller": "コントローラー",
    "Lock to controller": "コントローラーに固定",
    "Rescan": "再スキャン",
    "Auto (first found)": "自動（最初に見つかったもの）",
    "attached now": "現在接続中",
    "(no serial - not selectable)": "（シリアルなし - 選択不可）",

    # --- system tab updates block ---
    "Updates": "アップデート",
    "Check for updates at launch": "起動時に更新を確認",
    "When off, ZUV will not prompt for updates on startup. Toggle on and restart the app to check for a new release.":
        "オフの場合、ZUV は起動時に更新を確認しません。新しいリリースを確認するにはオンにしてアプリを再起動してください。",
    "ZUV not found: this build is not running inside a ZUV bundle (ZUV_CACHE_ROOT env var is missing), so the update toggle has nothing to control. Run the bundled .zuv.py to manage updates.":
        "ZUV が見つかりません: このビルドは ZUV バンドル内で実行されていません（ZUV_CACHE_ROOT 環境変数がありません）。更新トグルが制御する対象がないため、更新を管理するにはバンドルされた .zuv.py を実行してください。",

    # --- profiles tab ---
    "Load": "読み込み",
    "Rename": "名前変更",
    "Delete": "削除",
    "Save": "保存",
    "New profile name": "新しいプロファイル名",
    "File: {path}": "ファイル: {path}",
    "Note: the [b]Default[/] profile is reset to built-in values every time the app launches so new features and tuning come through. System settings (System tab) are preserved. To keep your own tuning across launches, save it as a named profile here.":
        "注意: [b]Default[/] プロファイルは、新機能や調整を反映するためアプリ起動のたびに組み込み値へリセットされます。システム設定（システムタブ）は保持されます。独自の調整を起動間で保持するには、ここで名前付きプロファイルとして保存してください。",

    # --- logs tab ---
    "level": "レベル",
    "pause": "一時停止",
    "resume": "再開",
    "clear": "クリア",

    # --- R2 実験的トリガー調整 ---
    "Sensitivity": "感度",
    "Experimental features": "実験的機能",
    "Not recommended for manual adjustment.": "手動での調整は推奨しません。",
    "ABS advanced tuning": "ABS 詳細調整",
    "Shared feedback": "共通フィードバック",
    "Redline grip warning": "レッドラインのグリップ警告",
    "Trigger near redline at": "レッドライン付近の発動位置",
    "Pulse rate (Hz)": "パルス周期 (Hz)",
    "Grip pulse strength": "グリップパルスの強さ",
    "Pulse hold time (ms)": "パルス保持時間 (ms)",
    "Traction/grip feedback": "トラクション／グリップフィードバック",
    "Grip feedback strength": "グリップフィードバックの強さ",
    "Traction/grip advanced tuning": "トラクション／グリップ詳細調整",
    "Minimum brake input": "最小ブレーキ入力",
    "Minimum speed (km/h)": "最低速度 (km/h)",
    "Longitudinal slip threshold": "縦方向スリップしきい値",
    "Combined slip threshold": "複合スリップしきい値",
    "Combined slip influence": "複合スリップの影響度",
    "Slip at maximum feedback": "最大フィードバック時のスリップ",
    "Minimum frequency (Hz)": "最小周波数 (Hz)",
    "Maximum frequency (Hz)": "最大周波数 (Hz)",
    "Minimum strength": "最小強度",
    "Feedback hold (ms)": "フィードバック保持時間 (ms)",
    "Top wall zones": "上部ウォールゾーン数",
    "Slip hysteresis": "スリップヒステリシス",
    "Attack smoothing (ms)": "立ち上がり平滑化 (ms)",
    "Release smoothing (ms)": "解除平滑化 (ms)",
    "G-force damping": "G フォース減衰",
    "Burnout rotation threshold": "バーンアウト回転しきい値",
    "Burnout rotation at maximum feedback": "最大フィードバック時のバーンアウト回転",
    "Tarmac minimum frequency (Hz)": "舗装路の最小周波数 (Hz)",
    "Tarmac maximum frequency (Hz)": "舗装路の最大周波数 (Hz)",
    "Water minimum frequency (Hz)": "水面の最小周波数 (Hz)",
    "Water maximum frequency (Hz)": "水面の最大周波数 (Hz)",
    "Dirt minimum frequency (Hz)": "ダートの最小周波数 (Hz)",
    "Dirt maximum frequency (Hz)": "ダートの最大周波数 (Hz)",
    "Gravel minimum frequency (Hz)": "グラベルの最小周波数 (Hz)",
    "Gravel maximum frequency (Hz)": "グラベルの最大周波数 (Hz)",

    # --- language tab ---
    "Pick a language, then restart the app to apply it.":
        "言語を選択し、アプリを再起動して適用してください。",
    "Restart the app to apply the new language.":
        "新しい言語を適用するにはアプリを再起動してください。",
    # --- R3 redline and collision haptics ---
    "Redline feedback": "レッドラインフィードバック",
    "R2 trigger redline vibration": "R2 トリガーのレッドライン振動",
    "Grip redline vibration": "グリップのレッドライン振動",
    "Left grip": "左グリップ",
    "Right grip": "右グリップ",
    "Trigger vibration frequency (Hz)": "トリガー振動周波数 (Hz)",
    "Trigger vibration strength": "トリガー振動強度",
    "Trigger hold time (ms)": "トリガー保持時間 (ms)",
    "Grip trigger near redline at": "グリップ警告の発動位置",
    "Grip pulse rate (Hz)": "グリップパルス周波数 (Hz)",
    "Grip redline advanced tuning": "グリップのレッドライン詳細調整",
    "Low-frequency pulse ratio": "低周波パルス比率",
    "Redline background level": "レッドライン時の背景レベル",
    "Collision haptics advanced tuning": "衝突触覚の詳細調整",
    "Collision jerk threshold": "衝突ジャークしきい値",
    "Collision duration (ms)": "衝突時間 (ms)",
    "Collision cooldown (ms)": "衝突クールダウン (ms)",
    "Collision rebound strength": "衝突リバウンド強度",
    "Collision weak-side strength": "衝突時の弱側強度",
    "Collision background level": "衝突時の背景レベル",
    "Grip release below redline at": "グリップ警告の解除位置",
}
