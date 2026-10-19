"""The shortcut bar and bottom status, and the rule that every key a surface names is
one that works."""

import re

import pytest
from interact_support import append_carried_log_record
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import ITEMS_PAGE, live_url
from render_cases_layout import banner_control
from render_cases_navigation import NOTED_PAGE, _publish
from render_harness import (
    INLINE_PAGE,
    LONG_PAGE,
    RELEASE_FOCUS,
    leaf_page,
    open_page,
    open_versions,
    page_comment,
    resized,
    shortcut_bar_text,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

from browser.navigation import (
    EXPANDED,
    KEY_LINE_HINTS,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_item_walk_position_shares_the_shortcut_line(browser, serve):
    """Navigation state keeps one quiet place while its destination and face change."""
    page = open_page(browser, serve(ITEMS_PAGE))
    resized(page, 390, 780)
    position = page.locator(".lf-walk-position")
    expect(position).to_be_hidden()
    expect(page.locator(".lf-banner-menu > .lf-queue")).to_have_count(1)

    page.keyboard.press("m")
    expect(position).to_have_text("1 of 4 waiting on me · Options")
    expect(position).to_be_visible()
    resized(page, 1200, 780)
    expect(position).to_be_visible()
    geometry = page.evaluate(
        """() => {
          const box = (selector) => document.querySelector(selector).getBoundingClientRect();
          const position = box('.lf-walk-position');
          const status = box('.lf-bottom-status');
          const line = box('.lf-shortcut-bar');
          const positionStyle = getComputedStyle(
            document.querySelector('.lf-walk-position'));
          const statusStyle = getComputedStyle(document.querySelector('.lf-bottom-status'));
          const lineStyle = getComputedStyle(document.querySelector('.lf-shortcut-bar'));
          const banner = box('.lf-banner');
          return {position: {left: position.left, right: position.right,
                             top: position.top, bottom: position.bottom},
                  status: {left: status.left, right: status.right,
                           top: status.top, bottom: status.bottom},
                  line: {left: line.left, right: line.right,
                         top: line.top, bottom: line.bottom},
                  banner: {bottom: banner.bottom},
                  first: document.querySelector('.lf-shortcut-bar').firstElementChild
                    .className,
                  parent: document.querySelector('.lf-walk-position').parentElement
                    .className,
                  face: {background: statusStyle.backgroundColor,
                         lineBackground: lineStyle.backgroundColor,
                         border: statusStyle.borderTopWidth,
                         positionBackground: positionStyle.backgroundColor,
                         positionBorder: positionStyle.borderTopWidth,
                         shadow: statusStyle.boxShadow},
                  font: {line: parseFloat(lineStyle.fontSize),
                         position: parseFloat(positionStyle.fontSize)},
                  userSelect: positionStyle.userSelect};
        }"""
    )
    assert "lf-walk-position" not in geometry["first"], geometry
    assert "lf-bottom-status" in geometry["parent"], geometry
    # The status is a chip standing in the bottom bar's row, at its far end.
    assert geometry["status"]["right"] == 1182, geometry
    assert geometry["line"]["top"] < geometry["status"]["top"], geometry
    assert geometry["status"]["bottom"] < geometry["line"]["bottom"], geometry
    assert (
        abs(
            (geometry["status"]["top"] - geometry["line"]["top"])
            - (geometry["line"]["bottom"] - geometry["status"]["bottom"])
        )
        <= 1
    ), geometry
    assert geometry["font"]["position"] == geometry["font"]["line"], geometry
    assert geometry["face"]["border"] == "1px", geometry
    assert geometry["face"]["positionBackground"] == "rgba(0, 0, 0, 0)", geometry
    assert geometry["face"]["positionBorder"] == "0px", geometry
    assert geometry["face"]["shadow"] == "none", geometry
    assert geometry["userSelect"] == "none", geometry

    for index in range(2, 5):
        page.keyboard.press("m")
        # Each stop says its widget's own word, such as Options or Rewrite.
        expect(position).to_have_text(
            re.compile(rf"^{index} of 4 waiting on me · \w+$")
        )
    expect(position).not_to_have_attribute("data-lf-boundary", "")
    status = page.locator(".lf-bottom-status")
    ordinary = status.evaluate("node => getComputedStyle(node).color")
    page.keyboard.press("m")
    expect(position).to_have_text("1 of 4 waiting on me · Options")
    expect(position).to_have_attribute("data-lf-boundary", "")
    assert (
        status.evaluate("node => node.getBoundingClientRect().left")
        == geometry["status"]["left"]
    )
    # Coming round the end of the walk is news, ink where the resting line is muted.
    assert status.evaluate("node => getComputedStyle(node).color") != ordinary
    assert (
        position.evaluate("node => getComputedStyle(node).backgroundColor")
        == geometry["face"]["positionBackground"]
    )
    expect(position).not_to_have_attribute("data-lf-boundary", "")

    page.locator("#h").click()
    expect(position).to_be_hidden()


def test_user_news_interrupts_and_then_restores_background_news(browser, serve):
    """The queue is local state; its complete Lit surface stays synchronous and retained."""
    page = open_page(browser, serve(NOTED_PAGE))
    page.locator(".lf-threads-toggle").focus()
    page.evaluate(
        """async () => {
          window.__lfStatusNodes = Object.fromEntries([
            '.lf-go-to-status',
            '.lf-walk-position',
            '.lf-notice',
            '.lf-live',
          ].map(selector => [selector, document.querySelector(selector)]));
          window.__lfNoticeFocus = document.activeElement;
          window.__lfLiveChanges = [];
          new MutationObserver(() => {
            const words = document.querySelector('.lf-live').textContent;
            if (words) window.__lfLiveChanges.push(words);
          }).observe(document.querySelector('.lf-live'), {
            childList: true,
            subtree: true,
          });
          const {notice} = await window.__lfWidgetApi();
          addEventListener('lf-test-notice', () => {
            notice('Agent replied — open Threads', {background: true});
            const shown = document.querySelector('.lf-notice');
            window.__lfSynchronousNotice = {
              message: shown.textContent,
              visible: shown.classList.contains('show'),
            };
          }, {once: true});
          dispatchEvent(new Event('lf-test-notice'));
        }"""
    )
    live = page.locator(".lf-live")
    notice = page.locator(".lf-notice")
    assert page.evaluate("() => window.__lfSynchronousNotice") == {
        "message": "Agent replied — open Threads",
        "visible": True,
    }
    expect(live).to_have_text("Agent replied — open Threads")
    expect(notice).to_have_text("Agent replied — open Threads")
    rendered(page)
    assert page.evaluate(
        """() => Object.entries(window.__lfStatusNodes).every(
          ([selector, node]) => document.querySelector(selector) === node
        )"""
    ), "a shared repaint replaced part of the retained bottom status surface"

    page.evaluate("async () => (await window.__lfWidgetApi()).notice('Saved — sent')")
    expect(live).to_have_text("Saved — sent")
    expect(notice).to_have_text("Saved — sent")
    expect(notice).to_have_text("Agent replied — open Threads")
    assert (
        page.evaluate(
            "() => window.__lfLiveChanges.filter("
            "words => words === 'Agent replied — open Threads').length"
        )
        == 1
    ), "restoring background news announced it again"
    page.keyboard.press("g")
    expect(notice).to_be_hidden()
    assert page.evaluate(
        """() => Object.entries(window.__lfStatusNodes).every(
          ([selector, node]) => document.querySelector(selector) === node
        ) && document.activeElement === window.__lfNoticeFocus"""
    ), "notice transitions replaced retained status or live-region nodes"


def test_overlapping_identical_live_announcements_are_fresh_changes(browser, serve):
    """Even overlapping identical words give the polite region two arrivals."""
    page = open_page(browser, serve(NOTED_PAGE))
    page.locator(".lf-threads-toggle").focus()
    page.evaluate(
        """async () => {
          window.__lfLiveNode = document.querySelector('.lf-live');
          window.__lfLiveFocus = document.activeElement;
          window.__lfRepeatedAnnouncements = [];
          new MutationObserver(() => {
            const words = document.querySelector('.lf-live').textContent;
            if (words) window.__lfRepeatedAnnouncements.push(words);
          }).observe(document.querySelector('.lf-live'), {
            childList: true,
            subtree: true,
          });
          const {announce} = await window.__lfWidgetApi();
          announce('Same update');
          announce('Same update');
        }"""
    )
    page.wait_for_function(
        "() => window.__lfRepeatedAnnouncements.filter("
        "words => words === 'Same update').length === 2"
    )
    assert page.evaluate(
        """() => document.querySelector('.lf-live') === window.__lfLiveNode
          && document.activeElement === window.__lfLiveFocus"""
    )


def test_no_two_hints_on_the_key_line_say_the_same_word(browser, serve):
    """The line is a row of words with keycaps over them, and the word is what is read.

    Two rows sharing one leaves the keycaps to carry the whole difference, which is the
    line failing at the one thing it is for. The versions menu once called both Tab
    directions "leave versions"; both its doors out now decline the compact line, so what
    it prints is its two unfamiliar actions — the marking walk and exact numbered travel.
    The page's `c` says "comment on the page", distinct from the t/T thread walk.

    Both scenes are read, and each is asserted to hold the rows at issue first: a line
    that had stopped showing them would report a clean result about a page the user
    never sees. The words are the register's, which is where the fix goes — the line
    prints what the rows say, and inventing a difference here would be this projection
    disagreeing with the reference and the announcements.
    """
    url = serve(LONG_PAGE, comments=2)
    _publish(serve.page_dir, 2, LONG_PAGE, "two")
    page = open_page(browser, url)

    # The expanded bar, because the ordinary shortlist shows the first live row and little
    # else: what this is about is two words a user can see at one time, and the expanded
    # bar is where the page's own scene is all of it.
    page.keyboard.press("?")
    rendered(page)
    at_rest = page.evaluate(KEY_LINE_HINTS)
    assert {"comment.create", "thread.next thread.previous"} <= {
        hint["commands"] for hint in at_rest
    }, f"the line no longer offers both the comments and the thread walk: {at_rest}"

    # Neither door out takes the line: the return frame and the menu's own close both
    # decline promotion, so the shortlist is the walk beside exact numbered travel.
    page.keyboard.press("Escape")
    open_versions(page)
    rendered(page)
    versions = page.evaluate(KEY_LINE_HINTS)
    assert {"version.later version.earlier", "version.open-v1 version.open-v2"} <= {
        hint["commands"] for hint in versions
    }, f"the versions menu no longer offers its two unfamiliar actions: {versions}"

    for scene, hints in (("the page", at_rest), ("the versions menu", versions)):
        said = {}
        for hint in hints:
            said.setdefault(hint["word"], []).append(hint["commands"])
        twice = {word: rows for word, rows in said.items() if len(rows) > 1}
        assert not twice, (
            f"on {scene} the shortcut bar says one word for two capabilities, so the "
            f"keycaps are the whole difference: {twice}"
        )


def test_registered_shortcuts_are_exposed_to_assistive_technology(browser, serve):
    """The same declarations that paint help expose their active keys through ARIA."""
    page = open_page(browser, serve(ITEMS_PAGE))

    expect(page.get_by_role("button", name="? more", exact=True)).to_have_attribute(
        "aria-keyshortcuts", "?"
    )
    # The page's box joins its card at the card's first open.
    expect(page_comment(page)).to_have_attribute(
        "aria-keyshortcuts", "Enter Meta+Enter Control+Enter"
    )
    page.keyboard.press("Escape")
    expect(page.locator("#live-question .lf-another leaf-text")).to_have_attribute(
        "aria-keyshortcuts", "Enter Meta+Enter Control+Enter"
    )
    assert page.locator(".lf-version-menu").get_attribute("aria-keyshortcuts") is None

    page.keyboard.press("m")
    mark = page.locator("#live-question .lf-pick").first
    expect(mark).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown Home End Space 1"
    )

    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(mark).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown Home End Space"
    )
    expect(
        page.locator(
            ".lf-command-reference tr",
            has_text="Next item waiting on me",
        ).locator("kbd")
    ).to_have_text("m")
    expect(
        page.locator(
            ".lf-command-reference tr",
            has_text="Previous item waiting on me",
        ).locator("kbd")
    ).to_have_text("M")
    page.keyboard.press("Escape")

    assert page.locator(".lf-queue").get_attribute("aria-keyshortcuts") is None
    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown Home End"
    )
    expect(page.locator(".lf-queue-row").first).to_have_attribute(
        "aria-keyshortcuts", "Enter Space"
    )
    page.keyboard.press("Escape")

    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.get_by_role("button", name="Back to more shortcuts")).to_have_attribute(
        "aria-keyshortcuts", "Escape"
    )
    page.keyboard.press("Escape")


