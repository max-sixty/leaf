"""Screenshot UI states on a base's runtime and this working tree's, and show which ones
changed.

    uv run leaf-dev stills [--base REF] [--state NAME]... [--authored]
        [--viewport WIDTHxHEIGHT|NAME] [--scheme dark] [--touch] [--browser ENGINE]

Each state of `leaf_dev.states` (all of them unless `--state` names some) is visited on
both arms through the loop `leaf-dev probe` runs too (`leaf_dev.visits`), which brings
a fresh tab on each to the state, in the engine `--browser` names. The base is the
merge base with `main` unless `--base` names another commit, and the head is this
working tree, uncommitted edits included (`leaf_dev.arms.choose_arms`). Each page is
built from this working tree's example source and served by the arm's own launcher,
so only the runtime, theme and server differ between the two stills of a state. With
`--authored`, the base instead reads its own example and companions
(`leaf_dev.arms.own_source`), so changes to page markup are visible as well. Each
capture starts with a fresh authored fixture and event log, so a prior gesture cannot
change another state's initial condition.
Message delivery belongs to thread_journey and test_render_thread_snapshots, whose
held checkpoints capture a send before its POST completes; a still cannot hold one.

`--viewport`, `--scheme` and `--touch` set the window of every state a run captures;
a state that names its own window keeps it unless `--viewport` gives another, and
`--touch` or `--no-touch` sets the pointer of either (the `leaf_dev.states` header
says when a state may name one). Raw screenshots always preserve the full viewport
and its geometry.
Use repeated `--state` options to compare only the states a change touches.

Whether a state changed, and where, is `lf-shot`'s reading of its two stills, from the
module that owns the rule (the default package's `widgets/image-difference.js`),
loaded into a tab of the browser that took the stills, or of a Chromium shell when
the iOS simulator took them.
Each invocation allocates a run directory under `.tmp/stills/`. Each state's
directory within it holds `base.png` and `head.png`, and for a
change `base-crop.png` and `head-crop.png` cropped to the union of its regions (or
whole, when the reading names none), ready to hand off as an `lf-shot` pair, and
`diff.png` outlining the head's own regions, a change in red and a move in blue. The
crops cover both stills' regions.

Beside each pair, the command reads the cascade a screenshot only shows in part: the
computed `STYLED` properties of every element in the document and its open shadow
trees, hidden ones included, so the corpus states read every page it composes (a
rule that depends on a page's own Layout, such as a sidebar page's panels, reads only
on that page's states).
Elements are keyed by their path of tags, ids and first two classes. A state with a
differing property, or a subtree only one arm has, also counts as changed, and its
`styles.txt` lists them (`style_changes`). The properties are the cascade's own, not
the geometry it produces, which the stills show; width, height and offsets stay out
because they move with every reflow. Below them, in Chromium, for each group's first
element, it lists the declarations Chromium's inspector reads as matching it in only
one arm, or in another order, each with its sheet, layers, scope and selector
(`declaration_changes`): the rule a change added, removed, edited or moved. Where none
differ, the element inherits the difference or reads it from a custom property.

The command reads, too, where words stand on their lines. Words of two faces centred
in boxes of their own stand on different baselines, the larger lower, and a reader
sees the line step by a pixel. In every state both arms completed,
`stills_baselines.js` reads the words that stand beside each other on a line (its
header says which), and the run's `baselines.txt` lists each line whose words stand a
quarter of a CSS pixel or more apart (`baseline_changes`): those only head splits,
those both arms split, and those only base splits. Words on a box of their own, such
as a key's letter on its badge, are listed and marked but count toward no split, since
the eye reads that box rather than their baseline.

Capture and comparison failures are reported per state, with tracebacks in its
directory; the remaining states still run. A state whose input the engine can't run,
such as any input on the iOS simulator, is such a failure. Only complete pairs enter
the comparison. Arm construction, browser setup failures and interrupts end the
command, and a state whose page can't be found ends it before any capture. Once the
whole report is written, the command exits 1 if any state failed, so a caller that
reads only the exit status still learns that a state went uncaptured.
"""

