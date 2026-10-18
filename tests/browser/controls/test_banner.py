"""The banner: its rows, status words and counts, its More and Versions menus, the
Leaves drawer it opens, and controls that hold still through news."""

import os
import re
from datetime import datetime, timedelta

import pytest
from interact_support import (
    append_carried_log_record,
    append_command,
    declare_work,
    end_work,
    record_claim,
    working,
)
from leaf import event_log as events_model
from leaf import leases as leases_model
from leaf import service as service_model
from leaf import state as cleanup_model
from leaf.render_checks import wait_until_ready
from playwright.sync_api import expect
from render_cases_interaction import SUGGESTION_PAGE, live_url, panel_comment
from render_cases_layout import (
    BANNER_WATCH,
    DEFINE_BOXES,
    NEIGHBOUR,
    NEIGHBOURHOOD,
    banner_control,
    displaced,
    page_at_rest,
)
from render_harness import (
    LONG_PAGE,
    RELEASE_FOCUS,
    accessible_expanded,
    leaf_page,
    nudge,
    open_page,
    open_versions,
    refuse,
    resized,
    root_overflow,
    scroll_settled,
    sending,
    stamp_page,
    told,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_banner_status_keeps_publication_links_outside_its_disclosure(browser, serve):
    """Publication links remain ordinary links, with no disclosure left to open; the
    ordinary status is a native disclosure the browser announces open and shut."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    page.evaluate(
        "() => { window.__lfStatusOwner = document.querySelector('leaf-banner-status'); }"
    )
    door = page.locator(".lf-status-button")
    detail = page.locator(".lf-status-detail")
    door.focus()
    page.keyboard.press("Enter")
    expect(detail).to_be_visible()
    expect(detail).to_be_focused()
    assert accessible_expanded(page, ".lf-status-button") is True

    for _ in range(2):
        page.evaluate(
            """() => window.__lfStatusOwner.present(Object.freeze({
              tone: '', summary: '', queues: '', queuesWidest: '',
              explanation: 'Published copy Install Leaf',
              publication: Object.freeze({
                copy: 'Published copy ', install: 'Install Leaf',
                installUrl: '/#install',
              }),
            }))"""
        )
        expect(door).to_have_count(0)
        expect(detail).to_have_count(0)
        expect(page.locator(".lf-status-text")).to_have_text(
            "Published copy Install Leaf"
        )
        link = page.get_by_role("link", name="Install Leaf", exact=True)
        expect(link).to_have_attribute("href", "/#install")
        assert not link.evaluate("node => !!node.closest('button')")

        page.evaluate(
            """() => window.__lfStatusOwner.present(Object.freeze({
              tone: 'offline', summary: 'Server offline', queues: '', queuesWidest: '',
              explanation: 'Server offline detail', publication: null,
            }))"""
        )
        expect(page.locator(".lf-publication-install")).to_have_count(0)
        expect(door).to_have_text("Server offline")
        expect(door).to_have_attribute("popovertarget", "lf-status-detail")
        assert accessible_expanded(page, ".lf-status-button") is False
        door.focus()
        page.keyboard.press("Enter")
        expect(detail).to_be_visible()
        expect(detail).to_be_focused()
        expect(detail).to_have_text("Server offline detail")
        assert accessible_expanded(page, ".lf-status-button") is True
        page.keyboard.press("Escape")
        expect(detail).to_be_hidden()
        expect(door).to_be_focused()
        assert accessible_expanded(page, ".lf-status-button") is False


def test_every_more_row_wears_one_face_and_rings_inside_the_menu(browser, serve):
    """The developer preview stands in More at every width, so it is one of More's
    rows and wears their face: a badge's smaller type and padding made it a 24px row
    among 30px ones. Every row is packed 4px from the menu's border, so a row's ring
    is drawn inside it; outside, it stood a pixel from the border."""
    url = serve(
        SUGGESTION_PAGE,
        preview={
            "kind": "example",
            "example": "feature-gallery",
            "checkout": "leaf.menu-rows",
            "commit": "c79736ebfcc7",
            "interaction": "author",
            "started": "2026-09-06T12:00:00+00:00",
        },
    )
    page = open_page(browser, url)
    resized(page, 1440, 900)
    page.locator(".lf-banner-more").focus()
    page.keyboard.press("Enter")
    menu = page.locator(".lf-banner-menu")
    expect(menu).to_be_visible()
    rows = page.evaluate(
        """() => [...document.querySelectorAll('.lf-banner-menu .lf-btn')]
          .filter((row) => row.checkVisibility())
          .map((row) => {
            const style = getComputedStyle(row);
            return [row.className, row.getBoundingClientRect().height, style.fontSize,
                    style.paddingInlineStart];
          })"""
    )
    assert any("lf-preview" in row[0] for row in rows), rows
    assert len({tuple(row[1:]) for row in rows}) == 1, rows
    preview = page.locator(".lf-banner-menu .lf-preview")
    expect(preview).to_be_focused()
    ring = preview.evaluate(
        """row => {
          const style = getComputedStyle(row);
          const width = parseFloat(style.outlineWidth);
          const offset = parseFloat(style.outlineOffset);
          const box = row.getBoundingClientRect();
          const menu = row.closest('.lf-banner-menu');
          const edge = menu.getBoundingClientRect();
          const border = parseFloat(getComputedStyle(menu).borderTopWidth);
          return {matches: row.matches(':focus-visible'),
                  clear: box.top - offset - width - (edge.top + border)};
        }"""
    )
    assert ring["matches"] and ring["clear"] >= 2, ring


def test_send_returns_to_more_when_a_gesture_step_displaced_the_comment_control(
    browser, serve
):
    """Send closes the page comment card onto the control that opened it, and where a
    gesture step has taken that control's place on the row, onto More, the door that
    still reaches it (`bannerControlDoor`). A task on the user puts its Done step on
    the row in the reading loop's place."""
    url = serve(
        leaf_page(
            "Task on you",
            '<section id="plan"><h2>Plan</h2>'
            "<p>Ship it on Tuesday, after the backfill.</p></section>"
            '<p id="tail">Nothing else is planned.</p>',
        )
    )
    page = open_page(browser, url)
    resized(page, 1280, 800)
    actions = page.locator(".lf-banner-actions")
    comment = actions.locator(".lf-page-comment")
    done = actions.get_by_role("button", name="Done", exact=True)
    more = page.locator(".lf-banner-more")
    field = page.get_by_role("textbox", name="Comment on the page", exact=True)

    def send(words):
        page.evaluate(RELEASE_FOCUS)
        page.keyboard.press("c")
        expect(field).to_be_focused()
        page.keyboard.type(words)
        with sending(page, words):
            page.keyboard.press("ControlOrMeta+Enter")
        expect(page.locator(".lf-page-comment-card")).to_be_hidden()

    # The control: with nothing displacing it, Send lands on the row's Comment.
    expect(comment).to_be_visible()
    send("With the row as it was")
    expect(comment).to_be_focused()

    # A task the agent puts on the user stands its Done step on the row.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "todo",
            "author": "agent",
            "agent": "Agent",
            "session": "displaced-row",
            "owner": "user",
            "subject": {"kind": "element", "id": "plan"},
            "title": "Check the plan",
        },
    )
    told(page)
    expect(done).to_be_visible()
    expect(comment).to_be_hidden()
    send("With the row displaced")
    expect(more).to_be_focused()
    assert [
        event["text"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ] == ["With the row as it was", "With the row displaced"]


def test_one_version_opens_a_menu_with_its_version(browser, serve):
    """A lone version keeps its note reachable without advertising a version walk."""
    page = open_page(browser, serve(LONG_PAGE))
    version = page.locator(".lf-version")
    expect(version).to_be_enabled()
    expect(version).to_have_text("Showing v1")
    expect(version).to_have_attribute("aria-haspopup", "menu")
    banner_control(page, ".lf-version").click()
    menu = page.locator(".lf-version-menu")
    expect(menu).to_be_visible()
    expect(menu.locator(".lf-version-row")).to_have_count(1)
    expect(menu.locator(".lf-version-row")).to_have_attribute("aria-current", "true")
    expect(menu.locator(".lf-version-num")).to_have_text("v1 (latest version)")
    expect(menu.locator(".lf-version-note")).to_have_text("t")


def test_the_versions_menu_uses_the_banner_panel_and_its_doors_edge(browser, serve):
    """Versions shares the banner panel's fixed top and its door's horizontal edge."""
    page = open_page(browser, serve(LONG_PAGE))
    picker = page.locator(".lf-version")
    expect(picker).to_be_enabled()
    banner_control(page, ".lf-version").click()
    menu = page.locator(".lf-version-menu")
    expect(menu).to_be_visible()
    boxes = menu.evaluate(
        """menu => {
              const button = document.querySelector('.lf-banner-more').getBoundingClientRect();
              const banner = document.querySelector('.lf-banner').getBoundingClientRect();
              const box = menu.getBoundingClientRect();
              return {banner: {bottom: banner.bottom},
                      button: {top: button.top, bottom: button.bottom, right: button.right},
                      menu: {top: box.top, right: box.right, left: box.left}};
            }"""
    )
    assert boxes["menu"]["top"] == pytest.approx(
        boxes["banner"]["bottom"] + 6, abs=2
    ), boxes
    assert boxes["menu"]["right"] == pytest.approx(boxes["button"]["right"], abs=2), (
        f"the versions menu did not line up with More's right edge: {boxes}"
    )

    resized(page, 320, 844)
    phone = menu.evaluate(
        """menu => {
              const button = document.querySelector('.lf-banner-more').getBoundingClientRect();
              const banner = document.querySelector('.lf-banner').getBoundingClientRect();
              const box = menu.getBoundingClientRect();
              return {banner: {bottom: banner.bottom},
                      button: {bottom: button.bottom, right: button.right},
                      menu: {top: box.top, right: box.right, left: box.left},
                      viewport: innerWidth};
            }"""
    )
    assert phone["menu"]["top"] == pytest.approx(
        phone["banner"]["bottom"] + 6, abs=2
    ), phone
    assert phone["menu"]["right"] == pytest.approx(phone["button"]["right"], abs=2), (
        f"the phone menu did not line up with More's trailing edge: {phone}"
    )
    assert phone["menu"]["left"] >= 0 and phone["menu"]["right"] <= phone["viewport"], (
        f"the phone menu left the viewport: {phone}"
    )
    assert phone["menu"]["right"] - phone["menu"]["left"] <= min(
        360, phone["viewport"] - 16
    ), phone
    assert root_overflow(page) == 0

    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    open_versions(page)
    shortcut = menu.evaluate(
        "menu => ({top: menu.getBoundingClientRect().top, "
        "banner: document.querySelector('.lf-banner').getBoundingClientRect().bottom})"
    )
    assert shortcut["top"] == pytest.approx(shortcut["banner"] + 6, abs=2), shortcut


# Where the banner's two parts stand, the height the theme states for it (the document's
# head is reserved at that height), and each control on its row that the banner cuts off.
BANNER_ROWS = """() => {
  const box = (selector) => document.querySelector(selector).getBoundingClientRect();
  const banner = box('.lf-banner'), status = box('.lf-banner-status'),
        actions = box('.lf-banner-actions');
  const shown = [...document.querySelectorAll('.lf-banner-actions > *')]
    .filter((control) => control.checkVisibility());
  const clipped = shown
    .filter((control) => {
      const at = control.getBoundingClientRect();
      return at.left < Math.max(banner.left, actions.left) - 0.5
        || at.right > Math.min(banner.right, actions.right) + 0.5
        || at.bottom > banner.bottom + 0.5;
    })
    .map((control) => control.textContent.trim());
  return {wrapped: actions.top >= status.bottom - 1,
          height: banner.height, bannerBottom: banner.bottom,
          stated: parseFloat(getComputedStyle(document.body, '::before').height),
          clipped, controls: shown.map((control) => control.textContent.trim()),
          main: document.querySelector('body > main').getBoundingClientRect().top};
}"""


def signed_off(html):
    return html.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )


