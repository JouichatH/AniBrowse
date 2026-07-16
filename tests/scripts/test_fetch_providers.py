"""Tests for the allanime ranking patch in scripts/fetch_providers.py.

The provider scrapers are fetched from the upstream viu-media wheel and are not
vendored in the repo, so the fork's best-first ranking edit ships as an
idempotent, version-pinned text patch applied right after fetch. These tests
pin that patch's behaviour against the exact upstream 3.5.0 body.
"""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "fetch_providers",
    Path(__file__).resolve().parents[2] / "scripts" / "fetch_providers.py",
)
fp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fp)  # type: ignore[union-attr]


# The exact upstream viu-media==3.5.0 body of AllAnime.episode_streams. The patch
# is anchored on the final `for source in sources:` loop; keep this in step with
# UPSTREAM_VERSION.
PRISTINE = '''\
    @debug_provider
    def episode_streams(self, params: EpisodeStreamsParams) -> Iterator[Server] | None:
        from .extractors import extract_server

        episode = self._get_episode_payload(params)
        if not episode:
            logger.error("nope")
            return

        sources = episode.get("sourceUrls") or []
        if not sources:
            logger.error("nope")
            return

        for source in sources:
            if server := extract_server(self.client, params.episode, episode, source):
                yield server
'''


def test_patch_pristine_applies():
    new_text, status = fp.apply_ranking_patch(PRISTINE)
    assert status == "patched"
    assert new_text != PRISTINE
    assert fp.RANKING_PATCH_MARKER in new_text
    # dedupe + priority sort landed in the body
    assert "_ranked.sort(" in new_text
    assert "for source in _ranked:" in new_text
    # the raw un-ranked loop is gone
    assert "for source in sources:\n            if server" not in new_text


def test_patch_is_idempotent():
    once, s1 = fp.apply_ranking_patch(PRISTINE)
    assert s1 == "patched"
    twice, s2 = fp.apply_ranking_patch(once)
    assert s2 == "already"
    assert twice == once  # second pass changes nothing


def test_patch_skips_unknown_shape():
    # An upstream version whose body no longer matches the pinned anchor must be
    # left untouched rather than corrupted.
    foreign = PRISTINE.replace("for source in sources:", "for src in sources:")
    new_text, status = fp.apply_ranking_patch(foreign)
    assert status == "skipped"
    assert new_text == foreign


def test_patched_body_ranks_best_first():
    """Execute the patched episode_streams to prove best-first + dedupe order."""
    patched, _ = fp.apply_ranking_patch(PRISTINE)

    # Build a runnable stand-in class exposing only what the method touches.
    ns: dict = {}
    src = (
        "from typing import Iterator\n"
        "class Server: pass\n"
        "class EpisodeStreamsParams: pass\n"
        "def debug_provider(f): return f\n"
        "class logger:\n"
        "    @staticmethod\n"
        "    def error(*a, **k): pass\n"
        "extract_server = None\n"  # patched-in below via a fake module
        "class AllAnime:\n" + patched
    )
    # `from .extractors import extract_server` inside the method needs a real
    # module; inject a fake that echoes the source's sourceName.
    import sys
    import types

    fake_extractors = types.ModuleType("_fake_extractors")
    fake_extractors.extract_server = lambda client, ep, episode, source: source.get(
        "sourceName"
    )
    # Rewrite the relative import to the fake module name.
    src = src.replace(
        "from .extractors import extract_server",
        "from _fake_extractors import extract_server",
    )
    sys.modules["_fake_extractors"] = fake_extractors
    try:
        exec(compile(src, "<patched>", "exec"), ns)
        AllAnime = ns["AllAnime"]
        inst = AllAnime()
        inst.client = None
        inst._get_episode_payload = lambda params: {
            "sourceUrls": [
                {"sourceName": "Mp4-upload", "priority": 4.0},
                {"sourceName": "Mp4-upload", "priority": 4.0},  # dup -> dropped
                {"sourceName": "Yt-mp4", "priority": 7.9},
                {"sourceName": "Default", "priority": 5.5},
                {"sourceName": "NoPrio"},  # missing priority -> 0.0, last
            ]
        }

        class P:
            episode = "9"
            translation_type = "sub"

        assert list(inst.episode_streams(P())) == [
            "Yt-mp4",
            "Default",
            "Mp4-upload",
            "NoPrio",
        ]
    finally:
        sys.modules.pop("_fake_extractors", None)
