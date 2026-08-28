"""File-side anchor and thread-projection tests."""

import json

from click.testing import CliRunner
from interact_support import (
    DRAFTED,
    PAGE,
    SUGGESTED,
    SUGGESTION,
    check,
    comment,
    decide,
    drafted,
    edit,
    page_state,
    publish,
    published,
    stamp,
    state_json,
    suggested,
)
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import hooks as hooks_model


def test_comment_anchors_on_a_quote_and_posts_as_claude(page_dir, sessionless):
    result = comment(
        published(page_dir), "--quote", "Ship dark", "--text", "dark for how long?"
    )
    assert result.exit_code == 0, result.output
    event = json.loads(result.output)
    assert (
        event["kind"] == "comment"
        and event["author"] == "claude"
        and event["revision"] == 1
    )
    # A bare run has no host session behind it, so the event carries no voice
    # fields — readers' generic label covers it — rather than a stored
    # placeholder wearing a name.
    assert "agent" not in event and "session" not in event
    assert event["anchor"]["quote"] == "Ship dark"
    # The section is derived the way the browser derives it — the nearest enclosing id.
    assert event["anchor"]["section"] == "flag-first"
    assert event["text"] == "dark for how long?"


def test_a_comment_carries_the_neighbours_that_tell_two_copies_apart(page_dir):
    """The context is the whole reason a later version can't hand the comment to another
    copy of the same words, so a written anchor stores it exactly as a selection does."""
    event = json.loads(
        comment(
            published(page_dir), "--quote", "Verify, then flip", "--text", "ok"
        ).output
    )
    anchor = event["anchor"]
    # Read out of the whole collapsed text and stopped by the fences around the option
    # row — the runtime writes controls between options, words this reading doesn't
    # hold. The runtime reads its side back the same way, and only a full match counts.
    assert (
        anchor["prefix"] == "risk: low Backfill first"
    )  # the option's own chip band, then its title
    assert (
        anchor["suffix"] == "."
    )  # the option's last words; the fence ends the reading


def test_a_written_comment_quotes_the_whole_passage(page_dir):
    """A quote is the passage the page marks, so the capture writes the whole of it
    however long, and the neighbour after it is the page's next words rather than the
    rest of the passage. Cut at four hundred characters, both were wrong together: the
    comment landed on the passage's opening, and the suffix that was meant to tell one
    copy from another was text the quote itself already held. The runtime captures the
    same anchor from the DOM, so a cap here would have been a cap there too."""
    passage = (
        "The cutoff moves whenever the backfill runs, and the guard reads a column "
        "the writer never fills, so the batch replays from the top on each release, "
        "and the counters disagree with the log and with each other, and the retry "
        "budget is spent long before anyone looks at it, and the operator reads the "
        "dashboard at noon and files the incident against the wrong service, and "
        "the runbook it links still names a host that was retired last spring."
    )
    assert len(passage) > 400, "the fixture no longer outruns the old cap"
    long = PAGE.replace(
        '  <lf-diagram id="flow"><pre>\ngraph LR\n  A --> B\n  </pre></lf-diagram>\n',
        f"  <p>{passage}</p>\n  <p>Deploys pause overnight.</p>\n",
    )
    (page_dir / "versions" / "v1.html").write_text(long)
    event = json.loads(
        comment(published(page_dir), "--quote", passage, "--text", "x").output
    )
    anchor = event["anchor"]
    assert anchor["quote"] == passage
    assert anchor["suffix"] == "Deploys pause overnight."


def test_a_quote_closing_its_section_stores_the_next_sections_words(page_dir):
    """A suffix clipped at the section's edge could be one character, a bar an identical
    copy elsewhere might clear; the whole reading gives a closing passage a full side.
    The section the anchor names scopes where the search may land, never what surrounds
    the passage."""
    two = PAGE.replace(
        '  <lf-diagram id="flow"><pre>\ngraph LR\n  A --> B\n  </pre></lf-diagram>\n',
        "  <p>Deploys pause overnight.</p>\n",
    ).replace(
        "</main>",
        '<section id="rollout">\n  <p>The rollout resumes.</p>\n</section>\n</main>',
    )
    (page_dir / "versions" / "v1.html").write_text(two)
    event = json.loads(
        comment(
            published(page_dir), "--quote", "Deploys pause overnight.", "--text", "x"
        ).output
    )
    assert event["anchor"]["section"] == "plan"
    assert event["anchor"]["suffix"] == "The rollout resumes."