def assert_banner_as_stated(read, wrapped):
    assert read["wrapped"] == wrapped, read
    assert read["height"] == pytest.approx(read["stated"], abs=0.5), (
        f"the banner drew a height other than the one the theme states: {read}"
    )
    assert read["main"] == pytest.approx(read["bannerBottom"], abs=1), (
        f"the document's head does not end where the banner does: {read}"
    )
    assert not read["clipped"], f"the banner cut off {read['clipped']}: {read}"


@pytest.mark.parametrize(
    ("width", "touch", "signoff", "wrapped"),
    [
        # A tablet's window holds the status and the queue counts beside Threads.
        (820, True, False, False),
        # Below that, a landscape phone gives the run, led by the counts, a row of its
        # own, so the sentence keeps a row of its own too.
        (740, True, False, True),
        # Capability arrival cannot change this window's row allocation. Approval
        # arriving or leaving at the other widths is
        # test_approval_capability_changes_keep_banner_targets.
        (600, False, False, True),
        (600, False, True, True),
        # A phone held upright is one row: the status, Threads and More, with Approval
        # behind More.
        (390, True, False, False),
        (470, True, False, False),
    ],
)
def test_the_banner_rows_follow_the_window_independently_of_sign_off(
    browser, serve, width, touch, signoff, wrapped
):
    """The viewport, UI type and aim size allocate the banner before controls arrive.

    Approval and its absence share that allocation, so a revision cannot change the
    document's top reservation. Each control fits the height the theme states.
    """
    html = signed_off(SUGGESTION_PAGE) if signoff else SUGGESTION_PAGE
    context = browser.new_context(
        viewport={"width": width, "height": 800}, has_touch=touch, is_mobile=touch
    )
    page = open_page(browser, serve(html), context=context)
    page_at_rest(page)
    read = page.evaluate(BANNER_ROWS)
    assert_banner_as_stated(read, wrapped)
    row = 53 if touch else 52 if width <= 480 else 42
    assert read["height"] == pytest.approx(row + (36 if wrapped else 0), abs=1), read


