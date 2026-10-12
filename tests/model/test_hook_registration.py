"""Each harness's registration of Leaf's hooks: the harness each names, the time
each is given, and the launcher that runs a hook through uv."""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import LEAF_COMMAND
from interact_support import (
    COMPOSITE_TIMEOUT,
    PLUGIN_ROOT,
    STATED_TIMEOUT,
    append_carried_log_record,
    continued,
    record_claim,
    serving,
    wait_for,
)
from leaf import files as files_model
from leaf import harness as harness_model
from leaf import hook_transport as hook_transport_model
from leaf import leases as leases_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model

# Each harness's own registrations of Leaf's hooks (`harness.hook_harness`); Pi's
# are its extension's calls (`test_interact_pi.py`).
REGISTRATIONS = {"claude-code": "hooks.json", "codex": "codex.json"}


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


def _registered_watch_arguments():
    """What Claude Code's background Stop registration passes its supervisor."""
    [hook] = [
        hook
        for registration in _registrations("claude-code")["Stop"]
        for hook in registration["hooks"]
        if hook.get("asyncRewake")
    ]
    words = shlex.split(hook["command"])
    return words[words.index("hook") :]


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


def test_every_carrying_hook_has_time_to_confirm_what_it_hands_over():
    """A hook confirms an inline delivery only within CONFIRM_WITHIN of starting,
    which holds only while every harness whose hooks carry input gives its prompt
    and Stop hooks at least twice that: the rest covers uv's start, the imports,
    and the receipt after the clock stops."""
    floor = 2 * hook_transport_model.CONFIRM_WITHIN
    for harness in REGISTRATIONS:
        for event in ("UserPromptSubmit", "Stop"):
            [hook] = [
                hook
                for registration in _registrations(harness)[event]
                for hook in registration["hooks"]
                if not hook.get("asyncRewake")
            ]
            assert hook["timeout"] >= floor, (harness, event)
    # The modules that run the hook themselves bound it with their own copy.
    for module in ("pi.ts", "claude-code.ts"):
        [timeout] = re.findall(
            r"const HOOK_TIMEOUT_MS = ([\d_]+);?$",
            (PLUGIN_ROOT / "hooks" / module).read_text(),
            re.MULTILINE,
        )
        assert int(timeout.replace("_", "")) >= floor * 1000, module


def test_the_registered_watch_hook_wakes_the_session(claimed, tmp_path):
    """Claude Code's background Stop registration runs the watch, and its exit 2
    with stderr is the whole wake. Driven the way Claude Code drives it, through a
    shell with the payload on stdin, because the wiring (the watch supervisor, uv,
    the exit status it passes through) is the subject."""
    [hook] = [
        hook
        for entry in _registrations("claude-code")["Stop"]
        for hook in entry["hooks"]
        if hook.get("asyncRewake")
    ]
    env = os.environ | {"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT)}
    leases_model.mark_hooks("s1")  # its harness runs Leaf's hooks
    serving(claimed, 1)
    session_model.cmd_waiting(claimed, "")
    cleanup_model.close_session_turn("s1")
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )

    def run():
        return subprocess.run(
            ["sh", "-c", hook["command"]],
            input=json.dumps({"hook_event_name": "Stop", "session_id": "s1"}),
            env=env,
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )

    woke = run()
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
    env["CLAUDE_PLUGIN_ROOT"] = str(broken)
    failed = run()
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


