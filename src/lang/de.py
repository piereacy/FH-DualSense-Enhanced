# -*- coding: utf-8 -*-
"""Deutsch (German) catalog. Keys are the English source strings."""

NAME = "Deutsch"

STRINGS = {
    "About and licenses": "Info und Lizenzen",
    # --- body haptics ---
    "Body haptics": "Körperhaptik",
    "Enable body haptics": "Körperhaptik aktivieren",
    ("Uses the same haptic mix over USB and Bluetooth; only the transport path differs. "
     "Disable in-game vibration only if you feel competing or doubled output."):
        "USB und Bluetooth verwenden denselben Haptik-Mix; nur der Übertragungsweg unterscheidet sich. "
        "Deaktiviere die Vibration im Spiel nur, wenn sich die Ausgaben gegenseitig stören "
        "oder doppelt anfühlen.",
    "Master intensity": "Gesamtintensität",
    "Engine intensity": "Motorintensität",
    "Road texture intensity": "Straßentexturintensität",
    "Impact and suspension intensity": "Aufprall- und Federungsintensität",
    "Slip and ABS intensity": "Schlupf- und ABS-Intensität",
    "Slip threshold": "Schlupfschwelle",

    # --- chrome / tabs ---
    "Controls": "Steuerung",
    "Profiles": "Profile",
    "Settings": "Einstellungen",
    "System": "System",
    "Language": "Sprache",
    "Logs": "Protokoll",
    "Quit": "Beenden",
    "♥ Sponsor": "♥ Sponsor",
    "Changelog": "Änderungsprotokoll",
    "connected": "verbunden",
    "waiting": "wartet",
    "active": "aktiv",
    "(none)": "(keine)",
    "Backend failed: {error}": "Backend fehlgeschlagen: {error}",
    "Profile: {name}": "Profil: {name}",
    "Active: {name}": "Aktiv: {name}",

    # --- controls tab (per-trigger effect switches) ---
    "Shift thump": "Schaltruck",
    "ABS rumble": "ABS-Vibration",
    "Static brake wall": "Statische Bremswand",
    "Brake stiffness": "Bremswiderstand",
    "Handbrake stiffness bonus": "Zusätzlicher Handbremswiderstand",
    "Idle buzz": "Leerlauf-Surren",
    "Throttle stiffness": "Gaswiderstand",

    # --- settings tab sections ---
    "Pedal dead zones": "Pedal-Totzonen",
    "Left trigger - Brake force": "Linker Trigger - Bremskraft",
    "Left trigger - Static wall (optional)": "Linker Trigger - Statische Wand (optional)",
    "Right trigger - Gas force": "Rechter Trigger - Gaskraft",
    "ABS (anti-lock brake) rumble": "ABS (Antiblockiersystem)-Vibration",
    "Idle buzz": "Leerlauf-Surren",
    "Gear shift thump": "Schaltruck",

    # --- settings tab fields ---
    "Gas trigger dead zone": "Gas-Trigger-Totzone",
    "Brake trigger dead zone": "Brems-Trigger-Totzone",
    "Resting stiffness": "Ruhewiderstand",
    "Hard-press stiffness": "Widerstand bei vollem Druck",
    "Stiffness curve shape": "Form der Widerstandskurve",
    "Handbrake extra stiffness": "Zusätzlicher Handbremswiderstand",
    "Wall position on the trigger": "Wandposition am Trigger",
    "Wall hardness": "Wandhärte",
    "Only when braking harder than": "Nur beim Bremsen stärker als",
    "Only when faster than (km/h)": "Nur bei Geschwindigkeit über (km/h)",
    "Wheel slip sensitivity": "Radschlupf-Empfindlichkeit",
    "Tire grip sensitivity": "Reifengrip-Empfindlichkeit",
    "Rumble speed (Hz)": "Vibrationsfrequenz (Hz)",
    "Rumble strength": "Vibrationsstärke",
    "Fire near redline at": "Auslösen nahe Drehzahlgrenze bei",
    "Buzz speed (Hz)": "Surrfrequenz (Hz)",
    "Buzz strength": "Surrstärke",
    "Buzz hold time (ms)": "Surr-Haltezeit (ms)",
    "Idle strength": "Leerlaufstärke",
    "Thump speed (Hz)": "Ruckfrequenz (Hz)",
    "Thump strength": "Ruckstärke",
    "Thump length (ms)": "Ruckdauer (ms)",

    # --- settings tab buttons / hints ---
    "Reset to defaults": "Auf Standard zurücksetzen",
    "Click again to confirm reset": "Zum Bestätigen erneut klicken",
    "In Forza HUD: host 127.0.0.1 (try ::1 if it fails).":
        "Im Forza-HUD: Host 127.0.0.1 (bei Problemen ::1 versuchen).",
    "Forward telemetry": "Telemetrie weiterleiten",
    "Mirror every received packet to another app (e.g. SimHub) without taking the port from it.":
        "Spiegelt jedes empfangene Paket an eine andere App (z. B. SimHub), ohne ihr den Port wegzunehmen.",
    "Forward to": "Weiterleiten an",
    "host:port targets, comma-separated. Default 127.0.0.1:5301.":
        "host:port-Ziele, durch Komma getrennt. Standard 127.0.0.1:5301.",
    "UDP port {port} is in use. Close the other listener or change the port in the System tab.":
        "UDP-Port {port} ist belegt. Schließen Sie den anderen Listener oder ändern Sie den Port im System-Tab.",

    # --- system tab sections / fields ---
    "Forza telemetry (applies on next launch)": "Forza-Telemetrie (wird beim nächsten Start übernommen)",
    "Startup pulse": "Start-Impuls",
    "Reconnect": "Wiederverbinden",
    "Application behavior": "Anwendungsverhalten",
    "Game detection": "Spielerkennung",
    "UDP port": "UDP-Port",
    "Startup buzz strength": "Start-Surrstärke",
    "Auto-reconnect when controller drops": "Automatisch wiederverbinden bei Controller-Verlust",
    "Reconnect check interval (s)": "Prüfintervall für Wiederverbindung (s)",
    "Auto-exit when the game closes": "Automatisch beenden, wenn das Spiel schließt",
    "Close the app when the game closes": "App schließen, wenn das Spiel beendet wird",
    "Move the app to the tray when minimized": "App beim Minimieren in den Infobereich verschieben",
    "Game-watch check interval (s)": "Prüfintervall der Spielüberwachung (s)",

    # --- DSX ---
    "DSX": "DSX",
    "DSX integration": "DSX-Integration",
    "Send triggers to DualSenseX over UDP. Takes effect immediately.":
        "Trigger über UDP an DualSenseX senden. Wird sofort wirksam.",
    "DSX connection": "DSX-Verbindung",
    "Host": "Host",
    "Port": "Port",
    "Default 127.0.0.1. Match the host in DSX settings.":
        "Standard 127.0.0.1. Muss mit dem Host in den DSX-Einstellungen übereinstimmen.",
    "Default 6969. Match the port in DSX settings.":
        "Standard 6969. Muss mit dem Port in den DSX-Einstellungen übereinstimmen.",
    "DSX is active - controller managed by DSX. Disable DSX to select a controller here.":
        "DSX ist aktiv - Controller wird von DSX verwaltet. Deaktivieren Sie DSX, um hier einen Controller auszuwählen.",
    "DSX: active": "DSX: aktiv",
    "DSX: off": "DSX: aus",

    # --- system tab controller block ---
    "Controller": "Controller",
    "Lock to controller": "Auf Controller festlegen",
    "Rescan": "Neu suchen",
    "Auto (first found)": "Automatisch (erster gefundener)",
    "attached now": "jetzt verbunden",
    "(no serial - not selectable)": "(keine Seriennummer - nicht auswählbar)",

    # --- system tab updates block ---
    "Updates": "Updates",
    "Check for updates at launch": "Beim Start nach Updates suchen",
    "When off, ZUV will not prompt for updates on startup. Toggle on and restart the app to check for a new release.":
        "Wenn deaktiviert, fragt ZUV beim Start nicht nach Updates. Aktivieren Sie die Option und starten Sie die App neu, um nach einer neuen Version zu suchen.",
    "ZUV not found: this build is not running inside a ZUV bundle (ZUV_CACHE_ROOT env var is missing), so the update toggle has nothing to control. Run the bundled .zuv.py to manage updates.":
        "ZUV nicht gefunden: Dieser Build läuft nicht in einem ZUV-Bundle (Umgebungsvariable ZUV_CACHE_ROOT fehlt), daher steuert der Update-Schalter nichts. Führen Sie die gebündelte .zuv.py aus, um Updates zu verwalten.",

    # --- profiles tab ---
    "Load": "Laden",
    "Rename": "Umbenennen",
    "Delete": "Löschen",
    "Save": "Speichern",
    "New profile name": "Neuer Profilname",
    "File: {path}": "Datei: {path}",
    "Note: the [b]Default[/] profile is reset to built-in values every time the app launches so new features and tuning come through. System settings (System tab) are preserved. To keep your own tuning across launches, save it as a named profile here.":
        "Hinweis: Das Profil [b]Default[/] wird bei jedem Start auf die integrierten Werte zurückgesetzt, damit neue Funktionen und Abstimmungen übernommen werden. Die Systemeinstellungen (System-Tab) bleiben erhalten. Um Ihre eigene Abstimmung über Neustarts hinweg zu behalten, speichern Sie sie hier als benanntes Profil.",
    "Profile": "Profil",
    "Saved profiles": "Gespeicherte Profile",
    "Save current settings": "Aktuelle Einstellungen speichern",
    "Save profile": "Profil speichern",
    "Share profile": "Profil teilen",
    "Export & Copy": "Exportieren & Kopieren",
    "Import": "Importieren",
    "Export the selected profile as a short code (copied to your clipboard), or paste a code below and import it.":
        "Das ausgewählte Profil als Kurzcode exportieren (in die Zwischenablage kopiert) oder unten einen Code einfügen und importieren.",
    "Save and switch named snapshots of your settings.":
        "Benannte Schnappschüsse Ihrer Einstellungen speichern und wechseln.",
    "The Default profile resets on every launch to pick up new features and tuning. System tab settings are preserved. Save a named profile to keep your own tuning.":
        "Das Default-Profil wird bei jedem Start zurückgesetzt, um neue Funktionen und Abstimmungen zu übernehmen. Die Einstellungen im System-Tab bleiben erhalten. Speichern Sie ein benanntes Profil, um Ihre eigene Abstimmung zu behalten.",
    "No profile selected.": "Kein Profil ausgewählt.",
    "Copied {name} to clipboard.": "{name} in die Zwischenablage kopiert.",
    "Copy failed. Select the code and copy manually.": "Kopieren fehlgeschlagen. Markieren Sie den Code und kopieren Sie ihn manuell.",
    "Export failed.": "Export fehlgeschlagen.",
    "Paste a code first.": "Fügen Sie zuerst einen Code ein.",
    "Invalid share code.": "Ungültiger Freigabecode.",
    "Imported as {name}.": "Als {name} importiert.",

    # --- controls / system descriptions ---
    "Toggle individual trigger effects. Changes save instantly.":
        "Einzelne Trigger-Effekte umschalten. Änderungen werden sofort gespeichert.",
    "Lock the app to a specific DualSense, or let it pick the first one.":
        "Die App auf einen bestimmten DualSense festlegen oder den ersten gefundenen verwenden.",
    "UDP port {port} in use": "UDP-Port {port} belegt",

    # --- logs tab ---
    "Level": "Stufe",
    "level": "Stufe",
    "pause": "Pause",
    "resume": "Fortsetzen",
    "clear": "Leeren",
    "latched": "fixiert",
    "Live application output. Increase verbosity for debugging.":
        "Live-Ausgabe der App. Für die Fehlersuche die Ausführlichkeit erhöhen.",

    # --- language tab ---
    "Available languages": "Verfügbare Sprachen",
    "Pick a language, then restart the app to apply it.":
        "Wählen Sie eine Sprache und starten Sie die App neu, um sie zu übernehmen.",
    "Restart the app to apply your choice.":
        "Starten Sie die App neu, um Ihre Auswahl zu übernehmen.",
    "Restart the app to apply the new language.":
        "Starten Sie die App neu, um die neue Sprache zu übernehmen.",

    # --- R2 experimentelle Trigger-Abstimmung ---
    "Sensitivity": "Empfindlichkeit",
    "Experimental features": "Experimentelle Funktionen",
    "Not recommended for manual adjustment.": "Manuelle Anpassung wird nicht empfohlen.",
    "Experimental dynamic resistance": "Experimenteller dynamischer Widerstand",
    "Experimental collision trigger feedback": "Experimentelles Kollisions-Trigger-Feedback",
    "Experimental road texture trigger feedback": "Experimentelles Fahrbahn-Trigger-Feedback",
    "ABS advanced tuning": "Erweiterte ABS-Abstimmung",
    "Shared feedback": "Gemeinsames Feedback",
    "Redline grip warning": "Drehzahlgrenzen-Warnung am Griff",
    "Trigger near redline at": "Nahe der Drehzahlgrenze auslösen bei",
    "Pulse rate (Hz)": "Pulsrate (Hz)",
    "Grip pulse strength": "Stärke des Griffpulses",
    "Pulse hold time (ms)": "Pulshaltezeit (ms)",
    "Traction/grip feedback": "Traktions-/Grip-Feedback",
    "Grip feedback strength": "Stärke des Grip-Feedbacks",
    "Traction/grip advanced tuning": "Erweiterte Traktions-/Grip-Abstimmung",
    "Minimum brake input": "Minimale Bremseingabe",
    "Minimum speed (km/h)": "Mindestgeschwindigkeit (km/h)",
    "Longitudinal slip threshold": "Schwelle für Längsschlupf",
    "Combined slip threshold": "Schwelle für kombinierten Schlupf",
    "Combined slip influence": "Einfluss des kombinierten Schlupfs",
    "Slip at maximum feedback": "Schlupf bei maximalem Feedback",
    "Minimum frequency (Hz)": "Minimale Frequenz (Hz)",
    "Maximum frequency (Hz)": "Maximale Frequenz (Hz)",
    "Minimum strength": "Minimale Stärke",
    "Feedback hold (ms)": "Feedback-Haltezeit (ms)",
    "Top wall zones": "Obere Wandzonen",
    "Slip hysteresis": "Schlupf-Hysterese",
    "Attack smoothing (ms)": "Anstiegs-Glättung (ms)",
    "Release smoothing (ms)": "Abfall-Glättung (ms)",
    "G-force damping": "G-Kraft-Dämpfung",
    "Burnout rotation threshold": "Burnout-Drehzahlschwelle",
    "Burnout rotation at maximum feedback": "Burnout-Drehzahl bei maximalem Feedback",
    "Tarmac minimum frequency (Hz)": "Asphalt: minimale Frequenz (Hz)",
    "Tarmac maximum frequency (Hz)": "Asphalt: maximale Frequenz (Hz)",
    "Water minimum frequency (Hz)": "Wasser: minimale Frequenz (Hz)",
    "Water maximum frequency (Hz)": "Wasser: maximale Frequenz (Hz)",
    "Dirt minimum frequency (Hz)": "Erde: minimale Frequenz (Hz)",
    "Dirt maximum frequency (Hz)": "Erde: maximale Frequenz (Hz)",
    "Gravel minimum frequency (Hz)": "Schotter: minimale Frequenz (Hz)",
    "Gravel maximum frequency (Hz)": "Schotter: maximale Frequenz (Hz)",

    # --- external links ---
    "Sponsor": "Sponsor",
    # --- R3 redline and collision haptics ---
    "Redline feedback": "Drehzahlgrenzen-Feedback",
    "R2 trigger redline vibration": "R2-Trigger-Vibration am Drehzahlbegrenzer",
    "Grip redline vibration": "Griffvibration am Drehzahlbegrenzer",
    "Left grip": "Linker Griff",
    "Right grip": "Rechter Griff",
    "Trigger vibration frequency (Hz)": "Trigger-Vibrationsfrequenz (Hz)",
    "Trigger vibration strength": "Trigger-Vibrationsstärke",
    "Trigger hold time (ms)": "Trigger-Haltezeit (ms)",
    "Grip trigger near redline at": "Griffwarnung auslösen bei",
    "Grip pulse rate (Hz)": "Griff-Pulsrate (Hz)",
    "Grip redline advanced tuning": "Erweiterte Griff-Drehzahlgrenzen-Abstimmung",
    "Low-frequency pulse ratio": "Anteil des niederfrequenten Pulses",
    "Redline background level": "Hintergrundpegel bei Drehzahlgrenze",
    "Collision haptics advanced tuning": "Erweiterte Kollisionshaptik",
    "Collision jerk threshold": "Kollisions-Ruckschwelle",
    "Collision duration (ms)": "Kollisionsdauer (ms)",
    "Collision cooldown (ms)": "Kollisions-Sperrzeit (ms)",
    "Collision rebound strength": "Stärke des Kollisionsrückpralls",
    "Collision weak-side strength": "Stärke der schwächeren Kollisionsseite",
    "Collision background level": "Hintergrundpegel bei Kollision",
    "Grip release below redline at": "Griffwarnung lösen unter",
    "Grip feedback": "Griff-Feedback",
    "Grip gear-shift thump": "Griff-Schaltruck",
    "R2 trigger gear-shift thump": "R2-Trigger-Schaltruck",
    "Grip thump strength": "Stärke des Griff-Schaltrucks",
    "Grip thump length (ms)": "Dauer des Griff-Schaltrucks (ms)",
    "Grip signal gain": "Griff-Signalverstärkung",
}

