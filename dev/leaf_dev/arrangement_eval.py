"""Author, revise and decide on one page-task sample under its explicit condition,
on the loop a user would run.

Leaf and ordinary HTML receive the same task in one live session (`LiveSession`),
then the same width preference as a chat message, then, where the task declares
them, the same user comment and a decision the user makes on the page. Each
sample contains only its selected condition; the HTML child sees no Leaf payload,
instructions or runtime.

- **Leaf** runs as installed: the arm is the session's plugin, hooks included. The
  agent serves the page and hands it over; the harness comments from a browser
  selection on the served page (`eval_user.comment_on_passage`), and the hook
  delivers the comment.
- **HTML** keeps chat turns, since it has no page to wait on: the comment arrives
  in chat, naming the passage in words.

The decision round is the same in both: a user agent makes the page's decision in
the browser (`eval_user.decide`), then the user asks in chat for it to be applied.
Leaf's agent reads the gestures from the page's log; HTML's user pastes what the
page offered to copy, or types the decision where it offered nothing, and so does
a Leaf user whose page took none of it. A reader then says what the agent applied,
from its answer and the page's final files, and `decision-applied` checks that
against what was chosen. On Leaf a fresh reader also reports the decision from
the page's state, without the conversation. A comment that directs an outcome is
the user's pick for that item, so recording it as chosen is correct; whether the
agent did is recorded, not checked.

Each phase records what the author spent and wrote, from the session's records
between the harness's `eval_phase` marks: time, turns, tokens and cost (`resumed`),
the CSS and script lines in the files it authored, and how many times it wrote and
rendered the page, the measure of its repair iterations. The user agent and the
readers spend too; that is the harness's, recorded apart.

The sample's output is what a judge needs: the user's request, the later messages,
the author's answer to the comment, and each version's screenshots by width,
written to `shots`, the one directory its judge may read. Capture records arrival
before inspecting task destinations, disclosures, selections and scroll regions,
on a disposable copy per viewport. Observation limits remain explicit. The YAML
cases hold the visual criteria and their three-way verdict assertion;
`eval-pairs` is the quality score, judging a pair's final versions side by side.
"""

import json
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import turbohtml
from leaf.delivery import opened_input_ids
from leaf.event_log import read_events
from leaf.harness import ClaudeCodeHarness
from leaf.passages import SourceReading
from leaf.render_checks import rendered
from leaf.schema import MESSAGE_KINDS
from leaf.service import requires_agent_attention
from leaf.structure import SourceDocument
from leaf.thread import successful_replies

from leaf_dev import ROOT, arrangement_plain
from leaf_dev.arms import (
    MODELS,
    TURN_LIMIT,
    LiveChild,
    LiveSession,
    blocks,
    completed,
    now,
    observed_sum,
    read_trace,
    resumed,
    run_agent,
    run_leaf,
    scratch,
    serving,
    trace_result,
    trace_summary,
)
from leaf_dev.browser import chrome, load, settle, tab
from leaf_dev.eval_cases import definition
from leaf_dev.eval_user import OPEN, comment_on_passage, decide, reveal

TASKS = ROOT / "evals"
DEFINITION = definition("arrangement_eval")
WIDTHS = {
    name: (tuple(width["viewport"]), width["description"])
    for name, width in DEFINITION["widths"].items()
}
PREFERENCE = DEFINITION["preference"]
# Content out of view is reachable through a labeled control, as both judges count
# it.
REACHABLE = DEFINITION["reachable"]
# How long a session that has answered stays quiet before the next phase, and how
# long the harness waits for a turn to start before calling a phase undelivered.
GRACE = 20
WAKE = 15 * 60


@dataclass(frozen=True)
class Comment:
    """The user's comment on the width-revised page, the same in both conditions.

    `target` names the passage in words, as a user writing in chat would. On Leaf the
    user selects the first of `quotes` the page draws, and otherwise comments on
    the page whole, naming the target. `applied` names a fact only the comment
    supplies, which the authored files carry once the change is made and the answer
    carries when it tells the user so."""

    target: str
    quotes: tuple[str, ...]
    text: str
    applied: str


@dataclass(frozen=True)
class Decision:
    """What the user decides on the page once it carries the comment, then asks
    the agent to apply. `task` tells the user agent what to do on the page; `typed`
    is the decision as the user types it in chat. `chosen` is what applying it
    records, item by item, each value one of the item's `values`."""

    task: str
    typed: str
    chosen: dict[str, str]
    values: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class Scenario:
    comment: Comment | None = None
    decision: Decision | None = None
    # What a reader clicks to open the item that holds the comment's passage.
    reveal: str = ""


