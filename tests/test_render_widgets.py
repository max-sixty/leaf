"""Board, suggestion, ask, and widget composition tests."""

import re
from itertools import pairwise
from pathlib import Path

import pytest
from interact_support import append_command
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf import render_checks as render_checks_model
from leaf.render_gate import version as render_gate_model
from playwright.sync_api import expect
from render_support import (
    ADDRESS_PAGE,
    ALL_ASKS_IN_ORDER,
    ASK_IN_A_CARD_PAGE,
    ASK_ROW_SAYS,
    ASK_WITH_CONTEXT_PAGE,
    ASKS_IN_A_ROW_PAGE,
    ASKS_IN_ORDER,
    ASKS_PAGE,
    BAD_CHART_PAGE,
    BOARD_PAGE,
    BOTH_STAMPS,
    CHANGE_SHAPES_PAGE,
    CHART_COLLISIONS,
    CHART_IN_A_MESSAGE_PAGE,
    CHART_MARKS,
    CHART_MARKUP,
    CHART_PAGE,
    CHIP_PAGE,
    COLLAPSED_PAGE,
    CONVERSATION_DIFF_PAGE,
    CROWDED_CHART_PAGE,
    DIFF_CLIPPING,
    DIFF_LANDING,
    DIFF_PRESS,
    DIFF_ROW_PLACEMENT,
    HOLD_MOTION,
    LONG_LINE_DIFF_PAGE,
    LONG_PAGE,
    MANIFEST_DIFF_PAGE,
    MESSAGE_ROOM_PAGE,
    MULTI_HUNK_PATCH,
    PROPOSED_PAGE,
    REBUILT_INLINE_PAGE,
    RENDERED,
    REPLY_HOST_PAGE,
    ROOM_HELD,
    ROOM_WIDGETS,
    ROOMS,
    SCROLL_SETTLE_MS,
    SCROLL_SETTLED,
    SHORT_SUGGESTION,
    STANDING_ASK,
    SUGGESTION_IN_CONTEXT_PAGE,
    SUGGESTION_PAGE,
    SWAP_PAGE,
    CutOff,
    actions,
    banner_address,
    compare_with,
    holding,
    key_line,
    leaf_page,
    live_url,
    open_page,
    panel_settled,
    post_event,
    refuse,
    resized,
    round_trip,
    select,
    sent_events,
    stamp_version_file,
    told,
    undo,
    unfolded_button,
    wait_for_revision,
)

pytestmark = pytest.mark.nightly

SWIPE_PAGE = leaf_page(
    "session backlog triage",
    """
<h1>Session-store follow-ups</h1>
<lf-ask id="session-triage-decision">
  <h2>Which session-store follow-ups should we keep?</h2>
  <p>Pass removes an item from this design; Keep carries it into implementation.</p>
  <lf-swipe-deck id="session-triage">
    <lf-swipe-pile id="session-queue" verdict="unseen">
      <lf-swipe-card id="swipe-a"><strong>Buffer rolling expiry</strong><p>Refresh once a minute.</p></lf-swipe-card>
      <lf-swipe-card id="swipe-b"><strong>Bound fallback lifetime</strong><p>Refuse snapshots after 90 seconds.</p></lf-swipe-card>
      <lf-swipe-card id="swipe-c"><strong>Partition capacity</strong><p>Separate rate-limit eviction.</p></lf-swipe-card>
      <lf-swipe-card id="swipe-d"><strong>Index account sessions</strong><p>Make device-wide revocation bounded.</p></lf-swipe-card>
    </lf-swipe-pile>
    <lf-swipe-pile id="session-pass" verdict="pass">
      <lf-swipe-card id="already-passed"><strong>Add Dynamo</strong><p>A new operating model.</p></lf-swipe-card>
    </lf-swipe-pile>
    <lf-swipe-pile id="session-keep" verdict="keep">
      <lf-swipe-card id="already-kept"><strong>Delete session keys</strong><p>The revocation primitive.</p></lf-swipe-card>
    </lf-swipe-pile>
  </lf-swipe-deck>
</lf-ask>
""",
)


def test_a_milestone_marker_is_centred_on_its_title(browser, serve):
    source = leaf_page(
        "milestone marker alignment",
        """
<h1>Release plan</h1>
<style>#rail { width: 160px; }</style>
<lf-milestones id="rail">
  <lf-milestone id="publish" status="active"><strong>Publish the release after validation</strong></lf-milestone>
</lf-milestones>
""",
    )
    page, errors = open_page(browser, serve(source))
    centres = page.locator("#publish").evaluate(
        """item => {
          const titleNode = item.querySelector(':scope > strong');
          const title = titleNode.getBoundingClientRect();
          const lineHeight = parseFloat(getComputedStyle(titleNode).lineHeight);
          const box = item.getBoundingClientRect();
          const marker = getComputedStyle(item, '::before');
          const border = marker.boxSizing === 'content-box'
            ? parseFloat(marker.borderTopWidth) + parseFloat(marker.borderBottomWidth)
            : 0;
          return {
            title: title.top + lineHeight / 2,
            titleLines: title.height / lineHeight,
            marker: box.top + parseFloat(marker.top)
              + (parseFloat(marker.height) + border) / 2,
          };
        }"""
    )
    assert centres["titleLines"] >= 2, centres
    assert centres["marker"] == pytest.approx(centres["title"], abs=0.5), centres
    assert errors == []
    page.close()


def test_suggestions_sharing_a_block_keep_source_and_keyboard_order(browser, serve):
    """Hoisted decision rows keep source order through upgrade and reconnection."""
    source = leaf_page(
        "suggestion-order",
        """
<h1>Release wording</h1>
<section id="shared-block">
  <p>First <lf-suggestion id="first-change"><lf-new>first proposal</lf-new></lf-suggestion>.</p>
  <p>Second <lf-suggestion id="second-change"><lf-new>second proposal</lf-new></lf-suggestion>.</p>
  <p>Third <lf-suggestion id="third-change"><lf-new>third proposal</lf-new></lf-suggestion>.</p>
</section>
""",
    )
    page, errors = open_page(browser, serve(source))
    expect(page.locator(".lf-sug-actions")).to_have_count(3)
    assert page.locator(".lf-sug-actions").evaluate_all(
        "rows => rows.map(row => row.dataset.lfFor)"
    ) == ["first-change", "second-change", "third-change"]
    page.locator("#first-change").evaluate(
        "el => { const parent = el.parentNode; const next = el.nextSibling;"
        "        el.remove(); document.dispatchEvent(new Event('lf-actions'));"
        "        parent.insertBefore(el, next); }"
    )
    assert page.locator(".lf-sug-actions").evaluate_all(
        "rows => rows.map(row => row.dataset.lfFor)"
    ) == [
        "first-change",
        "second-change",
        "third-change",
    ], "reconnecting the first suggestion moved its controls after later source rows"
    first_accept = page.locator("[data-lf-for='first-change'] .lf-sug-accept")
    first_accept.evaluate(
        "control => { control.setAttribute('aria-disabled', 'true');"
        "  document.dispatchEvent(new Event('lf-actions')); }"
    )
    expect(first_accept).to_have_attribute("aria-disabled", "false")
    page.locator("[data-lf-for='first-change'] .lf-sug-accept").focus()
    walked = []
    for _ in range(3):
        walked.append(
            page.evaluate(
                "() => document.activeElement.closest('.lf-sug-actions')?.dataset.lfFor"
            )
        )
        # Each row has two decision controls, and the roving semantic marker now joins
        # them in the same item. Walk past whichever row currently owns that one stop.
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        if page.locator(":focus").evaluate("el => el.matches('.lf-margin-marker')"):
            page.keyboard.press("Tab")
    assert walked == ["first-change", "second-change", "third-change"]
    assert errors == []
    page.close()


def test_a_detached_board_releases_and_restores_its_lifecycle(browser, serve):
    """Version replacement releases board resources and restores pointer dragging."""
    context = browser.new_context(viewport={"width": 1000, "height": 800})
    context.add_init_script(
        """(() => {
          window.__lfMotionListeners = {added: 0, removed: 0};
          const add = MediaQueryList.prototype.addEventListener;
          const remove = MediaQueryList.prototype.removeEventListener;
          MediaQueryList.prototype.addEventListener = function(type, listener, options) {
            if (type === 'change' && this.media === '(prefers-reduced-motion: reduce)')
              window.__lfMotionListeners.added++;
            return add.call(this, type, listener, options);
          };
          MediaQueryList.prototype.removeEventListener = function(type, listener, options) {
            if (type === 'change' && this.media === '(prefers-reduced-motion: reduce)')
              window.__lfMotionListeners.removed++;
            return remove.call(this, type, listener, options);
          };
        })()"""
    )
    try:
        page, errors = open_page(browser, serve(BOARD_PAGE), context=context)
        cdp = context.new_cdp_session(page)
        page.evaluate(
            """async () => {
              window.__lfSortablePrototype =
                (await import('/vendor/sortable.esm.js')).default.prototype;
            }"""
        )

        def sortable_count():
            # Keep the query handles in a disposable group. In particular, the probe
            # must not become the new owner of the DOM it is checking.
            group = "board-lifecycle-probe"
            prototype = cdp.send(
                "Runtime.evaluate",
                {
                    "expression": "window.__lfSortablePrototype",
                    "returnByValue": False,
                    "objectGroup": group,
                },
            )["result"]["objectId"]
            try:
                objects = cdp.send(
                    "Runtime.queryObjects",
                    {"prototypeObjectId": prototype, "objectGroup": group},
                )["objects"]["objectId"]
                return cdp.send(
                    "Runtime.callFunctionOn",
                    {
                        "objectId": objects,
                        "functionDeclaration": "function () { return this.length; }",
                        "returnByValue": True,
                    },
                )["result"]["value"]
            finally:
                cdp.send("Runtime.releaseObjectGroup", {"objectGroup": group})

        before = page.evaluate("() => ({...window.__lfMotionListeners})")
        assert sortable_count() == 2
        page.evaluate(
            """() => {
              window.__lfDetachedBoard = document.querySelector('lf-board');
              window.__lfDetachedBoard.remove();
            }"""
        )
        released = page.evaluate("() => ({...window.__lfMotionListeners})")
        assert released["removed"] > before["removed"], (
            f"detaching the board retained its motion listener: {before=}, {released=}"
        )
        cdp.send("HeapProfiler.collectGarbage")
        assert sortable_count() == 0, (
            "detaching the board retained its Sortable instances"
        )
        page.evaluate(
            "() => document.querySelector('main').append(window.__lfDetachedBoard)"
        )
        restored = page.evaluate("() => ({...window.__lfMotionListeners})")
        assert restored["added"] > before["added"], (
            f"reconnecting the board did not restore live motion changes: {restored=}"
        )
        assert sortable_count() == 2

        grip = page.locator("#card-heater .lf-grip").bounding_box()
        dest = page.locator("#col-done").bounding_box()
        page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
        page.mouse.down()
        page.mouse.move(
            dest["x"] + dest["width"] / 2,
            dest["y"] + dest["height"] / 2,
            steps=15,
        )
        page.mouse.up()
        page.wait_for_selector("#col-done #card-heater")
        assert errors == []
    finally:
        if "cdp" in locals():
            cdp.detach()
        context.close()


def test_live_widget_watchers_release_and_reconnect(browser, serve):
    """Live widget feeds release detached owners and call them after reconnection."""
    source = leaf_page(
        "widget watcher lifecycle",
        """
<section id="watched">
  <p><lf-suggestion id="watched-suggestion"><lf-old>old</lf-old><lf-new>new</lf-new></lf-suggestion></p>
  <lf-draft id="watched-draft"><pre>Draft words.</pre></lf-draft>
  <lf-roster id="watched-roster">
    <lf-agent id="watched-agent" state="working"><strong>worker</strong> Working.</lf-agent>
  </lf-roster>
  <lf-record id="watched-record"></lf-record>
</section>
""",
    )
    context = browser.new_context(viewport={"width": 1000, "height": 800})
    context.add_init_script(
        """(() => {
          const add = EventTarget.prototype.addEventListener;
          const remove = EventTarget.prototype.removeEventListener;
          const watched = new Set(['lf-actions', 'lf-drafts']);
          const wrappers = new Map();
          window.__lfWatchers = {
            added: Object.create(null),
            removed: Object.create(null),
            calls: Object.create(null),
          };
          for (const type of watched) {
            window.__lfWatchers.added[type] = 0;
            window.__lfWatchers.removed[type] = 0;
            window.__lfWatchers.calls[type] = 0;
          }
          EventTarget.prototype.addEventListener = function(type, listener, options) {
            if (this !== document || !watched.has(type) || typeof listener !== 'function')
              return add.call(this, type, listener, options);
            const wrapped = function(...args) {
              window.__lfWatchers.calls[type]++;
              return listener.apply(this, args);
            };
            let byType = wrappers.get(type);
            if (!byType) wrappers.set(type, byType = new Map());
            byType.set(listener, wrapped);
            window.__lfWatchers.added[type]++;
            return add.call(this, type, wrapped, options);
          };
          EventTarget.prototype.removeEventListener = function(type, listener, options) {
            if (this !== document || !watched.has(type) || typeof listener !== 'function')
              return remove.call(this, type, listener, options);
            const wrapped = wrappers.get(type)?.get(listener) ?? listener;
            window.__lfWatchers.removed[type]++;
            return remove.call(this, type, wrapped, options);
          };
        })()"""
    )
    try:
        page, errors = open_page(browser, serve(source), context=context)
        initial = page.evaluate("() => structuredClone(window.__lfWatchers)")
        initial_actions = (
            initial["added"]["lf-actions"] - initial["removed"]["lf-actions"]
        )
        initial_drafts = initial["added"]["lf-drafts"] - initial["removed"]["lf-drafts"]
        assert initial_actions >= 4
        assert initial_drafts >= 1

        page.evaluate(
            """() => {
              window.__lfWatchedSection = document.querySelector('#watched');
              window.__lfWatchedSection.remove();
            }"""
        )
        released = page.evaluate("() => structuredClone(window.__lfWatchers)")
        released_actions = (
            released["added"]["lf-actions"] - released["removed"]["lf-actions"]
        )
        released_drafts = (
            released["added"]["lf-drafts"] - released["removed"]["lf-drafts"]
        )
        assert released_actions == initial_actions - 4
        assert released_drafts == initial_drafts - 1
        released_calls = page.evaluate(
            """() => {
              const before = structuredClone(window.__lfWatchers.calls);
              document.dispatchEvent(new Event('lf-actions'));
              document.dispatchEvent(new CustomEvent('lf-drafts', {
                detail: {ctx: 'edit:watched-draft', value: null},
              }));
              return {
                actions: window.__lfWatchers.calls['lf-actions'] - before['lf-actions'],
                drafts: window.__lfWatchers.calls['lf-drafts'] - before['lf-drafts'],
              };
            }"""
        )
        assert released_calls == {
            "actions": released_actions,
            "drafts": released_drafts,
        }

        page.evaluate(
            "() => document.querySelector('main').append(window.__lfWatchedSection)"
        )
        restored = page.evaluate("() => structuredClone(window.__lfWatchers)")
        restored_actions = (
            restored["added"]["lf-actions"] - restored["removed"]["lf-actions"]
        )
        restored_drafts = (
            restored["added"]["lf-drafts"] - restored["removed"]["lf-drafts"]
        )
        assert restored_actions == initial_actions
        assert restored_drafts == initial_drafts
        restored_calls = page.evaluate(
            """() => {
              const before = structuredClone(window.__lfWatchers.calls);
              document.dispatchEvent(new Event('lf-actions'));
              document.dispatchEvent(new CustomEvent('lf-drafts', {
                detail: {ctx: 'edit:watched-draft', value: null},
              }));
              return {
                actions: window.__lfWatchers.calls['lf-actions'] - before['lf-actions'],
                drafts: window.__lfWatchers.calls['lf-drafts'] - before['lf-drafts'],
              };
            }"""
        )
        assert restored_calls == {
            "actions": restored_actions,
            "drafts": restored_drafts,
        }
        assert errors == []
    finally:
        context.close()


def test_a_table_of_contents_reads_the_page_outline_and_reveals_its_heading(
    browser, serve
):
    """The authored element is only a request for navigation. The module reads the
    page's headings in document order, keeps their relative depth, and gives an
    id-less heading a generated target without writing state onto the heading itself.
    A real fragment link lets the browser reveal a heading in a closed disclosure, so
    it is reachable rather than merely named."""
    source = leaf_page(
        "contents",
        """
<h1>Migration plan</h1>
<lf-toc id="contents"></lf-toc>
<section><h2 id="prepare">Prepare <lf-gloss tip="One cohort at a time.">gradually</lf-gloss></h2><p>Take a snapshot.</p></section>
<details style="margin-top: 110vh">
  <summary>Implementation detail</summary>
  <h3>Move the readers</h3>
  <p>Shift one cohort at a time.</p>
</details>
<section style="margin-bottom: 110vh"><h2>Verify</h2><p>Compare the totals.</p></section>
""",
    )
    url = serve(source)
    page, errors = open_page(browser, url)
    toc = page.get_by_role("navigation", name="On this page")

    expect(toc.get_by_role("link")).to_have_count(3)
    assert toc.get_by_role("link").all_text_contents() == [
        "Prepare gradually",
        "Move the readers",
        "Verify",
    ]
    assert toc.locator("li").evaluate_all(
        "nodes => nodes.map(node => node.dataset.lfDepth)"
    ) == ["0", "1", "0"]
    assert page.locator("h2, h3").evaluate_all(
        "nodes => nodes.map(node => node.getAttribute('id'))"
    ) == ["prepare", None, None]

    hrefs = toc.get_by_role("link").evaluate_all(
        "links => links.map(link => link.getAttribute('href'))"
    )
    assert hrefs[0] == "#prepare"
    assert hrefs[1].startswith("#lf-contents-section-")
    target = page.locator(hrefs[1])
    expect(target).to_have_attribute("data-lf-gen", "1")
    expect(target).to_have_class(re.compile(r"\blf-ui\b"))

    # A generated fragment target must not trap the heading's collapsed top margin
    # inside an otherwise transparent section. The section, target, and first visible
    # heading should begin at the same rendered edge.
    verify_geometry = page.get_by_role("heading", name="Verify").evaluate(
        """heading => {
          const section = heading.parentElement;
          const target = heading.previousElementSibling;
          return {
            sectionTop: section.getBoundingClientRect().top,
            targetTop: target.getBoundingClientRect().top,
            headingTop: heading.getBoundingClientRect().top,
          };
        }"""
    )
    assert max(verify_geometry.values()) - min(verify_geometry.values()) < 0.5, (
        verify_geometry
    )

    details = page.locator("details")
    expect(details).not_to_have_attribute("open", "")
    toc.get_by_role("link", name="Move the readers").click()
    expect(details).to_have_attribute("open", "")
    expect(page.locator(":target")).to_have_attribute("id", hrefs[1][1:])
    expect(page).to_have_url(re.compile(f"{re.escape(hrefs[1])}$"))
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)
    top = page.locator("h3").evaluate("heading => heading.getBoundingClientRect().top")
    assert 0 <= top < 150, f"the revealed heading stopped at {top}px"

    # The title is a visible page label, while each repeated heading is the label of a
    # browser-owned link under .lf-ui. The authored heading remains the one passage.
    spoken = page.locator("main").evaluate(
        "async main => (await import('/runtime/widget-api.js')).says(main)"
    )
    assert spoken.count("Prepare gradually") == 1
    assert spoken.count("Move the readers") == 1
    assert spoken.count("Verify") == 1
    expect(toc).to_have_class(re.compile(r"\blf-ui\b"))
    expect(toc).to_have_attribute("data-lf-gen", "1")
    assert errors == []
    page.close()

    # On first parse this id does not exist yet. The shared arrival pass runs after every
    # widget settles, so a copied link still reveals and reaches the generated target.
    direct, direct_errors = open_page(browser, url + hrefs[1])
    expect(direct.locator("details")).to_have_attribute("open", "")
    expect(direct).to_have_url(re.compile(f"{re.escape(hrefs[1])}$"))
    direct.wait_for_function(
        "heading => { const box = heading.getBoundingClientRect(); "
        "return box.top >= 0 && box.bottom <= innerHeight; }",
        arg=direct.locator("h3").element_handle(),
    )
    assert direct.locator("h3").evaluate(
        "heading => { const box = heading.getBoundingClientRect(); "
        "return box.top >= 0 && box.bottom <= innerHeight; }"
    )
    assert direct_errors == []
    direct.close()


def test_an_eyebrow_and_heading_keep_one_title_rhythm_through_contents(browser, serve):
    """An eyebrow is the heading's label, so its small bottom margin is the room inside
    the title while the heading level's larger top margin remains outside the pair.

    The contents widget inserts a zero-height fragment target before an id-less heading.
    That generated node must not split the same authored pair into a different layout."""
    source = leaf_page(
        "eyebrow title rhythm",
        """
<h1>Two labeled sections</h1>
<lf-toc id="contents"></lf-toc>
<p id="before-two">First section follows.</p>
<section id="section-two">
  <p class="eyebrow">release shape</p>
  <h2 id="title-two">Prepare the readers</h2>
  <p>Take a snapshot.</p>
</section>
<p id="before-three">A subsection follows.</p>
<section id="section-three">
  <p class="eyebrow">first cohort</p>
  <h3>Move the readers</h3>
  <p>Shift one cohort at a time.</p>
</section>
""",
    )
    page, errors = open_page(browser, serve(source))
    rhythm = page.evaluate(
        """() => Object.fromEntries([
          ['h2', ['section-two', 'before-two']],
          ['h3', ['section-three', 'before-three']],
        ].map(([level, [sectionId, beforeId]]) => {
          const section = document.getElementById(sectionId);
          const eyebrow = section.querySelector(':scope > .eyebrow');
          const heading = section.querySelector(`:scope > ${level}`);
          const before = document.getElementById(beforeId);
          const between = [];
          for (let node = eyebrow.nextElementSibling; node !== heading;
               node = node.nextElementSibling) between.push(node.className);
          const eyebrowBox = eyebrow.getBoundingClientRect();
          const headingBox = heading.getBoundingClientRect();
          return [level, {
            outer: eyebrowBox.top - before.getBoundingClientRect().bottom,
            inner: headingBox.top - eyebrowBox.bottom,
            between,
          }];
        }))"""
    )
    assert rhythm == {
        "h2": {"outer": 48, "inner": 10, "between": []},
        "h3": {
            "outer": 32,
            "inner": 10,
            "between": ["lf-toc-target lf-ui"],
        },
    }
    assert errors == []
    page.close()


def test_table_of_contents_history_is_native_back_and_forward(browser, serve):
    """A map link creates an ordinary fragment-history entry on the root scrollport.

    Back restores the reading position from before the click and Forward restores the
    fragment destination. Leaf keeps no competing pixel history and :target remains the
    browser's state throughout."""
    source = leaf_page(
        "native contents history",
        """
<h1>Migration plan</h1>
<aside class="sidebar"><lf-toc id="history-contents"></lf-toc></aside>
<section><h2 id="prepare">Prepare the readers</h2><div style="height: 900px"></div></section>
<section><h2 id="move">Move the readers</h2><div style="height: 900px"></div></section>
<section><h2 id="verify">Verify the readers</h2><div style="height: 600px"></div></section>
""",
    )
    page, errors = open_page(browser, serve(source))
    resized(page, 1400, 800)
    assert page.evaluate("history.scrollRestoration") == "auto"

    bookmark = 420
    page.evaluate(
        "top => document.scrollingElement.scrollTo({top, behavior: 'instant'})",
        bookmark,
    )
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 1", arg=bookmark
    )
    navigation = page.get_by_role("navigation", name="On this page")
    move = navigation.get_by_role("link", name="Move the readers")
    navigation.hover()
    expect(move).to_have_css("pointer-events", "auto")
    move.click()
    expect(page).to_have_url(re.compile(r"#move$"))
    expect(page.locator(":target")).to_have_attribute("id", "move")
    page.wait_for_function(
        "() => document.getElementById('move').getBoundingClientRect().top < 150"
    )
    destination = page.evaluate("document.scrollingElement.scrollTop")
    assert destination > bookmark + 400

    page.evaluate("history.back()")
    page.wait_for_function("() => location.hash === ''")
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2", arg=bookmark
    )
    assert page.locator(":target").count() == 0

    page.evaluate("history.forward()")
    page.wait_for_function("() => location.hash === '#move'")
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2",
        arg=destination,
    )
    expect(page.locator(":target")).to_have_attribute("id", "move")
    assert errors == []
    page.close()