def test_the_key_line_says_what_a_press_will_do(browser, serve):
    """The shortcut bar and dispatcher read one return frame for each keyboard entry."""
    url = serve(NOTED_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "One thread.",
            "anchor": {"quote": "first passage"},
        },
    )
    page = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")
    line = page.locator(".lf-shortcut-bar")

    # Page scope: the permanent verbs, thread rows only over threads, and no esc
    # chip — there is nothing to back out of.
    expect(line).to_contain_text("threads")
    expect(line).to_contain_text("more")
    expect(line.locator("kbd").filter(has_text=re.compile(r"^esc$"))).to_have_count(0)

    # Armed with the panel closed: the direct panel destination and its way out are visible.
    page.keyboard.press("g")
    expect(line).to_contain_text("Threads panel")
    expect(line).to_contain_text("cancel")
    page.keyboard.press("Escape")
    expect(line).not_to_contain_text("Threads panel")
    # The blue prefix is gone with the sequence; the ordinary line may reuse the same words.
    expect(
        page.locator('.lf-shortcut-bar kbd[data-lf-sequence-step-state="pressed"]')
    ).to_have_count(0)

    # c is comment everywhere. From the page it opens the banner's page comment card and
    # stands the user in its box, so one press comes back out: the card goes, and the
    # user stands on the control it hangs from, as after a press on it, and one more
    # lets go of the banner.
    page.keyboard.press("c")
    expect(page.locator(".lf-page-comment-card leaf-text")).to_be_focused()
    expect(line).to_contain_text("send")
    # A send key on an empty box is answered to a listener, not swallowed — silence
    # reads as a send that happened. The empty box shows it to anyone who sees it.
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-live")).to_contain_text("Nothing to send")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-page-comment-card")).to_be_hidden()
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    expect(page.locator(".lf-banner-actions > .lf-page-comment")).to_be_focused()
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")

    # g T is navigation to Threads. Its one completed sequence enters one surface, and one
    # Escape restores the page instead of stranding focus on the panel toggle.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(f"{EXPANDED} > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("?")
    page.keyboard.press("?")
    help_el = page.locator(".lf-command-reference")
    expect(help_el).to_be_visible()
    way_back = help_el.locator('tr[data-lf-command="navigation.back"]')
    expect(way_back).to_have_count(1)
    expect(way_back).to_contain_text("Close the thread panel")
    expect(
        help_el.get_by_role(
            "heading", name="In the covering auxiliary surface", exact=True
        )
    ).to_have_count(0)
    expect(help_el.locator('tr[data-lf-command="navigation.release"]')).to_have_count(0)
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(f"{EXPANDED} > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")

    # t opens the inline thread, whose way out is the element it is about.
    # Every rung earns a press here because Esc is the only keyboard collapse.
    card_thread = page.locator(".lf-margin-preview .lf-page-thread")
    page.keyboard.press("t")
    expect(card_thread).to_be_focused()
    expect(line).to_contain_text("back to element")
    # The global reference is a modal over everything; the card is where the user
    # stands rather than a layer of its own, so it waits under the modal, the reference
    # names its way out among the scene's, and the user comes back to it.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    way_out = help_el.locator('tr[data-lf-command="margin.back"]')
    expect(way_out).to_contain_text("page element this thread is about")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()
    expect(card_thread).to_be_focused()
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/interaction")
            and response.ok
            and any(
                row.get("type") == "command" and row["id"] == "margin.back"
                for row in response.request.post_data_json["entries"]
            )
        )
    ) as recorded:
        page.keyboard.press("Escape")
    command = next(
        row
        for row in recorded.value.request.post_data_json["entries"]
        if row.get("type") == "command" and row["id"] == "margin.back"
    )
    assert command["title"] == "back to element"
    assert command["description"] == "Return to the page element this thread is about"
    assert command["focus"]["target"] == "div"
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(page.locator(".lf-thread-panel")).to_be_hidden()

    # And a comment note. It is apparatus standing at the block it counts rather than a
    # destination, so the ladder's foot backs out of it onto the page and the standing
    # scope, which lets go of a destination, does not stand: the reference names that
    # one press rather than listing every step whose own condition is true.
    page.locator(".lf-mark-note").focus()
    expect(page.locator(".lf-mark-note")).to_be_focused()
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    backing_out = help_el.locator('tr[data-lf-command="navigation.back"]')
    expect(backing_out).to_have_count(1)
    expect(backing_out).to_contain_text("Back out onto the page")
    expect(help_el.locator('tr[data-lf-command="navigation.release"]')).to_have_count(0)


