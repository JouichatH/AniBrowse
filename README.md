<p align="center">
  <h1 align="center">FastAnime</h1>
</p>
<p align="center">
  <sup>
  Your browser anime experience, from the terminal.
  </sup>
</p>
<div align="center">

![PyPI - Downloads](https://img.shields.io/pypi/dm/fastanime) ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/Benexl/FastAnime/test.yml?label=Tests)
![Discord](https://img.shields.io/discord/1250887070906323096?label=Discord)
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/Benexl/FastAnime)
![PyPI - License](https://img.shields.io/pypi/l/fastanime)
![Static Badge](https://img.shields.io/badge/lines%20of%20code-13k%2B-green)
</div>

<p align="center">
<a href="https://discord.gg/HBEmAwvbHV">
<img src="https://invidget.switchblade.xyz/C4rhMA4mmK">
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

## Installation

![Windows](https://img.shields.io/badge/-Windows_x64-blue.svg?style=for-the-badge&logo=windows)
![Linux/BSD](https://img.shields.io/badge/-Linux/BSD-red.svg?style=for-the-badge&logo=linux)
![Arch Linux](https://img.shields.io/badge/-Arch_Linux-black.svg?style=for-the-badge&logo=archlinux)
![MacOS](https://img.shields.io/badge/-MacOS-lightblue.svg?style=for-the-badge&logo=apple)
![Android](https://img.shields.io/badge/-Android-green.svg?style=for-the-badge&logo=android)

The app runs wherever Python 3.10+ is available. On Android, you can use [Termux](https://github.com/termux/termux-app). For installation help, join our [Discord](https://discord.gg/HBEmAwvbHV).

### Installation on NixOS

![Static Badge](https://img.shields.io/badge/NixOs-black?style=flat&logo=nixos)

```bash
nix profile install github:Benexl/fastanime
```

### Installation on Arch Linux

![Static Badge](https://img.shields.io/badge/arch-black?style=flat&logo=archlinux)

Install from the AUR using an AUR helper like `yay` or `paru`.

```bash
# Stable version (recommended)
yay -S fastanime

# Git version (latest commit)
yay -S fastanime-git
```

### Recommended Installation (uv)

The recommended installation method is with [uv](https://docs.astral.sh/uv/), a fast Python package manager.

```bash
# Install with all optional features (recommended for the full experience)
uv tool install "fastanime[standard]"

# Stripped-down installations
uv tool install fastanime  # Core functionality only
uv tool install "fastanime[download]"  # For advanced downloading
uv tool install "fastanime[discord]"   # For Discord Rich Presence
uv tool install "fastanime[notifications]" # For desktop notifications
```

### Other Installation Methods

<details>
  <summary><b>pipx or pip</b></summary>
  
  #### Using pipx (Recommended for isolated environments)
  ```bash
  pipx install "fastanime[standard]"
  ```
  
  #### Using pip
  ```bash
  pip install "fastanime[standard]"
  ```
</details>

<details>
  <summary><b>Bleeding Edge & Building from Source</b></summary>
  
  ### Installing the Bleeding Edge Version
  Download the latest `fastanime_debug_build` artifact from the [GitHub Actions page](https://github.com/Benexl/FastAnime/actions), then:
  ```bash
  unzip fastanime_debug_build.zip
  uv tool install fastanime-*.whl
  ```

  ### Building from Source
  Requirements: [Git](https://git-scm.com/), [Python 3.10+](https://www.python.org/), and [uv](https://astral.sh/blog/uv).
  ```bash
  git clone https://github.com/Benexl/FastAnime.git --depth 1
  cd FastAnime
  uv tool install .
  fastanime --version
  ```
</details>

> [!TIP]
> Enable shell completions for a much better experience by running `fastanime completions` and following the on-screen instructions for your shell.

### External Dependencies

For the best experience, install these external tools:

*   **Required for Streaming:**
    *   [**mpv**](https://mpv.io/installation/) - The primary media player.
*   **Recommended for UI & Previews:**
    *   [**fzf**](https://github.com/junegunn/fzf) - For a powerful fuzzy-finder interface.
    *   [**chafa**](https://github.com/hpjansson/chafa) or [**kitty's icat**](https://sw.kovidgoyal.net/kitty/kittens/icat/) - For image previews in the terminal.
*   **Recommended for Downloads & Features:**
    *   [**ffmpeg**](https://www.ffmpeg.org/) - Required for downloading HLS streams.
    *   [**webtorrent-cli**](https://github.com/webtorrent/webtorrent-cli) - For streaming torrents.
    *   [**syncplay**](https://syncplay.pl/) - To watch anime together with friends.
    *   [**feh**](https://github.com/derf/feh) or **kitty's icat** - For the experimental manga mode.

## Usage

FastAnime offers a rich interactive TUI for browsing and a powerful CLI for scripting and automation.

### Global Options

Most options can be passed directly to the `fastanime` command to override your config for that session.

*   `--provider <allanime|animepahe>`: Choose the streaming site to use.
*   `--selector <fzf|rofi|default>`: Choose the UI backend.
*   `--preview`, `--no-preview`: Enable/disable image and info previews (requires `fzf`).
*   `--dub`, `--sub`: Set preferred translation type.
*   `--icons`, `--no-icons`: Toggle UI icons.
*   `--log`, `--log-file`: Enable logging to stdout or a file for debugging.
*   `--rich-traceback`: Show detailed, formatted tracebacks on error.

### Main Commands

*   `fastanime anilist`: The main entry point for the interactive TUI. Browse, search, and manage your lists.
*   `fastanime registry`: Manage your local database of anime. Sync, search, backup, and restore.
*   `fastanime download`: Scriptable command to download specific episodes.
*   `fastanime search`: Scriptable command to find and stream episodes directly.
*   `fastanime config`: Manage your configuration file.
*   `fastanime update`: Update FastAnime to the latest version.
*   `fastanime queue`: Add episodes to the background download queue.
*   `fastanime worker`: Run the background worker for downloads and notifications.

---

### Deep Dive: `fastanime anilist` (Interactive TUI)

This is the primary way to use FastAnime. Simply run `fastanime anilist` to launch a rich, interactive terminal experience. From here you can:

*   Browse trending, popular, and seasonal anime.
*   Manage your personal lists (Watching, Completed, etc.) after logging in with `fastanime anilist auth`.
*   Search for any anime in the AniList database.
*   View detailed information, characters, recommendations, reviews, and airing schedules.
*   Stream or download episodes.

#### `anilist search` Subcommand

A powerful command to filter the AniList database directly from your terminal.

```bash
# Search for anime from 2024, sorted by popularity, that is releasing and not on your list
fastanime anilist search -y 2024 -s POPULARITY_DESC --status RELEASING --not-on-list

# Find the most popular movies with the "Fantasy" genre
fastanime anilist search -g Fantasy -f MOVIE -s POPULARITY_DESC

# Dump search results as JSON instead of launching the TUI
fastanime anilist search -t "Demon Slayer" --dump-json
```

#### `anilist download` Subcommand

Combines the power of `anilist search` with the `download` command, allowing you to batch-download based on filters.

```bash
# Download episodes 1-12 of all fantasy anime that aired in Winter 2024
fastanime anilist download --season WINTER -y 2024 -g Fantasy -r "0:12"
```

---

### Deep Dive: `fastanime registry` (Local Database)

FastAnime maintains a local registry of your anime for offline access, enhanced performance, and powerful data management.

*   `registry sync`: Synchronize your local data with your remote AniList account.
*   `registry stats`: Show detailed statistics about your viewing habits.
*   `registry search`: Search your locally stored anime data.
*   `registry backup`: Create a compressed backup of your entire registry.
*   `registry restore`: Restore your data from a backup file.
*   `registry export/import`: Export your data to JSON/CSV for use in other applications.

---

### Scriptable Commands: `download` & `search`

These commands are designed for automation and quick access.

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
---
### MPV IPC Integration

When `use_ipc` is enabled, FastAnime provides powerful in-player controls without closing MPV.

#### Key Bindings
*   `Shift+N`: Play the next episode.
*   `Shift+P`: Play the previous episode.
*   `Shift+R`: Reload the current episode.
*   `Shift+A`: Toggle auto-play for the next episode.
*   `Shift+T`: Toggle between `dub` and `sub`.

#### Script Messages (MPV Console)
*   `script-message select-episode <number>`: Jump to a specific episode.
*   `script-message select-server <name>`: Switch to a different streaming server.

## Configuration

FastAnime is highly customizable via its configuration file, located at `~/.config/fastanime/config.ini` (path may vary by OS).
Run `fastanime config --path` to find the exact location on your system.

A default configuration file with detailed comments is created on first run. You can edit it with `fastanime config` or use the interactive wizard with `fastanime config --interactive`.

<details>
  <summary><b>Default Configuration (`config.ini`)</b></summary>
  
```ini
[general]
# The preferred watch history tracker (local,remote) in cases of conflicts
preferred_tracker = local
# The pygment style to use
pygment_style = github-dark
# The spinner to use
preferred_spinner = smiley
# The media database API to use (e.g., 'anilist', 'jikan').
media_api = anilist
# The default anime provider to use for scraping.
provider = allanime
# The interactive selector tool to use for menus.
selector = fzf
# Automatically select the best-matching search result from a provider.
auto_select_anime_result = True
# Display emoji icons in the user interface.
icons = True
# Type of preview to display in selectors.
preview = full
# The command-line tool to use for rendering images in the terminal.
image_renderer = icat
# The external application to use for viewing manga pages.
manga_viewer = feh
# Automatically check for new versions of FastAnime on startup.
check_for_updates = True
# Enable caching of network requests to speed up subsequent operations.
cache_requests = True
# Maximum lifetime for a cached request in DD:HH:MM format.
max_cache_lifetime = 03:00:00
# Attempt to normalize provider titles to match AniList titles.
normalize_titles = True
# Enable Discord Rich Presence to show your current activity.
discord = False
# Number of recently watched anime to keep in history.
recent = 50

[stream]
# The media player to use for streaming.
player = mpv
# Preferred stream quality.
quality = 1080
# Preferred audio/subtitle language type.
translation_type = sub
# The default server to use from a provider. 'top' uses the first available.
server = TOP
# Automatically play the next episode when the current one finishes.
auto_next = False
# Automatically resume playback from the last known episode and position.
continue_from_watch_history = True
# Which watch history to prioritize: local file or remote AniList progress.
preferred_watch_history = local
# Automatically skip openings/endings if skip data is available.
auto_skip = False
# Percentage of an episode to watch before it's marked as complete.
episode_complete_at = 80
# The format selection string for yt-dlp.
ytdlp_format = best[height<=1080]/bestvideo[height<=1080]+bestaudio/best
# Prevent updating AniList progress to a lower episode number.
force_forward_tracking = True
# Default behavior for tracking progress on AniList.
default_media_list_tracking = prompt
# Preferred language code for subtitles (e.g., 'en', 'es').
sub_lang = eng
# Use IPC communication with the player for advanced features like episode navigation.
use_ipc = True
```
</details>

## Contributing

Pull requests are highly welcome! Please read our [**Contributing Guidelines**](CONTRIBUTIONS.md) to get started with setting up a development environment and understanding our coding standards.

## Disclaimer

> [!IMPORTANT]
>
> This project scrapes public-facing websites (`allanime`, `animepahe`). The developer(s) of this application have no affiliation with these content providers. This application hosts zero content. Use at your own risk.
>
> [**Full Disclaimer**](DISCLAIMER.md)
