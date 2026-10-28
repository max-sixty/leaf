"""A finding: one thing a check found, or a command says, as a record its readers take
fields from.

Every check behind `page check` and `package check` reports through this one type: the
registry's validation, the markup checks, a sample's initial history, the capture of a
revision, the page-code run, the render gate in each color scheme and viewport, its
width sweep and advice, and the widget quality report. The suite's browser fixture
reports through it too: what the browser said, and what its health sensors
(`tests/*_watch.js`) found. So does every gate that refuses one event at the append
door (`event_contracts.admitted_event`). A refusal raised with what a check found
(`Rejected`, such as `RegistryError`, `ArtifactError` or `event_log.EventRefused`)
carries the records, so a command that reports it reads them from it. So does every
note a command gives beside its result, such as why a `leaf wait` ended. Each is
produced where it is detected, the browser probes and sensors included, which return
records rather than sentences, and its words are written here and nowhere else. A
command prints `finding.json()`, its words as `text`, in its result or as a note on
stderr (`note`), as the event door's refusal answer carries it, and a failing test
prints the words; every
other reader, the gate's retry policy and the suite among them, reads the fields.

- `code` names what was found, and decides the words (`_TEXT`).
- `at` names the element it concerns as `render-checks/locate.js` does (`<div id=x>`,
  or `<p> in <section id=x>` where the element has no id of its own), or is empty.
- `values` are what the check measured, as JSON.
- `severity` is `error`, which refuses the page, or `advice`, which leaves the call to
  its author.
- `scheme`, `viewports` and `widths` say where it was read: one color scheme, or none
  where the reading is scheme-blind; the fixed viewports it was read at, empty where it
  holds at every one; the swept widths a run spans, lowest and highest.
- `samples` says which document a markup check read: the page's own, where it is
  empty, or the live sample child these template ids name, outermost first (None for
  a template without one).

A markup finding names its element by the tag the author reads in the file, with its
id where the words name one, and keeps the line it opens on in `values`. A registry
finding names the element declaration it concerns in `at`, and keeps the file or
composition it was read in as `values.registry`.

A record compares by all of these, so two readings of one fault in one place are one
finding and the same fault at another width is another.
"""

import json
import sys
from dataclasses import dataclass, field, replace

from leaf.refusals import Refused

SEVERITIES = ("error", "advice")


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    at: str = ""
    values: dict = field(default_factory=dict)
    severity: str = "error"
    scheme: str | None = None
    viewports: tuple[str, ...] = ()
    widths: tuple[int, int] | None = None
    samples: tuple[str | None, ...] = ()

    def __post_init__(self):
        if self.code not in _TEXT:
            raise ValueError(f"no words for finding code {self.code!r}")
        if self.severity not in SEVERITIES:
            raise ValueError(f"unknown severity {self.severity!r}")

    def __hash__(self) -> int:
        return hash(json.dumps(self.json(text=False), sort_keys=True))

    def __str__(self) -> str:
        text = _words(self)
        if self.code in _CONSOLE and self.scheme is not None:
            text = f"console: {text}"
        if self.widths is not None:
            low, high = self.widths
            span = f"{low}px" if low == high else f"{low}–{high}px"
            text = f"at {span} wide, {text}"
        if self.scheme is not None:
            text = f"[{self.scheme}] {text}"
        if self.viewports:
            text = f"{text} (at {', '.join(self.viewports)})"
        return "".join(f"sample {s or '<unnamed>'!r}: " for s in self.samples) + text

    @classmethod
    def read(cls, record: dict, **where) -> "Finding":
        """The finding a browser probe returned as `{code, at, ...values}`."""
        values = dict(record)
        return cls(values.pop("code"), values.pop("at", ""), values, **where)

    @classmethod
    def loads(cls, found: dict) -> "Finding":
        """The finding `json` wrote."""
        return cls(
            found["code"],
            found.get("at", ""),
            found.get("values", {}),
            found["severity"],
            found.get("scheme"),
            tuple(found.get("viewports", ())),
            tuple(found["widths"]) if "widths" in found else None,
            tuple(found.get("samples", ())),
        )

    def json(self, *, text: bool = True) -> dict:
        found = {"code": self.code, "severity": self.severity}
        if self.at:
            found["at"] = self.at
        if self.scheme is not None:
            found["scheme"] = self.scheme
        if self.viewports:
            found["viewports"] = list(self.viewports)
        if self.widths is not None:
            found["widths"] = list(self.widths)
        if self.samples:
            found["samples"] = list(self.samples)
        if self.values:
            found["values"] = self.values
        if text:
            found["text"] = str(self)
        return found

    def but(self, **changes) -> "Finding":
        """This finding with `values` merged and any other field replaced."""
        values = changes.pop("values", None)
        if values is not None:
            changes["values"] = {**self.values, **values}
        return replace(self, **changes)


def _json(value) -> str:
    """`registry.schema.json_value`, imported when words are written: the event log
    raises findings, and a hook that reads a quiet page imports the log but never
    the schema validator behind that module."""
    from leaf.registry.schema import json_value

    return json_value(value)


def note(*found: Finding) -> None:
    """Say each finding beside a command's result, as one JSON line on stderr
    (`cli`), after whatever the result has printed."""
    sys.stdout.flush()
    for finding in found:
        print(
            json.dumps(finding.json(), ensure_ascii=False), file=sys.stderr, flush=True
        )


def element_at(tag: str, id: str = "") -> str:
    """How `locate.js` names an element known by its tag and authored id."""
    return f"<{tag} id={id}>" if id else f"<{tag}>"


def _explained(console: list[dict]) -> str:
    """What the console said, beside a wait that never ended."""
    return "\n".join(_words(Finding.loads(entry)) for entry in console)


def _requests(v: dict) -> str:
    return f"; still requesting {', '.join(v['requesting'])}" if v["requesting"] else ""


def _visual_problem(problem: dict) -> str:
    kind = problem["kind"]
    if kind == "unregistered":
        return "did not call registerVisualParts"
    return f"registered parts its prefixes do not admit {', '.join(problem['parts'])}"


def _verbatim(at: str, v: dict) -> str:
    provenance = v["provenance"]
    if provenance is None:
        where = " without pre-upgrade source provenance"
    elif provenance[0] == "page":
        where = f" at page occurrence {provenance[2] + 1}"
    else:
        where = f" at {provenance[0]} {provenance[1]} occurrence {provenance[2] + 1}"
    return (
        f"{at}{where} declares x-verbatim but shows {v['says'][:80]!r} with owned "
        f"structure {_json(v['shown'])} where the file reads "
        f"{_json(v['expected'])}"
    )


def _squeezed(at: str, v: dict) -> str:
    # A column is named by its heading, or by its place where it has none.
    columns = [
        c
        | {
            "name": f'"{c["heading"]}"'
            if c["heading"] is not None
            else f"column {i + 1}"
        }
        for i, c in enumerate(v["columns"])
    ]
    wraps = [c for c in columns if c["wraps"]]
    top = max(c["width"] for c in columns)
    widest = next(
        (c for c in columns if c["width"] == top and c["wraps"]),
        next(c for c in columns if c["width"] == top),
    )
    return (
        f"{at} scrolls {v['scrolls']}px sideways: "
        + ", ".join(f"{c['name']} wraps at {c['width']}px" for c in wraps)
        + (
            ""
            if widest["wraps"]
            else f" beside {widest['name']} at {widest['width']}px"
        )
        + " — every column stays in reach, so what this costs the reader is the"
        " wrapped cells' words a few to a line; an identifier in <code> breaks inside"
        " its cell, and a shorter word in the widest column gives the rest the measure,"
        " while hiding a column at this width takes its facts from the reader"
    )


def _clipped_content(at: str, v: dict) -> str:
    cuts = []
    if v["down"]:
        cuts.append(
            f"{v['down']}px of it below its height — let it grow to fit, move the rest"
            " into a <details>, or give it data-bound so it scrolls"
        )
    if v["across"]:
        cuts.append(
            f"{v['across']}px of it past its width — let it wrap, or scroll it"
            ' sideways with overflow-x: auto and class="scroll"'
        )
    return f"{at} cuts off its content where no scroll reaches it: " + "; ".join(cuts)


def _line(at: str, v: dict) -> str:
    """An element of the author's file, as they find it: its name and its line."""
    return f"{at} (line {v['line']})"


def _bearing(at: str, v: dict, value: str) -> str:
    """The element `at` names, written with the attribute the finding is about and
    its `value` as the words quote it."""
    return _line(f"{at[:-1]} {v['attr']}={value}>", v)


def _conditions(lacks: dict) -> str:
    """The `x-awaits.when` conditions a widget never met (`instances.unasked`)."""
    return " and ".join(
        " or ".join(
            f"`{attr}` is {'set' if value else 'unset'}"
            if isinstance(value, bool)
            else f"{attr}={_json(value)}"
            for value in values
        )
        for attr, values in lacks.items()
    )


def _seat(seat: dict) -> str:
    return (
        f"{seat['document']} <{seat['tag']}> input `{seat['input']}`"
        f" (line {seat['line']})"
    )


def _reference_contract(at: str, v: dict) -> str:
    expected = ", ".join(f"{key}={_json(value)}" for key, value in v["where"].items())
    found = (
        ", ".join(f"{key}={_json(value)}" for key, value in v["found"].items())
        if v["found"] is not None
        else "no declaration"
    )
    actual = (
        f"<{v['target_tag']}> has {found}"
        if v["target_tag"] is not None
        else "the target is not a registered widget"
    )
    return (
        f'{_line(at, v)}: {v["attr"]}="{v["target"]}" must name a {v["via"]} widget'
        f" where {expected}; {actual}"
    )


def _empty_question(at: str, v: dict) -> str:
    widgets = "; ".join(
        f"{_line(w['at'], w)} asks only where {_conditions(w['lacks'])}"
        for w in v["widgets"]
    )
    return f"{_line(at, v)}: asks the user nothing, " + (
        f"since {widgets}"
        if widgets
        else "since it holds no widget that asks (one declaring x-awaits); add one,"
        " or ask a question answered in words in a thread message with --obligation"
    )