def test_a_key_the_runtime_binds_is_a_key_some_surface_names(browser, serve):
    """One declaration per binding, and every surface is a projection of it. The d/u
    reading-page pair is the case that named this: a runtime key must be visible wherever
    the keyboard vocabulary is projected.

    Where it is projected is the expanded bar and the reference, not the resting line, which
    holds two chips and spends neither on scrolling. So the line is asked for the row it
    holds rather than the row it paints, and the reference below is read for the words —
    a key named on no surface at all is what this refuses.

    It is refused now, where a scope is declared, so the next binding written without a
    word fails on the page that introduces it rather than going quiet on every page after
    it. A row that presses nothing needs none — F7 is the browser's caret browsing, real
    and worth knowing and not what the next press does."""
    page = open_page(browser, serve(NOTED_PAGE))
    line = page.locator(".lf-shortcut-bar")
    movement = line.locator('.lf-shortcut[data-lf-command-ids~="page.down"]')
    expect(movement).to_have_count(1)
    expect(movement).to_have_attribute(
        "data-lf-command-ids", re.compile(r"\bpage\.up\b")
    )
    expect(movement.locator("kbd")).to_have_text("d / u")
    expect(movement).to_contain_text("page down / up")
    # Declared and worded, and painted where the user asks rather than on the resting
    # glance. The reference below is the surface that names it, and this is the pair of
    # counts that tells a row the line declined to paint from a row that says nothing.
    expect(
        line.locator(
            '.lf-shortcut:not([data-lf-off-line])[data-lf-command-ids~="page.down"]'
        )
    ).to_have_count(0)
    resized(page, 420, 800)
    compact = line.evaluate(
        """node => {
          const visible = [...node.querySelectorAll(".lf-shortcut, .lf-shortcut-more")]
            .filter(el => el.checkVisibility({visibilityProperty: true}));
          const tops = [];
          const tolerance = Math.min(...visible.map(el => el.offsetHeight)) / 2;
          for (const el of visible)
            if (tops.every(top => Math.abs(top - el.getBoundingClientRect().top) > tolerance))
              tops.push(el.getBoundingClientRect().top);
          return {
            rows: tops.length,
            clientWidth: node.clientWidth,
            scrollWidth: node.scrollWidth,
            clientHeight: node.clientHeight,
            scrollHeight: node.scrollHeight,
          };
        }"""
    )
    assert compact["rows"] == 1, compact
    assert compact["scrollWidth"] <= compact["clientWidth"], compact
    assert compact["scrollHeight"] <= compact["clientHeight"], compact

    # Linux's wider system face leaves little room on this line at the smallest supported
    # window, and the disclosure is the one control on it: whatever the face costs, the
    # hints leave before More does, and the line stays inside its own box rather than
    # clipping the way out of itself.
    resized(page, 320, 800)
    rendered(page)
    smallest = line.evaluate(
        """node => {
          const more = node.querySelector('.lf-shortcut-more');
          return {
            moreShown: more.checkVisibility(),
            clientWidth: node.clientWidth,
            scrollWidth: node.scrollWidth,
            clientHeight: node.clientHeight,
            scrollHeight: node.scrollHeight,
          };
        }"""
    )
    assert smallest["moreShown"], smallest
    assert smallest["scrollWidth"] <= smallest["clientWidth"], smallest
    assert smallest["scrollHeight"] <= smallest["clientHeight"], smallest
    resized(page, 1280, 800)
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_contain_text(
        "Move 60% of a page down"
    )
    expect(page.locator(".lf-command-reference")).to_contain_text(
        "Move 60% of a page up"
    )
    expect(page.locator(".lf-command-reference")).to_contain_text("Caret browsing")
    page.keyboard.press("Escape")
    expect(line).not_to_contain_text("F7")

    refused = page.evaluate(
        """async () => {
          const { commands } = await window.__lfWidgetApi();
          try {
            commands(document.body, 'A project scope', [
              { id: 'test.no-line', keys: ['F2'],
                run: () => {} },
            ]);
            return 'declared';
          } catch (e) {
            return e.message;
          }
        }"""
    )
    assert "title" in refused, refused

    # The other half of what this gate is for, and the quieter failure. `answers` asks
    # after Mod, Alt and Shift by name and reads every other prefix as absent, so a
    # binding written `Ctrl+k` is not a key that never fires — it is `k`, which fires on
    # a bare press while both surfaces spell the chip "Ctrl+k" and the press the chip
    # names does nothing. A declaration that means a different key than it says is the
    # one thing no surface can project, so it is refused where declarations enter.
    modified = page.evaluate(
        """async () => {
          const { commands } = await window.__lfWidgetApi();
          try {
            commands(document.body, 'A project scope', [
              { id: 'test.bad-modifier', keys: ['Ctrl+k'],
                title: 'a modifier the matcher never asks about',
                line: 'a key that is really just k', run: () => {} },
            ]);
            return 'declared';
          } catch (e) {
            return e.message;
          }
        }"""
    )
    assert "Ctrl is no modifier" in modified, modified
    assert "Mod, Alt, Shift" in modified, modified

    # Routes split one compact row into separately addressable commands. Every declared
    # binding therefore needs exactly one route: otherwise dispatch can gain a press that
    # both the reference and shortcut bar omit from their shared presentation projection.
    routed = page.evaluate(
        """async () => {
          const { commands } = await window.__lfWidgetApi();
          const declare = row => {
            try {
              commands(document.body, 'A routed project scope', [row]);
              return 'declared';
            } catch (e) {
              return e.message;
            }
          };
          return {
            missing: declare({
              id: 'test.missing-route', keys: ['F2', 'F3'],
              title: 'Move either way', line: 'move either way', run: () => {},
              routes: [{
                id: 'test.missing-route.first', binding: 'F2',
                title: 'Move one way', line: 'move one way',
              }],
            }),
            duplicate: declare({
              id: 'test.duplicate-route', keys: ['F4'],
              title: 'Move once', line: 'move once', run: () => {},
              routes: [
                {
                  id: 'test.duplicate-route.first', binding: 'F4',
                  title: 'Move first', line: 'move first',
                },
                {
                  id: 'test.duplicate-route.second', binding: 'F4',
                  title: 'Move second', line: 'move second',
                },
              ],
            }),
          };
        }"""
    )
    assert "has no route for F3" in routed["missing"], routed
    assert "routes F4 twice" in routed["duplicate"], routed

    # A registered result may deliberately precede the platform's own half of a press.
    # It still enters through the same register — and therefore the same surfaces and
    # scoping — but the dispatcher must not cancel that native result. The versions menu
    # uses this for the Tab that closes it before the browser moves focus past its door.
    native = page.evaluate(
        """async () => {
          const { commands } = await window.__lfWidgetApi();
          const owner = document.createElement('div');
          owner.tabIndex = -1;
          document.body.append(owner);
          owner.focus();
          let ran = 0;
          commands(owner, 'A native companion', [
            { id: 'test.native-companion', keys: ['F2'],
              title: 'Run before the browser', line: 'run first',
              native: true, run: () => ran++ },
          ]);
          const event = new KeyboardEvent(
            'keydown', {key: 'F2', bubbles: true, cancelable: true}
          );
          owner.dispatchEvent(event);
          owner.remove();
          return {ran, prevented: event.defaultPrevented};
        }"""
    )
    assert native == {"ran": 1, "prevented": False}, native


