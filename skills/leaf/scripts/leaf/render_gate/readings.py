"""Browser probe readings for one settled color scheme, the once-per-version width
sweep, the advice read from the desktop page and from the sweep, and the finding each
becomes."""

import json
import math
from dataclasses import dataclass
from itertools import pairwise

from leaf.passages import page_passages
from leaf.projection import (
    frozen_thread_reading,
    generated_children,
    page_reading,
    retirement_holders,
    retirement_outcomes,
    rewritten_bodies,
)
from leaf.registry.state import retirement_slots
from leaf.render_checks import evaluate_probe, wait_for_probe
from leaf.structure import SourceDocument

# A probe's arguments cross as JSON, so a node only CDP can name is handed to the
# `issueNode` probe as the receiver of a call made on the node itself.
_ISSUE_NODE = (
    "function () { return globalThis.__leafRenderDriver"
    ".call({name: 'issueNode', args: [this]}); }"
)


def _issue_fields(value, key=""):
    """Every scalar in an issue's details as (key, value), however deeply nested."""
    if isinstance(value, dict):
        for inner, item in value.items():
            yield from _issue_fields(item, inner)
    elif isinstance(value, list):
        for item in value:
            yield from _issue_fields(item, key)
    else:
        yield key, value


class DevtoolsIssues:
    """The issues Chrome raises in DevTools' Issues panel for one page.

    Chrome says some things only there and never in the console: a lazy image that
    holds no room, a blocked or mixed-content request, a deprecated API. The headless
    shell the suite runs raises Blink's issues but not the form issues Chrome's
    autofill layer adds, which is why `unnamedFormFields` reads that one itself.
    Listening starts before navigation; the reading is taken once the page settles,
    when the probe that locates a node has loaded."""

    def __init__(self, page):
        self._cdp = page.context.new_cdp_session(page)
        self._raised = []
        self._cdp.on(
            "Audits.issueAdded", lambda event: self._raised.append(event["issue"])
        )
        self._cdp.send("Audits.enable")

    def _node(self, backend_id: int) -> dict | None:
        from playwright.sync_api import Error as PlaywrightError

        try:
            node = self._cdp.send("DOM.resolveNode", {"backendNodeId": backend_id})
        except PlaywrightError:
            return None  # the node left the document after Chrome raised the issue
        answer = self._cdp.send(
            "Runtime.callFunctionOn",
            {
                "objectId": node["object"]["objectId"],
                "functionDeclaration": _ISSUE_NODE,
                "returnByValue": True,
            },
        )
        return answer["result"]["value"]

    def findings(self) -> list[str]:
        """Each issue about something the page owns, where it is and what it names.

        Details differ by issue type, so every scalar is written out except the
        protocol's handles, which name nothing a reader can find in the source; the
        first node handle is located instead."""
        found = []
        for issue in self._raised:
            fields = list(_issue_fields(issue["details"]))
            nodes = [v for k, v in fields if k == "nodeId" or k.endswith("NodeId")]
            facts = [f"{k}={v}" for k, v in fields if not k.endswith("Id") and v != ""]
            node = self._node(nodes[0]) if nodes else None
            if node is not None and not node["owned"]:
                continue
            found.append(
                f"DevTools issue {issue['code']}"
                + (f" at {node['at']}" if node else "")
                + (f" ({', '.join(facts)})" if facts else "")
            )
        return list(dict.fromkeys(found))


@dataclass(frozen=True, slots=True)
class _SchemeContext:
    page: object
    scheme: str
    errors: list
    resize_notices: list
    registry: dict
    declarations: dict
    state: dict
    markup: str
    here: int
    earlier: str | None
    replayed: bool
    unsettled: list
    devtools: DevtoolsIssues


def _projected_verbatim(document, registry, projection, authored_ids, source):
    """Read preserving owners after applying exactly the projection's text changes."""
    return page_passages(
        document,
        registry,
        decided=retirement_outcomes(projection.actions),
        rewrites=rewritten_bodies(projection.actions),
        additions=generated_children(projection.desired, authored_ids),
        source=source,
    ).verbatim


