#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="--editable"
INSTALL_PROMPT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --editable)
      MODE="--editable"
      ;;
    --no-editable)
      MODE="--no-editable"
      ;;
    --prompt)
      INSTALL_PROMPT=1
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ./install.sh [--editable|--no-editable] [--prompt]

Installs `tt` into your user Python environment without creating a virtualenv.
Defaults to an editable install so local code changes are picked up immediately.

Options:
  --editable      Install in editable mode (default)
  --no-editable   Install a regular user install
  --prompt        Also run `tt install-prompt zsh`
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
  shift
done

if ! python3 -m pip --version >/dev/null 2>&1; then
  python3 -m ensurepip --upgrade --user >/dev/null 2>&1 || true
fi

if ! python3 -m pip --version >/dev/null 2>&1; then
  echo "python3 -m pip is not available on this machine." >&2
  exit 1
fi

PIP_ARGS=(install --user --no-build-isolation)
PIP_INSTALL_HELP="$(python3 -m pip install --help 2>/dev/null || true)"
if [[ "$PIP_INSTALL_HELP" == *"--break-system-packages"* ]]; then
  PIP_ARGS+=(--break-system-packages)
fi
if [[ "$MODE" == "--editable" ]]; then
  PIP_ARGS+=(-e)
fi
PIP_ARGS+=("$SCRIPT_DIR")

PIP_OUTPUT=""
if ! PIP_OUTPUT="$(python3 -m pip "${PIP_ARGS[@]}" 2>&1)"; then
  if [[ "$PIP_OUTPUT" != *"Successfully installed"* ]] || [[ "$PIP_OUTPUT" != *"pyenv: cannot rehash"* ]]; then
    printf '%s\n' "$PIP_OUTPUT" >&2
    exit 1
  fi
fi
printf '%s\n' "$PIP_OUTPUT"

USER_BASE="$(python3 -c 'import site; print(site.getuserbase())')"
BIN_DIR="$USER_BASE/bin"

echo
echo "Installed tt."
echo "Binary location: $BIN_DIR"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo "Add this to your ~/.zshrc if needed:"
  echo "export PATH=\"$BIN_DIR:\$PATH\""
fi

if [[ $INSTALL_PROMPT -eq 1 ]]; then
  "$BIN_DIR/tt" install-prompt zsh
fi