def test_the_key_line_keeps_local_and_page_hints_and_progressively_reveals_the_rest(
    browser, serve
):
    """The short line is a glance, not the command reference. It keeps the first
    innermost live action and the way out when the current scene has one. One `? more`
    expands the shortcut bar to a bounded set of current commands; `? command reference` then opens the
    complete searchable register.

    The open panel is the causal contrast for the cap. A full page row crosses into the
    panel and paints over its foot; the bounded shortlist ends before it. The overlap is
    tested before opening the reference so a searchable popup cannot make the symptom
    disappear merely by covering both surfaces."""
    page = open_page(browser, serve(NOTED_PAGE, comments=2))
    page.set_viewport_size({"width": 1200, "height": 800})
    page.locator(".lf-threads-toggle").click()

    line = page.locator(".lf-shortcut-bar")
    visible_hints = line.locator(".lf-shortcut:not([data-lf-off-line])")
    assert visible_hints.count() == 2, page.evaluate(
        """() => { const line = document.querySelector('.lf-shortcut-bar'); return {
          client: line.clientWidth, scroll: line.scrollWidth,
          max: getComputedStyle(line).maxWidth,
          hints: [...line.querySelectorAll('.lf-shortcut')].map(el => ({
            text: el.textContent, off: el.hasAttribute('data-lf-off-line')
          }))
        }; }"""
    )
    assert not page.evaluate(
        """() => {
          const a = document.querySelector('.lf-shortcut-bar').getBoundingClientRect();
          const b = document.querySelector('.lf-thread-panel').getBoundingClientRect();
          return a.left < b.right && a.right > b.left &&
                 a.top < b.bottom && a.bottom > b.top;
        }"""
    ), "the shortcut bar crosses into the thread panel"

    # Moving into the box changes both contextual hints without introducing a second
    # shortlist: the same scope order the dispatcher uses supplies them, so what the line
    # says is what the innermost live scope answers and not a list kept beside it.
    #
    # Stand in the list directly, which hands focus to the thread it shows open: the
    # banner button that opened the panel is chrome, and its `c` meaning is deliberately
    # outside this key-line projection test.
    page.locator(".lf-threads").focus()
    expect(page.locator(f"{EXPANDED} > .lf-thread-summary")).to_be_focused()
    expect(visible_hints.nth(0)).not_to_contain_text("send")
    reply = page.locator(f"{EXPANDED} .lf-thread-reply leaf-text")
    reply.focus()
    expect(visible_hints).to_have_count(2)
    expect(visible_hints.nth(0)).to_contain_text("edit last message")
    write(reply, "A reply in progress.")
    expect(visible_hints.nth(0)).to_contain_text("send")
    expect(visible_hints.nth(1)).to_contain_text("back to thread")

    # The line shows only what works from where the user is. This text box owns `?`, so
    # More stands down with its key rather than showing bare; it returns, key and all,
    # when the user steps back out to the thread it was replying in.
    more_node = page.locator(".lf-shortcut-more")
    more_node.evaluate("button => window.__lfShortcutMore = button")
    expect(more_node).to_be_hidden()
    page.keyboard.press("Escape")
    expect(page.locator(f"{EXPANDED} > .lf-thread-summary")).to_be_focused()
    more = page.get_by_role("button", name="? more", exact=True)
    expect(more).to_have_attribute("aria-expanded", "false")
    expect(more).to_have_attribute("aria-keyshortcuts", "?")
    # By its key, so the user stays on the thread: a panel that covers the page takes
    # focus into itself, and a press on More would leave the line a different scene to
    # come back to.
    page.keyboard.press("?")
    help_el = page.locator(".lf-command-reference")
    search = page.get_by_role("combobox", name="Search commands")
    expect(help_el).to_be_hidden()
    expect(line).to_have_attribute("data-lf-expanded", "true")
    expect(page.locator(".lf-live")).to_contain_text(
        "Shortcut bar expanded. Press question mark again for Command reference"
    )
    assert visible_hints.count() > 2
    wide_hint_count = visible_hints.count()
    expect(line).to_contain_text("less")
    for width in (1200, 420):
        page.set_viewport_size({"width": width, "height": 800})
        rendered(page)
        assert more_node.evaluate("button => button === window.__lfShortcutMore")
        geometry = line.evaluate(
            """node => {
              const visible = [...node.querySelectorAll(".lf-shortcut, .lf-shortcut-more")]
                .filter(el => el.checkVisibility({visibilityProperty: true}));
              const boxes = visible.map(el => el.getBoundingClientRect());
              const tolerance = Math.min(...visible.map(el => el.offsetHeight)) / 2;
              const rows = [];
              for (const el of visible)
                if (rows.every(top => Math.abs(top - el.getBoundingClientRect().top) > tolerance))
                  rows.push(el.getBoundingClientRect().top);
              return {
                rows: rows.length,
                clientWidth: node.clientWidth,
                scrollWidth: node.scrollWidth,
                clientHeight: node.clientHeight,
                scrollHeight: node.scrollHeight,
                bandHeight: Math.max(...boxes.map(box => box.bottom))
                          - Math.min(...boxes.map(box => box.top)),
                maxItemHeight: Math.max(...boxes.map(box => box.height)),
              };
            }"""
        )
        assert geometry["rows"] <= 2, geometry
        assert geometry["scrollWidth"] <= geometry["clientWidth"], geometry
        assert geometry["scrollHeight"] <= geometry["clientHeight"], geometry
        assert geometry["bandHeight"] <= geometry["maxItemHeight"] * 2 + 8, geometry
    page.set_viewport_size({"width": 1200, "height": 800})
    rendered(page)
    expect(visible_hints).to_have_count(wide_hint_count)
    assert more_node.evaluate("button => button === window.__lfShortcutMore")
    more = page.get_by_role("button", name="? command reference", exact=True)
    expect(more).to_have_attribute("aria-expanded", "true")
    more.click()
    expect(help_el).to_be_visible()
    expect(search).to_be_focused()
    expect(page.get_by_role("button", name="Back to more shortcuts")).to_be_visible()
    expect(help_el).not_to_contain_text("With more keyboard shortcuts")

    search.fill("Align current item at top")
    visible_commands = help_el.locator("tr[data-lf-command]:not([hidden])")
    expect(visible_commands).to_have_count(1)
    expect(visible_commands.first).to_contain_text("Align current item at top")

    search.fill("thread panel")
    expect(
        help_el.get_by_role("heading", name="In the thread panel", exact=True)
    ).to_be_visible()
    expect(visible_commands).not_to_have_count(0)

    search.fill("no such shortcut")
    expect(help_el.locator(".lf-command-reference-empty")).to_be_visible()
    expect(visible_commands).to_have_count(0)
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()
    expect(line).to_have_attribute("data-lf-expanded", "true")
    expect(
        page.get_by_role("button", name="? command reference", exact=True)
    ).to_be_focused()
    page.keyboard.press("Escape")
    expect(line).to_have_attribute("data-lf-expanded", "false")
    expect(page.locator(".lf-live")).to_contain_text("Shortcut bar collapsed")
    expect(page.get_by_role("button", name="? more", exact=True)).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(visible_hints).to_have_count(2)


