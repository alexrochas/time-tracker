# Extensions: macOS menu bar (topbar)

`tt` has no built-in menu bar app, but `tt prompt` already prints the exact
compact status you want up there (e.g. `[3h17m left]` or `[+0h22m]`), so you
can drive an existing menu bar host with a tiny standalone shell script — no
changes to this repo required.

Recommended host: [xbar](https://xbarapp.com) or [SwiftBar](https://swiftbar.app).

```bash
brew install --cask xbar   # or: brew install --cask swiftbar
```

## Plugin scripts

The plugins live in [`xbar/`](../xbar):

- `tt.5s.sh`: `tt prompt` (remaining/overtime today), refreshes every 5s.
- `tt-week.1m.sh`: only the remaining hours of `tt week` (e.g. `34h32m left`), refreshes every minute.

## Install it

```bash
./xbar/install.sh
```

This symlinks the scripts into `~/Library/Application Support/xbar/plugins`, so
editing them in the repo is what xbar runs.

The number in the filename (`tt.5s.sh`) is the refresh interval xbar/SwiftBar
polls at. Rename the file (e.g. `tt.30s.sh`) to change it.

## Why the `PATH` export matters

xbar/SwiftBar run plugins with a minimal PATH
(`/usr/bin:/bin:/usr/sbin:/sbin`) that does **not** include wherever `tt` got
installed (commonly `~/Library/Python/<version>/bin` or `~/.local/bin`). If
`tt` isn't found, the script has no way to tell "idle" from "tt not on PATH"
without the explicit `command -v tt` check above — which is why it's there.
If you still see `tt: not found on PATH`, find your actual binary and adjust
the `PATH` line:

```bash
which tt
```
