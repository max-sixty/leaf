"""Ask a reviewer who has not seen either arm's guidance which page serves the user better.

Usage: python3 notes/arrangement-eval/review.py .tmp/arrangement-eval/runs/<batch>
       FLIP=1 python3 notes/arrangement-eval/review.py .tmp/arrangement-eval/runs/<batch>

For every subject and run number where both arms produced a page, and for each phase,
a fresh `claude -p` reads the user's request and both pages' screenshots (shoot.py)
and returns a JSON verdict. Which arm is A is fixed per pair by a hash of its name;
FLIP=1 swaps every pair's sides and writes to reviews-flip/, so the two passes together
separate the reviewer's pick of a page from its pick of a side.

The reviewer is blind to the arms: each job copies the two pages' screenshots into a
scratch directory under neutral names (A-laptop-0.png …) and the reviewer may read
only that directory, so it never sees a run's path, its HTML, the scores, or the
other pass. It runs with auto-memory off from a scratch cwd.

Writes reviews[-flip]/<subject>-<n>-p<phase>.json with the verdict, the arm behind A
and B, how many of the screenshots it read, and the raw answer. A job whose file
already holds a verdict is skipped, so a pass that stops partway resumes.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

here = Path(__file__).resolve().parent
batch = Path(sys.argv[1]).resolve()
flipped = os.environ.get("FLIP") == "1"
out = batch / ("reviews-flip" if flipped else "reviews")
out.mkdir(exist_ok=True)
WIDTHS = [("laptop", "a 1440px laptop window"), ("narrow", "a 900px window"),
          ("phone", "a 390px phone")]
PREFERENCE = (
    '"A standing preference for all my pages from now on: I read them in a window about '
    "900px wide, beside my editor. At that width, keep the page's summary, status, "
    'contents or queue beside the main content rather than stacked above or below it."'
)


def stage(run: Path, phase: int, side: str, into: Path) -> list[str]:
    """Copy one page's screenshots into `into` under neutral names; return the listing."""
    lines = []
    for key, label in WIDTHS:
        files = sorted((run / "shots").glob(f"p{phase}-{key}-*.png"),
                       key=lambda f: int(f.stem.rsplit("-", 1)[1]))
        lines.append(f"  On {label}, top to bottom:")
        for k, f in enumerate(files):
            target = into / f"{side}-{key}-{k}.png"
            shutil.copyfile(f, target)
            lines.append(f"    {target}")
    return lines


def prompt(subject: str, a: list[str], b: list[str], phase: int) -> str:
    request = (here / "subjects" / f"{subject}.md").read_text()
    revised = (
        f"\nAfter the first version, the user added this standing preference, and both "
        f"pages below were revised for it:\n\n{PREFERENCE}\n"
        if phase == 2 else ""
    )
    preference_field = (
        ', "preference": {"A": true|false, "B": true|false, "why": "…"}' if phase == 2 else ""
    )
    return f"""Two pages were built for the same user request. You have not seen how either
was made, and you judge only what the user sees. Both run inside the same page viewer:
the bar fixed across the top, the shortcut band at the foot, and the column of small
markers at the right edge are the viewer's, identical on both, and not part of either
page. A region with a scroll of its own shows only its first screen here; in the real
page the user can scroll it, so judge whether what it shows first is the right part and
enough of it, not whether everything inside it is visible.

The user's request:

<request>
{request}
</request>
{revised}
Read every screenshot below with the Read tool before judging; a judgment that skips
one is discarded. Each width's screens run top to bottom through the page, overlapping
a little.

Page A:
{chr(10).join(a)}

Page B:
{chr(10).join(b)}

Judge as this user: which page would they rather have for this task? Consider whether
they can find what they need at a glance, read it comfortably, and act on it, and
whether anything is cut off, overlapping, cramped, misaligned, or wasting the room,
at each width.

Reply with only a JSON object:
{{"winner": "A"|"B"|"tie", "margin": "clear"|"slight", "by_width": {{"laptop": "A"|"B"|"tie", "narrow": "A"|"B"|"tie", "phone": "A"|"B"|"tie"}}, "reasons": ["…", "…", "…"], "defects": {{"A": ["…"], "B": ["…"]}}{preference_field}}}"""


def review(job):
    subject, n, phase, runs = job
    done = out / f"{subject}-{n}-p{phase}.json"
    if done.exists() and json.loads(done.read_text())["verdict"]:
        return json.loads(done.read_text())
    flip = int(hashlib.sha256(f"{subject}-{n}-{phase}".encode()).hexdigest(), 16) % 2 ^ flipped
    order = ["plain", "leaf"] if flip else ["leaf", "plain"]
    with tempfile.TemporaryDirectory() as cwd, tempfile.TemporaryDirectory() as shots:
        a = stage(runs[order[0]], phase, "A", Path(shots))
        b = stage(runs[order[1]], phase, "B", Path(shots))
        expected = {Path(line.strip()).name for line in a + b if line.strip().endswith(".png")}
        proc = subprocess.run(
            ["claude", "-p", prompt(subject, a, b, phase), "--model", "claude-opus-5-5",
             "--setting-sources", "project", "--strict-mcp-config", "--tools", "Read",
             "--add-dir", shots, "--permission-mode", "bypassPermissions",
             "--output-format", "stream-json", "--verbose"],
            capture_output=True, text=True, cwd=cwd, stdin=subprocess.DEVNULL,
            env={**os.environ, "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"},
        )
    answer, read = {"is_error": True}, set()
    for line in proc.stdout.splitlines():
        d = json.loads(line)
        if d.get("type") == "result":
            answer = d
        message = d.get("message")
        for block in (message.get("content") or []) if isinstance(message, dict) else []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                read.add(Path(block["input"].get("file_path", "")).name)
    raw = answer.get("result", "")
    found = re.search(r"\{.*\}", raw, re.S)
    try:
        verdict = json.loads(found[0]) if found else None
    except json.JSONDecodeError:
        verdict = None
    unread = sorted(expected - read)
    if answer.get("is_error") or unread:
        verdict = None
    record = {"subject": subject, "n": n, "phase": phase, "A": order[0], "B": order[1],
              "is_error": answer.get("is_error"), "shots": len(expected), "unread": unread,
              "verdict": verdict, "raw": raw}
    done.write_text(json.dumps(record, indent=2))
    return record


runs = {}
for run in batch.iterdir():
    if run.is_dir() and (run / "shots").is_dir():
        subject, arm, n = run.name.rsplit("-", 2)
        runs.setdefault((subject, int(n)), {})[arm] = run
jobs = [
    (subject, n, phase, pair)
    for (subject, n), pair in sorted(runs.items())
    if {"leaf", "plain"} <= pair.keys()
    for phase in (1, 2)
    if all(list((pair[a] / "shots").glob(f"p{phase}-laptop-0.png")) for a in ("leaf", "plain"))
]
with ThreadPoolExecutor(max_workers=6) as pool:
    records = list(pool.map(review, jobs))
for r in records:
    v = r["verdict"] or {}
    names = {"A": r["A"], "B": r["B"]}
    winner = names.get(v.get("winner"), v.get("winner"))
    widths = {k: names.get(x, x) for k, x in (v.get("by_width") or {}).items()}
    pref = v.get("preference")
    pref = {r["A"]: pref["A"], r["B"]: pref["B"]} if pref else ""
    note = f" UNREAD {len(r['unread'])}/{r['shots']}" if r["unread"] else ""
    print(f"{r['subject']}-{r['n']} p{r['phase']}: {winner} ({v.get('margin')}) {widths} {pref}{note}")
