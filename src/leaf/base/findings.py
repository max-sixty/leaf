"""A finding: one thing a check found, or a command says, as a record its readers take
fields from.

Every check behind `page check` and `package check` reports through this one type: the
registry's validation, the markup checks, a sample's initial history, the capture of a
revision, the page-code run, the render gate, its width sweep and advice, and the
widget quality report. The suite's browser fixture
reports through it too: what the browser said, and what its health sensors
(`tests/*_watch.js`) found. So does every gate that refuses one event at the append
door (`event_contracts.admitted_event`). A refusal raised with what a check found
(`Rejected`, such as `RegistryError`, `ArtifactError` or `event_log.EventRefused`)
carries the records, so a command that reports it reads them from it. So does every
note a command gives beside its result, such as why a `leaf wait` ended. Each is
produced where it is detected, the browser probes and sensors included, which return
records rather than sentences, and its words are written here and nowhere else. A
command prints `finding.json()`, its words as `text`, in its result's `findings`
(`note`), as the event door's refusal answer carries it, and a failing test prints
the words; every
other reader, the gate's retry policy and the suite among them, reads the fields.

- `code` names what was found, and decides the words and whether it refuses
  (`_TEXT`).
- `at` names the element it concerns as `render-checks/locate.js` does (`<div id=x>`,
  or `<p> in <section id=x>` where the element has no id of its own), or is empty.
- `values` are what the check measured, as JSON.
- `widths` says where a swept reading stands: the widths its run spans, lowest and
  highest.
- `samples` says which document a markup check read: the page's own, where it is
  empty, or the live sample child these template ids name, outermost first (None for
  a template without one).

A markup finding names its element by the tag the author reads in the file, with its
id where the words name one, and keeps the line it opens on in `values`. A registry
finding names the element declaration it concerns in `at`, and keeps the file or
composition it was read in as `values.registry`.

A record compares by all of these, so two readings of one fault in one place are one
finding and the same fault at another width is another.

Whether a finding refuses is decided by its code, once, beside its words. A code
refuses only where `_TEXT` names the guarantee it keeps: `_refuses` for a check that
refuses its input, such as a page's source or an event, and `_fails` for the
browser's reading of a page, which fails the check while the page is still served.
A code declared `_Unread` says the browser could not read the page, as where it
crashed: it is advice, and the check counts its gate as not run, as on a host with
no browser (`Finding.unread`). Every other code is advice, which leaves the decision
to the author. `severity`, `error` or `advice`, reads that declaration. A refusal's
words end with its guarantee, so the agent learns what the refusal protects, and a
door that refuses what it read (`Rejected`), as the message door does, words a
`_fails` guarantee as a refusal too. Codes that protect the same thing, such as the
registry's, the capture's and the event door's, name one guarantee, written once.
`Rejected` raises only findings whose code refuses.

The maintainer chose this, following root `AGENTS.md`, "Leaf's role": Leaf refuses
only input that would break a guarantee whatever the agent meant, so each refusal
names that guarantee, and a new check advises until its author names one. Choosing
the severity where a check builds its finding, as a later change may be tempted to,
lets a check refuse by default without saying what it protects, and lets one code
refuse at one door and advise at another.
"""

import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace

from leaf.base.json_block import json_value
from leaf.base.refusals import Refused


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    at: str = ""
    values: dict = field(default_factory=dict)
    widths: tuple[int, int] | None = None
    samples: tuple[str | None, ...] = ()

    def __post_init__(self):
        if self.code not in _TEXT:
            raise ValueError(f"no words for finding code {self.code!r}")

    def __hash__(self) -> int:
        return hash(json.dumps(self.json(text=False), sort_keys=True))

    def __str__(self) -> str:
        said = _TEXT[self.code]
        if isinstance(said, _Refuses):
            return f"{self.said} ({said.how} {said.keeps})"
        return self.said

    @property
    def said(self) -> str:
        """The finding's words, with the widths and sample it was read at, and
        without the guarantee its refusal keeps. Another finding that lists this one
        shows these words, and so does the browser, to the person whose gesture was
        refused."""
        text = _words(self)
        if self.widths is not None:
            low, high = self.widths
            span = f"{low}px" if low == high else f"{low}–{high}px"
            text = f"at {span} wide, {text}"
        return "".join(f"sample {s or '<unnamed>'!r}: " for s in self.samples) + text

    @property
    def refusal(self) -> str:
        """The finding's words as a refusal (`Rejected`) gives them: its words, then
        the guarantee its code keeps, introduced as what was refused for, since that
        door refuses what it read whichever check found it."""
        said = _TEXT[self.code]
        if not isinstance(said, _Refuses):
            return self.said
        return f"{self.said} (refused so that {said.keeps})"

    @property
    def refuses(self) -> bool:
        """Whether the finding's code refuses what the check read or fails the check
        (`_refuses`, `_fails`), as its `severity` says `error`."""
        return isinstance(_TEXT[self.code], _Refuses)

    @property
    def unread(self) -> bool:
        """Whether the finding's code says the browser could not read the page
        (`_Unread`), which leaves the check as unread as on a host with no browser."""
        return isinstance(_TEXT[self.code], _Unread)

    @property
    def severity(self) -> str:
        """`error` where the finding refuses, else `advice`, as its record says."""
        return "error" if self.refuses else "advice"

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
            tuple(found["widths"]) if "widths" in found else None,
            tuple(found.get("samples", ())),
        )

    def json(self, *, text: bool = True) -> dict:
        found = {"code": self.code, "severity": self.severity}
        if self.at:
            found["at"] = self.at
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


# What the running command has noted for the record it prints (`hold`), or None
# where no record will carry a note.
_held: list[Finding] | None = None


def hold() -> None:
    """Keep what the running command notes for the record it prints on stdout
    (`with_held`), from now until that record is printed."""
    global _held
    _held = []


def release() -> list[Finding]:
    """Stop keeping notes, so each later one prints on stderr, and return those
    kept so far."""
    global _held
    held, _held = _held or [], None
    return held


def with_held(record: dict) -> dict:
    """`record` with what the command has noted added to its `findings`, as the
    command prints it on stdout (`cli`). A note after this prints on stderr, since no
    record is left to carry it, as one noted by a process that prints no record,
    such as a hook, a stream or a server, does."""
    if not (held := release()):
        return record
    return record | {
        "findings": [*record.get("findings", []), *(f.json() for f in held)]
    }


def note(*found: Finding) -> None:
    """Say each finding beside a command's result: in the `findings` of the record
    it prints (`with_held`), or as a JSON line on stderr where none will print. A
    finding the record already holds, as from a check run twice, is said once."""
    if _held is not None:
        _held.extend(f for f in dict.fromkeys(found) if f not in _held)
        return
    for finding in found:
        print(
            json.dumps(finding.json(), ensure_ascii=False), file=sys.stderr, flush=True
        )


def element_at(tag: str, id: str = "") -> str:
    """How `locate.js` names an element known by its tag and authored id."""
    return f"<{tag} id={id}>" if id else f"<{tag}>"


@dataclass(frozen=True, slots=True)
class _Refuses:
    """A refusing code's words, the guarantee it keeps (`keeps`), a clause saying
    what the user or a reader of the page relies on, and how its words introduce that
    guarantee (`how`): "refused so that" where the check refuses the input, as a
    page's source or an event, or "fails the check so that" where it reads a page
    the browser drew, which is served all the same, and fails the check that read
    it."""

    words: Callable[[str, dict], str]
    keeps: str
    how: str


def _refuses(keeps: str, words: Callable[[str, dict], str]) -> _Refuses:
    """The words of a code that refuses what its check read, to keep `keeps`."""
    return _Refuses(words, keeps, "refused so that")


@dataclass(frozen=True, slots=True)
class _Unread:
    """The words of a code that says the browser could not read the page, as where
    it crashed, Leaf's own preview server stopped answering, or the gate's probe
    failed: the finding is about the run, not the page, so the check counts the gate
    as not run (`render_gate.command.BrowserCheck`), keeps no reading of the version
    (`handover_pass`), and a message it held posts, as on a host with no
    browser. It is advice in every record, beside the result."""

    words: Callable[[str, dict], str]


def _fails(keeps: str, words: Callable[[str, dict], str]) -> _Refuses:
    """The words of a code that fails the browser's check of a page, to keep `keeps`:
    `page check --render` and `package check --render` exit 1, the page's server
    wakes the agent with its reading, and a message drawing it is refused, while the
    page itself is served."""
    return _Refuses(words, keeps, "fails the check so that")


# The guarantees refusing codes keep (`_refuses`, `_fails`), each written once.
_SHOWS = "the user sees what the agent wrote"
_SERVES = "every page Leaf activates can be served and loads its runtime"
_ONE_ID = "each id names one element for comments and commands to reach"
_RUNTIME_NAMES = "the runtime's own ids and markers name only what it wrote"
_DECIDES = "each decision the user makes is recorded and reads back as made"
_SUGGESTS = "a suggestion the user decides changes exactly the words it shows"
_REFERS = "each reference a widget makes reaches the element it names"
_DATA = "each widget reads the data its markup names, in its declared contract"
_UNSTYLED = "the page looks as its source says, whatever its threads hold"
_OPENS = "each live sample opens from the template its id names"
_LAYS_OUT = "Leaf and the page lay out each allocation as one of the values it takes"
_ADMITS = "each logged event fits its kind and names only what the page holds"
_OWN_VOICE = "each writer's words and decisions come only from that writer"
_AS_SEEN = "a gesture changes only what its sender saw when making it"
_TAKEN_BACK = "what the user took back stays taken back"
_LIVE = "the log records decisions only from live widgets, never quoted ones"
_PUBLISHED = "each revision's place in the log is where Leaf published it"
_EDITED = "a message shows as edited only when its words changed"
_ASKED_AGAIN = "each question a reply asks again stands on the user's On Me list"
_ASKS = "each question on the user's On Me list shows the words that ask it"
_ANSWERABLE = (
    "each question on the user's On Me list changes what it shows when answered"
)
_SAMPLED = (
    "a live sample opens with its authored history, every event one the log admits"
)
_DECLARED = "each widget's declaration means one thing to every part of Leaf"
_CAPTURED = "each revision draws every file it names, the same wherever it is shown"
_CONFINED = "no file from outside the page enters a revision or its export"
_NAMES = "each write acts on the item its id names"
_STANDS = "each step of the agent's plan reads where its work stands"
_PUBLISHES = "a reply reaches the user with the page edits saved before it"
_PASSAGE = "each comment anchors to the one passage its quote or id names"
_RESERVED = "each update gets one answer, from the writer that reserved it"
_VERSION_ANSWERS = "a decision on the page is answered by the version that writes it in"
_IN_THREAD = "what a message asks, promises or changes stays shown in its thread"
_PLAIN = "a command does only what its arguments plainly say"
_HELD = "a thread sent from a widget stays shown in that widget"
_ENDED = "a to-do's recorded outcome stays as its first end gave it"
_ONCE = "each gesture is taken back once, and the agent hears of it once"
_UNDONE = "an undo the page accepts changes what the user sees"
_READ_AS_WRITTEN = "the user's recorded decisions are read as they were written"
_SELECTED = "the page draws with the packages it selected"
_RETRIED = "a retried write returns the event it first made, never a second"
_OWED = "what an answer leaves owed stays on the user's or agent's list"
_NEWER = "the user's newer message stays owed until the agent answers it"
_TITLED = "every thread the agent writes in has a title naming its subject"
_REACHES = "the user can see and reach everything the page draws"
_MARKS = "each comment marks and reaches the element or part it anchors to"
_WORKS = "the user sees the page's widgets and scripts work as written"
_STATE = "each widget shows the state the log records"
_COMMENTS = "the user can comment on every word the page shows outside a control"
_QUOTES = "a comment's quote resolves to the words the page shows"
_EXAMPLES = "each widget's worked example draws for the authors who copy it"
_COMPOSES = "every page that selects the package composes into a layer Leaf serves"


