"""V8 CPU profiles of a page, recorded and read the same way by every command that
says where a page's time went: `bench-latency --profile` and `scaling --profile`.

`cpu_profile` records one into a `.cpuprofile` file, which DevTools and Perfetto
read too, and `Profile` reads one back as samples, each with its time and the chain of
functions above it. A function is named by its name, its file and its line, so the
same function keeps its name across profiles, revisions and arms.
"""

import json
import math
from collections import Counter
from contextlib import contextmanager
from itertools import pairwise
from pathlib import Path

from playwright.sync_api import Page

# How often V8 samples the stack, in microseconds. Sampling slows the page, so read
# proportions from a profile and durations from a run without one.
INTERVAL_US = 100
# Frames that say nothing about which runtime code ran: the sampler's own states.
OPAQUE = (
    "(root)",
    "(program)",
    "(idle)",
    "(garbage collector)",
)


@contextmanager
def cpu_profile(page: Page, path: Path):
    """Record a V8 CPU profile of `page`'s renderer for the life of the block, and
    write it to `path` as the block ends. Chromium only: Firefox has no V8, and
    `leaf_dev.commands.scaling`'s header says how to profile it."""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Profiler.enable")
    cdp.send("Profiler.setSamplingInterval", {"interval": INTERVAL_US})
    cdp.send("Profiler.start")
    try:
        yield
    finally:
        path.write_text(json.dumps(cdp.send("Profiler.stop")["profile"]))
        cdp.detach()


class Profile:
    """One CPU profile, read from the file `cpu_profile` wrote: each sample's time and
    the chain of frames above it."""

    def __init__(self, path: Path):
        profile = json.loads(path.read_text())
        nodes = {n["id"]: n for n in profile["nodes"]}
        parent = {c: n["id"] for n in profile["nodes"] for c in n.get("children", ())}

        def label(node_id):
            frame = nodes[node_id]["callFrame"]
            where = frame["url"].rsplit("/", 1)[-1]
            return (
                f"{frame['functionName'] or '(anon)'} {where}:{frame['lineNumber'] + 1}"
            )

        self.samples = []  # (timestamp µs, duration µs, frames leaf-first)
        at = profile["startTime"]
        deltas = profile["timeDeltas"]
        for sample, (delta, following) in zip(
            profile["samples"], pairwise([*deltas, 0]), strict=True
        ):
            at += delta
            chain, node_id = [], sample
            while node_id is not None:
                chain.append(label(node_id))
                node_id = parent.get(node_id)
            self.samples.append((at, following, chain))

    def dominant(self, lo: float, hi: float, count: int = 2) -> list:
        """The runtime call paths holding most samples between lo and hi."""
        paths = Counter()
        for at, _, chain in self.samples:
            if lo <= at < hi:
                named = [f for f in reversed(chain) if not f.startswith(OPAQUE)]
                paths[" > ".join(named[:3]) or chain[0]] += 1
        return [path for path, _ in paths.most_common(count)]

    def functions(
        self, lo: float = -math.inf, hi: float = math.inf
    ) -> tuple[Counter, Counter]:
        """Each function's own and inclusive µs between lo and hi, the whole profile
        by default. A sample counts once toward each function on its stack, so a
        recursive function's inclusive time is never counted twice."""
        own, inclusive = Counter(), Counter()
        for at, duration, chain in self.samples:
            if lo <= at < hi and not chain[0].startswith(OPAQUE[:3]):
                own[chain[0]] += duration
                for frame in set(chain) - {"(root) :0"}:
                    inclusive[frame] += duration
        return own, inclusive
