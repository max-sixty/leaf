"""A finding: one thing a check found, as a record its readers take fields from.

Every check behind `page check` and `package check --render` reports through this one
type: the markup checks, the page-code run, the render gate in each color scheme and
viewport, its width sweep and advice, and the widget quality report. The suite's
browser fixture reports through it too: what the browser said, and what its health
sensors (`tests/*_watch.js`) found. Each is produced where it is detected, the browser
probes and sensors included, which return records rather than sentences, and its words
are written here and nowhere else. The command boundary prints `str(finding)` for a
reader and `finding.json()` for `--json`, and a failing test prints the words; every
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
id where the words name one, and keeps the line it opens on in `values`.

A record compares by all of these, so two readings of one fault in one place are one
finding and the same fault at another width is another.
"""

import json
from dataclasses import dataclass, field, replace

from leaf.refusals import Refused
from leaf.registry.schema import json_value

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
    if kind in ("unreadable", "unrevealable"):
        verb = "read" if kind == "unreadable" else "reveal"
        return f"could not {verb} visual parts: {problem['error']}"
    said = {
        "unregistered-parts": "did not register declared parts",
        "unadmitted-parts": "registered parts its prefixes do not admit",
        "unlisted-parts": "leaves nameable parts unlisted",
        "unrevealed-parts": "did not reveal declared parts",
    }[kind]
    return f"{said} {', '.join(problem['parts'])}"


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
        f"structure {json_value(v['shown'])} where the file reads "
        f"{json_value(v['expected'])}"
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
        + " — an identifier in <code> breaks inside its cell; a column fewer, or a"
        " shorter word in the widest, gives the rest the measure"
    )


def _line(at: str, v: dict) -> str:
    """An element of the author's file, as they find it: its name and its line."""
    return f"{at} (line {v['line']})"


def _bearing(at: str, v: dict, value: str) -> str:
    """The element `at` names, written with the attribute the finding is about and
    its `value` as the words quote it."""
    return _line(f"{at[:-1]} {v['attr']}={value}>", v)


def _quoted(value: str) -> str:
    return f'"{value}"'


