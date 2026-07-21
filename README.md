<h1 align="center">ani-browse</h1>
<p align="center"><sup>Watch anime from your terminal — search, stream, and download, with automatic fallback to fast torrent releases.</sup></p>

## What is ani-browse?

ani-browse is a **free app for watching anime on your computer**. Instead of opening a web browser and clicking through ad-filled sites, you search and play everything from one clean screen you control with your keyboard.

It connects to your (free) **[AniList](https://anilist.co)** account to keep track of what you watch, automatically finds the best available source for each episode, and — when a brand-new episode isn't up yet on the usual sites — quietly falls back to **fast torrent releases** so you can watch it the day it airs.

Once it's installed, you don't need any technical knowledge: **arrow keys** to move, **Enter** to choose.

## What it can do

- 🔎 **Find any anime** — search the huge AniList catalog by name, genre, year, and more.
- ▶️ **Stream instantly** — pick an episode and it starts in seconds, automatically choosing the best and fastest source.
- 🧲 **Never wait for new episodes** — automatic torrent fallback grabs freshly-aired episodes before the usual sites upload them.
- ⏭️ **Skip openings & endings** — optional automatic skipping of intros and outros.
- 📥 **Download for offline** — queue episodes and let it download them in the background.
- 📋 **Track your list** — mark episodes watched, resume where you left off, and stay in sync with AniList.
- 🎨 **Cover-image previews** — see the artwork right inside the terminal.

> **You'll need:** a free [AniList account](https://anilist.co/signup) to browse and track anime. The installer sets up everything else for you.

## Install — step by step

### Windows

1. Click **Start**, type **PowerShell**, and open it.
2. Update **Windows Terminal** first — cover images need version 1.22 or newer, and a stock install is often older. Paste this and press **Enter** (safe to run even if it's already up to date):

   ```powershell
   winget upgrade Microsoft.WindowsTerminal
   ```

3. Copy the line below. **Right-click** inside the PowerShell window to paste it, then press **Enter**:

   ```powershell
   irm https://raw.githubusercontent.com/JouichatH/AniBrowse/master/install.ps1 | iex
   ```

4. Wait a few minutes while it installs everything — you'll see progress messages. (It's safe to run again if anything gets interrupted.)
5. When it finishes, **close PowerShell and open a new one — use Windows Terminal** (Start → type "Terminal") so you get the cover images.
6. Type **`ani-browse`** and press **Enter**. You're in! 🎉

> **Tip:** Cover images only show inside **Windows Terminal** (not the classic PowerShell window). It's preinstalled on Windows 11; on Windows 10 get it free from the Microsoft Store. If something looks off later, run **`ani-browse doctor`** — it checks your terminal, tools, and install and tells you how to fix what's wrong.
>
> **Updating from an older install?** Just re-run the installer command above — it also refreshes your settings so cover images and fullscreen playback work without any manual editing. (Or run `ani-browse config --refresh` yourself; your customizations are kept.)

### macOS / Linux

First make sure **git** is installed (on macOS, running `git` the first time offers to install it; on Linux use your package manager, e.g. `sudo apt install git`).

1. Open the **Terminal** app.
2. Copy and paste these lines one at a time, pressing **Enter** after each:

   ```bash
   git clone https://github.com/JouichatH/AniBrowse.git
   cd AniBrowse
   ./install.sh
   ```

3. Wait for it to finish — it sets up the app plus the media player (`mpv`), the menu tool (`fzf`), and the torrent helper.
4. Open a **new terminal**, type **`ani-browse`**, and press **Enter**. 🎉

> **If it says `command not found`:** run `export PATH="$HOME/.local/bin:$PATH"` and try again (that's where the installer puts the app; new terminals normally pick it up automatically).

> **A note on torrents:** when a new episode is only available via torrent, ani-browse streams it over BitTorrent, which briefly uploads (seeds) while you watch. Using a **VPN** is advisable. This only happens for the torrent fallback.

## First time using it

1. **Log in to AniList** (one time only). Type:

   ```bash
   ani-browse anilist auth
   ```

   This opens your web browser — approve the app, copy the code it shows you, and paste it back into the terminal.

2. **Start browsing:**

   ```bash
   ani-browse anilist
   ```

3. **Get around** with your keyboard:
   - **↑ / ↓** to move, **Enter** to choose, **Esc** to go back.
   - **Just start typing** to search.
   - Pick an anime → pick an episode → it plays.

**While an episode is playing** (a few handy keys):

- **Shift + N** / **Shift + P** — next / previous episode.
- **Ctrl + S** — switch to a different source if the current one is slow or low quality.
- Openings and endings can be skipped automatically once you turn that on in the settings.

That's everything you need to start. Settings, downloads, and power-user commands are in the documentation below.

---

<details>
<summary>Full documentation</summary>

<p align="center">
  <h1 align="center">Ani-Browse</h1>
</p>
<p align="center">
  <sup>
  Your browser anime experience, from the terminal.
  </sup>
</p>
<div align="center">

[![Tests](https://img.shields.io/github/actions/workflow/status/JouichatH/AniBrowse/test.yml?label=Tests)](https://github.com/JouichatH/AniBrowse/actions)
[![Issues](https://img.shields.io/github/issues/JouichatH/AniBrowse)](https://github.com/JouichatH/AniBrowse/issues)
[![License](https://img.shields.io/github/license/JouichatH/AniBrowse)](https://github.com/JouichatH/AniBrowse/blob/master/LICENSE)

</div>

[ani-browse-showcase.webm](https://github.com/user-attachments/assets/5da0ec87-7780-4310-9ca2-33fae7cadd5f)

<details>
<summary>Rofi</summary>
  
  [ani-browse-showcase-rofi.webm](https://github.com/user-attachments/assets/01f197d9-5ac9-45e6-a00b-8e8cd5ab459c)

</details>

<details>
  <summary>RICED</summary>
  
  *main menu*
  
  <img width="1895" height="1007" alt="image" src="https://github.com/user-attachments/assets/e6d8883f-0267-4783-9688-983dea524e78" />
  
  *anime preview menu*
  
  <img width="1895" height="1007" alt="image" src="https://github.com/user-attachments/assets/3b887bcc-a601-4c04-b477-8328f50c227d" />

*episode menu*

  <img width="1895" height="1007" alt="image" src="https://github.com/user-attachments/assets/f6284c55-a1a9-4720-83a0-efca0a767c85" />

</details>

> [!IMPORTANT]
> This project scrapes public-facing websites for its streaming / downloading capabilities and primarily acts as an anilist, jikan and many other media apis tui client. The developer(s) of this application have no affiliation with these content providers. This application hosts zero content and is intended for educational and personal use only. Use at your own risk.
>
> [**Read the Full Disclaimer**](DISCLAIMER.md)

## Core Features

- 📺 **Interactive TUI:** Browse, search, and manage your AniList library in a rich terminal interface powered by `fzf`, `rofi`, or a built-in selector.
- ⚡ **Powerful Search:** Filter the entire AniList database with over 20 different criteria, including genres, tags, year, status, and score.
- 💾 **Local Registry:** Maintain a fast, local database of your anime for offline access, detailed stats, and robust data management.
- ⚙️ **Background Downloader:** Queue episodes for download and let a persistent background worker handle the rest.
- 📜 **Scriptable CLI:** Automate streaming and downloading with powerful, non-interactive commands perfect for scripting.
- 🔧 **Highly Customizable:** Tailor every aspect—from UI colors and providers to playback behavior—via a simple, well-documented configuration file.
- 🔌 **Extensible Architecture:** Easily add new providers, media players, and UI selectors to fit your workflow.

## Installation

Ani-Browse runs on Windows, macOS, Linux, and Android (via Termux). The recommended install is the one-command installer at the [top of this README](#install), which clones this repo and sets everything up. Manual/source steps are below.

### Prerequisites

For the best experience, please install these external tools:

- **Required for Streaming:**
  - [**mpv**](https://mpv.io/installation/) - The primary and recommended media player.
- **Recommended for UI & Previews:**
  - [**fzf**](https://github.com/junegunn/fzf) - For the best fuzzy-finder interface.
  - [**chafa**](https://github.com/hpjansson/chafa) or [**kitty's icat**](https://sw.kovidgoyal.net/kitty/kittens/icat/) - For image previews in the terminal.
- **Recommended for Downloads & Advanced Features:**
  - [**ffmpeg**](https://www.ffmpeg.org/) - Required for downloading HLS streams and merging subtitles.
  - [**webtorrent-cli**](https://github.com/webtorrent/webtorrent-cli) - For streaming torrents directly.

### From source

The one-command installers at the [top of this README](#install) are the
recommended path — they clone this repo, install the app (isolated via pipx),
fetch the provider scrapers, and set up mpv / fzf / chafa / webtorrent.

To install manually instead:

```bash
git clone https://github.com/JouichatH/AniBrowse.git
cd AniBrowse
pipx install .                     # installs the `ani-browse` command (isolated)
python scripts/fetch_providers.py  # fetch the provider scrapers (run with the app's Python)
ani-browse --version
```

> The provider scrapers (allanime / animepahe / animeunity) are not vendored in
> this repo; `scripts/fetch_providers.py` downloads them. The installer runs this
> step for you.

> [!TIP]
> Enable shell completions for a much better experience by running `ani-browse completions` and following the on-screen instructions for your shell.

## Getting Started: Quick Start

Get up and running in three simple steps:

1. **Authenticate with AniList:**

    ```bash
    ani-browse anilist auth
    ```

    This will open your browser. Authorize the app and paste the obtained token back into the terminal. Alternatively, you can pass the token directly as an argument, or provide a path to a text file containing the token.

2. **Launch the Interactive TUI:**

    ```bash
    ani-browse anilist
    ```

3. **Browse & Play:** Use your arrow keys to navigate the menus, select an anime, and choose an episode to stream instantly.

## Usage Guide

### The Interactive TUI (`ani-browse anilist`)

This is the main, user-friendly way to use Ani-Browse. It provides a rich terminal experience where you can:

- Browse trending, popular, and seasonal anime.
- Manage your personal lists (Watching, Completed, Paused, etc.).
- Search for any anime in the AniList database.
- View detailed information, characters, recommendations, reviews, and airing schedules.
- Stream or download episodes directly from the menus.

### Powerful Searching (`ani-browse anilist search`)

Filter the entire AniList database with powerful command-line flags.

```bash
# Search for anime from 2024, sorted by popularity, that is releasing and not on your list
ani-browse anilist search -y 2024 -s POPULARITY_DESC --status RELEASING --not-on-list

# Find the most popular movies with the "Fantasy" genre
ani-browse anilist search -g Fantasy -f MOVIE -s POPULARITY_DESC

# Dump search results as JSON instead of launching the TUI
ani-browse anilist search -t "Demon Slayer" --dump-json
```

### Background Downloads (`ani-browse queue` & `worker`)

Ani-Browse includes a robust background downloading system.

1. **Add episodes to the queue:**

    ```bash
    # Add episodes 1-12 of Jujutsu Kaisen to the download queue
    ani-browse queue add -t "Jujutsu Kaisen" -r "0:12"
    ```

2. **Start the worker process:**

    ````bash
    # Run the worker in the foreground (press Ctrl+C to stop)
    ani-browse worker

    # Or run it as a background process
    ani-browse worker &
    ```The worker will now process the queue, download your episodes, and check for notifications.
    ````

### Scriptable Commands (`download` & `search`)

These commands are designed for automation and quick, non-interactive tasks.

#### `download` Examples

```bash
# Download the latest 5 episodes of One Piece
ani-browse download -t "One Piece" -r "-5"

# Download episodes 1 to 24, merge subtitles, and clean up original files
ani-browse download -t "Jujutsu Kaisen" -r "0:24" --merge --clean
```

#### `search` (Binging) Examples

```bash
# Start binging an anime from the first episode
ani-browse search -t "Attack on Titan" -r ":"

# Watch the latest episode directly
ani-browse search -t "My Hero Academia" -r "-1"
```

### Local Data Management (`ani-browse registry`)

Ani-Browse maintains a local database of your anime for offline access and enhanced performance.

- `registry sync`: Synchronize your local data with your remote AniList account.
- `registry stats`: Show detailed statistics about your viewing habits.
- `registry backup`: Create a compressed backup of your entire registry.
- `registry restore`: Restore your data from a backup file.
- `registry export/import`: Export/import your data to JSON/CSV for use in other applications.
- `registry clean`: Clean up orphaned or invalid entries from your local database.

## Configuration

Ani-Browse is highly customizable. A default configuration file with detailed comments is created on the first run.

- **Find your config file:** `ani-browse config --path`
- **Edit in your default editor:** `ani-browse config`
- **Use the interactive wizard:** `ani-browse config --interactive`

Most settings in the config file can be temporarily overridden with command-line flags (e.g., `ani-browse --provider animepahe anilist`).

<details>
  <summary><b>Default Configuration (`config.ini`) Explained</b></summary>

```ini
# [general] Section: Controls overall application behavior.
[general]
provider = allanime          ; The default anime provider (allanime, animepahe).
selector = fzf               ; The interactive UI tool (fzf, rofi, default).
preview = full               ; Preview type in selectors (full, text, image, none).
image_renderer = icat        ; Tool for terminal image previews (icat, chafa).
icons = True                 ; Display emoji icons in the UI.
auto_select_anime_result = True ; Automatically select the best search match.
...

# [stream] Section: Controls playback and streaming.
[stream]
player = mpv                 ; The media player to use (mpv, vlc).
quality = 1080               ; Preferred stream quality (1080, 720, 480, 360).
translation_type = sub       ; Preferred audio/subtitle type (sub, dub).
auto_next = False            ; Automatically play the next episode.
continue_from_watch_history = True ; Resume playback from where you left off.
use_ipc = True               ; Enable in-player controls via MPV's IPC.
...

# [downloads] Section: Controls the downloader.
[downloads]
downloader = auto            ; Downloader to use (auto, default, yt-dlp).
downloads_dir = ...          ; Directory to save downloaded anime.
max_concurrent_downloads = 3 ; Number of parallel downloads in the worker.
merge_subtitles = True       ; Automatically merge subtitles into the video file.
cleanup_after_merge = True   ; Delete original files after merging.
...

# [worker] Section: Controls the background worker process.
[worker]
enabled = True
notification_check_interval = 15 ; How often to check for new episodes (minutes).
download_check_interval = 5      ; How often to process the download queue (minutes).
...
```

</details>

## Advanced Features

### MPV IPC Integration

When `use_ipc = True` is set in your config, Ani-Browse provides powerful in-player controls without needing to close MPV.

**Key Bindings:**

- `Shift+N`: Play the next episode.
- `Shift+P`: Play the previous episode.
- `Shift+R`: Reload the current episode.
- `Shift+A`: Toggle auto-play for the next episode.
- `Shift+T`: Toggle between `dub` and `sub`.

**Script Messages (For MPV Console):**

- `script-message select-episode <number>`: Jump to a specific episode.
- `script-message select-server <name>`: Switch to a different streaming server.

### Running as a Service (Linux/systemd)

You can run the background worker as a systemd service for persistence.

1. Create a service file at `~/.config/systemd/user/ani-browse-worker.service`:

    ```ini
    [Unit]
    Description=Ani-Browse Background Worker
    After=network-online.target

    [Service]
    Type=simple
    ExecStart=/path/to/your/ani-browse worker --log
    Restart=always
    RestartSec=30

    [Install]
    WantedBy=default.target
    ```

    *Replace `/path/to/your/ani-browse` with the output of `which ani-browse`.*

2. Enable and start the service:

    ```bash
    systemctl --user daemon-reload
    systemctl --user enable --now ani-browse-worker.service
    ```

## Project using it

**[Inazuma](https://github.com/JouichatH/Inazuma)** - official gui wrapper over ani-browse built in kivymd

## Contributing

Contributions are welcome! Whether it's reporting a bug, proposing a feature, or writing code, your help is appreciated. Please read our [**Contributing Guidelines**](CONTRIBUTIONS.md) to get started.

</details>
