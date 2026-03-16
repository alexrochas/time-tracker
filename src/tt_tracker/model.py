from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum


class WorkState(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass(slots=True)
class Event:
    type: str
    at: datetime
    expected_resume_at: datetime | None = None

    def to_dict(self) -> dict[str, str]:
        payload = {
            "type": self.type,
            "at": self.at.isoformat(),
        }
        if self.expected_resume_at is not None:
            payload["expected_resume_at"] = self.expected_resume_at.isoformat()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> "Event":
        return cls(
            type=payload["type"],
            at=datetime.fromisoformat(payload["at"]),
            expected_resume_at=(
                datetime.fromisoformat(payload["expected_resume_at"])
                if payload.get("expected_resume_at")
                else None
            ),
        )


@dataclass(slots=True)
class DayRecord:
    day: date
    events: list[Event] = field(default_factory=list)

    def sorted_events(self) -> list[Event]:
        return sorted(self.events, key=lambda event: event.at)

    def to_dict(self) -> dict[str, object]:
        return {
            "date": self.day.isoformat(),
            "events": [event.to_dict() for event in self.sorted_events()],
        }

    @classmethod
    def empty(cls, day: date) -> "DayRecord":
        return cls(day=day, events=[])

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "DayRecord":
        return cls(
            day=date.fromisoformat(str(payload["date"])),
            events=[Event.from_dict(item) for item in payload.get("events", [])],
        )


@dataclass(slots=True)
class DaySummary:
    day: date
    state: WorkState
    started_at: datetime | None
    stopped_at: datetime | None
    worked: timedelta
    paused: timedelta
    target: timedelta
    balance: timedelta
    last_pause_at: datetime | None = None


def calculate_summary(
    record: DayRecord,
    reference: datetime,
    target: timedelta,
) -> DaySummary:
    state = WorkState.IDLE
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    last_pause_at: datetime | None = None
    work_started_at: datetime | None = None
    pause_started_at: datetime | None = None
    worked = timedelta()
    paused = timedelta()

    for event in record.sorted_events():
        if event.type == "start":
            if state in {WorkState.IDLE, WorkState.STOPPED}:
                state = WorkState.WORKING
                started_at = started_at or event.at
                work_started_at = event.at
        elif event.type == "pause":
            if state == WorkState.WORKING and work_started_at is not None:
                worked += safe_delta(work_started_at, event.at)
                work_started_at = None
                state = WorkState.PAUSED
                pause_started_at = event.at
                last_pause_at = event.at
        elif event.type == "continue":
            if state == WorkState.PAUSED and pause_started_at is not None:
                paused += safe_delta(pause_started_at, event.at)
                pause_started_at = None
                state = WorkState.WORKING
                work_started_at = event.at
        elif event.type == "stop":
            if state == WorkState.WORKING and work_started_at is not None:
                worked += safe_delta(work_started_at, event.at)
            elif state == WorkState.PAUSED and pause_started_at is not None:
                paused += safe_delta(pause_started_at, event.at)
            if state in {WorkState.WORKING, WorkState.PAUSED}:
                state = WorkState.STOPPED
                stopped_at = event.at
                work_started_at = None
                pause_started_at = None

    if state == WorkState.WORKING and work_started_at is not None:
        worked += safe_delta(work_started_at, reference)
    elif state == WorkState.PAUSED and pause_started_at is not None:
        paused += safe_delta(pause_started_at, reference)

    return DaySummary(
        day=record.day,
        state=state,
        started_at=started_at,
        stopped_at=stopped_at,
        worked=worked,
        paused=paused,
        target=target,
        balance=target - worked,
        last_pause_at=last_pause_at,
    )


def safe_delta(start: datetime, end: datetime) -> timedelta:
    if end < start:
        return timedelta()
    return end - start
