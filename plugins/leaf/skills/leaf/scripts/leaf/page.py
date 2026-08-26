"""Vendored page guidance, vocabulary, and projected state."""

import json
import sys
from pathlib import Path

from .data import page_data_binding_inventory, read_data
from .events import (
    bare_reaction,
    build_threads,
    is_reaction,
    seats_with_agent,
    thread_digest,
)
from .files import list_versions, published_versions, version_path
from .http import presence
from .passages import page_passages
from .projection import (
    canonical_updates,
    decisions,
    page_asks,
    page_projection,
    record_lag_entries,
    thread_asks,
)
from .registry import described, require_registry
from .schema import GUIDANCE_DIR
from .service import PageTransaction, running_server, unacknowledged
from .structure import parse_version
from .validation import thread_state

CATALOG_PREAMBLE = """\
# Widget vocabulary, vendored for this page — `version check` validates against it.
#
# Widgets are lf-* elements in the authored HTML; attributes carry scalars
# (enums, flags), children carry prose, and an item's title is a leading
# <strong> child. Every lf-* element takes an explicit end tag — never
# <lf-foo/>. Ids are authored (lowercase kebab), unique, stable across
# versions. Each entry is JSON Schema over the attributes, plus the x- keys
# that say how the layer treats the tag — what each of those means is printed
# after the entries ($keys).
"""


# Familiar layer-wide facts get a sentence saying what an author reads them for.
# Package-defined `$` facts print afterward under their own names, so extending the
# vocabulary needs no catalog branch. `$events` and `$layer` stay absent: they are the
# runtime contract and vendoring record, not declarations an author writes markup from.
CATALOG_FACTS = (
    ("$keys", "The x- keys an entry may declare, and what each one means."),
    (
        "$restated",
        "`restated` — the one attribute that spans widgets; read it before revising one.",
    ),
    ("$state", "x-state's fields — the facet, fold unit, and record forms."),
    ("$report", "x-report's fields — how a version answers a standing report."),
    ("$awaits", "x-awaits' fields — when an instance asks, and what answers it."),
    (
        "$languages",
        "The languages this page colors, in a code block's class or an x-language attribute.",
    ),
    ("$tones", "The tones this page's layer paints, on any x-tone attribute."),
    (
        "$series",
        "The categorical steps a chart's series are painted in, and how many there are.",
    ),
    (
        "$reactions",
        (
            "The one-press reactions a reader can put on a passage, an element, a "
            "message, or the page — each `token`'s glyph, meaning, and effect."
        ),
    ),
    (
        "$idioms",
        "Theme idioms — shapes the theme styles directly; no registry entry, no JS.",
    ),
)
CATALOG_INTERNAL_FACTS = {"$events", "$layer"}


def page_guidance(page_dir: Path, registry: dict | None = None) -> dict[str, str]:
    """Compose package-wide, contract, and widget guidance by audience."""
    parts = {}
    directory = page_dir / GUIDANCE_DIR
    if directory.is_dir():
        for path in sorted(directory.iterdir()):
            text = path.read_text(encoding="utf-8").strip()
            if text:
                parts.setdefault(path.stem, []).append(text)
    registry = registry if registry is not None else require_registry(page_dir)
    for contract, declaration in sorted(
        registry.get("$data", {}).get("contracts", {}).items()
    ):
        for audience, text in sorted(declaration.get("guidance", {}).items()):
            parts.setdefault(audience, []).append(
                f"# Data contract `{contract}`\n\n{text.strip()}"
            )
    for tag, entry in sorted(registry.items()):
        if not tag.startswith("lf-"):
            continue
        for audience, text in sorted(entry.get("x-guidance", {}).items()):
            parts.setdefault(audience, []).append(
                f"# Widget `<{tag}>`\n\n{text.strip()}"
            )
    return {
        audience: "\n\n".join(sections).rstrip() + "\n"
        for audience, sections in sorted(parts.items())
    }


