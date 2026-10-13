"""The widget quality report (`leaf/render_gate/widget_quality.py`): Leaf's own widgets
held to it, and `package check --render` telling a package's author what it found. And
the first box a widget keeps where the report's served examples do not reach: a tab set
opening on a later panel, and an export."""

import json
import re

import pytest
from interact_support import SKILL_ROOT
from leaf import exporting as exporting_model
from leaf.render_checks import wait_until_ready
from leaf.revision_delivery import json_script
from model_folds import leaf_page
from playwright.sync_api import expect
from render_harness import ROOT, consume_browser_errors, displayed


def grows_at_upgrade(tag: str, style: str) -> str:
    """A widget module that writes `style` onto its element when it upgrades."""
    return f"""\
import {{ once }} from "/runtime/widget-api.js";

export default class extends HTMLElement {{
    connectedCallback() {{
      if (once(this)) this.style.cssText = "{style}";
    }}
}};
"""


def keyed(tag: str, badge: str) -> str:
    """A widget module that declares a command with a context key on its element, and
    `badge` as the command's `bindingBadge` field, verbatim."""
    return f"""\
import {{ commands, once }} from "/runtime/widget-api.js";

export default class extends HTMLElement {{
    connectedCallback() {{
      if (!once(this)) return;
      commands(this, "Keyed", [
        {{ id: "{tag[3:]}.go", keys: [], contextKeys: ["1"], control: this,
          title: "Go", run: () => {{}}{badge} }},
      ]);
    }}
}}
"""


# Each authored widget the reader can see, by id: its box, its top measured from the
# document's start so a scroll between two readings is not a move; and the panels the
# tab sets show. An upgraded set's inactive panel is `hidden="until-found"`, which
# leaves it a box of no height that `checkVisibility` still counts.
SHOWN = """() => {
  const scrolled = document.scrollingElement.scrollTop;
  return {
    boxes: Object.fromEntries(
      [...document.querySelectorAll('body > main [id]')]
        .filter((element) => element.localName.startsWith('lf-'))
        .filter((element) => element.checkVisibility() && !element.closest('[hidden]'))
        .map((element) => {
          const box = element.getBoundingClientRect();
          return [element.id, [box.width, box.height, box.top + scrolled].map(Math.round)];
        }),
    ),
    panels: [...document.querySelectorAll('lf-tab')]
      .filter((panel) => panel.querySelector('p').checkVisibility())
      .map((panel) => panel.id),
  };
}"""

# The page's own tab strip, and a framed set below it, each with a taller later panel.
TAB_SETS = """
<h1 id="title">Views</h1>
<lf-tabs id="views">
  <lf-tab id="one" label="One"><p id="first">The first view is one line.</p></lf-tab>
  <lf-tab id="two" label="Two">
    <p id="second">The second view runs longer.</p>
    <p id="second-more">It holds a second paragraph, so it stands taller.</p>
  </lf-tab>
</lf-tabs>
<lf-tabs id="more">
  <lf-tab id="near" label="Near"><p id="near-words">Near.</p></lf-tab>
  <lf-tab id="far" label="Far">
    <p id="far-words">Far, and taller.</p>
    <p id="far-more">Another line.</p>
  </lf-tab>
</lf-tabs>
<p id="after">What follows the sets stays where it first painted.</p>
"""


def test_a_tab_set_first_paints_the_panel_it_opens_on(browser, serve):
    """A set opens on the panel holding the element the address's fragment names, and
    on reload on the panel this browser tab last showed, and shows that panel from the
    first paint: the prepaint marks it before the module graph has loaded, from the
    reading the module opens on, so nothing moves when the set upgrades. Without the
    mark the theme can reserve only the first panel, which neither journey opens on."""
    url = serve(leaf_page("Views", TAB_SETS))
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    boot = []

    def first_paint_then_presented(navigate):
        page.route("**/leaf.js", lambda route: boot.append(route))
        with page.expect_request("**/leaf.js"):
            navigate()
        displayed(page)
        assert boot, "the positive control did not hold the boot module"
        first = page.evaluate(SHOWN)
        page.unroute("**/leaf.js")
        boot.pop().continue_()
        wait_until_ready(page)
        return first, page.evaluate(SHOWN)

    try:
        first, presented = first_paint_then_presented(
            lambda: page.goto(f"{url}#second-more", wait_until="commit")
        )
        assert first["panels"] == ["two", "near"], first
        assert first == presented

        page.get_by_role("tab", name="Far").click()
        first, presented = first_paint_then_presented(
            lambda: page.reload(wait_until="commit")
        )
        assert first["panels"] == ["two", "far"], first
        assert first == presented
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


