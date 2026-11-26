"""Widget quality, remembered tab views and complete export presentation."""

import json
import re

import pytest
from click.testing import CliRunner
from interact_support import add_test_widget
from model_folds import leaf_page
from playwright.sync_api import expect
from render_harness import ROOT, consume_browser_errors

from leaf.commands import cli as cli_model
from leaf.pages import exporting as exporting_model
from leaf.pages.render_gate import command as render_command_model
from leaf.pages.render_gate.widget_quality import UnreadablePage, widget_findings
from leaf.serving.revision_delivery import json_script
from leaf.source.render_checks import wait_until_ready


def test_the_starter_widgets_leave_the_render_check_nothing_to_advise(
    tmp_path, browser
):
    """What `package init --widget` writes is right as written, for each tag named:
    the render check draws every starter's example and finds nothing to advise."""
    package = tmp_path / "package"
    made = CliRunner().invoke(
        cli_model.cli,
        ["package", "init", str(package), "--widget", "lf-one", "--widget", "lf-two"],
    )
    assert made.exit_code == 0, made.output
    assert widget_findings(browser.unwatched, package) == []


def test_package_render_check_refuses_a_failed_async_paint(tmp_path, browser):
    """A settled example whose asynchronous drawing rejected was not drawn."""
    package = tmp_path / "package"
    add_test_widget(package, "lf-async-panel", upgrade=True)
    (package / "widgets/lf-async-panel.js").write_text("""\
import { html } from "/vendor/lit.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
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


def test_package_render_check_names_the_import_a_module_fails_to_link(
    tmp_path, browser, monkeypatch
):
    """A widget module that imports a name the imported module doesn't export fails to
    link, so the page of worked examples says it cannot start. The check ends when the
    page says so and reports the page's reason, which quotes the browser's message
    naming the module and the name. A wait that ran to its deadline would instead
    name the stage the page never reached."""
    package = tmp_path / "package"
    made = CliRunner().invoke(
        cli_model.cli, ["package", "init", str(package), "--widget", "lf-unlinked"]
    )
    assert made.exit_code == 0, made.output
    (package / "widgets/lf-unlinked.js").write_text("""\
import { notExported } from "/runtime/portable-api.js";
customElements.define("lf-unlinked", class extends HTMLElement {
  connectedCallback() { this.textContent = notExported; }
});
""")
    monkeypatch.setattr(
        render_command_model,
        "run_in_browser",
        lambda read: (read(browser.unwatched), "the suite's browser"),
    )
    [finding] = render_command_model.widget_quality(package).findings
    assert finding.code == "unreadable-examples"
    error = finding.values["error"]
    assert error.startswith("the runtime could not start: "), error
    assert "/runtime/portable-api.js" in error and "notExported" in error, error


def keyed(tag: str, badge: str) -> str:
    """A widget module that declares a command with a context key on its element, and
    `badge` as the command's `bindingBadge` field, verbatim."""
    return f"""\
import {{ once }} from "/runtime/lib/once.js";

customElements.define(
  "{tag}",
  class extends HTMLElement {{
    connectedCallback() {{
      if (!once(this)) return;
      this.lfCommands = {{ title: "Keyed", rows: [
        {{ id: "{tag[3:]}.go", keys: [], contextKeys: ["1"], control: this,
          title: "Go", run: () => {{}}{badge} }},
      ] }};
      this.dispatchEvent(new CustomEvent("lf-commands", {{ bubbles: true, composed: true }}));
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
    exporting_model.cmd_export(serve.page_dir, exported, None, runtime=True)
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
    expect(first_page.locator("#drawing-words")).to_have_text(
        "The actual preview, with its own words."
    )
    expect(first_page.locator("#drawing input")).to_have_count(5)
    assert first_page.evaluate(SHOWN_PANELS) == ["one", "near"]

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.goto(exported.as_uri(), wait_until="load")
    wait_until_ready(page)
    for id in ("views", "more", "drawing", "faces-one", "faces-two"):
        expect(page.locator(f"#{id}")).to_be_visible()
    expect(page.locator("#drawing input")).to_have_count(5)
    expect(page.locator("#drawing lf-playground-output")).to_contain_text("Field note")
    # Each gallery draws one face per sample, the same samples in both.
    expect(page.locator("#faces-one .margin-entry-gallery-item")).not_to_have_count(0)
    drawn = page.locator("lf-margin-entry-gallery").evaluate_all(
        "galleries => galleries.map(gallery => [gallery.querySelectorAll('.margin-entry-gallery-item').length, gallery.querySelectorAll('.margin-entry-gallery-face').length])"
    )
    assert len(drawn) == 2 and drawn[0] == drawn[1], drawn
    assert drawn[0][0] == drawn[0][1], drawn
    expect(page.locator("html")).not_to_have_attribute("data-lf-live", "")

    # An export whose runtime cannot start retains readable authored content.
    broken = browser.new_page(viewport={"width": 1200, "height": 900})
    broken.goto(failed.as_uri(), wait_until="load")
    expect(broken.locator("html")).to_have_attribute(
        "data-lf-startup-error", "entry module did not load"
    )
    expect(broken.locator("main")).to_be_visible()
    expect(broken.locator("#drawing-words")).to_have_text(
        "The actual preview, with its own words."
    )
    assert broken.evaluate(SHOWN_PANELS) == ["one", "two", "near", "far"]
    consume_browser_errors(broken, "missing.js", "net::ERR_FAILED")


INITIAL_DRAWING_PAGE = """
<h1 id="title">First drawing</h1>
<lf-group id="drawing-q" label="How should the field note look?"><lf-playground id="drawing">
  <aside>
    <label id="field-note-title">Title <input name="title" value="Field note"></label>
    <label id="radius">Corner radius, px <input type="range" name="radius" min="0" max="24" value="12"></label>
    <label id="compact"><input type="checkbox" name="compact" role="switch"> Compact spacing</label>
    <fieldset id="tone"><legend>Tone</legend>
      <label id="tone-quiet"><input type="radio" name="tone" value="quiet" checked> Quiet</label>
      <label id="tone-bold"><input type="radio" name="tone" value="bold"> Bold</label>
    </fieldset>
  </aside>
  <p id="drawing-words">The actual preview, with its own words.</p>
  <lf-playground-output>Build <output for="title"></output> with
    <output for="radius"></output>px corners and
    <output for="tone"></output> emphasis.</lf-playground-output>
</lf-playground></lf-group>
<lf-margin-entry-gallery id="faces-one"></lf-margin-entry-gallery>
<lf-margin-entry-gallery id="faces-two"></lf-margin-entry-gallery>
<p id="after">Reading after the widgets stays in place.</p>
"""
