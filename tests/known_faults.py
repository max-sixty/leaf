"""The faults the browser fixture's watches report that tests' pages still make, each a
defect waiting on its fix (`render_harness.clean_browser`): shifts without input
(`shift_watch.js`) and typed words lost without a key or press (`words_watch.js`).

`KNOWN_UNASKED` names each test by file and function, whatever its parameters, with a
pattern for the region its known shift moves. A report from that test that names a node
in that region is kept, and any other shift fails it. Chrome names only the five nodes a
frame moved most, which differ between runs and machines, so a pattern names the
region rather than the node. Fixing a defect deletes its entry. A test joins only as a
defect to fix, never as behavior to keep (`tests/AGENTS.md`, "Consume a browser error
where it is caused")."""

import re

KNOWN_UNASKED = {
    "test_chrome_contracts.py": {
        # The shortcut line's More as its hints change.
        "test_incoming_reply_follows_a_selected_thread_before_later_cards": r"lf-shortcut",
        "test_a_repaint_unsettles_the_rendering_until_it_lands": r"lf-shortcut",
    },
    "test_render_application_boundary.py": {
        # A live page's paragraphs and the margin beside them as a package's Ask and a
        # fresh document draw after presentation.
        "test_current_readiness_releases_a_connected_page_widget": (
            r"lf-ask#package-ask|p#live-(lead|tail)-|lf-margin-cluster"
        ),
    },
}


# Typed words a page still takes off the screen without the user putting them away, by
# test, with a pattern for the words. A thread another actor settles takes its reply box,
# words and all, though the draft is kept: the box should stay with the words in it until
# the user sends or discards them.
KNOWN_LOSSES = {
    "test_render_pages.py": {
        "test_a_failed_resolution_restores_a_focused_inline_reply": (
            r"keep this inline reply"
        ),
    },
    "test_render_threads.py": {
        "test_a_thread_resolved_while_its_reply_is_written_keeps_the_user_on_it": (
            r"Half a thought"
        ),
        "test_an_external_resolution_leaves_the_user_on_the_thread_list": (
            r"This draft survives the other actor settling its thread"
        ),
    },
}


def watches_shifts(test):
    """Whether a pytest node `test`'s pages watch for shifts at all.

    The nightly-marked tests do not yet: their pages make hundreds of shifts, most of
    them widgets that upgrade after the authored document has painted and move what
    follows them after presentation, and a nightly run on Linux finds more than a run
    here does. They watch again, with the entries a fresh survey finds, once that
    upgrade is fixed."""
    return test.get_closest_marker("nightly") is None


def known(test, problem):
    """Whether a browser `problem` from a pytest node `test` is its known shift or loss."""
    region = KNOWN_UNASKED.get(test.path.name, {}).get(test.originalname)
    moved, unasked, _ = problem.partition(" moved without input")
    if region and unasked and re.search(region, moved):
        return True
    words = KNOWN_LOSSES.get(test.path.name, {}).get(test.originalname)
    _, lost, what = problem.partition("typed words left the screen")
    return bool(words and lost and re.search(words, what))
