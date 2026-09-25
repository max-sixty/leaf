"""The plain-CSS arm: an extracted Leaf payload with the arrangement vocabulary taken out.

`build(arm)` removes the layout elements (`lf-grid`, `lf-workspace`, `lf-pane`), the
width attribute (`data-width` on blocks and `main`), the layout idioms (`section.panel`,
`aside.sidebar`, `aside.sidenote`), and every sentence of guidance or check advice that
names them. In their place the authoring reference tells the agent to lay the page out
in its own CSS and lists the theme's published sizes. Widgets, the theme's typography,
the render checks, and the rest of the guidance are untouched, so the two arms differ
only in how a page is arranged.

Every edit is an exact replacement that must match once. A payload whose text has
moved (another ref, a rewritten guide) fails here rather than yielding an arm that
still carries the vocabulary; update the anchors, then rebuild the arms.
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

Lay the page out with ordinary HTML and your own CSS in the page's `<style>`. Choose
the arrangement from the shape of the subject:

- **An argument read in order** — a plan, a review, a write-up, a decision — needs no
  layout CSS: `main` is already a centred reading column. Most pages are this.
- **Regions read side by side** — a dashboard, a board with its status, a queue sorted
  into buckets — widen `main` and place the regions with CSS grid or flexbox.
- **Regions that must stay in view together** while each scrolls on its own — a queue
  beside its detail, controls beside a preview — hold the window: size the layout to
  the viewport's height less Leaf's banner and band, and bound each region.

The theme publishes its sizes as custom properties on `:root`. Use them rather than
restating numbers, so the page agrees with the theme and Leaf's chrome:

| Property | Value | What it is |
| --- | --- | --- |
| `--col` | 720px | the prose measure, and `main`'s default width |
| `--lf-page-measure` | `var(--col)` | the width `main` takes when the window has room; set it on `main` |
| `--col-pad` | 24px | `main`'s side padding |
| `--wide` | 1080px | the shared width for evidence wider than the measure |
| `{WIDE}` | 1600px | the widest a page of regions should grow |
| `--rail` | about 95px | the strip Leaf keeps at the window's right edge for comment markers |
| `--lf-banner-h` | 42px, 88px on a narrow window | the fixed banner; the page starts below it |
| `--lf-band-h` | 44px | the shortcut band fixed at the window's foot |
| `--sp-1` … `--sp-4` | 4, 8, 16, 24px | spacing steps |
| `--r` | 6px | corner radius |
| `--card`, `--field`, `--rule` | colours | a raised surface, a tinted field, a hairline |
| `--ink`, `--muted`, `--accent` | colours | text, secondary text, the accent |
| `--ok`, `--warn`, `--danger` | colours | status tones |

`main` is the page's box. Its width is `--lf-page-measure`, `var(--col)` by default,
centred in the room the window leaves beside the rail. To widen the page, set that
property on `main` and lift the column's cap:

```css
main { --lf-page-measure: var({WIDE}); max-width: none; }
```

On a window wider than about 864px, Leaf keeps the `--rail` strip at the window's right
edge for comment markers and the thread cards they open; `main` sized this way leaves it
clear, and so must anything you position outside `main`'s box. Leaf's chrome never moves
the page's content: the banner, the band and the rail are fixed reservations, so the
room a page has depends only on the window, and the Asks tray, the Threads panel and
thread cards stand over the page.

Keep running text at the measure inside a wider layout (`max-width: var(--col)` on
paragraphs and lists); tables, charts, and code may fill their region. Make every
side-by-side arrangement responsive: stack its regions where the window is too narrow
for them, with a container or media query, because the render check sweeps every width
from a 360px phone to a 1200px desktop.

Within the page, compose with these:

- **A comparison** is `lf-compare`, which keeps its variants paired at any width.
- **Controls beside evidence** is a playground, which declares how its controls
  operate its preview.
- **Several views of one artifact** are one `lf-tabs` set: page tabs for
  project-scale views that share one history, Threads panel, Ask inventory, and
  revision sequence, and a tabbed section for local alternatives within the
  surrounding view. The `lf-tabs` entry says which placement makes which, and how to
  order and retire views.

### Bounds

"""

BOUNDS_WIDTHS = """\
An individual block or section may request a responsive allocation with
`data-width="column"`, `data-width="wide"`, or `data-width="available"`. `column`
uses the standard prose measure, including inside a wider section. `wide` uses the
shared capped evidence width. `available` uses all room left by the page shell, frames,
chrome, and occupied margins. The occurrence overrides a widget's package default, so
`data-width="column"` can deliberately keep a normally wide widget with the prose.
Use these names on the semantic block itself, including a native `table`, `lf-code`, or
`lf-diff`; do not reproduce their responsive widths in page CSS.

"""


# The harness renders this page when it builds the arms, so a theme that stops
# honouring the guide's width hook fails the build instead of every plain run.
SMOKE = """<!doctype html>
<html lang="en"><head><title>Hook</title><meta name="description" content="Smoke page.">
<style>
main { --lf-page-measure: var({WIDE}); max-width: none; }
.regions { display: grid; grid-template-columns: 2fr 1fr; gap: var(--sp-4); }
@container (width < 640px) { .regions { grid-template-columns: 1fr; } }
</style></head><body><main>
<h1>Hook</h1>
<div class="regions">
<section id="body"><h2>Body</h2><p>A paragraph that runs long enough to wrap across the body region's
width, so the check measures text that fills it.</p></section>
<section id="rail"><h2>Rail</h2><p>Status.</p></section>
</div></main></body></html>
"""