# Each alert's candidate thresholds as the request lists them, and the user's setting.


CASES = {
    name: Scenario(
        comment=(
            Comment(**(comment | {"quotes": tuple(comment["quotes"])}))
            if (comment := case["inputs"]["comment"])
            else None
        ),
        decision=(
            Decision(
                **(
                    decision
                    | {
                        "values": {
                            item: tuple(values)
                            for item, values in decision["values"].items()
                        }
                    }
                )
            )
            if (decision := case["inputs"]["decision"])
            else None
        ),
        reveal=case["inputs"]["reveal"],
    )
    for name, case in DEFINITION["cases"].items()
}


@dataclass(frozen=True)
class Run:
    subject: str
    payload: Path
    directory: Path
    shots: Path
    harness: str = ClaudeCodeHarness.name
    condition: str = "leaf"
    phase_starts: dict = field(default_factory=dict, compare=False)

    @property
    def leaf_condition(self) -> bool:
        return self.condition == "leaf"

    @property
    def work(self) -> Path:
        return Path((self.directory / "work-dir").read_text())

    @property
    def authored_page(self) -> Path:
        return self.work / "page"

    @property
    def state(self) -> Path:
        return self.work / "state"

    def leaf(self, *args: str, **kwargs):
        return run_leaf(self.payload, self.state, *args, **kwargs)

    def page(self, phase: int) -> Path | None:
        page = self.directory / f"page-phase{phase}"
        return page if (page / "index.html").exists() else None

    def record(self, name: str, value: dict) -> None:
        (self.directory / f"{name}.json").write_text(json.dumps(value, indent=2))

    def recorded(self, name: str) -> dict:
        path = self.directory / f"{name}.json"
        return json.loads(path.read_text()) if path.exists() else {}


def phases(subject: str) -> tuple[int, ...]:
    """Authoring, the width revision, the comment and the decision, as the task has
    them."""
    scenario = CASES[subject]
    return (
        1,
        2,
        *((3,) if scenario.comment else ()),
        *((4,) if scenario.decision else ()),
    )


def first_prompt(payload: Path, page: Path, subject: str, condition="leaf") -> str:
    return DEFINITION["prompts"]["first"][condition].format(
        payload=payload,
        page=page,
        request=(TASKS / subject / "request.md").read_text(),
    )


def preference_message() -> str:
    return DEFINITION["prompts"]["preference"].format(preference=PREFERENCE)


def comment_message(comment: Comment) -> str:
    """The comment as a user writes it in chat, or on a page whole."""
    return DEFINITION["prompts"]["comment"].format(
        target=comment.target, text=comment.text
    )


# What applying a decision means here, where no system takes it but the page.


def apply_message(decision: Decision, route: str, copied: str | None) -> str:
    """The user's request to apply the decision: made on the page, pasted from what
    the page offered to copy, or typed."""
    return DEFINITION["prompts"]["apply"][route].format(
        typed=decision.typed, copied=copied
    )


def snapshot(page: Path, destination: Path) -> None:
    if page.exists():
        shutil.copytree(
            page,
            destination,
            ignore=shutil.ignore_patterns("service.json", "*.lock"),
        )


def latest_seq(page: Path) -> int:
    events = read_events(page) if (page / "events.jsonl").exists() else []
    return max((e["seq"] for e in events), default=0)


def author(run: Run, cwd: Path) -> None:
    """Run the sample's live session through its phases, preserving each phase's
    page, and stop any server it left running."""
    cwd.mkdir(parents=True, exist_ok=True)
    (run.directory / "work-dir").write_text(str(cwd))
    run.state.mkdir(parents=True)
    page = run.authored_page
    leaf = run.leaf_condition
    prompt = first_prompt(run.payload, page, run.subject, run.condition)
    (run.directory / "prompt-1.txt").write_text(prompt)
    child = LiveChild(
        cwd,
        prompt,
        *(("--plugin-dir", str(run.payload)) if leaf else ()),
        stderr=run.directory / "err.txt",
        limit=TURN_LIMIT,
        timed_out=run.directory / "timed-out",
        dirs=[run.payload] if leaf else [],
        env=(
            {"LEAF": str(run.payload / "bin/leaf"), "XDG_STATE_HOME": str(run.state)}
            if leaf
            else {}
        ),
        harness=run.harness,
    )
    try:
        with LiveSession(
            child,
            run.directory / "stream.jsonl",
            watch=(run.payload, run.state, page) if leaf else None,
        ) as live:
            for phase in phases(run.subject):
                live.note({"type": "eval_phase", "phase": phase, "received_at": now()})
                since = live.answered
                run.phase_starts[phase] = latest_seq(page)
                before = None
                if phase == 2:
                    live.send(preference_message())
                elif phase == 3:
                    before = comment(run, live)
                elif phase == 4:
                    decision_round(run, live)
                settled = live.settle(since, grace=GRACE, wake=WAKE, before=before)
                snapshot(page, run.directory / f"page-phase{phase}")
                if not settled or not (page / "index.html").exists():
                    break
                if leaf and not live.url:
                    break
    finally:
        if leaf:
            run.leaf("server", "stop", str(page))


