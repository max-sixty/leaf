"""Grade an authored page by whether every widget it placed, in the page or in a
thread's markup, draws.

A Promptfoo `python` assertion for short authoring cases. It reads the executor's
final `page check --render` on the saved page, which runs the page and opens every
thread whose messages carry markup (`render_gate/readings.thread_findings`), and
counts the findings that say a widget or the page's code failed rather than how the
page lays out. It also reads each `page check` the author ran, in order, for the
same findings, so a run tells what the author wrote that failed to draw, whether a
check it ran said so, and whether the page it left still fails.

The assertion passes when the final render check reports no such failure. Its
metadata carries every failure with the check that reported it and the tags each
part of the page placed, so a run's failure rate per widget kind reads from
`results.json` with no model in the loop.
"""

import json
import re
from pathlib import Path

from leaf_dev.authoring_eval import leaf_command

# The findings that say something failed to run or draw, as opposed to the geometry
# and wording readings: what the runtime posts as the page's `error` (a widget
# failing soft, an uncaught exception), a module that never upgraded, a render that
# threw, and a browser run that never reached a stage.
FAILED = {
    "browser-error",
    "console-error",
    "gate-failed",
    "missing-upgrades",
    "never-upgraded",
    "not-ready",
    "page-exception",
    "page-report",
    "render-threw",
    "window-error",
}
TAG = re.compile(r"<(lf-[a-z0-9-]+)")
FAILED_WIDGET = re.compile(r"<(lf-[a-z0-9-]+)[^>]*> failed")


def reading(text: str) -> dict | None:
    """The JSON document a `page check` printed, wherever its output holds one."""
    start = text.find('{"status"')
    if start < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(text[start:])[0]
    except ValueError:
        return None


def failures(document: dict | None) -> list[dict]:
    if document is None:
        return []
    return [
        {
            "code": finding["code"],
            "widget": (found[1] if (found := FAILED_WIDGET.search(text)) else None),
            "text": text[:600],
        }
        for finding in document.get("findings", [])
        # An author may reshape the output, as with jq, before the trace sees it.
        if isinstance(finding, dict)
        and finding.get("code") in FAILED
        and (text := finding.get("text") or json.dumps(finding.get("values", {})))
    ]


def placed(page: Path) -> dict:
    """The widget tags in the final page and in each message's markup."""
    html = (page / "index.html").read_text() if (page / "index.html").is_file() else ""
    messages = []
    log = page / "events.jsonl"
    if log.is_file():
        for line in log.read_text().splitlines():
            event = json.loads(line)
            if event.get("markup"):
                messages.append(sorted(set(TAG.findall(event["markup"]))))
    return {"page": sorted(set(TAG.findall(html))), "messages": messages}


def get_assert(output: str, context: dict) -> dict:
    response = context["providerResponse"]
    if response.get("error"):
        return {"pass": False, "score": 0.0, "reason": f"unscored: {response['error']}"}
    metadata = response["metadata"]
    final = reading(metadata["check_output"]["render"])
    if final is None:
        return {
            "pass": False,
            "score": 0.0,
            "reason": "unscored: the final render check printed no reading",
        }
    session = []
    for index, entry in enumerate(metadata["check_log"]):
        if "output" not in entry:
            continue
        command = leaf_command(entry["input"])
        found = failures(reading(entry["output"]))
        session.append(
            {
                "call": index,
                "render": "--render" in command,
                "status": (reading(entry["output"]) or {}).get("status"),
                "failures": found,
            }
        )
    final_failures = failures(final)
    passed = not final_failures
    drawn = placed(Path(metadata["work"]) / "page")
    return {
        "pass": passed,
        "score": float(passed),
        "reason": (
            "every widget drew"
            if passed
            else "; ".join(f"{f['code']}: {f['text'][:160]}" for f in final_failures)
        ),
        "metadata": {
            "draw_failures": {
                "final": final_failures,
                "final_browser": final.get("browser"),
                "session": session,
                "placed": drawn,
            }
        },
    }