import json
import re
import tempfile
import traceback
from collections.abc import Callable, Iterable
from contextlib import contextmanager, nullcontext
from difflib import SequenceMatcher
from functools import partial
from pathlib import Path

import click
from PIL import Image
from playwright.sync_api import Page, expect
from selenium.webdriver.remote.webdriver import WebDriver

from leaf.revision_artifact import resource_type
from leaf.runtime_selection import read_runtime
from leaf_dev import ROOT, gallery
from leaf_dev.arms import base_option, choose_arms, describe, run_directory
from leaf_dev.browser import (
    Window,
    chosen_window,
    engine_option,
    headless_shell,
    launch,
    screenshot,
    tab_options,
)
from leaf_dev.example_data import named_source
from leaf_dev.states import STATES, State
from leaf_dev.visits import Visit, said, visits

OUT = ROOT / ".tmp" / "stills"
CROP_MARGIN = 32
DIFFERENCE = ROOT / "packages" / "default" / "widgets" / "image-difference.js"
# Where `differences` serves the stills and the module that compares them.
ORIGIN = "http://stills.invalid"
# The computed properties `style_changes` compares: the faces, boxes and flow a rule
# sets, not the layout it produces.
STYLED = [
    "color",
    "background-color",
    "background-image",
    "border-top-width",
    "border-right-width",
    "border-bottom-width",
    "border-left-width",
    "border-top-style",
    "border-right-style",
    "border-bottom-style",
    "border-left-style",
    "border-top-color",
    "border-right-color",
    "border-bottom-color",
    "border-left-color",
    "border-top-left-radius",
    "border-top-right-radius",
    "border-bottom-right-radius",
    "border-bottom-left-radius",
    "box-shadow",
    "outline-style",
    "outline-width",
    "outline-color",
    "outline-offset",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "font-variant-numeric",
    "line-height",
    "letter-spacing",
    "text-transform",
    "text-align",
    "text-decoration-line",
    "text-decoration-color",
    "text-underline-offset",
    "text-wrap-style",
    "white-space",
    "overflow-wrap",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "display",
    "position",
    "max-width",
    "min-width",
    "max-height",
    "overflow-x",
    "overflow-y",
    "vertical-align",
    "list-style-type",
    "gap",
    "flex-direction",
    "align-items",
    "justify-content",
    "color-scheme",
    "container-type",
    "opacity",
    "visibility",
    "cursor",
    "box-sizing",
    "z-index",
]
# Every element's `STYLED` values by its path, sharing each distinct set of values, and
# the elements themselves by path on `window.stillsRead`, for `declarations`.
STYLES = """(properties) => {
  const skip = new Set(["head", "script", "style", "template", "link", "meta"]);
  const faces = new Map();
  const elements = {};
  const read = (window.stillsRead = new Map());
  const walk = (parent, prefix) => {
    const seen = {};
    for (const element of parent.children) {
      if (skip.has(element.localName)) continue;
      const label = element.localName + (element.id
        ? `#${element.id}`
        : [...element.classList].slice(0, 2).map((name) => `.${name}`).join(""));
      seen[label] = (seen[label] ?? -1) + 1;
      const key = prefix + label + (seen[label] ? `:${seen[label]}` : "");
      const style = getComputedStyle(element);
      const face = JSON.stringify(properties.map((name) => style.getPropertyValue(name)));
      if (!faces.has(face)) faces.set(face, faces.size);
      elements[key] = faces.get(face);
      read.set(key, element);
      walk(element, `${key} > `);
      if (element.shadowRoot) walk(element.shadowRoot, `${key} >> `);
    }
  };
  walk(document, "");
  return { faces: [...faces.keys()].map((face) => JSON.parse(face)), elements };
}"""
# Where the words beside each other on a line stand their baselines
# (`baseline_changes`), and the gap between two of them that the report names: half a
# device pixel of the 2x stills, which can round to a whole one. A reader saw a name
# stand half a CSS pixel below its time.
BASELINES = Path(__file__).with_name("stills_baselines.js").read_text()
SPLIT = 0.25


