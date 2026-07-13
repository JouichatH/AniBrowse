# ani-browse one-command installer for Windows (fork of viu-media/viu).
#
# Installs everything needed for a reproducible setup: a no-admin package
# manager (Scoop), the runtime tools (python, node, mpv, fzf, chafa), the
# ani-browse app itself (isolated via pipx), and webtorrent-cli for torrent
# streaming. Safe to re-run.
#
# Run from a clone:                    .\install.ps1
# Or one-line (clones automatically):
#   irm https://raw.githubusercontent.com/JouichatH/ani-browse/master/install.ps1 | iex

$ErrorActionPreference = 'Stop'
$RepoUrl = 'https://github.com/JouichatH/ani-browse'
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
Say "`nInstalling runtime tools (python, node, mpv, fzf, chafa, pipx)..."
scoop bucket add extras *> $null
scoop install python nodejs mpv fzf chafa pipx

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

# 4. Install the app, isolated (avoids conflicts with any base/anaconda env) --
Say "`nInstalling ani-browse (isolated via pipx)..."
pipx ensurepath *> $null
pipx install --force "$repo"
# Nice-to-have extras: fuzzy title matching + fast HTML parsing.
Say "Adding optional extras (thefuzz, lxml)..."
try { pipx inject viu-media thefuzz lxml *> $null } catch { Write-Host "  (extras skipped: $_)" -ForegroundColor Yellow }

# 4b. Fetch the provider scrapers (not vendored in this repo; see
#     scripts/fetch_providers.py) into the isolated app environment.
Say "Fetching provider scrapers from the viu-media wheel..."
$appPy = Join-Path (pipx environment --value PIPX_LOCAL_VENVS) 'viu-media\Scripts\python.exe'
if (Test-Path $appPy) {
    & $appPy (Join-Path $repo 'scripts\fetch_providers.py')
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
