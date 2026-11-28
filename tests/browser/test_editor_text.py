"""What an editor of a text holds for the widgets beside it, the same for every widget
that produces the `text-document` contract from what the user types, a file's editor
and a draft alike: the text as the user has it, saved or not, which moves once their
typing rests rather than at each key, so a diff bound to the editor follows the
typing."""

from datetime import UTC, datetime, timedelta

import pytest
from playwright.sync_api import Page, expect
from render_cases_interaction import live_url
from render_harness import holding, leaf_page, open_page, press_draft_control

from leaf.records import page_data as page_data_model
from leaf.source.file_bindings import bind_file

# The diff draws a comparison after awaits the input watch doesn't follow, so it would
# report each redraw the typing causes as a move without input, as for every diff in
# `widgets/test_diffs.py`.
pytestmark = pytest.mark.shifts_unsurveyed

EARLIER = "".join(f"Line {number}.\n" for number in range(1, 41))
CURRENT = EARLIER.replace("Line 5.", "Line five.")

# The editor's `text` output, as a reader beside it reads it.
TEXT = "() => document.getElementById('notes').text"


def _file_edit(page: Page):
    page.locator("#notes").get_by_role("textbox", name="File contents").click()
    page.keyboard.press("ControlOrMeta+End")


EDITORS = {
    "file": (
        '<lf-file-editor id="notes" binding="notes"></lf-file-editor>',
        _file_edit,
    ),
    "draft": (
        f'<lf-draft id="notes"><pre>\n{CURRENT}</pre></lf-draft>',
        lambda page: press_draft_control(page, "edit", "notes"),
    ),
}


@pytest.mark.parametrize("kind", EDITORS)
def test_an_editor_s_text_follows_typing_once_it_rests(browser, serve, tmp_path, kind):
    """The output holds what the user typed only once their typing has rested half a
    second, so a diff bound to it redraws once a pause rather than at each key. It
    holds the words before they are kept: a file's while its save is still on the way,
    and a draft's while its editor is open and the words unsent."""
    markup, edit = EDITORS[kind]
    url = serve(
        leaf_page(
            "Notes",
            f'<h1>Notes</h1>{markup}<lf-diff id="changes" for="notes" '
            'before="earlier"></lf-diff>',
        )
    )
    if kind == "file":
        file = tmp_path / "notes.md"
        file.write_text(CURRENT)
        bind_file(serve.page_dir, "notes", file)
    page_data_model.cmd_data_set(
        serve.page_dir, "earlier", {"name": "notes.md", "text": EARLIER}
    )
    page = open_page(browser, live_url(url))
    rows = page.locator("#changes .lf-diff-line")
    typed = rows.filter(has_text="typed")
    expect(rows.filter(has_text="Line five.")).to_have_count(1)
    expect(typed).to_have_count(0)
    saves = []

    def hold(route):
        if route.request.method == "POST":
            saves.append(route)
        else:
            route.continue_()

    page.route("**/api/files/notes", hold)

    edit(page)
    # From here only the test moves the page's clock, so the rest is the test's to end.
    page.clock.install()
    page.clock.pause_at(datetime.now(UTC) + timedelta(seconds=1))
    page.keyboard.type("typed")
    page.clock.run_for(499)
    assert "typed" not in page.evaluate(TEXT)["text"]
    page.clock.run_for(1)
    assert "typed" in page.evaluate(TEXT)["text"]
    page.clock.resume()
    expect(typed).to_have_count(1)
    if kind == "file":
        holding(page, saves, 1, "the save of the typing")
        assert file.read_text() == CURRENT
        saves[0].continue_()
    else:
        expect(page.locator("#notes leaf-text")).to_be_visible()
