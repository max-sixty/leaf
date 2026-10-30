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
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from known_widget_findings import KNOWN, PACKAGES
from model_folds import leaf_page
from playwright.sync_api import expect

from leaf import cli as cli_model
from leaf import layer as layer_model
from leaf import schema as schema_model
from leaf.render_checks import wait_until_ready
from leaf.render_gate.widget_quality import widget_findings


@pytest.mark.parametrize("package", PACKAGES, ids=lambda package: package.name)
def test_bundled_widgets_meet_the_widget_quality_checks(browser, package):
    """Each bundled package's report finds exactly what `known_widget_findings.py`
    lists for it: a new finding is a regression to fix, and a listed one that no
    longer occurs was fixed, so its entry goes. The pages it reads are full of the
    shifts the check exists to find, so it reads them unwatched."""
    # compiled_pages lends the browser tier a prepared kernel as its base layer.
    # Read its assets there rather than adding the checkout's source assets as a
    # second package over that kernel.
    if package == schema_model.ASSETS:
        package = layer_model.ASSETS
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
        made = CliRunner().invoke(
            cli_model.cli, ["package", "init", str(package), "--widget", widget]
        )
        assert made.exit_code == 0, made.output
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
    """Desktop and phone views reveal complete controls and restore saved inputs."""
    url = serve(
        leaf_page(
            "First drawing",
            INITIAL_DRAWING_PAGE,
            head='<link rel="stylesheet" href="/page/theme.css">'
            + (
                "<style>:root { --sans: Georgia, serif; --mono: Courier, monospace; }</style>"
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
        expect(page.locator("main")).to_be_hidden()
        assert boot, "the positive control did not hold the entry module"
        page.unroute("**/leaf.js")
        boot.pop().continue_()
        wait_until_ready(page)
        expect(page.locator('input[aria-label="Title"]')).to_have_value(title)
        expect(page.locator("lf-playground-output")).to_contain_text(title)
        assert page.locator(".margin-entry-gallery-face").count() == 44
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
        first_and_upgraded(lambda: page.reload(wait_until="commit"), title)
        expect(page.get_by_role("radio", name="Bold", exact=True)).to_be_checked()
        assert page.locator("#drawing").evaluate("host => host.values.title") == title
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")
