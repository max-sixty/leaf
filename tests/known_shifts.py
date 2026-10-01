"""The shifts without input that tests' pages still make, each a defect waiting on its
fix (`shift_watch.js`, `render_harness.clean_browser`).

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


def watches_shifts(test):
    """Whether a pytest node `test`'s pages watch for shifts at all.

    The nightly-marked tests do not yet: their pages make hundreds of shifts, most of
    them widgets that upgrade after the authored document has painted and move what
    follows them after presentation, and a nightly run on Linux finds more than a run
    here does. They watch again, with the entries a fresh survey finds, once that
    upgrade is fixed."""
    return test.get_closest_marker("nightly") is None


def known(test, problem):
    """Whether a browser `problem` from a pytest node `test` is its known shift."""
    region = KNOWN_UNASKED.get(test.path.name, {}).get(test.originalname)
    moved, unasked, _ = problem.partition(" moved without input")
    return bool(region and unasked and re.search(region, moved))