def test_a_finger_s_steps_keep_the_banner_s_rows(browser, serve):
    """A step a finger takes on the banner, here page search's, stands in the reading
    loop's place on the row the banner already has. Just wider than a phone's upright
    face, where the steps have the least room beside the status, they still fit, and
    the banner keeps its height, so opening search moves nothing."""
    context = browser.new_context(
        viewport={"width": 490, "height": 800}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(SUGGESTION_PAGE), context=context)
    page_at_rest(page)
    before = page.evaluate(BANNER_ROWS)
    assert_banner_as_stated(before, wrapped=True)
    page.keyboard.press("/")
    page.keyboard.type("feeder")
    expect(
        page.locator(".lf-banner-actions > .lf-btn", has_text="Next")
    ).to_be_visible()
    page_at_rest(page)
    read = page.evaluate(BANNER_ROWS)
    assert "Close search" in read["controls"], read
    assert_banner_as_stated(read, wrapped=True)
    assert read["main"] == pytest.approx(before["main"], abs=1), (before, read)


def test_a_revision_that_asks_for_sign_off_keeps_the_banner_s_rows(browser, serve):
    """An arriving approval capability uses the banner's existing second row."""
    page = open_page(browser, live_url(serve(SUGGESTION_PAGE)))
    resized(page, 600, 800)
    page_at_rest(page)
    before = page.evaluate(BANNER_ROWS)
    assert_banner_as_stated(before, wrapped=True)
    page.wait_for_timeout(600)  # Let Chrome's recent-input grace expire before news.
    (serve.page_dir / "index.html").write_text(
        signed_off(SUGGESTION_PAGE).replace(
            "</lf-board>", "</lf-board>\n<p>A draft asking for sign-off.</p>"
        )
    )
    told(page)
    expect(page.locator(".lf-banner-actions > .lf-signoff")).to_be_visible()
    page_at_rest(page)
    after = page.evaluate(BANNER_ROWS)
    assert_banner_as_stated(after, wrapped=True)
    for position in ("height", "bannerBottom", "stated", "main"):
        assert after[position] == pytest.approx(before[position], abs=0.5), (
            before,
            after,
        )