def test_a_margin_table_of_contents_maps_the_document_until_the_reader_enters_it(
    browser, serve
):
    """The roomy margin is a stable reading map rather than a compressed outline.

    Section rows divide the available height according to the content they lead, a
    moving lens shows the visible band, and late content growth redraws both. Labels
    reveal without moving the map or changing the item under the pointer. The same
    links remain an ordinary open outline where the margin posture is unavailable."""
    source = leaf_page(
        "contents map",
        """
<h1>Migration plan for the readers already in flight</h1>
<style>
  html { scroll-behavior: smooth; }
  #capacity, #limits { margin-block: 0; }
</style>
<div id="orientation" style="height: 420px"></div>
<aside class="sidebar" id="route"><lf-toc id="contents"></lf-toc></aside>
<section><h2 id="prepare">Prepare the copy without moving the active readers</h2><p>Take a snapshot.</p></section>
<div style="height: 90px"></div>
<section>
  <h3 id="capacity">Check capacity before opening the longer transfer window</h3>
  <h3 id="limits">Confirm the limits without moving the waiting readers</h3>
  <p>Leave room for both copies.</p>
</section>
<div id="late-content" style="height: 180px"></div>
<section><h2 id="move">Move each cohort while preserving its reading position</h2><p>Shift one cohort at a time.</p></section>
<div style="height: 640px"></div>
<section><h2 id="verify">Verify both readings before releasing the original copy</h2><p>Compare the totals.</p></section>
<div style="height: 360px"></div>
""",
    )
    url = serve(source)
    page, errors = open_page(browser, url)
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page")
    toc = page.locator("#contents")
    start = nav.locator(".lf-toc-start a")
    prepare = nav.get_by_role("link", name="Prepare the copy", exact=False)
    capacity = nav.get_by_role("link", name="Check capacity", exact=False)
    limits = nav.get_by_role("link", name="Confirm the limits", exact=False)
    verify = nav.get_by_role("link", name="Verify both readings", exact=False)
    page.mouse.move(1200, 700)
    # Every row says its own word as text, the start row included. Its word used to be an
    # attribute the rail form drew with `content: attr()`, which left the link that names
    # the whole document saying nothing at all to any reading that asks a link what it
    # says — the accessible name it falls back to, a text dump, the widget's own outline.
    said = nav.locator("a").evaluate_all(
        "links => links.map(a => a.textContent.trim())"
    )
    assert said and all(said), f"a contents row carries no words: {said}"
    expect(start).to_have_text("Migration plan for the readers already in flight")
    expect(start).to_have_attribute("href", re.compile(r"^#lf-contents-section-0"))
    expect(start).to_have_attribute("aria-current", "location")
    expect(toc).to_have_css("position", "fixed")
    expect(page.locator("aside.sidebar")).to_have_css("position", "sticky")
    expect(prepare).to_have_css("opacity", "0")
    expect(prepare).to_have_css("pointer-events", "none")
    motion = prepare.evaluate(
        "node => { const s = getComputedStyle(node); "
        "return {property: s.transitionProperty, duration: s.transitionDuration, "
        "timing: s.transitionTimingFunction}; }"
    )
    assert motion == {
        "property": "color, opacity",
        "duration": "0.12s, 0.24s",
        "timing": "ease-out, ease-out",
    }
    nav_box = nav.bounding_box()
    assert nav_box is not None
    assert 23 <= nav_box["x"] <= 25
    assert 64 <= nav_box["y"] <= 68
    assert nav_box["height"] >= 790, f"the reading map used only {nav_box['height']}px"
    assert abs(nav_box["y"] + nav_box["height"] - 876) <= 1
    prepare_box = page.locator("#prepare").bounding_box()
    assert prepare_box is not None
    assert nav_box["width"] == pytest.approx(292, abs=1)
    assert prepare_box["x"] - nav_box["x"] - nav_box["width"] == pytest.approx(
        24, abs=1
    )

    resized(page, 1800, 900)
    expect(nav).to_have_css("width", "320px")
    resized(page, 1152, 900)
    expect(nav).to_have_css("width", "240px")
    resized(page, 1400, 900)
    assert nav.bounding_box() == nav_box
    markers = nav.locator(".lf-toc-start, li").evaluate_all(
        """items => items.map(item => {
          const style = getComputedStyle(item, '::before');
          const box = item.getBoundingClientRect();
          return {content: style.content, width: style.width, height: style.height,
                  color: style.backgroundColor, x: box.x + parseFloat(style.left),
                  y: box.y + parseFloat(style.top)};
        })"""
    )
    assert markers[0]["content"] == '""' and markers[0]["width"] == "3px"
    assert markers[0]["color"] != "rgba(0, 0, 0, 0)"
    assert len({round(marker["x"]) for marker in markers}) == 1
    assert markers[-1]["y"] > nav_box["y"] + nav_box["height"] * 0.68
    assert markers[4]["y"] - markers[3]["y"] > markers[3]["y"] - markers[2]["y"]

    # The marker rows remain an exact scale of the document even where two nearby,
    # two-line labels need more room than the sections they name. The labels move aside
    # without overlapping; they do not make those short rows taller.
    map_layout = nav.locator(".lf-toc-rows").evaluate(
        """rows => {
          const track = rows.getBoundingClientRect();
          const items = [...rows.querySelectorAll('.lf-toc-start, li')];
          const spans = items.map(item =>
            Number(item.style.getPropertyValue('--lf-toc-span')));
          const total = spans.reduce((sum, span) => sum + span, 0);
          let before = 0;
          return items.map((item, index) => {
            const row = item.getBoundingClientRect();
            const label = item.querySelector(':scope > a').getBoundingClientRect();
            const expected = track.top + track.height * before / total;
            before += spans[index];
            return {rowTop: row.top, rowHeight: row.height, expected,
                    labelTop: label.top, labelBottom: label.bottom,
                    labelHeight: label.height};
          });
        }"""
    )
    assert all(
        item["rowTop"] == pytest.approx(item["expected"], abs=1) for item in map_layout
    )
    assert capacity.evaluate(
        "node => node.parentElement.getBoundingClientRect().height "
        "< node.getBoundingClientRect().height"
    )
    capacity_label = capacity.bounding_box()
    limits_label = limits.bounding_box()
    assert capacity_label is not None and limits_label is not None
    assert capacity_label["y"] + capacity_label["height"] <= limits_label["y"] + 1

    # The start row and top-level sections share one typographic edge. Depth changes
    # indentation, never the spine or the marker position.
    text_edge = (
        "node => node.getBoundingClientRect().x "
        "+ parseFloat(getComputedStyle(node).paddingLeft)"
    )
    assert abs(start.evaluate(text_edge) - prepare.evaluate(text_edge)) <= 1
    assert capacity.evaluate(text_edge) > prepare.evaluate(text_edge) + 7
    title_type = start.evaluate(
        "node => { const s = getComputedStyle(node); "
        "return {family: s.fontFamily, caps: s.fontVariantCaps}; }"
    )
    section_type = prepare.evaluate(
        "node => { const s = getComputedStyle(node); "
        "return {family: s.fontFamily, caps: s.fontVariantCaps}; }"
    )
    assert title_type == {**section_type, "caps": "normal"}
    expect(prepare).to_have_css("-webkit-line-clamp", "2")

    lens = nav.locator(".lf-toc-window")
    lens_before = lens.bounding_box()
    assert lens_before is not None
    assert 14 <= lens_before["height"] < nav_box["height"]

    # A Mermaid render, image load, disclosure, or other late block can change the
    # document after upgrade. Growing one such block must move the later sections in
    # the map without changing the rail's own box.
    move_before = markers[4]["y"]
    page.locator("#late-content").evaluate("node => { node.style.height = '580px'; }")
    page.wait_for_function(
        "before => { const item = document.querySelector('a[href=\"#move\"]').parentElement; "
        "const style = getComputedStyle(item, '::before'); "
        "return item.getBoundingClientRect().y + parseFloat(style.top) > before + 20; }",
        arg=move_before,
    )
    assert nav.bounding_box() == nav_box
    hidden_boxes = nav.locator(".lf-toc-start, li, a").evaluate_all(
        "nodes => nodes.map(node => { const r = node.getBoundingClientRect(); "
        "return [r.x, r.y, r.width, r.height]; })"
    )

    # The go-to menu reveals the same labels without moving focus into the rail.
    page.keyboard.press("g")
    for link in nav.locator("a").all():
        expect(link).to_have_css("opacity", "1")
        expect(link).to_have_css("pointer-events", "auto")
    assert (
        nav.locator(".lf-toc-start, li, a").evaluate_all(
            "nodes => nodes.map(node => { const r = node.getBoundingClientRect(); "
            "return [r.x, r.y, r.width, r.height]; })"
        )
        == hidden_boxes
    )
    assert nav.evaluate("node => !node.contains(document.activeElement)")
    page.keyboard.press("h")
    expect(prepare).to_have_css("opacity", "1")
    page.keyboard.press("Escape")
    expect(prepare).to_have_css("opacity", "1")
    page.keyboard.press("Escape")
    expect(prepare).to_have_css("opacity", "0")
    expect(prepare).to_have_css("pointer-events", "none")

    prepare.evaluate(
        "node => node.addEventListener('pointerdown', () => { window.lfTocPressed = true; }, { once: true })"
    )
    prepare_box = prepare.bounding_box()
    assert prepare_box is not None
    before_hash = page.evaluate("location.hash")
    page.mouse.click(prepare_box["x"] + 4, prepare_box["y"] + 4)
    assert page.evaluate("location.hash") == before_hash
    assert page.evaluate("window.lfTocPressed") is None
    expect(prepare).to_have_css("opacity", "1")
    expect(prepare).to_have_css("pointer-events", "auto")
    revealed_boxes = nav.locator(".lf-toc-start, li, a").evaluate_all(
        "nodes => nodes.map(node => { const r = node.getBoundingClientRect(); "
        "return [r.x, r.y, r.width, r.height]; })"
    )
    assert revealed_boxes == hidden_boxes

    # The viewport rail stays put through the whole document, including where its
    # authored sidebar has not reached the sticky edge yet and where main ends.
    for position in (0, 750, 10_000):
        page.evaluate(
            "top => document.scrollingElement.scrollTo({top, behavior: 'instant'})",
            position,
        )
        assert nav.bounding_box() == nav_box

    # A wheel over the rail stays in the document's native scroll chain.
    page.evaluate("document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})")
    page.mouse.move(nav_box["x"] + nav_box["width"] / 2, nav_box["y"] + 300)
    page.mouse.wheel(0, 260)
    page.wait_for_function("() => document.scrollingElement.scrollTop >= 250")
    page.mouse.wheel(0, 260)
    page.mouse.wheel(0, 260)
    page.wait_for_function("() => document.scrollingElement.scrollTop >= 750")
    assert page.locator("aside.sidebar").evaluate("node => node.scrollTop") == 0

    # Map travel keeps the reader oriented rather than teleporting. This records the
    # browser's actual scroll sequence; it does not make a duration claim.
    page.evaluate(
        "() => { document.scrollingElement.scrollTo({top: 0, behavior: 'instant'}); "
        "window.lfTocFrames = []; "
        "const sample = () => { window.lfTocFrames.push(document.scrollingElement.scrollTop); "
        "if (window.lfTocFrames.length < 90) requestAnimationFrame(sample); }; "
        "requestAnimationFrame(sample); }"
    )
    verify.click()
    expect(page).to_have_url(re.compile(r"#verify$"))
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)
    frames = page.evaluate("window.lfTocFrames")
    travelled = [position for position in frames if position > 0]
    assert len({round(position) for position in travelled}) >= 3, frames
    assert all(left <= right for left, right in pairwise(travelled)), frames

    start_href = start.get_attribute("href")
    assert start_href is not None
    start.click()
    expect(page).to_have_url(re.compile(rf"{re.escape(start_href)}$"))
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)
    expect(page.locator(":target")).to_have_attribute("id", start_href[1:])
    assert (
        page.locator(start_href).evaluate("node => node.getBoundingClientRect().top")
        < 150
    )

    page.evaluate("document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})")
    prepare.click()
    expect(page).to_have_url(re.compile(r"#prepare$"))
    expect(prepare).to_have_attribute("aria-current", "location")
    after_navigation = nav.bounding_box()
    assert after_navigation is not None
    assert after_navigation == nav_box, "following a link moved the contents rail"
    assert prepare.evaluate("node => node.matches(':hover')")

    # The lens is the viewport's position, not a destination travelling toward it.
    # Capture the first style turn after the scroll: a transition can finish at the
    # right place while still trailing every intermediate reading.
    page.evaluate(
        """() => {
          const rows = document.querySelector('.lf-toc-rows');
          const lens = document.querySelector('.lf-toc-window');
          window.lfTocLensFrame = null;
          new MutationObserver((records, observer) => {
            if (!records.some(record => record.attributeName === 'style')) return;
            const rowBox = rows.getBoundingClientRect();
            const start =
              parseFloat(rows.style.getPropertyValue('--lf-toc-window-start')) / 100;
            window.lfTocLensFrame = {
              actual: lens.getBoundingClientRect().top,
              expected: rowBox.top + rowBox.height * start,
            };
            observer.disconnect();
          }).observe(rows, {attributes: true, attributeFilter: ['style']});
        }"""
    )
    page.locator("#verify").evaluate(
        "node => node.scrollIntoView({block: 'start', behavior: 'instant'})"
    )
    expect(verify).to_have_attribute("aria-current", "location")
    page.wait_for_function("() => window.lfTocLensFrame !== null")
    lens_frame = page.evaluate("window.lfTocLensFrame")
    assert lens_frame["actual"] == pytest.approx(lens_frame["expected"], abs=1)
    lens_after = lens.bounding_box()
    assert lens_after is not None
    assert lens_after["y"] > lens_before["y"] + nav_box["height"] * 0.08

    page.mouse.move(1200, 700)
    expect(prepare).to_have_css("opacity", "0")
    page.locator("body").focus()
    # Twice: the layer's skip link is the document's first stop, and the map is what the
    # page itself opens with.
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    expect(start).to_be_focused()
    expect(start).to_have_css("opacity", "1")
    expect(start).to_have_css("outline-style", "solid")
    expect(start).to_have_css("outline-width", "2px")
    expect(start).to_have_css("outline-offset", "-2px")

    page.locator("body").focus()
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(prepare).to_have_css("opacity", "1")
    expect(start).to_be_hidden()
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, open=False)

    resized(page, 700, 900)
    expect(prepare).to_have_css("opacity", "1")
    expect(prepare).to_have_css("pointer-events", "auto")
    expect(start).to_be_hidden()

    resized(page, 1400, 900)
    page.emulate_media(media="print")
    page.evaluate(RENDERED)
    expect(prepare).to_have_css("opacity", "1")
    expect(start).to_be_visible()

    page.emulate_media(media="screen")
    page.evaluate(RENDERED)
    page.locator("html").evaluate("node => node.classList.add('lf-copy')")
    page.evaluate(RENDERED)
    expect(prepare).to_have_css("opacity", "1")
    expect(prepare).to_have_css("pointer-events", "auto")
    expect(start).to_be_hidden()
    expect(page.locator("aside.sidebar")).to_have_css("position", "static")
    page.locator("html").evaluate("node => node.classList.remove('lf-copy')")
    page.evaluate(RENDERED)

    page.emulate_media(media="screen", forced_colors="active")
    page.evaluate(RENDERED)
    page.mouse.move(1200, 700)
    expect(prepare).to_have_css("opacity", "0")
    forced_colors = nav.evaluate(
        "node => { const rows = node.querySelector('.lf-toc-rows'); "
        "const lens = node.querySelector('.lf-toc-window'); "
        "const items = [...node.querySelectorAll('.lf-toc-start, li')]; "
        "const current = items.find(item => item.querySelector('[aria-current]')); "
        "return { spine: getComputedStyle(rows, '::before').backgroundColor, "
        "lens: getComputedStyle(lens).backgroundColor, "
        "current: getComputedStyle(current, '::before').backgroundColor, "
        "inactive: items.filter(item => item !== current).map(item => "
        "getComputedStyle(item, '::before').backgroundColor) }; }"
    )
    canvas = page.locator("body").evaluate(
        "node => getComputedStyle(node).backgroundColor"
    )
    assert forced_colors["spine"] != canvas
    assert forced_colors["lens"] == forced_colors["current"]
    assert forced_colors["lens"] != forced_colors["spine"]
    assert all(color == forced_colors["spine"] for color in forced_colors["inactive"])

    page.emulate_media(media="screen", forced_colors="none", reduced_motion="reduce")
    page.evaluate(RENDERED)
    prepare_box = prepare.bounding_box()
    assert prepare_box is not None
    page.mouse.move(prepare_box["x"] + 4, prepare_box["y"] + 4)
    expect(prepare).to_have_css("opacity", "1")
    expect(prepare).to_have_css("pointer-events", "auto")
    expect(prepare).to_have_css("transition-duration", "0s")
    start.click()
    expect(page).to_have_url(re.compile(rf"{re.escape(start_href)}$"))
    assert (
        page.locator(start_href).evaluate("node => node.getBoundingClientRect().top")
        < 150
    )
    assert errors == []
    page.close()

    # A wide touch screen still gets the ordinary sticky sidebar. The ToC fixes itself
    # only in the fine-pointer posture where its hover map and wheel bridge are active.
    context = browser.new_context(
        viewport={"width": 1400, "height": 900}, has_touch=True
    )
    coarse, coarse_errors = open_page(browser, url, context=context)
    expect(coarse.locator("aside.sidebar")).to_have_css("position", "sticky")
    expect(coarse.locator("#contents")).to_have_css("position", "static")
    expect(
        coarse.get_by_role("navigation", name="On this page").get_by_role(
            "link", name="Prepare the copy", exact=False
        )
    ).to_have_css("opacity", "1")
    coarse.locator("aside.sidebar").evaluate(
        "node => { node.style.maxHeight = '80px'; node.scrollTop = 0; }"
    )
    coarse.evaluate("document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})")
    coarse_box = coarse.locator("aside.sidebar").bounding_box()
    assert coarse_box is not None
    coarse.mouse.move(coarse_box["x"] + 40, coarse_box["y"] + 40)
    coarse.mouse.wheel(0, 80)
    coarse.wait_for_function(
        "() => document.querySelector('aside.sidebar').scrollTop > 0"
    )
    assert coarse.evaluate("document.scrollingElement.scrollTop") == 0, (
        "the in-flow ToC stole a wheel from its own overflowing sidebar"
    )
    assert coarse_errors == []
    coarse.close()
    context.close()


def test_a_dense_document_map_keeps_markers_independent_of_label_height(browser, serve):
    """Density may make labels terser, never make the map taller than its spine.

    Two-line labels establish a real flex minimum. Enough of them once stretched an
    810px map past 1200px, so the lens described one coordinate system while the lower
    markers occupied another. In the dense voice labels leave the flex geometry and the
    row under the pointer reveals alone, keeping every destination without painting an
    unreadable stack of sixty lines."""
    sections = "\n".join(
        f"<section><h2 id='part-{index}'>Part {index}: preserve the active readers "
        f"while the longer migration window remains open</h2>"
        f"<p>Move cohort {index} only after its reading is stable.</p></section>"
        for index in range(1, 61)
    )
    source = leaf_page(
        "dense contents map",
        f"""
<h1>A migration with many independently verifiable steps</h1>
<aside class="sidebar"><lf-toc id="dense-contents"></lf-toc></aside>
{sections}
""",
    )
    page, errors = open_page(browser, serve(source))
    resized(page, 1400, 900)
    toc = page.locator("#dense-contents")
    nav = page.get_by_role("navigation", name="On this page")
    expect(toc).to_have_attribute("data-lf-dense", "")
    expect(nav.locator("li a").first).to_have_css("-webkit-line-clamp", "1")

    nav_box = nav.bounding_box()
    assert nav_box is not None
    assert nav.evaluate("node => node.scrollHeight <= node.clientHeight + 1")
    markers = nav.locator(".lf-toc-start, li").evaluate_all(
        "items => items.map(item => { const s = getComputedStyle(item, '::before'); "
        "const r = item.getBoundingClientRect(); return r.y + parseFloat(s.top); })"
    )
    assert markers[-1] <= nav_box["y"] + nav_box["height"]

    page.mouse.move(nav_box["x"] + 30, nav_box["y"] + 100)
    page.wait_for_timeout(300)
    shown = nav.locator(".lf-toc-start a, li a").evaluate_all(
        "links => links.filter(link => getComputedStyle(link).opacity === '1')"
        ".map(link => link.textContent || link.getAttribute('aria-label'))"
    )
    assert len(shown) == 1, f"the dense map painted overlapping labels: {shown}"
    hovered = nav.locator("li:hover a")
    expect(hovered).to_have_count(1)
    expect(hovered).to_have_css("pointer-events", "auto")
    href = hovered.get_attribute("href")
    hovered.click()
    expect(page).to_have_url(re.compile(rf"{re.escape(href)}$"))
    assert errors == []
    page.close()


def test_the_document_map_remeasures_tab_swaps_and_skips_hidden_headings(
    browser, serve
):
    """An equal-height panel swap changes the map without resizing the document.

    Both panels occupy the same outer height but put their heading at a different point.
    The active panel's heading must own the remaining span and the hidden panel must own
    none; at the bottom, current location means the last visible heading rather than the
    last heading in DOM order."""
    source = leaf_page(
        "tabbed contents map",
        """
<h1>Two routes through the same migration window</h1>
<style>#first-route, #second-route { height: 1100px; overflow: hidden; }</style>
<aside class="sidebar"><lf-toc id="tab-contents"></lf-toc></aside>
<lf-tabs id="routes">
  <lf-tab id="first-route" label="First route">
    <h2 id="first-heading">Prepare the readers before opening the window</h2>
    <div style="height: 900px"></div>
  </lf-tab>
  <lf-tab id="second-route" label="Second route">
    <div style="height: 420px"></div>
    <h2 id="second-heading">Verify the readers after closing the window</h2>
    <div style="height: 480px"></div>
  </lf-tab>
</lf-tabs>
""",
    )
    page, errors = open_page(browser, serve(source))
    resized(page, 1400, 900)
    first = page.get_by_role("navigation", name="On this page").get_by_role(
        "link", name="Prepare the readers", exact=False
    )
    second = page.get_by_role("navigation", name="On this page").get_by_role(
        "link", name="Verify the readers", exact=False
    )
    span = "node => Number(node.parentElement.style.getPropertyValue('--lf-toc-span'))"
    main_height = page.locator("main").evaluate("node => node.scrollHeight")
    assert first.evaluate(span) > 500
    assert second.evaluate(span) == 0

    page.evaluate(
        "document.scrollingElement.scrollTop = document.scrollingElement.scrollHeight"
    )
    expect(first).to_have_attribute("aria-current", "location")
    expect(second).not_to_have_attribute("aria-current", "location")

    page.get_by_role("tab", name="Second route").click()
    page.wait_for_function(
        "() => Number(document.querySelector('a[href=\"#second-heading\"]')"
        ".parentElement.style.getPropertyValue('--lf-toc-span')) > 400"
    )
    assert page.locator("main").evaluate("node => node.scrollHeight") == main_height
    assert first.evaluate(span) == 0
    assert second.evaluate(span) > 400
    page.evaluate(
        "document.scrollingElement.scrollTop = document.scrollingElement.scrollHeight"
    )
    expect(second).to_have_attribute("aria-current", "location")
    expect(first).not_to_have_attribute("aria-current", "location")
    assert errors == []
    page.close()


def test_a_gloss_opens_at_its_phrase_for_pointer_keyboard_and_touch(browser, serve):
    """The explanation is a glance, not a mouse-only tooltip: the phrase opens it on
    hover, Tab reaches its Explain control, and a click pins it for mouse or touch. In
    every form the top-layer card remains inside the viewport, and both the phrase and
    explanation remain the page's authored words."""
    source = leaf_page(
        "gloss",
        """
<h1>Rollout</h1>
<p style="margin-top: 110vh; text-align: right">
  Start with a
  <lf-gloss id="gloss-path" tip="A thin, end-to-end path through the real system."
    >walking skeleton</lf-gloss
  >.
</p>
""",
    )
    url = serve(source)
    page, errors = open_page(browser, url)
    gloss = page.locator("#gloss-path")
    mark = gloss.get_by_role("button", name="Explain “walking skeleton”")
    bubble = page.locator("#lf-gloss-tip-1")

    expect(bubble).to_be_hidden()
    affordance = gloss.evaluate(
        """el => {
          const phrase = getComputedStyle(el);
          const mark = el.querySelector('.lf-gloss-mark');
          const words = document.createRange();
          words.selectNodeContents(el.childNodes[0]);
          const tokens = document.createElement('span');
          tokens.style.cssText = 'color: var(--accent)';
          document.body.append(tokens);
          const tokenStyle = getComputedStyle(tokens);
          const accent = tokenStyle.color;
          tokens.remove();
          return {
            accent,
            extraWidth: el.getBoundingClientRect().width - words.getBoundingClientRect().width,
            underline: phrase.textDecorationColor,
            markOpacity: getComputedStyle(mark).opacity,
            markText: mark.textContent,
            markWidth: mark.getBoundingClientRect().width,
            pointer: phrase.cursor,
          };
        }"""
    )
    assert affordance["markText"] == ""
    assert affordance["markWidth"] == 1
    assert affordance["markOpacity"] == "0"
    assert affordance["pointer"] == "help"
    assert affordance["extraWidth"] == pytest.approx(0, abs=1)
    assert affordance["underline"] == affordance["accent"]
    gloss.hover()
    expect(bubble).to_be_visible()
    expect(bubble).to_have_text("A thin, end-to-end path through the real system.")

    # Auto popovers light-dismiss on a press outside the card. The phrase is outside
    # the card too, so the click that pins a hovered explanation must reconcile the
    # browser's just-closed popover with the widget state before the pointer leaves.
    gloss.click(position={"x": 20, "y": 8})
    page.mouse.move(0, 0)
    expect(bubble).to_be_visible()
    page.locator("h1").click()
    expect(bubble).to_be_hidden()
    gloss.hover()
    expect(bubble).to_be_visible()

    rect = bubble.evaluate("el => el.getBoundingClientRect()")
    viewport = page.evaluate("() => ({ width: innerWidth, height: innerHeight })")
    assert rect["left"] >= 0 and rect["right"] <= viewport["width"]
    assert rect["top"] >= 0 and rect["bottom"] <= viewport["height"]
    bubble.hover()
    expect(bubble).to_be_visible()

    # WCAG's hover-content route: Escape dismisses the card without requiring the
    # pointer to move away or transferring focus to a control the reader never used.
    page.keyboard.press("Escape")
    expect(bubble).to_be_hidden()

    page.mouse.move(0, 0)
    expect(bubble).to_be_hidden()
    page.locator("body").focus()
    # Twice: the layer's skip link is the document's first stop, and the mark is the
    # first thing the page itself offers.
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    expect(mark).to_be_focused()
    expect(bubble).to_be_visible()
    expect(gloss).to_have_css("outline-style", "solid")
    page.keyboard.press("Escape")
    expect(bubble).to_be_hidden()

    assert gloss.evaluate("el => el.childNodes[0].textContent.trim()") == (
        "walking skeleton"
    )
    assert errors == []
    page.close()

    # A real touch context, not a mouse click standing in for one: the tap pins the
    # explanation without a hover state, and a tap elsewhere light-dismisses it.
    context = browser.new_context(
        viewport={"width": 420, "height": 900}, has_touch=True
    )
    touch, touch_errors = open_page(browser, url, context=context)
    touch_gloss = touch.locator("#gloss-path")
    touch_bubble = touch.locator("#lf-gloss-tip-1")
    touch_gloss.tap(position={"x": 20, "y": 8})
    expect(touch_bubble).to_be_visible()
    touch.locator("h1").tap()
    expect(touch_bubble).to_be_hidden()
    assert touch_errors == []
    touch.close()
    context.close()


def test_a_nested_platform_control_does_not_pin_its_gloss(browser, serve):
    """A nested control owns its click even when its platform contract is an ARIA role."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "gloss control",
                '<h1>Term</h1><p><lf-gloss tip="An explanation.">'
                'term <span role="button" tabindex="0">work it</span>'
                "</lf-gloss></p>",
            )
        ),
    )
    control = page.get_by_role("button", name="work it", exact=True)
    bubble = page.get_by_role("note")
    control.hover()
    expect(bubble).to_be_visible()
    control.click()
    page.mouse.move(0, 0)
    page.locator("body").focus()
    expect(bubble).to_be_hidden()
    assert errors == []
    page.close()


def test_a_comment_on_a_gloss_reopens_its_explanation(browser, serve):
    """The tip is x-says page text, so a comment can rest on it like a tab's rendered
    label. Following that comment must reveal the otherwise hidden popover before the
    anchor scrolls; a durable thread cannot point to words the page then keeps closed."""
    tip = "A thin, end-to-end path through the real system."
    source = leaf_page(
        "gloss comment",
        f"""
<h1>Rollout</h1>
<p>Start with a <lf-gloss id="gloss-path" tip="{tip}">walking skeleton</lf-gloss>.</p>
""",
    )
    page, errors = open_page(browser, serve(source, anchored=[("gloss-path", tip)]))
    bubble = page.locator("#lf-gloss-tip-1")

    expect(bubble).to_be_hidden()
    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread .lf-quote").click()
    expect(bubble).to_be_visible()

    assert errors == []
    page.close()


def test_a_board_says_which_column_each_card_is_in(browser, serve):
    """Which column a card sits in is the one fact about it that isn't in its own
    text, and columns are three boxes side by side — geometry, which the
    accessibility tree doesn't carry. Flat, this board was six text runs and two
    Move buttons in a row: no boundary between the columns, and no button saying
    where its card was.

    Both halves are asserted from the tree itself rather than from the attributes
    behind it, because that is where they can be wrong: the column heading is CSS
    generated content, so the name reaching the tree once (as the list's) rather
    than twice depends on its alt text. Then a card moves, and the assertion is
    the second snapshot — a name set where the move happens goes stale on
    whichever path forgets to restate its location or durable pending state."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    board = page.locator("#sprint")

    assert board.aria_snapshot() == (
        '- list "Todo":\n'
        "  - listitem:\n"
        "    - strong: Heated perch\n"
        "    - 'button \"Move: Heated perch — Todo\"': ⠿\n"
        "  - listitem:\n"
        "    - strong: Squirrel baffle\n"
        "    - 'button \"Move: Squirrel baffle — Todo\"': ⠿\n"
        '- list "Done"'  # empty, and still announced: it is a drop target
    )

    # Grab the second card and push it into the next column, the keyboard's path.
    board.get_by_role("button", name="Move: Squirrel baffle — Todo").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    page.wait_for_selector("#col-done #card-baffle")
    expect(
        board.get_by_role(
            "button",
            name="Move: Squirrel baffle — Done — your move",
            exact=True,
        )
    ).to_be_visible()

    assert board.aria_snapshot() == (
        '- list "Todo":\n'
        "  - listitem:\n"
        "    - strong: Heated perch\n"
        "    - 'button \"Move: Heated perch — Todo\"': ⠿\n"
        '- list "Done":\n'
        "  - listitem:\n"
        "    - strong: Squirrel baffle\n"
        "    - 'button \"Move: Squirrel baffle — Done — your move\"': ⠿"
    )
    assert errors == []
    page.close()


def test_a_swipe_deck_is_one_ask_with_directional_action_hints(browser, serve):
    """a lands on the authored question and exposes the deck's own bindings there.

    The last classification both places its card and closes the Ask, so z reopens the
    question with that card back in the queue.
    """
    page, errors = open_page(browser, serve(SWIPE_PAGE))
    decision = page.locator("#session-triage-decision")

    expect(page.locator(".lf-asks")).to_have_text("Asks 0/1")
    # Outside the Ask projection, the package command still spells its real binding;
    # the Decision action name is not a keycap override.
    page.keyboard.press("?")
    page.keyboard.press("?")
    pass_reference = page.locator('.lf-help tr[data-lf-command="swipe.pass"]')
    expect(pass_reference.locator("kbd")).to_have_text("←")
    expect(pass_reference.locator(".lf-key-sequence")).to_have_attribute(
        "aria-label", "ArrowLeft"
    )
    expect(
        page.locator('.lf-help tr[data-lf-command="swipe.undo-last"]')
    ).to_have_count(0)
    page.keyboard.press("Escape")

    page.keyboard.press("a")
    expect(decision).to_be_focused()
    expect(page.locator(".lf-asks")).to_have_text("Asks 0/1")
    expect(page.locator(".lf-ask-addresses > .lf-ask-address")).to_have_text(["←", "→"])
    assert "← / →\nPass / Keep" in key_line(page)

    page.keyboard.press("Tab")
    assert "←\npass the active card" in key_line(page)
    assert "Pass\npass the active card" not in key_line(page)
    page.keyboard.press("a")
    expect(decision).to_be_focused()

    # The reference exposes the same exact routes as their inline bindings.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator('.lf-help-command[data-lf-command="swipe.pass"]')).to_have_text(
        "Activate the “Pass” action"
    )
    expect(page.locator('.lf-help-command[data-lf-command="swipe.keep"]')).to_have_text(
        "Activate the “Keep” action"
    )
    expect(
        page.locator('.lf-help-command[data-lf-command="ask.activate-nth"]')
    ).to_have_count(0)
    page.keyboard.press("Escape")

    for binding in ("ArrowRight", "ArrowLeft", "ArrowRight", "ArrowLeft"):
        page.keyboard.press(binding)
    round_trip(page)
    expect(page.locator(".lf-asks")).to_have_text("Asks 1/1")
    expect(page.locator(".lf-ask-addresses > .lf-ask-address")).to_have_count(0)
    assert "Undo last swipe" not in key_line(page)
    assert [event["action"] for event in actions(serve.page_dir)] == [
        "swipe",
        "swipe",
        "swipe",
        "finish",
    ]

    page.reload(wait_until="load")
    expect(page.locator("#session-pass > #swipe-d")).to_have_count(1)
    expect(page.locator(".lf-asks")).to_have_text("Asks 1/1")

    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    row = page.locator("button.lf-asks-row")
    expect(row).to_be_focused()
    expect(row.locator(".lf-asks-answer")).to_have_text("3 kept · 3 passed")
    page.keyboard.press("Enter")
    assert "Undo last swipe" not in key_line(page)

    page.keyboard.press("1")
    expect(page.locator("#session-pass > #swipe-d")).to_have_count(1)
    expect(page.locator(".lf-asks")).to_have_text("Asks 1/1")

    page.keyboard.press("z")
    round_trip(page)
    expect(page.locator("#session-queue > #swipe-d")).to_have_count(1)
    expect(page.locator(".lf-asks")).to_have_text("Asks 0/1")
    page.keyboard.press("a")
    expect(page.locator(".lf-asks")).to_have_text("Asks 0/1")
    assert errors == []
    page.close()


