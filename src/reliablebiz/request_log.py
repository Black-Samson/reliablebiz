"""Append-only JSON Lines request log (one line per handled request)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class RequestLogger:
    def __init__(self, log_dir: Path, filename: str = "requests.jsonl") -> None:
        self.path = Path(log_dir) / filename
        self._lock = threading.Lock()

    def write(self, record: dict[str, Any]) -> bool:
        """Write one record. Logging problems must never break the app."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(record, ensure_ascii=False, default=str)
            with self._lock, self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            return True
        except OSError:
            return False