def test_open_banner_menu_holds_seats_until_the_next_opening(browser, serve):
    """Passive removals and arrivals keep the reading and its keyboard destinations."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    page.evaluate("""async () => {
      window.toolbar = await window.__lfCheckApi();
      for (const [key, rank, offered] of [
        ['retiring', -30, true], ['arriving', -25, false], ['staying', -20, true],
        ['returning', -15, false],
      ]) {
        const control = document.createElement('button');
        control.className = `lf-ui lf-btn test-${key}`;
        control.textContent = key;
        toolbar.registerBannerControl({key, control, rank, conditional:true, offered, row: {label: key, group: 'page'}});
      }
    }""")
    more = page.locator(".lf-banner-more")
    more.focus()
    page.keyboard.press("Enter")
    retiring = page.locator(".test-retiring")
    staying = page.locator(".test-staying")
    arriving = page.locator(".test-arriving")
    retiring.focus()
    expect(retiring).to_be_focused()
    before = staying.bounding_box()
    page.evaluate("""() => {
      toolbar.showNews(document.querySelector('.test-retiring'), false);
      toolbar.showNews(document.querySelector('.test-arriving'), true);
      toolbar.markBannerControl(document.querySelector('.test-arriving'), 'new action');
    }""")
    expect(retiring).to_be_hidden()
    assert arriving.is_hidden()
    expect(staying).to_be_focused()
    expect(more).to_have_attribute("aria-label", re.compile("new action"))
    assert staying.bounding_box() == before
    assert retiring.evaluate("node => node.offsetHeight") > 0
    page.keyboard.press("Tab")
    expect(arriving).not_to_be_focused()
    page.keyboard.press("Escape")
    expect(more).to_be_focused()
    page.keyboard.press("Enter")
    expect(arriving).to_be_visible()
    expect(arriving).to_be_focused()
    assert retiring.evaluate("node => node.offsetHeight") == 0
    # Explicit travel can reveal a newly offered destination in the held menu.
    # Both the shared reveal route and a nested layer's return use that same owner.
    page.evaluate("""async () => {
      const {reveal} = await window.__lfCheckApi();
      const target = document.querySelector('.test-retiring');
      document.querySelector('.test-arriving').onclick = () => reveal(target, () => true);
      toolbar.showNews(target, true);
    }""")
    assert retiring.is_hidden()
    arriving.press("Enter")
    expect(retiring).to_be_visible()
    page.evaluate("""() => {
      const target = document.querySelector('.test-returning');
      document.querySelector('.test-arriving').onclick = () => toolbar.returnToBannerControl(target);
      toolbar.showNews(target, true);
    }""")
    returning = page.locator(".test-returning")
    assert returning.is_hidden()
    arriving.press("Enter")
    expect(returning).to_be_focused()


def test_item_banner_controls_keep_identity_and_focus_in_the_fixed_menu(
    browser, serve, other_leaf
):
    """The fixed menu retains each Lit-faced control and hands off removed focus."""
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    panel_comment(serve.page_dir, "Is this ready?", author="agent", question="Ship it?")
    page = open_page(browser, url)
    resized(page, 1440, 900)
    answer_all = page.locator(".lf-answer-all")
    expect(answer_all).to_be_hidden()
    expect(page.locator(".lf-banner-menu > .lf-answer-all")).to_have_count(1)
    page.evaluate(
        "button => { window.__lfBulkControl = button; }", answer_all.element_handle()
    )
    resized(page, 390, 900)
    expect(page.locator(".lf-banner-menu > .lf-answer-all")).to_have_count(1)
    assert answer_all.evaluate("button => button === window.__lfBulkControl")
    assert answer_all.locator(":scope > lf-item-banner-face").count() == 1
    order = page.evaluate(
        """() => [...document.querySelector('.lf-banner-menu').children,
                    ...document.querySelector('.lf-banner-actions').children]
          .map(control => control.matches('.lf-page-map-toggle') ? 'map' :
                          control.matches('.lf-answer-all') ? 'blanket' : null)
          .filter(Boolean)"""
    )
    assert order == [
        "map",
        "blanket",
    ], f"the toolbar changed the established Map-before-blanket order: {order}"

    page.evaluate(
        """async () => {
          const toolbar = await window.__lfCheckApi();
          for (let i = 0; i < 3; i++) {
            const control = document.createElement('button');
            control.className = `lf-ui lf-btn lf-focus-candidate-${i}`;
            control.textContent = `Focus candidate ${i + 1}`;
            control.disabled = i === 1;
            toolbar.registerBannerControl({
              key: `test-focus-candidate-${i}`,
              control,
              rank: toolbar.BANNER_CONTROL_RANK.blanket + i + 1,
              row: { label: control.textContent, group: "page" },
            });
          }
        }"""
    )
    page.locator(".lf-banner-more").click()
    retiring = page.locator(".lf-focus-candidate-0")
    retiring.focus()
    page.evaluate(
        """async control => {
          const toolbar = await window.__lfCheckApi();
          toolbar.showBannerControl(control, false);
        }""",
        retiring.element_handle(),
    )
    expect(page.locator(".lf-focus-candidate-2")).to_be_focused()

    # Semantic presence can change while the user is inside the overflow without
    # repartitioning the list under them or stranding focus on the retired control.
    expect(page.locator(".lf-banner-menu")).to_be_visible()
    answer_all.focus()
    page.evaluate(
        """async button => {
          const toolbar = await window.__lfCheckApi();
          toolbar.showNews(button, false);
        }""",
        answer_all.element_handle(),
    )
    expect(answer_all).to_be_hidden()
    expect(page.locator(".lf-banner-menu")).to_be_visible()
    assert answer_all.evaluate(
        "button => button.parentElement.matches('.lf-banner-menu')"
    )
    assert page.evaluate(
        "() => Boolean(document.activeElement.closest('.lf-banner-menu'))"
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-banner-more")).to_be_visible()


def test_a_status_kind_change_is_announced_in_the_banners_own_words(browser, serve):
    """The dot going red is not an announcement.

    The banner flipped to the offline colour and rewrote its line while the live region
    went on holding whatever it last said, so a user who is not watching the top of the
    window learned nothing. A kind changing — work starting, a turn ending, the server
    going — is what is worth interrupting for, and what it says is the banner's own
    sentence rather than a second account of it. The age moving and a count turning over
    are not kinds and stay out of the region."""
    url = serve(SUGGESTION_PAGE)
    # The agent has the page in hand when the user opens it.
    working(serve.page_dir, "Writing the page")
    page = open_page(browser, url)
    live = page.locator(".lf-live")
    expect(page.locator(".lf-banner .lf-dot.working")).to_be_visible()
    # The page arriving is the document's own announcement, not a change in it.
    assert live.text_content() == "", (
        f"the banner announced its first reading: {live.text_content()!r}"
    )

    claim = record_claim(serve.page_dir, id="s", pid=os.getpid())
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(serve.page_dir, claim["id"])
    )
    assert lease
    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.set_stream_activity(
            claim["id"], "provider-turn", {"kind": "awaiting_input"}
        )
    told(page)
    expect(live).to_contain_text("Claude is waiting for input")
    announced_wait = live.text_content()

    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.set_stream_activity(
            claim["id"], "provider-turn", {"kind": "tool", "detail": "Checking"}
        )
    told(page)
    assert live.text_content() == announced_wait

    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.set_stream_activity(
            claim["id"], "provider-turn", {"kind": "awaiting_approval"}
        )
    told(page)
    expect(live).to_contain_text("Claude is waiting for approval")
    leases_model.release_lease(lease)

    page.route("**/api/**", refuse)
    try:
        # A healthy page never asks without news, so give it one: the read that follows
        # is the one the route refuses.
        nudge(serve.page_dir)
        expect(page.locator(".lf-banner .lf-dot.offline")).to_be_visible()
        offline = " ".join(page.locator(".lf-status-detail").text_content().split())
        assert offline.startswith("Server offline"), (
            f"the banner's offline line has moved: {offline!r}"
        )
        expect(live).to_have_text(offline)
    finally:
        page.unroute("**/api/**")


def test_the_neighbour_reading_detects_a_whole_row_moving_on_press(browser):
    """Moving the containing row must not cancel a control's screen displacement."""
    page = browser.unwatched.new_page()
    page.set_viewport_size({"width": 800, "height": 600})
    page.set_content("""
      <div class="lf-playground-actions">
        <button id="move" onclick="this.parentElement.style.transform =
          this.parentElement.style.transform ? 'translate(2000px, 24px)' :
            'translate(32px, 24px)'">Move row</button>
        <button>Neighbour</button>
      </div>
    """)
    page.evaluate(DEFINE_BOXES)
    before = page.locator("#move").evaluate(NEIGHBOURHOOD, NEIGHBOUR)
    assert before["names"] == ['button "Neighbour"']
    assert displaced(before, page.evaluate("() => window.__lfBoxes()")) == []

    page.locator("#move").click()
    assert displaced(before, page.evaluate("() => window.__lfBoxes()")) == [
        'button "Neighbour" moved by [32, 24, 0, 0] (left, top, width, height)'
    ]
    # Moving beyond the viewport is displacement too, not hiding the control.
    page.locator("#move").click()
    assert page.get_by_role("button", name="Neighbour").bounding_box()["x"] > 800
    assert displaced(before, page.evaluate("() => window.__lfBoxes()")) == [
        'button "Neighbour" moved by [2000, 24, 0, 0] (left, top, width, height)'
    ]


