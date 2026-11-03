"""Tests scheduled by the measured cost of their boundary."""

from click.testing import CliRunner
from model.test_themes import catalogue, served_theme

from leaf.cli import cli
from leaf.registry.storage import layer_metadata
from leaf.themes import cmd_list
from leaf.vendoring import cmd_init


def test_theme_selection_is_independent_of_content_packages_and_later_defaults(
    tmp_path,
):
    config = catalogue(tmp_path)
    choices = cmd_list()["themes"]
    assert [(item["name"], item["default"]) for item in choices] == [
        ("reading", False),
        ("editorial", True),
        ("dense", False),
    ]
    assert choices[2]["instructions"] == "Use dense for its distinctive presentation."
    page = tmp_path / "page"
    cmd_init(page)
    captured = layer_metadata(page)
    assert captured["theme"] == {"name": "editorial", "source": "default"}
    config.write_text('themes = ["dense"]\ndefault = "dense"\n')
    cmd_init(page)
    assert layer_metadata(page)["theme"] == captured["theme"]
    cmd_init(page, ("diagram",), theme="dense")
    replaced = layer_metadata(page)
    assert replaced["packages"] == ["diagram"]
    assert replaced["theme"] == {"name": "dense", "source": "explicit"}
    css = served_theme(page)
    assert "#553399" in css and "#814b07" not in css
    assert cmd_init(page, dry_run=True)["changed"] is False
    without_theme = CliRunner().invoke(cli, ["page", "init", str(page), "--no-theme"])
    assert without_theme.exit_code == 0, without_theme.output
    cmd_init(page)
    assert layer_metadata(page)["packages"] == ["diagram"]
    assert layer_metadata(page)["theme"] is None
    cmd_init(page, theme="dense")
    cleared = CliRunner().invoke(cli, ["page", "init", str(page), "--no-packages"])
    assert cleared.exit_code == 0, cleared.output
    cmd_init(page)
    assert layer_metadata(page)["packages"] == []
    assert layer_metadata(page)["theme"] == {"name": "dense", "source": "explicit"}
