"""CLI, plugin payload, layer, and customization tests."""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import tomllib
from datetime import datetime
from pathlib import Path

import pytest
import tinycss2
from click.testing import CliRunner
from conftest import LEAF_COMMAND, PagePool, _retire
from interact_support import (
    COMMAND_HUB_PACKAGE,
    COMPOSITE_TIMEOUT,
    PAGE,
    PLUGIN_ROOT,
    ROOT,
    SHIPPED_PACKAGES,
    SKILL_ROOT,
    STATED_TIMEOUT,
    add_test_widget,
    case_alias,
    command_findings,
    declare_on_page,
    element_declaration,
    fetch,
    install_payload,
    js_facts,
    lock_contention,
    package_findings,
    publish,
    record_claim,
    registry_refusal,
    shipped_payload,
    vendored_at_another_protocol,
    wait_for,
    words,
)
from model_folds import leaf_page
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

from leaf import cli as cli_model
from leaf import data as data_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import files as interact_files
from leaf import hooks as hooks_model
from leaf import layer as layer_model
from leaf import locations as interact_locations
from leaf import machine as machine_model
from leaf import packages as packages_model
from leaf import schema as schema_model
from leaf import state as cleanup_model
from leaf import structure as structure_model
from leaf import vendoring as vendoring_model
from leaf.findings import Finding
from leaf.page import page_instructions
from leaf.refusals import Refused
from leaf.registry import storage as registry_storage
from leaf.registry import widgets as registry_widgets
from leaf.registry.contract import DECLARED_WORDS
from leaf.render_gate import browser as browser_model
from leaf.render_gate.preview import preview_server
from leaf.revisioning import activate_source


def storage_contract() -> tuple[list[str], list[str]]:
    """The files and directories page-storage.md's "Files" section puts in a page.

    Each entry is a bullet opening on its name in a code span; a name beneath a
    directory (`revisions/rN-H.html`) is that directory's entry. A virtual address
    (`/versions/…`) and state kept outside the page (`<state-home>/…`) are not in it.
    """
    text = (ROOT / "src" / "leaf" / "page-storage.md").read_text()
    section = text.split("\n## Files\n", 1)[1].split("\n## ", 1)[0]
    files, directories = set(), set()
    for name in re.findall(r"^- `([^`]+)`", section, re.MULTILINE):
        if name.startswith(("/", "<")):
            continue
        head, beneath, _ = name.partition("/")
        (directories if beneath else files).add(head)
    return sorted(files), sorted(directories)


STORAGE_FILES, STORAGE_DIRECTORIES = storage_contract()


def layer_files(page: Path) -> dict[str, bytes]:
    """The files the layer `page` selects serves, by rooted path."""
    return registry_storage.selected(registry_storage.layer_record(page), page).files


def layer_instructions(page: Path) -> dict[str, bytes]:
    """The instructions the layer `page` selects composes, by file name."""
    record = registry_storage.layer_record(page)
    return registry_storage.selected(record, page).directory_files["instructions"]


def test_cli_help_groups_commands_with_complete_summaries(regtest):
    cases = {
        "root": ["--help"],
        "codex": ["codex", "--help"],
        "connection": ["connection", "--help"],
        "data": ["data", "--help"],
        "package": ["package", "--help"],
        "package-init": ["package", "init", "--help"],
        "page": ["page", "--help"],
        "server": ["server", "--help"],
        "thread": ["thread", "--help"],
    }
    outputs = []

    for name, args in cases.items():
        result = CliRunner().invoke(
            cli_model.cli,
            args,
            prog_name="leaf",
            terminal_width=80,
        )

        assert result.exit_code == 0
        # pytest-regtest treats code points above Latin-1 as binary.
        output = result.output.encode("ascii", "backslashreplace").decode()
        outputs.append(f"## {name}\n{output}")

    regtest.write("\n".join(outputs))


def test_wait_help_says_where_a_delivery_says_how_to_confirm_it():
    result = CliRunner().invoke(
        cli_model.cli,
        ["wait", "--help"],
        terminal_width=200,
    )

    assert result.exit_code == 0
    assert "--forward" not in result.output
    normalized = " ".join(result.output.split())
    instruction = schema_model.WAIT_BATCH_OUTPUT_INSTRUCTION
    assert " ".join(instruction.split()) in normalized


def test_agent_interaction_command_help(regtest):
    """The complete help an agent follows between receiving and answering input.

    Keep the full CLI output, including options, beside the snapshots of what the
    hooks and waits print to the agent. A prose review can then follow a command
    named by a reminder without reconstructing its help from source docstrings.
    """
    outputs = []
    for command in (
        "wait",
        "delivery read",
        "delivery ack",
        "page state",
        "page claim",
        "thread summarize",
        "page open",
        "page close",
        "thread create",
        "thread reply",
        "thread edit",
        "thread resolve",
        "task end",
        "page report",
        "page check",
        "page stamp",
    ):
        result = CliRunner().invoke(
            cli_model.cli,
            [*command.split(), "--help"],
            prog_name="leaf",
            terminal_width=80,
        )
        assert result.exit_code == 0, result.output
        outputs.append(f"## leaf {command} --help\n{result.output}")
    regtest.write("\n".join(outputs).encode("ascii", "backslashreplace").decode())


def test_reply_command_guides_selection_and_followup(claimed, server, regtest):
    """Actual CLI recovery after two user messages arrive in one delivery."""
    page = claimed
    publish(page)
    runner = CliRunner()
    ids = []
    outputs = []
    references = []

    def record(args, code):
        result = runner.invoke(cli_model.cli, args, prog_name="leaf")
        assert result.exit_code == code, result.output
        output = result.output
        if code == 0:
            # A write prints its record; its own id and time differ each run.
            output = "".join(
                json.dumps({key: record[key] for key in ("kind", "parent")}) + "\n"
                for record in map(json.loads, output.splitlines())
            )
        text = f"$ leaf {' '.join(args)}\nexit: {code}\n{output}"
        text = text.replace(str(page), "/page")
        for ref in references:
            text = text.replace(ref, "response-ref")
        for number, event_id in enumerate(ids, 1):
            text = text.replace(event_id, f"user-{number}")
        outputs.append(text)

    record(["thread", "reply", "--text", "Answer"], 2)
    for text in ("Why this plan?", "What will it cost?"):
        code, response = fetch(
            f"{server}/api/event",
            data=json.dumps({"kind": "comment", "revision": 1, "text": text}).encode(),
        )
        assert code == 200, response
        ids.append(events_model.read_events(page)[-1]["id"])
    # Undelivered, the owed message has no reference yet: the refusal names the
    # wait that delivers one.
    record(["thread", "reply", str(page), ids[0], "--text", "Answer"], 1)
    woke = runner.invoke(cli_model.cli, ["wait", str(page)])
    assert woke.exit_code == 0, woke.output
    envelope = json.loads(woke.output)
    assert f"leaf delivery ack {envelope['id']} && leaf wait" in envelope["acknowledge"]
    delivery_model.receive(envelope, "s1")
    [batch] = envelope["batches"]
    assert len(batch["events"]) == 2
    reference = batch["events"][0]["answer"]["ref"]
    references.append(reference)
    # Delivered, the refusal names the delivery's exact reference.
    record(["thread", "reply", str(page), "--text", "Answer", "--done"], 1)
    record(["thread", "reply", str(page), ids[0], "--text", "Answer"], 1)

    def response_args(*extra):
        return ["thread", "reply", reference, "--text", "Answer", "--done", *extra]

    record(response_args(), 0)
    answered_events = events_model.read_events(page)
    record(response_args(), 0)
    assert events_model.read_events(page) == answered_events
    for addressed_option in (["--done"],):
        record(
            [
                "thread",
                "reply",
                str(page),
                ids[0],
                "--text",
                "Follow-up",
                *addressed_option,
            ],
            2,
        )
    assert events_model.read_events(page) == answered_events
    record(
        ["thread", "reply", str(page), ids[0], "--text", "Follow-up", "--obligation"],
        0,
    )
    followup = events_model.read_events(page)[-1]
    assert followup["parent"] == ids[0]
    assert followup["obligation"] is True
    # A page reaction can close without an answer: it never owed a reply.
    code, response = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "comment", "revision": 1, "token": "keep"}).encode(),
    )
    assert code == 200, response
    ids.append(events_model.read_events(page)[-1]["id"])
    record(["thread", "reply", "not-a-response-ref", "--text", "Answer", "--done"], 1)
    record(["thread", "resolve", str(page), ids[-1]], 0)
    regtest.write("\n".join(outputs).encode("ascii", "backslashreplace").decode())


@pytest.mark.parametrize("unreadable", ["claim", "lifecycle"])
def test_read_commands_leave_an_older_page_and_its_server_alone(
    claimed, server, unreadable
):
    """A read by another session cannot take a held page across a protocol bump."""
    from leaf.service import claim_path

    publish(claimed)
    vendored = vendored_at_another_protocol(claimed)
    record = (
        claim_path(claimed)
        if unreadable == "claim"
        else cleanup_model.session_file("s1", cleanup_model.SESSION_SUFFIX)
    )
    stored = interact_files.read_json(record)
    stored["format"] = "leaf-" + unreadable + "/999"
    cleanup_model.write_json(record, stored)
    revisions = interact_files.list_revisions(claimed)
    recorded = (claimed / schema_model.LAYER_FILE).read_bytes()
    for command in (
        ["page", "state", str(claimed)],
        ["page", "events", str(claimed)],
        ["page", "instructions", str(claimed)],
        ["page", "check", str(claimed)],
    ):
        subprocess.run(
            [*LEAF_COMMAND, *command],
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
            env={**os.environ, "CLAUDE_CODE_SESSION_ID": "s2"},
        )
        same_record = (claimed / schema_model.LAYER_FILE).read_bytes() == recorded
        assert same_record, command
        assert interact_files.list_revisions(claimed) == revisions
        assert fetch(f"{server}/api/state")[0] == 200
    assert registry_storage.layer_record(claimed)["protocol"] == vendored
    assert vendoring_model.renew_layer(claimed, None, command=True) is None
    assert (claimed / schema_model.LAYER_FILE).read_bytes() == recorded


def test_a_command_leaves_a_page_a_newer_leaf_vendored(claimed):
    """A process the session started before its plugin updated still runs the older
    Leaf, and must not take the page back to it: the newer Leaf's next hook would
    re-vendor it up again, reloading the user's tabs each time. Neither a command
    naming the page nor an explicit `page init` re-vendors it down, and each names
    the newer Leaf as the repair rather than the re-vendor it refuses."""
    publish(claimed)
    foreign = vendored_at_another_protocol(claimed, newer=True)
    for command in (["page", "check"], ["page", "init"]):
        refused = CliRunner().invoke(cli_model.cli, [*command, str(claimed)])
        assert refused.exit_code != 0
        assert f"Use a Leaf at protocol {foreign} or later" in refused.output
        assert "leaf page init" not in refused.output
        assert registry_storage.layer_record(claimed)["protocol"] == foreign
    # A fresh process in a session that does not hold the page reads the state of
    # the revision published before, and reports the same refusal as its source
    # error.
    stated = subprocess.run(
        [*LEAF_COMMAND, "page", "state", str(claimed)],
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
        env={**os.environ, "CLAUDE_CODE_SESSION_ID": "s2"},
    )
    assert stated.returncode == 0, stated.stderr
    error = json.loads(stated.stdout)["source"]["error"]
    assert f"Use a Leaf at protocol {foreign} or later" in error


def test_page_state_reports_a_layer_this_leaf_cannot_serve(claimed):
    """`page state` on a page this Leaf can neither serve nor write, from a session
    that may not re-vendor it since another one holds the page, still prints its
    reading, and says why under `source.error`, naming the re-vendor, from the one
    reading the servers and the append door refuse on (`layer.incompatible_layer`).
    Activation writes no revision under that layer, even for an edited source.

    A fresh process, as an agent's is: this one holds the revision `publish`
    captured in memory, under the vocabulary before the change."""
    page_dir = claimed
    publish(page_dir)
    vendored_at_another_protocol(page_dir)
    source = page_dir / "index.html"
    source.write_text(source.read_text().replace("<h2>Plan</h2>", "<h2>Plans</h2>"))
    revisions = interact_files.list_revisions(page_dir)

    result = subprocess.run(
        [*LEAF_COMMAND, "page", "state", str(page_dir)],
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
        env={**os.environ, "CLAUDE_CODE_SESSION_ID": "s2"},
    )
    assert result.returncode == 0, result.stderr
    state = json.loads(result.stdout)
    assert state["source"]["live"] is False
    assert "page protocol" in state["source"]["error"]
    assert f"leaf page init {page_dir}" in state["source"]["error"]
    assert state["active"]["revision"] == revisions[-1]
    assert interact_files.list_revisions(page_dir) == revisions


def test_the_skill_routes_every_reference_it_ships():
    """A reference SKILL.md never links is a file no session opens.

    The set comes from the directory rather than a list here, because a list is the
    second copy: adding a reference and forgetting to route it would leave it green.
    """
    root = SKILL_ROOT
    skill = (root / "SKILL.md").read_text()
    references = sorted((root / "references").rglob("*.md"))

    assert references, "no references read — an empty set routes itself"
    for path in references:
        relative = path.relative_to(root).as_posix()
        assert relative in skill, relative


def test_the_root_instructions_name_every_directory_of_the_projects_own_tree():
    """A top-level directory a session works in must be named where sessions read.

    The dotted directories belong to the harnesses and the tooling that read them, and
    a session finds each through the harness rather than through this map. The rest
    are the project's own tree, and every one of them is somewhere a session is
    sent to read or write. A session that lands in one the map never names has
    only the files in front of it to say what the directory is for — which is how
    `notes/` and `docs/` went unnamed while commits kept landing in both. The set
    comes from the tracked tree rather than a list here, for the reason the
    routing above states: a list is the second copy, and the directory added
    without the paragraph would stay green.

    The prefix is matched without its closing backtick, because a part is named at
    whatever depth it is owned at — `bin/leaf` is a launcher and
    `browser/` is a tree, and both name their directory.
    """
    instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    tops = {
        relative.parts[0]
        for path in shipped_payload()
        if len((relative := path.relative_to(PLUGIN_ROOT)).parts) > 1
    }
    directories = sorted(top for top in tops if not top.startswith("."))

    assert directories, "no directories read — an empty set names itself"
    unnamed = [d for d in directories if f"`{d}/" not in instructions]
    assert not unnamed, f"unnamed in AGENTS.md: {unnamed}"


def test_workflow_shell_continuations_use_literal_blocks():
    """A plain YAML scalar folds the newline before the shell sees the command."""
    workflows = list((ROOT / ".github" / "workflows").glob("*.y*ml"))
    assert workflows, "no workflows read — an empty set guards nothing"

    offenders = [
        f"{path.relative_to(ROOT)}:{line_number}"
        for path in workflows
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        )
        if re.match(r"^\s*run:\s+.*\\\s*$", line)
    ]

    assert not offenders, f"plain run scalars with shell continuations: {offenders}"


@pytest.mark.parametrize(
    "argv",
    [
        ["hook"],
        ["hook", "--harness"],
        ["hook", "--harness", "codex", "--bogus"],
        ["hook", "--harness", "codex", "--watch", "--pages"],
        ["session-end", "now"],
    ],
)
def test_harness_commands_report_click_usage_errors(argv):
    result = CliRunner().invoke(cli_model.cli, argv, input="{}")
    assert result.exit_code == 2
    assert result.stdout == ""
    assert json.loads(result.stderr)["error"]


def test_hook_options_use_click_order_and_help():
    runner = CliRunner()
    result = runner.invoke(
        cli_model.cli, ["hook", "--watch", "--harness=codex"], input="{}"
    )
    assert result.exit_code == 0, result.output
    assert result.output == ""
    help_result = runner.invoke(cli_model.cli, ["hook", "--help"])
    assert help_result.exit_code == 0
    assert "--harness" in help_result.output


def test_a_page_command_names_what_its_path_holds_instead(tmp_path, regtest):
    """A page command given the page's `index.html`, or a page source elsewhere, is
    told it was handed a file, and a directory with no log is offered `page init`."""
    source = tmp_path / "page.html"
    source.write_text(PAGE)
    for path in (source, tmp_path / "missing"):
        result = CliRunner().invoke(cli_model.cli, ["page", "state", str(path)])
        assert result.exit_code == 1
        print(result.output.replace(str(tmp_path), "<tmp>"), end="", file=regtest)


def test_a_write_prints_the_records_it_appended(tmp_path, monkeypatch):
    """Silence cannot tell an agent a no-op from a call that landed, and a sentence
    leaves it to guess at the id it needs next.

    Every write prints what it wrote, as JSON: an appended event exactly as `page
    events` reads it back, `seq` included, one line per record, and a status as its
    declaration stands in the status file. A command that also names its thread
    prints both records. `test_receipt_settles_one_known_request_once` holds the
    receipt's, since it needs a page with a request seat.

    The default layer declares no instructions audiences, which is why the page is
    built here rather than taken from the packaged fixture.
    """
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page_dir = tmp_path / "page"

    def written(args) -> list[dict]:
        result = runner.invoke(cli_model.cli, args)
        assert result.exit_code == 0, result.output
        return [json.loads(line) for line in result.output.splitlines()]

    def logged(record: dict) -> dict:
        return next(
            event
            for event in events_model.read_events(page_dir)
            if event["id"] == record["id"]
        )

    assert written(["page", "init", str(page_dir)]) == [{"page": str(page_dir)}]
    (page_dir / "index.html").write_text(PAGE)

    audiences = runner.invoke(cli_model.cli, ["page", "instructions", str(page_dir)])
    assert audiences.exit_code == 0, audiences.output
    assert json.loads(audiences.output) == {}

    [stamped] = written(["page", "stamp", str(page_dir), "--text", "first cut"])
    assert stamped == logged(stamped)
    assert (stamped["kind"], stamped["version"], stamped["seq"]) == ("note", 1, 1)

    again = runner.invoke(
        cli_model.cli, ["page", "stamp", str(page_dir), "--text", "again"]
    )
    assert again.exit_code != 0  # nothing changed, so there is no second version
    assert "already stamped as v1" in again.output

    [waiting] = written(["page", "open", str(page_dir)])
    assert waiting == logged(waiting)
    assert waiting["state"] == "waiting"

    # The comment's id is the thread's; --title names it in the same command.
    [opened] = written(
        [
            "thread",
            "create",
            str(page_dir),
            "--text",
            "which store?",
            "--title",
            "Storage",
        ]
    )
    root = opened["id"]
    assert opened == logged(opened)
    assert opened["title"] == "Storage"

    # A refused title refuses the whole command, so no message goes up unnamed.
    before = events_model.read_events(page_dir)
    [unnamed] = command_findings(
        "thread", "create", page_dir, "--text", "and the cache?", "--title", ""
    )
    assert (unnamed.code, unnamed.values["kind"]) == ("invalid-event", "comment")
    assert events_model.read_events(page_dir) == before

    for command, rejected_kind in (
        (
            ["thread", "reply", str(page_dir), root, "--text", "x", "--title", "a\nb"],
            "reply",
        ),
        (
            ["thread", "edit", str(page_dir), root, "--text", "y", "--title", " "],
            "thread_title",
        ),
    ):
        [refused] = command_findings(*command)
        assert (refused.code, refused.values["kind"]) == (
            "invalid-event",
            rejected_kind,
        )
        assert events_model.read_events(page_dir) == before

    # A reply's --title names only a thread nothing has named, so a name the harness
    # gave the thread while the agent worked stands; edit renames one.
    followed = runner.invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            root,
            "--text",
            "and wal mode",
            "--title",
            "WAL",
        ],
    )
    assert followed.exit_code == 0, followed.output
    [followed] = [json.loads(line) for line in followed.stdout.splitlines()]
    assert followed == logged(followed)
    assert followed["parent"] == root
    assert [
        event["title"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "thread_title"
    ] == []
    later = followed["id"]

    # Every command naming a thread takes any message in it, as reply does.
    [renamed] = written(["thread", "edit", str(page_dir), later, "--title", "Store"])
    assert (renamed["thread"], renamed["title"]) == (root, "Store")
    [edited] = written(["thread", "edit", str(page_dir), later, "--text", "and WAL"])
    assert (edited["kind"], edited["message"]) == ("edit", later)
    read = runner.invoke(cli_model.cli, ["page", "state", str(page_dir), later])
    assert read.exit_code == 0, read.output
    assert json.loads(read.output)["thread"]["id"] == root
    both = runner.invoke(
        cli_model.cli,
        ["thread", "reply", str(page_dir), root, "--for", root, "--text", "x"],
    )
    assert both.exit_code == 2
    assert "No such option '--for'" in both.output

    [todo] = written(
        ["thread", "reply", str(page_dir), later, "--text", "On it.", "--todo", "Trace"]
    )
    assert (todo["parent"], todo["todo"]) == (later, "Trace")

    [closed] = written(["thread", "resolve", str(page_dir), later])
    assert (closed["kind"], closed["parent"]) == ("resolve", later)


def test_init_help_names_the_source_revision_and_version_layout():
    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "init", "--help"],
        prog_name="leaf",
        terminal_width=80,
    )

    assert result.exit_code == 0
    help_text = " ".join(result.output.split())
    assert "composes its layer from the selection" in help_text
    assert "author writes PAGE/index.html" in help_text
    assert "--package" in result.output


