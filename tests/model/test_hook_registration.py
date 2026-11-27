"""Each harness's registration of Leaf's hooks: the harness each names, the time
each is given, and the launcher that runs a hook through uv."""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys

import pytest
from interact_support import (
    ADMITTING_DEPENDENCIES,
    COMPOSITE_TIMEOUT,
    EVERY_TURN_DEPENDENCIES,
    PLUGIN_ROOT,
    READING_DEPENDENCIES,
    STATED_TIMEOUT,
    append_carried_log_record,
    append_command,
    fresh_imports,
    leaf_main,
    published,
    record_claim,
    response_reference,
    serving,
    unlisted_dependencies,
    wait_for,
)

from leaf.base import harness as harness_model
from leaf.base import leases as leases_model
from leaf.base import service as service_model
from leaf.base import state as cleanup_model
from leaf.commands import session as session_model
from leaf.records import transaction as transaction_model

# Each harness's own registrations of Leaf's hooks (`harness.hook_harness`); Pi's
# are its extension's calls (`test_interact_pi.py`).
REGISTRATIONS = {"claude-code": "hooks.json", "codex": "codex.json"}


def _installed_since(plugins):
    """Record in `installed_plugins.json` a newer copy Claude Code installed beside
    the one a session loaded, and return its root."""
    newer = plugins / "cache" / "leaf" / "leaf" / "1b1b1b1b1b1b"
    launcher = newer / "bin" / "leaf"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\necho ran\n")
    launcher.chmod(0o755)
    (plugins / "installed_plugins.json").write_text(
        json.dumps({"plugins": {"leaf@leaf": [{"installPath": str(newer)}]}})
    )
    return newer


