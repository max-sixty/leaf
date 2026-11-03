"""A target's cluster of margin entries: its primary action, the secondary entries it
unfolds, their order, and the suggestion actions it keeps reachable through a decision
and its undo."""

import re

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record, newest_move
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    SUGGESTION_PAGE,
    live_url,
    panel_comment,
)
from render_harness import (
    RELEASE_FOCUS,
    _traffic,
    _until,
    consume_browser_errors,
    http_error_console,
    leaf_page,
    margins_laid_out,
    open_page,
    panel_field,
    resized,
    round_trip,
    sending,
    stamp_page,
    told,
    wait_for_revision,
)

from browser.margin import (
    ACTION_PAGE,
    COMMENT_ON_SUGGESTION,
    MARGIN_ACTIONS_PAGE,
    MARGIN_ENTRY_KEYBOARD_PAGE,
    _unfold,
    _unfold_suggestion_undo,
)
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model

pytestmark = pytest.mark.shifts_unsurveyed


COMMENT_ON_SECOND_SUGGESTION = {
    "kind": "comment",
    "author": "agent",
    "revision": 1,
    "text": "This one can wait for the autumn order.",
    "anchor": {"section": "sug-thistle"},
}


@pytest.mark.parametrize("width", [1200, 390])
def test_obligation_binding_badges_follow_the_visible_margin_entries(
    browser, serve, width
):
    """Obligation travel shows hoisted answers above fixed chrome, with binding badges."""
    context = browser.new_context(
        viewport={"width": width, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(
        browser,
        serve(
            MARGIN_ACTIONS_PAGE,
            website_publication={
                "kind": "example",
                "agent": "Leaf guide",
                "install_url": "/#install",
            },
        ),
        context=context,
    )
    page.keyboard.press("m")
    expect(page.locator("#s-replace")).to_be_focused()
    expect(
        page.locator(".lf-command-binding-badges .lf-command-binding-badge")
    ).to_have_text(["1", "2"])
    geometry = page.evaluate(
        """() => {
          const item = document.querySelector('[data-lf-margin-for="s-replace"]');
          const boxes = (nodes) => nodes.map((node) => {
            const box = node.getBoundingClientRect();
            return {x: box.left + box.width / 2, y: box.top + box.height / 2,
                    half: box.width / 2};
          });
          const controls = [...item.querySelectorAll('.lf-margin-entry')].filter((button) => {
            const box = button.getBoundingClientRect();
            return box.width && /^(Accept|Reject) the /.test(button.ariaLabel);
          });
          return {
            folded: Boolean(
              item.closest('[data-lf-folded]') || item.querySelector('[data-lf-folded]')
            ),
            controls: controls.map((control) => {
              const box = control.getBoundingClientRect();
              return {x: box.left, right: box.right, y: box.top, bottom: box.bottom};
            }),
            foot: innerHeight,
            panel: document.querySelector('.lf-floating-panel').getBoundingClientRect().toJSON(),
            chips: boxes([...document.querySelectorAll(
              '.lf-command-binding-badges .lf-command-binding-badge'
            )]),
          };
        }"""
    )
    assert len(geometry["controls"]) == 2, geometry
    # Inside the window across too: where the pin stands folded, navigating to that obligation
    # opens it leftward from its toggle.
    for control in geometry["controls"]:
        assert 0 <= control["x"] < control["right"] <= width, geometry
    # Above the window's foot, and clear of the floating panel standing over it.
    panel = geometry["panel"]
    for control in geometry["controls"]:
        assert 0 < control["y"] < control["bottom"] <= geometry["foot"], geometry
        assert (
            control["bottom"] <= panel["top"]
            or control["right"] <= panel["left"]
            or control["x"] >= panel["right"]
        ), geometry
    assert len(geometry["chips"]) == 2, geometry

    # Each chip hangs off its own control's upper corner, the left one unless that would
    # lay it over the control beside it: the pair stand 4px apart, so the second's digit
    # takes its right corner. A folded pin opens with its toggle right of Reject, so
    # every corner of Reject lays its digit over a control and the digit keeps the first
    # (key-badge-placement.js, `paint`). Whether the pin at 390px finds room for its pair
    # or folds depends on the line's width in the platform's fonts, so the case reads it.
    # A chip is pulled inside the window, which moves one whose corner stands under half
    # its width in.
    def hangs(corner, chip):
        return abs(max(corner, chip["half"]) - chip["x"]) <= 2

    first, second = geometry["chips"]
    accept, reject = geometry["controls"]
    for control, chip in zip(geometry["controls"], geometry["chips"], strict=True):
        assert abs(control["y"] - chip["y"]) <= 2, geometry
    assert hangs(accept["x"], first), geometry
    assert hangs(reject["x" if geometry["folded"] else "right"], second), geometry


# Where the margin's rows stand: in the rail (1440), as pins over the page (700), and as
# pins one of which folds its actions behind `…` (390). At 1200 every row stands in the
# rail, as at 1440.
MARGIN_PLACEMENT_WIDTHS = [1440, 700, 390]


def test_suggestion_actions_stay_reachable_through_a_decision_and_its_undo(
    browser, serve
):
    """Each suggestion's Accept and Reject are back within reach once its decision is
    undone, in every posture its row takes. Each undo returns the page to where it
    started, so one page walks every posture."""
    page = open_page(browser, serve(MARGIN_ACTIONS_PAGE))
    for width in MARGIN_PLACEMENT_WIDTHS:
        # Let go of the pin the last width left unfolded, so it folds back.
        page.mouse.move(0, 0)
        page.evaluate(RELEASE_FOCUS)
        resized(page, width, 900)
        margins_laid_out(page)
        _decide_and_undo_each_suggestion(page)


def _decide_and_undo_each_suggestion(page):
    for target, outcome in (
        ("s-replace", "accept"),
        ("s-insert", "reject"),
        ("s-delete", "accept"),
    ):
        item = page.locator(f'[data-lf-margin-for="{target}"]')
        _unfold(item)
        applied = int(page.locator("body").get_attribute("data-lf-applied"))
        with sending(page, f"{outcome} {target}"):
            item.get_by_role(
                "button", name=re.compile(f"^{outcome.title()} the ")
            ).click()
        expect(page.locator("body")).to_have_attribute(
            "data-lf-applied", str(applied + 1)
        )
        render_checks_model.wait_until_ready(page)
        margins_laid_out(page)
        undo_control = _unfold_suggestion_undo(page, target)
        applied += 1
        with sending(page, f"undo {target}"):
            undo_control.click()
        expect(page.locator("body")).to_have_attribute(
            "data-lf-applied", str(applied + 1)
        )
        render_checks_model.wait_until_ready(page)
        margins_laid_out(page)
        _unfold(item)
        expect(
            item.get_by_role("button", name=re.compile("^Accept the "))
        ).to_be_visible()
        expect(
            item.get_by_role("button", name=re.compile("^Reject the "))
        ).to_be_visible()


# A block suggestion, whose slots keep their padding transition, beside a paragraph news
# can arrive on.
BLOCK_SUGGESTION_PAGE = leaf_page(
    "Block suggestion",
    """
<h1 id="t">Block suggestion</h1>
<lf-suggestion id="s-block"><lf-old><p>The sample meeting starts at nine in the
  courtyard, and the practice session follows it.</p></lf-old><lf-new><p>The sample
  meeting starts at ten on the covered terrace.</p></lf-new></lf-suggestion>
<p id="crowded-line">Bring a notebook and a pencil.</p>
""",
)


@pytest.mark.parametrize(
    ("source", "target"),
    [(MARGIN_ACTIONS_PAGE, "s-replace"), (BLOCK_SUGGESTION_PAGE, "s-block")],
    ids=["inline", "block"],
)
def test_a_decided_suggestions_pin_stays_put_when_news_arrives_elsewhere(
    browser, serve, source, target
):
    """A decision changes the surviving words' box, and their pin takes its seat by
    them as the decision lands. Nothing that arrives afterwards moves it: an agent's
    comment on another paragraph re-lays the margin and leaves this pin where the
    decision put it, and the shift watch sees no control move without input. The same
    holds once Undo puts the words back. At 390px the pin perches over the words; an
    inline survivor settles its padding at once, and a block one over the fold."""
    page = open_page(browser, serve(source))
    resized(page, 390, 900)
    margins_laid_out(page)
    item = page.locator(f'[data-lf-margin-for="{target}"]')

    def news_leaves_the_pin(text):
        margins_laid_out(page)
        settled = item.bounding_box()
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "agent",
                "revision": 1,
                "text": text,
                "anchor": {"section": "crowded-line"},
            },
        )
        told(page)
        margins_laid_out(page)
        after = item.bounding_box()
        assert (after["x"], after["y"]) == pytest.approx(
            (settled["x"], settled["y"]), abs=0.5
        ), (text, settled, after)

    _unfold(item)
    applied = int(page.locator("body").get_attribute("data-lf-applied"))
    with sending(page, f"accept {target}"):
        item.get_by_role("button", name=re.compile("^Accept the ")).click()
    expect(page.locator("body")).to_have_attribute("data-lf-applied", str(applied + 1))
    render_checks_model.wait_until_ready(page)
    news_leaves_the_pin("News after the decision.")

    with sending(page, f"undo {target}"):
        _unfold_suggestion_undo(page, target).click()
    expect(page.locator("body")).to_have_attribute("data-lf-applied", str(applied + 2))
    render_checks_model.wait_until_ready(page)
    page.mouse.move(0, 0)
    page.evaluate(RELEASE_FOCUS)
    news_leaves_the_pin("News after the undo.")


