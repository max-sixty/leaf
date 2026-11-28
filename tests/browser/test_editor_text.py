"""What an editor of a text holds for the widgets beside it, the same for every widget
that produces the `text-document` contract from what the user types, a file's editor
and a draft alike: the text as the user has it, saved or not, which moves once their
typing rests rather than at each key, and `--replace` naming the value it holds, which
it takes as one edit of the user's that their undo takes back. A diff bound to the
editor reads the text and sends the request as its Revert."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from playwright.sync_api import Page, expect
from render_cases_interaction import live_url
from render_harness import leaf_page, open_page, press_draft_control, undo

from leaf.records import page_data as page_data_model
from leaf.source.file_bindings import bind_file

# The diff draws a comparison after awaits the input watch doesn't follow, so it would
# report each redraw the typing, a Revert or an undo causes as a move without input, as
# for every diff in `widgets/test_diffs.py`.
pytestmark = pytest.mark.shifts_unsurveyed

EARLIER = "".join(f"Line {number}.\n" for number in range(1, 41))
# Two changes far enough apart to make two hunks, as is the typing at the end.
CURRENT = EARLIER.replace("Line 5.", "Line five.").replace("Line 30.", "Line thirty.")

# The editor's `text` output, as a reader beside it reads it.
TEXT = "() => document.getElementById('notes').text"

# A `--replace` of the first line as a sender makes it, naming `revision`; whether it
# was taken, and whether the output moved by the next frame.
ASK = """async (revision) => {
  const editor = document.getElementById("notes");
  const held = editor.text;
  const taken = editor.dispatchEvent(
    new CommandEvent("command", {
      command: "--replace",
      source: Object.assign(document.createElement("button"), {
        value: JSON.stringify({
          text: held.text.replace("Line 1.", "Line one."),
          revision,
        }),
        textContent: "Asked",
      }),
      cancelable: true,
    }),
  );
  await new Promise((resolve) => requestAnimationFrame(resolve));
  return { taken, moved: editor.text !== held };
}"""


@dataclass(frozen=True)
class Editor:
    markup: str
    # Put the caret at the end of the text, ready to type.
    edit: Callable[[Page], None]
    # Finish editing, where the editor takes no replacement while open.
    close: Callable[[Page], None]
    # Take back the editor's last edit where the user stands after a Revert.
    undo: Callable[[Page], None]


def _file_edit(page: Page):
    page.locator("#notes").get_by_role("textbox", name="File contents").click()
    page.keyboard.press("ControlOrMeta+End")


EDITORS = {
    "file": Editor(
        markup='<lf-file-editor id="notes" binding="notes"></lf-file-editor>',
        edit=_file_edit,
        close=lambda page: None,
        # The Revert left the user in the file, whose own history takes it back.
        undo=lambda page: page.keyboard.press("ControlOrMeta+z"),
    ),
    "draft": Editor(
        markup=f'<lf-draft id="notes"><pre>\n{CURRENT}</pre></lf-draft>',
        edit=lambda page: press_draft_control(page, "edit", "notes"),
        close=lambda page: page.keyboard.press("ControlOrMeta+Enter"),
        # The Revert is an edit in the page's log, which the page's Undo takes back.
        undo=undo,
    ),
}


@pytest.mark.parametrize("kind", EDITORS)
def test_an_editor_s_text_follows_typing_once_it_rests_and_takes_a_revert(
    browser, serve, tmp_path, kind
):
    """The output holds what the user typed only once their typing has rested half a
    second, so a diff bound to it redraws once a pause rather than at each key, and it
    holds a draft's unsent words as a file's unsaved ones. A Revert on one hunk is
    taken as one edit, moving the output in the task that takes it, which leaves the
    user's other changes and their typing alone and which one undo takes back. A
    request naming a value the output no longer holds is refused, and a draft whose
    editor is open offers its diff no Revert at all, since its words can't be folded
    around one."""
    editor = EDITORS[kind]
    url = serve(
        leaf_page(
            "Notes",
            f'<h1>Notes</h1>{editor.markup}<lf-diff id="changes" for="notes" '
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
    reverts = page.locator("#changes .lf-diff-revert")
    expect(reverts).to_have_count(2)

    editor.edit(page)
    # From here only the test moves the page's clock, so the rest is the test's to end.
    page.clock.install()
    page.clock.pause_at(datetime.now(UTC) + timedelta(seconds=1))
    page.keyboard.type("typed")
    page.clock.run_for(499)
    assert "typed" not in page.evaluate(TEXT)["text"]
    page.clock.run_for(1)
    assert "typed" in page.evaluate(TEXT)["text"]
    page.clock.resume()
    if kind == "draft":
        assert "revision" not in page.evaluate(TEXT)
        expect(reverts).to_have_count(0)
    editor.close(page)
    expect(reverts).to_have_count(3)
    typed = page.evaluate(TEXT)["text"]

    reverts.nth(1).click()
    # The output holds the Revert at once, and a draft's holds no revision until the
    # server has answered its edit.
    page.wait_for_function(
        "() => document.getElementById('notes').text.text.includes('Line 30.\\n')"
        " && document.getElementById('notes').text.revision"
    )
    held = page.evaluate(TEXT)
    assert held["text"] == typed.replace("Line thirty.", "Line 30.")
    expect(reverts).to_have_count(2)

    editor.undo(page)
    page.wait_for_function(
        "() => document.getElementById('notes').text.text.includes('Line thirty.')"
    )
    assert page.evaluate(TEXT)["text"] == typed
    expect(reverts).to_have_count(3)
    assert page.evaluate(ASK, held["revision"]) == {"taken": False, "moved": False}
    assert page.evaluate(ASK, page.evaluate(TEXT)["revision"]) == {
        "taken": True,
        "moved": True,
    }
