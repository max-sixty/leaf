"""Where a thread opens from the margin, which card or panel shows it, and how each
press the user makes is taken off again."""

import re
from time import monotonic

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    OBLIGATION_PAGE,
    PANEL_PAGE,
    SUGGESTION_PAGE,
    executable_revision,
    live_url,
)
from render_cases_layout import current_location_ring
from render_harness import (
    PANEL,
    PANEL_THREAD,
    RELEASE_FOCUS,
    comment_note,
    leaf_page,
    margins_laid_out,
    open_page,
    open_threads,
    panel_field,
    panel_settled,
    press_visible,
    resized,
    scroll_settled,
    sending,
    stamp_page,
    ticked,
    told,
    wait_for_revision,
    write,
)

from browser.margin import (
    ACTION_ON_OBLIGATION,
    ACTION_PAGE,
    COMMENT_ON_OBLIGATION,
    COMMENT_ON_SUGGESTION,
    LONG_THREAD,
    LONG_THREAD_PAGE,
    LONG_THREAD_ROOT,
    ON_THE_PAGE,
    PARAGRAPH_ON_OBLIGATION,
    WORDS_RIGHT,
    _comment_on,
    leave_card,
    seeded_thread,
)
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_spilled_thread_opens_the_full_thread_without_a_hidden_anchor(browser, serve):
    """Page Map reveals a spilled thread's reading control before anchoring its card."""
    page = open_page(browser, serve(SUGGESTION_PAGE, events=[COMMENT_ON_SUGGESTION]))
    resized(page, 1440, 900)
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          const entries = [];
          const registration = registerContribution({
            key: 'details', target: document.getElementById('sug-refill'),
            read: () => ({entries, state: 'engaged'}), activate: () => {}});
          window.lfGrowThreadPeers = () => {
            const index = entries.length;
            entries.push(contributionEntry({key: `detail-${index}`, icon: 'dot',
              label: `Detail ${index}`, rank: 'secondary'}));
            registration.update();
          };
        }"""
    )
    item = page.locator('[data-lf-margin-for="sug-refill"]')
    expect(
        item.locator('.lf-margin-reading-option[data-lf-kinds="comment"]')
    ).to_be_visible()
    deadline = monotonic() + render_checks_model.SERVED_TIMEOUT_MS / 1000
    while not item.evaluate(
        """cluster => Boolean(cluster.querySelector('.lf-margin-spill')?.checkVisibility())
          && !cluster.querySelector('.lf-margin-reading-option[data-lf-kinds="comment"]')
            ?.checkVisibility()"""
    ):
        assert monotonic() < deadline, "the thread never spilled as peers were added"
        page.evaluate("window.lfGrowThreadPeers()")
        rendered(page)
    item.locator(".lf-margin-spill").click()
    dialog = page.locator(".lf-page-map-dialog")
    dialog.get_by_role("button", name=re.compile("^Open thread:")).click()
    expect(dialog).to_be_hidden()
    expect(
        item.locator('.lf-margin-reading-option[data-lf-kinds="comment"]')
    ).to_be_visible()
    thread_id = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == COMMENT_ON_SUGGESTION["text"]
    )
    thread = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{thread_id}"]'
    )
    expect(thread).to_be_focused()
    expect(thread).to_contain_text(COMMENT_ON_SUGGESTION["text"])
    expect(page.locator(PANEL)).not_to_have_attribute("data-open", re.compile(""))
    page.keyboard.press("c")
    expect(thread.locator("leaf-text")).to_be_focused()


def test_page_map_opens_a_thread_anchored_to_a_drawn_zero_area_svg_line(browser, serve):
    """A visible SVG stroke remains a usable comment target despite its zero-height box."""
    source = leaf_page(
        "Horizontal line comment",
        """
<h1>Review this diagram</h1>
<svg width="320" height="120" viewBox="0 0 320 120" role="img"
     aria-label="A horizontal line">
  <line id="hline" x1="10" y1="60" x2="310" y2="60"
        stroke="currentColor" stroke-width="8" />
</svg>
""",
    )
    comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "Check this line.",
        "anchor": {"section": "hline"},
    }
    page = open_page(browser, serve(source, events=[comment]))
    margins_laid_out(page)

    line = page.locator("#hline")
    assert line.evaluate("node => node.getBoundingClientRect().height") == 0
    assert line.evaluate("node => node.checkVisibility()")
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(dialog).to_be_visible()
    dialog.get_by_role(
        "button", name="Open thread: Check this line.", exact=True
    ).click()
    rendered(page)

    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    thread_id = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == comment["text"]
    )
    thread = preview.locator(f'.lf-page-thread[data-thread="{thread_id}"]')
    expect(thread).to_be_focused()
    expect(thread).to_contain_text("Check this line.")


def test_a_secondary_thread_keeps_card_ownership_through_membership_and_posture(
    browser, serve
):
    """The semantic thread margin entry owns its open card as a cluster reconfigures."""
    comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "First thread at this target.",
        "anchor": {"section": "how-cap"},
    }
    page = open_page(browser, serve(PANEL_PAGE, events=[comment]))
    resized(page, 1440, 900)
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          let primaryVisible = true;
          let peers = [];
          const registration = registerContribution({
            key: 'fixture', target: document.querySelector('#how-cap'),
            read: () => ({entries: [contributionEntry({
              key: 'act', glyph: 'A', label: 'Act', behavior: 'action',
              visible: primaryVisible
            }), ...peers]}), activate: () => {}
          });
          window.lfThreadOwner = {
            registration,
            showPrimary(visible) {
              primaryVisible = visible;
              registration.update({immediate: true});
            },
            addPeers() {
              peers = [1, 2, 3].map(i => contributionEntry({
                key: `peer-${i}`, glyph: 'P', label: `Peer ${i}`, behavior: 'action'
              }));
              registration.update({immediate: true});
            }
          };
        }"""
    )
    item = page.locator('[data-lf-margin-for="how-cap"]')
    marker = item.locator(":scope > .lf-margin-marker")
    more = item.locator(":scope > .lf-margin-more")
    options = item.locator(":scope > .lf-margin-options")
    thread = options.locator('.lf-margin-reading-option[data-lf-kinds="comment"]')
    thread.evaluate("node => node.dataset.stableProof = 'same-thread-button'")
    thread.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(thread).to_have_attribute("aria-expanded", "true")

    thread.focus()
    page.evaluate(
        """() => {
          window.lfThreadOwner.showPrimary(false);
        }"""
    )
    expect(marker).to_be_visible()
    expect(marker).to_be_focused()
    expect(marker).to_have_attribute("aria-controls", "lf-margin-preview")
    expect(marker).to_have_attribute("aria-expanded", "true")
    expect(page.locator(".lf-margin-preview")).to_be_visible()

    page.evaluate(
        """() => {
          window.lfThreadOwner.showPrimary(true);
        }"""
    )
    expect(options).to_be_visible()
    expect(thread).to_be_focused()
    expect(thread).to_have_attribute("data-stable-proof", "same-thread-button")
    expect(thread).to_have_attribute("aria-expanded", "true")

    second = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "text": "Second thread joined while the first card was open.",
            "anchor": {"section": "how-cap"},
        },
    )
    told(page)
    expect(thread).to_have_attribute("data-stable-proof", "same-thread-button")
    expect(thread.locator(".lf-margin-count")).to_have_text("2")
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(page.locator(".lf-margin-preview-position")).to_have_text("1/2")
    expect(thread).to_have_attribute("aria-expanded", "true")

    resized(page, 1207, 900)
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(PANEL)).not_to_have_attribute("data-open", re.compile(""))
    expect(thread).to_have_attribute("aria-controls", "lf-margin-preview")
    expect(thread).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    # The pointer's press displaced the page, and Escape hands the page back; the card's
    # ownership is read off the control's aria state above, not off where focus lands.
    assert page.evaluate("() => document.activeElement === document.body")

    resized(page, 1440, 900)
    expect(thread).to_have_attribute("aria-controls", "lf-margin-preview")
    expect(thread).to_have_attribute("aria-expanded", "false")
    expect(options).to_be_visible()
    expect(more).to_be_hidden()
    expect(thread).to_have_attribute("data-stable-proof", "same-thread-button")
    thread.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(thread).to_have_attribute("aria-expanded", "true")
    # A click leaves the card no different to close than a key: one press.
    leave_card(page)
    expect(thread).to_have_attribute("aria-expanded", "false")

    page.evaluate("window.lfThreadOwner.addPeers()")
    expect(options).to_be_hidden()
    comment_note(page, "#how-cap").press("Enter")
    expect(options).to_be_visible()
    assert page.evaluate(
        """async id => {
          const {readThreads, threadActions} = await window.__lfWidgetApi();
          const thread = readThreads().threads.find(thread => thread.id === id);
          return Boolean(await threadActions.open(thread.key, {part: 'thread'}));
        }""",
        second["id"],
    )
    expect(options).to_be_visible()
    expect(thread).to_have_attribute("aria-expanded", "true")
    page.locator(".lf-margin-preview-close").click()
    expect(options).to_be_hidden()


