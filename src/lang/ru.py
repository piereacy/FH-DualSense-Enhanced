# -*- coding: utf-8 -*-
"""Русский каталог перевода. Ключи — английские исходные строки."""

NAME = "Русский"

STRINGS = {
    "About and licenses": "О программе и лицензиях",
    # --- body haptics ---
    "Body haptics": "Тактильная отдача корпуса",
    "Enable body haptics": "Включить тактильную отдачу корпуса",
    ("Automatically uses high-fidelity USB audio or Bluetooth compatible rumble. "
     "Disable in-game vibration only if you feel competing or doubled output."):
        "Автоматически использует высококачественную аудиотактильную отдачу через USB или "
        "совместимую вибрацию через Bluetooth. Отключайте вибрацию в игре, только если чувствуете, "
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
    "Redline buzz": "Вибрация на отсечке",
    "Wheelspin buzz": "Вибрация при пробуксовке",
    "Idle buzz": "Вибрация на холостом ходу",
    "Throttle stiffness": "Жёсткость газа",

    # --- вкладка «Настройки» — разделы ---
    "Pedal dead zones": "Мёртвые зоны педалей",
    "Left trigger - Brake force": "Левый курок — усилие тормоза",
    "Left trigger - Static wall (optional)": "Левый курок — фиксированный упор (необязательно)",
    "Right trigger - Gas force": "Правый курок — усилие газа",
    "ABS (anti-lock brake) rumble": "Вибрация ABS (антиблокировочной системы)",
    "Redline (rev limiter) buzz": "Вибрация на отсечке (ограничителе оборотов)",
    "Wheelspin buzz": "Вибрация при пробуксовке",
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
    "Wheelspin advanced tuning": "Расширенная настройка пробуксовки",
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
}
