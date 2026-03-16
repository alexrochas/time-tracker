from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .model import DayRecord


DEFAULT_TARGET_MINUTES = 8 * 60


@dataclass(slots=True)
class TrackerStore:
    root: Path

    @classmethod
    def from_env(cls) -> "TrackerStore":
        import os

        configured = os.environ.get("TT_HOME")
        if configured:
            return cls(root=Path(configured).expanduser())
        return cls(root=Path.home() / ".tt")

    @property
    def days_dir(self) -> Path:
        return self.root / "days"

    @property
    def config_path(self) -> Path:
        return self.root / "config.json"

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    def ensure(self) -> None:
        self.days_dir.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self.save_config({"target_minutes": DEFAULT_TARGET_MINUTES})

    def day_path(self, day: date) -> Path:
        return self.days_dir / f"{day.isoformat()}.json"

    def load_day(self, day: date) -> DayRecord:
        path = self.day_path(day)
        if not path.exists():
            return DayRecord.empty(day)
        return DayRecord.from_dict(json.loads(path.read_text()))

    def save_day(self, record: DayRecord) -> Path:
        self.ensure()
        path = self.day_path(record.day)
        path.write_text(json.dumps(record.to_dict(), indent=2) + "\n")
        return path

    def load_config(self) -> dict[str, int]:
        self.ensure()
        return json.loads(self.config_path.read_text())

    def save_config(self, payload: dict[str, int]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(payload, indent=2) + "\n")

    def load_state(self) -> dict[str, str]:
        self.ensure()
        if not self.state_path.exists():
            return {}
        return json.loads(self.state_path.read_text())

    def save_state(self, payload: dict[str, str]) -> None:
        self.ensure()
        self.state_path.write_text(json.dumps(payload, indent=2) + "\n")

    def list_days(self) -> list[date]:
        if not self.days_dir.exists():
            return []
        return sorted(
            date.fromisoformat(path.stem)
            for path in self.days_dir.glob("*.json")
            if _looks_like_date(path.stem)
        )


def _looks_like_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True
