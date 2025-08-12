<p align="center">
  <h1 align="center">FastAnime</h1>
</p>
<p align="center">
  <sup>
  Your browser anime experience, from the terminal.
  </sup>
</p>
<div align="center">

[![PyPI - Version](https://img.shields.io/pypi/v/fastanime)](https://pypi.org/project/fastanime/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/fastanime)](https://pypi.org/project/fastanime/)
[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/Benexl/FastAnime/test.yml?label=Tests)](https://github.com/Benexl/FastAnime/actions)
[![Discord](https://img.shields.io/discord/1250887070906323096?label=Discord&logo=discord)](https://discord.gg/HBEmAwvbHV)
[![GitHub Issues](https://img.shields.io/github/issues/Benexl/FastAnime)](https://github.com/Benexl/FastAnime/issues)
[![PyPI - License](https://img.shields.io/pypi/l/fastanime)](https://github.com/Benexl/FastAnime/blob/master/LICENSE)

</div>

<p align="center">
  <a href="https://discord.gg/HBEmAwvbHV">
    <img src="https://invidget.switchblade.xyz/C4rhMA4mmK" alt="Discord Server Invite">
  </a>
</p>

![fastanime](https://github.com/user-attachments/assets/9ab09f26-e4a8-4b70-a315-7def998cec63)

<details>
  <summary>
    <b>Screenshots</b>
  </summary>
  <b>Media Results Menu:</b>
  <img width="1346" height="710" alt="image" src="https://github.com/user-attachments/assets/c56da5d2-d55d-445c-9ad7-4e007e986d5b" />
  <b>Episodes Menu with Preview:</b>
  <img width="1346" height="710" alt="image" src="https://github.com/user-attachments/assets/2294f621-8549-4b1c-9e28-d851b2585037" />

</details>
  
<details>
  <summary>
    <b>Riced Preview Examples</b>
  </summary>

**Anilist Results Menu (FZF):**
![image](https://github.com/user-attachments/assets/240023a7-7e4e-47dd-80ff-017d65081ee1)

**Episodes Menu with Preview (FZF):**
![image](https://github.com/user-attachments/assets/580f86ef-326f-4ab3-9bd8-c1cb312fbfa6)

**No Image Preview Mode:**
![image](https://github.com/user-attachments/assets/e1248a85-438f-4758-ae34-b0e0b224addd)

**Desktop Notifications + Episodes Menu:**
![image](https://github.com/user-attachments/assets/b7802ef1-ca0d-45f5-a13a-e39c96a5d499)

</details>

## Core Features

*   📺 **Interactive TUI:** Browse, search, and manage your AniList library in a rich terminal interface powered by `fzf`, `rofi`, or a built-in selector.
*   ⚡ **Powerful Search:** Filter the entire AniList database with over 20 different criteria, including genres, tags, year, status, and score.
*   💾 **Local Registry:** Maintain a fast, local database of your anime for offline access, detailed stats, and robust data management.
*   ⚙️ **Background Downloader:** Queue episodes for download and let a persistent background worker handle the rest.
*   📜 **Scriptable CLI:** Automate streaming and downloading with powerful, non-interactive commands perfect for scripting.
*   🔧 **Highly Customizable:** Tailor every aspect—from UI colors and providers to playback behavior—via a simple, well-documented configuration file.
*   🔌 **Extensible Architecture:** Easily add new providers, media players, and UI selectors to fit your workflow.

## Installation

FastAnime runs on any platform with Python 3.10+, including Windows, macOS, Linux, and Android (via Termux).

### Prerequisites

For the best experience, please install these external tools:

*   **Required for Streaming:**
    *   [**mpv**](https://mpv.io/installation/) - The primary and recommended media player.
*   **Recommended for UI & Previews:**
    *   [**fzf**](https://github.com/junegunn/fzf) - For the best fuzzy-finder interface.
    *   [**chafa**](https://github.com/hpjansson/chafa) or [**kitty's icat**](https://sw.kovidgoyal.net/kitty/kittens/icat/) - For image previews in the terminal.
*   **Recommended for Downloads & Advanced Features:**
    *   [**ffmpeg**](https://www.ffmpeg.org/) - Required for downloading HLS streams and merging subtitles.
    *   [**webtorrent-cli**](https://github.com/webtorrent/webtorrent-cli) - For streaming torrents directly.

### Recommended Installation (uv)

The best way to install FastAnime is with [**uv**](https://github.com/astral-sh/uv), a lightning-fast Python package manager.

```bash
# Install with all optional features for the full experience
uv tool install "fastanime[standard]"

# Or, pick and choose the extras you need:
uv tool install fastanime  # Core functionality only
uv tool install "fastanime[download]"  # For advanced downloading with yt-dlp
uv tool install "fastanime[discord]"   # For Discord Rich Presence
uv tool install "fastanime[notifications]" # For desktop notifications
```

### Other Installation Methods

<details>
  <summary><b>Platform-Specific and Alternative Installers</b></summary>
  
  #### Nix / NixOS
  ```bash
  nix profile install github:Benexl/fastanime
  ```

  #### Arch Linux (AUR)
  Use an AUR helper like `yay` or `paru`.
  ```bash
  # Stable version (recommended)
  yay -S fastanime

  # Git version (latest commit)
  yay -S fastanime-git
  ```

  #### Using pipx (for isolated environments)
  ```bash
  pipx install "fastanime[standard]"
  ```
  
  #### Using pip
  ```bash
  pip install "fastanime[standard]"
  ```
</details>

<details>
  <summary><b>Building from Source</b></summary>
  
  Requires [Git](https://git-scm.com/), [Python 3.10+](https://www.python.org/), and [uv](https://astral.sh/blog/uv).
  ```bash
  git clone https://github.com/Benexl/FastAnime.git --depth 1
  cd FastAnime
  uv tool install .
  fastanime --version
  ```
</details>

> [!TIP]
> Enable shell completions for a much better experience by running `fastanime completions` and following the on-screen instructions for your shell.

## Getting Started: Quick Start

Get up and running in three simple steps:

1.  **Authenticate with AniList:**
    ```bash
    fastanime anilist auth
    ```
    This will open your browser. Authorize the app and paste the obtained token back into the terminal.

2.  **Launch the Interactive TUI:**
    ```bash
    fastanime anilist
    ```

3.  **Browse & Play:** Use your arrow keys to navigate the menus, select an anime, and choose an episode to stream instantly.

## Usage Guide

### The Interactive TUI (`fastanime anilist`)

This is the main, user-friendly way to use FastAnime. It provides a rich terminal experience where you can:
*   Browse trending, popular, and seasonal anime.
*   Manage your personal lists (Watching, Completed, Paused, etc.).
*   Search for any anime in the AniList database.
*   View detailed information, characters, recommendations, reviews, and airing schedules.
*   Stream or download episodes directly from the menus.

### Powerful Searching (`fastanime anilist search`)

Filter the entire AniList database with powerful command-line flags.

```bash
# Search for anime from 2024, sorted by popularity, that is releasing and not on your list
fastanime anilist search -y 2024 -s POPULARITY_DESC --status RELEASING --not-on-list

# Find the most popular movies with the "Fantasy" genre
fastanime anilist search -g Fantasy -f MOVIE -s POPULARITY_DESC

# Dump search results as JSON instead of launching the TUI
fastanime anilist search -t "Demon Slayer" --dump-json
```

### Background Downloads (`fastanime queue` & `worker`)

FastAnime includes a robust background downloading system.

1.  **Add episodes to the queue:**
    ```bash
    # Add episodes 1-12 of Jujutsu Kaisen to the download queue
    fastanime queue add -t "Jujutsu Kaisen" -r "0:12"
    ```
2.  **Start the worker process:**
    ```bash
    # Run the worker in the foreground (press Ctrl+C to stop)
    fastanime worker

    # Or run it as a background process
    fastanime worker &
    ```The worker will now process the queue, download your episodes, and check for notifications.

### Scriptable Commands (`download` & `search`)

These commands are designed for automation and quick, non-interactive tasks.

#### `download` Examples
```bash
# Download the latest 5 episodes of One Piece
fastanime download -t "One Piece" -r "-5"

# Download episodes 1 to 24, merge subtitles, and clean up original files
fastanime download -t "Jujutsu Kaisen" -r "0:24" --merge --clean
```

#### `search` (Binging) Examples
```bash
# Start binging an anime from the first episode
fastanime search -t "Attack on Titan" -r ":"

# Watch the latest episode directly
fastanime search -t "My Hero Academia" -r "-1"
```

### Local Data Management (`fastanime registry`)

FastAnime maintains a local database of your anime for offline access and enhanced performance.

*   `registry sync`: Synchronize your local data with your remote AniList account.
*   `registry stats`: Show detailed statistics about your viewing habits.
*   `registry backup`: Create a compressed backup of your entire registry.
*   `registry restore`: Restore your data from a backup file.
*   `registry export/import`: Export/import your data to JSON/CSV for use in other applications.
*   `registry clean`: Clean up orphaned or invalid entries from your local database.

## Configuration

FastAnime is highly customizable. A default configuration file with detailed comments is created on the first run.

*   **Find your config file:** `fastanime config --path`
*   **Edit in your default editor:** `fastanime config`
*   **Use the interactive wizard:** `fastanime config --interactive`

Most settings in the config file can be temporarily overridden with command-line flags (e.g., `fastanime --provider animepahe anilist`).

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

When `use_ipc = True` is set in your config, FastAnime provides powerful in-player controls without needing to close MPV.

**Key Bindings:**
*   `Shift+N`: Play the next episode.
*   `Shift+P`: Play the previous episode.
*   `Shift+R`: Reload the current episode.
*   `Shift+A`: Toggle auto-play for the next episode.
*   `Shift+T`: Toggle between `dub` and `sub`.

**Script Messages (For MPV Console):**
*   `script-message select-episode <number>`: Jump to a specific episode.
*   `script-message select-server <name>`: Switch to a different streaming server.

### Running as a Service (Linux/systemd)

You can run the background worker as a systemd service for persistence.

1.  Create a service file at `~/.config/systemd/user/fastanime-worker.service`:
    ```ini
    [Unit]
    Description=FastAnime Background Worker
    After=network-online.target

    [Service]
    Type=simple
    ExecStart=/path/to/your/fastanime worker --log
    Restart=always
    RestartSec=30

    [Install]
    WantedBy=default.target
    ```
    *Replace `/path/to/your/fastanime` with the output of `which fastanime`.*

2.  Enable and start the service:
    ```bash
    systemctl --user daemon-reload
    systemctl --user enable --now fastanime-worker.service
    ```

## Contributing

Contributions are welcome! Whether it's reporting a bug, proposing a feature, or writing code, your help is appreciated. Please read our [**Contributing Guidelines**](CONTRIBUTIONS.md) to get started.

## Disclaimer

> [!IMPORTANT]
> This project scrapes public-facing websites. The developer(s) of this application have no affiliation with these content providers. This application hosts zero content and is intended for educational and personal use only. Use at your own risk.
> 
> [**Read the Full Disclaimer**](DISCLAIMER.md)
