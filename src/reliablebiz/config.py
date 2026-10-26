"""Runtime settings, read from environment variables (optionally a .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv is optional at runtime; settings fall back to defaults.
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    log_dir: Path
    max_input_chars: int

    @classmethod
    def from_env(cls) -> "Settings":
        if load_dotenv is not None:
            load_dotenv(PROJECT_ROOT / ".env", override=False)
        data_dir = Path(os.environ.get("RELIABLEBIZ_DATA_DIR", PROJECT_ROOT / "data"))
        log_dir = Path(os.environ.get("RELIABLEBIZ_LOG_DIR", PROJECT_ROOT / "logs"))
        try:
            max_chars = int(os.environ.get("RELIABLEBIZ_MAX_INPUT_CHARS", "500"))
        except ValueError:
            max_chars = 500
        return cls(data_dir=data_dir, log_dir=log_dir, max_input_chars=max(20, min(max_chars, 5000)))
