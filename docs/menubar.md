# Extensions: macOS menu bar (topbar)

`tt` has no built-in menu bar app, but `tt prompt` already prints the exact
compact status you want up there (e.g. `[3h17m left]` or `[+0h22m]`), so you
can drive an existing menu bar host with a tiny standalone shell script — no
changes to this repo required.

Recommended host: [xbar](https://xbarapp.com) or [SwiftBar](https://swiftbar.app).

```bash
brew install --cask xbar   # or: brew install --cask swiftbar
```

## Plugin script

Save this anywhere outside this repo, e.g. `~/bin/tt.5s.sh`:

```sh
#!/bin/sh
# xbar/SwiftBar plugin — shows `tt`'s remaining/overtime prompt in the macOS menu bar.
# Install: copy this file to your xbar/SwiftBar plugins folder, e.g.
#   cp tt.5s.sh ~/Library/Application\ Support/xbar/plugins/tt.5s.sh
#   chmod +x ~/Library/Application\ Support/xbar/plugins/tt.5s.sh
# The "5s" in the filename sets the refresh interval; rename to change it (e.g. tt.30s.sh).

export PATH="$HOME/Library/Python/3.14/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

if ! command -v tt >/dev/null 2>&1; then
  echo "tt: not found on PATH | color=red"
  exit 0
fi

raw=$(tt prompt 2>/dev/null)

# strip ANSI escape codes, keep the plain text
text=$(printf '%s' "$raw" | sed -E 's/\x1B\[[0-9;]*m//g')

if [ -z "$text" ]; then
  echo "tt: idle"
  exit 0
fi

# color green unless it's overtime (starts with '+')
case "$text" in
  \[+*) color=red ;;
  *) color=green ;;
esac

echo "$text | color=$color"
```

## Install it

```bash
mkdir -p ~/Library/Application\ Support/xbar/plugins
cp ~/bin/tt.5s.sh ~/Library/Application\ Support/xbar/plugins/tt.5s.sh
chmod +x ~/Library/Application\ Support/xbar/plugins/tt.5s.sh
```

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
