"""
MPV player integration for Ani-Browse.

This module provides the MpvPlayer class, which implements the BasePlayer interface for the MPV media player.
"""

import atexit
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import replace
from pathlib import Path
from urllib.parse import quote, unquote

from ....core.config import MpvConfig
from ....core.constants import APP_CACHE_DIR, SCRIPTS_DIR
from ....core.exceptions import AniBrowseError
from ....core.patterns import TORRENT_REGEX, YOUTUBE_REGEX
from ....core.utils import detect
from ..base import BasePlayer
from ..params import PlayerParams
from ..types import PlayerResult

logger = logging.getLogger(__name__)

ANI_SKIP_LUA = SCRIPTS_DIR / "mpv" / "ani_skip.lua"

MPV_AV_TIME_PATTERN = re.compile(r"[AV]+: ([0-9:]+) / ([0-9:]+) \(([0-9]+)%\)")

#: Cache of fetched ``.torrent`` metadata files, keyed by info hash, so a batch
#: torrent's metadata is fetched once per session rather than on every replay.
TORRENT_CACHE_DIR = APP_CACHE_DIR / "torrents"
#: Where webtorrent writes stream data; wiped before each play so disk usage
#: stays bounded to roughly one episode.
TORRENT_STREAM_DIR = TORRENT_CACHE_DIR / "stream"

#: Marker the nyaa provider appends to a *batch* magnet (``&x.aniep=7``) so we
#: stream only that episode's file out of a season pack. Mirrors
#: ``nyaa/provider.py::BATCH_EP_PARAM``.
_BATCH_EP_RE = re.compile(r"[?&]x\.aniep=(\d+(?:\.\d+)?)")
#: Standard magnet "exact source" param: HTTPS URL of the .torrent file (nyaa
#: serves these), which beats a DHT metadata fetch by an order of magnitude.
_XS_RE = re.compile(r"[?&]xs=([^&\s]+)")
#: Info hash inside a magnet URI.
_INFOHASH_RE = re.compile(r"btih:([A-Za-z0-9]{32,40})", re.IGNORECASE)
#: Episode number inside a fansub file name, e.g.
#: "[SubsPlease] Sousou no Frieren - 07v2 (1080p) [ABCD].mkv".
_FILE_EP_RE = re.compile(r"\s-\s0*(\d+(?:\.\d+)?)(?:v\d+)?(?=\s|$|\(|\[|\.)")

#: Seconds to allow the P2P downloadmeta fallback (DHT can be slow).
_META_TIMEOUT = 90
#: Seconds to wait for the local webtorrent stream server to serve the file.
_SERVER_READY_TIMEOUT = 45


def _batch_target_episode(url: str) -> "str | None":
    """The episode number a batch magnet asks us to stream, else None."""
    m = _BATCH_EP_RE.search(url or "")
    return m.group(1) if m else None


def _xs_url(magnet: str) -> "str | None":
    """The .torrent HTTP(S) URL carried in the magnet's xs param, else None."""
    m = _XS_RE.search(magnet or "")
    if not m:
        return None
    url = unquote(m.group(1))
    return url if url.startswith("http") else None


def _magnet_info_hash(magnet: str) -> "str | None":
    m = _INFOHASH_RE.search(magnet or "")
    return m.group(1).lower() if m else None


