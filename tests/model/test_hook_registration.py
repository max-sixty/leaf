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
from conftest import LEAF_COMMAND
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

from leaf import harness as harness_model
from leaf import hook_transport as hook_transport_model
from leaf import leases as leases_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model

# Each harness's own registrations of Leaf's hooks (`harness.hook_harness`); Pi's
# are its extension's calls (`test_interact_pi.py`).
REGISTRATIONS = {"claude-code": "hooks.json", "codex": "codex.json"}


def test_an_older_installed_copy_delivers_through_the_copy_installed_since(
    tmp_path, monkeypatch
):
    """Claude Code installs an update beside the copy a running session loaded and
    records it in `installed_plugins.json`; the older copy's delivery runs the newer
    one, and a checkout, which someone chose to run, runs itself."""
    from leaf import session_runtime

    cache = tmp_path / "plugins" / "cache" / "leaf" / "leaf"
    launchers = {}
    for version in ("0a0a0a0a0a0a", "1b1b1b1b1b1b"):
        launcher = cache / version / "bin" / "leaf"
        launcher.parent.mkdir(parents=True)
        launcher.write_text("#!/bin/sh\n")
        launcher.chmod(0o755)
        launchers[version] = launcher.resolve()
    (tmp_path / "plugins" / "installed_plugins.json").write_text(
        json.dumps(
            {"plugins": {"leaf@leaf": [{"installPath": str(cache / "1b1b1b1b1b1b")}]}}
        )
    )
    monkeypatch.setattr(session_runtime, "PLUGIN_ROOT", cache / "0a0a0a0a0a0a")
    assert session_runtime.delivering_launcher("") == launchers["1b1b1b1b1b1b"]
    # A bare command from the older copy runs the newer one, a hook its own way.
    ran = []
    monkeypatch.setattr(
        session_runtime.os, "execve", lambda path, argv, env: ran.append(argv)
    )
    session_runtime.hand_off_command(["page", "state", "p"])
    session_runtime.hand_off_command(["hook", "--harness", "claude-code"])
    assert ran == [[str(launchers["1b1b1b1b1b1b"]), "page", "state", "p"]]
    monkeypatch.setattr(session_runtime, "PLUGIN_ROOT", cache / "1b1b1b1b1b1b")
    assert session_runtime.delivering_launcher("") == launchers["1b1b1b1b1b1b"]
    monkeypatch.setattr(session_runtime, "PLUGIN_ROOT", tmp_path / "checkout")
    assert session_runtime.installed_launcher() is None