def cmd_guidance(page_dir: Path, audience: str | None) -> None:
    require_registry(page_dir)
    guides = page_guidance(page_dir)
    if audience is None:
        if guides:
            print("\n".join(guides))
        return
    if text := guides.get(audience):
        print(text, end="" if text.endswith("\n") else "\n")
        return
    available = ", ".join(guides) or "none"
    sys.exit(f"guidance audience {audience!r} is not available; available: {available}")


def cmd_catalog(page_dir: Path) -> None:
    reg = require_registry(page_dir)
    print(CATALOG_PREAMBLE)
    print(
        json.dumps(
            {k: v for k, v in reg.items() if not k.startswith("$")},
            indent=2,
            ensure_ascii=False,
        )
    )
    printed = set()
    for key, heading in CATALOG_FACTS:
        if fact := reg.get(key):
            print(f"\n# {heading}\n")
            print(json.dumps(fact, indent=2, ensure_ascii=False))
            printed.add(key)
    for key in sorted(set(reg) - printed - CATALOG_INTERNAL_FACTS):
        if key.startswith("$"):
            print(f"\n# {key}, declared by this layer.\n")
            print(json.dumps(reg[key], indent=2, ensure_ascii=False))
    guidance = page_guidance(page_dir, reg).get("author")
    if guidance and (text := guidance.strip()):
        print("\n# Guidance for authors\n")
        print(text)


def standing_entry(coordinate, e: dict, thread: str | None = None) -> dict:
    """One standing action, in the shape `page state` reports every one of them.

    `version` is the version the action was taken on, which for a widget an agent
    sent is a fact about the gesture and none about the widget: thread markup is
    frozen in the log, so no version bounds one of these and none can ever record
    it, which is why `lag` says nothing about them.
    """
    widget, unit, facet = coordinate
    return {
        "widget": widget,
        "unit": unit,
        "facet": facet,
        "action": e["action"],
        "detail": e["detail"],
        "version": e["version"],
        "seq": e["seq"],
        "thread": thread,
    }


def cmd_page_state(page_dir: Path) -> None:
    """Print the agent-side state from one transaction-consistent snapshot."""
    with PageTransaction(page_dir) as page:
        _write_page_state(page_dir, page.events)