def test_the_poll_leaves_the_banner_where_it_was(browser, serve):
    """The other half of the same rule, for the changes nobody asked for.

    A press has a line — the row the pressed control stands on, where the next gesture
    is already aimed — and below it the page is content and may move. News arriving on
    the poll has no gesture at all, so there is no line to draw: the user was
    somewhere else entirely, and every control in the chrome is a control they are
    holding. The document may still change under them, because a fact arriving is what
    they are here to see; its resulting destination may not be. A control whose own words
    the news rewrote may grow or shrink into free room, as the status press does when the
    sentence it carries changes; nothing else may move for it.

    The banner is where all of it lands, and it is packed to the right against a spacer,
    which decides who pays. A control that grows moves itself and everything to its
    *left*; everything to its right keeps its place. So `Threads: 9` becoming
    `Threads: 10` — a comment posted from the terminal while the user reads —
    slid the version picker 6px left, and the Accept all a second tab's decision puts
    away took the New-version chip with it.

    Driven by writing the events a real one would leave, since that is what the page
    reads either way, and there is no other way to reach this half: every gesture the
    press sweep above can make is one the user made, and none of these are."""
    # Three pending suggestions, so the Accept all count has somewhere to go before it
    # runs out; sign-off asked, so the row is the full one; nine comments already, so the
    # tenth crosses a digit; and pinned, so a v2 landing leaves the page where it is and
    # offers the chip rather than following it.
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html, comments=9)
    d = serve.page_dir
    page = open_page(browser, url, pin=True)
    comments = ".lf-banner .lf-threads-toggle"
    accept_all = '[title^="Accept every"]'
    page.wait_for_function(
        f"() => document.querySelector('{comments}').textContent === 'Threads: 9'"
    )
    page_at_rest(page)

    def publish_v2():
        stamp_page(d, html, "two")

    # The same events a second tab's presses would have posted, which is the only way one
    # user's browser hears about another's decisions.
    def decide(*widgets):
        for widget in widgets:
            append_command(
                d,
                {
                    "kind": "action",
                    "author": "user",
                    "revision": 1,
                    "widget": widget,
                    "action": "decide",
                    "detail": {"outcome": "accept"},
                },
            )

    for what, drive, arrived in [
        (
            "a tenth comment arrives",
            lambda: append_carried_log_record(
                d,
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "A tenth.",
                },
            ),
            f"() => document.querySelector('{comments}').textContent === 'Threads: 10'",
        ),
        (
            "a new version is published",
            publish_v2,
            # Legible wherever the fold has put it: on the row in its own words, or behind
            # the door with the door saying there is something there.
            (
                "() => { const chip = document.querySelector('.lf-latest-chip');"
                "  const door = document.querySelector('.lf-banner-more');"
                "  return chip.checkVisibility({visibilityProperty: true})"
                "    || (chip.classList.contains('lf-news-shown')"
                "        && door.hasAttribute('data-lf-news')); }"
            ),
        ),
        (
            "another tab decides two of the three pending suggestions",
            lambda: decide("sug-refill", "sug-thistle"),
            (
                f"() => document.querySelector('{accept_all}')"
                ".textContent === 'Accept all (1)'"
            ),
        ),
        (
            "another tab decides the last one",
            lambda: decide("sug-in-card"),
            # Gone, asked the way it is now gone: a control that has stood on this row keeps
            # its room, so its box is exactly what must not have changed here.
            (
                f"() => !document.querySelector('{accept_all}')"
                f" || !document.querySelector('{accept_all}')"
                ".checkVisibility({visibilityProperty: true})"
            ),
        ),
    ]:
        page.evaluate(DEFINE_BOXES)
        before = page.evaluate(BANNER_WATCH, NEIGHBOUR)
        assert len(before["names"]) >= 4, (
            f"before {what} the banner was showing only {before['names']}, which is "
            "fewer controls than it always has — this step asserts almost nothing"
        )
        drive()
        page.wait_for_function(arrived)
        page_at_rest(page)
        moved = displaced(before, page.evaluate("() => window.__lfBoxes()"), news=True)
        assert not moved, f"{what} and the banner moved:\n  " + "\n  ".join(moved)

    # The two primary controls keep their reserved words when the row narrows.
    holds_its_width = (
        "(names) => Object.fromEntries(names.map((s) => "
        "  [s, document.querySelector('.lf-banner-actions > ' + s)?.offsetWidth ?? null]))"
    )
    named = [
        ".lf-threads-toggle",
        ".lf-signoff",
    ]
    wide = page.evaluate(holds_its_width, named)
    # Narrowed, but not past the covering breakpoint: that row deliberately spends less
    # padding, so its controls are legitimately a few pixels narrower and a comparison
    # across it would read that as the collapse this is about.
    resized(page, 900, 900)
    narrow = page.evaluate(holds_its_width, named)
    stayed = {name: width for name, width in narrow.items() if width is not None}
    assert len(stayed) >= 2, f"the primary row lost one of its controls: {stayed}"
    assert stayed == {name: wide[name] for name in stayed}, (
        f"a primary control changed width: {stayed} against {wide}"
    )


STATUS_PRESS = """() => {
  const press = document.querySelector('.lf-status-button');
  const text = press.querySelector('.lf-status-text');
  const status = document.querySelector('.lf-banner-status');
  const roomRight = status.getBoundingClientRect().right
    - parseFloat(getComputedStyle(status).paddingRight);
  const box = press.getBoundingClientRect();
  return {left: box.left, top: box.top, right: box.right, roomRight,
          words: text.textContent, shown: text.clientWidth, needed: text.scrollWidth};
}"""


STATUS_COUNTS = """() => {
  const counts = document.querySelector('.lf-status-queues');
  const box = counts.getBoundingClientRect();
  const bar = document.querySelector('.lf-banner');
  const banner = bar.getBoundingClientRect();
  // Where the banner's rows end: its rule below them draws no row.
  const rowsEnd = banner.bottom - parseFloat(getComputedStyle(bar).borderBottomWidth);
  const meets = (other) => box.left < other.right - 0.5 && other.left < box.right - 0.5
    && box.top < other.bottom - 0.5 && other.top < box.bottom - 0.5;
  const others = [document.querySelector('.lf-banner-status'),
    ...document.querySelectorAll('.lf-banner-actions > :not([hidden])')];
  const approval = document.querySelector('.lf-banner-actions > .lf-signoff');
  // A room cuts its words inside its own child (controls.css), which the control's
  // scroll width does not see.
  const words = (n) => n.querySelector('[data-lf-room] > *') ?? n;
  return {shown: words(counts).clientWidth, needed: words(counts).scrollWidth,
          left: box.left, top: box.top, inert: counts.inert,
          statusLeft: document.querySelector('.lf-status-button').getBoundingClientRect().left,
          statusBottom: document.querySelector('.lf-banner-status').getBoundingClientRect().bottom,
          inBanner: box.left >= banner.left && box.right <= banner.right
            && box.top >= banner.top && box.bottom <= banner.bottom,
          drawn: box.top < rowsEnd - 0.5 && box.bottom > banner.top + 0.5,
          approval: approval?.checkVisibility()
            ? {shown: words(approval).clientWidth, needed: words(approval).scrollWidth}
            : null,
          overlaps: others.filter((n) => meets(n.getBoundingClientRect()))
            .map((n) => n.className)};
}"""


