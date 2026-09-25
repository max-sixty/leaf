"""Aggregate a batch's scores and reviews into per-subject, per-arm tables.

Usage: python3 notes/arrangement-eval/summarize.py .tmp/arrangement-eval/runs/<batch>

Reads <batch>/scores.json (score.py) and both review passes (review.py) and prints
Markdown: for each subject and phase, each arm's median turns, cost, checks run, checks
that reported a failure, CSS and JavaScript lines, and gate passes; then, per pair,
which arm the blind reviewer picked in both passes, overall and at each width, and how
often it judged each arm to honour the preference. Runs whose trace loaded auto-memory
are dropped.
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

print()
print("| arm | phase | turns | $ | CSS lines | JS lines | ✗ reports |")
print("|---|---|---|---|---|---|---|")
for arm in ("leaf", "plain"):
    for phase in (1, 2):
        rs = [r for r in rows if r["arm"] == arm and r["phase"] == phase]
        print(f"| {arm} | {phase} | {sum(r['trace']['turns'] for r in rs)} "
              f"| {sum(r['trace']['cost_usd'] for r in rs):.2f} "
              f"| {sum((r['page'] or {}).get('css_lines', 0) for r in rs)} "
              f"| {sum((r['page'] or {}).get('js_lines', 0) for r in rs)} "
              f"| {sum(r['trace']['refused'] for r in rs)} |")


def outcomes(folder: str) -> dict:
    """Each pair's pick in one review pass: the arm, 'tie', or None when discarded."""
    picks = {}
    for f in (batch / folder).glob("*.json"):
        r = json.loads(f.read_text())
        v = r["verdict"]
        names = {"A": r["A"], "B": r["B"], "tie": "tie"}
        picks[(r["subject"], r["phase"], r["n"])] = v and {
            "overall": names[v["winner"]],
            **{w: names.get(x, x) for w, x in (v.get("by_width") or {}).items()},
            **({"pref " + names[k]: bool(x) for k, x in v["preference"].items() if k in "AB"}
               if v.get("preference") else {}),
        }
    return picks


# A pair counts for an arm only when both passes, one with each arm as page A, pick it;
# a pair the passes disagree on, or either calls a tie, is a split.
first, second = outcomes("reviews"), outcomes("reviews-flip")
tally = defaultdict(Counter)
for key in sorted(first.keys() | second.keys()):
    a, b = first.get(key), second.get(key)
    cell = tally[key[:2]]
    if not (a and b):
        cell["discarded"] += 1
        continue
    for field in ("overall", "laptop", "narrow", "phone"):
        cell[f"{field} " + (a[field] if a[field] == b[field] != "tie" else "split")] += 1
    for arm in ("leaf", "plain"):
        cell[f"pref {arm}"] += a.get(f"pref {arm}", False) + b.get(f"pref {arm}", False)
print()
print("Pairs won in both passes, leaf/plain/split:")
print()
print("| subject | phase | overall | 1440px | 900px | 390px | preference met, leaf and plain, of 2 per pair | discarded |")
print("|---|---|---|---|---|---|---|---|")
for (subject, phase), c in sorted(tally.items()):
    def trio(prefix):
        return f"{c[prefix + ' leaf']}/{c[prefix + ' plain']}/{c[prefix + ' split']}"
    pairs = sum(c[f"overall {x}"] for x in ("leaf", "plain", "split"))
    pref = f"{c['pref leaf']}/{2 * pairs}, {c['pref plain']}/{2 * pairs}" if phase == 2 else ""
    print(f"| {subject} | {phase} | {trio('overall')} | {trio('laptop')} | {trio('narrow')} "
          f"| {trio('phone')} | {pref} | {c['discarded']} |")
