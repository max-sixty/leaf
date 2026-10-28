"""The Leaf that runs a harness session's delivery.

A harness session keeps running the plugin copy it loaded: Claude Code installs an
update into a new cache directory and leaves every running session on the old
one until `/reload-plugins` (`layer-registry.md`, "Page protocol"). A page a
newer Leaf re-vendored is then one the session's hooks and watch can't read, and
the user's input waits until someone reloads. So the session's hooks, its watch
and, from an installed copy, its bare `leaf` commands all hand themselves to one
launcher (`delivering_launcher`) before they read a page or change a turn; the
Codex delivery adapter follows the selection alone (`selected_launcher`):

- the launcher the session selected, while it exists: the checkout a user preview
  serves (`dev/leaf_dev/commands/preview.py`), or a checkout that re-vendored one
  of the session's pages (`vendoring._revendor`), whose protocol the session's own
  copy may not speak yet;
- otherwise, from a copy Claude Code installed, the copy it has installed since,
  which the marketplace sweep moves to each new commit;
- otherwise this one.

Each hook runs the chosen launcher's Python as it stands, so an update reaches a
session at its next hook without a reload; Claude Code still reads `hooks.json`
and the hooks module only as it loads the plugin, so a change to either still
waits for one. A selection whose checkout is gone falls back to the installed
copy, which refuses a page it can't read (`newer-layer`), so the agent learns why.
A running adapter keeps the modules it loaded until it retires, which it does once
its task owns no page. The selection lives in the session lifecycle record and
ends with its generation. Page servers retain their own runtime, so choosing
delivery does not replace a comparison arm's renderer.
"""

import json
import os
from pathlib import Path

from .refusals import Refused
from .state import (
    PLUGIN_ROOT,
    flocked,
    plugin_cache_copy,
    session_lock_path,
    session_record,
    write_session,
)


def delivering_launcher(session_id: str) -> Path:
    """The launcher that runs this session's delivery, as the module header
    ranks them."""
    return selected_launcher(session_id) or installed_launcher() or own_launcher()


def selected_launcher(session_id: str) -> Path | None:
    """A live generation's selection, where its launcher still runs."""
    record = session_record(session_id)
    if record is None or record["ended"] is not None:
        return None
    value = record.get("launcher")
    if value is None:
        return None
    launcher = Path(value)
    if launcher.is_absolute() and launcher.is_file() and os.access(launcher, os.X_OK):
        return launcher.resolve()
    return None


def installed_launcher() -> Path | None:
    """The launcher of the copy Claude Code has installed now, where this Leaf is
    one it installed: the `installPath` its `installed_plugins.json`, beside the
    cache, records for this plugin."""
    if not plugin_cache_copy(PLUGIN_ROOT):
        return None
    plugins = PLUGIN_ROOT.parents[3]
    name = f"{PLUGIN_ROOT.parent.name}@{PLUGIN_ROOT.parents[1].name}"
    try:
        record = json.loads((plugins / "installed_plugins.json").read_text())
        installs = record["plugins"][name]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    for install in installs:
        launcher = Path(install.get("installPath", "")) / "bin" / "leaf"
        if launcher.is_absolute() and os.access(launcher, os.X_OK):
            return launcher.resolve()
    return None


def select_launcher(session_id: str, launcher: Path) -> None:
    """Select `launcher` for the session's delivery, once a preview or a command
    has established its session lifetime."""
    launcher = launcher.resolve(strict=True)
    if not os.access(launcher, os.X_OK):
        raise Refused(f"the selected Leaf launcher is not executable: {launcher}")
    with flocked(session_lock_path(session_id)):
        record = session_record(session_id)
        if record is None or record["ended"] is not None:
            raise Refused("a session must be established before selecting its Leaf")
        if record.get("launcher") != str(launcher):
            write_session({**record, "launcher": str(launcher)})


def hand_off_command(argv: list[str]) -> None:
    """Run this `leaf` command under the session's delivering launcher, replacing
    this process, where this Leaf is a copy Claude Code installed and another
    launcher delivers for the session. A checkout's launcher is one someone chose
    to run, so it runs as it is; a hook hands itself off with its payload's
    session (`hooks.main`)."""
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


def select_checkout(session_id: str) -> None:
    """Select this Leaf for the session's delivery where it runs from a checkout
    and another Leaf delivers, as it re-vendors one of the session's pages past the
    copy the session loaded (`vendoring._revendor`). A hook runs the delivering
    Leaf already, so it selects nothing and leaves the lifecycle record its own
    readings compare against unchanged."""
    if (
        not plugin_cache_copy(PLUGIN_ROOT)
        and session_record(session_id) is not None
        and delivering_launcher(session_id) != own_launcher()
    ):
        select_launcher(session_id, own_launcher())


def own_launcher() -> Path:
    """The launcher beside the Python package currently running."""
    return (PLUGIN_ROOT / "bin" / "leaf").resolve()