def test_a_comment_refuses_a_quote_the_version_does_not_hold(page_dir):
    result = comment(published(page_dir), "--quote", "ship it on Friday", "--text", "x")
    assert result.exit_code != 0
    assert "doesn't say" in result.output


def test_a_comment_refuses_a_quote_the_version_holds_twice(page_dir):
    """Which copy was meant is a question with an answer, and there is someone to ask.
    The browser has to guess because the user has already gone; this doesn't."""
    twice = PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>\n  <p>Ship dark.</p>")
    (page_dir / "versions" / "v1.html").write_text(twice)
    result = comment(published(page_dir), "--quote", "Ship dark", "--text", "x")
    assert result.exit_code != 0
    assert "2 times" in result.output
    # Scoping it to one of them is the way out the message offers.
    scoped = comment(
        page_dir, "--quote", "Ship dark", "--section", "flag-first", "--text", "x"
    )
    assert scoped.exit_code == 0, scoped.output
    assert json.loads(scoped.output)["anchor"]["section"] == "flag-first"


def test_a_section_the_version_has_no_id_for_is_refused(page_dir):
    """The first gate on a written anchor, and the one a typo meets. An id the version
    doesn't hold reaches nobody in the browser — the runtime looks the element up and
    finds nothing — so it is refused here, where the writer can still fix it, rather
    than posting a comment that arrives pointing at the page's edge."""
    result = comment(published(page_dir), "--section", "backfil-first", "--text", "x")
    assert result.exit_code != 0
    assert "no element id 'backfil-first'" in result.output


def test_a_section_scopes_where_a_quote_may_land(page_dir):
    """--section is the way out the ambiguity message offers, so it has to be a bound
    and not a label: the words go in the anchor's section field, and the browser then
    searches inside that element alone. A quote the page holds elsewhere is not a quote
    this section says, and taking it would write a comment whose two halves disagree —
    a section that doesn't hold the passage the quote names, which is exactly the claim
    the file's reading may never make on the page's behalf."""
    elsewhere = comment(
        published(page_dir),
        "--quote",
        "Verify, then flip",
        "--section",
        "flag-first",
        "--text",
        "x",
    )
    assert elsewhere.exit_code != 0
    # Named as the section's silence, not the page's: the page does say it, one option over.
    assert "§ flag-first doesn't say 'Verify, then flip'" in elsewhere.output
    held = comment(
        page_dir,
        "--quote",
        "Verify, then flip",
        "--section",
        "backfill-first",
        "--text",
        "x",
    )
    assert held.exit_code == 0, held.output
    assert json.loads(held.output)["anchor"]["section"] == "backfill-first"


def test_a_widgets_data_body_is_not_quotable_but_the_widget_is(page_dir):
    """A diagram's source is a picture by the time the reader sees it, so quoting the
    source anchors on text no search will find. Pointing at the element is what a click
    on that diagram does in the browser, and that is the anchor offered instead."""
    body = comment(published(page_dir), "--quote", "graph LR", "--text", "x")
    assert body.exit_code != 0
    # Named, not merely refused. "the page doesn't say it" was the old answer, and it is
    # a wider claim than this reading can make — for a widget whose body does reach the
    # reader as text it is simply false, and it sent the writer to fix a page that was
    # never wrong.
    assert "§ flow's data body" in body.output and "--section flow" in body.output
    element = comment(
        page_dir, "--section", "flow", "--text", "the retry edge is missing"
    )
    assert element.exit_code == 0, element.output
    assert json.loads(element.output)["anchor"] == {"section": "flow"}