HIDDEN_TAB_PAGE = leaf_page(
    "a thread in a closed tab",
    """
  <lf-tabs id="views">
    <lf-tab id="view-open" label="Open"><p>The tab the page opens on.</p></lf-tab>
    <lf-tab id="view-closed" label="Closed">
      <p id="closed-words">Words in the tab the page does not open on.</p>
    </lf-tab>
  </lf-tabs>""",
)


@pytest.mark.parametrize(
    "options",
    [{"focus": False, "travel": False, "flash": False}, {"part": "thread"}],
    ids=["where-the-user-stands", "travelling"],
)
def test_opening_a_thread_reveals_its_closed_tab(browser, serve, options):
    """Opening a thread reveals its passage whether or not the page travels to it: its
    card stands beside the passage's margin row, which a closed tab hides. Opened where
    the user is located (`travel: false`), the card never placed and the opening never
    answered."""
    page = open_page(
        browser, serve(HIDDEN_TAB_PAGE, events=[_comment_on("closed-words")])
    )
    resized(page, 1440, 900)
    expect(page.locator("#view-closed")).to_be_hidden()
    opened = page.evaluate(
        """async options => {
          const {readThreads, threadActions} = await window.__lfWidgetApi();
          const [thread] = readThreads().threads;
          const opening = threadActions.open(thread.key, options);
          const late = new Promise(resolve => setTimeout(() => resolve('late'), 5000));
          const shown = await Promise.race([opening, late]);
          return shown === 'late' ? shown : Boolean(shown);
        }""",
        options,
    )
    assert opened is True
    expect(page.locator("#closed-words")).to_be_visible()
    expect(page.locator(".lf-margin-preview")).to_be_visible()


LONG_STRIP_PAGE = leaf_page(
    "a thread in the closed tab of a long strip",
    """
  <lf-tabs id="views">
    <lf-tab id="view-open" label="The open tab"><p id="open-words">Words.</p></lf-tab>"""
    + "".join(
        f'<lf-tab id="view-{n}" label="Another long tab name {n}"><p>Tab {n}.</p></lf-tab>'
        for n in range(8)
    )
    + """
    <lf-tab id="view-last" label="The last tab"><p id="last-words">Words.</p></lf-tab>
  </lf-tabs>
  <p id="hidden-words" hidden>Words the page hides.</p>
  <p id="unseen-words" style="visibility: hidden">Words the page leaves unseen.</p>""",
)


def open_where_the_user_stands(page, section, **options):
    """Open the thread about `section` without travel, as the render gate does, and
    say whether it opened, or "late" where it had not answered within five seconds."""
    return page.evaluate(
        """async ([section, options]) => {
          const {readThreads, threadActions} = await window.__lfWidgetApi();
          const thread = readThreads().threads.find(t => t.anchor.section === section);
          const opening = threadActions.open(
            thread.key, {focus: false, travel: false, ...options});
          const late = new Promise(resolve => setTimeout(() => resolve('late'), 5000));
          const shown = await Promise.race([opening, late]);
          return shown === 'late' ? shown : Boolean(shown);
        }""",
        [section, options],
    )


def test_a_thread_whose_passage_stays_hidden_opens_in_the_panel(browser, serve):
    """Where the passage stays hidden, its card has no row to stand beside, so the
    floating panel shows the thread. A thread opened with `scroll: false` reveals no
    closed tab, since a tab switch scrolls its strip, and a passage the page hides,
    with `hidden` or `visibility: hidden`, can't be revealed at all."""
    page = open_page(
        browser,
        serve(
            LONG_STRIP_PAGE,
            events=[
                _comment_on("last-words"),
                _comment_on("hidden-words"),
                _comment_on("unseen-words"),
            ],
        ),
    )
    resized(page, 390, 844)
    strip = page.locator("#views > .lf-tabstrip")
    assert strip.evaluate("s => s.scrollWidth > s.clientWidth"), "the strip fits"
    assert open_where_the_user_stands(page, "last-words", scroll=False) is True
    expect(page.locator(PANEL)).to_have_attribute("data-open", re.compile(".+"))
    expect(page.locator("#view-last")).to_be_hidden()
    assert strip.evaluate("s => s.scrollLeft") == 0
    for section in ("hidden-words", "unseen-words"):
        assert open_where_the_user_stands(page, section) is True, section


def test_a_thread_in_view_opens_beside_it_and_leaves_the_tab_strip(browser, serve):
    """A thread whose passage is in view opens its card beside it, and the tab strip the
    user scrolled stays where they left it."""
    page = open_page(
        browser, serve(LONG_STRIP_PAGE, events=[_comment_on("open-words")])
    )
    resized(page, 390, 844)
    strip = page.locator("#views > .lf-tabstrip")
    left = strip.evaluate("s => (s.scrollLeft = s.scrollWidth, s.scrollLeft)")
    assert left > 0, "the strip fits, so it proves nothing"
    assert open_where_the_user_stands(page, "open-words") is True
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    assert strip.evaluate("s => s.scrollLeft") == left


