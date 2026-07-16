#!/usr/bin/env python3
"""Measure time-to-playback for a provider's episode_streams.

This is the re-measurement harness for the "top speed watching" work. It times
two things against a real provider on your own connection:

  * time-to-first-server  — how long until the FIRST (best-ranked) server is
    ready. This is what Optimization A launches on, so it approximates
    time-to-playback.
  * time-to-full-list      — how long to resolve EVERY server (the old
    behaviour, which used to block the mpv spawn).

It also prints the servers in the order the provider yields them, so you can
confirm the best-first ranking (highest-priority / best-quality first).

Usage (run with the Python that has ani-browse installed):
    python scripts/probe_launch_timing.py --provider allanime --query "frieren" --episode 1
    python scripts/probe_launch_timing.py --provider animepahe --query "one piece" --episode 1 --index 0

Notes:
  * TLS verification is disabled (the shell env often lacks a CA bundle; the real
    app is unaffected). This is a diagnostic, not production code.
  * A title can have several search hits; use --index to pick a different one
    (the hits are printed first). anime ids expire, so it always live-searches.
"""

from __future__ import annotations

import argparse
import sys
from time import perf_counter

# Japanese titles break cp1252 stdout on Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001
    pass

PROVIDERS = {
    "allanime": ("viu_media.libs.provider.anime.allanime.provider", "AllAnime"),
    "animepahe": ("viu_media.libs.provider.anime.animepahe.provider", "AnimePahe"),
    "animeunity": ("viu_media.libs.provider.anime.animeunity.provider", "AnimeUnity"),
}


def _make_provider(name: str):
    import httpx

    from viu_media.libs.provider.anime.params import SearchParams  # noqa: F401

    module_name, cls_name = PROVIDERS[name]
    module = __import__(module_name, fromlist=[cls_name])
    client = httpx.Client(verify=False, timeout=25, follow_redirects=True)
    return getattr(module, cls_name)(client)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--provider", choices=list(PROVIDERS), default="allanime")
    ap.add_argument("--query", required=True, help="title to search for")
    ap.add_argument("--episode", default="1", help="episode number (default 1)")
    ap.add_argument("--translation", choices=["sub", "dub"], default="sub")
    ap.add_argument(
        "--index", type=int, default=0, help="which search hit to use (default 0)"
    )
    args = ap.parse_args()

    from viu_media.libs.provider.anime.params import (
        EpisodeStreamsParams,
        SearchParams,
    )

    provider = _make_provider(args.provider)

    print(f"Searching {args.provider} for {args.query!r} ...")
    results = provider.search(
        SearchParams(query=args.query, translation_type=args.translation)
    )
    hits = list(getattr(results, "results", []) or [])
    if not hits:
        print("No search results.")
        return 1
    for i, h in enumerate(hits[:10]):
        eps = getattr(getattr(h, "episodes", None), args.translation, []) or []
        mark = " <-- using" if i == args.index else ""
        print(f"  [{i}] {h.title}  (id={h.id}, {len(eps)} {args.translation} eps){mark}")
    if args.index >= len(hits):
        print(f"--index {args.index} out of range")
        return 1
    anime = hits[args.index]

    print(f"\nResolving episode {args.episode} ...")
    t0 = perf_counter()
    iterator = provider.episode_streams(
        EpisodeStreamsParams(
            anime_id=anime.id,
            query=args.query,
            episode=args.episode,
            translation_type=args.translation,
        )
    )
    if iterator is None:
        print("Provider returned no iterator (no streams).")
        return 1

    first = next(iter(iterator), None)
    t_first = perf_counter() - t0
    if first is None:
        print("No servers resolved.")
        return 1
    rest = list(iterator)
    t_full = perf_counter() - t0

    servers = [first] + rest

    def _q(s) -> str:
        return "/".join(str(link.quality) for link in s.links) or "?"

    print("\n--- ranking (order the provider yielded) ---")
    for i, s in enumerate(servers):
        tag = "  <-- launched (best-first)" if i == 0 else ""
        print(f"  {i + 1}. {s.name}  quality={_q(s)}{tag}")

    print("\n--- timing ---")
    print(f"  time-to-first-server : {t_first * 1000:7.0f} ms   (Optimization A launch)")
    print(f"  time-to-full-list    : {t_full * 1000:7.0f} ms   (old blocking resolve)")
    saved = (t_full - t_first) * 1000
    print(f"  moved off launch path: {saved:7.0f} ms   ({len(servers)} servers total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
