"""
IPC-based MPV Player implementation for FastAnime.
This provides advanced features like episode navigation, quality switching, and auto-next.

Usage:
    To enable IPC player, set `use_ipc = true` in the MPV config section.

    Key bindings:
    - Shift+N: Next episode
    - Shift+P: Previous episode
    - Shift+R: Reload current episode
    - Shift+T: Toggle translation type (sub/dub)
    - Shift+A: Toggle auto-next (placeholder)

    Script messages (can be sent via MPV console with 'script-message'):
    - select-episode <episode_number>: Jump to specific episode
    - select-server <server_name>: Switch server for current episode
    - select-quality <quality>: Switch quality (360, 480, 720, 1080)

Requirements:
    - MPV executable in PATH
    - Unix domain socket support (Linux/macOS)
"""

import json
import logging
import random
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Union

from ....core.config import MpvConfig
from ....core.exceptions import FastAnimeError
from ....core.utils import detect
from ....libs.provider.anime.base import BaseAnimeProvider
from ....libs.provider.anime.params import EpisodeStreamsParams
from ....libs.provider.anime.types import Server
from ..base import BasePlayer
from ..params import PlayerParams
from ..types import PlayerResult

logger = logging.getLogger(__name__)


def format_time(duration_in_secs: float) -> str:
    """Format duration in seconds to HH:MM:SS format."""
    h = int(duration_in_secs // 3600)
    m = int((duration_in_secs % 3600) // 60)
    s = int(duration_in_secs % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class MPVIPCError(FastAnimeError):
    """Exception raised for MPV IPC communication errors."""

    pass


class MPVIPCClient:
    """Client for communicating with MPV via IPC socket."""

    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.socket: Optional[socket.socket] = None
        self._request_id = 0

    def connect(self, timeout: float = 5.0) -> None:
        """Connect to MPV IPC socket."""
        start_time = time.time()
        last_exception = None

        while time.time() - start_time < timeout:
            try:
                self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.socket.settimeout(2.0)  # Set socket timeout
                self.socket.connect(self.socket_path)
                logger.info(f"Connected to MPV IPC socket at {self.socket_path}")
                return
            except (ConnectionRefusedError, FileNotFoundError, OSError) as e:
                last_exception = e
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                    self.socket = None
                time.sleep(0.2)  # Wait a bit longer between attempts
                continue

        error_msg = f"Failed to connect to MPV IPC socket at {self.socket_path}"
        if last_exception:
            error_msg += f": {last_exception}"
        raise MPVIPCError(error_msg)

    def disconnect(self) -> None:
        """Disconnect from MPV IPC socket."""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

    def send_command(
        self, command: List[Union[str, int, float, bool, None]]
    ) -> Dict[str, Any]:
        """Send a command to MPV and return the response."""
        if not self.socket:
            raise MPVIPCError("Not connected to MPV")

        self._request_id += 1
        request = {"command": command, "request_id": self._request_id}

        message = json.dumps(request) + "\n"
        try:
            self.socket.send(message.encode())

            # Read response - MPV sends one JSON object per line
            response_data = b""
            while True:
                chunk = self.socket.recv(1024)
                if not chunk:
                    break
                response_data += chunk
                if b"\n" in response_data:
                    break

            response_text = response_data.decode().strip()
            if response_text:
                # Handle multiple JSON objects on separate lines
                lines = response_text.split("\n")
                for line in lines:
                    line = line.strip()
                    if line:
                        try:
                            response = json.loads(line)
                            # Return the response that matches our request ID
                            if response.get("request_id") == self._request_id:
                                return response
                        except json.JSONDecodeError:
                            continue
                # If no matching response found, return the first valid JSON
                for line in lines:
                    line = line.strip()
                    if line:
                        try:
                            return json.loads(line)
                        except json.JSONDecodeError:
                            continue
            return {}
        except Exception as e:
            raise MPVIPCError(f"Failed to send command: {e}")

    def get_property(self, property_name: str) -> Union[str, bool, int, float, None]:
        """Get a property value from MPV."""
        response = self.send_command(["get_property", property_name])
        if response.get("error") == "success":
            return response.get("data")
        return None

    def set_property(
        self, property_name: str, value: Union[str, bool, int, float, None]
    ) -> bool:
        """Set a property value in MPV."""
        response = self.send_command(["set_property", property_name, value])
        return response.get("error") == "success"

    def observe_property(self, property_name: str, enable: bool = True) -> bool:
        """Observe a property for changes."""
        command = "observe_property" if enable else "unobserve_property"
        response = self.send_command([command, self._request_id, property_name])
        return response.get("error") == "success"


class MpvIPCPlayer(BasePlayer):
    """MPV Player implementation using IPC for advanced features."""

    def __init__(self, config: MpvConfig):
        self.config = config
        self.ipc_client: Optional[MPVIPCClient] = None
        self.mpv_process: Optional[subprocess.Popen] = None
        self.socket_path: Optional[str] = None

        # Player state
        self.last_stop_time: str = "0"
        self.last_total_time: str = "0"
        self.last_stop_time_secs: float = 0
        self.last_total_time_secs: float = 0
        self.current_media_title: str = ""
        self.player_fetching: bool = False

        # Runtime state - injected from outside
        self.anime_provider: Optional["BaseAnimeProvider"] = None
        self.current_anime: Optional[Any] = None
        self.available_episodes: List[str] = []
        self.current_episode: Optional[str] = None
        self.current_anime_id: Optional[str] = None
        self.current_anime_title: Optional[str] = None
        self.current_translation_type: str = "sub"
        self.current_server: Optional["Server"] = None
        self.subtitles: List[Dict[str, str]] = []

        # Event handlers
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.property_observers: Dict[str, List[Callable]] = {}
        self.key_bindings: Dict[str, Callable] = {}
        self.message_handlers: Dict[str, Callable] = {}

    def play(self, params: PlayerParams) -> PlayerResult:
        """Play media using MPV with IPC."""
        if detect.is_running_in_termux():
            raise FastAnimeError("IPC player not supported on termux")

        return self._play_with_ipc(params)

    def _play_with_ipc(self, params: PlayerParams) -> PlayerResult:
        """Play media using MPV IPC."""
        # Set up runtime dependencies from params if provided
        if params.anime_provider and params.current_anime:
            self.anime_provider = params.anime_provider
            self.current_anime = params.current_anime
            self.available_episodes = params.available_episodes or []
            self.current_episode = params.current_episode or ""
            self.current_anime_id = params.current_anime_id or ""
            self.current_anime_title = params.current_anime_title or ""
            self.current_translation_type = params.current_translation_type or "sub"

        try:
            self._setup_ipc_socket()
            self._start_mpv_process(params)
            self._connect_ipc()
            self._setup_event_handling()
            self._setup_key_bindings()
            self._setup_message_handlers()
            self._configure_player(params)

            # Wait for playback to complete
            self._wait_for_playback()

            return PlayerResult(
                stop_time=self.last_stop_time, total_time=self.last_total_time
            )
        finally:
            self._cleanup()

    def _setup_ipc_socket(self) -> None:
        """Create a temporary IPC socket path."""
        temp_dir = Path(tempfile.gettempdir())
        self.socket_path = str(temp_dir / f"mpv_ipc_{time.time()}.sock")

    def _start_mpv_process(self, params: PlayerParams) -> None:
        """Start MPV process with IPC enabled."""
        mpv_args = [
            "mpv",
            f"--input-ipc-server={self.socket_path}",
            "--idle=yes",
            "--force-window=yes",
            params.url,
        ]

        # Add custom MPV arguments
        mpv_args.extend(self._create_mpv_cli_options(params))

        # Add pre-args if configured
        pre_args = self.config.pre_args.split(",") if self.config.pre_args else []

        logger.info(f"Starting MPV with IPC socket: {self.socket_path}")

        self.mpv_process = subprocess.Popen(
            pre_args + mpv_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # Give MPV a moment to start and create the socket
        time.sleep(1.0)

    def _connect_ipc(self) -> None:
        """Connect to MPV IPC socket."""
        if not self.socket_path:
            raise MPVIPCError("Socket path not set")

        self.ipc_client = MPVIPCClient(self.socket_path)
        self.ipc_client.connect()

    def _setup_event_handling(self) -> None:
        """Setup event handlers for MPV events."""
        if not self.ipc_client:
            return

        # Request events we care about
        try:
            self.ipc_client.send_command(["request_log_messages", "info"])
        except Exception as e:
            logger.warning(f"Failed to request log messages: {e}")

        # Observe properties we care about
        try:
            self.ipc_client.observe_property("time-pos")
            self.ipc_client.observe_property("time-remaining")
            self.ipc_client.observe_property("duration")
            self.ipc_client.observe_property("filename")
        except Exception as e:
            logger.warning(f"Failed to observe properties: {e}")

    def _setup_key_bindings(self) -> None:
        """Setup custom key bindings."""
        if not self.ipc_client:
            return

        # Define key bindings using individual keybind commands
        key_bindings = {
            "shift+n": "script-message fastanime-next-episode",
            "shift+p": "script-message fastanime-previous-episode",
            "shift+a": "script-message fastanime-toggle-auto-next",
            "shift+t": "script-message fastanime-toggle-translation",
            "shift+r": "script-message fastanime-reload-episode",
        }

        # Register key bindings with MPV using keybind command
        for key, command in key_bindings.items():
            try:
                response = self.ipc_client.send_command(["keybind", key, command])
                logger.info(f"Key binding result for {key}: {response}")
            except Exception as e:
                logger.warning(f"Failed to bind key {key}: {e}")

        # Also show a message to indicate keys are ready
        try:
            self.ipc_client.send_command(
                [
                    "show-text",
                    "FastAnime IPC: Shift+N=Next, Shift+P=Prev, Shift+R=Reload, Shift+T=Toggle",
                    "3000",
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to show key binding message: {e}")

    def _setup_message_handlers(self) -> None:
        """Setup script message handlers."""
        self.message_handlers.update(
            {
                "select-episode": self._handle_select_episode,
                "select-server": self._handle_select_server,
                "select-quality": self._handle_select_quality,
                "fastanime-next-episode": lambda: self._next_episode(),
                "fastanime-previous-episode": lambda: self._previous_episode(),
                "fastanime-toggle-auto-next": lambda: self._toggle_auto_next(),
                "fastanime-toggle-translation": lambda: self._toggle_translation_type(),
                "fastanime-reload-episode": lambda: self._reload_episode(),
            }
        )

    def _configure_player(self, params: PlayerParams) -> None:
        """Configure MPV player with parameters."""
        if not self.ipc_client:
            return

        # Set title
        if params.title:
            try:
                self.ipc_client.set_property("title", params.title)
                self.current_media_title = params.title
            except MPVIPCError as e:
                logger.warning(f"Failed to set title: {e}")

        # Set start time
        if params.start_time:
            try:
                self.ipc_client.set_property("start", params.start_time)
            except MPVIPCError as e:
                logger.warning(f"Failed to set start time: {e}")

        # Add subtitles
        if params.subtitles:
            for i, subtitle_path in enumerate(params.subtitles):
                flag = "select" if i == 0 else "auto"
                try:
                    self.ipc_client.send_command(["sub-add", subtitle_path, flag])
                except MPVIPCError as e:
                    logger.warning(f"Failed to add subtitle {subtitle_path}: {e}")

        # Add any episode-specific subtitles
        try:
            self._add_episode_subtitles()
        except Exception as e:
            logger.warning(f"Failed to add episode subtitles: {e}")

        # Set HTTP headers (only if not empty)
        if params.headers:
            header_str = ",".join([f"{k}:{v}" for k, v in params.headers.items()])
            if header_str.strip():  # Only set if we have actual headers
                try:
                    self.ipc_client.set_property("http-header-fields", header_str)
                except MPVIPCError as e:
                    logger.warning(f"Failed to set HTTP headers: {e}")

    def _wait_for_playback(self) -> None:
        """Wait for playback to complete while handling events."""
        if not self.ipc_client:
            return

        try:
            while True:
                # Check if MPV process is still running
                if self.mpv_process and self.mpv_process.poll() is not None:
                    break

                # Handle property changes and events
                self._handle_events()

                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("Playback interrupted by user")

    def _handle_events(self) -> None:
        """Handle MPV events and property changes."""
        if not self.ipc_client or not self.ipc_client.socket:
            return

        try:
            # Check for incoming messages (non-blocking)
            self.ipc_client.socket.settimeout(0.01)
            try:
                data = self.ipc_client.socket.recv(4096)  # Increased buffer size
                if data:
                    message_text = data.decode().strip()
                    if message_text:
                        # Handle multiple JSON objects on separate lines
                        lines = message_text.split("\n")
                        for line in lines:
                            line = line.strip()
                            if line:
                                try:
                                    message = json.loads(line)
                                    self._handle_mpv_message(message)
                                except json.JSONDecodeError as e:
                                    logger.debug(
                                        f"Failed to parse JSON: {line[:100]} - {e}"
                                    )
                                    continue
            except socket.timeout:
                pass
            except Exception as e:
                logger.debug(f"Socket read error: {e}")
                pass
            finally:
                self.ipc_client.socket.settimeout(None)

            # Periodically update time properties (less frequently to avoid spam)

            if random.randint(1, 50) == 1:  # Only update occasionally
                # Get current time position (with error handling)
                try:
                    time_pos = self.ipc_client.get_property("time-pos")
                    if isinstance(time_pos, float):
                        self.last_stop_time = format_time(time_pos)
                        self.last_stop_time_secs = time_pos
                except (MPVIPCError, Exception):
                    pass

                # Get duration (with error handling)
                try:
                    duration = self.ipc_client.get_property("duration")
                    if isinstance(duration, float):
                        self.last_total_time = format_time(duration)
                        self.last_total_time_secs = duration
                except (MPVIPCError, Exception):
                    pass

                # Get time remaining for auto-next (with error handling)
                try:
                    time_remaining = self.ipc_client.get_property("time-remaining")
                    if (
                        isinstance(time_remaining, float)
                        and time_remaining < 1
                        and not self.player_fetching
                    ):
                        self._auto_next_episode()
                except (MPVIPCError, Exception):
                    pass

        except MPVIPCError:
            # IPC communication failed, probably because MPV closed
            pass

    def _handle_mpv_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming messages from MPV."""
        logger.debug(f"Received MPV message: {message}")

        if message.get("event") == "client-message":
            # Handle script messages
            args = message.get("args", [])
            if args and len(args) > 0:
                message_name = args[0]
                message_args = args[1:] if len(args) > 1 else []

                logger.info(
                    f"Handling script message: {message_name} with args: {message_args}"
                )

                handler = self.message_handlers.get(message_name)
                if handler:
                    try:
                        if message_args:
                            handler(*message_args)
                        else:
                            handler()
                    except Exception as e:
                        logger.error(f"Error handling message {message_name}: {e}")
                else:
                    logger.warning(f"No handler found for message: {message_name}")

        elif message.get("event") == "file-loaded":
            # File loaded event - add subtitles
            logger.info("File loaded, adding episode subtitles")
            self._add_episode_subtitles()

        elif message.get("event") == "property-change":
            # Handle property changes
            property_name = message.get("name")
            if property_name == "time-remaining":
                value = message.get("data")
                if value is not None and value < 1 and not self.player_fetching:
                    self._auto_next_episode()

        elif message.get("event"):
            # Log other events for debugging
            logger.debug(f"MPV event: {message.get('event')}")

        # Handle responses to our commands
        elif message.get("request_id"):
            logger.debug(f"Command response: {message}")

    def _cleanup(self) -> None:
        """Clean up resources."""
        if self.ipc_client:
            self.ipc_client.disconnect()

        if self.mpv_process:
            try:
                self.mpv_process.terminate()
                self.mpv_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.mpv_process.kill()

        # Remove socket file
        if self.socket_path and Path(self.socket_path).exists():
            try:
                Path(self.socket_path).unlink()
            except:
                pass

    def _create_mpv_cli_options(self, params: PlayerParams) -> List[str]:
        """Create MPV CLI options from parameters."""
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

    # Episode navigation methods (similar to original implementation)
    def _get_episode(
        self,
        episode_type: Literal["next", "previous", "reload", "custom"],
        ep_no: Optional[str] = None,
        server: str = "top",
    ) -> Optional[str]:
        """Get episode stream URL for navigation."""
        if (
            not self.anime_provider
            or not self.current_anime
            or not self.current_episode
        ):
            if self.ipc_client:
                self.ipc_client.send_command(
                    ["show-text", "Episode navigation not available"]
                )
            return None

        # Show status message
        if self.ipc_client:
            self.ipc_client.send_command(
                ["show-text", f"Fetching {episode_type} episode..."]
            )

        # Reset timing info for new episode
        self.last_stop_time = "0"
        self.last_total_time = "0"
        self.last_stop_time_secs = 0
        self.last_total_time_secs = 0

        # Determine target episode
        try:
            current_index = self.available_episodes.index(self.current_episode)

            if episode_type == "next":
                if current_index >= len(self.available_episodes) - 1:
                    if self.ipc_client:
                        self.ipc_client.send_command(
                            ["show-text", "Already at last episode"]
                        )
                    return None
                target_episode = self.available_episodes[current_index + 1]

            elif episode_type == "previous":
                if current_index <= 0:
                    if self.ipc_client:
                        self.ipc_client.send_command(
                            ["show-text", "Already at first episode"]
                        )
                    return None
                target_episode = self.available_episodes[current_index - 1]

            elif episode_type == "reload":
                target_episode = self.current_episode

            elif episode_type == "custom":
                if not ep_no or ep_no not in self.available_episodes:
                    if self.ipc_client:
                        self.ipc_client.send_command(
                            [
                                "show-text",
                                f"Invalid episode. Available: {', '.join(self.available_episodes)}",
                            ]
                        )
                    return None
                target_episode = ep_no

        except ValueError:
            if self.ipc_client:
                self.ipc_client.send_command(
                    ["show-text", "Current episode not found in available episodes"]
                )
            return None

        # Get streams for the target episode
        try:
            # Validate required fields
            if not self.current_anime_id:
                if self.ipc_client:
                    self.ipc_client.send_command(["show-text", "Missing anime ID"])
                return None

            # Cast translation type to proper literal
            translation_type: Literal["sub", "dub"] = (
                "sub" if self.current_translation_type == "sub" else "dub"
            )

            stream_params = EpisodeStreamsParams(
                anime_id=self.current_anime_id,
                query=self.current_anime_title or "",
                episode=target_episode,
                translation_type=translation_type,
            )

            episode_streams = self.anime_provider.episode_streams(stream_params)
            if not episode_streams:
                if self.ipc_client:
                    self.ipc_client.send_command(
                        ["show-text", "No streams found for episode"]
                    )
                return None

            # Select server (top or specific)
            if server == "top":
                selected_server = next(episode_streams, None)
            else:
                # Find specific server
                selected_server = None
                for stream_server in episode_streams:
                    if stream_server.name.lower() == server.lower():
                        selected_server = stream_server
                        break

                if not selected_server:
                    if self.ipc_client:
                        self.ipc_client.send_command(
                            ["show-text", f"Server '{server}' not found"]
                        )
                    return None

            if not selected_server:
                if self.ipc_client:
                    self.ipc_client.send_command(["show-text", "No server available"])
                return None

            # Get stream link - prefer highest quality
            if not selected_server.links:
                if self.ipc_client:
                    self.ipc_client.send_command(
                        ["show-text", "No stream links available"]
                    )
                return None

            # Sort by quality and get the best one
            sorted_links = sorted(
                selected_server.links, key=lambda x: int(x.quality), reverse=True
            )
            stream_link = sorted_links[0].link

            # Update current state
            self.current_episode = target_episode
            self.current_server = selected_server
            self.current_media_title = (
                selected_server.episode_title or f"Episode {target_episode}"
            )
            self.subtitles = [
                {"url": sub.url, "language": sub.language or "unknown"}
                for sub in selected_server.subtitles
            ]

            return stream_link

        except Exception as e:
            logger.error(f"Error fetching episode {target_episode}: {e}")
            if self.ipc_client:
                self.ipc_client.send_command(
                    ["show-text", f"Error fetching episode: {str(e)}"]
                )
            return None

    def _next_episode(self) -> None:
        """Navigate to next episode."""
        url = self._get_episode("next")
        if url and self.ipc_client:
            self.ipc_client.send_command(["loadfile", url])
            self.ipc_client.set_property("title", self.current_media_title)
            # Add subtitles after a short delay to ensure file is loaded
            time.sleep(0.5)
            self._add_episode_subtitles()

    def _previous_episode(self) -> None:
        """Navigate to previous episode."""
        url = self._get_episode("previous")
        if url and self.ipc_client:
            self.ipc_client.send_command(["loadfile", url])
            self.ipc_client.set_property("title", self.current_media_title)
            # Add subtitles after a short delay to ensure file is loaded
            time.sleep(0.5)
            self._add_episode_subtitles()

    def _reload_episode(self) -> None:
        """Reload current episode."""
        url = self._get_episode("reload")
        if url and self.ipc_client:
            self.ipc_client.send_command(["loadfile", url])
            self.ipc_client.set_property("title", self.current_media_title)
            # Add subtitles after a short delay to ensure file is loaded
            time.sleep(0.5)
            self._add_episode_subtitles()

    def _toggle_auto_next(self) -> None:
        """Toggle auto-next feature."""
        # This would be controlled by config, but for now just show message
        if self.ipc_client:
            self.ipc_client.send_command(
                ["show-text", "Auto-next feature toggle not implemented"]
            )

    def _toggle_translation_type(self) -> None:
        """Toggle between sub and dub."""
        if not self.anime_provider:
            return

        new_type = "sub" if self.current_translation_type == "dub" else "dub"
        if self.ipc_client:
            self.ipc_client.send_command(["show-text", f"Switching to {new_type}..."])

        # Try to reload current episode with new translation type
        old_type = self.current_translation_type
        self.current_translation_type = new_type

        url = self._get_episode("reload")
        if url and self.ipc_client:
            self.ipc_client.send_command(["loadfile", url])
            self.ipc_client.set_property("title", self.current_media_title)
            self.ipc_client.send_command(["show-text", f"Switched to {new_type}"])
            # Add subtitles after a short delay to ensure file is loaded
            time.sleep(0.5)
            self._add_episode_subtitles()
        else:
            # Revert if failed
            self.current_translation_type = old_type
            if self.ipc_client:
                self.ipc_client.send_command(
                    ["show-text", f"Failed to switch to {new_type}"]
                )

    def _auto_next_episode(self) -> None:
        """Automatically play next episode."""
        if not self.player_fetching:
            logger.info("Auto fetching next episode")
            self.player_fetching = True
            url = self._get_episode("next")
            if url and self.ipc_client:
                self.ipc_client.send_command(["loadfile", url])
                self.ipc_client.set_property("title", self.current_media_title)
                # Add subtitles after a short delay to ensure file is loaded
                time.sleep(0.5)
                self._add_episode_subtitles()

    # Message handlers
    def _handle_select_episode(self, episode: Optional[str] = None) -> None:
        """Handle episode selection message."""
        if not episode:
            if self.ipc_client:
                self.ipc_client.send_command(["show-text", "No episode was selected"])
            return

        url = self._get_episode("custom", episode)
        if url and self.ipc_client:
            self.ipc_client.send_command(["loadfile", url])
            self.ipc_client.set_property("title", self.current_media_title)
            # Add subtitles after a short delay to ensure file is loaded
            time.sleep(0.5)
            self._add_episode_subtitles()

    def _handle_select_server(self, server: Optional[str] = None) -> None:
        """Handle server selection message."""
        if not server:
            if self.ipc_client:
                self.ipc_client.send_command(["show-text", "No server was selected"])
            return

        url = self._get_episode("reload", server=server)
        if url and self.ipc_client:
            self.ipc_client.send_command(["loadfile", url])
            self.ipc_client.set_property("title", self.current_media_title)
            # Add subtitles after a short delay to ensure file is loaded
            time.sleep(0.5)
            self._add_episode_subtitles()

    def _handle_select_quality(self, quality: Optional[str] = None) -> None:
        """Handle quality selection message."""
        if not quality or not self.current_server:
            if self.ipc_client:
                self.ipc_client.send_command(["show-text", "No quality was selected"])
            return

        # Find link with matching quality
        matching_link = None
        for link in self.current_server.links:
            if link.quality == quality:
                matching_link = link
                break

        if matching_link:
            if self.ipc_client:
                self.ipc_client.send_command(
                    ["show-text", f"Switching to {quality}p quality..."]
                )
                self.ipc_client.send_command(["loadfile", matching_link.link])
        else:
            available_qualities = [link.quality for link in self.current_server.links]
            if self.ipc_client:
                self.ipc_client.send_command(
                    [
                        "show-text",
                        f"Quality {quality}p not available. Available: {', '.join(available_qualities)}",
                    ]
                )

    def show_text(self, text: str, duration: int = 2000) -> None:
        """Show text on MPV OSD."""
        if self.ipc_client:
            self.ipc_client.send_command(["show-text", text, str(duration)])

    def _add_episode_subtitles(self) -> None:
        """Add episode-specific subtitles after loading new episode."""
        if not self.ipc_client or not self.subtitles:
            return

        for i, subtitle in enumerate(self.subtitles):
            flag = "select" if i == 0 else "auto"
            try:
                self.ipc_client.send_command(
                    [
                        "sub-add",
                        subtitle["url"],
                        flag,
                        None,
                        subtitle.get("language", "unknown"),
                    ]
                )
            except Exception as e:
                logger.warning(f"Failed to add subtitle: {e}")


# Factory function for creating IPC player
def create_ipc_player(config: MpvConfig) -> MpvIPCPlayer:
    """Create an IPC-based MPV player instance."""
    return MpvIPCPlayer(config)