# Device pixels to a CSS pixel in each still: the density of the displays its pairs
# are read on, so a crop shows text and hairlines as the reader's screen draws them.
SCALE = 2


def capture(state: State, folder: Path, arm: str, visit: Visit) -> None:
    """Screenshot the tab `visit` brought to `state` to `folder/ARM.png`, and read
    into the visit the state's region in the screenshot, if it names one, its
    elements' styles (`STYLES`), and the lines whose words stand on baselines `SPLIT`
    apart (`BASELINES`)."""
    page = visit.page
    if state.region:
        target = page.locator(state.region)
        expect(target).to_be_visible()
        bounds = target.bounding_box()
        assert bounds is not None
        window = page.viewport_size
        # Keep the focus paint outside the target while omitting unrelated chrome.
        room = 8
        x, y = max(0, bounds["x"] - room), max(0, bounds["y"] - room)
        clip = {
            "x": x,
            "y": y,
            "width": min(window["width"], bounds["x"] + bounds["width"] + room) - x,
            "height": min(window["height"], bounds["y"] + bounds["height"] + room) - y,
        }
        visit.reading["region"] = {key: value * SCALE for key, value in clip.items()}
    (folder / f"{arm}.png").write_bytes(screenshot(page))
    reading = page.evaluate(STYLES, STYLED)
    visit.reading["styles"] = {
        key: reading["faces"][face] for key, face in reading["elements"].items()
    }
    visit.reading["splits"] = page.evaluate(BASELINES, SPLIT)


def style_changes(
    base: dict[str, list[str]], head: dict[str, list[str]]
) -> tuple[int, list[str], list[str]]:
    """Each `STYLED` property whose value differs between an element's base and head
    readings, grouped by property and values with up to four of its elements, then
    the subtrees only one arm has, each named by its outermost element, since a widget
    that draws in one arm and not the other adds every node of its drawing. Return how
    many element properties differ, plus those subtrees, the lines that list them, and
    each group's first element."""
    groups: dict[tuple[str, str, str], list[str]] = {}
    for key in base.keys() & head.keys():
        for name, before, after in zip(STYLED, base[key], head[key], strict=True):
            if before != after:
                groups.setdefault((name, before, after), []).append(key)
    alone = {
        heading: sorted(
            key for key in keys if re.sub(r" >>? [^ ]+$", "", key) not in keys
        )
        for heading, keys in (
            ("only in base", base.keys() - head.keys()),
            ("only in head", head.keys() - base.keys()),
        )
    }
    lines = []
    firsts = {}
    for (name, before, after), keys in sorted(
        groups.items(), key=lambda group: -len(group[1])
    ):
        keys.sort()
        firsts[keys[0]] = None
        lines.append(f"{name}: {before} -> {after}  x{len(keys)}")
        lines.extend(f"    {key}" for key in keys[:4])
    for heading, keys in alone.items():
        if keys:
            lines.append(f"{heading}  x{len(keys)}")
            lines.extend(f"    {key}" for key in keys[:4])
    count = sum(map(len, groups.values())) + sum(map(len, alone.values()))
    return count, lines, list(firsts)