def _expected_verbatim(markup, events, registry, here):
    """Expected preserving-owner readings in the page and frozen thread.

    Page actions are bounded by the immutable revision being rendered. Frozen message
    markup has no later authored revision and therefore uses the thread's whole
    action window. Both use the same passage projection as comment capture.
    """
    document = SourceDocument(markup)
    page = page_reading(document, events, registry, here)
    expected = _projected_verbatim(
        document,
        registry,
        page.projection,
        page.document.ids,
        ("page", None),
    )
    thread = frozen_thread_reading(events, registry)
    for event in events:
        if fragment := event.get("markup"):
            expected.update(
                _projected_verbatim(
                    SourceDocument(fragment),
                    registry,
                    thread.projection,
                    thread.structure.ids,
                    ("event", event["id"]),
                )
            )
    return expected


def _verbatim_findings(context: _SchemeContext) -> list[str]:
    shown = evaluate_probe(context.page, "shownVerbatim", context.declarations)
    if not shown:
        return []
    expected = _expected_verbatim(
        context.markup,
        context.state["events"],
        context.registry,
        context.here,
    )
    findings = []
    for reading in shown:
        provenance = reading["provenance"]
        key = tuple(provenance) if provenance is not None else None
        if reading["compositional"] == expected.get(key):
            continue
        owner = f"<{reading['tag']}"
        if reading["id"]:
            owner += f" id={reading['id']!r}"
        owner += ">"
        if provenance is None:
            where = " without pre-upgrade source provenance"
        elif provenance[0] == "page":
            where = f" at page occurrence {provenance[2] + 1}"
        else:
            where = (
                f" at {provenance[0]} {provenance[1]} occurrence {provenance[2] + 1}"
            )
        findings.append(
            f"{owner}{where} declares x-verbatim but shows "
            f"{reading['says'][:80]!r} with owned structure "
            f"{reading['compositional']!r} where the file reads "
            f"{expected.get(key, [])!r}"
        )
    return findings


