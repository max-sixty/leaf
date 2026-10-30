"""Preview and offline export tests."""

import json

from click.testing import CliRunner
from interact_support import PAGE, publish
from render_harness import (
    leaf_page,
)

from leaf import cli as cli_model
from leaf.event_log import read_events
from leaf.files import published_versions


def test_export_refuses_an_unstamped_version_without_replacing_the_destination(
    page_dir, tmp_path
):
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    output = tmp_path / "offline.html"
    output.write_text("Keep the existing export")
    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "export", str(page_dir), "--version", "9", "--out", str(output)],
    )
    assert result.exit_code != 0
    assert "v9 is not stamped" in result.output
    assert output.read_text() == "Keep the existing export"


def test_export_refuses_server_dependent_samples(serve, tmp_path):
    serve(
        leaf_page(
            "Live sample",
            '<lf-sample id="practice" label="practice">'
            '<template id="practice-source" data-sample><h1>Child</h1></template>'
            "</lf-sample>",
        )
    )
    output = tmp_path / "offline.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "export",
            str(serve.page_dir),
            "--out",
            str(output),
        ],
    )
    assert result.exit_code != 0
    assert "Live samples need a server" in result.output
    assert not output.exists()


def test_export_draft_captures_current_source_without_stamping(page_dir, tmp_path):
    source = page_dir / "index.html"
    source.write_text(
        PAGE.replace("</main>", '<h1 id="export-heading">First</h1></main>')
    )
    output = tmp_path / "offline.html"
    runner = CliRunner()
    args = ["page", "export", str(page_dir), "--out", str(output)]
    result = runner.invoke(cli_model.cli, [*args, "--draft"])
    assert result.exit_code == 0, result.output
    first = json.loads(result.output)
    assert first["version"] is None
    assert first["revision"] == 1
    assert '<h1 id="export-heading">First</h1>' in output.read_text()
    assert published_versions(page_dir, read_events(page_dir)) == []

    publish(page_dir)
    source.write_text(source.read_text().replace(">First</h1>", ">Second</h1>"))
    result = runner.invoke(cli_model.cli, args)
    assert result.exit_code == 0, result.output
    stamped = json.loads(result.output)
    assert stamped["version"] == 1
    assert stamped["revision"] == first["revision"]
    assert '<h1 id="export-heading">First</h1>' in output.read_text()

    result = runner.invoke(cli_model.cli, [*args, "--draft"])
    assert result.exit_code == 0, result.output
    draft = json.loads(result.output)
    assert draft["version"] is None
    assert draft["revision"] > first["revision"]
    assert '<h1 id="export-heading">Second</h1>' in output.read_text()
    assert published_versions(page_dir, read_events(page_dir)) == [1]


def test_export_draft_refuses_invalid_source_and_version_selection(page_dir, tmp_path):
    source = page_dir / "index.html"
    source.write_text(PAGE)
    publish(page_dir)
    output = tmp_path / "offline.html"
    output.write_text("Keep the existing export")
    args = ["page", "export", str(page_dir), "--out", str(output), "--draft"]
    result = CliRunner().invoke(cli_model.cli, [*args, "--version", "1"])
    assert result.exit_code != 0
    assert "--draft" in result.output and "--version" in result.output
    source.write_text("<main><lf-no-such-widget></lf-no-such-widget></main>")
    result = CliRunner().invoke(cli_model.cli, args)
    assert result.exit_code != 0
    assert "lf-no-such-widget" in result.output
    assert output.read_text() == "Keep the existing export"
