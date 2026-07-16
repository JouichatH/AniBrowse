"""Tests for the in-player server-switch menu JSON (Phase 3)."""

import json

from viu_media.cli.interactive.menu.media.servers import (
    _server_switch_entries,
    _write_servers_json,
)
from viu_media.libs.provider.anime.types import EpisodeStream, Server, Subtitle


def _server(name, link, quality="1080", headers=None, subs=None):
    return Server(
        name=name,
        links=[EpisodeStream(link=link, quality=quality)],
        headers=headers or {},
        subtitles=[Subtitle(url=u) for u in (subs or [])],
    )


def test_entries_pick_quality_and_mark_current():
    servers = [
        _server("Yt-mp4", "https://a/1080", quality="1080", headers={"Referer": "r"}),
        _server("Mp4", "https://b/720", quality="720"),
    ]
    entries = _server_switch_entries(servers, "1080", current_name="Yt-mp4")

    assert [e["name"] for e in entries] == ["Yt-mp4", "Mp4"]
    assert entries[0]["url"] == "https://a/1080"
    assert entries[0]["headers"] == {"Referer": "r"}
    assert entries[0]["current"] is True
    assert entries[1]["current"] is False


def test_entries_fall_back_to_first_link_when_quality_missing():
    # _filter_by_quality returns the first link if the requested quality is absent,
    # so a server is still switchable even if it lacks the exact quality.
    servers = [_server("Only720", "https://only/720", quality="720")]
    entries = _server_switch_entries(servers, "1080", current_name="Only720")
    assert len(entries) == 1
    assert entries[0]["url"] == "https://only/720"


def test_entries_exclude_torrents():
    magnet = "magnet:?xt=urn:btih:" + "a" * 40
    servers = [
        _server("nyaa:SubsPlease", magnet),
        _server("Yt-mp4", "https://a/1080"),
    ]
    entries = _server_switch_entries(servers, "1080", current_name="Yt-mp4")
    assert [e["name"] for e in entries] == ["Yt-mp4"]  # magnet dropped


def test_entries_carry_subtitles():
    servers = [_server("Yt-mp4", "https://a/1080", subs=["https://s/en.vtt"])]
    entries = _server_switch_entries(servers, "1080", current_name="Yt-mp4")
    assert entries[0]["subtitles"] == ["https://s/en.vtt"]


def test_write_servers_json_atomic_and_parseable(tmp_path):
    path = str(tmp_path / "servers.json")
    servers = [
        _server("Yt-mp4", "https://a/1080", headers={"Referer": "r"}),
        _server("Mp4", "https://b/1080"),
    ]
    _write_servers_json(path, servers, "1080", current_name="Yt-mp4")

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert [d["name"] for d in data] == ["Yt-mp4", "Mp4"]
    assert data[0]["current"] is True
    # No leftover temp file from the atomic replace.
    assert not (tmp_path / "servers.json.tmp").exists()


def test_write_servers_json_never_raises_on_bad_path():
    # A bad directory must be swallowed, not crash playback.
    _write_servers_json(
        "/nonexistent-dir-xyz/servers.json",
        [_server("Yt-mp4", "https://a/1080")],
        "1080",
        current_name="Yt-mp4",
    )
