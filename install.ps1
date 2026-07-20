# ani-browse one-command installer for Windows (fork of JouichatH/AniBrowse).
#
# Installs everything needed for a reproducible setup: a no-admin package
# manager (Scoop), the runtime tools (git, python, node, mpv, fzf, chafa), the
# ani-browse app itself (isolated via `uv tool`), and webtorrent-cli for
# torrent streaming. Safe to re-run.
#
# Run from a clone:                    .\install.ps1
# Or one-line (clones automatically):
#   irm https://raw.githubusercontent.com/JouichatH/AniBrowse/master/install.ps1 | iex

$ErrorActionPreference = 'Stop'
$RepoUrl = 'https://github.com/JouichatH/AniBrowse'
function Say($m, $c = 'Green') { Write-Host $m -ForegroundColor $c }

Say "`n=== ani-browse installer ===`n"

# 1. Scoop (no-admin package manager) ---------------------------------------
if (-not (Get-Command scoop -ErrorAction SilentlyContinue)) {
    Say "Installing Scoop (no admin needed)..."
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
    Invoke-RestMethod -Uri 'https://get.scoop.sh' | Invoke-Expression
} else {
    Say "Scoop already installed."
}

# 2. Runtime tools ----------------------------------------------------------
Say "`nInstalling runtime tools (git, python, node, mpv, fzf, chafa, uv)..."
# git must come first and via the main bucket: fresh machines have none, and
# Scoop itself needs git to add buckets (mpv lives in the 'extras' bucket).
# The clone step below needs git too.
scoop install git
scoop bucket add extras
scoop install python nodejs mpv fzf chafa uv
# Make the freshly-installed shims (git, pipx, ...) usable in THIS session -
# scoop puts them on the user PATH, but the current process predates that.
$shims = Join-Path $env:USERPROFILE 'scoop\shims'
if ($env:Path -notlike "*$shims*") { $env:Path = "$shims;$env:Path" }

# 3. Get the repo (use local copy if run from a clone, else clone it) --------
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot 'pyproject.toml'))) {
    $repo = $PSScriptRoot
    Say "`nUsing repository at $repo"
} else {
    $repo = Join-Path $env:USERPROFILE 'ani-browse'
    if (Test-Path (Join-Path $repo '.git')) {
        Say "`nUpdating existing clone at $repo"
        git -C $repo pull --ff-only
    } else {
        Say "`nCloning $RepoUrl -> $repo"
        git clone $RepoUrl $repo
    }
}

# 4. Install the app, isolated (avoids conflicts with any base/anaconda env).
#    uv (not pipx): Scoop's pipx pyz crashes on the Python Scoop now ships
#    (3.14, missing colorama), while uv is a single static binary that brings
#    its own managed interpreter - we pin the app to a known-good 3.12.
#    Extras baked in: thefuzz (fuzzy titles) + lxml (fast HTML parsing).
Say "`nInstalling ani-browse (isolated via uv tool)..."
# A running app locks files in its venv, making uv's reinstall die halfway
# with "Access denied" and leaving a broken environment. Catch it up front:
# the app runs as the venv's python.exe, so match processes by install path.
$toolsDir = (cmd /c "uv tool dir 2>nul").Trim()
if ($toolsDir) {
    $locked = Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith($toolsDir) }
    if ($locked) {
        Say "ani-browse appears to be running (close the app, any mpv/WebTorrent windows, then re-run this installer)." 'Yellow'
        exit 1
    }
}
#    playwright: drives a local browser to authorize allanime streaming
#    (see scripts/fetch_providers.py / token_capture); optional but bundled so
#    allanime works out of the box - without it the app uses nyaa torrents.
uv tool install --force --python 3.12 --with thefuzz --with lxml --with playwright "$repo"
# Put uv's executable dir on PATH (session + user), asking uv where it is:
# scoop's uv relocates it (scoop\persist\uv\tools\shims), so don't guess.
# cmd /c so no native stderr reaches PowerShell - under Stop+redirection,
# PS 5.1 turns benign stderr notes into fatal errors (`uv tool update-shell`
# killed the whole installer with "directory is already in PATH").
$uvBin = (cmd /c "uv tool dir --bin 2>nul").Trim()
if ($uvBin) {
    if ($env:Path -notlike "*$uvBin*") { $env:Path = "$uvBin;$env:Path" }
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ($userPath -notlike "*$uvBin*") {
        [Environment]::SetEnvironmentVariable('Path', "$userPath;$uvBin", 'User')
    }
}

# 4b. Fetch the provider scrapers (not vendored in this repo; see
#     scripts/fetch_providers.py) into the isolated app environment.
Say "Fetching provider scrapers from the viu-media wheel..."
$appPy = Join-Path (cmd /c "uv tool dir 2>nul").Trim() 'viu-media\Scripts\python.exe'
if (Test-Path $appPy) {
    & $appPy (Join-Path $repo 'scripts\fetch_providers.py')
    # Chromium for the allanime token capture. Best-effort: allanime falls
    # back to nyaa if this fails, so a hiccup must not abort the install.
    Say "Installing the browser for allanime streaming (optional)..."
    try { & $appPy -m playwright install chromium } catch {
        Write-Host "  [!] Browser install skipped; allanime will use nyaa. Run later:" -ForegroundColor Yellow
        Write-Host "      $appPy -m playwright install chromium" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [!] Could not locate the app's Python; after install run:" -ForegroundColor Yellow
    Write-Host "      python $repo\scripts\fetch_providers.py" -ForegroundColor Yellow
}

# 5. webtorrent-cli (for torrent/nyaa streaming) ----------------------------
& (Join-Path $repo 'scripts\install-webtorrent.ps1')

# 6. Verify -----------------------------------------------------------------
Say "`n=== verifying ==="
foreach ($c in 'ani-browse', 'mpv', 'fzf', 'chafa', 'webtorrent') {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) { Say ("  [OK]  {0,-12} {1}" -f $c, $cmd.Source) }
    else { Write-Host ("  [!]   {0,-12} not on PATH yet (open a new terminal)" -f $c) -ForegroundColor Yellow }
}

Say "`n=== Done! ===" 'Cyan'
Say "Open a NEW terminal (Windows Terminal recommended for cover images) and run:  ani-browse" 'Cyan'