@pytest.mark.parametrize(("width", "counts_drawn"), [(1280, True), (390, False)])
def test_the_status_press_grows_into_free_room_and_moves_nothing(
    browser, serve, width, counts_drawn
):
    """The status press is as wide as its words: its ring and its hit box are the
    sentence's, not the empty banner's. As the sentence the agent declares grows, the
    press grows rightward into the room the controls leave, and nothing else on the banner
    moves; once that room runs out its words truncate rather than push More. Approval and
    the agent's On count stay whole throughout. At 390 the status shares the phone's
    one row with Threads and More, Approval and On me stand behind More, and the count
    gives way to the sentence, which keeps what the two controls leave."""
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    page = open_page(browser, url)
    resized(page, width, 844)

    def say(detail):
        working(serve.page_dir, detail)
        told(page)
        page.wait_for_function(
            "(words) => document.querySelector('.lf-status-text').textContent === words",
            arg=f"Claude working — {detail}",
        )
        page_at_rest(page)
        return page.evaluate(STATUS_PRESS)

    short = say("tests")
    assert short["shown"] >= short["needed"], short
    # A press spanning the room would end at its edge; a phone's room is narrow.
    assert short["right"] < short["roomRight"] - 20, (
        f"a short status press still spans the banner's free room: {short}"
    )
    # The page's three suggestions and required approval wait on the user in
    # On me. The page task waits on the agent, so the agent's count stands beside status.
    expect(page.locator(".lf-queue")).to_have_text("On me: 4")
    expect(page.locator(".lf-status-queues")).to_have_text("On Claude: 1")
    page.evaluate(DEFINE_BOXES)
    beside = page.evaluate(
        BANNER_WATCH, f":is({NEIGHBOUR}, .lf-status-queues):not(.lf-status-button)"
    )
    assert any("lf-banner-more" in name for name in beside["names"]), beside["names"]

    # Longer, and still inside a phone's room beside Threads and More, with room to
    # spare for Linux's wider sans and the agent's name.
    longer = say("tests again")
    assert longer["shown"] >= longer["needed"], longer
    assert (longer["left"], longer["top"]) == (short["left"], short["top"])
    assert longer["right"] > short["right"], (short, longer)
    moved = displaced(beside, page.evaluate("() => window.__lfBoxes()"))
    assert not moved, "a longer status moved the banner:\n  " + "\n  ".join(moved)

    endless = say("checking every thread on the page before recording the update " * 4)
    assert endless["shown"] < endless["needed"], (
        f"a sentence longer than the room was shown whole: {endless}"
    )
    assert endless["right"] <= endless["roomRight"] + 0.5, endless
    # The sentence gives up its room, and the counts never cut Approval: where they
    # are drawn they stand whole, inside the banner, clear of the status and every
    # control, and on a phone's one row the banner leaves them out whole, with
    # Approval behind More.
    counts = page.evaluate(STATUS_COUNTS)
    if counts_drawn:
        assert counts["approval"], counts
        assert counts["approval"]["shown"] >= counts["approval"]["needed"], counts
    else:
        assert counts["approval"] is None, counts
    assert counts["drawn"] == counts_drawn, counts
    # The counts are a press; one the banner does not draw takes no Tab stop.
    assert counts["inert"] != counts_drawn, counts
    if counts_drawn:
        assert counts["shown"] >= counts["needed"] > 0, counts
        assert counts["inBanner"] and not counts["overlaps"], counts
    assert (endless["left"], endless["top"]) == (short["left"], short["top"])
    moved = displaced(beside, page.evaluate("() => window.__lfBoxes()"))
    assert not moved, "a status past its room pushed the banner:\n  " + "\n  ".join(
        moved
    )


def test_the_counts_lead_the_second_row_where_the_run_leaves_room(browser, serve):
    """Just wider than a phone held upright, the banner's status sentence has the first
    row, and the agent's On count leads the second, under the sentence's start, where
    the run leaves it room whole. A finger's search steps share that row: the count
    stands whole beside them where the font leaves it room, or gives way to them, never
    cutting a step or being cut itself, and comes back where it stood once the search
    closes."""
    context = browser.new_context(
        viewport={"width": 490, "height": 800}, has_touch=True, is_mobile=True
    )
    url = serve(SUGGESTION_PAGE)
    # A comment the agent owes a reply, so there is an agent's count to stand there.
    panel_comment(serve.page_dir, "Is the feeder sized right?")
    page = open_page(browser, url, context=context)
    expect(page.locator(".lf-status-queues")).to_have_text("On Claude: 1")
    page_at_rest(page)
    resting = page.evaluate(STATUS_COUNTS)
    assert resting["drawn"] and resting["inBanner"] and not resting["inert"], resting
    assert resting["shown"] >= resting["needed"] > 0, resting
    assert not resting["overlaps"], resting
    assert resting["left"] == pytest.approx(resting["statusLeft"], abs=1), resting
    assert resting["top"] >= resting["statusBottom"] - 0.5, resting

    page.keyboard.press("/")
    page.keyboard.type("feeder")
    expect(
        page.locator(".lf-banner-actions > .lf-btn", has_text="Next")
    ).to_be_visible()
    page_at_rest(page)
    searching = page.evaluate(STATUS_COUNTS)
    # Whether "On Claude: 1" fits beside the steps is the font's to say: macOS's leaves it
    # room at this width and Linux's does not. Either way it is drawn whole and live, or
    # gone and out of reach.
    assert searching["drawn"] != searching["inert"], searching
    if searching["drawn"]:
        assert searching["inBanner"] and not searching["overlaps"], searching
    clipped = page.evaluate(BANNER_ROWS)["clipped"]
    assert not clipped, f"the search steps were cut off: {clipped}"

    page.keyboard.press("Escape")
    expect(page.locator(".lf-banner-actions > .lf-btn", has_text="Next")).to_be_hidden()
    page_at_rest(page)
    back = page.evaluate(STATUS_COUNTS)
    assert (back["drawn"], back["inert"], back["left"], back["top"]) == (
        True,
        False,
        resting["left"],
        resting["top"],
    ), (resting, back)


def test_a_phone_s_one_row_seats_a_finger_s_steps_and_leaves_the_counts_out(
    browser, serve
):
    """On a phone the banner is one row and the queue counts stand down, inert, which
    the status's disclosure still says. A finger's search steps take Threads' place on
    that row whole, the status keeping what they leave, and the banner keeps its height
    while they stand and after they go."""
    context = browser.new_context(
        viewport={"width": 390, "height": 800}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(SUGGESTION_PAGE), context=context)
    expect(page.locator(".lf-status-detail")).to_contain_text("Waiting on me")
    page_at_rest(page)
    resting = page.evaluate(BANNER_ROWS)
    assert_banner_as_stated(resting, wrapped=False)
    counts = page.evaluate(STATUS_COUNTS)
    assert not counts["drawn"] and counts["inert"], counts

    page.keyboard.press("/")
    page.keyboard.type("feeder")
    expect(
        page.locator(".lf-banner-actions > .lf-btn", has_text="Next")
    ).to_be_visible()
    page_at_rest(page)
    searching = page.evaluate(BANNER_ROWS)
    assert_banner_as_stated(searching, wrapped=False)
    assert "Close search" in searching["controls"], searching
    assert page.locator(".lf-status-button").bounding_box()["width"] > 0

    page.keyboard.press("Escape")
    expect(page.locator(".lf-banner-actions > .lf-btn", has_text="Next")).to_be_hidden()
    page_at_rest(page)
    back = page.evaluate(BANNER_ROWS)
    assert back["main"] == pytest.approx(resting["main"], abs=0.5), (resting, back)