def test_character_shortcuts_off_removes_a_contextual_ask_digit(browser, serve):
    """A live arrow cannot keep filtered contextual actions on the key line."""
    page, errors = open_page(
        browser,
        serve(SHORT_SUGGESTION),
        init_script="localStorage.setItem('lf-character-shortcuts', '0')",
    )
    page.evaluate(
        """async () => {
          const {commands} = await import('/runtime/widget-api.js');
          const suggestion = document.getElementById('sug');
          const inspect = document.createElement('button');
          inspect.textContent = 'Inspect';
          inspect.onclick = () => { inspect.dataset.activated = '1'; };
          suggestion.append(inspect);
          commands(inspect, 'Explicit non-character action', [{
            id: 'test.inspect-left',
            keys: ['ArrowLeft'],
            control: inspect,
            decision: 'Inspect',
            does: 'Inspect this suggestion',
            line: 'Inspect',
            run: () => inspect.click(),
          }]);
        }"""
    )

    page.locator(".lf-asks").click()
    page.locator("button.lf-asks-row").click()
    expect(page.locator("#sug")).to_be_focused()
    assert "←\nInspect" in key_line(page)
    assert "Accept / Reject" not in key_line(page)
    expect(page.locator(".lf-ask-addresses > .lf-ask-address")).to_have_text("←")

    before = len(actions(serve.page_dir))
    page.keyboard.press("1")
    assert len(actions(serve.page_dir)) == before
    page.keyboard.press("ArrowLeft")
    expect(page.get_by_role("button", name="Inspect", exact=True)).to_have_attribute(
        "data-activated", "1"
    )
    assert errors == []
    page.close()


def test_swipe_deck_buttons_arrows_and_rapid_actions_share_order(browser, serve):
    """Every input route ends at a button click, and quick classifications retain
    gesture order while the outbox serializes their requests."""
    page, errors = open_page(browser, serve(SWIPE_PAGE))
    deck = page.locator("#session-triage")
    passed = deck.locator("#session-pass > lf-swipe-card")
    kept = deck.locator("#session-keep > lf-swipe-card")
    buttons = deck.locator(".lf-swipe-controls button:visible")

    expect(buttons).to_have_count(2)
    expect(deck).to_have_attribute("aria-keyshortcuts", "ArrowLeft ArrowRight")
    deck.get_by_role("button", name="← Pass", exact=True).click()
    expect(passed).to_have_count(2)
    round_trip(page)

    page.locator("#swipe-b").focus()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#session-keep > #swipe-b")).to_have_count(1)
    expect(page.locator("#swipe-c")).to_be_focused()
    round_trip(page)

    # No wait between these activations: the arrow's button click exposes the next
    # card synchronously while its network attempt is still the outbox's head.
    page.locator("#swipe-c").focus()
    page.keyboard.press("ArrowLeft")
    deck.get_by_role("button", name="Keep →", exact=True).click()
    expect(passed).to_have_count(3)
    expect(kept).to_have_count(3)
    expect(deck.locator(".lf-swipe-progress")).to_be_focused()
    round_trip(page)

    logged = actions(serve.page_dir)
    assert [event["action"] for event in logged] == [
        "swipe",
        "swipe",
        "swipe",
        "finish",
    ]
    assert [event["detail"] for event in logged] == [
        {"card": "swipe-a", "to": "session-pass", "index": 1},
        {"card": "swipe-b", "to": "session-keep", "index": 1},
        {"card": "swipe-c", "to": "session-pass", "index": 2},
        {
            "card": "swipe-d",
            "to": "session-keep",
            "index": 2,
        },
    ]
    assert errors == []
    page.close()


def test_a_crafted_finish_cannot_close_a_swipe_ask_with_an_unknown_card(browser, serve):
    """The answer verb carries the final position itself. Its references are
    validated before the verb can settle the Ask, so a crafted but schema-valid
    finish cannot leave an answered deck whose final classification never existed."""
    url = serve(SWIPE_PAGE)
    page, errors = open_page(browser, url)
    expect(page.locator(".lf-asks")).to_have_text("Asks 0/1")

    early = post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "action",
            "revision": 1,
            "widget": "session-triage",
            "action": "finish",
            "detail": {"card": "swipe-a", "to": "session-keep", "index": 1},
        },
    )
    assert early.status == 400
    assert "does not satisfy its completion condition" in early.json()["error"]

    refused = post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "action",
            "revision": 1,
            "widget": "session-triage",
            "action": "finish",
            "detail": {"card": "not-a-card", "to": "session-keep", "index": 2},
        },
    )

    assert refused.status == 400
    assert "unknown card 'not-a-card'" in refused.json()["error"]
    expect(page.locator(".lf-asks")).to_have_text("Asks 0/1")
    assert actions(serve.page_dir) == []
    assert errors == []
    page.close()


def test_a_newer_swipe_survives_an_older_swipe_refusal(browser, serve):
    """Optimistic cards are an outbox overlay, not snapshots of one another. If an
    older swipe is refused, its card returns while a later queued verdict still lands."""
    page, errors = open_page(browser, serve(SWIPE_PAGE))
    page.route("**/api/state*", refuse)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator("#swipe-a").focus()

    with page.expect_request("**/api/event"):
        page.keyboard.press("ArrowLeft")
    expect(page.locator("#swipe-b")).to_be_focused()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#swipe-c")).to_be_focused()
    expect(page.locator("#session-pass > #swipe-a")).to_have_count(1)
    expect(page.locator("#session-keep > #swipe-b")).to_have_count(1)
    assert len(held) == 1, (
        "the outbox sent a later gesture before its predecessor settled"
    )

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_request(
        lambda request: (
            "/api/event" in request.url
            and request.post_data_json.get("attempt") != attempt
        )
    ):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    holding(page, held, 2, "the surviving swipe")
    held[1].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    expect(page.locator("#session-keep > #swipe-b")).to_have_count(1)
    expect(page.locator("#swipe-a")).to_be_focused()
    page.keyboard.press("ArrowLeft")
    round_trip(page)
    assert [event["detail"]["card"] for event in actions(serve.page_dir)] == [
        "swipe-b",
        "swipe-a",
    ]
    assert errors and all("400" in error for error in errors)
    page.close()


def test_a_stale_rapid_finish_is_refused_when_an_earlier_card_returns(browser, serve):
    """The browser may mint the fourth rapid gesture as finish while all four local
    moves look complete. If the first move is refused, the append door must judge the
    later finish against authoritative post-action positions and leave the Ask open.
    """
    page, errors = open_page(browser, serve(SWIPE_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator("#swipe-a").focus()

    with page.expect_request("**/api/event"):
        for binding in ("ArrowLeft", "ArrowRight", "ArrowLeft", "ArrowRight"):
            page.keyboard.press(binding)
    expect(page.locator(".lf-swipe-progress")).to_be_focused()
    assert len(held) == 1

    first_attempt = held[0].request.post_data_json["attempt"]
    held[0].fulfill(
        status=400,
        json={
            "ok": False,
            "attempt": first_attempt,
            "error": "refused before append",
            "final": True,
        },
    )
    for index in range(1, 4):
        holding(page, held, index + 1, f"gesture {index + 1}")
        held[index].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    expect(page.locator("#session-queue > #swipe-d")).to_have_count(1)
    expect(page.locator(".lf-asks")).to_have_text("Asks 0/1")
    assert [event["detail"]["card"] for event in actions(serve.page_dir)] == [
        "swipe-b",
        "swipe-c",
    ]
    assert errors and all("400" in error for error in errors)
    page.close()


def test_swipe_deck_pointer_threshold_cancel_and_commit(browser, serve):
    """Pointer Events preserve a vertical/tentative read and cancel cleanly; only a
    horizontal drag beyond the deck's threshold reaches a verdict button."""
    url = serve(SWIPE_PAGE)
    page, errors = open_page(browser, url)
    card = page.locator("#swipe-a")
    box = card.bounding_box()
    assert box
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2

    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 24, y)
    page.mouse.up()
    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    expect(card).not_to_have_class(re.compile(r"\blf-swipe-dragging\b"))
    assert card.evaluate("el => el.style.getPropertyValue('--lf-swipe-drag-x')") == ""

    page.mouse.move(x, y)
    page.evaluate(
        """() => document.addEventListener('pointerdown', event => {
          window.__swipePointerId = event.pointerId;
        }, {capture: true, once: true})"""
    )
    page.mouse.down()
    page.mouse.move(x + 80, y)
    pointer_id = page.evaluate("window.__swipePointerId")
    assert isinstance(pointer_id, int)
    card.dispatch_event("pointercancel", {"pointerId": pointer_id})
    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    expect(card).not_to_have_class(re.compile(r"\blf-swipe-dragging\b"))
    expect(page.locator("#session-triage")).not_to_have_class(
        re.compile(r"\blf-dragging\b")
    )
    assert card.evaluate("el => el.style.getPropertyValue('--lf-swipe-drag-x')") == ""
    page.mouse.up()

    card.locator("p").first.evaluate(
        """element => {
          const range = document.createRange();
          range.selectNodeContents(element);
          const selection = getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          document.body.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true}));
        }"""
    )
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    assert page.evaluate("() => getSelection().toString().trim()")

    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x - 30, y)
    page.mouse.up()
    # The selection surface defers its release update by one task. Read only after that
    # task: before the claim boundary existed, a swipe the deck let go of restored the
    # range captured on pointerdown and raised the Comment bar again.
    page.evaluate("() => new Promise(resolve => setTimeout(resolve, 0))")
    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    assert page.evaluate("() => getSelection().toString()") == ""
    assert not page.locator(".lf-fab-bar").is_visible()

    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x - box["width"] * 0.35, y)
    page.mouse.up()
    expect(page.locator("#session-pass > #swipe-a")).to_have_count(1)
    round_trip(page)
    assert errors == []
    page.close()

    context = browser.new_context(
        viewport={"width": 420, "height": 900}, has_touch=True
    )
    touch, touch_errors = open_page(browser, url, context=context)
    touch_card = touch.locator("#swipe-b")
    touch_box = touch_card.bounding_box()
    assert touch_box
    tx = round(touch_box["x"] + touch_box["width"] / 2)
    ty = round(touch_box["y"] + touch_box["height"] / 2)
    cdp = context.new_cdp_session(touch)
    cdp.send(
        "Input.dispatchTouchEvent",
        {"type": "touchStart", "touchPoints": [{"x": tx, "y": ty}]},
    )
    for step in range(1, 8):
        cdp.send(
            "Input.dispatchTouchEvent",
            {
                "type": "touchMove",
                "touchPoints": [
                    {
                        "x": tx + round(touch_box["width"] * 0.35 * step / 7),
                        "y": ty,
                    }
                ],
            },
        )
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    expect(touch.locator("#session-keep > #swipe-b")).to_have_count(1)
    round_trip(touch)
    assert touch_errors == []
    touch.close()
    context.close()


def test_swipe_deck_exit_echo_starts_at_the_dragged_card_box(browser, serve):
    """The Tinder-like exit continues from the held card instead of gaining its
    padding and border a second time when the fixed-position echo is sized."""
    page, errors = open_page(browser, serve(SWIPE_PAGE), init_script=HOLD_MOTION)
    card = page.locator("#swipe-a")
    box = card.bounding_box()
    assert box
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2

    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x - box["width"] * 0.35, y)
    dragged = card.bounding_box()
    assert dragged
    page.mouse.up()

    echo = page.locator(".lf-swipe-exit")
    expect(echo).to_have_count(1)
    echo_box = echo.bounding_box()
    assert echo_box
    assert echo_box == pytest.approx(dragged, abs=0.02)
    page.evaluate("window.__lfHeld[0].finish()")
    expect(echo).to_have_count(0)
    round_trip(page)
    assert errors == []
    page.close()


def test_swipe_deck_reloads_replays_and_undoes_absolute_placement(browser, serve):
    """The pile position is durable state, not module memory: reload reconstructs it,
    and undo restores the card to its authored queue position."""
    url = serve(SWIPE_PAGE)
    page, errors = open_page(browser, url)
    page.get_by_role("button", name="Keep →", exact=True).click()
    round_trip(page)
    expect(page.locator("#session-keep > #swipe-a")).to_have_count(1)

    page.reload(wait_until="load")
    expect(page.locator("#session-keep > #swipe-a")).to_have_count(1)
    assert page.evaluate(
        """async () => {
          const {standingState} = await import('/runtime/widget-api.js');
          const deck = document.getElementById('session-triage');
          const {state} = standingState().find(({widget}) => widget === deck);
          window.swipeCards = [...deck.querySelectorAll('lf-swipe-card')];
          deck.renderState(state);
          deck.renderState(state);
          return window.swipeCards.every(card => document.getElementById(card.id) === card);
        }"""
    )
    assert page.eval_on_selector_all(
        "#session-keep > lf-swipe-card", "cards => cards.map(card => card.id)"
    ) == ["already-kept", "swipe-a"]
    undo(page)
    expect(page.locator("#session-queue > #swipe-a")).to_have_count(1)
    assert page.eval_on_selector_all(
        "#session-queue > lf-swipe-card", "cards => cards.map(card => card.id)"
    ) == ["swipe-a", "swipe-b", "swipe-c", "swipe-d"]
    assert page.evaluate(
        "window.swipeCards.every(card => document.getElementById(card.id) === card)"
    )
    assert errors == []
    page.close()


def test_a_quoted_swipe_deck_is_a_static_labeled_exhibit(browser, serve):
    source = SWIPE_PAGE.replace(
        '<lf-ask id="session-triage-decision">',
        '<lf-specimen id="swipe-example" label="session triage">',
    ).replace("</lf-ask>", "</lf-specimen>")
    page, errors = open_page(browser, serve(source))
    deck = page.locator("#session-triage")

    expect(deck.locator(".lf-swipe-controls")).to_have_count(0)
    expect(deck.get_by_role("button")).to_have_count(0)
    expect(deck.locator("lf-swipe-card[tabindex]")).to_have_count(0)
    expect(deck.locator("lf-swipe-card:visible")).to_have_count(6)
    assert deck.get_by_role("list").count() == 3
    resized(page, 420, 900)
    passed = page.locator("#session-pass").bounding_box()
    kept = page.locator("#session-keep").bounding_box()
    assert passed and kept and passed["y"] + passed["height"] <= kept["y"]
    assert errors == []
    page.close()


def test_a_swipe_deck_export_is_a_static_labeled_copy(browser, serve, tmp_path):
    url = serve(SWIPE_PAGE)
    out = tmp_path / "swipe-copy.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    copy = browser.new_page(viewport={"width": 1200, "height": 900})
    copy.goto(out.as_uri(), wait_until="load")
    deck = copy.locator("#session-triage")

    expect(copy.locator("script")).to_have_count(0)
    expect(deck.locator(".lf-swipe-controls")).to_be_hidden()
    expect(deck.get_by_role("button")).to_have_count(0)
    expect(deck.locator("lf-swipe-card[tabindex]")).to_have_count(0)
    expect(deck.locator("lf-swipe-card:visible")).to_have_count(6)
    assert deck.locator(".lf-swipe-pile-label").all_inner_texts() == [
        "QUEUE · 4",
        "PASSED · 1",
        "KEPT · 1",
    ]
    copy.close()


def test_a_reduced_motion_swipe_moves_without_an_exit_animation(browser, serve):
    context = browser.new_context(reduced_motion="reduce")
    page, errors = open_page(browser, serve(SWIPE_PAGE), context=context)
    page.get_by_role("button", name="← Pass", exact=True).click()

    expect(page.locator("#session-pass > #swipe-a")).to_have_count(1)
    expect(page.locator(".lf-swipe-exit")).to_have_count(0)
    round_trip(page)
    assert errors == []
    page.close()
    context.close()


def test_composer_grows_with_its_text_without_script(browser, serve):
    """The comment box fits its content, caps, and shrinks back — and no script
    touches its height. That last part is the point: sizing a textarea from JS
    means shrinking it to re-measure on every keystroke, and a box briefly too
    small for its own text flashes a scrollbar."""
    page, _ = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-threads-toggle").click()
    box = page.locator(".lf-general textarea")

    page.evaluate("""() => {
        const ta = document.querySelector('.lf-general textarea');
        window.__styled = 0;
        new MutationObserver(() => window.__styled++)
            .observe(ta, { attributes: true, attributeFilter: ['style'] });
    }""")

    def state():
        return box.evaluate("""ta => ({ h: Math.round(ta.getBoundingClientRect().height),
                                        scrollable: ta.scrollHeight > ta.clientHeight })""")

    empty = state()
    box.type("A comment long enough to wrap onto a second line and then a third.")
    grown = state()
    box.fill("x " * 900)  # far past the ceiling
    capped = state()
    box.fill("short again")
    shrunk = state()

    assert grown["h"] > empty["h"], "the box must grow with its content"
    assert not grown["scrollable"], "a box that fits its text must not be scrollable"
    # The ceiling is 50vh — the viewport's share, not a count of lines — measured
    # here in the suite's 900px-tall window.
    assert capped["h"] == 450, f"the box must stop at its ceiling, got {capped['h']}px"
    assert capped["scrollable"], (
        "past the ceiling the scrollbar is real and belongs there"
    )
    assert shrunk["h"] == empty["h"], "and it must shrink back"
    assert page.evaluate("window.__styled") == 0, "nothing may size the box from script"
    page.close()


@pytest.mark.parametrize("reduced_motion", ["no-preference", "reduce"])
def test_suggestion_controls_stay_out_of_the_column(browser, serve, reduced_motion):
    """Suggestion chrome hangs in the page margin, so the prose keeps the full column
    and reads as it will once the change is settled. The row is the column's own
    child and takes its line from an anchor inside the change, so how deep the
    change sits costs it nothing: one inside a card — a positioned ancestor, which
    `left: 100%` used to resolve against, dropping the row back into the text —
    hangs in the rail beside its card like any other. What is left is a
    measurement no lint can make: a window with no margin to hold the row docks it
    into flow, under the block it decides rather than overlapping the page.

    The margin the row hangs in is reserved, not left over, and the posture that
    proves it is the one a user reads in: with the thread panel open, a
    centred column left too little beside it and every row docked — above the
    change it decides, which reads as the paragraph before's."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE), init_script=HOLD_MOTION)
    page.emulate_media(reduced_motion=reduced_motion)
    assert errors == []
    column = page.locator("main").evaluate("el => el.getBoundingClientRect().right")
    room = page.evaluate("() => document.body.getBoundingClientRect().right")
    box = "el => el.getBoundingClientRect()"

    margin_rows = page.locator(
        "[data-lf-for='sug-refill'], [data-lf-for='sug-thistle']"
    )
    assert margin_rows.count() == 2
    for i in range(2):
        assert margin_rows.nth(i).evaluate(box)["left"] > column, (
            "a control row overlapping the column re-wraps the prose it reviews"
        )
    # Two changes a line apart, so the rows would collide at their natural offsets.
    first, second = (margin_rows.nth(i).evaluate(box) for i in range(2))
    assert first["bottom"] <= second["top"], "control rows must not stack on each other"

    # The card is positioned and the change is three elements down inside it, and
    # the row still hangs in the rail on the line that change starts — which is
    # what the anchor buys, and what a static position never could.
    in_card = page.locator("[data-lf-for='sug-in-card']").evaluate(box)
    assert in_card["left"] > column and in_card["right"] <= room, (
        "a change inside a widget is still a change the user decides in the margin"
    )
    assert (
        abs(in_card["top"] - page.locator("#sug-in-card lf-old").evaluate(box)["top"])
        <= 5
    ), "the row must hang on the change's own line, not on the block it follows"

    # The panel takes the right of the window, and the rail survives it: the rows
    # keep their line, clear of the column on one side and of the panel on the
    # other. Measured after the layout has moved, since opening the panel resizes
    # the page and the rows re-place on the frame after that.
    page.locator(".lf-threads-toggle").click()
    if reduced_motion == "no-preference":
        # Hold the presentation offset while the resize-driven placements dock the
        # rows. Let that frame's ResizeObserver delivery and its queued placement run
        # before finishing the carry, so no pending resize accidentally repairs them.
        page.wait_for_function(
            "() => [...document.querySelectorAll('[data-lf-for=sug-refill], [data-lf-for=sug-thistle]')]"
            ".every(r => r.parentElement.classList.contains('lf-docked'))"
        )
        page.evaluate("""() => new Promise(resolve => {
          requestAnimationFrame(() => requestAnimationFrame(resolve));
        })""")
    panel_settled(page)
    page.wait_for_function(
        "() => [...document.querySelectorAll("
        "'[data-lf-for=sug-refill], [data-lf-for=sug-thistle]')]"
        ".every(r => !r.parentElement.classList.contains('lf-docked'))"
    )
    narrowed = page.locator("main").evaluate("el => el.getBoundingClientRect().right")
    room = page.evaluate("() => document.body.getBoundingClientRect().right")
    for i in range(2):
        rect = margin_rows.nth(i).evaluate(box)
        assert rect["left"] > narrowed and rect["right"] <= room, (
            "with the panel open the row must still hang between column and panel"
        )

    # No margin anywhere: every row docks, and nothing spills sideways. Docked is
    # the same box in flow where the row was hoisted to, so it reads as a control
    # line under the block holding the change and never as the one before's.
    page.get_by_role("button", name="Close threads").click()
    # The panel gives the room back in one responsive layout, then carries the column to
    # it. Wait for that route before reading the rows against their settled blocks.
    panel_settled(page, open=False)
    resized(page, 820, 900)
    page.wait_for_function(
        "() => [...document.querySelectorAll('.lf-sug-actions')]"
        ".every(r => r.parentElement.classList.contains('lf-docked'))"
    )
    assert page.evaluate("() => document.body.scrollWidth <= document.body.clientWidth")
    for widget, block in [("sug-refill", "#replace"), ("sug-in-card", "#sug-in-card")]:
        assert (
            page.locator(f"[data-lf-for='{widget}']").evaluate(box)["top"]
            >= page.locator(block).evaluate(box)["bottom"]
        ), "a docked row belongs under the block whose change it decides"
    page.close()


def test_a_copy_says_a_change_is_only_proposed(browser, serve, tmp_path):
    """Who says the change is still a proposal, in each medium the page reaches.

    On screen the ✓/✗ row hanging on the change's own line says it, and the word is
    for whoever is listening, so it stays clipped. A copy and paper have no row —
    both strip controls the page does not speak through — so each pending slot needs
    visible words distinguishing a proposal from ordinary settled content.

    The word also had to change to be worth showing. Pendingness was carried by the
    word's mere presence, which no reader can perceive — nothing sits alongside to
    compare it against — and `deletion` is ARIA's own name for the completed act, so
    a listener heard the change announced as made while the page was still asking."""
    url = serve(PROPOSED_PAGE)
    page, errors = open_page(browser, url)

    quiet = "lf-suggestion:not([data-lf-state]) > :is(lf-old, lf-new) > .lf-quiet"
    read = """(sel) => [...document.querySelectorAll(sel)].map(el => {
        const r = el.getBoundingClientRect();
        return {word: el.textContent, shown: el.checkVisibility(),
                w: Math.round(r.width), h: Math.round(r.height)};
    })"""
    live = page.evaluate(read, quiet)
    assert [q["word"] for q in live] == [
        "proposed deletion",
        "proposed insertion",
        "proposed insertion",
        "proposed deletion",
    ], live
    for q in live:
        assert q["w"] <= 1 and q["h"] <= 1, (
            f"on screen the row says it; `{q['word']}` must hold no room, got {q}"
        )
    # And the row is there to say it — the fact the copy is about to lose.
    expect(page.locator(".lf-sug-actions")).to_have_count(3)
    assert errors == []
    page.close()

    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    copy = browser.new_page(viewport={"width": 1200, "height": 900})
    copy.goto(out.as_uri(), wait_until="load")
    assert copy.locator(".lf-sug-actions").count() == 0, (
        "the copy is only interesting because it has no controls left"
    )
    assert copy.locator(".lf-margin-item").count() == 0, (
        "stripping pending controls left their generated target item claiming a rail"
    )
    for medium in ("screen", "print"):
        copy.emulate_media(media=medium)
        shown = copy.evaluate(read, quiet)
        assert [q["word"] for q in shown] == [q["word"] for q in live], shown
        for q in shown:
            assert q["shown"] and q["w"] > 1, (
                f"[{medium}] with no row on the page, `{q['word']}` is the only thing "
                f"saying the change is unmade, and it is not on screen: {q}"
            )
    copy.close()


def test_a_moved_change_takes_its_controls_with_it(browser, serve):
    """The row is the column's child, not the change's, so the subtree a card
    travels in no longer carries it: a card dragged to another column, or moved by
    the replay of someone else's drag, leaves and re-enters the document with its
    row unhooked. Re-connection has to hang it again, or the user loses the
    only way to decide a change that is still plainly pending on the page. Replayed
    rather than dragged, because that is the same move with no gesture in the way."""
    url = serve(SUGGESTION_PAGE)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "feeders",
            "action": "move",
            "detail": {"card": "card-heater", "to": "col-done", "index": 0},
        },
    )
    page, errors = open_page(browser, url)
    expect(page.locator("#col-done #card-heater")).to_be_visible()
    box = "el => el.getBoundingClientRect()"
    row = page.locator("[data-lf-for='sug-in-card']")
    expect(row).to_be_visible()
    change = page.locator("#sug-in-card lf-old").evaluate(box)
    assert abs(row.evaluate(box)["top"] - change["top"]) <= 5, (
        "the row must find the moved change's line again, not the one it left"
    )
    row.locator(".lf-sug-accept").click()
    expect(page.locator("#sug-in-card lf-old")).to_be_hidden()
    assert errors == []
    page.close()


# A change the reader hasn't opened yet. The row hangs off an anchor in the
# change, and a collapsed container reports its content's last rendered geometry
# rather than nothing at all — so a row that trusted a measurement would hang in
# the margin deciding a change nobody can see.
def test_a_terse_compare_keeps_its_side_by_side_grid(browser, serve):
    """An exhibition is looked across where a decision is read down: terse variants
    share a row while block content stacks the group. Which children count as block
    is the phrasing-set inversion, and its one hazard is an inline widget — a
    chip-led pair must not stack, which is why the stylesheet's list excludes the
    marker the runtime paints from x-inline and this reads the shipped page to prove
    the grid actually held. It is the whole chain in one assertion: a declaration
    unpainted, a marker unread, or a selector naming the wrong attribute all arrive
    here as two variants that stacked."""
    page, errors = open_page(
        browser,
        serve(
            (Path(__file__).parent.parent / "examples/design-decision.html").read_text()
        ),
    )
    top = "el => el.getBoundingClientRect().top"
    assert page.locator("#var-session-cookie").evaluate(top) == page.locator(
        "#var-fallback-cookie"
    ).evaluate(top), "chip-led terse variants must share a row"
    assert page.locator("#var-payments-regime").evaluate(top) != page.locator(
        "#var-sessions-regime"
    ).evaluate(top), "block-content variants must stack"
    assert errors == []
    page.close()


def test_an_undone_suggestion_stays_inline_among_the_words(browser, serve):
    """An undone suggestion retains its inline presentation and the surrounding comparison layout."""
    page, errors = open_page(browser, serve(REBUILT_INLINE_PAGE))
    form = "() => getComputedStyle(document.getElementById('cmp-stores')).display"
    assert page.evaluate(form) == "grid", (
        "the exhibition stacked before anything was decided, so this proves nothing"
    )

    page.locator("[data-lf-for='sug-store'] .lf-sug-accept").click()
    round_trip(page)
    expect(page.locator("#sug-store lf-old")).to_be_hidden()
    undo(page)
    expect(page.locator("#sug-store lf-old")).to_be_visible()
    assert page.evaluate(form) == "grid", (
        "the rebuilt suggestion lost its inline mark, so the exhibition stacked"
    )
    assert errors == []
    page.close()


def test_a_block_change_emphasizes_the_words_that_moved(browser, serve):
    """A replacement's slots paint whole — which is all a dead copy keeps — and on
    the live page the words that differ deepen through the highlight registry, so
    the reader isn't left to eyeball-diff two paragraphs. Deciding clears the
    emphasis with the slot it retires: the survivor is plain prose."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    inside = """(id) => Object.fromEntries(['lf-sug-del', 'lf-sug-ins'].map(name =>
        [name, [...(CSS.highlights.get(name) ?? [])]
            .filter(r => document.getElementById(id).contains(r.startContainer))
            .length]))"""
    refill = page.evaluate(inside, "sug-refill")
    assert refill["lf-sug-del"] >= 1 and refill["lf-sug-ins"] >= 1, (
        "an edited sentence must emphasize the words that moved, on both sides"
    )

    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    assert page.evaluate(inside, "sug-refill") == {
        "lf-sug-del": 0,
        "lf-sug-ins": 0,
    }, "deciding must clear the emphasis with the slot it retires"
    assert errors == []
    page.close()


def test_a_whole_swap_paints_no_emphasis(browser, serve):
    """An alignment that shares almost nothing is a replacement, not an edit, and
    emphasis over everything says nothing — the similarity gate every mature diff
    view applies. The whole-slot tints already say a swap is on offer."""
    page, errors = open_page(browser, serve(SWAP_PAGE))
    total = page.evaluate(
        "() => (CSS.highlights.get('lf-sug-del')?.size ?? 0)"
        " + (CSS.highlights.get('lf-sug-ins')?.size ?? 0)"
    )
    assert total == 0, "unrelated old and new text must not be word-marked"
    assert errors == []
    page.close()


def test_a_row_waits_for_the_change_it_decides_to_be_on_screen(browser, serve):
    """A change inside a collapsed container has no line for its row to hang on,
    and an anchor that isn't rendered is no anchor at all: the row falls back to
    the block it was hoisted to and hangs there in the margin, offering to decide
    something the reader can't see. It waits instead, and arrives on the change's
    own line the moment the container opens — a real click on the summary, because
    opening it is the reader's gesture and the reflow it causes is the point."""
    page, errors = open_page(browser, serve(COLLAPSED_PAGE))
    waiting = page.locator("[data-lf-for='sug-boxes']")
    expect(page.locator("[data-lf-for='sug-now']")).to_be_visible()
    expect(waiting).to_be_hidden()

    page.locator("#sum").click()
    expect(waiting).to_be_visible()
    box = "el => el.getBoundingClientRect()"
    row = waiting.evaluate(box)
    assert row["left"] > page.locator("main").evaluate(box)["right"], (
        "the row must arrive in the margin, not over the prose that just opened"
    )
    assert (
        abs(row["top"] - page.locator("#sug-boxes lf-new").evaluate(box)["top"]) <= 5
    ), "and on the line of the change it decides"
    assert errors == []
    page.close()


