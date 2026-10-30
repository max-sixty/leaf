"""Model-free smoke checks for the developer-run Promptfoo integration.

Detailed grading, browser interaction and provider behavior are checked by running
an experiment while developing it, rather than maintaining regression matrices.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from leaf_dev import arms
from leaf_dev.arms import LiveSession, private_program
from leaf_dev.commands import eval as module
from leaf_dev.eval_codex import records_for


def test_live_session_drains_output_while_observing_the_page(tmp_path, monkeypatch):
    # A provider keeps producing notifications while canonical page state is read.
    # Blocking its reader there can fill the transport buffer and starve PONGs.
    drained = threading.Event()
    messages = [
        {"type": "user"},
        *({"type": "assistant", "sequence": n} for n in range(32)),
        {"type": "result"},
    ]

    def records():
        yield from messages
        drained.set()

    child = SimpleNamespace(
        __enter__=lambda: child,
        __exit__=lambda *args: None,
        records=records,
        close=lambda: None,
        native_sessions=tmp_path / "no-native-sessions",
    )
    page = tmp_path / "page"
    page.mkdir()
    (page / "events.jsonl").touch()

    def state(*args):
        assert drained.wait(5), "page observation blocked the provider's reader"
        return {
            "server": {"url": "http://127.0.0.1:1234/?t=test"},
            "active": {"revision": 1},
            "event_seq": 0,
            "status": "ready",
            "listening": True,
        }

    monkeypatch.setattr(arms, "read_page_state", state)
    stream = tmp_path / "stream.jsonl"
    with LiveSession(child, stream, watch=(tmp_path, tmp_path, page)) as live:
        assert list(live.records()) == messages
        assert live.answered == 1
        live.close()
    written = [json.loads(line) for line in stream.read_text().splitlines()]
    assert [r for r in written if not r["type"].startswith("eval_")] == messages
    assert written[1]["type"] == "eval_served"
    assert written[-1]["type"] == "eval_status"
    assert not live.reader.is_alive()


@pytest.mark.parametrize("author_fails", [False, True])
def test_workflow_archives_distinct_pages_with_the_same_name(
    tmp_path, monkeypatch, author_fails
):
    from leaf_dev import usability_eval as workflow

    work = tmp_path / "work"
    work.mkdir()
    output = tmp_path / "sample"
    output.mkdir()
    run = workflow.Run("archive-smoke", tmp_path / "payload", output)
    monkeypatch.setitem(workflow.CASES, run.case, workflow.Case(run.case, ("task",)))
    sources = {
        work / "page": "final updated page",
        work / "tmp" / "inspection" / "page": "earlier inspection copy",
        work / "page" / "nested" / "page": "nested page",
        run.state / "leaf" / "pages" / "page": "page in state home",
    }

    def author(*args):
        # Model boundary: an author may inspect copies and create other pages.
        for page, content in sources.items():
            page.mkdir(parents=True)
            (page / "events.jsonl").touch()
            (page / "index.html").write_text(content)
        if author_fails:
            raise RuntimeError("author interrupted")

    stopped = []
    monkeypatch.setattr(workflow, "execute_phases", author)
    monkeypatch.setattr(workflow.Run, "leaf", lambda self, *args: stopped.append(args))
    if author_fails:
        with pytest.raises(RuntimeError, match="author interrupted"):
            workflow.execute(run, work)
    else:
        workflow.execute(run, work)
    archives = json.loads((output / "pages.json").read_text())
    assert set(archives) == {str(page) for page in sources}
    assert len(set(archives.values())) == len(sources)
    assert {
        source: (output / archive / "index.html").read_text()
        for source, archive in archives.items()
    } == {str(page): content for page, content in sources.items()}
    assert set(stopped) == {("server", "stop", str(page)) for page in sources}


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox profile")
def test_authoring_sandbox_isolates_files_including_children(tmp_path, monkeypatch):
    assert shutil.which("sandbox-exec"), "macOS evals require sandbox-exec"
    host = tmp_path / "host-config"
    plugins = host / "plugins"
    plugins.mkdir(parents=True)
    host_skill = plugins / "SKILL.md"
    host_skill.write_text("other installed instructions")
    login = host / "auth.json"
    login.write_text("test login")
    monkeypatch.setenv("CODEX_HOME", str(host))
    with tempfile.TemporaryDirectory(prefix="leaf-isolation-", dir="/tmp") as directory:
        root = Path(directory)
        home, work = root / "home's files", root / "owned work"
        home.mkdir()
        work.mkdir()
        stale = root / "other-sample.txt"
        stale.write_text("unrelated sample")
        probe = work / "probe.py"
        probe.write_text("""\
