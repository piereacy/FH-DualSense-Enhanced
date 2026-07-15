# -*- coding: utf-8 -*-
"""Русский каталог перевода. Ключи — английские исходные строки."""

NAME = "Русский"

STRINGS = {
    "About and licenses": "О программе и лицензиях",
    # --- body haptics ---
    "Body haptics": "Тактильная отдача корпуса",
    "Enable body haptics": "Включить тактильную отдачу корпуса",
    ("Uses the same haptic mix over USB and Bluetooth; only the transport path differs. "
     "Disable in-game vibration only if you feel competing or doubled output."):
        "USB и Bluetooth используют одну тактильную смесь; отличается только путь передачи. "
        "Отключайте вибрацию в игре, только если чувствуете, "
        "что сигналы конфликтуют или дублируются.",
    "Master intensity": "Общая интенсивность",
    "Engine intensity": "Интенсивность двигателя",
    "Road texture intensity": "Интенсивность дорожной текстуры",
    "Impact and suspension intensity": "Интенсивность ударов и подвески",
    "Slip and ABS intensity": "Интенсивность скольжения и ABS",
    "Slip threshold": "Порог скольжения",

    # --- верхняя панель / вкладки ---
    "Controls": "Управление",
    "Profiles": "Профили",
    "Settings": "Настройки",
    "System": "Система",
    "Language": "Язык",
    "Logs": "Логи",
    "Quit": "Выход",
    "♥ Sponsor": "♥ Поддержать",
    "Changelog": "История изменений",
    "connected": "подключён",
    "waiting": "ожидание",
    "active": "активен",
    "(none)": "(нет)",
    "Backend failed: {error}": "Не удалось запустить бэкенд: {error}",
    "Profile: {name}": "Профиль: {name}",
    "Active: {name}": "Активен: {name}",

    # --- вкладка «Управление» (переключатели эффектов) ---
    "Shift thump": "Толчок при переключении",
    "ABS rumble": "Вибрация ABS",
    "Static brake wall": "Фиксированный упор тормоза",
    "Brake stiffness": "Жёсткость тормоза",
    "Handbrake stiffness bonus": "Доп. жёсткость ручника",
    "Idle buzz": "Вибрация на холостом ходу",
    "Throttle stiffness": "Жёсткость газа",

    # --- вкладка «Настройки» — разделы ---
    "Pedal dead zones": "Мёртвые зоны педалей",
    "Left trigger - Brake force": "Левый курок — усилие тормоза",
    "Left trigger - Static wall (optional)": "Левый курок — фиксированный упор (необязательно)",
    "Right trigger - Gas force": "Правый курок — усилие газа",
    "ABS (anti-lock brake) rumble": "Вибрация ABS (антиблокировочной системы)",
    "Idle buzz": "Вибрация на холостом ходу",
    "Gear shift thump": "Толчок при переключении передачи",

    # --- вкладка «Настройки» — поля ---
    "Gas trigger dead zone": "Мёртвая зона курка газа",
    "Brake trigger dead zone": "Мёртвая зона курка тормоза",
    "Resting stiffness": "Жёсткость в покое",
    "Hard-press stiffness": "Жёсткость при полном нажатии",
    "Stiffness curve shape": "Форма кривой жёсткости",
    "Handbrake extra stiffness": "Доп. жёсткость ручника",
    "Wall position on the trigger": "Положение упора на курке",
    "Wall hardness": "Жёсткость упора",
    "Only when braking harder than": "Только при торможении сильнее",
    "Only when faster than (km/h)": "Только на скорости выше (км/ч)",
    "Wheel slip sensitivity": "Чувствительность к проскальзыванию колёс",
    "Tire grip sensitivity": "Чувствительность к потере сцепления",
    "Rumble speed (Hz)": "Частота вибрации (Гц)",
    "Rumble strength": "Сила вибрации",
    "Fire near redline at": "Срабатывать у отсечки при",
    "Buzz speed (Hz)": "Частота вибрации (Гц)",
    "Buzz strength": "Сила вибрации",
    "Buzz hold time (ms)": "Длительность вибрации (мс)",
    "Idle strength": "Сила на холостом ходу",
    "Thump speed (Hz)": "Частота толчка (Гц)",
    "Thump strength": "Сила толчка",
    "Thump length (ms)": "Длительность толчка (мс)",

    # --- вкладка «Настройки» — кнопки / подсказки ---
    "Reset to defaults": "Сбросить по умолчанию",
    "Click again to confirm reset": "Нажмите ещё раз для подтверждения сброса",
    "In Forza HUD: host 127.0.0.1 (try ::1 if it fails).":
        "В Forza HUD: host 127.0.0.1 (если не работает, попробуйте ::1).",
    "Forward telemetry": "Пересылка телеметрии",
    "Mirror every received packet to another app (e.g. SimHub) without taking the port from it.":
        "Зеркалирует каждый полученный пакет в другое приложение (например, SimHub), не занимая порт.",
    "Forward to": "Пересылать на",
    "host:port targets, comma-separated. Default 127.0.0.1:5301.":
        "Цели host:port через запятую. По умолчанию 127.0.0.1:5301.",
    "UDP port {port} is in use. Close the other listener or change the port in the System tab.": (
        "UDP-порт {port} уже занят. Закройте программу, которая его использует, "
        "или измените порт на вкладке «Система»."
    ),

    # --- вкладка «Система» — разделы / поля ---
    "Forza telemetry (applies on next launch)": "Forza-телеметрия (применится при следующем запуске)",
    "Startup pulse": "Импульс при запуске",
    "Reconnect": "Переподключение",
    "Application behavior": "Поведение приложения",
    "Game detection": "Определение игры",
    "UDP port": "UDP-порт",
    "Startup buzz strength": "Сила вибрации при запуске",
    "Auto-reconnect when controller drops": "Автопереподключение при отключении геймпада",
    "Reconnect check interval (s)": "Интервал проверки подключения (с)",
    "Auto-exit when the game closes": "Автовыход при закрытии игры",
    "Close the app when the game closes": "Закрывать приложение после выхода из игры",
    "Move the app to the tray when minimized": "Сворачивать приложение в системный трей",
    "Game-watch check interval (s)": "Интервал проверки игры (с)",

    # --- DSX ---
    "DSX": "DSX",
    "DSX integration": "Интеграция с DSX",
    "Send triggers to DualSenseX over UDP. Takes effect immediately.":
        "Отправлять триггеры в DualSenseX через UDP. Вступает в силу немедленно.",
    "DSX connection": "Подключение DSX",
    "Host": "Хост",
    "Port": "Порт",
    "Default 127.0.0.1. Match the host in DSX settings.":
        "По умолчанию 127.0.0.1. Должно совпадать с хостом в настройках DSX.",
    "Default 6969. Match the port in DSX settings.":
        "По умолчанию 6969. Должно совпадать с портом в настройках DSX.",
    "DSX is active - controller managed by DSX. Disable DSX to select a controller here.":
        "DSX активен — геймпад управляется DSX. Отключите DSX, чтобы выбрать геймпад здесь.",
    "DSX: active": "DSX: активен",
    "DSX: off": "DSX: выкл",

    # --- вкладка «Система» — блок геймпада ---
    "Controller": "Геймпад",
    "Lock to controller": "Привязать к геймпаду",
    "Rescan": "Сканировать заново",
    "Auto (first found)": "Авто (первый найденный)",
    "attached now": "подключён сейчас",
    "(no serial - not selectable)": "(нет серийного номера — нельзя выбрать)",

    # --- вкладка «Система» — блок обновлений ---
    "Updates": "Обновления",
    "Check for updates at launch": "Проверять обновления при запуске",
    "When off, ZUV will not prompt for updates on startup. Toggle on and restart the app to check for a new release.": (
        "Если выключено, ZUV не будет предлагать обновления при запуске. "
        "Включите и перезапустите приложение, чтобы проверить новую версию."
    ),
    "ZUV not found: this build is not running inside a ZUV bundle (ZUV_CACHE_ROOT env var is missing), so the update toggle has nothing to control. Run the bundled .zuv.py to manage updates.": (
        "ZUV не найден: эта сборка запущена не внутри ZUV-пакета "
        "(переменная окружения ZUV_CACHE_ROOT отсутствует), поэтому переключателю "
        "обновлений нечем управлять. Запустите .zuv.py из поставки для управления обновлениями."
    ),

    # --- вкладка «Профили» ---
    "Load": "Загрузить",
    "Rename": "Переименовать",
    "Delete": "Удалить",
    "Save": "Сохранить",
    "New profile name": "Имя нового профиля",
    "File: {path}": "Файл: {path}",
    "Note: the [b]Default[/] profile is reset to built-in values every time the app launches so new features and tuning come through. System settings (System tab) are preserved. To keep your own tuning across launches, save it as a named profile here.": (
        "Примечание: профиль [b]Default[/] сбрасывается к встроенным значениям при каждом "
        "запуске приложения, чтобы применялись новые функции и настройки. Системные настройки "
        "(вкладка «Система») сохраняются. Чтобы сохранить свои настройки между запусками, "
        "сохраните их здесь как отдельный профиль."
    ),

    # --- вкладка «Логи» ---
    "level": "уровень",
    "pause": "пауза",
    "resume": "продолжить",
    "clear": "очистить",

    # --- экспериментальная настройка триггеров R2 ---
    "Sensitivity": "Чувствительность",
    "Experimental features": "Экспериментальные функции",
    "Not recommended for manual adjustment.": "Ручная настройка не рекомендуется.",
    "ABS advanced tuning": "Расширенная настройка ABS",
    "Shared feedback": "Общая обратная связь",
    "Redline grip warning": "Предупреждение об отсечке на рукоятках",
    "Trigger near redline at": "Срабатывание у красной зоны",
    "Pulse rate (Hz)": "Частота импульса (Гц)",
    "Grip pulse strength": "Сила импульса рукояток",
    "Pulse hold time (ms)": "Удержание импульса (мс)",
    "Traction/grip feedback": "Обратная связь сцепления",
    "Grip feedback strength": "Сила обратной связи сцепления",
    "Traction/grip advanced tuning": "Расширенная настройка сцепления",
    "Minimum brake input": "Минимальное нажатие тормоза",
    "Minimum speed (km/h)": "Минимальная скорость (км/ч)",
    "Longitudinal slip threshold": "Порог продольного скольжения",
    "Combined slip threshold": "Порог комбинированного скольжения",
    "Combined slip influence": "Влияние комбинированного скольжения",
    "Slip at maximum feedback": "Скольжение при максимальной отдаче",
    "Minimum frequency (Hz)": "Минимальная частота (Гц)",
    "Maximum frequency (Hz)": "Максимальная частота (Гц)",
    "Minimum strength": "Минимальная сила",
    "Feedback hold (ms)": "Удержание отдачи (мс)",
    "Top wall zones": "Верхние зоны упора",
    "Slip hysteresis": "Гистерезис скольжения",
    "Attack smoothing (ms)": "Сглаживание нарастания (мс)",
    "Release smoothing (ms)": "Сглаживание отпускания (мс)",
    "G-force damping": "Демпфирование перегрузкой",
    "Burnout rotation threshold": "Порог вращения при пробуксовке",
    "Burnout rotation at maximum feedback": "Вращение при максимальной отдаче",
    "Tarmac minimum frequency (Hz)": "Асфальт: минимальная частота (Гц)",
    "Tarmac maximum frequency (Hz)": "Асфальт: максимальная частота (Гц)",
    "Water minimum frequency (Hz)": "Вода: минимальная частота (Гц)",
    "Water maximum frequency (Hz)": "Вода: максимальная частота (Гц)",
    "Dirt minimum frequency (Hz)": "Грунт: минимальная частота (Гц)",
    "Dirt maximum frequency (Hz)": "Грунт: максимальная частота (Гц)",
    "Gravel minimum frequency (Hz)": "Гравий: минимальная частота (Гц)",
    "Gravel maximum frequency (Hz)": "Гравий: максимальная частота (Гц)",

    # --- вкладка «Язык» ---
    "Pick a language, then restart the app to apply it.":
        "Выберите язык, затем перезапустите приложение, чтобы применить его.",
    "Restart the app to apply the new language.":
        "Перезапустите приложение, чтобы применить новый язык.",
    # --- R3 redline and collision haptics ---
    "Redline feedback": "Обратная связь красной зоны",
    "R2 trigger redline vibration": "Вибрация R2-триггера в красной зоне",
    "Grip redline vibration": "Вибрация рукояток в красной зоне",
    "Left grip": "Левая рукоятка",
    "Right grip": "Правая рукоятка",
    "Trigger vibration frequency (Hz)": "Частота вибрации триггера (Гц)",
    "Trigger vibration strength": "Сила вибрации триггера",
    "Trigger hold time (ms)": "Удержание триггера (мс)",
    "Grip trigger near redline at": "Порог красной зоны для рукояток",
    "Grip pulse rate (Hz)": "Частота импульса рукояток (Гц)",
    "Grip redline advanced tuning": "Расширенная настройка красной зоны рукояток",
    "Low-frequency pulse ratio": "Доля низкочастотного импульса",
    "Redline background level": "Фоновый уровень в красной зоне",
    "Collision haptics advanced tuning": "Расширенная настройка столкновений",
    "Collision jerk threshold": "Порог рывка при столкновении",
    "Collision duration (ms)": "Длительность столкновения (мс)",
    "Collision cooldown (ms)": "Задержка повторного столкновения (мс)",
    "Collision rebound strength": "Сила отскока столкновения",
    "Collision weak-side strength": "Сила слабой стороны столкновения",
    "Collision background level": "Фоновый уровень при столкновении",
    "Grip release below redline at": "Порог отключения рукояток",
    "Grip feedback": "Обратная связь рукояток",
    "Grip gear-shift thump": "Толчок рукояток при переключении",
    "R2 trigger gear-shift thump": "Толчок курка R2 при переключении",
    "Grip thump strength": "Сила толчка рукояток",
    "Grip thump length (ms)": "Длительность толчка рукояток (мс)",
    "Grip signal gain": "Усиление сигнала рукояток",
}

