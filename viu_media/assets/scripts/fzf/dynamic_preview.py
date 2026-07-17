#!/usr/bin/env python3
#
# FZF Dynamic Preview Script for Search Results
#
# This script handles previews for dynamic search by reading from the cached
# search results JSON and generating preview content on-the-fly.
# Template variables are injected by Python using .replace()

import json
import os
import shutil
import subprocess
import sys
import time
from hashlib import sha256
from pathlib import Path

# Import the utility functions
from _ansi_utils import (
    get_terminal_width,
    print_rule,
    print_table_row,
    strip_markdown,
    wrap_text,
)


# --- Template Variables (Injected by Python) ---
SEARCH_RESULTS_FILE = Path("{SEARCH_RESULTS_FILE}")
IMAGE_CACHE_DIR = Path("{IMAGE_CACHE_DIR}")
PREVIEW_MODE = "{PREVIEW_MODE}"
IMAGE_RENDERER = "{IMAGE_RENDERER}"
HEADER_COLOR = "{HEADER_COLOR}"
SEPARATOR_COLOR = "{SEPARATOR_COLOR}"
SCALE_UP = "{SCALE_UP}" == "True"

# --- Arguments ---
# sys.argv[1] is the selected anime title from fzf
SELECTED_TITLE = sys.argv[1] if len(sys.argv) > 1 else ""


def format_number(num):
    """Format number with thousand separators."""
    if num is None:
        return "N/A"
    return f"{num:,}"


def format_score_stars(score):
    """Format score as stars out of 6."""
    if score is None:
        return "N/A"
    # Convert 0-100 score to 0-6 stars, capped at 6 for consistency
    stars = min(round(score * 6 / 100), 6)
    return "⭐" * stars + f" ({score}/100)"


def format_date(date_obj):
    """Format date object to string."""
    if not date_obj or date_obj == "null":
        return "N/A"

    year = date_obj.get("year")
    month = date_obj.get("month")
    day = date_obj.get("day")

    if not year:
        return "N/A"
    if month and day:
        return f"{day}/{month}/{year}"
    if month:
        return f"{month}/{year}"
    return str(year)


