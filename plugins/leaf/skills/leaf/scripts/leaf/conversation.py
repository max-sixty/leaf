"""CLI commands that write conversation and worker-report events."""

import json
import sys
from pathlib import Path

from leaf.asks import page_awaiting_values
from leaf.event_log import append_event
from leaf.events import thread_roots
from leaf.files import (
    latest_published,
    latest_revision,
    revision_path,
    version_revisions,
)
from leaf.host import message_identity
from leaf.passages import capture_anchor
from leaf.projection import (
    decisions,
    markup_facet,
    page_projection,
    rewritten_bodies,
)
from leaf.registry import require_registry
from leaf.revisioning import activate_source
from leaf.schema import MESSAGE_KINDS
from leaf.service import PageTransaction, contract_writer
from leaf.structure import parse_revision
from leaf.validation import (
    check_markup,
    read_text_arg,
    report_contract_error,
)


def _thread_root(events: list, to: str) -> tuple[str, dict | None]:
    messages = {
        event["id"]: event for event in events if event["kind"] in MESSAGE_KINDS
    }
    if to not in messages:
        sys.exit(f"unknown comment id {to!r}; known: {sorted(messages)}")
    root_id = thread_roots(events)[to]
    return root_id, messages.get(root_id)


def _version_response_unanswered(page_dir: Path, events: list, root: dict) -> bool:
    """Whether the page still owes this root the authored answer it asked for.

    Both readings below project markup alone: the empty event lists are the gate's
    subject rather than an omission. The reader's own pick lives in the log, and
    folding it in moved whichever side of the comparison it happened to fall on —
    before the proposal it answered the originating revision, after it the current
    one — so the same markup resolved or refused according to where one press
    landed in the log. A stamped version is what this thread asked for, so an
    unstamped live revision cannot settle it.
    """
    version = latest_published(page_dir, events)
    revision = version_revisions(events)[version]
    if revision <= root["revision"]:
        return True
    registry = require_registry(page_dir)
    html = revision_path(page_dir, revision).read_text(encoding="utf-8")
    projection, parser, spk = page_projection(html, [], registry, revision)
    awaiting = page_awaiting_values(html, parser, projection, spk, registry)
    target = root["anchor"]["section"]
    if awaiting.get(target, False):
        return True

    current = parser.by_id.get(target)
    if current is None:
        return True
    response = root["response"]
    current_entry = registry.get(current["tag"], {})
    if (current_entry.get("x-conversation") or {}).get("response") != response:
        return True

    original_revision = root["revision"]
    original_html = revision_path(page_dir, original_revision).read_text(
        encoding="utf-8"
    )
    original_projection, original, original_spk = page_projection(
        original_html, [], registry, original_revision
    )
    original_awaiting = page_awaiting_values(
        original_html,
        original,
        original_projection,
        original_spk,
        registry,
    )
    if original_awaiting.get(target, False):
        return False

    spec = current_entry["x-state"][response["verb"]]
    current_answer = markup_facet(target, spec, parser.by_id, spk, registry)
    original_answer = markup_facet(target, spec, original.by_id, original_spk, registry)
    return current_answer == original_answer


@contract_writer
def cmd_comment(
    page_dir: Path, quote: str, section: str, part: str, text, markup: str
) -> None:
    """Open a thread, as the user's own gestures do: on a passage where --quote or
    --section points at one, and on the page as a whole where neither does — the same
    anchorless shape the browser's general box posts, which is where a question about
    the work rather than a passage belongs. An anchor is captured against the active
    revision they are looking at and read as they see it: a slot
    their decision retired is off the page, and a draft they edited holds their words,
    so a quote is met here the way it would land there."""
    # Reading a body may wait on stdin; do that before taking the page lease.
    body = read_text_arg(text)
    with PageTransaction(page_dir) as page:
        events = page.events
        activate_source(page_dir, events)
        revision = latest_revision(page_dir)
        anchor = None
        if quote or section or part:
            html = revision_path(page_dir, revision).read_text(encoding="utf-8")
            registry = require_registry(page_dir)
            projection, _, _ = page_projection(html, events, registry, revision)
            decided = decisions(projection.actions, registry)
            edited = rewritten_bodies(projection.actions)
            try:
                anchor = capture_anchor(
                    html,
                    registry,
                    quote,
                    section,
                    decided,
                    edited,
                    part,
                )
            except ValueError as err:
                sys.exit(f"can't anchor in revision r{revision}: {err}")
        if markup:
            check_markup(page_dir, "comment", markup, events)
        event = {
            "kind": "comment",
            "author": "claude",
            **message_identity(),
            "revision": revision,
            "text": body,
        }
        if anchor:
            event["anchor"] = anchor
        if markup:
            event["markup"] = markup
        accepted = append_event(page, event)
    print(json.dumps(accepted, ensure_ascii=False))


