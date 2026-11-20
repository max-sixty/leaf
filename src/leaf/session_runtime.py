"""The Leaf that runs a harness session's delivery.

A harness session runs the plugin copy it loaded: Claude Code installs an update
into a new cache directory and leaves every running session on the old one until
`/reload-plugins`, and puts the loaded copy's `bin/` on its Bash tool's `PATH`. So
the session's hooks, its watch and its bare `leaf` commands run the Leaf whose
instructions and hooks module the session loaded, and an update reaches the
session when it reloads. The pages it holds stay readable meanwhile, since only the
session holding a page takes it to a newer page protocol (`vendoring.renew_layer`).
The user chose this over handing every session to the copy Claude Code installed
since, which ran code the session's instructions and hooks module didn't describe,
such as a flag its `SKILL.md` names that the newer Leaf dropped, and read Claude
Code's undocumented record of its installs to find that copy.

The session's hooks, its watch and, from an installed copy, its bare `leaf` commands
hand themselves on to a checkout the session selected (`delivering_launcher`) before
they read a page or change a turn: the checkout a user preview serves
(`dev/leaf_dev/commands/preview.py`), or a checkout whose command claimed one of the
session's pages or initialized one it holds (`select_checkout`), whose protocol the
session's copy may not speak yet. The Codex delivery adapter follows the selection
alone (`selected_launcher`).

Each hook runs the selected checkout's Python as it stands, so a change there
reaches the session at its next hook; Claude Code still reads `hooks.json` and the
hooks module only as it loads the plugin, so a change to either still waits for a
reload. Nothing checks that the module a session loaded and the Python a checkout
runs agree: the module only runs the instructions the Python gives it
(`carrier.py`), and one an older module doesn't know comes back failed, as a report
the Python refuses does, which hands a kept-back thread to the session at once;
where nothing reports, the line turn Leaf opened lapses after
`activity.STARTING_GRACE`. Either way the session gets the thread's messages as it
would without forks. The user chose this over checking that the loaded module is
the checkout's own, which turns forks off in every session that loaded the module
before the checkout's latest change. A selection whose checkout is gone falls back
to the session's own copy, which refuses a page it can't read (`newer-layer`), so
the agent learns why.
A running adapter keeps the modules it loaded until it retires, which it does once
its task owns no page. The selection lives in the session lifecycle record and
ends with its generation. Page servers retain their own runtime, so choosing
delivery does not replace a comparison arm's renderer.
"""

import os
from pathlib import Path

from .refusals import Refused
from .state import (
    PLUGIN_ROOT,
    flocked,
    plugin_cache_copy,
    session_live,
    session_lock_path,
    session_record,
    write_session,
)


def delivering_launcher(session_id: str) -> Path:
    """The launcher that runs this session's delivery: the one it selected, while
    it exists, else this one."""
    return selected_launcher(session_id) or own_launcher()


def selected_launcher(session_id: str) -> Path | None:
    """A live generation's selection, where its launcher still runs."""
    record = session_record(session_id)
    if not session_live(record):
        return None
    value = record.get("launcher")
    if value is not None and os.access(value, os.X_OK):
        return Path(value).resolve()
    return None


def select_launcher(session_id: str, launcher: Path) -> bool:
    """Select `launcher` for the session's delivery, once a preview or a command
    has established its session lifetime, and say whether the selection changed."""
    launcher = launcher.resolve(strict=True)
    if not os.access(launcher, os.X_OK):
        raise Refused(f"the selected Leaf launcher is not executable: {launcher}")
    with flocked(session_lock_path(session_id)):
        record = session_record(session_id)
        if not session_live(record):
            raise Refused("a session must be established before selecting its Leaf")
        if record.get("launcher") == str(launcher):
            return False
        write_session({**record, "launcher": str(launcher)})
        return True


def hand_off_command(argv: list[str]) -> None:
    """Run this `leaf` command under the checkout the session selected, replacing
    this process, where this Leaf is a copy Claude Code installed. A checkout's
    launcher is one someone chose to run, so it runs as it is; a hook hands itself
    off with its payload's session (`hooks.main`)."""
    if not plugin_cache_copy(PLUGIN_ROOT) or argv[:1] == ["hook"]:
        return
    from .harness import session_harness

    try:
        harness = session_harness()
    except Refused:
        harness = None
    launcher = delivering_launcher(harness.session if harness else "")
    if launcher == own_launcher():
        return
    environment = dict(os.environ)
    environment.pop("LEAF_HOST_LAUNCHER", None)
    os.execve(launcher, [str(launcher), *argv], environment)


def select_checkout(session_id: str) -> bool:
    """Select this Leaf for the session's delivery where it runs from a checkout,
    and say whether the selection changed. Its callers call it only for a page the
    established session takes or holds: a command that claims one (`server start`,
    `server run`, `page claim`), and an init or renewal of a held page
    (`vendoring._deliver_from_here`). The copy the session loaded may not read the
    page at this protocol, and a checkout can't tell which copy the session's hooks
    run, so it selects itself for each such page.

    A claim selects before it prepares delivery: a Codex task's adapter starts from
    the selected Leaf (`codex_adapter.preparing_adapter`), and one running from
    another Leaf leaves once this one is selected, so preparing first would join the
    adapter about to leave. Only a command selects: a hook runs the delivering Leaf
    already, and a write to the lifecycle record would change the snapshot its own
    readings compare against."""
    return not plugin_cache_copy(PLUGIN_ROOT) and select_launcher(
        session_id, own_launcher()
    )


def own_launcher() -> Path:
    """The launcher beside the Python package currently running."""
    return (PLUGIN_ROOT / "bin" / "leaf").resolve()
