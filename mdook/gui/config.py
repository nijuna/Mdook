"""GUI configuration persistence for Mdook.

Stores appearance themes, conversion defaults, and AI review credentials in
`~/.config/mdook/gui_config.json`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class GUIConfig:
    theme_family: str = "library"  # "library" | "amethyst" | "carbon"
    color_mode: str = "dark"  # "dark" | "light"
    output_mode: str = "vault"  # "vault" | "single_document"
    profile: str = "auto"  # "auto" | "literature" | "technical"
    output_dir: str = ""
    ai_enabled: bool = False
    ai_model: str = ""
    ai_base_url: str = ""
    ai_api_key: str = ""

    @classmethod
    def get_config_dir(cls) -> Path:
        base = Path.home() / ".config" / "mdook"
        base.mkdir(parents=True, exist_ok=True)
        return base

    @classmethod
    def get_config_path(cls) -> Path:
        return cls.get_config_dir() / "gui_config.json"

    @classmethod
    def load(cls) -> GUIConfig:
        path = cls.get_config_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            valid_keys = {f for f in cls.__dataclass_fields__}
            filtered = {k: v for k, v in data.items() if k in valid_keys}
            return cls(**filtered)
        except Exception:
            return cls()

    def save(self) -> None:
        path = self.get_config_path()
        try:
            path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except Exception:
            pass