def comment(run: Run, live: LiveSession):
    """Send the scenario's comment: from a selection on the served Leaf page, or
    in chat. On Leaf, record its delivery, `eval_received`, if it has arrived, and
    return the check that records it ahead of the record that shows it."""
    scenario = CASES[run.subject]
    remark = scenario.comment
    if not run.leaf_condition:
        live.send(comment_message(remark))
        return None
    posted = live.during(
        lambda: comment_on_passage(
            live.url,
            remark.quotes,
            remark.text,
            comment_message(remark),
            scenario.reveal,
        )
    )
    live.note({"type": "eval_post", **posted, "received_at": now()})
    event = next(
        e
        for e in read_events(run.authored_page)
        if e.get("attempt") == posted["attempt"]
    )
    run.record(
        "comment", {**posted, "event": event["id"], "anchor": event.get("anchor")}
    )
    delivered = False

    def received(record: dict | None = None) -> None:
        nonlocal delivered
        if not delivered and event["id"] in opened_input_ids(
            read_events(run.authored_page)
        ):
            delivered = True
            live.note(
                {"type": "eval_received", "event": event["id"], "received_at": now()}
            )

    # The hook may have delivered it while the browser was still posting.
    received()
    return received


def decision_round(run: Run, live: LiveSession) -> None:
    """Make the scenario's decision on the page as its user, then ask for it to be
    applied, recording the route the request took: what the page gave to copy
    where it offered that, the page itself where it sent the decision to the
    agent's log, and otherwise the decision typed."""
    decision = CASES[run.subject].decision
    page = run.authored_page
    before = latest_seq(page)

    def deciding():
        if run.leaf_condition:
            return decide(live.url, decision.task, run.directory / "user")
        with arrangement_plain.serving(page) as url:
            return decide(url, decision.task, run.directory / "user")

    made = live.during(deciding)
    # What the page sent the agent: the user's inputs admission marked as owing it
    # attention, rather than bookkeeping such as a read receipt.
    gestures = [
        {k: e.get(k) for k in ("kind", "widget", "action", "detail", "text")}
        for e in (read_events(page) if run.leaf_condition else [])
        if e["seq"] > before
        and e.get("author") == "user"
        and requires_agent_attention(e)
    ]
    copied = (made["copies"] or [None])[-1] or made["copied"]
    # The user copies only where the page has no way to send the decision, so
    # what it copied is the handover even beside inputs the page sent.
    if made["made"] and copied:
        route = "copied"
    elif made["made"] and gestures:
        route = "page"
    else:
        route = "typed"
    message = apply_message(decision, route, copied)
    run.record(
        "decision",
        {**made, "gestures": gestures, "route": route, "message": message},
    )
    live.send(message)


def answers_in_phase(run: Run, phase: int) -> list[str]:
    """The agent's page messages from `phase` on, which a Leaf agent may answer
    in rather than in chat."""
    start = run.phase_starts.get(phase, 0)
    return [
        f"{e.get('title') or ''} {e.get('text') or ''}".strip()
        for e in read_events(run.authored_page)
        if e["seq"] > start
        and e.get("author") == "agent"
        and e["kind"] in MESSAGE_KINDS
    ]


def items(decision: Decision) -> str:
    return "\n".join(
        f"- {item}: {' | '.join(values)}" for item, values in decision.values.items()
    )


def reading_schema(decision: Decision) -> str:
    """The reader's answer, which the harness's structured output holds to each
    item's listed values."""
    return json.dumps(
        {
            "type": "object",
            "properties": {
                item: {"type": "string", "enum": [*values, "undecided"]}
                for item, values in decision.values.items()
            },
            "required": list(decision.values),
            "additionalProperties": False,
        }
    )


