"""Widget quality reports and restored values in complete gallery views."""

import json
import os
import subprocess

import pytest
from browser.test_widget_quality import (
    INITIAL_DRAWING_PAGE,
    gallery_page_files_fixture,  # noqa: F401 (fixtures)
    keyed,
)
from conftest import LEAF_COMMAND
from interact_support import add_test_widget, wait_for
from known_widget_findings import KNOWN, PACKAGES
from model_folds import leaf_page
from playwright.sync_api import expect

from leaf.log import event_log
from leaf.pages.render_gate.widget_quality import widget_findings
from leaf.source.render_checks import wait_until_ready


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
        if (finding.values["tag"], finding.code) not in known
    ]
    assert not new, "findings known_widget_findings.py does not list:\n" + "\n".join(
        new
    )
    fixed = known - {(finding.values["tag"], finding.code) for finding in findings}
    assert not fixed, f"fixed, so delete from known_widget_findings.py: {sorted(fixed)}"


def test_package_check_render_reports_findings_as_advice(tmp_path, headless_shell):
    """The report names actionable content-growth and context-key advice, and exits 0."""
    package = tmp_path / "package"
    for widget in (
        "lf-bare",
        "lf-pinned",
        "lf-declared",
        "lf-sideways",
        "lf-roomy",
        "lf-shallow",
        "lf-keyed",
        "lf-badged",
    ):
        add_test_widget(package, widget, upgrade=True)
    widgets = package / "widgets"
    (widgets / "lf-keyed.js").write_text(keyed("lf-keyed", ""))
    (widgets / "lf-badged.js").write_text(keyed("lf-badged", ", bindingBadge: null"))
    # An element the theme does not style is inline, whose box a padding would not
    # grow the way a block's grows.
    (package / "defaults.css").write_text(
        ":is(lf-pinned, lf-declared, lf-sideways) { display: block; "
        "block-size: 100px; }\n"
        "lf-pinned { overflow: auto; }\n"
        "lf-declared { overflow: auto; --lf-holds-height: 1; }\n"
        "lf-sideways { overflow-x: auto; }\n"
        "lf-roomy { display: flex; min-block-size: 100px; overflow: auto; }\n"
        "lf-shallow { display: block; block-size: 10px; overflow-x: auto; }\n"
    )
    registry_path = package / "registry.json"
    registry = json.loads(registry_path.read_text())
    del registry["lf-bare"]["example"]
    registry_path.write_text(json.dumps(registry))

    ran = subprocess.run(
        [*LEAF_COMMAND, "package", "check", str(package), "--render"],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ | {"LEAF_BROWSER_EXECUTABLE": headless_shell},
    )
    assert ran.returncode == 0, ran.stderr
    report = json.loads(ran.stdout)
    assert report["status"] == 0
    assert report["browser"] == {
        "asked": ["widget quality"],
        "ran": ["widget quality"],
        "browser": headless_shell,
    }
    findings = report["findings"]
    assert {f["severity"] for f in findings} == {"advice"}, findings
    named = {}
    layouts = {}
    for f in findings:
        values = dict(f["values"])
        if "layout" in values:
            layouts.setdefault((f["code"], f["at"]), set()).add(values.pop("layout"))
        named.setdefault(f["code"], {})[f["at"]] = values
    # Each page of examples is read as a column document and in a workspace's pane, and
    # these widgets behave alike in both.
    assert all(seen == {"column", "workspace"} for seen in layouts.values()), layouts
    assert set(named) == {
        "example",
        "shows-context-keys",
        "grows-with-content",
    }, findings
    assert list(named["example"]) == ["<lf-bare>"]
    assert named["shows-context-keys"] == {
        "<lf-keyed id=keyed>": {"tag": "lf-keyed", "command": "keyed.go"}
    }
    assert {at: v["height"] for at, v in named["grows-with-content"].items()} == {
        "<lf-pinned id=pinned>": 100,
        "<lf-shallow id=shallow>": 10,
    }