def test_the_band_stays_over_the_covering_leaves_drawer(browser, serve, other_leaf):
    """A drawer stands under the bottom bar, its list ending above the band's height, and
    the Pages drawer, which always covers the page, is no exception: the band states the
    keys the drawer answers and stays over it and its scrim, its More control live. The
    covering drawer used to stand over the band, hiding the hints it painted for the drawer
    ("open it in a tab", "close pages") under the drawer and the scrim, where the items
    drawer, standing beside the page, left them in view."""
    page = open_page(browser, serve(LONG_PAGE))
    resized(page, 1440, 900)
    expect(page.locator(".lf-others")).to_have_text("All pages (2)")
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    drawer = page.locator(".lf-others-panel")
    assert drawer.evaluate("surface => surface.closest('dialog').matches(':modal')")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("close pages")
    reading = page.evaluate(
        """() => {
          const band = document.querySelector('.lf-shortcut-bar');
          const more = band.querySelector('.lf-shortcut-more');
          const box = more.getBoundingClientRect();
          const hit = document.elementFromPoint(box.x + box.width / 2,
                                                box.y + box.height / 2);
          const z = (selector) =>
            Number(getComputedStyle(document.querySelector(selector)).zIndex);
          return {more: more.contains(hit), inert: Boolean(band.closest('[inert]')),
                  over: z('.lf-shortcut-bar') > Math.max(
                    z('.lf-others-panel'), z('.lf-auxiliary-scrim'))};
        }"""
    )
    assert reading == {"more": True, "inert": False, "over": True}, reading
    page.keyboard.press("Escape")
    expect(drawer).not_to_be_visible()
    expect(page.locator(".lf-shortcut-bar")).not_to_have_attribute(
        "data-lf-over-covering", ""
    )