def test_a_margin_entry_carries_a_suggestion_through_its_whole_lifecycle(
    browser, serve
):
    """A suggestion's margin entry goes through each transition to a settled decision.

    A pending user action and an external work claim are different facts. The pending
    action is drawn as its result, with a live Undo in the pressed entry's seat, while
    the work claim keeps its workflow treatment.
    """
    page = open_page(browser, live_url(serve(MARGIN_ACTIONS_PAGE)))
    resized(page, 1440, 900)

    workflow = page.locator('[data-lf-margin-for="s-replace"]')
    accept = workflow.get_by_role(
        "button", name=re.compile(r"^Accept the suggested change")
    )
    expect(accept).to_have_attribute("data-lf-state", "idle")

    def reject(route):
        route.fulfill(
            status=400,
            json={"ok": False, "error": "transport refusal", "final": True},
        )

    page.route("**/api/event", reject)
    accept.click()
    expect(page.locator("#s-replace lf-old")).to_be_visible()
    consume_browser_errors(page, http_error_console(400))
    expect(accept).to_have_attribute("data-lf-state", "idle")
    page.unroute("**/api/event")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    sends = _traffic(page).sends
    accept.click()
    _until(page, lambda traffic: traffic.sends > sends, "held the acceptance")
    expect(accept).to_have_count(0)
    pending_undo = workflow.get_by_role("button", name=re.compile(r"^Undo accepting"))
    expect(pending_undo).to_have_attribute("data-lf-state", "idle")
    expect(pending_undo).not_to_have_attribute("aria-busy", "true")
    expect(pending_undo).to_be_enabled()
    expect(page.locator("#s-replace lf-old")).to_be_hidden()
    expect(page.locator("#s-replace lf-new")).to_be_visible()
    expect(pending_undo).to_have_css("opacity", "1")

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator("#s-replace")).to_have_attribute("data-lf-state", "accept")
    # No passing notice repeats the receipt the margin shows.
    expect(panel_field(page)).not_to_have_attribute(
        "placeholder", re.compile(r"^(Accepted|Rejected) .+")
    )
    expect(workflow.locator(".lf-margin-receipt")).to_have_count(0)
    undo_button = workflow.get_by_role("button", name=re.compile(r"^Undo accepting"))
    expect(undo_button).to_have_attribute("data-lf-state", "idle")
    expect(undo_button).to_have_css("opacity", "1")
    action_shadow = undo_button.evaluate("node => getComputedStyle(node).boxShadow")
    assert action_shadow != "none"
    sent = workflow.get_by_role("status", name=re.compile(r"^Queued for Claude for "))
    expect(sent).to_be_visible()
    expect(sent).to_have_attribute("data-lf-state", "idle")
    expect(sent).to_have_css("opacity", "1")

    claimed = CliRunner().invoke(
        cli_model.cli,
        [
            "task",
            "start",
            str(serve.page_dir),
            newest_move(serve.page_dir, "s-replace"),
            "--text",
            "applying the selected route",
        ],
    )
    assert claimed.exit_code == 0, claimed.output
    told(page)
    expect(undo_button).to_have_attribute("data-lf-agent-workflow", "working")
    expect(undo_button).to_have_attribute(
        "aria-description", re.compile("applying the selected route")
    )
    expect(undo_button).not_to_have_attribute("data-lf-agent-arrival", re.compile(".*"))
    working_shadow = undo_button.evaluate("node => getComputedStyle(node).boxShadow")
    assert working_shadow == action_shadow, (
        "agent workflow erased the action's raised shadow",
        action_shadow,
        working_shadow,
    )
    expect(workflow.locator('[data-lf-kinds="activity"]:visible')).to_have_count(0)

    stamped = stamp_page(
        serve.page_dir,
        MARGIN_ACTIONS_PAGE,
        "Apply the selected route",
    )
    wait_for_revision(page, stamped["revision"])
    expect(workflow.locator("[data-lf-agent-workflow]")).to_have_count(0)
    expect(page.locator("#s-replace lf-new")).to_be_visible()
    expect(workflow.locator(".lf-margin-receipt")).to_have_count(0)
    expect(
        workflow.get_by_role("button", name=re.compile(r"^Undo accepting"))
    ).to_have_count(1)


