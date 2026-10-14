"""Product controls really render ordinary HTML; the live loop carries each phase
to a scripted author; live judges explore disposable copies."""

import json
import time
from pathlib import Path

import turbohtml
from leaf.event_log import read_events
from leaf.service import PageTransaction
from leaf_dev import ROOT, arrangement_plain
from leaf_dev.arrangement_eval import (
    CASES,
    WIDTHS,
    comment_message,
    first_prompt,
)


def test_html_control_uses_browser_without_leaf_payload(tmp_path):
    page = tmp_path / "page"
    page.mkdir()
    (page / "index.html").write_text(
        "<!doctype html><title>Control</title><h1>Report</h1><p>Readable content.</p>"
    )
    prompt = first_prompt(ROOT, page, "document", "html")
    assert str(ROOT) not in prompt
    assert "$LEAF" not in prompt
    assert "ordinary HTML" in prompt
    comment = CASES["document"].comment
    message = comment_message(comment)
    assert comment.target in message and comment.text in message
    assert arrangement_plain.gate(page, WIDTHS)["passed"]
    (page / "index.html").write_text(
        "<!doctype html><title>Fault</title><style>body{width:1800px}</style><h1>Report</h1><script>throw Error('seeded fault')</script>"
    )
    reading = arrangement_plain.gate(page, WIDTHS)
    assert not reading["passed"]
    assert any("seeded fault" in item["error"] for item in reading["findings"])
    assert any("overflows" in item["error"] for item in reading["findings"])


class Scripted:
    """A live child whose author a test plays: `turn` answers each chat message,
    and `comment` each user comment the page admits, with the turn's reply."""

    def __init__(self, turn, comment=None, page: Path | None = None):
        self.turn, self.comment, self.page = turn, comment, page
        self.inbox, self.closed, self.seen = [], False, set()

    def __call__(self, cwd, prompt, *args, **kwargs):
        self.inbox.append(prompt)
        self.state = Path(kwargs["env"]["XDG_STATE_HOME"]) if kwargs["env"] else None
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def send(self, text):
        self.inbox.append(text)

    def close(self):
        self.closed = True

    def waiting(self) -> dict | None:
        if self.comment is None or not (self.page / "events.jsonl").exists():
            return None
        return next(
            (
                e
                for e in read_events(self.page)
                if e["kind"] == "comment"
                and e["author"] == "user"
                and e["id"] not in self.seen
            ),
            None,
        )

    def records(self):
        while not self.closed:
            if self.inbox:
                reply = self.turn(self.inbox.pop(0))
            elif event := self.waiting():
                self.seen.add(event["id"])
                with PageTransaction(self.page) as transaction:
                    from leaf.delivery import record_pickup

                    record_pickup(transaction, [event], session="eval")
                reply = self.comment(event)
            else:
                time.sleep(0.1)
                continue
            yield {"type": "assistant", "message": {"content": []}}
            yield {
                "type": "result",
                "is_error": False,
                "num_turns": 1,
                "duration_ms": 1000,
                "total_cost_usd": 0.0,
                "result": reply,
            }


DOCUMENT = (
    '<!doctype html><html lang="en"><head><title>Decision review</title>'
    '<meta name="description" content="Review evidence."></head><body>'
    '<main class="layout-column"><h1>Decision review</h1>'
    '<p id="review-status">{body}</p>'
    '<p id="ask">Need the database owners to say whether 55% peak CPU '
    "is acceptable.</p>"
    '<lf-ask id="choice"><h2>Which option?</h2><lf-options id="decision" choose>'
    '<lf-option id="redis">Stay on managed Redis</lf-option>'
    '<lf-option id="postgres">Postgres</lf-option>'
    "</lf-options></lf-ask></main></body></html>"
)


