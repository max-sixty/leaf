"""The widget quality report (`leaf/render_gate/widget_quality.py`): Leaf's own widgets
held to it, and `package check --render` telling a package's author what it found. And
the first box a widget keeps where the report's served examples do not reach: a tab set
opening on a later panel, and an export."""

import json
import os
import re
import subprocess

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import SKILL_ROOT
from known_widget_findings import KNOWN
from leaf import cli as cli_model
from leaf import exporting as exporting_model
from leaf import schema as schema_model
from leaf.render_checks import wait_until_ready
from leaf.render_gate.widget_quality import widget_findings
from leaf.revision_delivery import json_script
from model_folds import leaf_page
from playwright.sync_api import expect
from render_harness import consume_browser_errors, displayed

# The base layer's two halves and every bundled package, each reported on its own
# widgets as a package author's `package check --render` would.
PACKAGES = [
    schema_model.ASSETS,
    *sorted(path for path in (SKILL_ROOT / "packages").iterdir() if path.is_dir()),
]


def test_every_known_finding_names_a_bundled_package():
    """An entry under a package that is gone is never compared, so never deleted."""
    assert set(KNOWN) <= {package.name for package in PACKAGES}


@pytest.mark.parametrize("package", PACKAGES, ids=lambda package: package.name)
def test_bundled_widgets_meet_the_widget_quality_checks(browser, package):
    """Each bundled package's report finds exactly what `known_widget_findings.py`
    lists for it: a new finding is a regression to fix, and a listed one that no
    longer occurs was fixed, so its entry goes. The pages it reads are full of the
    shifts the check exists to find, so it reads them unwatched."""
    findings = widget_findings(browser.unwatched, package)
    known = KNOWN.get(package.name, set())
    new = [
        str(finding)
        for finding in findings
        if (finding.tag, finding.check) not in known
    ]
    assert not new, "findings known_widget_findings.py does not list:\n" + "\n".join(
        new
    )
    fixed = known - {(finding.tag, finding.check) for finding in findings}
    assert not fixed, f"fixed, so delete from known_widget_findings.py: {sorted(fixed)}"


def grows_at_upgrade(tag: str, style: str) -> str:
    """A widget module that writes `style` onto its element when it upgrades."""
    return f"""\
import {{ once }} from "/runtime/widget-api.js";

customElements.define(
  "{tag}",
  class extends HTMLElement {{
    connectedCallback() {{
      if (once(this)) this.style.cssText = "{style}";
    }}
  }},
);
"""


def test_package_check_render_reports_findings_as_advice(tmp_path, headless_shell):
    """`package check --render` names each finding by tag, check and measured fact,
    and still exits 0. `lf-grow` adds 40px at upgrade, on its own and inside two
    holders that each grow by exactly that: `lf-holder` because what it holds grew, so
    it is not named beside it, and `lf-fixed` because it sets its own height 40px
    taller, so it is. `lf-word` is inline and doubles its type, and since no size
    puts an inline box's lines back, the line holding it is named beside it. `lf-bare`
    has no worked example."""
    package = tmp_path / "package"
    for widget in ("lf-grow", "lf-holder", "lf-fixed", "lf-word", "lf-bare"):
        made = CliRunner().invoke(
            cli_model.cli, ["package", "init", str(package), "--widget", widget]
        )
        assert made.exit_code == 0, made.output
    widgets = package / "widgets"
    (widgets / "lf-grow.js").write_text(
        grows_at_upgrade("lf-grow", "padding-bottom: 40px")
    )
    (widgets / "lf-fixed.js").write_text(grows_at_upgrade("lf-fixed", "height: 140px"))
    (widgets / "lf-word.js").write_text(grows_at_upgrade("lf-word", "font-size: 32px"))
    # An element the theme does not style is inline, whose box a padding would not
    # grow the way a block's grows.
    (package / "theme.css").write_text(
        ":scope:is(lf-grow, lf-holder, lf-fixed) { display: block; }\n"
        ":scope:is(lf-fixed) { height: 100px; }\n"
    )
    registry_path = package / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-holder"]["x-example"] = (
        '<lf-holder id="holder"><lf-grow id="held">Held.</lf-grow></lf-holder>'
    )
    registry["lf-holder"]["x-example"] += (
        '<lf-holder id="line">A <lf-word id="spoken">word</lf-word> in a line.</lf-holder>'
    )
    registry["lf-fixed"]["x-example"] = (
        '<lf-fixed id="fixed"><lf-grow id="inner">Inner.</lf-grow></lf-fixed>'
    )
    del registry["lf-bare"]["x-example"]
    registry_path.write_text(json.dumps(registry))

    ran = subprocess.run(
        [*LEAF_COMMAND, "package", "check", str(package), "--render"],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ | {"LEAF_BROWSER_EXECUTABLE": headless_shell},
    )
    assert ran.returncode == 0, ran.stderr
    lines = ran.stdout.splitlines()
    assert lines[1] == (
        f"widget quality: 8 finding(s) for 5 widget(s) in {headless_shell}, "
        "advice for the widgets' author:"
    ), ran.stdout
    assert lines[2] == "  · <lf-bare> example: no worked example shows it"
    finding = re.compile(
        r"  · <(lf-[a-z]+) id='(\w+)'> keeps-first-box: "
        r"first painted (\d+)x(\d+), (\d+)x(\d+) once presented"
    )
    readings = [finding.fullmatch(line) for line in lines[3:]]
    assert all(readings), lines
    grown = {reading[2]: int(reading[6]) - int(reading[4]) for reading in readings}
    assert all(grown.pop(word) > 0 for word in ("word", "spoken", "line")), lines
    assert grown == {"grow": 40, "held": 40, "fixed": 40, "inner": 40}, lines


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


