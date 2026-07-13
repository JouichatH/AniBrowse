# Install webtorrent-cli on Windows, working around two issues that break the
# normal `npm install -g webtorrent-cli`:
#   1. A transitive dep (ip-set) runs `npx only-allow pnpm` in a preinstall
#      script, which fails under npm. We install with --ignore-scripts.
#   2. --ignore-scripts then skips node-datachannel's step that downloads its
#      prebuilt native binary, so we rebuild that one package afterwards.
# Finally we make sure npm's global bin dir is on PATH, because ani-browse
# finds the player via shutil.which("webtorrent").

$ErrorActionPreference = 'Stop'
function Say($m, $c = 'Green') { Write-Host $m -ForegroundColor $c }

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm not found. Install Node.js first (scoop install nodejs)."
}

if (Get-Command webtorrent -ErrorAction SilentlyContinue) {
    Say "webtorrent already installed: $((Get-Command webtorrent).Source)"
} else {
    Say "Installing webtorrent-cli (with Windows workaround)..."
    npm install -g webtorrent-cli --ignore-scripts
    $wtDir = Join-Path (npm root -g) 'webtorrent-cli'
    Say "Rebuilding node-datachannel to fetch its native binary..."
    Push-Location $wtDir
    try { npm rebuild node-datachannel } finally { Pop-Location }
}

# Ensure npm's global bin dir is on the user's PATH (so `webtorrent` is found).
$npmPrefix = (npm config get prefix).Trim()
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath -notlike "*$npmPrefix*") {
    Say "Adding npm global bin to your PATH: $npmPrefix"
    [Environment]::SetEnvironmentVariable('Path', "$userPath;$npmPrefix", 'User')
    $env:Path = "$env:Path;$npmPrefix"  # also for the current session
} else {
    Say "npm global bin already on PATH."
}

# Verify (use the session PATH we just extended)
$env:Path = "$env:Path;$npmPrefix"
$ver = (& "$npmPrefix\webtorrent" --version 2>&1 | Select-Object -First 1)
if ($LASTEXITCODE -eq 0) { Say "[OK] webtorrent $ver" }
else { Write-Host "[!] webtorrent installed but did not run cleanly. Open a new terminal and try 'webtorrent --version'." -ForegroundColor Yellow }
