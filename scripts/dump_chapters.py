"""Bulk-examine embedded episode chapters WITHOUT playing them.

Resolves each episode's stream the same way ani-browse does (primary provider,
then the nyaa torrent fallback) and reads the container's chapter list with
``ffprobe`` - so you can survey the real OP/ED chapter-title variations across
many episodes at once and tune the skip matcher against actual data.

Direct HTTP streams (allanime, etc.) are probed straight with ffprobe. Torrent
(magnet) streams need a short-lived ``webtorrent`` HTTP server, enabled with
``--torrents`` (webtorrent-cli must be installed).

Examples:
    uv run python scripts/dump_chapters.py "Frieren" --episodes 1-12
    uv run python scripts/dump_chapters.py "Frieren" --episodes 1-4 --source nyaa --torrents
    uv run python scripts/dump_chapters.py "Spy x Family" --episodes 1,3,5 --json out.json

Output: a per-episode chapter listing, then a summary table of every distinct
chapter title with its count and how the current matcher would classify it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from collections import Counter
from typing import Dict, List, Optional, Tuple

# --- pure helpers (unit-tested in tests/scripts/test_dump_chapters.py) -------


def parse_episode_arg(spec: str) -> List[str]:
    """Parse "1-12" / "1,3,5" / "1-3,7,10-12" into an episode-number list."""
    episodes: List[str] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            episodes.extend(str(n) for n in range(int(lo), int(hi) + 1))
        else:
            episodes.append(str(int(part)))
    return episodes


def parse_ffprobe_chapters(ffprobe_json: str) -> List[Tuple[float, float, str]]:
    """Extract ``(start, end, title)`` tuples from ffprobe -show_chapters JSON."""
    try:
        data = json.loads(ffprobe_json)
    except (json.JSONDecodeError, TypeError):
        return []
    result: List[Tuple[float, float, str]] = []
    for ch in data.get("chapters", []) or []:
        try:
            start = float(ch.get("start_time", -1))
            end = float(ch.get("end_time", -1))
        except (TypeError, ValueError):
            start = end = -1.0
        title = (ch.get("tags") or {}).get("title", "") or ""
        result.append((start, end, title.strip()))
    return result


def classify_title(title: str) -> Optional[str]:
    """How the ani_skip Lua matcher currently classifies a chapter title."""
    if not title:
        return None
    t = title.lower()
    if (
        "opening" in t
        or "ncop" in t
        or "intro" in t
        or t == "op"
        or t.startswith("op ")
        or t.startswith("op-")
    ):
        return "op"
    if (
        "ending" in t
        or "credit" in t
        or "outro" in t
        or "nced" in t
        or t == "ed"
        or t.startswith("ed ")
        or t.startswith("ed-")
    ):
        return "ed"
    return None


def summarize(rows: List[Tuple[str, float, float, str]]) -> List[Tuple[str, int, Optional[str]]]:
    """Distinct titles -> (title, count, classification), most common first."""
    counts: Counter = Counter(title for _ep, _s, _e, title in rows if title)
    return [
        (title, count, classify_title(title))
        for title, count in counts.most_common()
    ]


# --- resolution + ffprobe (network / subprocess) -----------------------------


def _resolve_stream(provider, config, title: str, episode: str, source: str):
    """Return (url, headers) for one episode, or (None, None)."""
    from viu_media.cli.interactive.menu.media._source_fallback import nyaa_servers
    from viu_media.libs.provider.anime.params import EpisodeStreamsParams

    servers = []
    if source in ("auto", "provider"):
        try:
            it = provider.episode_streams(
                EpisodeStreamsParams(
                    anime_id=title,
                    query=title,
                    episode=episode,
                    translation_type=config.stream.translation_type,
                )
            )
            servers = list(it) if it else []
        except Exception as e:  # noqa: BLE001
            print(f"  ep {episode}: provider error: {e}", file=sys.stderr)
    if not servers and source in ("auto", "nyaa"):
        servers = nyaa_servers(
            title, episode, config.stream.translation_type, config.stream.quality
        )
    if not servers:
        return None, None
    server = servers[0]
    return server.links[0].link, dict(server.headers or {})


def _ffprobe(url: str, headers: Dict[str, str], ffprobe: str) -> str:
    cmd = [ffprobe, "-v", "quiet", "-print_format", "json", "-show_chapters"]
    if headers:
        header_blob = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
        cmd += ["-headers", header_blob]
    cmd += ["-i", url]
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        ).stdout
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"  ffprobe failed: {e}", file=sys.stderr)
        return ""


def _ffprobe_torrent(magnet: str, ffprobe: str, webtorrent: str, port: int) -> str:
    """Serve a magnet over HTTP with webtorrent just long enough to ffprobe it.

    webtorrent only starts its HTTP server in streaming mode (no ``download``
    subcommand) and serves at ``/webtorrent/<infohash>/<file>`` - not ``/0`` -
    so we read the actual "Server running at:" URL from its output.
    """
    import tempfile

    # Redirect webtorrent output to a file and poll it - node block-buffers a
    # pipe (and its \r progress line never yields a newline to a reader thread),
    # but a file redirect flushes the "Server running at:" line promptly. Run via
    # the shell so a Windows .cmd wrapper + redirection propagate to the node
    # child (a bare Popen of the .cmd doesn't pass the handle through cleanly).
    log = tempfile.NamedTemporaryFile(
        mode="w+", suffix=".wt.log", delete=False, encoding="utf-8"
    )
    log.close()
    cmd = f'"{webtorrent}" "{magnet}" --port {port} > "{log.name}" 2>&1'
    proc = subprocess.Popen(cmd, shell=True)
    try:
        server_url = None
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and server_url is None:
            with open(log.name, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if "Server running at:" in line:
                        server_url = line.split("Server running at:", 1)[1].strip()
                        break
            time.sleep(1)
        if not server_url:
            print("  webtorrent server did not start in time", file=sys.stderr)
            return ""
        # Retry: the container header (with chapters) needs a few pieces first.
        out = ""
        for _ in range(20):
            out = _ffprobe(server_url, {}, ffprobe)
            if '"chapters"' in out:
                return out
            time.sleep(2)
        return out
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        try:
            import os

            os.unlink(log.name)
        except OSError:
            pass


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("title", help="Anime title as the provider knows it")
    parser.add_argument("--episodes", default="1-12", help='e.g. "1-12" or "1,3,5"')
    parser.add_argument("--provider", default=None, help="override the provider")
    parser.add_argument(
        "--source", choices=["auto", "provider", "nyaa"], default="auto"
    )
    parser.add_argument("--translation", default=None, help="sub/dub")
    parser.add_argument("--quality", default=None)
    parser.add_argument(
        "--torrents", action="store_true", help="probe magnets via webtorrent"
    )
    parser.add_argument("--port", type=int, default=8998)
    parser.add_argument("--json", dest="json_out", default=None)
    args = parser.parse_args(argv)

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        print("ffprobe not found in PATH (install ffmpeg).", file=sys.stderr)
        return 2
    webtorrent = shutil.which("webtorrent")

    from viu_media.core.config import AppConfig
    from viu_media.core.patterns import TORRENT_REGEX
    from viu_media.libs.provider.anime.provider import ProviderName, create_provider

    config = AppConfig()
    if args.provider:
        config.general.provider = ProviderName(args.provider)
    if args.translation:
        config.stream.translation_type = args.translation  # type: ignore[assignment]
    if args.quality:
        config.stream.quality = args.quality  # type: ignore[assignment]
    provider = create_provider(config.general.provider)

    rows: List[Tuple[str, float, float, str]] = []
    for episode in parse_episode_arg(args.episodes):
        url, headers = _resolve_stream(
            provider, config, args.title, episode, args.source
        )
        if not url:
            print(f"ep {episode}: no stream resolved")
            continue
        if TORRENT_REGEX.search(url):
            if not (args.torrents and webtorrent):
                print(f"ep {episode}: magnet (skipped; pass --torrents + webtorrent)")
                continue
            out = _ffprobe_torrent(url, ffprobe, webtorrent, args.port)
        else:
            out = _ffprobe(url, headers, ffprobe)
        chapters = parse_ffprobe_chapters(out)
        if not chapters:
            print(f"ep {episode}: no chapters")
            continue
        print(f"ep {episode}: {len(chapters)} chapters")
        for start, end, title in chapters:
            kind = classify_title(title)
            tag = f" -> {kind}" if kind else ""
            print(f"    {start:8.1f}-{end:8.1f}  {title!r}{tag}")
            rows.append((episode, start, end, title))

    print("\n=== title summary (most common first) ===")
    for title, count, kind in summarize(rows):
        tag = f"  [{kind}]" if kind else "  [unmatched]"
        print(f"  {count:3d}x  {title!r}{tag}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {"episode": ep, "start": s, "end": e, "title": t}
                    for ep, s, e, t in rows
                ],
                f,
                indent=2,
            )
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