def test_an_export_first_paints_its_widgets_at_their_presented_boxes(
    browser, serve, tmp_path
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
        )
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


@pytest.mark.parametrize("width", [1200, 390])
def test_initial_drawings_keep_their_nodes_and_wrapped_geometry_on_upgrade(
    browser, serve, width
):
    """Hold the full entry module to observe the actual parser-closing drawing.
    The default and a restored longer instruction keep the same control and gallery
    nodes and their geometry through upgrade, including the following reading and
    different font metrics in the phone. Two
    galleries also retain distinct control identities in one document."""
    url = serve(
        leaf_page(
            "First drawing",
            INITIAL_DRAWING_PAGE,
            head="<style>:root { --sans: Georgia, serif; --mono: Courier, monospace; }</style>"
            if width == 390
            else "",
        )
    )
    page = browser.new_page(
        viewport={"width": width, "height": 900}, has_touch=width == 390
    )
    boot = []
    reading = """selector => [...document.querySelectorAll(selector)]
      .map(node => {
        const box = node.getBoundingClientRect();
        return [node.id || node.localName, ...[box.x, box.y + scrollY, box.width, box.height].map(Math.round)];
      })"""

    def first_and_upgraded(navigate, title):
        page.route("**/leaf.js", lambda route: boot.append(route))
        with page.expect_request("**/leaf.js"):
            navigate()
        displayed(page)
        assert boot, "the positive control did not hold the entry module"
        expect(page.locator('input[aria-label="Title"]')).to_have_value(title)
        expect(page.locator("lf-playground-output")).to_contain_text(title)
        assert page.locator(".margin-entry-gallery-face").count() == 44
        page.evaluate(
            "selector => window.initialDrawingNodes = [...document.querySelectorAll(selector)]",
            INITIAL_DRAWING_NODES,
        )
        assert page.locator(".margin-entry-gallery-item").evaluate_all(
            "items => items.every(item => item.querySelector('.margin-entry-gallery-copy').getBoundingClientRect().left - item.querySelector('.margin-entry-gallery-face').getBoundingClientRect().right >= 7.5)"
        ), "the gallery label must follow the actual control's width"
        first = page.evaluate(reading, INITIAL_DRAWING_NODES)
        page.unroute("**/leaf.js")
        boot.pop().continue_()
        wait_until_ready(page)
        assert page.evaluate(reading, INITIAL_DRAWING_NODES) == first
        assert page.evaluate(
            "selector => [...document.querySelectorAll(selector)].every((node, i) => node === window.initialDrawingNodes[i])",
            INITIAL_DRAWING_NODES,
        )
        ids = page.locator(".margin-entry-gallery-face[id]").evaluate_all(
            "nodes => nodes.map(node => node.id)"
        )
        assert len(ids) == len(set(ids))

    try:
        first_and_upgraded(lambda: page.goto(url, wait_until="commit"), "Field note")
        title = "A longer title that wraps the actual instruction in a phone column"
        page.get_by_role("textbox", name="Title").fill(title)
        page.get_by_role("radio", name="Bold", exact=True).check()
        first_and_upgraded(lambda: page.reload(wait_until="commit"), title)
        expect(page.get_by_role("radio", name="Bold", exact=True)).to_be_checked()
        assert page.locator("#drawing").evaluate("host => host.values.title") == title
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")
