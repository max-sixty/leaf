"""Seat comment pins on a catalogue of targets and show where each one stands.

    uv run leaf-dev pins [--base [REF]]

A case is a small piece of page, ordinary or pathological, with comments anchored in it
(`CASES`). The catalogue is small, and its cases are the shapes that came to mind for a
pin to sit on, not ones picked because the placement handles them well; add one whenever
a page shows a placement that looks wrong. Every case stands on one page with no Layout,
so `main` fills the window and no rail stands beside it: each comment takes a pin. The
page is opened at each of `VIEWPORTS`, each case scrolled into view, and its pins read
against what they may not cover (`faults`).

The command builds that page from this working tree, and with `--base` from the merge
base with `main` (or REF) too, and writes a Leaf page at `.tmp/pins/report/pins.html`
that shows each case's crop at every viewport, its targets outlined in blue, beside the
faults read there. With `--base` each crop is an `lf-shot` pair that opens on its
changed pixels: where the base drew a pin in red, where this tree draws it in blue. Both
arms' crops of a case cover the same rectangle, so the pair lines up. Each run rewrites
that one page, so a running `--user` preview of it shows the new run as a revision, with
the threads left on it where they were. It prints the command that starts that preview.

The same catalogue is a test: `test_render_margin.py` asserts that every case at
every viewport has no fault beyond the kinds its `allow` accepts. So a case that
shows a bad placement goes into `CASES`; the test then fails until the placement is
fixed, or the case accepts that fault and says why in `why`, which the page shows.
A full run takes about 10s, and 20s with `--base`.
"""

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from html import escape
from math import hypot
from pathlib import Path

import click
from leaf.media import media_name
from PIL import Image, ImageDraw

from leaf_dev import ROOT
from leaf_dev.arms import base_ref, build_arm, run_directory, serving_source
from leaf_dev.browser import headless_shell, load, tab, use_linux_fonts

OUT = ROOT / ".tmp" / "pins"
# The report every run rewrites, so a preview of it follows each run as a revision of
# one page and keeps the threads on it; each run's captures stay in its own directory.
REPORT = OUT / "report"

# How far a pin may stand from the nearest box of its target.
REACH = 12
# How far a pin may reach into a box before it counts as over it.
SLIVER = 2
# Device pixels captured per CSS pixel, so a phone's crop stays sharp when the report's
# column draws it wider than the phone.
SCALE = 2

# Each viewport's size and whether a finger, rather than a mouse, drives it.
VIEWPORTS = {"desktop": ((1280, 800), False), "phone": ((390, 844), True)}
EVERY = tuple(VIEWPORTS)


@dataclass(frozen=True)
class Case:
    """`body` is the case's markup; each anchor is a comment's, as an event names it
    (`{"section": id}` for an element, with `"quote"` for a passage inside it); `allow`
    maps each fault kind the case accepts to the viewports it accepts it at, and `why`
    says why it accepts them."""

    name: str
    says: str
    body: str
    anchors: tuple[dict, ...]
    allow: dict[str, tuple[str, ...]] = field(default_factory=dict)
    why: str = ""


WORDS = (
    "Placement reads the room around a target before it seats the pin, and a pin "
    "that covers the words it is about makes the reader hide it to read them."
)
# A second sentence, so a full-width paragraph quotes neither twice.
MORE = (
    "Where every seat touching the target is taken, the pin stands on the target "
    "itself, and pressing o hides it."
)


def _cards(prefix: str, count: int) -> str:
    return "".join(
        f'<section id="{prefix}{i}" style="border:1px solid var(--rule);'
        'background:var(--card);margin:0;height:44px">'
        '<div style="background:var(--chip);height:44px">'
        f'<button class="button" style="float:right">Action</button></div></section>'
        for i in range(count)
    )


def _tiles(prefix: str, count: int) -> str:
    tiles = "".join(
        f'<div id="{prefix}{i}" style="border:1px solid var(--rule);padding:8px">'
        f"<strong>Tile {i}</strong><p style='margin:4px 0 0'>Twelve open, three late, "
        "one blocked on review.</p></div>"
        for i in range(count)
    )
    return (
        '<div style="display:grid;gap:4px;'
        f'grid-template-columns:repeat(auto-fill,minmax(150px,1fr))">{tiles}</div>'
    )