def test_the_registered_hook_delivers_or_says_nothing(claimed):
    """The harness command calls Leaf's launcher, and Leaf answers under uv.

    Exercise the exact registration, stdin, environment selection and returned
    context; an unowned session has nothing to hand over.
    """

    def run(payload, env=None):
        return subprocess.run(
            ["/bin/sh", "-c", _registered_hook_command("claude-code", "Stop")],
            input=payload,
            env=(env or os.environ) | {"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT)},
            capture_output=True,
            text=True,
            timeout=COMPOSITE_TIMEOUT,
            check=False,
        )

    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )
    stop = json.dumps({"hook_event_name": "Stop", "session_id": "s1"})
    answered = run(stop)
    assert answered.returncode == 0, answered.stderr
    assert answered.stdout, "nothing came back: the CLI never answered under uv"
    [batch] = json.loads(continued(answered.stdout).split("\n")[1])["batches"]
    assert [event["text"] for event in batch["events"]] == ["hi"]

    # The library answers an unowned session silently under uv as well.
    stranger = run(json.dumps({"hook_event_name": "Stop", "session_id": "s2"}))
    assert (stranger.returncode, stranger.stdout, stranger.stderr) == (0, "", "")


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
    "harness,event,watch",
    [
        ("claude-code", "SessionStart", False),
        ("claude-code", "Stop", False),
        ("claude-code", "Stop", True),
        ("claude-code", "UserPromptSubmit", False),
        ("codex", "SessionStart", False),
        ("codex", "Stop", False),
        ("codex", "UserPromptSubmit", False),
        ("codex", "PostToolUse", False),
        ("codex", "Interrupt", False),
    ],
)
def test_the_registered_hook_leaves_library_execution_to_uv(
    harness, event, watch, tmp_path
):
    """Turn hooks need no system Python; the shell launcher owns uv.

    This plugin copy has no library, and system python3 refuses to run. A recording
    uv witnesses the selected project, application command and unchanged payload.
    Only the async watch needs a stdlib supervisor to translate its wake result.
    """
    project = tmp_path / "plugin"
    supervisor = project / "hooks/scripts/background-watch.py"
    supervisor.parent.mkdir(parents=True)
    supervisor.write_bytes(
        (PLUGIN_ROOT / "hooks/scripts/background-watch.py").read_bytes()
    )
    launcher = project / "bin/leaf"
    launcher.parent.mkdir()
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
        (
            [sys.executable, "-S", str(supervisor), *_registered_watch_arguments()]
            if watch
            else ["/bin/sh", "-c", _registered_hook_command(harness, event)]
        ),
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
        "hook",
        "--harness",
        harness,
        *(["--watch"] if watch else []),
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
    program = project / "skills/leaf/scripts/leaf/state.py"
    program.parent.mkdir(parents=True)
    program.write_bytes(
        (PLUGIN_ROOT / "skills/leaf/scripts/leaf/state.py").read_bytes()
    )
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

    session = harness_model.session_harness().session
    assert run("PostToolUse", session) is None
    assert run("Stop", session) == {"hook_event_name": "Stop", "session_id": session}

    # Claiming a page marks the session for the rest of its generation.
    assert service_model.claim_page(page_dir)
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


