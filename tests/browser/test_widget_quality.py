"""Widget quality, remembered tab views and complete export presentation."""

import json
import re

import pytest
from click.testing import CliRunner
from model_folds import leaf_page
from playwright.sync_api import expect
from render_harness import ROOT, consume_browser_errors

from leaf import cli as cli_model
from leaf import exporting as exporting_model
from leaf.render_checks import wait_until_ready
from leaf.render_gate.widget_quality import UnreadablePage, widget_findings
from leaf.revision_delivery import json_script


def test_package_render_check_refuses_a_failed_async_paint(tmp_path, browser):
    """A settled example whose asynchronous drawing rejected was not drawn."""
    package = tmp_path / "package"
    made = CliRunner().invoke(
        cli_model.cli,
        ["package", "init", str(package), "--widget", "lf-async-panel"],
    )
    assert made.exit_code == 0, made.output
    (package / "widgets/lf-async-panel.js").write_text("""\
import { LeafElement, html } from "/runtime/widget-api.js";
customElements.define("lf-async-panel", class extends LeafElement {
  render() { return html`Instrument`; }
  async getUpdateComplete() {
    await super.getUpdateComplete();
    throw new Error("The instrument paint failed");
  }
});
""")
    with pytest.raises(UnreadablePage, match="The instrument paint failed"):
        widget_findings(browser.unwatched, package)


def test_package_render_check_compares_held_and_presented_boxes(tmp_path, browser):
    """A generated view needs its first box; an equal reserved box is a control."""
    package = tmp_path / "package"
    made = CliRunner().invoke(
        cli_model.cli,
        ["package", "init", str(package), "--widget", "lf-first-box"],
    )
    assert made.exit_code == 0, made.output
    registry_path = package / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-first-box"]["x-example"] = (
        '<lf-first-box id="moving"></lf-first-box>'
        '<lf-first-box id="reserved"></lf-first-box>'
    )
    registry_path.write_text(json.dumps(registry))
    (package / "defaults.css").write_text(
        "lf-first-box { display: block; } #reserved { block-size: 40px; }"
    )
    (package / "widgets/lf-first-box.js").write_text("""\
import {LeafElement, html} from "/runtime/widget-api.js";
customElements.define("lf-first-box", class extends LeafElement {
  render() { return html`<div style="block-size:40px">Drawn view</div>`; }
});
""")
    findings = [
        finding
        for finding in widget_findings(browser.unwatched, package)
        if finding.code == "keeps-first-box"
    ]
    assert {finding.at for finding in findings} == {"<lf-first-box id=moving>"}
    assert {finding.values["layout"] for finding in findings} == {"column", "workspace"}
    assert all(finding.values["first"]["height"] == 0 for finding in findings)
    assert all(finding.values["now"]["height"] == 40 for finding in findings)


def keyed(tag: str, badge: str) -> str:
    """A widget module that declares a command with a context key on its element, and
    `badge` as the command's `bindingBadge` field, verbatim."""
    return f"""\
import {{ once, commandsChanged }} from "/runtime/widget-api.js";

customElements.define(
  "{tag}",
  class extends HTMLElement {{
    connectedCallback() {{
      if (!once(this)) return;
      this.lfCommands = {{ title: "Keyed", rows: [
        {{ id: "{tag[3:]}.go", keys: [], contextKeys: ["1"], control: this,
          title: "Go", run: () => {{}}{badge} }},
      ] }};
      commandsChanged(this);
    }}
  }},
);
"""


# Inactive tabs keep until-found boxes; visibility decides which panel is readable.
SHOWN_PANELS = """() => [...document.querySelectorAll('lf-tab')]
  .filter((panel) => panel.querySelector('p').checkVisibility())
  .map((panel) => panel.id)"""

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
<p id="after">Text after the tab sets.</p>
"""


def test_tab_sets_open_on_a_fragment_and_restore_each_saved_panel(browser, serve):
    url = serve(leaf_page("Views", TAB_SETS))
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.goto(f"{url}#second-more")
    wait_until_ready(page)
    assert page.evaluate(SHOWN_PANELS) == ["two", "near"]
    page.get_by_role("tab", name="Far").click()
    page.reload()
    wait_until_ready(page)
    assert page.evaluate(SHOWN_PANELS) == ["two", "far"]


@pytest.fixture(name="gallery_page_files")
def gallery_page_files_fixture():
    """Keep the gallery's presentation tests on its actual page-owned assets."""
    companion = ROOT / "examples/developer/feature-gallery.page"
    return {
        path.relative_to(companion).as_posix(): path.read_text(encoding="utf-8")
        for path in companion.rglob("*")
        if path.is_file()
    }


def test_an_export_reveals_its_widgets_and_releases_readable_failure_fallback(
    browser, serve, tmp_path, gallery_page_files
):
    """Exports start readable, enhance into widgets, and retain source on failure."""
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
    assert packaged is not None
    package = json.loads(packaged[1])
    composed = package["document"]
    held_document, entries = entry.subn("", composed)
    assert entries == 1, "the composed export no longer names one entry module"

    def write_document(path, document):
        package["document"] = document
        assert packaged is not None
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
    expect(first_page.locator("main")).to_be_visible()
    expect(first_page.locator("#drawing lf-playground-preview")).to_have_text(
        "The actual preview, with its own words."
    )
    expect(first_page.locator("#drawing input")).to_have_count(0)
    assert first_page.evaluate(SHOWN_PANELS) == ["one", "near"]

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.goto(exported.as_uri(), wait_until="load")
    wait_until_ready(page)
    for id in ("views", "more", "drawing", "faces-one", "faces-two"):
        expect(page.locator(f"#{id}")).to_be_visible()
    expect(page.locator("#drawing input")).to_have_count(5)
    expect(page.locator("#drawing lf-playground-output")).to_contain_text("Field note")
    expect(page.locator("#faces-one .margin-entry-gallery-item")).to_have_count(22)
    expect(page.locator("html")).not_to_have_attribute("data-lf-live", "")

    # An export whose runtime cannot start retains readable authored content.
    broken = browser.new_page(viewport={"width": 1200, "height": 900})
    broken.goto(failed.as_uri(), wait_until="load")
    expect(broken.locator("html")).to_have_attribute(
        "data-lf-startup-error", "entry module did not load"
    )
    expect(broken.locator("main")).to_be_visible()
    expect(broken.locator("#drawing lf-playground-preview")).to_have_text(
        "The actual preview, with its own words."
    )
    assert broken.evaluate(SHOWN_PANELS) == ["one", "two", "near", "far"]
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