def build(arm: Path) -> str:
    """Patch the payload at `arm` into the plain arm, and return the smoke page."""
    skill = arm / "skills/leaf"
    # The theme's name for the widest page, which a later ref renamed.
    theme = (skill / "assets/theme.css").read_text()
    wide = "--wide-page-max" if "--wide-page-max:" in theme else "--sheet-max"
    patch_references(skill, wide)
    patch_registry(skill)
    patch_advice(skill)
    check_clean(arm)
    return SMOKE.replace("{WIDE}", wide)


def patch_references(skill: Path, wide: str) -> None:
    authoring = skill / "references/page-authoring.md"
    composing = COMPOSING.replace("{WIDE}", wide)
    replace_section(
        authoring, "## Composing a page\n", "A log, feed, or long listing", composing
    )
    replace(authoring, BOUNDS_WIDTHS, "")
    replace(
        authoring,
        "Let the package provide inspection controls and Leaf allocate space and\n"
        "scrolling; page-local width overrides and wheel handlers should not be needed.",
        "Let the package provide inspection controls; wheel handlers should not be needed.",
    )
    replace(
        skill / "references/authoring-evidence.md",
        'in a `<figure>` with an `id`, and give the figure `data-width="wide"` when it needs the room.',
        "in a `<figure>` with an `id`, and give the figure the room it needs in page CSS.",
    )


def patch_registry(skill: Path) -> None:
    path = skill / "packages/default/registry.json"
    reg = json.loads(path.read_text())
    for tag in ("lf-grid", "lf-workspace", "lf-pane"):
        del reg[tag]
        # The module goes too: loading is registry-driven, and an author listing the
        # payload would otherwise find the element there.
        (skill / f"packages/default/widgets/{tag}.js").unlink(missing_ok=True)
    metric = reg["lf-metric"]
    metric["description"] = metric["description"].replace(
        " A row of metrics is an lf-grid of lf-metric tiles.",
        " A row of metrics is a row of lf-metric tiles.",
    )
    metric["x-example"] = re.sub(
        r'<lf-grid id="k-row">(.*)</lf-grid>',
        r'<div class="k-row">\1</div>',
        metric["x-example"],
        flags=re.DOTALL,
    )
    gloss = reg["lf-gloss"]
    gloss["description"] = gloss["description"].replace(
        "a details disclosure, or a sidenote.", "or a details disclosure."
    )
    toc = reg["lf-toc"]
    toc["description"] = (
        toc["description"]
        .replace(
            "places one in an `aside.sidebar` near the opening by default",
            "places one near the opening by default",
        )
        .replace(
            "Root workspaces use their region navigation instead of a page-wide contents sidebar, and root",
            "Root",
        )
    )
    toc["x-example"] = (
        toc["x-example"]
        .replace('<aside class="sidebar" id="plan-sidebar">', '<nav id="plan-sidebar">')
        .replace("</aside>", "</nav>")
    )
    path.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")

    path = skill / "assets/registry.json"
    reg = json.loads(path.read_text())
    idioms = reg["$idioms"]
    for idiom in ("section.panel", "aside.sidebar", "aside.sidenote"):
        del idioms[idiom]
    idioms[".callout"]["description"] = idioms[".callout"]["description"].replace(
        "; a note they lose nothing by skipping goes in the margin (aside.sidenote)", ""
    )
    keys = json.dumps(reg["$keys"], ensure_ascii=False)
    dropped = (
        " An authored occurrence may override the default with data-width=column|wide|available;"
        " the runtime resolves that choice into data-lf-space and the theme allocates it"
        " without moving the prose axis."
    )
    sidebar = (
        "instead of advising an aside.sidebar that would take it out of root placement"
    )
    for old in (dropped, sidebar):
        if keys.count(old) != 1:
            sys.exit(f"$keys: moved: {old[:60]!r}")
    keys = keys.replace(dropped, "").replace(
        sidebar, "instead of advising a contents list"
    )
    reg["$keys"] = json.loads(keys)
    path.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")


def patch_advice(skill: Path) -> None:
    markup = skill / "scripts/leaf/validation/markup.py"
    replace(markup, '>: one in an "', '>: one "')
    replace(
        markup,
        '"aside.sidebar near the opening lists them',
        '"near the opening lists them',
    )


def check_clean(arm: Path) -> None:
    """Fail if the vocabulary survives anywhere the arm's author reads by default.

    Not covered, and so still readable by a plain author who searches for it:
    `references/packages.md`, the package-author reference, and the guidance and
    registries of the optional packages (monitoring, playground, swipe, visual-review,
    command-hub), which name the vocabulary in their examples. No plain page has used
    it, but plain agents have spent turns looking for it there."""
    skill = arm / "skills/leaf"
    pattern = re.compile(
        r"lf-grid|lf-workspace|lf-pane|data-width|section\.panel|aside\.sidebar|sidenote"
    )
    read = [
        skill / "SKILL.md",
        *sorted((skill / "references").glob("*.md")),
        skill / "packages/default/registry.json",
        skill / "assets/registry.json",
    ]
    hits = [
        f"{p.relative_to(arm)}:{n}: {line.strip()[:100]}"
        for p in read
        for n, line in enumerate(p.read_text().splitlines(), 1)
        if pattern.search(line) and "packages.md" not in p.name
    ]
    if hits:
        sys.exit("vocabulary survives:\n" + "\n".join(hits))
