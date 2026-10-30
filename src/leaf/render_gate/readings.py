"""Browser probe readings for one settled color scheme, the once-per-version width
sweep, the advice read from the sweep and from the desktop page, and the finding each
becomes.

Presentation readings here refuse faults the page author can fix by editing the page.
A broken output contract also refuses the version, with its producing implementation
identified by data_contracts.output_findings. Qualitative package presentation advice
belongs in widget_quality; readings of Leaf's own chrome or theme belong in the suite,
which holds Leaf's half."""

import json
from dataclasses import dataclass
from itertools import pairwise

from leaf.findings import Finding, element_at
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
from leaf.render_checks import evaluate_probe, one_frame, rendered, wait_for_probe
from leaf.structure import SourceDocument

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
    when the probe that locates a node has loaded. Each is advice: an issue's code
    names Chrome's lint, and a request that actually fails also reaches the console
    as an error, which refuses the page."""

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
                    severity="advice",
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
    unmarkable = evaluate_probe(page, "unmarkableElements")
    missing_threads = []
    retired = []
    if context.light:
        # x-thread-seat promises one page view per matching instance. A widget in
        # thread chrome already has the thread's reply surface and threadBox
        # deliberately returns none there. Everywhere else, ask the merged registry
        # for the instances and the module's own marker for the host it placed.
        missing_threads = evaluate_probe(page, "missingThreads", context.declarations)
        # Behind the caught-up wait: the settlement mark is replay's own write, so a
        # reading taken earlier asks after paint the page has not been asked to make
        # yet. Before the widget readings, whose replay is the last.
        if context.replayed and (holders := _retired_holders(context)):
            retired = evaluate_probe(page, "retiredSlots", holders)
    found = [*context.errors, *_widget_findings(context)]
    found += map(Finding.read, unmarkable)
    found += context.devtools.findings()
    found += map(Finding.read, missing_threads)
    found += map(Finding.read, retired)
    found += context.unsettled
    if context.light:
        found += _unreduced_motion(page)
    return found


def _unreduced_motion(page) -> list[Finding]:
    """Advice naming page content that keeps animating once the reader asks for less
    motion, which Leaf leaves to the page (state.css). Read last, since setting the
    preference stops Leaf's own motion for the readings after it."""
    page.emulate_media(reduced_motion="reduce")
    one_frame(page)
    found = [
        Finding.read(m, severity="advice")
        for m in evaluate_probe(page, "unreducedMotion")
    ]
    page.emulate_media(reduced_motion="null")
    return found


def _widget_findings(context: _SchemeContext) -> list[Finding]:
    """The readings of what widgets render, wherever they are drawn: the page, and an
    open thread's messages (`thread_findings`)."""
    page = context.page
    declarations = context.declarations
    replayed = context.replayed
    invalid_paints = evaluate_probe(page, "invalidPaints")
    missing_upgrades = evaluate_probe(page, "missingUpgrades", declarations)
    tiny = evaluate_probe(page, "tinyBoxes", declarations)
    # Words a widget's own chrome holds with nothing saying whose they are.
    unreachable = evaluate_probe(page, "unreachableWords")
    # x-verbatim promises the words this scheme renders. Source provenance was
    # captured before upgrade, so anonymous page and frozen-message owners have the
    # same coordinate as the file reading without acquiring authored ids. Its file
    # side is the settled projection, so a page that never applied that projection is
    # already reported by the readiness wait and supplies no comparison.
    dishonest_verbatim = _verbatim_findings(context) if replayed else []
    # Replay is scheme-blind, so one scheme's reading covers both.
    silent = []
    undeclared_attrs = []
    relative = []
    # Behind the caught-up wait: a report moves a declared attribute, so a reading
    # taken any earlier asks after a word the page has not been asked to say yet. A
    # page that never caught up is already reported there and read no further.
    if context.light and replayed:
        silent = evaluate_probe(page, "silentWords", declarations)
        # Behind the same wait, because reconciliation is one of the two writers: a
        # widget's render states one declared fact whole, and a record form is
        # exactly the attribute it may state that fact in.
        undeclared_attrs = evaluate_probe(page, "undeclaredAttrs", declarations)
        # Last: render the complete state again to prove idempotence, against the
        # same settled projection the read-only probes before it observed.
        relative = evaluate_probe(page, "relativeReplays")
    # The replay above can resize what an observer watches. Chrome
    # delivers that notice in the next rendering turn, so closing on the write
    # would call an attempt complete before its last error channel had spoken.
    one_frame(page)
    found = list(map(Finding.read, invalid_paints))
    if missing_upgrades:
        found.append(Finding("missing-upgrades", values={"tags": missing_upgrades}))
    if tiny:
        found.append(Finding("tiny-boxes", values={"boxes": tiny}))
    found += map(Finding.read, unreachable)
    found += dishonest_verbatim
    found += map(Finding.read, silent)
    # One mistake is on every instance, so one finding per tag and attribute.
    found += {(u["tag"], u["attr"]): Finding.read(u) for u in undeclared_attrs}.values()
    found += map(Finding.read, relative)
    return found


