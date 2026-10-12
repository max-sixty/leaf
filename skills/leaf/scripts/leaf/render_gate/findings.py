"""A finding: one thing a check found, as a record its readers take fields from.

Every check behind `page check` and `package check --render` reports through this one
type: the markup checks, the page-code run, the render gate in each color scheme and
viewport, its width sweep and advice, and the widget quality report. Each is produced
where it is detected, the browser probes included, which return records rather than
sentences, and its words are written here and nowhere else. The command boundary
prints `str(finding)` for a reader and `finding.json()` for `page check --json`; every
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

A record compares by all of these, so two readings of one fault in one place are one
finding and the same fault at another width is another.
"""

import json
from dataclasses import dataclass, field, replace

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
        return text

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


def _size(box: dict) -> str:
    return f"{round(box['width'])}x{round(box['height'])}"


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
        " anchored here would outline nothing and the Question walk would travel to"
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
    # The markup checks.
    "markup": lambda at, v: v["text"],
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
