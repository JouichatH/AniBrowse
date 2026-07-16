#!/usr/bin/env python3
"""Measure how much opening/ending skip adds to the LAUNCH path.

Since Phase 4, AniSkip is fetched in a background thread and delivered to the
player via a file, so turning skip on should no longer block the mpv spawn. This
probe quantifies that:

  * _with_skip OFF  — both toggles off; the function returns the params untouched.
  * _with_skip ON   — toggles on; the function writes the skip file and spawns the
    background fetch thread, then returns. This is the ACTUAL latency skip adds to
    the launch path (it does NOT wait for the network).
  * (optional) the background AniSkip fetch itself — what USED to sit on the
    launch path before Phase 4. Off the critical path now, but shown for contrast.

Usage (run with the Python that has ani-browse installed):
    python scripts/probe_skip_latency.py
    python scripts/probe_skip_latency.py --iters 3000
    python scripts/probe_skip_latency.py --fetch --mal-id 52991 --episode 1
"""

from __future__ import annotations

import argparse
import statistics
import sys
import tempfile
from time import perf_counter

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001
    pass


class _Media:
    """A media item with a MAL id (so the ON path spawns the fetch thread)."""

    def __init__(self, mal_id):
        self.id_mal = mal_id


def _time_with_skip(svc, params, media, iters):
    # One warm-up (first call imports/creates the cache dir etc.).
    svc._with_skip(params, media)
    samples = []
    for _ in range(iters):
        t0 = perf_counter()
        svc._with_skip(params, media)
        samples.append((perf_counter() - t0) * 1e6)  # microseconds
    samples.sort()
    return samples


def _report(label, samples):
    med = statistics.median(samples)
    mean = statistics.fmean(samples)
    p95 = samples[min(len(samples) - 1, int(len(samples) * 0.95))]
    print(f"  {label:<28} median={med:8.1f} us   mean={mean:8.1f} us   p95={p95:8.1f} us")
    return med


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=2000)
    ap.add_argument("--mal-id", type=int, default=52991, help="MAL id for the ON path")
    ap.add_argument("--episode", default="1")
    ap.add_argument(
        "--fetch",
        action="store_true",
        help="also time the real AniSkip network fetch (the backgrounded cost)",
    )
    args = ap.parse_args()

    from viu_media.cli.service.player import service as service_mod
    from viu_media.cli.service.player.service import PlayerService
    from viu_media.core.config import AppConfig
    from viu_media.libs.player.params import PlayerParams

    # Keep the probe from touching the real app cache.
    tmp = tempfile.mkdtemp()
    service_mod._skip_json_path = lambda: f"{tmp}/skip.json"  # type: ignore[assignment]

    params = PlayerParams(url="u", title="t", query="q", episode=args.episode)
    media = _Media(args.mal_id)

    def _svc(opening, ending):
        cfg = AppConfig()
        cfg.stream.opening_skip = opening
        cfg.stream.ending_skip = ending
        return PlayerService(cfg, provider=None)  # type: ignore[arg-type]

    print(f"Timing _with_skip over {args.iters} iterations (launch-path cost):\n")
    off = _time_with_skip(_svc(False, False), params, media, args.iters)
    on = _time_with_skip(_svc(True, True), params, media, args.iters)
    med_off = _report("skip OFF (both toggles)", off)
    med_on = _report("skip ON  (both toggles)", on)
    print(f"\n  => skip adds ~{med_on - med_off:.1f} us to the launch path "
          f"({(med_on - med_off) / 1000:.3f} ms)")

    if args.fetch:
        from viu_media.cli.service.player.aniskip import fetch_skip_times

        print(f"\nBackground AniSkip fetch (mal_id={args.mal_id}, ep {args.episode}) "
              "— off the critical path since Phase 4:")
        t0 = perf_counter()
        intervals = fetch_skip_times(args.mal_id, args.episode)
        dt = (perf_counter() - t0) * 1000
        kinds = ",".join(i.kind for i in intervals) or "none"
        print(f"  fetch took {dt:.0f} ms   (intervals: {kinds})")
        print("  ^ this is what USED to block the mpv spawn before Phase 4.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