def _scheme_findings(context: _SchemeContext) -> tuple[list, list]:
    page = context.page
    scheme = context.scheme
    registry = context.registry
    declarations = context.declarations
    state = context.state
    markup = context.markup
    here = context.here
    earlier = context.earlier
    replayed = context.replayed
    errors = context.errors
    resize_notices = context.resize_notices
    unsettled = context.unsettled
    failsoft = evaluate_probe(page, "failSoftErrors")
    invalid_paints = evaluate_probe(page, "invalidPaints")
    missing_upgrades = evaluate_probe(page, "missingUpgrades", declarations)
    tiny = evaluate_probe(page, "tinyBoxes", declarations)
    unmarkable = evaluate_probe(page, "unmarkableElements")
    overflow = evaluate_probe(page, "rootOverflow")
    misplaced = evaluate_probe(page, "misplacedBoxes")
    withheld = evaluate_probe(page, "withheldRoom")
    stranded = evaluate_probe(page, "strandedMargins")
    silent_cuts = evaluate_probe(page, "silentCuts")
    squeezed = evaluate_probe(page, "squeezedTables")
    clipped = evaluate_probe(page, "clippedControls")
    unreachable = evaluate_probe(page, "unreachableWords")
    covered = evaluate_probe(page, "coveredWords")
    unread = evaluate_probe(page, "unreadSyntax")
    # Shadow roots the registry doesn't declare: the passage walk, the
    # capture and the id lookups cross exactly the declared ones, so an
    # undeclared root's words silently anchor quotes astray. Generated controls
    # are UI rather than page words, so their implementation roots are exempt.
    undeclared_shadow = evaluate_probe(page, "undeclaredShadowRoots", registry)
    unnamed_fields = (
        evaluate_probe(page, "unnamedFormFields") if scheme == "light" else []
    )
    # x-verbatim promises the words this scheme renders. Source provenance was
    # captured before upgrade, so anonymous page and frozen-message owners have the
    # same coordinate as the file reading without acquiring authored ids. Its file
    # side is the settled projection, so a page that never applied that projection is
    # already reported by the readiness wait and supplies no comparison.
    dishonest_verbatim = _verbatim_findings(context) if replayed else []
    # Replay is scheme-blind, so one scheme's reading covers both.
    conflicts = []
    silent = []
    missing_threads = []
    undeclared_attrs = []
    retired = []
    if scheme == "light":
        # x-thread-seat promises one page view per matching instance. A widget in
        # thread chrome already has the thread's reply surface and threadBox
        # deliberately returns none there. Everywhere else, ask the merged registry
        # for the instances and the module's own marker for the host it placed.
        missing_threads = evaluate_probe(page, "missingThreads", declarations)
        # Behind the caught-up wait above: a report moves a painted attribute and
        # the pass that speaks it runs before the stamp, so a reading taken any
        # earlier asks after a word the page has not been asked to say yet. A page
        # that never caught up is already reported there and read no further.
        if replayed:
            silent = evaluate_probe(page, "silentWords", declarations)
            # Behind the same wait, because reconciliation is one of the two
            # writers: a renderState states one declared fact whole, and a
            # record form is exactly the attribute it may state that fact in.
            undeclared_attrs = evaluate_probe(page, "undeclaredAttrs", declarations)
            # Behind it too: the settlement mark is replay's own write, so a
            # reading taken earlier asks after paint the page has not been
            # asked to make yet. The expected outcomes are the file's, scoped
            # to each holder's own relation: `retirement_outcomes` folds any verb that
            # retires somewhere in the vocabulary, so a verb of that name on
            # a family it settles nothing of decides nothing here — the
            # browser's write reads the per-holder relation, and a comparison
            # against anything wider would fail a page both sides are right
            # about.
            if slots := retirement_slots(registry):
                reading = page_reading(
                    SourceDocument(markup), state["events"], registry, here
                )
                outcomes = retirement_outcomes(reading.projection.actions)
                holders = []
                for h in retirement_holders(reading.document, registry):
                    declared = slots[h["tag"]]
                    outcome = outcomes.get(h["id"])
                    if outcome not in declared:
                        outcome = None
                    holders.append(
                        {
                            "tag": h["tag"],
                            "id": h["id"],
                            "outcome": outcome,
                            "slots": sorted(declared.get(outcome, ())),
                        }
                    )
                if holders:
                    retired = evaluate_probe(page, "retiredSlots", holders)
    # One scheme, the palettes carrying no geometry between them, and before the
    # medium moves: a box's inset is what it declared in either.
    #
    # The document's boxes, not the layer's over them. This is the only reading
    # here that reaches the runtime's own chrome, and it reaches it by accident:
    # inside `display: none` an element's own display is still `block` and its
    # padding and margins still resolve, so a shut panel answers with numbers that
    # look like the page's. They are not the panel's own. A size container query
    # does not match in there, so a rule switching a slot between two forms is
    # stuck on one of them, and a percentage margin comes back unresolved for
    # `px` to read as its bare number. Every box reading beside this one sees zero
    # and stops, which is the honest answer.
    #
    # And the finding would be one the author cannot act on. Everything in here is
    # somebody else's: the layer's own parts, told to them in the words of a class
    # no page of theirs has, and a widget an agent sent in a reply, frozen in an
    # append-only log and admitted at a door of its own. Either way the version
    # would stay refused with no edit that clears it, which is why the coarse
    # question — which document is this in — is the right one to ask here. That is the failure examples/AGENTS.md names as the
    # reason a gate reading was moved out once already. The layer's half is leaf's
    # own to hold, and the suite holds it with the panel open, where the styles are
    # the panel's and the margin is one somebody can see.
    trapped = (
        [t for t in evaluate_probe(page, "trappedMargins") if not t["chrome"]]
        if scheme == "light"
        else []
    )
    split = (
        [t for t in evaluate_probe(page, "splitEdges") if not t["chrome"]]
        if scheme == "light"
        else []
    )
    # Last, and in one scheme: paper has no color scheme, and the medium has to be
    # put back before anything else reads a box.
    on_paper = []
    if scheme == "light":
        screen = evaluate_probe(page, "paperWords")
        page.emulate_media(media="print")
        paper = evaluate_probe(page, "paperWords")
        # Paper is laid out by rules no other medium runs, and it is the medium
        # nobody looks at, so the readings that only paper can fail are taken here
        # while it holds: words drawn over each other, and room that prints nothing.
        on_paper = [f"[print] {c}" for c in evaluate_probe(page, "coveredWords")]
        on_paper += [f"[print] {v}" for v in evaluate_probe(page, "paperVoids")]
        page.emulate_media(media="screen")
        # Paired on the words as well as the position: the page is live, and a state
        # landing between the two readings would otherwise shift one against the
        # other and report whatever happened to line up. A pair that disagrees says
        # nothing, which is the right way round — the next run reads it again.
        on_paper += [
            f"[print] {s['at']} drops {json.dumps(s['text'])}, which it says on screen"
            for s, p in zip(screen, paper, strict=False)
            if s["text"] == p["text"] and s["shown"] and not p["shown"]
        ]
    # Last: these probes render temporary complete states. Compare carried actions
    # against the authored baseline, restore current state, then prove idempotence.
    # The caught-up wait ensures they observe the same settled projection as the
    # preceding read-only probes.
    relative = []
    if scheme == "light" and replayed:
        if earlier is not None:
            projection = page_reading(
                SourceDocument(markup), state["events"], registry, here
            ).projection
            carried = [
                event["id"]
                for event, _spec in projection.actions.values()
                if event["revision"] < here
            ]
            if carried:
                conflicts = evaluate_probe(
                    page,
                    "replayOverrides",
                    {
                        "curHtml": markup,
                        "prevHtml": earlier,
                        "carriedActions": carried,
                    },
                )
        relative = evaluate_probe(page, "relativeReplays")
    # The print reset and replay above can resize what an observer watches. Chrome
    # delivers that notice in the next rendering turn, so closing on the write
    # would call an attempt complete before its last error channel had spoken. Ask
    # synchronously and poll the presented-frame fact from the driver: a compositor
    # that never draws cannot strand page.evaluate on its unresolved Promise.
    requested_frame = evaluate_probe(page, "requestFrame")
    wait_for_probe(page, "framePresented", requested_frame)
    found = [f"[{scheme}] console: {e}" for e in errors]
    for failure in failsoft:
        owner = f"<{failure['tag']}" + (
            f" id={failure['id']!r}>" if failure["id"] else ">"
        )
        found.append(f"[{scheme}] {owner} failed soft: {failure['message']}")
    for paint in invalid_paints:
        owner = f"<{paint['tag']}" + (f" id={paint['id']!r}>" if paint["id"] else ">")
        part = f" for data-id={paint['part']!r}" if paint["part"] else ""
        found.append(
            f"[{scheme}] {owner} renders {paint['property']}={paint['value']!r} "
            f"on <{paint['element']}>{part}, but that value does not resolve to valid "
            f"{paint['property']}"
        )
    if missing_upgrades:
        found.append(
            f"[{scheme}] upgraded widgets did not define their elements: "
            + ", ".join(f"<{tag}>" for tag in missing_upgrades)
        )
    if tiny:
        found.append(
            f"[{scheme}] widgets rendered with no usable size: {json.dumps(tiny)}"
        )
    found += [
        f"[{scheme}] <{u['tag']} id={u['id']!r}> shows {u['w']}x{u['h']}px of words"
        " and offers no box to mark: it draws none of its own and no element inside"
        " it draws one either, so a comment anchored here would outline nothing and"
        " the Ask walk would travel to the top of the page. Put the words in an"
        " element that takes a box"
        for u in unmarkable
    ]
    found += [f"[{scheme}] {text}" for _key, text in _overflow(overflow, misplaced)]
    found += [f"[{scheme}] {w}" for w in withheld]
    found += [f"[{scheme}] {s}" for s in stranded]
    found += [f"[{scheme}] {c}" for c in silent_cuts]
    found += [f"[{scheme}] {s}" for s in squeezed]
    found += [
        f"[{scheme}] the control .{c['ctrl'].split()[0]}"
        + (f" (#{c['id']})" if c["id"] else "")
        + f" is drawn {c['lost']}px outside the {c['by']} that clips it, where"
        " nothing can scroll to reach it — the page offers a press it does not show"
        for c in clipped
    ]
    found += [f"[{scheme}] {w}" for w in unreachable]
    found += [f"[{scheme}] {c}" for c in covered]
    found += [f"[{scheme}] {u}" for u in unread]
    if undeclared_shadow:
        found.append(
            f"[{scheme}] shadow roots the registry doesn't declare "
            f"(an undeclared root's words anchor quotes astray; declare "
            f"x-shadow): {', '.join(undeclared_shadow)}"
        )
    for field in unnamed_fields:
        label = f" labelled {field['label']!r}" if field["label"] else ""
        class_name = f" class={field['className']!r}" if field["className"] else ""
        found.append(
            f"[{scheme}] <{field['tag']}{class_name}>{label} has neither an id nor "
            "a name, so Chrome cannot identify the form field"
        )
    found += [f"[{scheme}] {issue}" for issue in context.devtools.findings()]
    found += [f"[{scheme}] {d}" for d in dishonest_verbatim]
    found += [f"[{scheme}] {s}" for s in silent]
    for c in missing_threads:
        found.append(
            f"[{scheme}] <{c['tag']} id={c['id']!r}> declares x-thread-seat but "
            f"rendered {c['hosts']} matching hosts; its module must place exactly "
            "one threadBox"
        )
    for u in {(x["tag"], x["attr"]): x for x in undeclared_attrs}.values():
        found.append(
            f"[{scheme}] <{u['tag']} id={u['id']!r}> carries {u['attr']!r}, which "
            "its element declaration does not name — declare it as a verb's record "
            "form (x-state) if a version is meant to carry it, or write the state "
            "on the chrome the module built"
        )
    for t in {(x["tag"], x["edge"]): x for x in trapped}.values():
        box = f"<{t['tag']}" + (f" class={t['cls']!r}" if t["cls"] else "") + ">"
        path = t.get("through", [])
        remedy = (
            "Remove the edge margin that overrides the shared trim"
            if t["frameDeclared"]
            else "Declare --lf-block-frame: 1 in the rule that draws the frame"
        )
        found.append(
            f"[{scheme}] {box} draws {t['drawn']:g}px of inset and shows "
            f"{t['drawn'] + t['margin']:g}px {t['edge']} what it holds "
            f"(id={t['id']!r}): its {t['edge'] == 'above' and 'first' or 'last'} "
            f"block is a <{t['child']}> reserving {t['margin']:g}px against a "
            f"neighbour it hasn't got, and the box is where that margin stops. "
            f"{remedy}{' (' + ' > '.join(path) + ')' if path else ''}, so the trim "
            f"in theme.css reaches it"
        )

    for t in {(x["tag"], x["cls"], x["edge"]): x for x in split}.values():
        box = f"<{t['tag']}" + (f" class={t['cls']!r}" if t["cls"] else "") + ">"
        which = "first" if t["edge"] == "above" else "last"
        found.append(
            f"[{scheme}] {box} (id={t['id']!r}) lays its children out side by side "
            f"at a frame's edge, so the trim takes its {which} item's margin while "
            f"the {t['margin']:g}px beside it stays, and the row no longer lines up. "
            "Declare --lf-holds-edge: 1 on it, so the trim stops there"
        )

    found += [f"[{scheme}] {r}" for r in retired]
    found += [f"[{scheme}] {u}" for u in unsettled]
    found += [f"[{scheme}] {c}" for c in conflicts]
    found += [f"[{scheme}] {r}" for r in relative]
    found += on_paper
    notices = [f"[{scheme}] console: {e}" for e in resize_notices]
    return found, notices