def test_the_ask_walk_lands_on_a_suggestion_the_reveal_just_opened(browser, serve):
    """Stepping the Asks opens the closed <details> a change waits inside, and does
    it in the same task as the arrival. The row un-waits on the runtime's reveal signal
    rather than at the observer's next frame: settled asynchronously, the arrival landed
    on a display:none element and the reader stayed where they were — at the previous
    decision — while the announce said otherwise, so Enter was aimed at a decision they
    had already seen."""
    page, errors = open_page(browser, serve(COLLAPSED_PAGE))
    page.keyboard.press("a")
    expect(page.locator("#sug-now[data-lf-ask]")).to_have_count(1)
    page.keyboard.press("a")
    expect(page.locator("#later")).to_have_attribute("open", "")
    expect(page.locator("#sug-boxes[data-lf-ask]")).to_have_count(1)
    # The arrival stands on the suggestion; what the reveal has to have done is leave the
    # control that answers it a thing the reader can reach, which a display:none control
    # is not.
    expect(page.locator("[data-lf-for='sug-boxes'] .lf-sug-accept")).to_be_visible()
    assert errors == []
    page.close()


def test_the_rail_survives_every_script_being_removed(browser, serve, tmp_path):
    """A standalone copy of a leaf page is its rendered DOM with the script tags
    dropped, and the pass that placed these rows is script. It doesn't have to run
    again: the row is a child of <main> in the serialized markup, and `left: 100%`
    against the column with `top: anchor(top)` against the change re-solve wherever
    the copy is opened and at whatever width. Including the change inside the card,
    whose positioned ancestor is exactly what a placement done in script would have
    had to correct for — and could not, with no script left to run."""
    page, _ = open_page(browser, serve(SUGGESTION_PAGE))
    page.evaluate("() => document.querySelectorAll('script').forEach(s => s.remove())")
    baked = page.evaluate("() => document.documentElement.outerHTML").replace(
        '<link rel="stylesheet" href="/theme.css">',
        "<style>" + (serve.page_dir / "theme.css").read_text() + "</style>",
    )
    page.close()

    standalone = tmp_path / "standalone.html"
    standalone.write_text(baked)
    loose = browser.new_page(viewport={"width": 1500, "height": 900})
    loose.goto(standalone.as_uri(), wait_until="load")
    assert loose.evaluate("document.querySelectorAll('script').length") == 0
    box = "el => el.getBoundingClientRect()"
    column = loose.locator("main").evaluate(box)["right"]
    for widget in ("sug-refill", "sug-in-card"):
        row = loose.locator(f"[data-lf-for='{widget}']").evaluate(box)
        assert row["left"] > column, f"{widget}'s row lost the rail without its script"
        assert (
            abs(row["top"] - loose.locator(f"#{widget} lf-old").evaluate(box)["top"])
            <= 5
        ), f"{widget}'s row lost its change's line without its script"
    loose.close()


def test_accepting_a_suggestion_settles_it_and_reaches_claude(browser, serve):
    """Accepting collapses the change to the proposal as ordinary prose — no
    tint, no strike — because the live view is the version plus the user's
    actions, and the honoring version only has to catch up.
    The outcome has to reach the log too: what the user sees settle and what
    Claude is told must be the same event.

    The resulting content, Undo control, and notice use the layer's existing state and
    feedback surfaces. No second status is inserted beside them."""
    page, _errors = open_page(browser, serve(SUGGESTION_PAGE))
    row = page.locator("[data-lf-for='sug-refill']")
    accept = row.locator(".lf-sug-accept")
    reject = row.locator(".lf-sug-reject")
    assert accept.get_attribute("aria-label").startswith(
        "Accept the suggested change: Refill a feeder when"
    ), "the button names the proposal, not the text being replaced"
    # Inside the row rather than on the page: the row is positioned, so a button's
    # offset box is its place on that row, and an inline change that reflows the
    # paragraph it sits in carries the whole row with it legitimately. What must not
    # move is one control against the other.
    box = "el => [el.offsetLeft, el.offsetTop, el.offsetWidth, el.offsetHeight]"
    before = accept.evaluate(box)
    # The verb is discovery chrome; at rest the Button is the canonical circle.
    expect(accept.locator(".lf-margin-button-icon")).to_have_attribute(
        "data-lf-icon", "check"
    )

    # A strike and two tints say which words are going and which are proposed, and say
    # it in no text at all: a reader listening got the sentence twice, the two readings
    # contradicting each other, with nothing to say either was a change.
    assert "deletion" in page.locator("#sug-refill lf-old").aria_snapshot()
    assert "insertion" in page.locator("#sug-refill lf-new").aria_snapshot()

    accept.click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    expect(page.locator("#sug-refill lf-new")).to_be_visible()
    expect(accept).to_have_count(0)
    undo_button = row.get_by_role("button", name=re.compile(r"^Undo accepting"))
    expect(undo_button.locator(".lf-margin-button-icon")).to_have_attribute(
        "data-lf-icon", "undo"
    )
    expect(row.locator(".lf-margin-receipt")).to_have_count(0)
    expect(row).not_to_contain_text("Accepted")
    assert undo_button.get_attribute("data-lf-said") is None
    expect(undo_button).to_be_enabled()
    expect(undo_button).to_be_focused()
    assert undo_button.evaluate(box) == before, (
        "Undo moved away from the press it replaces"
    )
    expect(page.locator(".lf-notice")).to_have_text(re.compile(r"^Accepted .+ — sent$"))
    expect(reject).to_be_hidden()
    settled = page.locator("#sug-refill lf-new").evaluate(
        "el => getComputedStyle(el).textDecorationLine + ' ' + getComputedStyle(el).backgroundColor"
    )
    # And the word goes with the marks, the settled slot being ordinary prose now:
    # a reader listening is told about a change while there is one to decide.
    assert "insertion" not in page.locator("#sug-refill lf-new").aria_snapshot()
    assert "line-through" not in settled and "rgba(0, 0, 0, 0)" in settled, (
        f"settled text still wears a pending mark: {settled}"
    )
    # The banner's count follows the page: three pending, one decided.
    expect(page.get_by_role("button", name="Accept all (2)")).to_be_visible()

    # The boundary before reading the shared log: what the press sent has to have a
    # definitive outcome first. The fetch this replaced proved nothing —
    # `wait_for_function` awaits the promise a predicate returns, but a falsy
    # resolution ends the wait instead of polling again, so it came back `False` on
    # the first poll and the read below ran unguarded.
    round_trip(page)
    logged = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert [(e["widget"], e["action"], e["author"]) for e in logged] == [
        ("sug-refill", "accept", "user")
    ]
    page.close()


def test_a_settled_deletion_keeps_undo_on_the_containing_passage(browser, serve):
    """A pure deletion leaves no suggestion box, but Undo remains reachable."""
    page, errors = open_page(browser, serve(PROPOSED_PAGE))
    page.locator("[data-lf-for='sug-delete'] .lf-sug-accept").click()

    expect(page.locator("#sug-delete")).to_be_hidden()
    undo = page.get_by_role("button", name=re.compile(r"^Undo accepting"))
    expect(undo).to_be_visible()
    expect(
        undo.locator("xpath=ancestor::*[contains(@class, 'lf-margin-item')]")
    ).not_to_have_class(re.compile(r"\blf-waiting\b"))
    expect(page.locator(".lf-margin-receipt")).to_have_count(0)
    assert errors == []
    page.close()


def test_rejecting_a_suggestion_promotes_the_surviving_button(browser, serve):
    """Reject leaves an active Undo, never a dead circle or a second status."""
    page, errors = open_page(browser, serve(SHORT_SUGGESTION))
    row = page.locator("[data-lf-for='sug']")
    reject = row.locator(".lf-sug-reject")
    unfolded_button(reject).click()

    expect(reject).to_have_count(0)
    undo_button = row.get_by_role("button", name=re.compile(r"^Undo rejecting"))
    expect(undo_button).to_have_attribute("data-lf-button-primary", "")
    expect(row.locator(".lf-sug-accept")).to_be_hidden()
    expect(row.locator(".lf-margin-receipt")).to_have_count(0)
    expect(row).not_to_contain_text("Rejected")
    undo_button.click()
    round_trip(page)
    expect(page.locator("#sug")).not_to_have_attribute(
        "data-lf-state", re.compile(".+")
    )
    expect(page.locator("[data-lf-for='sug'] .lf-sug-accept")).to_be_visible()
    assert errors == []
    page.close()


def test_a_settled_boxless_suggestion_keeps_its_own_margin_identity(browser, serve):
    """A `display: contents` suggestion still paints through its children; settling it
    must not re-perch Undo on the containing section and change the map target."""
    styled = SHORT_SUGGESTION.replace(
        "</head>", "<style>#sug { display: contents; }</style>\n</head>"
    )
    page, errors = open_page(browser, serve(styled))
    item = page.locator("[data-lf-for='sug']").locator("xpath=..")
    assert item.evaluate("row => row.lfEntry.target.id") == "sug"

    item.locator(".lf-sug-accept").click()
    expect(
        item.get_by_role("button", name=re.compile(r"^Undo accepting"))
    ).to_be_visible()
    expect(item.locator(".lf-margin-receipt")).to_have_count(0)
    assert item.evaluate("row => row.lfEntry.target.id") == "sug"
    assert errors == []
    page.close()


def test_a_refused_undo_keeps_the_outcome_and_can_be_retried(browser, serve):
    """Undo has the same failure lifecycle without inventing a counter-decision."""
    page, errors = open_page(browser, serve(SHORT_SUGGESTION))
    row = page.locator("[data-lf-for='sug']")
    unfolded_button(row.locator(".lf-sug-reject")).click()
    page.route(
        "**/api/event",
        lambda route: route.fulfill(
            status=400,
            json={"ok": False, "final": True, "error": "refused before append"},
        ),
    )
    row.get_by_role("button", name=re.compile(r"^Undo rejecting")).click()
    expect(row.locator(".lf-margin-receipt")).to_have_text("Undo failed · Rejected")
    expect(page.locator("#sug")).to_have_attribute("data-lf-state", "reject")
    item = row.locator("xpath=..")
    expect(item.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    page.unroute("**/api/event")
    item.get_by_role("button", name="Retry", exact=True).click()
    round_trip(page)
    expect(page.locator("#sug")).not_to_have_attribute(
        "data-lf-state", re.compile(".+")
    )
    logged = events_model.read_events(serve.page_dir)
    decision = next(event for event in logged if event.get("action") == "reject")
    assert [event["undoes"] for event in logged if event["kind"] == "undo"] == [
        decision["id"]
    ]
    assert errors and all("400" in error for error in errors)
    page.close()


# `folded` is the layer's own division of the pair rather than a convenience: accept
# rests in the rail as the target's primary Button, and reject is one press behind `…`.
@pytest.mark.parametrize(
    "outcome,verb,folded",
    [("accept", "Accepted", False), ("reject", "Rejected", True)],
)
def test_a_widget_naming_its_own_words_does_not_read_the_runtimes(
    browser, serve, outcome, verb, folded
):
    """The line saying a block carries a comment goes in the block, and a block inside a
    widget is still a block — so `textContent` on a widget's own slot now returns the
    author's words with the runtime's appended. A suggestion labels itself from that slot,
    and offered to accept “Retry three times. 1 comment”. It reads the slot the way the
    page is read instead, which is what `says` is for — read before deciding, because a
    reject retires the very slot the label comes from, and a retired slot says nothing:
    the notice then named the widget's id instead of the words the user judged. Short
    on purpose: the label cuts at 48 characters, which hid this on every shipped example."""
    url = serve(SHORT_SUGGESTION, anchored=[("now", "Retry three times")])
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Vacuous otherwise: the line has to be inside the slot the label is read from.
    assert page.locator("lf-new #now > .lf-mark-note").count() == 1
    control = page.locator(f"[data-lf-for='sug'] .lf-sug-{outcome}")
    (unfolded_button(control) if folded else control).click()
    expect(page.locator(".lf-notice")).to_have_text(
        f"{verb} “Retry three times.” — sent"
    )
    assert errors == []
    page.close()


def test_a_decided_change_folds_away_rather_than_vanishing(browser, serve):
    """A decision may move the page; it may not teleport it.

    A block change is a struck old paragraph stacked over a tinted new one, and
    accepting used to drop the old one with `display: none` in the frame of the press —
    179 measured pixels out of the middle of the shipped design page, with everything
    below jumping up under the pointer that had just pressed. The rule this layer
    already carries is that a change the user asked for may move the page and must do
    it as motion, because motion is the form the eye can follow to where the sentence
    went.

    Held at its first frame rather than sampled mid-flight, which would be a race with
    the clock and would pass on a fast machine either way: the fold is read where it
    starts (the slot's own height, not zero), stepped to the middle, and then let go, so
    what the test proves is the shape of the motion and not how long the run took.

    An inline change is the test below: it has nothing to follow, and folding one would
    be the harm rather than the fix."""
    page, errors = open_page(browser, serve(SHORT_SUGGESTION), init_script=HOLD_MOTION)
    old = page.locator("#sug lf-old")
    after = page.locator("#after")
    tall = old.evaluate("el => el.getBoundingClientRect().height")
    assert tall > 0
    below = after.evaluate("el => el.getBoundingClientRect().top")

    page.locator("[data-lf-for='sug'] .lf-sug-accept").click()
    # Awaited, because the state lands when the log takes the decision rather than in
    # the frame of the press. From that frame it is true everywhere at once — the log
    # carries it, the banner counts it, a second tab converging reads it — and the
    # pixels are the only thing still catching up, which is what the rest measures.
    expect(page.locator("#sug[data-lf-state='accept']")).to_have_count(1)
    held = page.evaluate(
        """() => window.__lfHeld.map((m) => [m.effect.target.tagName.toLowerCase(),
                                             m.effect.getTiming().duration])"""
    )
    assert [t for t, _ in held] == ["lf-old"], (
        f"the retired slot went without motion to follow: {held}"
    )
    at = "() => document.querySelector('#sug lf-old').getBoundingClientRect().height"
    assert page.evaluate(at) == pytest.approx(tall, abs=1), (
        "the fold begins somewhere other than where the paragraph was standing"
    )
    page.evaluate(
        "() => { const m = window.__lfHeld[0];"
        "        m.currentTime = m.effect.getTiming().duration / 2; }"
    )
    middle = page.evaluate(at)
    assert 0 < middle < tall, f"the fold's midpoint is not between its ends: {middle}"

    # The endpoint is part of the motion, not a scheduling gap the finish handler has
    # to beat. Read it synchronously at the exact duration: without a forwards fill the
    # effect has already stopped applying here and the slot springs back to its
    # unanimated height before cleanup gets its turn.
    endpoint = page.evaluate(
        """() => {
          const m = window.__lfHeld[0];
          m.currentTime = m.effect.getTiming().duration;
          return {
            height: m.effect.target.getBoundingClientRect().height,
            opacity: Number(getComputedStyle(m.effect.target).opacity),
            fill: m.effect.getTiming().fill,
          };
        }"""
    )
    assert endpoint["height"] == pytest.approx(0, abs=0.1), (
        f"the fold exposed its unanimated box at the endpoint: {endpoint}"
    )
    assert endpoint["opacity"] == pytest.approx(0, abs=0.001), (
        f"the fold exposed its unanimated ink at the endpoint: {endpoint}"
    )

    page.evaluate("() => window.__lfHeld[0].finish()")
    expect(old).to_be_hidden()
    page.wait_for_function(
        "() => document.querySelector('#sug lf-old').getAnimations().length === 0"
    )
    assert after.evaluate("el => el.getBoundingClientRect().top") < below, (
        "the page never gave back the room the retired paragraph was holding"
    )
    assert errors == []
    page.close()


def test_an_inline_change_is_swapped_rather_than_folded(browser, serve):
    """The other half of the rule above, and the half where folding would be the harm.

    A height to animate means a `display: block` held over the slot for the duration, so
    a few words swapped mid-sentence would open a paragraph break and close it again —
    motion answering a change that moved nothing. The shipped inline corpus is the case,
    and what it asserts is that nothing was started at all."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE), init_script=HOLD_MOTION)
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    assert page.evaluate("() => window.__lfHeld.length") == 0, (
        "a few words swapped inside a line were given a fold, and a block box to do it in"
    )
    assert errors == []
    page.close()


def test_a_reader_who_asked_for_less_motion_gets_the_collapse_at_once(browser, serve):
    """The fold is a courtesy to the eye, and an eye that asked for stillness is owed
    the outcome instead — the same bargain the board's own FLIP makes.

    Asked of the context rather than of the page, because the runtime reads the
    preference once as it loads: emulating it afterwards changes what the media query
    would answer and not what the module already recorded."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        color_scheme="light",
        reduced_motion="reduce",
    )
    try:
        page, errors = open_page(
            browser, serve(SHORT_SUGGESTION), context=context, init_script=HOLD_MOTION
        )
        page.locator("[data-lf-for='sug'] .lf-sug-accept").click()
        expect(page.locator("#sug lf-old")).to_be_hidden()
        assert page.evaluate("() => window.__lfHeld.length") == 0, (
            "a reader who asked for less motion was given a fold to sit through"
        )
        assert errors == []
    finally:
        context.close()


def test_accept_all_decides_every_pending_suggestion(browser, serve):
    """The banner's button is a shortcut for the user who has read the page
    and wants all of it, so it has to reach the ones their eye didn't: the
    suggestion inside a widget, whose controls dock in flow rather than hang in
    the margin. Each is decided individually, so the log records what was
    consented to one change at a time rather than one blanket yes."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    page.get_by_role("button", name="Accept all (3)").click()

    for widget in ("sug-refill", "sug-thistle", "sug-in-card"):
        expect(page.locator(f"#{widget} lf-new")).to_be_visible()
        # Waited for, not read once: each is decided by its own round trip, so the
        # last of them is still in flight when the first has settled.
        expect(
            page.locator(f"[data-lf-for='{widget}']").get_by_role(
                "button", name=re.compile(r"^Undo accepting")
            )
        ).to_be_visible()
        expect(
            page.locator(f"[data-lf-for='{widget}'] .lf-margin-receipt")
        ).to_have_count(0)
    for widget in (
        "sug-refill",
        "sug-in-card",
    ):  # the two that replace rather than insert
        expect(page.locator(f"#{widget} lf-old")).to_be_hidden()
    # Nothing left to accept, so the button says nothing rather than saying zero.
    expect(page.get_by_role("button", name=re.compile("Accept all"))).to_be_hidden()

    # The controls settle from their individual authoritative answers. Wait for the
    # whole outbox as well: the rows are asserted one at a time above, while this is
    # the boundary before reading the shared log as a sequence.
    round_trip(page)
    logged = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert [(e["widget"], e["action"]) for e in logged] == [
        ("sug-refill", "accept"),
        ("sug-thistle", "accept"),
        ("sug-in-card", "accept"),
    ]
    assert errors == []
    page.close()


def test_a_decision_the_server_never_took_never_shows_as_taken(browser, serve):
    """A decision is painted when the log takes it, never before, so a send the
    server refuses leaves the page exactly as it was. Settling first and putting it
    back on failure said the same thing in the end and flickered on the way: the
    press against a closed session painted one frame of settled content and Undo over
    a folding slot before rewinding it."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))

    def refuse_attempt(route):
        route.fulfill(
            status=400,
            json={
                "ok": False,
                "error": "refused before append",
                "final": True,
            },
        )

    page.route("**/api/event", refuse_attempt)
    # Watch the attribute across every frame, not just after: a rewind is only
    # visible while it is happening, and the end state is the same either way.
    page.evaluate(
        """() => {
          window.__settled = [];
          new MutationObserver(() => {
            window.__settled.push(
              document.getElementById('sug-refill').dataset.lfState ?? null);
          }).observe(document.getElementById('sug-refill'),
                     {attributes: true, attributeFilter: ['data-lf-state']});
        }"""
    )
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()

    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    assert page.locator("#sug-refill").get_attribute("data-lf-state") is None
    assert page.evaluate("() => window.__settled") == [], (
        "the refused decision must never have been on the element at all"
    )
    item = page.locator('[data-lf-margin-for="sug-refill"]')
    expect(item.locator(".lf-margin-receipt")).to_have_text("Failed")
    expect(item).to_have_attribute("data-lf-state", "failed")
    expect(item.locator(".lf-margin-more")).to_be_hidden()
    expect(item.get_by_role("button", name="Retry", exact=True)).to_be_visible()
    expect(item.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    expect(item.get_by_role("button", name="Details", exact=True)).to_have_count(0)
    expect(page.locator("#sug-refill")).not_to_have_attribute("aria-busy", "true")
    item.get_by_role("button", name="Cancel", exact=True).click()
    expect(item.locator(".lf-margin-receipt")).to_have_count(0)
    expect(item.locator(".lf-sug-accept")).to_be_focused()
    item.locator(".lf-sug-accept").click()
    expect(item.locator(".lf-margin-receipt")).to_have_text("Failed")
    # And the page's own count is derived from that, so it comes back too.
    expect(page.get_by_role("button", name="Accept all (3)")).to_be_visible()
    expect(page.locator(".lf-notice")).to_contain_text("Couldn't send")
    assert [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ] == []

    # Retry starts a fresh attempt without reloading or pretending the failed one won.
    page.unroute("**/api/event")
    item.get_by_role("button", name="Retry", exact=True).click()
    round_trip(page)
    logged = actions(serve.page_dir)
    assert [(event["widget"], event["action"]) for event in logged] == [
        ("sug-refill", "accept")
    ]
    assert logged[0]["attempt"]
    undo(page)
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    assert errors and all("400" in error for error in errors)
    page.close()


def test_an_ambiguous_decision_stays_one_gesture_while_retrying(browser, serve):
    """Losing an accepted action answer keeps the original press busy and retries
    that exact attempt. Repeating the press cannot mint a second decision that one
    undo would merely uncover."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    requests = []
    accepted = []

    def lose_first_answer(route):
        requests.append(route.request.post_data_json)
        if len(requests) == 1:
            accepted.append(route.fetch().status)
            refuse(route)
        else:
            route.continue_()

    # Force recovery through the outbox rather than letting a periodic read observe
    # the accepted attempt first. Both are valid recovery paths; this one proves the
    # retry reuses the identity whose answer was lost.
    page.route("**/api/state*", refuse)
    page.route("**/api/event", lose_first_answer)
    accept = page.locator("[data-lf-for='sug-refill'] .lf-sug-accept")
    with page.expect_event(
        "requestfailed", predicate=lambda request: "/api/event" in request.url
    ):
        accept.click()
    expect(page.locator("#sug-refill")).to_have_attribute("aria-busy", "true")
    expect(page.locator(".lf-notice")).to_contain_text("retrying your change")

    expect(accept).to_be_disabled()
    accept.evaluate("button => button.click()")
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    assert accepted == [200]
    assert len(requests) == 2
    assert len({request["attempt"] for request in requests}) == 1
    assert [
        (event["widget"], event["action"]) for event in actions(serve.page_dir)
    ] == [("sug-refill", "accept")]

    undo(page)
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    assert errors == []
    page.close()


def test_a_second_press_inside_the_round_trip_adds_no_second_decision(browser, serve):
    """One press, one decision — and the element's own state is no longer what makes
    that true. The decided state used to be written in the frame of the press, so a
    control pressed twice refused itself on the second; it now lands with the log's
    answer, leaving a whole round trip in which both controls are still offering.
    Presses made in that gap would each be a line in the log for one act, and an
    accept followed by a reject would resolve the thread the accept answers and then
    record the opposite outcome over it.

    Neither of those presses can be caught in the wire: `post` sends one action at a
    time, so they queue behind the held one instead of reaching the route. What they
    would leave is a line each in the log once the queue drains, and that is where
    this reads them."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    row = page.locator("[data-lf-for='sug-refill']")
    row.locator(".lf-sug-accept").click()
    holding(page, held, 1, "the decision")
    expect(row.locator(".lf-sug-accept")).to_be_disabled()
    row.locator(".lf-sug-accept").evaluate("button => button.click()")
    expect(unfolded_button(row.locator(".lf-sug-reject"))).to_be_disabled()
    row.locator(".lf-sug-reject").evaluate("button => button.click()")

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator("#sug-refill[data-lf-state='accept']")).to_have_count(1)
    assert [
        (e["widget"], e["action"])
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "action"
    ] == [("sug-refill", "accept")]
    assert errors == []
    page.close()