@pytest.mark.watch_shifts
def test_expanded_shortcuts_fit_their_region_with_larger_text(browser, serve):
    source = leaf_page(
        "Larger shortcut text",
        '<h1 id="title">Keep every shortcut readable</h1><p id="words">Words.</p>',
        head="<style>:root { --t-6: 18px; }</style>",
    )
    page = open_page(browser, serve(source))
    page.keyboard.press("?")
    line = page.locator(".lf-shortcut-bar")
    expect(line).to_have_attribute("data-lf-expanded", "true")
    counts = []
    for width in (1200, 390, 320, 1200):
        resized(page, width, 800)
        rendered(page)
        expect(
            page.get_by_role("button", name="? command reference", exact=True)
        ).to_be_visible()
        hints = line.locator(".lf-shortcut:not([data-lf-off-line])")
        expect(hints.filter(has_text="less")).to_have_count(1)
        counts.append(hints.count())
        reading = line.evaluate(
            """bar => {
              const region = bar.getBoundingClientRect();
              const visible = [...bar.querySelectorAll('.lf-shortcut:not([data-lf-off-line]), .lf-shortcut-more')];
              return {region: {left: region.left, right: region.right},
                hints: visible.map(node => {
                  const box = node.getBoundingClientRect();
                  return {text: node.textContent, left: box.left, right: box.right};
                })};
            }"""
        )
        assert reading["hints"], reading
        for hint in reading["hints"]:
            assert hint["left"] >= reading["region"]["left"] - 0.5, reading
            assert hint["right"] <= reading["region"]["right"] + 0.5, reading
    assert counts[0] > counts[1] >= 1, counts
    assert counts[-1] == counts[0], counts


def test_the_resting_key_line_leads_from_the_page_to_target_selection(browser, serve):
    """The sentence a user reads before they have pressed anything.

    Comment opens its box; selection first opens the picker. Whole-page search and page
    movement remain in the complete reference.

    Read off `:not([hidden])`, because renderShortcutBar leaves every live row in the DOM and
    hides the ones it will not paint: `to_contain_text` on the line answers about the
    register and would pass over a chip nobody can see."""
    page = open_page(browser, serve(NOTED_PAGE))
    line = page.locator(".lf-shortcut-bar")
    shown = line.locator(".lf-shortcut:not([data-lf-off-line])")
    expect(shown).to_have_count(2)
    expect(page.get_by_role("button", name="? more", exact=True)).to_be_visible()
    # One settled read, which pins the count, the order, the keys and the words together.
    assert (
        shortcut_bar_text(page) == "c\ncomment on the page\ns\nselect element\n?\nmore"
    ), shortcut_bar_text(page)

    # Search and page movement are still declared but off the glance nobody asked for.
    # React has no row at all until a target makes that capability live.
    for command in ("page.search.open", "page.down"):
        expect(
            line.locator(f'.lf-shortcut[data-lf-command-ids~="{command}"]')
        ).to_have_count(1)
        expect(
            line.locator(
                f'.lf-shortcut:not([data-lf-off-line])[data-lf-command-ids~="{command}"]'
            )
        ).to_have_count(0)
    expect(line.locator('[data-lf-command-ids~="reaction.open"]')).to_have_count(0)

    # And named in full by the reference, which lists every live capability rather than
    # the ones the current width has room for.
    page.keyboard.press("?")
    page.keyboard.press("?")
    help_el = page.locator(".lf-command-reference")
    expect(help_el).to_be_visible()
    expect(help_el).to_contain_text("Search all the text on the page")
    # Read the capability by the command the reference lists it under. Its words belong
    # to `target.picker.open` and are read once, in `test_render_semantic_selection.py`;
    # a second copy here only drifts. Both cases are in the `main` tier, so neither
    # holds those words before it lands.
    expect(help_el.locator('tr[data-lf-command="target.picker.open"]')).to_have_count(1)
    expect(help_el).not_to_contain_text("Open reactions")
    expect(help_el).to_contain_text("Move 60% of a page down")
    expect(help_el).to_contain_text("Move 60% of a page up")


