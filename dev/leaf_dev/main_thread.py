"""Native long animation frames for any page or interaction, without timing gates.

The browser reports frames of at least 50 ms and their script entry points, including
forced layout. This is a floor on work, not a CPU profile or proof which widget owns
it. Probe splits startup from its input steps; bench-latency selects its goal window.
"""

from pathlib import Path

SCRIPT = Path(__file__).with_suffix(".js")


def main_thread(frames: list[dict], start: float, end: float) -> dict:
    """Attribute long-frame work inside the benchmark's clock window.

    Forced layout has no separate timestamp, so apportion it with its script.
    """

    def inside(begin: float, ms: float) -> float:
        return max(0.0, min(end, begin + ms) - max(start, begin))

    owners: dict[str, list[float]] = {}
    render = 0.0
    for frame in frames:
        render += inside(frame["end"] - frame["render"], frame["render"])
        for script in frame["scripts"]:
            if not (ms := inside(script["start"], script["ms"])):
                continue
            spent = owners.setdefault(script["owner"], [0.0, 0.0])
            spent[0] += ms
            spent[1] += script["forced"] * ms / script["ms"]
    return {"owners": owners, "render": render}


def reading(page) -> dict:
    """Read through one completed rendering frame, then start a fresh observation.

    This lets the browser deliver the final frame's entry; it is not a settling
    delay. A caller waits for its own meaningful result before taking this reading.
    """
    measured = page.evaluate("""async () => {
      await new Promise(resolve => requestAnimationFrame(() => setTimeout(resolve, 0)));
      const result = window.__leafMainThread.reading();
      window.__leafMainThread.reset();
      return result;
    }""")
    if not measured["supported"]:
        return {"supported": False}
    frames = measured["frames"]
    attributed = main_thread(frames, float("-inf"), float("inf"))
    return {
        "long_frames": len(frames),
        "longest_frame_ms": round(
            max((f["end"] - f["start"] for f in frames), default=0), 1
        ),
        "blocking_ms": round(sum(f["blocking"] for f in frames), 1),
        "render_ms": round(attributed["render"], 1),
        "scripts": [
            {"owner": owner, "ms": round(ms, 1), "forced_layout_ms": round(forced, 1)}
            for owner, (ms, forced) in sorted(
                attributed["owners"].items(), key=lambda item: item[1][0], reverse=True
            )
        ],
    }
