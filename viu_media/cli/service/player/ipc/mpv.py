"""
IPC-based MPV Player implementation for Ani-Browse.
This provides advanced features like episode navigation, quality switching, and auto-next.
"""

import json
import logging
import os
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Dict, List, Literal, Optional

from .....core.config.model import StreamConfig
from .....core.exceptions import AniBrowseError
from .....core.utils import formatter
from .....libs.media_api.types import MediaItem
from .....libs.player.base import BasePlayer
from .....libs.player.params import PlayerParams
from .....libs.player.types import PlayerResult
from .....libs.provider.anime.base import BaseAnimeProvider
from .....libs.provider.anime.params import EpisodeStreamsParams
from .....core.patterns import TORRENT_REGEX
from .....libs.provider.anime.types import Anime, Server
from ....service.registry.models import DownloadStatus
from ...registry import MediaRegistryService
from .base import BaseIPCPlayer

logger = logging.getLogger(__name__)


def _numeric_next(episode: str) -> Optional[str]:
    """The next whole episode number as a string, or None if not numeric.

    Used to advance past the provider's last known episode when a newer one has
    aired and is only available via the nyaa fallback.
    """
    try:
        return str(int(float(episode)) + 1)
    except (TypeError, ValueError):
        return None


class MPVIPCError(AniBrowseError):
    """Exception raised for MPV IPC communication errors."""

    pass


