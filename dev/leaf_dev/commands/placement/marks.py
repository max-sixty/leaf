"""Put each of Leaf's marks on a catalogue of boxes in the holders pages put them in,
and write a gallery of where each mark stands.

    uv run leaf-dev placement marks [--case NAME]... [--base [REF]] [--browser ENGINE]

A case is one box a reader marks, such as a paragraph, a table or a button, standing
in one holder, such as the reading column, a bounded block or a sideways scroll box.
Each case's box opens its holder, so it meets the holder's edges as such a box does on
a page. A content box takes three marks: the Alt aim (`aim`), a comment's mark while
its comment box is open (`comment`), and the focus that Escape from that box leaves
on it (`focus`). A control takes the aim and the keyboard's focus ring (`tab`). Add a
case for a box or holder someone meets: a line in `CASES`, and a holder in `HOLDERS`
if its holder isn't there yet.

The cases stand on one page, which the command builds from this working tree, and with
`--base` from the merge base with `main` (or REF) too (`leaf_dev.arms.choose_arms`),
and opens on each arm through `leaf_dev.visits`. Each mark is put on its box by the
reader's input alone, read and captured, and taken off before the next. What the
gallery reports beside each capture is measured in the tab, against the box that
draws the mark, which is the focused control's carrier for `tab`:

- how far the nearest box that clips it cuts the mark, side by side;
- how far the mark's band runs over the box's words, side by side, where it stands
  inside the box: a band inside a table's edge crosses its cells' padding, and one
  inside a paragraph's crosses its first and last letters.

Each run writes `.tmp/marks/report/marks.html`, a Leaf page of the gallery with its
captures in `media/`, replacing the last run's, so a running `--user` preview of it
shows the new run as a revision, with the threads left on it where they were. The
run's own directory, `.tmp/marks/run-*/`, holds `readings.jsonl`, one line per case,
mark and arm, and each failure's traceback. The command prints the preview command.
"""

import html
import json
import shutil
import traceback
from dataclasses import dataclass
from pathlib import Path

import click
from PIL import Image
from playwright.sync_api import Page

from leaf_dev import ROOT, gallery
from leaf_dev.arms import base_option, choose_arms, run_directory
from leaf_dev.browser import WINDOWS, engine_option, launch, screenshot
from leaf_dev.states import State
from leaf_dev.visits import said, visits

OUT = ROOT / ".tmp" / "marks"
# The report every run rewrites, so a preview of it follows each run as a revision of
# one page and keeps the threads on it; each run's captures stay in its own directory.
REPORT = OUT / "report"
WINDOW = WINDOWS["macbook"]
# Device pixels captured per CSS pixel, so a two-pixel band reads in the gallery.
SCALE = 2

CONTENT = ("aim", "comment", "focus")
CONTROL = ("aim", "tab")
MARKS = {
    "aim": "Alt aim",
    "comment": "Comment",
    "focus": "Focus after Escape",
    "tab": "Keyboard focus",
}

FILLER = "<p>More of the holder's content.</p>" * 6
TABLE = (
    "<table{id}><thead><tr><th>Kind</th><th>Where its marks stand</th></tr></thead>"
    "<tbody><tr><td>Region</td><td>Outside its edge</td></tr>"
    "<tr><td>Control</td><td>Outside, a control's gap off</td></tr></tbody></table>"
)
PATCH = """<pre>
diff --git a/one.py b/one.py
--- a/one.py
+++ b/one.py
@@ -1,1 +1,1 @@
-old
+new
diff --git a/two.py b/two.py
--- a/two.py
+++ b/two.py
@@ -1,1 +1,1 @@
-old
+new
</pre>"""


@dataclass(frozen=True)
class Holder:
    """A box that holds a case's box: its title, what it is, and its markup, whose
    `{}` the case's box fills."""

    title: str
    says: str
    markup: str