def thread_findings(context: _SchemeContext, known: list[Finding]) -> list[Finding]:
    """The widget readings of each thread whose messages carry markup, read with that
    thread open, less what `known` already reports.

    A message's widgets render only where its thread is drawn, and the page draws one
    thread at a time: in its margin card, or in the floating panel's thread view where
    nothing on the page shows it. So each such thread is opened where a reader would
    find it, and the widget readings run again. The page's own widgets answer the same
    each time, so a finding is reported once. A page with no such thread pays one
    reading."""
    page = context.page
    found = dict.fromkeys(known)
    for thread in evaluate_probe(page, "threadsHoldingMarkup"):
        evaluate_probe(page, "openThreadToCheck", thread)
        wait_for_probe(page, "threadOpening", thread)
        answer = evaluate_probe(page, "threadOpening", thread)
        if not answer["shown"]:
            error = answer.get("error", "nothing drew it")
            failed = f"opening thread {thread} to read its widgets: {error}"
            found[Finding("gate-failed", values={"error": failed})] = None
        else:
            rendered(page)
            wait_for_probe(page, "pageSettled")
            found.update(dict.fromkeys(_widget_findings(context)))
    return [finding for finding in found if finding not in known]


def _keyed(records: list, severity: str = "error") -> dict[tuple[str, str], Finding]:
    """Width-dependent readings, such as overlay track collisions and clipped
    controls, each keyed by its element's place and kind. Covered words name the
    places of both elements as theirs."""
    return {
        (json.dumps(record["place"], sort_keys=True), record["code"]): Finding.read(
            record, severity=severity
        )
        for record in records
    }


def _overflow(overflow: int, misplaced: list) -> dict[tuple[str, str], Finding]:
    """The sideways readings at one width, each keyed by its element's place and kind."""
    found = {}
    if overflow > 0:
        found["<root scrollport>", "page-scrolls"] = Finding(
            "page-scrolls", values={"past": overflow}
        )
    return found | _keyed(misplaced)


# The widths the sweep takes a loaded page through: a version holds at every width from
# the narrowest phone to a wide desktop window, not only at the gate's fixed viewports. A
# grid that stacks at one width can leave its narrow track narrower than what it holds
# just above it, a band neither fixed viewport lands in, and the margin content
# arrives above the desktop viewport.
SWEEP_WIDTHS = range(360, 1921, 40)


def settle_at(page, width: int, height: int) -> None:
    """Resize the loaded page and stand it at its top, as a load at that size opens.

    A resize that reflows the page scrolls it, as the browser and the runtime keep the
    words in view where they were: the stacked workspace pages stood 169px down by
    360px, and rust-sort over 1000px down at 680px, with their sticky header over the
    words beneath it. So once the resize has settled the page jumps back to its top,
    without the smooth scrolling a page can ask for, which would still be on its way
    when the reading is taken."""
    page.set_viewport_size({"width": width, "height": height})
    # What the resize set moving in script (an observer, the layout that observer's
    # write causes, and whatever that chains into) has run and been laid out.
    rendered(page)
    if page.evaluate(
        "() => { const down = scrollY;"
        " scrollTo({ top: 0, left: 0, behavior: 'instant' }); return down; }"
    ):
        rendered(page)


def open_widgets(registry: dict) -> list[str]:
    """The widgets whose content is the page's own markup or members."""
    return [
        tag
        for tag, entry in registry.items()
        if is_element_name(tag) and entry.get("x-content") in ("markup", "members")
    ]


def sweep(page, widths, open_tags) -> list[tuple[int, dict]]:
    """The loaded page's geometry (`geometryReading`) at each of `widths`, in the order
    given, at the page's height.

    Resizes the loaded page rather than rendering it again. Callers walk in steps,
    widest first, so a layout script settles from the width before: a jump from
    the desktop's width straight to 360px left an lf-shot laid out for the desktop for a frame
    under load, and the sweep read that frame."""
    height = page.viewport_size["height"]
    readings = []
    for width in widths:
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


def swept_faults(samples) -> list[Finding]:
    """Sideways overflow, misplaced boxes and clipped content, scrollbar collisions,
    clipped controls and covered words across the gate's geometry samples, with the
    widths each run spans and what it reads at the narrowest. Each refuses the version,
    since a control cut off at 400px is as far out of reach as one cut off at 540px,
    except scrollbar clearance, a broken flow track chain and a declared breakout's
    containment, which are advice: the author decides how much clearance to leave and whether a holder
    should share the document's wider tracks.

    `samples` are (width, `geometryReading`) pairs, several at a width where the gate
    read it more than once (`version._render_version_attempt` says where). A fault any
    of them reads stands at that width, as the first of them to read it says, so a
    fault read at several is one run."""

    def faults(reading):
        return (
            _overflow(reading["overflow"], reading["misplaced"])
            | _keyed(reading["scrollbars"], severity="advice")
            | _keyed(reading["contained"], severity="advice")
            | _keyed(reading["clipped"])
            | _keyed(reading["covered"])
        )

    def at_any(readings):
        found = {}
        for reading in readings:
            found = faults(reading) | found
        return found

    by_width = {}
    for width, reading in samples:
        by_width.setdefault(width, []).append(reading)
    return _swept(sorted(by_width.items(), reverse=True), at_any)


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
    is a choice of composition only the author can make. Its words say what the reader
    keeps and what hiding a column at the narrow width would take: authors told only
    the remedies chased the advice for up to eight render checks, hiding columns at
    phone widths, which a phone reader then missed."""
    return _swept(
        readings,
        lambda reading: {
            (json.dumps(table["place"], sort_keys=True), table["code"]): Finding.read(
                table, severity="advice"
            )
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
            (json.dumps(d["place"], sort_keys=True), "shrunk-labels"): Finding(
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