def get_media_from_results(title):
    """Find media item in search results by title."""
    if not SEARCH_RESULTS_FILE.exists():
        return None

    try:
        with open(SEARCH_RESULTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        media_list = data.get("data", {}).get("Page", {}).get("media", [])

        for media in media_list:
            title_obj = media.get("title", {})
            eng = title_obj.get("english")
            rom = title_obj.get("romaji")
            nat = title_obj.get("native")

            if title in (eng, rom, nat):
                return media

        return None
    except Exception as e:
        print(f"Error reading search results: {e}", file=sys.stderr)
        return None


def download_image(url: str, output_path: Path) -> bool:
    """Download image from URL and save to file."""
    try:
        # Try using urllib (stdlib)
        from urllib import request

        req = request.Request(url, headers={"User-Agent": "ani-browse/1.0"})
        with request.urlopen(req, timeout=5) as response:
            data = response.read()
            output_path.write_bytes(data)
            return True
    except Exception:
        # Silently fail - preview will just not show image
        return False


def which(cmd):
    """Check if command exists."""
    return shutil.which(cmd)


def get_terminal_dimensions():
    """Get terminal dimensions from FZF environment."""
    fzf_cols = os.environ.get("FZF_PREVIEW_COLUMNS")
    fzf_lines = os.environ.get("FZF_PREVIEW_LINES")

    if fzf_cols and fzf_lines:
        return int(fzf_cols), int(fzf_lines)

    try:
        rows, cols = (
            subprocess.check_output(
                ["stty", "size"], text=True, stderr=subprocess.DEVNULL
            )
            .strip()
            .split()
        )
        return int(cols), int(rows)
    except Exception:
        return 80, 24


# chafa flags for real sixel graphics (used only when a renderer explicitly asks
# for sixel; note that fzf on Windows does NOT relay sixel through its preview
# pane, so on Windows Terminal this shows nothing - hence chafa-auto uses symbols).
#   -f sixel      : force the sixel encoder
#   --probe off   : don't query the terminal (impossible through fzf's pipe)
#   -w 9          : maximum work/quality
#   --dither none : clean flat output, best for (mostly flat) anime cover art
_CHAFA_SIXEL_FLAGS = ["-f", "sixel", "--probe", "off", "-w", "9", "--dither", "none"]
# High-quality symbol art. This is what actually renders inside fzf's preview on
# every platform. Much finer than chafa's default (plain `chafa -s WxH`), which is
# what looked "pixelized".
_CHAFA_SYMBOL_FLAGS = ["-f", "symbols", "--colors", "full", "-w", "9",
                       "--color-space", "din99d"]


def render_kitty(file_path, width, height, scale_up):
    """Render using the Kitty Graphics Protocol (kitten/icat)."""
    cmd = []
    if which("kitten"):
        cmd = ["kitten", "icat"]
    elif which("icat"):
        cmd = ["icat"]
    elif which("kitty"):
        cmd = ["kitty", "+kitten", "icat"]

    if not cmd:
        return False

    args = [
        "--clear",
        "--transfer-mode=memory",
        "--unicode-placeholder",
        "--stdin=no",
        f"--place={width}x{height}@0x0",
    ]

    if scale_up:
        args.append("--scale-up")

    args.append(file_path)

    subprocess.run(cmd + args, stdout=sys.stdout, stderr=sys.stderr)
    return True


def render_sixel(file_path, width, height):
    """Render using Sixel."""
    if which("chafa"):
        subprocess.run(
            ["chafa", *_CHAFA_SIXEL_FLAGS, "-s", f"{width}x{height}", file_path],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return True

    if which("img2sixel"):
        pixel_width = width * 10
        pixel_height = height * 20
        subprocess.run(
            [
                "img2sixel",
                f"--width={pixel_width}",
                f"--height={pixel_height}",
                file_path,
            ],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return True

    return False


def render_iterm(file_path, width, height):
    """Render using iTerm2 Inline Image Protocol."""
    if which("imgcat"):
        subprocess.run(
            ["imgcat", "-W", str(width), "-H", str(height), file_path],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return True

    if which("chafa"):
        subprocess.run(
            ["chafa", "-f", "iterm", "-s", f"{width}x{height}", file_path],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return True
    return False


def render_timg(file_path, width, height):
    """Render using timg."""
    if which("timg"):
        subprocess.run(
            ["timg", f"-g{width}x{height}", "--upscale", file_path],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        return True
    return False


def render_chafa_auto(file_path, width, height):
    """Render with chafa as high-quality symbol art.

    We force ``-f symbols`` with tuned flags rather than plain ``chafa -s WxH``:
    when chafa writes into fzf's captured pipe it can't probe the terminal and its
    default output is coarse/blocky (the "pixelized" look). Symbols are what fzf's
    preview can actually display on every platform (fzf does not relay sixel on
    Windows).
    """
    if not which("chafa"):
        return False
    subprocess.run(
        ["chafa", *_CHAFA_SYMBOL_FLAGS, "-s", f"{width}x{height}", file_path],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    return True


# --- Sixel overlay (Windows Terminal) ------------------------------------------
# fzf on Windows does not relay sixel through its preview pane, so we draw the real
# image straight onto the terminal, on top of blank rows the preview reserves. A
# detached copy of THIS script (re-invoked via __file__) does the drawing so it
# outlives the short preview process; it attaches to fzf's console and writes the
# sixel to CONOUT$ (fzf's preview children have no console of their own).

_OVERLAY_SENTINEL = "__viu_overlay_draw__"


def _overlay_possible():
    return (
        os.name == "nt"
        and bool(os.environ.get("WT_SESSION"))
        and bool(os.environ.get("FZF_PREVIEW_TOP"))
        and bool(which("chafa"))
    )


def _read_token(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _overlay_python():
    """Prefer pythonw.exe so the detached drawer never flashes a console window."""
    exe = sys.executable
    if os.name == "nt":
        pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(pyw):
            return pyw
    return exe


def _no_window_kwargs():
    """Popen kwargs that keep the detached drawer fully windowless on Windows."""
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0  # SW_HIDE
    return {"creationflags": 0x08000000, "startupinfo": startupinfo}  # CREATE_NO_WINDOW


def _sixel_overlay(file_path):
    """Reserve the image rows and launch the detached drawer. True if launched."""
    try:
        top = int(os.environ["FZF_PREVIEW_TOP"]) + 1
        left = int(os.environ.get("FZF_PREVIEW_LEFT", "0")) + 1
        cols = int(os.environ.get("FZF_PREVIEW_COLUMNS", "40"))
        lines = int(os.environ.get("FZF_PREVIEW_LINES", "40"))
    except (KeyError, ValueError):
        return False
    # Fill most of the pane. A portrait cover needs MORE cells wide than tall
    # (cells are ~2x taller than wide), so DON'T cap the width - that is what made
    # images tiny. Reserve ~70% of the pane height and let chafa preserve aspect.
    rows = max(12, min(lines - 3, int(lines * 0.7)))
    width = max(12, cols - 2)
    token_id = sha256(file_path.encode("utf-8")).hexdigest()
    token_file = IMAGE_CACHE_DIR / ".preview-current"
    try:
        IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        token_file.write_text(token_id, encoding="utf-8")
    except OSError:
        return False
    try:
        subprocess.Popen(
            [
                _overlay_python(), os.path.abspath(__file__), _OVERLAY_SENTINEL,
                file_path, str(top), str(left), str(width), str(rows),
                token_id, str(token_file),
            ],
            close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, **_no_window_kwargs(),
        )
    except Exception:
        return False
    # Reserve the image area so fzf's own text doesn't land where the sixel goes.
    sys.stdout.write("\n" * rows)
    sys.stdout.flush()
    return True


def _overlay_draw(argv):
    """Detached drawer entry point: paint the sixel onto fzf's console buffer."""
    try:
        image, top, left, cols, rows, token_id, token_file = argv[:7]
        top, left, cols, rows = int(top), int(left), int(cols), int(rows)
    except (ValueError, IndexError):
        return
    time.sleep(0.20)  # settle: draw only once fzf has repainted / scrolling paused
    if _read_token(token_file) != token_id:
        return
    try:
        proc = subprocess.run(
            ["chafa", "-f", "sixel", "--probe", "off", "-w", "9", "--dither", "none",
             "-s", f"{cols}x{max(rows - 1, 1)}", image],
            capture_output=True, timeout=15, **_no_window_kwargs(),
        )
        sixel = proc.stdout if proc.returncode == 0 else b""
    except Exception:
        return
    if not sixel or _read_token(token_file) != token_id:
        return
    parts = [b"\x1b7"]  # save cursor
    for i in range(rows):  # clear the target region first
        parts.append(("\x1b[%d;%dH\x1b[%dX" % (top + i, left, cols)).encode())
    parts.append(("\x1b[%d;%dH" % (top, left)).encode())  # position, then draw
    parts.append(sixel)
    parts.append(b"\x1b8")  # restore cursor
    _console_write(b"".join(parts))


def _console_write(data):
    if os.name == "nt":
        _console_write_windows(data)
        return
    try:
        with open("/dev/tty", "wb") as tty:
            tty.write(data)
            tty.flush()
    except OSError:
        pass


def _console_write_windows(data):
    import ctypes
    from ctypes import wintypes

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateFileW.restype = wintypes.HANDLE
    k.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    pid = _find_fzf_pid(k)
    if not pid:
        return
    k.FreeConsole()
    if not k.AttachConsole(wintypes.DWORD(pid)):
        return
    generic_write, share_rw, open_existing = 0x40000000, 0x3, 3
    handle = k.CreateFileW(
        "CONOUT$", generic_write, share_rw, None, open_existing, 0, None
    )
    invalid = ctypes.c_void_p(-1).value
    if not handle or handle == invalid:
        return
    written = wintypes.DWORD(0)
    buf = (ctypes.c_char * len(data)).from_buffer_copy(data)
    k.WriteFile(handle, buf, wintypes.DWORD(len(data)), ctypes.byref(written), None)
    k.CloseHandle(handle)


def _find_fzf_pid(k):
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260),
        ]

    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    invalid = ctypes.c_void_p(-1).value
    if not snap or snap == invalid:
        return None
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    pid = None
    try:
        if k.Process32FirstW(snap, ctypes.byref(entry)):
            while True:
                if entry.szExeFile.lower() == "fzf.exe":
                    pid = entry.th32ProcessID
                    break
                if not k.Process32NextW(snap, ctypes.byref(entry)):
                    break
    finally:
        k.CloseHandle(snap)
    return pid


def fzf_image_preview(file_path: str):
    """Main dispatch function to choose the best renderer."""
    cols, lines = get_terminal_dimensions()
    width = cols
    height = lines

    # Check explicit configuration
    if IMAGE_RENDERER == "icat" or IMAGE_RENDERER == "system-kitty":
        if render_kitty(file_path, width, height, SCALE_UP):
            return

    elif IMAGE_RENDERER == "sixel" or IMAGE_RENDERER == "system-sixels":
        # On Windows Terminal, draw a real image via the console overlay (fzf won't
        # relay sixel); elsewhere, sixel-to-stdout works.
        if _overlay_possible() and _sixel_overlay(file_path):
            return
        if render_sixel(file_path, width, height):
            return

    elif IMAGE_RENDERER == "imgcat":
        if render_iterm(file_path, width, height):
            return

    elif IMAGE_RENDERER == "timg":
        if render_timg(file_path, width, height):
            return

    elif IMAGE_RENDERER == "chafa":
        if render_chafa_auto(file_path, width, height):
            return

    # Auto-detection / Fallback
    if os.environ.get("KITTY_WINDOW_ID") or os.environ.get("GHOSTTY_BIN_DIR"):
        if render_kitty(file_path, width, height, SCALE_UP):
            return

    if os.environ.get("TERM_PROGRAM") == "iTerm.app":
        if render_iterm(file_path, width, height):
            return

    # Try standard tools in order of quality/preference
    if render_kitty(file_path, width, height, SCALE_UP):
        return
    if render_sixel(file_path, width, height):
        return
    if render_timg(file_path, width, height):
        return
    if render_chafa_auto(file_path, width, height):
        return

    print("⚠️ No suitable image renderer found (icat, chafa, timg, img2sixel).")


def main():
    # Detached drawer re-invocation (see _sixel_overlay): draw and exit.
    if len(sys.argv) > 2 and sys.argv[1] == _OVERLAY_SENTINEL:
        _overlay_draw(sys.argv[2:])
        return

    if not SELECTED_TITLE:
        print("No selection")
        return

    # Get the media data from cached search results
    media = get_media_from_results(SELECTED_TITLE)

    if not media:
        print("Loading preview...")
        return

    term_width = get_terminal_width()

    # Extract media information
    title_obj = media.get("title", {})
    title = (
        title_obj.get("english")
        or title_obj.get("romaji")
        or title_obj.get("native")
        or "Unknown"
    )

    # Show image if in image or full mode
    if PREVIEW_MODE in ("image", "full"):
        cover_image = media.get("coverImage", {}).get("large", "")
        if cover_image:
            # Ensure image cache directory exists
            IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # Generate hash matching the preview worker pattern
            # Use "anime-" prefix and hash of just the title (no KEY prefix for dynamic search)
            hash_id = f"anime-{sha256(SELECTED_TITLE.encode('utf-8')).hexdigest()}"
            image_file = IMAGE_CACHE_DIR / f"{hash_id}.png"

            # Download image if not cached
            if not image_file.exists():
                download_image(cover_image, image_file)

            # Try to render the image
            if image_file.exists():
                fzf_image_preview(str(image_file))
                print()  # Spacer
            else:
                print("🖼️  Loading image...")
                print()

    # Show text info if in text or full mode
    if PREVIEW_MODE in ("text", "full"):
        # Separator line
        r, g, b = map(int, SEPARATOR_COLOR.split(","))
        separator = f"\x1b[38;2;{r};{g};{b}m" + ("─" * term_width) + "\x1b[0m"
        print(separator, flush=True)

        # Title centered
        print(title.center(term_width))

        # Extract data
        status = media.get("status", "Unknown")
        format_type = media.get("format", "Unknown")
        episodes = media.get("episodes", "??")
        duration = media.get("duration")
        duration_str = f"{duration} min/ep" if duration else "Unknown"

        score = media.get("averageScore")
        score_str = format_score_stars(score)

        favourites = format_number(media.get("favourites", 0))
        popularity = format_number(media.get("popularity", 0))

        genres = ", ".join(media.get("genres", [])) or "Unknown"

        start_date = format_date(media.get("startDate"))
        end_date = format_date(media.get("endDate"))

        studios_list = media.get("studios", {}).get("nodes", [])
        # Studios are those with isAnimationStudio=true
        studios = ", ".join([s["name"] for s in studios_list if s.get("name") and s.get("isAnimationStudio")]) or "N/A"
        # Producers are those with isAnimationStudio=false
        producers = ", ".join([s["name"] for s in studios_list if s.get("name") and not s.get("isAnimationStudio")]) or "N/A"

        synonyms_list = media.get("synonyms", [])
        # Include romaji in synonyms if different from title
        romaji = title_obj.get("romaji")
        if romaji and romaji != title and romaji not in synonyms_list:
            synonyms_list = [romaji] + synonyms_list
        synonyms = ", ".join(synonyms_list) or "N/A"

        # Tags
        tags_list = media.get("tags", [])
        tags = ", ".join([t.get("name", "") for t in tags_list if t.get("name")]) or "N/A"

        # Next airing episode
        next_airing = media.get("nextAiringEpisode")
        if next_airing:
            next_ep = next_airing.get("episode", "?")
            airing_at = next_airing.get("airingAt")
            if airing_at:
                from datetime import datetime
                try:
                    dt = datetime.fromtimestamp(airing_at)
                    next_episode_str = f"Episode {next_ep} on {dt.strftime('%A, %d %B %Y at %H:%M')}"
                except (ValueError, OSError):
                    next_episode_str = f"Episode {next_ep}"
            else:
                next_episode_str = f"Episode {next_ep}"
        else:
            next_episode_str = "N/A"

        # User list status
        media_list_entry = media.get("mediaListEntry")
        if media_list_entry:
            user_status = media_list_entry.get("status", "NOT_ON_LIST")
            user_progress = f"Episode {media_list_entry.get('progress', 0)}"
        else:
            user_status = "NOT_ON_LIST"
            user_progress = "0"

        description = media.get("description", "No description available.")
        description = strip_markdown(description)

        # Print sections matching media_info.py structure exactly
        rows = [
            ("Score", score_str),
            ("Favorites", favourites),
            ("Popularity", popularity),
            ("Status", status),
        ]

        print_rule(SEPARATOR_COLOR)
        for key, value in rows:
            print_table_row(key, value, HEADER_COLOR, 15, term_width - 20)

        rows = [
            ("Episodes", str(episodes)),
            ("Duration", duration_str),
            ("Next Episode", next_episode_str),
        ]

        print_rule(SEPARATOR_COLOR)
        for key, value in rows:
            print_table_row(key, value, HEADER_COLOR, 15, term_width - 20)

        rows = [
            ("Genres", genres),
            ("Format", format_type),
        ]

        print_rule(SEPARATOR_COLOR)
        for key, value in rows:
            print_table_row(key, value, HEADER_COLOR, 15, term_width - 20)

        rows = [
            ("List Status", user_status),
            ("Progress", user_progress),
        ]

        print_rule(SEPARATOR_COLOR)
        for key, value in rows:
            print_table_row(key, value, HEADER_COLOR, 15, term_width - 20)

        rows = [
            ("Start Date", start_date),
            ("End Date", end_date),
        ]

        print_rule(SEPARATOR_COLOR)
        for key, value in rows:
            print_table_row(key, value, HEADER_COLOR, 15, term_width - 20)

        rows = [
            ("Studios", studios),
            ("Producers", producers),
        ]

        print_rule(SEPARATOR_COLOR)
        for key, value in rows:
            print_table_row(key, value, HEADER_COLOR, 15, term_width - 20)

        rows = [
            ("Synonyms", synonyms),
        ]

        print_rule(SEPARATOR_COLOR)
        for key, value in rows:
            print_table_row(key, value, HEADER_COLOR, 15, term_width - 20)

        rows = [
            ("Tags", tags),
        ]

        print_rule(SEPARATOR_COLOR)
        for key, value in rows:
            print_table_row(key, value, HEADER_COLOR, 15, term_width - 20)

        print_rule(SEPARATOR_COLOR)
        print(wrap_text(description, term_width))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Preview Error: {e}", file=sys.stderr)
