#!/bin/sh
# Camarón — one-time global install (macOS / Linux).
# Clones the kit into a fixed central location and puts `camaron` plus the legacy `camarones` alias on your PATH,
# so every cama-docs-* project shares one kit copy instead of a per-project copy going stale.
# Works from a checkout or piped from the web:
#   curl -fsSL https://raw.githubusercontent.com/iandelu/camarones-documenter/main/install-global.sh | sh
# CAMARONES_KIT_URL overrides where the kit comes from (a fork, or a local checkout while developing the kit).
set -e
KIT_URL="${CAMARONES_KIT_URL:-https://github.com/iandelu/camarones-documenter.git}"
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
    echo "🦐 Camarón needs uv (Python tool manager by Astral)."
    printf "   Install it now with Astral's official installer? [y/N] "
    { read -r ans < /dev/tty; } 2>/dev/null || ans=""   # piped from curl: stdin is this script, ask the terminal
    case "$ans" in
      y|Y) curl -LsSf https://astral.sh/uv/install.sh | sh ;;
      *) echo "   Install uv and run install-global.sh again."; exit 1 ;;
    esac
  fi
fi

mkdir -p "$(dirname "$CENTRAL")"
if [ -d "$CENTRAL/.git" ]; then
  echo "Updating existing central kit at $CENTRAL…"
  ORIGIN="$(git -C "$CENTRAL" remote get-url origin 2>/dev/null || true)"
  case "$ORIGIN" in
    *://*|*@*:*) if [ -n "$CAMARONES_KIT_URL" ]; then git -C "$CENTRAL" remote set-url origin "$KIT_URL"; fi ;;
    *) git -C "$CENTRAL" remote set-url origin "$KIT_URL" ;;   # older installs followed a local checkout
  esac
  if ! git -C "$CENTRAL" pull --ff-only --quiet 2>/dev/null; then
    # Upstream history was rewritten (rebased, amended): move onto it like `camaron self-update` does, as long as
    # nothing is uncommitted and every local commit already exists upstream by content.
    git -C "$CENTRAL" fetch --quiet || { echo "Could not reach the kit upstream from $CENTRAL." >&2; exit 1; }
    if [ -n "$(git -C "$CENTRAL" status --porcelain --untracked-files=no)" ]; then
      echo "The kit clone $CENTRAL has uncommitted changes — commit or discard them, then retry." >&2; exit 1
    fi
    if git -C "$CENTRAL" cherry '@{u}' HEAD | grep -q '^+'; then
      echo "The kit clone $CENTRAL has local commits that are not upstream — push or drop them, then retry." >&2; exit 1
    fi
    git -C "$CENTRAL" reset --hard --quiet '@{u}'
  fi
else
  echo "Cloning kit to $CENTRAL…"
  git clone --quiet "$KIT_URL" "$CENTRAL"
fi

mkdir -p "$BINDIR"
cat > "$BINDIR/camaron" <<EOF
#!/bin/sh
export PYTHONUTF8=1
export CAMARONES_GLOBAL=1
exec uv run --quiet --script "$CENTRAL/.camarones/camarones.py" "\$@"
EOF
chmod +x "$BINDIR/camaron"
cat > "$BINDIR/camarones" <<EOF
#!/bin/sh
exec "$BINDIR/camaron" "\$@"
EOF
chmod +x "$BINDIR/camarones"
echo "Global launcher written to $BINDIR/camaron; compatibility alias: camarones."

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
echo "🦐 Camarón installed globally."
echo "Open a new terminal and run: camaron new my-project"
echo "Update every project at once later with: camaron self-update"
