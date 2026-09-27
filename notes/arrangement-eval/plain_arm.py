"""The plain-CSS arm: an extracted Leaf payload with the arrangement vocabulary taken out.

`build(arm)` removes the Layout classes (`layout-column`, `layout-wide`,
`layout-sidebar`, `layout-tiles`, `layout-workspace`), the `lf-pane` element, the width
attribute (`data-width`), the rail declaration (`data-rail`), the margin idioms
(`section.panel`, `aside.sidebar`, `aside.sidenote`) and the margin reading
(`data-lf-margin`), and every sentence of guidance or check advice that names them. In
their place the authoring reference tells the agent to lay the page out in its own CSS
and lists the theme's published sizes. Widgets, the theme's typography, the render
checks, and the rest of the guidance are untouched, so the two arms differ only in how a
page is arranged.

The authoring reference's arrangement guidance, from "Composing a page" up to "Draw the
subject", is replaced whole, so a rewrite inside it needs no new anchor here. Every other
edit is an exact replacement that must match once. A payload whose text has moved fails
here rather than yielding an arm that still carries the vocabulary; update the anchors,
then rebuild the arms.
"""

import json
import re
import sys
from pathlib import Path


def replace(path: Path, old: str, new: str) -> None:
    """Replace `old` once, matching any run of whitespace in it against any other, so
    a rewrapped paragraph still matches."""
    text = path.read_text()
    pattern = r"\s+".join(re.escape(word) for word in old.split())
    matches = re.findall(pattern, text)
    if len(matches) != 1:
        sys.exit(f"{path}: expected one match, found {len(matches)}: {old[:80]!r}")
    path.write_text(re.sub(pattern, lambda _: new, text))


def replace_section(path: Path, start: str, end: str, new: str) -> None:
    """Replace from the heading `start` up to (not including) the heading `end`."""
    text = path.read_text()
    i, j = text.index(start), text.index(end)
    path.write_text(text[:i] + new + text[j:])


COMPOSING = """\
## Composing a page

Lay the page out with ordinary HTML and your own CSS in the page's `<style>`. `main`
has no arrangement of its own: its blocks run the window's width until the page's CSS
gives it one. Choose the arrangement from the shape of the subject:

- **Prose read in order** — a plan, a review, a write-up, a decision — is a reading
  column centred in the window. Most pages are this:

  ```css
  main { max-width: var(--col); margin-inline: auto; padding-inline: var(--col-pad); }
  ```

- **Independent status tiles** are a block whose children stand in equal cells, as
  many to a row as fit. Each cell holds a surface — a metric, chart, table, list or
  log, with at most a caption — rather than paragraphs; a row of headline numbers is
  `lf-metric` tiles in one. Tiles of paragraphs are prose cut into columns, and read
  worse than the column.
- **Regions read side by side** — a dashboard, a board with its status, a queue sorted
  into buckets, a long review whose contents and verdict stay beside the code — widen
  `main`, up to `--wide-page-max`, and place the regions with CSS grid or flexbox.
- **Regions that stay in view together** while each scrolls on its own, such as a
  queue beside its detail, hold the window: size the layout to `--lf-view-height`, the
  window's height less Leaf's banner and band, and bound each region.
- **A comparison** is `lf-compare`, which keeps its variants paired at any width.
- **Controls beside evidence** is a playground, which declares how its controls
  operate its preview.
- **Several views of one artifact** are one `lf-tabs` set: page tabs for
  project-scale views that share one history, Threads panel, Ask inventory, and
  revision sequence, and a tabbed section for local alternatives within the
  surrounding view. Page tabs are sections of one page: each panel takes the page's
  width. The `lf-tabs` entry says which placement makes which, and how to order and
  retire views.

The theme publishes its sizes as custom properties on `:root`. Use them rather than
restating numbers, so the page agrees with the theme and Leaf's chrome:

| Property | Value | What it is |
| --- | --- | --- |
| `--col` | 720px | the prose measure |
| `--col-pad` | 24px | the side padding a column keeps from the window |
| `--wide` | 1080px | the shared width for evidence wider than the measure |
| `--wide-page-max` | 1600px | the widest a page of regions should grow |
| `--rail` | about 95px | the strip for comment markers (below) |
| `--lf-banner-h` | 42px, 88px on a narrow window | the fixed banner; the page starts below it |
| `--lf-band-h` | 44px | the shortcut band fixed at the window's foot |
| `--lf-view-height` | the window less both | the height a page that holds the window has |
| `--sp-1` … `--sp-4` | 4, 8, 16, 24px | spacing steps |
| `--r` | 6px | corner radius |
| `--card`, `--field`, `--rule` | colours | a raised surface, a tinted field, a hairline |
| `--ink`, `--muted`, `--accent` | colours | text, secondary text, the accent |
| `--ok`, `--warn`, `--danger` | colours | status tones |

Keep running text at the measure inside a wider layout (`max-width: var(--col)` on
paragraphs and lists); tables, charts, and code may fill their region. Make every
side-by-side arrangement responsive: stack its regions where the window is too narrow
for them, with a container or media query, because the render check sweeps every width
from a 360px phone to a wide desktop.

A page grows without changing kind: a report that gains live status gains a row of
tiles, and its comments and anchors stay put.

The banner and the shortcut band at the foot of the window are fixed reservations, so
the room a page has depends only on the window, and nothing Leaf draws moves the page's
content: the rail stands in room the page leaves beside `main` (below).

### Bounds

A log, feed, or long listing bounds its own height with `data-bound`, naming the end
its newest entry is at. Put the entries in the order the reader needs, then bound
that order. A list that grows downward takes `data-bound="end"`, which opens it on
its last line, keeps that line in view while the user is at the end, and leaves them
where they scrolled back to otherwise. A newest-first list takes
`data-bound="start"`, which opens it at the top, as the page's own activity feed
does. Some widgets bound themselves by default. Don't make a box scroll vertically with page
CSS: Leaf keeps no reading position in a scroller it did not make, and `version
check` advises against one.

Show evidence at the scale needed to judge it. For a local change, supply an aligned
detail view with the complete object available for context; use whole frames when their
composition is the subject. A fitted thumbnail is an overview, not a substitute for
readable detail. Let the package provide inspection controls; wheel handlers should not
be needed.

### The rail

Leaf marks each commented or decided element with a marker: a thread, an Ask, a
suggestion's ✓/✗. Nothing Leaf draws moves the page's content, so plan the page's
geometry without them:

- Wherever the room right of `main`'s box holds a `--rail` strip, the markers stand in
  it, 22px past `main`'s content. A page as wide as the window leaves no such room.
- Where the rail does not stand, and in a region that scrolls on its own, each marker
  stands as a pin over the top-right corner of its block. A pin covers 26px of that
  corner with a mouse and 44px under a finger, so a block whose first line runs to its
  right edge loses the end of that line under a pin.
- The user hides every pin and passage mark with `o` to see what lies under them; the
  rail stays, since it covers nothing.

"""


