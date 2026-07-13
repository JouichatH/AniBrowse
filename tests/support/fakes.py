"""Scripted fakes for driving the interactive app headlessly.

These stand in for every external dependency (fzf, mpv, AniList, providers)
so menus and the IPC player can be exercised in-process with no terminal,
no subprocesses and no network. Inject them through the Context backing
fields (``ctx._selector``, ``ctx._player``, ...) — see tests/conftest.py.
"""

from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional

from viu_media.core.exceptions import NavigationAbort
from viu_media.libs.media_api.base import BaseApiClient
from viu_media.libs.media_api.types import (
    MediaItem,
    MediaSearchResult,
    MediaTitle,
    PageInfo,
    UserProfile,
)
from viu_media.libs.player.base import BasePlayer
from viu_media.libs.player.params import PlayerParams
from viu_media.libs.player.types import PlayerResult
from viu_media.libs.provider.anime.base import BaseAnimeProvider
from viu_media.libs.provider.anime.types import (
    Anime,
    AnimeEpisodes,
    EpisodeStream,
)
from viu_media.libs.provider.anime.types import PageInfo as ProviderPageInfo
from viu_media.libs.provider.anime.types import (
    SearchResult,
    SearchResults,
    Server,
)
from viu_media.libs.selectors.base import BaseSelector

# ---------------------------------------------------------------------------
# Canned model builders
# ---------------------------------------------------------------------------


def make_media_item(id: int = 1, title: str = "Test Anime", **kwargs) -> MediaItem:
    kwargs.setdefault("id_mal", 100 + id)
    kwargs.setdefault("episodes", 24)
    return MediaItem(id=id, title=MediaTitle(english=title, romaji=title), **kwargs)


def make_media_search_result(*items: MediaItem, **page_info) -> MediaSearchResult:
    if not items:
        items = (make_media_item(),)
    return MediaSearchResult(page_info=PageInfo(**page_info), media=list(items))


def make_anime(
    id: str = "anime-1",
    title: str = "Test Anime",
    episodes: Iterable[str] = ("1", "2", "3"),
    **kwargs,
) -> Anime:
    eps = list(episodes)
    return Anime(id=id, title=title, episodes=AnimeEpisodes(sub=eps, dub=eps), **kwargs)


def make_provider_search_results(*animes: Anime) -> SearchResults:
    if not animes:
        animes = (make_anime(),)
    return SearchResults(
        page_info=ProviderPageInfo(total=len(animes)),
        results=[
            SearchResult(id=a.id, title=a.title, episodes=a.episodes) for a in animes
        ],
    )