def _outside_main(content: list[dict]) -> list[str]:
    return [
        f"text in <{c['tag']}> at line {c['line']}"
        if c["text"]
        else f"<{c['tag']}> at line {c['line']}"
        for c in content
    ]


def _unservable_layer(v: dict, why: str, action: str) -> str:
    """Why this Leaf can neither serve a page nor write its log (`layer`)."""
    return (
        f"{v['page']} {why}, so it cannot serve the page or write its log. {action}"
        f" with `leaf page init {v['page']}`."
    )


def _unservable_revision(v: dict, why: str) -> str:
    """Why this Leaf can neither serve one revision nor admit input made on it."""
    return (
        f"Revision {v['revision']} {why}, so it cannot serve that revision or accept"
        " input made against it. Revisions saved since the page was re-vendored still"
        " open, and serving the page saves one from its source; where that fails,"
        " `leaf page check` names why."
    )


def _invalid_record(v: dict) -> str:
    """How the refusal of a record one widget's verb writes begins."""
    return f"<{v['tag']}> {v['kind']} {v['verb']!r} is invalid: "


def _visual_parts(declared: dict) -> str:
    """The part ids a section admits, as `registry.contract.VisualParts` says them."""
    from leaf.registry.contract import VisualParts

    return str(VisualParts(tuple(declared["prefixes"]), declared["all"]))


def _size(box: dict) -> str:
    return f"{round(box['width'])}x{round(box['height'])}"


def _declared(words, sep: str = ": "):
    """A registry finding's words: the file it read (`registry`), the element
    declaration `at` names, then `words`; and, for a fault in a vendored layer, how to
    replace it (`revendor`, the page to re-vendor)."""

    def said(at: str, v: dict) -> str:
        text = f"{at} {words(v)}" if at else words(v)
        if "registry" in v:
            text = f"{v['registry']}{sep}{text}"
        if "revendor" in v:
            text += f"; run `leaf page init {v['revendor']}` to re-vendor it"
        return text

    return said


def _json_path(path: list) -> str:
    """Where in a registry a schema complaint points, as `$data.contracts[0]`."""
    where = "".join(
        f"[{step}]" if isinstance(step, int) else f".{step}" for step in path
    )
    return where.lstrip(".") or "registry"


def _plain(value) -> str:
    """A declared value as the registry's words quote it: a word bare, else JSON."""
    return value if isinstance(value, str) else _json(value)


def _predicate(v: dict, says: str) -> str:
    return f"{v['key']} tests `{v['attr']}` {says}"


def _created(v: dict, says: str) -> str:
    return f"x-state verb `{v['verb']}` creates <{v['child']}>, {says}"


def _answering(v: dict, says: str) -> str:
    return f"x-awaits answering verb `{v['verb']}` {says}"


def _box(box: dict) -> str:
    return f"{round(box['left'])},{round(box['top'])} {_size(box)}"


def placed(steps: list[str] | None) -> str:
    """The words for where a suite sensor found a node: its steps innermost first
    (`tests/write_watch.js`, `place`), or that the node has gone."""
    return "a node since removed" if steps is None else " in ".join(steps)


def _by(v: dict) -> str:
    """How far a shift sensor's node moved, and what else its frame moved."""
    left, top = v["by"]
    moved = ", ".join(map(placed, v["beside"]))
    beside = f"; the same frame moved {moved}" if moved else ""
    return f" by ({left}, {top})px{beside}"


def _shift_evidence(v: dict) -> str:
    return f"\nshift evidence: {json.dumps(v['evidence'], ensure_ascii=False)}"


def _captured(words):
    """A capture finding's words: the file it read (`file`) and the reference in it
    (`specifier`), where it names them, then `words`."""

    def said(at: str, v: dict) -> str:
        where = "".join(
            [
                f"{v['file']}: " if "file" in v else "",
                f"{v['specifier']!r}: " if "specifier" in v else "",
            ]
        )
        return where + words(v)

    return said


def _fixture(words):
    """A sample history finding's words: the script it read (`reference`) and, for
    one of its events, which (`event`), then `words`."""

    def said(at: str, v: dict) -> str:
        where = f"data-sample-events {v['reference']!r}"
        if "event" in v:
            return f"{where}, event {v['event']}: {words(v)}"
        return f"{where}{words(v)}"

    return said


def _listed(findings: list[dict]) -> str:
    return "\n".join(f"  - {Finding.loads(found)}" for found in findings)