STRINGS.update({
    "R2 optional dynamic resistance": "Optionale dynamische R2-Triggerkraft",
    "Boost activation threshold": "Ladedruck-Aktivierungsschwelle",
    "Boost extra resistance": "Zusätzlicher Ladedruckwiderstand",
    "G-force extra resistance": "Zusätzlicher G-Kraft-Widerstand",
    "Grip pulse width": "Griff-Pulsbreite",
    "Grip entry impact": "Griff-Eintrittsimpuls",
    "Grip entry impact duration (ms)": "Dauer des Eintrittsimpulses (ms)",
    "Optional trigger events": "Optionale Triggerereignisse",
    "Collision trigger frequency (Hz)": "Kollisionstrigger-Frequenz (Hz)",
    "Collision trigger strength": "Kollisionstrigger-Stärke",
    "Collision trigger duration (ms)": "Kollisionstrigger-Dauer (ms)",
    "Road texture frequency (Hz)": "Fahrbahntextur-Frequenz (Hz)",
    "Road texture strength": "Fahrbahntextur-Stärke",
    "Rumble strip frequency (Hz)": "Rüttelstreifen-Frequenz (Hz)",
    "Rumble strip strength": "Rüttelstreifen-Stärke",
    "Collision trigger jolt": "Kollisionstrigger-Stoß",
    "Idle road texture": "Fahrbahntextur bei freiem Trigger",
    "L2 collision trigger jolt": "L2-Kollisionstrigger-Stoß",
    "R2 collision trigger jolt": "R2-Kollisionstrigger-Stoß",
    "L2 idle road texture": "L2-Fahrbahntextur bei freiem Trigger",
    "R2 idle road texture": "R2-Fahrbahntextur bei freiem Trigger",
    "Turbo boost resistance": "Turboladedruck-Widerstand",
    "G-force resistance": "G-Kraft-Widerstand",
    "G-force resistance advanced tuning": "Erweiterte G-Kraft-Widerstandsabstimmung",
    "Lateral G weight": "Gewichtung der Querbeschleunigung",
    "Longitudinal G weight": "Gewichtung der Längsbeschleunigung",
    "G force at maximum resistance": "G-Kraft bei maximalem Widerstand",
    "G-force attack smoothing (ms)": "G-Kraft-Anstiegsdämpfung (ms)",
    "G-force release smoothing (ms)": "G-Kraft-Abklingdämpfung (ms)",
    "Controller lighting": "Controller-Beleuchtung",
    "Optional visual feedback with independent switches.": "Optionales visuelles Feedback mit getrennten Schaltern.",
    "Tachometer lightbar": "Drehzahlmesser-Lichtleiste",
    "Enable tachometer lightbar": "Drehzahlmesser-Lichtleiste aktivieren",
    "Uses controller lighting only; it does not change trigger or grip feedback.":
        "Verwendet nur die Controller-Beleuchtung; Trigger- und Griff-Feedback bleiben unverändert.",
    "Lightbar starts at RPM ratio": "Lichtleiste startet bei Drehzahlverhältnis",
    "Lightbar flashes at RPM ratio": "Lichtleiste blinkt bei Drehzahlverhältnis",
    "Flash rate (Hz)": "Blinkfrequenz (Hz)",
    "Lightbar brightness": "Helligkeit der Lichtleiste",
    "Lightbar colors": "Farben der Lichtleiste",
    "Start color red": "Startfarbe Rot",
    "Start color green": "Startfarbe Grün",
    "Start color blue": "Startfarbe Blau",
    "Redline color red": "Begrenzerfarbe Rot",
    "Redline color green": "Begrenzerfarbe Grün",
    "Redline color blue": "Begrenzerfarbe Blau",
    "Gear player LEDs": "Gang-Player-LEDs",
    "Show gear on player LEDs": "Gang über Player-LEDs anzeigen",
    "Gears 1 to 5+ use the five white player indicator LEDs.":
        "Die Gänge 1 bis 5+ verwenden die fünf weißen Player-LEDs.",
})