def test_keyboard_arrival_at_a_margin_entry_cluster_replaces_ellipsis_with_all_entries(
    browser, serve
):
    """Keyboard arrival expands one target's peers instead of focusing its overflow.

    The cluster stands in the margin layer, after the page's content in the tab
    order, so the arrival is a keyboard focus on its first stop there."""
    page = open_page(browser, serve(MARGIN_ENTRY_KEYBOARD_PAGE))
    resized(page, 1440, 900)
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          registerContribution({key: 'extra', target: document.querySelector('#sug-refill'),
            read: () => ({entries: [contributionEntry({
              key: 'details', icon: 'comment', label: 'Details',
              behavior: 'disclosure', rank: 'reading'
            })]}), activate: () => {}});
        }"""
    )
    item = page.locator('[data-lf-margin-for="sug-refill"]')
    accept = item.get_by_role("button", name=re.compile(r"Accept"))
    more = item.locator(":scope > .lf-margin-more")
    options = item.locator(":scope > .lf-margin-options")
    expect(more).to_be_visible()
    page.locator("#before-margin-entries").focus()
    page.keyboard.press("Tab")
    accept.focus()

    expect(accept).to_be_focused()
    expect(more).to_be_hidden()
    expect(options).to_be_visible()
    reject = item.get_by_role("button", name=re.compile(r"Reject"))
    expect(reject).to_be_visible()
    page.keyboard.press("Tab")
    expect(reject).to_be_focused()
    expect(more).to_be_hidden()

    page.keyboard.press("Escape")
    expect(more).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(accept).to_be_focused()
    expect(options).to_be_visible()

    page.locator("#after-margin-entries").focus()
    expect(more).to_be_visible()
    expect(options).to_be_hidden()

    more.click()
    expect(options).to_be_visible()
    page.locator("#insert").click()
    expect(more).to_be_visible()
    expect(options).to_be_hidden()


def test_left_and_right_walk_the_revealed_margin_entry_cluster(browser, serve):
    """Horizontal arrows move between the peer margin entries revealed on keyboard entry."""
    page = open_page(browser, serve(MARGIN_ENTRY_KEYBOARD_PAGE))
    resized(page, 1440, 900)
    item = page.locator('[data-lf-margin-for="sug-refill"]')
    accept = item.get_by_role("button", name=re.compile(r"Accept"))
    reject = item.get_by_role("button", name=re.compile(r"Reject"))
    page.locator("#before-margin-entries").focus()
    page.keyboard.press("Tab")
    accept.focus()

    expect(accept).to_be_focused()
    page.keyboard.press("ArrowRight")
    expect(reject).to_be_focused()
    # The walk says where it stands in the panel's empty field.
    expect(panel_field(page)).to_have_attribute(
        "placeholder", re.compile("Action 2 of 2")
    )
    page.keyboard.press("ArrowLeft")
    expect(accept).to_be_focused()
    expect(panel_field(page)).to_have_attribute(
        "placeholder", re.compile("Action 1 of 2")
    )


def test_settling_a_secondary_action_keeps_its_undo_in_the_cluster(browser, serve):
    """The settled content and its Undo stay in one engaged cluster."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    resized(page, 1440, 900)
    item = page.locator('[data-lf-margin-for="sug-refill"]')
    options = item.locator(":scope > .lf-margin-options")

    with sending(page, "reject the secondary suggestion"):
        options.get_by_role("button", name=re.compile(r"Reject")).click()

    expect(item.locator(".lf-margin-receipt")).to_have_count(0)
    expect(item.locator(":scope > .lf-margin-more")).to_be_hidden()
    expect(options).to_be_visible()
    expect(
        options.get_by_role("status", name=re.compile(r"^Queued for Claude for "))
    ).to_be_visible()
    expect(item.locator(".lf-margin-entry:visible")).to_have_count(2)
    expect(
        item.get_by_role("button", name=re.compile(r"^Undo rejecting"))
    ).to_be_focused()