@pytest.mark.parametrize(
    "args",
    [
        ["hook", "--harness", "codex"],
        ["hook", "--harness", "claude-code", "--watch"],
        ["page", "check", "page", "--render"],
        ["thread", "reply", "page", "--for", "c1", "--text", "export"],
    ],
)
def test_shim_dispatches_every_command_through_one_uv_run(tmp_path, monkeypatch, args):
    fake_uv = tmp_path / "uv"
    fake_uv.write_text(
        '#!/bin/sh\nfor cli_arg in "$@"; do\n  printf "%s\\n" "$cli_arg"\ndone\n'
    )
    fake_uv.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    shim = PLUGIN_ROOT / "bin" / "leaf"
    selected = tmp_path / "selected-leaf"
    selected.symlink_to(shim)
    monkeypatch.setenv("LEAF_HOST_LAUNCHER", str(selected))

    result = subprocess.run(
        [shim, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    dispatched = result.stdout.splitlines()
    # One dispatch shape for every command, stated whole rather than as flags
    # that appear somewhere in it: an index named here would take the host's say
    # away, and the project has to be the payload beside the launcher rather
    # than whatever project the caller's directory sits in. `--no-dev` because
    # the dev group is the suite and the repo's own scripts, neither a harness's to
    # install. The module rather than the `leaf` console script because a long
    # payload path turns the console script into a `/bin/sh` trampoline.
    assert dispatched == [
        "run",
        "-q",
        "--no-dev",
        "--project",
        str(PLUGIN_ROOT),
        "python",
        "-m",
        "leaf",
        *args,
    ]


def test_the_launcher_uses_the_hosts_selected_leaf_for_commands_and_hooks(
    tmp_path, monkeypatch
):
    """A native plugin must retain the host's Python environment and hook stdin."""
    launcher = tmp_path / "plugin" / "bin" / "leaf"
    launcher.parent.mkdir(parents=True)
    shutil.copy2(PLUGIN_ROOT / "bin" / "leaf", launcher)
    interpreter = launcher.parent.parent / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("#!/bin/sh\nexit 3\n")
    interpreter.chmod(0o755)
    selected = tmp_path / "selected leaf"
    selected.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        'sys.stdout.write("".join(f"{arg}\\n" for arg in sys.argv[1:]) + sys.stdin.read())\n'
        "sys.exit(23)\n"
    )
    selected.chmod(0o755)
    monkeypatch.setenv("LEAF_HOST_LAUNCHER", str(selected))
    for args, payload in [
        (["page", "check", "a page"], ""),
        (["hook", "--harness", "codex"], '{"session_id":"hosted"}'),
    ]:
        result = subprocess.run(
            [launcher, *args],
            input=payload,
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
        assert (result.returncode, result.stdout, result.stderr) == (
            23,
            "".join(f"{arg}\n" for arg in args) + payload,
            "",
        )
    # A host may prepare its environment in a wrapper that invokes Leaf again.
    # The selection belongs to this dispatch, not to the wrapper's child.
    selected.write_text(
        '#!/bin/sh\nexec "' + str(PLUGIN_ROOT / "bin" / "leaf") + '" "$@"\n'
    )
    delegated = subprocess.run(
        [launcher, "--root"],
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert (delegated.returncode, delegated.stdout, delegated.stderr) == (
        0,
        f"{PLUGIN_ROOT}\n",
        "",
    )


def test_the_version_and_root_flags_describe_the_payload_this_leaf_ran_out_of(
    tmp_path,
):
    """Which copy of leaf answered is otherwise unknowable from outside it. A
    harness session runs the payload its plugin cache holds and a checkout stands
    beside it; `bin/leaf` is identical across versions and nothing the CLI
    prints says where it came from. `--version` prints the running source identity
    for reports and harnesses, while `--root` retains the exact payload directory
    needed to distinguish a stale cache from a checkout.

    Two copies asked the same question, because either half alone is satisfied
    by a flag that prints a constant, or the directory the command was typed in.
    The second is a harness's install, run through its own launcher, and nothing
    about it is this checkout.

    Eager and page-free, so it answers with no page named and nothing written
    where it ran, which is the whole of what a session asking the question has.
    """
    cached_commit = "123456789abc"
    cached = install_payload(
        tmp_path / "plugins" / "cache" / "marketplace" / "leaf" / cached_commit
    )
    # A harness's copy carries no `.git`, so the time it was made is the only date it
    # has: every file written then, the running module's own included.
    copied_at = 1_790_000_000
    layer = cached / "src" / "leaf" / "layer.py"
    os.utime(layer, (copied_at, copied_at))
    elsewhere = tmp_path / "unrelated-project"
    elsewhere.mkdir()

    def asked(command, flag, **environment):
        return subprocess.run(
            [*command, flag],
            cwd=elsewhere,
            env=os.environ | environment,
            capture_output=True,
            text=True,
            check=False,
        )

    checkout_launcher = [str(PLUGIN_ROOT / "bin" / "leaf")]
    here = asked(checkout_launcher, "--root")
    assert here.returncode == 0, here.stderr
    assert here.stdout.strip() == str(PLUGIN_ROOT.resolve())

    launcher = [str(cached / "bin" / "leaf")]
    there = asked(launcher, "--root")
    assert there.returncode == 0, there.stderr
    assert there.stdout.strip() == str(cached.resolve())

    version = asked(launcher, "--version", TZ="UTC")
    assert version.returncode == 0, version.stderr
    assert (
        version.stdout.strip()
        == f"leaf {cached_commit}, installed 2026-09-21T14:13:20+00:00"
    )

    checkout = asked(checkout_launcher, "--version")
    assert checkout.returncode == 0, checkout.stderr
    assert re.fullmatch(
        r"leaf [0-9a-f]{12}\+?, committed "
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:Z|[+-]\d\d:\d\d)",
        checkout.stdout.strip(),
    ), checkout.stdout

    assert list(elsewhere.iterdir()) == []


def test_claude_and_codex_load_the_same_plugin_payload():
    claude_marketplace = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text()
    )
    codex_marketplace = json.loads(
        (ROOT / ".agents" / "plugins" / "marketplace.json").read_text()
    )
    claude_manifest = json.loads(
        (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text()
    )
    codex_manifest = json.loads(
        (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text()
    )

    assert claude_marketplace["plugins"][0]["source"] == "./"
    assert codex_marketplace["plugins"][0]["source"] == {
        "source": "local",
        "path": "./",
    }
    assert codex_marketplace["plugins"][0]["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    assert claude_manifest["name"] == codex_manifest["name"] == "leaf"
    assert "version" not in claude_manifest
    assert "version" not in codex_manifest
    for relative in [
        "bin/leaf",
        # The project `bin/leaf` runs and the resolution an install gets.
        "pyproject.toml",
        "uv.lock",
        "hooks/hooks.json",
        "hooks/claude-code.ts",
        "hooks/codex.json",
        "hooks/scripts/background-watch.py",
        "skills/leaf/SKILL.md",
        "skills/leaf/references/authoring-on-me.md",
        "skills/leaf/references/authoring-evidence.md",
        "skills/leaf/references/authoring-revisions.md",
        "skills/leaf/references/codex-watcher.md",
        "skills/leaf/references/conversation-loop.md",
        "skills/leaf/references/threads.md",
        "skills/leaf/references/event-batches.md",
        "skills/leaf/references/harness-claude-code.md",
        "skills/leaf/references/harness-codex.md",
        "skills/leaf/references/codex-setup.md",
        "skills/leaf/references/page-checkpoints.md",
        "skills/leaf/references/packages.md",
        "skills/leaf/references/page-authoring.md",
        "skills/leaf/references/page-behavior.md",
        "skills/leaf/references/page-layout.md",
        "skills/leaf/references/live-samples.md",
        "skills/leaf/references/serving-pages.md",
        "packages/default/registry.json",
        "packages/diagram/registry.json",
        "packages/diff/registry.json",
        "packages/playground/registry.json",
        # The form a leaf process re-launches itself in.
        "src/leaf/__main__.py",
    ]:
        assert (PLUGIN_ROOT / relative).is_file()
    # The shipped plugin carries its canonical project instructions.
    instructions = [p for p in shipped_payload() if p.name == "AGENTS.md"]
    assert instructions, "no project instructions in the shipped payload"
    for agents in instructions:
        assert agents.is_file() and not agents.is_symlink()
    # A harness's copy must not contain links that escape the plugin tree.
    escaping = [
        path
        for path in shipped_payload()
        if path.is_symlink()
        and not path.resolve().is_relative_to(PLUGIN_ROOT.resolve())
    ]
    assert escaping == []
    # A lock pins the resolution and not where it comes from, which is why one
    # ships: `uv sync` pointed at another index asks *that* index for the pinned
    # versions rather than fetching the files.pythonhosted.org URLs written
    # beside them, and `--offline` installs from the cache without asking
    # anyone. What would take the host's own index out of the loop is the
    # payload naming one — in the project file, or in a `uv.toml` beside it —
    # so that is what this forbids. Read off the lines rather than a parsed
    # table because a comment is free to discuss an index where a setting is
    # not. The loopback launcher test below drives the same claim through a real
    # resolve against a closed port.
    configured = [
        line
        for line in (PLUGIN_ROOT / "pyproject.toml").read_text().splitlines()
        if "index" in line and not line.lstrip().startswith("#")
    ]
    assert configured == []
    assert not [path for path in shipped_payload() if path.name == "uv.toml"]
    assert [
        path.relative_to(PLUGIN_ROOT).as_posix()
        for path in shipped_payload()
        if path.suffix == ".lock"
    ] == ["uv.lock"]


def test_page_authoring_names_the_theme_s_largest_spacing_step():
    """Authors read the spacing scale's ends in page-authoring.md rather than the
    theme, so a step the theme adds is one they can find."""
    theme = (PLUGIN_ROOT / "browser/theme.css").read_text()
    largest = max(int(step) for step in re.findall(r"--sp-(\d+):", theme))
    prose = (PLUGIN_ROOT / "skills/leaf/references/page-authoring.md").read_text()
    assert f"`--sp-1` to `--sp-{largest}`" in " ".join(prose.split())


def test_the_launcher_resolves_through_the_hosts_own_index(tmp_path):
    """A closed local index fails without falling back to the shipped lock's URLs.

    A fresh cache makes uv consult the index. Allow uv's local HTTP request even
    when the rest of the suite uses UV_OFFLINE; forbid interpreter downloads and
    ignore host index configuration so this test needs only loopback networking.
    """
    installed = install_payload(tmp_path / "leaf")
    unconfigured = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("UV_INDEX")
        and name
        not in {"UV_DEFAULT_INDEX", "UV_FIND_LINKS", "UV_NO_INDEX", "UV_OFFLINE"}
    }
    mirrored = subprocess.run(
        [installed / "bin" / "leaf", "--help"],
        cwd=tmp_path,
        env={
            **unconfigured,
            "UV_CACHE_DIR": str(tmp_path / "mirror-cache"),
            "UV_DEFAULT_INDEX": "http://127.0.0.1:1/simple",
            "UV_NO_CONFIG": "1",
            "UV_PYTHON": sys.executable,
            "UV_PYTHON_DOWNLOADS": "never",
            "UV_HTTP_RETRIES": "0",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    output = mirrored.stdout + mirrored.stderr
    assert mirrored.returncode != 0, output
    assert "127.0.0.1:1" in output, output
    assert "pypi.org" not in output and "pythonhosted.org" not in output, output


def test_a_run_keeps_its_temporary_tree_out_of_the_candidate_payload(tmp_path):
    """The one flag that can put a run's fixtures inside the tree is refused.

    `--basetemp` is the whole reachable condition: it is the only way the run's
    temporary tree lands anywhere but `$TMPDIR`, and inside the checkout it would
    hand the payload test above every page the run writes. The refusal happens at
    configure time, so collecting one node id is enough to ask for it, and the
    outside path is the control that says what is refused is where the basetemp
    points rather than the flag itself.
    """

    def collect(basetemp):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--collect-only",
                f"--basetemp={basetemp}",
                "-o",
                f"cache_dir={tmp_path / 'cache'}",
                f"{__file__}::test_claude_and_codex_load_the_same_plugin_payload",
            ],
            capture_output=True,
            text=True,
            timeout=COMPOSITE_TIMEOUT,
            check=False,
        )

    inside = PLUGIN_ROOT / "basetemp-under-test"
    refused = collect(inside)
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert "would count as shipped payload" in refused.stdout + refused.stderr

    assert collect(tmp_path / "outside").returncode == 0


def test_the_payload_is_text():
    """Every tracked byte ships in every install and stays in history, so the tree
    holds no screenshot, recording or other binary (`AGENTS.md`, "The install runs
    this tree"). Screenshots came in under `notes/` twice, 5.6M of a probe's evidence
    and then 1.8M of a design study's before/after pairs, each by a maintainer's
    `git add` that no test of a tool's output path sees coming. An image lives in
    max-sixty/leaf-assets, at the path its reader looks for it, and evidence in
    `.tmp/`."""
    binary = []
    for path in shipped_payload():
        if not path.is_file():
            continue
        try:
            path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            binary.append(path.relative_to(PLUGIN_ROOT).as_posix())
    assert binary == [], "binary files in the tree: " + ", ".join(binary)


def test_every_skill_file_reads_in_one_command():
    """An agent reads a skill file with `cat` as often as with Read, and Claude Code
    hands a Bash output over 30,000 characters back as a 2 KB preview with the rest
    saved to a file the agent rarely opens. page-authoring.md at 48 KB reached
    authoring sessions that way until it was split, so each skill's files stay
    under that cap."""
    oversized = {
        path.relative_to(ROOT).as_posix(): size
        for root in (ROOT / "skills", ROOT / ".claude" / "skills")
        for path in root.rglob("*.md")
        if path.name == "SKILL.md" or {"references", "instructions"} & set(path.parts)
        if (size := len(path.read_text())) > 30_000
    }
    assert oversized == {}, oversized


def test_claude_and_codex_read_the_same_repository_skills():
    claude_skills = ROOT / ".claude" / "skills"
    codex_skills = ROOT / ".agents" / "skills"

    assert codex_skills.is_symlink()
    assert codex_skills.resolve() == claude_skills.resolve()


def test_the_selected_layer_holds_its_packages_but_not_the_runtime(page_dir):
    """A page records its selection, with a copy of the package it selects by path,
    and the layer composed from it carries the selected packages' files beside the
    core's, but none of the runtime's."""
    assert sorted(path.name for path in page_dir.iterdir()) == [
        "events.jsonl",
        "index.html",
        "layer.json",
        "packages",
    ]
    assert [path.name for path in (page_dir / "packages").iterdir()] == [
        COMMAND_HUB_PACKAGE.name
    ]
    files = layer_files(page_dir)
    assert "/theme.css" in files
    # The Leaf serving the page supplies its runtime and the kernel's vendor modules
    # (`runtime_selection`), so the layer holds none of them.
    assert "/leaf.js" not in files
    assert not any(path.startswith("/runtime/") for path in files)
    assert "/vendor/jsdiff.esm.js" not in layer_files(page_dir)
    assert "/vendor/floating-ui.esm.js" not in layer_files(page_dir)
    assert "/widgets/lf-tabs.js" in layer_files(page_dir)
    assert "/widgets/lf-chart.js" in layer_files(page_dir)
    assert "/vendor/plot.esm.js" in layer_files(page_dir)
    # The selected packages land in the same flat directories as the default one,
    # which is what lets a widget import `/vendor/…` without knowing where it came
    # from page_packages().
    assert "/widgets/lf-diagram.js" in layer_files(page_dir)
    assert "/vendor/pele.esm.js" in layer_files(page_dir)
    assert "/vendor/pele.LICENSES.txt" in layer_files(page_dir)
    assert "/widgets/lf-diff.js" in layer_files(page_dir)
    assert "/vendor/pierre-diffs.esm.js" in layer_files(page_dir)


def test_init_and_revendoring_preserve_the_page_owned_contribution(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "authored-page"
    authored = page / "page"
    (authored / "widgets").mkdir(parents=True)
    files = {
        "registry.json": json.dumps(
            {"lf-local": element_declaration("lf-local", upgrade=True)}
        ),
        "widgets/lf-local.js": "export function upgrade() {}\n",
        "controller.js": "export const mode = 'authored';\n",
        "theme.css": ".authored { color: rebeccapurple; }\n",
        "config.json": '{"title": "Authored configuration"}\n',
    }
    for name, content in files.items():
        (authored / name).write_text(content)
    runner = CliRunner()

    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    generation = registry_storage.layer_metadata(page)["generation"]
    revendored = runner.invoke(cli_model.cli, ["page", "init", str(page)])

    assert revendored.exit_code == 0, revendored.output
    assert registry_storage.layer_metadata(page)["generation"] == generation
    assert {name: (authored / name).read_text() for name in files} == files
    assert "lf-local" not in registry_storage.load_registry(page)
    composed = registry_storage.read_page_registry(page)
    assert composed.widget_sources["lf-local"] == "page/widgets/lf-local.js"


def test_a_lent_page_comes_back_as_the_shape_it_was_made_from(tmp_path, monkeypatch):
    """`initialized_page` composes a layer once and lends it, so the page a test
    mutates is the page the test after it asserts on. What makes that safe is
    that the reset reads the difference off the filesystem — identity, size,
    modification time — rather than off a list of the files somebody remembered
    a fixture writes. A page-owned file nobody has named yet is removed because
    the shape has not got it, and an edited layer record comes back because its
    stat moved."""
    monkeypatch.chdir(tmp_path)
    pool = PagePool(tmp_path / "shapes")

    def initialize(target):
        made = CliRunner().invoke(cli_model.cli, ["page", "init", str(target)])
        assert made.exit_code == 0, made.output

    first = pool.lend("plain", tmp_path / "first", initialize)
    shape = {path.relative_to(first).as_posix() for path in first.rglob("*")}

    (first / "index.html").write_text("<html></html>")
    (first / "media").mkdir()
    (first / "media" / "shot.png").write_bytes(b"png")
    (first / "notes").mkdir()
    (first / "notes" / "held.txt").write_text("scratch")
    # A symlink where the layer record belongs, and one where nothing does: the
    # reset reads a path as itself rather than as what it points at, so a broken
    # link is a file it removes rather than a stat that raises.
    (first / "layer.json").unlink()
    (first / "layer.json").symlink_to(tmp_path / "nowhere")
    (first / "media" / "elsewhere").symlink_to(tmp_path, target_is_directory=True)
    (first / "stream.json").write_text("{}")
    pool.give_back("plain", first)

    second = pool.lend("plain", tmp_path / "second", initialize)

    template = pool.shapes["plain"].template
    assert {path.relative_to(second).as_posix() for path in second.rglob("*")} == shape
    for name in ("layer.json", "events.jsonl"):
        assert (second / name).read_bytes() == (template / name).read_bytes(), name
    # A stream the test wrote is a file it added, so the reset takes it away.
    assert not (second / "stream.json").exists()


def _css_parse_errors(nodes):
    """Every parse-error token in a tinycss2 reading, at any depth."""
    errors = []
    for node in nodes:
        if node.type == "error":
            errors.append(f"{node.source_line}:{node.source_column} {node.message}")
        errors.extend(_css_parse_errors(getattr(node, "content", None) or []))
    return errors


def test_every_vendored_stylesheet_parses(page_dir):
    """The chrome's sheet was a JavaScript template literal, which `node --check` accepts
    with a body a backtick has cut short and the browser then refuses whole. As files,
    the gate's own CSS parser reads them, and an error token anywhere is the finding.
    The runtime's own sheets come from the Leaf serving the page (`runtime_selection`)."""
    for name, css in [
        ("theme.css", layer_files(page_dir)["/theme.css"].decode()),
        *(
            (name, (schema_model.ASSETS / "runtime" / name).read_text())
            for name in ("chrome.css", "marks.css")
        ),
    ]:
        rules = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
        assert rules, f"{name} is empty"
        assert not _css_parse_errors(rules), f"{name}: {_css_parse_errors(rules)}"


_FACE = frozenset(
    {
        "appearance",
        "background",
        "background-color",
        "border",
        "border-color",
        "border-radius",
        "border-width",
        "color",
        "cursor",
        "font",
        "font-family",
        "font-size",
        "font-style",
        "font-weight",
        "letter-spacing",
        "line-height",
        "opacity",
        "padding",
        "resize",
        "text-align",
        "text-transform",
    }
)


def _split_top(text, separators):
    """Split at separators outside parentheses, brackets and strings."""
    parts, depth, start, quote = [], 0, 0, None
    for at, char in enumerate(text):
        if quote:
            quote = None if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif not depth and char in separators:
            parts.append(text[start:at])
            start = at + 1
    parts.append(text[start:])
    return [part.strip() for part in parts if part.strip()]


def _selector_list(prelude, parent=()):
    """The complex selectors in a prelude, split on the commas separating them, and a
    nested rule's composed with the rule it stands in.

    `str.split` cannot do it: the commas inside `:is(button, [role="button"])` separate
    that function's arguments rather than the rule's subjects. A nested selector reads
    `&` as its parent, or stands after it as a descendant when it names no `&`."""
    written = _split_top(" ".join(tinycss2.serialize(prelude).split()), ",")
    if not parent:
        return written
    outer = (
        parent[0]
        if len(parent) == 1 and len(_split_top(parent[0], " >+~")) == 1
        else f":is({', '.join(parent)})"
    )
    return [
        one.replace("&", outer) if "&" in one else f"{outer} {one}" for one in written
    ]


# The at-rules whose contents are style rules that match elements. An animation's
# stops and a registered property's descriptors are neither, and reading them would
# have `0%` in one sheet tie with `0%` in another — two animations sharing nothing,
# reported as a selector both sheets dress.
_HOLDS_RULES = {"media", "supports", "container", "scope", "layer"}


def _style_rules(sheet, *, whole=False):
    """(conditions, enclosing, complex selector, declarations) for each style rule, of
    the file alone or, `whole`, of the sheet a page receives with its imports in place.

    `conditions` are the preludes of the @media, @supports, @container and @layer a rule
    stands under; `enclosing` is every at-rule keyword around it, @scope included, so a
    reading can ask for chrome.css's top level or for only what its `@scope` holds. A
    selector list is split, because a rule dressing four shapes states the same fact
    about each and another sheet's copy may name only one of them. Values are kept: a
    rule that answers another with a different value is an override, not a copy."""

    def body(block):
        return tinycss2.parse_blocks_contents(
            block, skip_comments=True, skip_whitespace=True
        )

    def declared(items):
        return [
            (item.lower_name, tinycss2.serialize(item.value).strip())
            for item in items
            if item.type == "declaration"
        ]

    # `parent` is the selector list a nested rule stands in; declarations written
    # straight inside a conditional group nested in a rule belong to that rule.
    def visit(rules, conditions, enclosing, parent=()):
        for rule in rules:
            if rule.type == "at-rule":
                if rule.lower_at_keyword not in _HOLDS_RULES or rule.content is None:
                    continue
                keyword = rule.lower_at_keyword
                query = " ".join(tinycss2.serialize(rule.prelude).split())
                inner = (
                    conditions
                    if keyword == "scope"
                    else (*conditions, f"@{keyword} {query}")
                )
                items = body(rule.content)
                if parent and (declarations := declared(items)):
                    for selector in parent:
                        yield inner, enclosing | {keyword}, selector, declarations
                yield from visit(items, inner, enclosing | {keyword}, parent)
                continue
            if rule.type != "qualified-rule":
                continue
            items = body(rule.content)
            selectors = _selector_list(rule.prelude, parent)
            declarations = declared(items)
            for selector in selectors:
                yield conditions, enclosing, selector, declarations
            yield from visit(items, conditions, enclosing, tuple(selectors))

    yield from visit(
        tinycss2.parse_stylesheet(
            layer_model.stylesheet(sheet, schema_model.PLUGIN_ROOT)
            if whole
            else sheet.read_text(),
            skip_comments=True,
            skip_whitespace=True,
        ),
        (),
        frozenset(),
    )


def _stated_faces(sheet, *, only_top_level):
    """{complex selector: {property}} for every rule stating a shared visual property."""
    stated = {}
    for _conditions, enclosing, selector, declarations in _style_rules(
        sheet, whole=True
    ):
        if only_top_level and enclosing & {"scope", "layer"}:
            continue
        properties = {name for name, _value in declarations if name in _FACE}
        if properties:
            stated.setdefault(selector, set()).update(properties)
    return stated


_PAGE_SIDE_SHEETS = [
    schema_model.ASSETS / "theme.css",
    schema_model.ASSETS / "shadow.css",
    *(
        path
        for name in schema_model.PACKAGE_STYLES
        for path in sorted(schema_model.BUNDLED_PACKAGES.glob(f"*/{name}"))
    ),
]


def _declared_rules(sheet, *, scoped):
    """{(conditions, complex selector): [declarations]}; `scoped` keeps only what stands
    inside chrome.css's `@scope`."""
    found = {}
    for conditions, enclosing, selector, declarations in _style_rules(
        sheet, whole=True
    ):
        if scoped and "scope" not in enclosing:
            continue
        found.setdefault((conditions, selector), []).append(declarations)
    return found


def test_the_chrome_restates_no_rule_a_page_side_sheet_already_makes():
    """A rule inside chrome.css's `@scope` reaches the chrome root; the same rule in
    theme.css or shadow.css reaches the page, the widget trees, and the chrome root too.
    Written in both, the shape has two statements to keep in step and the chrome's is the
    one anybody reading the page's sheet cannot see — which is how the whole reaction
    vocabulary came to be written twice, identically, in nineteen rules.

    Equality is the reading, because a scoped rule that says something different is the
    chrome answering the page on purpose: the margin projection's z-index above the
    page's is that, and is not a copy."""
    chrome = _declared_rules(
        schema_model.ASSETS / "runtime" / "chrome.css", scoped=True
    )
    assert chrome, "no scoped rules read from chrome.css — the reading is broken"
    restated = []
    for sheet in _PAGE_SIDE_SHEETS:
        for key, blocks in _declared_rules(sheet, scoped=False).items():
            for block in blocks:
                if block and block in chrome.get(key, []):
                    conditions, selector = key
                    where = f"{sheet.parent.name}/{sheet.name}"
                    restated.append(
                        f"`{' '.join((*conditions, selector))}` is stated identically "
                        f"in chrome.css and {where}"
                    )
    assert not restated, (
        "a rule written twice, once where the page cannot see it:\n"
        + "\n".join(sorted(set(restated)))
    )


def test_kernel_selectors_name_no_package_tag():
    """The kernel styles and finds a package widget by what its registry declares, a
    mark delivery paints such as `data-lf-margin-content`, never by its tag: a rule naming
    lf-toc serves lf-toc and no other contents map, and binds the kernel to one
    package's vocabulary. A kernel sheet's selectors and `@scope` preludes, and the
    selectors the runtime hands a DOM query, use no tag a bundled package declares as
    a type selector."""
    tags = {
        tag
        for registry in schema_model.BUNDLED_PACKAGES.glob("*/registry.json")
        for tag in json.loads(registry.read_text())
        if not tag.startswith("$")
    }

    def types(tokens):
        """The type selectors among `tokens`, in and out of `:is()`-like arguments."""
        previous = None
        for token in tokens:
            if token.type == "ident" and not (
                previous is not None
                and previous.type in ("literal", "delim")
                and previous.value in (".", ":", "::")
            ):
                yield token.value
            if token.type in ("function", "() block"):
                yield from types(
                    token.arguments if token.type == "function" else token.content
                )
            previous = token

    def leaks_in(selector):
        return tags & set(types(tinycss2.parse_component_value_list(selector)))

    def preludes(rules):
        for rule in rules:
            if rule.type == "qualified-rule" or (
                rule.type == "at-rule" and rule.lower_at_keyword == "scope"
            ):
                yield tinycss2.serialize(rule.prelude).strip()
            if getattr(rule, "content", None) is not None:
                yield from preludes(tinycss2.parse_blocks_contents(rule.content))

    leaks = []
    for sheet in sorted(schema_model.ASSETS.rglob("*.css")):
        if "vendor" in sheet.parts:
            continue
        where = sheet.relative_to(schema_model.ASSETS)
        rules = tinycss2.parse_stylesheet(sheet.read_text(), skip_comments=True)
        leaks += [f"{where}: {p}" for p in preludes(rules) if leaks_in(p)]
    modules = [
        module
        for module in sorted(schema_model.ASSETS.rglob("*.js"))
        if "vendor" not in module.parts
    ]
    queries = json.loads(js_facts("queries", modules))
    assert any(queries.values()), "no DOM query was read — the reading is broken"
    for module in modules:
        where = module.relative_to(schema_model.ASSETS)
        leaks += [
            f"{where}: {selector}"
            for selector in queries[str(module)]
            if leaks_in(selector)
        ]
    assert leaks == [], leaks


def test_layout_style_and_widgets_never_read_each_other():
    """A Layout places boxes, a style sets type and spacing, and a widget reads its own
    box and the theme's tokens (assets/AGENTS.md, "Space and scrolling"). So a Layout
    class is named only in layouts.css and a style class only in the kernel theme, and
    layouts.css sets no type: where one has to answer another, the owner sets a token
    saying what the box is, as `--lf-full-height` does, and the reader keys on that.

    A Layout class is one layouts.css styles; a style class is one the kernel theme
    gives its own type or spacing tokens (`--t-*`, `--sp-*`)."""
    layouts = schema_model.ASSETS / "layouts.css"
    theme = schema_model.ASSETS / "theme.css"
    owned = {
        layouts: {
            name
            for _conditions, _enclosing, selector, _declarations in _style_rules(
                layouts
            )
            for name in re.findall(r"\.(layout-[a-z-]+)", selector)
        },
        theme: {
            match[1]
            for _conditions, _enclosing, selector, declarations in _style_rules(theme)
            if (match := re.fullmatch(r"\.([a-z][a-z-]*)", selector))
            and any(name.startswith(("--t-", "--sp-")) for name, _ in declarations)
        },
    }
    assert {"layout-column", "layout-workspace"} <= owned[layouts], owned[layouts]
    assert owned[theme] == {"density-working"}, owned[theme]
    roots = (schema_model.ASSETS, schema_model.BUNDLED_PACKAGES)
    readers = []
    for source in sorted(path for root in roots for path in root.rglob("*.[cj]s*")):
        if "vendor" in source.parts:
            continue
        foreign = [names for home, names in owned.items() if home != source]
        named = re.compile(r"\b(" + "|".join(sorted(set().union(*foreign))) + r")\b")
        where = source.relative_to(schema_model.ASSETS.parent)
        if source.suffix == ".css":
            readers += [
                f"{where}: {selector}"
                for _conditions, _enclosing, selector, _declarations in _style_rules(
                    source
                )
                if named.search(selector)
            ]
        elif source.suffix == ".js":
            # A module reads a class through a string; a comment may name one.
            readers += [
                f"{where}: {literal[1]}"
                for literal in re.findall(
                    r"([\"'`])((?:(?!\1).)*)\1", source.read_text()
                )
                if named.search(literal[1])
            ]
    typed = [
        f"{selector} sets {name}"
        for _conditions, _enclosing, selector, declarations in _style_rules(layouts)
        for name, _value in declarations
        if name.startswith("font") or name in ("letter-spacing", "line-height")
    ]
    assert not readers, "a Layout or style class read outside its owner:\n" + "\n".join(
        readers
    )
    assert not typed, "layouts.css sets type:\n" + "\n".join(typed)


def test_controls_are_built_by_role_and_never_by_face():
    """Leaf's controls come from a closed set of roles, each with one face, so a widget
    cannot draw two controls of one kind two ways. The classes of a role's face are
    spelled only in prepaint.js's `ACTION_FACES`, which `offerAction` reads; any other
    bundled module that spells one, in a string or a comment, has chosen a face itself.
    module-authoring.md lists the roles for package authors, in the table's order.
    `primary` and the authored `button` face are ordinary words too, so they count
    where a string lists classes or a template's `class` attribute names them."""
    owner = schema_model.ASSETS / "runtime" / "prepaint.js"
    table = re.search(r"const ACTION_FACES = \{(.*?)\};", owner.read_text(), re.DOTALL)
    roles = dict(re.findall(r"(\w+): \"([^\"]+)\"", table[1]))
    assert {"symbol", "word", "commit"} <= roles.keys(), roles
    reference = (SKILL_ROOT / "references" / "module-authoring.md").read_text()
    documented = re.findall(r"^- `\"(\w+)\"`, ", reference, re.MULTILINE)
    assert documented == list(roles), "module-authoring.md lists other roles"
    faces = {name for classes in roles.values() for name in classes.split()}
    named = re.compile(
        r"(?<![\w-])("
        + "|".join(sorted(name for name in faces if name.startswith("lf-")))
        + r")(?![\w-])"
    )
    words = {name for name in faces if not name.startswith("lf-")} | {"button"}
    assert words == {"primary", "button"}, words
    spelled = []
    for root in (schema_model.ASSETS, schema_model.BUNDLED_PACKAGES):
        for source in sorted(root.rglob("*.js")):
            if "vendor" in source.parts or source == owner:
                continue
            text = source.read_text()
            where = source.relative_to(ROOT)
            spelled += [f"{where}: {match[1]}" for match in named.finditer(text)]
            code = re.sub(r"/\*.*?\*/|(?<![:\w\"'])//[^\n]*", "", text, flags=re.DOTALL)
            for literal in re.findall(r"([\"'`])((?:(?!\1).)*)\1", code):
                classes = literal[1].split()
                if (
                    len(classes) > 1
                    and all(re.fullmatch(r"[a-z][\w-]*", name) for name in classes)
                    and words & set(classes)
                ):
                    spelled.append(f"{where}: {literal[1]}")
            spelled += [
                f"{where}: class={value[1]}"
                for value in re.findall(r"class=([\"'])(.*?)\1", code)
                if words & set(value[1].split())
            ]
    assert not spelled, (
        "build these controls with offerAction or offeredAction by role:\n"
        + "\n".join(spelled)
    )


def test_no_rule_rounds_a_box_edged_on_one_side(tmp_path):
    """A box marked by a thick edge on one side is not also rounded (assets/AGENTS.md,
    "Visual grammar"): a stripe bent around a corner reads as decoration rather than a
    contour, and marks a state another face already shows. A state is one whole contour,
    or a stripe on a square box. Leaf's own sheets and pages are read, a page's from its
    `<style>` and the sheets shipped beside it, the corpus's merged copy aside, and a
    stripe is a side's border of 2px or more or an inset shadow offset
    along one axis only. The reading is per rule, so a radius another rule gives the
    same box passes it."""
    sides = re.compile(
        r"border-(?:left|right|top|bottom|inline-start|inline-end|block-start|"
        r"block-end)(?:-width)?"
    )
    inset = re.compile(r"(?:^|,)\s*inset\s+(-?[\d.]+)(?:px)?\s+(-?[\d.]+)(?:px)?\s+0")

    def thick(value):
        return any(float(px) >= 2 for px in re.findall(r"([\d.]+)px", value))

    def edged(declarations):
        return any(
            sides.fullmatch(name)
            and thick(value)
            or name == "box-shadow"
            and any(
                (abs(float(x)) >= 2) != (abs(float(y)) >= 2)
                for x, y in inset.findall(value)
            )
            for name, value in declarations
        )

    def rounded(declarations):
        return any(
            re.fullmatch(r"border(?:-[a-z-]+)?-radius", name)
            and not re.fullmatch(r"(0(px)?\s*)+", value)
            for name, value in declarations
        )

    sheets = [
        (sheet.relative_to(ROOT), sheet)
        for root in (schema_model.ASSETS, schema_model.BUNDLED_PACKAGES)
        for sheet in sorted(root.rglob("*.css"))
        if "vendor" not in sheet.parts
    ]
    for root in (ROOT / "examples", ROOT / "docs"):
        sheets += [
            (sheet.relative_to(ROOT), sheet)
            for sheet in sorted(root.rglob("*.css"))
            if not sheet.parent.name.startswith("corpus")
        ]
    for page in sorted(
        [*(ROOT / "examples").rglob("*.html"), *(ROOT / "docs").glob("*.html")]
    ):
        if page.name.startswith("corpus"):
            continue
        styles = re.findall(r"<style[^>]*>(.*?)</style>", page.read_text(), re.DOTALL)
        if styles:
            sheet = tmp_path / page.relative_to(ROOT).with_suffix(".css")
            sheet.parent.mkdir(parents=True, exist_ok=True)
            sheet.write_text("\n".join(styles))
            sheets.append((page.relative_to(ROOT), sheet))
    assert len(sheets) > 20, sheets
    found = [
        f"{where}: {selector}"
        for where, sheet in sheets
        for _conditions, _enclosing, selector, declarations in _style_rules(sheet)
        if edged(declarations) and rounded(declarations)
    ]
    assert not found, "a rounded box edged on one side:\n" + "\n".join(found)


def test_every_token_a_sheet_reads_is_set_somewhere():
    """A `var(--name)` with no fallback reads a property something sets: a sheet's
    declaration or `@property`, or a module or delivery writing it by name. One nothing
    sets makes its declaration invalid, so the property falls back to what it inherits or
    its initial value, and the page shows no sign of it: a hover background that never
    painted, an empty state with no padding, a size the scale has no step for."""
    # Anything that names a property as a declaration, an `@property` or a string sets
    # it, a vendored component's sheet included; what is read is Leaf's own sheets.
    written, prefixes, reads = set(), set(), []
    sources = (
        schema_model.ASSETS,
        schema_model.BUNDLED_PACKAGES,
        Path(schema_model.__file__).parent,
    )
    for source in sorted(path for root in sources for path in root.rglob("*")):
        if source.suffix not in (".css", ".js", ".py"):
            continue
        text = source.read_text()
        written |= set(re.findall(r"(--[\w-]+)\s*:", text))
        written |= set(re.findall(r"@property\s+(--[\w-]+)", text))
        written |= set(re.findall(r"[\"'`](--[\w-]+)[\"'`]", text))
        prefixes |= set(re.findall(r"`(--[\w-]+)\$\{", text))
        if source.suffix != ".css" or "vendor" in source.parts:
            continue
        for _conditions, _enclosing, selector, declarations in _style_rules(source):
            reads += [
                (name, f"{source.relative_to(schema_model.ASSETS.parent)}: {selector}")
                for _property, value in declarations
                for name in re.findall(r"var\(\s*(--[\w-]+)\s*\)", value)
            ]
    unset = sorted(
        f"{where} reads {name}"
        for name, where in set(reads)
        if name not in written and not name.startswith(tuple(prefixes))
    )
    assert not unset, "a token nothing sets:\n" + "\n".join(unset)


def test_no_face_is_stated_for_one_selector_in_both_layer_sheets():
    """chrome.css is adopted, so it cascades after theme.css and after every package
    theme concatenated onto it. One selector dressed for the same property in both
    sheets therefore has one copy that never applies — the adopted one wins whatever the
    other says — and nothing catches it, because no test and no browser gate can read a
    rule that never applied.

    The chip and the thread mark's note were written that way on purpose, restated in
    theme.css for the shadow roots the adopted sheet cannot reach, and the two copies
    had drifted: theme.css's chip cleared the platform's button face and chrome.css's
    did not, so in the light DOM that reset had never once run.

    Only chrome.css's top level is asked here. A rule inside its `@layer` loses to any
    unlayered choice whatever its specificity, and a rule inside its `@scope` wins
    inside the chrome root while the page-side copy still dresses the same shape
    everywhere else — one statement in two files rather than one that never applies,
    which the test above reads instead.

    One selector spelled the same on both sides is what this reads, which is the shape
    a copy takes. Two different selectors that tie on one element are the same defect
    and cannot be seen in a file; `adopted_sheet_findings` (test_render_gate.py) puts
    that question to a browser."""
    adopted = _stated_faces(
        schema_model.ASSETS / "runtime" / "chrome.css", only_top_level=True
    )
    assert adopted, "no top-level faces read from chrome.css — the reading is broken"
    twice = []
    for sheet in _PAGE_SIDE_SHEETS:
        for selector, properties in _stated_faces(sheet, only_top_level=False).items():
            both = properties & adopted.get(selector, set())
            if both:
                where = f"{sheet.parent.name}/{sheet.name}"
                twice.append(
                    f"`{selector}` states {sorted(both)} in chrome.css and {where}"
                )
    assert not twice, (
        "a face stated twice, where only the adopted copy applies:\n" + "\n".join(twice)
    )


# The page-side order `composed_sheets` reads a composed example's layer in: each
# root's own sheets, root by root in layer order.
_LAYER_SHEET_ORDER = [
    sheet
    for root in SHIPPED_PACKAGES
    for sheet in (
        root / name
        for name in (
            ("shadow.css", "theme.css")
            if root == schema_model.ASSETS
            else schema_model.PACKAGE_STYLES
        )
    )
    if sheet.is_file()
]


def test_the_injected_control_face_is_a_default_only_the_document_reads():
    """`.lf-ui-face` is a native default. `offer()` writes it on native controls, and a
    component that states the same property overrides it, so the face stands first in
    the layer's page-side order and loses on position. It keeps a class's specificity,
    so the page's own element rules lose to it. And a declared tree copies shadow.css,
    where lf-diff marks its line numbers `lf-ui`, so the selector reaches only elements
    under the document's root.

    Each of the three has broken once: stated in theme.css after shadow.css, Send drew
    near-black instead of the accent; at the head of shadow.css as a plain `.lf-ui`, the
    diff's line numbers took the control's size and ink; as `:where(.lf-ui)`, a page's
    `button, a` rule took the family of half corpus.html's widget controls. The browser
    cases that read those faces are `test_a_single_space_is_message_content_in_every_
    composer`, `test_a_diff_is_colored_by_each_files_own_path` and
    `test_a_pages_own_element_rules_leave_the_layers_controls_alone`; this one names the
    single rule all three depend on."""
    faces = [
        (sheet, selector)
        for sheet in _LAYER_SHEET_ORDER
        for _conditions, _enclosing, selector, declarations in _style_rules(
            sheet, whole=True
        )
        if any(name in _FACE for name, _value in declarations)
    ]
    assert faces, "no face was read from the layer's sheets — the reading is broken"
    # Public controls and injected controls share this one default; its root boundary
    # and class weight still protect shadow content and win over page element rules.
    control_face = ":where(:root) :is(.lf-ui-face, .button, .field)"
    assert faces[0] == (schema_model.ASSETS / "shadow.css", control_face), faces[0]
    defaults = [
        face
        for face in faces
        if face[1]
        in {
            ".lf-ui-face",
            ":where(.lf-ui-face)",
            ":where(:root) .lf-ui-face",
            control_face,
        }
    ]
    assert defaults == [faces[0]], defaults


def test_layer_style_sources_consume_the_runtime_layout_names():
    """CSS and runtime agree on shared property and attribute names."""
    page_paint = schema_model.ASSETS / "runtime" / "page-paint.js"
    read = json.loads(js_facts("literals", [page_paint]))
    assets = schema_model.ASSETS
    sheet = (assets / "theme.css").read_text() + (
        assets / "runtime/chrome.css"
    ).read_text()

    spelling = (
        "["
        + read[str(page_paint)]["constants"]["PAGE_PAINT_ATTRIBUTE.obligation"]
        + "]"
    )
    assert spelling in sheet, f"the layer sheets no longer spell {spelling}"


def test_prepaint_marks_the_state_the_stylesheet_reads():
    """Classic startup scripts publish the live and interactive states before modules
    run; the stylesheet must consume those same markers."""
    assets = schema_model.ASSETS
    bootstrap, prepaint = (
        assets / "runtime" / f"{name}.js" for name in ("bootstrap", "prepaint")
    )
    read = json.loads(js_facts("literals", [bootstrap, prepaint]))
    theme = (assets / "theme.css").read_text()

    assert ["data-lf-live", True] in read[str(bootstrap)]["calls"]["toggleAttribute"]
    assert "html[data-lf-live]" in theme
    assert ["data-lf-interactive", True] in read[str(prepaint)]["calls"][
        "toggleAttribute"
    ]
    assert "html[data-lf-interactive]" in theme
    assert 'script[type="module"][src="/leaf.js"]' not in theme


def test_identical_init_preserves_the_installed_layer(tmp_path):
    """No contract transition means no writes or invalidation of an open tab."""
    runner = CliRunner()
    page = tmp_path / "page"
    first_init = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert first_init.exit_code == 0, first_init.output

    def served_layer():
        state = runner.invoke(cli_model.cli, ["page", "state", str(page)])
        assert state.exit_code == 0, state.output
        return json.loads(state.output)["layer"]

    first = served_layer()

    files = {
        path.relative_to(page): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in page.rglob("*")
        if path.is_file()
    }
    planned = runner.invoke(cli_model.cli, ["page", "init", "--dry-run", str(page)])
    assert planned.exit_code == 0, planned.output
    assert json.loads(planned.output) == {"page": str(page), "changed": False}
    second_init = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert second_init.exit_code == 0, second_init.output
    assert {
        path.relative_to(page): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in page.rglob("*")
        if path.is_file()
    } == files
    assert served_layer() == first


def test_site_page_accepts_events_across_build_and_container_python_versions(
    claimed, server, monkeypatch
):
    """The build host and serving container can run different Python releases."""
    page = claimed
    publish(page)
    monkeypatch.setattr(sys, "version", "container Python version")
    planned = CliRunner().invoke(
        cli_model.cli, ["page", "init", "--dry-run", str(page)]
    )
    assert planned.exit_code == 0, planned.output
    assert not json.loads(planned.output)["changed"]
    code, response = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "comment", "revision": 1, "text": "Hello"}).encode(),
    )
    assert code == 200, response


PLAIN_PAGE = (
    '<!doctype html><html lang="en"><head><title>t</title></head>'
    "<body><main><h1>Title</h1><p>words</p></main></body></html>"
)


def test_the_browser_gate_opens_away_from_the_project_a_page_selected(
    tmp_path, monkeypatch
):
    """The gate opens a page away from the project its packages were selected in.

    `$layer.packages` records a project-relative selection, resolved against the
    directory `page init` ran in, so a reading composed from the page's packages would
    refuse this page everywhere else. The gate takes an explicit page path.
    """
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    package = tmp_path / ".leaf"
    package.mkdir()
    (package / "theme.css").write_text(
        ":root { --test-accent: red }\n", encoding="utf-8"
    )
    page = tmp_path / "page"
    initialized = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
    )
    assert initialized.exit_code == 0, initialized.output
    (page / "index.html").write_text(PLAIN_PAGE, encoding="utf-8")

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    with pytest.raises(Refused):
        layer_model.resolve_packages(("./.leaf",), Path.cwd())

    with preview_server(page, structure_model.SourceDocument(PLAIN_PAGE), 1) as url:
        assert url.startswith("http://127.0.0.1:")


