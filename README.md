<p align="center">
  <img src="assets/tt-logo.svg" alt="tt logo" width="640">
</p>

# `tt`

Local CLI time tracking for work hours, breaks, CSV export, manual editing, and a zsh prompt segment.

`tt` is meant for a simple personal workflow:
- start the workday
- pause for lunch or any other break
- continue after the pause
- stop at the end of the day
- fix mistakes later when you forgot to start, pause, continue, or stop on time

## Install

```bash
./install.sh
```

That installs `tt` into your user Python environment without creating a virtualenv.

By default, `./install.sh` performs an editable install, which is nice for local development because code changes are picked up after reinstalling without any extra setup.

Useful install variants:

```bash
./install.sh --prompt
./install.sh --no-editable
```

If `tt` is not found after install, the script prints the exact `PATH` line you should add to `~/.zshrc`.

## Features

- `tt` with no arguments shows your current status
- `tt start` starts the day now
- `tt start HH:mm` starts the day retroactively for today
- `tt pause` starts a break now
- `tt pause 45m` or `tt pause 1h` starts a timed break
- `tt continue` resumes now
- `tt continue 1h` says the break should only have lasted one hour
- `tt stop` ends the current workday
- `tt config set target 8h` sets your daily target
- `tt config set editor vim` sets a custom edit command
- `tt prompt` prints a compact prompt segment like `[3h17m left]`
- `tt install-prompt zsh` installs a managed left-side prompt hook
- `tt export` writes CSV summaries
- `tt edit` opens the underlying day file in your editor

## Quick start

Set your daily target once:

```bash
tt config set target 8h
tt config set editor vim
```

Then use it through the day:

```bash
tt start
tt pause 45m
tt continue
tt stop
tt status
```

If you forgot to start in the morning:

```bash
tt start 08:30
```

## Demo

Example day:

```bash
$ tt
Day: 2026-03-16 | State: idle | Worked: 0h00m | Paused: 0h00m | Target: 8h00m | Remaining: 8h00m

$ tt start 08:30
Started 2026-03-16 at 08:30.
Day: 2026-03-16 | State: working | Started: 08:30 | Worked: 1h45m | Paused: 0h00m | Target: 8h00m | Remaining: 6h15m

$ tt pause 45m
Paused at 12:00.
Auto-resume scheduled for 12:45.
Day: 2026-03-16 | State: paused | Started: 08:30 | Worked: 3h30m | Paused: 0h00m | Target: 8h00m | Remaining: 4h30m

$ tt continue
Continuing work on 2026-03-16.
Day: 2026-03-16 | State: working | Started: 08:30 | Worked: 3h30m | Paused: 0h45m | Target: 8h00m | Remaining: 4h30m

$ tt stop
Stopped at 17:15.
Day: 2026-03-16 | State: stopped | Started: 08:30 | Stopped: 17:15 | Worked: 8h00m | Paused: 0h45m | Target: 8h00m | Remaining: 0h00m
```

Prompt example:

```bash
[3h17m left] ➜  time-tracker
```

## Command reference

### Day flow

```bash
tt
tt start
tt start 08:30
tt pause
tt pause 45m
tt continue
tt continue 1h
tt stop
tt status
tt status 16.03
```

### Configuration

```bash
tt config show
tt config set target 8h
tt config set target 7h30m
tt config set editor vim
tt config set editor 'nvim +10 $'
```

### Export

Export a single day:

```bash
tt export 16.03 -o hours.csv
```

Export a range:

```bash
tt export 01.03 16.03 -o march.csv
tt export 01/03 16/03 -o march.csv
```

### Manual correction

Open the current day file:

```bash
tt edit
```

Open a specific day:

```bash
tt edit 16.03
```

This is useful when you forgot something more complicated and want to fix the event history directly.

By default, `tt edit` first respects `VISUAL` or `EDITOR`, then falls back to the current platform default behavior. You can override that with a configured command:

```bash
tt config set editor vim
tt config set editor 'nvim +10 $'
tt config set editor 'code --wait {file}'
```

If the configured command contains `$` or `{file}`, `tt` replaces that token with the day file path. If there is no placeholder, `tt` appends the file path automatically. When using `$`, quote it so your shell does not try to expand it first.

## Prompt integration

```bash
tt install-prompt zsh
```

This adds one managed block to your `~/.zshrc`.

The prompt segment:
- appears on the left
- is placed before your existing prompt
- shows remaining time in green/yellow
- shows overtime in red
- stays compact, for example `[3h17m left]` or `[+0h22m]`

Re-running `tt install-prompt zsh` updates the same managed block in place, so editable reinstalls do not require manual cleanup.

Remove it with:

```bash
tt uninstall-prompt zsh
```

## Data storage

`tt` stores data in `~/.tt` by default.

Inside that folder:
- `config.json` stores settings like your daily target
- `state.json` stores the currently open day
- `days/YYYY-MM-DD.json` stores the event history for each day

You can override the storage location with `TT_HOME`, which is handy for testing:

```bash
TT_HOME=/tmp/tt-demo tt start
```

## Development

For local development, just rerun:

```bash
./install.sh
```

Because the install is editable by default, the workflow stays simple. There is no need to manually clean your `~/.zshrc`, and the managed prompt block can be reapplied safely at any time.
