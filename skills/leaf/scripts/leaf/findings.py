"""A finding: one thing a check found, as a record its readers take fields from.

Every check behind `page check` and `package check` reports through this one type: the
registry's validation, the markup checks, the page-code run, the render gate in each
color scheme and viewport, its width sweep and advice, and the widget quality report.
The suite's browser fixture reports through it too: what the browser said, and what its
health sensors (`tests/*_watch.js`) found. So does every gate that refuses one event at
the append door (`event_contracts.admitted_event`). A refusal raised with what a check
found (`Rejected`, such as `RegistryError` or `event_log.EventRefused`) carries the
records, so a command that reports it reads them from it. Each is produced where it is
detected, the browser probes and sensors included, which return records rather than
sentences, and its words are written here and nowhere else. The command boundary prints
`str(finding)` for a reader and `finding.json()` for `--json`, as the event door's
refusal answer carries it, and a failing test prints the words; every other reader, the
gate's retry policy and the suite among them, reads the fields.

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
    if kind == "unreadable":
        return f"could not read visual parts: {problem['error']}"
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


# What the layer does with a word a widget declares from one of its lists, where the
# word is on it (`instances.DECLARED_WORDS`).
_HONORED = {
    "x-language": "a language this page's layer speaks",
    "x-tone": "a tone this page's layer paints",
}


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
        f"widgets rendered with no usable size: {_json(v['boxes'])}"
    ),
    "unmarkable": lambda at, v: (
        f"{at} shows {v['w']}x{v['h']}px of words and offers no box to mark: it draws"
        " none of its own and no element inside it draws one either, so a comment"
        " anchored here would outline nothing and the On me walk would travel to"
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
        f"{at} wears data-lf-state={_json(v['mark'])} where the log records "
        + (f"`{v['outcome']}`" if v["outcome"] else "no decision")
        + " — the mark is the layer's paint of a logged decision, so a module may say"
        " only what the log decided"
    ),
    "retired-slot": lambda at, v: (
        f"{at} settled `{v['outcome']}` and its <{v['slot']}> still shows"
        f" {_json(v['words'])} — those words have left the page's reading, so"
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
        f"{at} puts {_json(v['words'])} under .lf-ui, where no comment can reach it"
    ),
    "form-control-words": lambda at, v: (
        f"{at} says {_json(v['words'])} inside a form control, where no selection"
        " can reach it"
    ),
    "apparatus-among-authored": lambda at, v: (
        f"{at} stands among the children of {v['parent']}"
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
    # A layer this Leaf can neither serve nor write under (`layer.incompatible_layer`).
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
        f" <body>; found {_json(_outside_main(v['content']))}"
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
        f" {_json(v['known'])}"
    ),
    "meta-content": lambda at, v: (
        f'<meta name="{v["name"]}"> (line {v["line"]}): content must be one of'
        f" {_json(v['allowed'])}, found {v['found']!r}"
    ),
    "allocation-value": lambda at, v: (
        f"{_bearing(at, v, _json(v['value']))} has an invalid value; expected "
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
        " runtime's to write, whether or not it writes this name today"
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
    "empty-ask-context": _ask_context,
    "ask-context-headings": lambda at, v: (
        f"{_line(at, v)}: an ask context must have exactly one direct heading,"
        f" found {_json(v['headings']) if v['headings'] else 'none'}"
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
        f" {_json(v['known'])}"
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
    "dropped-ids": lambda at, v: (
        f"ids dropped from revision r{v['revision']}: {_json(v['ids'])}"
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
    "undeclared-event-kind": _declared(
        lambda v: (
            f"$events.handling names {v['kind']!r}, which $events.kinds does"
            " not declare"
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
            "$keys must carry a description and one paragraph per x- key the"
            f" lint admits — missing {_json(v['missing'])}, unadmitted"
            f" {_json(v['unadmitted'])}"
        )
    ),
    "idiom-selector": _declared(
        lambda v: f"idiom {v['selector']!r} selector cannot be matched: {v['error']}"
    ),
    "idiom-fields": _declared(
        lambda v: (
            f"idiom {v['selector']!r} must carry a non-empty description and"
            " x-example, with optional x-instructions and " + ", ".join(v["marks"])
        )
    ),
    "idiom-value": _declared(
        lambda v: (
            f"idiom {v['selector']!r} declares"
            f" {v['key']}={_json(v['value'])}; the value must satisfy its $keys"
            " declaration"
        )
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
    "initial-and-prepaint": _declared(
        lambda v: "declares both x-initial and x-prepaint"
    ),
    "prepaint-as": _declared(
        lambda v: (
            f"x-prepaint names <{v['as']}>, which declares no x-prepaint markup"
            " of its own"
        )
    ),
    "prepaint-upgrade": _declared(
        lambda v: (
            "x-prepaint requires x-upgrade: true, since only the widget's"
            " module takes it out"
        )
    ),
    "prepaint-shape": _declared(
        lambda v: (
            "x-prepaint must be one element written as the parser reads it"
            " back, every element closed"
        )
    ),
    "prepaint-element": _declared(
        lambda v: f"x-prepaint may not hold <{v['element']}>"
    ),
    "prepaint-marks": _declared(
        lambda v: (
            f"x-prepaint may carry no id and no data-lf- attribute (<{v['element']}>)"
        )
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
    "ask-context-id": _declared(lambda v: "x-ask-context does not require an id"),
    "ask-context-prose": _declared(
        lambda v: "x-ask-context must admit prose around the ask it frames"
    ),
    "data-contract": _declared(
        lambda v: (
            f"x-data input `{v['input']}` names unknown contract {v['contract']!r}"
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
    "predicate-not-flag": _declared(
        lambda v: _predicate(
            v, f"as {_json(v['value'])}, but that attribute is not a flag"
        )
    ),
    "predicate-flag": _declared(
        lambda v: (
            f"{v['key']} tests flag `{v['attr']}` as {_json(v['value'])};"
            " a flag is there or it isn't"
        )
    ),
    "predicate-enum": _declared(
        lambda v: _predicate(
            v, f"at {_json(v['value'])}, which its own enum does not admit"
        )
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
    # Its interactions: local work, its ask, and the state its verbs write.
    "work-inline": _declared(
        lambda v: "declares x-work but is inline; local work chrome needs a block slot"
    ),
    "work-content": _declared(
        lambda v: (
            f"declares x-work but x-content is {v['content']}; generated local"
            " chrome may only join authored prose"
        )
    ),
    "awaits-unanswered": _declared(
        lambda v: "x-awaits local ask declares no `answered` condition"
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
    "awaits-retired": _declared(
        lambda v: (
            f"x-awaits retires with `{v['flag']}`, but its `when` does not"
            f" require `{v['flag']}` absent"
        )
    ),
    "awaits-blanket": _declared(
        lambda v: (
            f"x-awaits blanket answer `{v['outcome']}` is not an outcome of a"
            " deciding verb that answers its ask"
        )
    ),
    "unoverruled": _declared(
        lambda v: (
            "declares agent-written x-state verbs"
            f" {_json(v['verbs'])} but not the boolean `overruled` attribute a"
            " version overrules a report in force with"
        )
    ),
    "unrestated": _declared(
        lambda v: (
            "declares user x-state verbs that fold on the widget but not the"
            " boolean `restated` attribute a version retracts a decision with"
        )
    ),
    "reserved-resolves": _declared(
        lambda v: (
            "declares attribute `resolves`, a reserved name (the thread an"
            " answer to its ask closes), but originates no local ask"
        )
    ),
    "verb-detail-schema": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` has an invalid detail schema: {v['reason']}"
        )
    ),
    "verb-detail-type": _declared(
        lambda v: f"x-state verb `{v['verb']}` detail schema must declare an object"
    ),
    "verb-detail-open": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` detail schema must state"
            " additionalProperties: false — a verb carries only the detail keys it"
            " declares"
        )
    ),
    "verb-detail-keys": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` detail schema declares"
            f" {_json(v['keys'])}; a detail states its type, properties, required"
            " and additionalProperties and nothing else, so the keys a verb can carry"
            " are the ones it names"
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
            f"x-state verbs {_json(v['verbs'])} all declare detail field"
            " `outcome`, a reserved name only one deciding verb may carry"
        )
    ),
    "deciding-verb": _declared(
        lambda v: (
            f"x-state verb `{v['verb']}` declares detail field `outcome`, a"
            " reserved name: the deciding verb folds by widget, is written by the user,"
            " and requires `outcome` as a string enum"
        )
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
    # A sign-off.
    "unstamped-version": lambda at, v: f"v{v['version']} is not a stamped version",
    "not-sign-off": lambda at, v: (
        f'v{v["version"]} does not declare <meta name="lf-review" content="sign-off">,'
        " so it has no approval to record"
    ),
    "unanswered-asks": lambda at, v: (
        f"v{v['version']} still has unanswered widget asks: {', '.join(v['asks'])}"
    ),
    # An action or a report, against its widget's declaration.
    "unknown-sender": lambda at, v: (
        f"unknown report widget {v['widget']!r} in revision r{v['revision']} — reports"
        " name page widgets only; thread markup is frozen, so no version could ever"
        " answer a report made there"
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
        f"reaction {v['undoes']} has been answered; withdraw it in the thread the"
        " answer opened"
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
        "progress must take in hand the reply input addressed by its parent"
    ),
    "not-a-widget": lambda at, v: f"{v['widget']!r} is not a widget on this page",
    "not-an-element": lambda at, v: f"{v['element']!r} is not an element on this page",
    "hidden-widget": lambda at, v: (
        f"{v['widget']} is not visible under the page's outcomes in force"
    ),
    "quoted-seat": lambda at, v: (
        f"{v['widget']} is quoted exhibit content, not a live page widget"
    ),
    "no-work-seat": lambda at, v: (
        f"{v['widget']} has no work seat; its widget declares no x-work and it holds"
        " no unsettled action"
    ),
    "duplicate-ask": lambda at, v: (
        f"{v['widget']!r} already has ask {v['ask']!r}; use that ask instead of"
        " opening duplicate work"
    ),
    "unowed-start": lambda at, v: (
        f"{v['item']!r} is neither an open to-do of yours nor an update you owe an"
        " answer to; start the id a delivered update or `leaf task open` gave you"
    ),
    "approval-ask": lambda at, v: (
        f"ask {v['todo']!r} requires the user's approval of v{v['version']}; it ends"
        " at the page's Approval control"
    ),
    "widget-ask": lambda at, v: (
        f"{v['todo']!r} is a widget ask; its source owns the answer, so retire it in"
        " the document"
    ),
    "users-prose-ask": lambda at, v: (
        "the user's reply or settling reaction answers a prose ask"
    ),
    "ended-ask": lambda at, v: f"ask {v['todo']!r} is already {v['status']}",
    "failed-prose-ask": lambda at, v: (
        "a prose ask ends `done` when the user answered it elsewhere, or `dropped`"
        " when it no longer applies"
    ),
    "ended-todo": lambda at, v: f"to-do {v['todo']!r} has already ended ({v['state']})",
    "todo-execution": lambda at, v: (
        f"to-do {v['todo']!r} was last started by "
        + (
            f"session {v['session']!r}"
            if v["session"] is not None
            else "a sessionless command"
        )
        + f" (start {v['start']!r}); take it in hand with `leaf task start`"
        " before ending it from another session"
    ),
    "unknown-todo": lambda at, v: f"unknown to-do {v['todo']!r}",
    "agents-todo": lambda at, v: (
        f"to-do {v['todo']!r} is the agent's; the user ends only a to-do on them"
    ),
    # The thread and task commands' refusals (`thread`, `tasks.cmd_open`), before or
    # beside the append door's. `held` is what the log holds a refused id as
    # (`validation.admission.logged_id`), and `answer` the command that answers an
    # owed update (`activity.answer_command`).
    "unknown-comment": lambda at, v: (
        f"unknown comment id {v['name']!r}"
        + (f"; {v['held']}" if v.get("held") else "")
        + f"; known: {_json(v['known'])}"
    ),
    "widget-not-thread": lambda at, v: (
        f"{v['name']} is a widget on the page, not a thread"
    ),
    "unknown-subject": lambda at, v: (
        f"{v['subject']!r} names no widget or element on this page; `{v['page']}`"
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
        f"event {v['event']!r} no longer requires a reply to {v['to']!r}; "
        + (v.get("held") or "read the current delivery or thread state")
    ),
    "reserved-answer": lambda at, v: (
        f"event {v['event']!r} is answered by this turn's messages; "
        + (
            "failure receipts wait for this turn to release the answer; answer in your"
            f" final message or use {v['command']} without `--failure`"
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
        f"thread {v['thread']!r} holds the command goal named by its opening comment,"
        " so its anchor cannot be changed"
    ),
    "no-anchor": lambda at, v: (
        f"thread {v['thread']!r} has no current anchor to detach"
    ),
    "widget-ask-markup": lambda at, v: (
        "--ask is for a prose ask; reply markup already declares a widget ask"
        f" ({', '.join(f'<{tag}>' for tag in v['tags'])})"
    ),
    "detail-field": lambda at, v: f"detail fields are name=value, got {v['field']!r}",
}

# What a browser shows the person whose gesture a refusal turned down, where the
# agent's words name internals that person never sees (`Rejected.user`).
_USER = {
    "stale-move": "The page changed while you moved this; move it again.",
    "stale-edit": "The message changed while you edited it; edit it again.",
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