# The harness renders this page when it builds the arms, so a theme that stops
# honouring the guide's sizes fails the build instead of every plain run.
SMOKE = """<!doctype html>
<html lang="en"><head><title>Hook</title><meta name="description" content="Smoke page.">
<style>
main { max-width: var(--wide-page-max); margin-inline: auto; padding-inline: var(--col-pad); }
.regions { display: grid; grid-template-columns: 2fr 1fr; gap: var(--sp-4); }
@media (width < 640px) { .regions { grid-template-columns: 1fr; } }
</style></head><body><main>
<h1>Hook</h1>
<div class="regions">
<section id="body"><h2>Body</h2><p>A paragraph that runs long enough to wrap across the body region's
width, so the check measures text that fills it.</p></section>
<section id="side"><h2>Side</h2><p>Status.</p></section>
</div></main></body></html>
"""

VOCABULARY = re.compile(
    r"layout-(column|wide|sidebar|tiles|workspace)|lf-pane|data-width|data-rail"
    r"|data-lf-margin|section\.panel|aside\.sidebar|sidenote"
)


def build(arm: Path) -> str:
    """Patch the payload at `arm` into the plain arm, and return the smoke page."""
    skill = arm / "skills/leaf"
    # The Layouts' stylesheet is the vocabulary itself, and an author who greps the
    # payload for a size the plain guide names reads it, so it goes whole.
    (skill / "assets/layouts.css").write_text("@layer lf-layouts {}\n")
    patch_references(skill)
    patch_registry(skill)
    patch_packages(skill)
    patch_advice(skill)
    check_clean(arm)
    return SMOKE


def patch_references(skill: Path) -> None:
    authoring = skill / "references/page-authoring.md"
    replace(authoring, '<main class="layout-column">…</main>', "<main>…</main>")
    replace_section(
        authoring, "## Composing a page\n", "## Draw the subject\n", COMPOSING
    )
    replace(
        skill / "references/authoring-evidence.md",
        'give the figure `data-width="wide"` when it needs the room.',
        "give the figure the room it needs in page CSS.",
    )