def _explained(console: list[dict]) -> str:
    """What the console said, beside a wait that never ended."""
    return "\n".join(_words(Finding.loads(entry)) for entry in console)


def _visual_problem(problem: dict) -> str:
    return f"named parts its prefixes do not admit {', '.join(problem['parts'])}"


def _verbatim(at: str, v: dict) -> str:
    provenance = v["provenance"]
    if provenance is None:
        where = " without pre-upgrade source provenance"
    elif provenance[0] == "page":
        where = f" at page occurrence {provenance[2] + 1}"
    else:
        where = f" at {provenance[0]} {provenance[1]} occurrence {provenance[2] + 1}"
    return (
        f"{at}{where} declares `verbatim` but shows {v['says'][:80]!r} with owned "
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
        + " — every column stays in reach, so what this costs the reader is the"
        " wrapped cells' words a few to a line; an identifier in <code> breaks inside"
        " its cell, and a shorter word in the widest column gives the rest the measure,"
        " while hiding a column at this width takes its facts from the reader"
    )


def _broken_names(at: str, v: dict) -> str:
    # The reading knows which names break, not which column holds the row's name, so
    # the words offer the remedy for either.
    names = ", ".join(v["names"])
    if (more := v["count"] - len(v["names"])) > 0:
        names += f" and {more} more"
    return (
        f"{at} draws {names} on more than one line, though each is under a third of the"
        " table's width; a name written as its row's <th scope=\"row\"> stays whole up"
        " to a third of the column, and white-space: nowrap in the page's CSS keeps a"
        " column of names on one line"
    )


def _drawn_height(at: str, v: dict) -> str:
    # `box` is the height the element holds now: past `before`, what follows it moved
    # as it drew; past `drawn`, a stated height larger than the drawing left room.
    text = (
        f"{at} was {v['before']}px tall before drawing and its drawing is"
        f" {v['drawn']}px tall"
    )
    if moved := v["box"] - v["before"]:
        direction = "down" if moved > 0 else "up"
        text += f", so what follows it moved {direction} {abs(moved)}px as it drew"
    if (blank := v["box"] - v["drawn"]) > 0:
        text += f", leaving {blank}px blank under the drawing"
    return (
        f'{text}; data-height="{v["drawn"]}" holds the drawing\'s height from'
        " first paint"
    )


def _scroll_mark(v: dict) -> str:
    """What scrolls a box sideways, for whoever wrote the box: the page's markup names
    its own boxes `class="lf-scroll"`, and a module marks a box it builds
    `data-lf-scroll`, with the overflow in its package's CSS
    (`module-scroll-and-motion.md`). `built` says the page's source didn't write it."""
    if v.get("built"):
        return (
            "with data-lf-scroll on it in the widget's module and overflow-x: auto in"
            " its package's CSS, since the page's markup can't reach a box the module"
            " builds"
        )
    return 'with overflow-x: auto and class="lf-scroll"'


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
            f" sideways {_scroll_mark(v)}"
        )
    return f"{at} cuts off its content where no scroll reaches it: " + "; ".join(cuts)


def _question_group(v: dict) -> str:
    """The named groups an asking widget may stand in (`values.groups`), as markup."""
    return " or ".join(f'<{tag} id="…" label="…">' for tag in v["groups"])


def _line(at: str, v: dict) -> str:
    """An element of the author's file, as they find it: its name and its line."""
    return f"{at} (line {v['line']})"


def _blocks(v: dict) -> str:
    """The blocks of the author's file a finding lists (`values.elements`), as they
    find them: a run of one tag in a row, under one enclosing id, reads as one, with
    its count and its lines."""
    runs: list[list[dict]] = []
    for element in v["elements"]:
        if runs and all(
            runs[-1][0].get(key) == element.get(key) for key in ("tag", "enclosing")
        ):
            runs[-1].append(element)
        else:
            runs.append([element])

    def said(run: list[dict]) -> str:
        first, last = run[0]["line"], run[-1]["line"]
        lines = f"line {first}" if first == last else f"lines {first}–{last}"
        count = f"{len(run)} " if len(run) > 1 else ""
        enclosing = run[0].get("enclosing")
        within = f" in #{enclosing}" if enclosing else ""
        return f"{count}<{run[0]['tag']}> ({lines}){within}"

    return ", ".join(said(run) for run in runs)


def _bearing(at: str, v: dict, value: str) -> str:
    """The element `at` names, written with the attribute the finding is about and
    its `value` as the words quote it."""
    return _line(f"{at[:-1]} {v['attr']}={value}>", v)


def _seat(seat: dict) -> str:
    document = f"{seat['document']} " if "document" in seat else ""
    element = element_at(seat["tag"], seat.get("widget", ""))
    return f"{document}{element} input `{seat['input']}` (line {seat['line']})"


def _unservable_layer(v: dict, why: str, action: str) -> str:
    """Why this Leaf can neither serve a page nor write its log (`layer`)."""
    return (
        f"{v['page']} {why}, so it cannot serve the page or write its log. {action}"
        f" with `leaf page init {v['page']}`."
    )


def _invalid_record(v: dict) -> str:
    """How the refusal of a record one widget's verb writes begins."""
    return f"<{v['tag']}> {v['kind']} {v['verb']!r} is invalid: "


def admitted_parts(prefixes: Sequence[str]) -> str:
    """The part ids a visual admits as `anchor.visual`, in words: ids starting with
    one of `prefixes` (`registry.contract.VisualParts`)."""
    if prefixes:
        return f"ids starting with {' or '.join(map(repr, prefixes))}"
    return "no visual parts"


def _size(box: dict) -> str:
    return f"{round(box['width'])}x{round(box['height'])}"


def _declared(words, sep: str = ": ", keeps: str | None = _DECLARED):
    """A registry finding's words: the file it read (`registry`), the element
    declaration `at` names, then `words`; refusing to keep `keeps`, the family's
    guarantee unless a member names its own, or advice where it is None."""

    def said(at: str, v: dict) -> str:
        text = f"{at} {words(v)}" if at else words(v)
        if "registry" in v:
            text = f"{v['registry']}{sep}{text}"
        return text

    return said if keeps is None else _refuses(keeps, said)


def _json_path(path: list) -> str:
    """Where in a registry a schema complaint points, as `$data.contracts[0]`."""
    where = "".join(
        f"[{step}]" if isinstance(step, int) else f".{step}" for step in path
    )
    return where.lstrip(".") or "registry"


def _plain(value) -> str:
    """A declared value as the registry's words quote it: a word bare, else JSON."""
    return value if isinstance(value, str) else json_value(value)


def _predicate(v: dict, says: str) -> str:
    return f"`{v['key']}` tests `{v['attr']}` {says}"


def _created(v: dict, says: str) -> str:
    return f"verb `{v['verb']}` (`verbs`) creates <{v['child']}>, {says}"


def _answering(v: dict, says: str) -> str:
    return f"`awaits` answering verb `{v['verb']}` {says}"


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


def _capture_where(v: dict) -> str:
    """Where a capture finding was read: the file (`file`) and the reference in it
    (`specifier`), where it names them."""
    return "".join(
        [
            f"{v['file']}: " if "file" in v else "",
            f"{v['specifier']!r}: " if "specifier" in v else "",
        ]
    )


def _captured(words, keeps: str = _CAPTURED):
    """A capture finding's words: where it was read (`_capture_where`), then `words`;
    refusing to keep `keeps`, the family's guarantee unless a member names its own."""
    return _refuses(keeps, lambda at, v: _capture_where(v) + words(v))


def _fixture(words):
    """A sample history finding's words: the script it read (`reference`) and, for
    one of its events, which (`event`), then `words`."""

    def said(at: str, v: dict) -> str:
        where = f"data-sample-events {v['reference']!r}"
        if "event" in v:
            return f"{where}, event {v['event']}: {words(v)}"
        return f"{where}{words(v)}"

    return _refuses(_SAMPLED, said)


def _listed(findings: list[dict]) -> str:
    return "\n".join(f"  - {Finding.loads(found).said}" for found in findings)


# What each element `structure.document_declarations` holds declares.
_DECLARES = {"<base>": "base URL", "<meta>": "HTTP headers", "<script>": "import map"}

# How a page names a module, since delivery owns the import map: said the same way
# where a bare name is refused and where the page's own map is.
_IMPORT_BY_URL = (
    "import a file under page/ by its path, or a package by its full http(s) URL"
    " (such as https://esm.sh/NAME)"
)

# The fix for a page's own file named outside page/, whichever reference names it.
_MOVE_UNDER_PAGE = (
    "move the file into page/ beside index.html and name it by that path, such as"
    " page/style.css or page/app.js"
)


