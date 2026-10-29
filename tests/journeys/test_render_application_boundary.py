"""Joint browser proof for immutable page inputs and fresh revision activation."""

import pytest
from browser.test_render_application_boundary import (
    PAGE_MODULE,
    activation_page,
    package_workspace,
)
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    LIVE_V1,
    LIVE_V2,
    live_url,
)
from render_harness import (
    holding,
    open_page,
    page_comment,
    panel_control,
    scroll_settled,
    sending,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

from leaf import event_log as events_model
from leaf_dev.browser import slow_cpu


def test_a_settled_delivery_activates_one_fresh_document_with_continuity(
    held_events, serve
):
    """One activation waits for its old document, then restores only Leaf state."""
    browser, held = held_events
    source = activation_page(LIVE_V1)
    version_url = serve(
        source,
        page_files={
            "app.js": PAGE_MODULE,
            "helper.js": 'export const label = "first";',
        },
    )
    page = open_page(browser, live_url(version_url))
    expect(page.locator("html")).to_have_attribute("data-page-module", "first:1")
    first_document = page.evaluate("performance.timeOrigin")
    page.evaluate("window.__pageModuleState.oldDocumentOnly = true")

    write(page_comment(page), "Keep this recoverable draft in the page.")
    page.keyboard.press("Escape")

    page.locator("#live-reading").evaluate(
        "el => { el.scrollIntoView({block: 'start'}); scrollBy(0, -120); }"
    )
    page.locator("#activation-go .lf-pick").click()
    holding(page, held, 1, "the unresolved option pick")
    focused_control = page.locator("#focused-control")
    focused_control.click()
    expect(focused_control).to_be_focused()
    reading_top = page.locator("#live-reading").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    assert page.evaluate("scrollY") > 0

    try:
        (serve.page_dir / "page" / "helper.js").write_text(
            'export const label = "second";'
        )
        stamp_page(
            serve.page_dir, activation_page(LIVE_V2), "activate the complete page"
        )
        told(page)

        assert page.evaluate("performance.timeOrigin") == first_document
        expect(page).to_have_title("Live first")
        expect(focused_control).to_be_focused()
        assert len(held) == 1

        # The explicit door may release a composition hold, but it cannot release the
        # delivery hold.
        latest = panel_control(page, "latest")
        with page.expect_response("**/api/state*"):
            latest.click()
        told(page)
        assert page.evaluate("performance.timeOrigin") == first_document
        assert len(held) == 1
    finally:
        held.pop(0).continue_()

    wait_for_revision(page, 2)
    expect(page.locator("html")).to_have_attribute("data-page-module", "second:1")
    assert page.evaluate("performance.timeOrigin") != first_document
    assert page.evaluate("window.__pageModuleState") == {
        "loads": 1,
        "label": "second",
    }
    # Leaf state crosses; the user's place on a control does not. A fresh document
    # cannot know it has found the same control again — an id, a tag and a count among
    # siblings are a shape, not an identity — so it leaves focus on the page, where the
    # page's own keys are live, rather than hand the next press to a guess.
    assert page.evaluate("document.activeElement === document.body")
    expect(page.locator("#activation-go")).to_have_attribute("chosen", "")
    restored_top = page.locator("#live-reading").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    assert abs(restored_top - reading_top) < 2, (reading_top, restored_top)
    expect(page_comment(page)).to_have_js_property(
        "value", "Keep this recoverable draft in the page."
    )

    historical = open_page(browser, version_url, pin=True)
    expect(historical.locator("html")).to_have_attribute("data-page-module", "first:1")


@pytest.mark.parametrize(
    ("primary", "travel", "source_top", "cross_boundary", "back_before_frame"),
    [
        (True, True, 200, False, False),
        (True, False, 200, False, False),
        # Back interrupts the native trip before its first compositor frame.
        (False, True, 1000, False, True),
        # A contextual card's travel, slowed until it crosses into the viewport.
        (False, True, 1000, True, False),
    ],
)
def test_primary_arrival_records_a_return_place_only_when_travelling(
    browser, serve, primary, travel, source_top, cross_boundary, back_before_frame
):
    """Back restores the working place left by a jump to the primary reader."""
    url = package_workspace(
        serve,
        before_reader='<p style="min-height:1600px">Earlier page context.</p>',
        primary=primary,
    )
    if not primary:
        append_carried_log_record(
            serve.page_dir,
            {
                "id": "anchored",
                "kind": "comment",
                "author": "agent",
                "revision": 1,
                "text": "Inspect this passage.",
                "anchor": {"section": "notes"},
            },
        )
    page = open_page(browser, url)
    page.set_viewport_size({"width": 1440, "height": 320})
    heading = page.locator("h1")
    heading.evaluate(
        """(node, top) => {
      node.tabIndex = -1;
      node.focus({preventScroll:true});
      const range = document.createRange();
      range.selectNodeContents(node);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
      window.scrollTo({top, behavior:'instant'});
    }""",
        source_top,
    )
    if cross_boundary:
        # Long native frames expose the compositor's one-frame anchor delay as the
        # contextual card travels into the viewport and changes placement plane.
        slow_cpu(page, 6)
    if back_before_frame:
        page.evaluate("""() => {
          const scrollBy = Element.prototype.scrollBy;
          Element.prototype.scrollBy = function(options) {
            const result = scrollBy.call(this, options);
            if (this === document.scrollingElement && options.behavior === 'smooth') {
              Element.prototype.scrollBy = scrollBy;
              window.backRequestedAt = scrollY;
              queueMicrotask(() => history.back());
            }
            return result;
          };
        }""")
    entries = page.evaluate("history.length")
    assert page.evaluate(
        """async ({travel, primary}) => {
          const api = await window.__lfWidgetApi();
          const thread = api.readThreads().threads.find(thread => thread.id === (primary ? 'opening' : 'anchored'));
          window.returnTripDestination = await api.threadActions.open(thread.key, {part:'reply', travel});
          return Boolean(returnTripDestination);
        }""",
        {"travel": travel, "primary": primary},
    )
    if not back_before_frame:
        assert page.evaluate("""() => {
          let active = document.activeElement;
          while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement;
          return active === returnTripDestination;
        }""")
    assert page.evaluate("history.length") == entries + int(travel)
    if travel:
        if back_before_frame:
            assert page.evaluate("backRequestedAt") == source_top
        else:
            # Back is ordinary input as soon as arrival returns, during smooth placement.
            page.wait_for_function("top => scrollY !== top", arg=source_top)
            if cross_boundary:
                page.wait_for_function("scrollY < 200")
                expect(page.locator("#lf-margin-preview")).to_be_in_viewport()
            page.go_back()
        expect(heading).to_be_focused()
        scroll_settled(page)
        assert page.evaluate("scrollY") == source_top
        assert page.evaluate("getSelection().toString()") == heading.text_content()
    else:
        assert page.evaluate("scrollY") == source_top


@pytest.mark.parametrize("width", [1440, 390])
def test_primary_package_reader_retains_native_widgets_drafts_and_creation(
    browser, serve, width
):
    context = browser.new_context(
        viewport={"width": width, "height": 900},
        has_touch=width < 500,
        is_mobile=width < 500,
    )
    url = package_workspace(serve)
    for question_id, text in [
        ("tone-question", "Should it stay concise?"),
        ("followup-question", "When should it send?"),
    ]:
        append_carried_log_record(
            serve.page_dir,
            {
                "id": question_id,
                "kind": "reply",
                "author": "agent",
                "revision": 1,
                "parent": "opening",
                "text": text,
                "obligation": True,
            },
        )
    page = open_page(browser, url, context=context)
    workspace = page.locator("#workspace")
    email = workspace.locator("lf-option#email")
    expect(email).to_be_visible()
    if width < 500:
        # Playwright's automatic click scroll has no trusted input for the
        # shift watcher; move the short reader with a user scroll first.
        workspace.locator(".reader").hover()
        page.mouse.wheel(0, 100)
    page.evaluate(
        "window.originalOption = document.querySelector('#workspace').querySelector('#email')"
    )
    with sending(page, "answer the package's native obligation"):
        email.get_by_role("checkbox").click()
    expect(workspace.locator(".counts")).to_contain_text("Email")
    workspace.get_by_role("button", name="Keep it concise.", exact=True).click()
    editor = workspace.get_by_role("textbox", name="Reply", exact=True)
    write(editor, "A shared draft")
    workspace.get_by_role("button", name="Feed", exact=True).click()
    expect(editor).to_have_js_property("value", "A shared draft")
    workspace.get_by_role("button", name="Shelf", exact=True).click()
    assert page.evaluate(
        "document.querySelector('#workspace').querySelector('#email') === window.originalOption"
    )
    expect(
        workspace.get_by_role("textbox", name="Reply", exact=True).last
    ).to_have_js_property("value", "A shared draft")
    with sending(page, "send the retained reply"):
        workspace.get_by_role("textbox", name="Reply", exact=True).last.press(
            "Control+Enter"
        )
    expect(workspace.get_by_text("A shared draft", exact=True)).to_be_visible()
    # One reply answers both questions; the separate proofread task remains due.
    # Counts include them, while the compact answer summary names only widget
    # choices instead of repeating words.
    expect(workspace.locator(".counts")).to_have_text(
        "1 waiting on me · 3 answered · Email"
    )
    with sending(page, "create a real conversation from a package"):
        workspace.get_by_role("textbox", name="New conversation").fill(
            "New package conversation"
        )
        workspace.get_by_role("button", name="Start conversation").click()
    expect(
        workspace.locator(".lf-page-thread").get_by_text(
            "New package conversation", exact=True
        )
    ).to_be_visible()
    assert any(
        event.get("text") == "New package conversation" and event["kind"] == "comment"
        for event in events_model.read_events(serve.page_dir)
    )