CLUSTER_SHAPE = """() => [...document.querySelectorAll('.lf-margin-cluster')].map(
  (host) => [
    host.dataset.lfMarginFor,
    host.querySelectorAll('.lf-margin-entry').length,
    Boolean(host.querySelector('.lf-margin-options')?.hidden),
  ])"""


def test_a_print_preview_leaves_the_clusters_as_it_found_them(browser, serve):
    """Paper takes every injected control out of the page, so the one
    contributor-visibility reading a margin render is built on comes back empty there
    and folds every cluster to nothing. That is a reading of the medium rather than of
    the page: news arriving while the user is located in the print preview leaves the
    margin entries where they were, and reaches them when the screen comes back.

    The shape is read as markup rather than as visibility, because on paper nothing in
    the margin is visible either way; what the fold does is empty the option group and
    take the margin entries out of the host."""
    page = open_page(browser, serve(ACTION_PAGE, events=[COMMENT_ON_SUGGESTION]))
    resized(page, 1440, 900)
    margins_laid_out(page)
    shape = page.evaluate(CLUSTER_SHAPE)
    assert [host for host in shape if host[1] > 1], (
        f"no cluster here holds the margin entries a paper reading would fold away: {shape}"
    )

    page.emulate_media(media="print")
    append_carried_log_record(serve.page_dir, COMMENT_ON_SECOND_SUGGESTION)
    told(page)
    assert page.evaluate(CLUSTER_SHAPE) == shape

    page.emulate_media(media="screen")
    thistle = page.locator('[data-lf-margin-for="sug-thistle"]')
    expect(thistle.locator(".lf-margin-marker")).to_have_attribute(
        "aria-label", re.compile(r"^Thread, ")
    )