def test_a_wait_the_reader_would_notice_says_so_and_a_short_one_says_nothing(
    browser, serve
):
    """The press paints nothing until the log answers, so a wait long enough to
    notice has to say it is waiting — and a wait too short to notice must not, or the
    look would flash on and off exactly where the settle-then-rewind flicker used to
    be. One delayed rule covers both, and it is keyed on aria-busy rather than on any
    tag, so lf-draft's own busy word is painted by it too.

    Held in the wire rather than timed against a real answer: the delay is measured
    from the press either way, and a send that never lands is the only way to read
    both sides of it without racing the machine the suite is on."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    resting = page.locator("[data-lf-for='sug-refill']").bounding_box()
    # Pressed and sampled inside the page: what painted and when is not a fact the
    # browser reports outward, and a reading taken over a CDP round trip would be
    # racing the delay rather than measuring it. Each frame is placed on the rule's
    # own clock rather than on the wall clock the press was made on — the animation
    # starts at the frame the busy attribute is first painted in, and what the press
    # does between the two is the layer's own work, not this rule's. Timed from the
    # press the whole 200ms delay and 140ms fade all but fill a fixed window, and a
    # loaded machine spends the remainder before the first frame; timed from the
    # animation, the delay and the fade are the only durations being read.
    frames = page.evaluate(
        """async () => {
          const el = document.getElementById('sug-refill');
          const out = [];
          let stop = false;
          const tick = () => {
            // Opacity first: reading it flushes the style that starts the animation,
            // so the frame it begins in reports the animation rather than nothing.
            const painted = Number(getComputedStyle(el).opacity);
            const [busy] = el.getAnimations();
            out.push([
              busy ? Number(busy.currentTime) : null,
              busy ? busy.playState : null,
              painted,
            ]);
            if (!stop) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
          document.querySelector("[data-lf-for='sug-refill'] .lf-sug-accept").click();
          await new Promise((r) => setTimeout(r, 700));
          stop = true;
          return out;
        }"""
    )
    # Before the rule has anything to say: the frames the press had not yet reached,
    # and the ones inside its delay. Once it has said it: the frames after the fade
    # has run, which the animation states as its own end rather than as a deadline.
    early = [o for elapsed, _state, o in frames if elapsed is None or elapsed < 150]
    late = [o for _elapsed, state, o in frames if state == "finished"]
    assert early and set(early) == {1}, (
        f"the wait was announced before it was one: {early}"
    )
    assert late and set(late) == {0.5}, f"a wait worth noticing said nothing: {late}"
    expect(page.locator("#sug-refill")).to_have_attribute("aria-busy", "true")
    # And it says it without moving the line the press was made on: the row the reader
    # just pressed stands where it stood, so a second press has the same target.
    assert page.locator("[data-lf-for='sug-refill']").bounding_box() == resting

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator("#sug-refill[data-lf-state='accept']")).to_have_count(1)
    expect(page.locator("#sug-refill")).not_to_have_attribute("aria-busy", "true")
    assert errors == []
    page.close()


def test_a_decision_travels_between_tabs_and_the_log_has_the_last_word(browser, serve):
    """Two windows on one page are two views of one log, not two documents. A
    decision taken in either arrives in the other by the same replay that keeps a
    reload's drag, and the record it leaves in the margin has to arrive with it: the
    tab that receives one settles it without the click that settled the tab that sent
    it, and a row still offering the press is a window disagreeing with the log about
    what has already been decided. Where the two disagree, the later entry in the log
    is what both end on."""
    url = serve(SUGGESTION_PAGE)
    first, first_errors = open_page(browser, url)
    second, second_errors = open_page(browser, url)

    # A tab that did not click has only its own poll to learn from.
    first.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    told(second)
    expect(second.locator("#sug-refill lf-old")).to_be_hidden()
    expect(second.locator("#sug-refill lf-new")).to_be_visible()
    # Nothing is left to decide. Replay replaces both offers with the existing Undo
    # action without adding a second status beside the settled content.
    row = second.locator("[data-lf-for='sug-refill']")
    accepted = row.get_by_role("button", name=re.compile(r"^Undo accepting"))
    expect(accepted.locator(".lf-margin-button-icon")).to_have_attribute(
        "data-lf-icon", "undo"
    )
    expect(row.locator(".lf-margin-receipt")).to_have_count(0)
    expect(accepted).to_be_enabled()
    # Its pair leaves; the surviving content and Undo carry the settled state.
    rejected = second.locator("[data-lf-for='sug-refill'] .lf-sug-reject")
    expect(rejected).to_be_hidden()
    expect(second.get_by_role("button", name="Accept all (2)")).to_be_visible()

    # Now the race the controls make possible: a window cut off from the log still
    # shows both buttons, so the user can decide the other way there. Two
    # decisions on one change, and the log's order — not either tab's belief —
    # settles it for both once the cut-off one catches up.
    third, third_errors = open_page(browser, url)
    cut = CutOff().hold(third)
    first.locator("[data-lf-for='sug-thistle'] .lf-sug-accept").click()
    # In the log before the reject is clicked, so which one is later is this test's
    # to decide rather than the network's.
    told(second)
    expect(second.get_by_role("button", name="Accept all (1)")).to_be_visible()
    unfolded_button(third.locator("[data-lf-for='sug-thistle'] .lf-sug-reject")).click()
    cut.restore()
    # The reject went out over a live channel, so every tab has to read it back —
    # the cut-off one included, which is where it stops being its own local click.
    for tab in (first, second, third):
        told(tab)
        expect(tab.locator("#sug-thistle lf-new")).to_be_hidden()
    assert first_errors == [] and second_errors == [] and third_errors == []
    for tab in (first, second, third):
        tab.close()


def test_the_banner_counts_completed_asks_against_the_active_total(browser, serve):
    """Two semantic readings, collected from declarations rather than from any tag.

    The count used to be a query for `lf-suggestion:not([data-lf-state])`: perfect for
    suggestions, and silently nothing for every other thing a page waits on. What
    makes an instance an Ask is now the entry's own attribute condition, and the entry
    explicitly names which state verbs answer it — so this page's five active Asks are
    one authored answer, a live question, a change nobody has decided, and two explicit
    questions nested in tasks.

    The rest of the page is every way of not being one, and each was a way of getting
    it wrong: a group whose pick the version already carries (`chosen`, with nothing in
    the log — a fold-only reading counts it as open on every shipped example), one the
    author has settled, one that takes no picks at all, an exhibited decision inside a
    lf-specimen, and a milestone at `blocked`, which is the same word on a widget whose
    entry does not declare it."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    decisions = page.locator(".lf-asks")
    expect(decisions).to_have_text("Asks 1/5")
    # The blanket answer counts the same list, narrowed to the one kind that declares
    # a verb for it, so the two numbers cannot describe different sets.
    expect(page.locator(".lf-answer-all")).to_have_text("Accept all (1)")

    # Answering advances the numerator without erasing the denominator. A pick is state
    # the page itself carries, so the count follows the click; the suggestion's outcome
    # is in the log alone, so that one follows the round trip.
    page.locator("#lq-token").click()
    expect(decisions).to_have_text("Asks 2/5")
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(decisions).to_have_text("Asks 3/5")
    expect(page.locator(".lf-answer-all")).to_be_hidden()

    # And clearing the pick asks again: an empty answer is no answer, which only a
    # reading of what the page carries can say.
    page.locator("#lq-token").click()
    expect(decisions).to_have_text("Asks 2/5")
    assert errors == []
    page.close()


def test_a_key_walks_the_page_s_open_asks(browser, serve):
    """t/T step the open threads; a/A step the things the page is waiting on the reader
    for. The category letter stays under one finger: lowercase advances and Shift goes
    back. Both walks repeat when held because walking often takes several presses.
    Both clamp at the ends like every other one-dimensional list, so another press keeps
    the reader on the edge instead of jumping across the page.

    The landing is marked on the ask and stands the reader on it, which is the same
    element the scroll has just brought to the top of the window — a walk that landed the
    control instead put them on whatever the decision's context and evidence had pushed
    off the bottom of the screen. Its contributed actions are directly addressable there;
    the controls themselves remain the next Tab stops."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    decisions = page.locator(".lf-asks")
    expect(decisions).to_have_text("Asks 1/5")
    walked = []
    for expected in [*ASKS_IN_ORDER, ASKS_IN_ORDER[-1]]:
        page.keyboard.press("a")
        # The ring is painted from the focus, in the frame after the press, so waiting
        # for it on the Ask this press stepped to is both the wait and the assertion —
        # a bare count would pass on the ring an earlier press left standing.
        expect(page.locator(f"#{expected}[data-lf-ask]")).to_have_count(1)
        # And exactly one decision wears it, the reader standing in one place at a time.
        expect(page.locator(STANDING_ASK)).to_have_count(1)
        # Walking changes the ring and not the durable progress count.
        expect(decisions).to_have_text("Asks 1/5")
        walked.append(
            page.evaluate(
                "() => document.activeElement.tagName.toLowerCase()"
                "      + ' ' + document.activeElement.className"
            )
        )
    assert walked == [
        "lf-ask ",  # the question's own region, its picks a Tab away
        "lf-suggestion ",  # the suggestion itself, its ✓ Accept hoisted into the margin
        "lf-ask ",  # the task's nested review question
        "lf-ask ",
        "lf-ask ",
    ], f"the walk landed on something else: {walked}"

    # And back, including one press past the first edge. The step off a suggestion is
    # measured from the suggestion rather than from the ✓ Accept holding the focus —
    # that row is hoisted out into the page margin as a sibling of the block it decides,
    # so a walk reading it where it hangs would step back onto the change the reader is
    # standing on.
    for expected in [*reversed(ASKS_IN_ORDER[:-1]), ASKS_IN_ORDER[0]]:
        page.keyboard.press("Shift+a")
        expect(page.locator(f"#{expected}[data-lf-ask]")).to_have_count(1)
        expect(page.locator(STANDING_ASK)).to_have_count(1)
        expect(decisions).to_have_text("Asks 1/5")

    # Every request has an answering control, so the walk never has to lend a tab stop
    # to authored content.
    expect(page.locator(STANDING_ASK)).to_have_count(1)
    # Asked of the tag's dash, the platform's own mark of a widget element, which is what
    # the export's own sweep for stray stops asks (BAKE).
    assert (
        page.evaluate(
            "() => [...document.querySelectorAll('main [tabindex]')]"
            "  .filter(el => el.tagName.includes('-') && !el.hasAttribute('data-lf-ask'))"
            "  .map(el => el.tagName.toLowerCase() + '#' + el.id)"
        )
        == []
    ), "a lent tab stop was left on a decision the reader has walked off"

    # The overlay and the key line offer it because there is something to reach.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_contain_text("waiting on you for")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-keyline")).to_contain_text("asks")

    # Leaving the ask takes the place off the count the way it takes the ring off the
    # page: a click into the prose is the reader standing nowhere in the list.
    page.locator("#h").click()
    expect(page.locator(STANDING_ASK)).to_have_count(0)
    expect(decisions).to_have_text("Asks 1/5")

    # An answered decision leaves the walk: deciding the change on its own control is where
    # the reader now stands, and the next press reaches what followed it rather than the
    # change they have just settled. The control the reader answered from keeps the
    # focus. It leaves the open walk while the completed/total count advances.
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(decisions).to_have_text("Asks 2/5")
    page.keyboard.press("a")
    expect(page.locator("#t-baffles-decision[data-lf-ask]")).to_have_count(1)
    expect(page.locator("#t-baffles-decision")).to_be_focused()
    expect(decisions).to_have_text("Asks 2/5")
    assert errors == []
    page.close()


def test_an_ask_arrival_starts_with_the_context_that_frames_it(browser, serve):
    """The decision is the question's whole reading region, not only its answer control.

    An options group used to be both the state owner and the navigation target. When
    the heading, premise, and evidence stood immediately above it, `d` centred the
    options and made the reader scroll backward before they could answer. `lf-ask`
    encodes that broader unit while the nested x-awaits widget still owns the action:
    the walk rings the region, aligns its opening below the banner, and stands the
    reader on it.

    On it, and not on the control that answers it, which was where the walk landed until
    the scroll and the focus were measured against each other. The scroll puts the
    region's opening at the top of the window and the answering control is as far down as
    the context and evidence are long: on the shipped corpus at 1200x900 the heading stood
    at 54px and the focused pick ran from 847 to 1107 in a 900px window, so the reader was
    told to look at one thing while standing on another they could not see, and their next
    Space would have worked it. The picks are the next Tab stops instead, which is what a
    stop at `tabindex: -1` on the region buys: it keeps its place in document order and
    everything inside the decision comes after it.
    """
    page, errors = open_page(browser, serve(ASK_WITH_CONTEXT_PAGE))
    # Short enough that even the pick in the card's compact header falls past the foot of
    # the window once the decision's opening is at its head, which is the shape the fault
    # has: the walk cannot both show the question and stand the reader on its answer.
    resized(page, 900, 230)

    # The options really do begin below context, and enough page follows the region for
    # aligning its start to be possible. Without either condition, centring the inner
    # widget could happen to look like the requested arrival.
    before = page.evaluate(
        """() => {
          const ask = document.getElementById('storage-decision').getBoundingClientRect();
          const options = document.getElementById('storage-options').getBoundingClientRect();
          return {context: options.top - ask.top,
                  room: document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight};
        }"""
    )
    assert before["context"] > 100, (
        "the fixture has no meaningful context above the options"
    )
    assert before["room"] > 500, "the page has no room to put the decision at its start"

    page.keyboard.press("a")
    expect(page.locator("#storage-decision")).to_be_focused()
    expect(page.locator("#storage-decision")).to_have_attribute("data-lf-ask", "1")
    expect(page.locator("#storage-options")).not_to_have_attribute("data-lf-ask", "1")
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)
    # Where the reader was left is on the screen the walk has just arranged, and the pick
    # the walk used to stand them on is the measurement that says the two cannot both be.
    standing = page.evaluate(
        """() => {
          const box = document.activeElement.getBoundingClientRect();
          const pick = document.querySelector('#storage-options .lf-pick')
            .getBoundingClientRect();
          return {top: box.top, pick: pick.top, height: innerHeight};
        }"""
    )
    assert standing["pick"] > standing["height"], (
        f"the first pick is on screen at this size, so standing on it would have been no "
        f"worse than standing on the Ask and nothing below is evidence: {standing}"
    )
    assert 0 <= standing["top"] < standing["height"], (
        f"the walk left the reader standing off the screen it had just scrolled: "
        f"{standing}"
    )
    landed = page.evaluate(
        """() => {
          const ask = document.getElementById('storage-decision').getBoundingClientRect();
          const options = document.getElementById('storage-options').getBoundingClientRect();
          const clear = parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop);
          return {ask: ask.top, options: options.top, clear};
        }"""
    )
    assert abs(landed["ask"] - landed["clear"]) <= 2, (
        f"the Ask starts at {landed['ask']:.1f}px instead of below the banner at "
        f"{landed['clear']:.1f}px"
    )
    assert landed["options"] > landed["ask"] + 100, (
        "the arrival did not leave the Ask's context above its options"
    )

    # Tab remains the complementary route into the widget's controls. Read after the
    # landing above, because a Tab onto a control below the fold scrolls to it and would
    # take the arrival's own geometry with it. The Ask action context remains the same.
    page.keyboard.press("Tab")
    expect(page.locator("#storage-options .lf-pick").first).to_be_focused()
    expect(
        page.locator("#storage-options > lf-option > .lf-address[data-lf-ask-address]")
    ).to_have_text(["1", "2"])

    # And nothing of the borrowed stop is left behind: PAGE_PAINT_ATTRIBUTES is the whole
    # of what the runtime may leave on an author's element, and `tabindex` is not in it.
    page.keyboard.press("Escape")
    expect(page.locator("#storage-decision")).not_to_have_attribute("tabindex", "-1")
    assert errors == []
    page.close()


def test_the_ask_itself_addresses_each_contributed_action(browser, serve):
    """a lands semantic focus on the Ask; digits work its exact action list there.

    The list is contributed by the decision widget rather than inferred from generated
    descendants: options own controls inside the Ask, while a suggestion's Buttons are
    hoisted into the shared margin. Core gives either list the same stable numeric
    projection, and pressing a digit activates the native control without first moving
    focus into the widget.
    """
    page, errors = open_page(browser, serve(ASKS_PAGE))
    resized(page, 900, 900)

    page.keyboard.press("a")
    expect(page.locator("#live-question-decision")).to_be_focused()
    assert "1–2\nKeep the store / Signed tokens" in key_line(page)
    expect(
        page.locator("#live-question > lf-option > .lf-address[data-lf-ask-address]")
    ).to_have_text(["1", "2"])

    page.keyboard.press("2")
    expect(page.locator("#lq-token")).to_have_attribute("chosen", "")
    round_trip(page)
    expect(page.locator(".lf-asks")).to_have_text("Asks 2/5")

    page.keyboard.press("a")
    expect(page.locator("#sug-refill")).to_be_focused()
    assert "1–2\nAccept / Reject" in key_line(page)
    expect(page.locator("[data-lf-for='sug-refill'] .lf-sug-accept")).to_have_attribute(
        "aria-keyshortcuts", "1"
    )
    expect(page.locator("[data-lf-for='sug-refill'] .lf-sug-reject")).to_have_attribute(
        "aria-keyshortcuts", "2"
    )
    page.keyboard.press("2")
    round_trip(page)
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "reject")

    assert errors == []
    page.close()


def test_ask_contextual_addresses_skip_explicit_numeric_bindings(browser, serve):
    """A package's own digit keeps its meaning beside keyless Decision commands."""
    page, errors = open_page(browser, serve(SHORT_SUGGESTION))
    resized(page, 900, 900)

    page.evaluate(
        """async () => {
          const {commands} = await import('/runtime/widget-api.js');
          const suggestion = document.getElementById('sug');
          const inspect = document.createElement('button');
          inspect.textContent = 'Inspect';
          inspect.onclick = () => { inspect.dataset.activated = '1'; };
          suggestion.append(inspect);
          commands(inspect, 'Explicit numeric action', [{
            id: 'test.inspect',
            keys: ['1'],
            control: inspect,
            label: 'I',
            decision: 'Inspect',
            does: 'Inspect this suggestion',
            line: 'Inspect',
            run: () => inspect.click(),
          }]);
        }"""
    )

    # The source scope keeps its presentation override in the global reference. Once the
    # reader enters the Ask, that projection presents the binding it actually resolves.
    page.keyboard.press("?")
    page.keyboard.press("?")
    inspect_reference = page.locator('.lf-help tr[data-lf-command="test.inspect"]')
    expect(inspect_reference.locator("kbd")).to_have_text("I")
    expect(inspect_reference.locator(".lf-key-sequence")).to_have_attribute(
        "aria-label", "I"
    )
    page.keyboard.press("Escape")

    inspect = page.get_by_role("button", name="Inspect")
    inspect.focus()
    assert "I\nInspect" in key_line(page)

    page.keyboard.press("a")
    expect(page.locator("#sug")).to_be_focused()
    assert "2 / 3 / 1\nAccept / Reject / Inspect" in key_line(page)
    expect(inspect).to_have_attribute("aria-keyshortcuts", "1")

    page.keyboard.press("1")
    expect(inspect).to_have_attribute("data-activated", "1")

    assert errors == []
    page.close()


def test_ask_action_name_functions_must_return_text(browser, serve):
    """Computed row and route names fail with the command-scoped contract error."""
    page, errors = open_page(browser, serve(SHORT_SUGGESTION))

    messages = page.evaluate(
        """async () => {
          const {decisionControls} = await import('/runtime/keyboard/bindings.js');
          const source = document.getElementById('sug');
          const control = document.createElement('button');
          source.append(control);
          const read = (row) => {
            try {
              decisionControls([{source, row}], 'the test Ask');
            } catch (error) {
              return error.message;
            }
            return null;
          };
          return {
            row: read({
              id: 'test.invalid-row-name', keys: [], control,
              decision: () => true,
            }),
            route: read({
              id: 'test.route-family', keys: ['ArrowLeft'], control,
              routes: [{
                id: 'test.invalid-route-name', binding: 'ArrowLeft',
                decision: () => true,
              }],
            }),
          };
        }"""
    )

    assert messages == {
        "row": "leaf: test.invalid-row-name in the test Ask has no Decision action name",
        "route": (
            "leaf: test.invalid-route-name in the test Ask has no Decision action name"
        ),
    }
    assert errors == []
    page.close()


def test_ask_explicit_commands_do_not_consume_contextual_address_slots(browser, serve):
    """Only keyless Decision commands count against the nine numeric addresses."""
    page, errors = open_page(browser, serve(SHORT_SUGGESTION))
    resized(page, 900, 900)

    page.evaluate(
        """async () => {
          const {commands} = await import('/runtime/widget-api.js');
          const suggestion = document.getElementById('sug');
          for (const [index, key] of [...'bcdefghij'].entries()) {
            const binding = `Alt+${key}`;
            const control = document.createElement('button');
            control.textContent = `Explicit ${key}`;
            suggestion.append(control);
            commands(control, `Explicit ${key}`, [{
              id: `test.explicit-${index}`,
              keys: [binding],
              control,
              decision: `Explicit ${key}`,
              does: `Run explicit command ${key}`,
              line: `Explicit ${key}`,
              run: () => control.click(),
            }]);
          }
          const later = document.createElement('button');
          later.textContent = 'Later keyless';
          later.onclick = () => { later.dataset.activated = '1'; };
          suggestion.append(later);
          commands(later, 'Later keyless action', [{
            id: 'test.later-keyless',
            keys: [],
            control: later,
            decision: 'Later keyless',
            does: 'Run the later keyless command',
            line: 'Later keyless',
            run: () => later.click(),
          }]);
        }"""
    )

    page.keyboard.press("a")
    expect(page.locator("#sug")).to_be_focused()

    # Accept and Reject take 1 and 2; nine explicitly bound commands consume no numeric
    # address, so the keyless command declared after all of them still receives 3.
    page.keyboard.press("3")
    expect(page.get_by_role("button", name="Later keyless")).to_have_attribute(
        "data-activated", "1"
    )

    assert errors == []
    page.close()


def test_ask_option_addresses_stay_one_projection_when_focus_enters_a_card(
    browser, serve
):
    """Tab keeps the Ask's address projection on the same option-card faces."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    resized(page, 900, 900)

    page.keyboard.press("a")
    ask = page.locator("#live-question > lf-option > .lf-address[data-lf-ask-address]")
    expect(ask).to_have_text(["1", "2"])
    ask_centers = ask.evaluate_all(
        """nodes => nodes.map(node => {
          const box = node.getBoundingClientRect();
          return {x: box.left + box.width / 2, y: box.top + box.height / 2 + scrollY};
        })"""
    )

    page.keyboard.press("Tab")
    focused = page.locator(
        "#live-question > lf-option > .lf-address[data-lf-ask-address]"
    )
    expect(focused).to_have_text(["1", "2"])
    focused_centers = focused.evaluate_all(
        """nodes => nodes.map(node => {
          const box = node.getBoundingClientRect();
          return {x: box.left + box.width / 2, y: box.top + box.height / 2 + scrollY};
        })"""
    )
    assert len(ask_centers) == len(focused_centers) == 2
    for ask_point, focused_point in zip(ask_centers, focused_centers, strict=True):
        assert ask_point["x"] == pytest.approx(focused_point["x"], abs=0.5)
        assert ask_point["y"] == pytest.approx(focused_point["y"], abs=0.5)

    assert errors == []
    page.close()


def test_ask_addresses_do_not_cover_their_key_line(browser, serve):
    """A row address that reaches the key line yields to the legend naming its digit."""
    page, errors = open_page(browser, serve(ADDRESS_PAGE))
    resized(page, 900, 520)

    # The first Ask uses titled cards, whose trailing addresses cannot meet the leading
    # key line. Step to the compact row Ask, where both occupy the leading edge.
    page.keyboard.press("a")
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)
    page.keyboard.press("a")
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)
    expect(
        page.locator("#rows > lf-option > .lf-address[data-lf-ask-address]")
    ).to_have_text(["1", "2"])
    # Put the second row's address one pixel into the key line's band. The first stays a
    # row above it, so a placement pass that reserves the legend keeps one and removes
    # the other. Calculate the scroll from their current boxes rather than pinning the
    # fixture to today's spacing.
    page.evaluate(
        """() => {
          const addresses = document.querySelectorAll(
            '#rows > lf-option > .lf-address[data-lf-ask-address]'
          );
          const last = addresses[addresses.length - 1].getBoundingClientRect();
          const line = document.querySelector('.lf-keyline').getBoundingClientRect();
          scrollTo(0, scrollY + last.top - line.top - 1);
        }"""
    )
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)
    expect(
        page.locator("#rows > lf-option > .lf-address[data-lf-ask-address]")
    ).to_have_count(1)
    geometry = page.evaluate(
        """() => {
          const read = node => {
            const box = node.getBoundingClientRect();
            return {left: box.left, right: box.right, top: box.top, bottom: box.bottom};
          };
          return {
            line: read(document.querySelector('.lf-keyline')),
            chips: [...document.querySelectorAll(
              '.lf-ask-addresses > .lf-ask-address, [data-lf-ask-address]'
            )].map(read),
          };
        }"""
    )
    assert geometry["chips"], "the fixture did not leave an Ask address on screen"
    assert all(
        chip["right"] <= geometry["line"]["left"]
        or geometry["line"]["right"] <= chip["left"]
        or chip["bottom"] <= geometry["line"]["top"]
        or geometry["line"]["bottom"] <= chip["top"]
        for chip in geometry["chips"]
    ), geometry

    assert errors == []
    page.close()


def test_a_needed_draft_contributes_its_current_ask_action(browser, serve):
    source = leaf_page(
        "needed draft address",
        """
<h1>Supply the copy</h1>
<lf-ask id="copy-ask"><h2>What should the invitation say?</h2>
  <lf-draft id="copy" needed><pre>Draft invitation</pre></lf-draft>
