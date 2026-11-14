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
from leaf_dev.commands.eval import run as module
from leaf_dev.eval_codex import records_for
from leaf_dev.eval_records import run_samples


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


def test_fork_replay_hands_the_answer_through_the_arms_leaf(tmp_path, monkeypatch):
    # No model runs: a stand-in for Claude Code reads the turn-end check's prompt
    # and answers it, so this shows the question reaching the fork and the answer
    # reaching the grader through the arm's Leaf, its edit landing on the page.
    import os

    from leaf_dev import ROOT, fork_eval

    work = tmp_path / "work"
    asked = tmp_path / "prompt"
    answer = {
        "asks": [],
        "findings": [
            {
                "kind": "stale",
                "page": str(work / "page"),
                "summary": "The lede still says 2 of 5 shards are rebuilt.",
                "quote": "all 5 shards rebuilt; alias search -> search-v7",
                "edit": {
                    "words": "2 of 5 shards are rebuilt",
                    "replacement": "all 5 shards are rebuilt",
                },
            }
        ],
    }
    result = {"type": "result", "subtype": "success", "result": json.dumps(answer)}
    program = (
        f"import sys; open({str(asked)!r}, 'w').write(sys.stdin.read()); "
        f"print({json.dumps(result)!r})"
    )

    def child(cwd, *args, **kwargs):
        home = cwd.with_name("home")
        return {
            "args": [sys.executable, "-c", program],
            "cwd": cwd,
            "env": {**os.environ, "HOME": str(home)},
        }

    monkeypatch.setattr(fork_eval, "claude_child", child)
    response = fork_eval.execute_scenario("stale-edit", ROOT, work)
    metadata = response["metadata"]
    assert metadata["checks"] == {
        "answered": True,
        "labels-found": True,
        "edits-land": True,
    }
    assert "<leaf-fork-check>" in asked.read_text()
    assert (work / "transcript.jsonl").is_file()
    assert "all 5 shards are rebuilt" in metadata["texts"]["judge"]


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
        {"head": tmp_path / "arm"},
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
    reported = run_samples((run,))
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


def test_model_option_sets_the_author_of_every_condition(tmp_path):
    config = module.prepare(
        ["configuration"],
        {"head": tmp_path / "arm"},
        tmp_path / "scratch",
        ("codex",),
        ("leaf", "html"),
        tmp_path / "samples",
        model="named-for-this-run",
    )
    assert [test["metadata"]["condition"] for test in config["tests"]] == [
        "leaf",
        "html",
    ]
    assert {provider["config"]["model"] for provider in config["providers"]} == {
        "named-for-this-run"
    }


