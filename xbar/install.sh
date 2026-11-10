#!/bin/sh
# Symlink the xbar plugins in this folder into xbar's plugins directory.
set -e
dir="$HOME/Library/Application Support/xbar/plugins"
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$dir"
for f in "$here"/tt*.sh; do
  chmod +x "$f"
  ln -sf "$f" "$dir/$(basename "$f")"
done
