"""Developer tooling checks; run explicitly from dev/tests."""

import json
import subprocess

from conftest import LEAF_COMMAND
from leaf_dev import draw_failures

# A control whose value lies outside its range, which plain `page check` leaves
# undrawn, and a thread message whose chart body throws, which it never opens.
PAGE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Control</title></head>
<body>
<main>
<h1>Control page</h1>
<lf-playground id="pg">
  <lf-playground-control name="radius" label="Corner radius" kind="range" value="40" min="0" max="24" step="1" unit="px"></lf-playground-control>
  <lf-playground-preview><p>Preview</p></lf-playground-preview>
  <lf-playground-output>Radius {radius}</lf-playground-output>
</lf-playground>
</main>
</body>
</html>
"""
# Written to the log directly, since `thread create` draws a chart before posting
# and refuses this one.
MESSAGE = {
    "kind": "comment",
    "author": "agent",
    "agent": "Claude",
    "session": "control",
    "revision": 1,
    "text": "Which fix first?",
    "markup": '<lf-chart id="bad"><pre>{marks: [Plot.lineY([1, 2, 3], {x: nosuchvar})]}</pre></lf-chart>',
    "id": "c58f503e",
    "attention": False,
    "ts": "2026-10-24T22:04:00.076-07:00",
}


def check(page, *flags):
    return subprocess.run(
        [*LEAF_COMMAND, "page", "check", str(page), *flags],
        capture_output=True,
        text=True,
        check=False,
    )


def test_grader_reports_widgets_plain_check_passes(
    initialized_page, headless_shell, tmp_path
):
    """The grader reads failures from the final `--render`, which draws the page's
    widgets and opens each thread holding markup, so it reports both widgets here
    that plain `page check` passes without a browser."""
    page = initialized_page(tmp_path / "page", ("playground",))
    (page / "index.html").write_text(PAGE)
    (page / "events.jsonl").write_text(json.dumps(MESSAGE) + "\n")

    plain = json.loads(check(page).stdout)
    assert (plain["status"], plain["browser"]) == (0, None), plain

    rendered = check(page, "--render")
    context = {
        "providerResponse": {
            "metadata": {
                "check_output": {"render": rendered.stdout},
                "check_log": [],
                "work": str(tmp_path),
            }
        }
    }
    graded = draw_failures.get_assert("", context)
    assert not graded["pass"], graded
    found = graded["metadata"]["draw_failures"]
    assert {failure["widget"] for failure in found["final"]} >= {
        "lf-playground",
        "lf-chart",
    }, found["final"]
    assert any(
        "control radius has a value outside its range" in failure["text"]
        for failure in found["final"]
    )
    assert found["placed"]["messages"] == [["lf-chart"]]
