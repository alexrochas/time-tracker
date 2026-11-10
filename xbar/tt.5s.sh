#!/bin/sh
# xbar/SwiftBar plugin — shows `tt`'s remaining/overtime prompt in the macOS menu bar.
# Install: run xbar/install.sh (symlinks into the xbar plugins folder).
# The "5s" in the filename sets the refresh interval; rename to change it (e.g. tt.30s.sh).

export PATH="$HOME/Library/Python/3.13/bin:$HOME/Library/Python/3.14/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

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