def test_payload_provenance_belongs_to_the_plugin_repo_without_writing_its_index(
    tmp_path, monkeypatch
):
    """An enclosing repo is not the payload, and reading the payload leaves Git alone."""

    def git(repo, *args):
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            check=True,
            text=True,
        )

    outer = tmp_path / "outer"
    plugin = outer / "installed" / "leaf"
    plugin.mkdir(parents=True)
    git(outer, "init")
    (outer / "tracked").write_text("outer\n")
    git(outer, "add", "tracked")
    git(
        outer,
        "-c",
        "user.name=Leaf Test",
        "-c",
        "user.email=leaf@example.test",
        "commit",
        "-m",
        "outer",
    )
    monkeypatch.setattr(layer_model, "PLUGIN_ROOT", plugin)
    assert layer_model.payload_provenance() == {}

    git(plugin, "init")
    payload = plugin / "payload"
    payload.write_text("first\n")
    git(plugin, "add", "payload")
    git(
        plugin,
        "-c",
        "user.name=Leaf Test",
        "-c",
        "user.email=leaf@example.test",
        "commit",
        "-m",
        "plugin",
    )
    (plugin / ".codex-marketplace-install.json").write_text("{}\n")
    index = plugin / ".git" / "index"
    before = index.stat().st_mtime_ns

    committed = git(plugin, "show", "--no-patch", "--format=%cI", "HEAD").stdout.strip()
    clean = layer_model.payload_provenance(include_path=True)
    assert clean == {
        "path": str(plugin),
        "commit": git(plugin, "rev-parse", "--short=12", "HEAD").stdout.strip(),
        "committed": committed,
        "dirty": False,
    }

    payload.write_text("changed\n")

    provenance = layer_model.payload_provenance(include_path=True)

    assert provenance == {
        "path": str(plugin),
        "commit": git(plugin, "rev-parse", "--short=12", "HEAD").stdout.strip(),
        "committed": committed,
        "dirty": True,
    }
    assert index.stat().st_mtime_ns == before