def _overflow(overflow: int, misplaced: list) -> list[tuple[tuple[str, str], str]]:
    """The sideways readings at one width, each keyed by its element and kind."""
    found = []
    if overflow > 0:
        found.append(
            (
                ("<root scrollport>", "scroll"),
                f"the page scrolls sideways by {overflow}px",
            )
        )
    return found + [((m["at"], m["kind"]), m["text"]) for m in misplaced]


# The widths the sweep takes a loaded page through: a version holds at every width from
# the narrowest phone to the desktop viewport, and the fixed viewports read it at two. A
# grid that stacks at one width can leave its narrow track narrower than what it holds
# just above it, a band neither viewport lands in.
SWEEP_WIDTHS = range(360, 1201, 40)


def sweep(page, viewports) -> list[tuple[int, dict]]:
    """The loaded page's geometry at every sweep width, widest first.

    Resizes the loaded page rather than rendering it again, and reads only geometry:
    the rest of the gate reads words, paint and state, which the fixed viewports
    already see. The fixed widths are swept too. The sweep runs at the desktop height,
    so a fault only a phone-height workspace posture shows is the phone viewport's to
    report."""
    height = viewports[0]["height"]
    fixed = {viewport["width"] for viewport in viewports}
    readings = []
    # Widest first, in steps, so a layout script settles from the width before rather
    # than from the desktop: a jump from 1200px straight to 360px left an lf-shot laid
    # out for the desktop for a frame under load, and the sweep read that frame.
    for width in sorted({*SWEEP_WIDTHS, *fixed}, reverse=True):
        page.set_viewport_size({"width": width, "height": height})
        # One rendering turn for the resize to be heard, then the runtime's settled
        # reading, so what it set moving in script (an observer, the layout that
        # observer's write causes, and whatever that chains into) has run and been laid out.
        wait_for_probe(page, "framePresented", evaluate_probe(page, "requestFrame"))
        wait_for_probe(page, "renderingSettled")
        readings.append(
            (
                width,
                {
                    "overflow": evaluate_probe(page, "rootOverflow"),
                    "misplaced": evaluate_probe(page, "misplacedBoxes"),
                    "grids": evaluate_probe(page, "templateGrids"),
                },
            )
        )
    return readings