def test_a_coarse_pointer_keeps_useful_status_without_keyboard_hints(browser, serve):
    """A phone drops key hints but keeps active navigation status."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, serve(ITEMS_PAGE), context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches"), (
        "the touch fixture never reached Leaf's coarse-pointer rules"
    )
    expect(page.locator(".lf-shortcut-bar")).to_be_hidden()
    room = page.evaluate(
        """() => {
              const line = document.querySelector('.lf-shortcut-bar');
              return {
                display: getComputedStyle(line).display,
                height: line.getBoundingClientRect().height,
                reserved: getComputedStyle(document.body).paddingBottom,
                moreShown: document.querySelector('.lf-shortcut-more').checkVisibility(),
              };
            }"""
    )
    assert room == {
        "display": "none",
        "height": 0,
        "reserved": "0px",
        "moreShown": False,
    }, room

    page.evaluate(
        """async () => {
              (await window.__lfWidgetApi()).notice('Saved — sent');
              dispatchEvent(new Event('resize'));
            }"""
    )
    expect(page.locator(".lf-banner-status .lf-status-notice")).to_have_text(
        "Saved — sent"
    )
    expect(page.locator(".lf-banner-status .lf-status-notice")).to_be_visible()
    assert (
        page.evaluate("() => getComputedStyle(document.body).paddingBottom") == "0px"
    ), "a transient notice reserved document space"

    # And the page is still whole underneath. Everything that asks how far down the
    # page reaches asks it of the line's box, and a line with no box answers 0 — the
    # top of the window — which reads as "all of it is covered". Item hints and the
    # search's own highlight are drawn for boxes above that answer, so a tablet got
    # `s` naming nothing and `/` painting no match, with the page itself intact and
    # nothing on screen saying why.
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint").first).to_be_visible()
    page.keyboard.press("Escape")

    page.keyboard.press("m")
    line = page.locator(".lf-shortcut-bar")
    expect(line).to_be_hidden()
    position = page.locator(".lf-walk-position")
    expect(position).to_have_text("1 of 4 waiting on me · Options")
    expect(position).to_be_visible()
    active_room = page.evaluate(
        """() => {
              const chip = document.querySelector('.lf-bottom-status')
                .getBoundingClientRect();
              return {
                height: document.querySelector('.lf-walk-position')
                  .getBoundingClientRect().height,
                top: chip.top, bottom: chip.bottom, viewport: innerHeight,
                reserved: parseFloat(getComputedStyle(document.body).paddingBottom),
              };
            }"""
    )
    # A touch screen draws no band, so the fixed status overlays the page like a
    # passing notice: showing it changes nothing about where the page ends, and the
    # whole chip stands inside the window, clear of its foot.
    assert active_room["height"] > 0, active_room
    assert active_room["reserved"] == 0, active_room
    assert 0 <= active_room["top"], active_room
    assert active_room["bottom"] <= active_room["viewport"] - 14 + 1, active_room

    page.locator("#h").click()
    expect(line).to_be_hidden()
    page.close()
    # The control the reading above needs, because `paddingBottom` computes to "0px"
    # wherever the theme reserves nothing: the same page at the same size under a fine
    # pointer has to reserve a band, or "reserved nothing" and "reserved nowhere" are the
    # same green.
    fine = open_page(browser, serve(NOTED_PAGE))
    resized(fine, 390, 844)
    rendered(fine)
    reserved = fine.evaluate("() => getComputedStyle(document.body).paddingBottom")
    assert reserved != "0px" and float(reserved.removesuffix("px")) > 20, reserved


FOOT_CONTROL_PAGE = NOTED_PAGE.replace(
    "</main>",
    '<div style="height: 2400px"></div>'
    '<lf-ask id="foot-d"><h2 id="foot-h">The last question</h2>'
    '<lf-options id="foot-o" choose>'
    '<lf-option id="foot-keep">Keep it</lf-option>'
    '<lf-option id="foot-change">Change it</lf-option>'
    "</lf-options></lf-ask></main>",
)


# The band the line stands in, and the room the document keeps for it. `footprint` is the
# whole of what the line takes at the foot of the window — its height plus every inset
# holding it off that foot — and `reserved` is the room the theme keeps for it at the
# body's end.
FOOT_ROOM = """() => {
  const line = document.querySelector('.lf-shortcut-bar').getBoundingClientRect();
  const box = document.getElementById('foot-change').getBoundingClientRect();
  const s = document.scrollingElement;
  return {
    atEnd: s.scrollTop + s.clientHeight >= s.scrollHeight - 1,
    lineHeight: line.height,
    footprint: document.documentElement.clientHeight - line.top,
    reserved: parseFloat(getComputedStyle(document.body).paddingBottom),
    clearance: line.top - box.bottom,
  };
}"""


# Where the line's chips are, and where its one real control is. The band is the whole
# fixed box; More is the only part of it that answers a press, so a hit test aimed at the
# page has to be aimed past it. Both are read from the rendered boxes rather than stated,
# because the chips' width is the register's answer for the current scene.
UNDER_THE_LINE = """(id) => {
  const line = document.querySelector('.lf-shortcut-bar').getBoundingClientRect();
  const more = document.querySelector('.lf-shortcut-more').getBoundingClientRect();
  const el = document.getElementById(id);
  const box = el.getBoundingClientRect();
  const left = Math.max(line.left, box.left);
  const right = Math.min(more.left, box.right);
  const x = (left + right) / 2;
  const y = line.top + line.height / 2;
  const at = document.elementFromPoint(x, y);
  return {
    band: right - left,
    covered: Math.min(line.bottom, box.bottom) - Math.max(line.top, box.top),
    reaches: Boolean(at) && (el === at || el.contains(at)),
    hit: at ? at.tagName + "." + (at.className || "") : null,
    aim: {x, y}, line: {left: line.left, top: line.top, bottom: line.bottom},
    more: {left: more.left}, box: {left: box.left, right: box.right,
      top: box.top, bottom: box.bottom},
  };
}"""


def test_the_key_line_stands_in_the_bottom_bar(browser, serve):
    """The line is the bottom bar, fixed at the foot of the window at one stated height,
    so what it owes the page is exactly that band: room of its own where the document
    ends, and no press taken from what it stands over on the way there. The page's own
    foot keeps its air above the band. A covering sheet leaves the band unchanged: its
    growing foreground footer is not geometry owned by the background line.

    The press is the other half. The line and its chips take no pointer events, so a
    control the line stands over on some scroll position is still a control. Its More
    button does take them, and deliberately: it is the only pointer route to the keyboard
    reference. The band is aimed past it here for that reason."""
    page = open_page(browser, serve(FOOT_CONTROL_PAGE))
    control = page.locator("#foot-change")
    expect(control).to_be_visible()

    page.evaluate(
        "() => { const s = document.scrollingElement; s.scrollTo({top: s.scrollHeight}); }"
    )
    rendered(page)
    ended = page.evaluate(FOOT_ROOM)
    assert ended["atEnd"] and ended["lineHeight"] > 0, ended
    # The reservation is the band itself, and the band reaches the window's foot.
    assert ended["reserved"] == pytest.approx(ended["footprint"], abs=1), ended
    assert ended["footprint"] == pytest.approx(ended["lineHeight"], abs=1), ended
    assert ended["clearance"] >= 20, (
        f"the document's last control ends in the shortcut bar's band: {ended}"
    )

    # A covering sheet makes the line inert background. Neither the sheet nor its footer
    # can move the line; the document's existing band remains a reading reservation for
    # the viewport-fixed line when the sheet closes again.
    resized(page, 420, 900)
    page.locator(".lf-threads-toggle").click()
    rendered(page)
    covered = page.evaluate(FOOT_ROOM)
    assert covered["footprint"] == pytest.approx(ended["footprint"], abs=1), (
        f"the covering sheet moved the viewport-fixed line: {ended}, {covered}"
    )
    assert covered["reserved"] == pytest.approx(covered["footprint"], abs=1), (
        f"the document lost the band's fixed reservation: {covered}"
    )
    page.keyboard.press("Escape")

    # And where the user is not at the end, the line is standing over the page. The
    # control keeps the press: the chips are painted, not pressable. Narrow, because that
    # is where the chips and the reading column share room at all — at 1200 the column
    # starts to the right of them and it is More that overhangs its first few pixels.
    resized(page, 520, 800)
    page.evaluate(
        """() => {
          const line = document.querySelector('.lf-shortcut-bar').getBoundingClientRect();
          const box = document.getElementById('foot-change').getBoundingClientRect();
          scrollBy(0, box.top + box.height / 2 - (line.top + line.height / 2));
        }"""
    )
    rendered(page)
    under = page.evaluate(UNDER_THE_LINE, "foot-change")
    assert under["band"] > 8 and under["covered"] > 0, (
        f"the aim never reached page under the line's chips, so it proves nothing: {under}"
    )
    assert under["reaches"], (
        f"the shortcut bar took a press aimed at the control underneath it: {under}"
    )

    # More is the exception, and the one that has to stay: it is the pointer route to the
    # reference. Asked as a press rather than as a declaration, the same way the chips
    # above were.
    expect(page.get_by_role("button", name="? more", exact=True)).to_be_visible()
    assert page.evaluate(
        """() => {
          const more = document.querySelector('.lf-shortcut-more');
          const box = more.getBoundingClientRect();
          const at = document.elementFromPoint(box.left + box.width / 2,
                                               box.top + box.height / 2);
          return more === at || more.contains(at);
        }"""
    ), "the line's own control stopped answering a press"


def test_the_expanded_key_line_stands_down_for_a_page_press_and_another_command(
    browser, serve
):
    """The expanded shortcut bar is transient help, so either kind of onward motion folds it. The
    page-click owner handles presses outside the line, while the dispatcher folds it
    before a registered command runs."""
    page = open_page(browser, serve(NOTED_PAGE))
    line = page.locator(".lf-shortcut-bar")

    page.keyboard.press("?")
    expect(line).to_have_attribute("data-lf-expanded", "true")
    page.locator("#t").click()
    expect(line).to_have_attribute("data-lf-expanded", "false")

    page.keyboard.press("?")
    expect(line).to_have_attribute("data-lf-expanded", "true")
    page.keyboard.press("g")
    expect(line).to_have_attribute("data-lf-expanded", "false")
    expect(
        line.locator('kbd[data-lf-sequence-step-state="pressed"]').first
    ).to_have_text("g")


def test_the_walk_reaches_more_and_goes_on_after_the_line_has_repainted(browser, serve):
    """A frame passes between one Tab and the next for every user, and none for a test.

    `renderShortcutBar` runs under the shared repaint frame, so it repaints the shortcut bar just after
    focus lands somewhere — including on More, the line's own button. Replacing the line's
    children used to take More out of the document, and removing a focused element blurs
    it; it came straight back as the same node, connected, with the user dropped to
    `body`. The button was never gone to look at and never gone from the DOM to assert on,
    so nothing but standing on it one frame later could see it.

    That is why the frame is the whole of this test. Pressed back to back the walk is
    whole, because the repaint has not run yet between the presses — the failure hid
    behind the one habit every browser test has. So each press waits for `rendered`, and the
    contrast is against the same walk pressed fast: they have to agree.

    Reaching More is the claim, and going on past it is the other half — a walk that
    loses focus to `body` does not stop, it silently restarts, and a user tabbing
    through their own page never gets past the banner."""
    page = open_page(browser, serve(NOTED_PAGE, comments=2))
    who = """() => {
      let e = document.activeElement;
      while (e?.shadowRoot?.activeElement) e = e.shadowRoot.activeElement;
      return e === document.body ? 'body' : (e?.className || e?.tagName || 'null');
    }"""

    walks = {}
    for settled in (False, True):
        # Start each walk from the page rather than from the last control in the
        # previous walk. Blurring preserves that control as the sequential focus
        # starting point, which only happened to wrap before the page gained a visual
        # reaction proxy as its first Tab stop.
        page.evaluate(RELEASE_FOCUS)
        trail = []
        for _ in range(24):
            page.keyboard.press("Tab")
            if settled:
                rendered(page)
            trail.append(page.evaluate(who))
        walks["frame" if settled else "fast"] = trail

    # The two walks have to be the same walk. A count of lost stops would need a
    # threshold, and there is no honest one: this page's order is three controls and a
    # wrap, so a `body` every fourth press is the walk working. What says focus was lost
    # is that waiting changed where the presses went.
    assert walks["fast"] == walks["frame"], (
        "a frame between presses changed the tab order:\n"
        f"  fast  {walks['fast']}\n  frame {walks['frame']}"
    )
    for how, trail in walks.items():
        assert any("lf-shortcut-more" in at for at in trail), (
            f"tabbing {how}, the walk never stood on More in 24 presses: {trail}"
        )

    # Standing on More, the repaint must leave the user on it.
    page.evaluate("() => document.activeElement?.blur()")
    for _ in range(24):
        page.keyboard.press("Tab")
        if page.evaluate(
            "() => document.activeElement?.classList?.contains('lf-shortcut-more')"
        ):
            break
    expect(page.locator(".lf-shortcut-more")).to_be_focused()
    rendered(page)
    expect(page.locator(".lf-shortcut-more")).to_be_focused()
    page.evaluate(
        """() => {
          const line = document.querySelector('.lf-shortcut-bar');
          window.__lfRetainedShortcut = line.querySelector('.lf-shortcut:not([data-lf-off-line])');
          window.__lfRetainedShortcutKey = window.__lfRetainedShortcut.querySelector('kbd');
          dispatchEvent(new Event('resize'));
        }"""
    )
    rendered(page)
    assert page.evaluate(
        """() => {
          const line = document.querySelector('.lf-shortcut-bar');
          const shortcut = line.querySelector('.lf-shortcut:not([data-lf-off-line])');
          return shortcut === window.__lfRetainedShortcut &&
            shortcut.querySelector('kbd') === window.__lfRetainedShortcutKey;
        }"""
    ), "an unchanged shortcut repaint replaced its chip or first keycap"


def test_a_page_at_rest_repaints_the_key_line_only_when_the_state_moves(browser, serve):
    """A repaint that schedules the next one is a loop no surface reports.

    `paintCoreControls` runs inside the shared repaint and writes what the More control
    currently says, `aria-expanded` among it. The runtime watches `open` and
    `aria-expanded` over the whole document, because those two attributes are how both
    spellings of a disclosure keep which way they stand, and it repaints the line for
    either. So the paint delivered its own write back to itself and asked for another
    frame, and the page went on repainting for as long as it was open — every browser
    test on every page paying for it, which is where it showed: the complete suite ran
    half again as long and the run went over its bound with a fifth of the tests unread.

    Nothing on screen says so, which is why the reading is the page's own frames at
    rest. A line that keeps repainting while neither the user nor the application
    moves is repainting for a reason the page has not got."""
    page = open_page(browser, serve(NOTED_PAGE, comments=2))
    page.evaluate(
        """() => {
          const probe = { frames: 0, paints: 0 };
          window.__lfProbe = probe;
          new MutationObserver(() => { probe.paints += 1; }).observe(
            document.querySelector(".lf-shortcut-bar"),
            { attributes: true, childList: true, subtree: true },
          );
          const tick = () => { probe.frames += 1; requestAnimationFrame(tick); };
          requestAnimationFrame(tick);
        }"""
    )
    # The window is the page's own frames rather than a duration: a loop of this shape
    # repaints once per frame whatever the machine's speed, so counting frames is what
    # makes the contrast the same size on a loaded runner as on a desk.
    page.wait_for_function("() => window.__lfProbe.frames >= 90")
    probe = page.evaluate("() => window.__lfProbe")

    assert probe["paints"] <= 1, (
        "the shortcut bar repainted without the state moving over "
        f"{probe['frames']} frames: {probe}"
    )


def test_focus_paint_releases_every_text_box_crossed_before_a_frame(browser, serve):
    """A synchronous input sync cannot hide an intermediate focus from repaint."""
    page = open_page(browser, serve(INLINE_PAGE, comments=2))
    # The page's box joins its card at the card's first open, and stays.
    page_comment(page)
    page.keyboard.press("Escape")
    page.locator(".lf-threads-toggle").click()
    general = page.locator(".lf-general leaf-text")
    replies = page.locator(".lf-thread leaf-text")
    assert general.get_attribute("placeholder") == "Comment on the page c"
    page.get_by_role("searchbox", name="Find in threads").focus()
    shortcut_bar_text(page)
    assert general.get_attribute("placeholder") == "Comment on the page"
    page_comment(page)
    shortcut_bar_text(page)
    assert re.search(r"⏎$", general.get_attribute("placeholder"))
    assert general.get_attribute("aria-label") == "Comment on the page"

    # Cross A -> B (and sync B) -> C in one turn, before the coalesced focus paint.
    # Native disclosure makes each reply box reachable only while its own card is open,
    # so the summary clicks are the browser-owned transition between them.
    replies.evaluate_all(
        """boxes => {
          boxes[0].closest('.lf-thread').querySelector(':scope > .lf-thread-summary').click();
          boxes[0].focus();
          boxes[0].dispatchEvent(new Event('input', {bubbles: true}));
          boxes[1].closest('.lf-thread').querySelector(':scope > .lf-thread-summary').click();
          boxes[1].focus();
        }"""
    )
    shortcut_bar_text(page)
    assert general.get_attribute("placeholder") == "Comment on the page"
    assert general.get_attribute("aria-label") == "Comment on the page"
    assert replies.nth(0).get_attribute("placeholder") == "Reply"
    assert replies.nth(0).get_attribute("aria-label") == "Reply"
    assert re.search(r"⏎$", replies.nth(1).get_attribute("placeholder"))
    assert replies.nth(1).get_attribute("aria-label") == "Reply"

    replies.nth(1).evaluate(
        "box => { const thread = box.closest('.lf-thread, .lf-page-thread'); "
        "(thread.querySelector(':scope > .lf-thread-summary') ?? thread).focus(); }"
    )
    shortcut_bar_text(page)
    assert replies.nth(1).get_attribute("placeholder") == "Reply c"
    page.keyboard.press("c")
    expect(replies.nth(1)).to_be_focused()
    shortcut_bar_text(page)
    assert re.search(r"⏎$", replies.nth(1).get_attribute("placeholder"))


def test_a_field_names_no_key_to_a_finger(browser, serve):
    """A touch screen hides the shortcut bar because its keys name presses the user
    cannot make, and a text field's placeholder is the same advert: the page's box
    said "Comment on the page c" and a thread's box "Reply c" to a phone. Whether a
    surface advertises keys is one reading (`advertisesKeys`), asked for the key that
    enters a box as well as the one that sends it."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, serve(INLINE_PAGE, comments=2), context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches")
    general = page.locator(".lf-general leaf-text")
    page_comment(page)
    expect(general).to_have_attribute("placeholder", "Comment on the page")
    page.keyboard.press("Escape")
    page.locator(".lf-threads-toggle").click()
    reply = page.locator(".lf-thread[open] .lf-thread-reply leaf-text")
    expect(reply).to_have_attribute("placeholder", "Reply")
    reply.focus()
    expect(reply).to_have_attribute("placeholder", "Reply")
    expect(page.locator(".lf-compose-placeholder")).to_have_count(0)