HOLDERS = {
    "column": Holder(
        "The reading column",
        "Nothing clips a box in the column, so every mark stands where its box's "
        "kind says.",
        "<div>{}</div>",
    ),
    "bounded": Holder(
        "A bounded block",
        "A block bounded with data-bound scrolls down inside its height, and so clips "
        "across too.",
        f'<div data-bound="start" style="--lf-bound: 11rem">{{}}{FILLER}</div>',
    ),
    "short": Holder(
        "A bounded block shorter than its bound",
        "A short log stands as tall as what it holds, so its first and last lines meet "
        "its top and bottom.",
        '<div data-bound="end">{}</div>',
    ),
    "scroller": Holder(
        "A sideways scroll box the page made",
        "A box the page's own CSS makes scroll across, as a wide table's wrapper "
        "does, without Leaf's scroll class.",
        '<div style="overflow-x: auto">{}</div>',
    ),
    "classed": Holder(
        "A sideways scroll box with lf-scroll",
        "The same box with Leaf's class for a box that scrolls across.",
        '<div class="lf-scroll" style="overflow-x: auto">{}</div>',
    ),
    "board": Holder(
        "A board",
        "A board scrolls its columns across, and each column scrolls its cards down.",
        "{}",
    ),
}


@dataclass(frozen=True)
class Case:
    """One box in one holder: its name, which is its box's id, the holder's key in
    `HOLDERS`, what the box is, its markup, whose `{id}` takes the box's id, the marks
    it takes, and where the marked box stands when it isn't the element with the id,
    as a Playwright selector."""

    name: str
    holder: str
    says: str
    markup: str
    marks: tuple[str, ...] = CONTENT
    target: str | None = None

    @property
    def selector(self) -> str:
        return self.target or f"#{self.name}"


def box(markup: str, name: str) -> str:
    return markup.replace("{id}", f' id="{name}"')


CASES = [
    Case(
        "column-paragraph",
        "column",
        "A paragraph",
        "<p{id}>A paragraph in the reading column, which nothing clips.</p>",
    ),
    Case(
        "column-item",
        "column",
        "A list item beside its marker",
        "<ul><li{id}>A list item beside its marker.</li><li>Another item.</li></ul>",
    ),
    Case(
        "column-link",
        "column",
        "A link opening a line",
        '<p><a{id} href="#column-link">A link that opens a line</a> in a paragraph.</p>',
        CONTROL,
    ),
    Case(
        "bounded-paragraph",
        "bounded",
        "A paragraph",
        "<p{id}>A paragraph in a bounded block, which fills the block's width as any "
        "paragraph does.</p>",
    ),
    Case(
        "bounded-heading",
        "bounded",
        "A heading",
        "<h3{id}>A heading in a bounded block</h3>",
    ),
    Case(
        "bounded-item",
        "bounded",
        "A list item beside its marker",
        "<ul><li{id}>A list item in a bounded block, long enough to reach the block's "
        "far side and wrap.</li><li>Another item.</li></ul>",
    ),
    Case(
        "bounded-link",
        "bounded",
        "A link opening a line",
        '<p><a{id} href="#bounded-link">A link that opens a line</a> in the block.</p>',
        CONTROL,
    ),
    Case("bounded-table", "bounded", "A table", TABLE),
    Case(
        "bounded-code",
        "bounded",
        "A code block",
        "<pre{id}><code>uv run leaf-dev placement marks --base</code></pre>",
    ),
    Case(
        "bounded-button",
        "bounded",
        "A button opening a line",
        '<p><button{id} type="button">A button</button> beside its words.</p>',
        CONTROL,
    ),
    Case(
        "bounded-option",
        "bounded",
        "An option row",
        '<lf-group id="bounded-option-group" label="Which map?"><lf-options'
        ' id="bounded-option-choice"><lf-option{id}>Street map</lf-option>'
        '<lf-option id="bounded-option-b">Trail map</lf-option></lf-options>'
        "</lf-group>",
        CONTROL,
    ),
    Case(
        "bounded-filter",
        "bounded",
        "A diff's file filter, a search field",
        f"<lf-diff{{id}}>{PATCH}</lf-diff>",
        ("tab",),
        "#bounded-filter wa-input",
    ),
    Case(
        "short-last",
        "short",
        "Its last line",
        "<p>The first line of a short log.</p><p{id}>Its last line.</p>",
    ),
    Case("scroller-table", "scroller", "A table filling the box", TABLE),
    Case(
        "scroller-wide",
        "scroller",
        "A table wider than the box",
        TABLE.replace("<table{id}>", '<table{id} style="inline-size: 1400px">'),
    ),
    Case(
        "scroller-paragraph",
        "scroller",
        "A paragraph",
        "<p{id}>A paragraph in a box that scrolls across.</p>",
    ),
    Case("classed-table", "classed", "A table filling the box", TABLE),
    Case(
        "board-column",
        "board",
        "The first column",
        '<lf-board id="board-column-board"><lf-column{id} label="Ready"><lf-card'
        ' id="board-column-card" label="A card"><strong>A card</strong></lf-card>'
        '</lf-column><lf-column id="board-column-later" label="Later"></lf-column>'
        "</lf-board>",
    ),
    Case(
        "board-card",
        "board",
        "A card in the first column",
        '<lf-board id="board-card-board"><lf-column id="board-card-ready" label="Ready">'
        '<lf-card{id} label="A card"><strong>A card</strong> standing first in its'
        ' column.</lf-card></lf-column><lf-column id="board-card-later" label="Later">'
        "</lf-column></lf-board>",
    ),
]


