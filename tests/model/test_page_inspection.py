"""Inspection attributes CSS and keeps rendered observations on their source basis."""

import json

from click.testing import CliRunner
from interact_support import write_revision
from model_folds import leaf_page

from leaf.base.files import list_revisions
from leaf.commands.cli import cli
from leaf.serving.page_inspection import cmd_inspect
from leaf.serving.user_views import observe_user_view
from model.test_user_views import report as browser_report


def test_inspection_attributes_nested_css_imports_widgets_and_sample_documents(
    page_dir,
):
    authored = page_dir / "page"
    authored.mkdir(exist_ok=True)
    (authored / "widgets").mkdir()
    shared = "p { color: red !important; & strong { color: blue; } }"
    sheet = '@import "./shared.css"; @media (width > 20em) { p { margin: 0; } }'
    (authored / "style.css").write_text(sheet)
    (authored / "shared.css").write_text(shared)
    unused = "p { padding: 999px; }"
    (authored / "unused.css").write_text(unused)
    download_script = "export const download = true;"
    (authored / "download.js").write_text(download_script)
    (authored / "widgets" / "lf-options.js").write_text(
        "export const styling = `p { color: blue }`;"
    )
    script = 'import "./shared.js"; export const label = "é";'
    shared_script = "export const shared = true;"
    (authored / "main.js").write_text(script)
    (authored / "shared.js").write_text(shared_script)
    inline_script = 'import "./page/main.js";'
    source = leaf_page(
        "Inspection",
        '<p id="intro" style="--label: &quot;é&quot;; color: green">Hi</p>\n'
        '<a download href="page/download.js">Download module</a>\n'
        '<template id="child" data-sample>\n'
        f'<script type="module">{inline_script}</script>\n'
        "<style>p { padding: 1px; }</style>\n"
        '<link rel="stylesheet" href="page/shared.css">\n'
        '<p id="child-p">Child</p></template>',
        head="<style>p { display: block; }</style>\n"
        '<script type="module" src="page/main.js"></script>\n'
        '<script type="application/json">{"not":"executable"}</script>\n'
        '<link rel="stylesheet" href="page/style.css">',
    )
    (page_dir / "index.html").write_text(source)
    before = list_revisions(page_dir)
    result = CliRunner().invoke(cli, ["page", "inspect", str(page_dir)])
    assert result.exit_code == 0, result.output
    reading = json.loads(result.output)
    assert list_revisions(page_dir) == before
    page = [item for item in reading["css"]["sources"] if item["owner"] == "page"]
    assert len(page) == 6
    # A revision holds every page file, so a sheet nothing links is listed, loaded by
    # no document.
    assert (
        next(item for item in page if item["path"] == "page/unused.css")["documents"]
        == []
    )
    imported = next(item for item in page if item["path"] == "page/shared.css")
    assert imported["documents"] == ["index.html", "index.html#child"]
    assert imported["rules"] == 2
    assert imported["declarations"] == 2
    assert imported["important"] == 1
    assert reading["css"]["page"] == {
        "bytes": sum(
            len(css.encode("utf-8"))
            for css in (
                shared,
                sheet,
                unused,
                "p { display: block; }",
                "p { padding: 1px; }",
                '--label: "é"; color: green',
            )
        ),
        "rules": 8,
        "declarations": 8,
        "inline_styles": 1,
        "important": 1,
    }
    child = next(
        item
        for item in page
        if item["kind"] == "style" and item["documents"] == ["index.html#child"]
    )
    assert (
        source.splitlines()[child["line"] - 1] == "<style>p { padding: 1px; }</style>"
    )
    assert reading["css"]["layer"]["bytes"] > 0
    assert reading["page_widgets"] == [
        {"tag": "lf-options", "path": "page/widgets/lf-options.js"}
    ]
    javascript = reading["javascript"]
    assert javascript["page"] == {
        "bytes": sum(
            len(text.encode("utf-8"))
            for text in (
                script,
                shared_script,
                inline_script,
                download_script,
                "export const styling = `p { color: blue }`;",
            )
        ),
        "files": 4,
        "inline_scripts": 1,
    }


