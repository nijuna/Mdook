"""Qt stylesheets (QSS) for the dark (default) and light themes.

Bridges to the dynamic theme system in `mdook.gui.theme`.
"""

from __future__ import annotations

from mdook.gui.theme import get_stylesheet

DARK_STYLE = get_stylesheet("library", "dark")
LIGHT_STYLE = get_stylesheet("library", "light")