MOVED_PASSAGE_PAGE = leaf_page(
    "a passage a revision moves into a closed tab",
    """
  <lf-tabs id="views">
    <lf-tab id="view-open" label="Open"><p id="moved-words">Words a revision moves.</p></lf-tab>
    <lf-tab id="view-closed" label="Closed"><p id="other-words">Other words.</p></lf-tab>
  </lf-tabs>""",
)


@pytest.mark.parametrize("installation", ["in-place", "fresh"])
@pytest.mark.parametrize("passage", ["drawn", "in-a-closed-tab"])
def test_a_card_open_across_a_revision_opens_where_its_passage_stands(
    browser, serve, installation, passage
):
    """A revision keeps an open card's thread in front of the reader as any opening
    does: the card beside its passage where the revision still draws it, else the
    floating panel, leaving closed the tab the revision moved the passage into. A user
    who stood in the card stands in the thread wherever it opens. Before,
    an in-place revision left the card open and unseen, waiting for a passage nothing
    would draw, and a fresh document reopened the card only for the margin to close
    it."""
    page = open_page(
        browser,
        live_url(serve(MOVED_PASSAGE_PAGE, events=[_comment_on("moved-words")])),
    )
    resized(page, 1440, 900)
    assert open_where_the_user_stands(page, "moved-words") is True
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    page.locator(".lf-margin-preview-close").focus()
    moved = '<p id="moved-words">Words a revision moves.</p>'
    revised = (
        MOVED_PASSAGE_PAGE.replace(moved, "").replace(
            '<p id="other-words">Other words.</p>', f"<p>Other words.</p>{moved}"
        )
        if passage == "in-a-closed-tab"
        else MOVED_PASSAGE_PAGE.replace("Other words.", "Revised words.")
    )
    if installation == "fresh":
        revised = executable_revision(revised, "fresh")
    first_document = page.evaluate("performance.timeOrigin")
    stamp_page(serve.page_dir, revised, "Revise it")
    wait_for_revision(page, 2)
    assert (page.evaluate("performance.timeOrigin") != first_document) == (
        installation == "fresh"
    )
    if passage == "drawn":
        expect(card).to_be_visible()
        expect(page.locator(".lf-margin-preview-close")).to_be_focused()
        expect(page.locator(PANEL_THREAD)).to_have_count(0)
    else:
        expect(page.locator(PANEL_THREAD)).to_be_focused()
        expect(page.locator("#view-closed")).to_be_hidden()
        expect(card).to_be_hidden()


def test_one_information_margin_entry_does_not_raise_a_preview(browser, serve):
    """A single non-thread reading travels directly; cards are reserved for threads."""
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]),
    )
    resized(page, 1600, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="on-me"]').first
    expect(marker).not_to_have_attribute("aria-controls", re.compile(".+"))
    expect(marker).not_to_have_attribute("aria-expanded", re.compile(".+"))
    marker.hover()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_hidden()
    marker.click()
    expect(preview).to_be_hidden()