def test_payload_provenance_reads_claude_codes_git_versioned_plugin_cache(
    tmp_path, monkeypatch
):
    """Claude's copied payload retains its source SHA in the documented cache path,
    and dates itself by when the copy was made, which its running module carries."""
    commit = "4cb17dc60870"
    plugin = tmp_path / ".claude" / "plugins" / "cache" / "leaf" / "leaf" / commit
    plugin.mkdir(parents=True)
    # A marketplace refresh may leave a newer sibling cached while an existing
    # session still runs this copy. Provenance follows this module's root, not the
    # newest directory available globally.
    (plugin.parent / "ffffffffffff").mkdir()
    monkeypatch.setattr(layer_model, "PLUGIN_ROOT", plugin)
    monkeypatch.setattr(
        layer_model.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("a cached payload should not invoke Git"),
    )

    copied = Path(layer_model.__file__).stat().st_mtime
    assert layer_model.payload_provenance(include_path=True) == {
        "path": str(plugin),
        "commit": commit,
        "dirty": False,
        "installed": datetime.fromtimestamp(copied)
        .astimezone()
        .isoformat(timespec="seconds"),
    }


def test_fresh_page_state_points_only_to_readable_authorities(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "page"
    initialized = CliRunner().invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output

    result = CliRunner().invoke(cli_model.cli, ["page", "state", str(page)])
    assert result.exit_code == 0, result.output
    state = json.loads(result.output)
    assert state["active"] is None
    assert state["source"]["file"] == "index.html"
    assert state["source"]["live"] is False
    assert "write index.html first" in state["source"]["error"]
    assert state["event_seq"] == 0
    assert state["data"] == {"dir": "data", "errors": []}
    assert (
        data_model.read_data(page, registry_storage.load_registry(page))["sources"]
        == {}
    )


def test_init_composes_nested_browser_modules(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = tmp_path / "package"
    module = package / "runtime" / "nested-package" / "fold" / "model.js"
    module.parent.mkdir(parents=True)
    module.write_text("export const model = 'package';\n")
    page = tmp_path / "page"
    runner = CliRunner()

    initialized = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "./package", str(page)]
    )

    assert initialized.exit_code == 0, initialized.output
    assert layer_files(page)["/runtime/nested-package/fold/model.js"] == (
        b"export const model = 'package';\n"
    )
    assert schema_model.SERVED_PATH.fullmatch("/runtime/nested-package/fold/model.js")
    assert not schema_model.SERVED_PATH.fullmatch("/vendor/../../stream.json")
    assert not schema_model.SERVED_PATH.fullmatch("/vendor/../leaf.js")


def test_the_layer_composer_is_the_browser_module_population():
    """The registry and composed layer, not independent filesystem globs, decide which
    browser modules a page receives. The JavaScript parser/linter owns import legality;
    this assertion owns the population it checks and includes dependency-only modules."""
    diagram = schema_model.BUNDLED_PACKAGES / "diagram"
    composition = layer_model.compose_layer(
        [schema_model.ASSETS, schema_model.DEFAULT_PACKAGE, diagram]
    )
    widgets = composition.directory_files["widgets"]
    upgraded = {
        f"{tag}.js"
        for tag, entry in composition.registry.items()
        if tag.startswith("lf-") and entry["x-upgrade"]
    }

    assert upgraded <= widgets.keys()
    assert "lf-diagram.js" in widgets
    assert {"lf-options-addition.js", "lf-options-settled.js"} <= widgets.keys()


def test_every_test_runs_against_a_throwaway_state_home(tmp_path_factory):
    """Fixture claims and installed packages stay outside the developer's state."""
    assert cleanup_model.state_home().is_relative_to(tmp_path_factory.getbasetemp())


@pytest.mark.parametrize("launcher_ends", ["wait", "exit"])
def test_a_spawned_process_ends_with_what_it_started(spawn, launcher_ends):
    """`spawn`'s teardown ends a child's descendants as well as the child, since a
    handle often names a launcher, as `under_codex`'s fake host does the shell
    that runs its command. That holds whether the launcher is still running or
    has already exited and left its child behind."""
    launcher = spawn(
        ["/bin/sh", "-c", f"sleep 600 & echo $!; {launcher_ends}"],
        stdout=subprocess.PIPE,
        text=True,
    )
    descendant = int(launcher.stdout.readline())
    if launcher_ends == "exit":
        launcher.wait(timeout=STATED_TIMEOUT)

    _retire(launcher)

    def running():
        try:
            os.kill(descendant, 0)
        except ProcessLookupError:
            return False
        return True

    wait_for(running, lambda alive: not alive, failure="the launcher's child survived")


@pytest.mark.parametrize(
    "first",
    [
        r".x { --token: \{; }",
        "@media print { .x { color: red;",
        r"@media print { .x { --token: \} \}",
        "/* a comment ending at EOF",
    ],
)
def test_composed_sheets_preserve_each_sources_eof_boundary(tmp_path, first):
    """Browser EOF recovery belongs to each source, before Leaf wraps and joins it.

    Escaped braces are tokens, not block delimiters. An unfinished block or comment
    in one source must not capture the wrapper or any later source's rules.
    """
    roots = [tmp_path / name for name in ("first", "second")]
    for root, css in zip(roots, (first, ".y { color: red; }"), strict=True):
        root.mkdir()
        (root / "theme.css").write_text(css)

    composed = layer_model.composed_sheets(roots)["theme.css"].decode()
    rules = tinycss2.parse_stylesheet(
        composed, skip_whitespace=True, skip_comments=True
    )
    assert [rule.lower_at_keyword for rule in rules] == ["layer", "layer", "layer"]
    assert tinycss2.serialize(rules[-1].prelude).strip() == "lf-theme"
    later = tinycss2.parse_rule_list(
        rules[-1].content, skip_whitespace=True, skip_comments=True
    )
    assert len(later) == 1
    assert tinycss2.serialize(later[0].prelude).strip() == ".y"