# The register's own answer to which commands a press can run, read with focus on the
# page, since the command reference is a modal scope that shadows the page once open:
# `runs`, what the page's enabled keys run from here; `runs_any`, what the reference can
# run from here, a command whose shortcut the user turned off included; `dead`, the
# commands of a scope the reference filters by liveness (one the user stands in, or one
# that asks to be) that cannot run now, by the liveness each row declares for the
# reference (`commandReferenceWhen`, else `when`); and `absent`, the commands of scopes
# this page has not got. A command id another present scope also declares, where the
# reference lists it as available there, is neither dead nor absent.
KEYBOARD_REGISTER = """async () => {
    const {availableCommandRoutes, stack, allBindings, commandEntries,
      commandPresentations, live, pageScopes, commandDeclarationsWithin} =
        await window.__lfCheckApi();
    const scopeIdentity = scope => scope.identity ?? scope;
    const running = (options) => {
        const ids = new Set();
        for (const [row, keys] of availableCommandRoutes(options))
            for (const key of keys)
                for (const {id} of commandEntries(row, [key])) ids.add(id);
        return ids;
    };
    const declared = (rows) => rows.flatMap((row) => commandPresentations(
        row, allBindings(row), {includeUnavailable: true}).map(({id}) => id));
    const has = (scope) => !scope.when || scope.when();
    const scopes = [
        ...pageScopes().flat().filter((scope) => typeof scope === 'object'),
        ...commandDeclarationsWithin(document.body).map(({scope}) => scope),
    ];
    const open = stack();
    const filtered = new Set([...open, ...scopes.filter(
        (scope) => has(scope) && scope.liveInCommandReference)].map(scopeIdentity));
    const runs = running(), runsAny = running({commands: true});
    const elsewhere = new Set(declared(scopes.filter(
        (scope) => has(scope) && !filtered.has(scopeIdentity(scope))
    ).flatMap((scope) => scope.rows)));
    const present = new Set(declared(scopes.filter(has).flatMap((scope) => scope.rows)));
    const dead = declared([...open, ...scopes].filter(
        (scope) => filtered.has(scopeIdentity(scope))
    ).flatMap((scope) => scope.rows).filter((row) =>
        !(row.commandReferenceWhen ? row.commandReferenceWhen() : live(row))));
    const missing = declared(scopes.filter((scope) => !has(scope))
        .flatMap((scope) => scope.rows));
    return {
        runs: [...runs],
        runs_any: [...runsAny],
        dead: [...new Set(dead)].filter((id) => !runsAny.has(id) && !elsewhere.has(id)),
        absent: [...new Set(missing)].filter((id) => !present.has(id)),
    };
}"""