def test_the_margin_groups_meanings_at_one_destination_without_moving_the_page(
    browser, serve
):
    """One location groups its thread and engaged handoff without moving the page."""
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]),
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    expect(marker).to_have_count(1)
    expect(marker.locator(".lf-margin-count")).to_have_count(0)
    expect(marker).to_have_attribute("aria-label", re.compile(r"Thread, \d+ of"))
    expect(marker).not_to_have_attribute("title", re.compile(".+"))
    more = marker.locator("xpath=..").locator(":scope > .lf-margin-more")
    expect(more).to_be_hidden()
    claim = marker.locator("xpath=..").evaluate(
        """item => {
          const style = getComputedStyle(item);
          const buttons = [...item.querySelectorAll(':scope > .lf-margin-entry')]
            .filter(button => button.checkVisibility());
          const needed = buttons.reduce(
            (total, button) => total + button.getBoundingClientRect().width, 0
          ) + (parseFloat(style.columnGap || style.gap) || 0)
            * Math.max(0, buttons.length - 1)
            + (parseFloat(style.marginLeft) || 0)
            + (parseFloat(style.paddingLeft) || 0)
            + (parseFloat(style.paddingRight) || 0);
          const probe = document.createElement('i');
          probe.style.cssText =
            'position:fixed;visibility:hidden;height:0;padding:0;border:0;width:var(--rail)';
          document.querySelector('main').append(probe);
          const rail = probe.getBoundingClientRect().width;
          probe.remove();
          return {needed, rail};
        }"""
    )
    assert claim["rail"] >= claim["needed"] - 0.5, claim

    before = page.evaluate("() => document.scrollingElement.scrollTop")
    marker.hover()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_hidden()
    expect(marker.locator(".lf-margin-entry-label")).to_be_visible()
    marker.focus()
    expect(preview).to_be_hidden()

    marker.click()
    expect(marker).to_have_attribute("aria-expanded", "true")
    expect(preview).to_be_visible()
    expect(marker.locator(".lf-margin-entry-label")).to_be_hidden()
    # The thread the user now stands in marks its element; no trace doubles it.
    expect(page.locator(".lf-visual-mark-here")).to_be_visible()
    expect(page.locator('.lf-target-trace[data-for="bracket"]')).to_be_hidden()
    preview_box = preview.bounding_box()
    assert preview_box["x"] >= page.evaluate(WORDS_RIGHT) + 7.5
    assert preview_box["x"] >= 0
    assert preview_box["x"] + preview_box["width"] <= page.evaluate("innerWidth")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(preview).not_to_contain_text("options · choose")
    close = preview.get_by_role("button", name="Dismiss thread view", exact=True)
    resolve = preview.get_by_role("button", name="Resolve thread", exact=True)
    expect(close.locator('svg[data-lf-icon="cross"]')).to_have_count(1)
    expect(resolve.locator('svg[data-lf-icon="check"]')).to_have_count(1)
    expect(close).to_have_text("")
    expect(resolve).to_have_text("")
    reply = preview.get_by_role("textbox", name="Reply", exact=True)
    expect(reply).to_be_visible()
    geometry = preview.evaluate(
        """preview => {
          const thread = preview.querySelector('.lf-page-thread');
          // The controls stand over the transcript's top, beside each message's head.
          const metaRow = thread.querySelector(':scope > .lf-margin-thread-controls');
          const close = preview.querySelector('.lf-margin-preview-close');
          const resolve = thread.querySelector('.lf-resolve');
          const mr = metaRow.getBoundingClientRect();
          const cr = close.getBoundingClientRect();
          const rr = resolve.getBoundingClientRect();
          return {
            metaRow: {top: mr.top, bottom: mr.bottom},
            close: {top: cr.top, left: cr.left, bottom: cr.bottom},
            closeBorderColor: getComputedStyle(close).borderTopColor,
            resolveBorder: getComputedStyle(resolve, '::before').borderTopWidth,
            resolve: {top: rr.top, right: rr.right, bottom: rr.bottom},
          };
        }"""
    )
    assert geometry["closeBorderColor"] == "rgba(0, 0, 0, 0)"
    assert float(geometry["resolveBorder"][:-2]) == 0
    assert geometry["resolve"]["top"] == pytest.approx(geometry["close"]["top"], abs=1)
    assert geometry["resolve"]["bottom"] == pytest.approx(
        geometry["close"]["bottom"], abs=1
    )
    assert geometry["resolve"]["right"] <= geometry["close"]["left"] - 3, geometry
    # The card opens on the row containing Dismiss and Resolve.
    assert geometry["metaRow"]["top"] <= geometry["close"]["top"]
    assert geometry["metaRow"]["bottom"] >= geometry["close"]["bottom"]
    reply.click()
    expect(reply).to_be_focused()
    page.locator("h1").click()
    expect(preview).to_be_hidden()
    marker.click()
    expect(reply).to_be_visible()
    expect(reply).not_to_be_focused()
    reply.click()
    expect(reply).to_be_focused()
    write(reply, "Keep this draft visible.")
    page.locator(".lf-margin-preview-close").click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(marker).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(preview.locator(".lf-page-thread")).to_be_focused()
    expect(preview.locator("leaf-text")).to_be_visible()
    expect(preview.locator("leaf-text")).to_have_js_property(
        "value", "Keep this draft visible."
    )
    for activation in ("keyboard", "pointer"):
        write(reply, "Keep this draft visible.")
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "resolve",
                "author": "agent",
                "agent": "Codex",
                "parent": preview.locator(".lf-page-thread").get_attribute(
                    "data-thread"
                ),
            },
        )
        told(page)
        # Editing keeps the reply drawn, so only the control changes, with no
        # changed room to hold behind a news notice. Both routes return to the draft.
        # The check drawn done names who resolved it before Reopen.
        reopen = preview.get_by_role("button", name=re.compile(r"· Reopen$"))
        if activation == "keyboard":
            reopen.focus()
        with sending(page, "reopen the thread beside its kept draft"):
            if activation == "keyboard":
                page.keyboard.press("Enter")
            else:
                reopen.click()
        expect(reply).to_be_focused()
        expect(reply).to_have_js_property("value", "Keep this draft visible.")
    write(preview.locator("leaf-text"), "")
    page.locator(".lf-margin-preview-close").click()
    page.keyboard.press("Enter")
    expect(preview.locator("leaf-text")).to_be_visible()
    # The card is anchored to a target and hoisted into the chrome, so it lets the
    # user go beside that target rather than onto the marker it hung from, which a `t`
    # from the page would never have stood them on.
    leave_card(page)
    # The walk is over the markers the viewport holds and never scrolls to reach one,
    # which is what this case is named for. So it starts at the first of them and steps
    # down, against the count the walk itself publishes, rather than pressing from
    # wherever the card left the user: from the last marker on screen the press
    # clamps, and this case used to read that clamp as a walk that had failed to move.
    # Home is the margin's own key, so the user has to be in the margin to press it —
    # the card handed them back to the page, which is not.
    marker.focus()
    # Opening the card and walking its markers are separate scroll guarantees.
    # Editing the reply between them can move the document to reveal its caret.
    before_walk = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("Home")
    # The panel's empty field says where the walk stands.
    position = panel_field(page)
    expect(position).to_have_attribute("placeholder", re.compile(r"^Marker 1 of \d+"))
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before_walk
    said = re.search(r"Marker 1 of (\d+)", position.get_attribute("placeholder"))
    assert said is not None
    total = int(said.group(1))
    assert total > 1, said.group(0)
    first = page.locator(":focus").get_attribute("aria-label")
    page.keyboard.press("ArrowDown")
    expect(position).to_have_attribute(
        "placeholder", re.compile(rf"^Marker 2 of {total}\b")
    )
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before_walk
    assert page.evaluate("() => document.activeElement.matches('.lf-margin-marker')")
    assert page.locator(":focus").get_attribute("aria-label") != first

    options = marker.locator("xpath=..").locator(":scope > .lf-margin-options")
    expect(options).to_be_visible()
    # The move's delivery status, whatever its stage has reached: the pickup grace can
    # run out during this journey, turning "Sent" to "Waiting for delivery".
    status = options.get_by_role("status")
    expect(status).to_be_visible()
    expect(preview).to_be_hidden()
    status.click()
    expect(options).to_be_visible()
    expect(preview).to_be_hidden()


def test_design_mode_retires_and_suppresses_the_top_layer_margin_preview(
    browser, serve
):
    """Ordinary design paint never promises to rise above the browser's top layer."""
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]),
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()

    preview.get_by_role("button", name="Dismiss thread view").focus()
    page.keyboard.press("l")
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    expect(preview).to_be_hidden()
    page.mouse.move(4, 200)
    page.evaluate(RELEASE_FOCUS)
    marker.hover()
    expect(preview).to_be_hidden()
    page.evaluate(RELEASE_FOCUS)
    marker.focus()
    expect(preview).to_be_hidden()
    page.keyboard.press("Enter")
    expect(preview).to_be_hidden()
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")


def test_a_thread_can_be_answered_in_the_margin_without_opening_threads(browser, serve):
    """The anchored thread is a complete thread in its margin card: its marker opens
    the card on the thread, `c` writes in its reply box, and Send answers the thread
    with Threads left shut. With Threads open in the panel, the marker still opens the
    card beside the passage: the panel shows a passage's thread only where the page
    draws it nowhere.

    Where the card stands belongs to the placement tests beside this one; how a send
    is delivered belongs to the `margin` case of `test_render_thread_snapshots.py`."""
    page = open_page(browser, serve(OBLIGATION_PAGE, events=[PARAGRAPH_ON_OBLIGATION]))
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    preview = page.locator(".lf-margin-preview")
    thread = page.locator(".lf-margin-thread")
    reply = thread.locator("leaf-text")

    marker.click()
    expect(thread.locator(".lf-page-thread")).to_be_focused()
    expect(thread.locator(".lf-msg-body")).to_have_text(PARAGRAPH_ON_OBLIGATION["text"])
    expect(preview.get_by_role("button", name=re.compile(r"Threads?"))).to_have_count(0)
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    write(reply, "Yes. One visit can cover both jobs.")
    with sending(page, "the reply"):
        thread.get_by_role("button", name="Send").click()

    expect(thread.locator(".lf-page-thread")).to_contain_text(
        "Yes. One visit can cover both jobs."
    )
    expect(page.locator(PANEL)).not_to_have_attribute("data-open", re.compile(""))
    expect(preview).to_be_visible()
    root_id = thread.locator(".lf-page-thread").get_attribute("data-thread")
    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("kind") == "reply" and event.get("parent") == root_id
    ]
    assert [event["text"] for event in replies] == [
        "Yes. One visit can cover both jobs."
    ]

    page.locator(".lf-margin-preview-close").click()
    expect(preview).to_be_hidden()
    open_threads(page)
    marker.focus()
    page.keyboard.press("Enter")
    expect(preview).to_be_visible()
    expect(preview.locator(f'.lf-page-thread[data-thread="{root_id}"]')).to_be_focused()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)


