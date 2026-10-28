"""Theme choices become recorded selections, independent of later preferences."""

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from leaf.cli import cli
from leaf.machine import package_store
from leaf.packages import cmd_package_install
from leaf.refusals import Refused
from leaf.registry.storage import LAYER, layer_metadata, layer_record, selected
from leaf.schema import LAYER_FILE
from leaf.themes import cmd_list
from leaf.vendoring import cmd_init

NONE = {"name": "none", "source": "explicit"}


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


def served_theme(page: Path) -> str:
    """The theme sheet the layer `page` selects serves (`registry.storage.selected`)."""
    return selected(layer_record(page), page).files["/theme.css"].decode()


def test_an_installed_theme_keeps_the_files_its_sheet_imports(tmp_path):
    """A theme split into files with `@import` installs whole, so a page selecting
    the installed copy carries the imported rules, whether an imported file stands in
    a directory of its own or in one the package already ships."""
    source = tmp_path / "split"
    (source / "styles").mkdir(parents=True)
    (source / "widgets").mkdir()
    (source / "theme.css").write_text(
        '@import "./styles/accent.css";\n@import "./widgets/paper.css";\n'
    )
    (source / "styles/accent.css").write_text(":root { --accent: #123456; }\n")
    (source / "widgets/paper.css").write_text(":root { --paper: #fedcba; }\n")
    cmd_package_install(source)
    config = Path(os.environ["XDG_CONFIG_HOME"]) / "leaf/themes.toml"
    config.parent.mkdir(parents=True)
    config.write_text('themes = ["split"]\n')
    page = tmp_path / "page"
    cmd_init(page, theme="split")
    theme = served_theme(page)
    assert "#123456" in theme and "#fedcba" in theme


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
    assert layer_metadata(page)["theme"] == NONE
    cmd_init(page, theme="dense")
    cleared = CliRunner().invoke(cli, ["page", "init", str(page), "--no-packages"])
    assert cleared.exit_code == 0, cleared.output
    cmd_init(page)
    assert layer_metadata(page)["packages"] == []
    assert layer_metadata(page)["theme"] == {"name": "dense", "source": "explicit"}


def test_a_new_page_reads_in_leaf_s_look_unless_it_takes_none(tmp_path):
    """With no default of the user's, a new page takes the bundled reading theme, its
    idioms and element rules; a page that takes none composes neither, while the
    markup face Leaf's own surfaces wear stays in the core sheet, off until a theme or
    the page turns it on."""
    page = tmp_path / "page"
    cmd_init(page)
    assert layer_metadata(page)["theme"] == {"name": "reading", "source": "default"}
    assert ".callout" in selected(layer_record(page), page).registry
    assert "color-scheme: light dark;\n  --lf-reading-face: 1;" in served_theme(page)
    cmd_init(page, theme=False)
    assert layer_metadata(page)["theme"] == NONE
    assert ".callout" not in selected(layer_record(page), page).registry
    bare = served_theme(page)
    assert (
        ".callout" not in bare
        and "color-scheme: light dark;\n  --lf-reading" not in bare
    )
    assert "style(--lf-reading-face: 1)" in bare


def test_a_page_recording_no_theme_choice_reads_in_leaf_s_look(tmp_path):
    """A record that names no theme, as a page initialized before the reading look
    was a theme does, composes Leaf's default, and re-initializing keeps it there:
    only `--no-theme` records taking none."""
    page = tmp_path / "page"
    cmd_init(page)
    LAYER.write(page / LAYER_FILE, {**layer_record(page), "theme": None})
    assert ".callout" in selected(layer_record(page), page).registry
    cmd_init(page)
    assert ".callout" in selected(layer_record(page), page).registry


def test_a_project_package_restates_a_theme_s_idiom(tmp_path, monkeypatch):
    """The theme composes before the content packages, so a project package that
    restates one of its idioms replaces the entry and its rule follows the theme's."""
    project = tmp_path / "proj" / ".leaf"
    project.mkdir(parents=True)
    callout = {
        "description": "project callout",
        "x-example": '<aside class="callout">…</aside>',
    }
    (project / "registry.json").write_text(json.dumps({".callout": callout}))
    (project / "elements.css").write_text(".callout { background: teal; }\n")
    monkeypatch.chdir(project.parent)
    page = tmp_path / "page"
    cmd_init(page, ("./.leaf",))
    layer = selected(layer_record(page), page)
    assert layer.registry[".callout"] == callout
    sheet = layer.files["/theme.css"].decode()
    assert sheet.index(
        "background: var(--lf-ground);\n  padding: 12px 16px"
    ) < sheet.index("background: teal")


def test_none_names_no_theme_in_the_catalogue(tmp_path):
    config = Path(os.environ["XDG_CONFIG_HOME"]) / "leaf/themes.toml"
    config.parent.mkdir(parents=True)
    config.write_text('themes = ["none"]\n')
    with pytest.raises(Refused, match="means no theme"):
        cmd_list()


def test_missing_theme_refuses_revendoring_and_keeps_the_selection(tmp_path):
    catalogue(tmp_path)
    page = tmp_path / "page"
    cmd_init(page)
    recorded = (page / LAYER_FILE).read_bytes()
    (package_store() / "names/editorial").unlink()
    with pytest.raises(Refused, match="unknown package 'editorial'"):
        cmd_init(page)
    assert (page / LAYER_FILE).read_bytes() == recorded
    assert layer_metadata(page)["theme"]["name"] == "editorial"


def test_an_explicit_theme_must_name_a_personal_choice_before_creating_a_page(tmp_path):
    catalogue(tmp_path)
    page = tmp_path / "page"
    refused = CliRunner().invoke(
        cli, ["page", "init", str(page), "--theme", "misspelled"]
    )
    assert refused.exit_code != 0
    assert "leaf theme list" in refused.output
    assert not page.exists()
