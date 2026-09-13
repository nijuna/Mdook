"""Dynamic Theme System for Mdook Desktop GUI.

Provides 3 theme families with both Dark and Light variants (6 total themes):
1. The Library (Warm Amber / Charcoal / Aged Parchment)
2. Amethyst (Deep Zinc / Royal Violet / Clean Off-White)
3. Carbon (Monochrome Graphite / Cool Slate / Studio White)

All stylesheets are generated dynamically from token dictionaries with zero
external dependencies, sub-millisecond switching, and strictly zero emojis.
"""

from __future__ import annotations

THEME_FAMILIES = {
    "library": "The Library",
    "amethyst": "Amethyst",
    "carbon": "Carbon",
}

COLOR_MODES = {
    "dark": "Dark",
    "light": "Light",
}

THEME_TOKENS: dict[str, dict[str, dict[str, str]]] = {
    "library": {
        "dark": {
            "base_bg": "#16161a",
            "surface_card": "#212127",
            "surface_hover": "#2b2b34",
            "border": "#33333d",
            "border_active": "#f59e0b",
            "primary_accent": "#f59e0b",
            "accent_hover": "#d97706",
            "accent_text": "#16161a",
            "accent_disabled": "#3f301d",
            "text_primary": "#f4f4f5",
            "text_secondary": "#a1a1aa",
            "text_muted": "#71717a",
            "input_bg": "#1a1a20",
            "input_border": "#383844",
            "pill_bg": "#2c2c36",
            "drop_zone_bg": "#1a1a20",
            "drop_zone_border": "#3f3f4e",
            "drop_zone_active": "#26221a",
            "badge_bg": "#2e2417",
            "badge_text": "#f59e0b",
            "badge_border": "#4e3a1f",
            "progress_bg": "#24242d",
            "progress_chunk": "#f59e0b",
            "success_text": "#10b981",
            "error_text": "#f43f5e",
        },
        "light": {
            "base_bg": "#fdfbf7",
            "surface_card": "#f4efe6",
            "surface_hover": "#ebe4d8",
            "border": "#dfd6c7",
            "border_active": "#b45309",
            "primary_accent": "#b45309",
            "accent_hover": "#92400e",
            "accent_text": "#ffffff",
            "accent_disabled": "#d9beaa",
            "text_primary": "#1c1917",
            "text_secondary": "#78716c",
            "text_muted": "#a8a29e",
            "input_bg": "#ffffff",
            "input_border": "#d6ccbc",
            "pill_bg": "#e9e1d3",
            "drop_zone_bg": "#f9f5ee",
            "drop_zone_border": "#d8cdbc",
            "drop_zone_active": "#f2ebde",
            "badge_bg": "#fef3c7",
            "badge_text": "#92400e",
            "badge_border": "#fcd34d",
            "progress_bg": "#e7decfa",
            "progress_chunk": "#b45309",
            "success_text": "#059669",
            "error_text": "#e11d48",
        },
    },
    "amethyst": {
        "dark": {
            "base_bg": "#18181b",
            "surface_card": "#24242c",
            "surface_hover": "#2e2e38",
            "border": "#353542",
            "border_active": "#8b5cf6",
            "primary_accent": "#8b5cf6",
            "accent_hover": "#7c3aed",
            "accent_text": "#ffffff",
            "accent_disabled": "#362c4a",
            "text_primary": "#fafafa",
            "text_secondary": "#a1a1aa",
            "text_muted": "#71717a",
            "input_bg": "#1f1f26",
            "input_border": "#3a3a4c",
            "pill_bg": "#2d2d38",
            "drop_zone_bg": "#1d1d24",
            "drop_zone_border": "#424254",
            "drop_zone_active": "#262038",
            "badge_bg": "#2a223f",
            "badge_text": "#c4b5fd",
            "badge_border": "#4c3a72",
            "progress_bg": "#282834",
            "progress_chunk": "#8b5cf6",
            "success_text": "#10b981",
            "error_text": "#f43f5e",
        },
        "light": {
            "base_bg": "#fafafa",
            "surface_card": "#f4f4f5",
            "surface_hover": "#ebebed",
            "border": "#e4e4e7",
            "border_active": "#7c3aed",
            "primary_accent": "#7c3aed",
            "accent_hover": "#6d28d9",
            "accent_text": "#ffffff",
            "accent_disabled": "#c4b5fd",
            "text_primary": "#18181b",
            "text_secondary": "#71717a",
            "text_muted": "#a1a1aa",
            "input_bg": "#ffffff",
            "input_border": "#d4d4d8",
            "pill_bg": "#e4e4e7",
            "drop_zone_bg": "#f9f9fb",
            "drop_zone_border": "#d4d4d8",
            "drop_zone_active": "#f3e8ff",
            "badge_bg": "#ede9fe",
            "badge_text": "#6d28d9",
            "badge_border": "#ddd6fe",
            "progress_bg": "#e4e4e7",
            "progress_chunk": "#7c3aed",
            "success_text": "#059669",
            "error_text": "#e11d48",
        },
    },
    "carbon": {
        "dark": {
            "base_bg": "#09090b",
            "surface_card": "#151518",
            "surface_hover": "#1f1f24",
            "border": "#27272a",
            "border_active": "#38bdf8",
            "primary_accent": "#38bdf8",
            "accent_hover": "#0284c7",
            "accent_text": "#09090b",
            "accent_disabled": "#162f3d",
            "text_primary": "#f4f4f5",
            "text_secondary": "#94a3b8",
            "text_muted": "#64748b",
            "input_bg": "#101014",
            "input_border": "#2e2e36",
            "pill_bg": "#1e1e24",
            "drop_zone_bg": "#111115",
            "drop_zone_border": "#2e2e36",
            "drop_zone_active": "#10202c",
            "badge_bg": "#0e2b3d",
            "badge_text": "#7dd3fc",
            "badge_border": "#164e63",
            "progress_bg": "#18181e",
            "progress_chunk": "#38bdf8",
            "success_text": "#10b981",
            "error_text": "#f43f5e",
        },
        "light": {
            "base_bg": "#ffffff",
            "surface_card": "#f8fafc",
            "surface_hover": "#f1f5f9",
            "border": "#e2e8f0",
            "border_active": "#0284c7",
            "primary_accent": "#0284c7",
            "accent_hover": "#0369a1",
            "accent_text": "#ffffff",
            "accent_disabled": "#bae6fd",
            "text_primary": "#0f172a",
            "text_secondary": "#64748b",
            "text_muted": "#94a3b8",
            "input_bg": "#ffffff",
            "input_border": "#cbd5e1",
            "pill_bg": "#e2e8f0",
            "drop_zone_bg": "#f8fafc",
            "drop_zone_border": "#cbd5e1",
            "drop_zone_active": "#e0f2fe",
            "badge_bg": "#e0f2fe",
            "badge_text": "#0369a1",
            "badge_border": "#bae6fd",
            "progress_bg": "#e2e8f0",
            "progress_chunk": "#0284c7",
            "success_text": "#059669",
            "error_text": "#e11d48",
        },
    },
}


