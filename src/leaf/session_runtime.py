"""The runtime a developer selects to own a session's delivery.

A user preview exercises a checkout that may know declarations the installed
plugin does not. Its session therefore uses that checkout's launcher for hooks and
the Codex delivery adapter, before either reads a page or changes a turn. Each hook
runs the checkout's Python as it stands; a running adapter keeps the modules it
loaded until it retires, which it does once its task owns no page, as when the
preview that claimed it stops. The selection lives in the session lifecycle record
and ends with its generation; ordinary plugin sessions have no selection. Page
servers retain their own runtime, so choosing delivery does not replace a
comparison arm's renderer.
"""

import os
from pathlib import Path

from .refusals import Refused
from .state import (
    PLUGIN_ROOT,
    flocked,
    session_lock_path,
    session_record,
    write_session,
)


def selected_launcher(session_id: str) -> Path | None:
    """Read a live generation's selection, refusing an unavailable runtime."""
    record = session_record(session_id)
    if record is None or record["ended"] is not None:
        return None
    value = record.get("launcher")
    if value is None:
        return None
    launcher = Path(value)
    if (
        not launcher.is_absolute()
        or not launcher.is_file()
        or not os.access(launcher, os.X_OK)
    ):
        raise Refused(
            f"this session's selected Leaf launcher is unavailable: {launcher}; "
            "restore that checkout or start a user preview from its replacement"
        )
    return launcher.resolve()


def select_launcher(session_id: str, launcher: Path) -> None:
    """Select delivery only after a preview has established its session lifetime."""
    launcher = launcher.resolve(strict=True)
    if not os.access(launcher, os.X_OK):
        raise Refused(f"the selected Leaf launcher is not executable: {launcher}")
    with flocked(session_lock_path(session_id)):
        record = session_record(session_id)
        if record is None or record["ended"] is not None:
            raise Refused(
                "a user preview must establish its session before selecting Leaf"
            )
        if record.get("launcher") != str(launcher):
            write_session({**record, "launcher": str(launcher)})


def own_launcher() -> Path:
    """The launcher beside the Python package currently running."""
    return (PLUGIN_ROOT / "bin" / "leaf").resolve()