def test_a_comment_may_name_a_declared_visual_part(page_dir):
    parted = PAGE.replace(
        '<lf-diagram id="flow">',
        '<lf-diagram id="flow" parts="node:A node:B">',
    )
    (page_dir / "versions" / "v1.html").write_text(parted)
    published(page_dir)

    result = comment(
        page_dir,
        "--section",
        "flow",
        "--part",
        "node:A",
        "--text",
        "where does this retry?",
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["anchor"] == {
        "section": "flow",
        "visual": "node:A",
    }

    unknown = comment(
        page_dir,
        "--section",
        "flow",
        "--part",
        "node:Missing",
        "--text",
        "x",
    )
    assert unknown.exit_code != 0
    assert "known: ['node:A', 'node:B']" in unknown.output

    unseated = comment(page_dir, "--part", "node:A", "--text", "x")
    assert unseated.exit_code != 0
    assert "--part needs --section" in unseated.output


def test_a_version_keeps_each_declared_visual_part_addressable(page_dir):
    parted = PAGE.replace(
        '<lf-diagram id="flow">',
        '<lf-diagram id="flow" parts="node:A node:B">',
    )
    (page_dir / "versions" / "v1.html").write_text(parted)
    published(page_dir)
    (page_dir / "versions" / "v2.html").write_text(
        parted.replace(' parts="node:A node:B"', ' parts="node:B"')
    )

    result = check(page_dir, 2)
    assert result.exit_code != 0
    assert (
        "visual parts present in revision r1 but dropped in index.html" in result.output
    )
    assert "flow · node:A" in result.output


def test_a_quote_may_not_run_across_a_widgets_parts(page_dir):
    """A module can replace or insert words the file's reading cannot model. A quote
    spanning one of those joins would resolve to nothing in the
    user's browser, so it's refused here, where someone can still do something about
    it. Either side of the join quotes fine."""
    fenced = PAGE.replace(
        '  <lf-diagram id="flow"><pre>\ngraph LR\n  A --> B\n  </pre></lf-diagram>',
        "  <p>Before the diagram.</p>\n"
        '  <lf-diagram id="flow"><pre>\ngraph LR\n  A --> B\n  </pre></lf-diagram>\n'
        "  <p>After the diagram.</p>",
    )
    (page_dir / "versions" / "v1.html").write_text(fenced)
    published(page_dir)
    across = comment(
        page_dir,
        "--quote",
        "Before the diagram. After the diagram.",
        "--text",
        "x",
    )
    assert across.exit_code != 0
    assert "across a widget's parts" in across.output
    assert (
        comment(page_dir, "--quote", "Before the diagram.", "--text", "x").exit_code
        == 0
    )


def test_a_verbatim_body_is_quotable_where_a_source_body_is_not(page_dir):
    """The registry draws the line: lf-draft renders the authored text into a plain div
    the anchor pass can see (x-verbatim), and lf-diagram renders a picture instead."""
    result = comment(
        drafted(page_dir), "--quote", "every mutating command", "--text", "which ones?"
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["anchor"]["section"] == "note"


def test_an_edited_draft_reads_as_the_users_words(page_dir):
    """An `edit` is absolute — the log carries the whole new body, and replay writes
    exactly that into the DOM the anchor pass searches — so the reading
    `leaf comment` captures against holds the user's words in the authored
    body's place: quotable, collapsed like any passage, genuinely adjacent to the
    prose around them (no fence — the screen shows that adjacency too)."""
    drafted(page_dir)
    edit(page_dir, "Adds --dry-run to purge\nand rebuild only.")
    result = comment(page_dir, "--quote", "purge and rebuild only", "--text", "x")
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["anchor"]["section"] == "note"
    across = comment(page_dir, "--quote", "Plan Adds --dry-run to purge", "--text", "x")
    assert across.exit_code == 0, across.output


def test_a_quote_of_words_an_edit_replaced_is_refused_naming_the_edit(page_dir):
    """The authored body is still in the file, but the user is no longer reading
    it — posted, the comment would detach in front of them. Refused at write time
    naming what removed the words, the retired slot's own treatment; a quote merely
    reaching into the replaced body from outside is the same detachment."""
    drafted(page_dir)
    edit(page_dir, "Adds --dry-run to purge and rebuild only.")
    result = comment(page_dir, "--quote", "every mutating command", "--text", "x")
    assert result.exit_code != 0
    assert "rewrote § note" in result.output and "their edit" in result.output
    across = comment(page_dir, "--quote", "Plan Adds --dry-run to every", "--text", "x")
    assert across.exit_code != 0 and "rewrote § note" in across.output


def test_a_restated_draft_takes_the_pen_back_from_the_reading(page_dir):
    """`restated` retracts the edit, so replay stops painting it and the reading
    returns to the version as authored: the new body quotable, the retracted edit's
    text nowhere — not even a refusal names it, since nothing removed it from this
    version's page. A fresh edit on the new version stands again."""
    drafted(page_dir)
    edit(page_dir, "Adds --dry-run to purge and rebuild only.")
    revised = DRAFTED.replace(
        '<lf-draft id="note"><pre>\nAdds --dry-run to every mutating command.',
        '<lf-draft id="note" restated><pre>\nOnly purge gets a dry-run; the rest apply live.',
    )
    (page_dir / "versions" / "v2.html").write_text(revised)
    noted = stamp(page_dir, 2, "took the pen back")
    assert noted.exit_code == 0, noted.output
    kept = comment(page_dir, "--quote", "the rest apply live", "--text", "x")
    assert kept.exit_code == 0, kept.output
    gone = comment(page_dir, "--quote", "purge and rebuild only", "--text", "x")
    assert gone.exit_code != 0 and "doesn't say" in gone.output
    edit(page_dir, "Fine, but default the flag on.", version=2)
    again = comment(page_dir, "--quote", "default the flag on", "--text", "x")
    assert again.exit_code == 0, again.output


def test_a_verb_the_registry_no_longer_speaks_moves_nothing(page_dir):
    """The registry is the gate, not the payload's shape: a logged action whose
    verb this page's vendored x-state doesn't declare — a verb a later layer
    retired — folds to nothing, so the reading stays the version as authored
    rather than trusting whatever text the event carried."""
    drafted(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "note",
            "action": "scribble",
            "detail": {"text": "Words no layer speaks."},
        },
    )
    kept = comment(page_dir, "--quote", "every mutating command", "--text", "x")
    assert kept.exit_code == 0, kept.output
    gone = comment(page_dir, "--quote", "Words no layer speaks", "--text", "x")
    assert gone.exit_code != 0 and "doesn't say" in gone.output


def test_an_unhonored_edit_outlives_a_republish(page_dir):
    """v2 re-emits the authored body with no `restated`, so the user's words
    still stand over it — replay carries them, and the reading follows: silence
    retracts nothing. This is the drift the whole mechanism closes: the file holds
    words the page stopped showing a version ago."""
    drafted(page_dir)
    edit(page_dir, "Adds --dry-run to purge and rebuild only.")
    (page_dir / "versions" / "v2.html").write_text(
        DRAFTED.replace("<title>t</title>", "<title>t · revised</title>")
    )
    noted = stamp(page_dir, 2, "changes elsewhere")
    assert noted.exit_code == 0, noted.output
    kept = comment(page_dir, "--quote", "purge and rebuild only", "--text", "x")
    assert kept.exit_code == 0, kept.output
    gone = comment(page_dir, "--quote", "every mutating command", "--text", "x")
    assert gone.exit_code != 0 and "rewrote § note" in gone.output


def test_a_widgets_x_says_attribute_is_quotable_like_any_other_passage(page_dir):
    """renderSaid puts these words in the DOM, so the anchor pass can find them and this
    has to offer them — otherwise a metric's own number is the one thing on the page
    Claude can't point at. Both edges the registry can give one are here: the option's
    chip band opens the element, and the metric's delta closes it."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            '  <lf-diagram id="flow">',
            '  <lf-metrics><lf-metric id="k-visits" value="312" delta="+41"'
            ' direction="up-good">daily visits</lf-metric></lf-metrics>\n'
            '  <lf-diagram id="flow">',
        )
    )
    published(page_dir)
    for quote, section in (
        ("risk: low Backfill first", "backfill-first"),
        ("daily visits +41", "k-visits"),
    ):
        result = comment(page_dir, "--quote", quote, "--text", "x")
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["anchor"]["section"] == section


def test_a_decision_retires_its_losing_slot_from_comments_reach(page_dir):
    """The user's accept removes lf-old from the page (the browser's anchor pass
    skips it), so a quote into it is refused naming the decision — posted, it would
    detach in front of them. The surviving slot quotes as ever, and a re-decision
    moves the line: the reading follows the log the way replay does, last word
    standing."""
    suggested(page_dir)
    decide(page_dir, "accept")
    gone = comment(
        page_dir, "--quote", "Refill every feeder each morning.", "--text", "x"
    )
    assert gone.exit_code != 0
    assert "chose to accept § sug-refill" in gone.output and "retired" in gone.output
    kept = comment(page_dir, "--quote", "camera shows it half-empty", "--text", "x")
    assert kept.exit_code == 0, kept.output

    decide(page_dir, "reject")
    gone = comment(page_dir, "--quote", "camera shows it half-empty", "--text", "x")
    assert gone.exit_code != 0 and "chose to reject § sug-refill" in gone.output
    kept = comment(
        page_dir, "--quote", "Refill every feeder each morning.", "--text", "x"
    )
    assert kept.exit_code == 0, kept.output


def test_a_section_inside_a_retired_slot_is_refused(page_dir):
    """An element anchor is a click on the element, and a retired slot's children
    are elements nobody can click. The id is still in the file — the refusal has to
    come from the decision, not the structure."""
    suggested(page_dir)
    decide(page_dir, "accept")
    result = comment(page_dir, "--section", "refill-rule", "--text", "x")
    assert result.exit_code != 0
    assert "chose to accept" in result.output and "sug-refill" in result.output


def test_a_decision_that_empties_its_widget_takes_it_off_sections_reach(page_dir):
    """A deletion accepted and an insertion refused both settle to nothing: the
    wrapper's markup is still in the file, but the user's screen shows nothing
    there, so an element anchor on it would read attached while outlining nothing.
    Pending, the wrapper answers like any element; settled empty, the refusal names
    the decision that emptied it."""
    lone = PAGE.replace(
        "<lf-options>",
        '<lf-suggestion id="sug-drop">\n'
        "  <lf-old><p>The manual sightings log.</p></lf-old>\n"
        "</lf-suggestion>\n"
        '<lf-suggestion id="sug-add">\n'
        "  <lf-new><p>Switch the north feeder to thistle.</p></lf-new>\n"
        "</lf-suggestion>\n<lf-options>",
    )
    (page_dir / "versions" / "v1.html").write_text(lone)
    published(page_dir)
    for wid in ("sug-drop", "sug-add"):
        ok = comment(page_dir, "--section", wid, "--text", "x")
        assert ok.exit_code == 0, ok.output
    decide(page_dir, "accept", widget="sug-drop")
    decide(page_dir, "reject", widget="sug-add")
    for wid, verb in (("sug-drop", "accept"), ("sug-add", "reject")):
        gone = comment(page_dir, "--section", wid, "--text", "x")
        assert gone.exit_code != 0
        assert "settled to nothing" in gone.output and f"chose to {verb}" in gone.output


def test_a_settled_replacement_still_answers_an_element_anchor(page_dir):
    """Deciding a replacement keeps a slot on screen, so the wrapper is still a thing
    to point at — only a decision that leaves nothing takes the element away."""
    suggested(page_dir)
    decide(page_dir, "accept")
    ok = comment(page_dir, "--section", "sug-refill", "--text", "x")
    assert ok.exit_code == 0, ok.output


def test_a_decision_settles_which_copy_a_quote_names(page_dir):
    """The browser counts occurrences on the page as decided, so the file has to
    count the same way — otherwise a passage unique in front of the user reads
    as ambiguous here, and an anchor allowed on the wrong count would carry context
    from words they no longer see."""
    twice = SUGGESTED.replace(
        "<h2>Plan</h2>", "<h2>Plan</h2>\n  <p>Refill every feeder each morning.</p>"
    )
    (page_dir / "versions" / "v1.html").write_text(twice)
    published(page_dir)
    ambiguous = comment(
        page_dir, "--quote", "Refill every feeder each morning.", "--text", "x"
    )
    assert ambiguous.exit_code != 0 and "2 times" in ambiguous.output
    decide(page_dir, "accept")
    result = comment(
        page_dir, "--quote", "Refill every feeder each morning.", "--text", "x"
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["anchor"]["section"] == "plan"


def test_a_restated_suggestion_hands_its_slot_back(page_dir):
    """A version that rewrites under a decision retracts it (`restated`), and replay
    then shows the suggestion pending again — both slots on the page. The reading
    follows the log all the way, not just to the first decision it finds."""
    suggested(page_dir)
    decide(page_dir, "accept")
    revised = SUGGESTED.replace(
        "Refill when the camera shows it half-empty.",
        "Refill when the camera shows it two-thirds empty.",
    ).replace(
        '<lf-suggestion id="sug-refill">', '<lf-suggestion id="sug-refill" restated>'
    )
    (page_dir / "versions" / "v2.html").write_text(revised)
    noted = stamp(page_dir, 2, "revised the proposal")
    assert noted.exit_code == 0, noted.output
    result = comment(
        page_dir, "--quote", "Refill every feeder each morning.", "--text", "x"
    )
    assert result.exit_code == 0, result.output


def test_a_decision_the_reader_took_back_hands_its_slot_back(page_dir):
    """Withdrawing is the second way a decision stops standing, and the file's
    reading owes it the same answer as `restated`: the retired half is on the page
    again, so a quote reaches it. Both are read in the one fold, which is what makes
    a single clause serve the anchor pass, the lint's state gate, and the ids a
    version honoring the decision would have been allowed to drop."""
    suggested(page_dir)
    decide(page_dir, "accept")
    retired = ["--quote", "Refill every feeder each morning.", "--text", "x"]
    assert comment(page_dir, *retired).exit_code != 0

    accepted = next(
        e for e in events_model.read_events(page_dir) if e["kind"] == "action"
    )
    events_model.append_event(
        page_dir, {"kind": "undo", "author": "user", "undoes": accepted["id"]}
    )
    result = comment(page_dir, *retired)
    assert result.exit_code == 0, result.output


def test_a_version_may_not_honor_a_decision_the_reader_took_back(page_dir):
    """The sharpest reading of whether a withdrawal actually undid anything, because
    it is the one the reader never sees: honoring a decision is how a version drops
    the ids the decision retired, and `version check` licenses that only from the
    standing fold. The same v2 is therefore accepted while the accept stands and
    refused the moment it is taken back — which is the file side saying the page is
    pending again, in the one place it could not be saying it out of politeness."""
    suggested(page_dir)
    decide(page_dir, "accept")
    # What honoring an accept looks like: the surviving half written straight,
    # keeping its id, and the wrapper and the retired half gone with the decision.
    honored = SUGGESTED.replace(
        SUGGESTION,
        '<p id="refill-camera">Refill when the camera shows it half-empty.</p>\n'
        "<lf-options>",
    )
    assert "sug-refill" not in honored and "refill-rule" not in honored
    (page_dir / "versions" / "v2.html").write_text(honored)
    assert check(page_dir, 2).exit_code == 0

    accepted = next(
        e for e in events_model.read_events(page_dir) if e["kind"] == "action"
    )
    events_model.append_event(
        page_dir, {"kind": "undo", "author": "user", "undoes": accepted["id"]}
    )
    assert check(page_dir, 2).exit_code == 1


def test_what_the_reader_never_sees_is_not_quotable(page_dir):
    """The runtime roots a section-less anchor at document.body, so a <title> is text no
    anchor can reach — and a page's title is often a sentence from the page as well."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace("<title>t</title>", "<title>Backfill cutover plan</title>")
    )
    result = comment(
        published(page_dir), "--quote", "Backfill cutover plan", "--text", "x"
    )
    assert result.exit_code != 0
    assert "doesn't say" in result.output