def matches(decision: Decision, reading: dict | None) -> dict[str, bool]:
    """Each item, and whether the reading gives its chosen value."""
    return {
        item: reading is not None and reading[item] == chosen
        for item, chosen in decision.chosen.items()
    }


def read_applied(run: Run, reply: str) -> dict:
    """What the agent applied, read by a judge from the final page's authored
    files, with its answers in the decision phase only to point the way."""
    decision = CASES[run.subject].decision
    evidence = run.directory / "applied"
    files = evidence / "page"
    page = run.authored_page
    for found in authored_files(page, run.condition):
        target = files / found.relative_to(page)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(found, target)
    answer = evidence / "answer.txt"
    answer.write_text(
        "\n\n".join([reply, *answers_in_phase(run, 4)]) if run.leaf_condition else reply
    )
    listed = "\n".join(
        f"- {path}" for path in sorted(files.rglob("*")) if path.is_file()
    )
    prompt = DEFINITION["prompts"]["reading"].format(
        situation=DEFINITION["prompts"]["reading_applied"].format(
            listed=listed, answer=answer
        ),
        items=items(decision),
    )
    (evidence / "prompt.txt").write_text(prompt)
    with scratch() as cwd:
        trace = run_agent(
            cwd,
            prompt,
            "--tools",
            "Read",
            "--json-schema",
            reading_schema(decision),
            out=evidence / "stream.jsonl",
            err=evidence / "err.txt",
            dirs=[evidence],
            model=MODELS["judge"],
        )
    reading = trace_result(trace).get("structured_output")
    return {
        "reading": reading,
        "items": matches(decision, reading),
        "trace": trace_summary(trace),
    }


def read_decision(run: Run) -> dict:
    """The user's decision as a fresh Leaf reader reports it from the page's state,
    without the author's conversation."""
    decision = CASES[run.subject].decision
    page = run.authored_page
    destination = run.directory / "reader"
    destination.mkdir()
    source_before = (page / "index.html").read_bytes()
    events_before = (page / "events.jsonl").read_bytes()
    prompt = DEFINITION["prompts"]["reading"].format(
        situation=DEFINITION["prompts"]["reading_decision"].format(
            payload=run.payload, page=page
        ),
        items=items(decision),
    )
    (destination / "prompt.txt").write_text(prompt)
    with scratch() as work:
        trace = run_agent(
            work,
            prompt,
            "--json-schema",
            reading_schema(decision),
            out=destination / "stream.jsonl",
            err=destination / "err.txt",
            dirs=[run.payload, page],
            env={
                "LEAF": str(run.payload / "bin/leaf"),
                "XDG_STATE_HOME": str(run.state),
            },
            harness=run.harness,
        )
    reading = trace_result(trace).get("structured_output")
    return {
        "completed": completed(trace),
        "page_unchanged": source_before == (page / "index.html").read_bytes()
        and events_before == (page / "events.jsonl").read_bytes(),
        "reading": reading,
        "items": matches(decision, reading),
        "trace": trace_summary(trace),
    }


def chosen_options(page: Path | None) -> set[str]:
    """The `lf-option`s a Leaf page's markup marks chosen."""
    if page is None:
        return set()
    return {
        r["attrs"]["id"]
        for r in SourceDocument((page / "index.html").read_text()).lf_elements
        if r["tag"] == "lf-option" and "chosen" in r["attrs"] and "id" in r["attrs"]
    }


def gate(run: Run, phase: int, page: Path) -> dict:
    """Independently check the authored page, retaining the check's output."""
    if run.condition == "html":
        reading = arrangement_plain.gate(page, WIDTHS)
    else:
        proc = run.leaf("page", "check", str(page), "--render", timeout=900)
        reading = {"passed": proc.returncode == 0, "output": proc.stdout + proc.stderr}
    (run.directory / f"gate-{phase}.json").write_text(json.dumps(reading, indent=2))
    return reading