def test_a_sheet_composes_the_files_it_imports_in_place(tmp_path):
    """A package splits its sheet into files with `@import` and needs no build: each
    file's rules stand where its import stood, in the layer it asks for, and each file
    keeps its own EOF recovery. So an edit to any of them reaches the next composition,
    and the page asks for no import."""
    (tmp_path / "parts").mkdir()
    (tmp_path / "theme.css").write_text(
        '@import "./parts/open.css";\n'
        "@import url(parts/layered.css) layer(extra);\n"
        ".after { color: blue; }\n"
    )
    (tmp_path / "parts/open.css").write_text(".open { color: red;")
    (tmp_path / "parts/layered.css").write_text(".layered { color: green; }")

    composed = layer_model.composed_sheets([tmp_path])["theme.css"].decode()
    assert "@import" not in composed
    # A reader that follows the layer's inputs, such as a live preview, follows them.
    assert {
        (tmp_path / "parts" / name).resolve() for name in ("open.css", "layered.css")
    } <= set(layer_model.input_paths([tmp_path]))

    def shape(rule):
        """A style rule's selector, or an at-rule's prelude and the rules it holds."""
        prelude = tinycss2.serialize(rule.prelude).strip()
        if rule.type == "qualified-rule":
            return prelude
        held = tinycss2.parse_blocks_contents(rule.content, skip_whitespace=True)
        return [prelude, [shape(item) for item in held]]

    *_, layer = tinycss2.parse_stylesheet(composed, skip_whitespace=True)
    assert shape(layer) == ["lf-base", [".open", ["extra", [".layered"]], ".after"]]


@pytest.mark.parametrize(
    "imported",
    [
        '"../outside.css"',
        '"/theme.css"',
        '"https://example.com/a.css"',
        '"a.css" print',
    ],
)
def test_a_sheet_imports_only_its_own_files_whole(tmp_path, imported):
    """An import names a file inside its package, so the package composes the same
    wherever it is installed, and comes whole or in a layer; a condition belongs
    inside the imported file."""
    package = tmp_path / "package"
    package.mkdir()
    (tmp_path / "outside.css").write_text(".outside {}")
    (package / "a.css").write_text(".a {}")
    (package / "theme.css").write_text(f"@import {imported};\n")
    with pytest.raises(Refused, match="import"):
        layer_model.composed_sheets([package])


def test_sheets_that_import_each_other_are_refused_by_name(tmp_path):
    """A cycle of imports is refused naming its files, and a reader that follows the
    layer's inputs, as vendoring and a live preview do, still finishes and lists them."""
    (tmp_path / "theme.css").write_text('@import "a.css";\n')
    (tmp_path / "a.css").write_text('@import "b.css";\n.a {}\n')
    (tmp_path / "b.css").write_text('@import "a.css";\n.b {}\n')
    with pytest.raises(Refused, match=r"a\.css -> .*b\.css -> .*a\.css"):
        layer_model.composed_sheets([tmp_path])
    assert {(tmp_path / name).resolve() for name in ("a.css", "b.css")} <= set(
        layer_model.input_paths([tmp_path])
    )


@pytest.mark.parametrize(
    "css",
    [
        r'.x { content: "\d800"; }',
        r".\dfff {}",
        r".x { background: url(\d800.svg); }",
    ],
)
def test_composed_sheets_replace_surrogate_escapes_as_the_browser_does(tmp_path, css):
    """CSS replaces surrogate escapes with U+FFFD in strings, identifiers and URLs.

    tinycss2 instead emits lone surrogates; serialization must preserve browser
    meaning rather than crash UTF-8 encoding while composing the layer.
    """
    (tmp_path / "theme.css").write_text(':root { --kept: "é🍂"; }\n' + css)
    sheet = layer_model.composed_sheets([tmp_path])["theme.css"].decode()
    assert "\ufffd" in sheet
    assert "é🍂" in sheet


def test_package_contributions_keep_their_roles_when_a_widget_is_added(tmp_path):
    """A package's page contribution survives acquiring a widget, and package
    installation captures every source sheet the compositor reads."""
    package = tmp_path / "contributions"
    package.mkdir()
    (package / "registry.json").write_text("{}")
    (package / "theme.css").write_text("/* theme.css */ p { color: purple; }")
    before = layer_model.composed_sheets([schema_model.ASSETS, package])

    (package / "registry.json").write_text(
        json.dumps({"lf-contribution": element_declaration("lf-contribution")})
    )
    assert layer_model.composed_sheets([schema_model.ASSETS, package]) == before
    for name in ("elements.css", "widgets.css", "widget-shadow.css"):
        (package / name).write_text("lf-contribution { color: green; }")
    staged = tmp_path / "installed"
    staged.mkdir()
    packages_model.copy_package_contract(package, staged)
    assert {
        name: (staged / name).read_bytes() for name in schema_model.PACKAGE_STYLES
    } == {name: (package / name).read_bytes() for name in schema_model.PACKAGE_STYLES}
    assert {package / name for name in schema_model.PACKAGE_STYLES} <= set(
        layer_model.input_paths([package])
    )
    assert layer_model.composed_sheets([schema_model.ASSETS, staged]) == (
        layer_model.composed_sheets([schema_model.ASSETS, package])
    )


def test_init_merges_registry_layers_by_complete_entry(tmp_path, monkeypatch):
    """A custom widget adds one element declaration; it need not fork the shipped vocabulary.

    Precedence still belongs to the later layer, but at the declaration boundary: the
    project declaration replaces the user's whole schema rather than inheriting stale
    fields from it.
    """
    user = tmp_path / "config" / "leaf"
    project = tmp_path / "project"
    project_layer = project / ".leaf"
    user.mkdir(parents=True)
    project_layer.mkdir(parents=True)
    user_entry = {
        "description": "user shape",
        "type": "object",
        "properties": {"user-only": {"type": "string"}},
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": False,
    }
    project_entry = {
        "description": "project shape",
        "type": "object",
        "properties": {"project-only": {"type": "string"}},
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": False,
    }
    project_only = {
        "description": "project-only shape",
        "type": "object",
        "properties": {},
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": False,
    }
    (user / "registry.json").write_text(json.dumps({"lf-local": user_entry}))
    (project_layer / "registry.json").write_text(
        json.dumps({"lf-local": project_entry, "lf-project-only": project_only})
    )
    monkeypatch.chdir(project)

    page = tmp_path / "page"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            "../config/leaf",
            "--package",
            "./.leaf",
            str(page),
        ],
    )

    assert result.exit_code == 0, result.output
    registry = registry_storage.load_registry(page)
    assert registry["lf-local"] == project_entry
    assert registry["lf-project-only"] == project_only
    assert "lf-options" in registry and "$events" in registry


def test_init_merges_idioms_by_complete_entry_and_facts_by_member(
    tmp_path, monkeypatch
):
    """Selecting a layer preserves unrelated vocabulary and facts, while a
    restated idiom replaces its complete entry just as an element does."""
    project = tmp_path / "proj"
    layer = project / ".leaf"
    layer.mkdir(parents=True)
    hazard = {
        "description": "A tinted aside for operational hazards.",
        "x-example": '<aside class="hazard">Deploys freeze Friday.</aside>',
    }
    sidenote = {
        "description": "project sidenote",
        "x-example": '<aside class="sidenote">…</aside>',
    }
    (layer / "registry.json").write_text(
        json.dumps(
            {
                ".hazard": hazard,
                "aside.sidenote": sidenote,
                # Adding one extension preserves the other keys of this fact map.
                "$languages": {"paths": {"svelte": "javascript"}},
            }
        )
    )
    monkeypatch.chdir(project)
    page = tmp_path / "page"
    result = CliRunner().invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
    )
    assert result.exit_code == 0, result.output
    registry = registry_storage.load_registry(page)
    shipped = json.loads((schema_model.ASSETS / "registry.json").read_text())
    assert registry[".hazard"] == hazard
    assert registry["aside.sidenote"] == sidenote
    assert set(shipped) <= set(registry)
    assert registry["$languages"]["paths"]["svelte"] == "javascript"
    assert set(shipped["$languages"]["paths"]) <= set(registry["$languages"]["paths"])
    assert registry["$languages"]["names"] == shipped["$languages"]["names"]


def test_path_case_policy_matches_the_filesystem(tmp_path):
    probe = tmp_path / "CaseProbe"
    probe.mkdir()
    alias_resolves = (tmp_path / "cASEpROBE").exists()

    assert interact_locations._filesystem_case_sensitive(tmp_path) is not alias_resolves


def test_path_overlap_respects_case_sensitive_future_names(tmp_path, monkeypatch):
    upper = tmp_path / "FutureScope"
    lower = tmp_path / "fUTUREsCOPE"
    monkeypatch.setattr(
        interact_locations, "_filesystem_case_sensitive", lambda path: True
    )
    assert not interact_locations.locations_overlap(
        interact_locations.path_location(upper),
        interact_locations.path_location(lower),
    )

    monkeypatch.setattr(
        interact_locations, "_filesystem_case_sensitive", lambda path: False
    )
    assert interact_locations.paths_same(upper, lower)


def test_an_initialized_page_owns_what_the_storage_contract_names(
    tmp_path, monkeypatch
):
    """page-storage.md's "Files" is the page directory's whole inventory: the page
    owns each file it names and everything beneath each directory, and nothing else
    is Leaf's there. The same name one level down belongs to no page."""
    assert sorted(schema_model.PAGE_OWNED_FILES) == STORAGE_FILES
    assert sorted(schema_model.PAGE_OWNED_DIRS) == STORAGE_DIRECTORIES

    monkeypatch.chdir(tmp_path)
    page = tmp_path / "page"
    initialized = CliRunner().invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    owner = packages_model.initialized_page_owning
    for name in STORAGE_FILES:
        assert owner(page / name) == page, name
        assert owner(page / ".leaf" / name) is None, name
    for directory in STORAGE_DIRECTORIES:
        assert owner(page / directory / "future") == page, directory


def test_replace_files_rejects_case_aliased_future_targets(tmp_path, monkeypatch):
    monkeypatch.setattr(
        interact_locations, "_filesystem_case_sensitive", lambda path: False
    )
    first = tmp_path / "Result.css"
    second = tmp_path / "rESULT.CSS"

    with pytest.raises(Refused, match="resolve to the same target"):
        interact_files.replace_files(
            [(first, b"first", False), (second, b"second", False)]
        )

    assert not first.exists() and not second.exists()


def test_init_refuses_case_aliased_layer_scopes(tmp_path, monkeypatch):
    project = tmp_path / "Project"
    project.mkdir()
    alias = case_alias(project)
    monkeypatch.chdir(project)
    user_layer = alias / ".LEAF" / "leaf"
    user_layer.mkdir(parents=True)
    theme = user_layer / "theme.css"
    theme.write_text(":root { --accent: teal; }\n")
    before = theme.read_bytes()
    page = tmp_path / "page"

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            "./.leaf",
            "--package",
            "./.LEAF/leaf",
            str(page),
        ],
    )

    assert result.exit_code != 0
    assert "package scopes must be separate" in result.output
    assert theme.read_bytes() == before
    assert not page.exists()


def test_init_reads_the_complete_layer_before_revendoring(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }

    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    (layer / "registry.json").write_text(
        json.dumps({"lf-bad-theme": element_declaration("lf-bad-theme")})
    )
    (layer / "theme.css").write_bytes(b"\xff")

    result = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
    )

    assert result.exit_code != 0
    assert "theme.css must be UTF-8" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_a_rejected_init_leaves_a_precreated_directory_empty(tmp_path, monkeypatch):
    """A directory the caller prepared is not page state until init succeeds."""
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "prepared page"
    page.mkdir()
    layer = tmp_path / ".leaf"
    layer.mkdir()
    (layer / "theme.css").write_text(".bad { color red; }\n")

    result = CliRunner().invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
    )

    assert result.exit_code != 0
    assert "theme.css syntax error" in result.output
    assert list(page.iterdir()) == []


def test_page_commands_do_not_mint_the_successful_init_marker(tmp_path):
    """An existing directory becomes a page only through a completed page init."""
    page = tmp_path / "prepared page"
    page.mkdir()

    result = CliRunner().invoke(cli_model.cli, ["server", "stop", str(page)])

    assert result.exit_code != 0
    assert f"leaf page init '{page}'" in json.loads(result.stderr)["error"]
    assert list(page.iterdir()) == []


def test_concurrent_page_init_serializes_creation(tmp_path, monkeypatch):
    """One page lock covers creation before the page log exists: a second init
    that arrives while the first is creating the page waits on that lock, and
    creates only once the first has finished.

    The first creation is held inside the lock until the second is found waiting
    on it. Without the lock the second would begin creating beside the first, which
    the same wait observes instead."""
    page = tmp_path / "page"
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()
    creations = []
    errors = []
    original_init = vendoring_model._init_page
    # The page's lock is a flock on the directory, which the first init takes
    # uncontended; the second is the one taker that can find it held.
    second_waiting = lock_contention(monkeypatch, page, by="second-init")

    def paused_init(page_dir, selected, *, theme=None):
        creator = threading.current_thread().name
        creations.append(creator)
        if creator == "first-init":
            first_entered.set()
            assert release_first.wait(STATED_TIMEOUT), "the first init was never let go"
        else:
            second_entered.set()
        original_init(page_dir, selected, theme=theme)

    def initialize():
        try:
            vendoring_model.cmd_init(page)
        except BaseException as error:  # noqa: BLE001 - carried to the assertion
            errors.append(error)

    monkeypatch.setattr(vendoring_model, "_init_page", paused_init)
    first = threading.Thread(target=initialize, name="first-init")
    second = threading.Thread(target=initialize, name="second-init")
    first.start()
    try:
        wait_for(
            lambda: first_entered.is_set() or bool(errors),
            bool,
            failure="the first init never began creating the page",
        )
        assert errors == []
        second.start()
        wait_for(
            lambda: second_waiting.is_set() or second_entered.is_set() or bool(errors),
            bool,
            failure="the second init neither waited on the page lock nor began creating",
        )
        assert errors == []
        assert not second_entered.is_set(), (
            "the second init began creating while the first held the page"
        )
    finally:
        release_first.set()
        first.join(timeout=STATED_TIMEOUT)
        if second.ident is not None:
            second.join(timeout=STATED_TIMEOUT)

    assert not first.is_alive(), "the first init never finished"
    assert not second.is_alive(), "the second init never finished"
    assert errors == []
    assert creations == ["first-init", "second-init"]
    assert (page / cleanup_model.EVENTS_FILE).is_file()


def test_hooks_do_not_mint_the_successful_init_marker_for_a_deleted_page(page_dir):
    """An external claim does not turn a deleted page back into initialized state."""
    record_claim(page_dir, id="stale-session")
    shutil.rmtree(page_dir)
    page_dir.mkdir()

    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "Stop", "session_id": "stale-session"}
    )

    assert list(page_dir.iterdir()) == []


def test_a_failed_fresh_commit_does_not_mark_the_page_initialized(
    tmp_path, monkeypatch
):
    """The stable log marks a completed init, not one that failed while committing."""
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "interrupted-page"

    def fail_layer_commit(page_dir, record):
        raise OSError("layer commit failed")

    monkeypatch.setattr(vendoring_model, "_write_record", fail_layer_commit)

    with pytest.raises(OSError, match="layer commit failed"):
        vendoring_model.cmd_init(page)

    assert not (page / "events.jsonl").exists()


def test_init_refuses_malformed_layer_css_before_revendoring(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    theme = tmp_path / ".leaf" / "theme.css"
    theme.parent.mkdir(parents=True)
    theme.write_text(".bad { color red; }\n")

    result = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
    )

    assert result.exit_code != 0
    assert f"{theme} syntax error" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before


@pytest.mark.parametrize(
    ("source_relative", "destination_relative"),
    [("widgets", "media"), ("theme.css", "index.html")],
)
def test_init_refuses_a_layer_source_aliased_to_a_page_destination(
    tmp_path, monkeypatch, source_relative, destination_relative
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    destination = page / destination_relative
    if destination_relative == "index.html":
        destination.write_text(PAGE)
    else:
        destination.mkdir()
    if destination.is_dir():
        (destination / "keep-source.txt").write_text(
            "stale pruning must not delete a package"
        )

    source = tmp_path / ".leaf" / source_relative
    source.parent.mkdir(parents=True)
    source.symlink_to(destination, target_is_directory=destination.is_dir())
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }

    result = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
    )

    assert result.exit_code != 0
    assert "overlaps page destination" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before


@pytest.mark.parametrize("destination", ("revisions", "media"))
def test_init_refuses_a_package_nested_in_a_page_owned_directory(
    tmp_path, monkeypatch, destination
):
    page = tmp_path / "page"
    package_parent = page / destination
    package = package_parent / ".leaf"
    package.mkdir(parents=True)
    theme = package / "theme.css"
    theme.write_text(":root { --accent: teal; }\n")
    monkeypatch.chdir(package_parent)

    result = CliRunner().invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
    )

    assert result.exit_code != 0
    assert "overlaps page destination" in result.output
    assert theme.read_text() == ":root { --accent: teal; }\n"
    assert not (page / cleanup_model.EVENTS_FILE).exists()


def test_init_refuses_a_case_aliased_source_at_a_page_destination(
    tmp_path, monkeypatch
):
    project = tmp_path / "Project"
    project.mkdir()
    monkeypatch.chdir(project)
    runner = CliRunner()
    page = tmp_path / "MixedCasePage"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    (page / "index.html").write_text(PAGE)
    alias = case_alias(page)
    target = alias / "INDEX.HTML"
    assert target.samefile(page / "index.html")
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    layer_theme = project / ".leaf" / "theme.css"
    layer_theme.parent.mkdir(parents=True)
    layer_theme.symlink_to(target)

    result = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
    )

    assert result.exit_code != 0
    assert "overlaps page destination" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before


@pytest.mark.parametrize(
    ("example", "code"),
    [
        (
            '<lf-toned-note id="repeat"><p id="repeat">Two</p></lf-toned-note>',
            "duplicate-ids",
        ),
        (
            '<tr><td id="repeat">One</td><td id="repeat">Two</td></tr>',
            "duplicate-ids",
        ),
        ('<lf-toned-note id="lf-example">One</lf-toned-note>', "reserved-ids"),
        (
            '<lf-toned-note id="note"><p id="two words">One</p></lf-toned-note>',
            "spaced-ids",
        ),
    ],
    ids=["duplicate", "table-duplicate", "reserved", "spaced"],
)
def test_init_refuses_invalid_ids_in_a_registry_example(
    tmp_path, monkeypatch, example, code
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output
    add_test_widget(tmp_path / ".leaf", "lf-toned-note")
    registry_path = tmp_path / ".leaf" / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-toned-note"]["x-example"] = example
    registry_path.write_text(json.dumps(registry))

    [refused] = command_findings(
        "page", "init", "--package", "./.leaf", str(tmp_path / "page")
    )

    assert (refused.code, refused.at) == ("invalid-example", "<lf-toned-note>")
    assert refused.values["finding"]["code"] == code


def test_explicit_package_order_is_registry_file_and_theme_precedence(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    for name in ("first", "second"):
        package = tmp_path / name
        (package / "widgets").mkdir(parents=True)
        declaration = element_declaration("lf-shared")
        declaration["description"] = name
        (package / "registry.json").write_text(json.dumps({"lf-shared": declaration}))
        (package / "theme.css").write_text(f":root {{ --package-{name}: 1; }}\n")
        (package / "widgets" / "shared.js").write_text(f"// {name}\n")

    page = tmp_path / "page"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            "./first",
            "--package",
            "./second",
            str(page),
        ],
    )

    assert result.exit_code == 0, result.output
    registry = registry_storage.load_registry(page)
    assert registry["$layer"]["packages"] == ["./packages/first", "./packages/second"]
    assert registry["lf-shared"]["description"] == "second"
    assert layer_files(page)["/widgets/shared.js"] == b"// second\n"
    theme = layer_files(page)["/theme.css"].decode()
    assert theme.index("--package-first") < theme.index("--package-second")


