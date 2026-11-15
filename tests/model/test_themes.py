"""Theme choices become recorded selections, independent of later preferences."""

import json
import os
from pathlib import Path

from leaf.packages import cmd_package_install
from leaf.registry.storage import layer_metadata, layer_record, selected
from leaf.vendoring import cmd_init


def catalogue(tmp_path, *, default="editorial"):
    """Two installed themes described by their own instructions, one personal default."""
    for name, color in (("editorial", "#814b07"), ("dense", "#553399")):
        source = tmp_path / name
        source.mkdir()
        (source / "overrides.css").write_text(f":root {{ --lf-accent: {color}; }}")
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
    layer_2 = layer_record(page)
    assert layer_2 is not None
    return selected(layer_2, page).files["/theme.css"].decode()


def test_an_installed_theme_keeps_the_files_its_sheet_imports(tmp_path):
    """A theme split into files with `@import` installs whole, so a page selecting
    the installed copy carries the imported rules, whether an imported file stands in
    a directory of its own or in one the package already ships."""
    source = tmp_path / "split"
    (source / "styles").mkdir(parents=True)
    (source / "widgets").mkdir()
    (source / "overrides.css").write_text(
        '@import "./styles/accent.css";\n@import "./widgets/paper.css";\n'
    )
    (source / "styles/accent.css").write_text(":root { --lf-accent: #123456; }\n")
    (source / "widgets/paper.css").write_text(":root { --lf-paper: #fedcba; }\n")
    cmd_package_install(source)
    config = Path(os.environ["XDG_CONFIG_HOME"]) / "leaf/themes.toml"
    config.parent.mkdir(parents=True)
    config.write_text('themes = ["split"]\n')
    page = tmp_path / "page"
    cmd_init(page, theme="split")
    theme = served_theme(page)
    assert "#123456" in theme and "#fedcba" in theme


def test_a_new_page_reads_in_leaf_s_look_unless_it_takes_none(tmp_path):
    """With no default of the user's, a new page takes the bundled reading theme, its
    idioms and element rules; a page that takes none composes neither, while the
    markup face Leaf's own surfaces wear stays in the core sheet, off until a theme or
    the page turns it on."""
    page = tmp_path / "page"
    cmd_init(page)
    assert layer_metadata(page)["theme"] == {"name": "reading", "source": "default"}
    layer_3 = layer_record(page)
    assert layer_3 is not None
    assert ".callout" in selected(layer_3, page).vocabulary.registry
    assert "color-scheme: light dark;\n  --lf-reading-face: 1;" in served_theme(page)
    cmd_init(page, theme=False)
    assert layer_metadata(page)["theme"] is None
    layer_4 = layer_record(page)
    assert layer_4 is not None
    assert ".callout" not in selected(layer_4, page).vocabulary.registry
    bare = served_theme(page)
    assert (
        ".callout" not in bare
        and "color-scheme: light dark;\n  --lf-reading" not in bare
    )
    assert "style(--lf-reading-face: 1)" in bare


def test_a_personal_theme_builds_on_the_reading_look(tmp_path):
    """A personal theme composes after `reading`, so one that states only an accent
    keeps the look's face and idioms, and its own declaration follows the look's."""
    catalogue(tmp_path)
    page = tmp_path / "page"
    cmd_init(page, theme="dense")
    record = layer_record(page)
    assert record is not None
    assert record["theme"] == {"name": "dense", "source": "explicit"}
    layer = selected(record, page)
    assert ".callout" in layer.vocabulary.registry
    sheet = layer.files["/theme.css"].decode()
    assert sheet.index("--lf-reading-face: 1;") < sheet.index("--lf-accent: #553399")


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
    (project / "defaults.css").write_text(".callout { background: teal; }\n")
    monkeypatch.chdir(project.parent)
    page = tmp_path / "page"
    cmd_init(page, ("./.leaf",))
    layer_5 = layer_record(page)
    assert layer_5 is not None
    layer = selected(layer_5, page)
    assert layer.vocabulary.registry[".callout"] == callout
    sheet = layer.files["/theme.css"].decode()
    assert sheet.index(
        "background: var(--lf-ground);\n  padding: 12px 16px"
    ) < sheet.index("background: teal")