def test_session_selected_runtime_owns_the_whole_native_hook(tmp_path, monkeypatch):
    """An installed hook preserves stdin and defers lifecycle to the checkout.

    The other executable stands for an independently installed Leaf; it records
    what crossed the executable boundary instead of importing this test's runtime.
    A large payload also proves delegation is not bounded by an unwritten pipe.
    A gated hook keeps its gate, so the checkout's launcher runs it in one
    interpreter too (`bin/leaf`).
    """
    from leaf.session_runtime import select_launcher

    selected = tmp_path / "checkout with spaces" / "bin" / "leaf"
    selected.parent.mkdir(parents=True)
    selected.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "print(json.dumps({'argv': sys.argv[1:], 'payload': json.load(sys.stdin), "
        "'host': os.environ.get('LEAF_HOST_LAUNCHER')}))\n"
        "sys.exit(23)\n"
    )
    selected.chmod(0o755)
    cleanup_model.ensure_session("selected-runtime", {})
    select_launcher("selected-runtime", selected)
    before = cleanup_model.session_record("selected-runtime")
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "selected-runtime",
        "tool_input": "a" * 256_000,
    }
    monkeypatch.delenv("LEAF_HOST_LAUNCHER", raising=False)
    result = subprocess.run(
        [*LEAF_COMMAND, "hook", "--harness", "codex", "--if-claimed"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert result.returncode == 23, result.stderr
    assert json.loads(result.stdout) == {
        "argv": ["hook", "--harness", "codex", "--if-claimed"],
        "payload": payload,
        "host": None,
    }
    assert cleanup_model.session_record("selected-runtime") == before

    # A selection whose checkout is gone falls back to the Leaf running, which
    # refuses whatever page it can't read itself.
    selected.unlink()
    fallen_back = subprocess.run(
        [*LEAF_COMMAND, "hook", "--harness", "codex"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert fallen_back.returncode == 0, fallen_back.stderr
    assert "argv" not in fallen_back.stdout

    # A new generation returns to the installed default.
    cleanup_model.end_session("selected-runtime")
    cleanup_model.ensure_session("selected-runtime", {})
    value = cleanup_model.session_record("selected-runtime")
    assert value is not None
    assert "launcher" not in value


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
    """Outside a compaction, Leaf's start hook adds only a reconnect notice, which
    the prompt hook hands the same first turn, while Claude Code holds a resumed
    session's first reply until its start hooks end. After a compaction it tells
    the agent to read the leaf skill again (`hooks.reload_skill`) before it
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
            assert hook["timeout"] == hook_transport_model.HOOK_TIMEOUT_S, (
                harness,
                event,
            )
    # Pi's extension runs the hook itself and bounds it with its own copy.
    [timeout] = re.findall(
        r"const HOOK_TIMEOUT_MS = ([\d_]+);?$",
        (PLUGIN_ROOT / "hooks" / "pi.ts").read_text(),
        re.MULTILINE,
    )
    assert int(timeout.replace("_", "")) == hook_transport_model.HOOK_TIMEOUT_S * 1000


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
    unresolvable = run("{}", env=os.environ | {"PATH": str(tmp_path / "no-tools")})
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
        "-m",
        "leaf",
        *_registered_hook_arguments(harness, event),
    ]
    assert received.read_text() == payload
    assert not python_called.exists()


def test_codex_tool_hook_runs_leaf_only_for_a_session_that_claimed_a_page(
    page_dir, tmp_path
):
    """Codex runs its tool hook after every tool call of every task, and most hold
    no page, so the launcher asks the environment's interpreter first, and only for
    a session that has claimed one runs the whole hook in that interpreter. That
    interpreter starts uv only to sync its environment, the first time and after
    the lock changes, as an update to a checkout changes it. Every other Codex hook
    runs whole through uv, and so does the tool hook whose payload the question
    can't be read from: a failure there must not drop it."""
    project = tmp_path / "plugin"
    launcher = project / "bin/leaf"
    launcher.parent.mkdir(parents=True)
    launcher.write_bytes((PLUGIN_ROOT / "bin/leaf").read_bytes())
    launcher.chmod(0o755)
    program = project / "src/leaf/state.py"
    program.parent.mkdir(parents=True)
    program.write_bytes((PLUGIN_ROOT / "src/leaf/state.py").read_bytes())
    lock = project / "uv.lock"
    lock.write_text("version = 1\n")
    (project / "pyproject.toml").write_text("[project]\nname = 'leaf'\n")
    interpreter = project / ".venv/bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to(sys.executable)
    tools = tmp_path / "tools"
    tools.mkdir()
    # A stand-in uv records each command. It runs the gate's own hand-off as uv
    # would once synced, and takes in any other hook's payload.
    uv = tools / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" >> "$UV_CALLS"\n'
        'case "$*" in *"/state.py synced "*)\n'
        '    [ -n "$CHANGED_DURING_SYNC" ] && echo "# changed" >> "$CHANGED_DURING_SYNC"\n'
        '    while [ "$1" != python ]; do shift; done\n'
        '    shift; exec "$INTERPRETER" "$@";;\n'
        "esac\n"
        '/bin/cat > "$UV_CALLED"\n'
    )
    uv.chmod(0o755)
    uv_calls = tmp_path / "uv-calls"
    # A stand-in for the package records the hook the gate's interpreter runs.
    stand_in = tmp_path / "stand-in"
    (stand_in / "leaf").mkdir(parents=True)
    (stand_in / "leaf/__init__.py").write_text("")
    (stand_in / "leaf/__main__.py").write_text(
        "import json, os, sys\n"
        "def main():\n"
        "    ran = {'argv': sys.argv[1:], 'stdin': sys.stdin.read()}\n"
        "    with open(os.environ['LEAF_CALLED'], 'w') as record:\n"
        "        json.dump(ran, record)\n"
    )
    uv_called, leaf_called = tmp_path / "uv-called", tmp_path / "leaf-called"

    def run(event, session, payload=None, changed_during_sync=None):
        """What the hook asked uv for, a sync before the gate ran it again or a
        run of the whole hook, and where the hook ran: through uv, in the gate's
        interpreter, or nowhere. `changed_during_sync` is a file the stand-in uv
        appends to as it syncs."""
        uv_called.unlink(missing_ok=True)
        leaf_called.unlink(missing_ok=True)
        uv_calls.unlink(missing_ok=True)
        payload = payload or json.dumps(
            {"hook_event_name": event, "session_id": session}
        )
        done = subprocess.run(
            ["/bin/sh", "-c", _registered_hook_command("codex", event)],
            input=payload,
            env=os.environ
            | {
                "PLUGIN_ROOT": str(project),
                "PATH": f"{tools}:/usr/bin:/bin",
                "PYTHONPATH": str(stand_in),
                "UV_CALLED": str(uv_called),
                "UV_CALLS": str(uv_calls),
                "INTERPRETER": str(interpreter),
                "LEAF_CALLED": str(leaf_called),
                "CHANGED_DURING_SYNC": str(changed_during_sync or ""),
            },
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
        assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
        calls = uv_calls.read_text().splitlines() if uv_calls.exists() else []
        verbs = ["sync" if "/state.py synced " in call else "run" for call in calls]
        if uv_called.exists():
            return verbs, ("uv", uv_called.read_text())
        if leaf_called.exists():
            ran = json.loads(leaf_called.read_text())
            assert ran["argv"] == _registered_hook_arguments("codex", event)
            return verbs, ("in the gate", ran["stdin"])
        return verbs, None

    harness_2 = harness_model.session_harness()
    assert harness_2 is not None
    session = harness_2.session
    assert run("PostToolUse", session) == ([], None)
    stop = json.dumps({"hook_event_name": "Stop", "session_id": session})
    assert run("Stop", session) == (["run"], ("uv", stop))

    # Claiming a page marks the session for the rest of its generation.
    assert service_model.claim_page(page_dir)
    tool_use = json.dumps({"hook_event_name": "PostToolUse", "session_id": session})
    in_the_gate = ("in the gate", tool_use)
    assert run("PostToolUse", session) == (["sync"], in_the_gate)
    assert run("PostToolUse", session) == ([], in_the_gate)
    assert run("PostToolUse", "another-session") == ([], None)

    # An update that changes the lock syncs the environment before the next hook.
    lock.write_text("version = 1\nrevision = 2\n")
    assert run("PostToolUse", session) == (["sync"], in_the_gate)
    assert run("PostToolUse", session) == ([], in_the_gate)

    # A second update landing while uv syncs for the first leaves the record
    # behind both, so the next hook syncs again.
    lock.write_text("version = 1\nrevision = 3\n")
    synced_first = run("PostToolUse", session, changed_during_sync=lock)
    assert synced_first == (["sync"], in_the_gate)
    assert run("PostToolUse", session) == (["sync"], in_the_gate)
    assert run("PostToolUse", session) == ([], in_the_gate)

    # A payload the gate can't read runs the hook whole, which reports it.
    assert run("PostToolUse", session, "not json") == ([], ("in the gate", "not json"))


def test_a_hook_in_a_session_holding_no_page_imports_no_page_reading_or_server(
    page_dir,
):
    """A harness runs Leaf's hooks at every turn of every session the plugin is
    installed in, and most hold no page. Each waits on `import leaf.hooks`, so
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
        from leaf.codex_state import hook_turn
        observed = hook_turn("holds-nothing")
        assert observed["turn"] == turn_id
        assert observed["running"] == (event not in ("Stop", "Interrupt"))
"""
    _, imported = fresh_imports(program)
    assert unlisted_dependencies(imported, EVERY_TURN_DEPENDENCIES) == {}
    page_reading_or_serving = (
        "leaf.hosting",
        "leaf.http",
        "leaf.codex",
        "leaf.delivery",
        "leaf.thread",
        "leaf.hook_transport",
        "leaf.served_state.page",
        "leaf.event_contracts",
        "leaf.anchor_capture",
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
    _, imported = fresh_imports("import leaf.hook_transport\n")
    assert unlisted_dependencies(imported, EVERY_TURN_DEPENDENCIES) == {}


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
    source checks, the server or the file watcher."""
    published(claimed)
    hook = ["hook", "--harness", "claude-code"]
    payload = {"hook_event_name": process, "session_id": "s1", "prompt_id": "p1"}
    if process == "Stop":
        _, imported = fresh_imports(leaf_main(*hook, stdin=json.dumps(payload)))
        assert "leaf.served_state.context" in imported, "the hook read no page"
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
                "Checking.",
            )
        )
        assert asked["id"] in printed, printed
    assert unlisted_dependencies(imported, listed) == {}


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
    from leaf.hooks import cmd_hook
    from leaf.refusals import Refused

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
    with service_model.PageTransaction(page_dir) as page:
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