def test_a_copy_that_lost_its_project_refuses_naming_the_reload(tmp_path):
    """Claude Code may delete an orphaned copy's files while a session still runs
    its launcher. That launcher refuses, naming `/reload-plugins`, rather than run
    the copy Claude Code installed since or leave uv to run the caller's `python`."""
    loaded = _installed_since(tmp_path / "plugins").with_name("0a0a0a0a0a0a")
    orphan = loaded / "bin" / "leaf"
    orphan.parent.mkdir(parents=True)
    shutil.copy(PLUGIN_ROOT / "bin/leaf", orphan)
    refused = subprocess.run(
        [str(orphan), "page", "state", "a page"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert (refused.returncode, refused.stdout) == (1, ""), refused.stderr
    assert "has lost its files; run /reload-plugins" in refused.stderr


def _registrations(harness):
    path = PLUGIN_ROOT / "hooks" / REGISTRATIONS[harness]
    return json.loads(path.read_text())["hooks"]


def _registered_hook_command(harness, event):
    """The synchronous command the installed harness runs for this event."""
    [hook] = [
        hook
        for registration in _registrations(harness)[event]
        for hook in registration["hooks"]
        if not hook.get("asyncRewake")
    ]
    return hook["command"]


def test_claude_code_runs_the_start_hook_only_after_a_compaction():
    """Outside a compaction, Leaf's start hook has nothing to add, while Claude Code
    holds a resumed session's first reply until its start hooks end; the prompt
    hook serves the session's pages again (`reconnect`). After a compaction it
    tells the agent to read the leaf skill again (`hooks.reload_skill`) before it
    replies, which nothing else does."""
    [registration] = _registrations("claude-code")["SessionStart"]
    assert registration["matcher"] == "compact"
    [hook] = registration["hooks"]
    assert not hook.get("async")


def _registered_hook_arguments(harness, event):
    """The `leaf` arguments the synchronous registration for this event passes."""
    words = shlex.split(_registered_hook_command(harness, event))
    return words[words.index("hook") : words.index("||")]


def _registered_watch():
    """Claude Code's background Stop registration."""
    [hook] = [
        hook
        for registration in _registrations("claude-code")["Stop"]
        for hook in registration["hooks"]
        if hook.get("asyncRewake")
    ]
    return hook


def test_each_harness_registration_names_its_harness():
    """A hook learns which harness ran it from its registration, never from an
    environment that a harness launched from another's shell inherits. So every
    `leaf hook` a harness's file registers passes that harness's name, the
    manifest of each harness names only its own file, and only Claude Code's
    holds the background watch: Codex ignores `asyncRewake` and would wait on
    it."""
    assert set(REGISTRATIONS) | {"pi"} == set(harness_model.HOOK_HARNESSES)
    codex_manifest = json.loads((PLUGIN_ROOT / ".codex-plugin/plugin.json").read_text())
    assert codex_manifest["hooks"] == "./hooks/codex.json"
    for harness in REGISTRATIONS:
        hooks = [
            hook
            for registrations in _registrations(harness).values()
            for registration in registrations
            for hook in registration["hooks"]
        ]
        named = [
            words[words.index("--harness") + 1]
            for words in map(shlex.split, (hook["command"] for hook in hooks))
            if "hook" in words
        ]
        assert named and set(named) == {harness}
        assert any(hook.get("asyncRewake") for hook in hooks) == (
            harness == "claude-code"
        )


def test_every_carrying_hook_has_the_timeout_leaf_counts_on():
    """Every harness whose hooks carry input gives its prompt and Stop hooks
    HOOK_TIMEOUT_S, the time Leaf counts on: a hook confirms an inline delivery
    only within half of it (CONFIRM_WITHIN), and a turn-end watch gives the Stop
    hook all of it to close the turn before waking for pending input."""
    for harness in REGISTRATIONS:
        for event in (
            "UserPromptSubmit",
            "Stop",
            *(["PostToolBatch"] if harness == "claude-code" else []),
        ):
            [hook] = [
                hook
                for registration in _registrations(harness)[event]
                for hook in registration["hooks"]
                if not hook.get("asyncRewake")
            ]
            assert hook["timeout"] == harness_model.HOOK_TIMEOUT_S, (
                harness,
                event,
            )
    # Pi's extension runs the hook itself and bounds it with its own copy.
    [timeout] = re.findall(
        r"const HOOK_TIMEOUT_MS = ([\d_]+);?$",
        (PLUGIN_ROOT / "hooks" / "pi.ts").read_text(),
        re.MULTILINE,
    )
    assert int(timeout.replace("_", "")) == harness_model.HOOK_TIMEOUT_S * 1000


def test_the_registered_watch_hook_wakes_the_session(claimed, tmp_path):
    """Claude Code's background Stop registration runs the watch, and its exit 2
    with stderr is the whole wake. Driven the way Claude Code drives it, through a
    shell with the payload on stdin, because the wiring (the watch supervisor, uv,
    the exit status it passes through) is the subject."""
    command = _registered_watch()["command"]
    env = os.environ | {"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT)}
    leases_model.mark_hooks("s1")  # its harness runs Leaf's hooks
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)
    cleanup_model.close_session_turn("s1")
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )

    def run(env):
        return subprocess.run(
            ["sh", "-c", command],
            input=json.dumps({"hook_event_name": "Stop", "session_id": "s1"}),
            env=env,
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )

    woke = run(env)
    assert (woke.returncode, woke.stdout) == (2, ""), woke.stderr
    assert woke.stderr.startswith(f"{claimed} has new input")

    # uv and Python spend exit 2 on startup failures too. Report the error as a
    # nonblocking failure, distinct from the successful delivery wake.
    broken = tmp_path / "plugin"
    (broken / "hooks" / "scripts").mkdir(parents=True)
    (broken / "pyproject.toml").write_text("not a project")
    shutil.copy(
        PLUGIN_ROOT / "hooks" / "scripts" / "background-watch.py",
        broken / "hooks" / "scripts",
    )
    (broken / "bin").mkdir()
    shutil.copy(PLUGIN_ROOT / "bin/leaf", broken / "bin/leaf")
    failed = run(env | {"CLAUDE_PLUGIN_ROOT": str(broken)})
    assert (failed.returncode, failed.stdout) == (1, "")
    assert "pyproject.toml" in failed.stderr


def test_cancelling_the_background_registration_never_wakes_the_session(
    tmp_path, spawn
):
    """Cancellation stays quiet even if the child catches SIGTERM and exits zero."""
    project = tmp_path / "plugin"
    supervisor = project / "hooks/scripts/background-watch.py"
    supervisor.parent.mkdir(parents=True)
    supervisor.write_bytes(
        (PLUGIN_ROOT / "hooks/scripts/background-watch.py").read_bytes()
    )
    launcher = project / "bin/leaf"
    launcher.parent.mkdir()
    launcher.write_text(
        f"#!{sys.executable}\n"
        "import signal, sys\n"
        "from pathlib import Path\n"
        "def cancelled(*args):\n"
        "    print('not a delivery')\n"
        "    print('cancelled', file=sys.stderr)\n"
        "    sys.exit(0)\n"
        "signal.signal(signal.SIGTERM, cancelled)\n"
        "Path(sys.argv[-1]).touch()\n"
        "signal.pause()\n"
    )
    launcher.chmod(0o755)
    ready = tmp_path / "ready"
    watching = spawn(
        [sys.executable, str(supervisor), str(ready)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    watching.stdin.write("{}")
    watching.stdin.close()
    watching.stdin = None
    wait_for(ready.exists, bool, failure="the child watch never started")
    watching.terminate()
    out, err = watching.communicate(timeout=STATED_TIMEOUT)
    assert (watching.returncode, out, err) == (0, "", "")


@pytest.mark.parametrize("harness", REGISTRATIONS)
def test_registered_hook_failures_remain_nonblocking_and_visible(harness, tmp_path):
    """Failed application and uv startup retain diagnostics without blocking a turn.

    In particular uv's exit 2 must not become the harness's blocking status.
    """

    def run(payload, env=None):
        return subprocess.run(
            ["/bin/sh", "-c", _registered_hook_command(harness, "Stop")],
            input=payload,
            env=(env or os.environ)
            | {"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT), "PLUGIN_ROOT": str(PLUGIN_ROOT)},
            capture_output=True,
            text=True,
            timeout=COMPOSITE_TIMEOUT,
            check=False,
        )

    crashed = run("not a hook payload")
    assert (crashed.returncode, crashed.stdout) == (1, "")
    assert "hook expects" in crashed.stderr
    # The launcher finds its root with `dirname`; only uv is missing.
    tools = tmp_path / "no-uv"
    tools.mkdir()
    (tools / "dirname").symlink_to(shutil.which("dirname"))
    unresolvable = run("{}", env=os.environ | {"PATH": str(tools)})
    assert (unresolvable.returncode, unresolvable.stdout) == (1, "")
    assert "uv" in unresolvable.stderr


@pytest.mark.parametrize(
    "harness,event",
    [
        ("claude-code", "SessionStart"),
        ("claude-code", "PostToolBatch"),
        ("claude-code", "Stop"),
        ("claude-code", "UserPromptSubmit"),
        ("codex", "SessionStart"),
        ("codex", "Stop"),
        ("codex", "UserPromptSubmit"),
        ("codex", "PostToolUse"),
        ("codex", "Interrupt"),
    ],
)
def test_the_registered_hook_leaves_library_execution_to_uv(harness, event, tmp_path):
    """Turn hooks need no system Python; the shell launcher owns uv.

    This plugin copy has no library, and system python3 refuses to run. A recording
    uv witnesses the selected project, application command and unchanged payload.
    """
    project = tmp_path / "plugin"
    launcher = project / "bin/leaf"
    launcher.parent.mkdir(parents=True)
    launcher.write_bytes((PLUGIN_ROOT / "bin/leaf").read_bytes())
    launcher.chmod(0o755)
    (project / "pyproject.toml").touch()
    tools = tmp_path / "tools"
    tools.mkdir()
    uv = tools / "uv"
    uv.write_text(
        '#!/bin/sh\nprintf \'%s\\n\' "$@" > "$UV_CALLED"\n/bin/cat > "$UV_INPUT"\n'
    )
    uv.chmod(0o755)
    python = tools / "python3"
    python.write_text('#!/bin/sh\nprintf called > "$PYTHON_CALLED"\nexit 99\n')
    python.chmod(0o755)
    python_called = tmp_path / "python-called"
    called, received = tmp_path / "uv-called", tmp_path / "uv-input"
    payload = json.dumps({"hook_event_name": event, "session_id": "hook-harness"})
    done = subprocess.run(
        ["/bin/sh", "-c", _registered_hook_command(harness, event)],
        input=payload,
        env=os.environ
        | {
            "PATH": f"{tools}:/usr/bin:/bin",
            "CLAUDE_PLUGIN_ROOT": str(project),
            "PLUGIN_ROOT": str(project),
            "PYTHON_CALLED": str(python_called),
            "UV_CALLED": str(called),
            "UV_INPUT": str(received),
        },
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    assert called.read_text().splitlines() == [
        "run",
        "-q",
        "--no-dev",
        "--project",
        str(project),
        "python",
        "-P",
        "-m",
        "leaf",
        *_registered_hook_arguments(harness, event),
    ]
    assert received.read_text() == payload
    assert not python_called.exists()


def test_codex_tool_hook_starts_leaf_only_for_a_session_that_claimed_a_page(
    page_dir, tmp_path
):
    """Codex runs its tool hook after every tool call of every task, and most hold
    no page, so the launcher asks the environment's interpreter first and starts
    uv only for a session that has claimed one. Every other Codex hook runs whole,
    and so does the tool hook wherever the question cannot be asked: a failure
    there must not drop it."""
    project = tmp_path / "plugin"
    launcher = project / "bin/leaf"
    launcher.parent.mkdir(parents=True)
    launcher.write_bytes((PLUGIN_ROOT / "bin/leaf").read_bytes())
    launcher.chmod(0o755)
    (project / "pyproject.toml").touch()
    program = project / "src/leaf/base/state.py"
    program.parent.mkdir(parents=True)
    program.write_bytes((PLUGIN_ROOT / "src/leaf/base/state.py").read_bytes())
    interpreter = project / ".venv/bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to(sys.executable)
    tools = tmp_path / "tools"
    tools.mkdir()
    called = tmp_path / "uv-called"
    uv = tools / "uv"
    uv.write_text('#!/bin/sh\n/bin/cat > "$UV_CALLED"\n')
    uv.chmod(0o755)

    def run(event, session):
        called.unlink(missing_ok=True)
        payload = json.dumps({"hook_event_name": event, "session_id": session})
        done = subprocess.run(
            ["/bin/sh", "-c", _registered_hook_command("codex", event)],
            input=payload,
            env=os.environ
            | {
                "PLUGIN_ROOT": str(project),
                "PATH": f"{tools}:/usr/bin:/bin",
                "UV_CALLED": str(called),
            },
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
        assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
        return json.loads(called.read_text()) if called.exists() else None

    harness_2 = harness_model.session_harness()
    assert harness_2 is not None
    session = harness_2.session
    assert run("PostToolUse", session) is None
    assert run("Stop", session) == {"hook_event_name": "Stop", "session_id": session}

    # Claiming a page marks the session for the rest of its generation.
    assert transaction_model.claim_page(page_dir)
    assert run("PostToolUse", session) == {
        "hook_event_name": "PostToolUse",
        "session_id": session,
    }
    assert run("PostToolUse", "another-session") is None

    # An interpreter that cannot answer leaves the hook to run whole.
    interpreter.unlink()
    interpreter.write_text("#!/bin/sh\nexit 1\n")
    interpreter.chmod(0o755)
    assert run("PostToolUse", "another-session") == {
        "hook_event_name": "PostToolUse",
        "session_id": "another-session",
    }


def test_a_hook_in_a_session_holding_no_page_imports_no_page_reading_or_server(
    page_dir,
):
    """A harness runs Leaf's hooks at every turn of every session the plugin is
    installed in, and most hold no page. Each waits on `import leaf.commands.hooks`, so
    that import, and a prompt or Stop hook in a session holding nothing, loads
    neither the page servers nor page reading: markup, registry schemas, and
    anchor capture. Run in a fresh interpreter, whose `sys.modules` is the hook's."""
    record_claim(page_dir, id="another-session")
    program = """
import io, json, runpy, sys
HOOK = ["hook", "--harness", "codex"]
cases = (
    ("UserPromptSubmit", HOOK, None),
    ("Stop", HOOK, None),
    ("Stop", ["hook", "--harness", "claude-code", "--watch"], None),
    ("UserPromptSubmit", HOOK, "provider-turn"),
    ("PostToolUse", HOOK, "provider-turn"),
    ("Stop", HOOK, "provider-turn"),
    ("UserPromptSubmit", HOOK, "interrupted-turn"),
    ("Interrupt", HOOK, "interrupted-turn"),
)
for event, args, turn_id in cases:
    sys.argv = ["leaf", *args]
    payload = {"hook_event_name": event, "session_id": "holds-nothing"}
    if turn_id:
        payload["turn_id"] = turn_id
    sys.stdin = io.StringIO(json.dumps(payload))
    try:
        runpy.run_module("leaf", run_name="__main__")
    except SystemExit as error:
        assert error.code == 0, error.code
    if turn_id:
        from leaf.agents.codex_state import hook_turn
        observed = hook_turn("holds-nothing")
        assert observed["turn"] == turn_id
        assert observed["running"] == (event not in ("Stop", "Interrupt"))
"""
    _, imported = fresh_imports(program)
    assert unlisted_dependencies(imported, EVERY_TURN_DEPENDENCIES) == {}
    page_reading_or_serving = (
        "leaf.pages.hosting",
        "leaf.serving.http",
        "leaf.agents.codex",
        "leaf.agents.delivery",
        "leaf.agents.thread",
        "leaf.commands.hook_transport",
        "leaf.serving.served_state.page",
        "leaf.records.event_contracts",
        "leaf.source.anchor_capture",
    )
    assert {
        module: imported[module]
        for module in page_reading_or_serving
        if module in imported
    } == {}


def test_the_hook_transport_imports_no_page_model():
    """Claude Code runs the tool-boundary hook before every model call, and one with
    nothing new reads only its pages' logs (`hook_transport.new_input`). So the hook
    transport loads the schema validators, the HTML, Markdown, CSS and script
    parsers and the file watcher only where a hook reads a page, vendors it or
    watches it; each costs tens of milliseconds at every start."""
    _, imported = fresh_imports("import leaf.commands.hook_transport\n")
    assert unlisted_dependencies(imported, EVERY_TURN_DEPENDENCIES) == {}


# The browser run (`render_gate/page_code.py`), and the Codex transport, whose import
# registers an exit handler: a step that draws nothing in a browser and asks Codex
# nothing loads neither.
UNASKED = ("leaf.pages.render_gate.page_code", "leaf.agents.codex")


@pytest.mark.parametrize(
    ("process", "listed"),
    [
        pytest.param("Stop", READING_DEPENDENCIES, id="stop"),
        pytest.param("UserPromptSubmit", ADMITTING_DEPENDENCIES, id="prompt"),
        pytest.param("thread reply", ADMITTING_DEPENDENCIES, id="reply"),
    ],
)
def test_a_session_holding_a_page_loads_only_the_dependencies_each_step_uses(
    claimed, process, listed
):
    """A session holding a page starts Leaf at each step of every turn, and each
    process pays at every start for what it imports. A Stop hook with nothing to hand
    over reads the page in its layer's vocabulary, which is merged and stamped but
    not validated (`layer-registry.md`), so it loads no schema validator. A prompt
    hook delivering the user's comment, and the agent's reply, load the validator to
    match handling clauses and to admit the event, and neither loads the page's
    source checks, the server or the file watcher. None of them asks Codex anything
    or draws anything in a browser: the reply's HTML runs the message check, which
    loads the browser run only for markup a browser must judge
    (`render_gate/messages.py`)."""
    published(claimed)
    hook = ["hook", "--harness", "claude-code"]
    payload = {"hook_event_name": process, "session_id": "s1", "prompt_id": "p1"}
    if process == "Stop":
        _, imported = fresh_imports(leaf_main(*hook, stdin=json.dumps(payload)))
        # The work fold loads inside `presence.read_work`, so only a read of the
        # page's work imports it there.
        assert imported.get("leaf.records.work_state", "").startswith(
            "leaf/agents/presence.py:"
        ), "the hook read no page"
    else:
        asked = append_command(
            claimed,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Check it."},
        )
        printed, imported = fresh_imports(
            leaf_main(*hook, stdin=json.dumps(payload))
            if process == "UserPromptSubmit"
            else leaf_main(
                "thread",
                "reply",
                response_reference(claimed, asked),
                "--ephemeral",
                "--text",
                "<em>Checking.</em>",
                "--title",
                "Check",
            )
        )
        assert asked["id"] in printed, printed
    assert unlisted_dependencies(imported, listed) == {}
    assert {m: imported[m] for m in UNASKED if m in imported} == {}


def test_a_page_check_with_nothing_a_browser_must_judge_loads_no_browser_run(page_dir):
    """An agent checks its page after each edit. A page that runs no code of its own
    and places no widget only a browser can judge needs no browser
    (`browser_judged.needs_browser`), so its check loads none of the browser run, and
    none of the Codex transport."""
    printed, imported = fresh_imports(leaf_main("page", "check", str(page_dir)))
    assert json.loads(printed)["browser"] is None, printed
    assert {m: imported[m] for m in UNASKED if m in imported} == {}


@pytest.mark.parametrize(
    ("native_session", "started"),
    [("dispatched-chat", True), ("dispatched-chat", False), ("another-chat", True)],
)
def test_codex_startup_can_claim_its_first_page_without_a_prompt(
    page_dir, tmp_path, monkeypatch, native_session, started
):
    """A dispatched desktop chat begins with tool input, not a user prompt.

    Run its registered startup hooks with no prior lifecycle or claim. Only a
    native transcript naming this chat can establish the first page's owner.
    """
    from leaf.base.refusals import Refused
    from leaf.commands.hooks import cmd_hook

    sid = "dispatched-chat"
    source = tmp_path / "native.jsonl"
    opened = cleanup_model.now_iso()
    source.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": native_session}})
        + "\n"
        + (
            json.dumps(
                {
                    "type": "event_msg",
                    "timestamp": opened,
                    "payload": {"type": "task_started", "turn_id": "first-turn"},
                }
            )
            + "\n"
            if started
            else ""
        )
    )
    assert cleanup_model.session_record(sid) is None
    for registration in _registrations("codex")["SessionStart"]:
        if re.search(registration.get("matcher", ""), "startup"):
            cmd_hook(
                "codex",
                {
                    "hook_event_name": "SessionStart",
                    "source": "startup",
                    "session_id": sid,
                    "transcript_path": str(source),
                },
            )
    harness = harness_model.CodexHarness(sid, "Codex")
    monkeypatch.setattr(harness_model.CodexHarness, "process_pid", lambda _: 123)
    monkeypatch.setattr(
        harness_model, "process_argv", lambda _: ["codex", "app-server"]
    )
    if native_session != sid:
        assert cleanup_model.session_record(sid) is None
        with pytest.raises(Refused, match="validated native transcript"):
            harness.lifetime()
        return
    with transaction_model.PageTransaction(page_dir) as page:
        page.take_claim(harness)
    claim = service_model.page_claim(page_dir)
    assert service_model.claim_is_active(claim)
    assert claim is not None
    assert claim["turn"] == ("first-turn" if started else None)
    assert claim["turn_opened"] == (opened if started else None)
    assert claim["turn_closed"] is None
    turn_record = cleanup_model.session_record(sid)
    assert turn_record is not None
    assert turn_record["transcript_path"] == str(source)