def fixture(cases: list[Case]) -> str:
    """The page every case stands on, each in a holder of its own."""
    blocks = "\n".join(
        f'<section id="case-{case.name}" tabindex="-1"><h2 style="margin-block-end: 32px">{html.escape(case.name)}</h2>\n'
        + HOLDERS[case.holder].markup.replace("{}", box(case.markup, case.name))
        + "\n</section>"
        for case in cases
    )
    return gallery.page(
        "Mark cases",
        "Boxes in the holders pages put them in, for leaf-dev placement marks.",
        f"<h1>Mark cases</h1>\n{blocks}",
    )


# The mark `kind` on `target`, read against the box that draws it and the nearest box
# clipping that one, in CSS pixels of the viewport.
READ = r"""([target, kind]) => {
  const up = (el) =>
    el.assignedSlot ?? el.parentElement ??
    (el.getRootNode() instanceof ShadowRoot ? el.getRootNode().host : null);
  let start = target;
  if (kind === "tab") {
    start = document.activeElement;
    while (start?.shadowRoot?.activeElement) start = start.shadowRoot.activeElement;
  }
  const px = (value) => Number.parseFloat(value) || 0;
  const sides = (value) => {
    const v = value.split(" ").map(px);
    return [v[0], v[1] ?? v[0], v[2] ?? v[0], v[3] ?? v[1] ?? v[0]];
  };
  let carrier = null;
  let style = null;
  for (let at = start; at; at = up(at)) {
    const s = getComputedStyle(at);
    if ((s.outlineStyle !== "none" && px(s.outlineWidth) > 0) || s.borderImageSource !== "none") {
      carrier = at;
      style = s;
      break;
    }
    if (kind !== "tab") break;
  }
  const name = (el) => el.localName + (el.id ? "#" + el.id : "") +
    (el.getAttribute("part") ? `::part(${el.getAttribute("part")})` : "");
  const box = (carrier ?? target).getBoundingClientRect();
  const rect = (r) => ({ left: r.left, top: r.top, right: r.right, bottom: r.bottom });
  const reading = {
    box: rect(box),
    focused: start && start !== target ? name(start) : null,
    flush: target.hasAttribute("data-lf-flush"),
  };
  if (!carrier) return { ...reading, carrier: null };
  let outer;
  let band;
  if (style.borderImageSource !== "none") {
    const [t, r, b, l] = sides(style.borderImageOutset);
    outer = { left: box.left - l, top: box.top - t, right: box.right + r, bottom: box.bottom + b };
    band = sides(style.borderImageWidth)[0];
  } else {
    const reach = px(style.outlineOffset) + px(style.outlineWidth);
    outer = { left: box.left - reach, top: box.top - reach, right: box.right + reach, bottom: box.bottom + reach };
    band = px(style.outlineWidth);
  }
  const inner = { left: outer.left + band, top: outer.top + band, right: outer.right - band, bottom: outer.bottom - band };
  let clip = null;
  let clipping = null;
  for (let at = up(carrier); at && at !== document.documentElement && at !== document.body; at = up(at)) {
    const s = getComputedStyle(at);
    if (s.overflowX !== "visible" || s.overflowY !== "visible") {
      clip = at;
      clipping = s;
      break;
    }
  }
  const cut = { left: 0, top: 0, right: 0, bottom: 0 };
  if (clip) {
    // A box that scrolls shows everything it scrolls through, as the runtime reads it
    // (dom/geometry.js, `clipsMarks`), so a scroll never counts as a cut.
    const r = clip.getBoundingClientRect();
    const scrolls = (overflow) => overflow === "auto" || overflow === "scroll";
    const across = scrolls(clipping.overflowX);
    const down = scrolls(clipping.overflowY);
    const left = r.left + clip.clientLeft - (across ? clip.scrollLeft : 0);
    const top = r.top + clip.clientTop - (down ? clip.scrollTop : 0);
    const shows = {
      left,
      top,
      right: left + (across ? clip.scrollWidth : clip.clientWidth),
      bottom: top + (down ? clip.scrollHeight : clip.clientHeight),
    };
    if (clipping.overflowX !== "visible") {
      cut.left = Math.max(0, shows.left - outer.left);
      cut.right = Math.max(0, outer.right - shows.right);
    }
    if (clipping.overflowY !== "visible") {
      cut.top = Math.max(0, shows.top - outer.top);
      cut.bottom = Math.max(0, outer.bottom - shows.bottom);
    }
  }
  const words = { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity };
  const walker = document.createTreeWalker(carrier, NodeFilter.SHOW_TEXT);
  for (let text = walker.nextNode(); text; text = walker.nextNode()) {
    if (!text.data.trim()) continue;
    const range = document.createRange();
    range.selectNodeContents(text);
    for (const r of range.getClientRects()) {
      if (!r.width || !r.height) continue;
      words.left = Math.min(words.left, r.left);
      words.top = Math.min(words.top, r.top);
      words.right = Math.max(words.right, r.right);
      words.bottom = Math.max(words.bottom, r.bottom);
    }
  }
  const over = { left: 0, top: 0, right: 0, bottom: 0 };
  if (words.left < Infinity) {
    over.left = Math.max(0, inner.left - words.left);
    over.right = Math.max(0, words.right - inner.right);
    over.top = Math.max(0, inner.top - words.top);
    over.bottom = Math.max(0, words.bottom - inner.bottom);
  }
  return {
    ...reading,
    carrier: name(carrier),
    offset: style.borderImageSource !== "none" ? null : style.outlineOffset,
    mark: rect(outer),
    clip: clip ? name(clip) : null,
    cut,
    over,
  };
}"""


