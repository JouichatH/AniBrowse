#!/usr/bin/env bash
# ani-browse installer for Linux / macOS (fork of viu-media/viu).
# Installs runtime tools via your package manager, the ani-browse app (isolated
# via pipx), and webtorrent-cli for torrent streaming. Safe to re-run.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
C_OK=$'\033[1;32m'; C_WARN=$'\033[1;33m'; C_DIM=$'\033[2m'; C_RST=$'\033[0m'
ok()   { printf '%s✓ %s%s\n' "$C_OK" "$*" "$C_RST"; }
warn() { printf '%s! %s%s\n' "$C_WARN" "$*" "$C_RST"; }
info() { printf '%s%s%s\n' "$C_DIM" "$*" "$C_RST"; }

printf '\n%s=== ani-browse installer ===%s\n\n' "$C_OK" "$C_RST"

# 1. Runtime tools ----------------------------------------------------------
install_tools() {
    if command -v brew >/dev/null 2>&1; then
        brew install mpv fzf chafa node python pipx
    elif command -v apt >/dev/null 2>&1; then
        sudo apt update
        sudo apt install -y mpv fzf chafa nodejs npm python3 python3-pip pipx
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --needed mpv fzf chafa nodejs npm python python-pipx
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y mpv fzf chafa nodejs python3 python3-pip pipx
    else
        warn "No supported package manager found. Install manually: mpv fzf chafa node python3 pipx"
        return 1
    fi
}
info "Installing runtime tools (mpv, fzf, chafa, node, python, pipx)..."
install_tools || true

# 2. Install the app, isolated ---------------------------------------------
info "Installing ani-browse (isolated via pipx)..."
pipx ensurepath >/dev/null 2>&1 || true
pipx install --force "$REPO_DIR"
pipx inject viu-media thefuzz lxml >/dev/null 2>&1 || warn "optional extras skipped"

# Fetch the provider scrapers (not vendored here; see scripts/fetch_providers.py)
info "Fetching provider scrapers from the viu-media wheel..."
APP_PY="$(pipx environment --value PIPX_LOCAL_VENVS 2>/dev/null)/viu-media/bin/python"
if [ -x "$APP_PY" ]; then
    "$APP_PY" "$REPO_DIR/scripts/fetch_providers.py" || warn "provider fetch failed — run scripts/fetch_providers.py manually"
else
    warn "couldn't locate app python; after install run: python $REPO_DIR/scripts/fetch_providers.py"
fi

# 3. webtorrent-cli (same workaround as Windows: a dep's preinstall forces
#    pnpm and native binaries need a rebuild after --ignore-scripts) ---------
if command -v webtorrent >/dev/null 2>&1; then
    ok "webtorrent already installed"
elif command -v npm >/dev/null 2>&1; then
    info "Installing webtorrent-cli (with workaround)..."
    npm install -g webtorrent-cli --ignore-scripts
    ( cd "$(npm root -g)/webtorrent-cli" && npm rebuild node-datachannel )
    ok "webtorrent-cli installed"
else
    warn "npm not found — install Node.js, then: npm i -g webtorrent-cli"
fi

# 4. Verify -----------------------------------------------------------------
echo
for c in ani-browse mpv fzf chafa webtorrent; do
    if command -v "$c" >/dev/null 2>&1; then ok "$c -> $(command -v "$c")"
    else warn "$c not on PATH yet (open a new shell)"; fi
done
printf '\n%sDone! Run:%s  ani-browse\n' "$C_OK" "$C_RST"
