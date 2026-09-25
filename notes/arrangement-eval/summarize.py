"""Aggregate a batch's scores and reviews into per-subject, per-arm tables.

Usage: python3 notes/arrangement-eval/summarize.py .tmp/arrangement-eval/runs/<batch>

Reads <batch>/scores.json (score.py) and <batch>/reviews/*.json (review.py) and prints
Markdown: for each subject and phase, each arm's median turns, cost, checks run, checks
that reported a failure, CSS and JavaScript lines, and gate passes; then the blind
reviewer's overall and layout-only picks, and how often each arm honoured the preference.
Runs whose trace loaded auto-memory are dropped.
"""

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

batch = Path(sys.argv[1])
rows = [r for r in json.loads((batch / "scores.json").read_text())
        if not r["trace"].get("memory") and not r["trace"].get("is_error")]
cells = defaultdict(list)
for r in rows:
    cells[(r["subject"], r["phase"], r["arm"])].append(r)


def med(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else float("nan")


print("| subject | phase | arm | n | gate pass | turns | $ | checks | ✗ reports | CSS lines | JS lines |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for (subject, phase, arm), rs in sorted(cells.items()):
    t = [r["trace"] for r in rs]
    p = [r["page"] or {} for r in rs]
    passed = sum(bool(r.get("gate", {}).get("passed")) for r in rs)
    print(
        f"| {subject} | {phase} | {arm} | {len(rs)} | {passed}/{len(rs)} "
        f"| {med([x['turns'] for x in t]):g} | {med([x['cost_usd'] for x in t]):.2f} "
        f"| {med([x['checks'] for x in t]):g} | {med([x['refused'] for x in t]):g} "
        f"| {med([x.get('css_lines') for x in p]):g} | {med([x.get('js_lines') for x in p]):g} |"
    )

reviews = [json.loads(f.read_text()) for f in sorted(batch.glob("reviews*/*.json"))]
tally = defaultdict(Counter)
for r in reviews:
    v = r["verdict"]
    if not v:
        continue
    name = {"A": r["A"], "B": r["B"], "tie": "tie"}
    key = (r["subject"], r["phase"])
    tally[key]["overall " + name[v["winner"]]] += 1
    tally[key]["layout " + name.get(v.get("layout_winner"), "?")] += 1
    for width, pick in (v.get("by_width") or {}).items():
        tally[key][f"{width} {name.get(pick, '?')}"] += 1
    if pref := v.get("preference"):
        for side in ("A", "B"):
            tally[key][f"pref {r[side]}"] += bool(pref.get(side))
print()
print("| subject | phase | overall leaf/plain/tie | layout leaf/plain/tie | laptop | narrow | phone | preference met leaf, plain |")
print("|---|---|---|---|---|---|---|---|")
for (subject, phase), c in sorted(tally.items()):
    def trio(prefix):
        return f"{c[prefix + ' leaf']}/{c[prefix + ' plain']}/{c[prefix + ' tie']}"
    pref = f"{c['pref leaf']}, {c['pref plain']}" if phase == 2 else ""
    print(f"| {subject} | {phase} | {trio('overall')} | {trio('layout')} | {trio('laptop')} "
          f"| {trio('narrow')} | {trio('phone')} | {pref} |")