def test_a_thread_margin_entry_opens_inline_when_the_panel_is_closed(browser, serve):
    """A marker opens its thread in a card beside the passage, even where a sidebar
    takes the room the margin would have."""
    sidebar_page = OBLIGATION_PAGE.replace(
        '<main class="layout-column">',
        '<main class="layout-sidebar"><aside><div class="layout-track">Page reference</div></aside>'
        '<div class="layout-column">',
        1,
    ).replace("</main>", "</div></main>", 1)
    page = open_page(browser, serve(sidebar_page, events=[COMMENT_ON_OBLIGATION]))
    resized(page, 1200, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')

    marker.click()

    expect(page.locator(PANEL)).not_to_have_attribute("data-open", re.compile(""))
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-margin-thread .lf-page-thread")).to_be_focused()
    expect(
        page.locator(".lf-margin-thread").get_by_role(
            "textbox", name="Reply", exact=True
        )
    ).to_be_visible()
    expect(marker).to_have_attribute("aria-controls", "lf-margin-preview")
    expect(marker).to_have_attribute("aria-expanded", "true")


def test_a_card_opens_on_its_first_unread_reply(browser, serve):
    """A card opens where the replies the user hasn't read begin, so a long one is read
    from its head down and reads like the short one after it. Opened at its latest
    reply instead, the card showed that reply whole, which read it, beneath the end of a
    long one whose start stayed above the card and so stayed unread."""
    long_reply, short_reply = (
        LONG_THREAD[1],
        {
            **LONG_THREAD[1],
            "text": "Landed: the first two now close to the page.",
            "id": "d" * 32,
            "ts": "2026-09-18T19:34:26-07:00",
        },
    )
    page = open_page(
        browser,
        serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT, long_reply, short_reply]),
    )
    resized(page, 1440, 700)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    transcript = page.locator(".lf-margin-preview .lf-thread-transcript")
    first = transcript.locator(".lf-msg").nth(1)
    expect(first).to_be_visible()
    room = transcript.evaluate("list => list.scrollHeight - list.clientHeight")
    assert room > 300, f"the transcript scrolls {room}px, too little to need a landing"
    assert (
        abs(
            first.bounding_box()["y"]
            - transcript.evaluate(
                "list => list.getBoundingClientRect().top + list.clientTop"
                " + parseFloat(getComputedStyle(list).paddingTop)"
                " + parseFloat(getComputedStyle(list).getPropertyValue('--lf-top'))"
            )
        )
        <= 1
    )
    # Each unread reply says New in its head, which a screen reader reads with it.
    expect(transcript.locator(".lf-msg-new")).to_have_count(2)
    expect(first.locator(".lf-msg-head")).to_contain_text("New")

    # Partway down the long reply, its head has stuck with New in it.
    transcript.hover()
    page.mouse.wheel(0, 240)
    page.wait_for_function(
        "list => list.scrollTop > 200", arg=transcript.element_handle()
    )
    tag = first.locator(".lf-msg-new").bounding_box()
    top = transcript.evaluate("list => list.getBoundingClientRect().top")
    assert top - 1 <= tag["y"] <= top + 30, (tag, top)

    for _ in range(40):
        if transcript.evaluate(
            "list => list.scrollTop + list.clientHeight >= list.scrollHeight - 1"
        ):
            break
        page.mouse.wheel(0, 120)
        page.wait_for_timeout(20)
    expect(transcript.locator(".lf-msg-new")).to_have_count(0)
    marked = {
        item["message"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "read"
        for item in event["messages"]
    }
    assert marked == {long_reply["id"], short_reply["id"]}


@pytest.mark.parametrize(
    ("width", "threads_open"), [(760, False), (1000, True), (1440, False)]
)
def test_a_new_anchored_comment_keeps_the_users_thread_view(
    browser, serve, width, threads_open
):
    """A send continues beside the passage, keeping the page put, whether or not the
    panel's Threads view stood open: the panel shows a passage's thread only where the
    page draws it nowhere."""
    page = open_page(browser, serve(OBLIGATION_PAGE))
    resized(page, width, 900)
    if threads_open:
        open_threads(page)
    page.locator("#mounts-p").click(click_count=3)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "Check the January failure mode.")
    passage_before = page.locator("#mounts-p").bounding_box()
    with sending(page, "the anchored comment"):
        page.keyboard.press("ControlOrMeta+Enter")

    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["text"]) == (
        "comment",
        "Check the January failure mode.",
    )
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    thread = preview.locator(
        f'.lf-margin-thread .lf-page-thread[data-thread="{sent["id"]}"]'
    )
    expect(thread.locator(".lf-msg-body")).to_have_text(sent["text"])
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    preview_box = preview.bounding_box()
    assert preview_box["x"] >= 0, preview_box
    assert preview_box["x"] + preview_box["width"] <= width, preview_box
    # The send leaves the user on its card.
    expect(thread).to_be_focused()
    press_visible(page, thread.get_by_role("textbox", name="Reply", exact=True))
    expect(thread.locator("leaf-text")).to_be_focused()
    page.keyboard.type("the next thought")
    expect(thread.locator("leaf-text")).to_have_js_property("value", "the next thought")
    passage_after = page.locator("#mounts-p").bounding_box()
    for coordinate in ("x", "y", "width", "height"):
        assert passage_after[coordinate] == pytest.approx(
            passage_before[coordinate], abs=1
        )
    # Reply opened the editor; Escape leaves the box for its thread and then takes
    # the card down beside the passage it is about. Neither step focuses the margin
    # entry the card hangs from, which the user never stood on and which says its
    # transient label as they arrive.
    page.keyboard.press("Escape")  # out of the reply box the user opened
    expect(thread).to_be_focused()
    leave_card(page)


