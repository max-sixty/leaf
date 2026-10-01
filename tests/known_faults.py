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
    "test_render_read_state.py": {
        # The margin marker an arriving thread or a reopening brings, which the margin
        # projection inserts unplaced and the layout places a frame later. On Linux's
        # headless shell the unplaced row stands at the window's origin, and its move
        # into the rail reads as a shift. In the second, also the shortcut line's More as
        # its hints change, where the test focuses the notice by script after a reading
        # landed.
        "test_a_reopening_in_a_page_seat_waits_where_reopen_stood": r"lf-margin-",
        "test_a_thread_the_agent_starts_in_a_page_seat_waits_in_the_row_it_would_follow": (
            r"lf-margin-|lf-shortcut"
        ),
    },
    "test_render_application_boundary.py": {
        # The open panel card's messages, 12px up, as the answer to the user's pick in it
        # lands: the card's summary drops the line saying "On you to answer". Chrome no
        # longer names the card once it is redrawn ("a node since removed").
        "test_packages_and_panel_share_threads_through_gestures_and_authored_content": (
            r"a node since removed"
        ),
        # The shortcut line's More as its hints change, when the test focuses the subject
        # by script after news has landed.
        "test_package_thread_mirrors_share_core_conversation_without_claiming_placement": (
            r"lf-shortcut"
        ),
        # A live page's paragraphs and the margin beside them as a package's Ask and a
        # fresh document draw after presentation.
        "test_current_readiness_releases_a_connected_page_widget": (
            r"lf-ask#package-ask|p#live-(lead|tail)-|lf-margin-cluster"
        ),
        # The shortcut line, as its hints change when the test takes the focused widget
        # out by script after news has landed, and a margin cluster coming into view from
        # where it waits off the page, as news lands after a choice on the page's own
        # widget. Chrome no longer names the cluster once it is replaced ("a node since
        # removed").
        "test_page_owned_registry_and_widget_use_the_captured_public_api": (
            r"lf-shortcut|lf-margin-cluster|a node since removed"
        ),
        # As the answer to the user's pick lands: the shortcut line's More, as the hints
        # change, and the Ask's margin cluster, coming into view from where it waits off
        # the page.
        "test_admission_holds_approval_until_the_answer_is_in_the_log": (
            r"lf-shortcut-more|lf-margin-cluster"
        ),
        # A margin cluster coming into view from where it waits off the page, as news
        # lands.
        "test_a_settled_delivery_activates_one_fresh_document_with_continuity": (
            r"lf-margin-cluster"
        ),
    },
    "test_render_send_placement.py": {
        # The shortcut line's More as its hints change when the answer to the send lands,
        # where load puts that answer past the press's own frames.
        "test_where_a_comment_stands_before_and_after_send": r"lf-shortcut",
    },
    "test_website_server.py": {
        # The panel's later cards rising, and what they hold coming into view, as a card
        # whose thread news resolved folds away under the Open filter: the user's next
        # comment's card stands below the folding one, and the fold's frames after the
        # comment's answer lands are news.
        "test_a_website_turn_posts_its_answer_when_the_move_is_settled_first": (
            r"lf-thread-compact|lf-msg|lf-action-icon|lf-resolve"
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

    Ordinary tests watch by default. A surveyed nightly test opts in with
    `watch_shifts`, independently of when it runs. The remaining nightly tests await
    a fresh survey after the widget prepaint fixes; the earlier survey found hundreds
    of shifts and more failures on Linux than on macOS. This selection does not lift
    the watcher's separate first-presentation exemption (`shift_watch.js`)."""
    return (
        test.get_closest_marker("nightly") is None
        or test.get_closest_marker("watch_shifts") is not None
    )


def known(test, problem):
    """Whether a browser `problem` from a pytest node `test` is its known shift or loss."""
    region = KNOWN_UNASKED.get(test.path.name, {}).get(test.originalname)
    moved, unasked, _ = problem.partition(" moved without input")
    # Chrome can report a card and its children as separate sources of one layout
    # shift. The child report still names the card among that frame's sources.
    frame = problem.partition("; the same frame moved ")[2]
    if region and unasked and re.search(region, f"{moved}, {frame}"):
        return True
    words = KNOWN_LOSSES.get(test.path.name, {}).get(test.originalname)
    _, lost, what = problem.partition("typed words left the screen")
    return bool(words and lost and re.search(words, what))