DIFF_EXAMPLE = json.loads(
    (SKILL_ROOT / "packages" / "diff" / "registry.json").read_text()
)["lf-diff"]["x-example"]

# Each case's markup and the window width it is read at. A draft indented as the HTML
# around it is, its closing tag on a line of its own, with words that wrap in a phone's
# column. The diff package's worked example, whose stated height is its drawing's at
# the report's desktop width, read in a phone's window, where it also opens the column;
# and at a desktop width closing a panel, whose frame trims the host's own margin. A
# framed tab set and a side-list queue whose names run past a phone's width, each
# reserving the one row its strip keeps, the queue's group labels included.
FIRST_BOXES = {
    "draft-in-a-phone-column": (
        """
<lf-draft id="note">
  <pre>
    Adds --dry-run to every mutating command, so a script can see what would change.
  </pre>
</lf-draft>
""",
        320,
    ),
    "diff-in-a-phone-column": (DIFF_EXAMPLE, 320),
    "diff-closing-a-panel": (
        f'<section class="panel" id="ends"><p>The patch.</p>{DIFF_EXAMPLE}</section>',
        1200,
    ),
    "tab-names-outrunning-a-phone": (
        '<section id="views-section"><lf-tabs id="views">'
        + "".join(
            f'<lf-tab id="view-{i}" label="View {i}"><p id="words-{i}">View {i}.</p>'
            "</lf-tab>"
            for i in range(12)
        )
        + "</lf-tabs></section>",
        390,
    ),
    "queue-in-a-phone": (
        '<lf-tabs id="queue" list="side">'
        + "".join(
            f'<lf-tab id="item-{i}" label="Item {i}" summary="{i} days old" '
            f'group="{"Merge" if i < 6 else "Close"}">'
            f'<p id="item-words-{i}">Item {i}.</p></lf-tab>'
            for i in range(12)
        )
        + "</lf-tabs>",
        390,
    ),
}


@pytest.mark.parametrize("case", FIRST_BOXES)
def test_a_widget_first_paints_the_box_it_presents(browser, serve, case):
    """A draft's authored words stand where its drawn body will, the source's
    indentation and closing line dropped and the words wrapped as the body wraps them.
    A diff's toolbar keeps one row in a phone's column, so the height its author stated
    at a desktop width holds there, and its drawing hands no margin out past the frame
    trim at either edge. A tab strip is one row however many names it holds, the
    summary line a queue's rows carry included, so the open panel stands where it
    first painted. What follows each stays where it first painted."""
    markup, width = FIRST_BOXES[case]
    url = serve(
        leaf_page(
            "First boxes",
            markup + '\n<lf-draft id="after"><pre>After.</pre></lf-draft>',
        )
    )
    page = browser.new_page(viewport={"width": width, "height": 900})
    boot = []
    page.route("**/leaf.js", lambda route: boot.append(route))
    try:
        with page.expect_request("**/leaf.js"):
            page.goto(url, wait_until="commit")
        displayed(page)
        assert boot, "the positive control did not hold the boot module"
        first = page.evaluate(SHOWN)["boxes"]
        page.unroute("**/leaf.js")
        boot.pop().continue_()
        wait_until_ready(page)
        assert first == page.evaluate(SHOWN)["boxes"]
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


@pytest.fixture(name="gallery_page_files")
def gallery_page_files_fixture():
    """Keep the gallery's initial-paint tests on its actual page-owned assets."""
    companion = ROOT / "examples/developer/feature-gallery.page"
    return {
        path.relative_to(companion).as_posix(): path.read_text(encoding="utf-8")
        for path in companion.rglob("*")
        if path.is_file()
    }