def test_init_refuses_a_case_aliased_page_inside_a_package(tmp_path, monkeypatch):
    project = tmp_path / "Project"
    project.mkdir()
    alias = case_alias(project)
    monkeypatch.chdir(project)
    runner = CliRunner()
    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output
    layer = project / ".leaf"
    page = alias / ".LEAF" / "WIDGETS"
    assert page.samefile(layer / "widgets")
    before = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }

    result = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
    )

    assert result.exit_code != 0
    assert "inside package" in result.output
    after = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_init_refuses_non_utf8_package_instructions_before_revendoring(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    package = tmp_path / ".leaf" / "instructions"
    package.mkdir(parents=True)
    source = package / "author.md"
    source.write_text("# Project author\n")
    page = tmp_path / "page"
    initialized = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
    )
    assert initialized.exit_code == 0, initialized.output
    before = (page / schema_model.LAYER_FILE).read_bytes()

    source.write_bytes(b"\xff")
    # The next command is a fresh process, which reads the package again.

    result = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
    )

    assert result.exit_code != 0
    assert "instructions/author.md must be UTF-8" in result.output
    assert (page / schema_model.LAYER_FILE).read_bytes() == before


def test_init_refuses_a_noncanonical_instructions_audience(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    instructions = tmp_path / ".leaf" / "instructions"
    instructions.mkdir(parents=True)
    malformed = instructions / "Project Lead.md"
    malformed.write_text("Use the project package.\n")
    page = tmp_path / "page"

    result = CliRunner().invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
    )

    assert result.exit_code != 0
    assert f"{malformed} must be named <audience>.md" in result.output
    assert not page.exists()


def test_init_refuses_overlapping_package_scopes(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    user = config / "leaf"
    user.mkdir(parents=True)
    (user / "theme.css").write_text(":root { --accent: teal; }\n")
    project_layer = project / ".leaf"
    project_layer.symlink_to(user, target_is_directory=True)
    monkeypatch.chdir(project)
    before = {
        path.relative_to(user): path.read_bytes()
        for path in user.rglob("*")
        if path.is_file()
    }
    page = tmp_path / "page"

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            "../config/leaf",
            "--package",
            "./.leaf",
            str(page),
        ],
    )

    assert result.exit_code != 0
    assert "package scopes must be separate" in result.output
    after = {
        path.relative_to(user): path.read_bytes()
        for path in user.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not page.exists()


@pytest.mark.parametrize("user", [False, True], ids=["project", "user"])
def test_init_refuses_to_overwrite_a_package(tmp_path, monkeypatch, user):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    monkeypatch.chdir(project)
    runner = CliRunner()
    package = config / "leaf" if user else project / ".leaf"
    created = runner.invoke(cli_model.cli, ["package", "init", str(package)])
    assert created.exit_code == 0, created.output

    layer = package
    before = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }
    assert before

    result = runner.invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            "../config/leaf" if user else "./.leaf",
            str(layer),
        ],
    )

    assert result.exit_code != 0
    assert "inside package" in result.output
    after = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_init_refuses_to_write_inside_a_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output
    layer = tmp_path / ".leaf"
    before = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }

    result = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(layer / "widgets")]
    )

    assert result.exit_code != 0
    assert "inside package" in result.output
    after = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }
    assert after == before


@pytest.mark.parametrize(
    ("relative", "directory"),
    [
        ("theme.css", True),
        ("widgets.css", True),
        ("registry.json", True),
        ("instructions", False),
        ("widgets", False),
        ("vendor", False),
    ],
)
def test_init_refuses_wrong_kind_package_paths(
    tmp_path, monkeypatch, relative, directory
):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / ".leaf" / relative
    path.parent.mkdir(parents=True)
    if directory:
        path.mkdir()
    else:
        path.write_text("not a directory")

    result = CliRunner().invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(tmp_path / "page")]
    )

    assert result.exit_code != 0
    assert str(path) in result.output


def test_package_allows_a_symlink_managed_external_layer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    managed = tmp_path / "managed"
    widgets = managed / "widgets"
    widgets.mkdir(parents=True)
    theme = managed / "theme.css"
    theme.write_text(":root { --accent: teal; }\n")
    registry = managed / "registry.json"
    registry.write_text("{}\n")
    (layer / "theme.css").symlink_to(theme)
    (layer / "registry.json").symlink_to(registry)
    (layer / "widgets").symlink_to(widgets, target_is_directory=True)

    runner = CliRunner()
    result = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code == 0, result.output
    assert (layer / "theme.css").is_symlink()
    assert (layer / "registry.json").is_symlink()
    assert (layer / "widgets").is_symlink()
    assert theme.read_text() == ":root { --accent: teal; }\n"
    assert json.loads(registry.read_text()) == {}
    checked = runner.invoke(cli_model.cli, ["package", "check", ".leaf"])
    assert checked.exit_code == 0, checked.output


def test_package_check_and_page_init_refuse_an_upgraded_widget_without_its_module(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output
    add_test_widget(tmp_path / ".leaf", "lf-unfinished")

    registry_path = tmp_path / ".leaf" / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-unfinished"]["x-upgrade"] = True
    registry["lf-unfinished"]["x-verbatim"] = True
    registry_path.write_text(json.dumps(registry))

    for args in (
        ["package", "check", ".leaf"],
        ["page", "init", "--package", "./.leaf", str(tmp_path / "page")],
    ):
        result = runner.invoke(cli_model.cli, args)
        assert result.exit_code != 0
        assert "widgets/lf-unfinished.js" in result.output


def test_package_check_requires_a_non_empty_widget_description(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output
    add_test_widget(tmp_path / ".leaf", "lf-toned-note")
    registry_path = tmp_path / ".leaf" / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-toned-note"]["description"] = "   "
    registry_path.write_text(json.dumps(registry))

    result = runner.invoke(cli_model.cli, ["package", "check", ".leaf"])

    assert result.exit_code != 0
    # The refusal is the result's one finding.
    report = json.loads(result.stdout)
    assert (report["status"], report["browser"]) == (1, None)
    [refusal] = report["findings"]
    assert (refusal["code"], refusal["at"], refusal["severity"]) == (
        "no-description",
        "<lf-toned-note>",
        "error",
    )


def test_package_check_refuses_a_registry_example_that_violates_its_schema(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output
    add_test_widget(tmp_path / ".leaf", "lf-toned-note")

    registry_path = tmp_path / ".leaf" / "registry.json"
    registry = json.loads(registry_path.read_text())
    entry = registry["lf-toned-note"]
    entry["properties"]["tone"] = {"enum": ["quiet", "loud"]}
    entry["required"].append("tone")
    registry_path.write_text(json.dumps(registry))

    status, [refused] = package_findings(".leaf")
    assert status == 1

    assert (refused.code, refused.at) == ("invalid-example", "<lf-toned-note>")
    example = Finding.loads(refused.values["finding"])
    assert (example.code, example.values["keyword"]) == ("attribute-schema", "required")
    assert "'tone'" in example.values["reason"]


def test_package_check_refuses_malformed_css_without_writing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    theme = layer / "theme.css"
    theme.write_text(".bad { color red; }\n")

    before = theme.read_bytes()
    result = CliRunner().invoke(cli_model.cli, ["package", "check", ".leaf"])

    assert result.exit_code != 0
    assert f"{theme} syntax error" in result.output
    assert theme.read_bytes() == before
    assert not (layer / "registry.json").exists()
    assert not (layer / "widgets").exists()


def test_package_check_requires_an_existing_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli_model.cli, ["package", "check", "packages/missing"])

    assert result.exit_code != 0
    assert "is not a package directory" in result.output
    assert not (tmp_path / "packages").exists()


def test_package_command_accepts_the_root_of_a_standalone_package_repo(
    tmp_path, monkeypatch
):
    package = tmp_path / "callout-package"
    package.mkdir()
    monkeypatch.chdir(package)

    result = CliRunner().invoke(cli_model.cli, ["package", "init", "."])

    assert result.exit_code == 0, result.output
    assert (package / "registry.json").is_file()
    assert (package / "theme.css").is_file()
    assert (package / "instructions").is_dir()
    assert (package / "widgets").is_dir()
    assert (package / "vendor").is_dir()


def test_package_command_can_target_the_user_package(tmp_path, monkeypatch):
    config = tmp_path / "config"
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        cli_model.cli, ["package", "init", str(config / "leaf")]
    )

    assert result.exit_code == 0, result.output
    package = config / "leaf"
    assert json.loads((package / "registry.json").read_text()) == {}
    assert (package / "theme.css").is_file()
    assert not (tmp_path / ".leaf").exists()


def test_package_init_creates_independently_selectable_packages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    callout = Path("packages/callout")
    accent = Path("packages/accent")

    for path in (callout, accent):
        result = runner.invoke(cli_model.cli, ["package", "init", str(path)])
        assert result.exit_code == 0, result.output
    add_test_widget(tmp_path / callout, "lf-callout", upgrade=True)
    with (tmp_path / accent / "theme.css").open("a") as theme:
        theme.write("\n:root { --accent: teal; }\n")

    page = tmp_path / "page"
    initialized = runner.invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            str(callout),
            "--package",
            str(accent),
            str(page),
        ],
    )
    assert initialized.exit_code == 0, initialized.output
    registry = registry_storage.load_registry(page)
    assert registry["$layer"]["packages"] == [
        "./packages/callout",
        "./packages/accent",
    ]
    assert "lf-callout" in registry
    assert "/widgets/lf-callout.js" in layer_files(page)


def test_package_install_makes_a_source_selectable_by_name(tmp_path, monkeypatch):
    """An installed package is a bundled one kept somewhere else.

    The store holds the package contract and none of the rest of the author's
    working directory, and the page reads the store rather than the source, which
    is gone by the time it is vendored.
    """
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    source = tmp_path / "src" / "callout"
    created = runner.invoke(cli_model.cli, ["package", "init", str(source)])
    assert created.exit_code == 0, created.output
    add_test_widget(source, "lf-callout", upgrade=True)
    (source / "README.md").write_text("How to work on this package.\n")
    (source / "spec").mkdir()
    (source / "spec" / "case.txt").write_text("the author's own test\n")

    installed = runner.invoke(cli_model.cli, ["package", "install", str(source)])

    assert installed.exit_code == 0, installed.output
    stored = Path(json.loads(installed.output)["package"])
    assert layer_model.named_package("callout") == stored
    assert sorted(path.name for path in stored.iterdir()) == [
        "instructions",
        "registry.json",
        "runtime",
        "theme.css",
        "vendor",
        "widgets",
        "widgets.css",
    ]

    shutil.rmtree(source)
    page = tmp_path / "page"
    vendored = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "callout", str(page)]
    )

    assert vendored.exit_code == 0, vendored.output
    registry = registry_storage.load_registry(page)
    assert registry["$layer"]["packages"] == ["callout"]
    assert "lf-callout" in registry
    assert "/widgets/lf-callout.js" in layer_files(page)


def test_package_install_refuses_a_source_it_cannot_check_or_name(
    tmp_path, monkeypatch
):
    """The install door is `package check` plus a name a page can select.

    A package that fails composition, and one whose directory name is not a name
    `--package` accepts, are both refused before the store exists.
    """
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    broken = tmp_path / "src" / "broken"
    unnamable = tmp_path / "src" / "Callout Package"
    for source in (broken, unnamable):
        created = runner.invoke(cli_model.cli, ["package", "init", str(source)])
        assert created.exit_code == 0, created.output
    (broken / "theme.css").write_text(".bad { color red; }\n")

    failed = runner.invoke(cli_model.cli, ["package", "install", str(broken)])
    misnamed = runner.invoke(cli_model.cli, ["package", "install", str(unnamable)])

    assert failed.exit_code != 0
    assert f"{broken / 'theme.css'} syntax error" in failed.output
    assert misnamed.exit_code != 0
    assert "'Callout Package' cannot be selected by name" in misnamed.output
    assert not machine_model.package_store().exists()


def test_package_init_ignores_unselected_packages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "config"
    config.mkdir()
    (config / "leaf").write_text("not a directory")
    (tmp_path / ".leaf").write_text("not a directory")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    package = tmp_path / "callout"
    result = CliRunner().invoke(cli_model.cli, ["package", "init", str(package)])
    assert result.exit_code == 0, result.output
    assert (package / "registry.json").is_file()
    assert (config / "leaf").read_text() == "not a directory"
    assert (tmp_path / ".leaf").read_text() == "not a directory"


def test_package_init_never_overwrites_existing_contents(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    theme = layer / "theme.css"
    theme.write_text(":root { --accent: rebeccapurple; }\n")

    result = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert result.exit_code == 0, result.output
    assert theme.read_text() == ":root { --accent: rebeccapurple; }\n"
    (layer / "registry.json").write_text('{"$local": {"value": 1}}\n')
    (layer / "instructions" / "author.md").write_text("Keep me.\n")
    before = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }

    repeated = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert repeated.exit_code == 0, repeated.output
    assert {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    } == before


def test_package_init_widget_merges_an_existing_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    package = tmp_path / ".leaf"
    initialized = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert initialized.exit_code == 0, initialized.output
    existing = add_test_widget(package, "lf-existing")
    instructions = package / "instructions" / "author.md"
    instructions.write_text("Keep this package instructions.\n")
    helper = package / "runtime" / "existing-helper.js"
    helper.write_text("export const existing = true;\n")
    theme = (package / "theme.css").read_bytes()

    result = runner.invoke(
        cli_model.cli,
        ["package", "init", ".leaf", "--widget", "lf-added-note"],
    )

    assert result.exit_code == 0, result.output
    registry = json.loads((package / "registry.json").read_text())
    assert registry["lf-existing"] == existing
    assert "lf-added-note" in registry
    assert (package / "theme.css").read_bytes() == theme
    assert instructions.read_text() == "Keep this package instructions.\n"
    assert helper.read_text() == "export const existing = true;\n"


def test_package_install_checks_the_bytes_it_publishes(tmp_path, monkeypatch):
    """Source admission precedes copying; an editor changing it in between must
    not publish an invalid package under a name pages can select.
    """
    source = tmp_path / "package"
    packages_model.cmd_package_init(source)
    copy_contract = packages_model.copy_package_contract

    def changed_during_copy(package, staged):
        (package / "theme.css").write_text(".bad { color red; }\n")
        copy_contract(package, staged)

    monkeypatch.setattr(packages_model, "copy_package_contract", changed_during_copy)
    result = CliRunner().invoke(cli_model.cli, ["package", "install", str(source)])
    assert result.exit_code != 0
    assert "syntax error" in result.output
    assert layer_model.named_package(source.name) is None


def test_package_init_widget_stages_only_the_package_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    (unrelated / "missing").symlink_to(unrelated / "not-there")

    result = CliRunner().invoke(
        cli_model.cli,
        ["package", "init", ".", "--widget", "lf-risk-note"],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "widgets" / "lf-risk-note.js").is_file()
    assert (unrelated / "missing").is_symlink()


def test_package_init_widget_validates_its_tag_without_writing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = tmp_path / "package"

    result = CliRunner().invoke(
        cli_model.cli,
        ["package", "init", str(package), "--widget", "risk-note"],
    )

    assert result.exit_code != 0
    assert "invalid widget tag 'risk-note': an element name is `lf-`" in result.output
    assert not package.exists()


@pytest.mark.parametrize("collision", ["tag", "module", "lower-layer"])
def test_package_init_widget_refuses_existing_members_without_writing(
    tmp_path, monkeypatch, collision
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    package = tmp_path / ".leaf"
    initialized = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert initialized.exit_code == 0, initialized.output
    tag = "lf-existing-note"
    if collision == "tag":
        add_test_widget(package, tag)
    elif collision == "module":
        (package / "widgets" / f"{tag}.js").write_text("// keep this module\n")
    else:
        tag = "lf-options"
    before = {
        path.relative_to(package): path.read_bytes()
        for path in package.rglob("*")
        if path.is_file()
    }

    result = runner.invoke(
        cli_model.cli,
        ["package", "init", ".leaf", "--widget", tag],
    )

    assert result.exit_code != 0
    assert "already exists in the composed layer" in result.output
    assert {
        path.relative_to(package): path.read_bytes()
        for path in package.rglob("*")
        if path.is_file()
    } == before


def test_package_init_widget_cannot_overwrite_a_member_created_during_init(
    tmp_path, monkeypatch
):
    """Candidate validation and installation are separated by real work. A second
    writer winning the module name in that interval keeps its bytes; initialization
    fails without publishing the generated element declaration around them.
    """
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    package = tmp_path / ".leaf"
    initialized = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert initialized.exit_code == 0, initialized.output
    before_registry = (package / "registry.json").read_bytes()
    real_create = packages_model.create_package_files

    def concurrent_create(root, files):
        module = package / "widgets" / "lf-race-note.js"
        module.write_text("// concurrent writer keeps this\n")
        return real_create(root, files)

    monkeypatch.setattr(packages_model, "create_package_files", concurrent_create)
    result = runner.invoke(
        cli_model.cli,
        ["package", "init", ".leaf", "--widget", "lf-race-note"],
    )

    assert result.exit_code != 0
    assert "was created while package init was running" in result.output
    assert (package / "widgets" / "lf-race-note.js").read_text() == (
        "// concurrent writer keeps this\n"
    )
    assert (package / "registry.json").read_bytes() == before_registry


def test_package_init_widget_checks_its_candidate_before_writing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = tmp_path / "package"
    declaration = element_declaration("lf-risk-note", upgrade=True)
    declaration["x-example"] = "<lf-risk-note>Missing the required id.</lf-risk-note>"
    monkeypatch.setattr(
        packages_model, "starter_element_declaration", lambda tag: declaration
    )

    [refused] = command_findings(
        "package", "init", str(package), "--widget", "lf-risk-note"
    )

    assert (refused.code, refused.at) == ("invalid-example", "<lf-risk-note>")
    assert not package.exists()


def test_package_init_validates_every_target_before_writing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    layer = tmp_path / ".leaf"
    theme = layer / "theme.css"
    theme.mkdir(parents=True)
    sentinel = theme / "keep.txt"
    sentinel.write_text("keep")

    result = CliRunner().invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert "theme.css must be a file" in result.output
    assert sentinel.read_text() == "keep"
    assert not (layer / "registry.json").exists()
    assert not (layer / "widgets").exists()


@pytest.mark.parametrize(
    ("relative", "directory"),
    [("vendor", False), ("icon.svg", True)],
)
def test_package_init_validates_the_complete_package(
    tmp_path, monkeypatch, relative, directory
):
    monkeypatch.chdir(tmp_path)
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    malformed = layer / relative
    if directory:
        malformed.mkdir()
    else:
        malformed.write_text("not a directory")

    result = CliRunner().invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert str(malformed) in result.output
    assert not (layer / "theme.css").exists()
    assert not (layer / "registry.json").exists()
    assert not (layer / "widgets").exists()


def test_package_preserves_a_symlinked_registry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    shared_registry = tmp_path / "shared-registry.json"
    shared_registry.write_text("{}\n")
    registry = layer / "registry.json"
    registry.symlink_to(shared_registry)

    result = CliRunner().invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code == 0, result.output
    assert registry.is_symlink()
    assert json.loads(shared_registry.read_text()) == {}


def test_package_recognizes_a_page_without_runtime_status(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    # A page has no stream until a harness observes a turn on it.
    assert not (page / "stream.json").exists()
    before = (page / "events.jsonl").read_bytes()

    layer = project / ".leaf"
    layer.mkdir(parents=True)
    (layer / "theme.css").symlink_to(page / "events.jsonl")

    result = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert "owned by initialized page" in result.output
    assert (page / "events.jsonl").read_bytes() == before
    assert not (layer / "registry.json").exists()


@pytest.mark.parametrize("user", [False, True], ids=["project", "user"])
def test_package_refuses_an_initialized_page_as_a_layer(tmp_path, monkeypatch, user):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    monkeypatch.chdir(project)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }

    layer = config / "leaf" if user else project / ".leaf"
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.symlink_to(page, target_is_directory=True)
    result = runner.invoke(cli_model.cli, ["package", "init", str(layer)])

    assert result.exit_code != 0
    assert "owned by initialized page" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before


@pytest.mark.parametrize(
    ("source_name", "page_name"),
    [
        ("theme.css", "events.jsonl"),
        ("widgets", schema_model.MEDIA_DIR),
        ("vendor", "revisions"),
    ],
)
def test_package_refuses_sources_aliased_to_page_owned_state(
    tmp_path, monkeypatch, source_name, page_name
):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    target = page / page_name
    if source_name in schema_model.BROWSER_DIRS:
        target.mkdir(exist_ok=True)
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }

    layer = project / ".leaf"
    layer.mkdir(parents=True)
    (layer / source_name).symlink_to(target, target_is_directory=target.is_dir())

    result = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert "owned by initialized page" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not (layer / "registry.json").exists()