@pytest.mark.parametrize("threads_open", [False, True])
def test_a_comment_sent_from_a_control_is_left_by_the_levels_it_opened(
    browser, serve, threads_open
):
    """The send lands on its thread, and each press takes off one level.

    `c` opens the box on whatever the user is located in without moving them off it,
    and the send leaves them on the card it puts up, whether or not the panel's Threads
    view stood open. The card's one press lets them go beside the page it is about.
    The control `c` was pressed from is not a landing.
    """
    page = open_page(browser, serve(OBLIGATION_PAGE))
    resized(page, 1440, 900)
    if threads_open:
        open_threads(page)
    stood = page.locator("lf-option-control").first
    stood.focus()
    expect(stood).to_be_focused()

    page.keyboard.press("c")
    composer = page.locator(".lf-fab-input")
    expect(composer).to_be_focused()
    page.keyboard.type("Worth checking before the frost.")
    with sending(page, "the comment on the chosen option"):
        page.keyboard.press("ControlOrMeta+Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    preview = page.locator(".lf-margin-preview")
    expect(
        preview.locator(f'.lf-page-thread[data-thread="{sent["id"]}"]')
    ).to_be_focused()
    leave_card(page)


def test_arriving_on_a_commented_element_shows_its_thread_beside_it(browser, serve):
    """A thread belongs to the element it is about, so both stand together.

    Arriving at the element by keyboard puts its card up without taking the user off
    the element; the element keeps its ring and the card stands clear of it. A press
    on the element leaves the card, since the user is still there, while a press
    anywhere else on the page, or letting go, takes it down.
    """
    page = open_page(browser, serve(OBLIGATION_PAGE))
    resized(page, 1201, 900)
    sent = seeded_thread(page, serve.page_dir, "#mounts-p")
    preview = page.locator(".lf-margin-preview")
    card = preview.locator(f'.lf-page-thread[data-thread="{sent["id"]}"]')
    passage = page.locator("#mounts-p")

    # Keyboard modality, then the user lands on the element as a go-to hint puts them.
    page.keyboard.press("Tab")
    passage.evaluate("node => { node.tabIndex = -1; node.focus(); }")
    assert passage.evaluate("node => node.matches(':focus-visible')")
    expect(card).to_be_visible()
    expect(passage).to_be_focused()
    boxes = page.evaluate(
        """() => ({
          card: document.querySelector('.lf-margin-preview').getBoundingClientRect(),
          passage: document.querySelector('#mounts-p').getBoundingClientRect(),
        })"""
    )
    card_box, passage_box = boxes["card"], boxes["passage"]
    assert (
        card_box["left"] >= passage_box["right"]
        or card_box["top"] >= passage_box["bottom"]
        or card_box["bottom"] <= passage_box["top"]
    ), boxes

    # Letting go of the element takes its card.
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")

    # A pointer on the passage the card is about keeps the current location there too, holding
    # nothing, and Escape takes the card from there.
    passage.evaluate("node => node.removeAttribute('tabindex')")
    marker = page.locator('[data-lf-margin-for="mounts-p"] .lf-margin-marker')
    marker.click()
    expect(card).to_be_focused()
    passage.click()
    expect(preview).to_be_visible()
    assert page.evaluate("() => document.activeElement === document.body")
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()

    # A press elsewhere on the page moves the current location elsewhere.
    marker.click()
    expect(card).to_be_focused()
    page.locator("h1").click()
    expect(preview).to_be_hidden()


@pytest.mark.parametrize("entry", ["note", "comment"])
def test_a_card_stays_its_press_to_take_off_when_it_moves_on(browser, serve, entry):
    """The card a press put up adds no level whatever thread it shows.

    `t` walks the card on to the next thread without adding a level, so the way out is
    still one press, beside the thread's target: neither the note nor the control `c`
    was pressed from is current any more, and the margin entry the card now hangs from
    is one the user never stood on.
    """
    page = open_page(browser, serve(OBLIGATION_PAGE))
    resized(page, 1440, 900)
    seeded_thread(page, serve.page_dir, "#mounts-p")
    seeded_thread(page, serve.page_dir, "#heater-p")
    preview = page.locator(".lf-margin-preview")
    card = preview.locator(".lf-page-thread")
    if entry == "note":
        stood = comment_note(page, "#mounts-p")
        stood.focus()
        page.keyboard.press("Enter")
        expect(card).to_be_focused()
    else:
        stood = page.locator("lf-option-control").first
        stood.focus()
        page.keyboard.press("c")
        page.keyboard.type("A third thought.")
        with sending(page, "the comment from the control"):
            page.keyboard.press("ControlOrMeta+Enter")
        expect(card).to_be_focused()
    shown = card.get_attribute("data-thread")

    page.keyboard.press("t")
    expect(card).not_to_have_attribute("data-thread", shown)
    expect(card).to_be_focused()

    # The card lets the user go beside the target it is anchored to rather than onto
    # the margin control it hangs from.
    leave_card(page)


def test_an_asks_card_closes_beside_its_options_and_comes_back_with_them(
    browser, serve
):
    """Escape takes an ask's thread card down beside the ask, so Tab goes on into its
    options and the card comes back with them: the user chooses with the discussion
    beside the question. The second ask has another below it on screen, which a landing
    at the top of the screen would Tab into instead."""
    page = open_page(
        browser,
        serve(
            OBLIGATION_PAGE,
            events=[
                COMMENT_ON_OBLIGATION,
                {
                    **COMMENT_ON_OBLIGATION,
                    "text": "Do we own a torque wrench already?",
                    "anchor": {"section": "tools"},
                },
            ],
        ),
    )
    resized(page, 1440, 900)
    card = page.locator(".lf-margin-preview .lf-page-thread")
    page.keyboard.press("t")
    expect(card).to_contain_text(COMMENT_ON_OBLIGATION["text"])
    page.keyboard.press("t")
    expect(card).to_contain_text("torque wrench")
    # The walk glides the ask into view; the user reads the thread before leaving it.
    scroll_settled(page)
    leave_card(page)
    page.keyboard.press("Tab")
    expect(page.locator("#tl-clamp lf-option-control")).to_be_focused()
    expect(card).to_contain_text("torque wrench")


def test_a_comment_raised_inside_a_card_s_target_takes_the_card_down(browser, serve):
    """A new comment box stands clear of the thread card the user moved on from.

    The card stays up while the user is located at its target, and an aimed comment inside
    that target keeps the same current location. The card is drawn above the page-level comment
    box and covers the margin beside the target, so leaving it up hid the field the
    user was typing into. The box on a new target takes the card down instead.
    """
    page = open_page(browser, serve(OBLIGATION_PAGE))
    resized(page, 1440, 900)
    seeded_thread(page, serve.page_dir, "#mounts-p")
    preview = page.locator(".lf-margin-preview")
    comment_note(page, "#mounts-p").focus()
    page.keyboard.press("Enter")
    expect(preview).to_be_visible()

    page.locator("#mounts-p").click(modifiers=["Alt"])
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    expect(preview).to_be_hidden()
    assert page.evaluate(
        """() => {
          const box = document.querySelector('.lf-fab-bar').getBoundingClientRect();
          const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
          return Boolean(hit?.closest('.lf-fab-bar'));
        }"""
    )


def test_a_card_walked_off_the_unfolded_cluster_lands_on_the_page(browser, serve):
    """A cluster unfolded on another entry stands beside the card, not under it.

    The card holds the margin's context while it is up, so a cluster the user unfolded
    stays open as `t` walks the card on to a thread on a different entry. Landing on the
    entry the card now hangs from would hand the next press a fold belonging to an entry
    somewhere else, so the card lets the user go beside its target and the cluster
    answers next, at the entry the user actually unfolded.
    """
    page = open_page(
        browser,
        serve(
            ACTION_PAGE,
            events=[
                COMMENT_ON_SUGGESTION,
                {
                    "kind": "comment",
                    "author": "agent",
                    "revision": 1,
                    "text": "The plain paragraph carries a thread of its own.",
                    "anchor": {"section": "insert"},
                },
            ],
        ),
    )
    resized(page, 1440, 900)
    unfolded = page.locator('[data-lf-margin-for="sug-refill"]')
    more = unfolded.locator(":scope > .lf-margin-more")
    options = unfolded.locator(":scope > .lf-margin-options")
    more.click()
    expect(options).to_be_visible()

    thread_margin_entry = options.locator(
        '.lf-margin-reading-option[data-lf-kinds="comment"]'
    )
    thread_margin_entry.click()
    preview = page.locator(".lf-margin-preview")
    card = preview.locator(".lf-page-thread")
    expect(preview).to_be_visible()
    card.focus()
    shown = card.get_attribute("data-thread")

    # The walk carries the card to a thread whose own margin entry is already shown,
    # so nothing unfolds to hang it from and nothing folds the cluster: the card holds
    # the margin's context, so the user's cluster is still open behind it.
    page.keyboard.press("t")
    expect(card).not_to_have_attribute("data-thread", shown)
    expect(options).to_be_visible()

    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    expect(options).to_be_visible()

    page.keyboard.press("Escape")
    expect(options).to_be_hidden()
    expect(more).to_be_focused()


def test_going_to_a_side_surface_folds_the_cluster_the_user_left(browser, serve):
    """Unfolded options stay open while a layer over the page holds the user, since
    that layer hands them back to the cluster as it closes. The panel's On view is
    somewhere else they went, so going to it folds the options, though the panel
    stands in the same native dialog as the chrome's layers."""
    page = open_page(browser, serve(ACTION_PAGE, events=[COMMENT_ON_SUGGESTION]))
    resized(page, 1440, 900)
    item = page.locator('[data-lf-margin-for="sug-refill"]')
    item.locator(":scope > .lf-margin-more").click()
    expect(item).to_have_attribute("data-lf-options-open", "")
    option = item.locator(".lf-margin-options .lf-margin-entry:visible").first
    option.focus()

    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    expect(item).to_have_attribute("data-lf-options-open", "")
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    expect(option).to_be_focused()

    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    assert page.locator(PANEL).evaluate("panel => panel.matches(':focus-within')")
    expect(item).not_to_have_attribute("data-lf-options-open", "")


@pytest.mark.parametrize("second", ["note", "marker"])
def test_a_second_press_into_an_open_card_leaves_one_level_to_take_off(
    browser, serve, second
):
    """A press from outside replaces what the card shows rather than stacking a level.

    The card shows one thread, so the second note or marker changes its contents and
    leaves one card open. Its way out is the target it is anchored to and then the
    page: neither note nor marker is a place the user was located.
    """
    page = open_page(browser, serve(OBLIGATION_PAGE))
    resized(page, 1440, 900)
    seeded_thread(page, serve.page_dir, "#mounts-p")
    seeded_thread(page, serve.page_dir, "#heater-p")
    preview = page.locator(".lf-margin-preview")
    card = preview.locator(".lf-page-thread")
    first = comment_note(page, "#mounts-p")
    first.focus()
    page.keyboard.press("Enter")
    expect(card).to_be_focused()
    shown = card.get_attribute("data-thread")

    stood = (
        comment_note(page, "#heater-p")
        if second == "note"
        else page.locator('[data-lf-margin-for="heater-p"] .lf-margin-marker')
    )
    stood.focus()
    page.keyboard.press("Enter")
    expect(card).not_to_have_attribute("data-thread", shown)
    expect(card).to_be_focused()

    # One card is open whichever press put this thread in it, so there is one way
    # out of it, beside the target it is anchored to.
    leave_card(page)


def test_a_shared_passage_steps_between_single_thread_cards(browser, serve):
    """A shared target shows one unambiguous thread and local navigation."""
    second_comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "Keep the second thread separate.",
        "anchor": {"section": "bracket"},
    }
    page = open_page(
        browser, serve(OBLIGATION_PAGE, events=[COMMENT_ON_OBLIGATION, second_comment])
    )
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
    preview = page.locator(".lf-margin-preview")

    expect(preview.locator(".lf-margin-thread")).to_have_count(1)
    expect(preview.locator(".lf-margin-preview-position")).to_have_text("1/2")
    previous = preview.get_by_role("button", name="Previous thread")
    next_thread = preview.get_by_role("button", name="Next thread")
    controls = preview.evaluate(
        """preview => Object.fromEntries(
          ['.lf-margin-preview-nav', '.lf-resolve', '.lf-margin-preview-close'].map(
            selector => {
              const box = preview.querySelector(selector).getBoundingClientRect();
              return [selector, {left: box.left, right: box.right,
                middle: box.top + box.height / 2}];
            }
          )
        )"""
    )
    assert controls[".lf-resolve"]["middle"] == pytest.approx(
        controls[".lf-margin-preview-close"]["middle"], abs=1
    ), controls
    assert controls[".lf-margin-preview-nav"]["middle"] == pytest.approx(
        controls[".lf-resolve"]["middle"], abs=1
    ), controls
    assert (
        controls[".lf-margin-preview-nav"]["right"] < controls[".lf-resolve"]["left"]
    ), controls
    assert (
        controls[".lf-resolve"]["right"] < controls[".lf-margin-preview-close"]["left"]
    ), controls
    expect(previous).to_be_disabled()
    expect(next_thread).to_be_enabled()
    disabled_style = previous.evaluate(
        "button => [getComputedStyle(button).backgroundColor, "
        "getComputedStyle(button).color]"
    )
    previous.hover()
    assert (
        previous.evaluate(
            "button => [getComputedStyle(button).backgroundColor, "
            "getComputedStyle(button).color]"
        )
        == disabled_style
    )
    expect(preview).to_contain_text(COMMENT_ON_OBLIGATION["text"])
    next_thread.click()
    expect(preview.locator(".lf-margin-preview-position")).to_have_text("2/2")
    expect(preview).to_contain_text(second_comment["text"])
    expect(preview).not_to_contain_text(COMMENT_ON_OBLIGATION["text"])
    expect(previous).to_be_enabled()
    expect(next_thread).to_be_disabled()
    expect(preview.locator(".lf-page-thread")).to_be_focused()
    previous.click()
    expect(next_thread).to_be_visible()
    expect(preview.get_by_role("button", name="Dismiss thread view")).to_be_visible()
    next_thread.click()
    expect(preview.locator(".lf-page-thread")).to_be_focused()
    page.keyboard.press("r")
    told(page)
    expect(preview.locator(".lf-margin-preview-nav")).to_be_hidden()
    expect(preview).to_contain_text(COMMENT_ON_OBLIGATION["text"])
    expect(preview).not_to_contain_text(second_comment["text"])
    expect(preview.get_by_role("button", name=re.compile(r"Threads?"))).to_have_count(0)
    open_threads(page)
    expect(preview).to_be_hidden()


