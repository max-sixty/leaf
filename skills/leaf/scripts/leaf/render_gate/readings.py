"""Browser probe readings for one settled color scheme, the once-per-version width
sweep, the advice read from the sweep and from the desktop page, and the finding each
becomes.

A reading refuses a version only for a fault its author can fix by editing the page.
A reading about Leaf's own chrome or theme, including one that would have to
recognize a Leaf control by its markup to judge it, belongs in the suite, which holds
Leaf's half."""

from dataclasses import dataclass
from itertools import pairwise

from leaf.passages import SourceReading, page_passages
from leaf.projection import (
    frozen_thread_reading,
    generated_children,
    page_reading,
    retirement_holders,
    retirement_outcomes,
    rewritten_bodies,
)
from leaf.registry.contract import is_element_name, retirement_slots
from leaf.render_checks import evaluate_probe, one_frame, rendered
from leaf.structure import SourceDocument

from .findings import Finding, element_at

# A probe's arguments cross as JSON, so a node only CDP can name is handed to the
# `issueNode` probe as the receiver of a call made on the node itself.
_ISSUE_NODE = (
    "function () { const view = (this.ownerDocument ?? this).defaultView;"
    " let driver; try { driver = view.top.__leafRenderDriver; }"
    " catch (error) { if (error.name === 'SecurityError') return null; throw error; }"
    " return driver.call({name: 'issueNode', args: [this]}); }"
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
        # Preserve the actual node for the ownership reading. Lifting a shadow
        # input to its iframe first would turn a control's issue into the page's.
        return self._call(node["object"], _ISSUE_NODE, by_value=True)["value"]

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

    def findings(self) -> list[Finding]:
        """Each issue about something the page owns, where it is and what it names.

        Details differ by issue type, so every scalar is kept except the protocol's
        handles, which name nothing a reader can find in the source; the first node
        handle is located instead."""
        found = []
        for issue in self._raised:
            fields = list(_issue_fields(issue["details"]))
            nodes = [v for k, v in fields if k == "nodeId" or k.endswith("NodeId")]
            details = [[k, v] for k, v in fields if not k.endswith("Id") and v != ""]
            node = self._node(nodes[0]) if nodes else None
            if node is not None and not node["owned"]:
                continue
            found.append(
                Finding(
                    "devtools-issue",
                    node["at"] if node else "",
                    {"issue": issue["code"], "details": details},
                )
            )
        return list(dict.fromkeys(found))


@dataclass(frozen=True, slots=True)
class _SchemeContext:
    page: object
    light: bool
    errors: list
    registry: dict
    declarations: dict
    state: dict
    markup: str
    here: int
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
    page = page_reading(SourceReading(SourceDocument(markup), registry), events, here)
    expected = _projected_verbatim(
        page.document,
        registry,
        page.projection,
        page.document.ids,
        ("page", None),
    )
    thread = frozen_thread_reading(events, registry)
    for event_id, fragment in thread.structure.fragments.items():
        expected.update(
            _projected_verbatim(
                fragment,
                registry,
                thread.projection,
                thread.structure.ids,
                ("event", event_id),
            )
        )
    return expected


def _verbatim_findings(context: _SchemeContext) -> list[Finding]:
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
        findings.append(
            Finding(
                "verbatim",
                element_at(reading["tag"], reading["id"]),
                {
                    "provenance": provenance,
                    "says": reading["says"],
                    "shown": reading["compositional"],
                    "expected": expected.get(key, []),
                },
            )
        )
    return findings


def _retired_holders(context: _SchemeContext) -> list[dict]:
    """Each settlement holder on the page with the outcome the file's reading gives it
    and the slots that outcome retires, for `retiredSlots` to hold the page to.

    The expected outcomes are the file's, scoped to each holder's own relation:
    `retirement_outcomes` folds any verb that retires somewhere in the vocabulary, so a
    verb of that name on a family it settles nothing of decides nothing here — the
    browser's write reads the per-holder relation, and a comparison against anything
    wider would fail a page both sides are right about."""
    slots = retirement_slots(context.registry)
    if not slots:
        return []
    reading = page_reading(
        SourceReading(SourceDocument(context.markup), context.registry),
        context.state["events"],
        context.here,
    )
    outcomes = retirement_outcomes(reading.projection.actions)
    holders = []
    for h in retirement_holders(reading.document, context.registry):
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
    return holders


def _scheme_findings(context: _SchemeContext) -> list[Finding]:
    """Every finding read from one settled scheme, without the scheme it was read in."""
    page = context.page
    declarations = context.declarations
    replayed = context.replayed
    invalid_paints = evaluate_probe(page, "invalidPaints")
    missing_upgrades = evaluate_probe(page, "missingUpgrades", declarations)
    tiny = evaluate_probe(page, "tinyBoxes", declarations)
    unmarkable = evaluate_probe(page, "unmarkableElements")
    column = evaluate_probe(page, "columnGeometry")
    scrollbars = evaluate_probe(page, "scrollbarClearance")
    reachability = evaluate_probe(page, "reachabilityReading")
    # Shadow roots the registry doesn't declare: the passage walk, the
    # capture and the id lookups cross exactly the declared ones, so an
    # undeclared root's words silently anchor quotes astray. Generated controls
    # are UI rather than page words, so their implementation roots are exempt.
    undeclared_shadow = evaluate_probe(page, "undeclaredShadowRoots", context.registry)
    # x-verbatim promises the words this scheme renders. Source provenance was
    # captured before upgrade, so anonymous page and frozen-message owners have the
    # same coordinate as the file reading without acquiring authored ids. Its file
    # side is the settled projection, so a page that never applied that projection is
    # already reported by the readiness wait and supplies no comparison.
    dishonest_verbatim = _verbatim_findings(context) if replayed else []
    # Replay is scheme-blind, so one scheme's reading covers both.
    silent = []
    missing_threads = []
    undeclared_attrs = []
    retired = []
    relative = []
    if context.light:
        # x-thread-seat promises one page view per matching instance. A widget in
        # thread chrome already has the thread's reply surface and threadBox
        # deliberately returns none there. Everywhere else, ask the merged registry
        # for the instances and the module's own marker for the host it placed.
        missing_threads = evaluate_probe(page, "missingThreads", declarations)
        # Behind the caught-up wait above: a report moves a declared attribute, so
        # a reading taken any earlier asks after a word the page has not been asked
        # to say yet. A page that never caught up is already reported there and
        # read no further.
        if replayed:
            silent = evaluate_probe(page, "silentWords", declarations)
            # Behind the same wait, because reconciliation is one of the two
            # writers: a renderState states one declared fact whole, and a
            # record form is exactly the attribute it may state that fact in.
            undeclared_attrs = evaluate_probe(page, "undeclaredAttrs", declarations)
            # Behind it too: the settlement mark is replay's own write, so a
            # reading taken earlier asks after paint the page has not been
            # asked to make yet.
            if holders := _retired_holders(context):
                retired = evaluate_probe(page, "retiredSlots", holders)
            # Last: render the complete state again to prove idempotence.
            # The caught-up wait ensures they observe the same settled projection as
            # the preceding read-only probes.
            relative = evaluate_probe(page, "relativeReplays")
    # The replay above can resize what an observer watches. Chrome
    # delivers that notice in the next rendering turn, so closing on the write
    # would call an attempt complete before its last error channel had spoken.
    one_frame(page)
    found = [*context.errors, *map(Finding.read, invalid_paints)]
    if missing_upgrades:
        found.append(Finding("missing-upgrades", values={"tags": missing_upgrades}))
    if tiny:
        found.append(Finding("tiny-boxes", values={"boxes": tiny}))
    found += map(Finding.read, unmarkable)
    found += _overflow(column["overflow"], column["misplaced"]).values()
    found += _scrollbars(scrollbars).values()
    for kind in ("clipped", "unreachable", "covered"):
        found += map(Finding.read, reachability[kind])
    if undeclared_shadow:
        found.append(Finding("undeclared-shadow", values={"hosts": undeclared_shadow}))
    found += context.devtools.findings()
    found += dishonest_verbatim
    found += map(Finding.read, silent)
    found += map(Finding.read, missing_threads)
    # One mistake is on every instance, so one finding per tag and attribute.
    found += {(u["tag"], u["attr"]): Finding.read(u) for u in undeclared_attrs}.values()
    found += map(Finding.read, retired)
    found += context.unsettled
    found += map(Finding.read, relative)
    return found


def _scrollbars(boxes: list) -> dict[tuple[str, str], Finding]:
    """Overlay track collisions, keyed like other width-dependent geometry."""
    return {(box["place"], box["code"]): Finding.read(box) for box in boxes}


def _overflow(overflow: int, misplaced: list) -> dict[tuple[str, str], Finding]:
    """The sideways readings at one width, each keyed by its element's place and kind."""
    found = {}
    if overflow > 0:
        found["<root scrollport>", "page-scrolls"] = Finding(
            "page-scrolls", values={"past": overflow}
        )
    return found | {(m["place"], m["code"]): Finding.read(m) for m in misplaced}


# The widths the sweep takes a loaded page through: a version holds at every width from
# the narrowest phone to a wide desktop window, and the fixed viewports read it at two. A
# grid that stacks at one width can leave its narrow track narrower than what it holds
# just above it, a band neither viewport lands in, and the margin's residents arrive
# above the desktop viewport.
SWEEP_WIDTHS = range(360, 1921, 40)


def settle_at(page, width: int, height: int) -> None:
    page.set_viewport_size({"width": width, "height": height})
    # What the resize set moving in script (an observer, the layout that observer's
    # write causes, and whatever that chains into) has run and been laid out.
    rendered(page)


def open_widgets(registry: dict) -> list[str]:
    """The widgets whose content is the page's own markup or members."""
    return [
        tag
        for tag, entry in registry.items()
        if is_element_name(tag) and entry.get("x-content") in ("markup", "members")
    ]


def sweep(page, viewports, open_tags) -> list[tuple[int, dict]]:
    """The loaded page's geometry at every sweep width, widest first.

    Resizes the loaded page rather than rendering it again, and reads only the
    geometry the functions below report across widths (`geometryReading`): the rest
    of the gate is read at the fixed viewports. The fixed widths are swept too. The
    sweep runs at the desktop height, so a fault only a phone-height workspace
    posture shows is the phone viewport's to report."""
    height = viewports[0]["height"]
    fixed = {viewport["width"] for viewport in viewports}
    readings = []
    # Widest first, in steps, so a layout script settles from the width before rather
    # than from the desktop: a jump from 1200px straight to 360px left an lf-shot laid
    # out for the desktop for a frame under load, and the sweep read that frame.
    for width in sorted({*SWEEP_WIDTHS, *fixed}, reverse=True):
        settle_at(page, width, height)
        readings.append((width, evaluate_probe(page, "geometryReading", open_tags)))
    return readings


def _swept(readings, faults) -> list[Finding]:
    """Each unbroken run of sweep steps a fault stands across, widest first, as the
    finding it reads at the narrowest of them with the widths the run spans.

    `faults` names each finding in one width's reading by a key, the element's place
    (locate.js) rather than its name, which two elements can share, and the finding's
    code. A fault that clears at some width and returns at a narrower one is two runs,
    each reported on its own. A window that narrows leaves less room for what the page
    holds, so a run's narrowest width is where its fault usually stands at its
    worst."""
    runs = []
    latest = {}
    for step, (width, reading) in enumerate(readings):
        for key, finding in faults(reading).items():
            last = latest.get(key)
            if last is not None and last[0] == step - 1:
                run = last[1]
                run[0].append(width)
                run[1] = finding
            else:
                run = [[width], finding]
                runs.append(run)
            latest[key] = (step, run)
    return [finding.but(widths=(min(widths), max(widths))) for widths, finding in runs]


def arrangement_changes(readings) -> list[tuple[int, str, str]]:
    """Where the page's own arrangement changes, widest first, at the sweep's steps.

    For each step across which a flex or grid box of the page's own splits its children
    into rows differently, the narrowest swept width at which the wider arrangement still
    holds, the first box that changes (a selector), and what changes below it
    (`<div id=regions> 1+2 → 1+1+1`). That is the arrangement at its tightest, the width an
    author most needs to see."""
    changes = []
    for (high, above), (_low, below) in pairwise(readings):
        wide = {box["path"]: box for box in above["arrangement"]}
        narrow = {box["path"]: box["rows"] for box in below["arrangement"]}
        moved = [path for path, box in wide.items() if narrow.get(path) != box["rows"]]
        if moved:
            said = "; ".join(
                f"{wide[path]['at']} {wide[path]['rows']} → "
                f"{narrow.get(path, 'unarranged')}"
                for path in moved
            )
            changes.append((high, moved[0], said))
    return changes


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
            settle_at(page, middle, height)
            if evaluate_probe(page, "marginResidents") == above:
                high = middle
            else:
                low = middle
        changes.append(high)
    return changes


def swept_overflow(readings, viewports) -> list[Finding]:
    """Sideways overflow and scrollbar collisions the fixed viewports miss, with
    the widths each run spans and what it reads at the narrowest.

    A run that takes in a fixed width is dropped here, because that viewport's own
    reading already reports it in both schemes."""
    fixed = {viewport["width"] for viewport in viewports}
    return [
        finding
        for finding in _swept(
            readings,
            lambda reading: (
                _overflow(reading["overflow"], reading["misplaced"])
                | _scrollbars(reading["scrollbars"])
            ),
        )
        if not any(finding.widths[0] <= width <= finding.widths[1] for width in fixed)
    ]


# The advice below is read from the sweep, at every swept width, since a narrower window
# can draw a page worse than either fixed viewport does. Each item names the widths it
# spans and what it reads at the narrowest. Which of those widths a page answers for is
# the author's call, so none of it refuses a version.


def squeezed_table_advice(readings) -> list[Finding]:
    """Advice naming each table that scrolls sideways with a cell wrapped.

    The sweep is the reading's only home, and it takes in the fixed viewports' widths.
    Advice rather than a failure because the table still scrolls and every word in it
    stays in reach: what costs the reader is prose wrapped a word a line beside a
    scroller, and the remedy (a column fewer, shorter words, an identifier in `<code>`)
    is a choice of composition only the author can make."""
    return _swept(
        readings,
        lambda reading: {
            (table["place"], table["code"]): Finding.read(table, severity="advice")
            for table in reading["squeezed"]
        },
    )


def shrunk_label_advice(readings) -> list[Finding]:
    """Advice naming each drawing whose fit to its box draws labels too small to read.

    Advice rather than a failure because the remedy is a choice of composition — larger
    labels, fewer of them, a narrower drawing, more room — that only the author can make,
    and a page that makes none of them still says everything it says."""

    def drawings(width, reading):
        threshold = reading["labels"]["threshold_px"]
        return {
            (d["place"], "shrunk-labels"): Finding(
                "shrunk-labels",
                d["at"],
                {
                    "place": d["place"],
                    "threshold": threshold,
                    "labels": d["labels"],
                    "width": width,
                    "words": d["words"],
                    "drawn": d["drawn"],
                    "set": d["set"],
                },
                severity="advice",
            )
            for d in reading["labels"]["drawings"]
        }

    # The reading names no width, so each step's findings carry their own.
    return _swept(
        [(width, (width, reading)) for width, reading in readings],
        lambda stepped: drawings(*stepped),
    )


def unreserved_height_advice(page, declarations: dict) -> list[Finding]:
    """Advice naming each widget whose module drew it at a height its first paint did
    not reserve (x-height), with the data-height that would have.

    Read at the desktop viewport the page first painted at, before the sweep resizes
    it: the reading compares each box with its first paint, and at another width a
    box's height moves with its reflow whatever its first paint reserved. Advice
    rather than a failure: the page reads the same once the drawing lands, and only
    the moment it lands moves what follows it."""
    return [
        Finding.read(reading, severity="advice")
        for reading in evaluate_probe(page, "unreservedHeights", declarations)
    ]