def swept_overflow(readings, viewports) -> list[str]:
    """Sideways overflow the fixed viewports miss, at the narrowest width it starts.

    A fault met at a fixed width is dropped here, because that viewport's own reading
    already reports it in both schemes."""
    fixed = {viewport["width"] for viewport in viewports}
    seen = {}
    for width, reading in readings:
        for key, text in _overflow(reading["overflow"], reading["misplaced"]):
            widths, _text = seen.setdefault(key, ([], text))
            widths.append(width)
    found = []
    for widths, text in seen.values():
        if fixed & set(widths):
            continue
        low, high = min(widths), max(widths)
        span = f"{low}px" if low == high else f"{low}–{high}px"
        found.append(f"at {span} wide, {text}")
    return found


# The window below which a template's stacking is no longer worth an author's attention.
# Every template stacks somewhere between a phone and the desktop, and a page that
# follows the wide-page guidance (`2fr 1fr` on a wide page stacks below 757px) would
# otherwise carry this advice by default. Above it the reader is at a desktop window
# they keep, a laptop's or half a large screen's, where the regions laid side by side
# arriving one under another is the layout they get, and a held workspace's panes turn
# into short boxes the page scrolls past. Over the shipped corpus the templates stack
# below 520–757px, except the triage board's `3fr 1fr`, which stacks below 1000px.
STACKING_WINDOW = 800


