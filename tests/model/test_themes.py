"""Personal theme choices become captured layers, independent of later preferences."""

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from interact_support import publish
from model_folds import leaf_page

from leaf.cli import cli
from leaf.exporting import cmd_export
from leaf.machine import package_store
from leaf.packages import cmd_package_install
from leaf.refusals import Refused
from leaf.registry.storage import layer_metadata
from leaf.themes import cmd_list
from leaf.vendoring import cmd_init


def catalogue(tmp_path, *, default="editorial"):
    """Two installed themes described by their own instructions, one personal default."""
    for name, color in (("editorial", "#814b07"), ("dense", "#553399")):
        source = tmp_path / name
        source.mkdir()
        (source / "theme.css").write_text(f":root {{ --accent: {color}; }}")
        (source / "instructions").mkdir()
        (source / "instructions/author.md").write_text(
            f"Use {name} for its distinctive presentation."
        )
        cmd_package_install(source)
    config = Path(os.environ["XDG_CONFIG_HOME"]) / "leaf/themes.toml"
    config.parent.mkdir(parents=True)
    config.write_text(f'themes = ["editorial", "dense"]\ndefault = "{default}"\n')
    return config


def test_an_installed_theme_keeps_the_files_its_sheet_imports(tmp_path):
    """A theme split into files with `@import` installs whole, so a page vendored
    from the installed copy carries the imported rules."""
    source = tmp_path / "split"
    (source / "styles").mkdir(parents=True)
    (source / "theme.css").write_text('@import "./styles/accent.css";\n')
    (source / "styles/accent.css").write_text(":root { --accent: #123456; }\n")
    cmd_package_install(source)
    config = Path(os.environ["XDG_CONFIG_HOME"]) / "leaf/themes.toml"
    config.parent.mkdir(parents=True)
    config.write_text('themes = ["split"]\n')
    page = tmp_path / "page"
    cmd_init(page, theme="split")
    assert "#123456" in (page / "theme.css").read_text()


def test_theme_selection_is_independent_of_content_packages_and_later_defaults(
    tmp_path,
):
    config = catalogue(tmp_path)
    choices = cmd_list()["themes"]
    assert [(item["name"], item["default"]) for item in choices] == [
        ("editorial", True),
        ("dense", False),
    ]
    assert choices[1]["instructions"] == "Use dense for its distinctive presentation."
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
    css = (page / "theme.css").read_text()
    assert "#553399" in css and "#814b07" not in css
    assert cmd_init(page, dry_run=True)["changed"] is False
    without_theme = CliRunner().invoke(cli, ["page", "init", str(page), "--no-theme"])
    assert without_theme.exit_code == 0, without_theme.output
    cmd_init(page)
    assert layer_metadata(page)["packages"] == ["diagram"]
    assert layer_metadata(page)["theme"] is None
    cleared = CliRunner().invoke(cli, ["page", "init", str(page), "--no-packages"])
    assert cleared.exit_code == 0, cleared.output
    cmd_init(page)
    assert layer_metadata(page)["packages"] == []
    assert layer_metadata(page)["theme"] is None


def test_missing_theme_refuses_revendoring_but_captured_page_exports(tmp_path):
    catalogue(tmp_path)
    page = tmp_path / "page"
    cmd_init(page)
    (page / "index.html").write_text(
        leaf_page("Captured theme", '<h1 id="title">Captured theme</h1>')
    )
    publish(page, "Captured appearance")
    captured = (page / "registry.json").read_bytes()
    (package_store() / "names/editorial").unlink()
    with pytest.raises(Refused, match="unknown package 'editorial'"):
        cmd_init(page)
    assert (page / "registry.json").read_bytes() == captured
    output = tmp_path / "export.html"
    cmd_export(page, output, None)
    assert "#814b07" in output.read_text()
    assert json.loads(captured)["$layer"]["theme"]["name"] == "editorial"


def test_an_explicit_theme_must_name_a_personal_choice_before_creating_a_page(tmp_path):
    catalogue(tmp_path)
    page = tmp_path / "page"
    refused = CliRunner().invoke(
        cli, ["page", "init", str(page), "--theme", "misspelled"]
    )
    assert refused.exit_code != 0
    assert "leaf theme list" in refused.output
    assert not page.exists()