</lf-ask>
""",
    )
    page, errors = open_page(browser, serve(source))

    page.keyboard.press("a")
    expect(page.locator("#copy-ask")).to_be_focused()
    assert "1\nEdit" in key_line(page)
    page.keyboard.press("1")
    expect(page.get_by_role("textbox", name="Edit copy")).to_be_focused()

    assert errors == []
    page.close()


def test_an_ask_that_cannot_name_itself_arrives_on_the_words_that_explain_it(
    browser, serve
):
    """A change to a phrase has no region to declare, so the document supplies one.

    An x-ask-surface widget states its own arrival region: a heading, the context, then the
    control. A suggestion can stand mid-sentence, so it can never satisfy "an ask must
    name itself without context outside the ask" and no region can be written round it.
    Arriving on the change alone put its own top edge under the banner and took the
    sentence and the heading with it, leaving the reader on the change with nothing on
    screen saying what they would be accepting.

    The heading, the sentence, and the change are read together: a landing on the
    sentence alone would satisfy a heading assertion by accident on a page whose
    heading happens to sit one line above it, and this page's does not.
    """
    page, errors = open_page(browser, serve(SUGGESTION_IN_CONTEXT_PAGE))
    resized(page, 900, 500)

    # The change is below the fold and the page can scroll, or standing still would look
    # like the arrival this asks for.
    assert page.evaluate(
        """() => {
          const box = document.getElementById('sc-sug').getBoundingClientRect();
          const se = document.scrollingElement;
          return box.top > se.clientHeight && se.scrollHeight - se.clientHeight > 500;
        }"""
    ), "the fixture already shows the change on the first screen"

    page.keyboard.press("a")
    expect(page.locator("#sc-sug")).to_be_focused()
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)

    landed = page.evaluate(
        """() => {
          const at = (id) => document.getElementById(id).getBoundingClientRect();
          return {
            heading: at('sc-api-heading').top,
            sentence: at('sc-api-why').top,
            change: at('sc-sug').top,
            foot: at('sc-sug').bottom,
            view: document.scrollingElement.clientHeight,
            clear: parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop),
          };
        }"""
    )
    assert abs(landed["heading"] - landed["clear"]) <= 2, (
        f"the arrival put the heading over this change at {landed['heading']:.1f}px "
        f"rather than below the banner at {landed['clear']:.1f}px"
    )
    assert landed["clear"] < landed["sentence"] < landed["change"], (
        "the sentence the change stands in is not on screen above it"
    )
    assert landed["foot"] <= landed["view"], "the change itself ran off the screen"
    assert errors == []
    page.close()


def test_an_arrival_does_not_reach_back_into_the_ask_before_it(browser, serve):
    """The heading over a change is the one it stands under, not the last one written.

    Two asks in a row is the ordinary way to write two, and the second here has no
    heading of its own under its container. The nearest heading written before it is
    then the first ask's own, and arriving there would put a different question in
    front of the reader as this change's context. A candidate has to share a container
    with the change for that reason, which also stops the search at the part of the
    document the change is in.

    The change is reached from the foot of the page rather than by stepping forward off
    the ask above it. Arriving at that ask leaves this one on screen already, where the
    press deliberately moves nothing and there is no travel to read.
    """
    page, errors = open_page(browser, serve(ASKS_IN_A_ROW_PAGE))
    resized(page, 900, 500)

    page.evaluate(
        "() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight)"
    )
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)

    page.keyboard.press("Shift+a")  # back to the nearest ask above, which is the change
    expect(page.locator("#ar-sug")).to_be_focused()
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)

    landed = page.evaluate(
        """() => {
          const at = (id) => document.getElementById(id).getBoundingClientRect();
          return {
            other: at('ar-other-heading').top,
            otherFoot: at('ar-other-decision').bottom,
            change: at('ar-sug').top,
            foot: at('ar-sug').bottom,
            view: document.scrollingElement.clientHeight,
            clear: parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop),
          };
        }"""
    )
    assert landed["otherFoot"] <= landed["change"], (
        "the fixture no longer has the previous ask standing above this one"
    )
    # The previous ask's heading is close enough to reach: without the container bound
    # it fits the screen from its own top to this change's foot, so it would be chosen
    # and the reader would start on the question they are not being asked.
    assert landed["foot"] - landed["other"] <= landed["view"] - landed["clear"], (
        "the fixture has moved the two asks too far apart for the wrong heading to be "
        "reachable, so this test can no longer tell the container bound is working"
    )
    assert abs(landed["other"] - landed["clear"]) > 2, (
        "the arrival put the previous ask's heading below the banner, so the reader "
        "starts on the question they are not being asked"
    )
    assert landed["foot"] <= landed["view"], "the change itself ran off the screen"
    assert errors == []
    page.close()


def test_an_ask_inside_a_card_is_brought_into_that_card(browser, serve):
    """The arrival places a region out on the page; the ask may be in a box of its own.

    The placement moves whichever scroller the region belongs to, and for a region on
    the page that is never the card's. So the ask's own box comes into view first, which
    is the one pass that moves a nested scroller. Handing the placement the region alone
    left the ask unscrolled in its card, with the ring and focus on a change the reader
    could not see — and the walk's next press repeated the same non-arrival.
    """
    page, errors = open_page(browser, serve(ASK_IN_A_CARD_PAGE))
    resized(page, 900, 500)

    # The card hides the ask to begin with, or the reveal has nothing to do — and the
    # region really is outside the card, or the region's own reveal would scroll the card
    # whatever the arrival did, and a green result would say nothing about it.
    assert page.evaluate(
        """() => {
          const card = document.getElementById('ac-card');
          const box = document.getElementById('ac-sug').getBoundingClientRect();
          const head = document.getElementById('ac-heading').getBoundingClientRect();
          const se = document.scrollingElement;
          const clear = parseFloat(getComputedStyle(se).scrollPaddingTop) || 0;
          const inside = card.querySelector(
            'p,li,h1,h2,h3,h4,h5,h6,td,th,pre,blockquote,dd,dt,figcaption,summary');
          return card.scrollHeight > card.clientHeight &&
                 box.top > card.getBoundingClientRect().bottom &&
                 box.bottom - head.top <= se.clientHeight - clear &&
                 !(inside && !inside.closest('lf-suggestion'));
        }"""
    ), (
        "the fixture's card shows the change already, holds a block before it, or has "
        "grown past the heading's reach — the region would then be the change itself"
    )

    page.keyboard.press("a")
    expect(page.locator("#ac-sug")).to_be_focused()
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)

    seen = page.evaluate(
        """() => {
          const box = document.getElementById('ac-sug').getBoundingClientRect();
          const card = document.getElementById('ac-card').getBoundingClientRect();
          const view = document.scrollingElement.clientHeight;
          return {
            insideCard: box.top >= card.top - 0.5 && box.bottom <= card.bottom + 0.5,
            onScreen: box.top >= 0 && box.bottom <= view,
          };
        }"""
    )
    assert seen["insideCard"], (
        "the change is still outside its card's own band, so the card was never scrolled"
    )
    # Where the card's own top ends up is not promised: the region can be a block inside
    # the card, and placing that at the banner takes the card's top edge above it. What
    # is promised is the change, in the window and in its card's band at once.
    assert seen["onScreen"], "the change is in its card's band but off the window"
    assert errors == []
    page.close()


def test_an_ask_already_in_front_of_the_reader_is_not_travelled_to(browser, serve):
    """The press moves the ring and the focus and leaves the page where it stands.

    Rebuilding a view the reader is already looking at is motion that says nothing, and
    it costs them whatever adjustment they had made within it. The gate reads what the
    page shows of the ask rather than what its own box claims, which is the reading
    commentOnItem makes before its own travel.

    The first press is the control: the walk does travel, from a page that opens above
    the change, so a second press standing still is this gate rather than a walk that
    never moves the page at all.
    """
    page, errors = open_page(browser, serve(SUGGESTION_IN_CONTEXT_PAGE))
    resized(page, 900, 500)

    page.keyboard.press("a")
    expect(page.locator("#sc-sug")).to_be_focused()
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)
    arrived = page.evaluate("() => document.scrollingElement.scrollTop")
    assert arrived > 0, "the walk did not travel to the ask at all"

    # A little above that arrival: the region's start is still clear of the banner and
    # the change's foot is still on screen, so this is the same view with the reader's
    # own adjustment in it.
    page.evaluate("() => document.scrollingElement.scrollBy(0, -40)")
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)
    held = page.evaluate("() => document.scrollingElement.scrollTop")
    assert held == arrived - 40, "the page did not take the reader's own adjustment"

    # The press's own announcement is the edge this absence stands behind. `goToAsk`
    # travels before it announces, so a live region that has spoken again is a press whose
    # travel has already been decided and begun. Waiting on the scroll alone cannot say
    # that: two equal samples taken before a glide starts are the reading a page that
    # never moved gives, and the settle probe carries its last reading between waits, so
    # it answered from the nudge that came before this press. The sentinel makes it take a
    # fresh sample and then hold, which is the window a travel would appear in.
    page.evaluate("() => { document.querySelector('.lf-live').textContent = ''; }")
    page.keyboard.press("a")  # one ask, so the clamped walk stays on it
    expect(page.locator(".lf-live")).to_have_text(re.compile(r"waiting on you"))
    expect(page.locator("#sc-sug")).to_be_focused()
    page.evaluate("() => { window.__lfScroll = -1; }")
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == held, (
        "the walk travelled to an ask the reader could already see"
    )
    assert errors == []
    page.close()


def test_the_ask_walk_starts_from_where_the_reader_is(browser, serve):
    """The walk measures from the reader, the way Space page travel measures from the scroll position
    and t/T from the focused thread. It kept an id of its own instead, so every walk
    the reader had not made with this key started at the top of the page: scroll
    halfway down and press `d` and you were taken back past everything you had read,
    and so was anyone who had just selected a paragraph to comment on.

    Two readings of where they are are left in turn: what they are reading, and where
    the walk itself last left off. The banner's button is no place — pressing it opens
    the tray and leaves the focus on itself, so a walk measured from the focus after it
    would restart on every press, and the ring is gone from the page by then, the reader
    being in the banner. A selected passage now enters its comment field immediately;
    while that field stands, letters are text rather than page-navigation keys."""
    page, errors = open_page(browser, serve(ASKS_PAGE))

    # A window short enough that reading down the page leaves the top of it behind,
    # which is the whole of what the reader has to do to be somewhere.
    resized(page, 900, 400)

    # Scrolled to the change with nothing selected and nothing focused: the decision after
    # it, not the question above it. They are standing *in* that suggestion, which is
    # why it is the decision they step off rather than the one they step to.
    page.locator("#refill-now").evaluate("el => el.scrollIntoView({block: 'center'})")
    page.keyboard.press("a")
    expect(page.locator("#t-baffles-decision")).to_have_attribute("data-lf-ask", "1")

    # The banner's press opens the tray and keeps the focus, so the walk after it
    # measures from where the reader stands in the page and steps on rather than
    # restarting — the button being no place to measure from.
    page.locator(".lf-asks").click()
    page.keyboard.press("a")
    expect(page.locator("#t-bath-decision")).to_have_attribute("data-lf-ask", "1")

    assert errors == []
    page.close()


def test_the_asks_tray_names_an_ask_a_message_carries(browser, serve):
    """A decision carried by a reply is a decision, and the tray has to name it in its words.

    The page holds none of its own, so the one row here is the question Claude put in
    the conversation — the AskUserQuestion shape, which reaches a reader through the
    panel and through this tray and nowhere else. It is read here exactly as a group
    on the page is read: the decision's own words, its label first, run together and cut at
    the row's cap. `startswith` for that reason — the cut is the tray's business and
    this is about which words reach it, which is the whole of what the row asserts for
    a page-borne ask two tests below.

    It read `rp-decision` before, and then read the label alone: a veto on chrome threw the
    reading away, and lifting it left the panel over the widget standing in for the
    widget's own chrome, so only a declared label got out. The reading is rooted at the
    ask now, so the layer above it is nobody's apparatus and the words underneath are
    the widget's own."""
    url = serve(REPLY_HOST_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-which",
            "author": "user",
            "revision": 1,
            "text": "Either would do. Which are you leaning towards?",
        },
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-which",
            "revision": 1,
            "text": "The second, but the cost lands on you either way:",
            "markup": (
                '<lf-ask id="rp-decision-region"><h3>Which should I write up first?</h3>'
                '<lf-options id="rp-decision" choose>'
                '<lf-option id="rp-now">The migration</lf-option>'
                '<lf-option id="rp-later">The rollback</lf-option>'
                "</lf-options></lf-ask>"
            ),
        },
    )
    page, errors = open_page(browser, url)
    resized(page, 1200, 900)

    page.locator(".lf-asks").click()
    expect(page.locator(".lf-asks-panel")).to_be_visible()
    rows = page.evaluate(ASK_ROW_SAYS)
    assert len(rows) == 1, rows
    assert rows[0]["at"] == "rp-decision-region", rows
    assert rows[0]["says"].startswith("Which should I write up first?"), rows
    assert errors == []
    page.close()


def test_a_widget_a_message_carries_holds_the_room_its_words_will_need(browser, serve):
    """A measurement is a measurement wherever the widget was built, or it is a zero.

    Two shipped widgets take a number off a live box at upgrade — the room a card keeps
    clear of its grip and the width of a roster's state column — because a constant goes
    stale in the next face. A widget
    upgrades wherever the runtime connects it, and one of those places is a message body
    inside a thread panel nobody has opened: `display: none`, so every box under it is
    zero. `once` then refuses the second upgrade that would put it right and the body is
    cached for the life of the tab, so the zero is permanent.

    The reply is in the log before the page loads and the panel is shut, which is the
    only arrangement that reproduces it: a reply arriving into an open panel upgrades
    into boxes and was always right. Rooms are compared rather than named, because the
    number is the face's and this is about whether it was ever read.

    Both of them, because `measure` is the primitive and each module's wiring to it is
    its own line."""
    url = serve(MESSAGE_ROOM_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-room",
            "author": "user",
            "revision": 1,
            "text": "Anything else worth adding?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-room",
            "revision": 1,
            "text": "These, and who is on them:",
            "markup": ROOM_WIDGETS.format(id="mr-msg"),
        },
    )
    page, errors = open_page(browser, url)
    resized(page, 1200, 900)

    held = {}
    for suffix, prop in ROOMS:
        held[suffix] = page.evaluate(ROOM_HELD, [f"mr-page{suffix}", prop])
        # Against a page that stopped reserving anything, where this would pass on both
        # sides reading the same nothing.
        assert held[suffix] not in ("0px", "", None), (suffix, prop, held)

    page.locator(".lf-threads-toggle").click()
    expect(page.locator("#mr-msg-b")).to_be_visible()
    # The re-measure is delivered with the layout that gave these their boxes, so the
    # reading waits for a frame that has been through one.
    page.evaluate(RENDERED)
    for suffix, prop in ROOMS:
        assert page.evaluate(ROOM_HELD, [f"mr-msg{suffix}", prop]) == held[suffix], (
            suffix,
            prop,
        )
    assert errors == []
    page.close()


def test_a_drag_across_a_question_in_a_reply_is_not_a_passage_of_the_page(
    browser, serve
):
    """A selection made in the panel is not the page's words, whatever it looks like.

    `leaf comment --section` refuses to anchor on a widget an agent sent, and it is the
    reading that is supposed to promise less than the browser's. The browser offered
    the 💬 over a question in a reply and wrote an anchor onto that widget's own id into
    an append-only log — naming a section no version holds, so it could never paint and
    never be found again.

    A declared label is the hole it came through: it is the page speaking inside the
    control it labels, so it answers the "are these the runtime's words" question for
    itself and the panel above it never got asked. That question was standing in for a
    second one nobody was putting — which document is this — and the drag needs both.

    The same drag on the page's own prose comes first and must raise the button. It is
    the control: this asserts an absence, and an absence proves nothing on a page where
    nothing was ever going to appear. The drags are real ones, so the mouseup guard is
    under test with the button.

    Then two turns of the macrotask queue, because the handler raises the button from a
    bare `setTimeout` — asserting straight after the drag reads the frame before the
    decision and passes whatever the decision would have been."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-store",
            "author": "user",
            "revision": 1,
            "text": "Which store?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-store",
            "revision": 1,
            "text": "Depends what you want to keep:",
            "markup": (
                '<lf-ask id="ps-decision-region"><h3>Which store should I write up?</h3>'
                '<lf-options id="ps-decision" choose>'
                '<lf-option id="ps-redis">Redis</lf-option>'
                '<lf-option id="ps-cookie">A signed cookie</lf-option>'
                "</lf-options></lf-ask>"
            ),
        },
    )
    page, errors = open_page(browser, url)
    resized(page, 1200, 900)

    def drag(locator):
        expect(locator).to_be_visible()
        box = locator.bounding_box()
        y = box["y"] + box["height"] / 2
        select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
        return page.evaluate("() => getSelection().toString()")

    # The control, taken with the panel still shut: the same gesture on the page's own
    # words raises the button here. Opening the panel slides the document over, and a
    # drag run across that reads a box from the frame before and selects nothing — the
    # panel's own contents are fixed and stay where they are read.
    intro = page.locator("#intro")
    box = intro.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    expect(page.locator("#lf-composer-quote")).to_contain_text("signed-cookie")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    # Put it down again, so what follows is a rise and not a leftover.
    page.locator("#h").click()
    expect(page.locator(".lf-fab-input")).to_be_hidden()

    page.locator(".lf-threads-toggle").click()
    assert "Which store" in drag(page.locator("#ps-decision-region > h3"))
    # Both turns the handler could have used: it defers with a bare setTimeout, and the
    # step it queues queues nothing further.
    for _ in range(2):
        page.evaluate("() => new Promise((r) => setTimeout(r))")
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    assert errors == []
    page.close()


def test_a_conversation_seated_in_a_widget_is_not_a_change_to_the_document(
    browser, serve
):
    """What a reader and an agent said to each other is not something the page changed.

    A widget declaring x-conversation grows a seat on the page, and the layer fills it
    from the log — messages the runtime built, wearing `.lf-ui` and `data-lf-gen`, and
    standing inside the widget out in `<main>`. The version diff walks every block the
    page holds and keys each by `wrote`, which is exactly the reading that leaves
    generated words out, so those blocks key to nothing and are skipped.

    They stopped being skipped when `wrote` was bounded at the element handed in: a
    reading can start *inside* generated chrome, and rooted at one of those `<p>`s the
    box above it was no longer over the reading. The base version is parsed unupgraded
    and holds no conversation at all, so every message became an insertion — the
    reader's own comment and the agent's reply painted as changes to the document, and
    the count in the version note inflated by both.

    The bound is the widget the reading belongs to now, and a conversation seat is
    inside its widget, so the box is between the words and their frame either way."""
    url = serve(CONVERSATION_DIFF_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "cd-thread",
            "author": "user",
            "revision": 1,
            "text": "Does the tray fit the north bracket?",
            "anchor": {"section": "cd-q"},
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "cd-thread",
            "revision": 1,
            "text": "It does, with the wider plate.",
        },
    )
    page, errors = open_page(browser, live_url(url))
    resized(page, 1200, 900)
    # The seat is filled before the diff runs, or this asserts over a page that never
    # had the blocks in question.
    expect(page.locator("#cd-q .lf-conversation-msg")).to_have_count(2)

    (d / ".fixture-versions" / "v2.html").write_text(
        CONVERSATION_DIFF_PAGE.replace(
            '<p id="cd-lede">The south pair is up and drawing traffic.</p>',
            '<p id="cd-lede">The south pair is up and drawing traffic.</p>\n'
            '<p id="cd-new">The north pair waits on brackets.</p>',
        )
    )
    stamp_version_file(d, 2, "two")
    wait_for_revision(page, 2)
    expect(page.locator("#cd-q .lf-conversation-msg")).to_have_count(2)

    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map((e) => e.id)"
    ) == ["cd-new"], "the diff read the conversation as words the base version lacked"
    assert errors == []
    page.close()


def test_an_agent_message_edit_updates_the_panel_and_its_inline_conversation(
    browser, serve
):
    """The edit is one log arrival and both views fold it onto the original message.

    Neither view gains a second message. Their standing message nodes survive the
    arrival, so an edit cannot disturb a reader working elsewhere in the same thread;
    only the prose inside changes, and both heads disclose that it changed.
    """
    url = serve(CONVERSATION_DIFF_PAGE)
    d = serve.page_dir
    message = events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "edited-agent-message",
            "author": "claude",
            "agent": "Indexer",
            "session": "worker-1",
            "revision": 1,
            "text": "The north bracket fit.",
            "anchor": {"section": "cd-q"},
            "markup": (
                '<lf-options id="edited-message-choice" choose>'
                '<lf-option id="edited-message-now">Fit it now</lf-option>'
                "</lf-options>"
            ),
        },
    )
    page, errors = open_page(browser, url)
    resized(page, 1200, 900)
    inline = page.locator(f'#cd-q .lf-conversation-msg[data-event="{message["id"]}"]')
    expect(inline.locator(".lf-conversation-body")).to_have_text(
        "The north bracket fit."
    )
    page.locator(".lf-threads-toggle").click()
    panel = page.locator(f'.lf-msg[data-mid="{message["id"]}"]')
    expect(panel.locator(".lf-msg-text")).to_have_text("The north bracket fit.")
    page.evaluate(
        """([message]) => {
          window.__editedInline = document.querySelector(
            `#cd-q .lf-conversation-msg[data-event="${message}"]`);
          window.__editedPanel = document.querySelector(`.lf-msg[data-mid="${message}"]`);
          window.__editedWidget = document.querySelector('#edited-message-choice');
        }""",
        [message["id"]],
    )

    revision = events_model.append_event(
        d,
        {
            "kind": "edit",
            "author": "claude",
            "agent": "Indexer",
            "session": "worker-1",
            "message": message["id"],
            "text": (
                "The north bracket fits.\n\n"
                "```python\n"
                "def fitted():\n"
                "    return True\n"
                "```"
            ),
        },
    )
    told(page)

    expect(inline.locator(".lf-conversation-body")).to_contain_text(
        "The north bracket fits."
    )
    expect(panel.locator(".lf-msg-text")).to_contain_text("The north bracket fits.")
    expect(panel.locator('pre code [data-lf-syn="kw"]').first).to_have_text("def")
    expect(inline.locator(".lf-edited")).to_have_text("edited")
    expect(panel.locator(".lf-edited")).to_have_text("edited")
    expect(page.locator(f'.lf-msg[data-mid="{revision["id"]}"]')).to_have_count(0)
    assert page.evaluate(
        "() => window.__editedInline.isConnected && window.__editedPanel.isConnected"
        " && window.__editedWidget.isConnected"
    ), "the edit replaced a standing message or its frozen widget"
    assert events_model.read_events(d)[-2]["text"] == "The north bracket fit."
    assert errors == []
    page.close()


def test_a_thread_on_a_widget_an_agent_sent_names_it_and_stands_apart(browser, serve):
    """A question the agent asked is not one of the runtime's own buttons.

    Design mode lets a reader comment on anything the layer draws, so a thread can be
    anchored on a widget that arrived in a reply. Two things were then said about it and
    both were wrong. The panel filed it under "The page's own layer", which groups the
    agent's question with the composer and the version chooser — the layer's parts wear
    the runtime's id namespace, which authored markup may not take, and that is what
    tells one from the other. And the thread's label read `§ ps-decision`, the bare id.

    The label is the part with the mechanism worth naming. An element anchor is labelled
    with its item's opening words, read when the node is built — and on the reconcile
    that first builds this node, the message body carrying the widget has not been
    connected yet, so the item did not exist and the reading came back empty. A node the
    reconcile keeps is never built again, so nothing asked a second time. It is repainted
    with the quote now, which is the pass that already exists for records whose subject
    the reconcile has just written."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-sent",
            "author": "user",
            "revision": 1,
            "text": "Which store?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-sent",
            "revision": 1,
            "text": "Depends what you want to keep:",
            "markup": (
                '<lf-ask id="ps-decision-region"><h3>Which store should I write up?</h3>'
                '<lf-options id="ps-decision" choose>'
                '<lf-option id="ps-redis">Redis</lf-option>'
                '<lf-option id="ps-cookie">A signed cookie</lf-option>'
                "</lf-options></lf-ask>"
            ),
        },
    )
    # The shape design mode writes: an element anchor naming a widget no version holds.
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-on-sent",
            "author": "user",
            "revision": 1,
            "text": "Redis, and say why in the patch.",
            "anchor": {"section": "ps-decision-region"},
        },
    )
    page, errors = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-threads-toggle").click()

    thread = page.locator('.lf-thread[data-id="c-on-sent"]')
    expect(thread).to_be_visible()
    label = thread.locator(".lf-quote").inner_text()
    assert "Which store should I write up?" in label, label
    assert "ps-decision-region" not in label, label
    # The heading over it, and the layer's own name kept for the layer's own parts.
    groups = page.evaluate(
        "() => [...document.querySelectorAll('.lf-group')].map((g) => g.textContent)"
    )
    assert "Sent in the conversation" in groups, groups
    assert "The page's own layer" not in groups, groups
    assert errors == []
    page.close()


def test_a_change_says_which_of_the_three_it_is(browser, serve):
    """A row names its ask by kind and then by the decision's own opening words, and for a
    change those opening words are whichever half comes first — the current text, where
    there is one. So a deletion arrived on the tray under the words it was proposing to
    remove, with nothing to tell it from the insertion above it, which was proposing to
    add its own. Three shapes, one tag, one word for all of them.

    The tag is the right word wherever one tag is one kind of thing, which is every
    other widget here, so the fix is not to teach the tray about suggestions: the entry
    declares that this tag's word comes from its module (x-word), and the module reads
    it off the slots it holds. The group below is in this page to hold the other half of
    that — a widget declaring nothing still gets its tag, and would go on getting it if
    the declaration were dropped."""
    page, errors = open_page(browser, serve(CHANGE_SHAPES_PAGE))
    resized(page, 1200, 900)

    page.locator(".lf-asks").click()
    expect(page.locator(".lf-asks-panel")).to_be_visible()
    rows = page.evaluate(ASK_ROW_SAYS)

    assert {r["at"]: r["kind"] for r in rows} == {
        "sug-rewrite": "rewrite",
        "sug-insert": "insertion",
        "sug-delete": "deletion",
        "shapes-decision": "ask",
    }
    # The words beside the kind are still the element's own, and the two changes that
    # keep a current paragraph still open on it — the reading did not move, only what
    # is said about it.
    said = {r["at"]: r["says"] for r in rows}
    assert said["sug-delete"].startswith("Retries are logged"), said
    assert said["sug-insert"].startswith("Parked jobs"), said
    assert errors == []
    page.close()


def test_the_asks_control_opens_active_asks_and_answers(browser, serve):
    """The banner control shows every active Ask, so the reader can review and revise.

    The rows are allAsks() — open and answered — in document order, and a twelfth
    widget joins the tray by declaring x-awaits. Each says what kind of thing is asking,
    the Ask's authored heading, and its current answer when it has one.

    A closed tray holds no rows at all. That is not tidiness: they are the open
    tray's rendering, the banner's count is the closed tray's, and a hidden list of
    buttons is a set of controls no reader can press — which the press sweep sees as
    the page's control set changing under it."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    resized(page, 1200, 900)
    tray = page.locator(".lf-asks-panel")
    expect(tray).to_be_hidden()
    assert page.evaluate(ASK_ROW_SAYS) == [], "a closed tray holds no rows"

    decisions_control = page.locator(".lf-asks")
    decisions_control.focus()
    page.keyboard.press("Enter")
    expect(tray).to_be_visible()
    rows = page.evaluate(ASK_ROW_SAYS)
    assert [r["at"] for r in rows] == ALL_ASKS_IN_ORDER, (
        "the tray is allAsks() in document order"
    )
    for row in rows:
        assert row["w"] > 100 and row["h"] > 20, f"{row['at']}'s row has no usable size"
        assert row["kind"], f"{row['at']}'s row does not say what kind of thing asks"

    # The Ask leads with its authored heading rather than the first option's answer.
    said = {r["at"]: r["says"] for r in rows}
    assert said["live-question-decision"].startswith("Where should sessions live?"), (
        said["live-question-decision"]
    )
    assert said["t-baffles-decision"].startswith("Are the baffles ready?"), said[
        "t-baffles-decision"
    ]
    honored = next(row for row in rows if row["at"] == "honored-decision")
    assert (honored["state"], honored["answer"]) == ("answered", "Two-tier gates")

    # Answered, and the row remains as the route back while its current answer appears.
    page.locator("#lq-token").click()
    expect(page.locator(".lf-asks")).to_have_text("Asks 2/5")
    expect(page.locator("button.lf-asks-row")).to_have_count(5)
    answered = next(
        row
        for row in page.evaluate(ASK_ROW_SAYS)
        if row["at"] == "live-question-decision"
    )
    assert (answered["state"], answered["answer"]) == ("answered", "Signed tokens")

    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    round_trip(page)
    suggestion = next(
        row for row in page.evaluate(ASK_ROW_SAYS) if row["at"] == "sug-refill"
    )
    assert (suggestion["state"], suggestion["answer"]) == ("answered", "Accepted")

    # And closing takes the rest with it, for the reason the docstring gives: a tray
    # that is down is not a list, so it holds nothing to reach and nothing to press.
    decisions_control.focus()
    page.keyboard.press("Enter")
    expect(tray).to_be_hidden()
    assert page.evaluate(ASK_ROW_SAYS) == [], "a closed tray keeps its rows"
    assert errors == []
    page.close()


def test_completed_ask_progress_persists_and_its_row_can_revise_by_keyboard(
    browser, serve
):
    """Completion keeps the same concise route back through the existing action model."""
    page, errors = open_page(browser, serve(ASK_WITH_CONTEXT_PAGE))
    resized(page, 1200, 900)
    progress = page.locator(".lf-asks")
    expect(progress).to_have_text("Asks 0/1")

    page.locator("#storage-stop").click()
    round_trip(page)
    expect(progress).to_have_text("Asks 1/1")
    expect(progress).to_have_attribute("data-lf-complete", "")
    treatment = progress.evaluate(
        """button => {
          const probe = document.createElement('span');
          probe.style.color = 'var(--ok-ink)';
          probe.style.background = 'var(--ok-tint)';
          document.body.append(probe);
          const actual = getComputedStyle(button);
          const expected = getComputedStyle(probe);
          const result = {
            color: actual.color === expected.color,
            background: actual.backgroundColor === expected.backgroundColor,
          };
          probe.remove();
          return result;
        }"""
    )
    assert treatment == {"color": True, "background": True}

    page.reload(wait_until="load")
    page.wait_for_function(BOTH_STAMPS)
    expect(progress).to_have_text("Asks 1/1")
    expect(progress).to_have_attribute("data-lf-complete", "")

    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    row = page.locator("button.lf-asks-row")
    expect(row).to_have_count(1)
    expect(row).to_be_focused()
    expect(row.locator(".lf-asks-answer")).to_have_text("Pause offline editing")

    page.keyboard.press("Enter")
    expect(page.locator("#storage-decision")).to_be_focused()
    assert "1–2\nDrop the oldest documents / Pause offline editing" in key_line(page)
    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("#storage-evict")).to_have_attribute("chosen", "")
    expect(progress).to_have_text("Asks 1/1")
    expect(row.locator(".lf-asks-answer")).to_have_text("Drop the oldest documents")
    assert errors == []
    page.close()


def test_an_empty_option_uses_its_id_as_the_answer(browser, serve):
    source = leaf_page(
        "empty option answer",
        """<h1>Choose the unnamed route</h1>