def test_live_loop_carries_each_phase_to_the_author(tmp_path, monkeypatch):
    """Script only the model and the user agent: the served page takes a comment
    from a browser selection, its delivery is recorded, the user's pick reaches
    the log, and each phase's page and request stay apart."""
    from leaf_dev import arrangement_eval, usability_eval
    from leaf_dev.arms import PageClient, read_page_state, run_leaf

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    run = arrangement_eval.Run("document", ROOT, evidence, evidence / "shots")
    cwd = tmp_path / "cwd"
    page = cwd / "page"
    versions = []

    def stamp(body):
        (page / "index.html").write_text(DOCUMENT.format(body=body))
        run_leaf(
            ROOT, run.state, "page", "stamp", str(page), "--text", body, check=True
        )

    def turn(message):
        versions.append(message)
        if len(versions) == 1:
            run_leaf(ROOT, run.state, "page", "init", str(page), check=True)
            stamp("Author version 1")
            run_leaf(ROOT, run.state, "server", "start", str(page), check=True)
            return read_page_state(ROOT, run.state, page)["server"]["url"]
        if len(versions) == 2:
            assert "900px" in message
            stamp("Author version 2")
            return "Revised."
        assert message.startswith("I've made my decisions on the page.")
        stamp("Decided: stay on managed Redis, 7-day TTL")
        return "Applied: staying on managed Redis with a 7-day TTL."

    def comment(event):
        assert event["text"] == CASES["document"].comment.text
        assert "anchor" in event
        usability_eval.arm_fixture(
            run, "answer", str(page), event["id"], "Named Mei Tanaka's team."
        )
        stamp("Ask Mei Tanaka's team")
        return "Answered on the page."

    def decide(url, task, directory):
        state = PageClient(url).state()
        PageClient(url).post(
            {
                "kind": "action",
                "widget": "decision",
                "action": "choose",
                "revision": state["active"]["revision"],
                "detail": {"value": ["redis"]},
                "attempt": "scripted-user-pick-0001",
            }
        )
        return {"made": True, "copied": None, "notes": "", "copies": [], "trace": {}}

    child = Scripted(turn, comment, page)
    monkeypatch.setattr(arrangement_eval, "LiveChild", child)
    monkeypatch.setattr(arrangement_eval, "decide", decide)
    monkeypatch.setattr(arrangement_eval, "GRACE", 0.5)
    arrangement_eval.author(run, cwd)

    records = [
        json.loads(line)
        for line in (evidence / "stream.jsonl").read_text().splitlines()
    ]
    assert [r["phase"] for r in records if r["type"] == "eval_phase"] == [1, 2, 3, 4]
    assert any(r["type"] == "eval_served" for r in records)
    assert any(r["type"] == "eval_received" for r in records)
    for phase, marker in enumerate(
        ("Author version 1", "Author version 2", "Mei Tanaka", "Decided"), 1
    ):
        assert marker in (evidence / f"page-phase{phase}/index.html").read_text()
    remark = run.recorded("comment")
    assert remark["route"] == "selection" and remark["anchor"]
    decision = run.recorded("decision")
    assert decision["route"] == "page"
    assert [g["detail"] for g in decision["gestures"]] == [{"value": ["redis"]}]
    assert arrangement_eval.comment_applied(run, evidence / "page-phase3")
    assert arrangement_eval.comment_answer(run, "") == "Named Mei Tanaka's team."

    def reader(cwd, prompt, *args, out, err, **kwargs):
        assert "stay on managed Redis, 7-day TTL" in prompt
        answer = Path(prompt.split("answers at ")[1].split(" ")[0].rstrip("."))
        assert "7-day TTL" in answer.read_text()
        # The reader is held to its answer's shape, as the harness returns it.
        assert "--json-schema" in args
        answer = {"option": "stay on managed Redis, 7-day TTL"}
        trace = [
            {
                "type": "result",
                "is_error": False,
                "result": json.dumps(answer),
                "structured_output": answer,
            }
        ]
        out.write_text("\n".join(json.dumps(r) for r in trace))
        return trace

    monkeypatch.setattr(arrangement_eval, "run_agent", reader)
    split = arrangement_eval.phase_traces(records)
    applied = arrangement_eval.read_applied(run, arrangement_eval.replies(split[4]))
    assert applied["items"] == {"option": True}


def test_completed_record_has_a_render_correction_loop_without_a_decision(
    tmp_path, monkeypatch
):
    """Script only the model; actual checks reject, repair and render its page."""
    from leaf_dev import arrangement_eval
    from leaf_dev.arms import read_page_state

    calls = []
    child = None

    def turn(prompt):
        calls.append(prompt)
        page = child.cwd / "page"

        def leaf(*arguments):
            return arrangement_eval.run_leaf(ROOT, child.state, *arguments)

        if len(calls) == 1:
            assert f"page check {page} --render" in prompt
            assert leaf("page", "init", str(page)).returncode == 0
        (page / "index.html").write_text("<!doctype html><p>Incomplete record</p>")
        refused = leaf("page", "check", str(page), "--render")
        assert refused.returncode != 0
        (page / "index.html").write_text(
            '<!doctype html><html lang="en"><head><title>Completed rollout</title>'
            '<meta name="description" content="A completed rollout record."></head>'
            '<body><main class="layout-sidebar"><header><h1>Completed rollout</h1>'
            f'<p id="version">Version {len(calls)}</p>'
            '</header><aside id="checks">'
            "<div><h2>Checks</h2>"
            '<p>Five passed. One failed.</p><lf-toc id="contents"></lf-toc></div></aside>'
            '<section id="log"><h2>Rollout log</h2>'
            + "<p>Completed rollout entry.</p>" * 40
            + "</section></main></body></html>"
        )
        accepted = leaf("page", "check", str(page), "--render")
        assert accepted.returncode == 0, accepted.stdout + accepted.stderr
        assert leaf("page", "stamp", str(page), "--text", "Repaired").returncode == 0
        if len(calls) == 1:
            assert leaf("server", "start", str(page)).returncode == 0
            return read_page_state(ROOT, child.state, page)["server"]["url"]
        return str(page)

    class Child(Scripted):
        def __call__(self, cwd, prompt, *args, **kwargs):
            self.cwd = cwd
            return super().__call__(cwd, prompt, *args, **kwargs)

    child = Child(turn)
    monkeypatch.setattr(arrangement_eval, "LiveChild", child)
    monkeypatch.setattr(arrangement_eval, "GRACE", 0.5)
    evidence = tmp_path / "evidence"
    response = arrangement_eval.execute_scenario(
        "sidebar-page-at-900px", ROOT, evidence, shots=evidence / "shots"
    )
    assert len(calls) == 2
    assert all(response["metadata"]["checks"].values()), response["metadata"]["checks"]
    assert not any(
        key.startswith("decision-") for key in response["metadata"]["checks"]
    )
    for phase in response["metadata"]["diagnostics"]["phases"].values():
        assert phase["captures"]["short"]
        assert all(Path(path).is_file() for path in phase["captures"]["short"])