def get_tokens(theme_family: str = "library", color_mode: str = "dark") -> dict[str, str]:
    """Retrieve color tokens for a given family and mode with fallback."""
    family = theme_family.lower() if theme_family.lower() in THEME_TOKENS else "library"
    mode = color_mode.lower() if color_mode.lower() in ("dark", "light") else "dark"
    return THEME_TOKENS[family][mode]


def get_stylesheet(theme_family: str = "library", color_mode: str = "dark") -> str:
    """Generates the complete application stylesheet string."""
    t = get_tokens(theme_family, color_mode)

    return f"""
QWidget {{
    background-color: {t["base_bg"]};
    color: {t["text_primary"]};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background-color: {t["base_bg"]};
}}

QLabel, QWidget#TransparentRow, QWidget#AISettingsWidget, QWidget#HeaderWidget {{
    background-color: transparent;
}}

/* Header Bar */
#HeaderTitle {{
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.5px;
    color: {t["text_primary"]};
}}

#HeaderSubtitle {{
    color: {t["text_muted"]};
    font-size: 12px;
}}

QPushButton#SettingsButton {{
    background-color: {t["surface_card"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
    color: {t["text_secondary"]};
}}

QPushButton#SettingsButton:hover {{
    border-color: {t["border_active"]};
    color: {t["text_primary"]};
    background-color: {t["surface_hover"]};
}}

/* Cards & Surfaces */
QFrame#Card, QFrame#BookCard, QFrame#ResultCard {{
    background-color: {t["surface_card"]};
    border: 1px solid {t["border"]};
    border-radius: 8px;
}}

QFrame#Card[dragging="true"], QFrame#DropZone[dragging="true"] {{
    border: 2px dashed {t["border_active"]};
    background-color: {t["drop_zone_active"]};
}}

QLabel#TestStatusLabel[status="pending"] {{
    color: {t["text_muted"]};
}}

QLabel#TestStatusLabel[status="success"] {{
    color: {t["success_text"]};
    font-weight: 600;
}}

QLabel#TestStatusLabel[status="error"] {{
    color: {t["error_text"]};
    font-weight: 500;
}}

/* Hero Drop Zone */
QFrame#DropZone {{
    background-color: {t["drop_zone_bg"]};
    border: 2px dashed {t["drop_zone_border"]};
    border-radius: 10px;
}}

QFrame#DropZone[dragActive="true"], QFrame#DropZone:hover {{
    border-color: {t["border_active"]};
    background-color: {t["drop_zone_active"]};
}}

QLabel#DropTitle {{
    font-size: 15px;
    font-weight: 600;
    color: {t["text_primary"]};
}}

QLabel#DropSubtitle {{
    font-size: 12px;
    color: {t["text_muted"]};
}}

/* Badges & Pills */
QLabel#BadgePill {{
    background-color: {t["badge_bg"]};
    color: {t["badge_text"]};
    border: 1px solid {t["badge_border"]};
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel#InfoPill {{
    background-color: {t["pill_bg"]};
    color: {t["text_secondary"]};
    border: 1px solid {t["border"]};
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
}}

/* Labels */
QLabel#FieldLabel {{
    color: {t["text_secondary"]};
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QLabel#StatusLabel {{
    color: {t["text_muted"]};
    font-size: 12px;
}}

QLabel#SuccessStatus {{
    color: {t["success_text"]};
    font-weight: 600;
    font-size: 14px;
}}

QLabel#ErrorStatus {{
    color: {t["error_text"]};
    font-weight: 600;
    font-size: 14px;
}}

/* Form Controls */
QLineEdit {{
    background-color: {t["input_bg"]};
    border: 1px solid {t["input_border"]};
    border-radius: 6px;
    padding: 7px 10px;
    color: {t["text_primary"]};
}}

QLineEdit:focus {{
    border-color: {t["border_active"]};
}}

QLineEdit:read-only {{
    color: {t["text_muted"]};
    background-color: {t["surface_card"]};
}}

QComboBox {{
    background-color: {t["input_bg"]};
    border: 1px solid {t["input_border"]};
    border-radius: 6px;
    padding: 6px 10px;
    color: {t["text_primary"]};
}}

QComboBox:focus {{
    border-color: {t["border_active"]};
}}

QComboBox QAbstractItemView {{
    background-color: {t["surface_card"]};
    border: 1px solid {t["border"]};
    color: {t["text_primary"]};
    selection-background-color: {t["primary_accent"]};
    selection-color: {t["accent_text"]};
}}

/* Radio Buttons for Segmented Output Selector */
QRadioButton {{
    background-color: transparent;
    color: {t["text_primary"]};
    spacing: 8px;
    font-weight: 500;
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {t["border"]};
    border-radius: 8px;
    background-color: {t["input_bg"]};
}}

QRadioButton::indicator:hover {{
    border-color: {t["border_active"]};
}}

QRadioButton::indicator:checked {{
    border: 5px solid {t["primary_accent"]};
    background-color: {t["base_bg"]};
}}

/* Checkboxes */
QCheckBox {{
    background-color: transparent;
    spacing: 8px;
    color: {t["text_primary"]};
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {t["input_border"]};
    border-radius: 4px;
    background-color: {t["input_bg"]};
}}

QCheckBox::indicator:hover {{
    border-color: {t["border_active"]};
}}

QCheckBox::indicator:checked {{
    background-color: {t["primary_accent"]};
    border-color: {t["primary_accent"]};
}}

/* Buttons */
QPushButton {{
    background-color: {t["surface_card"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 500;
    color: {t["text_primary"]};
}}

QPushButton:hover {{
    background-color: {t["surface_hover"]};
    border-color: {t["border_active"]};
}}

QPushButton:pressed {{
    background-color: {t["input_bg"]};
}}

QPushButton:disabled {{
    color: {t["text_muted"]};
    background-color: {t["surface_card"]};
    border-color: {t["border"]};
}}

QPushButton#PrimaryButton {{
    background-color: {t["primary_accent"]};
    border: 1px solid {t["primary_accent"]};
    color: {t["accent_text"]};
    font-weight: 600;
    font-size: 14px;
    padding: 9px 20px;
    border-radius: 6px;
}}

QPushButton#PrimaryButton:hover {{
    background-color: {t["accent_hover"]};
    border-color: {t["accent_hover"]};
}}

QPushButton#PrimaryButton:disabled {{
    background-color: {t["accent_disabled"]};
    border-color: {t["accent_disabled"]};
    color: {t["text_muted"]};
}}

/* Progress Bar */
QProgressBar {{
    background-color: {t["progress_bg"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    text-align: center;
    color: {t["text_primary"]};
    font-size: 12px;
    font-weight: 600;
    height: 18px;
}}

QProgressBar::chunk {{
    background-color: {t["progress_chunk"]};
    border-radius: 5px;
}}

/* Stepper Breadcrumbs */
QLabel#StepBreadcrumb {{
    color: {t["text_muted"]};
    font-size: 12px;
    font-weight: 500;
}}

QLabel#StepBreadcrumb[active="true"] {{
    color: {t["primary_accent"]};
    font-weight: 700;
}}

QLabel#StepBreadcrumb[done="true"] {{
    color: {t["text_primary"]};
}}

/* ScrollBars */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {t["border"]};
    border-radius: 4px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {t["text_muted"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