STRINGS.update({
    "R2 optional dynamic resistance": "Дополнительное динамическое сопротивление R2",
    "Boost activation threshold": "Порог включения наддува",
    "Boost extra resistance": "Добавочное сопротивление наддува",
    "G-force extra resistance": "Добавочное сопротивление от перегрузки",
    "Grip pulse width": "Ширина импульса рукояток",
    "Grip entry impact": "Начальный удар рукояток",
    "Grip entry impact duration (ms)": "Длительность начального удара (мс)",
    "Optional trigger events": "Дополнительные события курков",
    "Collision trigger frequency (Hz)": "Частота удара курка при столкновении (Гц)",
    "Collision trigger strength": "Сила удара курка при столкновении",
    "Collision trigger duration (ms)": "Длительность удара курка (мс)",
    "Road texture frequency (Hz)": "Частота текстуры дороги (Гц)",
    "Road texture strength": "Сила текстуры дороги",
    "Rumble strip frequency (Hz)": "Частота виброполосы (Гц)",
    "Rumble strip strength": "Сила виброполосы",
    "Collision trigger jolt": "Удар курка при столкновении",
    "Idle road texture": "Текстура дороги при отпущенном курке",
    "Turbo boost resistance": "Сопротивление турбонаддува",
    "G-force resistance": "Сопротивление от перегрузки",
    "G-force resistance advanced tuning": "Расширенная настройка сопротивления от перегрузки",
    "Lateral G weight": "Вес поперечной перегрузки",
    "Longitudinal G weight": "Вес продольной перегрузки",
    "G force at maximum resistance": "Перегрузка для максимального сопротивления",
    "G-force attack smoothing (ms)": "Сглаживание нарастания перегрузки (мс)",
    "G-force release smoothing (ms)": "Сглаживание спада перегрузки (мс)",
    "Controller lighting": "Подсветка контроллера",
    "Optional visual feedback with independent switches.": "Дополнительная визуальная индикация с отдельными переключателями.",
    "Tachometer lightbar": "Световая панель тахометра",
    "Enable tachometer lightbar": "Включить световую панель тахометра",
    "Uses controller lighting only; it does not change trigger or grip feedback.":
        "Использует только подсветку контроллера и не меняет отдачу курков или рукояток.",
    "Lightbar starts at RPM ratio": "Порог оборотов для включения панели",
    "Lightbar flashes at RPM ratio": "Порог оборотов для мигания панели",
    "Flash rate (Hz)": "Частота мигания (Гц)",
    "Lightbar brightness": "Яркость световой панели",
    "Lightbar colors": "Цвета световой панели",
    "Start color red": "Начальный красный",
    "Start color green": "Начальный зелёный",
    "Start color blue": "Начальный синий",
    "Redline color red": "Красный на отсечке",
    "Redline color green": "Зелёный на отсечке",
    "Redline color blue": "Синий на отсечке",
    "Gear player LEDs": "Индикаторы передачи",
    "Show gear on player LEDs": "Показывать передачу индикаторами игрока",
    "Gears 1 to 5+ use the five white player indicator LEDs.":
        "Передачи от 1 до 5+ отображаются пятью белыми индикаторами игрока.",
})