def _conditions(lacks: dict) -> str:
    """The `x-awaits.when` conditions a widget never met (`instances.unasked`)."""
    return " and ".join(
        " or ".join(
            f"{attr} is {'present' if value else 'absent'}"
            if isinstance(value, bool)
            else f"{attr}={json_value(value)}"
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
    expected = ", ".join(
        f"{key}={json_value(value)}" for key, value in v["where"].items()
    )
    found = (
        ", ".join(f"{key}={json_value(value)}" for key, value in v["found"].items())
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


def _ask_context(at: str, v: dict) -> str:
    widgets = "; ".join(
        f"{_line(w['at'], w)} asks only where {_conditions(w['lacks'])}"
        for w in v["widgets"]
    )
    return f"{_line(at, v)}: an ask context registers no ask: " + (
        widgets or "it holds no widget that declares x-awaits"
    )


def _outside_main(content: list[dict]) -> list[str]:
    return [
        f"text in <{c['tag']}> at line {c['line']}"
        if c["text"]
        else f"<{c['tag']}> at line {c['line']}"
        for c in content
    ]


def _pinned(v: dict) -> str:
    revisions = v["revisions"]
    return (
        "pinned revision"
        + ("s " if len(revisions) > 1 else " ")
        + ", ".join(f"r{revision}" for revision in revisions)
        + f" cannot render this thread markup: {Finding.loads(v['finding'])}"
    )


# What the layer does with a word a widget declares from one of its lists, where the
# word is on it (`instances.DECLARED_WORDS`).
_HONORED = {
    "x-language": "a language this page's layer speaks",
    "x-tone": "a tone this page's layer paints",
}


def _size(box: dict) -> str:
    return f"{round(box['width'])}x{round(box['height'])}"


def _box(box: dict) -> str:
    return f"{round(box['left'])},{round(box['top'])} {_size(box)}"


def _by(v: dict) -> str:
    """How far a shift sensor's node moved, and what else its frame moved."""
    left, top = v["by"]
    beside = f"; the same frame moved {', '.join(v['beside'])}" if v["beside"] else ""
    return f" by ({left}, {top})px{beside}"


def _shift_evidence(v: dict) -> str:
    return f"\nshift evidence: {json.dumps(v['evidence'], ensure_ascii=False)}"


# The words for each code, from the finding's `at` and `values`. A console code's
# words are what the console said; read by the gate in a color scheme, beside findings
# of its own, it says "console: " first.
_TEXT = {
    # What the browser's console and the page's window reported.
    "console-error": lambda at, v: v["text"],
    "console-warning": lambda at, v: f"warning: {v['text']}",
    "failed-load": lambda at, v: f"{v['status']} {v['url']}",
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
    # The suite's health sensors (`tests/*_watch.js`), each naming a node as the
    # sensors do (`textarea#field`).
    "moved-without-input": lambda at, v: (
        f"{v['node']} moved without input{_by(v)}{_shift_evidence(v)}"
    ),
    "typing-moved": lambda at, v: (
        f"typing in {v['field']} moved {v['node']}{_by(v)}; the key found"
        f" {_box(v['found'])}, the frame painted {_box(v['painted'])}"
        f"{_shift_evidence(v)}"
    ),
    "shift-watch-missed": lambda at, v: (
        f"shift watch missed a change to {v['node'] or "the page's nodes"}"
        f" ({', '.join(v['changed'])})"
        + (
            f" and to {v['others']} other node{'' if v['others'] == 1 else 's'}"
            if v["others"]
            else ""
        )
        + ": a source of change is missing from the sensor's announcements"
        ' (shift_watch.js, "Unchanged frames")'
    ),
    "unchanged-write": lambda at, v: (
        f"unchanged write: children of {v['node']}"
        if v["what"] == "children"
        else f"unchanged write: {v['what']} on {v['node']}"
    ),
    "words-left-screen": lambda at, v: (
        "typed words left the screen without a key or press:"
        f" {json.dumps(v['words'], ensure_ascii=False)} in {v['place']}"
    ),
    # The gate's own run, where it could not read the page.
    "gate-failed": lambda at, v: (
        f"the browser gate failed while running its probe module: {v['error']}"
    ),
    "probe-failed": lambda at, v: f"the browser probe module failed: {v['error']}",
    "no-banner": lambda at, v: (
        "the runtime never injected its banner — "
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
        f"widgets rendered with no usable size: {json_value(v['boxes'])}"
    ),
    "unmarkable": lambda at, v: (
        f"{at} shows {v['w']}x{v['h']}px of words and offers no box to mark: it draws"
        " none of its own and no element inside it draws one either, so a comment"
        " anchored here would outline nothing and the Questions walk would travel to"
        " the top of the page. Put the words in an element that takes a box"
    ),
    "undeclared-shadow": lambda at, v: (
        "shadow roots the registry doesn't declare (an undeclared root's words anchor"
        f" quotes astray; declare x-shadow): {', '.join(v['hosts'])}"
    ),
    "devtools-issue": lambda at, v: (
        f"DevTools issue {v['issue']}"
        + (f" at {at}" if at else "")
        + (
            f" ({', '.join(f'{k}={json_value(x)}' for k, x in v['details'])})"
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
        f"{at} wears data-lf-state={json_value(v['mark'])} where the log records "
        + (f"`{v['outcome']}`" if v["outcome"] else "no decision")
        + " — the mark is the layer's paint of a logged decision, so a module may say"
        " only what the log decided"
    ),
    "retired-slot": lambda at, v: (
        f"{at} settled `{v['outcome']}` and its <{v['slot']}> still shows"
        f" {json_value(v['words'])} — those words have left the page's reading, so"
        " the user can select what no comment can anchor to; the layer hides a"
        " retired slot by default, so something in this family is showing it anyway"
    ),
    "render-threw": lambda at, v: (
        f"{at} renderState threw when the complete state was rendered a second time:"
        f" {v['error']}"
    ),
    "relative-render": lambda at, v: (
        f"{at} renderState is relative — rendering the same complete state changed"
        f" {', '.join(v['changed'])}. Render the supplied values without stepping"
        " from the DOM."
    ),
    # Geometry, read at the fixed viewports and across the sweep.
    "page-scrolls": lambda at, v: f"the page scrolls sideways by {v['past']}px",
    "outside-part": lambda at, v: (
        f"{at} stands {v['past']}px outside the {v['host']} it is part of"
    ),
    "past-column": lambda at, v: (
        f"{at} is set {v['past']}px past the column, out in the margin"
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
        f"{at} is drawn over {v['resident']}, which stands in the margin it grew into"
        " — the side that holds it gives no room"
    ),
    "clipped-out": lambda at, v: (
        f"{at} is drawn {v['past']}px outside {v['container']}, which does not show it"
    ),
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
    "painted-words": lambda at, v: (
        f'{at} paints {v["attr"]}="{v["value"]}" rather than saying it'
    ),
    "chrome-words": lambda at, v: (
        f"{at} puts {json_value(v['words'])} under .lf-ui, where no comment can"
        " reach it"
    ),
    "form-control-words": lambda at, v: (
        f"{at} says {json_value(v['words'])} inside a form control, where no selection"
        " can reach it"
    ),
    "apparatus-among-authored": lambda at, v: (
        f"{at} stands among the children of {v['parent']}"
    ),
    "unread-syntax": lambda at, v: (
        f"code styled {json_value(v['style'])} reads at {v['ratio']:.1f}:1 against the"
        " block it is set on"
    ),
    "covered-words": lambda at, v: (
        f"{at} draws {json_value(v['words'])} in the same place as {v['under']}'s"
        f" {json_value(v['covered'])}"
    ),
    # Advice: what the author decides.
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
        f"{at} draws {v['drawn']}px tall where its first paint "
        + (
            "reserves no height"
            if v["reserved"] is None
            else f"reserves {v['reserved']}px"
        )
        + f', so what follows it moves when it is drawn: state data-height="{v["drawn"]}"'
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
    "invalid-registry": lambda at, v: v["error"],
    "capture-failed": lambda at, v: v["error"],
    "sample-history": lambda at, v: v["error"],
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
        "paintable authored content must stay inside the one <main> directly under"
        f" <body>; found {json_value(_outside_main(v['content']))}"
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
    "async-script": lambda at, v: (
        f"<script async> (line {v['line']}) runs whenever it arrives, which can be"
        " before Leaf reads the page; leave async off"
    ),
    "parser-blocking-script": lambda at, v: (
        f"{_line(at, v)} runs while the page is still parsing, before Leaf reads it;"
        ' write inline JavaScript as <script type="module">, and load a classic script'
        " file with <script defer src>"
    ),
    "document-declaration": lambda at, v: (
        f"{_line(at, v)} declares something about the whole document, which delivery"
        " owns"
    ),
    "unknown-meta": lambda at, v: (
        f'<meta name="{v["name"]}"> (line {v["line"]}): unknown lf- meta; known:'
        f" {json_value(v['known'])}"
    ),
    "meta-content": lambda at, v: (
        f'<meta name="{v["name"]}"> (line {v["line"]}): content must be one of'
        f" {json_value(v['allowed'])}, found {v['found']!r}"
    ),
    "allocation-value": lambda at, v: (
        f"{_bearing(at, v, json_value(v['value']))} has an invalid value; expected "
        + (
            "a whole number of CSS pixels"
            if v["allowed"] is None
            else f"one of {', '.join(v['allowed'])}"
        )
    ),
    "css-unclosed": lambda at, v: (
        f"{v['sheet']}: {v['depth']} block(s) left open at end of file — every rule"
        " after the unclosed brace, this stylesheet's or a later layer's, lands inside"
        " its scope"
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
        f"duplicate ids (anchors need unique targets): {json_value(v['ids'])}"
    ),
    "spaced-ids": lambda at, v: (
        "ids containing whitespace, which HTML forbids in an id:"
        f" {json_value(v['ids'])}"
    ),
    "reserved-ids": lambda at, v: (
        "ids in the runtime's own lf- namespace (it coins lf-composer-quote there, and"
        f" points ARIA at them): {json_value(v['ids'])}"
    ),
    "event-shaped-ids": lambda at, v: (
        "ids shaped like the event ids the log mints (eight hex digits), which"
        f" commands would read as a message: {json_value(v['ids'])}"
    ),
    "reserved-markers": lambda at, v: (
        f"{at} at line {v['line']} wears the runtime's own markers"
        f" ({', '.join(v['markers'])}); the lf- and data-lf- namespaces are the"
        " runtime's to write, whether or not it writes this name today"
    ),
    "ids-taken-by-messages": lambda at, v: (
        f"ids already taken by message markup: {json_value(v['ids'])}"
    ),
    "ids-taken": lambda at, v: (
        f"ids already taken by the page or an earlier message: {json_value(v['ids'])}"
    ),
    # Widgets, against the registry that declares them.
    "unknown-widget": lambda at, v: (
        f"{_line(at, v)}: unknown widget — not in the vendored registry.json"
    ),
    "attribute-schema": lambda at, v: f"{_line(at, v)}: {v['reason']}",
    "not-member": lambda at, v: (
        f"{_line(at, v)}: must be a direct member of "
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
        f"{_line(at, v)}: admits only {json_value(v['admits'])} members, found"
        f" {json_value(v['found'])}"
    ),
    "loose-text": lambda at, v: (
        f"{_line(at, v)}: loose text between its members isn't allowed"
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
        + (json_value(v["body"]) if v["body"] else "nothing")
        + "; wrap several blocks in one <div> or <section>"
    ),
    "repeated-parts": lambda at, v: (
        f"{_line(at, v)}: visual part ids must be unique, repeated"
        f" {json_value(v['parts'])}"
    ),
    "needs-id": lambda at, v: (
        f"{_line(at, v)}: a matching {v['role']} instance requires an id"
    ),
    "empty-ask-context": _ask_context,
    "ask-context-headings": lambda at, v: (
        f"{_line(at, v)}: an ask context must have exactly one direct heading,"
        f" found {json_value(v['headings']) if v['headings'] else 'none'}"
    ),
    "ask-context-heading-first": lambda at, v: (
        f"{_line(at, v)}: an ask context's direct heading must be its first"
        " content, found "
        + ("text" if v["first"] == "#text" else f"<{v['first']}>")
        + " first"
    ),
    "unknown-word": lambda at, v: (
        f"{_bearing(at, v, _quoted(v['value']))}: not {_HONORED[v['declares']]} —"
        " known:"
        f" {json_value(v['known'])}"
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
    "pinned-unrenderable": lambda at, v: _pinned(v),
    "pinned-vocabulary": lambda at, v: (
        "thread markup must use vocabulary shared by the active registry and every"
        " pinned revision; otherwise ask with --text (and --ask for a reply)"
    ),
    "sample-loop": lambda at, v: (
        f"sample {json_value(v['samples'])} selects thread {v['thread']!r}, which"
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
    "dropped-ids": lambda at, v: (
        f"ids dropped from revision r{v['revision']}: {json_value(v['ids'])}"
    ),
    "measurement-lag": lambda at, v: (
        f"measurement behind its source: {_line(at, v)} pins source {v['source']!r}"
        f" run {v['run']}, but that source now holds run {v['current_run']}"
    ),
    "unreadable-data": lambda at, v: f"data source unreadable: {v['error']}",
    "relocated-anchor": lambda at, v: (
        f"open thread {v['thread']} anchor no longer resolves; activation will move it"
        " to "
        + (
            f"section {v['section']!r}"
            if v["section"] is not None
            else "a detached thread"
        )
    ),
    # The package check's refusal.
    "package": lambda at, v: v["text"],
    "leaf-version": lambda at, v: (
        f"Leaf {v['vendored']} vendored this page; this is Leaf {v['running']}. If the"
        f" page misbehaves, `leaf page init {v['page']}` re-vendors it."
    ),
    # The widget quality report, for a widget's author.
    "unreadable-examples": lambda at, v: (
        f"widget examples could not be drawn: {v['error']}"
    ),
    "example": lambda at, v: f"{at} example: no worked example shows it",
    "keeps-first-box": lambda at, v: (
        f"{at} keeps-first-box: first painted {_size(v['first'])},"
        f" {_size(v['now'])} once presented"
    ),
    "shows-context-keys": lambda at, v: (
        f"{at} shows-context-keys: {v['command']} declares context keys and no"
        " bindingBadge, so its key works with nothing on the page showing it; lend"
        " the command a face, or request a corner badge with bindingBadge: null"
    ),
    "grows-with-content": lambda at, v: (
        f"{at} grows-with-content: {v['box']} holds {v['height']}px and scrolls"
        " inside it; let it grow with its content, or declare --lf-holds-height: 1"
        " where the task needs its own scroll"
    ),
}

_CONSOLE = {
    "console-error",
    "console-warning",
    "failed-load",
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
    """A gate's refusal of what it found: the words list the findings under
    `heading`, and `findings` keeps the records for a reader that wants the facts."""

    def __init__(self, heading: str, findings: list[Finding]):
        super().__init__(f"{heading}:\n" + "\n".join(f"  - {f}" for f in findings))
        self.findings = findings