class MPVIPCClient:
    """Client for communicating with MPV via IPC socket with a dedicated reader thread."""

    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.socket: Optional[Any] = None
        self._request_id_counter = 0
        self._lock = threading.Lock()

        self._reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._message_buffer = b""

        self._event_queue: Queue = Queue()
        self._response_dict: Dict[int, Any] = {}
        self._response_events: Dict[int, threading.Event] = {}

    @staticmethod
    def _is_windows_named_pipe(path: str) -> bool:
        return path.startswith("\\\\.\\pipe\\")

    @staticmethod
    def _supports_unix_sockets() -> bool:
        return hasattr(socket, "AF_UNIX")

    @staticmethod
    def _open_windows_named_pipe(path: str):
        # MPV's JSON IPC on Windows uses named pipes like: \\.\pipe\mpvpipe
        # Opening the pipe as a binary file supports read/write.
        f = open(path, "r+b", buffering=0)

        class _PipeConn:
            def __init__(self, fileobj):
                self._f = fileobj

            def recv(self, n: int) -> bytes:
                return self._f.read(n)

            def sendall(self, data: bytes) -> None:
                self._f.write(data)
                self._f.flush()

            def close(self) -> None:
                self._f.close()

        return _PipeConn(f)

    def connect(self, timeout: float = 5.0) -> None:
        """Connect to MPV IPC socket and start the reader thread."""

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if self._supports_unix_sockets() and not self._is_windows_named_pipe(
                    self.socket_path
                ):
                    self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) # type: ignore (type error on Windows but this code path won't be used there)
                    self.socket.connect(self.socket_path)
                else:
                    if os.name != "nt" or not self._is_windows_named_pipe(self.socket_path):
                        raise MPVIPCError(
                            "MPV IPC requires Unix domain sockets (AF_UNIX) or a Windows named pipe path "
                            "like \\\\.\\pipe\\mpvpipe. Got: "
                            f"{self.socket_path}"
                        )
                    self.socket = self._open_windows_named_pipe(self.socket_path)
                logger.info(f"Connected to MPV IPC socket at {self.socket_path}")
                self._start_reader_thread()
                return
            except (ConnectionRefusedError, FileNotFoundError, OSError):
                time.sleep(0.2)
        raise MPVIPCError(f"Failed to connect to MPV IPC socket at {self.socket_path}")

    def disconnect(self) -> None:
        """Disconnect from MPV IPC socket and stop the reader thread."""
        self._stop_event.set()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2.0)
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def _start_reader_thread(self):
        """Starts the background thread to read messages from the socket."""
        self._stop_event.clear()
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

    def _read_loop(self):
        """Continuously reads data from the socket and processes messages."""
        while not self._stop_event.is_set():
            try:
                if not self.socket:
                    break
                # A blocking recv is efficient as the thread will sleep until data is available.
                data = self.socket.recv(4096)
                if not data:
                    logger.info("MPV IPC socket closed.")
                    # Put a special event to signal the main loop that MPV has shut down.
                    self._event_queue.put({"event": "shutdown"})
                    break

                self._message_buffer += data
                self._process_buffer()
            except (socket.timeout, BlockingIOError):
                continue
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"Error in IPC read loop: {e}")
                break

    def _process_buffer(self):
        """Processes the internal buffer to extract full JSON messages."""
        while b"\n" in self._message_buffer:
            message_data, self._message_buffer = self._message_buffer.split(b"\n", 1)
            if not message_data:
                continue

            try:
                message = json.loads(message_data.decode("utf-8"))
                # Responses have a 'request_id' and 'error' field, events do not.
                if "request_id" in message and "error" in message:
                    req_id = message["request_id"]
                    with self._lock:
                        self._response_dict[req_id] = message
                        if req_id in self._response_events:
                            self._response_events[req_id].set()
                else:  # It's an event
                    self._event_queue.put(message)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(
                    f"Failed to decode MPV message: {message_data[:100]}... Error: {e}"
                )

    def get_event(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        """Retrieves an event from the event queue."""
        try:
            return self._event_queue.get(block=block, timeout=timeout)
        except Empty:
            return None

    def send_command(self, command: List[Any], timeout: float = 5.0) -> Dict[str, Any]:
        """Send a command and wait for a specific response."""
        if not self.socket:
            raise MPVIPCError("Not connected to MPV")

        with self._lock:
            self._request_id_counter += 1
            request_id = self._request_id_counter

            request = {"command": command, "request_id": request_id}

            response_event = threading.Event()
            self._response_events[request_id] = response_event

        try:
            message = json.dumps(request) + "\n"
            self.socket.sendall(message.encode("utf-8"))

            if response_event.wait(timeout=timeout):
                with self._lock:
                    return self._response_dict.pop(request_id, {})
            else:
                raise MPVIPCError(f"Timeout waiting for response to command: {command}")
        finally:
            with self._lock:
                self._response_events.pop(request_id, None)


@dataclass
class PlayerState:
    """Represents the dynamic state of the media player."""

    stream_config: StreamConfig
    query: str
    episode: str
    # Keyed by the provider's raw server name (e.g. "gogoanime", "Luf-mp4", or
    # "nyaa:SubsPlease (12 seeders)") - NOT the ProviderServer enum. Forcing names
    # into the enum raised ValueError for every non-enum name (all nyaa names and
    # many provider names), which silently killed in-player next/auto-next. This
    # mirrors how the servers menu keys its own map.
    servers: Dict[str, Server] = field(default_factory=dict)
    server_name: Optional[str] = None
    media_item: Optional[MediaItem] = None
    stop_time_secs: float = 0
    total_time_secs: float = 0

    @property
    def episode_title(self) -> str:
        if self.media_item:
            if (
                self.media_item.streaming_episodes
                and self.episode in self.media_item.streaming_episodes
            ):
                return (
                    self.media_item.streaming_episodes[self.episode].title
                    or f"Episode {self.episode}"
                )
            return f"{self.media_item.title.english or self.media_item.title.romaji} - Episode {self.episode}"
        if server := self.server:
            return server.episode_title or f"Episode {self.episode}"
        return f"Episode {self.episode}"

    @property
    def server(self) -> Optional[Server]:
        if not self.servers:
            logger.warning("Attempt to access server when servers are unavailable.")
            return None

        # stream_config.server is a ProviderServer enum; compare its string value
        # against the raw server-name keys. "TOP" (the default) never matches a
        # real name, so we fall through to the first server - same as the menu.
        preferred = str(
            getattr(self.stream_config.server, "value", self.stream_config.server)
        )
        if preferred in self.servers:
            server_name = preferred
        elif self.server_name and self.server_name in self.servers:
            server_name = self.server_name
        else:
            server_name = next(iter(self.servers))
            self.server_name = server_name

        return self.servers.get(server_name)

    @property
    def stream_url(self) -> Optional[str]:
        if server := self.server:
            # Simple quality selection for now
            return server.links[0].link
        return None

    @property
    def stream_subtitles(self) -> List[str]:
        return [sub.url for sub in self.server.subtitles] if self.server else []

    @property
    def stream_headers(self) -> Dict[str, str]:
        return self.server.headers if self.server else {}

    @property
    def stop_time(self) -> Optional[str]:
        return (
            formatter.format_time(self.stop_time_secs)
            if self.stop_time_secs > 0
            else None
        )

    @property
    def total_time(self) -> Optional[str]:
        return (
            formatter.format_time(self.total_time_secs)
            if self.total_time_secs > 0
            else None
        )

    def reset(self):
        self.stop_time_secs = 0
        self.total_time_secs = 0


class MpvIPCPlayer(BaseIPCPlayer):
    """MPV Player implementation using IPC for advanced features."""

    stream_config: StreamConfig
    mpv_process: Optional[subprocess.Popen]
    ipc_client: MPVIPCClient
    player_state: PlayerState
    player_fetching: bool = False
    player_first_run: bool = True
    event_handlers: Dict[str, List[Callable]] = {}
    property_observers: Dict[str, List[Callable]] = {}
    key_bindings: Dict[str, Callable] = {}
    message_handlers: Dict[str, Callable] = {}
    provider: Optional[BaseAnimeProvider] = None
    anime: Optional[Anime] = None
    media_item: Optional[MediaItem] = None

    registry: Optional[MediaRegistryService] = None

    def __init__(
        self,
        stream_config: StreamConfig,
        ipc_client: Optional["MPVIPCClient"] = None,
    ):
        super().__init__(stream_config)
        self.socket_path: Optional[str] = None
        # An injected client (tests) bypasses _start_mpv_process/_connect_ipc so
        # the player can be exercised with no real mpv subprocess or socket.
        self._injected_ipc_client = ipc_client
        # None until a real mpv is launched; the injected-client path leaves it
        # unset, so the poll()/terminate() sites must tolerate None.
        self.mpv_process = None
        self._fetch_thread: Optional[threading.Thread] = None
        self._fetch_result_queue: Queue = Queue()
        # Prefetched servers for neighbour episodes, keyed by episode number, so
        # next/previous/auto-next fire instantly. Populated by background workers
        # during playback; consumed (popped) by the fetch task.
        self._prefetch: Dict[str, Dict[str, Server]] = {}
        self._prefetch_lock = threading.Lock()
        self._prefetch_inflight: set = set()
        self._prefetch_threads: List[threading.Thread] = []
        # Opening/ending skip intervals for the current episode (from AniSkip).
        self._skips: List[Any] = []
        self._skips_applied: set = set()
        self._skip_fetch_started = False
        self._skip_thread: Optional[threading.Thread] = None

    def play(
        self,
        player: BasePlayer,
        player_params: PlayerParams,
        provider: Optional[BaseAnimeProvider] = None,
        anime: Optional[Anime] = None,
        registry: Optional[MediaRegistryService] = None,
        media_item: Optional[MediaItem] = None,
    ) -> PlayerResult:
        self.provider = provider
        self.anime = anime
        self.media_item = media_item
        self.registry = registry
        self.player_state = PlayerState(
            self.stream_config,
            player_params.query,
            player_params.episode,
            media_item=media_item,
        )

        return self._play_with_ipc(player, player_params)

    def _play_with_ipc(self, player: BasePlayer, params: PlayerParams) -> PlayerResult:
        """Play media using MPV IPC."""
        try:
            if self._injected_ipc_client is not None:
                # Test seam: a client was supplied, so skip spawning mpv and
                # connecting a real socket.
                self.ipc_client = self._injected_ipc_client
            else:
                self._start_mpv_process(player, params)
                self._connect_ipc()
            self._setup_event_handling()
            self._setup_key_bindings()
            self._setup_message_handlers()
            self._wait_for_playback()

            return PlayerResult(
                episode=self.player_state.episode,
                stop_time=self.player_state.stop_time,
                total_time=self.player_state.total_time,
            )
        except MPVIPCError as e:
            logger.warning(
                f"IPC connection failed: {e}. Falling back to non-IPC playback."
            )
            if (
                input("Failed to play with IPC. Continue without it? (Y/n): ").lower()
                != "n"
            ):
                return player.play(params)
            else:
                return PlayerResult(
                    episode=params.episode, stop_time=None, total_time=None
                )
        finally:
            self._cleanup()

    def _start_mpv_process(self, player: BasePlayer, params: PlayerParams) -> None:
        """Start MPV process with IPC enabled."""
        if hasattr(socket, "AF_UNIX"):
            temp_dir = Path(tempfile.gettempdir())
            self.socket_path = str(temp_dir / f"mpv_ipc_{time.time()}.sock")
        else:
            # Windows MPV IPC uses named pipes.
            self.socket_path = f"\\\\.\\pipe\\mpv_ipc_{int(time.time() * 1000)}"
        self.mpv_process = player.play_with_ipc(params, self.socket_path)
        time.sleep(1.0)

    def _connect_ipc(self):
        if not self.socket_path:
            raise MPVIPCError("Socket path not set")
        self.ipc_client = MPVIPCClient(self.socket_path)
        self.ipc_client.connect()

    def _setup_event_handling(self):
        if not self.ipc_client:
            return
        self.ipc_client.send_command(["request_log_messages", "info"])
        self.ipc_client.send_command(["observe_property", 1, "time-pos"])
        self.ipc_client.send_command(["observe_property", 2, "duration"])
        self.ipc_client.send_command(["observe_property", 3, "percent-pos"])
        self.ipc_client.send_command(["observe_property", 4, "filename"])

    def _bind_key(self, key, command, description):
        if not self.ipc_client:
            return
        try:
            response = self.ipc_client.send_command(["keybind", key, command])
            if response.get("error") != "success":
                logger.warning(f"Failed to bind key {key}: {response.get('error')}")
                self._show_text(f"Error binding '{description}' key", duration=3000)
        except Exception as e:
            logger.error(f"Exception binding key {key}: {e}")

    def _setup_key_bindings(self):
        key_bindings = {
            "shift+n": ("script-message viu-next-episode", "Next Episode"),
            "shift+p": (
                "script-message viu-previous-episode",
                "Previous Episode",
            ),
            "shift+a": (
                "script-message viu-toggle-auto-next",
                "Toggle Auto-Next",
            ),
            "shift+o": (
                "script-message viu-toggle-opening-skip",
                "Toggle Opening Skip",
            ),
            "shift+e": (
                "script-message viu-toggle-ending-skip",
                "Toggle Ending Skip",
            ),
            "shift+t": (
                "script-message viu-toggle-translation",
                "Toggle Translation",
            ),
            "shift+r": ("script-message viu-reload-episode", "Reload Episode"),
        }
        for key, (command, description) in key_bindings.items():
            self._bind_key(key, command, description)

        self._show_text(
            "Ani-Browse IPC: Shift+N=Next, Shift+P=Prev, Shift+R=Reload, "
            "Shift+O=Skip OP, Shift+E=Skip ED, Shift+A=Auto-Next",
            4000,
        )

    def _setup_message_handlers(self):
        self.message_handlers.update(
            {
                "viu-next-episode": self._next_episode,
                "viu-previous-episode": self._previous_episode,
                "viu-reload-episode": self._reload_episode,
                "viu-toggle-auto-next": self._toggle_auto_next,
                "viu-toggle-opening-skip": self._toggle_opening_skip,
                "viu-toggle-ending-skip": self._toggle_ending_skip,
                "viu-toggle-translation": self._toggle_translation_type,
                "select-episode": self._handle_select_episode,
                "select-server": self._handle_select_server,
                "select-quality": self._handle_select_quality,
            }
        )

    def _wait_for_playback(self):
        """A non-blocking loop that checks for MPV process exit and processes events."""
        if not self.ipc_client:
            return

        should_stop = False
        try:
            while not should_stop:
                if self.mpv_process and self.mpv_process.poll() is not None:
                    logger.info("MPV process has exited.")
                    break

                try:
                    while True:
                        message = self.ipc_client.get_event(block=False)
                        if message is None:
                            break

                        if message.get("event") == "shutdown":
                            should_stop = True
                            break

                        self._handle_mpv_message(message)

                    try:
                        fetch_result = self._fetch_result_queue.get(block=False)
                        self._handle_fetch_result(fetch_result)
                    except Empty:
                        pass
                except MPVIPCError as e:
                    # A transient IPC hiccup during event/fetch handling (mpv
                    # briefly unresponsive around eof->idle) must NOT tear down
                    # the whole IPC player. Log and keep looping; the eof-driven
                    # auto-next and the fetch queue continue to work.
                    logger.debug("Transient IPC error in playback loop: %s", e)

                if should_stop:
                    break
                time.sleep(0.05)

        except KeyboardInterrupt:
            logger.info("Playback interrupted by user")

    def _handle_mpv_message(self, message: Dict[str, Any]):
        event = message.get("event")
        if event == "property-change":
            self._handle_property_change(message)
        elif event == "client-message":
            self._handle_client_message(message)
        elif event == "file-loaded":
            time.sleep(0.1)
            self._configure_player()
            # Warm the neighbour cache for the episode now playing (incl. the
            # very first one, which is loaded at launch, not via the fetch task).
            self._start_prefetch()
        elif event == "end-file":
            # Only a genuine end-of-file counts. "stop" fires when we replace the
            # file for next/reload, "quit" on user exit, "error" on failure - none
            # of those should auto-advance. mpv runs with --idle=yes, so at eof it
            # goes idle (window stays) instead of quitting, letting us load next.
            if message.get("reason") == "eof" and not self.player_fetching:
                self._auto_next_episode()
        elif event:
            logger.debug(f"MPV event: {event}")

    def _handle_property_change(self, message: Dict[str, Any]):
        name = message.get("name")
        data = message.get("data")
        if name == "time-pos" and isinstance(data, (int, float)):
            self.player_state.stop_time_secs = data
            self._maybe_skip(float(data))
        elif name == "duration" and isinstance(data, (int, float)):
            self.player_state.total_time_secs = data
            # Duration is known right after a file loads; use it to fetch the
            # opening/ending intervals for this episode (once, best-effort).
            if data > 0 and not self._skip_fetch_started:
                self._start_skip_fetch(float(data))
        # NOTE: auto-next is intentionally NOT driven by percent-pos here. It fires
        # only on the real end of the video (the mpv "end-file"/eof event), so any
        # post-ending scene still plays and ending-skip never advances by itself.

    def _handle_client_message(self, message: Dict[str, Any]):
        args = message.get("args", [])
        if args:
            handler_name = args[0]
            handler_args = args[1:]
            handler = self.message_handlers.get(handler_name)
            if handler:
                try:
                    handler(*handler_args)
                except Exception as e:
                    logger.error(f"Error in message handler for '{handler_name}': {e}")

    def _cleanup(self):
        if self.ipc_client:
            self.ipc_client.disconnect()
        if self.mpv_process:
            try:
                self.mpv_process.terminate()
                self.mpv_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.mpv_process.kill()
        if (
            self.socket_path
            and not self.socket_path.startswith("\\\\.\\pipe\\")
            and Path(self.socket_path).exists()
        ):
            Path(self.socket_path).unlink(missing_ok=True)

    def _get_episode(
        self,
        episode_type: Literal["next", "previous", "reload", "custom"],
        ep_no: Optional[str] = None,
    ):
        if self.player_fetching:
            self._show_text("Player is busy. Please wait.")
            return

        self.player_fetching = True
        self._show_text(f"Fetching {episode_type} episode...")

        self._fetch_thread = threading.Thread(
            target=self._fetch_episode_task, args=(episode_type, ep_no), daemon=True
        )
        self._fetch_thread.start()

    def _fetch_episode_task(
        self,
        episode_type: Literal["next", "previous", "reload", "custom"],
        ep_no: Optional[str] = None,
    ):
        """This function runs in a background thread to fetch episode streams."""
        try:
            if self.anime and self.provider:
                available_episodes = getattr(
                    self.anime.episodes, self.stream_config.translation_type
                )
                if not available_episodes:
                    raise ValueError(
                        f"No {self.stream_config.translation_type} episodes available."
                    )

                # The current episode may not be in the provider's list (e.g. one
                # merged in from nyaa), so resolve the index defensively.
                current_index = (
                    available_episodes.index(self.player_state.episode)
                    if self.player_state.episode in available_episodes
                    else None
                )

                if episode_type == "next":
                    if (
                        current_index is not None
                        and current_index < len(available_episodes) - 1
                    ):
                        target_episode = available_episodes[current_index + 1]
                    else:
                        # Past the provider's last episode - a newer episode may
                        # have aired and only exist on nyaa (lagging simulcast).
                        # Compute the numeric next; the nyaa fallback below serves it.
                        target_episode = _numeric_next(self.player_state.episode)
                        if target_episode is None:
                            raise ValueError("Already at the last episode.")
                elif episode_type == "previous":
                    if current_index is None or current_index <= 0:
                        raise ValueError("Already at first episode")
                    target_episode = available_episodes[current_index - 1]
                elif episode_type == "reload":
                    target_episode = self.player_state.episode
                elif episode_type == "custom":
                    if not ep_no:
                        raise ValueError("No episode specified")
                    target_episode = ep_no
                else:
                    return

                # Use a prefetched result if one is ready (instant next/prev);
                # otherwise resolve now (primary provider, then nyaa fallback).
                with self._prefetch_lock:
                    servers = self._prefetch.pop(target_episode, None)
                if not servers:
                    servers = self._resolve_servers(target_episode)
                if not servers:
                    raise ValueError(f"No streams found for episode {target_episode}")

                self._fetch_result_queue.put(
                    {
                        "type": "success",
                        "target_episode": target_episode,
                        "servers": servers,
                    }
                )
            elif self.registry and self.media_item:
                record = self.registry.get_media_record(self.media_item.id)
                if not record or not record.media_episodes:
                    logger.warning("No downloaded episodes found for this anime.")
                    return

                downloaded_episodes = {
                    ep.episode_number: ep.file_path
                    for ep in record.media_episodes
                    if ep.download_status == DownloadStatus.COMPLETED
                    and ep.file_path
                    and ep.file_path.exists()
                }
                available_episodes = list(sorted(downloaded_episodes.keys(), key=float))
                current_index = available_episodes.index(self.player_state.episode)

                if episode_type == "next":
                    if current_index >= len(available_episodes) - 1:
                        raise ValueError("Already at the last episode.")
                    target_episode = available_episodes[current_index + 1]
                elif episode_type == "previous":
                    if current_index <= 0:
                        raise ValueError("Already at first episode")
                    target_episode = available_episodes[current_index - 1]
                elif episode_type == "reload":
                    target_episode = self.player_state.episode
                elif episode_type == "custom":
                    if not ep_no or ep_no not in available_episodes:
                        raise ValueError(
                            f"Invalid episode. Available: {', '.join(available_episodes)}"
                        )
                    target_episode = ep_no
                else:
                    return
                file_path = downloaded_episodes[target_episode]

                # Marshal the load back to the main loop via the queue (exactly
                # like the streaming path) instead of writing IPC from this fetch
                # thread - keeps all mpv writes on one thread and lets a transient
                # timeout be handled uniformly by _handle_fetch_result.
                self._fetch_result_queue.put(
                    {
                        "type": "success",
                        "target_episode": target_episode,
                        "file_path": str(file_path),
                    }
                )

        except Exception as e:
            logger.error(f"Episode fetch task failed: {e}")
            self._fetch_result_queue.put({"type": "error", "message": str(e)})

    def _handle_fetch_result(self, result: Dict[str, Any]):
        """Handles the result from the background fetch thread in the main thread."""
        self.player_fetching = False
        if result["type"] != "success":
            self._show_text(f"Error: {result['message']}")
            return

        self.player_state.episode = result["target_episode"]
        self.player_state.reset()
        self._reset_skips()
        if "servers" in result:
            # Streamed episode: load via the resolved server's stream URL.
            self.player_state.servers = result["servers"]
            self._show_text(f"Fetched {self.player_state.episode_title}")
            self._load_current_stream()
            # Warm the cache for the new episode's neighbours.
            self._start_prefetch()
        else:
            # Locally downloaded episode: load the file path directly.
            file_path = result["file_path"]
            self._show_text(f"Fetched {file_path}")
            if self.ipc_client:
                try:
                    self.ipc_client.send_command(["loadfile", file_path])
                except MPVIPCError as e:
                    logger.warning(
                        "Failed to load downloaded file (transient IPC error): %s", e
                    )

    def _next_episode(self):
        self._get_episode("next")

    def _previous_episode(self):
        self._get_episode("previous")

    def _reload_episode(self):
        self._get_episode("reload")

    def _auto_next_episode(self):
        if self.stream_config.auto_next:
            self._next_episode()

    def _nyaa_servers_for(self, episode: str) -> Dict[str, Server]:
        """nyaa torrent servers for one episode as a server map, or {} if none.

        Mirrors the interactive servers menu's fallback so in-player next/auto-next
        can advance to episodes the primary source lags on. Best-effort. No IPC
        writes here - this runs from fetch/prefetch background threads.
        """
        if type(self.provider).__name__ == "Nyaa":
            return {}
        if not getattr(self.stream_config, "nyaa_fallback", True):
            return {}
        try:
            from ....interactive.menu.media._source_fallback import nyaa_servers

            servers = nyaa_servers(
                self.player_state.query,
                episode,
                self.stream_config.translation_type,
                self.stream_config.quality,
            )
            return {s.name: s for s in servers}
        except Exception as e:  # noqa: BLE001 - fallback must never raise
            logger.debug("in-player nyaa fallback failed for ep %s: %s", episode, e)
            return {}

    # ---- stream resolution + prefetch --------------------------------------
    def _resolve_servers(self, target_episode: str) -> Dict[str, Server]:
        """Server map for one episode: primary provider, then nyaa. {} if none.

        Runs from background threads only (fetch task / prefetch workers) - no IPC.
        """
        if not (self.anime and self.provider):
            return {}
        stream_params = EpisodeStreamsParams(
            anime_id=self.anime.id,
            query=self.player_state.query,
            episode=target_episode,
            translation_type=self.stream_config.translation_type,
            quality=self.stream_config.quality,
        )
        try:
            episode_streams = list(self.provider.episode_streams(stream_params) or [])
        except Exception as e:  # noqa: BLE001 - provider hiccup -> try nyaa
            logger.debug("primary stream fetch failed for ep %s: %s", target_episode, e)
            episode_streams = []
        servers = {s.name: s for s in episode_streams}
        if not servers:
            servers = self._nyaa_servers_for(target_episode)
        return servers

    def _neighbour_episodes(self) -> List[str]:
        """The next and previous episode numbers to prefetch for the current one."""
        if not self.anime:
            return []
        available = (
            getattr(self.anime.episodes, self.stream_config.translation_type, []) or []
        )
        current = self.player_state.episode
        targets: List[str] = []
        if current in available:
            idx = available.index(current)
            if idx < len(available) - 1:
                targets.append(available[idx + 1])
            else:
                nxt = _numeric_next(current)
                if nxt:
                    targets.append(nxt)
            if idx > 0:
                targets.append(available[idx - 1])
        else:
            nxt = _numeric_next(current)
            if nxt:
                targets.append(nxt)
        return targets

    def _start_prefetch(self):
        """Kick off background fetches for the current episode's neighbours.

        Only for streaming (not the local/registry path). Deduplicates against
        both the ready cache and in-flight fetches; results land in ``_prefetch``
        for the fetch task to consume instantly.
        """
        if not (self.anime and self.provider):
            return
        for target in self._neighbour_episodes():
            with self._prefetch_lock:
                if target in self._prefetch or target in self._prefetch_inflight:
                    continue
                self._prefetch_inflight.add(target)
            thread = threading.Thread(
                target=self._prefetch_worker, args=(target,), daemon=True
            )
            self._prefetch_threads.append(thread)
            thread.start()

    def _prefetch_worker(self, target: str):
        try:
            servers = self._resolve_servers(target)
            if servers:
                with self._prefetch_lock:
                    self._prefetch[target] = servers
                logger.debug(
                    "prefetched %d server(s) for episode %s", len(servers), target
                )
        except Exception as e:  # noqa: BLE001 - prefetch must never raise
            logger.debug("prefetch failed for episode %s: %s", target, e)
        finally:
            with self._prefetch_lock:
                self._prefetch_inflight.discard(target)

    # ---- opening/ending skip ------------------------------------------------
    def _reset_skips(self):
        """Forget skip intervals; call whenever a new episode is loaded."""
        self._skips = []
        self._skips_applied = set()
        self._skip_fetch_started = False

    def _start_skip_fetch(self, episode_length: float):
        """Fetch AniSkip intervals for the current episode in the background."""
        self._skip_fetch_started = True
        if not (self.stream_config.opening_skip or self.stream_config.ending_skip):
            return  # nothing to skip; don't hit the network
        mal_id = self.media_item.id_mal if self.media_item else None
        if not mal_id:
            return
        episode = self.player_state.episode

        def _task():
            from ..aniskip import fetch_skip_times

            intervals = fetch_skip_times(mal_id, episode, episode_length)
            # Only adopt results if we're still on the same episode.
            if intervals and self.player_state.episode == episode:
                self._skips = intervals
                logger.info(
                    "aniskip: %d interval(s) for ep %s", len(intervals), episode
                )

        self._skip_thread = threading.Thread(target=_task, daemon=True)
        self._skip_thread.start()

    def _maybe_skip(self, position: float):
        """Seek past the opening/ending if enabled and we've entered one."""
        if not self._skips:
            return
        for interval in self._skips:
            if id(interval) in self._skips_applied:
                continue
            enabled = (
                self.stream_config.opening_skip
                if interval.kind == "op"
                else self.stream_config.ending_skip
            )
            if not enabled or not interval.contains(position):
                continue
            self._skips_applied.add(id(interval))
            # Seek to the end of the segment. If that lands at the true end of the
            # video (ending is the final segment), mpv fires end-file/eof next,
            # which is what triggers auto-next - the skip itself never does.
            try:
                self.ipc_client.send_command(["seek", interval.end, "absolute"])
            except MPVIPCError as e:
                # A missed skip is cosmetic; never let it collapse the player.
                logger.debug("skip seek failed (ignored): %s", e)
                return
            self._show_text(
                "Skipping opening" if interval.kind == "op" else "Skipping ending"
            )
            return

    def _load_current_stream(self):
        if not (self.ipc_client and self.player_state):
            return
        url = self.player_state.stream_url
        if not url:
            return
        if TORRENT_REGEX.search(url):
            # mpv can't load a magnet directly - torrents stream via a separate
            # `webtorrent --mpv` process, which we can't inject into the running
            # IPC player. Tell the user instead of silently sitting idle.
            logger.warning("In-player advance to a torrent is unsupported: %s", url)
            self._show_text(
                "Next episode is a torrent - open it from the menu to stream it.",
                4000,
            )
            return
        try:
            # Re-apply this server's HTTP headers before loading; the next
            # episode's host may differ from the one mpv launched with.
            headers = self.player_state.stream_headers
            if headers:
                self.ipc_client.send_command(
                    [
                        "set_property",
                        "http-header-fields",
                        [f"{k}: {v}" for k, v in headers.items()],
                    ]
                )
            self.ipc_client.send_command(["loadfile", url])
        except MPVIPCError as e:
            # Loading the next stream is the one write we don't want to lose,
            # but a transient timeout here still must not collapse the player.
            # The eof/next machinery can retry; log loudly and continue.
            logger.warning("Failed to load stream (transient IPC error): %s", e)

    def _show_text(self, text: str, duration: int = 2000):
        if self.ipc_client:
            try:
                self.ipc_client.send_command(["show-text", text, str(duration)])
            except MPVIPCError as e:
                # A cosmetic on-screen toast must NEVER kill playback. During the
                # eof->idle transition mpv can be briefly unresponsive and this
                # blocking write times out; swallow it (this was the root cause of
                # auto-next silently collapsing to the non-IPC fallback).
                logger.debug("show-text failed (ignored): %s", e)

    def _configure_player(self):
        if not self.ipc_client or self.player_first_run:
            self.player_first_run = False
            return

        try:
            self.ipc_client.send_command(["seek", 0, "absolute"])
            self.ipc_client.send_command(
                ["set_property", "title", self.player_state.episode_title]
            )
        except MPVIPCError as e:
            logger.debug("configure_player IPC write failed (ignored): %s", e)
        self._add_episode_subtitles()

    def _add_episode_subtitles(self):
        if not self.ipc_client or not self.player_state.stream_subtitles:
            return

        time.sleep(0.5)
        for i, sub_url in enumerate(self.player_state.stream_subtitles):
            flag = "select" if i == 0 else "auto"
            try:
                self.ipc_client.send_command(["sub-add", sub_url, flag])
            except MPVIPCError as e:
                logger.debug("sub-add failed (ignored): %s", e)

    def _toggle_auto_next(self):
        self.stream_config.auto_next = not self.stream_config.auto_next
        self._show_text(
            f"Auto-next {'enabled' if self.stream_config.auto_next else 'disabled'}"
        )

    def _toggle_opening_skip(self):
        self.stream_config.opening_skip = not self.stream_config.opening_skip
        state = "enabled" if self.stream_config.opening_skip else "disabled"
        self._show_text(f"Opening skip {state}")
        # Turned on mid-episode with no intervals yet? Fetch them now.
        if self.stream_config.opening_skip and not self._skips:
            self._skip_fetch_started = False
            if self.player_state.total_time_secs > 0:
                self._start_skip_fetch(self.player_state.total_time_secs)

    def _toggle_ending_skip(self):
        self.stream_config.ending_skip = not self.stream_config.ending_skip
        state = "enabled" if self.stream_config.ending_skip else "disabled"
        self._show_text(f"Ending skip {state}")
        if self.stream_config.ending_skip and not self._skips:
            self._skip_fetch_started = False
            if self.player_state.total_time_secs > 0:
                self._start_skip_fetch(self.player_state.total_time_secs)

    def _toggle_translation_type(self):
        new_type = "sub" if self.stream_config.translation_type == "dub" else "dub"
        self._show_text(f"Switching to {new_type}...")
        self.stream_config.translation_type = new_type
        self._reload_episode()

    def _handle_select_episode(self, episode: Optional[str] = None):
        if episode:
            self._get_episode("custom", episode)

    def _handle_select_server(self, server: Optional[str] = None):
        if not server or not self.player_state:
            return
        if server in self.player_state.servers:
            self.player_state.server_name = server
            self._reload_episode()
        else:
            available_servers = ", ".join(self.player_state.servers.keys())
            self._show_text(
                f"Server '{server}' not available. Available: {available_servers}"
            )

    def _handle_select_quality(self, quality: Optional[str] = None):
        self._show_text("Quality switching is not yet implemented.")