def stacking_advice(readings) -> list[str]:
    """Advice naming each track template that stacks in a desktop window.

    The module's rule gives the grid width its tracks need, exactly. What maps that onto
    a window is the page's geometry, which is piecewise: a wide page holds at its cap
    and then loses 0.92px of grid per pixel of window, a column page holds at 720px,
    and a nested grid gets its track's share of either. So one reading at 1200px cannot
    say where a grid stacks: taking a pixel of window for a pixel of grid put a
    `1fr 2.4fr` template at 882px on an available page and 906px on a wide one, where
    both stack below 854px. The sweep already lays the page out every 40px, so the
    window is interpolated between the sweep widths either side of the flip, at no
    layout of its own; that is exact wherever the geometry has no bend inside those
    40px, and otherwise off by less than them. A template already stacked at
    the widest reading stacks in every window, and says so."""
    by_grid = {}
    for width, reading in readings:
        for grid in reading["grids"]:
            by_grid.setdefault(grid["key"], []).append((width, grid))
    found = []
    for seen in by_grid.values():
        widest_width, widest = seen[0]
        name = widest["at"]
        tracks = (
            f'its columns="{widest["columns"]}" tracks need '
            f"{round(widest['need'])}px side by side"
        )
        if widest["stacked"]:
            found.append(
                f"{name} stands in one column at {widest_width}px wide: {tracks}, and "
                f"it has {round(widest['width'])}px. Give the narrowest track a larger "
                'share, or the grid more room (page-authoring.md, "A wide page")'
            )
            continue
        flip = next(
            (
                (high, above, low, below)
                for (high, above), (low, below) in pairwise(seen)
                if below["stacked"]
            ),
            None,
        )
        if flip is None:
            continue
        high, above, low, below = flip
        grown = above["width"] - below["width"]
        share = (below["need"] - below["width"]) / grown if grown > 0 else 1
        window = math.ceil(low + min(max(share, 0), 1) * (high - low))
        if window < STACKING_WINDOW:
            continue
        found.append(
            f"{name} stacks into one column in a window narrower than {window}px: "
            f"{tracks}, and it has {round(widest['width'])}px at {widest_width}px. "
            "Where a reader's window is narrower and the regions should stay side by "
            'side, give the narrowest track a larger share (page-authoring.md, "A wide '
            'page")'
        )
    return found


