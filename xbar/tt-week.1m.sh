#!/bin/sh
export PATH="$HOME/Library/Python/3.13/bin:$HOME/Library/Python/3.14/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
rem=$(tt week 2>/dev/null | sed -E 's/\x1B\[[0-9;]*m//g' | sed -nE 's/.*Remaining: *([^ |]+).*/\1/p')
echo "${rem:-tt week: ?} left"