STRINGS.update({
    "Save settings before exit?": "Einstellungen vor dem Beenden speichern?",
    "Save your tuning before exit?": "Abstimmung vor dem Beenden speichern?",
    "Default already autosaved these changes. Save a named profile to keep a reusable snapshot.":
        "Default hat diese Änderungen automatisch gespeichert. Speichere ein benanntes Profil als wiederverwendbare Momentaufnahme.",
    "Save as named profile and exit": "Als benanntes Profil speichern und beenden",
    "Exit directly": "Direkt beenden",
    "Cancel": "Abbrechen",
    "Profile name cannot be empty.": "Der Profilname darf nicht leer sein.",
    "Could not save the profile. Please try again.": "Das Profil konnte nicht gespeichert werden. Bitte erneut versuchen.",
    "Restore factory defaults": "Werkseinstellungen wiederherstellen",
    "Restore all factory defaults?": "Alle Werkseinstellungen wiederherstellen?",
    "This resets haptics, system settings, language, and Default. Named profiles are kept.":
        "Dies setzt Haptik, Systemeinstellungen, Sprache und Default zurück. Benannte Profile bleiben erhalten.",
    "Restore defaults": "Standardwerte wiederherstellen",
    "Could not restore defaults. Check the log and try again.": "Standardwerte konnten nicht wiederhergestellt werden. Protokoll prüfen und erneut versuchen.",
    "Factory defaults restored. Restart to refresh the interface language.":
        "Werkseinstellungen wiederhergestellt. Zum Aktualisieren der Oberflächensprache neu starten.",
    "Default autosaves and persists across restarts. Save a named profile when you want a reusable snapshot.":
        "Default speichert automatisch und bleibt nach Neustarts erhalten. Für eine wiederverwendbare Momentaufnahme ein benanntes Profil speichern.",
    "Miku Console uses the shared settings, haptic engine, and controller backend.":
        "Miku Console nutzt die gemeinsamen Einstellungen, die Haptik-Engine und das Controller-Backend.",
})

