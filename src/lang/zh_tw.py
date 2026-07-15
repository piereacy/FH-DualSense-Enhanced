# -*- coding: utf-8 -*-
"""繁體中文（台灣）catalog. Keys are the English source strings."""

NAME = "繁體中文（台灣）"

STRINGS = {
    "About and licenses": "關於與授權條款",
    # --- body haptics ---
    "Body haptics": "握把觸覺",
    "Enable body haptics": "啟用握把觸覺",
    ("Uses the same haptic mix over USB and Bluetooth; only the transport path differs. "
     "Disable in-game vibration only if you feel competing or doubled output."):
        "USB 與藍牙使用相同的觸覺混合與強度，只有底層傳輸路徑不同。"
        "只有在感覺輸出互相干擾或出現雙重震動時，才關閉遊戲內震動。",
    "Master intensity": "總體強度",
    "Engine intensity": "引擎強度",
    "Road texture intensity": "路面紋理強度",
    "Impact and suspension intensity": "碰撞與懸吊強度",
    "Slip and ABS intensity": "打滑與 ABS 強度",
    "Slip threshold": "打滑閾值",

    # --- chrome / tabs ---
    "Controls": "控制",
    "Profiles": "設定檔",
    "Settings": "設定",
    "System": "系統",
    "Language": "語言",
    "Logs": "日誌",
    "Quit": "離開",
    "♥ Sponsor": "♥ 贊助",
    "Changelog": "更新日誌",
    "connected": "已連線",
    "waiting": "等待中",
    "active": "使用中",
    "(none)": "（無）",
    "Backend failed: {error}": "後端啟動失敗：{error}",
    "Profile: {name}": "設定檔：{name}",
    "Active: {name}": "使用中：{name}",

    # --- controls tab (per-trigger effect switches) ---
    "Shift thump": "換檔衝擊",
    "ABS rumble": "ABS 震動",
    "Static brake wall": "固定煞車阻力牆",
    "Brake stiffness": "煞車阻力",
    "Handbrake stiffness bonus": "手煞車額外阻力",
    "Idle buzz": "怠速震動",
    "Throttle stiffness": "油門阻力",

    # --- settings tab sections ---
    "Pedal dead zones": "踏板死區",
    "Left trigger - Brake force": "左扳機 - 煞車力道",
    "Left trigger - Static wall (optional)": "左扳機 - 固定阻力牆（選用）",
    "Right trigger - Gas force": "右扳機 - 油門力道",
    "ABS (anti-lock brake) rumble": "ABS（防鎖死煞車）震動",
    "Idle buzz": "怠速震動",
    "Gear shift thump": "換檔衝擊",

    # --- settings tab fields ---
    "Gas trigger dead zone": "油門扳機死區",
    "Brake trigger dead zone": "煞車扳機死區",
    "Resting stiffness": "靜止阻力",
    "Hard-press stiffness": "深踩阻力",
    "Stiffness curve shape": "阻力曲線形狀",
    "Handbrake extra stiffness": "手煞車額外阻力",
    "Wall position on the trigger": "扳機上的阻力牆位置",
    "Wall hardness": "阻力牆硬度",
    "Only when braking harder than": "煞車力道高於此值時",
    "Only when faster than (km/h)": "車速高於此值時 (km/h)",
    "Wheel slip sensitivity": "輪胎滑移靈敏度",
    "Tire grip sensitivity": "輪胎抓地靈敏度",
    "Rumble speed (Hz)": "震動速度 (Hz)",
    "Rumble strength": "震動強度",
    "Fire near redline at": "接近紅線時觸發",
    "Buzz speed (Hz)": "震動速度 (Hz)",
    "Buzz strength": "震動強度",
    "Buzz hold time (ms)": "震動持續時間 (ms)",
    "Idle strength": "怠速強度",
    "Thump speed (Hz)": "衝擊速度 (Hz)",
    "Thump strength": "衝擊強度",
    "Thump length (ms)": "衝擊時間 (ms)",

    # --- settings tab buttons / hints ---
    "Reset to defaults": "重設為預設值",
    "Click again to confirm reset": "再按一次確認重設",
    "In Forza HUD: host 127.0.0.1 (try ::1 if it fails).":
        "在 Forza HUD 中: host 設為 127.0.0.1（不行的話試試 ::1）。",
    "Forward telemetry": "轉發遙測資料",
    "Mirror every received packet to another app (e.g. SimHub) without taking the port from it.":
        "將收到的每個封包鏡像到另一個應用程式（如 SimHub），且不佔用連接埠。",
    "Forward to": "轉發到",
    "host:port targets, comma-separated. Default 127.0.0.1:5301.":
        "host:port 目標，以逗號分隔。預設 127.0.0.1:5301。",
    "UDP port {port} is in use. Close the other listener or change the port in the System tab.":
        "UDP 連接埠 {port} 已被使用。請關閉其他監聽程式，或到系統分頁更改連接埠。",

    # --- system tab sections / fields ---
    "Forza telemetry (applies on next launch)": "Forza 遙測（下次啟動生效）",
    "Startup pulse": "啟動震動",
    "Reconnect": "重新連線",
    "Application behavior": "軟體行為",
    "Game detection": "遊戲偵測",
    "UDP port": "UDP 連接埠",
    "Startup buzz strength": "啟動震動強度",
    "Auto-reconnect when controller drops": "手把斷線時自動重新連線",
    "Reconnect check interval (s)": "重新連線檢查間隔（秒）",
    "Auto-exit when the game closes": "遊戲關閉時自動離開",
    "Close the app when the game closes": "關閉遊戲後同時關閉軟體",
    "Move the app to the tray when minimized": "最小化視窗後移至系統匣",
    "Game-watch check interval (s)": "遊戲監看檢查間隔（秒）",

    # --- DSX ---
    "DSX": "DSX",
    "DSX integration": "DSX 整合",
    "Send triggers to DualSenseX over UDP. Takes effect immediately.":
        "透過 UDP 將扳機效果送到 DualSenseX。會立即生效。",
    "DSX connection": "DSX 連線",
    "Host": "主機",
    "Port": "連接埠",
    "Default 127.0.0.1. Match the host in DSX settings.":
        "預設為 127.0.0.1。需與 DSX 設定中的主機一致。",
    "Default 6969. Match the port in DSX settings.":
        "預設為 6969。需與 DSX 設定中的連接埠一致。",
    "DSX is active - controller managed by DSX. Disable DSX to select a controller here.":
        "DSX 已啟用 - 手把由 DSX 管理。停用 DSX 後才能在這裡選擇手把。",
    "DSX: active": "DSX：已啟用",
    "DSX: off": "DSX：已關閉",

    # --- system tab controller block ---
    "Controller": "手把",
    "Lock to controller": "鎖定手把",
    "Rescan": "重新掃描",
    "Auto (first found)": "自動（第一個找到的）",
    "attached now": "目前已連接",
    "(no serial - not selectable)": "（無序號 - 無法選擇）",

    # --- system tab updates block ---
    "Updates": "更新",
    "Check for updates at launch": "啟動時檢查更新",
    "When off, ZUV will not prompt for updates on startup. Toggle on and restart the app to check for a new release.":
        "關閉時，ZUV 不會在啟動時提示更新。開啟後重新啟動應用程式，即可檢查新版本。",
    "ZUV not found: this build is not running inside a ZUV bundle (ZUV_CACHE_ROOT env var is missing), so the update toggle has nothing to control. Run the bundled .zuv.py to manage updates.":
        "找不到 ZUV：這個版本不是在 ZUV bundle 內執行（缺少 ZUV_CACHE_ROOT 環境變數），所以更新開關沒有可控制的項目。請執行打包的 .zuv.py 來管理更新。",

    # --- profiles tab ---
    "Load": "載入",
    "Rename": "重新命名",
    "Delete": "刪除",
    "Save": "儲存",
    "New profile name": "新設定檔名稱",
    "File: {path}": "檔案：{path}",
    "Note: the [b]Default[/] profile is reset to built-in values every time the app launches so new features and tuning come through. System settings (System tab) are preserved. To keep your own tuning across launches, save it as a named profile here.":
        "注意：[b]Default[/] 設定檔會在每次啟動時重設為內建值，讓新功能與調校能套用進來。系統設定（系統分頁）會保留。若要在每次啟動後保留自己的調校，請在這裡另存成具名設定檔。",
    "Profile": "設定檔",
    "Saved profiles": "已儲存的設定檔",
    "Save current settings": "儲存目前設定",
    "Save profile": "儲存設定檔",
    "Share profile": "分享設定檔",
    "Export & Copy": "匯出並複製",
    "Import": "匯入",
    "Export the selected profile as a short code (copied to your clipboard), or paste a code below and import it.":
        "將選取的設定檔匯出成短代碼（並複製到剪貼簿），或在下方貼上代碼後匯入。",
    "Save and switch named snapshots of your settings.":
        "儲存並切換具名的設定快照。",
    "The Default profile resets on every launch to pick up new features and tuning. System tab settings are preserved. Save a named profile to keep your own tuning.":
        "Default 設定檔會在每次啟動時重設，以套用新功能與調校。系統分頁設定會保留。請儲存具名設定檔來保留自己的調校。",
    "No profile selected.": "尚未選擇設定檔。",
    "Copied {name} to clipboard.": "已將 {name} 複製到剪貼簿。",
    "Copy failed. Select the code and copy manually.": "複製失敗。請選取代碼後手動複製。",
    "Export failed.": "匯出失敗。",
    "Paste a code first.": "請先貼上代碼。",
    "Invalid share code.": "分享代碼無效。",
    "Imported as {name}.": "已匯入為 {name}。",

    # --- controls / system descriptions ---
    "Toggle individual trigger effects. Changes save instantly.":
        "個別開關扳機效果。變更會立即儲存。",
    "Lock the app to a specific DualSense, or let it pick the first one.":
        "將應用程式鎖定到特定 DualSense，或讓它自動選擇第一個找到的手把。",
    "UDP port {port} in use": "UDP 連接埠 {port} 使用中",

    # --- logs tab ---
    "Level": "等級",
    "level": "等級",
    "pause": "暫停",
    "resume": "繼續",
    "clear": "清除",
    "latched": "已鎖定",
    "Live application output. Increase verbosity for debugging.":
        "即時應用程式輸出。除錯時可提高詳細程度。",

    # --- language tab ---
    "Available languages": "可用語言",
    "Pick a language, then restart the app to apply it.":
        "選擇語言後，重新啟動應用程式即可套用。",
    "Restart the app to apply your choice.":
        "重新啟動應用程式以套用你的選擇。",
    "Restart the app to apply the new language.":
        "重新啟動應用程式以套用新語言。",

    # --- R2 實驗性扳機調校 ---
    "Sensitivity": "靈敏度",
    "Experimental features": "實驗性功能",
    "Not recommended for manual adjustment.": "不建議自行調整。",
    "ABS advanced tuning": "ABS 進階調校",
    "Shared feedback": "共享回饋",
    "Redline grip warning": "紅線握把警告",
    "Trigger near redline at": "接近紅線時觸發",
    "Pulse rate (Hz)": "脈衝頻率（Hz）",
    "Grip pulse strength": "握把脈衝強度",
    "Pulse hold time (ms)": "脈衝保持時間（ms）",
    "Traction/grip feedback": "抓地力回饋",
    "Grip feedback strength": "抓地力回饋強度",
    "Traction/grip advanced tuning": "抓地力進階調校",
    "Minimum brake input": "最低煞車輸入",
    "Minimum speed (km/h)": "最低速度（km/h）",
    "Longitudinal slip threshold": "縱向滑移門檻",
    "Combined slip threshold": "綜合滑移門檻",
    "Combined slip influence": "綜合滑移影響",
    "Slip at maximum feedback": "達到最大回饋的滑移量",
    "Minimum frequency (Hz)": "最低頻率（Hz）",
    "Maximum frequency (Hz)": "最高頻率（Hz）",
    "Minimum strength": "最低強度",
    "Feedback hold (ms)": "回饋保持時間（ms）",
    "Top wall zones": "頂部阻力牆區域數",
    "Slip hysteresis": "滑移遲滯",
    "Attack smoothing (ms)": "建立平滑時間（ms）",
    "Release smoothing (ms)": "釋放平滑時間（ms）",
    "G-force damping": "G 力衰減",
    "Burnout rotation threshold": "燒胎轉速門檻",
    "Burnout rotation at maximum feedback": "達到最大回饋的燒胎轉速",
    "Tarmac minimum frequency (Hz)": "鋪裝路最低頻率（Hz）",
    "Tarmac maximum frequency (Hz)": "鋪裝路最高頻率（Hz）",
    "Water minimum frequency (Hz)": "積水最低頻率（Hz）",
    "Water maximum frequency (Hz)": "積水最高頻率（Hz）",
    "Dirt minimum frequency (Hz)": "泥土最低頻率（Hz）",
    "Dirt maximum frequency (Hz)": "泥土最高頻率（Hz）",
    "Gravel minimum frequency (Hz)": "碎石最低頻率（Hz）",
    "Gravel maximum frequency (Hz)": "碎石最高頻率（Hz）",

    # --- external links ---
    "Sponsor": "贊助",
    # --- R3 redline and collision haptics ---
    "Redline feedback": "紅線回饋",
    "R2 trigger redline vibration": "R2 扳機鍵紅線震動",
    "Grip redline vibration": "握把紅線震動",
    "Left grip": "左握把",
    "Right grip": "右握把",
    "Trigger vibration frequency (Hz)": "扳機鍵震動頻率（Hz）",
    "Trigger vibration strength": "扳機鍵震動強度",
    "Trigger hold time (ms)": "扳機鍵保持時間（ms）",
    "Grip trigger near redline at": "握把接近紅線時觸發",
    "Grip pulse rate (Hz)": "握把脈衝頻率（Hz）",
    "Grip redline advanced tuning": "握把紅線進階調校",
    "Low-frequency pulse ratio": "低頻脈衝比例",
    "Redline background level": "紅線背景震動比例",
    "Collision haptics advanced tuning": "碰撞觸覺進階調校",
    "Collision jerk threshold": "碰撞加速度突變門檻",
    "Collision duration (ms)": "碰撞持續時間（ms）",
    "Collision cooldown (ms)": "碰撞冷卻時間（ms）",
    "Collision rebound strength": "碰撞回彈強度",
    "Collision weak-side strength": "碰撞弱側強度",
    "Collision background level": "碰撞背景震動比例",
    "Grip release below redline at": "握把紅線釋放門檻",
    "Grip feedback": "握把回饋",
    "Grip gear-shift thump": "握把換檔衝擊",
    "R2 trigger gear-shift thump": "R2 扳機鍵換檔衝擊",
    "Grip thump strength": "握把衝擊強度",
    "Grip thump length (ms)": "握把衝擊持續時間（毫秒）",
    "Grip signal gain": "握把訊號增益",
}