import subprocess
import sys
from pathlib import Path

mode, work, stale, host_skill, login = sys.argv[1:]
owned = Path(work) / mode
owned.write_text("own output")
assert owned.read_text() == "own output"
assert Path(login).read_text() == "test login"
for outside in (Path(stale), Path(host_skill)):
    for operation in (outside.read_text, lambda: outside.write_text("overwrite")):
        try:
            operation()
        except PermissionError:
            pass
        else:
            raise AssertionError("another sample's content was accessible")
if mode == "parent":
    subprocess.run([sys.executable, __file__, "child", work, stale, host_skill, login], check=True)
print("isolated")
""")
        launcher = private_program(Path(sys.executable), home, work)
        result = subprocess.run(
            [
                str(launcher),
                str(probe),
                "parent",
                str(work),
                str(stale),
                str(host_skill),
                str(login),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.splitlines() == ["isolated", "isolated"]
        assert stale.read_text() == "unrelated sample"
        assert host_skill.read_text() == "other installed instructions"


def test_codex_trace_keeps_subagent_activity_without_inventing_tool_calls():
    # Codex 0.163 sends each activity as item/started and item/completed. Its
    # activity identifies the child but does not expose the child's private brief.
    activities = [
        {
            "type": "subAgentActivity",
            "id": f"activity-{kind}",
            "kind": kind,
            "agentThreadId": "child-thread",
            "agentPath": "/root/panel_schematic",
            "model": "gpt-6.1-sol" if kind == "started" else None,
            "reasoningEffort": "medium" if kind == "started" else None,
        }
        for kind in ("started", "interacted", "completed")
    ]
    trace = [
        record
        for item in activities
        for method in ("item/started", "item/completed")
        for record in records_for(
            {"method": method, "params": {"item": item}}, "parent-thread", ""
        )
    ]
    assert trace == activities


def test_catalog_builds_native_and_workflow_promptfoo_tests(tmp_path, monkeypatch):
    # Configuration shares the external login; no native provider is invoked.
    login = tmp_path / "login"
    login.mkdir()
    (login / "auth.json").write_text("{}")
    monkeypatch.setenv("CODEX_HOME", str(login))
    skill = tmp_path / "arm" / ".claude" / "skills" / "developing-leaf" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("Maintainer instructions.")
    cases = module.catalog()
    assert cases
    # The same live-page assertion can grade a complete workflow or a short task.
    cases["page-reads-at-every-width/queue"]["assert"].append(
        cases["configuration"]["assert"][0]
    )
    monkeypatch.setattr(module, "catalog", lambda: cases)
    config = module.prepare(
        [
            # Its provider takes instructions; the next case's provider takes none.
            "interaction-proof-follows-the-reader",
            "todo-outlasts-the-turn",
            "configuration",
            "dashboard/reader-clean",
            "parent-keeps-leaf-responsive/during-work",
            "page-reads-at-every-width/queue",
        ],
        {"candidate": tmp_path / "arm"},
        tmp_path / "scratch",
        ("claude-code",),
        ("leaf", "html"),
        tmp_path / "samples",
    )
    assert config["providers"] and config["tests"]
    assert all(test["assert"] for test in config["tests"])
    assert {test["metadata"]["case"] for test in config["tests"]} == {
        "interaction-proof-follows-the-reader",
        "todo-outlasts-the-turn",
        "configuration",
        "dashboard/reader-clean",
        "parent-keeps-leaf-responsive/during-work",
        "page-reads-at-every-width/queue",
    }
    assert all(
        provider["config"]["viewports"] == ["desktop"]
        for provider in config["providers"]
        if provider["label"].endswith("/workflow")
    )
    # A prompt may reuse another task's request by naming its file.
    queue = next(
        test
        for test in config["tests"]
        if test["metadata"]["case"] == "page-reads-at-every-width/queue"
    )
    assert "ESC-4107" in queue["vars"]["prompt"]
    for test in config["tests"]:
        if test["metadata"]["case"] in {
            "configuration",
            "page-reads-at-every-width/queue",
        }:
            live = next(
                a
                for a in test["assert"]
                if a["value"].endswith("/authoring_assertion.mjs")
            )
            assert live["config"]["judge"]["id"].endswith("/arrangement_eval.py")

    # A saved run can contain the same Python provider on different models. The
    # report must join labels and keep the saved model, even after pins change.
    from leaf_dev.commands.eval_report import report_samples

    providers = [
        provider
        for provider in config["providers"]
        if provider["label"].endswith("/workflow")
    ]
    assert len({provider["id"] for provider in providers}) == 1
    records = []
    for index, provider in enumerate(providers):
        provider["config"]["model"] = f"recorded-model-{index}"
        records.append(
            {
                "id": str(index),
                "provider": {key: provider[key] for key in ("id", "label")},
                "testCase": next(
                    test
                    for test in config["tests"]
                    if test["metadata"]["case"] == "configuration"
                ),
                "response": {},
            }
        )
    monkeypatch.setitem(module.MODELS, "claude-code", "a-new-default")
    native = next(
        p for p in config["providers"] if p["id"] == "anthropic:claude-agent-sdk"
    )
    native_model = native["config"]["model"]
    records.append(
        {
            "id": "native",
            "provider": {key: native[key] for key in ("id", "label")},
            "testCase": next(
                test
                for test in config["tests"]
                if test["metadata"]["case"] == "todo-outlasts-the-turn"
            ),
            "response": {},
        }
    )
    run = tmp_path / "recorded-run"
    run.mkdir()
    (run / "results.json").write_text(
        json.dumps({"config": config, "results": {"results": records}})
    )
    reported = report_samples((run,))
    native_execution = reported["todo-outlasts-the-turn"][native["label"]][0][
        "execution_metadata"
    ]
    assert native_execution["author"] == {
        "harness": "claude-code",
        "model": native_model,
    }
    assert native_execution["kind"] == "probe"
    assert native_execution["requested_viewports"] == []
    columns = reported["configuration"]
    for index, provider in enumerate(providers):
        execution = columns[provider["label"]][0]["execution_metadata"]
        assert execution["author"]["model"] == f"recorded-model-{index}"
        assert execution["kind"] == "workflow"
        assert execution["requested_viewports"] == ["desktop"]


def test_widget_format_matrix_uses_one_model_and_separate_checks(tmp_path):
    config = module.prepare(
        ["widget-formats/choice"],
        {"candidate": tmp_path / "arm"},
        tmp_path / "scratch",
        ("codex",),
        ("leaf", "json", "adaptive"),
        tmp_path / "samples",
        model="gpt-6-luna",
    )
    assert [test["metadata"]["condition"] for test in config["tests"]] == [
        "leaf",
        "json",
        "adaptive",
    ]
    assert {provider["config"]["model"] for provider in config["providers"]} == {
        "gpt-6-luna"
    }
    assert all(
        "Use the Leaf skill" in test["vars"]["prompt"] for test in config["tests"][:2]
    )
    assert "Use the Leaf skill" not in config["tests"][2]["vars"]["prompt"]
    assert [
        [assertion["metric"] for assertion in test["assert"]]
        for test in config["tests"]
    ] == [
        ["completed", "page-valid", "interaction-proven", "task-fit"],
        ["completed", "format-valid", "page-valid", "interaction-proven", "task-fit"],
        ["completed", "format-valid", "page-valid", "interaction-proven", "task-fit"],
    ]


def test_eval_command_delegates_configuration_and_status_to_promptfoo(
    tmp_path, monkeypatch
):
    # Replace the external Promptfoo CLI; keep real catalog/configuration generation.
    promptfoo = tmp_path / "promptfoo"
    calls = tmp_path / "calls"
    promptfoo.write_text(f'#!/bin/sh\necho "$*" > {calls}\nexit 100\n')
    promptfoo.chmod(0o755)

    def build_arm(ref, destination):
        (destination / "skills" / "leaf").mkdir(parents=True)
        return "0123456789abcdef"

    monkeypatch.setattr(module, "PROMPTFOO", promptfoo)
    monkeypatch.setattr(module, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(module, "build_arm", build_arm)
    result = CliRunner().invoke(
        module.eval,
        [
            "--harness",
            "claude-code",
            "patch-review",
            "--viewport",
            "phone",
            "--viewport",
            "desktop",
            "--repeat",
            "3",
        ],
    )
    assert result.exit_code == 100, result.output
    assert calls.read_text().strip().endswith("--repeat 3")
    config = json.loads(
        next((tmp_path / "runs").glob("*/promptfooconfig.json")).read_text()
    )
    assert config["providers"] and len(config["tests"]) == 1
    assert len(config["providers"]) == 1
    assert config["providers"][0]["config"]["viewports"] == ["phone", "desktop"]
    assert "--viewport" not in calls.read_text()


def test_arrangement_retains_linked_pages_per_phase(tmp_path, monkeypatch):
    from contextlib import ExitStack, contextmanager

    from playwright.sync_api import expect

    from leaf_dev import ROOT
    from leaf_dev import arrangement_eval as workflow
    from leaf_dev.browser import headless_shell, load, settle, tab

    work = tmp_path / "originals"
    directory = tmp_path / "sample"
    directory.mkdir()
    (directory / "work-dir").write_text(str(work))
    run = workflow.Run("queue-hand-off", ROOT, directory, tmp_path / "shots")
    main, handoff = run.authored_page, work / "handoff"
    main.mkdir(parents=True)
    incomplete = "<h1>Author stopped before initialization"
    (main / "index.html").write_text(incomplete)
    workflow.snapshot_phase(run, 0)
    page_result = run.page(0)
    assert page_result is not None
    assert (page_result / "index.html").read_text() == incomplete
    assert (
        json.loads((directory / "page-phase0-pages.json").read_text())[0]["url"] is None
    )
    for page in (main, handoff):
        run.leaf("page", "init", str(page), check=True)
        (page / "index.html").write_text(
            "<!doctype html><html><head><title>Saved page</title></head>"
            '<body><main><h1 id="title">Initial page</h1></main></body></html>'
        )
    with ExitStack() as servers:
        urls = {}
        for page in (main, handoff):
            run.leaf("server", "start", str(page), check=True)
            servers.callback(run.leaf, "server", "stop", str(page))
            urls[page] = arms.read_page_state(ROOT, run.state, page)["server"]["url"]
        (main / "index.html").write_text(
            "<!doctype html><html><head><title>Queue</title></head><body><main>"
            '<h1 id="title">Queue</h1>'
            f'<a id="handoff" href="{urls[handoff]}#result">Open handoff</a>'
            '<a id="external" href="https://example.com/">External</a>'
            f'<p id="quoted">The original address was {urls[handoff]}</p>'
            '<lf-ask id="question"><h2>Keep this decision?</h2>'
            '<lf-options id="answer" choose><lf-option id="keep">Keep</lf-option>'
            "</lf-options></lf-ask></main></body></html>"
        )
        with headless_shell() as browser, tab(browser) as view:
            load(view, urls[main])
            view.locator("#keep .lf-pick").click()
            expect(view.locator("#keep .lf-pick")).to_have_attribute(
                "aria-checked", "true"
            )
        for phase in (1, 2):
            (handoff / "index.html").write_text(
                "<!doctype html><html><head><title>Handoff</title></head><body><main>"
                f'<h1 id="result">Handoff phase {phase}</h1>'
                f'<a href="{urls[main]}">Back to queue</a></main></body></html>'
            )
            workflow.snapshot_phase(run, phase)
    shutil.rmtree(work)
    originals = {p: p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    with headless_shell() as browser:
        for phase in (1, 2):
            saved = {"page": run.page(phase), "payload": ROOT, "condition": "leaf"}
            with workflow.restored_page(saved) as (url, restored), tab(browser) as view:
                assert set(restored) == set(urls.values())
                load(view, url)
                expect(view.locator("#keep .lf-pick")).to_have_attribute(
                    "aria-checked", "true"
                )
                expect(view.locator("#quoted")).to_contain_text(urls[handoff])
                expect(view.locator("#external")).to_have_attribute(
                    "href", "https://example.com/"
                )
                with view.expect_popup() as opened:
                    view.get_by_role("link", name="Open handoff").click()
                linked = opened.value
                settle(linked)
                expect(
                    linked.get_by_role("heading", name=f"Handoff phase {phase}")
                ).to_be_visible()
                with linked.expect_popup() as returned:
                    linked.get_by_role("link", name="Back to queue").click()
                expect(returned.value.locator("#keep .lf-pick")).to_have_attribute(
                    "aria-checked", "true"
                )
    assert {p: p.read_bytes() for p in originals} == originals

    # The judge receives delivered addresses as well as navigable page links.
    reply = f"Review the queue at {urls[main]} and the handoff at {urls[handoff]}."
    evidence = tmp_path / "judge"

    def inspect_judge(_cwd, instructions, *args, **kwargs):
        restored = json.loads((evidence / "restored-pages.json").read_text())["final"]
        assert set(restored) == set(urls.values())
        assert reply in instructions
        assert all(address in instructions for address in restored.values())
        raise RuntimeError("Judge prompt inspected without invoking a model")

    monkeypatch.setattr(workflow, "run_agent", inspect_judge)
    monkeypatch.setattr(workflow.pane_readings, "read", lambda *args: {})
    result = workflow.judge_pages(
        {
            "final": {
                "page": run.page(2),
                "payload": ROOT,
                "condition": "leaf",
                "author_reply": reply,
            }
        },
        {},
        "Review the delivered queue and handoff.",
        {},
        evidence,
    )
    assert result["error"] == "Judge prompt inspected without invoking a model"
    assert {p: p.read_bytes() for p in originals} == originals

    # Model boundary only: the author created both servers before it settled.
    cleanup = workflow.Run(
        "queue-hand-off", ROOT, tmp_path / "cleanup-sample", tmp_path / "shots"
    )
    cleanup.directory.mkdir()
    cleanup_work = tmp_path / "cleanup-originals"
    monkeypatch.setattr(workflow, "LiveChild", lambda *args, **kwargs: None)
    monkeypatch.setattr(workflow, "pinned_copy", lambda *args: None)

    @contextmanager
    def authored(*args, **kwargs):
        for page in (
            cleanup.authored_page,
            cleanup_work / "handoff",
            cleanup.state / "leaf" / "pages" / "note",
        ):
            cleanup.leaf("page", "init", str(page), check=True)
            cleanup.leaf("server", "start", str(page), check=True)
        yield SimpleNamespace(
            answered=0, note=lambda *args: None, settle=lambda *args, **kwargs: False
        )

    monkeypatch.setattr(workflow, "LiveSession", authored)
    workflow.author(cleanup, cleanup_work)
    retained = json.loads((cleanup.directory / "page-phase1-pages.json").read_text())
    assert len(retained) == 3
    for page in arms.pages(cleanup_work):
        assert arms.read_page_state(ROOT, cleanup.state, page)["server"] is None
    shutil.rmtree(cleanup_work)
