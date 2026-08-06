from __future__ import annotations

import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tt_tracker.cli import (
    build_editor_command,
    build_zsh_prompt_block,
    format_prompt,
    main,
    open_editor,
    parse_clock_time,
    parse_day,
    parse_duration,
    parse_time_argument,
    replace_managed_block,
)
from tt_tracker.model import DaySummary, WorkState
from tt_tracker.storage import TrackerStore
from tt_tracker.tracker import Tracker, TrackerError


class TrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.store = TrackerStore(root=Path(self.temp_dir.name))
        self.tracker = Tracker(self.store)
        self.tz = datetime.now().astimezone().tzinfo

    def dt(self, day: int, hour: int, minute: int = 0) -> datetime:
        return datetime(2026, 3, day, hour, minute, tzinfo=self.tz)

    def test_pause_continue_stop_flow(self) -> None:
        self.tracker.start(self.dt(16, 9, 0))
        self.tracker.pause(self.dt(16, 12, 0))
        self.tracker.resume(self.dt(16, 14, 0), timedelta(hours=1))
        summary = self.tracker.stop(self.dt(16, 18, 0))

        self.assertEqual(summary.worked, timedelta(hours=8))
        self.assertEqual(summary.paused, timedelta(hours=1))
        self.assertEqual(summary.balance, timedelta())

    def test_auto_resume_happens_from_scheduled_pause(self) -> None:
        self.tracker.start(self.dt(16, 9, 0))
        self.tracker.pause(self.dt(16, 12, 0), timedelta(minutes=30))

        summary = self.tracker.summary_for_day(self.dt(16, 9, 0).date(), self.dt(16, 13, 0))

        self.assertEqual(summary.worked, timedelta(hours=3, minutes=30))
        payload = json.loads((self.store.days_dir / "2026-03-16.json").read_text())
        self.assertEqual(payload["events"][-1]["type"], "continue")
        self.assertEqual(
            datetime.fromisoformat(payload["events"][-1]["at"]),
            self.dt(16, 12, 30),
        )

    def test_parse_duration_supports_hours_minutes_and_plain_minutes(self) -> None:
        self.assertEqual(parse_duration("1h30m"), timedelta(hours=1, minutes=30))
        self.assertEqual(parse_duration("45m"), timedelta(minutes=45))
        self.assertEqual(parse_duration("15"), timedelta(minutes=15))

    def test_parse_day_accepts_common_formats(self) -> None:
        default_day = self.dt(16, 9, 0).date()
        self.assertEqual(parse_day("2026-03-15", default_day).isoformat(), "2026-03-15")
        self.assertEqual(parse_day("15.03.2026", default_day).isoformat(), "2026-03-15")
        self.assertEqual(parse_day("15/03", default_day).isoformat(), "2026-03-15")

    def test_parse_clock_time_uses_today(self) -> None:
        reference = self.dt(16, 10, 0)
        self.assertEqual(parse_clock_time("08:30", reference), self.dt(16, 8, 30))

    def test_parse_time_argument_handles_relative_offsets(self) -> None:
        reference = self.dt(16, 10, 0)
        self.assertEqual(parse_time_argument("+30", reference), self.dt(16, 10, 30))
        self.assertEqual(parse_time_argument("-30", reference), self.dt(16, 9, 30))
        self.assertEqual(parse_time_argument("+90", reference), self.dt(16, 11, 30))

    def test_parse_time_argument_handles_absolute_time_formats(self) -> None:
        reference = self.dt(16, 10, 0)
        self.assertEqual(parse_time_argument("08:30", reference), self.dt(16, 8, 30))
        self.assertEqual(parse_time_argument("15h30", reference), self.dt(16, 15, 30))
        self.assertEqual(parse_time_argument("15H30", reference), self.dt(16, 15, 30))

    def test_backdated_start_counts_work_since_that_time(self) -> None:
        summary = self.tracker.start(self.dt(16, 8, 30))
        now_summary = self.tracker.summary_for_day(summary.day, self.dt(16, 10, 0))

        self.assertEqual(now_summary.worked, timedelta(hours=1, minutes=30))

    def test_backdated_start_rejects_earlier_than_existing_events(self) -> None:
        self.tracker.start(self.dt(16, 9, 0))
        self.tracker.stop(self.dt(16, 10, 0))

        with self.assertRaises(TrackerError):
            self.tracker.start(self.dt(16, 8, 30))

    def test_editor_config_is_preserved_when_target_changes(self) -> None:
        self.tracker.config_editor_command("vim $")

        target = self.tracker.config_target(timedelta(hours=7, minutes=30))

        self.assertEqual(target, timedelta(hours=7, minutes=30))
        self.assertEqual(self.tracker.current_editor_command(), "vim $")
        self.assertEqual(self.store.load_config()["target_minutes"], 450)

    def test_build_editor_command_replaces_placeholder(self) -> None:
        command = build_editor_command('vim -c "set number" $', Path("/tmp/day file.json"))

        self.assertEqual(command, ["vim", "-c", "set number", "/tmp/day file.json"])

    def test_build_editor_command_appends_path_without_placeholder(self) -> None:
        command = build_editor_command("vim -u NONE", Path("/tmp/day file.json"))

        self.assertEqual(command, ["vim", "-u", "NONE", "/tmp/day file.json"])

    def test_open_editor_prefers_configured_command(self) -> None:
        with patch("tt_tracker.cli.subprocess.run") as run_mock:
            open_editor(Path("/tmp/day.json"), "vim $")

        run_mock.assert_called_once_with(["vim", "/tmp/day.json"], check=True)

    def test_main_without_command_prints_status(self) -> None:
        os_env = __import__("os").environ
        previous = os_env.get("TT_HOME")
        os_env["TT_HOME"] = self.temp_dir.name
        try:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main([])
        finally:
            if previous is None:
                os_env.pop("TT_HOME", None)
            else:
                os_env["TT_HOME"] = previous

        self.assertEqual(exit_code, 0)
        self.assertIn("State: idle", output.getvalue())

    def test_main_config_set_editor(self) -> None:
        os_env = __import__("os").environ
        previous = os_env.get("TT_HOME")
        os_env["TT_HOME"] = self.temp_dir.name
        try:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["config", "set", "editor", "vim", "$"])
        finally:
            if previous is None:
                os_env.pop("TT_HOME", None)
            else:
                os_env["TT_HOME"] = previous

        self.assertEqual(exit_code, 0)
        self.assertEqual(self.tracker.current_editor_command(), "vim $")
        self.assertIn("Updated editor to vim $.", output.getvalue())

    def test_main_export_defaults_to_timeline(self) -> None:
        self.tracker.start(self.dt(16, 8, 30))
        self.tracker.pause(self.dt(16, 12, 0))
        self.tracker.resume(self.dt(16, 12, 45))
        self.tracker.stop(self.dt(16, 17, 15))

        os_env = __import__("os").environ
        previous = os_env.get("TT_HOME")
        os_env["TT_HOME"] = self.temp_dir.name
        try:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["export", "16.03"])
        finally:
            if previous is None:
                os_env.pop("TT_HOME", None)
            else:
                os_env["TT_HOME"] = previous

        rendered = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("2026-03-16 | stopped", rendered)
        self.assertIn("work   3h30m", rendered)
        self.assertIn("break  0h45m", rendered)
        self.assertIn("work   4h30m", rendered)
        self.assertIn("total: worked 8h00m | paused 0h45m", rendered)

    def test_main_export_csv_requires_flag(self) -> None:
        self.tracker.start(self.dt(16, 8, 30))
        self.tracker.stop(self.dt(16, 16, 30))

        os_env = __import__("os").environ
        previous = os_env.get("TT_HOME")
        os_env["TT_HOME"] = self.temp_dir.name
        try:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["export", "16.03", "--csv"])
        finally:
            if previous is None:
                os_env.pop("TT_HOME", None)
            else:
                os_env["TT_HOME"] = previous

        rendered = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("date,worked_minutes,worked_hhmm", rendered)
        self.assertIn("2026-03-16,480,8h00m", rendered)

    def test_prompt_text_does_not_include_tt_label(self) -> None:
        summary = DaySummary(
            day=self.dt(16, 9, 0).date(),
            state=WorkState.WORKING,
            started_at=self.dt(16, 9, 0),
            stopped_at=None,
            worked=timedelta(hours=4, minutes=43),
            paused=timedelta(minutes=15),
            target=timedelta(hours=8),
            balance=timedelta(hours=3, minutes=17),
        )

        self.assertEqual(format_prompt(summary, color=False), "[3h17m left]")

    def test_prompt_block_replaces_existing_copy(self) -> None:
        original = "export PATH=/tmp/bin:$PATH\n"
        once = replace_managed_block(original, build_zsh_prompt_block())
        twice = replace_managed_block(once, build_zsh_prompt_block())

        self.assertEqual(once, twice)
        self.assertIn("TT_ORIGINAL_PROMPT", once)
        self.assertIn('PROMPT=\'$(_tt_prompt_command) \'"${TT_ORIGINAL_PROMPT}"', once)


if __name__ == "__main__":
    unittest.main()
