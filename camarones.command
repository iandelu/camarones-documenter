#!/bin/sh
# 🦐 Camarones Documenter launcher (macOS / Linux). Runs only local files; opens the wizard, or a command: ./camarones.command help
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# macOS: files extracted from a downloaded zip carry the "quarantine" flag that makes Gatekeeper block them.
# Clear it on the kit files only, so the next double-click on camarones.command just works.
if [ "$(uname)" = "Darwin" ] && command -v xattr >/dev/null 2>&1; then
  xattr -dr com.apple.quarantine .camarones camarones.command camarones.cmd 2>/dev/null
fi

if ! command -v uv >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "🦐 Installing uv with Homebrew (one-time)…"
    brew install uv || exit 1
  elif [ -t 0 ]; then
    echo "🦐 Camarones Documenter needs uv (Python tool manager by Astral, brings its own Python)."
    echo "   Recommended: install Homebrew (https://brew.sh) and run: brew install uv"
    printf "   Or install it now with Astral's official installer? [y/N] "
    read -r ans
    case "$ans" in
      y|Y|s|S) curl -LsSf https://astral.sh/uv/install.sh | sh || exit 1 ;;
      *) echo "   Install uv and open Camarones Documenter again."; exit 1 ;;
    esac
    export PATH="$HOME/.local/bin:$PATH"
  else
    echo "uv not found: https://docs.astral.sh/uv/getting-started/installation/" >&2; exit 1
  fi
fi
exec uv run --quiet --script ".camarones/camarones.py" "$@"
