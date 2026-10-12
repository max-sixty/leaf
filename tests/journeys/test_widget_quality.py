"""The widget quality report (`leaf/render_gate/widget_quality.py`): Leaf's own widgets
held to it, and `package check --render` telling a package's author what it found. And
the first box a widget keeps where the report's served examples do not reach: a tab set
opening on a later panel, and an export."""

import json
import os
import re
import subprocess

import pytest
from browser.test_widget_quality import (
    INITIAL_DRAWING_NODES,
    INITIAL_DRAWING_PAGE,
    gallery_page_files_fixture,  # noqa: F401 (fixtures)
    grows_at_upgrade,
    keyed,
)
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from known_widget_findings import KNOWN, PACKAGES
from leaf import cli as cli_model
from leaf.render_checks import wait_until_ready
from leaf.render_gate.widget_quality import widget_findings
from model_folds import leaf_page
from playwright.sync_api import expect
from render_harness import displayed


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


def test_package_check_render_reports_findings_as_advice(tmp_path, headless_shell):
    """`package check --render` names each finding by tag, check and measured fact,
    and still exits 0. `lf-grow` adds 40px at upgrade, on its own and inside two
    holders that each grow by exactly that: `lf-holder` because what it holds grew, so
    it is not named beside it, and `lf-fixed` because it sets its own height 40px
    taller, so it is. `lf-word` is inline and doubles its type, and since no size
    puts an inline box's lines back, the line holding it is named beside it. `lf-bare`
    has no worked example.

    `lf-pinned` keeps a height its theme sets and scrolls inside it, so it is named for
    not growing with its content even though its one line fits. `lf-declared` keeps the
    same height and says so with `--lf-holds-height: 1`, `lf-sideways` keeps it but asks
    to scroll only sideways, and `lf-roomy` asks to scroll but grows past its minimum
    height, so none of them is. `lf-shallow` asks only for sideways scrolling, but its
    line runs past its height, so it scrolls vertically and is named.

    `lf-keyed` declares a context key with no `bindingBadge`, so the page never shows
    it and it is named; `lf-badged` asks for a corner badge, so it is not."""
    package = tmp_path / "package"
    for widget in (
        "lf-grow",
        "lf-holder",
        "lf-fixed",
        "lf-word",
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
    (widgets / "lf-grow.js").write_text(
        grows_at_upgrade("lf-grow", "padding-bottom: 40px")
    )
    (widgets / "lf-fixed.js").write_text(grows_at_upgrade("lf-fixed", "height: 140px"))
    (widgets / "lf-word.js").write_text(grows_at_upgrade("lf-word", "font-size: 32px"))
    (widgets / "lf-keyed.js").write_text(keyed("lf-keyed", ""))
    (widgets / "lf-badged.js").write_text(keyed("lf-badged", ", bindingBadge: null"))
    # An element the theme does not style is inline, whose box a padding would not
    # grow the way a block's grows.
    (package / "theme.css").write_text(
        ":scope:is(lf-grow, lf-holder, lf-fixed) { display: block; }\n"
        ":scope:is(lf-fixed) { height: 100px; }\n"
        ":scope:is(lf-pinned, lf-declared, lf-sideways) { display: block; "
        "block-size: 100px; }\n"
        ":scope:is(lf-pinned) { overflow: auto; }\n"
        ":scope:is(lf-declared) { overflow: auto; --lf-holds-height: 1; }\n"
        ":scope:is(lf-sideways) { overflow-x: auto; }\n"
        ":scope:is(lf-roomy) { display: flex; min-block-size: 100px; overflow: auto; }\n"
        ":scope:is(lf-shallow) { display: block; block-size: 10px; overflow-x: auto; }\n"
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
        f"widget quality: 11 finding(s) for 12 widget(s) in {headless_shell}, "
        "advice for the widgets' author:"
    ), ran.stdout
    assert lines[2] == "  · <lf-bare> example: no worked example shows it"
    finding = re.compile(
        r"  · <(lf-[a-z]+) id='(\w+)'> keeps-first-box: "
        r"first painted (\d+)x(\d+), (\d+)x(\d+) once presented"
    )
    advice = (
        "and scrolls inside it; let it grow with its content, or declare "
        "--lf-holds-height: 1 where the task needs its own scroll"
    )
    assert lines[-3:] == [
        (
            "  · <lf-keyed id='keyed'> shows-context-keys: keyed.go declares "
            "context keys and no bindingBadge, so its key works with nothing on the "
            "page showing it; lend the command a face, or request a corner badge "
            "with bindingBadge: null"
        ),
        (
            "  · <lf-pinned id='pinned'> grows-with-content: <lf-pinned id=pinned> "
            f"holds 100px {advice}"
        ),
        (
            "  · <lf-shallow id='shallow'> grows-with-content: <lf-shallow id=shallow> "
            f"holds 10px {advice}"
        ),
    ], ran.stdout
    readings = [finding.fullmatch(line) for line in lines[3:-3]]
    assert all(readings), lines
    grown = {reading[2]: int(reading[6]) - int(reading[4]) for reading in readings}
    assert all(grown.pop(word) > 0 for word in ("word", "spoken", "line")), lines
    assert grown == {"grow": 40, "held": 40, "fixed": 40, "inner": 40}, lines


@pytest.mark.parametrize("width", [1200, 390])
def test_initial_drawings_keep_their_nodes_and_wrapped_geometry_on_upgrade(
    browser, serve, width, gallery_page_files
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