STRINGS.update({
    "Overview": "Übersicht", "Drive": "Fahren", "Driving feedback": "Fahrfeedback",
    "Grip haptics": "Griff-Haptik", "Lights": "Licht", "Lang": "Sprache",
    "System and updates": "System und Updates",
    "Controller, telemetry, profile, and update status at a glance.": "Controller, Telemetrie, Profil und Update-Status auf einen Blick.",
    "Every interface variant uses the same settings, haptic engine, and controller backend.": "Alle drei Oberflächen verwenden dieselben Einstellungen, dieselbe Haptik-Engine und dasselbe Controller-Backend.",
    "Active profile": "Aktives Profil", "Changes save instantly": "Änderungen werden sofort gespeichert",
    "Connected": "Verbunden", "Waiting": "Warten", "Listening": "Empfang aktiv",
    "Waiting for packets": "Warten auf Telemetrie", "USB or Bluetooth": "USB oder Bluetooth",
    "Transport: {transport}": "Verbindung: {transport}", "Forza telemetry": "Forza-Telemetrie",
    "UDP data out": "UDP Data Out", "UDP port {port}": "UDP-Port {port}",
    "Quick access": "Schnellzugriff", "R4 workspace": "R4-Arbeitsbereich", "DualSense": "DualSense",
    "Profile": "Profil", "Automatically check for updates": "Automatisch nach Updates suchen",
    "Download updates in the background": "Updates im Hintergrund herunterladen",
    "Check now": "Jetzt prüfen", "Download update": "Update herunterladen",
    "Restart and install": "Neu starten und installieren", "View release": "Release anzeigen",
    "Update status: idle": "Update-Status: bereit", "Built-in updater": "Integrierter Updater",
    "Windows EXE": "Windows-EXE", "Unavailable in this runtime": "In dieser Laufzeit nicht verfügbar",
    "Built-in updates require the Windows standalone EXE": "Integrierte Updates benötigen die eigenständige Windows-EXE",
    "Checking for updates": "Updates werden gesucht", "You are up to date": "Die Version ist aktuell",
    "Update available: {tag}": "Update verfügbar: {tag}", "Downloading update": "Update wird heruntergeladen",
    "Verifying update": "Update wird geprüft", "Update ready to install": "Update ist installationsbereit",
    "Restarting to install": "Neustart zur Installation", "Update failed": "Update fehlgeschlagen",
    "Could not start update: {error}": "Update konnte nicht gestartet werden: {error}",
    "Toggle individual trigger effects. Changes save instantly.": "Einzelne Triggereffekte umschalten. Änderungen werden sofort gespeichert.",
    "Lock the app to a specific DualSense, or let it pick the first one.": "Die App an einen bestimmten DualSense binden oder automatisch den ersten auswählen.",
})