def test_one_target_has_one_primary_margin_entry_and_inline_secondary_margin_entries(
    browser, serve
):
    """A primary action acts; the ellipsis unfolds the remaining margin entries in place."""
    page = open_page(browser, serve(ACTION_PAGE, events=[COMMENT_ON_SUGGESTION]))
    resized(page, 1440, 900)

    suggestion_item = page.locator('[data-lf-margin-for="sug-refill"]')
    suggestion = suggestion_item
    expect(suggestion_item).to_have_class(re.compile(r"lf-margin-cluster"))
    expect(suggestion_item.locator(":scope > .lf-margin-marker")).to_have_count(1)
    expect(suggestion_item.locator(".lf-sug-accept")).to_be_visible()
    expect(suggestion_item.locator(".lf-sug-reject")).to_be_hidden()
    expect(suggestion_item.locator(":scope > .lf-margin-marker")).to_be_hidden()
    more = suggestion_item.locator(":scope > .lf-margin-more")
    expect(more).to_be_visible()
    for button in (suggestion_item.locator(".lf-sug-accept"), more):
        expect(button).to_have_class(re.compile(r"lf-margin-entry"))
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-entry-label")
    ).to_be_hidden()
    expect(suggestion_item.locator(".lf-sug-accept")).to_have_attribute(
        "data-lf-behavior", "action"
    )
    expect(suggestion_item.locator(".lf-sug-accept")).not_to_have_attribute(
        "aria-expanded", re.compile(".+")
    )
    expect(more).to_have_attribute("data-lf-behavior", "disclosure")
    expect(more).to_have_attribute("aria-expanded", "false")

    more.click()
    preview = page.locator(".lf-margin-preview")
    options = suggestion_item.locator(":scope > .lf-margin-options")
    expect(options).to_be_visible()
    expect(preview).to_be_hidden()
    expect(more).to_have_attribute("aria-expanded", "true")
    expect(more).to_be_hidden()
    reject = options.get_by_role("button", name=re.compile(r"Reject"))
    expect(reject).to_be_focused()
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    back = reference.locator(
        '.lf-command-reference-command[data-lf-command="navigation.back"]'
    )
    expect(back.locator(".lf-command-reference-title-words")).to_have_text(
        "Close options"
    )
    back.click()
    expect(reference).to_be_hidden()
    expect(options).to_be_hidden()
    expect(more).to_be_focused()
    more.click()
    expect(reject).to_be_visible()
    expect(options.get_by_role("button", name=re.compile(r"Ask for"))).to_have_count(0)
    expect(reject).to_be_focused()
    page.keyboard.press("Escape")
    expect(options).to_be_hidden()
    expect(more).to_be_focused()

    accept = suggestion.locator(".lf-sug-accept")
    expect(page.locator(".lf-margin-entry[title]")).to_have_count(0)
    page.mouse.move(0, 0)
    page.evaluate("() => document.activeElement.blur()")
    expect(accept).to_have_attribute("data-lf-tone", "positive")
    offer_backgrounds = [
        control.evaluate("el => getComputedStyle(el).backgroundColor")
        for control in (accept, more)
    ]
    assert len(set(offer_backgrounds)) == 1, (
        "interactive offers should share one unfilled resting surface"
    )
    borders = [
        control.evaluate(
            "el => { const s = getComputedStyle(el); "
            "return [s.borderTopWidth, s.borderRightWidth, "
            "s.borderBottomWidth, s.borderLeftWidth]; }"
        )
        for control in (accept, more)
    ]
    assert borders == [
        ["2px"] * 4,
        ["1px"] * 4,
    ], "the whole ring no longer distinguishes immediate actions from context"
    border_colors = [
        control.evaluate("el => getComputedStyle(el).borderTopColor")
        for control in (accept, more)
    ]
    assert border_colors[1] != border_colors[0], (
        "the disclosure should retain its firmer line beside the immediate action"
    )
    shadows = [
        control.evaluate("el => getComputedStyle(el).boxShadow")
        for control in (accept, more)
    ]
    assert shadows[0] != "none" and shadows[1] == "none", (
        "only an immediate Action should rise off the shared paper surface"
    )

    before_hover = more.bounding_box()
    more.hover()
    expect(more.locator(".lf-margin-entry-label")).to_be_visible()
    assert more.bounding_box() == before_hover, (
        "the transient label moved its margin entry"
    )
    page.mouse.move(0, 0)
    expect(more.locator(".lf-margin-entry-label")).to_be_hidden()

    # In the rail; a pin's entries are smaller, since a pin covers what it stands on.
    shapes = page.locator(
        ".lf-sug-accept:visible, .lf-margin-more:visible, .lf-margin-marker:visible"
    ).evaluate_all(
        "els => els.filter(el => el.closest('[data-lf-place=\"rail\"]'))"
        ".map(el => { const box = el.getBoundingClientRect(); "
        "const style = getComputedStyle(el); "
        "return [Math.round(box.width), Math.round(box.height), style.borderRadius]; })"
    )
    assert len({tuple(shape) for shape in shapes}) == 1, (
        "actions, disclosures, and overflow no longer share one margin entry shape"
    )

    accept.focus()
    # Reconciliation that does not change the target order leaves the complete item in
    # place, so a focused contribution remains focused.
    page.evaluate(
        """async () => {
          window.dispatchEvent(new Event('resize'));
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
        }"""
    )
    expect(accept).to_be_focused()
    column = page.locator("main").evaluate(
        "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
    )
    page.keyboard.press("e")
    reactions = suggestion_item.locator(":scope > .lf-margin-options")
    expect(preview).to_be_hidden()
    expect(suggestion_item.locator(".lf-margin-entry:visible")).to_have_count(6)
    expect(reactions.locator(".lf-react").first).to_have_class(
        re.compile(r"lf-margin-entry")
    )
    ok = reactions.get_by_role("button", name="keep", exact=True)
    expect(ok).to_have_attribute("aria-label", "keep")
    expect(ok).not_to_have_attribute("title", re.compile(".+"))
    ok.hover()
    expect(ok.locator(".lf-margin-entry-label")).to_have_text("keep")
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    assert (
        page.locator("main").evaluate(
            "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
        )
        == column
    ), "opening reaction choices moved the readable column"
    assert reactions.evaluate("surface => surface.matches('.lf-margin-options')"), (
        "e did not expand the target's canonical margin entry options"
    )

    # Labels remain transient even with abundant room; options never widen the rail.
    resized(page, 2400, 900)
    page.mouse.move(0, 0)
    page.evaluate("() => document.activeElement.blur()")
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-entry-label")
    ).to_be_hidden()
    accept.hover()
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-entry-label")
    ).to_be_visible()
    page.mouse.move(0, 0)
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-entry-label")
    ).to_be_hidden()
    accept.focus()
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-entry-label")
    ).to_be_visible()
    page.mouse.move(0, 0)
    accept.focus()
    page.keyboard.press("e")
    expect(suggestion_item.locator(".lf-margin-entry:visible")).to_have_count(6)

    page.keyboard.press("Escape")
    expect(suggestion_item.locator(".lf-react:visible")).to_have_count(0)
    expect(options).to_be_visible()
    page.keyboard.press("Escape")
    expect(options).to_be_hidden()
    more.click()
    expect(options).to_be_visible()
    thread_margin_entry = options.locator(
        '.lf-margin-reading-option[data-lf-kinds="comment"]'
    )
    expect(thread_margin_entry).to_be_visible()
    thread_margin_entry.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(options).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(options).to_be_visible()
    # Back on the entry the card hung from, the cluster the user unfolded being the
    # level under it and the one the next press folds.
    expect(thread_margin_entry).to_be_focused()
    page.keyboard.press("Escape")
    expect(options).to_be_hidden()
    expect(more).to_be_focused()

    # On a narrow screen each item stands near its target in room where it finds some:
    # within 12px, or a line of its words further out where none lies nearer, as the
    # suggestion's pin does at the end of the heading above its paragraph.
    page.keyboard.press("Escape")
    page.evaluate("() => document.activeElement.blur()")
    resized(page, 390, 900)
    margins_laid_out(page)
    suggestion.locator(".lf-sug-accept").focus()
    expect(page.locator("#sug-refill")).to_be_in_viewport()
    expect(suggestion_item).to_have_attribute("data-lf-place", "pin")
    stands = suggestion_item.evaluate(
        """item => {
          const row = item.getBoundingClientRect();
          const target = item.lfTarget;
          const box = target.getBoundingClientRect();
          const block = getComputedStyle(target).display.startsWith('inline')
            ? target.parentElement : target;
          const line = parseFloat(getComputedStyle(block).lineHeight) || 0;
          return {near: Math.hypot(
                    Math.max(0, row.left - box.right, box.left - row.right),
                    Math.max(0, row.top - box.bottom, box.top - row.bottom))
                    <= 12 + line,
                  inPage: row.left >= 0 && row.right <= innerWidth};
        }"""
    )
    assert stands == {"near": True, "inPage": True}, stands
    expect(suggestion_item.locator(":scope > .lf-margin-marker")).to_be_hidden()
    page.keyboard.press("e")
    expect(suggestion_item.locator(".lf-margin-entry:visible")).to_have_count(6)
    with sending(page, "the keep reaction"):
        reactions.get_by_role("button", name=re.compile(r"^keep\b")).click()
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["token"] == "keep" and sent["anchor"] == {"section": "sug-refill"}