<lf-ask id="empty-decision"><h2>Which route?</h2>
  <lf-options id="empty-options" choose>
    <lf-option id="empty" chosen></lf-option>
    <lf-option id="named"><strong>Named route</strong></lf-option>
  </lf-options>
</lf-ask>""",
    )
    page, errors = open_page(browser, serve(source))

    page.locator(".lf-asks").click()
    expect(page.locator(".lf-asks-answer")).to_have_text("empty")

    assert errors == []
    page.close()


def test_an_ask_rejects_two_answer_readers_even_when_their_words_match(browser, serve):
    page, errors = open_page(browser, serve(ASKS_PAGE))
    page.evaluate(
        """async () => {
          const {commands} = await import('/runtime/widget-api.js');
          const options = document.getElementById('honored');
          const extra = document.createElement('span');
          options.append(extra);
          commands(extra, 'Duplicate answer', [], {answer: () => 'Two-tier gates'});
        }"""
    )

    with page.expect_event("pageerror") as raised:
        page.locator(".lf-asks").click()
    assert "honored-decision has more than one answer reader" in str(raised.value)
    assert any("more than one answer reader" in error for error in errors)
    page.close()


def test_an_answered_boxless_ask_reopens_on_its_visible_revision_control(
    browser, serve
):
    """A tray-row arrival preserves Ask semantics when its source has no box to focus."""
    page, errors = open_page(browser, serve(CHANGE_SHAPES_PAGE))
    resized(page, 560, 620)
    progress = page.locator(".lf-asks")
    expect(progress).to_have_text("Asks 0/4")

    page.locator("[data-lf-for='sug-delete'] .lf-sug-accept").click()
    round_trip(page)
    expect(page.locator("#sug-delete")).to_be_hidden()
    expect(progress).to_have_text("Asks 1/4")

    banner_address(page, ".lf-asks").click()
    row = page.locator('.lf-asks-row[data-lf-at="sug-delete"]')
    expect(row.locator(".lf-asks-answer")).to_have_text("Accepted")
    row.click()
    expect(page.locator(".lf-asks-panel")).to_be_hidden()
    undo = page.locator('[data-lf-for="sug-delete"] [data-lf-button-key="undo"]')
    expect(undo).to_be_focused()
    assert "1\nUndo" in key_line(page)

    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("#sug-delete")).to_be_visible()
    expect(progress).to_have_text("Asks 0/4")
    assert errors == []
    page.close()


def test_a_tray_the_reader_left_standing_comes_back_standing(browser, serve):
    """Reloading is not resetting: a tray someone stood up to watch stays stood, the
    rule the thread panel already keeps. Which makes the reload the one moment a
    tray is put up by something other than a press, and that is where it broke — the
    restore ran while the module was still evaluating and filled the tray from a
    reading of the page's active Asks declared further down the file, so the reader who
    had left it open got a ReferenceError instead of a page.

    Nothing static could have caught it and neither could the render gate, which
    presses no keys and so never has a tray to restore. It took a reader with the
    tray open pressing reload, which is what this now is."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    page.locator(".lf-asks").click()
    tray = page.locator(".lf-asks-panel")
    expect(tray).to_be_visible()
    expect(page.locator("button.lf-asks-row")).to_have_count(len(ALL_ASKS_IN_ORDER))

    page.reload(wait_until="load")
    page.wait_for_function(BOTH_STAMPS)
    expect(tray).to_be_visible()
    expect(page.locator("button.lf-asks-row")).to_have_count(len(ALL_ASKS_IN_ORDER))
    # And the room it takes comes back with it, or the tray returns lying over the
    # column it is meant to stand beside.
    page.wait_for_function(
        """() => getComputedStyle(document.body).marginLeft !== '0px'"""
    )
    assert errors == [], errors
    page.close()


def test_a_row_stands_the_reader_on_the_ask_it_names(browser, serve):
    """Pressing a row uses the same arrival as the Ask walk. It scrolls there, rings the
    Ask, and stands the reader on its opening context; its controls are the next Tab
    stops, while the numeric action map is already available for direct revision.

    The ring lands in two places for one reason: the decision on the page and its row on the
    tray are two surfaces showing where the reader is standing, painted from the one
    reading of it (markHere), so neither can say something the other doesn't."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    # Narrow enough that the tray covers the page. A destination selected from a covering
    # sheet must dismiss the sheet; otherwise all the focus and scrolling below happen
    # correctly behind an opaque surface.
    resized(page, 560, 620)
    banner_address(page, ".lf-asks").click()
    expect(page.locator(".lf-asks-panel")).to_be_visible()

    # The last of the four, which a short window leaves well off screen.
    on_screen = """() => {
      const r = document.querySelector('#t-bath-decision').getBoundingClientRect();
      return r.top >= 0 && r.bottom <= innerHeight;
    }"""
    assert not page.evaluate(on_screen), (
        "the fixture must start with #t-bath-decision off screen"
    )

    page.locator("button.lf-asks-row[data-lf-at='t-bath-decision']").click()
    expect(page.locator(".lf-asks-panel")).to_be_hidden()
    page.wait_for_function(on_screen)
    expect(page.locator("#t-bath-decision")).to_be_focused()
    expect(page.locator("#t-bath-decision")).to_have_attribute("data-lf-ask", "1")
    page.keyboard.press("Tab")
    expect(page.locator("#t-bath-decision .lf-pick").first).to_be_focused()
    # The covering tray has gone, so its projected rows go with it. The page carries the
    # one standing mark rather than leaving a second, hidden authority in the closed tray.
    marked = page.evaluate(
        """() => [...document.querySelectorAll('[data-lf-ask]')]
             .map((e) => e.id || e.getAttribute('data-lf-at'))"""
    )
    assert sorted(set(marked)) == ["t-bath-decision"], marked
    assert errors == []
    page.close()


def test_the_asks_tray_takes_room_rather_than_covering_the_column(browser, serve):
    """A leaf's row is a way out of this page and an Ask's row is a way around it, so
    pressing one sends the reader into the document — and a tray lying over the
    document would be hiding the thing it just sent them to. At a 720px column the two
    overlap on any window under about 1320px, which is most of them, so the strip comes
    out of the page the way the thread panel's does on the other side.

    Below twice the tray's own width there is no strip to take, and it covers instead —
    the same bargain at the same ratio the panel strikes, so a reader who has learned
    one edge has learned the other."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    geometry = """() => ({
      column: Math.round(document.querySelector('main').getBoundingClientRect().left),
      tray: Math.round(
        document.querySelector('.lf-asks-panel').getBoundingClientRect().right),
      sideways: document.documentElement.scrollWidth
                - document.documentElement.clientWidth,
    })"""

    resized(page, 1200, 800)
    page.locator(".lf-asks").click()
    expect(page.locator(".lf-asks-panel")).to_be_visible()
    page.wait_for_function(
        """() => getComputedStyle(document.body).marginLeft !== '0px'"""
    )
    wide = page.evaluate(geometry)
    assert wide["column"] >= wide["tray"], (
        f"the tray covers the column: it ends at {wide['tray']} and the column "
        f"begins at {wide['column']}"
    )
    assert wide["sideways"] == 0, "the page scrolls sideways with the tray up"

    # Narrow enough and the strip is more than the page can give, so it covers.
    resized(page, 560, 800)
    page.wait_for_function(
        """() => getComputedStyle(document.body).marginLeft === '0px'"""
    )
    assert page.evaluate(geometry)["sideways"] == 0
    assert errors == []
    page.close()


def test_one_tray_stands_on_the_left_edge_at_a_time(browser, serve, other_leaf):
    """Both trays want the edge, so opening either closes the other. Which one is up
    is one fact in one place: a boolean per tray would be one guarantee written twice,
    and the two would first disagree the day a third surface opened one without closing
    the other — leaving two trays over one edge with the lower unreachable.

    Escape names whichever is up rather than saying "close the tray" over two of
    them, which is the rung the reader is actually holding.

    The `other_leaf` fixture is the whole reason the leaves tray has anything to show:
    a tray of one — the page the reader is already on — is not worth a control, so
    without a neighbour `g L` is unavailable and there is no second tray to be exclusive
    with."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    decisions, leaves = (
        page.locator(".lf-asks-panel"),
        page.locator(".lf-others-panel"),
    )

    page.locator(".lf-asks").click()
    expect(decisions).to_be_visible()
    expect(leaves).to_be_hidden()

    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(leaves).to_be_visible()
    expect(decisions).to_be_hidden()
    # The page has its room back the moment the Asks tray goes down.
    page.wait_for_function(
        """() => getComputedStyle(document.body).marginLeft === '0px'"""
    )

    page.locator(".lf-asks").click()
    expect(decisions).to_be_visible()
    expect(leaves).to_be_hidden()

    page.keyboard.press("Escape")
    expect(decisions).to_be_hidden()
    expect(leaves).to_be_hidden()
    assert errors == []
    page.close()


def test_the_ring_is_one_box_around_the_whole_change(browser, serve):
    """A suggestion is one decision, so it wears one ring, whatever its slots are made of.

    The wrapper generated no box once — the same "take the form your content takes" with
    the box left out — and an element with none measures (0,0) at the document's origin,
    which is not a degenerate answer but a wrong one. Everything that asked the wrapper
    where it was believed it, so the travel centred the top of the document and a page
    whose open decisions were all suggestions answered `d` by appearing to do nothing at all.

    Hanging the ring on the pieces instead covered that and said the wrong thing about
    the change: two outlines meeting down the middle of a sentence, or stacked across
    two block slots, read as two boxes touching rather than as the one decision the reader is
    standing in. So what is asserted here is that the reader is taken to the change, and
    that the wrapper alone wears the mark, in one box reaching round both slots."""
    page, errors = open_page(browser, serve(ASKS_PAGE))

    # Short enough that reaching the change is travel rather than a press with the
    # change already on screen.
    resized(page, 900, 400)

    # Where the change stands, which is where its contents paint — the wrapper's own
    # rect answers this question wrongly, which is the whole subject here. Whole in the
    # window rather than merely overlapping it: the bug leaves the change a little below
    # the fold, so "some part of it showing" is a bar the wrong answer can clear.
    fully_shown = """() => { const r = document.createRange();
      r.selectNodeContents(document.getElementById('sug-refill'));
      const box = r.getBoundingClientRect();
      return box.top >= 0 && box.bottom <= innerHeight; }"""

    page.keyboard.press("a")
    expect(page.locator("#live-question-decision")).to_have_attribute(
        "data-lf-ask", "1"
    )
    # Where the reader now stands, which is what the next press is measured against. The
    # bug takes them to the document's origin, so a scroll that ends *below* where they
    # started is the whole of what says they were carried to the change instead.
    #
    # Said that way rather than as "the change was off screen before the press": that was
    # true by a few dozen pixels, which made it a fact about how tall the blocks above the
    # change happened to be. Giving the question above it a label set one more line and
    # the precondition stopped holding, with nothing wrong anywhere.
    was = page.evaluate("() => document.scrollingElement.scrollTop")
    assert was > 0, "the reader must have somewhere to have come from"

    page.keyboard.press("a")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-ask", "1")

    # The condition everything below rests on, stated rather than assumed: put
    # display: contents back on the wrapper and it measures (0,0), the mark paints
    # nothing, and the count further down passes on an element no reader can see.
    box = page.evaluate(
        "() => { const r = document.getElementById('sug-refill').getBoundingClientRect();"
        " return [r.width, r.height]; }"
    )
    assert box[0] > 40 and box[1] > 10, f"the wrapper drew no box to ring: {box}"

    # The travel is a glide, so the fact to wait on is that it has finished. Both
    # assertions are then about the landing: measured from the wrapper's own rect the
    # change sits at the document's origin, so the reader is carried to the top of the
    # page — up from where they stood, with the change still below the fold.
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)
    assert page.evaluate("() => document.scrollingElement.scrollTop") > was, (
        "the walk went up rather than down, which is where the document's origin is"
    )
    assert page.evaluate(fully_shown), "the walk left the change out of the window"

    # What wears the mark: the wrapper, which carries the id every reader of the mark
    # asks after. Not the slots, and not the empty span the widget prepends to itself to
    # anchor its controls from — a 2px mark of its own beside the change is not the
    # promise.
    marks = page.evaluate("""() => [...document.querySelectorAll('main [data-lf-ask]')].map(e => {
      return { what: e.id || e.tagName, fragments: e.getClientRects().length,
               ring: getComputedStyle(e).outlineStyle !== 'none' };
    })""")
    assert [m["what"] for m in marks] == ["sug-refill"]
    assert marks[0]["ring"]
    # One fragment, so the outline closes round the change once. An inline box broken
    # around block children has three and draws no visible edge on any of them, which is
    # what a wrapper that only says `inline` gets for a change made of paragraphs.
    assert marks[0]["fragments"] == 1, marks

    # And the box reaches round both slots, which a ring on the pieces could not promise:
    # the reader is standing in the change, not in half of it.
    assert page.evaluate("""() => {
      const w = document.getElementById('sug-refill').getBoundingClientRect();
      return ['refill-was', 'refill-now'].every(id => {
        const r = document.getElementById(id).getBoundingClientRect();
        return r.top >= w.top - 1 && r.bottom <= w.bottom + 1
            && r.left >= w.left - 1 && r.right <= w.right + 1; });
    }"""), "the wrapper's box does not reach round both slots"

    assert errors == []
    page.close()


def test_the_walk_travels_to_an_ask_a_page_left_boxless(browser, serve):
    """`display: contents` is one line of CSS, and a page or a project layer can put it
    on anything. Nothing in the shipped vocabulary carries it now, so this case only
    reaches the runtime from outside — which is where the reading has to hold, because
    an element generating no box measures (0,0) at the document's origin and every
    consumer that believes it travels to the top of the page.

    The travel reads where the content paints (shownBox), and the ring hangs on the
    boxes the decision shows through (shownParts) — the same answer an element-anchored
    comment's outline gives, so the walk's mark and the thread's cannot disagree about
    where a boxless decision is. The outermost mark still names the decision, one place for the
    reader to be standing."""
    styled = ASKS_PAGE.replace(
        "</head>", "<style>#sug-refill { display: contents; }</style>\n</head>"
    )
    page, errors = open_page(browser, serve(styled))
    resized(page, 900, 400)

    # Asked of what the change paints, since the wrapper itself no longer says: this is
    # the reading the runtime has to take for the travel to land anywhere real. Whole in
    # the window because merely overlapping it is a state the glide passes through.
    fully_shown = """() => { const r = document.createRange();
      r.selectNodeContents(document.getElementById('sug-refill'));
      const box = r.getBoundingClientRect();
      return box.top >= 0 && box.bottom <= innerHeight; }"""

    page.keyboard.press("a")
    expect(page.locator("#live-question-decision")).to_have_attribute(
        "data-lf-ask", "1"
    )
    was = page.evaluate("() => document.scrollingElement.scrollTop")
    assert was > 0, "the reader must have somewhere to have come from"

    page.keyboard.press("a")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-ask", "1")
    assert page.evaluate(
        "() => { const r = document.getElementById('sug-refill').getBoundingClientRect();"
        " return [r.width, r.height]; }"
    ) == [0, 0], "the page's own style no longer takes the wrapper's box away"
    page.wait_for_function(SCROLL_SETTLED, arg=SCROLL_SETTLE_MS)
    assert page.evaluate("() => document.scrollingElement.scrollTop") > was, (
        "the walk went up rather than down, which is where the document's origin is"
    )
    assert page.evaluate(fully_shown), "the walk left the change out of the window"

    # The decision and the boxes it shows through wear the mark, the decision outermost — one
    # place to stand, painted where the reader can see it.
    marks = page.evaluate("""() => [...document.querySelectorAll('main [data-lf-ask]')]
      .map(e => e.id || e.tagName)""")
    assert marks == [
        "sug-refill",
        "LF-OLD",
        "LF-NEW",
    ], f"the mark went somewhere else than the decision and its shown boxes: {marks}"
    expect(page.locator(STANDING_ASK)).to_have_count(1)

    assert errors == []
    page.close()


def test_a_commented_ask_does_not_wear_its_ring_on_the_runtime_s_own_note(
    browser, serve
):
    """The boxes a decision shows through are the page's, never the runtime's.

    The paint pass writes one hidden line per block holding a comment, saying how many
    it holds, and for an element anchor that line lands inside the element the anchor
    names. It is clipped to a pixel, so it has a box — and a wrapper that draws none of
    its own then had two children with area, its slot and the runtime's word about the
    page. Area alone kept the wrong ones out only by luck: the family's control line
    happens to be zero-wide, and this one is not.

    The order is why nothing caught it. The note is written after the marks are placed,
    so the first paint of a page sees no note and the ring is right; it moves onto the
    pixel on the next pass — which the Ask walk always is, the reader having pressed a
    key. So the fault needs a comment on the page *and* a repaint, and shows as a 1px
    ring beside the change instead of on it.

    The shipped wrapper draws a box of its own now, so the page supplies the boxless
    one here — the line of CSS any page can write is what keeps this reachable."""
    url = serve(
        ASKS_PAGE.replace(
            "</head>", "<style>#sug-refill { display: contents; }</style>\n</head>"
        )
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Does this hold when the camera is offline?",
            "anchor": {"section": "sug-refill"},
        },
    )
    page, errors = open_page(browser, url)
    # The note is what this test is about, so its presence is stated rather than assumed:
    # without it every assertion below holds for the wrong reason.
    note = page.locator("#sug-refill .lf-mark-note")
    expect(note).to_have_count(1)

    page.keyboard.press("a")
    page.keyboard.press("a")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-ask", "1")

    # By tag rather than by class: the slots are wearing the comment's own outline too,
    # this decision being the one that carries the comment, and a class would read that back
    # instead of naming the element.
    marks = page.evaluate("""() => [...document.querySelectorAll('[data-lf-ask]')]
      .map(e => e.id || e.tagName)""")
    assert marks == [
        "sug-refill",
        "LF-OLD",
        "LF-NEW",
    ], f"the ring reached past the page's own boxes: {marks}"
    expect(page.locator("#sug-refill .lf-mark-note[data-lf-ask]")).to_have_count(0)
    assert errors == []
    page.close()


# Charts. Every reading here is of the composed drawing rather than of the body it was
# built from: the body is the one thing that cannot be wrong, and everything between it
# and the picture is the module.
DREW = {
    # kind: (series, marks each, the element each series is drawn as)
    "c-bars": (2, 3, "rect"),
    "c-rows": (1, 2, "rect"),
    "c-stack": (2, 2, "rect"),
    "c-line": (1, 1, "path"),
    "c-dots": (1, 3, "circle"),
}


def test_every_number_in_a_chart_body_reaches_the_drawing(browser, serve):
    """A chart that drew nothing still has a box, an axis and no console error, so the
    render gate passes it: the drawing is the one part of a chart that no other reading
    is looking at. Each kind is counted rather than merely found, because the module
    walks a different route to each mark — a bar's height comes from a pair of bounds, a
    stacked bar's from a running total, a line's from one path over every point — and a
    route that dropped the last row of its body would leave a chart that still reads as
    a chart."""
    page, errors = open_page(browser, serve(CHART_PAGE))
    for widget, (count, each, tag) in DREW.items():
        drew = page.evaluate(CHART_MARKS, widget)
        assert drew, f"{widget} drew nothing at all"
        assert [s["n"] for s in drew["series"]] == list(range(1, count + 1)), (
            widget,
            drew,
        )
        for series in drew["series"]:
            assert (series["shapes"], series["tag"].lower()) == (each, tag), (
                widget,
                series,
            )
    assert errors == []
    page.close()


def test_a_bar_s_length_is_the_number_it_stands_for(browser, serve):
    """Counting the marks says a chart drew; it never says the drawing is the body.

    Three separate defects lived in exactly that gap and every one of them kept the mark
    count right — two rows sharing an x value drew one bar hidden behind another at a
    width nothing else on the page was drawn to, a negative segment in a stack drew over
    the bar below it and read as the total it was meant to reduce, and a fractional
    series put its own axis labels outside the drawing. So this reads the painted
    rectangles: their heights against the numbers they stand for, and their widths
    against the cap the file states, which is the reading that would have caught all
    three.

    A ratio rather than a pixel count, because the plot's height is the widget's business
    and the proportion is the chart's claim. Both series, because they are drawn by two
    marks against one scale, and a scale each would be the commonest way for this to be
    wrong and still look plausible."""
    page, errors = open_page(browser, serve(CHART_PAGE))
    bars = page.evaluate(
        """(id) => {
            const svg = document.getElementById(id).querySelector('svg');
            return [...svg.querySelectorAll('[class^="lf-series-"]')].map((g) =>
                [...g.querySelectorAll('rect')].map((r) => {
                    const box = r.getBoundingClientRect();
                    return [Math.round(box.height * 100) / 100, Math.round(box.width)];
                }));
        }""",
        arg="c-bars",
    )
    # The body CHART_PAGE carries, so a drawing that lost a row or drew one twice cannot
    # agree with it by accident.
    numbers = [[12, 19, 14], [7, 11, 17]]
    scale = bars[0][0][0] / numbers[0][0]
    assert scale > 1, bars
    for drew, wanted in zip(bars, numbers, strict=True):
        assert [round(h / scale, 1) for h, _ in drew] == [float(n) for n in wanted], (
            drew,
            wanted,
            scale,
        )
        # 48 is the file's own cap on a bar. A band holding two rows that collapsed into
        # one measured 137 against it, which no count of marks can see.
        assert all(w <= 49 for _, w in drew), drew
    assert errors == []
    page.close()


def test_no_two_of_a_chart_s_words_land_in_the_same_place(browser, serve):
    """An axis draws every label it has and stops there, so a column narrower than the
    labels need gives the reader one long word: five winters at a phone's width read
    2021-222022-232023-242024-252025-26, on a page that had already shipped. The bars are
    all still drawn, so a count of marks says the chart is fine and so does every other
    reading the gate has.

    Every pair of words rather than the neighbours, because the pairs that go wrong are
    not always adjacent: the value label of a row chart is anchored to the far end of its
    own axis and lands on the last tick, which it did at every width including the one the
    corpus is read at.

    A phone first, then the column: a rule that fits a narrow window by dropping labels
    could drop them everywhere, and the wide reading is what says it did not."""
    for width in (320, 1200):
        page, errors = open_page(browser, serve(CROWDED_CHART_PAGE))
        resized(page, width, 900)
        page.wait_for_function(
            """() => [...document.querySelectorAll('lf-chart')].every((el) => {
                const svg = el.querySelector('svg');
                return svg && Number(svg.getAttribute('width')) === Math.round(el.clientWidth);
            })"""
        )
        assert page.evaluate(CHART_COLLISIONS) == [], width
        # And the labels that survive still name the bands, rather than the axis giving up
        # and drawing none of them.
        assert (
            page.evaluate(
                """() => document.querySelectorAll(
                 '#crowd-band [data-lf-part="x-axis tick label"] text').length"""
            )
            > 0
        )
        assert errors == []
        page.close()


def test_the_gate_passes_a_chart_whose_tick_names_its_month_on_a_second_line(
    browser, serve
):
    """A dated axis names the month where one begins, on a line under the day: the tick
    for the first week of June reads 1 over Jun. Those two lines are two tspans of one
    <text>, offset by the dy the drawing asked for, and each reports a line box carrying
    the font's own leading — a couple of pixels taller than the step between them. So the
    pass hunting words drawn on other words read every such tick as a collision, on a
    drawing where no glyph comes near another, and the corpus's own heat-loss page failed
    the gate for drawing a perfectly ordinary axis.

    The reading is taken twice, as the float and the collapse are: once as the gate runs
    it, where the label's lines are held out, and once with that hold defeated, where it
    has to report. Otherwise a pass here would also be what a gate that never looked at
    the drawing returns. The two lines are pulled onto each other before either reading,
    so the second leg rests on an overlap this test arranged rather than on the leading
    the axis happens to be drawn with."""
    url = serve(CHART_PAGE)
    page, errors = open_page(browser, url)
    # Vacuous otherwise: the page has to be carrying a tick that takes two lines.
    stacked = page.evaluate(
        """() => [...document.querySelectorAll('#c-line text')]
             .filter((t) => t.querySelectorAll('tspan').length > 1)
             .map((t) => t.textContent)"""
    )
    assert stacked, "no tick names its month on a second line, so nothing is held out"
    # The overlap the second reading needs belongs to the test rather than to whatever
    # leading lf-chart settles on: the month is pulled onto the day above it, so the two
    # boxes have to land on each other whatever step the drawing asked for. `held` does
    # not move, because the hold asks which label a line belongs to and not how far apart
    # a label's lines are.
    page.evaluate(
        """() => [...document.querySelectorAll('#c-line text')]
             .flatMap((t) => [...t.querySelectorAll('tspan')].slice(1))
             .forEach((line) => line.setAttribute('dy', '0'))"""
    )
    # The same named reading with its same-label hold disabled.
    held, reported = (
        render_checks_model.evaluate_probe(page, "coveredWords"),
        render_checks_model.evaluate_probe(
            page, "coveredWords", {"holdLabelLines": False}
        ),
    )
    assert errors == []
    assert held == []
    assert any("c-line" in found for found in reported), (
        "the lines land on nothing, so a gate that never looked would pass this too"
    )
    page.close()
    assert render_gate_model.render_version(browser, url) == []


def test_the_covered_words_gate_still_reads_two_of_a_chart_s_labels_on_each_other(
    browser, serve
):
    """The other half of the exemption above, put back as a bug: a label's own lines are
    one run of words the drawing lays out together, and two labels landing on each other
    is the fault this pass exists to report. Arranged by standing one whole <text> on
    another rather than by spreading a label's lines, because the hold asks which <text>
    drew a line and not how far a line was moved.

    `<text>` is the case it is written for, being the near-miss that reads as one label
    and is not: every tick of an axis is a <text> inside one <g> inside one <svg>, so a
    hold reaching for either of those carries the whole drawing with it — every word of a
    chart stops being read against every other word of that chart — and nothing else in
    the suite would say so. The corpus sweeps and the copy assert this pass returns
    nothing, which a wider hold only makes more true; the chart's own collision test reads
    CHART_COLLISIONS, which compares whole <text> boxes and never sees this pass; and the
    exemption above defeats the predicate wholesale, so it reports the same either way.
    The only standing bug-back on this pass reporting is the float's, and that is an HTML
    page whose runs never get an SVG label at all."""
    page, errors = open_page(browser, serve(CHART_PAGE))
    # Two ticks the drawing places by transform, one stood on the other. The labels stay
    # whole, so what lands is two <text> elements rather than two lines of one.
    moved = page.evaluate(
        """() => {
            const ticks = [...document.querySelectorAll('#c-line text')]
                .filter((t) => t.hasAttribute('transform') && !t.querySelector('tspan'));
            if (ticks.length < 2) return null;
            ticks[1].setAttribute('transform', ticks[0].getAttribute('transform'));
            return [ticks[0].textContent, ticks[1].textContent];
        }"""
    )
    assert moved, "no two ticks the drawing places by transform, so nothing was stacked"
    covered = render_checks_model.evaluate_probe(page, "coveredWords")
    assert errors == []
    assert [f for f in covered if all(f'"{word}"' in f for word in moved)], (
        f"two of a chart's labels stood on each other unreported: {covered}"
    )
    page.close()