# Why the passage cases accept a far pin; seating it by the passage's own lines is open.
PASSAGE = (
    "A passage's pin stands by the element holding it, not by the passage, so it can"
    " stand a window's width from the words quoted."
)

CASES = (
    Case(
        "paragraph",
        "A short paragraph narrower than the window: room beside its corner.",
        f'<p id="paragraph-p" style="max-width:34ch">{WORDS}</p>',
        ({"section": "paragraph-p"},),
    ),
    Case(
        "wide-paragraph",
        "A paragraph that runs the window's full width, so nothing stands beside it.",
        f'<p id="wide-paragraph-p">{WORDS} {MORE}</p>',
        ({"section": "wide-paragraph-p"},),
    ),
    Case(
        "heading",
        "A short heading over a paragraph.",
        f'<h2 id="heading-h">Release checklist</h2><p>{WORDS}</p>',
        ({"section": "heading-h"},),
    ),
    Case(
        "quote-mid-line",
        "A passage in the middle of a line of a full-width paragraph.",
        f'<p id="quote-mid-line-p">{WORDS} {MORE}</p>',
        ({"section": "quote-mid-line-p", "quote": "before it seats the pin"},),
        allow={"far": EVERY},
        why=PASSAGE,
    ),
    Case(
        "quote-paragraph-end",
        "A passage that ends its paragraph, short of the window's edge.",
        f'<p id="quote-paragraph-end-p">{WORDS}</p>',
        ({"section": "quote-paragraph-end-p", "quote": "to read them."},),
        allow={"far": EVERY},
        why=PASSAGE,
    ),
    Case(
        "one-word",
        "A single word inside a sentence.",
        f'<p id="one-word-p">{WORDS}</p>',
        ({"section": "one-word-p", "quote": "seats"},),
        allow={"far": EVERY},
        why=PASSAGE,
    ),
    Case(
        "list-items",
        "Three neighbouring list items, each with a comment.",
        "<ul>"
        + "".join(
            f'<li id="list-items-{i}">Item {i}: check the release notes</li>'
            for i in range(3)
        )
        + "</ul>",
        tuple({"section": f"list-items-{i}"} for i in range(3)),
    ),
    Case(
        "tight-list",
        "Full-width list items shorter than a pin, one comment on the first.",
        '<ul style="line-height:20px;margin:0">'
        + "".join(
            f'<li id="tight-list-{i}">{WORDS[: 30 + 10 * i]}</li>' for i in range(3)
        )
        + "</ul>",
        ({"section": "tight-list-0"},),
    ),
    Case(
        "two-comments-one-target",
        "Two comments on one short paragraph.",
        f'<p id="two-comments-p" style="max-width:34ch">{WORDS}</p>',
        (
            {"section": "two-comments-p", "quote": "Placement reads the room"},
            {"section": "two-comments-p", "quote": "to read them."},
        ),
        allow={"far": EVERY},
        why="Both comments' pins stand together, by the paragraph holding them.",
    ),
    Case(
        "image",
        "A figure narrower than the window.",
        '<svg id="image-svg" width="320" height="180" role="img" aria-label="chart">'
        '<rect width="320" height="180" fill="#9cc"/></svg>',
        ({"section": "image-svg"},),
    ),
    Case(
        "wide-image",
        "A figure as wide as the window, right under a paragraph.",
        f'<p style="margin:0">{WORDS} {MORE}</p>'
        '<svg id="wide-image-svg" width="100%" height="160" role="img" '
        'aria-label="chart"><rect width="100%" height="160" fill="#9cc"/></svg>',
        ({"section": "wide-image-svg"},),
    ),
    Case(
        "table",
        "A full-width table with text in every cell.",
        '<table id="table-t" style="width:100%"><tr><th>Stage</th><th>Owner</th>'
        "<th>State</th></tr><tr><td>Build</td><td>Release</td><td>Green</td></tr>"
        "<tr><td>Deploy</td><td>Platform</td><td>Waiting on review</td></tr></table>",
        ({"section": "table-t"},),
    ),
    Case(
        "code-block",
        "A preformatted block whose lines run past its scrolling box.",
        '<pre id="code-block-pre" style="overflow:auto"><code>'
        + escape("def seat(pin, target):\n    " + "return " + "target.corner() + " * 12)
        + "\n</code></pre>",
        ({"section": "code-block-pre"},),
    ),
    Case(
        "toolbar",
        "A full-width row with its buttons at the right edge.",
        '<div id="toolbar-row" style="display:flex;gap:8px;align-items:center">'
        "<strong>Filters</strong><span style='flex:1'></span>"
        '<button class="button">Reset</button><button class="button">Apply</button>'
        "</div>",
        ({"section": "toolbar-row"},),
    ),
    Case(
        "cards",
        "Cards edge to edge, each a header with Action at its right; the comment is on"
        " the second.",
        _cards("cards-", 4),
        ({"section": "cards-1"},),
    ),
    Case(
        "tiles",
        "A grid of tiles across the window, tight together; comments on the second"
        " and the sixth.",
        _tiles("tiles-", 8),
        ({"section": "tiles-1"}, {"section": "tiles-5"}),
    ),
    Case(
        "form-field",
        "A full-width labelled input.",
        '<label id="form-field-l" style="display:block">Release name '
        '<input style="width:100%;box-sizing:border-box" value="2026.10"></label>',
        ({"section": "form-field-l"},),
    ),
    Case(
        "details",
        "A closed disclosure, whose summary is a control.",
        '<details id="details-d"><summary>Why the deploy waited</summary>'
        f"<p>{WORDS}</p></details>",
        ({"section": "details-d"},),
    ),
    Case(
        "scroll-pane",
        "A narrow paragraph at the top of a short bounded block, which scrolls.",
        '<div data-bound="start" style="height:120px;border:1px solid var(--rule)">'
        f'<p id="scroll-pane-p" style="max-width:260px">{WORDS}</p>'
        f"<p>{WORDS}</p></div>",
        ({"section": "scroll-pane-p"},),
    ),
    Case(
        "scroll-pane-cut",
        "A narrow paragraph a short bounded block shows only the top of, below another.",
        '<div data-bound="start" style="height:120px;border:1px solid var(--rule)">'
        "<p>Placement reads the room.</p>"
        f'<p id="scroll-pane-cut-p" style="max-width:260px">{WORDS} {MORE}</p>'
        f"<p>{WORDS}</p></div>",
        ({"section": "scroll-pane-cut-p"},),
    ),
    Case(
        "paragraph-in-flow",
        "A full-width paragraph between two others, at a document's usual spacing.",
        f"<p>{WORDS} {MORE}</p>"
        f'<p id="paragraph-in-flow-p">{MORE} {WORDS}</p>'
        f"<p>{WORDS} {MORE}</p>",
        ({"section": "paragraph-in-flow-p"},),
        allow={"words": ("phone",)},
        why="On a phone every seat touching it is on words, its own or its"
        " neighbours'.",
    ),
    Case(
        "dense-text",
        "A long, full-width section with no line short of the edge, right under a"
        " paragraph.",
        f'<p style="margin:0">{WORDS} {MORE}</p>'
        '<div id="dense-text-d" style="text-align:justify;text-align-last:justify">'
        + f"{WORDS} " * 6
        + "</div>",
        ({"section": "dense-text-d"},),
    ),
    Case(
        "keypad",
        "A target made wholly of buttons, edge to edge, right under a paragraph.",
        f'<p style="margin:0">{WORDS} {MORE}</p>'
        '<div id="keypad-d" style="display:grid;grid-template-columns:repeat(4,1fr)">'
        + "".join(f'<button class="button">{key}</button>' for key in "123456789*0#")
        + "</div>",
        ({"section": "keypad-d"},),
    ),
)