def make_server(
    name: str = "TOP",
    link: str = "https://example.com/stream.m3u8",
    episode: str = "1",
    **kwargs,
) -> Server:
    return Server(
        name=name,
        links=[EpisodeStream(link=link)],
        episode_title=f"Episode {episode}",
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Selector
# ---------------------------------------------------------------------------


def pick(substring: str) -> Callable[[List[str]], str]:
    """Script entry that picks the first choice containing ``substring``."""

    def _pick(choices: List[str]) -> str:
        for choice in choices:
            if substring in choice:
                return choice
        raise AssertionError(f"No choice contains {substring!r}; got: {choices}")

    return _pick


class FakeSelector(BaseSelector):
    """Selector driven by a scripted queue of answers.

    Script entries may be:
      - a plain value: returned as-is (must match a choice for ``choose``)
      - an int: index into the offered choices
      - a callable: called with the choices, returns the answer (see ``pick``)

    When the script runs out, ``NavigationAbort`` is raised — exactly what a
    real selector does when the user hits Esc — so driven flows terminate.
    """

    def __init__(self, script: Optional[Iterable[Any]] = None):
        self.script: deque = deque(script or [])
        self.calls: List[tuple] = []

    def _next(self, kind: str, prompt: str, choices: Optional[List[str]] = None):
        self.calls.append((kind, prompt, choices))
        if not self.script:
            raise NavigationAbort()
        entry = self.script.popleft()
        if callable(entry):
            return entry(choices if choices is not None else [])
        if isinstance(entry, int) and not isinstance(entry, bool) and choices:
            return choices[entry]
        return entry

    def choose(self, prompt, choices, *, preview=None, header=None):
        answer = self._next("choose", prompt, choices)
        if answer is not None and answer not in choices:
            raise AssertionError(
                f"Scripted answer {answer!r} is not an offered choice for "
                f"{prompt!r}; got: {choices}"
            )
        return answer

    def choose_multiple(self, prompt, choices, preview=None):
        answer = self._next("choose_multiple", prompt, choices)
        if answer is None:
            return []
        return answer if isinstance(answer, list) else [answer]

    def confirm(self, prompt, *, default=False):
        answer = self._next("confirm", prompt)
        return bool(answer)

    def ask(self, prompt, *, default=None):
        return self._next("ask", prompt)

    def search(
        self,
        prompt,
        search_command,
        *,
        preview=None,
        header=None,
        initial_query=None,
        initial_results=None,
    ):
        return self._next("search", prompt, initial_results)


# ---------------------------------------------------------------------------
# Media API
# ---------------------------------------------------------------------------


class FakeApiClient(BaseApiClient):
    """Media API returning canned results; records the params it was given."""

    def __init__(
        self,
        search_result: Optional[MediaSearchResult] = None,
        user: Optional[UserProfile] = None,
    ):
        super().__init__(config=None, client=None)  # type: ignore[arg-type]
        self.search_result = search_result or make_media_search_result()
        self.user = user
        self.calls: List[tuple] = []

    def authenticate(self, token):
        self.calls.append(("authenticate", token))
        return self.user

    def is_authenticated(self):
        return self.user is not None

    def get_viewer_profile(self):
        return self.user

    def search_media(self, params):
        self.calls.append(("search_media", params))
        return self.search_result

    def search_media_list(self, params):
        self.calls.append(("search_media_list", params))
        return self.search_result

    def update_list_entry(self, params):
        self.calls.append(("update_list_entry", params))
        return True

    def delete_list_entry(self, media_id):
        self.calls.append(("delete_list_entry", media_id))
        return True

    def get_recommendation_for(self, params):
        return []

    def get_characters_of(self, params):
        return None

    def get_related_anime_for(self, params):
        return []

    def get_airing_schedule_for(self, params):
        return None

    def get_reviews_for(self, params):
        return []

    def get_notifications(self):
        return []

    def transform_raw_search_data(self, raw_data):
        return None


# ---------------------------------------------------------------------------
# Anime provider
# ---------------------------------------------------------------------------


class FakeAnimeProvider(BaseAnimeProvider):
    """Provider serving canned search results / anime / per-episode servers."""

    HEADERS: Dict[str, str] = {}

    def __init__(
        self,
        anime: Optional[Anime] = None,
        search_results: Optional[SearchResults] = None,
        servers: Optional[Dict[str, List[Server]]] = None,
    ):
        # Deliberately no super().__init__: the base wants an httpx.Client and
        # fakes must never own network handles.
        self.client = None
        self.anime = anime or make_anime()
        self.search_results = search_results or make_provider_search_results(
            self.anime
        )
        # episode number -> servers for it; None means "serve every episode
        # the anime declares" with a default server.
        self.servers = servers
        self.calls: List[tuple] = []

    def search(self, params):
        self.calls.append(("search", params))
        return self.search_results

    def get(self, params):
        self.calls.append(("get", params))
        return self.anime

    def episode_streams(self, params) -> Optional[Iterator[Server]]:
        self.calls.append(("episode_streams", params))
        if self.servers is not None:
            servers = self.servers.get(params.episode, [])
            return iter(servers) if servers else None
        if params.episode in self.anime.episodes.sub:
            return iter([make_server(episode=params.episode)])
        return None


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------


class FakeBasePlayer(BasePlayer):
    """BasePlayer that records plays and refuses to spawn processes."""

    def __init__(self, config=None):
        self.stream_config = config
        self.play_calls: List[PlayerParams] = []

    def play(self, params: PlayerParams) -> PlayerResult:
        self.play_calls.append(params)
        return PlayerResult(episode=params.episode)

    def play_with_ipc(self, params: PlayerParams, socket_path: str):
        raise AssertionError(
            "FakeBasePlayer.play_with_ipc called - a test tried to launch mpv"
        )


class FakePlayerService:
    """Duck-typed PlayerService: menus call ``ctx.player.play(...)``."""

    def __init__(self, results: Optional[Iterable[PlayerResult]] = None):
        self.results: deque = deque(results or [])
        self.play_calls: List[tuple] = []

    def play(
        self,
        params: PlayerParams,
        anime: Optional[Anime] = None,
        media_item: Optional[MediaItem] = None,
        local: bool = False,
    ) -> PlayerResult:
        self.play_calls.append((params, anime, media_item, local))
        if self.results:
            return self.results.popleft()
        return PlayerResult(
            episode=params.episode, stop_time="00:20:00", total_time="00:23:00"
        )


class FakeWatchHistory:
    """WatchHistoryService stand-in: no persistence, records tracked results."""

    def __init__(self, resume: tuple = (None, None)):
        self._resume = resume
        self.tracked: List[tuple] = []

    def get_episode(self, media_item):
        # (episode, start_time) to resume from; (None, None) = start fresh.
        return self._resume

    def track(self, media_item, player_result):
        self.tracked.append((media_item, player_result))


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


class _NoopProgress:
    def add_task(self, *args, **kwargs):
        return 0

    def update(self, *args, **kwargs):
        pass

    def advance(self, *args, **kwargs):
        pass


class FakeFeedback:
    """FeedbackService stand-in: silent, but keeps a log of every message."""

    def __init__(self):
        self.messages: List[tuple] = []

    def _record(self, level, message, details=None):
        self.messages.append((level, message, details))

    def success(self, message, details=None):
        self._record("success", message, details)

    def error(self, message, details=None):
        self._record("error", message, details)

    def warning(self, message, details=None):
        self._record("warning", message, details)

    def info(self, message, details=None):
        self._record("info", message, details)

    @contextmanager
    def progress(self, message, *args, **kwargs):
        self._record("progress", message)
        yield 0, _NoopProgress()

    def pause_for_user(self, message="Press Enter to continue"):
        self._record("pause", message)

    def clear_console(self):
        pass


# ---------------------------------------------------------------------------
# MPV IPC client
# ---------------------------------------------------------------------------


class FakeIPCClient:
    """Stands in for MPVIPCClient: records commands, serves scripted events.

    - ``events``: initial mpv events to feed ``get_event`` (dicts).
    - ``fail_on``: command names (e.g. ``"show-text"``) whose ``send_command``
      raises ``MPVIPCError`` — reproduces the transient-timeout bug.
    - ``shutdown_when``: predicate on this client; once true (checked when the
      scripted events are drained) a ``shutdown`` event ends the player loop.
    - ``max_idle_polls``: safety valve so a wedged loop ends instead of
      hanging the test run.
    """

    def __init__(
        self,
        events: Optional[Iterable[Dict[str, Any]]] = None,
        fail_on: Optional[Iterable[str]] = None,
        shutdown_when: Optional[Callable[["FakeIPCClient"], bool]] = None,
        max_idle_polls: int = 400,
    ):
        self.events: deque = deque(events or [])
        self.fail_on = set(fail_on or [])
        self.shutdown_when = shutdown_when
        self.max_idle_polls = max_idle_polls
        self.commands: List[List[Any]] = []
        self.connected = False
        self._idle_polls = 0

    def connect(self, timeout: float = 5.0) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def push_event(self, event: Dict[str, Any]) -> None:
        self.events.append(event)

    def commands_named(self, name: str) -> List[List[Any]]:
        return [c for c in self.commands if c and c[0] == name]

    def send_command(self, command: List[Any], timeout: float = 5.0) -> Dict[str, Any]:
        from viu_media.cli.service.player.ipc.mpv import MPVIPCError

        self.commands.append(list(command))
        if command and command[0] in self.fail_on:
            raise MPVIPCError(f"Timeout waiting for response to command: {command}")
        return {"error": "success", "request_id": len(self.commands)}

    def get_event(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        if self.events:
            self._idle_polls = 0
            return self.events.popleft()
        self._idle_polls += 1
        if self.shutdown_when is not None and self.shutdown_when(self):
            return {"event": "shutdown"}
        if self._idle_polls > self.max_idle_polls:
            return {"event": "shutdown"}
        return None
