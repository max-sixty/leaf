"""Read recovery advice from the pages a session still intends to serve.

Session-start and prompt hooks repeat the advice while ownership or serving is down.
The reading does not reserve delivery or change page state. Stop, release,
persistent services, previews and another session's pages remain excluded.
A concurrent stop, transfer or recovery may make advice obsolete before it is read;
the agent may already have received advice before that change in either case.
"""

import shlex
from pathlib import Path

from .schema import EVENTS_FILE, PREVIEW_FILE
from .service import claim_is_active, claim_records, page_claim
from .state import session_record


def notices(
    harness: str | None, session_id: str, expected: dict | None
) -> list[str] | None:
    """Read reconnect advice, or None when this hook's lifecycle moved on."""
    from .server import read_service, running_server

    messages = []
    for retained in claim_records(session_id) if harness else []:
        page_dir = Path(retained["page"])
        claim = page_claim(page_dir)
        if (
            claim is None
            or (claim["harness"], claim["id"]) != (harness, session_id)
            or (page_dir / PREVIEW_FILE).exists()
            or not (page_dir / EVENTS_FILE).is_file()
        ):
            continue
        service = read_service(page_dir)
        if (
            service is None
            or not service["enabled"]
            or service["lifetime"] != "session"
            or (claim_is_active(claim) and running_server(page_dir) is not None)
        ):
            continue
        command = shlex.join(["leaf", "server", "start", str(page_dir)])
        messages.append(
            f"Your Leaf page needs reconnecting: {page_dir}. "
            "Restore its server and the delivery of updates with:\n"
            f"```sh\n{command}\n```"
        )
    return messages if session_record(session_id) == expected else None
