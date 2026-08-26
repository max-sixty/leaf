"""CLI commands that write conversation and worker-report events."""

import json
import sys
from pathlib import Path

from leaf.events import append_event
from leaf.files import latest_published, version_path
from leaf.passages import capture_anchor
from leaf.projection import decisions, page_projection, rewritten_bodies
from leaf.registry import require_registry
from leaf.service import PageTransaction, contract_writer, message_identity
from leaf.structure import parse_version
from leaf.validation import (
    check_markup,
    read_text_arg,
    report_contract_error,
)


@contract_writer
def cmd_comment(
    page_dir: Path, quote: str, section: str, part: str, text, markup: str
) -> None:
    """Open a thread, as the user's own gestures do: on a passage where --quote or
    --section points at one, and on the page as a whole where neither does — the same
    anchorless shape the browser's general box posts, which is where a question about
    the work rather than a passage belongs. An anchor is captured against the version
    they are looking at — the newest published one, since a version no `note` has
    released is a passage nobody can be pointed at — and read as they see it: a slot
    their decision retired is off the page, and a draft they edited holds their words,
    so a quote is met here the way it would land there."""
    # Reading a body may wait on stdin; do that before taking the page lease.
    body = read_text_arg(text)
    with PageTransaction(page_dir) as page:
        events = page.events
        version = latest_published(page_dir, events)
        anchor = None
        if quote or section or part:
            html = version_path(page_dir, version).read_text(encoding="utf-8")
            registry = require_registry(page_dir)
            projection, _, _ = page_projection(html, events, registry, version)
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
                sys.exit(f"can't anchor in v{version}: {err}")
        if markup:
            check_markup(page_dir, "comment", markup, events)
        event = {
            "kind": "comment",
            "author": "claude",
            **message_identity(),
            "version": version,
            "text": body,
        }
        if anchor:
            event["anchor"] = anchor
        if markup:
            event["markup"] = markup
        accepted = append_event(page, event)
    print(json.dumps(accepted, ensure_ascii=False))


@contract_writer
def cmd_reply(page_dir: Path, to: str, text, markup: str) -> dict:
    """Post one complete threaded reply."""
    body = read_text_arg(text)
    with PageTransaction(page_dir) as page:
        events = page.events
        known = {e["id"] for e in events if e["kind"] in {"comment", "reply"}}
        if to not in known:
            sys.exit(f"unknown comment id {to!r}; known: {sorted(known)}")
        if markup:
            check_markup(page_dir, "reply", markup, events)
        event = {
            "kind": "reply",
            "author": "claude",
            **message_identity(),
            "parent": to,
            "text": body,
        }
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
        known = {e["id"] for e in events if e["kind"] in {"comment", "reply"}}
        if to not in known:
            sys.exit(f"unknown comment id {to!r}; known: {sorted(known)}")
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
    stamped with the posting session's voice, and made against the newest
    published version — the page the reader is looking at. The runtime paints it
    live; it stands until a version absorbs or overrules it by id (see
    `version publish`), and the page's watcher wakes to fold it in. Field values
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
        version = latest_published(page_dir, events)
        registry = require_registry(page_dir)
        event = {
            "kind": "report",
            "author": "claude",
            **message_identity(),
            "widget": widget,
            "action": verb,
            "detail": detail,
            "version": version,
        }
        if error := report_contract_error(
            event, parse_version(page_dir, version).by_id, registry
        ):
            sys.exit(error)
        accepted = append_event(page, event)
    print(json.dumps(accepted, ensure_ascii=False))