def test_the_registered_session_end_releases_shared_claims_without_an_environment(
    page_dir, tmp_path
):
    """A fresh install releases another checkout's claims within harness shutdown.

    Only the launcher and standalone stdlib cleanup exist in this install. No
    package can be imported and uv refuses to run; macOS's system Python 3.9
    exercises the same entry without site packages.
    """
    project = tmp_path / "cold-plugin"
    launcher = project / "bin/leaf"
    launcher.parent.mkdir(parents=True)
    launcher.write_bytes((PLUGIN_ROOT / "bin/leaf").read_bytes())
    launcher.chmod(0o755)
    program = project / "skills/leaf/scripts/leaf/state.py"
    program.parent.mkdir(parents=True)
    program.write_bytes(
        (PLUGIN_ROOT / "skills/leaf/scripts/leaf/state.py").read_bytes()
    )
    tools = tmp_path / "tools"
    tools.mkdir()
    system_python = Path("/usr/bin/python3")
    (tools / "python3").symlink_to(
        system_python if system_python.exists() else sys.executable
    )
    uv_called = tmp_path / "uv-called"
    uv = tools / "uv"
    uv.write_text('#!/bin/sh\nprintf called > "$UV_CALLED"\nexit 99\n')
    uv.chmod(0o755)

    record_claim(page_dir, id="ended-session")
    marker_files = [
        cleanup_model.session_file("ended-session", suffix)
        for suffix in (
            cleanup_model.HOOKS_SUFFIX,
            cleanup_model.STEP_HOOK_SUFFIX,
            cleanup_model.TITLES_SUFFIX,
        )
    ]
    for marker in marker_files:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("session evidence")
    claims = service_model.claim_path(page_dir).parent
    (claims / "malformed.json").write_text("{")
    (claims / "wrong-shape.json").write_text("[]")
    missing_page = tmp_path / "missing-page"
    missing_claim = {"id": "ended-session", "page": str(missing_page)}
    missing_path = service_model.claim_path(missing_page)
    cleanup_model.write_json(missing_path, missing_claim)
    foreign = page_dir.parent / "foreign-page"
    foreign.mkdir()
    (foreign / cleanup_model.EVENTS_FILE).touch()
    record_claim(foreign, id="another-session")
    foreign_claim = service_model.page_claim(foreign)

    done = subprocess.run(
        ["/bin/sh", "-c", _registered_hook_command("claude-code", "SessionEnd")],
        input=json.dumps(
            {"hook_event_name": "SessionEnd", "session_id": "ended-session"}
        ),
        env=os.environ
        | {
            "CLAUDE_PLUGIN_ROOT": str(project),
            "PATH": f"{tools}:/usr/bin:/bin",
            "UV_CALLED": str(uv_called),
        },
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    assert not uv_called.exists()
    assert not service_model.claim_is_active(service_model.page_claim(page_dir))
    assert not any(marker.exists() for marker in marker_files)
    assert service_model.page_claim(foreign) == foreign_claim
    assert files_model.read_json(missing_path) == missing_claim
    assert not missing_page.exists()

    # An empty shutdown needs neither a page nor a managed environment either.
    done = subprocess.run(
        ["/bin/sh", "-c", _registered_hook_command("claude-code", "SessionEnd")],
        input=json.dumps({"hook_event_name": "SessionEnd", "session_id": "empty"}),
        env=os.environ
        | {
            "CLAUDE_PLUGIN_ROOT": str(project),
            "PATH": f"{tools}:/usr/bin:/bin",
            "UV_CALLED": str(uv_called),
        },
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    assert not uv_called.exists()

    # The console and module entry use the same cleanup in a managed runtime.
    record_claim(page_dir, id="managed-session")
    done = subprocess.run(
        [*LEAF_COMMAND, "session-end"],
        input=json.dumps(
            {"hook_event_name": "SessionEnd", "session_id": "managed-session"}
        ),
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
    assert not service_model.claim_is_active(service_model.page_claim(page_dir))


def test_a_hook_in_a_session_holding_no_page_imports_no_page_reading_or_server(
    page_dir,
):
    """A harness runs Leaf's hooks at every turn of every session the plugin is
    installed in, and most hold no page. Each waits on `import leaf.hooks`, so
    that import, and a prompt or Stop hook in a session holding nothing, loads
    neither the page servers nor page reading: markup, registry schemas, and
    anchor capture. Run in a fresh interpreter, whose `sys.modules` is the hook's."""
    record_claim(page_dir, id="another-session")
    probe = """\
import io, json, runpy, sys
imported = [sorted(sys.modules)]
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
    runpy.run_module("leaf", run_name="__main__")
    if turn_id:
        from leaf.codex_state import hook_turn
        observed = hook_turn("holds-nothing")
        assert observed["turn"] == turn_id
        assert observed["running"] == (event not in ("Stop", "Interrupt"))
    imported.append(sorted(sys.modules))
print(json.dumps(imported))
"""
    done = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=True,
    )
    heavy = (
        "leaf.cli",
        "psutil",
        "click",
        "leaf.hosting",
        "uvicorn",
        "leaf.http",
        "leaf.codex",
        "leaf.delivery",
        "leaf.thread",
        "websockets",
        "leaf.hook_transport",
        "leaf.served_state.page",
        "leaf.event_contracts",
        "leaf.anchor_capture",
        "jsonschema",
        "markdown_it",
        "turbohtml",
    )
    for loaded in json.loads(done.stdout):
        assert [module for module in heavy if module in loaded] == []