def test_an_open_thread_refresh_keeps_the_current_margin_entry_target_highlighted(
    browser, serve
):
    """An open card does not own the highlight after the user aims elsewhere."""
    page = open_page(browser, serve(ACTION_PAGE, events=[COMMENT_ON_SUGGESTION]))
    resized(page, 1440, 900)
    suggestion = page.locator('[data-lf-margin-for="sug-refill"]')
    suggestion.locator(".lf-margin-more").click()
    suggestion.locator('.lf-margin-reading-option[data-lf-kinds="comment"]').click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.locator('[data-lf-margin-for="sug-thistle"] .lf-sug-accept').focus()
    trace = page.locator('.lf-target-trace[data-for="sug-thistle"]')
    expect(trace).to_be_visible()
    ticked(page)
    expect(trace).to_be_visible()


def test_focusing_a_thread_margin_entry_does_not_open_its_card(browser, serve):
    """Walking the Page Map never inserts an unrequested thread into the Tab order."""
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]),
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    preview = page.locator(".lf-margin-preview")

    marker.focus()
    expect(preview).to_be_hidden()
    toggle = page.locator(".lf-fp-on-user")
    toggle.focus()

    expect(toggle).to_be_focused()
    expect(preview).to_be_hidden()
    expect(page.locator('.lf-target-trace[data-for="bracket"]')).to_be_hidden()


