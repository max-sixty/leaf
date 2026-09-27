"""Browser probe readings for one settled color scheme, the once-per-version width
sweep, the advice read from the desktop page and from the sweep, and the finding each
becomes.

A reading refuses a version only for a fault its author can fix by editing the page.
A reading about Leaf's own chrome or theme, including one that would have to
recognize a Leaf control by its markup to judge it, belongs in the suite, which holds
Leaf's half."""

import json
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
from leaf.render_checks import evaluate_probe, one_frame, rendered
from leaf.structure import SourceDocument

# A probe's arguments cross as JSON, so a node only CDP can name is handed to the
# `issueNode` probe as the receiver of a call made on the node itself.
_ISSUE_NODE = (
    "function () { return globalThis.__leafRenderDriver"
    ".call({name: 'issueNode', args: [this]}); }"
)
# A node in a child frame is that frame's to show, and the frame is the page's, so the
# issue is placed at the frame element in the page's own document, where the probes
# run. A cross-origin frame withholds that element, and the issue goes unplaced.
_IN_PAGE = (
    "function () { let node = this; const view = (n) => (n.ownerDocument ?? n)"
    ".defaultView; while (node && view(node) !== top) node = view(node).frameElement;"
    " return node; }"
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
    holds no room, a blocked or mixed-content request, a deprecated API, a form field
    autofill cannot identify. The headless shell the suite runs raises Blink's issues
    but not the autofill layer's.
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
        in_page = self._call(node["object"], _IN_PAGE, by_value=False)
        if in_page.get("subtype") == "null":
            return None
        # The frame element came back as the child frame's object. Resolving it again
        # by id answers in its own document's context, where the probes are loaded.
        described = self._cdp.send(
            "DOM.describeNode", {"objectId": in_page["objectId"]}
        )
        page_node = self._cdp.send(
            "DOM.resolveNode", {"backendNodeId": described["node"]["backendNodeId"]}
        )
        return self._call(page_node["object"], _ISSUE_NODE, by_value=True)["value"]

    def _call(self, receiver: dict, function: str, *, by_value: bool) -> dict:
        answer = self._cdp.send(
            "Runtime.callFunctionOn",
            {
                "objectId": receiver["objectId"],
                "functionDeclaration": function,
                "returnByValue": by_value,
            },
        )
        if "exceptionDetails" in answer:
            raise RuntimeError(
                "locating a DevTools issue's node failed: "
                + answer["exceptionDetails"]["exception"]["description"]
            )
        return answer["result"]

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
    stranded = evaluate_probe(page, "strandedMargins")
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
    # The replay above can resize what an observer watches. Chrome
    # delivers that notice in the next rendering turn, so closing on the write
    # would call an attempt complete before its last error channel had spoken.
    one_frame(page)
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
    found += [f"[{scheme}] {s}" for s in stranded]
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
    found += [f"[{scheme}] {r}" for r in retired]
    found += [f"[{scheme}] {u}" for u in unsettled]
    found += [f"[{scheme}] {c}" for c in conflicts]
    found += [f"[{scheme}] {r}" for r in relative]
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
# the narrowest phone to a wide desktop window, and the fixed viewports read it at two. A
# grid that stacks at one width can leave its narrow track narrower than what it holds
# just above it, a band neither viewport lands in, and the margin's residents arrive
# above the desktop viewport.
SWEEP_WIDTHS = range(360, 1921, 40)

# What of the page's own stands in its margin: the tokens the margin pass writes on
# `main` (margin-layout.js, `settleResidency`), less the rail, which holds only Leaf's
# markers and never moves the column.
MARGIN_READING = (
    "(document.querySelector('main')?.getAttribute('data-lf-margin') ?? '')"
    ".split(' ').filter(t => t && t !== 'rail').join(' ')"
)


def _settle_at(page, width: int, height: int) -> None:
    page.set_viewport_size({"width": width, "height": height})
    # What the resize set moving in script (an observer, the layout that observer's
    # write causes, and whatever that chains into) has run and been laid out.
    rendered(page)


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
        _settle_at(page, width, height)
        readings.append(
            (
                width,
                {
                    "overflow": evaluate_probe(page, "rootOverflow"),
                    "misplaced": evaluate_probe(page, "misplacedBoxes"),
                    "margin": page.evaluate(MARGIN_READING),
                },
            )
        )
    return readings


def margin_changes(page, readings, height: int) -> list[int]:
    """The widths at which the page's margin content changes, narrowest first.

    For each sweep step across which what stands in the margin differs, the narrowest
    width at which the wider reading holds, found by halving the step on the loaded
    page. That is where each resident first stands in the margin, with the least room it
    will ever have there, so the gate renders the page at each."""
    stepped = sorted((width, reading["margin"]) for width, reading in readings)
    changes = []
    for (low, below), (high, above) in pairwise(stepped):
        if below == above:
            continue
        while high - low > 1:
            middle = (low + high) // 2
            _settle_at(page, middle, height)
            if page.evaluate(MARGIN_READING) == above:
                high = middle
            else:
                low = middle
        changes.append(high)
    return changes


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