def test_a_comment_can_point_at_an_unstamped_live_revision(page_dir):
    result = comment(page_dir, "--quote", "Ship dark", "--text", "x")
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["revision"] == 1


def test_a_comment_without_an_anchor_asks_the_page_whole(page_dir):
    """Neither --quote nor --section is the browser's general box's own shape: a
    thread on the page as a whole, where a question about the work belongs."""
    result = comment(published(page_dir), "--text", "just a thought")
    assert result.exit_code == 0, result.output
    event = json.loads(result.output)
    assert event["kind"] == "comment" and event["author"] == "claude"
    assert "anchor" not in event


def test_the_agents_own_comment_is_not_printed_back_to_it(page_dir):
    """`leaf wait` and the banner's unread count both turn on author, so a note
    Claude leaves can't wake its own watcher or read as a comment nobody answered."""
    published(page_dir)
    assert comment(page_dir, "--quote", "Ship dark", "--text", "x").exit_code == 0
    assert page_state(page_dir)["pending"] == 0
    assert hooks_model.unattended_pages("") == []


def test_resolve_closes_a_thread_the_way_the_panel_does(page_dir, monkeypatch):
    """The agent's ✓ Resolve: the same event the panel's control posts, named by any
    message in the thread the way `leaf reply --to` is, and carrying the posting
    session's voice — which is the whole of how a reader learns a thread they did not
    close was closed."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s-7")
    monkeypatch.setenv("LEAF_AGENT", "Indexer")
    published(page_dir)
    root = events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "cameras are flaky",
        },
    )
    answer = json.loads(
        CliRunner()
        .invoke(
            cli_model.cli,
            ["reply", str(page_dir), "--to", root["id"], "--text", "fixed in v2"],
        )
        .output
    )

    result = CliRunner().invoke(
        cli_model.cli, ["resolve", str(page_dir), "--to", answer["id"]]
    )
    assert result.exit_code == 0, result.output
    event = json.loads(result.output)
    assert event["kind"] == "resolve" and event["author"] == "claude"
    assert event["parent"] == answer["id"]
    assert event["agent"] == "Indexer" and event["session"] == "s-7"

    threads = state_json(page_dir)["threads"]
    assert [t["resolved"] for t in threads] == ["claude"]

    transcript = CliRunner().invoke(cli_model.cli, ["transcript", str(page_dir)])
    assert "resolved by Indexer" in transcript.output


def test_resolve_refuses_a_message_the_log_has_not_got(page_dir):
    """The parent rule is the reply door's, so a thread can't be closed by naming
    something outside the conversation."""
    result = CliRunner().invoke(cli_model.cli, ["resolve", str(page_dir), "--to", "c9"])
    assert result.exit_code != 0
    assert "unknown comment id" in result.output


def test_unresolve_reopens_a_thread_in_agent_readings(page_dir):
    """The agent-side fold reads the inverse transition from the same log as the
    browser, so page state and the transcript both show the thread open again."""
    published(page_dir)
    root = events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Still relevant?",
        },
    )
    events_model.append_event(
        page_dir, {"kind": "resolve", "author": "user", "parent": root["id"]}
    )
    events_model.append_event(
        page_dir, {"kind": "unresolve", "author": "user", "parent": root["id"]}
    )

    assert state_json(page_dir)["threads"][0]["resolved"] is None
    transcript = CliRunner().invoke(cli_model.cli, ["transcript", str(page_dir)])
    assert "— resolved" not in transcript.output


def test_a_closed_thread_stops_asking(page_dir):
    """A question in a thread is the thread's, so closing the thread withdraws it.
    Otherwise an agent that asked and then answered the question for itself leaves
    the reader a standing ask for the life of the page, pointing into the disclosure
    closed threads live in."""
    (page_dir / "versions" / "v1.html").write_text(PAGE)
    publish(page_dir)
    root = events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "revision": 1,
            "text": "Which mitigations?",
            "markup": '<lf-ask id="gm-ask"><p>The retry budget is shared.</p>'
            '<lf-options id="gm" choose>'
            '<lf-option id="m-cap"><strong>Cap retries</strong></lf-option>'
            "</lf-options></lf-ask>",
        },
    )
    assert state_json(page_dir)["asks"] == [
        {"id": "gm-ask", "tag": "lf-ask", "thread": root["id"]}
    ]
    events_model.append_event(
        page_dir, {"kind": "resolve", "author": "claude", "parent": root["id"]}
    )
    assert state_json(page_dir)["asks"] == []


def test_thread_asks_share_one_projection_across_open_fragments(page_dir):
    """Independent thread widgets fold together while retaining their threads."""
    publish(page_dir)
    roots = []
    for suffix in ("a", "b"):
        roots.append(
            events_model.append_event(
                page_dir,
                {
                    "kind": "comment",
                    "author": "claude",
                    "revision": 1,
                    "text": f"Choose {suffix}",
                    "markup": (
                        f'<lf-options id="group-{suffix}" choose>'
                        f'<lf-option id="option-{suffix}"><strong>{suffix}</strong></lf-option>'
                        "</lf-options>"
                    ),
                },
            )
        )
    assert state_json(page_dir)["asks"] == [
        {"id": "group-a", "tag": "lf-options", "thread": roots[0]["id"]},
        {"id": "group-b", "tag": "lf-options", "thread": roots[1]["id"]},
    ]

    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "group-a",
            "action": "choose",
            "detail": {"options": ["option-a"]},
        },
    )
    assert state_json(page_dir)["asks"] == [
        {"id": "group-b", "tag": "lf-options", "thread": roots[1]["id"]}
    ]


def test_message_markup_may_not_dress_the_document_it_is_put_into(page_dir):
    """A fragment has no page of its own, so it gets no stylesheet of its own.

    The runtime parses an agent's markup into a template and moves those nodes into the
    message body, where a <style> among them becomes a document stylesheet like any
    other. `main h1 { color: red !important }` in a reply repainted the version's own
    heading, and the same declaration in a version answers to the syntax, column and
    cascade gates this door was never running. The inline half rides the same route: an
    !important on a protected presentation property outranks the theme's first
    important layer, which is exactly what a version is refused for.

    The widget beside them is what makes each refusal specific — a fragment carrying
    nothing but a widget still posts."""
    published(page_dir)
    widget = (
        '<lf-options id="d1" choose><lf-option id="d1-a">A</lf-option></lf-options>'
    )

    sheet = comment(
        page_dir,
        "--text",
        "look:",
        "--markup",
        "<style>main h1 { color: red }</style>" + widget,
    )
    assert sheet.exit_code != 0 and "<style>" in sheet.output

    linked = comment(
        page_dir,
        "--text",
        "look:",
        "--markup",
        '<link rel="stylesheet" href="/theme.css">' + widget,
    )
    assert linked.exit_code != 0 and "stylesheet" in linked.output

    inline = comment(
        page_dir,
        "--text",
        "look:",
        "--markup",
        '<p style="display: none !important">gone</p>' + widget,
    )
    assert inline.exit_code != 0 and "display" in inline.output

    assert comment(page_dir, "--text", "look:", "--markup", widget).exit_code == 0


def test_page_state_holds_a_decision_made_on_a_widget_an_agent_sent(page_dir):
    """The reader answering the agent's own question is answering the page.

    `page state` projects the published version's elements, and a widget carried by a
    message is in none of them — so a press on an AskUserQuestion resolved no
    declaration and stood nowhere. A session picking the page up read `asks` reporting
    the question answered and `state` reporting that nobody had answered anything,
    while the browser had been folding that same action all along.

    It is named by its thread rather than by a version, because thread markup is frozen
    in the log: no version bounds one of these and none can ever record it, which is
    also why `lag` has nothing to say about it."""
    published(page_dir)
    assert (
        comment(
            page_dir,
            "--text",
            "Pick one:",
            "--markup",
            '<lf-options id="ps-q" choose label="Which store?">'
            '<lf-option id="ps-redis">Redis</lf-option>'
            '<lf-option id="ps-cookie">A signed cookie</lf-option>'
            "</lf-options>",
        ).exit_code
        == 0
    )
    thread = events_model.read_events(page_dir)[-1]["id"]
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "ps-q",
            "action": "choose",
            "detail": {"options": ["ps-cookie"]},
        },
    )
    out = CliRunner().invoke(cli_model.cli, ["page", "state", str(page_dir)])
    assert out.exit_code == 0, out.output
    state = json.loads(out.stdout)
    assert [
        (s["widget"], s["action"], s["detail"], s["thread"]) for s in state["state"]
    ] == [("ps-q", "choose", {"options": ["ps-cookie"]}, thread)]
    # The page's own widgets are unrecorded either way, so the debt reading stays quiet
    # about one nothing could ever record.
    assert state["lag"] == []


def test_a_comments_widget_markup_shares_one_id_universe_with_replies(page_dir):
    """A Claude comment's markup lands in the panel exactly as a reply's does, so it
    validates the same way and claims ids from the same pool."""
    published(page_dir)
    assert (
        comment(
            page_dir,
            "--quote",
            "Ship dark",
            "--text",
            "Pick:",
            "--markup",
            '<lf-options id="q1" choose><lf-option id="q1-a"><strong>A</strong>'
            '<span id="thread-label">Label</span></lf-option></lf-options>',
        ).exit_code
        == 0
    )
    events_model.append_event(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    clash = CliRunner().invoke(
        cli_model.cli,
        [
            "reply",
            str(page_dir),
            "--to",
            "c1",
            "--text",
            "See:",
            "--markup",
            '<lf-diagram id="q1"><pre>\ngraph LR\n  A --> B\n</pre></lf-diagram>',
        ],
    )
    assert clash.exit_code != 0 and "q1" in clash.output

    plain_clash = CliRunner().invoke(
        cli_model.cli,
        [
            "reply",
            str(page_dir),
            "--to",
            "c1",
            "--text",
            "See:",
            "--markup",
            '<lf-diagram id="thread-label"><pre>graph LR\n  A --> B</pre></lf-diagram>',
        ],
    )
    assert plain_clash.exit_code != 0 and "thread-label" in plain_clash.output