def baseline_changes(split: dict[str, dict[str, list[dict]]]) -> list[str]:
    """The lines whose words stand on baselines `SPLIT` apart in `split` (each arm's,
    by state, from `BASELINES`): those only head splits, those both arms split, with
    how far apart each arm stands them, and those only base splits, each with its
    words' faces and where each stands against the line's first."""

    def keyed(arm: str) -> dict[tuple, tuple[str, dict]]:
        # A line is known by its state, row and words, and by which of the lines alike
        # in those it is (`nth`), so two rows that read alike stay two.
        return {
            (
                state,
                line["row"],
                *(item["text"] for item in line["items"]),
                line["nth"],
            ): (state, line)
            for state, lines in split[arm].items()
            for line in lines
        }

    head, base = keyed("head"), keyed("base")
    groups = (
        ("only head splits", head, head.keys() - base.keys()),
        ("both arms split", head, head.keys() & base.keys()),
        ("only base splits", base, base.keys() - head.keys()),
    )
    lines = []
    for title, read, keys in groups:
        if not keys:
            continue
        lines.append(f"lines {title}  x{len(keys)}")
        for key in sorted(keys):
            state, line = read[key]
            spread = f"{line['spread']}px"
            if key in base and key in head:
                spread = f"{base[key][1]['spread']} -> {spread}"
            lines.append(f"  {state}: {line['row']}  {spread} apart")
            lines.extend(
                f"      {item['text']!r} {item['face']}"
                f"{' on a box' if item['boxed'] else ''} {item['offset']:+.2f}"
                for item in line["items"]
            )
    return lines


def declarations(page: Page) -> Callable[[str], list[str]]:
    """Read an element `STYLES` read, by its key, through Chromium's inspector: every
    authored declaration of the rules that match it and of its style attribute, in the
    order the inspector lists them, each with its sheet, layers, scope and selector."""
    session = page.context.new_cdp_session(page)
    sheets: dict[str, dict] = {}
    session.on(
        "CSS.styleSheetAdded",
        lambda event: sheets.update({event["header"]["styleSheetId"]: event["header"]}),
    )
    session.send("DOM.enable")
    session.send("CSS.enable")
    session.send("DOM.getDocument")

    def label(rule: dict) -> str:
        header = sheets.get(rule.get("styleSheetId"), {})
        if rule["origin"] != "regular":
            sheet = rule["origin"]
        elif header.get("isConstructed"):
            sheet = "constructed"
        # An inline sheet's URL is its document's, which names the arm's port.
        elif header.get("isInline") or not header.get("sourceURL"):
            sheet = "<style>"
        else:
            sheet = header["sourceURL"].rsplit("/", 1)[-1]
        layers = ".".join(layer["text"] or "anonymous" for layer in rule["layers"])
        return " ".join(
            [
                sheet,
                *([f"@layer {layers}"] if layers else []),
                *(f"@scope {scope['text']}" for scope in rule["scopes"]),
                rule["selectorList"]["text"],
            ]
        )

    def read(key: str) -> list[str]:
        element = session.send(
            "Runtime.evaluate", {"expression": f"stillsRead.get({json.dumps(key)})"}
        )
        node = session.send(
            "DOM.requestNode", {"objectId": element["result"]["objectId"]}
        )
        matched = session.send("CSS.getMatchedStylesForNode", node)
        rules = [
            (label(entry["rule"]), entry["rule"]["style"])
            for entry in matched["matchedCSSRules"]
        ]
        if matched.get("inlineStyle"):
            rules.append(("style attribute", matched["inlineStyle"]))
        return [
            f"{rule} {{ {' '.join(declaration['text'].split())} }}"
            for rule, style in rules
            for declaration in style["cssProperties"]
            if "text" in declaration
        ]

    return read


def declaration_changes(pages: dict[str, Page], keys: Iterable[str]) -> list[str]:
    """For each element, the declarations (`declarations`) that match it in only one
    of the arms' `pages`, or in another order, as lines under its key."""
    read = {arm: declarations(page) for arm, page in pages.items()}
    lines = ["declarations that differ, on each group's first element"]
    for key in keys:
        before, after = read["base"](key), read["head"](key)
        changes = [
            line
            for tag, i, j, k, m in SequenceMatcher(
                None, before, after, autojunk=False
            ).get_opcodes()
            if tag != "equal"
            for line in [
                *(f"- {row}" for row in before[i:j]),
                *(f"+ {row}" for row in after[k:m]),
            ]
        ]
        lines.append(f"    {key}")
        lines.extend(
            f"        {line}"
            for line in changes
            or ["none: it inherits the difference or reads it from a custom property"]
        )
    return lines


