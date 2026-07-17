"""R4 teal GUI design tokens.

This is a color-language reference only. No character art, branded font, or
third-party visual asset is bundled. Never hardcode page colors elsewhere.
"""

# Background tiers ---------------------------------------------------------
BG_DEEP   = ("#e8fbf9", "#101a1d")
BG_MAIN   = ("#f7fffe", "#142327")
BG_PANEL  = ("#edf9f8", "#193037")
BG_INPUT  = ("#ffffff", "#0d181b")
BG_HOVER  = ("#d9f4f1", "#214047")
BG_ACTIVE = ("#c1eee9", "#28525a")

# Borders
BORDER = ("#bfe6e2", "#285159")

# Text
TEXT       = ("#102b2d", "#eafdfc")
TEXT_MUTED = ("#3f6668", "#a9cfcd")
TEXT_FAINT = ("#67898a", "#739b9b")

# Accent
ACCENT       = "#39c5bb"
ACCENT_HOVER = "#2da99f"
ACCENT_SOFT  = ("#20a99f", "#86e8e1")

# Semantic
GREEN  = ("#168a67", "#45d39e")
YELLOW = ("#a36900", "#ffcc66")
RED    = ("#b62b4a", "#ff6685")
PINK   = "#ff6aa9"
BLUE   = ("#228fc5", "#63c7f2")

# Spacing tokens
PAD_XS = 4
PAD_SM = 8
PAD_MD = 16
PAD_LG = 24

# Sizes
SIDEBAR_W = 204
HEADER_H  = 44

# Font sizes
FS_H1 = 18
FS_H2 = 13
FS_BODY = 12
FS_SMALL = 11
FS_TINY = 10

# Icon glyphs
ICON = {
    "Overview": "\u25c8",
    "Driving": "\U0001f3ce",
    "Haptics": "\u224b",
    "Lighting": "\u2726",
    "Controls": "\U0001F3AE",  # gamepad
    "Profiles": "\U0001F4CB",  # clipboard
    "Settings": "\u2699",        # gear
    "System":   "\U0001F5A5",  # computer
    "Language": "\U0001F310",  # globe
    "Logs":     "\U0001F4DC",  # scroll
    "About":    "\u24D8",      # information
    "pause":    "\u23F8",
    "play":     "\u25B6",
    "clear":    "\U0001F5D1",
    "reload":   "\u21BB",
    "heart":    "\u2665",
    "dot":      "\u25CF",
    "x":        "\u2715",
    "warn":     "\u26A0",
}