@pytest.mark.parametrize("width", [1200, 390])
def test_complete_views_restore_native_values_in_wrapped_layouts(
    browser, serve, width, gallery_page_files
):
    """Readable desktop and phone source enhances into controls with saved inputs."""
    url = serve(
        leaf_page(
            "First drawing",
            INITIAL_DRAWING_PAGE,
            head='<link rel="stylesheet" href="/page/theme.css">'
            + (
                "<style>:root { --lf-sans: Georgia, serif; --lf-mono: Courier, monospace; }</style>"
                if width == 390
                else ""
            ),
        ),
        page_files=gallery_page_files,
    )
    page = browser.new_page(
        viewport={"width": width, "height": 900}, has_touch=width == 390
    )
    boot = []

    def first_and_upgraded(navigate, title):
        page.route("**/leaf.js", lambda route: boot.append(route))
        with page.expect_request("**/leaf.js"):
            navigate()
        expect(page.locator("main")).to_be_visible()
        expect(page.locator("#drawing-words")).to_have_text(
            "The actual preview, with its own words."
        )
        expect(page.locator("#drawing input")).to_have_count(5)
        assert boot, "the positive control did not hold the entry module"
        page.unroute("**/leaf.js")
        boot.pop().continue_()
        wait_until_ready(page)
        expect(page.get_by_role("textbox", name="Title")).to_have_value(title)
        expect(page.locator("lf-playground-output")).to_contain_text(title)
        # Each of the page's two galleries draws one face per sample, the same samples.
        drawn = page.locator("lf-margin-entry-gallery").evaluate_all(
            "galleries => galleries.map(gallery => [gallery.querySelectorAll('.margin-entry-gallery-item').length, gallery.querySelectorAll('.margin-entry-gallery-face').length])"
        )
        assert len(drawn) == 2 and drawn[0] == drawn[1], drawn
        assert drawn[0][0] > 0 and drawn[0][0] == drawn[0][1], drawn
        assert page.locator(".margin-entry-gallery-item").evaluate_all(
            "items => items.every(item => item.querySelector('.margin-entry-gallery-copy').getBoundingClientRect().left - item.querySelector('.margin-entry-gallery-face').getBoundingClientRect().right >= 7.5)"
        ), "the gallery label must follow the actual control's width"
        ids = page.locator(".margin-entry-gallery-face[id]").evaluate_all(
            "nodes => nodes.map(node => node.id)"
        )
        assert len(ids) == len(set(ids))

    try:
        first_and_upgraded(lambda: page.goto(url, wait_until="commit"), "Field note")
        title = "A longer title that wraps the actual instruction in a phone column"
        page.get_by_role("textbox", name="Title").fill(title)
        page.get_by_role("radio", name="Bold", exact=True).check()
        # The blur records the title and the press then records Bold; the press's
        # record waits for the first's answer, so a reload before the log holds it
        # leaves it unsent.
        wait_for(
            lambda: [
                event["detail"]["values"]
                for event in event_log.read_events(serve.page_dir)
                if event.get("action") == "tune"
            ],
            lambda tunes: tunes and tunes[-1]["tone"] == "bold",
            failure="the press on Bold was never recorded",
        )
        first_and_upgraded(lambda: page.reload(wait_until="commit"), title)
        expect(page.get_by_role("radio", name="Bold", exact=True)).to_be_checked()
        assert page.locator("#drawing").evaluate("host => host.values.title") == title
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


def test_package_render_check_compares_held_and_presented_boxes(tmp_path, browser):
    """A generated view needs its first box; an equal reserved box is a control."""
    package = tmp_path / "package"
    add_test_widget(package, "lf-first-box", upgrade=True)
    registry_path = package / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-first-box"]["example"] = (
        '<lf-first-box id="moving"></lf-first-box>'
        '<lf-first-box id="reserved"></lf-first-box>'
    )
    registry_path.write_text(json.dumps(registry))
    (package / "defaults.css").write_text(
        "lf-first-box { display: block; } #reserved { block-size: 40px; }"
    )
    (package / "widgets/lf-first-box.js").write_text("""\
import { html } from "/vendor/lit.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
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