def test_page_init_refuses_a_duplicate_package_selection(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = tmp_path / "solo"
    package.mkdir()

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            "./solo",
            "--package",
            "./solo",
            str(tmp_path / "page"),
        ],
    )

    assert result.exit_code == 2
    assert "each --package selection may appear only once" in result.output


def test_page_init_refuses_an_empty_package_selection_before_writing(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "page"

    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "init", "--package", "", str(page)],
    )

    assert result.exit_code == 2
    assert "--package selections cannot be empty" in result.output
    assert not page.exists()


def test_page_init_does_not_treat_an_unknown_bare_name_as_a_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "solo").mkdir()
    page = tmp_path / "page"

    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "init", "--package", "solo", str(page)],
    )

    assert result.exit_code == 1
    assert "unknown package 'solo'" in result.output
    assert "run `leaf package install`" in result.output
    assert "use './solo'" in result.output
    assert not page.exists()


def test_selecting_the_bundled_default_package_is_redundant(tmp_path):
    page = tmp_path / "page"
    result = CliRunner().invoke(
        cli_model.cli, ["page", "init", "--package", "default", str(page)]
    )
    assert result.exit_code == 0, result.output
    assert "lf-options" in registry_storage.load_registry(page)


def test_page_init_refuses_to_publish_an_absolute_package_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "solo"
    source.mkdir()
    page = tmp_path / "page"

    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "init", "--package", str(source), str(page)],
    )

    assert result.exit_code == 1
    assert (
        "use a bundled name, explicit project-relative path, or ~ path" in result.output
    )
    assert "does not publish a machine path" in result.output
    assert not page.exists()


def test_page_init_selects_the_same_directory_contract_at_any_cardinality(
    tmp_path, monkeypatch
):
    """A package is not a multi-widget subtype.

    One root below carries exactly one widget plus its private helper and vendor
    data; the other carries only theme rules. Both enter the same ordered merger
    as a many-widget package, and a plain re-vendor resolves their recorded
    project-relative paths again.
    """
    monkeypatch.chdir(tmp_path)
    widget_package = tmp_path / "solo"
    (widget_package / "widgets").mkdir(parents=True)
    (widget_package / "vendor").mkdir()
    (widget_package / "registry.json").write_text(
        json.dumps({"lf-solo": element_declaration("lf-solo", upgrade=True)})
    )
    (widget_package / "widgets.css").write_text("lf-solo { --lf-block-frame: 1; }\n")
    (widget_package / "widgets" / "lf-solo.js").write_text(
        'import { ready } from "./ready.js";\n'
        'customElements.define("lf-solo", class extends HTMLElement {\n'
        "  connectedCallback() { ready(this); }\n"
        "});\n"
    )
    (widget_package / "widgets" / "ready.js").write_text(
        "export const ready = (el) => { el.dataset.ready = '1'; };\n"
    )
    (widget_package / "vendor" / "solo.json").write_text('{"accent":"plum"}\n')
    (widget_package / "instructions").mkdir()
    (widget_package / "instructions" / "author.md").write_text("Use one solo.\n")
    (widget_package / "instructions" / "worker.md").write_text("Report the result.\n")

    theme_package = tmp_path / "night"
    theme_package.mkdir()
    (theme_package / "theme.css").write_text(":root { --solo-night: 1; }\n")
    (theme_package / "instructions").mkdir()
    (theme_package / "instructions" / "author.md").write_text("Use after dusk.\n")
    (theme_package / "instructions" / "reviewer.md").write_text("Check the contrast.\n")

    page = tmp_path / "page"
    initialized = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            "./solo",
            "--package",
            "./night",
            str(page),
        ],
    )

    assert initialized.exit_code == 0, initialized.output
    registry = registry_storage.load_registry(page)
    assert registry["$layer"]["packages"] == ["./packages/solo", "./packages/night"]
    assert "lf-solo" in registry
    assert "/widgets/lf-solo.js" in layer_files(page)
    assert "/widgets/ready.js" in layer_files(page)
    assert "/vendor/solo.json" in layer_files(page)
    theme = layer_files(page)["/theme.css"].decode()
    # Each contribution keeps its role regardless of the package's widget count.
    assert theme.index("lf-solo { --lf-block-frame: 1; }") < theme.index(
        ":root { --solo-night: 1; }"
    )
    instructions = layer_instructions(page)["author.md"].decode()
    assert instructions == (
        "# Package `solo`\n\nUse one solo.\n\n# Package `night`\n\nUse after dusk.\n"
    )
    assert "Report the result." in layer_instructions(page)["worker.md"].decode()
    assert "Check the contrast." in layer_instructions(page)["reviewer.md"].decode()

    reading = CliRunner().invoke(cli_model.cli, ["page", "instructions", str(page)])
    assert reading.exit_code == 0, reading.output
    assert json.loads(reading.output) == {
        "author": instructions,
        "reviewer": "# Package `night`\n\nCheck the contrast.\n",
        "worker": "# Package `solo`\n\nReport the result.\n",
    }

    revendored = CliRunner().invoke(cli_model.cli, ["page", "init", str(page)])
    assert revendored.exit_code == 0, revendored.output
    assert registry_storage.load_registry(page)["$layer"]["packages"] == [
        "./packages/solo",
        "./packages/night",
    ]


def test_page_owned_pr_brief_composes_its_data_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = ROOT / "examples" / "pr-walkthrough.page"
    selection = "./" + os.path.relpath(package, tmp_path)
    page = tmp_path / "review"

    checked = CliRunner().invoke(cli_model.cli, ["package", "check", str(package)])
    initialized = CliRunner().invoke(
        cli_model.cli,
        ["page", "init", "--package", selection, str(page)],
    )

    assert checked.exit_code == 0, checked.output
    assert initialized.exit_code == 0, initialized.output
    registry = registry_storage.load_registry(page)
    widget = registry["lf-pr-brief"]
    assert registry["$layer"]["packages"] == ["./packages/pr-walkthrough.page"]
    assert widget["x-data"] == {
        "request": {
            "contract": "pull-request",
            "source": "source",
            "property": "value",
        }
    }
    assert "pull-request" in registry["$data"]["contracts"]
    assert "/widgets/lf-pr-brief.js" in layer_files(page)
    assert "lf-call-diff" not in registry
    assert "/widgets/lf-call-diff.js" not in layer_files(page)


@pytest.mark.parametrize(
    ("package", "markup"),
    [
        (
            str(ROOT / "examples" / "pr-walkthrough.page"),
            '<lf-pr-brief id="pr" source="pr-data"></lf-pr-brief>',
        ),
        (
            "diff",
            (
                '<lf-call-diff id="calls" source="calls-data" diff="patch"></lf-call-diff>'
                '<lf-diff id="patch"><pre>diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n'
                "@@ -1 +1 @@\n-old()\n+new()\n</pre></lf-diff>"
            ),
        ),
    ],
)
def test_review_evidence_packages_export_independently(
    tmp_path, monkeypatch, package, markup
):
    """Call navigation and page-owned PR metadata export with their selected declarations."""
    monkeypatch.chdir(tmp_path)
    selection = (
        "./" + os.path.relpath(package, tmp_path)
        if Path(package).is_absolute()
        else package
    )
    page = tmp_path / "review"
    runner = CliRunner()
    initialized = runner.invoke(
        cli_model.cli, ["page", "init", "--package", selection, str(page)]
    )
    assert initialized.exit_code == 0, initialized.output
    (page / "index.html").write_text(
        "<!doctype html><html><head><title>Review evidence</title></head><body>"
        f'<main><h1 id="title">Review evidence</h1>{markup}</main></body></html>'
    )
    stamped = runner.invoke(
        cli_model.cli, ["page", "stamp", str(page), "--text", "Review evidence"]
    )
    assert stamped.exit_code == 0, stamped.output
    exported = runner.invoke(
        cli_model.cli,
        ["page", "export", str(page), "-o", str(tmp_path / "export.html")],
    )
    assert exported.exit_code == 0, exported.output
    if package == "diff":
        source = page / "index.html"
        source.write_text(source.read_text().replace('diff="patch"', 'diff="title"'))
        checked = runner.invoke(cli_model.cli, ["page", "check", str(page)])
        assert checked.exit_code != 0
        assert 'diff="title" must name a $diff.widgets widget' in words(checked.output)


def test_visual_review_package_composes_its_run_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = schema_model.BUNDLED_PACKAGES / "visual-review"
    page = tmp_path / "visual-review"

    checked = CliRunner().invoke(cli_model.cli, ["package", "check", str(package)])
    initialized = CliRunner().invoke(
        cli_model.cli,
        ["page", "init", "--package", "visual-review", str(page)],
    )

    assert checked.exit_code == 0, checked.output
    assert initialized.exit_code == 0, initialized.output
    registry = registry_storage.load_registry(page)
    widget = registry["lf-visual-review"]
    assert registry["$layer"]["packages"] == ["visual-review"]
    assert widget["x-data"] == {
        "run": {
            "contract": "visual-run",
            "source": "source",
            "property": "value",
        }
    }
    assert widget["x-state"]["review"]["unit"] == "case"
    assert widget["x-thread-surface"] is True
    assert "visual-run" in registry["$data"]["contracts"]
    assert "/widgets/lf-visual-review.js" in layer_files(page)
    assert "author.md" in layer_instructions(page)


@pytest.mark.parametrize(
    ("change", "refusal"),
    [
        (
            lambda run: {**run, "cases": [*run["cases"], run["cases"][0]]},
            "record keys must be unique",
        ),
        (
            lambda run: {**run, "base": {**run["base"], "url": "http://a.test:99999/"}},
            "'http://a.test:99999/' is not a 'uri'",
        ),
    ],
    ids=["repeated-case-id", "url-the-browser-cannot-parse"],
)
def test_data_set_refuses_a_visual_run_the_widget_cannot_show(
    tmp_path, monkeypatch, change, refusal
):
    """A case id addresses the case's review decisions and threads, and the widget
    opens each target URL with the browser's URL parser, so `data set` refuses a run
    that repeats an id or names a URL that parser refuses, rather than storing a run
    the widget cannot show."""
    monkeypatch.chdir(tmp_path)
    example = Path(__file__).parents[2] / "examples" / "developer"
    page = tmp_path / "visual-review"
    runner = CliRunner()
    initialized = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "visual-review", str(page)]
    )
    assert initialized.exit_code == 0, initialized.output
    shutil.copy(example / "visual-review-gallery.html", page / "index.html")
    run = json.loads((example / "visual-review-gallery.data.json").read_text())[
        "gallery-visual-run"
    ]

    def data_set(value):
        return runner.invoke(
            cli_model.cli,
            ["data", "set", str(page), "gallery-visual-run"],
            input=json.dumps(value),
        )

    accepted = data_set(run)
    refused = data_set(change(run))

    assert accepted.exit_code == 0, accepted.output
    assert refused.exit_code == 1
    assert refusal in refused.output


def test_a_bundled_name_wins_over_a_same_named_project_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    local = tmp_path / "diagram"
    local.mkdir()
    (local / "registry.json").write_text(
        json.dumps({"lf-local": element_declaration("lf-local")})
    )

    bundled = tmp_path / "bundled"
    local_page = tmp_path / "local"
    bundled_result = CliRunner().invoke(
        cli_model.cli,
        ["page", "init", "--package", "diagram", str(bundled)],
    )
    local_result = CliRunner().invoke(
        cli_model.cli,
        ["page", "init", "--package", "./diagram", str(local_page)],
    )

    assert bundled_result.exit_code == 0, bundled_result.output
    assert local_result.exit_code == 0, local_result.output
    bundled_registry = registry_storage.load_registry(bundled)
    local_registry = registry_storage.load_registry(local_page)
    assert "lf-diagram" in bundled_registry
    assert "lf-local" not in bundled_registry
    assert bundled_registry["$layer"]["packages"] == ["diagram"]
    assert "lf-diagram" not in local_registry
    assert "lf-local" in local_registry
    assert local_registry["$layer"]["packages"] == ["./packages/diagram"]


def test_a_revision_reads_its_package_copy_after_the_selection_moves_on(
    tmp_path, monkeypatch
):
    """A saved version keeps the package it was written with: dropping the package
    from the selection leaves its copy for the revisions that name it, and an edit to
    the package reaches them at a new address, never under one a browser cached, and
    as a new generation, which an open document reloads on."""
    from leaf.revision_artifact import read_artifact
    from leaf.revisioning import activate_source
    from leaf.runtime_selection import execution_identity

    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "custom"
    (custom / "widgets").mkdir(parents=True)
    (custom / "widgets" / "helper.js").write_text("export const value = 1;\n")
    page = tmp_path / "page"
    init = ["page", "init", "--package", "./custom", str(page)]
    assert CliRunner().invoke(cli_model.cli, init).exit_code == 0
    (page / "index.html").write_text(PLAIN_PAGE)
    assert activate_source(page).error is None
    first = execution_identity(read_artifact(page, 1))
    generation = registry_storage.layer_record(page)["generation"]

    (custom / "widgets" / "helper.js").write_text("export const value = 2;\n")
    assert CliRunner().invoke(cli_model.cli, init).exit_code == 0
    assert execution_identity(read_artifact(page, 1)) != first
    assert registry_storage.layer_record(page)["generation"] != generation

    cleared = CliRunner().invoke(
        cli_model.cli, ["page", "init", "--no-packages", str(page)]
    )
    assert cleared.exit_code == 0, cleared.output
    assert registry_storage.layer_packages(page) == []
    assert "/widgets/helper.js" in layer_files_of_revision(page, 1)


def layer_files_of_revision(page: Path, revision: int) -> dict[str, bytes]:
    from leaf.revision_artifact import read_artifact

    manifest = json.loads(read_artifact(page, revision).manifest)
    return registry_storage.selected(manifest["layer"], page).files


def test_init_merges_reaction_tokens_merge_patch_style(tmp_path, monkeypatch):
    """The shipped tokens are the default layer's statement, not core's. A project's
    entry under a token's name replaces that token whole, a new name joins after
    the shipped ones, and `null` removes one — which is the only way a layer can take
    a token off the bar without restating the whole set. The order used by the optional
    digit accelerators is the merged map's."""
    project = tmp_path / "proj"
    layer = project / ".leaf"
    layer.mkdir(parents=True)
    (layer / "registry.json").write_text(
        json.dumps(
            {
                "$reactions": {
                    "tokens": {
                        "keep": {"glyph": "👍", "settles": True},
                        "shorten": None,
                        "meh": {"glyph": "~"},
                    }
                }
            }
        )
    )
    monkeypatch.chdir(project)

    page = tmp_path / "page"
    result = CliRunner().invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
    )

    assert result.exit_code == 0, result.output
    tokens = registry_storage.load_registry(page)["$reactions"]["tokens"]
    assert list(tokens) == ["keep", "change", "clarify", "support", "prioritize", "meh"]
    assert tokens["keep"] == {"glyph": "👍", "settles": True}
    assert tokens["meh"] == {"glyph": "~"}
    assert "settles" not in tokens["change"]