def capture_views(view, shots: Path, prefix: str, settled, destinations=()) -> dict:
    """Record arrival and task inspection, without equating DOM text with visibility.

    Collection is bounded; unvisited states and failed operations remain explicit
    limits. The caller provides a disposable page, because inspection can record
    decisions. Screenshots establish appearance; DOM text only establishes current
    light-DOM presence, including hidden content, not reachability or legibility.
    """
    shots.mkdir(parents=True, exist_ok=True)
    images, states, limits = [], [], []

    def screens(action):
        view.evaluate("window.scrollTo({top:0,left:0,behavior:'instant'})")
        height = view.evaluate("document.documentElement.scrollHeight")
        step = int(view.viewport_size["height"] * 0.85)
        count = 1 + max(0, height - view.viewport_size["height"] + step - 1) // step
        if count > 16:
            limits.append(f"{action}: document exceeds 16 screens")
        for index in range(min(count, 16)):
            if len(images) >= 64:
                limits.append("Screenshot limit reached")
                return
            view.evaluate(
                "y => window.scrollTo({top:y,left:0,behavior:'instant'})", index * step
            )
            settled(view)
            path = shots / f"{prefix}-{len(images)}.png"
            view.screenshot(path=path)
            images.append(str(path))
            states.append(
                {
                    "action": action,
                    "image": str(path),
                    "accessibility": view.locator("body").aria_snapshot(),
                    "reading": view.evaluate("""() => {
                  const copy = (document.querySelector('main') || document.body).cloneNode(true);
                  copy.querySelectorAll('script,style,template').forEach(n => n.remove());
                  return {dom_text:copy.textContent, scroll_y:scrollY,
                    width:innerWidth, scroll_width:document.documentElement.scrollWidth};
                }"""),
                }
            )

    def operate(label, operation):
        from playwright.sync_api import Error

        try:
            operation()
            settled(view)
        except Error as error:
            limits.append(f"{label}: {str(error).splitlines()[0]}")
        screens(label)

    screens("Arrival; authored state before inspection")
    for target in destinations:
        operate(
            f"Inspect task item: {target}",
            lambda target=target: reveal(view, target, re.escape(target), settled),
        )
    controls = view.locator(
        'details > summary, [role="tab"], button[aria-pressed], button[aria-controls]'
    )
    if controls.count() > 16:
        limits.append("More than 16 disclosure/navigation controls; some unvisited")
    for control in controls.all()[:16]:
        if (
            not control.is_visible()
            or control.evaluate(OPEN)
            or control.get_attribute("aria-pressed") == "true"
        ):
            continue
        label = control.inner_text().strip()
        operate(f"Open: {label}", lambda control=control: control.click(timeout=2000))
    selections = 0
    for select in view.locator("select").all():
        if not select.is_visible() or not select.is_enabled():
            continue
        original = select.input_value()
        for option in select.locator("option").all():
            value = option.evaluate("el => el.value")
            if value == original or option.is_disabled():
                continue
            if selections >= 16:
                limits.append("Selection limit reached; some options unvisited")
                break
            selections += 1
            operate(
                f"Inspect option: {option.inner_text()}",
                lambda value=value, select=select: select.select_option(
                    value, timeout=2000
                ),
            )
        operate(
            "Restore original selection",
            lambda select=select, original=original: select.select_option(
                original, timeout=2000
            ),
        )
    # Operate actual scroll owners. Hidden/clip overflow is never scrolled by script.
    handles = view.evaluate_handle("""() => [...document.querySelectorAll('body *')].filter(el => {
      const css=getComputedStyle(el);
      return el.checkVisibility() && el.clientWidth && el.clientHeight &&
        ((el.scrollWidth>el.clientWidth+1 && /auto|scroll/.test(css.overflowX)) ||
         (el.scrollHeight>el.clientHeight+1 && /auto|scroll/.test(css.overflowY)));
    })""").get_properties()
    if len(handles) > 8:
        limits.append("More than 8 scroll regions; some unvisited")
    for handle in list(handles.values())[:8]:
        owner = handle.as_element()
        for axis in ("x", "y"):
            extent, size = owner.evaluate(
                "(el,a) => a==='x' ? [el.scrollWidth-el.clientWidth,el.clientWidth] : [el.scrollHeight-el.clientHeight,el.clientHeight]",
                axis,
            )
            if extent <= 1:
                continue
            step = max(1, int(size * 0.85))
            count = (extent + step - 1) // step
            if count > 8:
                limits.append(f"Scroll region on {axis} exceeds 8 screens")
            for position in range(1, min(count, 8) + 1):
                target = min(extent, position * step)

                def scroll(owner=owner, axis=axis, target=target):
                    owner.scroll_into_view_if_needed(timeout=2000)
                    box = owner.bounding_box()
                    current = owner.evaluate(
                        "(el,a) => a==='x' ? el.scrollLeft : el.scrollTop", axis
                    )
                    view.mouse.move(
                        box["x"] + min(20, box["width"] / 2),
                        box["y"] + min(20, box["height"] / 2),
                    )
                    view.mouse.wheel(
                        target - current if axis == "x" else 0,
                        target - current if axis == "y" else 0,
                    )
                    view.wait_for_function(
                        "([el,a,end]) => Math.abs((a==='x'?el.scrollLeft:el.scrollTop)-end)<2",
                        arg=[owner, axis, target],
                        timeout=2000,
                    )

                operate(f"Scroll region on {axis} to {target}", scroll)
    return {
        "images": images,
        "states": states,
        "limits": limits,
        "note": "Inspection choices are collector inputs, not user decisions. DOM/accessibility text does not prove visual legibility. Controls not operated remain unverified.",
    }