def wait_on(page: Page, selector: str, attribute: str, present: bool = True) -> None:
    page.locator(selector).evaluate(
        f"""(el) => new Promise((done, failed) => {{
          const started = performance.now();
          const check = () => {{
            const now = el.hasAttribute('{attribute}');
            if (now === {str(present).lower()}) return done();
            if (performance.now() - started > 5000)
              return failed(new Error('{attribute} never {"came" if present else "went"}'));
            requestAnimationFrame(check);
          }};
          check();
        }})"""
    )


def frames(page: Page, count: int = 2) -> None:
    page.evaluate(
        "(count) => new Promise((done) => { const step = (n) => n ? "
        "requestAnimationFrame(() => step(n - 1)) : done(); step(count); })",
        count,
    )


def aim(page: Page, case: Case) -> None:
    """Hold Alt over the case's box, near its start, where its own words are."""
    where = page.locator(case.selector).bounding_box()
    assert where is not None
    page.mouse.move(where["x"] + 14, where["y"] + 9)
    page.keyboard.down("Alt")
    page.mouse.move(where["x"] + 16, where["y"] + 10)
    wait_on(page, case.selector, "data-lf-aimed")


# Whether focus stands in `target`, in its shadow trees included.
FOCUS_IN = """(target) => {
  let at = document.activeElement;
  while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
  for (; at; at = at.assignedSlot ?? at.parentElement ?? at.getRootNode().host)
    if (at === target) return true;
  return false;
}"""


def tab_to(page: Page, case: Case) -> None:
    """Tab from the start of the case's section until focus stands in its box, as a
    reader's keyboard reaches it, passing any stop on the way, such as a holder that
    scrolls."""
    page.locator(f"#case-{case.name}").focus()
    target = page.locator(case.selector)
    for _ in range(12):
        page.keyboard.press("Tab")
        if target.evaluate(FOCUS_IN):
            return
    raise AssertionError(f"Tab never reached {case.selector}")


def put(page: Page, case: Case, mark: str) -> None:
    """Put `mark` on the case's box by the reader's input."""
    if mark == "aim":
        aim(page, case)
    elif mark == "comment":
        aim(page, case)
        page.mouse.down()
        page.mouse.up()
        page.keyboard.up("Alt")
        wait_on(page, case.selector, "data-lf-mark")
    elif mark == "focus":
        page.keyboard.press("Escape")
        page.wait_for_function(
            "(selector) => document.querySelector(selector)"
            "?.getAttribute('data-lf-mark') === 'focus'",
            arg=case.selector.split(" ")[0],
        )
    elif mark == "tab":
        tab_to(page, case)
    frames(page)