@pytest.mark.parametrize(
    "entry",
    [
        {"glyph": ""},
        {"glyph": "✓", "means": "x"},  # prose the layer does not declare
        {"glyph": "✓", "settle": True},  # a flag nothing reads
        {"glyph": "✓", "settles": "yes"},
    ],
)
def test_package_check_refuses_a_malformed_reaction_token(tmp_path, monkeypatch, entry):
    """Consumers read declared fields directly, so an invalid glyph, an undeclared
    field, or a misspelled behavior must fail at the package boundary instead of
    disappearing."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli_model.cli, ["package", "init", ".leaf"]).exit_code == 0
    registry_path = tmp_path / ".leaf" / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["$reactions"] = {"tokens": {"nod": entry}}
    registry_path.write_text(json.dumps(registry))

    status, [refused] = package_findings(".leaf")
    assert status == 1

    assert refused.code == "layer-facts"
    assert refused.values["path"][:3] == ["$reactions", "tokens", "nod"]


def test_the_register_is_the_only_way_a_key_enters_the_runtime():
    """Every surface that names a key is a projection of the register, which holds only if
    nothing binds a key behind its back. That is not a property a rendered page can be
    asked about — a listener nobody declared looks exactly like no listener at all until
    the press it eats goes missing — so it is pinned in the source, the way the
    document-level class surface is. The listeners are read from each parsed module
    (tests/js_facts.mjs), so one wrapped across lines or registered for several
    types in a loop counts as written.

    Each allowed one is named here. The dispatcher has a capture listener for
    shortcut characters, before nested libraries' typeahead, and a bubble listener
    for other keys, after controls' own handling; both use the same register.
    The aim latch is not a binding at all: holding ⌥ arms nothing and answers no
    press, it paints what
    a click would take, and its keyup half has no place in a table of presses. The
    prepaint bootstrap's hold answers no press either: it keeps keys pressed before the
    page presents and hands them to the dispatcher's owner. The sample bootstrap's
    other listener enters its browsing context on trusted input without answering a
    key; the same listener handles pointer input. prepaint.js records inputs
    from the document's first script. focus.js reads keys as the end of a label press
    and as a Tab's step; neither answers a command. The
    interaction log records keys and answers none. A control standing over a page block, such as a code block's Copy, hands Tab back to its block. Another is how every
    drift this register replaced began — a
    `keydown` beside a display list, the two of them free to disagree about which keys the
    widget answers."""
    sources = [
        ROOT / "browser/leaf.js",
        *sorted((ROOT / "browser/runtime").rglob("*.js")),
        *sorted((ROOT / "packages").glob("*/widgets/*.js")),
        *sorted((ROOT / "examples/packages").glob("*/widgets/*.js")),
    ]
    listed = js_facts("keydown", sources).split()
    by_file = {}
    for line in listed:
        name = line.split(":")[0]
        by_file[name] = by_file.get(name, 0) + 1
    assert by_file == {
        "controller.js": 2,
        "aim.js": 1,
        "bootstrap.js": 2,
        "prepaint.js": 1,
        "focus.js": 2,
        "interaction-log.js": 1,
        "block-controls.js": 1,
    }, (
        f"the runtime's keydown listeners changed: {listed}. A key belongs in the "
        "register (keys(el, title, rows)), which is what lets a surface promise it."
    )


def test_a_host_that_names_nothing_is_asked_for_its_path_only_after_chrome(
    monkeypatch, tmp_path
):
    """With no variable set, PATH is the host's own statement of where its programs
    are, and a hardcoded candidate list is not: a list needs an entry per
    distribution and can never name a `/nix/store/<hash>-chromium-*/bin/chromium`.

    It is asked second, after the Chrome channel rather than before it, and that
    order is the whole of what keeps this from moving a host that works today: a box
    with both a Google Chrome and a distro Chromium goes on getting the Chrome the
    channel finds. So the launch is driven twice over one PATH holding one browser —
    once where the channel answers, once where it raises what Playwright raises on a
    host with no Chrome installed — and the assertion is the calls that were made,
    since a test reading only the browser back cannot see which of the two produced
    it."""
    from playwright.sync_api import Error as PlaywrightError

    chromium = tmp_path / "bin" / "chromium"
    chromium.parent.mkdir()
    chromium.write_text("#!/bin/sh\nexec true\n")
    chromium.chmod(0o755)
    for variable in browser_model.VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("PATH", str(chromium.parent))

    calls = []

    class Chromium:
        def __init__(self, channel_answers):
            self.channel_answers = channel_answers

        def launch(self, **kwargs):
            calls.append(kwargs)
            if "channel" in kwargs and not self.channel_answers:
                raise PlaywrightError(
                    "BrowserType.launch: Chromium distribution 'chrome' is not found "
                    "at /opt/google/chrome/chrome"
                )
            return "a browser"

    class Playwright:
        def __init__(self, channel_answers):
            self.chromium = Chromium(channel_answers)

    launched, name = browser_model.launch_browser(Playwright(True))
    assert (launched, name) == ("a browser", "Chrome")
    assert calls == [{"channel": "chrome"}], "the channel keeps the hosts it has"

    calls.clear()
    launched, name = browser_model.launch_browser(Playwright(False))
    assert (launched, name) == ("a browser", str(chromium))
    assert calls == [{"channel": "chrome"}, {"executable_path": str(chromium)}]

    # And the same reading is what the failed-launch line says, so a host with
    # neither is told what was looked for rather than named a variable twice.
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert browser_model.discovered_executable() is None
    hint = browser_model.browser_hint()
    assert "chromium" in hint and "LEAF_BROWSER_EXECUTABLE" in hint

    # Inside an agent's sandbox no browser starts however the host names one, so
    # the line sends the check outside the sandbox instead.
    monkeypatch.setenv("CODEX_SANDBOX", "seatbelt")
    hint = browser_model.browser_hint()
    assert "CODEX_SANDBOX=seatbelt" in hint and "outside the sandbox" in hint


def test_producer_instructions_names_a_package_script_the_run_door_reaches(tmp_path):
    """A reader of `leaf page instructions` with no skill loaded, such as a worker the
    author assigns, gets a pipeline it can run as printed: the producer names a
    package and a script, and `package run` finds that script by the same lookup
    `--package` resolves through, with no path on this machine in the text."""
    page = tmp_path / "patch-page"
    initialized = CliRunner().invoke(
        cli_model.cli, ["page", "init", "--package", "diff", str(page)]
    )
    assert initialized.exit_code == 0, initialized.output
    producer = CliRunner().invoke(
        cli_model.cli,
        ["page", "instructions", str(page), "--contract", "unified-diff"],
    )
    assert producer.exit_code == 0, producer.output
    [(package, script)] = re.findall(
        r"\| leaf package run (\S+) (\S+) \| leaf data set ",
        json.loads(producer.output)["producer"],
    )
    assert (layer_model.named_package(package) / "scripts" / script).is_file()
    assert not (page / "scripts").exists(), "a page never vendors scripts"


def test_an_installed_package_runs_its_own_scripts_by_name(tmp_path, monkeypatch):
    """`package install` carries `scripts/`, and `package run` runs one in the
    environment its header declares, handing it stdin, the arguments after the
    script's name (options included), stdout, and its exit status."""
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "src" / "tally"
    created = CliRunner().invoke(cli_model.cli, ["package", "init", str(source)])
    assert created.exit_code == 0, created.output
    (source / "scripts").mkdir()
    (source / "scripts" / "count.py").write_text(
        "# /// script\n"
        "# dependencies = []\n"
        "# ///\n"
        "import json, sys\n"
        "lines = sys.stdin.read().splitlines()\n"
        "json.dump({'args': sys.argv[1:], 'lines': len(lines)}, sys.stdout)\n"
        "sys.exit(3 if '--fail' in sys.argv else 0)\n"
    )
    installed = CliRunner().invoke(cli_model.cli, ["package", "install", str(source)])
    assert installed.exit_code == 0, installed.output
    shutil.rmtree(source)

    def run(*arguments):
        return subprocess.run(
            [*LEAF_COMMAND, "package", "run", *arguments],
            input="one\ntwo\n",
            capture_output=True,
            text=True,
            check=False,
        )

    counted = run("tally", "count.py", "--label", "x y")
    failed = run("tally", "count.py", "--fail")
    missing = run("tally", "total.py")
    unknown = run("tallies", "count.py")

    assert counted.returncode == 0, counted.stderr
    assert json.loads(counted.stdout) == {"args": ["--label", "x y"], "lines": 2}
    assert failed.returncode == 3
    assert json.loads(failed.stdout) == {"args": ["--fail"], "lines": 2}
    assert missing.returncode == 1
    assert json.loads(missing.stderr)["error"] == (
        "package 'tally' has no script 'total.py'; available: count.py"
    )
    assert unknown.returncode == 1
    assert "unknown package 'tallies'" in unknown.stderr


def test_package_check_refuses_a_script_that_would_run_in_the_callers_project(
    tmp_path, monkeypatch
):
    """Without an inline `script` block, `uv run --script` runs a file in whatever
    project the caller's directory reaches, so check and install refuse one."""
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "src" / "tally"
    created = CliRunner().invoke(cli_model.cli, ["package", "init", str(source)])
    assert created.exit_code == 0, created.output
    (source / "scripts").mkdir()
    script = source / "scripts" / "count.py"
    script.write_text("print('counted')\n")

    checked = CliRunner().invoke(cli_model.cli, ["package", "check", str(source)])
    installed = CliRunner().invoke(cli_model.cli, ["package", "install", str(source)])

    assert checked.exit_code == 1
    [refused] = json.loads(checked.stdout)["findings"]
    assert refused["code"] == "package"
    assert refused["text"].startswith(str(script))
    message = "needs an inline `# /// script` metadata block"
    assert message in refused["text"]
    assert installed.exit_code == 1
    assert message in json.loads(installed.stderr)["error"]
    assert not (machine_model.package_store() / "tally").exists()


def bundled_script_metadata(script: Path) -> dict:
    """The inline `script` block of one bundled script, read as PEP 723 reads it."""
    (block,) = [
        match["content"]
        for match in packages_model.INLINE_METADATA.finditer(script.read_text())
        if match["type"] == "script"
    ]
    return tomllib.loads(
        "".join(
            line[2:] if line.startswith("# ") else line[1:]
            for line in block.splitlines(keepends=True)
        )
    )


def test_the_suite_pins_every_bundled_script_dependency():
    """A bundled script's header declares its dependencies and ships no lock, so
    they follow the tree's dependency policy, a floor and no cap (AGENTS.md, "The
    install runs this tree"), and the dev group repeats each one: `uv.lock` then pins
    what the suite runs the script against, and the suite needs no network to run it.
    """
    pyproject = (PLUGIN_ROOT / "pyproject.toml").read_text()
    scripts = sorted(schema_model.BUNDLED_PACKAGES.glob("*/scripts/*.py"))
    assert scripts
    declared = set()
    for script in scripts:
        metadata = bundled_script_metadata(script)
        constraints = [metadata[key] for key in ["requires-python"] if key in metadata]
        for value in metadata.get("dependencies", []):
            requirement = Requirement(value)
            assert requirement.url is None, (script, value)
            constraints.append(str(requirement.specifier))
            declared.add(str(requirement))
        for constraint in constraints:
            assert {spec.operator for spec in SpecifierSet(constraint)} == {">="}, (
                script,
                constraint,
            )
    # Bundled packages never pass through `package install`, so hold their scripts
    # to the same check here.
    for package in {script.parent.parent for script in scripts}:
        checked = CliRunner().invoke(cli_model.cli, ["package", "check", str(package)])
        assert checked.exit_code == 0, checked.output
    assert [
        requirement
        for requirement in sorted(declared)
        if f'  "{requirement}",' not in pyproject
    ] == []


@pytest.fixture
def instruction_page(tmp_path: Path, monkeypatch):
    """A page selecting a package of instructed vocabulary and audience instructions,
    before authoring has started."""
    monkeypatch.chdir(tmp_path)
    package = tmp_path / "instructed"
    registry = {"$data": {"contracts": {}}}
    owner = element_declaration("lf-instruction-owner")
    owner.update(
        {
            "x-content": "markup",
            "x-instructions": "Choose the owner's inputs before composing it.",
            "x-example": '<lf-instruction-owner id="owner"><p class="instruction-caption">Inputs</p><lf-instruction-member id="input" kind="first"></lf-instruction-member><lf-instruction-example id="example"></lf-instruction-example></lf-instruction-owner>',
            "x-data": {
                "records": {"contract": "instruction-records", "source": "source"}
            },
        }
    )
    owner["properties"]["source"] = {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"}
    registry["lf-instruction-owner"] = owner
    registry[".instruction-summary"] = {
        "description": "A summary of the selected inputs.",
        "x-instructions": "Keep the summary beside its inputs.",
        "x-example": '<tr class="instruction-summary"><td class="instruction-number"><lf-instruction-owner id="owner"></lf-instruction-owner></td></tr>',
    }
    registry[".instruction-number"] = {
        "description": "A numeric table cell.",
        "x-instructions": "Align numeric inputs in their table cell.",
        "x-example": '<td class="instruction-number">12</td>',
    }
    registry[".instruction-caption"] = {
        "description": "A caption for the inputs.",
        "x-instructions": "Name what the inputs collect.",
        "x-example": '<p class="instruction-caption">Inputs</p>',
    }
    registry[".instruction-unused"] = {
        "description": "An unrelated note.",
        "x-instructions": "Unused idiom instructions.",
        "x-example": '<p class="instruction-unused">A different note.</p>',
    }
    registry["body"] = {
        "description": "The document body.",
        "x-instructions": "Unused body instructions.",
        "x-example": "<body><p>A complete document.</p></body>",
    }
    member = element_declaration("lf-instruction-member")
    member.update(
        {
            "x-owners": ["lf-instruction-owner"],
            "x-instructions": "Declare each member's kind.",
        }
    )
    member["properties"]["kind"] = {"type": "string", "enum": ["first", "second"]}
    member["required"].append("kind")
    member["x-example"] = (
        '<lf-instruction-owner id="owner"><lf-instruction-member id="member"'
        ' kind="first">One</lf-instruction-member></lf-instruction-owner>'
    )
    registry["lf-instruction-member"] = member
    for tag, text in (
        ("lf-instruction-example", "Preserve the copied example's companion."),
        ("lf-instruction-unused", "This optional alternative is unused."),
    ):
        entry = element_declaration(tag)
        entry["x-instructions"] = text
        entry["x-owners"] = ["lf-instruction-owner"]
        entry["x-example"] = (
            f'<lf-instruction-owner id="owner"><{tag} id="member">One</{tag}>'
            "</lf-instruction-owner>"
        )
        registry[tag] = entry
    registry["$data"]["contracts"].update(
        {
            "instruction-records": {
                "description": "Records for the selected widget.",
                "schema": {"type": "object"},
                "instructions": {
                    "author": "Bind a named records source.",
                    "producer": "Supply records in one snapshot.",
                },
            },
            "instruction-unused": {
                "description": "A different source.",
                "schema": {"type": "object"},
                "instructions": {"producer": "Unused producer instructions."},
            },
        }
    )
    directory = package / "instructions"
    directory.mkdir(parents=True)
    (package / "registry.json").write_text(json.dumps(registry))
    (directory / "author.md").write_text("Shared composition instructions.\n")
    (directory / "coordinator.md").write_text("Assign the selected work.\n")
    page = tmp_path / "page"
    result = CliRunner().invoke(
        cli_model.cli, ["page", "init", "--package", "./instructed", str(page)]
    )
    assert result.exit_code == 0, result.output
    assert not (page / "index.html").exists()
    return page


def test_selected_instructions_cover_dependencies_without_loading_unused_vocabulary(
    instruction_page,
):
    shared = page_instructions(instruction_page)
    assert set(shared) == {"author", "coordinator"}
    assert "Vocabulary" not in shared["author"]
    assert "Data contract" not in shared["author"]

    selected = page_instructions(instruction_page, entries=(".instruction-summary",))
    assert set(selected) == {"author", "coordinator", "producer"}
    author = selected["author"]
    assert "Shared composition instructions." in author
    assert "Keep the summary beside its inputs." in author
    assert "Align numeric inputs in their table cell." in author
    assert "Name what the inputs collect." in author
    assert "Bind a named records source." in author
    assert "Choose the owner's inputs" in author
    assert "Declare each member's kind." in author
    assert "Preserve the copied example's companion." in author
    assert "unused" not in author
    assert selected["producer"] == (
        "# Data contract `instruction-records`\n\nSupply records in one snapshot.\n"
    )
    assert author.count("# Vocabulary `lf-instruction-owner`") == 1


def test_a_declared_attribute_lists_its_words_in_the_composed_schema(page_dir):
    """An attribute that names a layer-wide word, such as a column's tone or a code
    block's language, takes the layer's list as its `enum` in the vocabulary a page
    composes, so its schema says what it accepts to validation and to an author
    reading the entry, and the selected entry's instructions list the words."""
    registry = registry_storage.read_page_registry(page_dir).registry
    checked = set()
    for key, fact in DECLARED_WORDS:
        for name, entry in registry.items():
            if name.startswith("$") or not isinstance(entry, dict) or key not in entry:
                continue
            names = registry[fact]["names"]
            assert entry["properties"][entry[key]]["enum"] == names
            author = page_instructions(page_dir, entries=(name,))["author"]
            listed = ", ".join(f"`{word}`" for word in names)
            assert f"`{entry[key]}` takes one of: {listed}." in author
            checked.add(key)
    assert checked == {key for key, _ in DECLARED_WORDS}


def test_cli_selection_returns_the_composed_audience_map(instruction_page):
    runner = CliRunner()
    reading = runner.invoke(
        cli_model.cli,
        [
            "page",
            "instructions",
            str(instruction_page),
            "--use",
            ".instruction-summary",
            "--contract",
            "instruction-records",
        ],
    )
    assert reading.exit_code == 0, reading.output
    assert json.loads(reading.output) == page_instructions(
        instruction_page,
        entries=(".instruction-summary",),
        contracts=("instruction-records",),
    )
    producer = runner.invoke(
        cli_model.cli,
        [
            "page",
            "instructions",
            str(instruction_page),
            "--contract",
            "instruction-records",
        ],
    )
    assert producer.exit_code == 0, producer.output
    assert json.loads(producer.output)["producer"] == (
        "# Data contract `instruction-records`\n\nSupply records in one snapshot.\n"
    )
    for option, value, message in (
        ("--use", "lf-absent", "unknown instructions vocabulary entry"),
        ("--use", "$data", "unknown instructions vocabulary entry"),
        # A Layout is a class the page's CSS provides; the refusal says where it is.
        ("--use", "layout-tiles", "page-layout.md describes them"),
        ("--contract", "absent", "unknown instructions data contract"),
    ):
        result = runner.invoke(
            cli_model.cli,
            ["page", "instructions", str(instruction_page), option, value],
        )
        assert result.exit_code != 0
        assert message in result.output


def test_widget_instructions_are_nonempty_text_and_reject_the_old_shape():
    entry = element_declaration("lf-instruction-test")
    for key, value in (
        ("x-instructions", ""),
        ("x-instructions", " \n\t"),
        ("x-instructions", {"author": "Use this."}),
        ("x-guidance", {"author": "Use this."}),
    ):
        malformed = {**entry, key: value}
        refused = registry_refusal(
            lambda malformed=malformed: registry_widgets.validate_widget_schemas(
                {"lf-instruction-test": malformed}, {"contracts": {}}, "registry.json"
            )
        )
        assert (refused.code, refused.at) == (
            "invalid-extensions",
            "<lf-instruction-test>",
        )
    registry_widgets.validate_widget_schemas(
        {"lf-instruction-test": {**entry, "x-instructions": "Use this."}},
        {"contracts": {}},
        "registry.json",
    )


def test_instruction_reading_uses_the_candidate_vocabulary_before_html_changes(
    instruction_page,
):
    source = instruction_page / "index.html"
    source.write_text(
        leaf_page("Instructions", '<p id="intro">A minimal document.</p>')
    )
    activation = activate_source(instruction_page)
    assert activation.error is None, activation.error
    original_html = source.read_text()

    declare_on_page(
        instruction_page,
        lambda registry: registry["lf-instruction-owner"].update(
            {"x-instructions": "Use the new candidate contract."}
        ),
    )
    instructions = page_instructions(
        instruction_page, entries=("lf-instruction-owner",)
    )
    assert "Use the new candidate contract." in instructions["author"]
    assert "Choose the owner's inputs" not in instructions["author"]
    assert source.read_text() == original_html