@contextmanager
def differences(out: Path, browser):
    """One comparison tab in `browser`, or in a Chromium shell when `browser` is the
    iOS simulator's Safari, yielding `lf-shot`'s reading of a named state's pair.

    Reuse the browser module for the catalogue; each comparison is a separate call
    so a state's unreadable image or failed crop leaves the other pairs available.
    """

    # The module imports the public package API, as a widget does, so the tab answers
    # with this tree's runtime under the package's own vendored modules.
    runtime = read_runtime().source

    def serve(route) -> None:
        path = route.request.url.removeprefix(ORIGIN)
        package = ROOT / "packages" / "default" / path.lstrip("/")
        if path == "/image-difference.js":
            route.fulfill(path=DIFFERENCE, content_type="text/javascript")
        elif path.startswith("/vendor/") and package.is_file():
            route.fulfill(path=package)
        elif path in runtime:
            route.fulfill(body=runtime[path], content_type=resource_type(path))
        elif path.endswith(".png"):
            route.fulfill(path=out / path.lstrip("/"))
        else:
            route.fulfill(body="<!doctype html>", content_type="text/html")

    with (
        headless_shell() if isinstance(browser, WebDriver) else nullcontext(browser)
    ) as browser:
        context = browser.new_context()
        try:
            context.route(f"{ORIGIN}/**", serve)
            page = context.new_page()
            page.goto(f"{ORIGIN}/")
            compare_images = page.evaluate_handle(
                "async () => (await import('/image-difference.js')).compareImages"
            )

            def compare(name: str) -> dict:
                return compare_images.evaluate(
                    """async (compareImages, name) => {
                      const load = async (arm) => {
                        const image = new Image();
                        image.src = `/${name}/${arm}.png`;
                        await image.decode();
                        return image;
                      };
                      return compareImages(await load("base"), await load("head"));
                    }""",
                    name,
                )

            yield compare
        finally:
            context.close()


def crop(
    folder: Path, regions: list[dict], *, framing: list[dict] | None = None
) -> None:
    """Crop both stills around framing (or changed regions); retain actual diff outlines."""
    base = Image.open(folder / "base.png").convert("RGB")
    head = Image.open(folder / "head.png").convert("RGB")
    framing = regions if framing is None else framing
    box = (
        gallery.frame(map(gallery.edges, framing), CROP_MARGIN, head.width, head.height)
        if framing
        else (0, 0, head.width, head.height)
    )
    base.crop(box).save(folder / "base-crop.png")
    head.crop(box).save(folder / "head-crop.png")
    faded = Image.blend(head, Image.new("RGB", head.size, "white"), 0.6)
    after = [r for r in regions if r["side"] == "after"]
    for color, kind in (((220, 0, 0), True), ((40, 110, 230), False)):
        faded = gallery.marked(
            faded,
            color,
            outlined=[
                gallery.edges(r) for r in after if (r["kind"] == "changed") == kind
            ],
        )
    faded.crop(box).save(folder / "diff.png")