def test_the_banner_uses_the_page_mark_and_puts_each_edge_by_its_panel(
    browser, serve, other_leaf
):
    """The page mark and fixed primary/secondary seats survive every width."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    stamp_page(serve.page_dir, html, "two")
    page = open_page(browser, url)
    expect(page.locator(".lf-others")).to_have_text("All pages (2)")
    expect(page.locator(".lf-signoff")).to_be_visible()

    mark = page.locator(".lf-banner .lf-dot")
    mask = mark.evaluate("el => getComputedStyle(el).maskImage")
    assert "/icon.svg" in mask, f"the banner mark came from {mask!r}, not icon.svg"
    page.emulate_media(forced_colors="active")
    forced = mark.evaluate(
        """el => ({mark: getComputedStyle(el).backgroundColor,
                    banner: getComputedStyle(el.closest('.lf-banner')).backgroundColor})"""
    )
    assert forced["mark"] != forced["banner"], (
        "the masked page mark disappears into the forced-colors banner"
    )
    page.emulate_media(forced_colors="none")

    def actions():
        return page.evaluate(
            """() => {
                 const toolbar = document.querySelector('.lf-banner-actions');
                 const menu = document.querySelector('.lf-banner-menu');
                 return [...menu.children, ...toolbar.children].map(el =>
                   [['others', 'lf-others'], ['latest', 'lf-latest-chip'],
                    ['queue', 'lf-queue'], ['version', 'lf-version'],
                    ['comments', 'lf-threads-toggle'], ['signoff', 'lf-signoff']]
                     .find(([, cls]) => el.classList.contains(cls))?.[0])
                   .filter(Boolean);
               }"""
        )

    # A phone moves Approval and On me to the head of More, off the row.
    desk = ["others", "latest", "version", "signoff", "queue", "comments"]
    phone = ["signoff", "queue", "others", "latest", "version", "comments"]
    for width in (1200, 390, 320):
        resized(page, width, 900)
        assert actions() == (desk if width > 480 else phone)
        expect(page.locator(".lf-banner-menu > .lf-others")).to_have_count(1)
        expect(page.locator(".lf-banner-menu > .lf-version")).to_have_count(1)
        seat = ".lf-banner-actions" if width > 480 else ".lf-banner-menu"
        expect(page.locator(f"{seat} > .lf-signoff")).to_have_count(1)
        expect(page.locator(".lf-banner-actions > .lf-threads-toggle")).to_be_visible()
        fit = page.evaluate(
            """() => { const actions = document.querySelector('.lf-banner-actions');
              const threads = document.querySelector('.lf-threads-toggle');
              const box = threads.getBoundingClientRect();
              const edge = document.elementFromPoint(box.right - 1, box.top + box.height / 2);
              return {shown: actions.clientWidth, needed: actions.scrollWidth,
                      threads: {left: box.left, right: box.right,
                                visible: threads.checkVisibility(),
                                ownsRightEdge: edge === threads || threads.contains(edge)}}; }"""
        )
        assert fit["needed"] <= fit["shown"] + 1, fit
        assert root_overflow(page) == 0, fit
        assert fit["threads"]["visible"] and fit["threads"]["ownsRightEdge"], fit
        assert 0 <= fit["threads"]["left"] < fit["threads"]["right"] <= width, fit


def test_a_panel_row_follows_its_pages_status_live(
    browser, serve, other_leaf, tmp_path
):
    """The panel is a status surface, not a snapshot: a neighbour's declaration
    changing on disk repaints its row at the next poll, in place, and the row's
    hover follows it, being the same account written where there is room for it
    whole."""
    _, other_dir = other_leaf
    page = open_page(browser, serve(LONG_PAGE))
    # The key is live once the list has arrived, which the button's count states.
    expect(page.locator(".lf-others")).to_have_text("All pages (2)")
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    row = page.locator("a.lf-others-row")
    expect(row.locator(".lf-others-line")).to_have_text("Working — running the suite")
    declare_work(other_dir, "recording the demo")
    told(page)
    expect(row.locator(".lf-others-line")).to_have_text("Working — recording the demo")
    # A neighbour waiting on its own user says so in this seat's shorter words, and
    # in the same term its banner uses, with what it is waiting for: the panel is
    # where a user picks which page to go to. The hover holds it whole, since the
    # line ellipsizes at the panel's width, and it is the row's hover and not the
    # line's, the innermost title winning where two overlap.
    end_work(other_dir)
    cleanup_model.write_json(
        other_dir / "status.json",
        {
            "state": "waiting",
            "detail": "pick a storage engine",
            "ts": cleanup_model.now_iso(),
        },
    )
    told(page)
    line = row.locator(".lf-others-line")
    expect(line).to_have_text("Awaits — pick a storage engine")
    expect(row).to_have_attribute(
        "title",
        f"The other leaf\n{tmp_path / 'other-work'}\nAwaits — pick a storage engine",
    )
    assert line.get_attribute("title") is None, (
        "the line carries a tooltip of its own again, which wins under the pointer "
        "over the row's whole account"
    )


def test_a_closed_leaf_clears_itself_off_the_drawer(browser, serve, other_leaf):
    """A closed leaf leaves the drawer on the poll that says so. Its server stays
    up — a persistent one for good — so the row would otherwise stand forever and the
    count a user glances at to find who needs them would become a tally of
    everything that has ever run here. This page's own row never drops — a user
    looking at a closed page is still looking at it — so a drawer with nothing live
    left on it still says where the user is, and the count says (1) for it."""
    _, other_dir = other_leaf
    page = open_page(browser, serve(LONG_PAGE))
    btn = page.locator(".lf-others")
    expect(btn).to_have_text("All pages (2)")
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    rows = page.locator("a.lf-others-row")
    expect(rows).to_have_count(1)
    rows.first.focus()
    cleanup_model.write_json(
        other_dir / "status.json",
        {"state": "idle", "detail": "", "ts": cleanup_model.now_iso()},
    )
    told(page)
    expect(rows).to_have_count(0)
    expect(btn).to_have_text("All pages (1)")
    expect(page.locator(".lf-others-self .lf-others-title")).to_have_text("long")
    expect(page.locator(".lf-others-panel")).to_be_focused()
    # The open panel remains the modal destination after its last link leaves. Its own
    # nav is the fallback landing, and its global destination remains the same toggle as the
    # banner door even though that inert door is unavailable to a pointer.
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(page.locator(".lf-others-panel")).not_to_be_visible()
    expect(btn).to_have_attribute("aria-expanded", "false")
    # Nothing live remains to reopen it: its button stands while the panel does and
    # stands down with it, which is the count's other half.
    told(page)
    expect(btn).not_to_be_visible()


def test_a_removed_leaf_hands_focus_on_without_revealing_the_old_reading(
    browser, serve, other_leaf
):
    """A disappearing focused row preserves the later rows reached with the wheel."""
    page = open_page(browser, serve(LONG_PAGE))
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(page.locator(".lf-others-panel")).to_have_class(re.compile(r"\bopen\b"))
    page.evaluate(
        "document.querySelector('.lf-others-panel').getAnimations().forEach(a => a.finish())"
    )
    page.evaluate(
        """async () => {
          const list = document.querySelector('lf-leaves-list');
          const row = list.model.rows.find(row => !row.self);
          window.auditLeaves = Array.from({length: 30}, (_,index) => ({
            ...row, key: `audit-${index}`, href: `${row.href}&audit=${index}`,
            title: `Live leaf ${index}`,
          }));
          await list.present({...list.model, rows: window.auditLeaves});
        }"""
    )
    page.keyboard.press("Home")
    rows = page.locator("a.lf-others-row")
    expect(rows.first).to_be_focused()
    box = page.locator("lf-leaves-list")
    area = box.bounding_box()
    assert area is not None
    page.mouse.move(area["x"] + 50, area["y"] + 100)
    page.mouse.wheel(0, 700)
    page.wait_for_function("document.querySelector('lf-leaves-list').scrollTop > 500")
    scroll_settled(page, "lf-leaves-list")
    expect(rows.first).to_be_focused()
    reading = rows.nth(15).bounding_box()
    assert reading is not None
    page.evaluate(
        """async () => {
          const list = document.querySelector('lf-leaves-list');
          await list.present({...list.model, rows: window.auditLeaves.slice(1)});
        }"""
    )
    expect(rows.first).to_be_focused()
    after = rows.nth(14).bounding_box()
    assert after is not None
    assert abs(after["y"] - reading["y"]) <= 1


def test_a_leaves_clock_change_reopens_only_its_same_epoch_presentation(
    browser, serve, other_leaf
):
    """A time-only Leaves repaint repairs presentation at the current epoch."""
    now = datetime.now().astimezone()
    page = browser.new_page()

    def quiet_neighbor(route):
        answer = route.fetch()
        state = answer.json()
        for neighbor in state["others"]:
            activity = neighbor["activity"]
            activity.update(kind="away", dropped=False, ts=now.isoformat())
            activity["counts"]["overdue"] = 1
        route.fulfill(response=answer, json=state)

    # The test's neighbor arrives through the real state boundary. Its clock alone
    # changes afterward; no second runtime reading is mutated beside the publisher.
    page.route("**/api/state*", quiet_neighbor)
    page.goto(serve(LONG_PAGE), wait_until="load")
    wait_until_ready(page)
    told(page, until=lambda state: bool(state["others"]))
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    before = page.evaluate(
        """async () => {
          const presentation = await window.__lfCheckApi();
          const list = document.querySelector('lf-leaves-list');
          const schedule = list.scheduleUpdate.bind(list);
          let release;
          const held = new Promise(resolve => { release = resolve; });
          let armed = true;
          list.scheduleUpdate = () => {
            if (!armed) return schedule();
            armed = false;
            window.leavesClockHeld = true;
            return held.then(schedule);
          };
          window.releaseLeavesClock = release;
          window.leavesPresentation = presentation;
          const reading = presentation.readApplicationPresentation();
          return {
            semanticEpoch: reading.semanticEpoch,
            presentedEpoch: reading.presentedEpoch,
          };
        }"""
    )
    expect(page.locator("a.lf-others-row .lf-others-line")).to_have_text(
        "Quiet (just now)"
    )
    page.unroute("**/api/state*", quiet_neighbor)
    page.route("**/api/state*", refuse)
    page.clock.set_fixed_time(now + timedelta(minutes=1))
    page.wait_for_function("window.leavesClockHeld")
    held = page.evaluate(
        """() => {
          window.leavesReady = false;
          leavesPresentation.whenApplicationPresented().then(() => {
            window.leavesReady = true;
          });
          const reading = leavesPresentation.readApplicationPresentation();
          return {
            pending: reading.pending,
            semanticEpoch: reading.semanticEpoch,
            presentedEpoch: reading.presentedEpoch,
            ready: leavesReady,
          };
        }"""
    )
    assert held == {
        "pending": ["leaves"],
        "semanticEpoch": before["semanticEpoch"],
        "presentedEpoch": before["presentedEpoch"],
        "ready": False,
    }
    page.evaluate("releaseLeavesClock()")
    page.wait_for_function("window.leavesReady")
    expect(page.locator("a.lf-others-row .lf-others-line")).to_have_text(
        "Quiet (1m ago)"
    )
    assert page.evaluate(
        """() => {
          const reading = leavesPresentation.readApplicationPresentation();
          return [reading.semanticEpoch, reading.presentedEpoch];
        }"""
    ) == [before["semanticEpoch"], before["presentedEpoch"]]