def source() -> str:
    """The page holding every case, each in a box of its own, apart from the next."""
    boxes = "\n".join(
        f'<section class="pin-case" id="case-{case.name}" '
        f'style="margin:0 0 96px">{case.body}</section>'
        for case in CASES
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<title>Pin cases</title>
</head>
<body>
<main>
<h1>Pin cases</h1>
{boxes}
</main>
</body>
</html>
"""


def events() -> list[dict]:
    """One comment per anchor, as a command states it."""
    return [
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": f"Comment {index} on {case.name}",
            "anchor": anchor,
        }
        for case in CASES
        for index, anchor in enumerate(case.anchors)
    ]


# A case's targets, the pins standing for them, and what the pins may not cover, as
# client rectangles. Text and controls are clipped to the boxes that clip them, so a
# line running past a scrolling box counts only where it shows.
READING = """async (anchors) => {
  const edges = ({left, top, right, bottom}) => ({left, top, right, bottom});
  const clipped = (el, rect) => {
    let {left, top, right, bottom} = rect;
    for (let at = el; at && at !== document.body; at = at.parentElement) {
      const style = getComputedStyle(at);
      if (style.overflowX === 'visible' && style.overflowY === 'visible') continue;
      const clip = at.getBoundingClientRect();
      left = Math.max(left, clip.left); right = Math.min(right, clip.right);
      top = Math.max(top, clip.top); bottom = Math.min(bottom, clip.bottom);
    }
    return right - left > 2 && bottom - top > 2 ? {left, top, right, bottom} : null;
  };
  const boxes = (el, rects) => [...rects].map((r) => clipped(el, r)).filter(Boolean);
  const quoted = (root, quote) => {
    const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let text = '';
    for (let node = walk.nextNode(); node; node = walk.nextNode()) {
      nodes.push([node, text.length]);
      text += node.data;
    }
    const start = text.indexOf(quote);
    const at = (offset) => {
      const [node, base] = nodes.findLast(([, base]) => base <= offset);
      return [node, offset - base];
    };
    const range = document.createRange();
    range.setStart(...at(start));
    range.setEnd(...at(start + quote.length));
    return range;
  };
  const target = document.getElementById(anchors[0].section);
  const box = target.closest('.pin-case');
  // Below the banner, with room above the case for a pin seated over it.
  document.scrollingElement.scrollTop += box.getBoundingClientRect().top - 160;
  await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
  const words = [];
  const walk = document.createTreeWalker(box, NodeFilter.SHOW_TEXT);
  for (let node = walk.nextNode(); node; node = walk.nextNode()) {
    if (!node.data.trim() || !node.parentElement.checkVisibility()) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    words.push(...boxes(node.parentElement, range.getClientRects()));
  }
  const all = (selector) => [...box.querySelectorAll(selector)]
    .filter((el) => el.checkVisibility())
    .flatMap((el) => boxes(el, el.getClientRects()));
  const targets = anchors.map((anchor) => {
    const el = document.getElementById(anchor.section);
    const rects = anchor.quote ? quoted(el, anchor.quote).getClientRects()
      : el.getClientRects();
    return {for: anchor.section, parts: boxes(el, rects)};
  });
  const pins = [...new Set(anchors.map((anchor) => anchor.section))].map((id) => {
    const row = document.querySelector(`[data-lf-margin-for="${id}"]`);
    return {
      for: id,
      place: row?.dataset.lfPlace ?? null,
      entries: row ? [...row.querySelectorAll('.lf-margin-entry')]
        .filter((entry) => entry.checkVisibility())
        .map((entry) => edges(entry.getBoundingClientRect())) : [],
    };
  });
  return {
    width: document.documentElement.clientWidth,
    height: innerHeight,
    box: edges(box.getBoundingClientRect()),
    words,
    // A box the keyboard reaches only to scroll it takes no press a pin could miss.
    controls: all('button, a[href], input, select, textarea, summary, [role=button]'),
    media: all('img, svg:not(svg svg), video, canvas, iframe'),
    targets,
    pins,
  };
}"""


def read(page, case: Case) -> dict:
    """Scroll `case` into view on an open page and read it (`READING`)."""
    return page.evaluate(READING, list(case.anchors))


def _meets(a: dict, b: dict) -> bool:
    """Whether `a` and `b` share more than a sliver: a text box's top or bottom pixel
    is the empty edge of its line, and two rectangles touching share none."""
    return (
        min(a["right"], b["right"]) - max(a["left"], b["left"]) > SLIVER
        and min(a["bottom"], b["bottom"]) - max(a["top"], b["top"]) > SLIVER
    )


def _distance(a: dict, b: dict) -> float:
    return hypot(
        max(0, b["left"] - a["right"], a["left"] - b["right"]),
        max(0, b["top"] - a["bottom"], a["top"] - b["bottom"]),
    )


def faults(reading: dict) -> list[tuple[str, str]]:
    """Each fault in one case's reading, as its kind and the target it is about. A pin
    is over `words`, `controls` or `media`; out of reach of its target (`far`), past
    the window's edge (`offscreen`), or over another pin (`overlap`); or a comment has
    no pin shown at all (`hidden`)."""
    found = []
    seated = [
        (pin["for"], entry) for pin in reading["pins"] for entry in pin["entries"]
    ]
    for pin in reading["pins"]:
        name = pin["for"]
        if not pin["entries"]:
            found.append(("hidden", name))
            continue
        parts = [
            part for t in reading["targets"] if t["for"] == name for part in t["parts"]
        ]
        for entry in pin["entries"]:
            if parts and min(_distance(entry, part) for part in parts) > REACH:
                found.append(("far", name))
            # Only across: a pin below a tall target is past the window's foot at
            # this scroll and reached by scrolling, as its target is.
            if entry["left"] < 0 or entry["right"] > reading["width"]:
                found.append(("offscreen", name))
            for kind in ("words", "controls", "media"):
                if any(_meets(entry, box) for box in reading[kind]):
                    found.append((kind, name))
            if any(other != name and _meets(entry, box) for other, box in seated):
                found.append(("overlap", name))
    return sorted(set(found))


def accepted(case: Case, kind: str, viewport: str) -> bool:
    return viewport in case.allow.get(kind, ())


def unaccepted(case: Case, reading: dict, viewport: str) -> list[tuple[str, str]]:
    return [f for f in faults(reading) if not accepted(case, f[0], viewport)]


def frame(readings: list[dict]) -> tuple[int, int, int, int]:
    """The rectangle around a case and its pins in every reading of it, so each arm's
    crop of one case at one viewport covers the same place on the page."""
    pad = 16
    rects = [
        rect
        for reading in readings
        for rect in (
            reading["box"],
            *(entry for pin in reading["pins"] for entry in pin["entries"]),
        )
    ]
    return (
        int(max(0, min(r["left"] for r in rects) - pad)),
        int(max(0, min(r["top"] for r in rects) - pad)),
        int(min(readings[0]["width"], max(r["right"] for r in rects) + pad)),
        int(min(readings[0]["height"], max(r["bottom"] for r in rects) + pad)),
    )


def crop(seen: dict, rect: tuple[int, int, int, int], out: Path) -> Path:
    """Crop one arm's screenshot of a case to `rect`, in CSS pixels, outlining its
    targets, and write it to `out` at the capture's SCALE."""
    reading = seen["reading"]
    image = Image.open(seen["shot"]).convert("RGB")
    draw = ImageDraw.Draw(image)
    for target in reading["targets"]:
        for part in target["parts"]:
            draw.rectangle(
                tuple(
                    SCALE * edge
                    for edge in (
                        part["left"],
                        part["top"],
                        part["right"],
                        part["bottom"],
                    )
                ),
                outline=(40, 110, 230),
                width=SCALE,
            )
    image.crop(tuple(SCALE * edge for edge in rect)).save(out)
    return out


def capture(browser, address: str, out: Path) -> dict:
    """Open `address` at each viewport, screenshot each case under `out`, and return
    `{case: {viewport: {"faults", "unaccepted", "reading", "shot"}}}`."""
    result = {case.name: {} for case in CASES}
    for viewport, (size, touch) in VIEWPORTS.items():
        with tab(browser, size, touch=touch, scale=SCALE) as page:
            load(page, address)
            for case in CASES:
                reading = read(page, case)
                shot = out / f"{case.name}-{viewport}-full.png"
                page.screenshot(path=shot)
                result[case.name][viewport] = {
                    "faults": faults(reading),
                    "unaccepted": unaccepted(case, reading, viewport),
                    "reading": reading,
                    "shot": shot,
                }
    return result


def _media(page_media: Path, image: Path) -> str:
    data = image.read_bytes()
    name = media_name(data, ".png")
    (page_media / name).write_bytes(data)
    return f"/media/{name}"


def _fault_list(case: Case, viewport: str, found: list[tuple[str, str]]) -> str:
    if not found:
        return "none"
    return ", ".join(
        f"{kind} ({target}){' — accepted' if accepted(case, kind, viewport) else ''}"
        for kind, target in found
    )


PAIRS = (
    " Each pair opens on its changed pixels: red where the base drew something, such as"
    " a pin it has moved, and blue where this tree draws it. Plain shows the two"
    " images under a divider."
)


def report(arms: dict[str, tuple[str, dict]], out: Path) -> Path:
    """Write the Leaf page that shows every case's crops into REPORT, replacing the
    last run's, and return its path. Crops are cut into the run directory `out`."""
    media = REPORT / "media"
    shutil.rmtree(media, ignore_errors=True)
    media.mkdir(parents=True)
    head = arms["head"][1]
    base = arms.get("base")
    failing = [
        case
        for case in CASES
        if any(seen["unaccepted"] for seen in head[case.name].values())
    ]
    against = f" against {escape(base[0])}" if base else ""
    summary = (
        "<p>No case has a fault its <code>allow</code> does not accept.</p>"
        if not failing
        else "<p>Cases with a fault their <code>allow</code> does not accept:</p><ul>"
        + "".join(
            f'<li><a href="#{case.name}">{case.name}</a></li>' for case in failing
        )
        + "</ul>"
    )
    sections = []
    for case in CASES:
        rows = []
        for viewport in VIEWPORTS:
            seen = head[case.name][viewport]
            before = base[1][case.name][viewport] if base else None
            rect = frame([seen["reading"], *([before["reading"]] if before else [])])
            stem = out / f"{case.name}-{viewport}"
            after_image = _media(media, crop(seen, rect, stem.with_suffix(".head.png")))
            line = f"<p><strong>{viewport}</strong>: faults {_fault_list(case, viewport, seen['faults'])}"
            if before:
                line += (
                    f"; on the base, {_fault_list(case, viewport, before['faults'])}"
                )
                picture = (
                    f'<lf-shot id="{case.name}-{viewport}-shot" pixels '
                    f'alt="the {case.name} case at {viewport} width" '
                    f'before="{_media(media, crop(before, rect, stem.with_suffix(".base.png")))}" '
                    f'after="{after_image}"></lf-shot>'
                )
            else:
                picture = (
                    f'<img src="{after_image}" '
                    f'alt="the {case.name} case at {viewport} width">'
                )
            rows.append(f"{line}</p>\n{picture}")
        sections.append(
            f'<section id="{case.name}">\n<h2>{case.name}</h2>\n'
            f"<p>{escape(case.says)}</p>\n"
            + (f"<p>Accepted: {escape(case.why)}</p>\n" if case.why else "")
            + "\n".join(rows)
            + "\n</section>"
        )
    page = REPORT / "pins.html"
    page.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<title>Pin cases</title>
</head>
<body>
<main class="layout-column">
<header id="intro">
<h1>Pin cases</h1>
<p>{len(CASES)} cases on {escape(arms["head"][0])}{against}, at
{" and ".join(f"{v} ({s[0][0]}px)" for v, s in VIEWPORTS.items())}. Targets are
outlined in blue.{PAIRS if base else ""}</p>
<p>These are few, and not chosen to flatter the placement: they are the shapes that
came to mind for a pin to sit on. Where a page shows a placement that looks wrong,
add its shape here as a case.</p>
{summary}
</header>
{chr(10).join(sections)}
</main>
</body>
</html>
""",
        encoding="utf-8",
    )
    return page


@click.command()
@click.option(
    "--base",
    is_flag=False,
    flag_value="",
    default=None,
    help="Also seat the cases on the merge base with main, or the ref given.",
)
def pins(base) -> None:
    """Seat every pin case on this working tree, and write a Leaf page of crops."""
    use_linux_fonts()
    OUT.mkdir(parents=True, exist_ok=True)
    out = run_directory(OUT)
    with tempfile.TemporaryDirectory(prefix="leaf-pins-") as built:
        scratch = Path(built)
        fixture = scratch / "cases.html"
        fixture.write_text(source(), encoding="utf-8")
        fixture.with_suffix(".jsonl").write_text(
            "".join(
                json.dumps(
                    {**event, "id": f"pin{index:04d}", "ts": "2026-10-13T00:00:00Z"}
                )
                + "\n"
                for index, event in enumerate(events())
            ),
            encoding="utf-8",
        )
        arms = {"head": ("this working tree", ROOT)}
        if base is not None:
            commit = base_ref(base)
            build_arm(commit, scratch / "base-arm")
            arms["base"] = (commit[:10], scratch / "base-arm")
        readings = {}
        with headless_shell() as browser:
            for arm, (label, arm_dir) in arms.items():
                shots = out / arm
                shots.mkdir()
                with serving_source(arm_dir, fixture, scratch / arm) as address:
                    readings[arm] = (label, capture(browser, address, shots))
    page = report(readings, out)
    click.echo(page)
    click.echo(f"uv run leaf-dev preview --source {page} --slot pins --user")
