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
        # A node that moves 12px up and is gone before Chrome names it, where the answer
        # to opening a thread lands while the opened card still renders: with the answer
        # held back, nothing moves.
        "test_packages_and_panel_share_threads_through_gestures_and_authored_content": (
            r"a node since removed"
        ),
        # The second mirror's reply box, 60px down, as the answer to a reply sent from
        # the first lands. Chrome no longer names it once the second mirror's filter
        # takes the thread away ("a node since removed").
        "test_package_thread_mirrors_share_core_conversation_without_claiming_placement": (
            r"lf-compose-field|a node since removed"
        ),
        # A live page's paragraphs and the margin beside them as a package's Ask and a
        # fresh document draw after presentation.
        "test_current_readiness_releases_a_connected_page_widget": (
            r"lf-ask#package-ask|p#live-(lead|tail)-|lf-margin-cluster"
        ),
        # A live page's Ask and the paragraphs after it, 39px up, the shortcut line and a
        # margin cluster coming into view from where it waits off the page, as news lands
        # after a choice on the page's own widget. Chrome no longer names the cluster
        # once it is replaced ("a node since removed").
        "test_page_owned_registry_and_widget_use_the_captured_public_api": (
            r"lf-ask#package-ask|p#live-(lead|tail)-|lf-shortcut|lf-margin-cluster"
            r"|a node since removed"
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
        # The second package filter's field and list, 74px up, as the answer to the
        # user's new thread lands; with the answer held back, they move when it lands.
        "test_package_thread_widgets_keep_local_filters_and_independent_subscriptions": (
            r"lf-thread-filter#second"
        ),
        # The user's message in the open panel's card, 28px up, as the answer to a
        # package's thread action lands.
        "test_package_thread_actions_share_core_admission_and_current_availability": (
            r"div\.lf-msg"
        ),
    },
    "test_website_server.py": {
        # The panel's later cards rising, and what they hold coming into view, as a
        # card folds away, its thread resolved by news, while the answer to the user's
        # next comment lands.
        "test_a_website_turn_posts_its_answer_when_the_move_is_settled_first": (
            r"lf-thread-compact|lf-msg|lf-action-icon|lf-resolve"
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