def test_eval_command_delegates_configuration_and_status_to_promptfoo(
    tmp_path, monkeypatch
):
    # Replace the external Promptfoo CLI; keep real catalog/configuration generation.
    promptfoo = tmp_path / "promptfoo"
    calls = tmp_path / "calls"
    promptfoo.write_text(f'#!/bin/sh\necho "$*" > {calls}\nexit 100\n')
    promptfoo.chmod(0o755)

    def build_arm(ref, destination, *, paths=arms.PAYLOAD):
        assert paths == arms.PAYLOAD
        (destination / "skills" / "leaf").mkdir(parents=True)
        return "0123456789abcdef"

    monkeypatch.setattr(module, "PROMPTFOO", promptfoo)
    monkeypatch.setattr(module, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(arms, "build_arm", build_arm)
    result = CliRunner().invoke(
        module.eval,
        [
            "--harness",
            "claude-code",
            "patch-review",
            "--base",
            "HEAD",
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
    (run,) = (tmp_path / "runs").iterdir()
    config = json.loads((run / "promptfooconfig.json").read_text())
    assert len(config["tests"]) == 1
    # Each arm is its own payload copy, kept with the run for grading again.
    assert {
        provider["label"]: provider["config"]["payload"]
        for provider in config["providers"]
    } == {
        f"claude-code/{arm}/workflow": str(run / "arms" / arm)
        for arm in ("base", "head")
    }
    assert config["providers"][0]["config"]["viewports"] == ["phone", "desktop"]
    assert "--viewport" not in calls.read_text()


def saved_run(run: Path) -> Path:
    """A retained run of one complete task: two saved samples in each of two
    columns, the last from an author that did not complete."""
    from leaf_dev.arrangement_eval import comparison_inputs

    comparison = comparison_inputs("document-live-status", ("phone",))
    providers, results = [], []
    for arm in ("base", "head", "base", "head"):
        label = f"codex:app-server/{arm}/workflow"
        providers.append(
            {
                "id": "file://provider.py",
                "label": label,
                "config": {"harness": "codex", "model": arm},
            }
        )
        work = run / "samples" / f"document-{arm}-{len(results)}"
        response = {
            "output": f"{arm} summary",
            "metadata": {
                "work": str(work),
                "checks": {"completed": True},
                "diagnostics": {
                    "subject": "document-live-status",
                    "comparison": comparison,
                    "payload": f"/original/{arm}",
                    "condition": "leaf",
                    "phases": {
                        version: {
                            "page": str(work / f"page-phase{version}"),
                            "trace": {"reply": f"{arm} phase {version}"},
                        }
                        for version in comparison["phases"].values()
                    },
                },
            },
        }
        results.append(
            {
                "id": f"result-{len(results)}",
                "provider": {"id": "file://provider.py", "label": label},
                "testCase": {
                    "description": "Live status document",
                    "vars": {"prompt": "configuration"},
                    "metadata": {"case": "configuration", "condition": "leaf"},
                },
                "response": response
                | ({"error": "Author did not complete"} if len(results) == 3 else {}),
            }
        )
    run.mkdir(parents=True)
    (run / "results.json").write_text(
        json.dumps(
            {"config": {"providers": providers}, "results": {"results": results}}
        )
    )
    return run


def test_from_replays_saved_outputs_under_current_grading(tmp_path, monkeypatch):
    """`--from` builds Promptfoo tests that replay saved results, with no author."""
    from leaf_dev import regrade

    login = tmp_path / "login"
    login.mkdir()
    (login / "auth.json").write_text("{}")
    monkeypatch.setenv("CODEX_HOME", str(login))
    promptfoo = tmp_path / "promptfoo"
    promptfoo.write_text("#!/bin/sh\nexit 0\n")
    promptfoo.chmod(0o755)
    monkeypatch.setattr(module, "PROMPTFOO", promptfoo)
    monkeypatch.setattr(module, "RUNS", tmp_path / "runs")
    run = saved_run(tmp_path / "saved")
    original = (run / "results.json").read_bytes()

    # Each saved output is graded by its case's current assertions in its own
    # column, and a failed response fails again without being graded.
    result = CliRunner().invoke(module.eval, ["--from", str(run)])
    assert result.exit_code == 0, result.output
    config = json.loads(
        next((tmp_path / "runs").glob("*/promptfooconfig.json")).read_text()
    )
    assert [p["label"] for p in config["providers"]] == [
        "codex:app-server/base/workflow",
        "codex:app-server/head/workflow",
    ]
    assert {p["id"] for p in config["providers"]} == {regrade.REPLAY}
    current = module.grading(module.catalog()["configuration"], "leaf", lambda: {})
    for test in config["tests"]:
        assert test["assert"] == current["assert"]
        assert test["vars"] == {"prompt": "configuration"}
        (reference,) = test["metadata"]["saved"]
        replayed = regrade.replay("", {}, {"test": test})
        assert replayed["output"] == f"{reference['sample'].split('-')[1]} summary"
        assert replayed["metadata"]["work"].endswith(reference["sample"])
    assert [
        regrade.replay("", {}, {"test": t}).get("error") for t in config["tests"]
    ] == [
        None,
        None,
        None,
        "Author did not complete",
    ]

    result = CliRunner().invoke(module.eval, ["--from", str(run), "--harness", "codex"])
    assert result.exit_code != 0 and "--harness" in result.output
    assert (run / "results.json").read_bytes() == original


def test_judgments_of_saved_samples_reach_the_report(tmp_path, monkeypatch):
    """Only the live judge is replaced: the tests, their replayed samples, page
    roles, evidence and the report's reading of both orders are real."""
    from leaf_dev import regrade
    from leaf_dev.commands.eval import report as eval_report

    run = saved_run(tmp_path / "saved")
    base, head = (
        "codex:app-server/base/workflow",
        "codex:app-server/head/workflow",
    )
    judged = []

    def judge(pages, widths, prompt, schema, evidence, *, handovers):
        assert evidence.parent == tmp_path / "out" / "judgments"
        judged.append((set(pages), prompt))
        if "overall" not in schema["properties"]:
            return {
                "output": {
                    "status": "complete",
                    "explored": "Desktop navigation.",
                    "observations": [],
                    "unverified": [],
                },
                "metadata": {"evidence": str(evidence)},
            }
        # The judge prefers the head's page in whichever position it stands.
        better = "A" if pages["A"]["payload"].name == "head" else "B"
        worse = {"A": "B", "B": "A"}[better]
        return {
            "output": {
                "status": "complete",
                **{aspect: better for aspect in (*regrade.ASPECTS, "overall")},
                "margin": "clear",
                f"defects_{worse}": ["Clipped table"],
                f"defects_{better}": [],
                "reason": "The head keeps the table readable.",
            },
            "metadata": {"evidence": str(evidence)},
        }

    monkeypatch.setattr(regrade, "judge_pages", judge)

    def graded(name: str, variables: dict) -> tuple[Path, list[dict]]:
        """Run the named judgment's tests as Promptfoo would, and save the run."""
        config = module.saved_config((run,), (), name, tmp_path / "out", tmp_path)
        results = []
        for index, test in enumerate(config["tests"]):
            result = {"id": f"{name}-{index}", "testCase": test}
            response = regrade.replay("", {}, {"test": test})
            # Promptfoo grades no response that failed.
            if "error" not in response:
                (assertion,) = test["assert"]
                outcome = getattr(regrade, name)(
                    None,
                    {
                        "providerResponse": response,
                        "test": test,
                        "vars": {**test["vars"], **variables},
                        "config": assertion["config"],
                    },
                )
                assert outcome["pass"], outcome["reason"]
                result["gradingResult"] = {"componentResults": [outcome]}
            results.append(result)
        judging = tmp_path / name
        judging.mkdir()
        (judging / "results.json").write_text(
            json.dumps({"config": config, "results": {"results": results}})
        )
        return judging, results

    # Each pair is judged in both presentation orders, and the report counts a
    # winner both orders name, by column. The author that did not complete keeps
    # its place, and its pair is unscored.
    judging, results = graded("pair", {})
    assert [
        [reference["column"] for reference in result["testCase"]["metadata"]["saved"]]
        for result in results
    ] == [[base, head], [head, base]] * 2
    assert head in results[1]["gradingResult"]["componentResults"][0]["reason"]
    assert judged[0][0] == {
        f"{position}{suffix}"
        for position in "AB"
        for suffix in ("", "_before_decision", "_before_revision")
    }
    (source, pair), (_, unscored) = eval_report.pair_records((judging,))
    assert source == judging / "results.json"
    assert pair["status"] == "complete" and pair["winner"] == head
    assert pair["orders"][1]["defects"] == {base: ["Clipped table"], head: []}
    assert unscored["status"] == "unscored" and unscored["orders"] == [None, None]
    assert eval_report.run_samples((judging,)) == {}

    judging, _ = graded("discovery", {"focus": "Investigate long decision premises"})
    pages, prompt = judged[-1]
    assert pages == {"page", "page_before_decision", "page_before_revision"}
    assert "Investigate long decision premises" in prompt
    section = eval_report.discovery_section(tmp_path / "report", (judging,))
    assert section.count("Desktop navigation.") == 3


def test_review_citations_become_leaf_elements_the_page_check_accepts(tmp_path):
    """The browser is the last of the review's tabs, and each citation draws its saved
    captures and links that land, while one that names nothing stops the report."""
    import turbohtml
    from PIL import Image

    from leaf_dev.commands.eval import report as eval_report

    run = saved_run(tmp_path / "saved")
    for sample in ("document-base-0", "document-head-1"):
        shots = run / "screenshots" / sample
        shots.mkdir(parents=True)
        for name in run_samples((run,))["document-live-status"][
            "codex:app-server/base/workflow"
        ][0]["diagnostics"]["comparison"]["widths"]:
            for phase in ("3", "5"):
                Image.new("RGB", (8, 8)).save(shots / f"p{phase}-{name}-1.png")
    patch = tmp_path / "change.diff"
    patch.write_text(
        "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n"
        "@@ -1,2 +1,2 @@\n \n-old\n+new\n"
    )
    review = tmp_path / "review.html"
    review.write_text(
        f"""<h1 id="title">Keeping the “change”</h1>
<lf-tabs id="review-views">
  <lf-tab id="report-introduction" label="Introduction">
    <p>A review’s own words.</p>
    <lf-eval-cite before="saved/document-base-0" after="saved/document-head-1@3"
      before-label="Base" aligned></lf-eval-cite>
    <p><lf-eval-cite file="{patch}" label="The change" links></lf-eval-cite></p>
    <lf-eval-cite id="patch" file="{patch}" label="The patch"></lf-eval-cite>
    <p><lf-eval-cite id="head" output="saved/document-head-1" links></lf-eval-cite>
      <a href="#head">again</a></p>
    <lf-eval-cite id="uncaptured" output="saved/document-base-0@4"></lf-eval-cite>
  </lf-tab>
</lf-tabs>
"""
    )
    page = tmp_path / "report"
    arguments = [str(page), str(run), "--review", str(review)]

    result = CliRunner().invoke(eval_report.eval_report, arguments)

    assert result.exit_code == 0, result.output
    written = (page / "index.html").read_text()
    assert "lf-eval-cite" not in written
    assert "<title>Keeping the “change”</title>" in written
    document = turbohtml.parse(written)
    assert [tab.attrs["id"] for tab in document.select("#review-views > lf-tab")] == [
        "report-introduction",
        "all-results",
    ]
    assert written.count("<lf-shot ") == 1
    assert written.count('<lf-diff id="patch" collapsed>') == 1
    assert "\n&#32;\n-old" in written
    # Every link the citations write lands, a sample's link back to its citation too.
    ids = {element.attrs["id"] for element in document.select("[id]")}
    hrefs = {str(link.attrs["href"])[1:] for link in document.select('a[href^="#"]')}
    assert hrefs and hrefs <= ids
    assert "Base and After · " in written
    # A phase with no captures still offers its links.
    uncaptured = written.split('id="uncaptured"')[1].split("No screens.")[0]
    assert "and details</a>" in uncaptured
    eval_report.leaf("page", "check", str(page))

    for missing in (
        "saved/document-absent",
        "elsewhere/document-base-0",
        "saved/document-base-0@9",
    ):
        review.write_text(
            f'<h1>Report</h1><lf-eval-cite output="{missing}"></lf-eval-cite>'
        )
        result = CliRunner().invoke(eval_report.eval_report, arguments)
        assert result.exit_code != 0 and missing in result.output
    for refused, said in (
        ('<lf-eval-cite file="/absent.json"></lf-eval-cite>', "/absent.json"),
        (f'<lf-eval-cite file="{patch}">Words</lf-eval-cite>', "takes no content"),
    ):
        review.write_text(f"<h1>Report</h1>{refused}")
        result = CliRunner().invoke(eval_report.eval_report, arguments)
        assert result.exit_code != 0 and said in result.output
    assert (page / "index.html").read_text() == written


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
