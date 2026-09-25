"""Screenshot every run's page at the widths the comparison is judged at.

Usage: uv run notes/arrangement-eval/shoot.py .tmp/arrangement-eval/runs/<batch>

For each run and phase, serves the phase's page with the arm's own launcher (under the
run's state home, so no claim reaches this machine's pages) and captures, into
<run>/shots/:

- p<phase>-laptop-<k>.png   1440×900
- p<phase>-narrow-<k>.png   900×900, the width the standing preference names
- p<phase>-phone-<k>.png    390×844

where <k> counts screens down the page: the viewport as first seen, then scrolled by
85% of the window each time, up to eight screens. Scrolling the window rather than
resizing it to the content keeps a layout that holds the window at its real size and
shows the fixed chrome where a reader meets it. What scrolls inside a region is shown
as first drawn.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

batch = Path(sys.argv[1]).resolve()
WIDTHS = {"laptop": (1440, 900), "narrow": (900, 900), "phone": (390, 844)}


def serve(payload: Path, page: Path, state: Path) -> str:
    env = {**os.environ, "XDG_STATE_HOME": str(state)}
    out = subprocess.run(
        [str(payload / "bin/leaf"), "server", "start", "--standing", str(page)],
        capture_output=True, text=True, env=env, check=True,
    ).stdout
    return re.search(r"https?://\S+", out)[0]


def stop(payload: Path, page: Path, state: Path) -> None:
    env = {**os.environ, "XDG_STATE_HOME": str(state)}
    subprocess.run([str(payload / "bin/leaf"), "server", "stop", str(page)],
                   capture_output=True, env=env)


def settle(tab) -> None:
    tab.wait_for_function("document.body.hasAttribute('data-lf-presented')", timeout=30000)
    tab.wait_for_timeout(600)


with sync_playwright() as p:
    browser = p.chromium.launch()
    for run in sorted(d for d in batch.iterdir() if d.is_dir()):
        prompt = (run / "prompt-1.txt").read_text()
        payload = Path(re.search(r"instructions are in (\S+)/skills/leaf/SKILL\.md", prompt)[1])
        shots = run / "shots"
        shots.mkdir(exist_ok=True)
        for phase, page in ((1, run / "page-phase1"), (2, run / "page")):
            if not (page / "index.html").exists():
                continue
            url = serve(payload, page, run / "state")
            try:
                for name, (w, h) in WIDTHS.items():
                    ctx = browser.new_context(
                        viewport={"width": w, "height": h},
                        device_scale_factor=1,
                        is_mobile=name == "phone",
                        has_touch=name == "phone",
                    )
                    tab = ctx.new_page()
                    tab.goto(url)
                    settle(tab)
                    height = tab.evaluate("document.documentElement.scrollHeight")
                    step = int(h * 0.85)
                    for k in range(min(8, 1 + max(0, height - h + step - 1) // step)):
                        tab.evaluate(f"window.scrollTo(0, {k * step})")
                        tab.wait_for_timeout(250)
                        tab.screenshot(path=shots / f"p{phase}-{name}-{k}.png")
                    ctx.close()
            finally:
                stop(payload, page, run / "state")
        print(run.name, "shot")
    browser.close()
