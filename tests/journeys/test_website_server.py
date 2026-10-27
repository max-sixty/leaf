"""The website route adapter preserves Leaf's canonical served-page contract."""

import os

import leaf_website as website_server
import pytest
from browser.threads import open_panel_thread
from leaf_dev.commands import verify_site
from playwright.sync_api import expect
from process.website_server import (
    _no_harness_outlives_its_test_fixture,  # noqa: F401 (fixtures)
    hosted_follower,
)
from render_harness import (
    LONG_PAGE,
    PANEL_THREAD,
    open_page,
    page_comment,
    panel_field,
    told,
    write,
)

from leaf.delivery import current_responses
from leaf.event_log import read_events
from leaf.leases import take_lease, waiter_lease_path
from leaf.render_checks import rendered
from leaf.thread import ProviderFinal, cmd_resolve, post_reply


@pytest.mark.parametrize("read_elsewhere", [False, True], ids=["here", "elsewhere"])
def test_a_website_turn_posts_its_answer_when_the_move_is_settled_first(
    browser, serve, read_elsewhere, request
):
    """A resolve during a turn cannot hide its completed answer from Open Threads.

    Exercise the hosted commit and the publication gate's actual browser observer,
    then verify settlement and retry at the same durable response address.
    """
    url = serve(LONG_PAGE)
    page_dir = serve.page_dir
    page = open_page(browser, url)
    verify_site.observe_startup(page)
    page.reload()
    told(page)
    box = page_comment(page)
    page.evaluate("window.__leafVerifier.startVisibleReplyClock")
    write(box, "edit the page")
    box.press("ControlOrMeta+Enter")
    told(page)
    [comment] = [event for event in read_events(page_dir) if event["kind"] == "comment"]
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    harness = website_server.WebsiteCodexHarness("codex")
    turn = hosted_follower(harness, page_dir, prepared)
    watcher = take_lease(waiter_lease_path(page_dir, "hosted-thread"))
    assert watcher is not None
    request.addfinalizer(watcher.close)
    # The send opens the new thread's view in the panel, its reply standing in the
    # field with the caret in it.
    thread = page.locator(f'{PANEL_THREAD}[data-thread="{comment["id"]}"]')
    expect(thread).to_be_visible()
    # The user goes on writing in the reply, which the agent's resolve below must not
    # take from under them. The agent's reply joins the thread with its first words,
    # not when the turn opens its draft.
    reply = panel_field(page)
    expect(reply).to_be_focused()
    write(reply, "While you look")
    turn.begin()
    turn.reply_stream.update({"opening": "Looking at the page."})
    # Present the accepted turn before resolving it: coalescing these server writes
    # would never exercise a workflow receipt disappearing beside the news control.
    told(page)
    rendered(page)
    # The turn's opening streams into the open thread at its end, where it moves none
    # of the words above it.
    expect(thread.locator(".lf-msg.agent")).to_contain_text("Looking at the page.")
    metadata = thread.locator(".lf-msg").first.locator(":scope > .lf-msg-head")
    receipt = metadata.locator(".lf-msg-sending")
    expect(receipt).to_have_text("Replying")
    news = page.locator(".lf-fp-controls .lf-thread-news")

    def receipt_words():
        return receipt.evaluate("""node => {
          const range = document.createRange();
          range.selectNodeContents(node);
          return range.getBoundingClientRect().width;
        }""")

    receipt_width = receipt_words()
    initial_receipt = receipt.inner_text()
    assert receipt.evaluate("node => node.scrollWidth <= node.clientWidth")
    head = metadata.bounding_box()
    # Losing the provider watcher changes Replying to the longer stale receipt
    # while its answer still waits. The words spend their own retained box.
    watcher.close()
    told(page)
    rendered(page)
    expect(receipt).to_have_text("Gone quiet")
    expect(receipt).to_have_attribute("title", "Gone quiet · Looking at the page.")
    assert receipt_words() > receipt_width, (
        initial_receipt,
        receipt_width,
        receipt_words(),
    )
    assert metadata.bounding_box() == head
    cmd_resolve(page_dir, comment["id"])
    told(page)
    rendered(page)
    # The agent's resolution is news, so the thread the user is writing in stays open
    # in front of them, holding it behind its notice.
    expect(thread).to_be_visible()
    expect(news).to_have_text("Resolved")
    expect(metadata.locator(".lf-msg-sending")).to_have_count(0)
    if read_elsewhere:
        box = page_comment(page)
        write(box, "A separate thread")
        box.press("ControlOrMeta+Enter")
        told(page)
        [other] = [
            event
            for event in read_events(page_dir)
            if event["kind"] == "comment" and event["id"] != comment["id"]
        ]
        other_thread = page.locator(f'{PANEL_THREAD}[data-thread="{other["id"]}"]')
        expect(other_thread).to_be_visible()

    committed = page.evaluate("Date.now()")
    turn.commit(
        {
            "id": "app-server-turn",
            "status": "completed",
            "items": [
                {
                    "type": "agentMessage",
                    "phase": "final_answer",
                    "id": "msg-1",
                    "text": "deployment verified",
                }
            ],
        }
    )

    told(page)
    rendered(page)
    if read_elsewhere:
        # The user's new thread stands in the view, so the answer shows nowhere yet.
        expect(other_thread).to_be_visible()
        expect(thread).to_have_count(0)
        assert set(current_responses(page_dir, read_events(page_dir))) == {other["id"]}
        [elsewhere] = [
            event
            for event in read_events(page_dir)
            if event["kind"] == "reply"
            and event["parent"] == comment["id"]
            and not event.get("ephemeral")
        ]
        # The resolve does not hide it: Threads still lists the thread among the open
        # ones, and opening it there shows the answer, which the page times then.
        view = open_panel_thread(page, comment["id"])
        message = view.locator(".lf-msg.agent").filter(has_text="deployment verified")
        expect(message).to_be_visible()
        shown = page.evaluate(
            "window.__leafVerifier.replyShownAt",
            {"thread": comment["id"], "id": elsewhere["id"]},
        )
        assert shown["by"] == "message"
        assert committed <= shown["at"]
    else:
        # The answer completes the streamed opening in place at the thread's end, so it
        # moves nothing the user reads or writes and shows at once, the resolve it
        # reopens with it. The page times its notice and its own message.
        expect(news).to_be_hidden()
        expect(page.locator(".lf-fp-settle")).to_have_accessible_name("Resolve thread")
        expect(
            thread.locator(".lf-msg.agent").filter(has_text="deployment verified")
        ).to_be_visible()
        expect(reply).to_have_js_property("value", "While you look")
        answer_id = next(
            event["id"]
            for event in read_events(page_dir)
            if event["kind"] == "reply"
            and event["parent"] == comment["id"]
            and not event.get("ephemeral")
        )
        page.wait_for_function(
            "address => window.__leafVerifier.replyShownAt(address)?.message != null",
            arg={"thread": comment["id"], "id": answer_id},
        )
        shown = page.evaluate(
            "window.__leafVerifier.replyShownAt",
            {"thread": comment["id"], "id": answer_id},
        )
        assert shown["message"] is not None
        assert committed <= shown["at"] <= shown["message"]
        assert current_responses(page_dir, read_events(page_dir)) == {}
    [answer] = [
        event
        for event in read_events(page_dir)
        if event["kind"] == "reply" and not event.get("ephemeral")
    ]
    assert answer["parent"] == comment["id"]
    assert answer["text"] == "deployment verified"
    assert answer["responds"] == comment["id"]
    # Retrying the same delivery keeps one answer and its original response scope.
    assert (
        post_reply(
            page_dir,
            {"parent": comment["id"], "responds": comment["id"]},
            "deployment verified",
            settlement=ProviderFinal("test-final"),
            attempt=answer["attempt"],
            identity={"session": "hosted-thread"},
        )
        == answer
    )