def test_a_chart_says_its_numbers_to_a_reader_who_cannot_see_it(browser, serve):
    """A drawing is where the body went. The module replaces the widget's own <pre> with
    it, so after the upgrade the numbers exist on the page as geometry and nowhere else —
    a reader on a screen reader is handed a picture and told it is a picture. The label
    is the words back, and it carries the numbers rather than a summary of them, because
    a summary answers a question nobody asked instead of the one the chart is about."""
    page, errors = open_page(browser, serve(CHART_PAGE))
    said = page.locator("#c-bars svg").get_attribute("aria-label")
    assert "merged by quarter" in said, said
    for series, numbers in (("apps", ("12", "19", "14")), ("infra", ("7", "11", "17"))):
        assert f"{series}: " in said, said
        for quarter, number in zip(("Q1", "Q2", "Q3"), numbers):
            assert f"{quarter} {number}" in said, (quarter, number, said)
    # And the drawing is one picture rather than a tree of unreachable tick labels.
    assert page.locator("#c-bars svg").get_attribute("role") == "img"
    assert errors == []
    page.close()


def test_a_chart_wears_the_page_s_colors_and_turns_over_with_the_scheme(browser, serve):
    """The colour of a series is the stylesheet's answer to a class, and nothing else.

    The alternative is what a diagram has to do: resolve the tokens in JavaScript and
    write the values into the drawing. That freezes the browser it was drawn in — a copy
    exported from a light window opens as a light slab for a dark reader, and a scheme
    flipped mid-read leaves the drawing behind. So this asserts both halves: that each
    series is painted the token it names, and that no hex colour was written into the
    drawing at all. The flip is made with no reload, so the nodes under it are the same
    nodes; a module that had painted them would fail here and pass every static check."""
    page, errors = open_page(browser, serve(CHART_PAGE))

    def worn():
        drew = page.evaluate(CHART_MARKS, "c-bars")
        assert drew["painted"] == [], drew["painted"]
        return [(s["token"], s["worn"]) for s in drew["series"]]

    light = worn()
    for token, paint in light:
        assert token in paint, (token, paint)
    assert light[0][0] != light[1][0], "two series wearing one colour proves nothing"

    page.emulate_media(color_scheme="dark")
    dark = worn()
    for token, paint in dark:
        assert token in paint, (token, paint)
    assert [t for t, _ in dark] != [t for t, _ in light], (
        "the dark palette must differ, or the flip proves nothing"
    )
    assert errors == []
    page.close()


def test_a_chart_is_drawn_for_the_room_it_has_rather_than_scaled_into_it(
    browser, serve
):
    """A drawing that scales takes its labels with it. That is what a diagram does, and
    at 63% of its natural size a five-node flowchart's labels went under legibility; a
    chart has no natural size to keep, so it is drawn again for the width it now has and
    its text stays the size the theme set. The room changes for reasons a reader never
    asked about — a window narrower than the column, the thread panel taking its strip
    out of one — so this is the ordinary case rather than a window somebody dragged."""
    page, errors = open_page(browser, serve(CHART_PAGE))
    before = page.evaluate(CHART_MARKS, "c-bars")
    assert before["width"] == before["room"], before

    # Narrower than the column, which is where the room actually changes: the column is
    # capped, so a wider window leaves a chart exactly where it was.
    resized(page, 620, 900)
    page.wait_for_function(
        """(id) => {
            const el = document.getElementById(id), svg = el.querySelector('svg');
            return svg && Number(svg.getAttribute('width')) === Math.round(el.clientWidth);
        }""",
        arg="c-bars",
    )
    after = page.evaluate(CHART_MARKS, "c-bars")
    assert after["room"] < before["room"], (before, after)
    # The painted box of a tick label, not its computed font-size: a drawing scaled by its
    # viewBox keeps the same computed size and renders smaller, so the property this test
    # is about is invisible to the one reading and plain in the other.
    assert after["tick"] == before["tick"], (before, after)
    assert errors == []
    page.close()


def test_a_body_the_module_cannot_draw_says_which_row_stopped_it(browser, serve):
    """The body is the author's, and the author is the only party who can fix it, so a
    refusal names the row rather than the exception. Two refusals, because they are
    different claims: a cell that is not a number is a typo, and a sixth series is a
    palette that has no step for it — the colours are stepped to stay apart under
    colour-blind vision, and a seventh drawn in the second's colour is a chart that lies
    to some readers and to no others."""
    page, errors = open_page(browser, serve(BAD_CHART_PAGE))
    cell = page.locator("#bad-cell .lf-error").inner_text()
    assert "row 3" in cell and "twelve" in cell, cell
    count = page.locator("#bad-count .lf-error").inner_text()
    assert "6 series" in count and "at most 5" in count, count
    # The three a mark count cannot see. A repeated x draws one row on top of another in
    # the band they share, a negative segment draws over the bar it was meant to shorten
    # and the column reads as the total without it, and a blank column takes a colour and
    # a line in the key for a series that is never drawn.
    assert "share the x value Q1" in page.locator("#bad-twice .lf-error").inner_text()
    assert "cannot be negative" in page.locator("#bad-sign .lf-error").inner_text()
    assert "infra has no numbers" in page.locator("#bad-blank .lf-error").inner_text()
    # The source stays under the message: a refusal the reader cannot check is half a
    # refusal.
    expect(page.locator("#bad-cell .lf-error pre")).to_contain_text("Q2, twelve")
    # A refusal is a box, never a console line: a body the module will not draw is the
    # author's to fix and nobody else's to hear about, and an error on the console is a
    # render-gate finding on every page that carries one.
    assert errors == []
    page.close()


def test_a_dated_column_is_read_as_the_day_the_page_wrote(browser, serve):
    """`new Date("2026-06-01")` is UTC midnight, and a scale that renders it in the
    reader's own zone puts it under May 31 for everybody west of Greenwich — a chart of
    daily totals silently one day out, in some readers' browsers and not the author's.
    The context is pinned to a zone where that is true, and the page is asked to confirm
    it: without that confirmation this test passes on a machine whose clock happens to
    be UTC, which is most of them in a container."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        color_scheme="light",
        timezone_id="America/Anchorage",
    )
    page, errors = open_page(browser, serve(CHART_PAGE), context=context)
    assert page.evaluate('() => new Date("2026-06-01").getDate()') == 31, (
        "the context must sit west of Greenwich, or the reading proves nothing"
    )
    ticks = page.evaluate(
        """() => [...document.querySelectorAll(
             '#c-line [data-lf-part="x-axis tick label"] text')].map(t => t.textContent)"""
    )
    assert ticks, "the line chart must draw a dated axis"
    assert not any("May" in tick or "31" in tick for tick in ticks), ticks
    assert any("Jun" in tick for tick in ticks), ticks
    assert errors == []
    page.close()
    context.close()


def test_a_redraw_keeps_the_words_the_runtime_hung_on_the_chart(browser, serve):
    """A chart redraws for a new width, and the runtime writes inside widgets.

    The line saying a comment stands on this chart is a child of the element, put there by
    the anchor pass. Replacing the element's children to hold the new drawing took it away
    — and took it away at the moment the reader narrowed the window or opened the panel to
    read that very comment, for the life of the tab, since nothing puts it back. So the
    drawing lives in a box of its own and the redraw replaces what is in that box.

    The room is changed by the window rather than by the panel, because the panel's strip
    is a layout the test would then be asserting about; what this is about is that a
    redraw happened at all, which the drawing's own width says."""
    page, errors = open_page(
        browser, serve(CHART_PAGE, anchored=[("c-bars", "")]), context=None
    )
    read = """() => {
        const el = document.getElementById('c-bars');
        return { room: Math.round(el.clientWidth),
                 notes: el.querySelectorAll('.lf-ui').length,
                 drawn: Number(el.querySelector('svg').getAttribute('width')) };
    }"""
    before = page.evaluate(read)
    assert before["notes"] > 0, "the fixture must hang a comment line on the chart"

    resized(page, 620, 900)
    page.wait_for_function(
        """(was) => {
            const el = document.getElementById('c-bars'), svg = el.querySelector('svg');
            return svg && Number(svg.getAttribute('width')) !== was;
        }""",
        arg=before["drawn"],
    )
    after = page.evaluate(read)
    assert after["drawn"] < before["drawn"], (before, after)
    assert after["notes"] == before["notes"], (before, after)
    assert errors == []
    page.close()


def test_a_chart_a_message_carries_waits_for_a_box_rather_than_drawing_into_none(
    browser, serve
):
    """A chart is drawn to the room it has, and a widget upgrades wherever the runtime
    connects it — including a message body inside a thread panel nobody has opened,
    which is `display: none` and has no room at all. Drawn there it would be a drawing
    720 pixels of nothing wide, and `once` refuses the second upgrade that would put it
    right, so the reader would open the panel onto an empty box for the life of the tab.

    The reply is in the log before the page loads and the panel is shut, which is the
    only arrangement that reproduces it: a reply arriving into an open panel has boxes
    already."""
    url = serve(CHART_IN_A_MESSAGE_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-chart",
            "author": "user",
            "revision": 1,
            "text": "How did the quarter go?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-chart",
            "revision": 1,
            "text": "Like this:",
            "markup": CHART_MARKUP.format(id="msg-chart"),
        },
    )
    page, errors = open_page(browser, url)
    assert (
        page.evaluate("() => document.getElementById('msg-chart').clientWidth") == 0
    ), "the panel must be shut, or there was a box all along"

    page.locator(".lf-threads-toggle").click()
    expect(page.locator("#msg-chart svg")).to_be_visible()
    page.wait_for_function(
        """() => {
            const el = document.getElementById('msg-chart'), svg = el.querySelector('svg');
            return svg && Number(svg.getAttribute('width')) === Math.round(el.clientWidth);
        }"""
    )
    drawn = page.evaluate(CHART_MARKS, "msg-chart")
    assert drawn["room"] > 100, drawn
    assert [s["shapes"] for s in drawn["series"]] == [2], drawn
    assert errors == []
    page.close()


def _bound_diff(browser, serve):
    """The review the three diff tests below read, with its feed in place before the page
    loads. Bound rather than written inline because that is the form a review arrives in,
    and the only one whose rows are commentable data — `projectData` keys each by file,
    side and source line, which is the coordinate a remark on a line is recorded at."""
    url = serve(LONG_LINE_DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", MULTI_HUNK_PATCH)
    page, errors = open_page(browser, url)
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    return page, errors


def test_a_wrapped_diff_shows_every_line_whole_and_paper_wraps_whatever_the_switch_says(
    browser, serve
):
    """A diff line is `white-space: pre` inside a box that scrolls sideways, so the only
    way to read the end of a long one is a scrollbar at the foot of the whole file. On the
    shipped review that bar sits about 24,000px below the line being read, which is not an
    answer at all; on paper there is no bar and the text is simply gone — 40 of that
    patch's 2,348 rows came out cut, the worst by 744px.

    Three claims, and the middle one is why the other two are in the same test. The switch
    wraps and unwraps: pressed off again the rows are cut again, so it is the switch doing
    it rather than the page having settled differently. And paper wraps with the switch
    off, because the sheet cannot be left holding an answer nobody can press.

    The unwrapped reading is the population as well as the anchor: a clean wrapped result
    means nothing unless the same reading, on the same rows, can see a cut line."""
    page, errors = _bound_diff(browser, serve)
    switch = page.locator("lf-diff .lf-diff-wrap")

    cut = page.evaluate(DIFF_CLIPPING)
    assert cut["rows"] > 20, f"nothing to read: {cut}"
    assert cut["cut"] > 0 and cut["worst"] > 300, (
        f"no line runs past its box, so a wrapped result would prove nothing: {cut}"
    )

    switch.click()
    wrapped = page.evaluate(DIFF_CLIPPING)
    assert wrapped["rows"] == cut["rows"], (wrapped, cut)
    assert wrapped["cut"] == 0, f"wrapped and still cut off: {wrapped}"

    switch.click()
    assert page.evaluate(DIFF_CLIPPING)["cut"] == cut["cut"], (
        "unwrapping left the lines inside their box, so the switch was not what wrapped "
        "them"
    )

    # Paper also takes the "Mark reviewed" press off each file, and the row it stood ahead
    # of is pulled back up over where it was: with the press gone the pull has nothing to
    # take back, and it drew every file's header 24px inside the file before it. The row
    # starts at its wrapper's top in both media, which is where it would with no press.
    placed = page.evaluate(DIFF_ROW_PLACEMENT)
    assert placed["files"] == 2 and (placed["lift"], placed["drop"]) == (0, 0), (
        f"a file's row does not start where its wrapper does: {placed}"
    )
    page.emulate_media(media="print")
    printed = page.evaluate(DIFF_CLIPPING)
    on_paper = page.evaluate(DIFF_ROW_PLACEMENT)
    page.emulate_media(media="screen")
    assert printed["rows"] == cut["rows"], (printed, cut)
    assert printed["cut"] == 0, (
        f"the switch is off and paper cannot press it, so this text is gone: {printed}"
    )
    assert (on_paper["lift"], on_paper["drop"]) == (0, 0), (
        f"on paper a file's row is drawn above its own wrapper: {on_paper}"
    )
    assert errors == []
    page.close()


def test_a_diff_keeps_the_file_named_while_its_hunks_go_past_and_lands_below_that_name(
    browser, serve
):
    """Two halves of one question — which file am I reading, and where did that press put
    me. The shipped review is 46 files and 32,000px: opening one and reading down it left
    nothing on screen saying whose lines these were, because the file's header stood in
    flow and scrolled away with its own first rows.

    Pinned, the header stands exactly where the banner ends, which is the slot the thread
    panel's run headings take over their own list. A press then has to land past it:
    `scrollIntoView` reads the document's scroll-padding, which reserves the banner, and
    the header's own height is added to that as the rows' scroll-margin — measured,
    because a long path wraps and no stylesheet can work that number out.

    Reduced motion so the landing read is the product's and not the frame a smooth scroll
    happened to be on. The walk starts from the tools row, which belongs to no file, so
    the first `]` is the first hunk and the second is the step this test is about."""
    page, errors = _bound_diff(browser, serve)
    page.emulate_media(reduced_motion="reduce")

    in_flow = page.evaluate(DIFF_LANDING)
    assert in_flow["headTop"] > in_flow["bannerBottom"], (
        f"the header already meets the banner before anything scrolled: {in_flow}"
    )
    page.evaluate(
        """() => {
            const file = document.querySelector('lf-diff').shadowRoot
                .querySelector('details');
            file.scrollIntoView({ block: 'start' });
            window.scrollBy(0, 200);
        }"""
    )
    pinned = page.evaluate(DIFF_LANDING)
    assert pinned["headTop"] == pinned["bannerBottom"], (
        f"the file's name is not against the banner: {pinned}"
    )
    assert pinned["bannerBottom"] == in_flow["bannerBottom"], (
        "the banner moved, so the header meeting it says nothing"
    )
    # The press drawn onto that line came with it. It stands outside the disclosure, so
    # nothing about the summary pinning moves it; placed against the file's top it stayed
    # there and scrolled off under the banner, leaving the pinned header's column empty
    # and "Mark reviewed" out of reach for the whole of the file it names. Reached by a
    # pointer as well as measured, because a box can stand on the line and still be
    # painted under the header.
    press = page.evaluate(DIFF_PRESS)
    assert abs(press["top"] - (press["headTop"] + 5)) <= 2, (
        f"the review press is not on the pinned header's line: {press}"
    )
    assert press["hit"] == "review", (
        f"a pointer on the press reaches something else: {press}"
    )
    # And it leaves with the file. A sticky box is held inside its containing block by
    # its margin box, so a negative margin on the press lent it that much travel past
    # the file's end: with the header unpinned and gone, the press stood on for 32px of
    # scroll over the next file's header and that file's own press. Scrolled to where
    # the file's foot is 15px under the banner's edge, the press's foot is no lower than
    # the file's.
    page.evaluate(
        """() => {
            const file = document.querySelector('lf-diff').shadowRoot
                .querySelector('.lf-diff-file').getBoundingClientRect();
            const banner = document.querySelector('.lf-banner').getBoundingClientRect();
            window.scrollBy(0, file.bottom - banner.bottom + 15);
        }"""
    )
    leaving = page.evaluate(DIFF_PRESS)
    assert leaving["fileBottom"] < pinned["bannerBottom"], (
        f"the file has not left the banner's edge, so nothing is being measured: {leaving}"
    )
    assert leaving["bottom"] <= leaving["fileBottom"], (
        f"the review press outlives its file: {leaving}"
    )
    page.evaluate("() => window.scrollTo(0, 0)")

    page.locator("lf-diff .lf-diff-wrap").focus()
    page.keyboard.press("]")
    first = page.evaluate(DIFF_LANDING)
    assert first["line"] == "1", f"the first hunk of the first file: {first}"

    page.keyboard.press("]")
    landed = page.evaluate(DIFF_LANDING)
    assert landed["line"] == "40", (
        f"the next hunk starts at new line 40, which its @@ header says: {landed}"
    )
    assert landed["path"] == "app/handlers.py", landed
    assert landed["top"] >= landed["headBottom"], (
        f"the row it landed on is behind the file's own pinned header: {landed}"
    )
    assert landed["headTop"] == landed["bannerBottom"], (
        f"the header is not pinned where the landing was measured against: {landed}"
    )
    assert errors == []
    page.close()


def test_a_backward_hunk_step_from_the_diff_itself_opens_one_file_and_lands_in_it(
    browser, serve
):
    """The mirror of the first `]` above, from the same standing: nothing focused inside
    the diff. That is where an in-page link to the diff's own id leaves a reader, since
    `focusDestination` focuses the host, and the diff's keys answer there because the
    scope climb starts at the focused node itself.

    Going forward, nothing-focused meant every hunk lay ahead and the walk stopped at the
    first. Going back it meant every hunk lay ahead too, so none lay behind: the walk ran
    through the whole list, opened each file and fetched its lines, and landed nowhere. A
    collapsed manifest is where that costs — one fetch per file — so the reading here is
    the fetch count and the open count beside the landing, on the review's last hunk."""
    url = serve(MANIFEST_DIFF_PAGE)
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        data_model.unified_diff_manifest(MULTI_HUNK_PATCH),
    )
    page, errors = open_page(browser, url)
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    fetched = []
    page.on(
        "request",
        lambda request: (
            fetched.append(request.url) if "/api/data" in request.url else None
        ),
    )
    # Focused as `focusDestination` leaves a host that an in-page link named.
    page.evaluate(
        """() => {
            const diff = document.querySelector('lf-diff');
            diff.tabIndex = -1;
            diff.focus();
        }"""
    )
    assert page.evaluate("() => document.activeElement.localName") == "lf-diff"
    assert (
        page.evaluate(
            "() => document.querySelector('lf-diff').shadowRoot.activeElement"
        )
        is None
    ), "the standing this test is about is nothing focused inside the diff"

    page.keyboard.press("[")
    page.wait_for_function(
        """() => {
            const at = document.querySelector('lf-diff').shadowRoot.activeElement;
            return at && at.dataset.line !== undefined;
        }"""
    )
    landed = page.evaluate(DIFF_LANDING)
    assert landed["line"] == "200", f"the last file's last hunk starts at 200: {landed}"
    assert landed["path"] == "app/routes.py", landed
    opened = page.evaluate(
        "() => document.querySelector('lf-diff').shadowRoot"
        ".querySelectorAll('details[open]').length"
    )
    assert opened == 1, f"the step opened files it never reached: {opened} open"
    assert len(fetched) == 1, (
        f"one file's lines were needed, {len(fetched)} were fetched"
    )
    assert errors == []
    page.close()


# A phrase late in the diff's longest line: unwrapped it is off the right of the box, and
# wrapped it is on a line box of its own — the two states the test below is about.
_DIFF_TAIL = "whichever remote it came from"
# The line is one row split across syntax spans inside a shadow root, so the range is built
# over its text nodes rather than dragged: a pointer drag cannot reach words that are off
# the box in the state this starts in.
_SELECT_IN_ROW = """(row, phrase) => {
    const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
    const nodes = [], starts = [];
    let flat = '';
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      starts.push(flat.length); nodes.push(node); flat += node.data;
    }
    const start = flat.indexOf(phrase);
    if (start < 0) return null;
    const at = (offset) => {
      const index = starts.findLastIndex((value) => value <= offset);
      return [nodes[index], offset - starts[index]];
    };
    const range = document.createRange();
    range.setStart(...at(start));
    range.setEnd(...at(start + phrase.length));
    const selection = getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    // The row is a block, so it has one client rectangle however many line boxes are in
    // it. Its height is what says how many, and its overhang says whether the words
    // selected were on screen at all.
    return { text: selection.toString(),
             height: Math.round(row.getBoundingClientRect().height),
             cut: row.scrollWidth > row.clientWidth };
}"""


def test_a_comment_on_a_wrapped_diff_line_names_the_line_an_unwrapped_one_names(
    browser, serve
):
    """Wrapping is a decision about line boxes; a comment's coordinate is a decision about
    lines of the patch. A wrapped line is still one line to the anchor, so the same words
    selected in the same row record the same coordinate either way — file, side, and
    source line — or turning the switch on would quietly move where a remark lands.

    The same row and the same phrase both times, with wrap the only difference, and the
    row's own box is read to prove that difference was real: one line tall and running
    past its box unwrapped, several lines tall and whole wrapped. Two identical anchors
    off a line that never wrapped would be asserting nothing at all."""
    page, errors = _bound_diff(browser, serve)
    row = page.locator('lf-diff [data-lf-datum=\'["app/handlers.py","new",81]\']')

    flat = row.evaluate(_SELECT_IN_ROW, _DIFF_TAIL)
    assert flat["text"] == _DIFF_TAIL, flat
    assert flat["cut"], f"the words selected are inside the box already: {flat}"
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.locator(".lf-composer textarea").fill("Unwrapped, this line runs off the box.")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)

    page.locator("lf-diff .lf-diff-wrap").click()
    folded = row.evaluate(_SELECT_IN_ROW, _DIFF_TAIL)
    assert folded["text"] == _DIFF_TAIL, folded
    assert folded["height"] > flat["height"] and not folded["cut"], (
        f"the line did not wrap, so both anchors describe one geometry: {folded}"
    )
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.locator(".lf-composer textarea").fill("Wrapped, the same words are on screen.")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)

    anchors = [
        event["anchor"] for event in sent_events(serve.page_dir) if event.get("anchor")
    ]
    assert len(anchors) == 2, anchors
    assert (
        anchors[0]
        == anchors[1]
        == {
            "section": "patch",
            "datum": '["app/handlers.py","new",81]',
            "quote": _DIFF_TAIL,
            "source": "review-patch",
            "data_revision": 1,
        }
    ), anchors
    assert errors == []


def test_a_control_a_widget_built_is_told_from_a_label_it_wrote(browser, serve):
    """One rule, read off the marker `offer` already writes, rather than each widget
    deciding for itself whether the reader can press what it drew.

    The measured fault was that they could not tell: on the command hub a chip that
    opened a section and a badge that counted something computed the same ground, the
    same ink, the same 999px corner and the same 11.5px size, so the only way to learn
    which was which was to press one. That is not a fact about chips — it is what happens
    when "this is pressable" has no owner, and every widget that draws a small filled
    shape has to remember to say it again.

    So the layer says it once, against `data-lf-offer`, and the value is what it reads:
    `offer` writes the tag or role for a thing to press and the empty string for the rest
    of the chrome it builds — a controls row, a history disclosure, an edit box. A badge
    the page wrote carries no marker at all and needs no exclusion, which is the half
    worth pinning: the rule stays off it because the marker means what it says, not
    because a list of static classes is kept beside the rule.

    Three registers, because a pointer, a hand and a keyboard arrive by different routes
    and only one of them is on screen at rest. The hand is the resting answer, and a
    control with nothing left to do gives it up along with its opacity. The badges are
    read outside a choose group on purpose: a card group makes the whole option the
    press, so a chip inside one inherits the hand from the control it is sitting in and
    would be answering this question about its parent. The wash is the aim, read as a
    change against each control's own resting shadow rather than against a constant: a
    control is free to wear a drop shadow of its own, and several here do, so an
    absolute reading would pin the theme's current furniture instead of the rule. The
    ring is the keyboard's, and this is the half of it a shared rule has to get right by
    losing: a control with a ring of its own keeps it and keeps its name, so what is
    asserted here is that a named ring is drawn and not which rule drew it. Which box
    wears it is a separate question from which one holds the focus - a joined option group
    draws it on the row its picks give up, and getComputedStyle(activeElement) reports
    'no ring' for a control whose ring is perfectly fine. Where nothing else claims one,
    the shared rule is what draws it, and that case is asserted on a request press in
    test_render_projection.py, which is where the layer has a control no widget rings."""
    page, errors = open_page(browser, serve(CHIP_PAGE))
    state = """() => {
      const kind = (el) => {
        const cs = getComputedStyle(el);
        return {cursor: cs.cursor, opacity: cs.opacity,
                off: el.matches('[aria-disabled="true"], :disabled')};
      };
      const presses = [...document.querySelectorAll('[data-lf-offer]')]
        .filter((el) => el.dataset.lfOffer !== '');
      const said = [document.querySelector('#intro > .tag'),
                    document.querySelector('#t-camera .lf-chips > span')];
      return {
        presses: presses.map(kind), said: said.map(kind),
        saidMarked: said.map((el) => el.hasAttribute('data-lf-offer')),
      };
    }"""
    rest = page.evaluate(state)
    live = [p for p in rest["presses"] if not p["off"]]
    spent = [p for p in rest["presses"] if p["off"]]
    assert live and spent and len(rest["said"]) == 2, (
        f"the page is missing one of the three populations this compares: {rest}"
    )
    assert all(p["cursor"] == "pointer" for p in live), (
        f"a control a widget built does not take the hand: {live}"
    )
    assert all(p["cursor"] == "default" and float(p["opacity"]) < 1 for p in spent), (
        f"a control with nothing left to do still offers itself: {spent}"
    )
    assert not any(s["cursor"] == "pointer" for s in rest["said"]), (
        "a label the page wrote takes the hand, so the reader is invited to press words"
    )
    assert rest["saidMarked"] == [False, False], (
        "a static label carries the control marker, so the rule is being kept off it by "
        "an exclusion rather than by the marker meaning what it says"
    )
    # The aim. The wash is an inset shadow so that it deepens whatever fill the control
    # already wears instead of contesting the `background` its own widget wrote, which is
    # what lets it be read as an addition to whatever the control had at rest.
    shadow = "el => getComputedStyle(el).boxShadow"
    mark = page.locator("#p-keep .lf-pick")
    before = mark.evaluate(shadow)
    mark.hover()
    washed = mark.evaluate(shadow)
    assert washed != before and "inset" in washed, (
        f"the control under the pointer says nothing about being pressed: "
        f"{before!r} -> {washed!r}"
    )
    tag = page.locator("#intro > .tag")
    tag_rest = tag.evaluate(shadow)
    tag.hover()
    assert tag.evaluate(shadow) == tag_rest, (
        "a label the page wrote answers the pointer as though it were a control"
    )

    # The keyboard. Reached by a real Tab, because :focus-visible is a fact about how
    # focus arrived and element.focus() alone draws no ring at all.
    mark.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    ring = page.evaluate(
        """() => { const on = document.activeElement.closest('lf-option')
                          ?? document.activeElement;
             const cs = getComputedStyle(on);
             return [cs.outlineStyle, cs.outlineWidth,
                     cs.getPropertyValue('--here-ring-w').trim(),
                     cs.getPropertyValue('--lf-here-ring').trim()]; }"""
    )
    assert ring[0] == "solid" and ring[1] == ring[2] and ring[3] != "none", (
        f"nothing draws a named here ring where the keyboard is standing: {ring}"
    )
    assert errors == []
    page.close()
