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
            + """
<lf-milestones>
  <lf-milestone id="build" status="active" when="weeks 2-3" tags="wood,solar">
    <strong>Build the feeders</strong> Two classic, two heated.
  </lf-milestone>
</lf-milestones>
<lf-tree id="tree"><pre>
feeders/
  mount.py  +2 -2
  sites/
    north.toml
</pre></lf-tree>
""",
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

    assert {"views", "more", "build", "tree"} <= first["boxes"].keys(), first
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
