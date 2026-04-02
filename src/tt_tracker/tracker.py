from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .model import DayRecord, DaySummary, Event, WorkState, calculate_summary
from .storage import DEFAULT_TARGET_MINUTES, TrackerStore


class TrackerError(RuntimeError):
    """Raised when a command cannot be completed."""


EDITOR_COMMAND_KEY = "editor_command"


@dataclass(slots=True)
class Tracker:
    store: TrackerStore

    def current_target(self) -> timedelta:
        config = self.store.load_config()
        return timedelta(minutes=config.get("target_minutes", DEFAULT_TARGET_MINUTES))

    def config_target(self, duration: timedelta) -> timedelta:
        minutes = int(duration.total_seconds() // 60)
        config = self.store.load_config()
        config["target_minutes"] = minutes
        self.store.save_config(config)
        return timedelta(minutes=minutes)

    def current_editor_command(self) -> str | None:
        command = self.store.load_config().get(EDITOR_COMMAND_KEY)
        if not isinstance(command, str):
            return None
        command = command.strip()
        return command or None

    def config_editor_command(self, command: str) -> str:
        normalized = command.strip()
        if not normalized:
            raise ValueError("Editor command cannot be empty.")
        config = self.store.load_config()
        config[EDITOR_COMMAND_KEY] = normalized
        self.store.save_config(config)
        return normalized

    def current_day(self, reference: datetime) -> date:
        state = self.store.load_state()
        open_day = state.get("open_day")
        if open_day:
            return date.fromisoformat(open_day)
        return reference.date()

    def open_record(self, reference: datetime) -> tuple[DayRecord | None, DaySummary | None]:
        state = self.store.load_state()
        open_day = state.get("open_day")
        if open_day:
            record = self.store.load_day(date.fromisoformat(open_day))
            changed = self.auto_resume_if_due(record, reference)
            if changed:
                self.store.save_day(record)
            summary = calculate_summary(record, reference, self.current_target())
            if summary.state in {WorkState.WORKING, WorkState.PAUSED}:
                return record, summary
            self.store.save_state({})
        for day in reversed(self.store.list_days()):
            record = self.store.load_day(day)
            changed = self.auto_resume_if_due(record, reference)
            if changed:
                self.store.save_day(record)
            summary = calculate_summary(record, reference, self.current_target())
            if summary.state in {WorkState.WORKING, WorkState.PAUSED}:
                self.store.save_state({"open_day": day.isoformat()})
                return record, summary
        return None, None

    def start(self, reference: datetime) -> DaySummary:
        open_record, summary = self.open_record(reference)
        if open_record is not None and summary is not None:
            raise TrackerError(
                f"A workday is already open for {open_record.day.isoformat()} ({summary.state.value})."
            )
        record = self.store.load_day(reference.date())
        if record.events:
            last_event_at = max(event.at for event in record.events)
            if reference <= last_event_at:
                raise TrackerError("Start time must be after the last event already recorded for the day.")
        record.events.append(Event(type="start", at=reference))
        self.store.save_day(record)
        self.store.save_state({"open_day": reference.date().isoformat()})
        return calculate_summary(record, reference, self.current_target())

    def pause(self, reference: datetime, duration: timedelta | None = None) -> DaySummary:
        record, summary = self.require_open(reference)
        if summary.state != WorkState.WORKING:
            raise TrackerError("You can only pause while a workday is running.")
        expected_resume_at = reference + duration if duration is not None else None
        record.events.append(
            Event(type="pause", at=reference, expected_resume_at=expected_resume_at)
        )
        self.store.save_day(record)
        return calculate_summary(record, reference, self.current_target())

    def resume(self, reference: datetime, duration: timedelta | None = None) -> DaySummary:
        record, summary = self.require_open(reference)
        if summary.state != WorkState.PAUSED:
            raise TrackerError("You are not currently paused.")
        pause_event = self.last_event(record, "pause")
        if pause_event is None:
            raise TrackerError("Could not find the last pause event.")
        continue_at = reference
        if duration is not None:
            continue_at = pause_event.at + duration
            if continue_at > reference:
                raise TrackerError("The continue duration points to a time in the future.")
        record.events.append(Event(type="continue", at=continue_at))
        self.store.save_day(record)
        return calculate_summary(record, reference, self.current_target())

    def stop(self, reference: datetime) -> DaySummary:
        record, summary = self.require_open(reference)
        if summary.state not in {WorkState.WORKING, WorkState.PAUSED}:
            raise TrackerError("There is no running workday to stop.")
        record.events.append(Event(type="stop", at=reference))
        self.store.save_day(record)
        self.store.save_state({})
        return calculate_summary(record, reference, self.current_target())

    def summary_for_day(self, day: date, reference: datetime) -> DaySummary:
        record = self.store.load_day(day)
        changed = self.auto_resume_if_due(record, reference)
        if changed:
            self.store.save_day(record)
        return calculate_summary(record, reference, self.current_target())

    def ensure_day_file(self, day: date) -> str:
        record = self.store.load_day(day)
        return str(self.store.save_day(record))

    def auto_resume_if_due(self, record: DayRecord, reference: datetime) -> bool:
        summary = calculate_summary(record, reference, self.current_target())
        if summary.state != WorkState.PAUSED:
            return False
        pause_event = self.last_event(record, "pause")
        if pause_event is None or pause_event.expected_resume_at is None:
            return False
        if pause_event.expected_resume_at > reference:
            return False
        has_continue_after_pause = any(
            event.type == "continue" and event.at >= pause_event.at for event in record.sorted_events()
        )
        if has_continue_after_pause:
            return False
        record.events.append(Event(type="continue", at=pause_event.expected_resume_at))
        return True

    def require_open(self, reference: datetime) -> tuple[DayRecord, DaySummary]:
        record, summary = self.open_record(reference)
        if record is None or summary is None:
            raise TrackerError("No active workday. Run `tt start` first.")
        return record, summary

    @staticmethod
    def last_event(record: DayRecord, event_type: str) -> Event | None:
        for event in reversed(record.sorted_events()):
            if event.type == event_type:
                return event
        return None