def capture_phase(
    run: Run, phase: int, page: Path | None = None
) -> dict[str, list[str]]:
    """Capture arrival and relevant inspected states on a fresh copy per viewport."""
    captures = {name: [] for name in WIDTHS}
    page = page or run.page(phase)
    if page is None:
        return captures
    if any(run.shots.glob(f"p{phase}-*")):
        raise ValueError("Observations already exist; use a fresh shots directory")
    scenario = CASES[run.subject]
    targets = list(scenario.decision.values) if run.subject == "queue" else []
    if phase >= 3 and scenario.reveal:
        targets.append(scenario.reveal)
    html = run.condition == "html"

    def settled(view):
        if html:
            arrangement_plain.settle(view)
        else:
            rendered(view)
            settle(view)

    observations = {}
    with chrome() as browser:
        for name, (viewport, _) in WIDTHS.items():
            with tempfile.TemporaryDirectory(prefix="leaf-capture-") as temporary:
                copied = Path(temporary) / "page"
                shutil.copytree(page, copied)
                server = (
                    arrangement_plain.serving(copied)
                    if html
                    else serving(run.payload, Path(temporary) / "state", copied)
                )
                with (
                    server as url,
                    tab(browser, viewport=viewport, touch=name == "phone") as view,
                ):
                    (arrangement_plain.load if html else load)(view, url)
                    reading = capture_views(
                        view, run.shots, f"p{phase}-{name}", settled, targets
                    )
                    captures[name] = reading["images"]
                    observations[name] = reading
    (run.shots / f"p{phase}-observations.json").write_text(
        json.dumps(observations, indent=2)
    )
    return captures


def capture(run: Run) -> dict[int, dict[str, list[str]]]:
    """Capture every phase's page."""
    return {phase: capture_phase(run, phase) for phase in phases(run.subject)}


AUTHORED = (".html", ".css", ".js", ".mjs", ".json")


def authored_files(page: Path, condition: str) -> list[Path]:
    """The text files the author wrote: all of an HTML page's; a Leaf page's
    document, its page-specific inputs and its data, leaving out what Leaf vendors."""
    if condition == "html":
        found = page.rglob("*")
    else:
        found = [
            page / "index.html",
            *(page / "page").rglob("*"),
            *(page / "data").rglob("*"),
        ]
    return sorted(f for f in found if f.is_file() and f.suffix in AUTHORED)


def authored_lines(page: Path, condition: str) -> dict[str, int]:
    """Non-blank CSS and script lines across the authored files, inline or separate,
    and the count of `style` attributes."""
    counts = {"css_lines": 0, "script_lines": 0, "style_attributes": 0}

    def lines(text: str) -> int:
        return sum(1 for line in text.splitlines() if line.strip())

    for file in authored_files(page, condition):
        if file.suffix == ".css":
            counts["css_lines"] += lines(file.read_text())
        elif file.suffix in (".js", ".mjs"):
            counts["script_lines"] += lines(file.read_text())
        elif file.suffix == ".html":
            # The parsed tree, template contents included, so a live sample's code
            # counts as the author's too.
            tree = turbohtml.parse(file.read_text())
            counts["css_lines"] += sum(lines(e.text) for e in tree.select("style"))
            counts["script_lines"] += sum(
                lines(e.text) for e in tree.select("script:not([src])")
            )
            counts["style_attributes"] += len(tree.select("[style]"))
    return counts


# A shell command that writes the page, and one that renders it in a browser. Both
# read command text, so they approximate: a write through some other program, or a
# browser run under another name, goes uncounted.
SHELL_WRITE = re.compile(
    r"sed -i|perl -\w*i|\.write\(|write_text\(|(>|tee)\s*\S*index\.html"
)
RENDER = re.compile(r"page check|playwright|chrom|puppeteer|screenshot", re.IGNORECASE)