def _write_page_state(page_dir: Path, events: list) -> None:
    """Where the page stands, as one JSON object — the agent-side twin of the
    browser's /api/state, folded rather than raw. /api/state ships the log and
    lets the runtime replay it; a session picking a page up owes the same
    reading, and doing it in-head over `leaf events` is how a standing decision
    gets missed. So this prints the readings the runtime derives, from the same
    constructions it derives them with: the published markup's elements, the
    projection of the user's standing state and the reports standing on the agent
    channel, where the record lags either (`record_lag_entries`), the open asks
    on the page and in threads (the banner's own count), each comment thread's
    exchange,
    and presence beside what answers for it. Computed on demand from the log,
    version, registry, and source store — no derived reading is stored, so there
    is no second copy of the truth to reconcile.

    Every markup-derived reading is of the latest *published* version, because
    that is the page the user sees and acts on; a written draft shows up in
    `versions.written` and nowhere else."""
    registry = require_registry(page_dir)
    published = published_versions(page_dir, events)
    written = list_versions(page_dir)
    pres = presence(page_dir, events)
    claims = pres.pop("claims")
    # The published page's readings, up front and through the one construction
    # (page_projection) every consumer of declared state reads, so the threads
    # settle against the same page the projection was built over rather than no page.
    parser, projection, spk = None, None, {}
    if published:
        html = version_path(page_dir, published[-1]).read_text(encoding="utf-8")
        projection, parser, spk = page_projection(html, events, registry, published[-1])
    threads = build_threads(events, spk)
    state = {
        "page": str(page_dir),
        "title": "",
        "versions": {"published": published, "written": written},
        **pres,
        # The watcher's number where `pending` is the reader's: everything a
        # wait would still print, workers' reports included.
        "unacked": len(unacknowledged(events, pres["cursor"])),
        "server": running_server(page_dir),
        "elements": [],
        "state": [],
        "updates": [],
        "data": read_data(page_dir),
        "data_bindings": page_data_binding_inventory(page_dir, registry, events),
        "asks": [],
        # Whole, through the same digest a delivery carries: a session picking
        # the page up is in the position this reading exists for, and a count of
        # messages it cannot read tells it a conversation happened without
        # letting it answer one.
        # A reaction nobody has replied to opened no conversation: it is
        # paint on the page, and stands under `reactions` below.
        "threads": [thread_digest(t) for t in threads.values() if not bare_reaction(t)],
        # Every reaction still standing — the agent-side reading of the marks
        # the page paints, each explained (`means`) off this page's vocabulary.
        # On the page (`anchor`, or none for the page whole) while its thread is
        # unresolved; in a thread (`parent`) while that thread is open.
        "reactions": [
            described(
                {
                    "id": m["id"],
                    "token": m["token"],
                    "anchor": m.get("anchor"),
                    "about": m.get("about"),
                    "parent": m.get("parent"),
                    "thread": root,
                    "version": m.get("version"),
                    "seq": m["seq"],
                },
                registry,
            )
            for root, t in threads.items()
            if not t["resolved"]
            for m in t["msgs"]
            if is_reaction(m)
        ],
        "lag": [],
    }
    if published:
        byid = parser.by_id
        state["title"] = parser.title.strip()
        state["elements"] = [
            {
                "tag": r["tag"],
                "id": r["attrs"].get("id"),
                "line": r["line"],
                "thread": None,
            }
            for r in parser.lf_elements
        ]
        state["state"] = [
            standing_entry(coordinate, e)
            for coordinate, (e, _) in projection.actions.items()
        ]
        # An ask standing in a slot the log has retired — a group inside the lf-new
        # of a rejected suggestion — left the page with the slot, so it is nobody's
        # to answer; the passage reading already knows which ids a decision dropped.
        passages = page_passages(
            html, registry, decisions(projection.actions, registry)
        )
        state["asks"] = page_asks(
            parser,
            projection,
            byid,
            spk,
            registry,
            set(passages.retired) | set(passages.gone),
            # A session picking the page up wants the reader's list, so a request
            # whose own seat conversation is with this agent is not on it: the next
            # word there is owed by the agent, and the stop hook says so.
            seats_with_agent(threads),
        )
        state["lag"] = record_lag_entries(projection, byid, spk, registry)
    elif written:
        state["title"] = parse_version(page_dir, written[-1]).title.strip()
    state["asks"] += thread_asks(
        events, registry, {rid for rid, t in threads.items() if t["resolved"]}
    )
    state["updates"] = canonical_updates(
        projection,
        claims,
        threads,
        events,
    )
    # The panel's own document, listed and projected the way the version's is, and
    # for the same reason: a widget an agent sent is a widget, and the reader
    # answering one is answering the page. The projection above is of the published
    # version's elements alone, so a press on an AskUserQuestion resolved no
    # declaration and stood nowhere — a session picking the page up read the reader's
    # answer to its own question as an answer nobody had given, with `asks` reporting
    # the same question answered.
    #
    # `thread` is the one key that separates them, present on every entry so a reader
    # of this can take the two halves the same way, and the elements come along so
    # nothing here names a widget the same object never lists. Both lists are then in
    # one order rather than two sorted halves.
    thread_actions, thread_byid, thread_of = thread_state(events, registry)
    state["elements"] += [
        {
            "tag": rec["tag"],
            "id": wid,
            "line": rec["line"],
            "thread": thread_of[wid],
        }
        for wid, rec in thread_byid.items()
    ]
    state["elements"].sort(key=lambda e: (e["thread"] or "", e["line"]))
    state["state"] += [
        standing_entry(coordinate, e, thread_of[coordinate[0]])
        for coordinate, (e, _) in thread_actions.actions.items()
    ]
    state["state"].sort(key=lambda s: (s["widget"], s["unit"], s["facet"]))
    print(json.dumps(state, indent=2, ensure_ascii=False))
