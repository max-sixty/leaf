"""The website route adapter preserves Leaf's canonical served-page contract."""

import json
import os
import shutil

import leaf_website as website_server
import pytest
from leaf.delivery import current_responses
from leaf.event_log import read_events
from leaf.leases import take_lease, waiter_lease_path
from leaf.render_checks import rendered
from leaf.thread import ProviderFinal, cmd_resolve, post_reply
from leaf_dev import example_previews, journey, verify_site
from playwright.sync_api import expect
from process.test_website_server import (
    ROOT,
    _no_harness_outlives_its_test_fixture,  # noqa: F401 (fixtures)
    get,
    hosted_follower,
)
from render_harness import (
    LONG_PAGE,
    open_page,
    page_comment,
    panel_settled,
    told,
    write,
)


@pytest.mark.parametrize(
    ("read_elsewhere", "reveal"),
    [(False, "click"), (False, "arrive"), (True, None)],
    ids=["click", "arrive", "elsewhere"],
)
def test_a_website_turn_posts_its_answer_when_the_move_is_settled_first(
    browser, serve, read_elsewhere, reveal, request
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, True)
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
    thread = page.locator(f'.lf-threads > [data-id="{comment["id"]}"]')
    # An active editor holds the turn's opening so this journey exercises the receipt
    # beside held news; an idle panel thread streams it immediately. The reply joins
    # the thread with its first words, not when the turn opens its draft.
    thread.locator("leaf-text").focus()
    turn.begin()
    turn.reply_stream.update(
        {
            "message": {
                "item": "msg-0",
                "phase": "commentary",
                "text": "Looking at the page.",
                "complete": False,
            }
        }
    )
    # Present the accepted turn before resolving it: coalescing these server writes
    # would never exercise a workflow receipt disappearing beside the news control.
    told(page)
    rendered(page)
    metadata = thread.locator(
        ".lf-thread-transcript > .lf-msg:first-child > .lf-msg-head"
    )

    def held_header():
        return metadata.evaluate("""head => {
          const rect = selector => head.querySelector(selector).getBoundingClientRect();
          const author = rect('b');
          const time = rect('time');
          const meta = rect('.lf-msg-meta');
          const news = head.closest('.lf-thread').querySelector('.lf-thread-news')
            .getBoundingClientRect();
          return {authorX: author.x, timeX: time.x, metadataRight: meta.right,
            newsLeft: news.left};
        }""")

    receipt = metadata.locator(".lf-msg-sending")
    expect(receipt).to_have_text("Replying")
    news = thread.locator(".lf-thread-news")
    expect(news).to_be_visible()
    news_left = news.bounding_box()["x"]
    held = held_header()
    assert held["metadataRight"] <= held["newsLeft"], held

    def receipt_words():
        return receipt.evaluate("""node => {
          const range = document.createRange();
          range.selectNodeContents(node);
          return range.getBoundingClientRect().width;
        }""")

    receipt_width = receipt_words()
    initial_receipt = receipt.inner_text()
    assert receipt.evaluate("node => node.scrollWidth <= node.clientWidth")
    # The gap belongs to neither receipt nor notice. Read its actual paint as
    # well as the retained parent box: unclipped glyphs can escape a child whose
    # bounding box still fits, without changing any metadata/news geometry.
    thread.evaluate(
        "node => Promise.all(node.getAnimations({subtree: true})"
        ".filter(animation => Number.isFinite("
        "animation.effect.getComputedTiming().endTime))"
        ".map(animation => animation.finished))"
    )
    gutter = receipt.evaluate(
        """node => {
      const metadata = node.closest('.lf-msg-meta').getBoundingClientRect();
      const notice = node.closest('.lf-thread').querySelector('.lf-thread-news')
        .getBoundingClientRect();
      const receipt = node.getBoundingClientRect();
      const x = Math.ceil(metadata.right);
      const y = Math.floor(receipt.top);
      return {x, y, width: Math.floor(notice.left) - x,
        height: Math.ceil(receipt.bottom) - y};
    }"""
    )
    assert gutter["width"] > 0, gutter
    gutter_before = page.screenshot(clip=gutter)
    # Losing the provider watcher changes Replying to the longer stale receipt
    # while its answer still waits. The words spend their own retained box.
    watcher.close()
    told(page)
    rendered(page)
    expect(receipt).to_have_text("Update stale")
    expect(receipt).to_have_attribute("title", "Update stale")
    assert receipt_words() > receipt_width, (
        initial_receipt,
        receipt_width,
        receipt_words(),
    )
    assert held_header() == held
    assert page.screenshot(clip=gutter) == gutter_before, (
        "the longer workflow receipt painted into the gap before held news"
    )
    cmd_resolve(page_dir, comment["id"])
    told(page)
    rendered(page)
    # The agent's resolution is news, so the card the user is looking at stays in
    # Open Threads, holding it behind its notice, rather than folding out from in
    # front of them.
    expect(thread).to_have_count(1)
    expect(news).to_have_text("Resolved · 1 new reply")
    expect(thread).to_be_visible()
    expect(metadata.locator(".lf-msg-sending")).to_have_count(0)
    assert news.bounding_box()["x"] == news_left
    assert held_header() == held
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
        other_thread = page.locator(f'.lf-thread[data-id="{other["id"]}"]')
        expect(other_thread).to_have_attribute("open", "")

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
    drawn = page.evaluate("Date.now()")
    if read_elsewhere:
        # The thread folded when the user's new one opened, and a folded card holds
        # nothing, since its title row draws at one size.
        expect(other_thread).to_have_attribute("open", "")
        expect(news).to_have_count(0)
        expect(thread.locator(".lf-msg.agent")).to_be_hidden()
        assert set(current_responses(page_dir, read_events(page_dir))) == {other["id"]}
        # Its row is all the user sees of the answer, and the page times the answer
        # from it whatever the journey is doing then.
        [folded] = [
            event
            for event in read_events(page_dir)
            if event["kind"] == "reply" and event["parent"] == comment["id"]
        ]
        shown = page.evaluate(
            "window.__leafVerifier.replyShownAt",
            {"thread": comment["id"], "id": folded["id"], "ts": folded["ts"]},
        )
        assert shown["by"] == "row"
        assert committed <= shown["at"] <= drawn
    else:
        # The short thread's reopened answer would move its active editor, so the
        # reader explicitly opens the news before the visibility clock can see it. The
        # card stands as drawn, open, so the reopening is no news.
        expect(news).to_have_text("1 new reply")
        assert news.bounding_box()["x"] == news_left
        assert held_header() == held
        expect(
            thread.locator(".lf-msg.agent").filter(has_text="deployment verified")
        ).to_have_count(0)
        answer_id = next(
            event["id"]
            for event in read_events(page_dir)
            if event["kind"] == "reply" and event["parent"] == comment["id"]
        )
        # The held answer's notice is what the user is shown of it, and the page
        # times the answer from the notice before anyone opens it.
        held_answer = next(e for e in read_events(page_dir) if e["id"] == answer_id)
        shown = page.evaluate(
            "window.__leafVerifier.replyShownAt",
            {"thread": comment["id"], "id": answer_id, "ts": held_answer["ts"]},
        )
        assert shown["by"] == "notice"
        assert committed <= shown["at"] <= drawn
        if reveal == "click":
            journey.open_news(page, comment["id"])
        else:
            # Choosing the thread's title is an arrival, which shows what it holds.
            title = thread.locator(":scope > .lf-thread-summary")
            title.click()
            expect(title).to_be_focused()
            expect(thread).to_have_attribute("open", "")
        expect(news).to_have_count(0)
        # Opened, the answer's own message comes into view too, though the notice
        # had already shown the user it was there.
        page.wait_for_function(
            "id => window.__leafVerifier.visibleReplyDebug().shown.messages[id]",
            arg=answer_id,
        )
        assert current_responses(page_dir, read_events(page_dir)) == {}
    [answer] = [event for event in read_events(page_dir) if event["kind"] == "reply"]
    assert answer["parent"] == comment["id"]
    assert answer["text"] == "deployment verified"
    assert answer["responds"] == comment["id"]
    # Retrying the same delivery keeps one answer and its original response scope.
    assert (
        post_reply(
            page_dir,
            {"to": comment["id"], "for": comment["id"]},
            "deployment verified",
            settlement=ProviderFinal("test-final"),
            attempt=answer["attempt"],
            identity={"session": "hosted-thread"},
        )
        == answer
    )


