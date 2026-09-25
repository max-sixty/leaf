"""Score every run in a batch: the trace, the page's CSS and vocabulary, and the gate.

Usage: uv run notes/arrangement-eval/score.py .tmp/arrangement-eval/runs/<batch> [--no-gate]

For each run directory (<subject>-<arm>-<n>) and each phase (1: the first page,
2: after the standing preference), it records:

- the agent's cost: turns, output tokens, cost in dollars, wall time;
- iterations: how many times it ran `version check`, how many with `--render`, how many
  of those exited non-zero, and how many times it wrote or edited the page;
- what it read: the references and registry lookups in its trace;
- what it wrote: page CSS (non-blank lines of <style> and page/*.css; style
  attributes counted apart), page JavaScript, and each arrangement term it used;
- the gate: an independent `version check --render` on the phase's page, run with the
  arm's own launcher, and whether it passed.

Writes <batch>/scores.json and prints one table row per run and phase.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

batch = Path(sys.argv[1]).resolve()
gate = "--no-gate" not in sys.argv
arms_dir = None

VOCAB = {
    "lf-grid": r"<lf-grid\b",
    "lf-workspace": r"<lf-workspace\b",
    "lf-pane": r"<lf-pane\b",
    "data-width": r"\bdata-width=",
    "panel": r"class=\"[^\"]*\bpanel\b",
    "sidebar": r"class=\"[^\"]*\bsidebar\b",
    "sidenote": r"class=\"[^\"]*\bsidenote\b",
    "data-bound": r"\bdata-bound=",
    "lf-tabs": r"<lf-tabs\b",
}


def trace(stream: Path) -> dict:
    if not stream.exists():
        return {"missing": True}
    calls, results, reads, result, memory = {}, {}, [], {}, False
    for line in stream.read_text().splitlines():
        d = json.loads(line)
        if d.get("type") == "result":
            result = d
        # A child that loaded auto-memory read the user's notes, so the run is void.
        if d.get("type") == "system" and d.get("memory_paths"):
            memory = True
        if not isinstance(d.get("message"), dict):
            continue
        for block in (d.get("message") or {}).get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                calls[block["id"]] = block
            elif block.get("type") == "tool_result":
                results[block["tool_use_id"]] = block
    checks = renders = refused = writes = 0
    for cid, call in calls.items():
        name, inp = call["name"], call.get("input", {})
        if name == "Bash":
            cmd = inp.get("command", "")
            if "version check" in cmd and "--help" not in cmd:
                checks += 1
                renders += "--render" in cmd
                # The exit status is often masked by a pipe or a chained command, so
                # read the check's own verdict mark. A `| tail` that cuts the mark off
                # hides a failure, so this is a floor.
                out = results.get(cid, {}).get("content")
                out = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
                refused += "✗" in out
            elif "index.html" in cmd and re.search(
                r"-pi\b|sed -i|write_text|open\([^)]*['\"]w|>\s*\S*index\.html", cmd
            ):
                writes += 1
            reads += re.findall(r"references/[\w-]+\.md", cmd)
            reads += [f"registry:{k}" for k in re.findall(r'\.\["([^"]+)"\]', cmd)]
        elif name == "Read":
            reads.append(Path(inp.get("file_path", "")).name)
        elif name in ("Write", "Edit") and "index.html" in inp.get("file_path", ""):
            writes += 1
    usage = result.get("usage", {})
    return {
        "memory": memory,
        "turns": result.get("num_turns"),
        "is_error": result.get("is_error"),
        "cost_usd": round(result.get("total_cost_usd", 0), 2),
        "minutes": round(result.get("duration_ms", 0) / 60000, 1),
        "output_tokens": usage.get("output_tokens"),
        "checks": checks,
        "renders": renders,
        "refused": refused,
        "page_writes": writes,
        "reads": sorted(set(reads)),
        "reply": (result.get("result") or "")[-300:],
    }


def page_css(html: str, page: Path | None) -> dict:
    styles = re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)
    css_lines = [l for s in styles for l in s.splitlines() if l.strip()]
    inline = re.findall(r'\sstyle="[^"]*"', html)
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)
    js_lines = [l for s in scripts for l in s.splitlines() if l.strip()]
    linked = 0
    if page and (page / "page").is_dir():
        for f in (page / "page").rglob("*.css"):
            linked += sum(1 for l in f.read_text().splitlines() if l.strip())
        for f in (page / "page").rglob("*.js"):
            js_lines += [l for l in f.read_text().splitlines() if l.strip()]
    return {
        "css_lines": len(css_lines) + linked,
        "css_bytes": sum(len(s) for s in styles),
        "style_attrs": len(inline),
        "js_lines": len(js_lines),
        "vocab": {k: len(re.findall(p, html)) for k, p in VOCAB.items() if re.search(p, html)},
    }


def run_gate(payload: Path, page: Path, state: Path) -> dict:
    env = {"XDG_STATE_HOME": str(state), "PATH": "/usr/bin:/bin:/opt/homebrew/bin"}
    import os

    env = {**os.environ, **env}
    proc = subprocess.run(
        [str(payload / "bin/leaf"), "version", "check", str(page), "--render"],
        capture_output=True,
        text=True,
        env=env,
        timeout=900,
    )
    out = proc.stdout + proc.stderr
    return {"passed": proc.returncode == 0, "output": out[-4000:]}


def phase_page(run: Path, phase: int) -> Path | None:
    page = run / "page"
    if not (page / "index.html").exists():
        return None
    if phase == 2:
        return page
    first = run / "phase1.html"
    if not first.exists():
        return None
    copy = run / "page-phase1"
    if not copy.exists():
        shutil.copytree(page, copy, ignore=shutil.ignore_patterns("service.json", "*.lock"))
        (copy / "index.html").write_text(first.read_text())
    return copy


rows = []
for run in sorted(p for p in batch.iterdir() if p.is_dir()):
    subject, arm, n = run.name.rsplit("-", 2)
    prompt = (run / "prompt-1.txt").read_text()
    payload = Path(re.search(r"instructions are in (\S+)/skills/leaf/SKILL\.md", prompt)[1])
    for phase in (1, 2):
        row = {"subject": subject, "arm": arm, "n": int(n), "phase": phase}
        row["trace"] = trace(run / f"stream-{phase}.jsonl")
        page = phase_page(run, phase)
        if page is None:
            row["page"] = None
        else:
            html = (page / "index.html").read_text()
            row["page"] = page_css(html, page)
            if gate:
                cached = run / f"gate-{phase}.json"
                if not cached.exists():
                    cached.write_text(json.dumps(run_gate(payload, page, run / "state")))
                row["gate"] = json.loads(cached.read_text())
        rows.append(row)

(batch / "scores.json").write_text(json.dumps(rows, indent=2))
head = f"{'run':24} ph gate turns $    min chk rnd ref wr css js  vocab"
print(head)
for r in rows:
    t, p = r["trace"], r["page"] or {}
    g = r.get("gate", {})
    print(
        f"{r['subject'] + '-' + r['arm'] + '-' + str(r['n']):24} {r['phase']}"
        f"{'M' if t.get('memory') else ' '} "
        f"{('pass' if g.get('passed') else 'FAIL') if g else '  - ':4} "
        f"{t.get('turns') or 0:5} {t.get('cost_usd') or 0:4.1f} {t.get('minutes') or 0:4.0f} "
        f"{t.get('checks', 0):3} {t.get('renders', 0):3} {t.get('refused', 0):3} "
        f"{t.get('page_writes', 0):2} {p.get('css_lines', 0):3} {p.get('js_lines', 0):3} "
        f"{p.get('vocab', {})}"
    )