def test_reader_calibration_shows_the_judge_its_page_at_every_width(tmp_path):
    """No model runs: the seeded triage page renders, and the output lists every
    capture under its width, which is all the count rubric reads."""
    from leaf_dev import reader_eval

    response = reader_eval.execute_scenario(
        "seeded", ROOT, tmp_path, shots=tmp_path / "shots"
    )
    assert response["metadata"]["checks"] == {"completed": True}
    output = response["output"]
    widths = [line for line in output.splitlines() if line.startswith("  On ")]
    assert widths == [f"  On {label}, top to bottom:" for _, label in WIDTHS.values()]
    listed = [
        Path(line.strip())
        for line in output.splitlines()
        if line.strip().endswith(".png")
    ]
    assert listed and all(path.is_file() for path in listed)
    seeded = turbohtml.parse((tmp_path / "source.html").read_text())
    clean = turbohtml.parse(reader_eval.fixture(reader_eval.CASES["clean"]))
    assert seeded.select_one("#count-open dd strong").text == "8"
    assert clean.select_one("#count-open dd strong").text == "7"


def test_reveal_opens_the_named_item_though_its_words_show_elsewhere(tmp_path):
    """A summary naming the comment's fact does not stand for the commented item:
    the capture opens the item, and leaves one already open as it is."""
    from leaf_dev.browser import chrome, tab
    from leaf_dev.eval_user import reveal, shows

    (tmp_path / "index.html").write_text(
        "<!doctype html><title>Queue</title><main>"
        "<p>Routed today: Sam Okafor.</p>"
        "<button onclick=\"document.getElementById('t').hidden=false\">ESC-4110</button>"
        '<div id="t" hidden><h2>ESC-4110</h2><p>Route to Sam Okafor.</p></div></main>'
    )
    with (
        arrangement_plain.serving(tmp_path) as url,
        chrome() as browser,
        tab(browser) as view,
    ):
        arrangement_plain.load(view, url)
        assert shows(view, "Sam Okafor")
        assert reveal(view, "ESC-4110", "Sam Okafor", arrangement_plain.settle) == (
            "opened"
        )
        assert view.locator("#t").is_visible()
        # Opening it again leaves an open disclosure open.
        view.set_content(
            "<details open><summary>ESC-4110</summary><p>Sam Okafor</p></details>"
        )
        assert reveal(view, "ESC-4110", "Sam Okafor", arrangement_plain.settle) == (
            "opened"
        )
        assert view.locator("details").get_attribute("open") is not None
        # The button, not its row; and an unmarked toggle already open stays open.
        view.set_content(
            '<p>Sam Okafor</p><ul><li>ESC-4110 <button onclick="t.hidden=!t.hidden">'
            'ESC-4110</button></li></ul><div id="t" hidden>Route to Sam Okafor.</div>'
        )
        reveal(view, "ESC-4110", "Route to Sam", arrangement_plain.settle)
        assert view.locator("#t").is_visible()
        reveal(view, "ESC-4110", "Route to Sam", arrangement_plain.settle)
        assert view.locator("#t").is_visible()
        # A row whose own click draws the button that opens the ticket.
        view.set_content(
            '<ul><li onclick="b.hidden=false">ESC-4110 <button id="b" hidden '
            'onclick="event.stopPropagation(); t.hidden=false">ESC-4110 details'
            '</button></li></ul><div id="t" hidden>Route to Sam Okafor.</div>'
        )
        reveal(view, "ESC-4110", "Route to Sam", arrangement_plain.settle)
        assert view.locator("#t").is_visible()
        # A link that navigates to the ticket's own page, whose button opens it.
        (tmp_path / "ticket.html").write_text(
            '<button onclick="t.hidden=false">ESC-4110 details</button>'
            '<div id="t" hidden>Route to Sam Okafor.</div>'
        )
        view.set_content(f'<a href="{url}ticket.html">ESC-4110</a>')
        reveal(view, "ESC-4110", "Route to Sam", arrangement_plain.settle)
        assert view.locator("#t").is_visible()