def tool_work(trace: list[dict], page: Path) -> dict[str, int]:
    """The phase's writes to the page, its first draft plus each repair iteration,
    and the times it rendered the page to check it."""
    writes = renders = 0
    for block in blocks(trace):
        if block.get("type") != "tool_use":
            continue
        given = block.get("input", {})
        if block.get("name") in ("Write", "Edit", "MultiEdit"):
            writes += str(given.get("file_path", "")).startswith(f"{page}/")
        elif command := given.get("command"):
            writes += bool(
                SHELL_WRITE.search(command)
                and (str(page) in command or "index.html" in command)
            )
            renders += bool(RENDER.search(command))
    return {"page_writes": writes, "renders": renders}


def comment_applied(run: Run, page: Path) -> bool:
    """Whether the authored files carry the fact only the comment supplied: what an
    HTML file says (`SourceReading`), any other file whole."""
    text = " ".join(
        SourceReading(SourceDocument(f.read_text()), {}).passages.text
        if f.suffix == ".html"
        else f.read_text()
        for f in authored_files(page, run.condition)
    )
    return (
        re.search(CASES[run.subject].comment.applied, " ".join(text.split()))
        is not None
    )


def comment_answer(run: Run, reply: str) -> str:
    """What the author told the user about their comment, where it was asked: its
    replies on the comment's thread in Leaf, its chat reply in HTML. The judge reads
    it (the case's "comment-answered" assertion)."""
    if not run.leaf_condition:
        return reply
    thread = run.recorded("comment").get("event")
    answers = (
        successful_replies(read_events(run.authored_page), thread) if thread else []
    )
    return "\n\n".join(
        f"{answer.get('title', '')}\n{answer['text']}".strip() for answer in answers
    )


def phase_traces(trace: list[dict]) -> dict[int, list[dict]]:
    """The session's records split at the harness's `eval_phase` marks."""
    split: dict[int, list[dict]] = {}
    current = None
    for record in trace:
        if record.get("type") == "eval_phase":
            current = record["phase"]
            split[current] = []
        elif current is not None:
            split[current].append(record)
    return split


def replies(trace: list[dict]) -> str:
    """Every turn's closing message in a phase, in order."""
    return "\n\n".join(
        r.get("result") or "" for r in trace if r.get("type") == "result"
    ).strip()


def listing(captures: dict[str, list[str]]) -> list[str]:
    """A version's screenshot paths as the judge reads them, by width."""
    lines = []
    for name, (_, label) in WIDTHS.items():
        lines.append(f"  On {label}, top to bottom:")
        lines += [f"    {path}" for path in captures[name]]
    return lines


def later_messages(subject: str, first: str = "version 1") -> list[str]:
    """The user's messages after the first version, as both judges read them."""
    scenario = CASES[subject]
    lines = [f'After {first}, the user added a standing preference: "{PREFERENCE}"']
    if comment := scenario.comment:
        lines += ["", f'Then the user commented: "{comment_message(comment)}"']
    if decision := scenario.decision:
        lines += [
            "",
            (
                "Then the user made these decisions on the page and asked for them "
                f'to be applied: "{decision.typed}"'
            ),
        ]
    return lines


def brief(
    subject: str, captures: dict[int, dict[str, list[str]]], answer: str = ""
) -> str:
    """What the judge reads: the request, the later messages, the author's `answer`
    to the comment, and each version's screenshots."""
    lines = [
        f"<request>\n{(TASKS / subject / 'request.md').read_text()}</request>",
        "",
        *later_messages(subject),
        "",
        "Each message after the request produced the next version.",
    ]
    if CASES[subject].comment:
        lines += [
            "",
            "The author answered the comment:",
            f"<answer>\n{answer or '(no answer)'}\n</answer>",
        ]
    for phase in phases(subject):
        lines += ["", f"Version {phase} screenshots:", *listing(captures[phase])]
    return "\n".join(lines)