def test_inspection_distinguishes_working_css_from_the_observed_revision(page_dir):
    authored = page_dir / "page"
    authored.mkdir(exist_ok=True)
    css = authored / "style.css"
    css.write_text("p { color: red; }")
    source = leaf_page(
        "Inspection",
        '<p id="p">Text</p>',
        head='<link rel="stylesheet" href="page/style.css">',
    )
    (page_dir / "index.html").write_text(source)
    write_revision(page_dir, 1, source.encode())
    observe_user_view(page_dir, browser_report())
    original = cmd_inspect(page_dir, 1)
    assert original["views"]["sessions"][0]["matches_source"] is True
    css.write_text("p { color: red; margin: 0; }")
    current = cmd_inspect(page_dir)
    assert current["basis"]["revision"] is None
    assert current["basis"]["source_digest"] == original["basis"]["source_digest"]
    assert current["basis"]["artifact_digest"] != original["basis"]["artifact_digest"]
    view = current["views"]["sessions"][0]
    assert view["matches_source"] is False
    assert view["checks"]["matches_source"] is False
    assert view["checks"]["viewport"] == {"width": 900, "height": 700}
    assert cmd_inspect(page_dir, 1)["css"] == original["css"]
    result = CliRunner().invoke(
        cli, ["page", "inspect", str(page_dir), "--compare-to", "1"]
    )
    assert result.exit_code == 0, result.output
    comparison = json.loads(result.output)["comparison"]
    assert comparison["basis"] == original["basis"]
    assert comparison["css"]["page"]["declarations"] == 1
    assert comparison["css"]["layer"]["declarations"] == 0
    assert len(comparison["sources"]) == 1
    changed = comparison["sources"][0]
    assert changed["path"] == "page/style.css"
    assert changed["status"] == "changed"
    assert changed["css_delta"]["declarations"] == 1
    assert changed["after"]["bytes"] - changed["before"]["bytes"] == len("margin: 0; ")
    assert cmd_inspect(page_dir, 1, compare_to=1)["comparison"]["sources"] == []
    result = CliRunner().invoke(
        cli, ["page", "inspect", str(page_dir), "--revision", "20"]
    )
    assert result.exit_code == 1
    assert "unknown revision r20" in result.output


def test_inspection_counts_prose_words_apart_from_collapsed_ones(page_dir):
    def words(n, first="w"):
        return " ".join(f"{first}{i}" for i in range(n))

    plain = leaf_page("Words", f'<p id="p">{words(14)}</p>')
    (page_dir / "index.html").write_text(plain)
    write_revision(page_dir, 1, plain.encode())
    (page_dir / "index.html").write_text(
        leaf_page(
            "Words",
            f'<p id="p">{words(14)}</p>\n<p id="q">{words(12, "q")}</p>\n'
            '<table id="t"><tr><th>Key</th><th>Meaning</th></tr>'
            f"<tr><td>gap</td><td>{words(13, 'c')}</td></tr></table>\n"
            f"<pre>{words(20, 'x')}</pre>\n"
            f'<p id="r">{words(12, "r")}</p>\n'
            f'<details id="source"><summary>The rule</summary>'
            f"<blockquote>{words(15, 's')}</blockquote></details>\n"
            f'<p id="later" hidden>{words(12, "h")}</p>',
        )
    )
    report = cmd_inspect(page_dir, compare_to=1)
    # The table's sentence-long cell counts as prose; its short cells and the closed
    # disclosure's summary are scanned; the code counts nothing.
    assert report["words"]["shown"] == 14 + 12 + 13 + 12
    assert report["comparison"]["words"] == {
        "shown": 12 + 13 + 12,
        "collapsed": 15 + 12,
        "scanned": len("Key Meaning gap The rule".split()),
    }


def test_inspection_does_not_report_missing_styles_as_zero(page_dir):
    (page_dir / "index.html").write_text(
        leaf_page(
            "Partial",
            '<p id="p">Text</p>',
            head="<style>p { color: red; broken; margin: 0; }</style>",
        )
    )
    partial = cmd_inspect(page_dir)
    style = next(
        source for source in partial["css"]["sources"] if source["kind"] == "style"
    )
    assert style["syntax_errors"][0]["code"] == "css-dropped"
    assert partial["css"]["coverage"][-1].startswith("CSS syntax errors")
    (page_dir / "index.html").write_text(
        leaf_page(
            "Missing",
            '<p id="p">Text</p>',
            head='<link rel="stylesheet" href="page/missing.css">',
        )
    )
    result = CliRunner().invoke(cli, ["page", "inspect", str(page_dir)])
    assert result.exit_code != 0
    assert "missing.css" in result.output