def take_off(page: Page, case: Case, mark: str) -> None:
    """Take the case's mark off before the next, leaving the comment box open
    between a comment and the focus its Escape leaves."""
    if mark == "comment":
        return
    if mark == "aim":
        page.keyboard.up("Alt")
    page.mouse.move(0, 0)
    page.evaluate(
        "() => { let at = document.activeElement;"
        " while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;"
        " at?.blur(); }"
    )
    wait_on(page, case.selector.split(" ")[0], "data-lf-aimed", present=False)
    frames(page)


def visit(page: Page, cases: list[Case], out: Path, arm: str) -> list[dict]:
    """Put each case's marks on it in turn, reading and capturing each."""
    seen = []
    for case in cases:
        holder = page.locator(f"#case-{case.name} > :last-child")
        holder.evaluate(
            "el => el.scrollIntoView({block: 'center', behavior: 'instant'})"
        )
        frames(page)
        for mark in case.marks:
            record: dict = {"case": case.name, "mark": mark, "arm": arm}
            try:
                put(page, case, mark)
                record["reading"] = page.locator(case.selector).evaluate(
                    f"(target) => ({READ})([target, {json.dumps(mark)}])"
                )
                record["holder"] = holder.evaluate(
                    "el => { const r = el.getBoundingClientRect();"
                    " return {left: r.left, top: r.top, right: r.right, bottom: r.bottom}; }"
                )
                shot = out / f"{case.name}-{mark}-{arm}.png"
                shot.write_bytes(screenshot(page))
                record["shot"] = str(shot)
                take_off(page, case, mark)
            except Exception as error:
                record["failed"] = said(error)
                record["traceback"] = "".join(traceback.format_exception(error))
                page.keyboard.up("Alt")
                page.keyboard.press("Escape")
                page.keyboard.press("Escape")
                page.mouse.move(0, 0)
            seen.append(record)
    return seen


def crop_box(records: list[dict]) -> tuple[int, int, int, int]:
    """The rectangle round a case's holder, the same on every arm so a pair lines
    up, cut to the band round the marked box where the holder runs tall."""
    readings = [r for r in records if "reading" in r]
    left, top, right, bottom = gallery.frame(
        [r["holder"] for r in readings], 16, *WINDOW.size
    )
    marked_top = min(r["reading"]["box"]["top"] for r in readings) - 36
    marked_bottom = max(r["reading"]["box"]["bottom"] for r in readings) + 36
    if bottom - top > 260:
        top, bottom = max(top, marked_top), min(bottom, max(marked_bottom, top + 120))
    return int(left), int(top), int(right), int(bottom)


def sentence(record: dict) -> str:
    """What the reading says of the mark, in a phrase."""
    if "failed" in record:
        return f"failed: {record['failed']}"
    reading = record["reading"]
    if not reading["carrier"]:
        return "no mark drawn"

    def sides(amounts: dict) -> str:
        named = [(side, amounts[side]) for side in ("left", "right", "top", "bottom")]
        shown = [f"{amount:.0f}px at {side}" for side, amount in named if amount >= 0.5]
        return ", ".join(shown)

    cut, over = sides(reading["cut"]), sides(reading["over"])
    said_ = []
    if cut:
        said_.append(f"cut {cut}")
    if over:
        said_.append(f"over its words {over}")
    return "; ".join(said_) or "whole, clear of its words"


