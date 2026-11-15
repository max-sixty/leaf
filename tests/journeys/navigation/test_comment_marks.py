"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.navigation.test_comment_marks import _ring_round
from interact_support import append_carried_log_record
from render_cases_navigation import NOTED_PAGE
from render_harness import comment_note, expect_comment_notes, open_page

pytestmark = pytest.mark.shifts_unsurveyed


def test_notes_of_one_passage_across_two_blocks_each_follow_their_block_redrawn(
    browser, serve
):
    """A passage across two blocks gives each its note, both entering the same thread.
    When the page draws both blocks anew in one task, each note goes to its own block's
    copy: none is left on the shelf named by nothing, and the user on the first block's
    note stays on it, ringed round the first block's copy."""
    url = serve(NOTED_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Crosses the boundary.",
            "anchor": {"quote": "to land in it. A short second"},
        },
    )
    page = open_page(browser, url)
    expect_comment_notes(page, "#p1", 1)
    expect_comment_notes(page, "#p2", 1)
    note = comment_note(page, "#p1")
    note.evaluate("note => { window.__lfNote = note; note.focus(); }")
    page.evaluate(
        """() => {
          for (const id of ["p1", "p2"]) {
            const block = document.getElementById(id);
            const copy = block.cloneNode(true);
            copy.dataset.redrawn = "";
            // Left behind, so the ring on the copy is the runtime's doing.
            copy.removeAttribute("data-lf-proxied");
            block.replaceWith(copy);
          }
        }"""
    )
    expect_comment_notes(page, "#p1[data-redrawn]", 1)
    expect_comment_notes(page, "#p2[data-redrawn]", 1)
    assert page.evaluate(
        """() => [...document.querySelectorAll('.lf-mark-note')].map((note) =>
          [...document.querySelectorAll('[aria-details]')].filter(
            (block) => block.isConnected && block.ariaDetailsElements?.includes(note),
          ).map((block) => block.id),
        )"""
    ) == [["p1"], ["p2"]]
    assert page.evaluate(
        """() => document.activeElement === window.__lfNote &&
          document.getElementById('p1').ariaDetailsElements.includes(window.__lfNote)"""
    )
    assert _ring_round(page, "#p1[data-redrawn]")