# The words for each code, from the finding's `at` and `values`. A console code's
# words are what the console said.
_TEXT = {
    "invalid-output": _fails(
        _DATA,
        lambda at, v: (
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
    ),
    # What the browser's console and the page's window reported.
    "console-error": _fails(
        _WORKS, lambda at, v: f"{v['text']} — {v['url']}" if v.get("url") else v["text"]
    ),
    "console-warning": lambda at, v: f"warning: {v['text']}",
    "page-exception": _fails(_WORKS, lambda at, v: v["text"]),
    "window-error": _fails(_WORKS, lambda at, v: f"window error: {v['text']}"),
    # A ResizeObserver loop the window reported, which fails the check where a
    # complete second attempt repeats it (`render_gate.version.render_version`).
    "resize-loop": _fails(
        _WORKS,
        lambda at, v: (
            f"window error: {v['text']}"
            + (
                " (recurred on the confirming render attempt)"
                if v.get("confirmation")
                else ""
            )
        ),
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
    "unmoved-scroll": lambda at, v: (
        f"unmoved scroll: {v['how']} on {placed(v['node'])}, from {' < '.join(v['by'])}"
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
    "gate-failed": _Unread(
        lambda at, v: (
            f"the browser gate failed while running its probe module, before it"
            f" finished reading the page: {v['error']}"
        )
    ),
    # A thread holding a message's HTML that the page couldn't open, read after the rest
    # of the page: the page's defect, where `gate-failed` is the gate's own.
    "thread-not-drawn": _fails(
        _REACHES,
        lambda at, v: (
            f"thread {v['thread']} did not open to show its messages: {v['error']}"
        ),
    ),
    "probe-failed": _Unread(
        lambda at, v: (
            f"the browser probe module failed before it finished reading the page:"
            f" {v['error']}"
            + (" — " + _explained(v["console"]) if v.get("console") else "")
        )
    ),
    "reading-overran": _fails(
        _SERVES,
        lambda at, v: (
            f"the render check gave up on this version after {v['seconds'] // 60} minutes"
            " without finishing a reading of it; a page script that never stops, such as"
            " a loop that starts after load, keeps a reading running"
        ),
    ),
    "no-runtime": _fails(
        _SERVES,
        lambda at, v: (
            "the runtime never started — "
            + (_explained(v["console"]) or "and no console message explains why")
        ),
    ),
    "never-upgraded": _fails(
        _SERVES,
        lambda at, v: (
            "the widget layer never finished upgrading — "
            + (_explained(v["console"]) or "and no console message explains why")
        ),
    ),
    "no-browser": _Unread(
        lambda at, v: (
            f"{v['error']}; the browser checks did not run, so a failure only they"
            " would find shows when a browser first draws the page"
        )
    ),
    "server-stopped": _Unread(
        lambda at, v: (
            f"the preview server stopped answering before the browser finished"
            f" reading the page: {v['error']}"
        )
    ),
    "not-ready": _fails(_SERVES, lambda at, v: v["error"]),
    "never-settled": lambda at, v: (
        f"the page never stopped moving ({', '.join(v['moving'])}), so the check"
        " read it in motion"
    ),
    # Widgets and their modules.
    "visual-parts": _fails(
        _MARKS,
        lambda at, v: (
            f"{at} declares addressable visual parts but its module "
            + "; ".join(_visual_problem(problem) for problem in v["problems"])
        ),
    ),
    "invalid-paint": _fails(
        _WORKS,
        lambda at, v: (
            f"{at} renders {v['property']}={v['value']!r} on <{v['element']}>"
            + (f" for data-id={v['part']!r}" if v["part"] else "")
            + f", but that value does not resolve to valid {v['property']}"
        ),
    ),
    "missing-upgrades": _fails(
        _WORKS,
        lambda at, v: (
            "upgraded widgets did not define their elements: "
            + ", ".join(f"<{tag}>" for tag in v["tags"])
        ),
    ),
    "tiny-boxes": _fails(
        _WORKS,
        lambda at, v: f"widgets rendered with no usable size: {json_value(v['boxes'])}",
    ),
    "unread-commands": _fails(
        _WORKS,
        lambda at, v: (
            f"{at} sets lfCommands, but no lf-commands event from it reached Leaf, so"
            " its keys bind nothing and the buttons its rows name do nothing; dispatch"
            " a bubbling, composed lf-commands event on the element once it stands in"
            " the page (module-plain-elements.md, lf-commands)"
        ),
    ),
    "unmarkable": _fails(
        _MARKS,
        lambda at, v: (
            f"{at} shows {v['w']}x{v['h']}px of words, but neither it nor anything"
            " inside it draws a box; put the words in an element that takes a box"
        ),
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
    "verbatim": _fails(_QUOTES, _verbatim),
    "undeclared-attr": lambda at, v: (
        f"{at} carries {v['attr']!r}, which its element declaration does not name —"
        " declare it as a verb's record form (`verbs`) if a version is meant to carry"
        " it, or write the state on the chrome the module built"
    ),
    "settlement-mark": _fails(
        _STATE,
        lambda at, v: (
            f"{at} has data-lf-state={json_value(v['mark'])} where the log records "
            + (f"`{v['outcome']}`" if v["outcome"] else "no decision")
            + "; leave data-lf-state to Leaf, which sets it from the decision in the"
            " log"
        ),
    ),
    "retired-slot": _fails(
        _STATE,
        lambda at, v: (
            f"{at} is settled `{v['outcome']}`, but its <{v['slot']}> still shows"
            f" {json_value(v['words'])}. Leaf hides a retired slot by default, so this"
            " widget's own styles or module must be showing it"
        ),
    ),
    "render-threw": _fails(
        _STATE,
        lambda at, v: (
            f"{at} render() threw when the complete state was rendered a second time:"
            f" {v['error']}"
        ),
    ),
    "relative-render": _fails(
        _STATE,
        lambda at, v: (
            f"{at} render() is relative — rendering the same complete state changed"
            f" {', '.join(v['changed'])}. Render the supplied values without stepping"
            " from the DOM."
        ),
    ),
    # Geometry, read across the width sweep.
    "page-scrolls": lambda at, v: f"the page scrolls sideways by {v['past']}px",
    "outside-part": lambda at, v: (
        f"{at} stands {v['past']}px outside the {v['host']} it is part of"
    ),
    "past-column": lambda at, v: (
        f"{at} is set {v['past']}px past the column, out in the margin; "
        + (
            f"as a {v['item']} item it is by default no narrower than its content, so"
            " first give it min-width: 0, which keeps a wide table or scrolling box in"
            " it scrolling inside the column; or, "
            if v.get("item")
            else ""
        )
        + 'to give it more room, mark it data-width="wide" or "available" rather than'
        " sizing it past the column, or scroll it sideways in a box of its own"
        f" {_scroll_mark(v)}"
    ),
    "outside-frame": lambda at, v: (
        f"{at} stands {v['past']}px outside the {v['frame']} that frames it — to widen"
        " the frame with it, put data-width on the frame; to hold it inside, draw the"
        " frame on a div, since a section, article or details hands the page's room on"
        " to what it holds"
    ),
    "past-room": lambda at, v: (
        f"{at} stands {v['past']}px past the room the page has for a wide widget"
    ),
    "over-margin": _fails(
        _REACHES,
        lambda at, v: (
            f"{at} grows into the margin and is drawn over {v['marginContent']}, which already"
            " sits there; that side of the page has no free room for it"
        ),
    ),
    "clipped-out": _fails(
        _REACHES,
        lambda at, v: (
            f"{at} is drawn {v['past']}px outside {v['container']}, which does not show it"
        ),
    ),
    "clipped-content": _fails(_REACHES, _clipped_content),
    "scrollbar-clearance": lambda at, v: (
        f"{at} leaves {v['clear']}px below its {v['content']} for a"
        f" {v['required']:g}px horizontal overlay scrollbar; avoid the horizontal"
        " overflow or reserve room below the content so reaching for the bar does"
        " not cover it"
    ),
    "clipped-control": _fails(
        _REACHES,
        lambda at, v: (
            f"the control .{v['control'].split()[0]}"
            + (f" (#{v['id']})" if v["id"] else "")
            + f" is drawn {v['lost']}px outside the {v['by']} that clips it, where nothing"
            " can scroll to reach it"
        ),
    ),
    "chrome-words": _fails(
        _COMMENTS,
        lambda at, v: (
            f"{at} puts {json_value(v['words'])} under .lf-ui, where no comment can reach it"
        ),
    ),
    "form-control-words": lambda at, v: (
        f"{at} says {json_value(v['words'])} inside a form control, where no selection"
        " can reach it"
    ),
    "apparatus-among-authored": lambda at, v: (
        f"{at}, which Leaf adds, stands among the page's own elements inside"
        f" {v['parent']}, so the page's rules that read its structure, such as"
        " :first-child or h2 + p, match differently"
    ),
    "unread-syntax": lambda at, v: (
        f"code styled {json_value(v['style'])} reads at {v['ratio']:.1f}:1 against the"
        " block it is set on"
    ),
    "covered-words": _fails(
        _REACHES,
        lambda at, v: (
            f"{at} draws {json_value(v['words'])} in the same place as {v['under']}'s"
            f" {json_value(v['covered'])}"
        ),
    ),
    # What the author decides.
    "unreduced-motion": lambda at, v: (
        f"{at} keeps moving for a reader who asked for less motion; stop or shorten it"
        " under @media (prefers-reduced-motion: reduce)"
    ),
    "uncoloured-code": lambda at, v: (
        f"{at} declares {v['language']}, but no reading face reaches it, so Leaf"
        " leaves its tokens uncoloured; to colour it, set --lf-reading-face: 1 on a"
        " box around the <pre>, or select the reading package"
    ),
    "contained-space": lambda at, v: (
        f"{at} declares {v['space']} space but stays inside "
        + ", ".join(v["holders"])
        + "; to let it break out with the words around it staying on the column, write"
        " each unframed wrapper as a section, article or details, which hands the"
        " page's room on, or drop it; to widen a frame around it, put data-width on"
        " the frame"
    ),
    "words-off-column": lambda at, v: (
        f"{at} reaches past the column's start edge and takes its words with it, so"
        " they no longer line up with the page's; move data-width to the block inside"
        " that needs the room, which a section, article or details around it hands"
        " the page's room"
    ),
    "squeezed-table": _squeezed,
    "broken-name": _broken_names,
    "drawn-height": _drawn_height,
    "shrunk-labels": lambda at, v: (
        f"{at} draws labels below {v['threshold']}px, {v['labels']} at"
        f" {v['width']}px, the smallest ({v['words']!r}) at {v['drawn']:g}px from"
        f" the {v['set']:g}px it was set at: the drawing is scaled to fit its box"
        " and its labels with it, so set them larger in the viewBox's units, draw"
        " the viewBox nearer the width it is shown at, or give it more room"
        " (authoring-evidence.md, Interactive and visual evidence)"
    ),
    # The page's own code, run once in the browser.
    "page-report": _fails(_WORKS, lambda at, v: v["text"]),
    "browser-error": _Unread(
        lambda at, v: (
            f"the browser failed before it finished reading the page: {v['error']}"
        )
    ),
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
    "no-source": _refuses(
        _SERVES, lambda at, v: f"no {v['path']}; write index.html first"
    ),
    "not-utf8": _refuses(
        _SERVES, lambda at, v: f"{v['path']} is not UTF-8: {v['error']}"
    ),
    # A sample's initial history, read from the JSON script its template names.
    "sample-source-both": _refuses(
        _SAMPLED,
        lambda at, v: "use either data-sample-events or data-sample-threads, not both",
    ),
    "sample-script": _fixture(
        lambda v: " must name one script in the markup declaring its template"
    ),
    "sample-script-type": _fixture(
        lambda v: " needs an inline application/json script"
    ),
    "sample-json": _fixture(lambda v: f": invalid JSON: {v['error']}"),
    "sample-array": _fixture(lambda v: " must contain an array of event objects"),
    "fixture-ts": _fixture(lambda v: "ts must be an ISO timestamp with a time zone"),
    "fixture-id-repeated": _fixture(lambda v: f"event id {v['id']!r} already exists"),
    "fixture-id-taken": _fixture(
        lambda v: f"event id {v['id']!r} is already a document or message widget id"
    ),
    "fixture-media": _fixture(
        lambda v: "; ".join(Finding.loads(found).said for found in v["findings"])
    ),
    "fixture-markup": _fixture(
        lambda v: f"{v['kind']} markup doesn't validate:\n{_listed(v['findings'])}"
    ),
    "fixture-ids-taken": _fixture(
        lambda v: f"message widget ids already taken by events: {json_value(v['ids'])}"
    ),
    "fixture-event": _fixture(
        lambda v: "; ".join(Finding.loads(found).said for found in v["findings"])
    ),
    "fixture-refused": _fixture(lambda v: v["error"]),
    "head-count": _refuses(
        _SERVES,
        lambda at, v: (
            "the page must have one explicit <head> directly under <html>; found"
            f" {v['tags']} head tags, {v['parsed']} parsed heads, and {v['direct']} direct"
            " html heads"
        ),
    ),
    "body-count": _refuses(
        _SERVES,
        lambda at, v: (
            f"the page must have one explicit <body>; found {v['tags']} body tags"
        ),
    ),
    "main-count": lambda at, v: (
        "a Layout arranges only one <main> directly under <body>; found"
        f" {v['mains']} mains, and {v['direct']} directly under <body>, so the page"
        " draws as the browser lays out its body"
    ),
    "unclosed": _refuses(
        _SHOWS,
        lambda at, v: (
            "unclosed tags: "
            + ", ".join(f"<{e['tag']}> (line {e['line']})" for e in v["elements"])
        ),
    ),
    "self-closing": _refuses(
        _SHOWS,
        lambda at, v: (
            f"{at[:-1]}/> at line {v['line']} is self-closing: HTML ignores the slash and"
            f" the element would swallow what follows — write {at[:-1]} …></{at[1:-1]}>"
        ),
    ),
    "split-pre": _refuses(
        _SHOWS,
        lambda at, v: (
            f"{at} holds a <{v['block']}> at line {v['line']}: a blank line inside a block"
            " of HTML ends the block, and Markdown read the lines after it as Markdown."
            " Start the <pre> on its own line after a blank line, or write its text in a"
            " Markdown fence"
        ),
    ),
    "noscript": lambda at, v: (
        f"{at} at line {v['line']}: a browser running the page's scripts draws none"
        " of its content, so the user never sees it; write it plainly or leave it out"
    ),
    "unnamed-sample": _refuses(
        _OPENS,
        lambda at, v: f"<template data-sample> at line {v['line']}: needs a stable id",
    ),
    "document-declaration": _refuses(
        _SERVES,
        lambda at, v: (
            f"{_line(at, v)} declares the document's {_DECLARES[at]}; remove it"
            + (f", and {_IMPORT_BY_URL}" if at == "<script>" else "")
        ),
    ),
    "allocation-value": _refuses(
        _LAYS_OUT,
        lambda at, v: (
            f"{_bearing(at, v, json_value(v['value']))} has an invalid value; expected "
            + (
                "a whole number of CSS pixels"
                if v["allowed"] is None
                else f"one of {', '.join(v['allowed'])}"
            )
        ),
    ),
    "unnamed-card": lambda at, v: (
        f"{_line(at, v)}: leads with a <strong> but has no label, so Leaf names it by"
        ' all its words; give its name in label="…" and keep the <strong> as the title'
        " the page shows"
    ),
    "inert-allocation": lambda at, v: (
        f"{_bearing(at, v, json_value(v['value']))} has no effect: "
        + {
            "flow": "the element takes no width of its own, so put it on the block"
            " inside that needs the room",
            "content": "only a block inside body, other than main, takes it, so put"
            " it on the block that needs it",
            "declared": "only a widget that draws into a box of a stated height"
            " takes it",
        }[v["holds"]]
    ),
    "css-syntax": _refuses(
        _CAPTURED,
        lambda at, v: (
            f"{v['sheet']} syntax error at {v['row']}:{v['column']}: {v['message']}"
        ),
    ),
    "css-dropped": lambda at, v: (
        f"{v['sheet']} syntax error at {v['row']}:{v['column']}, a declaration or"
        f" rule a browser drops without a word: {v['message']}"
    ),
    "unset-property": lambda at, v: (
        f"{v['sheet']} reads {v['property']} with no fallback on line"
        f"{'s' if len(v['rows']) > 1 else ''} {', '.join(map(str, v['rows']))}, and"
        " no sheet or module in Leaf, the package or its layer sets it, so each"
        " declaration reading it computes to nothing; read a theme token"
        ' (package-themes.md, "Theme tokens"), set the property, or give a fallback'
    ),
    "unserved-media": _refuses(
        _SHOWS,
        lambda at, v: (
            f"{v['ref']} isn't a name `leaf page media` gives, so the page never serves it"
        ),
    ),
    "missing-media": _refuses(
        _SHOWS,
        lambda at, v: (
            f"{v['ref']} isn't in the page directory; `leaf page media` puts it there"
        ),
    ),
    # Ids and the runtime's own names.
    "duplicate-ids": _refuses(
        _ONE_ID, lambda at, v: f"duplicate ids: {json_value(v['ids'])}"
    ),
    "spaced-ids": lambda at, v: (
        f"ids containing whitespace, which HTML forbids in an id: {json_value(v['ids'])};"
        " a comment anchors on the whole id, so rename it before a thread holds it"
    ),
    "reserved-ids": _refuses(
        _RUNTIME_NAMES,
        lambda at, v: f"ids in the runtime's own lf- namespace: {json_value(v['ids'])}",
    ),
    "reserved-markers": _refuses(
        _RUNTIME_NAMES,
        lambda at, v: (
            f"{at} at line {v['line']} wears the runtime's own markers"
            f" ({', '.join(v['markers'])}); the lf- and data-lf- namespaces are the"
            " runtime's to write, but for the classes Leaf's idioms name"
        ),
    ),
    "ids-taken-by-events": _refuses(
        _ONE_ID,
        lambda at, v: (
            "ids the page's log already gives its events, which a command's ID could"
            f" name instead: {json_value(v['ids'])}"
        ),
    ),
    "ids-taken-by-messages": _refuses(
        _ONE_ID,
        lambda at, v: f"ids already taken by message markup: {json_value(v['ids'])}",
    ),
    "ids-taken": _refuses(
        _ONE_ID,
        lambda at, v: (
            f"ids already taken by the page or an earlier message: {json_value(v['ids'])}"
        ),
    ),
    # Widgets, against the registry that declares them.
    "unknown-widget": _refuses(
        _SHOWS,
        lambda at, v: f"{_line(at, v)}: unknown widget — not in the page's registry",
    ),
    "attribute-schema": _refuses(
        _SHOWS, lambda at, v: f"{_line(at, v)}: {v['reason']}"
    ),
    "member-record-slot": _refuses(
        _DECIDES,
        lambda at, v: (
            f"{_line(at, v)}: scalar verb `{v['value_verb']}` and `{v['owner']}`'s "
            f"selection verb `{v['owner_verb']}` both write attribute `{v['attr']}`"
        ),
    ),
    "not-member": _refuses(
        _SHOWS,
        lambda at, v: (
            f"{_line(at, v)}: must be a direct member of "
            + " or ".join(f"<{owner}>" for owner in v["owners"])
            + (f", found <{v['parent']}>" if v["parent"] else "")
        ),
    ),
    "content-empty": _refuses(
        _SHOWS,
        lambda at, v: (
            f"{_line(at, v)}: takes no content — write {at[:-1]} …></{at[1:-1]}>"
        ),
    ),
    "data-body": _refuses(
        _SHOWS,
        lambda at, v: (
            f"{_line(at, v)}: "
            + (
                "its bound input supplies the text, so it holds no <pre>"
                if v.get("bound")
                else "its body is one <pre> holding the text (escape < and >)"
            )
            + ", found "
            + (", ".join(f"<{c}>" for c in v["children"]) or "nothing")
        ),
    ),
    "text-outside-pre": _refuses(
        _SHOWS,
        lambda at, v: (
            f"{_line(at, v)}: text outside its <pre> — the whole body goes inside it"
        ),
    ),
    "stray-members": _refuses(
        _SHOWS,
        lambda at, v: (
            f"{_line(at, v)}: admits only {json_value(v['admits'])} members, found"
            f" {json_value(v['found'])}"
        ),
    ),
    "loose-text": _refuses(
        _SHOWS,
        lambda at, v: f"{_line(at, v)}: loose text between its members isn't allowed",
    ),
    "parts-in-layout": lambda at, v: (
        f"{_line(at, v)}: stands in a <main> that carries {v['layout']}, so its"
        " parts draw as a strip of tabs inside that Layout rather than as a page of"
        " parts; a page of parts needs a <main> with no Layout, since each part's"
        ' child carries its own (page-layout.md, "A page of parts")'
    ),
    "pane-ends": lambda at, v: (
        f"{_line(at, v)}: `reading-role` {v['role']} holds more than one direct"
        " <header> or <footer>; its grid sets each one after the first beside it, in a"
        " column of its own, so put what they hold in one <header> or <footer>"
    ),
    "pane-header-first": lambda at, v: (
        f"{_line(at, v)}: `reading-role` {v['role']} holds its direct <header> after"
        " other children; its grid still draws the header on top, but keyboard and"
        " screen-reader order follow the markup"
    ),
    "pane-footer-last": lambda at, v: (
        f"{_line(at, v)}: `reading-role` {v['role']} holds its direct <footer> before"
        " other children; its grid still draws the footer at the bottom, but keyboard"
        " and screen-reader order follow the markup"
    ),
    "pane-body": lambda at, v: (
        f"{_line(at, v)}: `reading-role` {v['role']} "
        + (
            "holds loose text as its body, which stands without the body's padding"
            " and doesn't scroll as the pane's body; wrap it in a <p> or <div>"
            if v["body"] == ["#text"]
            else f"holds {len(v['body'])} body blocks ({json_value(v['body'])}); its grid"
            " places them all in its one body cell, where they overlap, and only the"
            " first element among them scrolls as the pane's body, so wrap them in one"
            " <div> or <section>"
        )
    ),
    "workspace-bodies": lambda at, v: (
        f"{_line(at, v)}: a workspace has one body beside its header and footer, and"
        f" this one has {len(v['bodies'])} ({', '.join(v['bodies'])}). While the"
        " workspace fills the window, the bodies it lays out split its height evenly,"
        " and a short one leaves blank space under its lines. To add"
        " material beside the regions' work, make the body a tab set with"
        ' `flow="page"` whose first tab holds the regions, and give the material a tab'
        ' of its own (page-layout.md, "A workspace")'
    ),
    "needs-id": _refuses(
        _DECIDES,
        lambda at, v: f"{_line(at, v)}: a matching {v['role']} instance requires an id",
    ),
    "ungrouped-question": lambda at, v: (
        f"{_line(at, v)}: asks the user, but no group holds its question, so On Me"
        " names it by the widget's label alone and selects only the widget; where"
        " its premise stands outside it, write that premise and this widget in"
        f" {_question_group(v)}, its label asking the question"
    ),
    "unnamed-question": _refuses(
        _ASKS,
        lambda at, v: (
            f"{_line(at, v)}: asks the user, but "
            + (
                f"{v['group']} round it has a blank label; give it a label"
                if "group" in v
                else "no label names its question; write its premise and this"
                f" widget in {_question_group(v)}, its label"
            )
            + " asking the question"
        ),
    ),
    "unknown-reference": _refuses(
        _REFERS,
        lambda at, v: (
            f'{_line(at, v)}: {v["attr"]}="{v["target"]}" names no element in this version'
        ),
    ),
    "work-assignment": _refuses(
        _REFERS,
        lambda at, v: (
            f'{_line(at, v)}: {v["attr"]}="{v["target"]}" must name a goal, but '
            + (f"<{v['target_tag']}>" if v["target_tag"] else "the element it names")
            + " has no role goal in $work.widgets"
        ),
    ),
    "ambiguous-data-binding": _refuses(
        _DATA,
        lambda at, v: (
            f"{_line(at, v)}: input {v['input']!r} binds both an external source and widget output"
        ),
    ),
    "output-contract": _refuses(
        _DATA,
        lambda at, v: (
            f"{_line(at, v)}: input {v['input']!r} reads the one output of"
            f" {v['target']!r} with contract {v['contract']!r}, and it declares "
            + (", ".join(repr(name) for name in v["outputs"]) or "none")
        ),
    ),
    "unknown-command": _refuses(
        _REFERS,
        lambda at, v: (
            f'{_line(at, v)}: command="{v["command"]}" is neither one of HTML\'s'
            " commands nor a custom command, which starts with --, so the button"
            " would do nothing"
        ),
    ),
    "nested-suggestion": _refuses(
        _SUGGESTS, lambda at, v: f"{_line(at, v)}: suggestions don't nest"
    ),
    "empty-suggestion": _refuses(
        _ANSWERABLE,
        lambda at, v: (
            f"{_line(at, v)}: needs a <lf-old> (what it replaces), a <lf-new> (what it"
            " proposes), or both"
        ),
    ),
    "repeated-slot": _refuses(
        _SUGGESTS,
        lambda at, v: (
            f"{_line(at, v)}: carries {v['count']} <{v['slot']}> children, one at most"
        ),
    ),
    "unknown-thread": lambda at, v: (
        f"{_line(at, v)}: resolves={v['resolves']!r} names no thread in this"
        " document, so deciding it closes no thread"
    ),
    "contract-conflict": _refuses(
        _DATA,
        lambda at, v: (
            f"source {v['source']!r} is bound to both contract {v['first']['contract']!r}"
            f" at {_seat(v['first'])} and contract {v['then']['contract']!r} at"
            f" {_seat(v['then'])}; use a new source id for the new meaning"
        ),
    ),
    "file-contract": _refuses(
        _DATA,
        lambda at, v: (
            f"source {v['source']!r} is a file the page binds, a 'text-document', but"
            f" {_seat(v['seat'])} reads it as {v['seat']['contract']!r}; bind that"
            " input to another source, or show the file in an input that reads"
            " 'text-document'"
        ),
    ),
    # Message markup, which no version settles.
    "message-settlement": lambda at, v: (
        f"{at} proposes a change inside a message, where deciding it changes only the"
        " message's own words and no version writes it into the page; to propose a"
        " change to the page, put it in the page's next version"
    ),
    "message-style": _refuses(
        _UNSTYLED,
        lambda at, v: (
            "<style> in message markup becomes a stylesheet of the whole document it is"
            " put into; a widget's look belongs in the layer's theme, beside its element"
            " declaration"
        ),
    ),
    "message-stylesheet": _refuses(
        _UNSTYLED,
        lambda at, v: (
            "<link rel=stylesheet> in message markup dresses the whole document it is put"
            " into; the page serves the one theme its layer composes"
        ),
    ),
    "sample-loop": _refuses(
        _SERVES,
        lambda at, v: (
            f"sample {json_value(v['samples'])} selects thread {v['thread']!r}, which"
            " holds this message, so its child would hold the same sample again; select"
            " other threads"
        ),
    ),
    # What the author decides about the source.
    "unpointable-section": lambda at, v: (
        "unpointable — no comment or reading position can hold to a section with"
        f" no id: {_blocks(v)}; give each an id"
    ),
    "unpointable": lambda at, v: (
        "unpointable — these blocks have no id, nor does anything enclosing them, so"
        f" element selection has no target: {_blocks(v)}; give the page's sections ids,"
        " or each block a reader may point at alone"
    ),
    "unpointable-wide": lambda at, v: (
        "unpointable — a comment aimed at a block with no id lands on the whole of"
        f" the element named: {_blocks(v)}; give each block its own id"
    ),
    "uncoloured-language": lambda at, v: (
        f'{_line(at, v)}: class="language-{v["language"]}" names no language Leaf'
        " colours, so its code shows uncoloured; Leaf colours "
        + ", ".join(v["names"])
        + ", and short names for them such as py and sh, and typesets LaTeX in"
        ' class="language-math" as a formula'
    ),
    "literal-markdown": lambda at, v: (
        "Markdown shown as typed — HTML reads no Markdown, so the page shows the"
        " backticks, ** or brackets of a code span, bold or link in"
        f" {_blocks(v)}; write each as <code>, <strong> or <a href>, or, where the"
        " syntax is itself the text, put it in <code>, <samp> or <pre>"
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
        lambda v: f"registry declarations must be objects: {json_value(v['names'])}"
    ),
    "page-layer": _declared(
        lambda v: "$layer belongs to the selected layer", keeps=_SELECTED
    ),
    "layer-unavailable": _refuses(
        _SELECTED,
        lambda at, v: (
            f"this Leaf cannot compose the page's layer: {v['error']}; choose its"
            " packages again with `leaf page init --package`"
        ),
    ),
    "no-layer": _refuses(
        _SELECTED,
        lambda at, v: f"{v['page']} has no layer.json; run `leaf page init` first",
    ),
    # Its shared layer facts.
    "layer-facts": _declared(lambda v: f"{_json_path(v['path'])}: {v['reason']}"),
    "fixed-events": _declared(
        lambda v: (
            f"$events.{v['key']} is Leaf's fixed transport contract, so Leaf keeps"
            " its own and ignores this layer's"
        ),
        keeps=None,
    ),
    "fixed-kernel-fact": _declared(
        lambda v: (
            f"{v['name']} is Leaf's own, so Leaf keeps its value and ignores"
            " this layer's"
        ),
        keeps=None,
    ),
    "undeclared-event-kind": _declared(
        lambda v: (
            f"$events.{v['key']} names {v['kind']!r}, which is none of"
            f" {', '.join(v['declared'])}, so no delivery carries its clauses"
        ),
        keeps=None,
    ),
    "invalid-when": _declared(
        lambda v: (
            f"$events.{v['key']}.{v['kind']} clause `when` is not a valid JSON"
            f" Schema: {v['reason']}"
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
            f"$languages.paths maps {json_value(v['extensions'])} to languages"
            " $languages.names does not declare"
        )
    ),
    "contract-resource": _declared(
        lambda v: (
            f"$data contract {v['contract']!r} resource expression"
            f" {v['expression']!r} is invalid: {v['error']}"
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
    # Its work role, which `$work.widgets` maps the declaration onto.
    "work-reference": _declared(
        lambda v: (
            f"$work worker assignment `{v['attr']}` must be declared in `refers`"
            ", as {}"
        )
    ),
    "work-state": _declared(
        lambda v: (
            f"$work state `{v['attr']}` must be recorded by a verb with unit widget"
            " and a value record on it"
        )
    ),
    "work-value": _declared(
        lambda v: (
            f"$work {v['key']} lists {json_value(v['values'])}, which state attribute"
            f" `{v['attr']}` does not admit"
        )
    ),
    # An element declaration, on its own.
    "invalid-declaration": _declared(
        lambda v: (
            "is not a valid declaration ($keys)"
            + (f" at `{_json_path(v['path'])}`" if v.get("path") else "")
            + f": {v['reason']}"
        )
    ),
    "attributes-schema": _declared(
        lambda v: f"attributes are not a valid JSON Schema: {v['reason']}"
    ),
    "invalid-example": _declared(
        lambda v: f"`example` is invalid: {Finding.loads(v['finding']).said}",
        keeps=None,
    ),
    "data-input": _declared(
        lambda v: {
            "inputs": "its <pre> is the text of its `value` input when the markup"
            " binds none, so content: data takes at most one `value` input",
            "words": "content: markdown takes no `value` input, since its <pre> is"
            " its words",
            "state": "its <pre> is the text of its `value` input when the markup"
            " binds none, so content: data takes no `value` input with a body"
            " record, whose <pre> is its state",
        }[v["reason"]]
    ),
    "requires": _declared(
        lambda v: f"`{v['key']}` requires {v['needs']}: {_plain(v['value'])}"
    ),
    "unnamed-module": _declared(
        lambda v: (
            "no declared tag has the name of "
            + ", ".join(v["modules"])
            + "; a page widget's module is page/widgets/<tag>.js, and a helper"
            " module stands elsewhere under page/"
        ),
        keeps=_SHOWS,
    ),
    "needs-module": _declared(
        lambda v: (
            f"declares {', '.join(v['keys'])}, which a module provides, and has"
            f" none at {v['module']}"
        )
    ),
    "unknown-declarations": _declared(
        lambda v: (
            f"`{v['key']}` names unknown element declarations {json_value(v['names'])}"
        )
    ),
    "undeclared-attributes": _declared(
        lambda v: f"`{v['key']}` names undeclared attributes {json_value(v['names'])}"
    ),
    "reading-role-attr": _declared(
        lambda v: f"`reading-role` {v['role']} instances require a string {v['attr']}"
    ),
    "data-contract": _declared(
        lambda v: (
            f"input `{v['input']}` (`inputs`) names unknown contract {v['contract']!r}"
        )
    ),
    "unknown-output-contract": _declared(
        lambda v: f"`outputs` `{v['output']}` names unknown contract {v['contract']!r}"
    ),
    "data-source": _declared(
        lambda v: (
            f"input `{v['input']}` (`inputs`) source attribute `{v['attr']}` is"
            " not declared a string, so only `leaf data`'s own grammar checks the"
            " names it holds"
        ),
        keeps=None,
    ),
    "measured-source": _declared(
        lambda v: (
            f"input `{v['input']}` (`inputs`) declares `measured` but no required"
            " `source` attribute"
            + (f" (`{v['attr']}` is optional)" if v["attr"] else "")
            + ", so an instance without one is never compared with its source's"
            " latest run"
        ),
        keeps=None,
    ),
    "measured-run": _declared(
        lambda v: (
            f"input `{v['input']}` (`inputs`) names `{v['attr']}` as `measured`,"
            " which is not a required nonempty string, so an instance without it is"
            " never compared with its source's latest run"
        ),
        keeps=None,
    ),
    "visual-id": _declared(
        lambda v: (
            "has addressable visual parts but does not require an `id` for their anchor"
        )
    ),
    # Its conditions, read against its own attributes.
    "predicate-attribute": _declared(
        lambda v: f"`{v['key']}` names undeclared attribute `{v['attr']}`"
    ),
    "predicate-schema": _declared(
        lambda v: _predicate(
            v,
            f"at {json_value(v['value'])}, which its own schema does not admit:"
            f" {v['reason']}",
        )
    ),
    "binding-written": _declared(
        lambda v: (
            "`inputs` binding attributes are authored, but"
            f" {json_value(v['attrs'])} are written by value records"
        )
    ),
    "run-written": _declared(
        lambda v: (
            f"`inputs` `measured` attribute `{v['attr']}` is an authored source"
            " receipt, but is written by a value record"
        )
    ),
    # Its interactions: its obligation, and the state its verbs write.
    "answering-detail": _declared(
        lambda v: _answering(
            v, f"detail condition names an undeclared or invalid field `{v['field']}`"
        )
    ),
    "awaits-verbs": _declared(
        lambda v: (
            f"`awaits` answers with verbs {json_value(v['verbs'])}, which are"
            " not `verbs` the user writes"
        )
    ),
    "awaits-value": _declared(
        lambda v: "`awaits` value must name a user-written verb (`verbs`)"
    ),
    "awaits-retired": _declared(
        lambda v: (
            f"`awaits` retires with `{v['flag']}`, but its `when` does not"
            f" require `{v['flag']}` absent"
        )
    ),
    "awaits-blanket": _declared(
        lambda v: (
            f"`awaits` blanket answer `{v['outcome']}` is not an outcome of a"
            " deciding verb that answers its obligation"
        )
    ),
    "verb-detail-schema": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) has an invalid detail schema: {v['reason']}"
        )
    ),
    "creates-unit": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) creates a child, so its fold unit must"
            " name the detail field carrying the child's id and it declares no record"
            " form"
        )
    ),
    "creates-detail": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) creates a child, so its detail must be"
            f" exactly the required id string `{v['unit']}` and the required non-empty"
            f" words `{v['words']}`"
        )
    ),
    "creates-unknown": _declared(
        lambda v: f"verb `{v['verb']}` (`verbs`) creates unknown child <{v['child']}>"
    ),
    "creates-owner": _declared(
        lambda v: _created(v, "whose `owners` does not admit the sender")
    ),
    "creates-content": _declared(
        lambda v: _created(v, "which must declare content markup")
    ),
    "creates-required": _declared(
        lambda v: _created(v, "which must require id and no other authored attributes")
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
            f"`verbs` `{v['verbs'][0]}` and `{v['verbs'][1]}` claim the"
            f" same physical record slot (unit `{v['unit']}`, {v['kind']}"
            + (f" `{v['attr']}`" if v["attr"] else "")
            + "); distinct verbs must record independently"
        )
    ),
    "unit-undeclared": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) must declare and require its fold unit"
            f" `{v['unit']}` in detail"
        )
    ),
    "unit-type": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) fold unit `{v['unit']}` must be a string"
        )
    ),
    "record-unit": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) names a `unit` its `{v['kind']}` record"
            f" already decides ({v['unit']!r}); leave `unit` out"
        )
    ),
    "record-within": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) records a position within"
            f" <{v['within']}>, which no package in the layer declares"
        )
    ),
    "position-container": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) records positions within <{v['within']}>,"
            " but no declaration places an element of that tag, holding members of"
            " its own, at or inside this widget, so a drop of the widget's own"
            f" members is refused; set `verbs.{v['verb']}.record.within` to "
            + (
                " or ".join(f"<{tag}>" for tag in v["containers"])
                if v["containers"]
                else "this widget's own tag, and give the elements it reorders"
                " `owners` naming this widget"
            )
        ),
        keeps=None,
    ),
    "body-content": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) records its body, so content must be"
            " data or markdown; projection states text rather than a prose subtree"
        )
    ),
    "body-nested": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) records its body but admits nested"
            f" widgets {json_value(v['widgets'])}; a text statement cannot reconstruct"
            " their state"
        )
    ),
    "record-undeclared": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) records undeclared attribute `{v['attr']}`"
        )
    ),
    "record-type": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) record attribute `{v['attr']}` must be"
            " a string or string enum; HTML attributes cannot restore another JSON type"
        )
    ),
    "deciding-verbs": _declared(
        lambda v: (
            f"`verbs` {json_value(v['verbs'])} all declare `decides: true`;"
            " only one verb may decide which members retire"
        )
    ),
    "deciding-verb": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) declares `decides: true`:"
            " the deciding verb folds by widget, is written by the user,"
            " and requires `outcome` as a string enum"
        )
    ),
    "verb-contract": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) binds detail field `{v['field']}` to"
            f" attribute `{v['attribute']}`: the field must be declared and the"
            " attribute declared a string"
        )
    ),
    "instance-contract": _refuses(
        _DECIDES,
        lambda at, v: (
            f"{at} attribute `{v['attribute']}` names unknown data contract"
            f" {v['contract']!r} for `{v['verb']}` detail field `{v['field']}`"
        ),
    ),
    "withdraws-outcome": _declared(
        lambda v: (
            f"verb `{v['verb']}` (`verbs`) declares `withdraws: {v['outcome']}`,"
            " which is not a value of its `outcome` field"
        )
    ),
    "retired-when": _declared(
        lambda v: (
            f"`retired-when` `{v['outcome']}` is invalid: <{v['owner']}>"
            " declares no deciding verb (`verbs`) with that outcome"
        )
    ),
    "answering-part": _declared(
        lambda v: _answering(
            v,
            "folds on a part rather than the widget, so `awaits.answered` gives"
            " it a condition with `empty` or `every`",
        )
    ),
    "answering-every": _declared(
        lambda v: _answering(
            v,
            f"requires every <{v['member']}>, but `every` needs a verb kept per"
            " member with no position record and no `empty` beside it, and a"
            " member that lists this widget in `owners` and requires `id`",
        )
    ),
    "answering-position": _declared(
        lambda v: _answering(v, "tests an empty container but records no position")
    ),
    "answering-members": _declared(
        lambda v: _answering(
            v,
            f"tests whether its container <{v['within']}> is empty, but that"
            " container's content is not members",
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
            f"tests <{v['within']}> `{v['attr']}` at {json_value(v['value'])}, which"
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
    "dependency-escapes": _captured(
        lambda v: "dependency escapes the page", keeps=_CONFINED
    ),
    "dependency-outside-page": _captured(
        lambda v: (
            "a page's own files (stylesheets, scripts, images, data) live under page/"
            f" or media/; {_MOVE_UNDER_PAGE}"
        )
    ),
    "dependency-symlink": _captured(
        lambda v: "dependency escapes its source directory through a symlink",
        keeps=_CONFINED,
    ),
    "dependency-unreadable": _captured(
        lambda v: f"cannot capture dependency: {v['error']}"
    ),
    "module-not-local": _captured(
        lambda v: (
            f"a bare module name has no import map to resolve it; {_IMPORT_BY_URL}"
        )
    ),
    "module-type": _captured(
        lambda v: "a module dependency must be JavaScript or JSON"
    ),
    "module-outside-page": _captured(
        lambda v: (
            "a module the page imports is a public entry point such as"
            " /runtime/widget-api.js, an http(s) URL, or the page's own file under"
            f" page/; {_MOVE_UNDER_PAGE}"
        )
    ),
    "script-not-utf8": _captured(lambda v: "JavaScript is not UTF-8"),
    "stylesheet-type": _captured(
        lambda v: "a stylesheet dependency must have CSS MIME type"
    ),
    "css-not-utf8": _captured(lambda v: "CSS is not UTF-8"),
    "css-url": lambda at, v: (
        f"{v['sheet']} at {v['row']}:{v['column']}: url() holds more than one value,"
        " so a browser drops its declaration without a word; write one quoted URL"
    ),
    "css-import": _captured(
        lambda v: "CSS @import requires a stylesheet with CSS MIME type"
    ),
    "revision-exists": _captured(lambda v: f"revision r{v['revision']} already exists"),
    "digest-collision": _captured(lambda v: "immutable artifact digest collision"),
    "manifest-digest": _captured(
        lambda v: "captured manifest digest does not match revision"
    ),
    "layer-import-remote": lambda at, v: (
        _capture_where(v) + "a layer module imports from another server, which the"
        " export leaves to load from there, so the file needs the network to draw"
    ),
    "layer-import-missing": _captured(lambda v: "captured layer import is missing"),
    # The package check's refusal.
    "package": _refuses(_COMPOSES, lambda at, v: v["text"]),
    # The widget quality report, for a widget's author.
    "unreadable-examples": _fails(
        _EXAMPLES, lambda at, v: f"widget examples could not be drawn: {v['error']}"
    ),
    "example": lambda at, v: f"{at} example: no worked example shows it",
    "keeps-first-box": lambda at, v: (
        f"{at} keeps-first-box: in a {v['layout']} page, {_size(v['first'])}"
        f" before upgrade, {_size(v['now'])} once presented"
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
    "attempt-conflict": _refuses(
        _RETRIED,
        lambda at, v: f"attempt {v['attempt']!r} already belongs to another event",
    ),
    "foreign-layer": _refuses(
        _READ_AS_WRITTEN,
        lambda at, v: _unservable_layer(
            v,
            f"was initialized by a Leaf at page protocol {v['recorded']}, and this Leaf"
            f" ({v['leaf']}) speaks protocol {v['protocol']}",
            "Update the page's Leaf runtime",
        ),
    ),
    "newer-layer": _refuses(
        _READ_AS_WRITTEN,
        lambda at, v: (
            f"{v['page']} was initialized by a Leaf newer than this one ({v['leaf']},"
            f" at page protocol {v['protocol']}), so this Leaf can neither serve nor"
            " write the page. Use a newer Leaf; in Claude Code, /reload-plugins loads"
            " the installed copy."
        ),
    ),
    "no-registry": _refuses(
        _ADMITS, lambda at, v: "the page has no layer.json; run `leaf page init` on it"
    ),
    "unknown-kind": _refuses(
        _ADMITS, lambda at, v: f"kind must be one of {json_value(v['kinds'])}"
    ),
    "invalid-event": _refuses(
        _ADMITS, lambda at, v: f"{v['kind']} event is invalid: {v['error']}"
    ),
    "unknown-revision": _refuses(
        _ADMITS,
        lambda at, v: (
            f"{v['kind']} revision must be one of {json_value(v['revisions'])}"
        ),
    ),
    "publication-owner": _refuses(
        _PUBLISHED, lambda at, v: "publication is owned by the checked source publisher"
    ),
    # An action or a report, against its widget's declaration.
    "unknown-sender": _refuses(
        _ADMITS,
        lambda at, v: (
            f"unknown report widget {v['widget']!r} in revision r{v['revision']};"
            " reports name page widgets only"
            if v["kind"] == "report"
            else f"unknown action widget {v['widget']!r} in revision r{v['revision']} or"
            " agent-authored thread markup"
        ),
    ),
    "undeclared-tag": _refuses(
        _ADMITS,
        lambda at, v: (
            f"registry no longer declares <{v['tag']}> for {v['kind']} widget"
            f" {v['widget']!r}"
        ),
    ),
    "foreign-verb": _refuses(
        _OWN_VOICE,
        lambda at, v: (
            f"<{v['tag']}> {v['verb']!r} is a verb the {v['writer']} writes; this"
            f" {v['kind']} came from the {v['sender']}"
        ),
    ),
    "undeclared-verb": _refuses(
        _ADMITS,
        lambda at, v: (
            f"<{v['tag']}> does not declare {v['kind']} verb {v['verb']!r}"
            + (
                f"; it declares {json_value(v['declared'])}"
                if v["kind"] == "report" and v["declared"]
                else ""
            )
        ),
    ),
    "invalid-detail": _refuses(
        _ADMITS,
        lambda at, v: (
            f"<{v['tag']}> {v['kind']} {v['verb']!r} detail is invalid: {v['error']}"
        ),
    ),
    "quoted-widget": _refuses(
        _LIVE,
        lambda at, v: (
            f"<{v['tag']}> {v['widget']!r} stands inside an exhibit (`exhibit`)"
        ),
    ),
    "created-exists": _refuses(
        _ONE_ID,
        lambda at, v: (
            f"<{v['tag']}> action {v['verb']!r} creates {v['created']!r}, which already"
            " names an authored element"
        ),
    ),
    "unknown-unit": _refuses(
        _ADMITS,
        lambda at, v: (
            f"{_invalid_record(v)}position record names unknown unit {v['unit']!r}"
        ),
    ),
    "unknown-destination": _refuses(
        _ADMITS,
        lambda at, v: (
            f"{_invalid_record(v)}position record names unknown destination"
            f" {v['destination']!r}"
        ),
    ),
    "foreign-destination": _refuses(
        _ADMITS,
        lambda at, v: (
            f"{_invalid_record(v)}position record destination {v['destination']!r} is"
            f" <{v['found']}>, not <{v['within']}>"
        ),
    ),
    "foreign-unit": _refuses(
        _ADMITS,
        lambda at, v: (
            f"{_invalid_record(v)}position record unit {v['unit']!r} is not owned by"
            f" action widget {v['widget']!r}"
        ),
    ),
    "nested-unit": _refuses(
        _ADMITS,
        lambda at, v: (
            f"{_invalid_record(v)}position record cannot put {v['unit']!r} inside itself"
            f" or its descendant {v['destination']!r}"
        ),
    ),
    "outside-destination": _refuses(
        _ADMITS,
        lambda at, v: (
            f"{_invalid_record(v)}position record destination {v['destination']!r} is"
            f" outside action widget {v['widget']!r}"
        ),
    ),
    "unowned-placement": _refuses(
        _ADMITS,
        lambda at, v: (
            f"{_invalid_record(v)}position record cannot put <{v['unit_tag']}>"
            f" {v['unit']!r} within <{v['found']}> {v['destination']!r}"
        ),
    ),
    "unknown-members": _refuses(
        _ADMITS,
        lambda at, v: (
            f"{_invalid_record(v)}{', '.join(v['strangers'])} name no member of"
            f" {v['widget']!r}"
        ),
    ),
    "stale-move": _refuses(
        _AS_SEEN,
        lambda at, v: (
            f"{v['kind']} {v['verb']!r} on {v['widget']!r} was made on r{v['revision']},"
            f" and r{v['newest']} authors {v['container']!r} differently"
        ),
    ),
    # A comment's anchor and hold.
    "datum-unknown-section": _refuses(
        _ADMITS, lambda at, v: f"datum anchor names unknown section {v['section']!r}"
    ),
    "datum-unbound-source": _refuses(
        _ADMITS,
        lambda at, v: (
            f"datum anchor source {v['source']!r} is not bound by section {v['section']!r}"
        ),
    ),
    "datum-unsupplied-source": _refuses(
        _ADMITS,
        lambda at, v: (
            f"datum anchor source {v['source']!r} has never been supplied to this page"
        ),
    ),
    "datum-undrawn-source": _refuses(
        _ADMITS,
        lambda at, v: (
            f"datum anchor names what source {v['source']!r} holds now, an error"
            f" rather than a value section {v['section']!r} could draw: {v['why']}"
        ),
    ),
    "hold-target": _refuses(
        _ADMITS,
        lambda at, v: (
            "comment holds must name the widget on the page that its anchor names, with"
            " no passage, datum or part"
        ),
    ),
    "visual-with-passage": _refuses(
        _ADMITS,
        lambda at, v: (
            f"visual anchor {v['visual']!r} names a box rather than a passage, so it"
            " cannot also carry a quote or a datum"
        ),
    ),
    "undeclared-visual": _refuses(
        _ADMITS,
        lambda at, v: (
            f"visual anchor {v['visual']!r} is not declared on section {v['section']!r};"
            f" {admitted_parts(v['prefixes'])}"
        ),
    ),
    # A message, an edit, and a thread's presentation.
    "unknown-parent": _refuses(
        _ADMITS, lambda at, v: f"unknown parent {v['parent']!r}"
    ),
    "withdrawn-parent": _refuses(
        _TAKEN_BACK, lambda at, v: f"parent {v['parent']!r} has been taken back"
    ),
    "unknown-message": _refuses(
        _ADMITS, lambda at, v: f"unknown message {v['message']!r}"
    ),
    "foreign-message": _refuses(
        _OWN_VOICE,
        lambda at, v: f"message {v['message']!r} is not {v['author']}-authored",
    ),
    "wordless-message": _refuses(
        _ADMITS, lambda at, v: f"message {v['message']!r} has no words to revise"
    ),
    "withdrawn-message": _refuses(
        _TAKEN_BACK, lambda at, v: f"message {v['message']!r} has been taken back"
    ),
    "stale-edit": _refuses(
        _AS_SEEN,
        lambda at, v: (
            f"edit of {v['message']!r} was written over {v['base']!r}, and"
            f" {v['latest']!r} has since revised it"
        ),
    ),
    "unchanged-edit": _refuses(
        _EDITED,
        lambda at, v: f"edit of {v['message']!r} says what the message already says",
    ),
    "missing-thread": _refuses(
        _ADMITS, lambda at, v: f"unknown thread {v['thread']!r}"
    ),
    "summary-endpoints": _refuses(
        _ADMITS, lambda at, v: "summary endpoints must name spoken turns in one thread"
    ),
    "summary-order": _refuses(
        _ADMITS,
        lambda at, v: (
            f"summary's `from` {v['from']!r} comes after its `through` {v['through']!r}"
            " in thread order"
        ),
    ),
    "reanchor-thread": _refuses(
        _ADMITS, lambda at, v: "reanchor needs an open anchored thread"
    ),
    "reanchor-section": _refuses(
        _ADMITS,
        lambda at, v: (
            "reanchor must retain the thread's surviving section or detach it"
        ),
    ),
    "unknown-content-version": _refuses(
        _NAMES,
        lambda at, v: (
            f"{v['version']!r} is not a content version of agent message {v['message']!r}"
        ),
    ),
    # An undo (`events.UndoReading`): `undoes` names the gesture, `target` its kind.
    "unknown-undo": _refuses(_NAMES, lambda at, v: f"unknown undoes {v['undoes']!r}"),
    "foreign-gesture": _refuses(
        _OWN_VOICE,
        lambda at, v: f"{v['target']} {v['undoes']} is not the user's own gesture",
    ),
    "withdrawn-gesture": _refuses(
        _ONCE, lambda at, v: f"{v['undoes']} has already been taken back"
    ),
    "unundoable": _refuses(
        _ADMITS,
        lambda at, v: (
            f"{v['target']} events cannot be taken back (the kinds that can are"
            f" {', '.join(v['undoable'])})"
        ),
    ),
    "absorbed-move": _refuses(
        _UNDONE,
        lambda at, v: (
            f"move {v['undoes']} was made on r{v['revision']}, and a later revision's"
            " markup now places its unit; move it again instead"
        ),
    ),
    # A to-do, a start and an ending (`todos.todo_error`, `work.widget_seat_error`).
    "not-a-widget": _refuses(
        _NAMES, lambda at, v: f"{v['widget']!r} is not a widget on this page"
    ),
    "not-an-element": _refuses(
        _NAMES, lambda at, v: f"{v['element']!r} is not an element on this page"
    ),
    "plan-depth": lambda at, v: (
        f"plan step {v['step']!r} is at depth {v['depth']}, more than one below the"
        " step before it, so the plan shows it one level below that step; the first"
        " step is at depth 0 and each is at most one deeper than the one above"
    ),
    "unknown-plan-item": _refuses(
        _NAMES,
        lambda at, v: (
            f"{v['item']!r} names no to-do or obligation on this page; name an id from"
            " `leaf page state`, or write a new step as a `todo` with its title"
        ),
    ),
    "plan-empty-heading": _refuses(
        _STANDS,
        lambda at, v: (
            f"plan heading {v['title']!r} has no step under it; write a step of work"
            " as a `todo` with its title, or put steps one level below the heading"
        ),
    ),
    "unowed-start": _refuses(
        _NAMES,
        lambda at, v: (
            f"{v['item']!r} is neither an open to-do of yours nor an update you owe an"
            " answer to; start the id a delivered update or `leaf task create` gave you"
        ),
    ),
    "obligation-end": _refuses(
        _NAMES,
        lambda at, v: (
            f"{v['todo']!r} is the user's to answer, not a to-do; "
            + (
                "once they answer it elsewhere or it no longer applies, resolve its thread"
                f" with `leaf thread resolve <page> {v['message']}`, after a reply saying"
                " how if the thread should record it"
                if v["message"]
                else "record their answer in the widget's state, or withdraw the widget, in"
                " a revision"
            )
        ),
    ),
    "unasked-obligation": _refuses(
        _ASKED_AGAIN,
        lambda at, v: (
            f"no message in this thread asks the question {v['question']!r}; --obligation"
            " takes an id from the delivery's `settled` or `leaf page state`, and without"
            " an id it asks a new question"
        ),
    ),
    "ended-todo": _refuses(
        _ENDED, lambda at, v: f"to-do {v['todo']!r} has already ended ({v['state']})"
    ),
    "unknown-todo": _refuses(_NAMES, lambda at, v: f"unknown to-do {v['todo']!r}"),
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
    # A `page init`, or the renewal a command naming the page made
    # (`vendoring.renew_layer`), and the service it held down
    # (`hosting.restarting_server`).
    "unready-reinit": lambda at, v: (
        f"re-initialized {v['page']}, but index.html will not activate until"
        " `leaf page check` passes:\n" + "\n".join(f"  - {e}" for e in v["errors"])
    ),
    "renewal-refused": lambda at, v: (
        f"{v['page']} is at an older page protocol, and this Leaf could not take it"
        f" to its own: {v['error']}"
    ),
    # A start from a Leaf that doesn't act for the session the environment names
    # (`hosting.claim_and_start`, `harness.unserved_session`).
    "serves-for-no-session": lambda at, v: (
        f"this Leaf ({v['leaf']}) isn't the one session {v['session']}'s hooks run,"
        f" so it serves {v['page']} for no session: the session's hooks won't hear"
        f" it. Hear it with `{v['leaf']}/bin/leaf wait {v['page']}`."
    ),
    "server-stays-stopped": lambda at, v: (
        f"{v['page']}'s server stays stopped; `leaf server start {v['page']}` serves"
        " it again."
    ),
    "server-unowned": lambda at, v: (
        f"{v['page']}'s server has no live session owner, so it stays stopped;"
        f" `leaf server start {v['page']}` serves it for this one."
    ),
    "stopped-during-init": lambda at, v: (
        f"{v['page']}'s server was stopped while `page init` held it down, so it"
        " stays stopped."
    ),
    # `page check`'s advice on a page whose live server runs another Leaf
    # (`layer.other_serving_leaf`), named by the path and commit it records.
    "another-leaf-serving": lambda at, v: (
        f"{v['page']}'s server runs the Leaf at {v['path']}"
        + (f" ({v['commit']})" if v["commit"] else "")
        + ", not this one, so the user's tab may not draw what this Leaf checked;"
        f" restart it with `leaf server stop {v['page']}` then"
        f" `leaf server start {v['page']}`"
    ),
    # `page check`'s advice on a page holding drafts a Leaf of another version kept,
    # which this one never reads (`validation.command.other_version_drafts`).
    "other-version-drafts": lambda at, v: (
        f"{v['page']} keeps unsent drafts another Leaf version wrote, in {v['file']},"
        " which this Leaf doesn't read: tell the user where they are rather than"
        " reading them, and remove the file when they say"
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
    # back or could not, and why it ended. A prompt hook that could not serve a
    # session's page again says so too (`reconnect.serve_again`).
    "server-restarted": lambda at, v: (
        f"{v['page']}: server had died; restarted at {v['url']}"
    ),
    "revive-refused": lambda at, v: (
        f"{v['page']}: server was down and did not start again: {v['error']}"
    ),
    "server-down": lambda at, v: (
        f"{v['page']}: server is not running; restart it with"
        f" `leaf server start {v['page']}`"
    ),
    "not-owned": lambda at, v: (
        f"stopped watching {', '.join(v['pages'])}: this session no longer owns"
        + (" it" if len(v["pages"]) == 1 else " them")
    ),
    "held-for-a-session": lambda at, v: (
        f"stopped watching {v['page']}: {v['holder']} holds it, and this Leaf acts"
        f" for no session; `leaf server start {v['page']}` in an agent session takes"
        " it over"
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
    # The thread and task commands' refusals (`thread`, `tasks.cmd_create`), before or
    # beside the append door's. `held` is what the log holds a refused id as
    # (`authored_checks.admission.logged_id`), and `answer` the command that answers an
    # owed update (`activity.answer_command`).
    "unknown-comment": _refuses(
        _NAMES,
        lambda at, v: (
            f"unknown message id {v['name']!r}"
            + (f"; {v['held']}" if v.get("held") else "")
            + f"; known: {json_value(v['known'])}"
        ),
    ),
    "widget-not-thread": _refuses(
        _NAMES, lambda at, v: f"{v['name']} is a widget on the page, not a thread"
    ),
    "unknown-subject": _refuses(
        _NAMES,
        lambda at, v: (
            f"{v['subject']!r} names no thread, widget or element on this page; `{v['page']}`"
            " names the page as a whole"
        ),
    ),
    "invalid-source": _refuses(
        _PUBLISHES,
        lambda at, v: (
            f"cannot {v['operation']} while index.html is invalid: {v['error']}"
        ),
    ),
    "unanchorable": _refuses(
        _PASSAGE,
        lambda at, v: (
            f"can't anchor in revision r{v['revision']}: {v['error']}"
            + (
                f"; {v['held']}, while `--section` takes an element id the page's markup"
                " declares"
                if v.get("held")
                else ""
            )
        ),
    ),
    # What `thread create --part` notes beside a thread on a part its visual didn't
    # draw (`anchor_capture.drawn_part`): one the page shows on the whole visual, and
    # one no drawing of the page could check.
    "part-on-whole": lambda at, v: (
        f"§ {v['section']} drew no part {v['part']!r} {v['when']}, so the thread"
        " stands on the whole visual until the visual draws that part; it drew"
        f" {', '.join(v['drew'])}"
    ),
    "unchecked-part": lambda at, v: (
        f"Leaf couldn't read what § {v['section']} draws, so it didn't check part"
        f" {v['part']!r}"
    ),
    "superseded-reply": _refuses(
        _NEWER,
        lambda at, v: (
            f"event {v['event']!r} no longer requires a reply to {v['parent']!r}; "
            + (v.get("held") or "read the current delivery or thread state")
        ),
    ),
    # What `thread.post_reply` notes beside a message that answers nothing: progress
    # on an update no longer owed, which takes nothing in hand; an answer to an
    # update whose earlier answer promised a to-do still open; and an answer the
    # thread it joins still owes.
    "superseded-progress": lambda at, v: (
        f"event {v['event']!r} no longer requires a reply, so this progress takes"
        " nothing in hand; "
        + (v.get("held") or "read the current delivery or thread state")
    ),
    "promised-todo": lambda at, v: (
        f"event {v['event']!r} was already answered by {v['todo']!r}, whose to-do"
        f" {v['title']!r} is still open, so this reply answers nothing new;"
        f' `leaf task end {v["page"]} {v["todo"]} done --text "<where the result is>"`'
        " ends the to-do"
    ),
    "owed-response": lambda at, v: (
        f"thread {v['thread']!r} still owes the user an answer, which this message"
        f" doesn't give; {v['answer']} answers it"
    ),
    "reserved-answer": _refuses(
        _RESERVED,
        lambda at, v: (
            f"event {v['event']!r} is answered by this turn's messages; "
            + (
                "failure receipts wait for this turn to release the answer; answer in your"
                f" final message or with {v['command']}"
                if v["failure"]
                else f"use {v['command']} to commit an explicit answer"
            )
        ),
    ),
    "not-a-reply": _refuses(
        _VERSION_ANSWERS,
        lambda at, v: (
            f"response {v['reference']!r} requires {v['answer']}, not a reply"
        ),
    ),
    "title-fitted": lambda at, v: (
        f"the title ran past {v['limit']} characters, so it was cut to"
        f" {v['title']!r}; `leaf thread edit` with --title renames the thread"
    ),
    "ephemeral-content": _refuses(
        _IN_THREAD,
        lambda at, v: (
            "--ephemeral is for progress text; it cannot ask the user, open a to-do, hold"
            " a widget, report failure, or move the thread"
        ),
    ),
    "detach-with-target": _refuses(
        _PLAIN,
        lambda at, v: "--detach cannot be combined with --quote, --section, or --part",
    ),
    "held-anchor": _refuses(
        _HELD,
        lambda at, v: (
            f"thread {v['thread']!r} holds the widget its first comment was sent from, so"
            " its anchor cannot be moved or detached"
        ),
    ),
    "undeclared-answer": _refuses(
        _OWED,
        lambda at, v: (
            "say what the answer leaves: --done when it delivers what was asked, --todo"
            " TITLE when it promises work it doesn't deliver, or --obligation when it needs"
            " the user's next move"
            + (
                f"; or let the <{v['tag']} id={v['id']!r}> in the text ask in its place,"
                f" which it does with {v['needs']}"
                if v
                else " (a widget in the text may also ask)"
            )
        ),
    ),
    "obligation-beside-widget": lambda at, v: (
        f"the <{v['tag']} id={v['id']!r}> in the text also waits on the user, so"
        " this message asks twice: their pick answers the widget, and --obligation"
        " keeps the message on their On Me list until they reply in words or the"
        " thread is resolved"
    ),
    "detail-field": _refuses(
        _PLAIN, lambda at, v: f"detail fields are name=value, got {v['field']!r}"
    ),
    "edit-answered-widget": lambda at, v: (
        f"the user has acted on {at} in message {v['message']!r}; their answer stays"
        " recorded against its ids"
        + (
            ", so it shows on the markup this edit leaves there"
            if v["kept"]
            else ", and this edit removes what it chose, so the thread no longer shows"
            " that answer"
        )
    ),
    "edit-under-summary": lambda at, v: (
        f"message {v['message']!r} is folded under summary {v['summary']!r}, which"
        " stands as you wrote it; if this edit changes what it reports, summarize"
        f" {v['from']!r} through {v['through']!r} again with `leaf thread summarize`"
    ),
    "stays-closed": lambda at, v: (
        f"the user resolved thread {v['thread']!r}, so this message went into it"
        " without bringing it back to their list, which suits the answer or result"
        f" they asked for; `{v['command']}` brings it back where the message holds"
        " news they would want to stop and read"
    ),
    "untitled-thread": _refuses(
        _TITLED,
        lambda at, v: (
            f"thread {v['thread']!r} has no title yet; name its subject with"
            ' --title "<a few words>" on this reply'
        ),
    ),
    "title-kept": lambda at, v: (
        f"the thread is already titled {v['title']!r}, so the reply's title went"
        " unused; `leaf thread edit` with --title renames the thread"
    ),
}

# What a browser shows the person whose gesture a refusal turned down, where the
# agent's words name internals that person never sees (`Rejected.user`).
_USER = {
    "stale-move": "The page changed while I moved this; move it again.",
    "stale-edit": "The message changed while I edited it; edit it again.",
}


def _words(finding: Finding) -> str:
    said = _TEXT[finding.code]
    if isinstance(said, (_Refuses, _Unread)):
        said = said.words
    return said(finding.at, finding.values)


class Rejected(Refused):
    """A refusal of what a check found. Its words list the findings under
    `heading`, or are the findings' own words where there is none, and `findings`
    keeps their records for a reader that wants the facts.

    Every finding's code refuses or fails a check (`_refuses`, `_fails`), so a check
    refuses only with a guarantee to name. The person whose gesture was refused reads
    a finding's `_USER` words where its code has them, and otherwise its words
    without the guarantee (`Finding.said`)."""

    def __init__(self, findings: list[Finding], heading: str | None = None):
        findings = list(findings)
        if advice := [f.code for f in findings if not f.refuses]:
            raise ValueError(f"advice cannot refuse: {', '.join(advice)}")

        def listed(words) -> str:
            if heading:
                return f"{heading}:\n" + "\n".join(f"  - {words(f)}" for f in findings)
            return "\n".join(map(words, findings))

        super().__init__(listed(lambda f: f.refusal))
        # The person whose gesture it was reads what was refused, not the guarantee
        # the refusal tells the agent it keeps.
        if not heading and len(findings) == 1 and findings[0].code in _USER:
            self.user = _USER[findings[0].code]
        else:
            self.user = listed(lambda f: f.said)
        self.findings = findings
