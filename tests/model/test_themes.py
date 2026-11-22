"""Theme choices become recorded selections, independent of later preferences."""

import json
import os
from pathlib import Path

import pytest

from leaf.packages import cmd_package_install, package_layer_inputs
from leaf.refusals import Refused
from leaf.registry.storage import layer_metadata, layer_record, selected
from leaf.themes import with_theme
from leaf.vendoring import cmd_init

# The declaration that turns the reading look on, as the served sheet holds it.
READING_ROOT = "color-scheme: light dark;\n  --lf-reading-face: 1;"


def theme_package(source: Path, css: str, base: str | None = None) -> Path:
    """A theme package at `source` whose overrides.css holds `css`, building on the
    theme `base` names, or standing alone."""
    source.mkdir()
    (source / "overrides.css").write_text(css)
    if base is not None:
        (source / "registry.json").write_text(json.dumps({"$theme": {"base": base}}))
    return source


def catalogue(tmp_path, *, default="editorial"):
    """Two installed themes described by their own instructions, one personal default:
    `editorial` builds on `reading`, and `dense` stands alone."""
    for name, color, base in (
        ("editorial", "#814b07", "reading"),
        ("dense", "#553399", None),
    ):
        source = theme_package(
            tmp_path / name, f":root {{ --lf-accent: {color}; }}", base
        )
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
    """With no default of the user's, a new page takes the bundled reading theme; a
    page that takes none composes no theme, while the markup face Leaf's own surfaces
    wear stays in the core sheet, off until a theme or the page turns it on. Either
    way the page's markup takes Leaf's idioms, which are the kernel's."""
    page = tmp_path / "page"
    cmd_init(page)
    assert layer_metadata(page)["theme"] == {"name": "reading", "source": "default"}
    layer_3 = layer_record(page)
    assert layer_3 is not None
    assert ".lf-callout" in selected(layer_3, page).vocabulary.registry
    assert READING_ROOT in served_theme(page)
    cmd_init(page, theme=False)
    assert layer_metadata(page)["theme"] is None
    layer_4 = layer_record(page)
    assert layer_4 is not None
    assert ".lf-callout" in selected(layer_4, page).vocabulary.registry
    bare = served_theme(page)
    assert READING_ROOT not in bare
    assert ".lf-callout {" in bare and "style(--lf-reading-face: 1)" in bare


def test_a_theme_stands_alone_or_builds_on_the_base_it_names(tmp_path):
    """A personal theme composes after the base it names, so one that wants `reading`
    with another accent states only the accent and keeps the look, its declaration
    following the look's. A theme that names none composes without `reading`. `leaf
    package check` composes a theme over its base as a page taking it does."""
    catalogue(tmp_path)
    assert with_theme(("diagram",), {"name": "editorial"}) == (
        "reading",
        "editorial",
        "diagram",
    )
    assert with_theme(("diagram",), {"name": "dense"}) == ("dense", "diagram")
    page = tmp_path / "page"
    cmd_init(page, theme="editorial")
    sheet = served_theme(page)
    assert sheet.index(READING_ROOT) < sheet.index("--lf-accent: #814b07")
    cmd_init(page, theme="dense")
    record = layer_record(page)
    assert record is not None
    assert record["theme"] == {"name": "dense", "source": "explicit"}
    layer = selected(record, page)
    sheet = layer.files["/theme.css"].decode()
    assert READING_ROOT not in sheet and "--lf-accent: #553399" in sheet
    assert ".lf-callout" in layer.vocabulary.registry
    on_dense = theme_package(tmp_path / "on-dense", ":root { --lf-r: 0; }", "dense")
    assert [root.name for root in package_layer_inputs(on_dense)][-2:] == [
        "dense",
        "on-dense",
    ]
    assert "reading" not in [root.name for root in package_layer_inputs(on_dense)]


def test_a_theme_s_bases_must_be_installed_and_lead_nowhere_back(tmp_path):
    """A base the machine lacks, bases that name each other, or a `$theme` of another
    shape refuse to compose, naming the themes, rather than composing without the
    base. Installing a theme composes it as a page taking it would, so a missing base
    refuses the install."""
    orphan = theme_package(tmp_path / "orphan", "", "absent")
    with pytest.raises(
        Refused, match="'orphan' builds on theme 'absent', which is not"
    ):
        cmd_package_install(orphan)
    (tmp_path / "first").mkdir()
    cmd_package_install(theme_package(tmp_path / "first/loop-a", ""))
    cmd_package_install(theme_package(tmp_path / "loop-b", "", "loop-a"))
    cmd_package_install(theme_package(tmp_path / "loop-a", "", "loop-b"))
    with pytest.raises(
        Refused, match="build on each other: loop-b -> loop-a -> loop-b"
    ):
        with_theme((), {"name": "loop-a"})
    shapeless = theme_package(tmp_path / "shapeless", "", "reading")
    (shapeless / "registry.json").write_text(json.dumps({"$theme": {"on": "reading"}}))
    with pytest.raises(
        Refused, match=r"\$theme: Additional properties are not allowed"
    ):
        package_layer_inputs(shapeless)


def test_a_project_package_restates_a_kernel_idiom(tmp_path, monkeypatch):
    """The kernel's idioms compose before every package, so a project package that
    restates one replaces the entry and its rule follows the kernel's."""
    project = tmp_path / "proj" / ".leaf"
    project.mkdir(parents=True)
    callout = {
        "description": "project callout",
        "example": '<aside class="lf-callout">…</aside>',
    }
    (project / "registry.json").write_text(json.dumps({".lf-callout": callout}))
    (project / "defaults.css").write_text(".lf-callout { background: teal; }\n")
    monkeypatch.chdir(project.parent)
    page = tmp_path / "page"
    cmd_init(page, ("./.leaf",))
    layer_5 = layer_record(page)
    assert layer_5 is not None
    layer = selected(layer_5, page)
    assert layer.vocabulary.registry[".lf-callout"] == callout
    sheet = layer.files["/theme.css"].decode()
    assert sheet.index(
        "background: var(--lf-ground);\n  padding: 12px 16px"
    ) < sheet.index("background: teal")