def expected_checks(case: str, *, condition="leaf") -> list[str]:
    """Common outcome checks apply to both tools; the hand-over, the comment's
    delivery and the fresh reader are Leaf's own."""
    if case not in CASES:
        raise ValueError(f"Unknown authored task: {case}")
    scenario, leaf = CASES[case], condition == "leaf"
    return [
        "completed",
        *(
            f"phase-{phase}-{check}"
            for phase in phases(case)
            for check in ("completed", "page", "render", "captures")
        ),
        *(["handed-over"] if leaf else []),
        *(["comment-delivered"] if leaf and scenario.comment else []),
        *(["comment-applied"] if scenario.comment else []),
        *(["decision-made", "decision-applied"] if scenario.decision else []),
        *(
            [
                "decision-reader-completed",
                "decision-reader-correct",
                "decision-reader-page-unchanged",
            ]
            if leaf and scenario.decision
            else []
        ),
    ]


def execute_scenario(
    case: str,
    payload: Path,
    work: Path,
    *,
    shots: Path,
    harness=ClaudeCodeHarness.name,
    condition="leaf",
) -> dict:
    """Execute only the selected condition; Promptfoo owns the condition matrix."""
    work.mkdir(parents=True, exist_ok=True)
    checks = dict.fromkeys(expected_checks(case, condition=condition), False)
    run = Run(case, payload, work, shots, harness, condition)
    scenario = CASES[case]
    diagnostics = {
        "subject": case,
        "harness": harness,
        "condition": condition,
        "phases": {},
    }
    harness_costs = []
    with scratch(payload) as child_work:
        author(run, child_work)
        trace = read_trace(work / "stream.jsonl")
        split = phase_traces(trace)
        order = list(phases(case))
        session = dict(
            zip(order, resumed([trace_summary(split.get(p, [])) for p in order]))
        )
        if run.leaf_condition:
            served = next((r["url"] for r in trace if r["type"] == "eval_served"), None)
            checks["handed-over"] = served is not None and served in replies(
                split.get(1, [])
            )
            if scenario.comment:
                checks["comment-delivered"] = any(
                    r["type"] == "eval_received" for r in trace
                )
                remark = run.recorded("comment")
                diagnostics["comment"] = remark
                # A comment that directs an outcome may be recorded as the user's
                # pick, which is right; record whether it was.
                diagnostics["comment_recorded_pick"] = sorted(
                    chosen_options(run.page(3)) - chosen_options(run.page(2))
                )
        if scenario.decision:
            made = run.recorded("decision")
            harness_costs.append((made.get("trace") or {}).get("cost_usd"))
            checks["decision-made"] = made.get("made") is True
            decision = {"made": made}
            if (run.authored_page / "index.html").exists() and 4 in split:
                applied = read_applied(run, replies(split[4]))
                harness_costs.append(applied["trace"]["cost_usd"])
                decision["applied"] = applied
                checks["decision-applied"] = all(applied["items"].values())
                if run.leaf_condition:
                    reader = read_decision(run)
                    harness_costs.append(reader["trace"]["cost_usd"])
                    decision["reader"] = reader
                    checks["decision-reader-completed"] = reader["completed"]
                    checks["decision-reader-correct"] = all(reader["items"].values())
                    checks["decision-reader-page-unchanged"] = reader["page_unchanged"]
            diagnostics["decision"] = decision
        captures = capture(run)
        answer = ""
        for phase in order:
            summary = session[phase]
            checks[f"phase-{phase}-completed"] = summary["completed"]
            page = run.page(phase)
            checks[f"phase-{phase}-page"] = page is not None
            checks[f"phase-{phase}-captures"] = all(captures[phase].values())
            row = {
                "trace": summary,
                "captures": captures[phase],
                "observations": json.loads(
                    (shots / f"p{phase}-observations.json").read_text()
                )
                if page
                else {},
                **tool_work(split.get(phase, []), run.authored_page),
            }
            if page:
                reading = gate(run, phase, page)
                checks[f"phase-{phase}-render"] = reading["passed"]
                row |= {
                    "page": str(page),
                    "gate": reading,
                    **authored_lines(page, condition),
                }
                if phase == 3:
                    checks["comment-applied"] = comment_applied(run, page)
                    answer = comment_answer(run, summary["reply"])
            diagnostics["phases"][phase] = row
    checks["completed"] = all(checks[f"phase-{phase}-completed"] for phase in order)
    authoring = [session[p]["cost_usd"] for p in order]
    diagnostics["cost"] = {
        "author": observed_sum(authoring),
        "harness": observed_sum(harness_costs),
    }
    return {
        "output": brief(case, captures, answer),
        "metadata": {"checks": checks, "diagnostics": diagnostics},
        **(
            {"cost": cost}
            if (cost := observed_sum([*authoring, *harness_costs])) is not None
            else {}
        ),
    }
