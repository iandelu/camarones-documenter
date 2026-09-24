#!/bin/sh
# Camarones Documenter — one-time global install (macOS / Linux).
# Clones this repo into a fixed central location and puts a `camarones` launcher on your PATH,
# so every cama-docs-* project shares one kit copy instead of a per-project copy going stale.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
CENTRAL="$HOME/.camarones/kit"
BINDIR="$HOME/.local/bin"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required — install it first." >&2; exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "🦐 Installing uv with Homebrew (one-time)…"
    brew install uv
  else
    echo "🦐 Camarones Documenter needs uv (Python tool manager by Astral)."
    printf "   Install it now with Astral's official installer? [y/N] "
    read -r ans
    case "$ans" in
      y|Y) curl -LsSf https://astral.sh/uv/install.sh | sh ;;
      *) echo "   Install uv and run install-global.sh again."; exit 1 ;;
    esac
  fi
fi

mkdir -p "$(dirname "$CENTRAL")"
if [ -d "$CENTRAL/.git" ]; then
  echo "Updating existing central kit at $CENTRAL…"
  git -C "$CENTRAL" pull --ff-only
else
  echo "Cloning kit to $CENTRAL…"
  git clone --quiet "$SRC" "$CENTRAL"
fi

mkdir -p "$BINDIR"
cat > "$BINDIR/camarones" <<EOF
#!/bin/sh
export PYTHONUTF8=1
export CAMARONES_GLOBAL=1
exec uv run --quiet --script "$CENTRAL/.camarones/camarones.py" "\$@"
EOF
chmod +x "$BINDIR/camarones"
echo "Global launcher written to $BINDIR/camarones."

case ":$PATH:" in
  *":$BINDIR:"*) : ;;
  *)
    RC="$HOME/.bashrc"
    case "$SHELL" in
      */zsh) RC="$HOME/.zshrc" ;;
    esac
    if ! grep -qs "$BINDIR" "$RC" 2>/dev/null; then
      echo "export PATH=\"$BINDIR:\$PATH\"" >> "$RC"
      echo "Added $BINDIR to PATH in $RC — open a new terminal, or run: export PATH=\"$BINDIR:\$PATH\""
    fi
    ;;
esac

echo
echo "🦐 Camarones Documenter installed globally."
echo "Open a new terminal and run: camarones new my-project"
echo "Update every project at once later with: camarones self-update"