def _stream_file_url(port: int, info_hash: str, file_path: str) -> str:
    """webtorrent's HTTP stream URL for one file of a torrent.

    The server route is ``/webtorrent/<infoHash>/<file.path>`` with the path
    joined by ``/`` (verified live; the metadata's Windows-style ``\\`` join
    404s) and URL-encoded per segment.
    """
    rel = quote(file_path.replace("\\", "/"), safe="/")
    return f"http://localhost:{port}/webtorrent/{info_hash}/{rel}"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_http_ok(url: str, timeout: float) -> bool:
    """Poll ``url`` with HEAD until 2xx or the deadline passes."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=3) as r:
                if 200 <= r.status < 300:
                    return True
        except OSError:
            pass
        time.sleep(0.3)
    return False


def _valid_torrent_file(path: Path) -> bool:
    """Cheap sanity check: bencoded torrents start with a ``d`` dict marker."""
    try:
        with open(path, "rb") as f:
            return f.read(1) == b"d"
    except OSError:
        return False


#: Driver that serves a torrent over HTTP using the webtorrent LIBRARY.
#: webtorrent-cli drops the magnet's so= (select-only) param - a season batch
#: would download every episode - while the library honors it (verified live).
ANI_STREAM_MJS = SCRIPTS_DIR / "node" / "ani_stream.mjs"


def _find_node_cmdjs(webtorrent_cli: str) -> "list[str] | None":
    """[node, cmd.js] to run webtorrent-cli directly.

    We spawn node itself (not the npm ``.cmd`` shim) so terminating/timing-out
    the process actually stops it - killing the shim on Windows leaves the
    node child orphaned.
    """
    node = shutil.which("node")
    cmdjs = (
        Path(webtorrent_cli).resolve().parent
        / "node_modules"
        / "webtorrent-cli"
        / "bin"
        / "cmd.js"
    )
    if node and cmdjs.exists():
        return [node, str(cmdjs)]
    return None


def _find_stream_server_cmd(webtorrent_cli: str) -> "list[str] | None":
    """[node, ani_stream.mjs, <webtorrent index file:// URL>] or None.

    The driver imports the webtorrent library out of the globally-installed
    webtorrent-cli package, so no extra npm install is needed.
    """
    node = shutil.which("node")
    npm_root = Path(webtorrent_cli).resolve().parent / "node_modules"
    candidates = [
        npm_root / "webtorrent-cli" / "node_modules" / "webtorrent" / "index.js",
        npm_root / "webtorrent" / "index.js",  # hoisted layout
    ]
    if node and ANI_STREAM_MJS.exists():
        for wt_index in candidates:
            if wt_index.exists():
                return [node, str(ANI_STREAM_MJS), wt_index.as_uri()]
    return None


#: The app-session-wide torrent stream server (see ani_stream.mjs). Spawned on
#: the first torrent play and reused for every one after: consecutive episodes
#: skip node startup, metadata exchange and - within a season batch - swarm
#: bootstrap, which is where most of the per-episode delay went.
_stream_session: "dict | None" = None


def _shutdown_stream_session() -> None:
    global _stream_session
    session = _stream_session
    _stream_session = None
    if session is None:
        return
    proc = session["proc"]
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except (OSError, subprocess.SubprocessError):
        try:
            proc.kill()
        except OSError:
            pass


def _get_stream_session(webtorrent_cli: str) -> "dict | None":
    """The live session server, spawning it on first use (None if impossible)."""
    global _stream_session
    session = _stream_session
    if session is not None and session["proc"].poll() is None:
        return session
    _stream_session = None

    server_cmd = _find_stream_server_cmd(webtorrent_cli)
    if server_cmd is None:
        return None
    shutil.rmtree(TORRENT_STREAM_DIR, ignore_errors=True)
    try:
        TORRENT_STREAM_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    port = _free_port()
    try:
        proc = subprocess.Popen(
            [*server_cmd, str(TORRENT_STREAM_DIR), str(port)],
            env=detect.get_clean_env(),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError as e:
        logger.warning("could not start torrent stream server: %s", e)
        return None
    _stream_session = {"proc": proc, "port": port}
    atexit.register(_shutdown_stream_session)
    return _stream_session


#: Guards session stdin: PLAY comes from the main thread, WARM from prefetch
#: threads, and interleaved partial writes would corrupt the line protocol.
_session_write_lock = threading.Lock()


def _session_send(session: dict, line: str) -> bool:
    try:
        with _session_write_lock:
            session["proc"].stdin.write(line + "\n")
            session["proc"].stdin.flush()
        return True
    except (OSError, ValueError):
        return False


def _torrent_file_index(files: list, magnet: str) -> "int | None":
    """Which file of the torrent a magnet refers to (marker/single/largest)."""
    target_ep = _batch_target_episode(magnet)
    if target_ep is not None:
        return _pick_batch_file_index(files, target_ep)
    if len(files) == 1:
        return 0
    if not files:
        return None
    return max(range(len(files)), key=lambda i: files[i].get("length") or 0)


def warm_torrent_stream(magnet: str) -> None:
    """Best-effort head-prefetch of a torrent episode for instant auto-next.

    Called from neighbour-prefetch threads while an episode is playing. A
    strict no-op unless the session server is ALREADY running (never spawns
    node speculatively) and never falls back to a slow P2P metadata fetch.
    """
    session = _stream_session
    if session is None or session["proc"].poll() is not None:
        return
    if not magnet.startswith("magnet:"):
        return
    cli = shutil.which("webtorrent")
    if not cli:
        return
    try:
        tpath = _ensure_torrent_file(magnet, cli, allow_p2p=False)
        if tpath is None:
            return
        files = _torrent_files(cli, str(tpath))
        index = _torrent_file_index(files, magnet)
        if index is None:
            return
        # so= keeps the moment between add and the driver's deselect from
        # kicking off a whole-pack download.
        _session_send(session, f"WARM {index} {magnet}&so={index}")
        logger.info("[ani-timing] torrent prewarm sent for file %s", index)
    except Exception:
        logger.debug("torrent prewarm failed", exc_info=True)


def _file_episode(name: str) -> "str | None":
    m = _FILE_EP_RE.search(name or "")
    return m.group(1) if m else None


def _pick_batch_file_index(files: list, target_ep: str) -> "int | None":
    """Index of the file whose name is the requested episode, else None.

    ``files`` is webtorrent's ``info`` JSON file list (array order == the index
    ``--select`` expects). Matching is by parsed episode number, not position,
    so specials / reordered packs still resolve correctly.
    """
    try:
        want = float(target_ep)
    except (TypeError, ValueError):
        return None
    for i, f in enumerate(files):
        ep = _file_episode(f.get("name") or f.get("path") or "")
        if ep is not None and float(ep) == want:
            return i
    return None


def _torrent_files(webtorrent_cli: str, torrent_path: str) -> list:
    """File list from a local ``.torrent`` via ``webtorrent info`` (JSON)."""
    try:
        out = subprocess.run(
            [webtorrent_cli, "info", torrent_path],
            env=detect.get_clean_env(),
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("webtorrent info failed for %s: %s", torrent_path, e)
        return []
    start = out.find("{")
    if start < 0:
        return []
    try:
        return json.loads(out[start:]).get("files", []) or []
    except (ValueError, AttributeError) as e:
        logger.debug("could not parse webtorrent info JSON: %s", e)
        return []


def _ensure_torrent_file(
    magnet: str, webtorrent_cli: str, allow_p2p: bool = True
) -> "Path | None":
    """Local ``.torrent`` for a magnet: cache, else xs HTTP GET, else P2P.

    A corrupt cached file (e.g. a fetch killed mid-write) is deleted and
    re-fetched rather than poisoning every future attempt. The HTTP path via
    the magnet's ``xs`` URL is sub-second; the ``downloadmeta`` DHT fallback
    can take up to ``_META_TIMEOUT`` and announces itself on the terminal.
    """
    info_hash = _magnet_info_hash(magnet)
    if not info_hash:
        return None
    try:
        TORRENT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    path = TORRENT_CACHE_DIR / f"{info_hash}.torrent"
    if path.exists():
        if _valid_torrent_file(path):
            return path
        try:
            path.unlink()
        except OSError:
            return None

    xs = _xs_url(magnet)
    if xs:
        try:
            import httpx  # lazy: keep app launch fast

            r = httpx.get(xs, timeout=15, follow_redirects=True)
            r.raise_for_status()
            if r.content[:1] == b"d":
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(r.content)
                os.replace(tmp, path)
                return path
            logger.debug("xs URL %s did not return a torrent file", xs)
        except Exception as e:  # httpx errors, OSError
            logger.debug("xs fetch failed for %s: %s", xs, e)

    if not allow_p2p:  # background prewarm never blocks on a DHT fetch
        return None

    print("[torrent] fetching metadata from peers (can take a minute)...")
    # Prefer spawning node directly: timing out the npm .cmd shim on Windows
    # orphans the node child, which would keep hunting for peers forever.
    runner = _find_node_cmdjs(webtorrent_cli) or [webtorrent_cli]
    try:
        subprocess.run(
            [*runner, "downloadmeta", magnet, "--out", str(TORRENT_CACHE_DIR)],
            env=detect.get_clean_env(),
            capture_output=True,
            text=True,
            timeout=_META_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("webtorrent downloadmeta failed: %s", e)
        return None
    return path if _valid_torrent_file(path) else None


#: mpv exit codes emitted by ani_skip.lua's Shift+N / Shift+P bindings.
NEXT_EPISODE_EXIT_CODE = 100
PREVIOUS_EPISODE_EXIT_CODE = 101


def _ani_lua_args(params: PlayerParams) -> list[str]:
    """mpv args that load ani_skip.lua for in-player nav keys + op/ed skipping.

    Always loaded on the clean path (the nav keys need it); the skip options are
    passed through from ``params``. Returns ``[]`` only if the script is missing.
    """
    if not ANI_SKIP_LUA.exists():
        return []
    op = params.skip_op or (-1.0, -1.0)
    ed = params.skip_ed or (-1.0, -1.0)
    opts = (
        "ani_skip-nav_keys=yes,"
        f"ani_skip-op_enabled={'yes' if params.skip_op_enabled else 'no'},"
        f"ani_skip-ed_enabled={'yes' if params.skip_ed_enabled else 'no'},"
        f"ani_skip-op_start={op[0]},ani_skip-op_end={op[1]},"
        f"ani_skip-ed_start={ed[0]},ani_skip-ed_end={ed[1]}"
    )
    # In-player server switch: the Lua only binds Ctrl+S when given a servers
    # JSON path. Paths never contain commas (which separate script-opts), so this
    # is safe to append verbatim.
    if params.servers_json:
        opts += f",ani_skip-servers_json={params.servers_json}"
    # AniSkip intervals delivered via file (fetched off the launch path).
    if params.skip_json:
        opts += f",ani_skip-skip_json={params.skip_json}"
    return [f"--script={ANI_SKIP_LUA}", f"--script-opts={opts}"]


def _run_mpv_teed(args: list[str], env: dict) -> tuple[str, int | None]:
    """Run mpv, streaming its ``[viu-...]`` diagnostic lines to the terminal
    live while capturing the full output for post-playback parsing.

    Replaces a plain ``subprocess.run(capture_output=True)``: that hid mpv's
    output until after exit, so the opening/ending detection log was only ever
    visible in app.log. Here we still capture everything (for
    ``parse_playback_time`` and ``_log_mpv_chapters``) but echo the skip/chapter
    diagnostic lines as they arrive, so detection is watchable in action.

    stderr is merged into stdout so the single stream carries both mpv's log
    messages (where the Lua's ``print`` lands) and the status line.
    """
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )
    captured: list[str] = []
    assert proc.stdout is not None
    for chunk in iter(proc.stdout.readline, ""):
        captured.append(chunk)
        # mpv rewrites its status line in place with \r; split on it too so our
        # \n-terminated diagnostic lines are not hidden behind the status line.
        for piece in chunk.replace("\r", "\n").split("\n"):
            if "[ani-skip]" in piece or "[ani-chapters]" in piece:
                try:
                    sys.stderr.write(piece.strip() + "\n")
                    sys.stderr.flush()
                except (UnicodeError, OSError):
                    # Never let a terminal encoding/pipe hiccup kill playback;
                    # the line is still captured for app.log regardless.
                    pass
    proc.stdout.close()
    returncode = proc.wait()
    return "".join(captured), returncode


def _action_for_exit_code(code: int | None) -> str | None:
    if code == NEXT_EPISODE_EXIT_CODE:
        return "next"
    if code == PREVIOUS_EPISODE_EXIT_CODE:
        return "previous"
    return None


_CHAPTER_LINE = re.compile(
    r"\[ani-chapters\] #(\d+) t=(-?[0-9.]+) title=(.*)"
)


def parse_mpv_chapters(
    stdout: str | None, stderr: str | None
) -> list[tuple[float, str]]:
    """Extract the ``(time, title)`` chapters that ani_skip.lua logged.

    The embedded chapter list comes from the media container the source served;
    capturing the real titles lets us see the OP/ED naming variations and tune
    the Lua's chapter matcher against actual data.
    """
    chapters: list[tuple[float, str]] = []
    for stream in (stdout, stderr):
        if not stream:
            continue
        for line in stream.splitlines():
            m = _CHAPTER_LINE.search(line)
            if m:
                chapters.append((float(m.group(2)), m.group(3).strip()))
    return chapters


def _log_mpv_chapters(stdout: str | None, stderr: str | None) -> None:
    chapters = parse_mpv_chapters(stdout, stderr)
    if chapters:
        logger.info(
            "mpv chapters: %s",
            ", ".join(f"{t:.0f}s={title!r}" for t, title in chapters),
        )
    # Also surface any skips the ani_skip Lua performed, for diagnosing coverage.
    for stream in (stdout, stderr):
        if not stream:
            continue
        for line in stream.splitlines():
            i = line.find("[ani-skip]")
            if i != -1:
                logger.info("ani_skip %s", line[i + len("[ani-skip]"):].strip())


def parse_playback_time(
    stdout: str | None, stderr: str | None
) -> tuple[str | None, str | None]:
    """Extract the final ``(stop_time, total_time)`` from captured mpv output.

    mpv rewrites its ``AV: 00:10 / 24:00 (41%)`` status line in place using
    carriage returns, and depending on build/OS emits it on stdout or stderr, so
    we scan BOTH and split on \\r and \\n. Scanning in reverse yields the LAST
    reported position - i.e. where playback actually stopped - which is what auto
    -next needs to tell "watched to the end" from "quit early". Returns
    ``(None, None)`` if no status line was captured.
    """
    combined = f"{stdout or ''}\n{stderr or ''}"
    for line in reversed(re.split(r"[\r\n]+", combined)):
        match = MPV_AV_TIME_PATTERN.search(line.strip())
        if match:
            return match.group(1), match.group(2)
    return None, None


class MpvPlayer(BasePlayer):
    """
    MPV player implementation for Ani-Browse.

    Provides playback functionality using the MPV media player, supporting desktop, mobile, torrents, and syncplay.
    """

    def __init__(self, config: MpvConfig):
        """
        Initialize the MpvPlayer with the given MPV configuration.

        Args:
            config: MpvConfig object containing MPV-specific settings.
        """
        self.config = config
        self.executable = shutil.which("mpv")

    def play(self, params):
        """
        Play the given media using MPV, handling desktop, mobile, torrent, and syncplay scenarios.

        Args:
            params: PlayerParams object containing playback parameters.

        Returns:
            PlayerResult: Information about the playback session.
        """
        if TORRENT_REGEX.match(params.url) and detect.is_running_in_termux():
            raise AniBrowseError("Unable to play torrents on termux")
        elif params.syncplay and detect.is_running_in_termux():
            raise AniBrowseError("Unable to play with syncplay on termux")
        elif detect.is_running_in_termux():
            return self._play_on_mobile(params)
        else:
            return self._play_on_desktop(params)

    def _play_on_mobile(self, params) -> PlayerResult:
        """
        Play media on a mobile device using Android intents.

        Args:
            params: PlayerParams object containing playback parameters.

        Returns:
            PlayerResult: Information about the playback session.
        """
        if YOUTUBE_REGEX.match(params.url):
            args = [
                "nohup",
                "am",
                "start",
                "--user",
                "0",
                "-a",
                "android.intent.action.VIEW",
                "-d",
                params.url,
                "-n",
                "com.google.android.youtube/.UrlActivity",
            ]
        else:
            args = [
                "nohup",
                "am",
                "start",
                "--user",
                "0",
                "-a",
                "android.intent.action.VIEW",
                "-d",
                params.url,
                "-n",
                "is.xyz.mpv/.MPVActivity",
            ]

        subprocess.run(args,env=detect.get_clean_env())

        return PlayerResult(params.episode)

    def _play_on_desktop(self, params) -> PlayerResult:
        """
        Play media on a desktop environment using MPV.

        Args:
            params: PlayerParams object containing playback parameters.

        Returns:
            PlayerResult: Information about the playback session.
        """
        if not self.executable:
            raise AniBrowseError("MPV executable not found in PATH.")

        if TORRENT_REGEX.search(params.url):
            return self._stream_on_desktop_with_webtorrent_cli(params)
        elif params.syncplay:
            return self._stream_on_desktop_with_syncplay(params)
        else:
            return self._stream_on_desktop_with_subprocess(params)

    def _stream_on_desktop_with_subprocess(self, params: PlayerParams) -> PlayerResult:
        """
        Stream media using MPV via subprocess, capturing playback times.

        Args:
            params: PlayerParams object containing playback parameters.

        Returns:
            PlayerResult: Information about the playback session, including stop and total time.
        """
        mpv_args = [self.executable, params.url]

        mpv_args.extend(self._create_mpv_cli_options(params))
        # Load the ani_skip Lua for in-player next/prev keys and opening/ending
        # skip (the IPC path does its own thing, so this is clean-path only).
        mpv_args.extend(_ani_lua_args(params))

        pre_args = self.config.pre_args.split(",") if self.config.pre_args else []

        output, returncode = _run_mpv_teed(
            pre_args + mpv_args, detect.get_clean_env()
        )
        stop_time, total_time = parse_playback_time(output, None)
        # Record the episode's embedded chapters (from ani_skip.lua) so real
        # OP/ED title variations land in the log for tuning the skip matcher.
        _log_mpv_chapters(output, None)
        return PlayerResult(
            episode=params.episode,
            total_time=total_time,
            stop_time=stop_time,
            action=_action_for_exit_code(returncode),
        )

    def play_with_ipc(self, params: PlayerParams, socket_path: str) -> subprocess.Popen:
        """
        Stream using MPV with IPC (Inter-Process Communication) for enhanced features.

        Args:
            params: PlayerParams object containing playback parameters.
            socket_path: Path to the IPC socket for player control.

        Returns:
            subprocess.Popen: The running MPV process.
        """
        mpv_args = [
            self.executable,
            f"--input-ipc-server={socket_path}",
            "--idle=yes",
            "--force-window=yes",
            params.url,
        ]

        # Add custom MPV arguments
        mpv_args.extend(self._create_mpv_cli_options(params))

        # Add pre-args if configured
        pre_args = self.config.pre_args.split(",") if self.config.pre_args else []

        logger.info(f"Starting MPV with IPC socket: {socket_path}")

        process = subprocess.Popen(pre_args + mpv_args,env=detect.get_clean_env())

        return process

    def _stream_on_desktop_with_webtorrent_cli(
        self, params: PlayerParams
    ) -> PlayerResult:
        """
        Stream torrent media using the webtorrent CLI and MPV.

        Args:
            params: PlayerParams object containing playback parameters.

        Returns:
            PlayerResult: Information about the playback session.
        """
        WEBTORRENT_CLI = shutil.which("webtorrent")
        if not WEBTORRENT_CLI:
            raise AniBrowseError("Please Install webtorrent cli inorder to stream torrents")

        target_ep = _batch_target_episode(params.url)

        # Resolve the torrent's file list so we know WHICH file to play: the
        # episode the batch marker names, or the largest file otherwise
        # (matching webtorrent's own default choice).
        meta: "tuple[Path, list, int] | None" = None
        if params.url.startswith("magnet:"):
            tpath = _ensure_torrent_file(params.url, WEBTORRENT_CLI)
            if tpath is not None:
                files = _torrent_files(WEBTORRENT_CLI, str(tpath))
                if not files:
                    # Metadata parsed to nothing: treat the cache entry as bad.
                    try:
                        tpath.unlink()
                    except OSError:
                        pass
                else:
                    index = _torrent_file_index(files, params.url)
                    if index is not None:
                        meta = (tpath, files, index)

        if target_ep is not None and meta is None:
            # Never guess: playing the pack's default file would be a WRONG
            # episode. Surface the failure and let the user pick another server.
            msg = (
                f"could not identify episode {target_ep} inside the batch "
                "torrent; not playing to avoid a wrong episode - try another "
                "server"
            )
            print(f"[torrent] {msg}")
            logger.warning(msg)
            return PlayerResult(params.episode)

        if meta is not None:
            result = self._stream_via_local_server(WEBTORRENT_CLI, params, meta)
            if result is not None:
                return result

        # Legacy path: webtorrent owns mpv (no lua keys / skip / auto-next).
        # Still selects the correct file for a batch.
        args = [WEBTORRENT_CLI, params.url, "--mpv"]
        if meta is not None and len(meta[1]) > 1:
            args += ["--select", str(meta[2])]
        if mpv_args := self._create_mpv_cli_options(params):
            args.append("--player-args")
            args.extend(mpv_args)

        subprocess.run(args,env=detect.get_clean_env())
        return PlayerResult(params.episode)

    def _stream_via_local_server(
        self, webtorrent_cli: str, params: PlayerParams, meta: "tuple[Path, list, int]"
    ) -> "PlayerResult | None":
        """Serve the torrent locally and play it with OUR mpv.

        The ani_stream.mjs driver (webtorrent LIBRARY, not the cli - the cli
        drops ``so=``) runs as a bare stream server, and mpv is launched
        through the normal subprocess path, so everything the clean path
        provides - ani_skip lua (OP/ED skip, Shift+N/P, Ctrl+S), playback time
        capture, watch history, auto-next - works for torrents too. For a
        multi-file pack the magnet gets ``&so=<index>`` so webtorrent downloads
        ONLY the wanted episode instead of the whole season. Returns None to
        let the caller fall back to the legacy webtorrent-owned-mpv path.
        """
        tpath, files, index = meta
        info_hash = _magnet_info_hash(params.url)
        file_path = files[index].get("path") or files[index].get("name") or ""
        if info_hash is None or not file_path:
            return None

        # so= keeps the brief window between metadata arrival and our explicit
        # PLAY selection from starting a whole-pack download.
        magnet = params.url
        if len(files) > 1:
            magnet += f"&so={index}"

        # Two attempts: a fresh spawn can lose its port to a bind race
        # (EADDRINUSE kills the driver), in which case retry on a new port.
        stream_url = None
        for attempt in (1, 2):
            session = _get_stream_session(webtorrent_cli)
            if session is None:
                return None
            stream_url = _stream_file_url(session["port"], info_hash, file_path)
            if not _session_send(session, f"PLAY {index} {magnet}"):
                _shutdown_stream_session()
                continue
            print("[torrent] starting stream...")
            if _wait_http_ok(stream_url, timeout=_SERVER_READY_TIMEOUT):
                break
            logger.warning(
                "torrent stream server not ready (attempt %s)", attempt
            )
            if session["proc"].poll() is not None:
                _shutdown_stream_session()  # died (e.g. port race): respawn
                continue
            return None  # server alive but torrent stalled: legacy fallback
        else:
            return None
        # The session stays alive after mpv exits: the next episode reuses the
        # warm client/swarm, and atexit shuts it down with the app.
        return self._stream_on_desktop_with_subprocess(
            replace(params, url=stream_url)
        )

    def _stream_on_desktop_with_syncplay(self, params: PlayerParams) -> PlayerResult:
        """
        Stream media using Syncplay for synchronized playback with friends.

        Args:
            params: PlayerParams object containing playback parameters.

        Returns:
            PlayerResult: Information about the playback session.
        """
        SYNCPLAY_EXECUTABLE = shutil.which("syncplay")
        if not SYNCPLAY_EXECUTABLE:
            raise AniBrowseError(
                "Please install syncplay to be able to stream with your friends"
            )
        args = [SYNCPLAY_EXECUTABLE, params.url]
        if mpv_args := self._create_mpv_cli_options(params):
            args.append("--")
            args.extend(mpv_args)
        subprocess.run(args,env=detect.get_clean_env())

        return PlayerResult(params.episode)

    def _create_mpv_cli_options(self, params: PlayerParams) -> list[str]:
        """
        Create a list of MPV CLI options based on playback parameters.

        Args:
            params: PlayerParams object containing playback parameters.

        Returns:
            list[str]: List of MPV CLI arguments.
        """
        mpv_args = []
        if params.headers:
            header_str = ",".join([f"{k}:{v}" for k, v in params.headers.items()])
            mpv_args.append(f"--http-header-fields={header_str}")

        if params.subtitles:
            for sub in params.subtitles:
                mpv_args.append(f"--sub-file={sub}")

        if params.start_time:
            mpv_args.append(f"--start={params.start_time}")

        if params.title:
            mpv_args.append(f"--title={params.title}")

        if self.config.args:
            mpv_args.extend(self.config.args.split(","))
        return mpv_args


if __name__ == "__main__":
    from ....core.constants import APP_ASCII_ART

    print(APP_ASCII_ART)
    url = input("Enter the url you would like to stream: ")
    mpv = MpvPlayer(MpvConfig())
    player_result = mpv.play(PlayerParams(episode="", query="", url=url, title=""))
    print(player_result)
