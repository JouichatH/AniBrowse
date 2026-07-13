"""Tests for the AniSkip client and SkipInterval (mocked HTTP)."""

import pytest

from viu_media.cli.service.player.aniskip import (
    ANISKIP_URL,
    SkipInterval,
    fetch_skip_times,
)


# ---- SkipInterval.contains ----------------------------------------------


def test_contains_is_half_open():
    interval = SkipInterval(kind="op", start=10.0, end=30.0)
    assert not interval.contains(9.99)
    assert interval.contains(10.0)  # start is inclusive
    assert interval.contains(29.99)
    assert not interval.contains(30.0)  # end (the seek target) is exclusive


# ---- fetch_skip_times: guards that never hit the network -----------------


@pytest.mark.parametrize("mal_id", [None, 0])
def test_no_mal_id_returns_empty_without_request(mal_id, httpx_mock):
    assert fetch_skip_times(mal_id, "1") == []
    assert httpx_mock.get_requests() == []


@pytest.mark.parametrize("episode", ["Special", "OVA", "abc"])
def test_non_numeric_episode_returns_empty_without_request(episode, httpx_mock):
    assert fetch_skip_times(123, episode) == []
    assert httpx_mock.get_requests() == []


def test_non_positive_episode_returns_empty(httpx_mock):
    assert fetch_skip_times(123, "0") == []
    assert httpx_mock.get_requests() == []


# ---- fetch_skip_times: HTTP responses ------------------------------------


def _url(mal_id, ep):
    return f"{ANISKIP_URL}/{mal_id}/{ep}"


def test_404_returns_empty(httpx_mock):
    httpx_mock.add_response(status_code=404)
    assert fetch_skip_times(123, "1") == []


def test_found_false_returns_empty(httpx_mock):
    httpx_mock.add_response(
        json={"found": False, "results": []}
    )
    assert fetch_skip_times(123, "1") == []


def test_parses_op_and_ed_intervals(httpx_mock):
    httpx_mock.add_response(
        json={
            "found": True,
            "results": [
                {"skipType": "op", "interval": {"startTime": 80.0, "endTime": 110.0}},
                {"skipType": "ed", "interval": {"startTime": 1300, "endTime": 1400}},
            ],
        },
    )
    intervals = fetch_skip_times(123, "1")
    kinds = {i.kind for i in intervals}
    assert kinds == {"op", "ed"}
    op = next(i for i in intervals if i.kind == "op")
    assert (op.start, op.end) == (80.0, 110.0)


def test_mixed_kinds_collapse_to_op_ed(httpx_mock):
    httpx_mock.add_response(
        json={
            "found": True,
            "results": [
                {"skipType": "mixed-op", "interval": {"startTime": 0, "endTime": 90}},
                {"skipType": "mixed-ed", "interval": {"startTime": 1200, "endTime": 1320}},
            ],
        },
    )
    assert sorted(i.kind for i in fetch_skip_times(123, "1")) == ["ed", "op"]


def test_recap_and_unknown_kinds_dropped(httpx_mock):
    httpx_mock.add_response(
        json={
            "found": True,
            "results": [
                {"skipType": "recap", "interval": {"startTime": 0, "endTime": 60}},
                {"skipType": "op", "interval": {"startTime": 80, "endTime": 110}},
            ],
        },
    )
    intervals = fetch_skip_times(123, "1")
    assert [i.kind for i in intervals] == ["op"]


def test_bad_and_zero_length_intervals_filtered(httpx_mock):
    httpx_mock.add_response(
        json={
            "found": True,
            "results": [
                {"skipType": "op", "interval": {"startTime": 100, "endTime": 100}},  # zero length
                {"skipType": "op", "interval": {"startTime": 100, "endTime": 80}},   # negative
                {"skipType": "ed", "interval": {}},                                   # missing keys
                {"skipType": "ed", "interval": {"startTime": "x", "endTime": "y"}},   # non-numeric
                {"skipType": "op", "interval": {"startTime": 80, "endTime": 110}},    # the one good one
            ],
        },
    )
    intervals = fetch_skip_times(123, "1")
    assert len(intervals) == 1
    assert (intervals[0].start, intervals[0].end) == (80.0, 110.0)


def test_episode_coerced_to_int_in_url(httpx_mock):
    httpx_mock.add_response(
        json={"found": False, "results": []}
    )
    fetch_skip_times(123, "5.0")
    request = httpx_mock.get_requests()[0]
    assert "/123/5" in str(request.url)


def test_network_error_swallowed(httpx_mock):
    httpx_mock.add_exception(RuntimeError("boom"))
    assert fetch_skip_times(123, "1") == []
