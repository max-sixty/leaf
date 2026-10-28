"""A thread's reply box through a send still under way."""

from playwright.sync_api import expect
from render_harness import holding, leaf_page, open_page, panel_field, round_trip

from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf.render_checks import rendered


def test_a_draft_typed_during_a_reply_s_send_outlives_its_admission(browser, serve):
    """The reply box empties as a reply is sent, and words the user types there while
    that send is still held are a new draft: the earlier reply's admission leaves them
    in the box rather than clearing or replacing them."""
    url = serve(leaf_page("Reply drafts", "<h1>Review the release</h1>"))
    events_model.append_event(
        serve.page_dir,
        {
            "id": "root",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep the review clear.",
        },
    )
    page = open_page(browser, url)
    open_panel_thread(page, "root")
    draft = panel_field(page)
    held = []
    page.route(
        "**/api/event",
        lambda route: (
            held.append(route)
            if route.request.post_data_json["kind"] == "reply"
            else route.continue_()
        ),
    )
    first = "Keep the reader's words in the thread while this reply is being sent."
    newer = "Keep the next draft separate from the reply still being sent."
    draft.click()
    page.keyboard.insert_text(first)
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the first reply")
    rendered(page)
    expect(draft).to_have_js_property("value", "")
    draft.click()
    page.keyboard.insert_text(newer)
    held.pop().continue_()
    round_trip(page)
    rendered(page)
    expect(draft).to_have_js_property("value", newer)
    page.unroute_all(behavior="wait")