def margin_cover_advice(page) -> list[str]:
    """Advice naming each pin that stands over lines of the page's text."""
    width = page.viewport_size["width"]
    return [
        f"at {width}px wide the margin pin for {pin['at']} stands over "
        f"{pin['covered']} line(s) of text: a pin stands inside its block's "
        "top-right corner, so give the block padding on its right, or the page a rail "
        "(page-authoring.md, the rail and the margin), where those words matter"
        for pin in evaluate_probe(page, "coveringMargins")
    ]


# The drawn size below which a shrunk label is advised about. The theme's drawing idiom
# sets its labels at 10–12px in the viewBox's units (theme.css, `svg.drawing`; its 9px
# step glyph is one bold numeral on a dot), so an idiom drawing shown at its own width
# stays clear of it, and one shrunk by a fifth does not.
LEGIBLE_LABEL_PX = 10


def shrunk_label_advice(page) -> list[str]:
    """Advice naming each drawing whose fit to its box draws labels too small to read.

    Read at the desktop viewport, where the other advice is: a narrower window scales a
    drawing further still, and which of its widths a page answers for is not settled here.
    Advice rather than a failure because the remedy is a choice of composition — larger
    labels, fewer of them, a narrower drawing, more room — that only the author can make,
    and a page that makes none of them still says everything it says."""
    width = page.viewport_size["width"]
    return [
        f"at {width}px wide {d['at']} draws {d['labels']} label(s) below "
        f"{LEGIBLE_LABEL_PX}px, the smallest ({d['words']!r}) at {d['drawn']:g}px from "
        f"the {d['set']:g}px it was set at: the drawing is scaled to fit its box and its "
        "labels with it, so set them larger in the viewBox's units, draw the viewBox "
        "nearer the width it is shown at, or give it more room "
        "(authoring-evidence.md, Interactive and visual evidence)"
        for d in evaluate_probe(page, "shrunkLabels", LEGIBLE_LABEL_PX)
    ]


def alignment_advice(page) -> list[str]:
    """Advice when a page's grids split on more lines than any one of them needs."""
    reading = evaluate_probe(page, "misalignedSplits")
    if reading["unshared"] < 1:
        return []
    width = page.viewport_size["width"]
    named = ", ".join(
        f"{grid['at']} at {', '.join(f'{x}px' for x in grid['splits'])}"
        for grid in reading["grids"]
    )
    return [
        (
            f"at {width}px wide the page's grids split at {reading['unshared']} more "
            f"place(s) than its busiest grid needs — {named}: lay the page's regions on "
            'one set of tracks (page-authoring.md, "A wide page")'
        )
    ]
