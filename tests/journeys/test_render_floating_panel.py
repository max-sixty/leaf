"The floating panel: Leaf's one chrome, a box over the page's foot.\n\nEach test is one journey a user takes through the panel: writing a page comment and replying in the same field, settling the thread, finding\nthreads and taking in news, answering obligations, travelling between versions, and\nfolding the panel to the leaf in the window's corner and back."

import pytest
from browser.test_render_floating_panel import field, floating, settled
from playwright.sync_api import expect
from render_harness import (
    LONG_PAGE,
    open_page,
)


def test_a_long_draft_fades_where_words_run_past_the_field(browser, serve):
    """A draft taller than the field shows no scrollbar, whose overlay flashed with each
    line; its words fade at whichever edge they run past, read from the field's scroll
    rather than a scroll timeline, which Firefox lacks."""
    page = floating(browser, serve(LONG_PAGE))
    field(page).click()
    for line in range(30):
        page.keyboard.type(f"line {line}")
        page.keyboard.press("Shift+Enter")

    def shows(states):
        page.wait_for_function(
            f"() => document.querySelector('.lf-fp-field leaf-text').matches('{states}')"
        )

    expect(field(page)).to_have_css("scrollbar-width", "none")
    shows(":state(more-above):not(:state(more-below))")
    field(page).evaluate("box => box.scrollTop = 0")
    shows(":state(more-below):not(:state(more-above))")
    field(page).evaluate("box => box.scrollTop = 100")
    shows(":state(more-below):state(more-above)")


from browser.test_render_floating_panel import FOOT
from interact_support import (
    append_carried_log_record,
)
from render_cases_interaction import (
    panel_comment,
)
from render_harness import (
    open_threads,
    panel_view,
    sending,
    told,
)


def test_nothing_lies_over_a_view_s_foot_but_new_reply(browser, serve):
    """An open view's foot keeps no room for anything but its padding, and nothing lies
    over it: not the line over the field, which would repeat where the words go, nor
    news arriving in it, which the view shows. At the view's end its last words stand
    just above its padding, in a long Threads list and a long thread the user types at
    the end of. New reply alone stands at its foot, on the panel's ground and inside the
    view, clear of the user's own last turn while the answer to it waits below."""
    url = serve(LONG_PAGE, comments=12)
    long_root = panel_comment(serve.page_dir, "Walk me through the whole rollout.")
    for step in range(8):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": long_root,
                "revision": 1,
                "text": f"Step {step}. "
                + "The cohort widens once the alarms hold. " * 4,
            },
        )
    page = floating(browser, url)

    def at_end(parts):
        page.locator(".lf-fp-view:not([data-leaving])").evaluate(
            "view => view.scrollTop = view.scrollHeight"
        )
        settled(page)
        foot = page.evaluate(FOOT, [parts, 0])
        assert foot["said"] == [], foot
        assert 0 <= foot["below"] < 10, foot

    open_threads(page)
    inventory = page.locator(panel_view("threads"))
    expect(inventory.locator(".lf-fp-thread")).to_have_count(13)
    field(page).click()
    page.keyboard.type("Could")
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-drafted", "")
    at_end(".lf-fp-thread")

    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    inventory.locator(".lf-fp-thread", has_text="Walk me through").click()
    reader = page.locator(panel_view("thread"))
    expect(reader.locator(".lf-msg")).to_have_count(9)
    field(page).click()
    page.keyboard.type("Could")
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-drafted", "")
    at_end(".lf-msg")

    # The answer to the user's turn waits below the fold behind New reply, and its
    # arrival goes unsaid over the view that holds it.
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("And the weekend?")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(reader.locator(".lf-msg")).to_have_count(10)
    settled(page)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": long_root,
            "revision": 1,
            "text": "It would. "
            + "Someone stays on call through Sunday, and Monday too. " * 40,
        },
    )
    told(page)
    expect(reader.locator(".lf-fp-new-reply")).to_have_text("New reply")
    settled(page)
    # The user's own turn, the last message but the answer below the fold.
    foot = page.evaluate(FOOT, [".lf-msg-text", 1])
    assert foot["said"] == [], foot
    assert foot["press"]["over"] >= 0, foot
    assert foot["press"]["under"] >= 0, foot


def test_a_long_draft_offers_more_room_at_a_press(browser, serve):
    """Past three lines the field offers more room, by a press rather than on its own:
    a mark stands over the leaf, beside the field's first line, taking no room of its
    own, including with a view open. Pressing it widens the panel, keeps the field at
    least as tall as the draft stood, without standing a short draft half the window
    tall, and keeps the caret in the words; emptying the field folds it back."""
    page = floating(browser, serve(LONG_PAGE))
    panel = page.locator(".lf-floating-panel")
    expand = page.locator(".lf-fp-expand")
    field(page).click()
    page.keyboard.type("A line of words long enough to wrap in the panel's field, " * 2)
    expect(expand).to_be_hidden()
    narrow = panel.bounding_box()["width"]
    page.keyboard.type("A line of words long enough to wrap in the panel's field, " * 2)
    expect(expand).to_be_visible()
    words = page.locator(".lf-fp-field").bounding_box()
    leaf = page.locator(".lf-fp-leaf").bounding_box()
    mark = expand.bounding_box()
    assert mark["x"] + mark["width"] <= words["x"] + 0.5, (words, mark)
    assert words["y"] <= mark["y"] + 0.5, (words, mark)
    assert mark["y"] + mark["height"] <= leaf["y"] + 0.5, (leaf, mark)
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    expect(page.locator(panel_view("threads"))).to_be_visible()
    expect(expand).to_be_visible()
    words = page.locator(".lf-fp-field").bounding_box()
    leaf = page.locator(".lf-fp-leaf").bounding_box()
    mark = expand.bounding_box()
    assert mark["x"] + mark["width"] <= words["x"] + 0.5, (words, mark)
    assert mark["y"] + mark["height"] <= leaf["y"] + 0.5, (leaf, mark)
    page.keyboard.press("Escape")
    field(page).click()
    expect(expand).to_have_attribute("aria-pressed", "false")
    before = field(page).bounding_box()["height"]
    expand.click()
    expect(expand).to_have_attribute("aria-pressed", "true")
    expect(field(page)).to_be_focused()
    settled(page)
    assert panel.bounding_box()["width"] > narrow + 100
    tall = field(page).bounding_box()["height"]
    assert before - 1 <= tall < page.viewport_size["height"] / 3, (before, tall)
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    expect(expand).to_be_hidden()
    settled(page)
    assert panel.bounding_box()["width"] == pytest.approx(narrow, abs=1)


def test_more_room_on_a_phone_keeps_the_panel_its_width(browser, serve):
    """On a phone the panel already spans the window less its gutter, so more room to
    write leaves it as wide as it was. The wider panel's own width named the desktop's
    24px gutter rather than the phone's 20px, so pressing for more room narrowed it."""
    context = browser.new_context(viewport={"width": 390, "height": 800})
    page = open_page(browser, serve(LONG_PAGE), context=context)
    panel = page.locator(".lf-floating-panel")
    expand = page.locator(".lf-fp-row > .lf-fp-expand")
    field(page).click()
    page.keyboard.type("A line of words long enough to wrap in the panel's field, " * 4)
    expect(expand).to_be_visible()
    settled(page)
    narrow = panel.bounding_box()["width"]
    expand.click()
    expect(expand).to_have_attribute("aria-pressed", "true")
    settled(page)
    assert panel.bounding_box()["width"] == pytest.approx(narrow, abs=0.5)
