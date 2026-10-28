"""Preview and offline export tests."""

from click.testing import CliRunner
from interact_support import PAGE, publish
from render_harness import (
    leaf_page,
)

from leaf import cli as cli_model


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