# The words for each code, from the finding's `at` and `values`. A console code's
# words are what the console said; read by the gate in a color scheme, beside findings
# of its own, it says "console: " first.
_TEXT = {
    "invalid-output": lambda at, v: (
        f"{at} ("
        + "; ".join(
            f"{owner} {part}"
            for part, owner in (
                ("implementation", v["owner"]),
                ("output declaration", v.get("declaration_owner")),
                ("contract", v.get("contract_owner")),
            )
            if owner is not None
        )
        + f"): {v['error']}"
        if any(
            v.get(key) not in (None, v["owner"])
            for key in ("declaration_owner", "contract_owner")
        )
        else f"{at} ({v['owner']} producer): {v['error']}"
    ),
    # What the browser's console and the page's window reported.
    "console-error": lambda at, v: (
        f"{v['text']} — {v['url']}" if v.get("url") else v["text"]
    ),
    "console-warning": lambda at, v: f"warning: {v['text']}",
    "page-exception": lambda at, v: v["text"],
    "window-error": lambda at, v: f"window error: {v['text']}",
    "resize-loop": lambda at, v: (
        f"window error: {v['text']}"
        + {
            None: "",
            "recurred": " (recurred on the confirming render attempt)",
            "incomplete": " (the confirming render attempt did not complete)",
        }[v.get("confirmation")]
    ),
    "upgraded-early": lambda at, v: (
        f"pre-upgrade: widgets upgraded before Leaf entry ran: {', '.join(v['tags'])}"
    ),
    "ready-early": lambda at, v: (
        "pre-upgrade: runtime readiness appeared before Leaf entry ran: "
        + ", ".join(v["stamps"])
    ),
    "main-unlaid": lambda at, v: (
        "pre-upgrade: authored main has no measurable pre-upgrade layout"
    ),
    # The suite's health sensors (`tests/*_watch.js`), each placing a node by its
    # steps (`placed`).
    "moved-without-input": lambda at, v: (
        f"{placed(v['node'])} moved without input{_by(v)}{_shift_evidence(v)}"
    ),
    "typing-moved": lambda at, v: (
        f"typing in {placed(v['field'])} moved {placed(v['node'])}{_by(v)};"
        f" the key found {_box(v['found'])}, the frame painted {_box(v['painted'])}"
        f"{_shift_evidence(v)}"
    ),
    "gesture-scrolled": lambda at, v: (
        f"a scroll during the {v['input']} on {placed(v['node'])} moved it{_by(v)};"
        " only a gesture that takes the user somewhere may, as its command's"
        " `travels` or the history entry it adds says"
        f"{_shift_evidence(v)}"
    ),
    "shift-watch-missed": lambda at, v: (
        "shift watch missed a change to "
        + (placed(v["node"]) if v["node"] else "the page's nodes")
        + f" ({', '.join(v['changed'])})"
        + (
            f" and to {v['others']} other node{'' if v['others'] == 1 else 's'}"
            if v["others"]
            else ""
        )
        + ": a source of change is missing from the sensor's announcements"
        ' (shift_watch.js, "Unchanged frames")'
    ),
    "unchanged-write": lambda at, v: (
        f"unchanged write: children of {placed(v['node'])}"
        if v["what"] == "children"
        else f"unchanged write: {v['what']} on {placed(v['node'])}"
    ),
    "words-left-screen": lambda at, v: (
        "typed words left the screen without a key or press:"
        f" {json.dumps(v['words'], ensure_ascii=False)} in {placed(v['place'])}"
    ),
    "place-resized": lambda at, v: (
        f"{placed(v['place'])} changed size from {_size(v['before'])} to"
        f" {_size(v['after'])} as {', '.join(map(placed, v['left']))} gave way to"
        f" {', '.join(map(placed, v['arrived']))}"
        + (f" after a {v['input']}" if v["input"] else " without input")
    ),
    # The gate's own run, where it could not read the page.
    "gate-failed": lambda at, v: (
        f"the browser gate failed while running its probe module: {v['error']}"
    ),
    "probe-failed": lambda at, v: f"the browser probe module failed: {v['error']}",
    "no-runtime": lambda at, v: (
        "the runtime never injected its chrome — "
        + (_explained(v["console"]) or "and no console message explains why")
    ),
    "never-reached": lambda at, v: (
        f"pre-upgrade proof failed: the document never reached {v['arrival']}"
        + _requests(v)
        + (" — " + _explained(v["console"]) if v["console"] else "")
    ),
    "entry-not-single": lambda at, v: (
        "pre-upgrade proof failed: the document has no single canonical Leaf entry"
        + (" — " + _explained(v["console"]) if v["console"] else "")
    ),
    "entry-not-requested": lambda at, v: (
        "pre-upgrade proof failed: the browser did not request one canonical Leaf entry"
        + (" — " + _explained(v["console"]) if v["console"] else "")
    ),
    "never-upgraded": lambda at, v: (
        "the widget layer never finished upgrading — "
        + (_explained(v["console"]) or "and no console message explains why")
    ),
    "server-stopped": lambda at, v: f"the server stopped answering: {v['error']}",
    "not-ready": lambda at, v: v["error"],
    "never-settled": lambda at, v: (
        f"the page never stopped moving: {', '.join(v['moving'])}"
    ),
    # Widgets and their modules.
    "visual-parts": lambda at, v: (
        f"{at} declares addressable visual parts but its module "
        + "; ".join(_visual_problem(problem) for problem in v["problems"])
    ),
    "invalid-paint": lambda at, v: (
        f"{at} renders {v['property']}={v['value']!r} on <{v['element']}>"
        + (f" for data-id={v['part']!r}" if v["part"] else "")
        + f", but that value does not resolve to valid {v['property']}"
    ),
    "missing-upgrades": lambda at, v: (
        "upgraded widgets did not define their elements: "
        + ", ".join(f"<{tag}>" for tag in v["tags"])
    ),
    "tiny-boxes": lambda at, v: (
        f"widgets rendered with no usable size: {_json(v['boxes'])}"
    ),
    "unmarkable": lambda at, v: (
        f"{at} shows {v['w']}x{v['h']}px of words, but neither it nor anything"
        " inside it draws a box, so a comment anchored here outlines nothing. Put"
        " the words in an element that takes a box"
    ),
    "devtools-issue": lambda at, v: (
        f"DevTools issue {v['issue']}"
        + (f" at {at}" if at else "")
        + (
            f" ({', '.join(f'{k}={_json(x)}' for k, x in v['details'])})"
            if v["details"]
            else ""
        )
    ),
    "verbatim": _verbatim,
    "silent-word": lambda at, v: (
        f'{at} declares {v["attr"]} as x-says and never says "{v["value"]}"'
    ),
    "missing-thread-seat": lambda at, v: (
        f"{at} declares x-thread-seat but rendered {v['hosts']} matching hosts; its"
        " module must place exactly one threadBox"
    ),
    "undeclared-attr": lambda at, v: (
        f"{at} carries {v['attr']!r}, which its element declaration does not name —"
        " declare it as a verb's record form (x-state) if a version is meant to carry"
        " it, or write the state on the chrome the module built"
    ),
    "settlement-mark": lambda at, v: (
        f"{at} has data-lf-state={_json(v['mark'])} where the log records "
        + (f"`{v['outcome']}`" if v["outcome"] else "no decision")
        + " — Leaf sets data-lf-state from the decision in the log, so a widget's"
        " module must not set it to anything else"
    ),
    "retired-slot": lambda at, v: (
        f"{at} is settled `{v['outcome']}`, but its <{v['slot']}> still shows"
        f" {_json(v['words'])}. Leaf hides a retired slot by default, so this"
        " widget's own styles or module must be showing it, and no comment can"
        " anchor to its words"
    ),
    "render-threw": lambda at, v: (
        f"{at} render() threw when the complete state was rendered a second time:"
        f" {v['error']}"
    ),
    "relative-render": lambda at, v: (
        f"{at} render() is relative — rendering the same complete state changed"
        f" {', '.join(v['changed'])}. Render the supplied values without stepping"
        " from the DOM."
    ),
    # Geometry, read across the width sweep.
    "page-scrolls": lambda at, v: f"the page scrolls sideways by {v['past']}px",
    "outside-part": lambda at, v: (
        f"{at} stands {v['past']}px outside the {v['host']} it is part of"
    ),
    "past-column": lambda at, v: (
        f"{at} is set {v['past']}px past the column, out in the margin; to give it"
        ' more room, mark it data-width="wide" or "available" rather than sizing it'
        " past the column"
    ),
    "outside-frame": lambda at, v: (
        f"{at} stands {v['past']}px outside the {v['frame']} that frames it — declare"
        " --lf-block-frame: 1 in the rule that draws the frame, so the box holds the"
        " room in as well as the margins"
    ),
    "past-room": lambda at, v: (
        f"{at} stands {v['past']}px past the room the page has for a wide widget"
    ),
    "over-margin": lambda at, v: (
        f"{at} grows into the margin and is drawn over {v['marginContent']}, which already"
        " sits there; that side of the page has no free room for it"
    ),
    "off-axis": lambda at, v: (
        f"{at} is drawn {v['drawn']}px wide where its width grants {v['granted']}px"
        " of room, so it stands off the prose axis — a width or max-width set on it"
        " overrides the room's"
    ),
    "clipped-out": lambda at, v: (
        f"{at} is drawn {v['past']}px outside {v['container']}, which does not show it"
    ),
    "clipped-content": _clipped_content,
    "scrollbar-clearance": lambda at, v: (
        f"{at} leaves {v['clear']}px below its {v['content']} for a"
        f" {v['required']:g}px horizontal overlay scrollbar; avoid the horizontal"
        " overflow or reserve room below the content so reaching for the bar does"
        " not cover it"
    ),
    "clipped-control": lambda at, v: (
        f"the control .{v['control'].split()[0]}"
        + (f" (#{v['id']})" if v["id"] else "")
        + f" is drawn {v['lost']}px outside the {v['by']} that clips it, where nothing"
        " can scroll to reach it — the page offers a press it does not show"
    ),
    "chrome-words": lambda at, v: (
        f"{at} puts {_json(v['words'])} under .lf-ui, where no comment can reach it"
    ),
    "form-control-words": lambda at, v: (
        f"{at} says {_json(v['words'])} inside a form control, where no selection"
        " can reach it"
    ),
    "apparatus-among-authored": lambda at, v: (
        f"{at}, which Leaf adds, stands among the page's own elements inside"
        f" {v['parent']}, so the page's rules that read its structure, such as"
        " :first-child or h2 + p, match differently"
    ),
    "unread-syntax": lambda at, v: (
        f"code styled {_json(v['style'])} reads at {v['ratio']:.1f}:1 against the"
        " block it is set on"
    ),
    "covered-words": lambda at, v: (
        f"{at} draws {_json(v['words'])} in the same place as {v['under']}'s"
        f" {_json(v['covered'])}"
    ),
    # Advice: what the author decides.
    "unreduced-motion": lambda at, v: (
        f"{at} keeps moving for a reader who asked for less motion; stop or shorten it"
        " under @media (prefers-reduced-motion: reduce)"
    ),
    "squeezed-table": _squeezed,
    "shrunk-labels": lambda at, v: (
        f"{at} draws labels below {v['threshold']}px, {v['labels']} at"
        f" {v['width']}px, the smallest ({v['words']!r}) at {v['drawn']:g}px from"
        f" the {v['set']:g}px it was set at: the drawing is scaled to fit its box"
        " and its labels with it, so set them larger in the viewBox's units, draw"
        " the viewBox nearer the width it is shown at, or give it more room"
        " (authoring-evidence.md, Interactive and visual evidence)"
    ),
    "unreserved-height": lambda at, v: (
        f"{at} first paints {v['first']}px tall, "
        + (
            "reserving no height"
            if v["reserved"] is None
            else f"reserving {v['reserved']}px"
        )
        + f", and draws {v['drawn']}px tall, so what follows it moves"
        f" {abs(v['drawn'] - v['first'])}px when it is drawn:"
        f' state data-height="{v["drawn"]}"'
    ),
    # The page's own code, run once in the browser.
    "page-report": lambda at, v: v["text"],
    "browser-error": lambda at, v: v["error"],
    "request-failed": lambda at, v: (
        f"Browser request failed ({v['kind']}, {v['error']}) in {v['frame']}:"
        f" {v['url']}"
    ),
    "request-status": lambda at, v: (
        f"Browser request returned HTTP {v['status']} ({v['kind']}) in {v['frame']}:"
        f" {v['url']}"
    ),
    # The markup checks, of a page's source, its samples' documents and message
    # markup. The source as a whole:
    "no-source": lambda at, v: f"no {v['path']}; write index.html first",
    "not-utf8": lambda at, v: f"{v['path']} is not UTF-8: {v['error']}",
    # A sample's initial history, read from the JSON script its template names.
    "sample-source-both": lambda at, v: (
        "use either data-sample-events or data-sample-threads, not both"
    ),
    "sample-script": _fixture(
        lambda v: " must name one script in the markup declaring its template"
    ),
    "sample-script-type": _fixture(
        lambda v: " needs an inline application/json script"
    ),
    "sample-json": _fixture(lambda v: f": invalid JSON: {v['error']}"),
    "sample-array": _fixture(lambda v: " must contain an array of event objects"),
    "fixture-publication": _fixture(
        lambda v: "publication is owned by the checked source publisher"
    ),
    "fixture-kind": _fixture(lambda v: f"kind must be one of {_json(v['kinds'])}"),
    "fixture-ts": _fixture(lambda v: "ts must be an ISO timestamp with a time zone"),
    "fixture-id-repeated": _fixture(lambda v: f"event id {v['id']!r} already exists"),
    "fixture-id-taken": _fixture(
        lambda v: f"event id {v['id']!r} is already a document or message widget id"
    ),
    "fixture-media": _fixture(
        lambda v: "; ".join(str(Finding.loads(found)) for found in v["findings"])
    ),
    "fixture-markup": _fixture(
        lambda v: f"{v['kind']} markup doesn't validate:\n{_listed(v['findings'])}"
    ),
    "fixture-ids-taken": _fixture(
        lambda v: f"message widget ids already taken by events: {_json(v['ids'])}"
    ),
    "fixture-event": _fixture(
        lambda v: "; ".join(str(Finding.loads(found)) for found in v["findings"])
    ),
    "fixture-refused": _fixture(lambda v: v["error"]),
    "missing-vendored": lambda at, v: (
        f"{v['file']} missing from the page directory; run `leaf page init` to vendor"
        " the layer"
    ),
    "head-count": lambda at, v: (
        "the page must have one explicit <head> directly under <html>; found"
        f" {v['tags']} head tags, {v['parsed']} parsed heads, and {v['direct']} direct"
        " html heads"
    ),
    "main-count": lambda at, v: (
        f"the page must have one <main> directly under <body>; found {v['bodies']}"
        f" bodies, {v['mains']} mains, and {v['direct']} direct body mains"
    ),
    "outside-main": lambda at, v: (
        "the page's content goes inside the one <main> directly under <body>, which"
        " Leaf reads as the page; move these inside it (a grid or header of the"
        f" page's own goes on or in <main>): {_json(_outside_main(v['content']))}"
    ),
    "unclosed": lambda at, v: (
        "unclosed tags: "
        + ", ".join(f"<{e['tag']}> (line {e['line']})" for e in v["elements"])
    ),
    "self-closing": lambda at, v: (
        f"{at[:-1]}/> at line {v['line']} is self-closing: HTML ignores the slash and"
        f" the element would swallow what follows — write {at[:-1]} …></{at[1:-1]}>"
    ),
    "noscript": lambda at, v: (
        f"{at} at line {v['line']}: the browser renders none of its content; write it"
        " plainly or leave it out"
    ),
    "unnamed-sample": lambda at, v: (
        f"<template data-sample> at line {v['line']}: needs a stable id"
    ),
    "document-declaration": lambda at, v: (
        f"{_line(at, v)} declares something about the whole document, which delivery"
        " owns"
    ),
    "allocation-value": lambda at, v: (
        f"{_bearing(at, v, _json(v['value']))} has an invalid value; expected "
        + (
            "a whole number of CSS pixels"
            if v["allowed"] is None
            else f"one of {', '.join(v['allowed'])}"
        )
    ),
    "css-syntax": lambda at, v: (
        f"{v['sheet']} syntax error at {v['row']}:{v['column']}: {v['message']}"
    ),
    "unserved-media": lambda at, v: (
        f"{v['ref']} isn't a name `leaf page media` gives, so the page never serves it"
    ),
    "missing-media": lambda at, v: (
        f"{v['ref']} isn't in the page directory; `leaf page media` puts it there"
    ),
    # Ids and the runtime's own names.
    "duplicate-ids": lambda at, v: (
        f"duplicate ids (anchors need unique targets): {_json(v['ids'])}"
    ),
    "spaced-ids": lambda at, v: (
        f"ids containing whitespace, which HTML forbids in an id: {_json(v['ids'])}"
    ),
    "reserved-ids": lambda at, v: (
        "ids in the runtime's own lf- namespace (it coins lf-composer-quote there, and"
        f" points ARIA at them): {_json(v['ids'])}"
    ),
    "event-shaped-ids": lambda at, v: (
        "ids shaped like the event ids the log mints (eight hex digits), which"
        f" commands would read as a message: {_json(v['ids'])}"
    ),
    "reserved-markers": lambda at, v: (
        f"{at} at line {v['line']} wears the runtime's own markers"
        f" ({', '.join(v['markers'])}); the lf- and data-lf- namespaces are the"
        " runtime's to write"
    ),
    "ids-taken-by-messages": lambda at, v: (
        f"ids already taken by message markup: {_json(v['ids'])}"
    ),
    "ids-taken": lambda at, v: (
        f"ids already taken by the page or an earlier message: {_json(v['ids'])}"
    ),
    # Widgets, against the registry that declares them.
    "unknown-widget": lambda at, v: (
        f"{_line(at, v)}: unknown widget — not in the vendored registry.json"
    ),
    "attribute-schema": lambda at, v: f"{_line(at, v)}: {v['reason']}",
    "member-record-slot": lambda at, v: (
        f"{_line(at, v)}: scalar verb `{v['value_verb']}` and `{v['owner']}`'s "
        f"selection verb `{v['owner_verb']}` both write attribute `{v['attr']}`"
    ),
    "not-member": lambda at, v: (
        f"{_line(at, v)}: must be a direct member of "
        + " or ".join(f"<{owner}>" for owner in v["owners"])
        + " or stand inside its "
        + " or ".join(f"<{region}>" for region in v["within"])
        if v["within"]
        else f"{_line(at, v)}: must be a direct member of "
        + " or ".join(f"<{owner}>" for owner in v["owners"])
        + (f", found <{v['parent']}>" if v["parent"] else "")
    ),
    "content-empty": lambda at, v: (
        f"{_line(at, v)}: takes no content — write {at[:-1]} …></{at[1:-1]}>"
    ),
    "data-body": lambda at, v: (
        f"{_line(at, v)}: its body is one <pre> holding the text (escape < and >),"
        " found " + (", ".join(f"<{c}>" for c in v["children"]) or "nothing")
    ),
    "text-outside-pre": lambda at, v: (
        f"{_line(at, v)}: text outside its <pre> — the whole body goes inside it"
    ),
    "stray-members": lambda at, v: (
        f"{_line(at, v)}: admits only {_json(v['admits'])} members, found"
        f" {_json(v['found'])}"
    ),
    "loose-text": lambda at, v: (
        f"{_line(at, v)}: loose text between its members isn't allowed"
    ),
    "parts-in-layout": lambda at, v: (
        f"{_line(at, v)}: stands in a <main> that carries {v['layout']}; a page of"
        " parts needs a <main> with no Layout, since each part's child carries its"
        ' own (page-layout.md, "A page of parts")'
    ),
    "pane-ends": lambda at, v: (
        f"{_line(at, v)}: x-reading-role {v['role']} admits at most one direct"
        " <header> and one direct <footer>"
    ),
    "pane-header-first": lambda at, v: (
        f"{_line(at, v)}: x-reading-role {v['role']} direct <header> must be first"
    ),
    "pane-footer-last": lambda at, v: (
        f"{_line(at, v)}: x-reading-role {v['role']} direct <footer> must be last"
    ),
    "pane-body": lambda at, v: (
        f"{_line(at, v)}: x-reading-role {v['role']} must contain exactly one direct"
        " body element between its header and footer, found "
        + (_json(v["body"]) if v["body"] else "nothing")
        + "; wrap several blocks in one <div> or <section>"
    ),
    "needs-id": lambda at, v: (
        f"{_line(at, v)}: a matching {v['role']} instance requires an id"
    ),
    "empty-question": _empty_question,
    "untitled-question": lambda at, v: (
        f"{_line(at, v)}: this enclosing widget needs a heading to title its obligations,"
        " leading its content alone or in an <hgroup> or <header>"
    ),
    "repeated-key": lambda at, v: (
        f'{_line(at, v)}: {v["key"]}="{v["value"]}" repeats the {at} at line'
        f" {v['first_line']} in the same <{v['scope']}>"
    ),
    "unmatched-member": lambda at, v: (
        f'{_line(at, v)}: {v["attr"]}="{v["target"]}" names no <{v["member"]}'
        f' {v["key"]}="{v["target"]}"> in its <{v["scope"]}>'
    ),
    "unknown-reference": lambda at, v: (
        f'{_line(at, v)}: {v["attr"]}="{v["target"]}" names no element in this version'
    ),
    "reference-contract": _reference_contract,
    "ambiguous-data-binding": lambda at, v: (
        f"{_line(at, v)}: input {v['input']!r} binds both an external source and widget output"
    ),
    "output-contract": lambda at, v: (
        f"{_line(at, v)}: input {v['input']!r} requires output {v['output']!r} of {v['target']!r} with contract {v['contract']!r}"
    ),
    "shows-outside": lambda at, v: (
        f'{_line(at, v)}: {v["attr"]}="{v["target"]}" names a widget outside its own'
        " document; a view shows answers in the page or message it stands in"
    ),
    "shows-no-answer": lambda at, v: (
        f'{_line(at, v)}: {v["attr"]}="{v["target"]}" names a widget whose answer no'
        " view can show: its x-awaits value verb records neither a value nor members"
        " an x-awaits key names"
    ),
    "shows-without-open": lambda at, v: (
        f"{_line(at, v)}: every <{v['place']}> beside its own has a `{v['value_attr']}`,"
        f" so none can hold it while {v['target']}'s answer names no value; add a"
        f" <{v['place']}> without `{v['value_attr']}`"
    ),
    "shows-untakeable": lambda at, v: (
        f"{_line(at, v)}: {v['target']} has no answer {v['value']!r}, which a"
        f" <{v['place']}> beside it holds"
    ),
    "shown-elsewhere": lambda at, v: (
        f"{_line(at, v)}: stands in a <{v['place']}> holding "
        + (f"{v['stands']!r}" if v["stands"] else "no value")
        + f", but {v['target']}'s answer is "
        + (
            f"{v['answer']!r}; move it to the <{v['place']}> whose"
            f" `{v['value_attr']}` is {v['answer']!r}"
            if v["answer"]
            else f"no value; move it to a <{v['place']}> without `{v['value_attr']}`"
        )
    ),
    "outside-reference": lambda at, v: (
        f'{_line(at, v)}: {v["attr"]}="{v["target"]}" names an element outside its'
        " own document, which it fills"
    ),
    "unowned": lambda at, v: (
        f"{_line(at, v)}: no <{v['referrer']}> names it in `{v['attr']}`"
    ),
    "owned-twice": lambda at, v: (
        f'{_line(at, v)}: {v["attr"]}="{v["target"]}" is already named by'
        f" {v['first']} (line {v['first_line']}); only one element may name it"
    ),
    "nested-suggestion": lambda at, v: f"{_line(at, v)}: suggestions don't nest",
    "empty-suggestion": lambda at, v: (
        f"{_line(at, v)}: needs a <lf-old> (what it replaces), a <lf-new> (what it"
        " proposes), or both"
    ),
    "repeated-slot": lambda at, v: (
        f"{_line(at, v)}: carries {v['count']} <{v['slot']}> children, one at most"
    ),
    "unknown-thread": lambda at, v: (
        f"{_line(at, v)}: resolves={v['resolves']!r} names no thread in this document"
    ),
    "contract-conflict": lambda at, v: (
        f"source {v['source']!r} is bound to both contract {v['first']['contract']!r}"
        f" at {_seat(v['first'])} and contract {v['then']['contract']!r} at"
        f" {_seat(v['then'])}; use a new source id for the new meaning"
    ),
    # Message markup, which the log freezes.
    "frozen-settlement": lambda at, v: (
        f"{at} is a settlement holder, but thread markup is frozen in the log and no"
        " version could ever settle it; put the change in the next version instead"
    ),
    "message-style": lambda at, v: (
        "<style> in message markup becomes a stylesheet of the whole document it is"
        " put into; a widget's look belongs in the layer's theme, beside its element"
        " declaration"
    ),
    "message-stylesheet": lambda at, v: (
        "<link rel=stylesheet> in message markup dresses the whole document it is put"
        " into; the page serves the one vendored theme it was reviewed with"
    ),
    "sample-loop": lambda at, v: (
        f"sample {_json(v['samples'])} selects thread {v['thread']!r}, which"
        " holds this message, so its child would hold the same sample again; select"
        " other threads"
    ),
    # Advice on the source.
    "unpointable-section": lambda at, v: (
        f"unpointable — {_line(at, v)} has no id, so no comment or reading position"
        " can hold to it"
    ),
    "unpointable": lambda at, v: (
        f"unpointable — {_line(at, v)} has no id, nor anything enclosing it, so"
        " element selection has no target"
    ),
    "unpointable-wide": lambda at, v: (
        f"unpointable — {_line(at, v)} has no id, so a comment aimed at it lands on"
        f" the whole of #{v['enclosing']}"
    ),
    "measurement-lag": lambda at, v: (
        f"measurement behind its source: {_line(at, v)} pins source {v['source']!r}"
        f" run {v['run']}, but that source now holds run {v['current_run']}"
    ),
    "unreadable-data": lambda at, v: f"data source unreadable: {v['error']}",
    "relocated-anchor": lambda at, v: (
        f"open thread {v['thread']} anchor no longer resolves; its revision moves it"
        " to "
        + (
            f"section {v['section']!r}"
            if v["section"] is not None
            else "a detached thread"
        )
        + "; to place it yourself, reply in it with --section or --quote, or"
        " --detach"
    ),
    # A registry, the vocabulary a page or package declares: `registry` is the file it
    # was read from, and `at` the element declaration a finding concerns. The file:
    "registry-not-file": _declared(lambda v: "registry.json must be a file"),
    "registry-json": _declared(
        lambda v: f"invalid JSON ({v['error']}, line {v['line']})"
    ),
    "registry-not-utf8": _declared(lambda v: "must be UTF-8", sep=" "),
    "registry-not-object": _declared(lambda v: "registry must be a JSON object"),
    "declaration-not-object": _declared(
        lambda v: f"registry declarations must be objects: {_json(v['names'])}"
    ),
    "no-incoming-registry": _declared(
        lambda v: "the incoming layer has no registry.json"
    ),
    "page-layer": _declared(lambda v: "$layer belongs to the selected layer"),
    "layer-packages": _declared(
        lambda v: "$layer.packages must be a unique list of non-empty strings"
    ),
    "layer-identity": _declared(
        lambda v: "vendored registry lacks its $layer identity; run `leaf page init`"
    ),
    # Its shared layer facts.
    "layer-facts": _declared(lambda v: f"{_json_path(v['path'])}: {v['reason']}"),
    "fixed-events": _declared(
        lambda v: (
            f"$events.{v['key']} is Leaf's fixed transport contract and cannot"
            " be changed by a layer"
        )
    ),
    "fixed-kernel-fact": _declared(
        lambda v: f"{v['name']} is Leaf's own and cannot be changed by a layer"
    ),
    "undeclared-event-kind": _declared(
        lambda v: (
            f"$events.{v['key']} names {v['kind']!r}, which is none of"
            f" {', '.join(v['declared'])}"
        )
    ),
    "invalid-when": _declared(
        lambda v: (
            f"$events.{v['key']}.{v['kind']} clause `when` is not a valid JSON"
            f" Schema: {v['reason']}"
        )
    ),
    "keys-documentation": _declared(
        lambda v: (
            f"{v['fact']} must carry a description and one paragraph per key the"
            f" lint admits — missing {_json(v['missing'])}, unadmitted"
            f" {_json(v['unadmitted'])}"
        )
    ),
    "idiom-selector": _declared(
        lambda v: f"idiom {v['selector']!r} selector cannot be matched: {v['error']}"
    ),
    "idiom-schema": _declared(
        lambda v: f"idiom {v['selector']!r} {_json_path(v['path'])}: {v['reason']}"
    ),
    "undeclared-language": _declared(
        lambda v: (
            f"$languages.paths maps {_json(v['extensions'])} to languages"
            " $languages.names does not declare"
        )
    ),
    "contract-resource": _declared(
        lambda v: (
            f"$data contract {v['contract']!r} resource expression"
            f" {v['expression']!r} is invalid: {v['error']}"
        )
    ),
    "contract-records": _declared(
        lambda v: (
            f"$data contract {v['contract']!r} records must name distinct"
            " items, key, and deferred fields"
        )
    ),
    "contract-schema": _declared(
        lambda v: (
            f"$data contract {v['contract']!r} has an invalid JSON Schema:"
            f" {v['reason']}"
        )
    ),
    "contract-reference": _declared(
        lambda v: (
            f"$data contract {v['contract']!r} schema reference"
            f" {v['reference']!r} does not resolve within the package; data contracts"
            " must be self-contained"
        )
    ),
    # An element declaration, on its own.
    "declaration-schema": _declared(
        lambda v: f"is not a valid JSON Schema: {v['reason']}"
    ),
    "no-description": _declared(lambda v: "must carry a non-empty description"),
    "invalid-extensions": _declared(
        lambda v: f"registry extensions are invalid: {v['reason']}"
    ),
    "example-data": _declared(lambda v: f"x-example-data is invalid: {v['reason']}"),
    "invalid-example": _declared(
        lambda v: f"x-example is invalid: {Finding.loads(v['finding'])}"
    ),
    "missing-module": _declared(
        lambda v: (
            "is upgraded but its module is missing; expected"
            f" {v['expected'][0]} or {v['expected'][1]}"
        )
    ),
    "markdown-needs-data": _declared(
        lambda v: "block Markdown requires x-content: data"
    ),
    "requires": _declared(
        lambda v: f"{v['key']} requires {v['needs']}: {_plain(v['value'])}"
    ),
    "needs-upgrade": _declared(
        lambda v: f"declares {', '.join(v['keys'])} but has no upgraded handler"
    ),
    "unknown-declarations": _declared(
        lambda v: f"{v['key']} names unknown element declarations {_json(v['names'])}"
    ),
    "undeclared-attributes": _declared(
        lambda v: f"{v['key']} names undeclared attributes {_json(v['names'])}"
    ),
    "reading-role-attr": _declared(
        lambda v: f"x-reading-role {v['role']} instances require a string {v['attr']}"
    ),
    "addressable-id": _declared(
        lambda v: (
            f"{v['key']} instances are addressable, so the element declaration"
            " must declare a string `id` attribute"
        )
    ),
    "enclosing-id": _declared(lambda v: "x-encloses must require an id"),
    "enclosing-prose": _declared(
        lambda v: "x-encloses must admit prose around the obligations it frames"
    ),
    "data-contract": _declared(
        lambda v: (
            f"x-data input `{v['input']}` names unknown contract {v['contract']!r}"
        )
    ),
    "unknown-output-contract": _declared(
        lambda v: f"x-output `{v['output']}` names unknown contract {v['contract']!r}"
    ),
    "data-reference": _declared(
        lambda v: (
            f"x-data input `{v['input']}` reference `{v['attr']}` must name an x-refers element relation"
        )
    ),
    "data-source": _declared(
        lambda v: (
            f"x-data input `{v['input']}` source attribute `{v['attr']}` must"
            " be a canonical data source string"
        )
    ),
    "measured-input": _declared(
        lambda v: f"x-measured input `{v['input']}` is not one of its x-data inputs"
    ),
    "measured-source": _declared(
        lambda v: (
            f"x-measured input `{v['input']}` source attribute `{v['attr']}`"
            " must be required"
        )
    ),
    "measured-run": _declared(
        lambda v: (
            f"x-measured run attribute `{v['attr']}` must be required and"
            " declare a nonempty string"
        )
    ),
    "refers-unknown-member": _declared(
        lambda v: (
            f"x-refers `{v['attr']}` names unknown element declaration <{v['member']}>"
        )
    ),
    "refers-unkeyed": _declared(
        lambda v: (
            f"x-refers `{v['attr']}` names <{v['member']}> by `{v['key']}`,"
            f" which <{v['member']}> does not declare in x-unique"
        )
    ),
    "refers-unknown-map": _declared(
        lambda v: f"x-refers `{v['attr']}` names unknown registry map {v['via']!r}"
    ),
    "refers-unmatched": _declared(
        lambda v: (
            f"x-refers `{v['attr']}` requires {v['via']} where "
            + ", ".join(f"{key}={_json(value)}" for key, value in v["where"].items())
            + ", but no declared widget matches"
        )
    ),
    "visual-id": _declared(
        lambda v: (
            "has addressable visual parts but does not require a string `id`"
            " for their anchor"
        )
    ),
    "visual-upgrade": _declared(
        lambda v: (
            "declares addressable visual parts but has no upgraded handler to"
            " resolve them"
        )
    ),
    # Its conditions, read against its own attributes.
    "predicate-attribute": _declared(
        lambda v: f"{v['key']} names undeclared attribute `{v['attr']}`"
    ),
    "predicate-schema": _declared(
        lambda v: _predicate(
            v,
            f"at {_json(v['value'])}, which its own schema does not admit:"
            f" {v['reason']}",
        )
    ),
    "seat-written": _declared(
        lambda v: (
            "x-thread-seat predicate attributes are authored and static, but"
            f" {_json(v['attrs'])} are written by value records"
        )
    ),
    "binding-written": _declared(
        lambda v: (
            "x-data binding attributes are authored, but"
            f" {_json(v['attrs'])} are written by value records"
        )
    ),
    "run-written": _declared(
        lambda v: (
            f"x-measured run attribute `{v['attr']}` is an authored source"
            " receipt, but is written by a value record"
        )
    ),
    # Its interactions: local work, its obligation, and the state its verbs write.
    "work-inline": _declared(
        lambda v: "declares x-work but is inline; local work chrome needs a block slot"
    ),
    "work-content": _declared(
        lambda v: (
            f"declares x-work but x-content is {v['content']}; generated local"
            " chrome may only join authored prose"
        )
    ),
    "awaits-records": _declared(
        lambda v: (
            "x-awaits.records must name an x-data input whose contract declares records and whose binding names only an external source attribute"
        )
    ),
    "answering-record": _declared(
        lambda v: _answering(
            v,
            "must use the same record unit as x-awaits.value, with custom detail and no empty condition",
        )
    ),
    "answering-detail": _declared(
        lambda v: _answering(
            v, f"detail condition names an undeclared or invalid field `{v['field']}`"
        )
    ),
    "awaits-unanswered": _declared(
        lambda v: "x-awaits local obligation declares no `answered` condition"
    ),
    "awaits-verbs": _declared(
        lambda v: (
            f"x-awaits answers with verbs {_json(v['verbs'])}, which are"
            " not x-state verbs the user writes"
        )
    ),
    "awaits-value": _declared(
        lambda v: "x-awaits value must name a user-written x-state verb"
    ),
    "awaits-key": _declared(
        lambda v: (
            f"x-awaits key `{v['key']}` needs an attribute-record value verb whose"
            f" members declare `{v['key']}` in x-unique for this widget"
        )
    ),
    "shows-reference": _declared(
        lambda v: (
            f"x-shows attr `{v['attr']}` must be an x-refers relation to any element"
        )
    ),
    "shows-value": _declared(
        lambda v: (
            f"x-shows value `{v['attr']}` is no attribute of "
            + ", ".join(f"<{owner}>" for owner in v["owners"])
        )
    ),
    "awaits-retired": _declared(
        lambda v: (
            f"x-awaits retires with `{v['flag']}`, but its `when` does not"
            f" require `{v['flag']}` absent"
        )
    ),
    "awaits-blanket": _declared(
        lambda v: (
            f"x-awaits blanket answer `{v['outcome']}` is not an outcome of a"
            " deciding verb that answers its obligation"
        )
    ),
    "unoverruled": _declared(
        lambda v: (
            "declares agent-written x-state verbs"
            f" {_json(v['verbs'])} but no boolean `overruled` attribute, which a"
            " version sets to overrule a worker's report"
        )
    ),
    "unrestated": _declared(
        lambda v: (
            "declares user x-state verbs on the whole widget but no boolean"
            " `restated` attribute, which a version sets to retract the user's"
            " decision"
        )
    ),
    "reserved-resolves": _declared(
        lambda v: (
            "declares attribute `resolves`, a reserved name (the thread an"
            " answer to its obligation closes), but originates no local obligation"
        )
    ),
    "verb-detail-schema": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` has an invalid detail schema: {v['reason']}"
        )
    ),
    "creates-unit": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` creates a child, so its fold unit must"
            " name the detail field carrying the child's id and it declares no record"
            " form"
        )
    ),
    "creates-detail": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` creates a child, so its detail must be"
            f" exactly the required element id `{v['unit']}` and the required non-empty"
            f" words `{v['words']}`"
        )
    ),
    "creates-unknown": _declared(
        lambda v: f"x-state verb `{v['verb']}` creates unknown child <{v['child']}>"
    ),
    "creates-owner": _declared(
        lambda v: _created(v, "whose x-owners does not admit the sender")
    ),
    "creates-content": _declared(
        lambda v: _created(v, "which must declare x-content markup")
    ),
    "creates-required": _declared(
        lambda v: _created(v, "which must require id and no other authored attributes")
    ),
    "creates-id": _declared(
        lambda v: _created(
            v, "whose required id must use the canonical element-id schema"
        )
    ),
    "creates-semantic-owner": _declared(
        lambda v: _created(
            v,
            "which must be a parent-owned member without independent owner capabilities: "
            + ", ".join(v["keys"]),
        )
    ),
    "shared-slot": _declared(
        lambda v: (
            f"x-state verbs `{v['verbs'][0]}` and `{v['verbs'][1]}` claim the"
            f" same physical record slot (unit `{v['unit']}`, {v['kind']}"
            + (f" `{v['attr']}`" if v["attr"] else "")
            + "); distinct verbs must record independently"
        )
    ),
    "unit-undeclared": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` must declare and require its fold unit"
            f" `{v['unit']}` in detail"
        )
    ),
    "unit-type": _declared(
        lambda v: f"x-state verb `{v['verb']}` fold unit `{v['unit']}` must be a string"
    ),
    "record-unit": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` record `{v['kind']}` requires unit:"
            f" {v['unit']!r}"
        )
    ),
    "record-within": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` records a position within unknown"
            f" widget <{v['within']}>"
        )
    ),
    "body-content": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` records its body, so x-content must be"
            " data; projection states text rather than a prose subtree"
        )
    ),
    "body-nested": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` records its body but admits nested"
            f" widgets {_json(v['widgets'])}; a text statement cannot reconstruct"
            " their state"
        )
    ),
    "record-undeclared": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` records undeclared attribute `{v['attr']}`"
        )
    ),
    "record-says": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` records x-says attribute"
            f" `{v['attr']}`, whose value is words the user sees — declared state may not"
            " move the page's words"
        )
    ),
    "record-type": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` record attribute `{v['attr']}` must be"
            " a string or string enum; HTML attributes cannot restore another JSON type"
        )
    ),
    "deciding-verbs": _declared(
        lambda v: (
            f"x-state verbs {_json(v['verbs'])} all declare `decides: true`;"
            " only one verb may decide which members retire"
        )
    ),
    "deciding-verb": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` declares `decides: true`:"
            " the deciding verb folds by widget, is written by the user,"
            " and requires `outcome` as a string enum"
        )
    ),
    "verb-contract": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` binds detail field `{v['field']}` to"
            f" attribute `{v['attribute']}`: the field must be declared and the"
            " attribute must be a string matching the data contract name pattern"
        )
    ),
    "instance-contract": lambda at, v: (
        f"{at} attribute `{v['attribute']}` names unknown data contract"
        f" {v['contract']!r} for `{v['verb']}` detail field `{v['field']}`"
    ),
    "withdrawn-as": _declared(
        lambda v: f"x-withdrawn-as `{v['outcome']}` is not a deciding outcome"
    ),
    "retired-when": _declared(
        lambda v: (
            f"x-retired-when `{v['outcome']}` is invalid: <{v['owner']}>"
            " declares no deciding x-state verb with that outcome"
        )
    ),
    "answering-part": _declared(
        lambda v: _answering(
            v, "folds on a part rather than the widget, so its condition needs `empty`"
        )
    ),
    "answering-position": _declared(
        lambda v: _answering(v, "tests an empty container but records no position")
    ),
    "answering-container": _declared(
        lambda v: _answering(v, f"names unknown container <{v['within']}>")
    ),
    "answering-members": _declared(
        lambda v: _answering(
            v, f"names <{v['within']}>, whose x-content is not members"
        )
    ),
    "answering-undeclared": _declared(
        lambda v: _answering(
            v, f"tests undeclared <{v['within']}> attribute `{v['attr']}`"
        )
    ),
    "answering-mutable": _declared(
        lambda v: _answering(
            v, f"tests mutable <{v['within']}> attribute `{v['attr']}`"
        )
    ),
    "answering-schema": _declared(
        lambda v: _answering(
            v,
            f"tests <{v['within']}> `{v['attr']}` at {_json(v['value'])}, which"
            f" its schema does not admit: {v['reason']}",
        )
    ),
    # Capturing the page and the files it loads as an immutable revision: `file` is
    # the file a finding concerns, and `specifier` the reference in it.
    "dependency-url": _captured(lambda v: f"invalid dependency URL: {v['error']}"),
    "dependency-scheme-dependent": _captured(
        lambda v: (
            "dependency's local or external meaning depends on the page's URL scheme;"
            " use a relative path or a complete http(s) URL"
        )
    ),
    "dependency-not-local": _captured(
        lambda v: (
            "dependency must be a local URL (module URLs have no query or"
            " fragment), or an http(s) URL"
        )
    ),
    "dependency-encoded": _captured(
        lambda v: "decoded dependency path contains a backslash or control character"
    ),
    "dependency-escapes": _captured(lambda v: "dependency escapes the page"),
    "dependency-outside-page": _captured(
        lambda v: (
            "a page's own files (stylesheets, scripts, images, data) live under page/"
            " beside index.html, or media/; move the file there and name it by that"
            " path, such as page/style.css"
        )
    ),
    "dependency-symlink": _captured(
        lambda v: "dependency escapes its source directory through a symlink"
    ),
    "dependency-unreadable": _captured(
        lambda v: f"cannot capture dependency: {v['error']}"
    ),
    "module-not-local": _captured(
        lambda v: (
            "a bare module name has no import map to resolve it; import a file under"
            " page/ by its path, or a package by its full http(s) URL (such as"
            " https://esm.sh/NAME)"
        )
    ),
    "module-type": _captured(
        lambda v: "a module dependency must be JavaScript or JSON"
    ),
    "module-outside-page": _captured(
        lambda v: (
            "a module the page imports lives under page/, is a public entry point"
            " such as /runtime/widget-api.js, or is an http(s) URL"
        )
    ),
    "script-not-utf8": _captured(lambda v: "JavaScript is not UTF-8"),
    "script-outside-page": _captured(
        lambda v: "a page's own scripts live under page/; move it there"
    ),
    "stylesheet-type": _captured(
        lambda v: "a stylesheet dependency must have CSS MIME type"
    ),
    "css-not-utf8": _captured(lambda v: "CSS is not UTF-8"),
    "css-invalid": _captured(lambda v: f"invalid CSS: {v['error']}"),
    "css-url": _captured(lambda v: "CSS url() requires one literal URL"),
    "css-import": _captured(
        lambda v: "CSS @import requires a stylesheet with CSS MIME type"
    ),
    "revision-exists": _captured(lambda v: f"revision r{v['revision']} already exists"),
    "digest-collision": _captured(lambda v: "immutable artifact digest collision"),
    "manifest-digest": _captured(
        lambda v: "captured manifest digest does not match revision"
    ),
    "layer-import-remote": _captured(lambda v: "captured layer import is not local"),
    "layer-import-missing": _captured(lambda v: "captured layer import is missing"),
    # The package check's refusal.
    "package": lambda at, v: v["text"],
    "leaf-version": lambda at, v: (
        f"Leaf {v['vendored']} vendored this page; this is Leaf {v['running']}."
    ),
    # The widget quality report, for a widget's author.
    "unreadable-examples": lambda at, v: (
        f"widget examples could not be drawn: {v['error']}"
    ),
    "example": lambda at, v: f"{at} example: no worked example shows it",
    "keeps-first-box": lambda at, v: (
        f"{at} keeps-first-box: in a {v['layout']} page, first painted"
        f" {_size(v['first'])}, {_size(v['now'])} once presented"
    ),
    "shows-context-keys": lambda at, v: (
        f"{at} shows-context-keys: in a {v['layout']} page, {v['command']} declares"
        " context keys and no"
        " bindingBadge, so its key works with nothing on the page showing it; lend"
        " the command a face, or request a corner badge with bindingBadge: null"
    ),
    "grows-with-content": lambda at, v: (
        f"{at} grows-with-content: in a {v['layout']} page, {v['box']} holds"
        f" {v['height']}px and scrolls"
        " inside it; let it grow with its content, or declare --lf-holds-height: 1"
        " where the task needs its own scroll"
    ),
    # The append door's refusals of one event (`event_contracts.admitted_event`). The
    # door adds the refused event's `kind` to every one; the other values name what it
    # concerns, and where a value was refused, what would have been admitted.
    "attempt-conflict": lambda at, v: (
        f"attempt {v['attempt']!r} already belongs to another event"
    ),
    "foreign-layer": lambda at, v: _unservable_layer(
        v,
        f"was vendored by a Leaf at page protocol {v['vendored']}, and this Leaf"
        f" ({v['leaf']}) speaks protocol {v['protocol']}",
        "Update the page's Leaf runtime",
    ),
    "newer-layer": lambda at, v: (
        f"{v['page']} was vendored at page protocol {v['vendored']} by a newer Leaf"
        f" ({v['vendored_by']}), and this Leaf ({v['leaf']}) speaks protocol"
        f" {v['protocol']}, so it can neither serve nor re-vendor the page. Use a"
        f" Leaf at protocol {v['vendored']} or later; in Claude Code,"
        " `/reload-plugins` loads an installed update."
    ),
    "retired-layer": lambda at, v: _unservable_layer(
        v,
        f"was vendored by a Leaf that declares {', '.join(v['retired'])}, which this"
        f" Leaf ({v['leaf']}) no longer admits",
        "Re-vendor it",
    ),
    "foreign-revision": lambda at, v: _unservable_revision(
        v,
        f"was saved at page protocol {v['saved']}, and this Leaf speaks protocol"
        f" {v['protocol']}",
    ),
    "retired-revision": lambda at, v: _unservable_revision(
        v,
        f"was saved by a Leaf that declares {', '.join(v['retired'])}, which this"
        " Leaf no longer admits",
    ),
    "no-registry": lambda at, v: "the page has no registry.json",
    "unknown-kind": lambda at, v: f"kind must be one of {_json(v['kinds'])}",
    "invalid-event": lambda at, v: f"{v['kind']} event is invalid: {v['error']}",
    "unknown-revision": lambda at, v: (
        f"{v['kind']} revision must be one of {_json(v['revisions'])}"
    ),
    "publication-owner": lambda at, v: (
        "publication is owned by the checked source publisher"
    ),
    "publication-revision": lambda at, v: (
        "publication must name its checked candidate revision"
    ),
    # An action or a report, against its widget's declaration.
    "unknown-sender": lambda at, v: (
        f"unknown report widget {v['widget']!r} in revision r{v['revision']} — reports"
        " name page widgets only, since no version can answer a report in frozen"
        " thread markup"
        if v["kind"] == "report"
        else f"unknown action widget {v['widget']!r} in revision r{v['revision']} or"
        " agent-authored thread markup"
    ),
    "undeclared-tag": lambda at, v: (
        f"registry no longer declares <{v['tag']}> for {v['kind']} widget"
        f" {v['widget']!r}"
    ),
    "foreign-verb": lambda at, v: (
        f"<{v['tag']}> {v['verb']!r} is a verb the {v['writer']} writes; this"
        f" {v['kind']} came from the {v['sender']}"
    ),
    "undeclared-verb": lambda at, v: (
        f"<{v['tag']}> does not declare {v['kind']} verb {v['verb']!r}"
        + (
            f"; it declares {_json(v['declared'])}"
            if v["kind"] == "report" and v["declared"]
            else ""
        )
    ),
    "invalid-detail": lambda at, v: (
        f"<{v['tag']}> {v['kind']} {v['verb']!r} detail is invalid: {v['error']}"
    ),
    "quoted-widget": lambda at, v: (
        f"<{v['tag']}> {v['widget']!r} stands inside an exhibit (x-exhibit); quoted"
        " material takes no input"
    ),
    "created-exists": lambda at, v: (
        f"<{v['tag']}> action {v['verb']!r} creates {v['created']!r}, which already"
        " names an authored element"
    ),
    "unknown-unit": lambda at, v: (
        f"{_invalid_record(v)}position record names unknown unit {v['unit']!r}"
    ),
    "unknown-destination": lambda at, v: (
        f"{_invalid_record(v)}position record names unknown destination"
        f" {v['destination']!r}"
    ),
    "foreign-destination": lambda at, v: (
        f"{_invalid_record(v)}position record destination {v['destination']!r} is"
        f" <{v['found']}>, not <{v['within']}>"
    ),
    "foreign-unit": lambda at, v: (
        f"{_invalid_record(v)}position record unit {v['unit']!r} is not owned by"
        f" action widget {v['widget']!r}"
    ),
    "shown-unit": lambda at, v: (
        f"{_invalid_record(v)}{v['unit']!r} shows the answer of {v['shows']!r}, which"
        " decides where it stands; change that answer instead"
    ),
    "nested-unit": lambda at, v: (
        f"{_invalid_record(v)}position record cannot put {v['unit']!r} inside itself"
        f" or its descendant {v['destination']!r}"
    ),
    "outside-destination": lambda at, v: (
        f"{_invalid_record(v)}position record destination {v['destination']!r} is"
        f" outside action widget {v['widget']!r}"
    ),
    "unowned-placement": lambda at, v: (
        f"{_invalid_record(v)}position record cannot put <{v['unit_tag']}>"
        f" {v['unit']!r} within <{v['found']}> {v['destination']!r}"
    ),
    "unknown-members": lambda at, v: (
        f"{_invalid_record(v)}{', '.join(v['strangers'])} name no member of"
        f" {v['widget']!r}"
    ),
    "stale-move": lambda at, v: (
        f"{v['kind']} {v['verb']!r} on {v['widget']!r} was made on r{v['revision']},"
        f" and r{v['newest']} authors {v['container']!r} differently, so its rank no"
        " longer names the gap it was dropped into"
    ),
    "unknown-reaction": lambda at, v: (
        f"unknown reaction token {v['token']!r}; this layer declares"
        f" {_json(v['tokens'])}"
    ),
    # A comment's anchor and hold.
    "datum-unknown-section": lambda at, v: (
        f"datum anchor names unknown section {v['section']!r}"
    ),
    "datum-unbound-source": lambda at, v: (
        f"datum anchor source {v['source']!r} is not bound by section {v['section']!r}"
    ),
    "datum-unsupplied-source": lambda at, v: (
        f"datum anchor source {v['source']!r} has never been supplied to this page"
    ),
    "hold-target": lambda at, v: (
        "comment holds must name its exact-section anchor on a matching x-thread-seat"
        " hold target"
    ),
    "visual-with-passage": lambda at, v: (
        f"visual anchor {v['visual']!r} names a box rather than a passage, so it"
        " cannot also carry a quote or a datum"
    ),
    "undeclared-visual": lambda at, v: (
        f"visual anchor {v['visual']!r} is not declared on section {v['section']!r};"
        f" {_visual_parts(v['declared'])}"
    ),
    # A message, an edit, and a thread's presentation.
    "unknown-parent": lambda at, v: f"unknown parent {v['parent']!r}",
    "withdrawn-parent": lambda at, v: f"parent {v['parent']!r} has been taken back",
    "unknown-message": lambda at, v: f"unknown message {v['message']!r}",
    "foreign-message": lambda at, v: (
        f"message {v['message']!r} is not {v['author']}-authored"
    ),
    "wordless-message": lambda at, v: (
        f"message {v['message']!r} has no words to revise"
    ),
    "stale-edit": lambda at, v: (
        f"edit of {v['message']!r} was written over {v['base']!r}, and"
        f" {v['latest']!r} has since revised it"
    ),
    "unchanged-edit": lambda at, v: (
        f"edit of {v['message']!r} says what the message already says"
    ),
    "missing-thread": lambda at, v: f"unknown thread {v['thread']!r}",
    "summary-endpoints": lambda at, v: (
        "summary endpoints must name spoken turns in one thread"
    ),
    "summary-order": lambda at, v: (
        "summary must cover at least two messages in thread order"
    ),
    "reanchor-thread": lambda at, v: "reanchor needs an open anchored thread",
    "reanchor-section": lambda at, v: (
        "reanchor must retain the thread's surviving section or detach it"
    ),
    "unknown-content-version": lambda at, v: (
        f"{v['version']!r} is not a content version of agent message {v['message']!r}"
    ),
    # An undo (`events.UndoReading`): `undoes` names the gesture, `target` its kind.
    "unknown-undo": lambda at, v: f"unknown undoes {v['undoes']!r}",
    "foreign-gesture": lambda at, v: (
        f"{v['target']} {v['undoes']} is not the user's own gesture"
    ),
    "withdrawn-gesture": lambda at, v: f"{v['undoes']} has already been taken back",
    "said-message": lambda at, v: (
        f"{v['target']} {v['undoes']} is not a reaction; a message with words in it"
        " is said rather than unsaid"
    ),
    "answered-reaction": lambda at, v: (
        f"reaction {v['undoes']} has a reply or task attached; continue in its thread"
    ),
    "resolved-reaction": lambda at, v: (
        f"reaction {v['undoes']} stands on a resolved thread"
    ),
    "unundoable": lambda at, v: (
        f"{v['target']} events cannot be taken back (the kinds that can are"
        f" {', '.join(v['undoable'])} and a reaction)"
    ),
    "absorbed-move": lambda at, v: (
        f"move {v['undoes']} was made on r{v['revision']}, and a later revision's"
        " markup now places its unit; move it again instead"
    ),
    # A to-do, a start and an ending (`tasks.task_error`, `work.widget_seat_error`).
    "progress-parent": lambda at, v: (
        f"this progress line replies to {v['parent']!r} but starts an update you owe"
        f" no reply to {v['parent']!r} for; it may already be answered"
    ),
    "not-a-widget": lambda at, v: f"{v['widget']!r} is not a widget on this page",
    "not-an-element": lambda at, v: f"{v['element']!r} is not an element on this page",
    "hidden-widget": lambda at, v: (
        f"{v['widget']} no longer shows on the page: a decision in the log retired it"
        " or left it empty; open the to-do on another element or on `page`"
    ),
    "quoted-seat": lambda at, v: (
        f"{v['widget']} is quoted exhibit content, not a live page widget"
    ),
    "no-work-seat": lambda at, v: (
        f"{v['widget']} has no work seat; its widget declares no x-work and it holds"
        " no unsettled action"
    ),
    "duplicate-obligation": lambda at, v: (
        f"{v['widget']!r} already has obligation {v['obligation']!r}; use that obligation instead of"
        " opening duplicate work"
    ),
    "plan-depth": lambda at, v: (
        f"plan step {v['step']!r} is at depth {v['depth']}, more than one below the"
        " step before it; the first step is at depth 0 and each step is at most one"
        " deeper than the one above"
    ),
    "unknown-plan-item": lambda at, v: (
        f"{v['item']!r} names no to-do or obligation on this page; name an id `leaf task"
        " open` printed or an obligation id from `leaf page state`, or write a plain step"
        " with a title and state"
    ),
    "unowed-start": lambda at, v: (
        f"{v['item']!r} is neither an open to-do of yours nor an update you owe an"
        " answer to; start the id a delivered update or `leaf task create` gave you"
    ),
    "widget-obligation": lambda at, v: (
        f"{v['todo']!r} is answered by its widget's state, so retire it in the document"
    ),
    "users-question": lambda at, v: (
        "the user's message or settling reaction answers a question asked in words"
    ),
    "ended-obligation": lambda at, v: (
        f"obligation {v['todo']!r} is already {v['status']}"
    ),
    "failed-question": lambda at, v: (
        "a question asked in words ends `done` when the user answered it elsewhere,"
        " or `dropped` when it no longer applies"
    ),
    "ended-todo": lambda at, v: f"to-do {v['todo']!r} has already ended ({v['state']})",
    "todo-execution": lambda at, v: (
        f"to-do {v['todo']!r} was last started by "
        + (
            f"session {v['session']!r}"
            if v["session"] is not None
            else "a sessionless command"
        )
        + f" (start {v['start']!r}); start it with `leaf task start`"
        " before ending it from another session"
    ),
    "unknown-todo": lambda at, v: f"unknown to-do {v['todo']!r}",
    "agents-todo": lambda at, v: (
        f"to-do {v['todo']!r} is the agent's; the user ends only a to-do on them"
    ),
    # What other commands note beside their result (`note`). `page open` over
    # updates it still owes an answer, each named by the command that answers it:
    "page-open-owes": lambda at, v: (
        f"{len(v['answers'])} user update{'s' if len(v['answers']) != 1 else ''} with"
        f" no answer ({'; '.join(v['answers'])}); opening the page does not answer them"
    ),
    # `delivery ack` of a delivery an earlier turn already picked up
    # (`delivery.earlier_pickup`), with the answers its updates still owe:
    "delivery-repeated": lambda at, v: (
        f"an earlier turn already picked up delivery {v['delivery']}, so don't redo"
        " the work that turn did. "
        + (
            f"Still unanswered: {'; '.join(v['answers'])}."
            if v["answers"]
            else "None of its updates still owes an answer."
        )
    ),
    # A re-vendor a command naming the page made (`vendoring.renew_layer`), and the
    # service it held down (`hosting.restarting_server`).
    "unready-revendor": lambda at, v: (
        f"re-vendored {v['page']}, but index.html will not activate until"
        " `leaf page check` passes:\n" + "\n".join(f"  - {e}" for e in v["errors"])
    ),
    "revendor-refused": lambda at, v: (
        f"{v['page']} needs a re-vendor this Leaf could not make: {v['error']}"
    ),
    "server-stays-stopped": lambda at, v: (
        f"{v['page']}'s server stays stopped; `leaf server start {v['page']}` serves"
        " it again."
    ),
    "server-unowned": lambda at, v: (
        f"{v['page']}'s server has no live session owner, so it stays stopped;"
        f" `leaf server start {v['page']}` serves it for this one."
    ),
    "stopped-while-revendored": lambda at, v: (
        f"{v['page']}'s server was stopped while it was re-vendored, so it stays"
        " stopped."
    ),
    # A server just started (`hosting.started_server`).
    "loopback-only": lambda at, v: (
        "the URL reaches only this machine; re-serve with --host NAME for a user"
        " elsewhere"
    ),
    # A native file watch the kernel refused (`file_changes`), which polls instead.
    "watch-limit": lambda at, v: (
        f"the kernel has no native file watch left ({v['limit']} is reached), so"
        f" this process polls {', '.join(v['roots'])} instead and notices changes"
        " later"
    ),
    # A `leaf wait` (`session.Watch`, `session.read_watch_pass`): a server it brought
    # back or could not, and why it ended.
    "server-restarted": lambda at, v: (
        f"{v['page']}: server had died; restarted at {v['url']}"
    ),
    "revive-refused": lambda at, v: (
        f"{v['page']}: server had died and did not start again: {v['error']}"
    ),
    "server-down": lambda at, v: (
        f"{v['page']}: server is not running; restart it with"
        f" `leaf server start {v['page']}`"
    ),
    "not-owned": lambda at, v: (
        f"stopped watching {', '.join(v['pages'])}: this session no longer owns"
        + (" it" if len(v["pages"]) == 1 else " them")
    ),
    "nothing-to-watch": lambda at, v: (
        "nothing to watch: "
        + (
            f"{v['page']} is not claimed by this session"
            if v["page"]
            else "no page named and none claimed by this session"
        )
    ),
    "pages-idle": lambda at, v: (
        f"the {'page' if len(v['pages']) == 1 else 'pages'} closed;"
        f" {', '.join(v['pages'])} {'is' if len(v['pages']) == 1 else 'are'} idle"
    ),
    "wait-active": lambda at, v: (
        f"another `leaf wait` is already active for {v['target']}"
    ),
    "watch-taken-over": lambda at, v: (
        "a watch between turns took over this session's pages"
    ),
    # The thread and task commands' refusals (`thread`, `todos.cmd_create`), before or
    # beside the append door's. `held` is what the log holds a refused id as
    # (`validation.admission.logged_id`), and `answer` the command that answers an
    # owed update (`activity.answer_command`).
    "unknown-comment": lambda at, v: (
        f"unknown message id {v['name']!r}"
        + (f"; {v['held']}" if v.get("held") else "")
        + f"; known: {_json(v['known'])}"
    ),
    "widget-not-thread": lambda at, v: (
        f"{v['name']} is a widget on the page, not a thread"
    ),
    "unknown-subject": lambda at, v: (
        f"{v['subject']!r} names no thread, widget or element on this page; `{v['page']}`"
        " names the page as a whole"
    ),
    "invalid-source": lambda at, v: (
        f"cannot {v['operation']} while index.html is invalid: {v['error']}"
    ),
    "unanchorable": lambda at, v: (
        f"can't anchor in revision r{v['revision']}: {v['error']}"
        + (
            f"; {v['held']}, while `--section` takes an element id the page's markup"
            " declares"
            if v.get("held")
            else ""
        )
    ),
    "redeclared-answer": lambda at, v: (
        f"{v['message']!r} already answered this with a different declaration; ask or"
        " promise in a new message with `leaf thread reply`"
    ),
    "unowed-reply": lambda at, v: (
        f"event {v['event']!r} takes no reply; "
        + (v.get("held") or f"this page's log holds no event {v['event']!r}")
    ),
    "superseded-reply": lambda at, v: (
        f"event {v['event']!r} no longer requires a reply to {v['parent']!r}; "
        + (v.get("held") or "read the current delivery or thread state")
    ),
    "reserved-answer": lambda at, v: (
        f"event {v['event']!r} is answered by this turn's messages; "
        + (
            "failure receipts wait for this turn to release the answer; answer in your"
            f" final message or with {v['command']}"
            if v["failure"]
            else f"use {v['command']} to commit an explicit answer"
        )
    ),
    "owed-response": lambda at, v: (
        f"thread {v['thread']!r} currently requires a response; {v['answer']} answers"
        " it"
    ),
    "not-a-reply": lambda at, v: (
        f"response {v['reference']!r} requires {v['answer']}, not a reply"
    ),
    "ephemeral-content": lambda at, v: (
        "--ephemeral is for progress text; it cannot ask the user, open a to-do, carry"
        " widgets, report failure, or move the thread"
    ),
    "detach-with-target": lambda at, v: (
        "--detach cannot be combined with --quote, --section, or --part"
    ),
    "held-anchor": lambda at, v: (
        f"thread {v['thread']!r} holds the widget its first comment was sent from, so"
        " its anchor cannot be moved or detached"
    ),
    "no-anchor": lambda at, v: (
        f"thread {v['thread']!r} has no current anchor to detach"
    ),
    "undeclared-answer": lambda at, v: (
        "say what the answer leaves: --done when it delivers what was asked, --todo"
        " TITLE when it promises work it doesn't deliver, or --obligation when it needs"
        " the user's next move (a widget in --markup may also ask)"
    ),
    "detail-field": lambda at, v: f"detail fields are name=value, got {v['field']!r}",
}

# What a browser shows the person whose gesture a refusal turned down, where the
# agent's words name internals that person never sees (`Rejected.user`).
_USER = {
    "stale-move": "The page changed while I moved this; move it again.",
    "stale-edit": "The message changed while I edited it; edit it again.",
}

_CONSOLE = {
    "console-error",
    "console-warning",
    "page-exception",
    "window-error",
    "resize-loop",
    "upgraded-early",
    "ready-early",
    "main-unlaid",
}


def _words(finding: Finding) -> str:
    return _TEXT[finding.code](finding.at, finding.values)


class Rejected(Refused):
    """A refusal of what a check found: the words list the findings under `heading`,
    or are the findings' own where there is none, and `findings` keeps the records
    for a reader that wants the facts. A browser shows the person whose gesture one
    finding refuses its `_USER` words, where its code has them."""

    def __init__(self, findings: list[Finding], heading: str | None = None):
        findings = list(findings)
        super().__init__(
            f"{heading}:\n" + "\n".join(f"  - {f}" for f in findings)
            if heading
            else "\n".join(map(str, findings))
        )
        if not heading and len(findings) == 1 and findings[0].code in _USER:
            self.user = _USER[findings[0].code]
        self.findings = findings