@contract_writer
def cmd_reply(page_dir: Path, to: str, text, markup: str, awaits: bool = False) -> dict:
    """Post one complete threaded reply."""
    body = read_text_arg(text)
    with PageTransaction(page_dir) as page:
        events = page.events
        root_id, root = _thread_root(events, to)
        if root and (root.get("response") or {}).get("kind") == "version":
            sys.exit(
                f"thread {root_id!r} requires a page version and cannot take a reply; "
                "incorporate its request in the next version, or open a separate "
                "thread on the same Ask with `leaf comment --section <ask-id>` if "
                "you need an answer first"
            )
        fragment = check_markup(page_dir, "reply", markup, events) if markup else None
        if awaits and fragment:
            registry = require_registry(page_dir)
            structural = sorted(
                {
                    rec["tag"]
                    for rec in fragment.lf_elements
                    if (registry.get(rec["tag"]) or {}).get("x-awaits") is not None
                }
            )
            if structural:
                sys.exit(
                    "--awaits is for a prose question; reply markup already declares "
                    "whether its request is open through x-awaits "
                    f"({', '.join(f'<{tag}>' for tag in structural)})"
                )
        event = {
            "kind": "reply",
            "author": "claude",
            **message_identity(),
            "parent": to,
            "text": body,
        }
        if awaits:
            event["awaits"] = True
        if markup:
            event["markup"] = markup
        return append_event(page, event)


@contract_writer
def cmd_edit(page_dir: Path, to: str, text) -> dict:
    """Append a text revision to one message authored by this agent session.

    The message event is immutable: the edit points back to it, so the log retains
    every wording while thread folds project the latest one. Markup stays frozen with
    the original message because reader actions may already rest on widgets it sent.
    """
    body = read_text_arg(text)
    with PageTransaction(page_dir) as page:
        require_registry(page_dir)
        events = page.events
        target = next(
            (
                event
                for event in events
                if event["kind"] in {"comment", "reply"} and event["id"] == to
            ),
            None,
        )
        if target is None:
            known = sorted(
                event["id"] for event in events if event["kind"] in {"comment", "reply"}
            )
            sys.exit(f"unknown comment id {to!r}; known: {known}")
        if target["author"] != "claude":
            sys.exit(f"message {to!r} is not agent-authored")
        identity = message_identity()
        owner = target.get("session")
        if not owner:
            sys.exit(f"message {to!r} has no agent session identity")
        if owner != identity.get("session"):
            sys.exit(f"message {to!r} belongs to agent session {owner!r}")
        return append_event(
            page,
            {
                "kind": "edit",
                "author": "claude",
                **identity,
                "message": to,
                "text": body,
            },
        )


@contract_writer
def cmd_resolve(page_dir: Path, to: str) -> None:
    """Close a thread, as the reader's own ✓ Resolve does. Same event, same rule on
    `parent` — any message in the thread names it — and `author` the whole
    difference, which is how the panel can say who closed it."""
    with PageTransaction(page_dir) as page:
        events = page.events
        root_id, root = _thread_root(events, to)
        if (
            root
            and (root.get("response") or {}).get("kind") == "version"
            and _version_response_unanswered(page_dir, events, root)
        ):
            sys.exit(
                f"thread {root_id!r} requires a page version that answers its "
                "originating Ask, or changes its declared answer if it was already "
                "answered, before the agent can resolve it"
            )
        event = {
            "kind": "resolve",
            "author": "claude",
            **message_identity(),
            "parent": to,
        }
        accepted = append_event(page, event)
    print(json.dumps(accepted, ensure_ascii=False))


@contract_writer
def cmd_report(page_dir: Path, widget: str, verb: str, fields: tuple) -> None:
    """A worker's provisional news: a declared state change folded onto a page
    widget, validated at this door the way the POST door validates an action,
    stamped with the posting session's voice, and made against the active revision —
    the page the reader is looking at. The runtime paints it live; it stands until
    a stamped revision absorbs or overrules it by id (see `version stamp`), and the
    page's watcher wakes to fold it in. Field values
    are strings — the declared detail schemas for reports speak in attribute
    values, which is all a report may move."""
    detail = {}
    for field in fields:
        name, eq, value = field.partition("=")
        if not eq or not name:
            sys.exit(f"detail fields are name=value, got {field!r}")
        detail[name] = value
    with PageTransaction(page_dir) as page:
        events = page.events
        activate_source(page_dir, events)
        revision = latest_revision(page_dir)
        registry = require_registry(page_dir)
        event = {
            "kind": "report",
            "author": "claude",
            **message_identity(),
            "widget": widget,
            "action": verb,
            "detail": detail,
            "revision": revision,
        }
        if error := report_contract_error(
            event, parse_revision(page_dir, revision).by_id, registry
        ):
            sys.exit(error)
        accepted = append_event(page, event)
    print(json.dumps(accepted, ensure_ascii=False))