def patch_registry(skill: Path) -> None:
    path = skill / "packages/default/registry.json"
    reg = json.loads(path.read_text())
    del reg["lf-pane"]
    # The module goes too: loading is registry-driven, and an author listing the
    # payload would otherwise find the element there.
    (skill / "packages/default/widgets/lf-pane.js").unlink(missing_ok=True)
    edits = {
        ("lf-metric", "description"): [
            (
                " A row of metrics is lf-metric tiles in a `layout-tiles` block.",
                " A row of metrics is a row of lf-metric tiles.",
            )
        ],
        ("lf-metric", "x-example"): [
            ('<div class="layout-tiles">', '<div class="k-row">')
        ],
        ("lf-gloss", "description"): [
            ("a details disclosure, or a sidenote.", "or a details disclosure.")
        ],
        ("lf-toc", "description"): [
            (
                "places one in an `aside.sidebar` near the opening by default",
                "places one near the opening by default",
            ),
            (
                (
                    "A workspace page (`main.layout-workspace`) uses its regions for navigation"
                    " instead of a page-wide contents sidebar, and root page tabs supply"
                ),
                "Root page tabs supply",
            ),
        ],
        ("lf-toc", "x-example"): [
            ('<aside class="sidebar" id="plan-sidebar">', '<nav id="plan-sidebar">'),
            ("</aside>", "</nav>"),
        ],
    }
    for (tag, field), pairs in edits.items():
        for old, new in pairs:
            if reg[tag][field].count(old) != 1:
                sys.exit(f"{tag}.{field}: moved: {old[:60]!r}")
            reg[tag][field] = reg[tag][field].replace(old, new)
    path.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")

    path = skill / "assets/registry.json"
    reg = json.loads(path.read_text())
    for idiom in ("section.panel", "aside.sidebar", "aside.sidenote"):
        del reg["$idioms"][idiom]
    text = json.dumps(
        {"$idioms": reg["$idioms"], "$keys": reg["$keys"]}, ensure_ascii=False
    )
    for old in (
        "; a note they lose nothing by skipping goes in the margin (aside.sidenote)",
        (
            " An authored occurrence may override the default with"
            " data-width=column|wide|available; the runtime resolves that choice into"
            " data-lf-space and the theme allocates it without moving the prose axis."
        ),
    ):
        if text.count(old) != 1:
            sys.exit(f"assets registry: moved: {old[:60]!r}")
        text = text.replace(old, "")
    reg.update(json.loads(text))
    path.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")


def patch_packages(skill: Path) -> None:
    """The optional packages' guidance names the Layout a page of theirs takes."""
    packages = skill / "packages"
    for rel, old, new in (
        (
            "command-hub/guidance/author.md",
            'On a sidebar page (`<main class="layout-sidebar">`), lay the tree',
            "On a page with a side track beside its body, lay the tree",
        ),
        (
            "command-hub/registry.json",
            '<div class=\\"layout-sidebar\\">',
            '<div class=\\"hub\\">',
        ),
        (
            "monitoring/guidance/author.md",
            'beside its `aside`, `<main class="layout-sidebar">` with the `aside` written'
            " after the body.",
            "beside a side track written after it.",
        ),
        (
            "monitoring/guidance/author.md",
            "observed and required values in the `aside`.",
            "observed and required values in the side track.",
        ),
        (
            "monitoring/guidance/author.md",
            "rollback procedure in the `aside` or below",
            "rollback procedure in the side track or below",
        ),
        (
            "monitoring/guidance/author.md",
            "as `lf-metric` tiles in a `layout-tiles` block,",
            "as a row of `lf-metric` tiles,",
        ),
        (
            "swipe/guidance/author.md",
            'on a wide page (`<main class="layout-wide">`) it puts',
            "on a wide page it puts",
        ),
        (
            "playground/guidance/author.md",
            (
                'belongs on a wide page (`<main class="layout-wide">`), or on a workspace page'
                ' (`<main class="layout-workspace">`) whose body is the playground\'s Ask,'
                " where the stage grows to the window's height."
            ),
            "belongs on a wide page.",
        ),
        (
            "visual-review/guidance/author.md",
            (
                "make `lf-visual-review` the body of a workspace page,"
                ' `<main class="layout-workspace">`, after an optional `header`. Where the'
                " window holds the workspace, the review fills it: the navigation and case"
                " furniture stay in view and the evidence stage takes the height left. A"
                " smaller window, or a review in a document with prose around it, keeps the"
                " same order in ordinary flow,"
            ),
            (
                "make `lf-visual-review` the page's body, after an optional `header`. It keeps"
                " its order in ordinary flow,"
            ),
        ),
    ):
        replace(packages / rel, old, new)


def patch_advice(skill: Path) -> None:
    # A plain page's `main` carries no Layout class by design, so the advice to add one
    # would fire on every page and name a class this arm doesn't have.
    replace(
        skill / "scripts/leaf/validation/source.py", "*unarranged_main(parser),", ""
    )


def check_clean(arm: Path) -> None:
    """Fail if the vocabulary survives in the guidance an author reads: the skill, its
    references, every package's registry and guidance, and the Layouts' stylesheet.

    Not covered, and so still readable by a plain author who searches for it:
    `references/packages.md`, the package-author reference, which names `lf-pane` as
    a pane role; the theme's and runtime's own rules and comments; and maintainer
    contracts beside the scripts."""
    skill = arm / "skills/leaf"
    read = [
        skill / "SKILL.md",
        *sorted((skill / "references").glob("*.md")),
        *sorted((skill / "packages").glob("*/registry.json")),
        *sorted((skill / "packages").glob("*/guidance/**/*.md")),
        skill / "assets/registry.json",
        skill / "assets/layouts.css",
    ]
    hits = [
        f"{p.relative_to(arm)}:{n}: {line.strip()[:100]}"
        for p in read
        if p.name != "packages.md"
        for n, line in enumerate(p.read_text().splitlines(), 1)
        if VOCABULARY.search(line)
    ]
    if hits:
        sys.exit("vocabulary survives:\n" + "\n".join(hits))