STRINGS.update({
    "Overview": "Обзор", "Drive": "Вождение", "Driving feedback": "Обратная связь вождения",
    "Grip haptics": "Тактильная отдача рукояток", "Lights": "Подсветка", "Lang": "Язык",
    "System and updates": "Система и обновления",
    "Controller, telemetry, profile, and update status at a glance.": "Состояние контроллера, телеметрии, профиля и обновлений на одном экране.",
    "Every interface variant uses the same settings, haptic engine, and controller backend.": "Все три интерфейса используют одинаковые настройки, тактильный движок и сервер контроллера.",
    "Active profile": "Активный профиль", "Changes save instantly": "Изменения сохраняются сразу",
    "Connected": "Подключён", "Waiting": "Ожидание", "Listening": "Приём данных",
    "Waiting for packets": "Ожидание телеметрии", "USB or Bluetooth": "USB или Bluetooth",
    "Transport: {transport}": "Подключение: {transport}", "Forza telemetry": "Телеметрия Forza",
    "UDP data out": "UDP Data Out", "UDP port {port}": "UDP-порт {port}",
    "UDP port {port} in use": "UDP-порт {port} уже используется",
    "Quick access": "Быстрый доступ", "R4 workspace": "Рабочая область R4", "DualSense": "DualSense",
    "Profile": "Профиль", "Automatically check for updates": "Автоматически проверять обновления",
    "Download updates in the background": "Загружать обновления в фоне",
    "Check now": "Проверить сейчас", "Download update": "Загрузить обновление",
    "Restart and install": "Перезапустить и установить", "View release": "Открыть Release",
    "Update status: idle": "Обновление: ожидание", "Built-in updater": "Встроенное обновление",
    "Windows EXE": "Windows EXE", "Unavailable in this runtime": "Недоступно в этом режиме запуска",
    "Built-in updates require the Windows standalone EXE": "Для встроенного обновления нужен автономный Windows EXE",
    "Checking for updates": "Проверка обновлений", "You are up to date": "Установлена последняя версия",
    "Update available: {tag}": "Доступно обновление: {tag}", "Downloading update": "Загрузка обновления",
    "Verifying update": "Проверка обновления", "Update ready to install": "Обновление готово к установке",
    "Restarting to install": "Перезапуск для установки", "Update failed": "Ошибка обновления",
    "Could not start update: {error}": "Не удалось запустить обновление: {error}",
    "Toggle individual trigger effects. Changes save instantly.": "Включайте эффекты курков по отдельности. Изменения сохраняются сразу.",
    "Lock the app to a specific DualSense, or let it pick the first one.": "Закрепить приложение за выбранным DualSense или автоматически выбрать первый.",
    "Available languages": "Доступные языки", "Restart the app to apply your choice.": "Перезапустите приложение, чтобы применить выбор.",
    "Save and switch named snapshots of your settings.": "Сохраняйте и переключайте именованные снимки настроек.",
    "Saved profiles": "Сохранённые профили", "Save current settings": "Сохранить текущие настройки",
    "Save profile": "Сохранить профиль", "Share profile": "Поделиться профилем",
    "Export & Copy": "Экспортировать и копировать", "Import": "Импортировать",
    "Export the selected profile as a short code (copied to your clipboard), or paste a code below and import it.": "Экспортируйте выбранный профиль в короткий код с копированием в буфер или вставьте код ниже для импорта.",
    "No profile selected.": "Профиль не выбран.", "Copied {name} to clipboard.": "{name} скопирован в буфер обмена.",
    "Copy failed. Select the code and copy manually.": "Не удалось скопировать. Выделите код и скопируйте вручную.",
    "Export failed.": "Ошибка экспорта.", "Paste a code first.": "Сначала вставьте код.",
    "Invalid share code.": "Недопустимый код профиля.", "Imported as {name}.": "Импортировано как {name}.",
    "The Default profile resets on every launch to pick up new features and tuning. System tab settings are preserved. Save a named profile to keep your own tuning.": "Профиль Default обновляется при каждом запуске, чтобы получать новые функции и настройки. Параметры раздела системы сохраняются. Создайте именованный профиль для своих настроек.",
    "Live application output. Increase verbosity for debugging.": "Текущий журнал приложения. Для диагностики увеличьте подробность.",
    "Level": "Уровень", "latched": "удержание связи",
})