@click.command()
@base_option(paired=True)
@click.option(
    "--state",
    "names",
    type=click.Choice([state.name for state in STATES]),
    metavar="NAME",
    multiple=True,
    help="Capture a state of leaf_dev.states; repeat for more. Defaults to them all.",
)
@click.option(
    "--authored",
    is_flag=True,
    help="Build the base's pages from its own authored sources.",
)
@tab_options
@engine_option
def stills(
    base: str,
    names: tuple[str, ...],
    authored: bool,
    viewport: Window | None,
    scheme: str,
    touch: bool | None,
    engine: str,
) -> None:
    """Screenshot UI states on the base's runtime and this working tree's, in
    Chromium, Firefox, WebKit or Safari on an iPhone simulator (--browser), and crop
    each state that changed into a before/after pair under .tmp/stills/.

    --viewport, --scheme and --touch set the window of every state captured; a state
    that names its own window keeps it unless --viewport gives another, and --touch
    or --no-touch sets the pointer of either. The iPhone sets its own window, and its
    Safari takes no input, so only a state at rest captures there."""
    states = [state for state in STATES if not names or state.name in names]
    sources = {state.name: named_source(state.source) for state in states}
    out = run_directory(OUT)
    failed: dict[str, list[str]] = {}
    read: dict[str, dict] = {}
    split: dict[str, dict[str, list[dict]]] = {"base": {}, "head": {}}

    def failure(state: State, phase: str, error: Exception) -> None:
        failed.setdefault(state.name, []).append(f"on {phase}: {said(error)}")
        (out / state.name / f"{phase}-error.txt").write_text(
            "".join(traceback.format_exception(error))
        )

    with (
        tempfile.TemporaryDirectory(prefix="leaf-stills-") as built,
        launch(engine, scheme) as browser,
        differences(out, browser) as compare,
    ):
        scratch = Path(built)
        arms = choose_arms(base, scratch)
        for state in states:
            folder = out / state.name
            folder.mkdir()
            # Every state starts from its authored fixture, so a prior Send or Resolve
            # can't become the next state's initial event log. The base refuses a
            # source written in vocabulary only the head declares; that state has no
            # base still, and the head's still stands alone in its folder. Both arms'
            # tabs stay open through the comparison, which reads them.
            with visits(
                browser,
                arms,
                state,
                sources[state.name],
                scratch / state.name,
                window=chosen_window(state.window, viewport, touch),
                scheme=scheme,
                read=partial(capture, state, folder),
                scale=SCALE,
                authored=authored,
            ) as each:
                found = dict(each)
                for arm, visit in found.items():
                    if visit.error:
                        failure(state, arm, visit.error)
                if state.name in failed:
                    continue
                for arm, visit in found.items():
                    split[arm][state.name] = visit.reading["splits"]
                try:
                    difference = compare(state.name)
                    if difference["changed"]:
                        crop(
                            folder,
                            difference["regions"],
                            framing=[
                                visit.reading["region"]
                                for visit in found.values()
                                if "region" in visit.reading
                            ]
                            or None,
                        )
                    difference["styles"], lines, firsts = style_changes(
                        found["base"].reading["styles"], found["head"].reading["styles"]
                    )
                    if firsts and engine == "chromium":
                        lines += declaration_changes(
                            {arm: visit.page for arm, visit in found.items()}, firsts
                        )
                    if lines:
                        (folder / "styles.txt").write_text("\n".join(lines) + "\n")
                    read[state.name] = difference
                except Exception as error:
                    failure(state, "comparison", error)
    click.echo(describe(arms))
    unchanged = 0
    for state in states:
        folder = out / state.name
        if state.name in failed:
            click.echo(f"  failed  {state.name} {'; '.join(failed[state.name])}")
        elif (difference := read[state.name])["changed"] or difference["styles"]:
            click.echo(
                f"  changed {state.name}: {difference['changed']} px,"
                f" {difference['styles']} styles -> {folder}"
            )
        else:
            unchanged += 1
    click.echo(f"{unchanged} of {len(states)} states unchanged")
    if lines := baseline_changes(split):
        (out / "baselines.txt").write_text("\n".join(lines) + "\n")
        click.echo(
            "lines whose words split their baseline: "
            + ", ".join(line.strip() for line in lines if line.startswith("lines"))
            + f" -> {out / 'baselines.txt'}"
        )
    click.echo(f"files in {out}")
    if failed:
        raise SystemExit(1)