def report(
    cases: list[Case], records: list[dict], arms: dict, engine: str, out: Path
) -> Path:
    """Write the gallery into REPORT, replacing the last run's, and return its path."""
    media = REPORT / "media"
    shutil.rmtree(media, ignore_errors=True)
    media.mkdir(parents=True)
    by = {(r["case"], r["mark"], r["arm"]): r for r in records}
    sections = []
    for holder_key, holder in HOLDERS.items():
        rows = []
        for case in (c for c in cases if c.holder == holder_key):
            ran = [r for r in records if r["case"] == case.name]
            rect = crop_box(ran) if any("reading" in r for r in ran) else None
            tiles = []
            for mark in case.marks:
                got = {arm: by.get((case.name, mark, arm)) for arm in arms}
                images = {}
                for arm, record in got.items():
                    if record and "shot" in record and rect:
                        left, top, right, bottom = rect
                        crop = out / f"{case.name}-{mark}-{arm}.crop.png"
                        Image.open(record["shot"]).convert("RGB").crop(
                            (SCALE * left, SCALE * top, SCALE * right, SCALE * bottom)
                        ).save(crop)
                        images[arm] = gallery.media(media, crop.read_bytes())
                head = got.get("head")
                alt = f"{case.says} in {holder.title.lower()}, {MARKS[mark].lower()}"
                picture = (
                    gallery.shot(
                        f"{case.name}-{mark}-shot",
                        alt + (f": {sentence(head)}" if head else ""),
                        images.get("base"),
                        images["head"],
                    )
                    if "head" in images
                    else ""
                )
                said_ = "<br>".join(
                    f"{arm.capitalize() + ': ' if len(arms) > 1 else ''}"
                    f"{html.escape(sentence(record)) if record else 'not run'}"
                    for arm, record in got.items()
                )
                tiles.append(
                    f'<figure id="{case.name}-{mark}">{picture}<figcaption>'
                    f"<strong>{MARKS[mark]}</strong>: {said_}</figcaption></figure>"
                )
            rows.append(
                f'<h3 id="{case.name}">{html.escape(case.says)}</h3>\n'
                f'<div class="layout-tiles marks" data-width="available">\n'
                + "\n".join(tiles)
                + "\n</div>"
            )
        if rows:
            sections.append(
                f'<section id="{holder_key}">\n<h2>{html.escape(holder.title)}</h2>\n'
                f"<p>{html.escape(holder.says)}</p>\n"
                + "\n".join(rows)
                + "\n</section>"
            )
    commits = ", ".join(f"{arm} at {arm_.commit[:9]}" for arm, arm_ in arms.items())
    pairs = (
        " Each capture is a pair, the base's before this tree's; Pixels shows red where"
        " the base drew and blue where this tree draws."
        if "base" in arms
        else ""
    )
    page = REPORT / "marks.html"
    page.write_text(
        gallery.page(
            "Mark placements",
            "Where Leaf stands each of its marks on a catalogue of boxes, in the "
            "holders pages put them in.",
            f"""<h1 id="title">Mark placements</h1>
<p id="lede">Each capture is one of Leaf's marks on a box as {engine.capitalize()} draws
it ({commits}), beside how far a clip cuts the mark and how far it runs over the box's
words.{pairs} Regenerate with <code>uv run leaf-dev placement marks</code>; add a case
to <code>CASES</code> in <code>dev/leaf_dev/commands/placement/marks.py</code>.</p>
{chr(10).join(sections)}""",
            head=STYLE,
        ),
        encoding="utf-8",
    )
    return page


STYLE = """<style>
  .marks {
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 40rem), 1fr));
  }
</style>"""


@click.command("marks")
@click.option(
    "--case",
    "names",
    multiple=True,
    type=click.Choice([case.name for case in CASES]),
    help="Run only this case; repeat for more.",
)
@engine_option
@base_option()
def marks(names, engine, base) -> None:
    """Put each mark on each case of CASES, and write a gallery of where it stands
    (this module's header says what each reports)."""
    cases = [case for case in CASES if not names or case.name in names]
    out = run_directory(OUT)
    scratch = out / "scratch"
    scratch.mkdir()
    source = out / "cases.html"
    source.write_text(fixture(cases), encoding="utf-8")
    records: list[dict] = []
    with launch(engine) as browser:
        arms = choose_arms(base, scratch)

        def read(arm, visit_) -> None:
            visit_.doing = "read"
            records.extend(visit(visit_.page, cases, out, arm))

        with visits(
            browser,
            arms,
            State("marks", str(source), window=WINDOW),
            source,
            scratch,
            window=WINDOW,
            scheme="light",
            scale=SCALE,
            read=read,
        ) as each:
            for arm, visit_ in each:
                if visit_.error:
                    raise click.ClickException(
                        f"{arm}: {visit_.doing}: {said(visit_.error)}"
                    )
    with (out / "readings.jsonl").open("w") as readings:
        for record in records:
            readings.write(json.dumps(record) + "\n")
            click.echo(
                f"{record['case']} {record['mark']} {record['arm']}: {sentence(record)}"
            )
    page = report(cases, records, arms, engine, out)
    click.echo(page)
    click.echo(f"uv run leaf-dev preview --source {page} --slot marks --user")
    if any("failed" in record for record in records):
        raise click.ClickException("a mark failed; see its line in readings.jsonl")
