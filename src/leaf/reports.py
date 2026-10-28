"""A worker's report: a declared state change an agent writes onto a page widget.

`leaf page report` appends one `report` event against the active revision, the page
the user is looking at, through the append door, which admits it as it admits a
user's action: the widget must be on that revision and the verb one of its
agent-written `x-state` verbs, with the fields that verb declares. The runtime paints
the report live, marked provisional, until a stamped revision absorbs or overrules it
by id (`publishing`), and the page's watcher wakes to fold it in. A report belongs to
no thread.
"""

from pathlib import Path

from leaf.event_contracts import append_admitted
from leaf.files import require_revision
from leaf.findings import Finding, Rejected
from leaf.leases import contract_writer
from leaf.service import PageTransaction


@contract_writer
def cmd_report(page_dir: Path, widget: str, verb: str, fields: tuple) -> dict:
    """Append a report of `verb` on `widget`, stamped with the posting session's
    voice. Each field is `name=value`; values are strings, since the declared detail
    schemas for reports speak in attribute values, which is all a report may move."""
    from leaf.revisioning import activate_source

    detail = {}
    for field in fields:
        name, eq, value = field.partition("=")
        if not eq or not name:
            raise Rejected([Finding("detail-field", values={"field": field})])
        detail[name] = value
    with PageTransaction(page_dir) as page:
        activate_source(page_dir, transaction=page)
        event = {
            "kind": "report",
            "author": "agent",
            "widget": widget,
            "action": verb,
            "detail": detail,
            "revision": require_revision(page_dir),
        }
        return append_admitted(page, event)[0]