def test_the_preview_generator_bootstraps_a_new_catalog_entry(tmp_path, monkeypatch):
    pinned = example_previews.pinned_assets()
    current = tmp_path / "current"
    (current / "examples").mkdir(parents=True)
    shutil.copytree(pinned / "demo", current / "demo")
    existing = current / "examples" / "example-existing.jpg"
    shutil.copy2(next((pinned / "examples").glob("example-*.jpg")), existing)
    source = ROOT / "examples" / "ideas-to-implement.html"
    sources = [source]
    monkeypatch.setattr(example_previews, "pinned_assets", lambda: current)
    monkeypatch.setattr(example_previews, "catalog_sources", lambda: sources)
    monkeypatch.setattr(example_previews.site_build, "catalog_sources", lambda: sources)
    monkeypatch.setattr(
        example_previews.site_build, "published_page_sources", lambda: sources
    )

    assets = example_previews.bootstrap_assets(tmp_path / "assets")
    site = tmp_path / "site"
    example_previews.site_build.build_examples(
        site, example_previews.site_build.checkout_leaf(), assets=assets
    )

    assert (
        assets / "examples" / "example-ideas-to-implement.jpg"
    ).read_bytes() == existing.read_bytes()
    with example_previews.serve_examples(site) as root:
        state = json.loads(get(f"{root}/examples/ideas-to-implement/api/state")[0])
    assert state["publication"]["kind"] == "example"
