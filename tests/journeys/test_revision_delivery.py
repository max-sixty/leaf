"""Tests scheduled by the measured cost of their boundary."""

import json
import subprocess

from conftest import LEAF_COMMAND
from playwright.sync_api import expect
from render_harness import leaf_page, open_page


def test_page_code_fetches_a_page_file_nothing_names(browser, serve):
    """A revision holds every file under page/, so a module fetching one by a URL it
    computes draws it, in a served version and under `page check --render`."""
    source = leaf_page(
        "Page data", '<h1 id="title">Page data</h1><p id="message">Waiting</p>'
    )
    source = source.replace(
        "</head>", '<script type="module" src="/page/app.js"></script></head>'
    )
    url = serve(
        source,
        packages=(),
        page_files={
            "app.js": """
const url = new URL("./tables/data.json", import.meta.url);
const response = await fetch(url);
if (!response.ok) throw new Error(`${url}: ${response.status}`);
document.getElementById("message").textContent = (await response.json()).message;
""",
            "tables/data.json": '{"message": "Drawn from page data"}',
        },
    )
    page = open_page(browser, url)
    expect(page.locator("#message")).to_have_text("Drawn from page data")

    checked = subprocess.run(
        [*LEAF_COMMAND, "page", "check", str(serve.page_dir), "--render"],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(checked.stdout)
    assert report["browser"]["ran"] == ["page code", "render check"], report
    assert [f for f in report["findings"] if f["severity"] == "error"] == []


def test_an_export_runs_the_exporters_runtime(page_dir, monkeypatch):
    """An export pairs the state the exporting Leaf reads with that Leaf's runtime,
    whichever Leaf captured the version, since only that runtime reads that state."""
    from click.testing import CliRunner

    from leaf import cli as cli_model
    from leaf import runtime_selection
    from leaf.exporting import cmd_export

    stamped = CliRunner().invoke(
        cli_model.cli, ["page", "stamp", str(page_dir), "--text", "Exported"]
    )
    assert stamped.exit_code == 0, stamped.output
    current = runtime_selection.read_runtime()
    marker = b"/* the exporting Leaf's runtime */"
    exporter = runtime_selection.ServingRuntime(
        {
            **current.source,
            "/runtime/prepaint.js": current.source["/runtime/prepaint.js"] + marker,
        },
        None,
        frozenset(),
        current.probes,
    )
    monkeypatch.setattr(runtime_selection, "serving_runtime", lambda: exporter)

    out = page_dir.parent / "export.html"
    cmd_export(page_dir, out, 1)

    assert marker.decode() in out.read_text()
