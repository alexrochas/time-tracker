from __future__ import annotations

import argparse
import csv
import os
import platform
import shlex
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from .model import DayRecord, WorkState, calculate_summary
from .storage import TrackerStore
from .tracker import Tracker, TrackerError

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"

PROMPT_START = "# >>> tt prompt >>>"
PROMPT_END = "# <<< tt prompt <<<"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tt", description="Track work hours from the command line.")
    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser("start", help="Start the workday.")
    start_parser.add_argument(
        "start_time",
        nargs="?",
        help="Optional start time for today in HH:mm format, for example 08:30.",
    )

    pause_parser = subparsers.add_parser("pause", help="Pause the current workday.")
    pause_parser.add_argument("duration", nargs="?", help="Optional pause length, for example 45m or 1h.")

    continue_parser = subparsers.add_parser("continue", help="Resume after a pause.")
    continue_parser.add_argument(
        "duration",
        nargs="?",
        help="Optional actual pause duration, for example 1h if you forgot to continue on time.",
    )

    subparsers.add_parser("stop", help="Stop the current workday.")

    status_parser = subparsers.add_parser("status", help="Show the current status or a single day summary.")
    status_parser.add_argument("day", nargs="?", help="Optional day, such as 2026-03-16 or 16.03.")

    export_parser = subparsers.add_parser(
        "export",
        help="Show one or more days as a timeline, or export them as CSV.",
    )
    export_parser.add_argument("from_day", nargs="?", help="Start day, such as 01.03 or 2026-03-01.")
    export_parser.add_argument("to_day", nargs="?", help="End day. Defaults to the same value as from_day.")
    format_group = export_parser.add_mutually_exclusive_group()
    format_group.add_argument(
        "--csv",
        action="store_const",
        dest="format",
        const="csv",
        help="Write CSV instead of the default timeline view.",
    )
    format_group.add_argument(
        "--timeline",
        action="store_const",
        dest="format",
        const="timeline",
        help="Write the day-by-day timeline view.",
    )
    export_parser.set_defaults(format="timeline")
    export_parser.add_argument("-o", "--output", help="Write the selected format to a file instead of stdout.")

    edit_parser = subparsers.add_parser("edit", help="Open a day file in your editor.")
    edit_parser.add_argument("day", nargs="?", help="Optional day. Defaults to the open day or today.")

    config_parser = subparsers.add_parser("config", help="Show or change configuration.")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    config_subparsers.add_parser("show", help="Show the current configuration.")
    config_set_parser = config_subparsers.add_parser("set", help="Set a configuration value.")
    config_set_parser.add_argument("key", choices=["target", "editor"], help="Configuration key.")
    config_set_parser.add_argument("value", nargs="+", help="Value for the key, such as 8h or vim.")

    prompt_parser = subparsers.add_parser("prompt", help="Print a prompt segment.")
    prompt_parser.add_argument("--plain", action="store_true", help="Disable ANSI colors.")

    install_parser = subparsers.add_parser("install-prompt", help="Install the managed shell prompt hook.")
    install_parser.add_argument("shell", choices=["zsh"], help="Shell type.")
    install_parser.add_argument(
        "--rc-file",
        default=str(Path.home() / ".zshrc"),
        help="Shell rc file to update. Defaults to ~/.zshrc.",
    )

    uninstall_parser = subparsers.add_parser("uninstall-prompt", help="Remove the managed shell prompt hook.")
    uninstall_parser.add_argument("shell", choices=["zsh"], help="Shell type.")
    uninstall_parser.add_argument(
        "--rc-file",
        default=str(Path.home() / ".zshrc"),
        help="Shell rc file to update. Defaults to ~/.zshrc.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw_argv = argv if argv is not None else sys.argv[1:]
    args = parser.parse_args(raw_argv)
    tracker = Tracker(TrackerStore.from_env())
    now = datetime.now().astimezone()

    try:
        if args.command is None:
            day = tracker.current_day(now)
            summary = tracker.summary_for_day(day, now)
            print(format_status(summary))
            return 0

        if args.command == "start":
            start_at = parse_clock_time(args.start_time, now) if args.start_time else now
            tracker.start(start_at)
            summary = tracker.summary_for_day(start_at.date(), now)
            print(f"Started {start_at.date().isoformat()} at {format_clock(start_at)}.")
            print(format_status(summary))
            return 0

        if args.command == "pause":
            duration = parse_duration(args.duration) if args.duration else None
            summary = tracker.pause(now, duration)
            print(f"Paused at {format_clock(now)}.")
            if duration:
                print(f"Auto-resume scheduled for {format_clock(now + duration)}.")
            print(format_status(summary))
            return 0

        if args.command == "continue":
            duration = parse_duration(args.duration) if args.duration else None
            summary = tracker.resume(now, duration)
            print(f"Continuing work on {summary.day.isoformat()}.")
            print(format_status(summary))
            return 0

        if args.command == "stop":
            summary = tracker.stop(now)
            print(f"Stopped at {format_clock(now)}.")
            print(format_status(summary))
            return 0

        if args.command == "status":
            day = parse_day(args.day, now.date()) if args.day else tracker.current_day(now)
            summary = tracker.summary_for_day(day, now)
            print(format_status(summary))
            return 0

        if args.command == "export":
            from_day = parse_day(args.from_day, now.date()) if args.from_day else now.date()
            to_day = parse_day(args.to_day, from_day) if args.to_day else from_day
            export_report(tracker, from_day, to_day, now, args.output, args.format)
            return 0

        if args.command == "edit":
            day = parse_day(args.day, now.date()) if args.day else tracker.current_day(now)
            path = tracker.ensure_day_file(day)
            open_editor(Path(path), tracker.current_editor_command())
            print(f"Opened {path}.")
            return 0

        if args.command == "config":
            if args.config_command == "show":
                target = tracker.current_target()
                print(f"target={format_duration(target)}")
                print(f"editor={tracker.current_editor_command() or ''}")
                print(f"store={tracker.store.root}")
                return 0
            if args.config_command == "set":
                value = " ".join(args.value)
                if args.key == "target":
                    target = tracker.config_target(parse_duration(value))
                    print(f"Updated target to {format_duration(target)}.")
                    return 0
                if args.key == "editor":
                    command = tracker.config_editor_command(value)
                    print(f"Updated editor to {command}.")
                return 0

        if args.command == "prompt":
            record, summary = tracker.open_record(now)
            if summary is None:
                summary = tracker.summary_for_day(now.date(), now)
            print(format_prompt(summary, color=not args.plain), end="")
            return 0

        if args.command == "install-prompt":
            install_prompt(Path(args.rc_file), args.shell)
            print(f"Installed managed prompt block in {args.rc_file}.")
            return 0

        if args.command == "uninstall-prompt":
            uninstall_prompt(Path(args.rc_file))
            print(f"Removed managed prompt block from {args.rc_file}.")
            return 0
    except TrackerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    parser.error("Unknown command")
    return 2


def format_status(summary) -> str:
    parts = [f"Day: {summary.day.isoformat()}", f"State: {summary.state.value}"]
    if summary.started_at is not None:
        parts.append(f"Started: {format_clock(summary.started_at)}")
    if summary.stopped_at is not None:
        parts.append(f"Stopped: {format_clock(summary.stopped_at)}")
    parts.append(f"Worked: {format_duration(summary.worked)}")
    parts.append(f"Paused: {format_duration(summary.paused)}")
    parts.append(f"Target: {format_duration(summary.target)}")
    if summary.balance >= timedelta():
        parts.append(f"Remaining: {format_duration(summary.balance)}")
    else:
        parts.append(f"Overtime: {format_duration(abs(summary.balance))}")
    return " | ".join(parts)


def format_prompt(summary, color: bool) -> str:
    if summary.state == WorkState.IDLE and summary.worked == timedelta():
        return ""
    if summary.state == WorkState.PAUSED:
        text = f"[paused {format_duration(summary.paused)} | worked {format_duration(summary.worked)}]"
        return paint(text, YELLOW, color)
    if summary.balance > timedelta():
        tone = GREEN if summary.balance > timedelta(hours=1) else YELLOW
        text = f"[{format_duration(summary.balance)} left]"
        return paint(text, tone, color)
    text = f"[+{format_duration(abs(summary.balance))}]"
    return paint(text, RED, color)


def export_report(
    tracker: Tracker,
    from_day: date,
    to_day: date,
    reference: datetime,
    output_path: str | None,
    output_format: str,
) -> None:
    if to_day < from_day:
        raise ValueError("The export end day must be on or after the start day.")
    if output_format == "csv":
        export_csv(tracker, from_day, to_day, reference, output_path)
        return
    export_timeline(tracker, from_day, to_day, reference, output_path)


def export_csv(
    tracker: Tracker,
    from_day: date,
    to_day: date,
    reference: datetime,
    output_path: str | None,
) -> None:
    target = tracker.current_target()
    rows = []
    current = from_day
    while current <= to_day:
        summary = tracker.summary_for_day(current, reference)
        rows.append(
            {
                "date": current.isoformat(),
                "worked_minutes": rounded_minutes(summary.worked),
                "worked_hhmm": format_duration(summary.worked),
                "paused_minutes": rounded_minutes(summary.paused),
                "paused_hhmm": format_duration(summary.paused),
                "target_minutes": rounded_minutes(target),
                "target_hhmm": format_duration(target),
                "balance_minutes": rounded_minutes(summary.balance),
                "state": summary.state.value,
                "started_at": summary.started_at.isoformat() if summary.started_at else "",
                "stopped_at": summary.stopped_at.isoformat() if summary.stopped_at else "",
            }
        )
        current += timedelta(days=1)

    fieldnames = list(rows[0].keys()) if rows else [
        "date",
        "worked_minutes",
        "worked_hhmm",
        "paused_minutes",
        "paused_hhmm",
        "target_minutes",
        "target_hhmm",
        "balance_minutes",
        "state",
        "started_at",
        "stopped_at",
    ]
    handle = open(output_path, "w", newline="") if output_path else sys.stdout
    should_close = output_path is not None
    try:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if should_close:
            handle.close()


def export_timeline(
    tracker: Tracker,
    from_day: date,
    to_day: date,
    reference: datetime,
    output_path: str | None,
) -> None:
    target = tracker.current_target()
    handle = open(output_path, "w") if output_path else sys.stdout
    should_close = output_path is not None
    current = from_day
    try:
        first_day = True
        while current <= to_day:
            if not first_day:
                print(file=handle)
            first_day = False
            record = tracker.store.load_day(current)
            changed = tracker.auto_resume_if_due(record, reference)
            if changed:
                tracker.store.save_day(record)
            summary = calculate_summary(record, reference, target)
            print(f"{current.isoformat()} | {summary.state.value}", file=handle)
            segments = build_timeline_segments(record, reference)
            if segments:
                for label, start_at, end_at, duration in segments:
                    print(
                        f"  {format_clock(start_at)} -> {format_clock(end_at)}  {label:<5}  {format_duration(duration)}",
                        file=handle,
                    )
            else:
                print("  no entries", file=handle)
            print(
                "  total: "
                f"worked {format_duration(summary.worked)} | "
                f"paused {format_duration(summary.paused)} | "
                f"target {format_duration(summary.target)} | "
                f"{format_balance(summary.balance)}",
                file=handle,
            )
            current += timedelta(days=1)
    finally:
        if should_close:
            handle.close()


def build_timeline_segments(
    record: DayRecord,
    reference: datetime,
) -> list[tuple[str, datetime, datetime, timedelta]]:
    segments: list[tuple[str, datetime, datetime, timedelta]] = []
    state = WorkState.IDLE
    work_started_at: datetime | None = None
    pause_started_at: datetime | None = None

    for event in record.sorted_events():
        if event.type == "start":
            if state in {WorkState.IDLE, WorkState.STOPPED}:
                state = WorkState.WORKING
                work_started_at = event.at
        elif event.type == "pause":
            if state == WorkState.WORKING and work_started_at is not None:
                segments.append(("work", work_started_at, event.at, safe_timeline_delta(work_started_at, event.at)))
                work_started_at = None
                pause_started_at = event.at
                state = WorkState.PAUSED
        elif event.type == "continue":
            if state == WorkState.PAUSED and pause_started_at is not None:
                segments.append(
                    ("break", pause_started_at, event.at, safe_timeline_delta(pause_started_at, event.at))
                )
                pause_started_at = None
                work_started_at = event.at
                state = WorkState.WORKING
        elif event.type == "stop":
            if state == WorkState.WORKING and work_started_at is not None:
                segments.append(("work", work_started_at, event.at, safe_timeline_delta(work_started_at, event.at)))
            elif state == WorkState.PAUSED and pause_started_at is not None:
                segments.append(
                    ("break", pause_started_at, event.at, safe_timeline_delta(pause_started_at, event.at))
                )
            state = WorkState.STOPPED
            work_started_at = None
            pause_started_at = None

    if state == WorkState.WORKING and work_started_at is not None:
        segments.append(("work", work_started_at, reference, safe_timeline_delta(work_started_at, reference)))
    elif state == WorkState.PAUSED and pause_started_at is not None:
        segments.append(("break", pause_started_at, reference, safe_timeline_delta(pause_started_at, reference)))

    return segments


def safe_timeline_delta(start: datetime, end: datetime) -> timedelta:
    if end < start:
        return timedelta()
    return end - start


def format_balance(balance: timedelta) -> str:
    if balance >= timedelta():
        return f"remaining {format_duration(balance)}"
    return f"overtime {format_duration(abs(balance))}"


def parse_day(value: str, default_day: date) -> date:
    if value is None:
        return default_day
    value = value.strip()
    if not value:
        return default_day
    if value.lower() == "today":
        return default_day
    if value.lower() == "yesterday":
        return default_day - timedelta(days=1)
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass

    separator = "." if "." in value else "/" if "/" in value else None
    if separator is None:
        raise ValueError(f"Unsupported date format: {value}")
    parts = value.split(separator)
    if len(parts) == 2:
        day, month = map(int, parts)
        return date(default_day.year, month, day)
    if len(parts) == 3:
        day, month, year = map(int, parts)
        if year < 100:
            year += 2000
        return date(year, month, day)
    raise ValueError(f"Unsupported date format: {value}")


def parse_duration(value: str) -> timedelta:
    value = value.strip().lower()
    if not value:
        raise ValueError("Duration cannot be empty.")

    total_minutes = 0
    digits = ""
    saw_unit = False
    for char in value:
        if char.isdigit():
            digits += char
            continue
        if char.isspace():
            continue
        if char not in {"h", "m"}:
            raise ValueError(f"Unsupported duration format: {value}")
        if not digits:
            raise ValueError(f"Missing number before '{char}' in duration.")
        amount = int(digits)
        digits = ""
        saw_unit = True
        if char == "h":
            total_minutes += amount * 60
        else:
            total_minutes += amount

    if digits:
        total_minutes += int(digits)
    elif not saw_unit:
        raise ValueError(f"Unsupported duration format: {value}")

    if total_minutes <= 0:
        raise ValueError("Duration must be greater than zero.")
    return timedelta(minutes=total_minutes)


def parse_clock_time(value: str, reference: datetime) -> datetime:
    try:
        parsed = datetime.strptime(value.strip(), "%H:%M").time()
    except ValueError as exc:
        raise ValueError("Time must use HH:mm, for example 08:30.") from exc

    candidate = datetime.combine(reference.date(), parsed, tzinfo=reference.tzinfo)
    if candidate > reference:
        raise ValueError("Start time cannot be in the future.")
    return candidate


def format_duration(duration: timedelta) -> str:
    total_minutes = rounded_minutes(duration)
    sign = "-" if total_minutes < 0 else ""
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    return f"{sign}{hours}h{minutes:02d}m"


def format_clock(value: datetime) -> str:
    return value.astimezone().strftime("%H:%M")


def paint(text: str, tone: str, color: bool) -> str:
    if not color:
        return text
    return f"{tone}{text}{RESET}"


def rounded_minutes(duration: timedelta) -> int:
    return int(round(duration.total_seconds() / 60))


def open_editor(path: Path, configured_command: str | None = None) -> None:
    if configured_command:
        subprocess.run(build_editor_command(configured_command, path), check=True)
        return
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        subprocess.run([*shlex.split(editor), str(path)], check=True)
        return
    if platform.system() == "Darwin":
        subprocess.run(["open", "-t", str(path)], check=True)
        return
    subprocess.run(["vi", str(path)], check=True)


def build_editor_command(command: str, path: Path) -> list[str]:
    parts = shlex.split(command)
    replacements = {"$", "{file}"}
    substituted = [str(path) if part in replacements else part for part in parts]
    if not any(part in replacements for part in parts):
        substituted.append(str(path))
    return substituted


def install_prompt(rc_path: Path, shell: str) -> None:
    if shell != "zsh":
        raise ValueError("Only zsh is supported right now.")
    block = build_zsh_prompt_block()
    existing = rc_path.read_text() if rc_path.exists() else ""
    updated = replace_managed_block(existing, block)
    rc_path.write_text(updated)


def uninstall_prompt(rc_path: Path) -> None:
    existing = rc_path.read_text() if rc_path.exists() else ""
    updated = replace_managed_block(existing, None)
    rc_path.write_text(updated)


def replace_managed_block(content: str, block: str | None) -> str:
    start = content.find(PROMPT_START)
    end = content.find(PROMPT_END)
    if start != -1 and end != -1 and end >= start:
        end += len(PROMPT_END)
        while end < len(content) and content[end] == "\n":
            end += 1
        content = content[:start].rstrip("\n") + ("\n" if start > 0 else "") + content[end:]
    if block is None:
        return content.rstrip() + ("\n" if content else "")
    content = content.rstrip()
    if content:
        content += "\n\n"
    return content + block + "\n"


def build_zsh_prompt_block() -> str:
    return "\n".join(
        [
            PROMPT_START,
            "if command -v tt >/dev/null 2>&1; then",
            "  setopt PROMPT_SUBST",
            '  typeset -g TT_ORIGINAL_PROMPT="${TT_ORIGINAL_PROMPT:-$PROMPT}"',
            "  _tt_prompt_command() {",
            "    tt prompt",
            "  }",
            '  PROMPT=\'$(_tt_prompt_command) \'"${TT_ORIGINAL_PROMPT}"',
            "fi",
            PROMPT_END,
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