def test_an_export_first_paints_its_widgets_at_their_presented_boxes(
    browser, serve, tmp_path, gallery_page_files
):
    """An export runs the runtime, so its widgets take the boxes their modules will
    draw from the first paint, as a served page's do; it draws no live chrome, so it
    reserves no banner. Its first paint is the export without its entry module, which
    is the document the browser lays out before the module graph runs. One whose entry
    cannot load falls back to the readable page."""
    serve(
        leaf_page(
            "Exported",
            TAB_SETS
            + INITIAL_DRAWING_PAGE.replace('id="title"', 'id="drawing-title"').replace(
                'id="after"', 'id="drawing-after"'
            ),
            head='<link rel="stylesheet" href="/page/theme.css">',
        ),
        page_files=gallery_page_files,
    )
    exported = tmp_path / "exported.html"
    exporting_model.cmd_export(serve.page_dir, exported, None)
    entry = re.compile(
        r'(<script type="module" src=)"[^"]*"( data-lf-runtime></script>)'
    )
    source = exported.read_text(encoding="utf-8")
    packaged = re.search(
        r'<script type="application/json" data-lf-export>(.*?)</script>',
        source,
        re.DOTALL,
    )
    package = json.loads(packaged[1])
    composed = package["document"]
    held_document, entries = entry.subn("", composed)
    assert entries == 1, "the composed export no longer names one entry module"

    def write_document(path, document):
        package["document"] = document
        path.write_text(
            source[: packaged.start(1)]
            + json_script(package)
            + source[packaged.end(1) :],
            encoding="utf-8",
        )

    held = tmp_path / "held.html"
    write_document(held, held_document)
    failed = tmp_path / "failed.html"
    write_document(failed, entry.sub(r'\1"missing.js"\2', composed))

    first_page = browser.new_page(viewport={"width": 1200, "height": 900})
    first_page.goto(held.as_uri(), wait_until="load")
    displayed(first_page)
    first = first_page.evaluate(SHOWN)

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.goto(exported.as_uri(), wait_until="load")
    wait_until_ready(page)
    presented = page.evaluate(SHOWN)

    assert {
        "views",
        "more",
        "drawing",
        "faces-one",
        "faces-two",
    } <= first["boxes"].keys(), first
    expect(first_page.locator("#drawing input")).to_have_count(5)
    expect(first_page.locator("#drawing lf-playground-output")).to_contain_text(
        "Field note"
    )
    expect(first_page.locator("#faces-one .margin-entry-gallery-item")).to_have_count(
        22
    )
    assert first == presented
    assert (
        page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--lf-banner-h')"
        )
        == "0px"
    )

    # An export whose runtime cannot start has no server to wait for, but it still
    # gives back the readable fallback: every panel, under its label.
    broken = browser.new_page(viewport={"width": 1200, "height": 900})
    broken.goto(failed.as_uri(), wait_until="load")
    expect(broken.locator("html")).to_have_attribute(
        "data-lf-startup-error", "entry module did not load"
    )
    assert broken.evaluate(SHOWN)["panels"] == ["one", "two", "near", "far"]
    consume_browser_errors(broken, "missing.js", "net::ERR_FAILED")


INITIAL_DRAWING_PAGE = """
<h1 id="title">First drawing</h1>
<lf-playground id="drawing">
  <lf-playground-control name="title" label="Title" kind="text" value="Field note"></lf-playground-control>
  <lf-playground-control name="radius" label="Corner radius" kind="range" value="12" min="0" max="24" unit="px"></lf-playground-control>
  <lf-playground-control name="compact" label="Compact spacing" kind="toggle" value="false"></lf-playground-control>
  <lf-playground-control name="tone" label="Tone" kind="choice" value="quiet">
    <lf-playground-choice value="quiet" label="Quiet"></lf-playground-choice>
    <lf-playground-choice value="bold" label="Bold"></lf-playground-choice>
  </lf-playground-control>
  <lf-playground-preview><p>The actual preview, with its own words.</p></lf-playground-preview>
  <lf-playground-output>Build <lf-playground-value for="title"></lf-playground-value> with
    <lf-playground-value for="radius"></lf-playground-value> corners and
    <lf-playground-value for="tone"></lf-playground-value> emphasis.</lf-playground-output>
</lf-playground>
<lf-margin-entry-gallery id="faces-one"></lf-margin-entry-gallery>
<lf-margin-entry-gallery id="faces-two"></lf-margin-entry-gallery>
<p id="after">Reading after the widgets stays in place.</p>
"""

# Native fields, wrapped labels and instructions, and the paragraph after two
# independent galleries. Measuring just the outer widget can miss movement inside it.
INITIAL_DRAWING_NODES = """lf-playground, lf-playground-control,
  lf-playground-preview, lf-playground-output, lf-playground-value,
  .lf-playground-input, .lf-playground-control-label, .lf-playground-choice-face,
  .lf-playground-reading, .lf-playground-copy-trigger,
  lf-margin-entry-gallery, .margin-entry-gallery-name, .margin-entry-gallery-detail, .margin-entry-gallery-heading, .margin-entry-gallery-summary, .margin-entry-gallery-face,
  #after"""