def shown_commands(page):
    """What the register says can run, and the command ids the shortcut bar and the
    command reference name, read in that order and through the reference's `?` route."""
    register = page.evaluate(KEYBOARD_REGISTER)
    line = page.locator(".lf-shortcut-bar")
    # One list per chip, hidden ones included: the unfolded bar shows them.
    chips = line.locator("[data-lf-command-ids]").evaluate_all(
        "spans => spans.map(s => s.dataset.lfCommandIds.split(' ').filter(Boolean))"
    )
    help_el = page.locator(".lf-command-reference")
    # The first `?` unfolds the bar when it has more to show and the second opens the
    # reference; with nothing more, or the bar already unfolded, one press opens it.
    page.keyboard.press("?")
    page.wait_for_function(
        """() => document.querySelector('.lf-command-reference')?.checkVisibility()
            || document.querySelector('.lf-shortcut-bar')
                .getAttribute('data-lf-expanded') === 'true'"""
    )
    if not help_el.is_visible():
        page.keyboard.press("?")
    expect(help_el).to_be_visible()
    reference = help_el.locator("tr[data-lf-command]").evaluate_all(
        "rows => rows.map(r => r.dataset.lfCommand)"
    )
    runnable = help_el.locator(
        'button[data-lf-command][data-lf-available="true"]'
    ).evaluate_all("buttons => buttons.map(b => b.dataset.lfCommand)")
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()
    return (
        {key: set(ids) for key, ids in register.items()},
        chips,
        set(reference),
        set(runnable),
    )


def test_a_key_on_screen_is_a_key_that_works(browser, serve):
    """Every command a keyboard surface names is one the dispatcher will run.

    The shortcut bar names only commands that run from where the user stands. The
    command reference names no command of a scope this page has not got, and none that
    cannot run in a scope where it filters by liveness; a row it marks runnable runs.
    Liveness is one declaration the dispatcher and both surfaces ask, so the test holds
    the surfaces to the register by command id rather than by their words, in the
    states that change what is live: a thread walk only once there are threads, and
    still over resolved ones; a thread's own commands only once the page has one; and
    a version walk only once there is a version to walk to."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir
    page = open_page(browser, live_url(url))

    def surfaces_name_what_runs():
        register, chips, reference, runnable = shown_commands(page)
        assert chips, "the shortcut bar shows no key"
        assert all(chips), "the shortcut bar shows a key that names no command"
        bar = set().union(*chips)
        assert bar <= register["runs"], (
            f"the shortcut bar names {bar - register['runs']}, which would not run"
        )
        assert runnable <= register["runs_any"], (
            f"the command reference offers {runnable - register['runs_any']} "
            "as runnable, which would not run"
        )
        assert not reference & register["dead"], (
            f"the command reference names {reference & register['dead']}, "
            "which cannot run where it applies"
        )
        assert not reference & register["absent"], (
            f"the command reference names {reference & register['absent']}, "
            "from a scope this page has not got"
        )
        return register, bar, reference

    # No threads and one version: there is nothing to walk, so the walks are dead
    # where the user stands, and the page has no thread scope and no link.
    register, bar, reference = surfaces_name_what_runs()
    assert {"thread.next", "thread.previous", "version.later"} <= register["dead"]
    assert {"thread.primary", "link.follow"} <= register["absent"]
    # The dispatcher asks the same declaration: neither half of the walk runs.
    page.keyboard.press("t")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()

    # Threads arrive, making the walk live and the thread scope the page's own.
    for text in ["A thread.", "Another."]:
        append_carried_log_record(
            d, {"kind": "comment", "author": "user", "revision": 1, "text": text}
        )
    told(page)
    expect(page.locator(".lf-thread")).to_have_count(2)
    register, bar, reference = surfaces_name_what_runs()
    assert {"thread.next", "thread.previous"} <= bar & register["runs"]
    assert "thread.primary" in reference
    assert "version.later" in register["dead"]

    # The walk's key, pressed, stands the user on a thread in the Threads panel, where
    # the thread's own commands run.
    page.keyboard.press("t")
    expect(page.locator(".lf-thread-summary").first).to_be_focused()
    register, bar, reference = surfaces_name_what_runs()
    assert "thread.resolution.toggle" in bar & register["runs"]

    # A second version gives the versions menu somewhere to walk to.
    stamp_page(d, NOTED_PAGE, "two")
    wait_for_revision(page, 2)
    register, bar, reference = surfaces_name_what_runs()
    assert {"version.later", "version.earlier"} <= reference

    # With every thread resolved and the panel showing the resolved ones, the walk
    # still has threads to walk, so it stays live over a resolved card.
    for n in [1, 2]:
        card = page.locator(".lf-threads > .lf-thread:not([hidden])").first
        card.locator(":scope > .lf-thread-summary").click()
        card.get_by_role("button", name="Resolve").click()
        expect(page.locator('[data-filter-value="resolved"]')).to_have_text(
            f"Resolved ({n})"
        )
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    resolved = page.locator('.lf-thread[data-resolved="true"]:not([hidden])')
    expect(resolved).to_have_count(2)
    resolved.first.locator(":scope > .lf-thread-summary").focus()
    register, bar, reference = surfaces_name_what_runs()
    assert {"thread.next", "thread.previous"} <= bar & register["runs"]