def test_secondary_margin_entry_proxies_preserve_disabled_and_focus_contract(
    browser, serve
):
    """Proxy presses preserve a user's explicit fold until they leave or close it."""
    page = open_page(browser, serve(PANEL_PAGE))
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          let visible = {act: true, backup: true, locked: true, details: true};
          window.lfPrimaryClicks = 0;
          window.lfBackupClicks = 0;
          window.lfMarginFocusResults = [];
          window.lfRequestedMarginFocus = null;
          const registration = registerContribution({
            key: 'fixture', target: document.querySelector('#how-cap'),
            read: () => ({entries: [
              contributionEntry({key: 'act', glyph: 'A', label: 'Act',
                behavior: 'action', visible: visible.act}),
              contributionEntry({key: 'backup', glyph: 'B', label: 'Backup',
                behavior: 'action', rank: 'secondary', visible: visible.backup}),
              contributionEntry({key: 'locked', glyph: 'L', label: 'Locked',
                behavior: 'action', rank: 'secondary', disabled: true,
                visible: visible.locked}),
              contributionEntry({key: 'details', glyph: 'D', label: 'Details',
                behavior: 'disclosure', rank: 'reading', visible: visible.details,
                relation: {kind: 'element', id: 'how-cap', expanded: true}}),
            ]}),
            activate: (token, {focus}) => {
              if (token === 'act') window.lfPrimaryClicks += 1;
              if (token === 'backup') window.lfBackupClicks += 1;
              if (window.lfRequestedMarginFocus)
                window.lfMarginFocusResults.push({
                  capability: typeof focus,
                  moved: focus(window.lfRequestedMarginFocus),
                });
            }
          });
          window.lfMarginEntryFixture = {
            registration,
            hide(...keys) {
              visible = {...visible};
              keys.forEach(key => visible[key] = false);
              registration.update({immediate: true});
            }
          };
        }"""
    )
    item = page.locator('[data-lf-margin-for="how-cap"]')
    more = item.locator(":scope > .lf-margin-more")
    options = item.locator(":scope > .lf-margin-options")
    more.click()
    backup = options.get_by_role("button", name="Backup")
    expect(options.get_by_role("button", name="Locked")).to_be_disabled()
    expect(options.get_by_role("button", name="Details")).to_have_attribute(
        "aria-expanded", "true"
    )

    primary = item.locator("[data-lf-margin-entry-primary]")
    primary.focus()
    page.keyboard.press("Enter")
    assert page.evaluate("() => window.lfPrimaryClicks") == 1
    expect(options).to_be_hidden()
    expect(primary).to_be_focused()

    more.click()
    backup.focus()
    page.keyboard.press("Enter")
    assert page.evaluate("() => window.lfBackupClicks") == 1
    expect(options).to_be_visible()
    expect(backup).to_be_focused()
    page.keyboard.press("Escape")
    expect(options).to_be_hidden()
    expect(more).to_be_focused()

    more.click()
    backup.focus()
    page.evaluate(
        """() => {
          window.lfMarginEntryFixture.hide('backup', 'details');
        }"""
    )
    expect(options.get_by_role("button", name="Locked")).to_be_visible()
    expect(more).to_be_hidden()
    expect(primary).to_be_focused()

    page.evaluate(
        """() => {
          document.activeElement.blur();
          window.lfRequestedMarginFocus = 'act';
          window.lfMarginEntryFixture.registration.activate('act');
        }"""
    )
    expect(primary).to_be_focused()
    assert page.evaluate("() => window.lfMarginFocusResults.at(-1)") == {
        "capability": "function",
        "moved": True,
    }

    primary.evaluate(
        """button => {
          document.activeElement.blur();
          window.lfRequestedMarginFocus = 'act';
          button.click();
        }"""
    )
    expect(page.locator("body")).to_be_focused()
    assert page.evaluate("() => window.lfMarginFocusResults.at(-1)") == {
        "capability": "function",
        "moved": False,
    }

    page.keyboard.press("Escape")
    expect(more).to_be_hidden()
    expect(options.get_by_role("button", name="Locked")).to_be_visible()
    primary.focus()

    page.evaluate(
        """() => {
          window.lfMarginEntryFixture.hide('locked');
        }"""
    )
    expect(more).to_be_hidden()
    expect(primary).to_be_focused()


@pytest.mark.parametrize("width", [1440, 390])
def test_margin_entry_order_and_page_map_actions_are_stable_at_both_widths(
    browser, serve, width
):
    """Semantic priority beats registration order; density never loses an action."""
    fixture = leaf_page(
        "Dense margin entry targets",
        '<p id="first">First target</p><p id="second">Second target</p>',
    )
    page = open_page(browser, serve(fixture))
    resized(page, width, 900)
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          window.contributionEntryFixtures = [];
          for (const [index, id] of ['first', 'second'].entries()) {
            const target = document.getElementById(id);
            const fixture = {engaged: true, saveState: 'engaged', registrations: []};
            const ordinary = () => {
              const entries = [
                contributionEntry({key: 'act', icon: 'check', label: `Act ${id}`,
                  rank: 'primary'}),
                ...Array.from({length: 5}, (_, n) => contributionEntry({
                  key: `detail-${n + 1}`, icon: 'dot',
                  label: `Detail ${n + 1} ${id}`,
                  rank: 'secondary', visible: fixture.engaged || n === 0
                }))
              ];
              return index ? entries.reverse() : entries;
            };
            const editor = () => {
              const entries = [
                contributionEntry({key: 'cancel', icon: 'cross', label: `Cancel ${id}`,
                  rank: 'escape', state: 'engaged', visible: fixture.engaged}),
                contributionEntry({key: 'save', icon: 'check',
                  label: `Save ${id} with a longer explanation that must remain inside its tooltip`,
                  rank: 'complete', tone: 'positive', state: fixture.saveState,
                  visible: fixture.engaged})
              ];
              return index ? entries.reverse() : entries;
            };
            const offers = [
              {key: 'ordinary', target, read: () => ({entries: ordinary()}),
                activate: token => {
                  if (token.startsWith('detail-'))
                    target.dataset.lastAction = token.slice('detail-'.length);
                }},
              {key: 'editor', target,
                read: () => ({entries: editor(),
                  state: fixture.engaged ? 'engaged' : 'idle'}), activate: () => {}}
            ];
            for (const offered of index ? offers.reverse() : offers)
              fixture.registrations.push(registerContribution(offered));
            // One state change reaches both contributions, and the margin paints it
            // once rather than once with each of them.
            fixture.rest = () => {
              fixture.engaged = false;
              fixture.registrations.forEach(registration => registration.update());
            };
            fixture.busy = () => {
              fixture.saveState = 'busy';
              fixture.registrations.forEach(registration => registration.update());
            };
            window.contributionEntryFixtures.push(fixture);
          }
        }"""
    )
    margins_laid_out(page)
    for target in ("first", "second"):
        item = page.locator(f'[data-lf-margin-for="{target}"]')
        action_order = [
            "save",
            "cancel",
            "act",
            *[f"detail-{index}" for index in range(1, 6)],
        ]
        visible_actions = item.locator(".lf-margin-entry:visible").evaluate_all(
            """buttons => buttons.filter(button => !button.matches('.lf-margin-spill'))
              .map(button => button.dataset.lfMarginEntryKey)"""
        )
        assert visible_actions == [
            key for key in action_order if key in visible_actions
        ]
        expect(item.locator(".lf-margin-more")).to_be_hidden()
        primary = item.locator('[data-lf-margin-entry-key="save"]')
        primary.focus()
        expect(primary).to_be_focused()
        expect(page.locator(f'.lf-target-trace[data-for="{target}"]')).to_be_visible()
        primary.hover()
        label = item.locator('[data-lf-margin-entry-key="save"] .lf-margin-entry-label')
        expect(label).to_be_visible()
        box = label.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= width
        assert label.evaluate("label => label.scrollWidth <= label.clientWidth")
        page.keyboard.press("g")
        page.keyboard.press("Shift+p")
        dialog = page.locator(".lf-page-map-dialog")
        expect(dialog).to_be_visible()
        expect(
            dialog.get_by_role(
                "searchbox", name="Find an action, status, or location in Page Map"
            )
        ).to_be_focused()
        assert (
            dialog.locator(".lf-page-map-group")
            .filter(has=page.get_by_role("heading", name=f"{target.title()} target"))
            .locator(".lf-page-map-action")
            .evaluate_all(
                "buttons => buttons.map(button => button.dataset.lfMarginEntryKey)"
            )
            == action_order
        )
        dialog.get_by_role("button", name=f"Detail 5 {target}", exact=True).click()
        expect(page.locator(f"#{target}")).to_have_attribute("data-last-action", "5")
        expect(dialog).to_be_hidden()

    first = page.locator('[data-lf-margin-for="first"]')
    second = page.locator('[data-lf-margin-for="second"]')
    save = first.locator('[data-lf-margin-entry-key="save"]')
    save.focus()
    save.hover()
    second.locator('[data-lf-margin-entry-key="save"]').focus()
    expect(page.locator('.lf-target-trace[data-for="second"]')).to_be_visible()
    expect(page.locator('.lf-target-trace[data-for="first"]')).to_be_hidden()
    save.hover()
    expect(page.locator('.lf-target-trace[data-for="first"]')).to_be_visible()
    ring = save.evaluate("button => getComputedStyle(button).borderTopWidth")
    page.evaluate("() => window.contributionEntryFixtures[0].busy()")
    expect(save).to_have_attribute("aria-busy", "true")
    expect(save).to_have_attribute("data-lf-tone", "positive")
    assert save.evaluate("button => getComputedStyle(button).borderTopWidth") == ring
    page.emulate_media(forced_colors="active")
    assert (
        save.locator("svg").evaluate("icon => getComputedStyle(icon).stroke") != "none"
    )
    page.emulate_media(forced_colors="none")

    page.evaluate(
        "() => window.contributionEntryFixtures.forEach(fixture => fixture.rest())"
    )
    for target in ("first", "second"):
        item = page.locator(f'[data-lf-margin-for="{target}"]')
        expect(item.locator(".lf-margin-entry:visible")).to_have_count(2)
        expect(item.locator(".lf-margin-more")).to_be_hidden()
        expect(
            item.get_by_role("button", name=f"Act {target}", exact=True)
        ).to_be_visible()
        expect(
            item.get_by_role("button", name=f"Detail 1 {target}", exact=True)
        ).to_be_visible()


def test_a_reading_marker_remains_visible_beside_offered_actions(browser, serve):
    """Expanding offered actions keeps the target's thread marker reachable."""
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "Keep this thread visible.", {"section": "how-cap"})
    page = open_page(browser, url)
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          registerContribution({
            key: 'reading-actions', target: document.querySelector('#how-cap'),
            read: () => ({entries: Array.from({length: 2}, (_, index) =>
              contributionEntry({key: `peer-${index}`, icon: 'dot',
                label: `Peer ${index}`, rank: 'secondary'})), side: 'after'}),
            activate: () => {}
          });
        }"""
    )
    item = page.locator('[data-lf-margin-for="how-cap"]')
    item.locator(":scope > .lf-margin-more").click()
    expect(item.locator(":scope > .lf-margin-marker")).to_be_visible()
    for index in range(2):
        expect(
            item.get_by_role("button", name=f"Peer {index}", exact=True)
        ).to_be_visible()