def test_a_card_follows_the_margin_entry_it_hangs_from_in_the_tab_order(browser, serve):
    """A card stands in the Tab order just after the margin entry that opened it, as a
    popover stands after its invoker. Shift+Tab from the card's first stop goes back to
    the entry, keeping the card open and the page still, rather than to the page's last
    stop; Tab from the entry goes into the card; and leaving that pair either way
    passes over the card rather than circling through it."""
    page = open_page(
        browser,
        serve(PANEL_PAGE, events=[_comment_on("lede", "Check the schedule.")]),
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    preview = page.locator(".lf-margin-preview")
    in_card = "() => document.querySelector('.lf-margin-preview').contains(document.activeElement)"
    marker.focus()
    page.keyboard.press("Enter")
    expect(preview.locator(".lf-page-thread")).to_be_focused()
    scrolled = page.evaluate("scrollY")

    page.keyboard.press("Shift+Tab")
    expect(marker).to_be_focused()
    expect(preview).to_be_visible()
    assert page.evaluate("scrollY") == scrolled
    page.keyboard.press("Tab")
    first = preview.get_by_role("button", name="Open in panel", exact=True)
    expect(first).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(marker).to_be_focused()

    # Out past the card's last stop, to the stop after the entry, and back to the entry.
    page.keyboard.press("Tab")
    for _ in range(10):
        page.keyboard.press("Tab")
        if not page.evaluate(in_card):
            break
    assert not page.evaluate(in_card), "Tab never left the card"
    expect(marker).not_to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(marker).to_be_focused()
    # Back from the entry to the page, over the card.
    page.keyboard.press("Shift+Tab")
    assert page.evaluate(ON_THE_PAGE)


def test_an_open_desktop_preview_reconciles_arriving_meanings(browser, serve):
    """A pinned marker card stays current while its semantic location is retained."""
    page = open_page(
        browser,
        serve(
            OBLIGATION_PAGE,
            events=[
                ACTION_ON_OBLIGATION,
                {**COMMENT_ON_OBLIGATION, "id": "f" * 32},
            ],
        ),
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "text": "A second reading arrived while the preview was pinned.",
            "id": "0" * 32,
            "anchor": {"section": "bracket"},
        },
    )
    told(page)
    expect(marker.locator(".lf-margin-count")).to_have_text("2")
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(page.locator(".lf-margin-preview-position")).to_have_text("1/2")
    expect(page.locator(".lf-margin-thread")).not_to_contain_text(
        "A second reading arrived while the preview was pinned."
    )
    page.get_by_role("button", name="Next thread").click()
    expect(page.locator(".lf-margin-preview-position")).to_have_text("2/2")
    expect(page.locator(".lf-margin-thread")).to_contain_text(
        "A second reading arrived while the preview was pinned."
    )


CELL_TARGET_PAGE = leaf_page(
    "a comment in a table's last column",
    """
<h1 id="t">Phases</h1>
<p id="before">A paragraph above the table.</p>
<table id="phases">
<thead><tr><th>Phase</th><th>Contents</th><th>Choice</th></tr></thead>
<tbody>
<tr id="phase-1"><td>1</td><td>Maintainer instructions rewritten.</td><td>Committed</td></tr>
<tr id="phase-2"><td>2</td><td>Agent instructions rewritten.</td><td>Delivery depth</td></tr>
</tbody>
</table>
""",
)


def test_resolving_a_cells_thread_rings_the_whole_cell(browser, serve):
    """Resolving from the card hands the user to the thread's target, here a cell in
    the table's last column. The table clips to its own edges, which that cell stands
    flush with, so the ring it wears there has to be whole inside the table."""
    page = open_page(
        browser,
        serve(
            CELL_TARGET_PAGE,
            events=[_comment_on("phase-2", quote="Delivery depth")],
        ),
    )
    resized(page, 1440, 900)
    page.keyboard.press("Tab")  # keyboard modality, so the landing's ring is drawn
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    marker.focus()
    page.keyboard.press("Enter")
    preview = page.locator(".lf-margin-preview")
    expect(preview.locator(".lf-page-thread")).to_be_focused()

    page.keyboard.press("r")
    expect(preview).to_be_hidden()
    cell = page.locator("#phase-2 > td").last
    expect(cell).to_be_focused()
    ring = current_location_ring(page)
    assert ring, "the cell the user is located on wears no ring"
    assert ring["cuts"] == [], ring["cuts"]


def test_open_in_panel_moves_the_cards_thread_and_its_reply_to_the_panel(
    browser, serve
):
    """A card's Open in panel closes the card and opens its thread in the panel's view,
    the reply being written there along with it, and Show on page brings both back."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=LONG_THREAD))
    resized(page, 1440, 900)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    reply = preview.locator(".lf-thread-reply leaf-text")
    reply.click()
    page.keyboard.type("Halfway through a reply")

    preview.get_by_role("button", name="Open in panel").click()
    expect(preview).to_be_hidden()
    panel_settled(page, view="thread")
    expect(page.locator(PANEL_THREAD)).to_contain_text("Start with the first two.")
    expect(panel_field(page)).to_have_js_property("value", "Halfway through a reply")

    page.locator(PANEL).get_by_role("button", name="Show on page").click()
    expect(preview).to_be_visible()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    expect(reply).to_have_js_property("value", "Halfway through a reply")
