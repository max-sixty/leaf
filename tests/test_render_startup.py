"""Initial presentation, polling, presence, and projected-data tests."""

import io
import itertools
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf import files as files_model
from leaf import hosting as hosting_model
from leaf import http as http_model
from leaf import render_checks as render_checks_model
from leaf import service as service_model
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_support import (
    _CARD,
    BOTH_STAMPS,
    DRAFT_EDITED,
    DRAFT_TEXT,
    FIRST_PRESENTATION,
    JOURNEY_V1,
    JOURNEY_V2,
    LONG_PAGE,
    RENDERED,
    SENTENCE,
    SHADOWED_DIFF,
    SHORT_SUGGESTION,
    SUGGEST_BLOCK,
    TAB_AND_DOT,
    TAB_TONE,
    TOKEN,
    _card_done,
    _draft_says,
    _publish,
    _traffic,
    compare_with,
    data_projection_page,
    live_url,
    live_watcher,
    nudge,
    open_page,
    panel_settled,
    record_claim,
    refuse,
    round_trip,
    select,
    sent_events,
    told,
    undo,
    wait_for_revision,
    watched,
)

pytestmark = pytest.mark.nightly


def test_widget_api_selects_helpers_from_their_runtime_owners(browser, serve):
    page, errors = open_page(browser, serve(SHORT_SUGGESTION))
    exports = page.evaluate(
        """async () => {
          const api = await import('/runtime/widget-api.js');
          const entry = await import('/leaf.js');
          const names = [
            'clearDraft',
            'closestDeclaring',
            'declarationFor',
            'elementsDeclaring',
            'layerFact',
            'loadDraft',
            'matchesWhen',
            'quietWord',
            'saveDraft',
            'sendDraft',
            'watchDraft',
          ];
          return Object.fromEntries(names.map((name) => [name, {
            api: typeof api[name],
            entry: name in entry,
          }]));
        }"""
    )
    assert exports == {
        name: {"api": "function", "entry": False}
        for name in [
            "clearDraft",
            "closestDeclaring",
            "declarationFor",
            "elementsDeclaring",
            "layerFact",
            "loadDraft",
            "matchesWhen",
            "quietWord",
            "saveDraft",
            "sendDraft",
            "watchDraft",
        ]
    }
    assert errors == []
    page.close()


def test_refusing_the_storage_objects_does_not_block_startup(browser, serve):
    """Acquiring web storage can itself throw before any method is called.

    The stores' unavailable answer covers that outer browser boundary too, so a
    locked-down page loses only remembered view state and drafts, not the page.
    """
    page, errors = open_page(
        browser,
        serve(SHORT_SUGGESTION),
        init_script="""
          for (const name of ['localStorage', 'sessionStorage'])
            Object.defineProperty(window, name, {
              configurable: true,
              get() { throw new DOMException('blocked', 'SecurityError'); },
            });
        """,
    )
    expect(page.locator("main")).to_be_visible()
    tab_store = page.evaluate(
        """async () => {
          const { tabStore } = await import('/runtime/widget-api.js');
          return {
            read: tabStore.read('refused'),
            wrote: tabStore.set('refused', '1'),
            keys: tabStore.keys(),
            where: tabStore.where('refused'),
          };
        }"""
    )
    assert tab_store == {
        "read": {"available": False, "value": None},
        "wrote": False,
        "keys": [],
        "where": {"store": "session", "key": "refused"},
    }
    assert errors == []
    page.close()


def test_first_replay_is_the_pages_first_presentation(browser, serve):
    """A version is not the page the reader left when the log already changed it.

    Hold the first state response beyond the document stamp and record every frame the
    browser offers to paint. The authored suggestion stays laid out — presentation is
    paint, not a second rendering — but none of those frames may expose it. Releasing the
    one held response applies the decision and releases the page exactly once."""
    url = serve(
        SHORT_SUGGESTION.replace(
            "</head>",
            """<style>
main, main * {
  visibility: visible !important;
  opacity: 1 !important;
  interactivity: auto !important;
  pointer-events: auto !important;
}
</style></head>""",
        )
        .replace(
            "<main>",
            '<main style="visibility: visible; opacity: 1; interactivity: auto; '
            'pointer-events: auto">',
        )
        .replace(
            "<lf-old>",
            "<lf-old>"
            '<button id="stale-control">Stale control</button>'
            '<dialog id="stale-dialog" style="visibility: visible; opacity: 1; '
            'interactivity: auto; pointer-events: auto">'
            '<button style="visibility: visible">'
            "Top-layer stale control</button></dialog>",
        )
        .replace("</main>", SHADOWED_DIFF)
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug",
            "action": "accept",
            "detail": {},
        },
    )
    held = []
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.add_init_script(FIRST_PRESENTATION)
    page.route("**/api/state*", lambda route: held.append(route))
    try:
        page.goto(url, wait_until="load")
        page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
        page.wait_for_function(
            "() => Number(getComputedStyle(document.body, '::after').opacity) > 0"
        )
        page.locator("#stale-dialog").evaluate("dialog => dialog.showModal()")
        page.evaluate(
            """() => {
              const root = document.querySelector('#shadowed').shadowRoot;
              const dialog = document.createElement('dialog');
              dialog.id = 'shadow-stale-dialog';
              dialog.innerHTML = '<button>Shadow top-layer stale control</button>';
              root.append(dialog);
              dialog.showModal();
              const popover = document.createElement('div');
              popover.id = 'shadow-stale-popover';
              popover.setAttribute('popover', 'manual');
              popover.textContent = 'Shadow top-layer stale popover';
              root.append(popover);
              popover.showPopover();
              const nonmodal = document.createElement('dialog');
              nonmodal.id = 'shadow-final-nonmodal';
              nonmodal.textContent = 'Final state is non-modal';
              root.append(nonmodal);
              nonmodal.showModal();
              nonmodal.close();
              nonmodal.show();
            }"""
        )
        frames = page.evaluate("() => window.__lfPresentation.frames")
        assert held, "the positive control did not hold the first state response"
        assert frames and all(frame["height"] > 0 for frame in frames), (
            f"the authored state was never laid out, so the paint gate tested nothing: {frames}"
        )
        assert not [frame for frame in frames if frame["stale"]], (
            f"authored state was visibly painted before replay: {frames}"
        )
        assert not [frame for frame in frames if frame["interactive"]], (
            f"authored state accepted a pointer before replay: {frames}"
        )
        assert not page.locator("#stale-control").evaluate(
            "element => { element.focus(); return document.activeElement === element; }"
        ), "authored state accepted keyboard focus before replay"
        assert not page.locator("#stale-dialog").is_visible(), (
            "authored top-layer content painted before replay"
        )
        assert not page.locator("#stale-dialog button").evaluate(
            "element => { element.focus(); return document.activeElement === element; }"
        ), "authored top-layer content accepted focus before replay"
        assert not page.locator("#stale-dialog").evaluate(
            """dialog => {
              const box = dialog.getBoundingClientRect();
              return dialog.contains(document.elementFromPoint(
                box.left + box.width / 2,
                box.top + box.height / 2,
              ));
            }"""
        ), "authored top-layer content accepted a pointer before replay"
        shadow_state = page.evaluate(
            """() => {
              const root = document.querySelector('#shadowed').shadowRoot;
              const dialog = root.querySelector('#shadow-stale-dialog');
              const control = dialog.querySelector('button');
              control.focus();
              const box = dialog.getBoundingClientRect();
              return {
                visibility: getComputedStyle(dialog).visibility,
                opacity: getComputedStyle(dialog).opacity,
                focused: root.activeElement === control,
                hit: dialog.contains(root.elementFromPoint(
                  box.left + box.width / 2,
                  box.top + box.height / 2,
                )),
              };
            }"""
        )
        assert shadow_state == {
            "visibility": "hidden",
            "opacity": "0",
            "focused": False,
            "hit": False,
        }, f"authored shadow top-layer content escaped before replay: {shadow_state}"
        shadow_popover = page.evaluate(
            """() => {
              const root = document.querySelector('#shadowed').shadowRoot;
              const popover = root.querySelector('#shadow-stale-popover');
              const box = popover.getBoundingClientRect();
              return {
                visibility: getComputedStyle(popover).visibility,
                opacity: getComputedStyle(popover).opacity,
                hit: popover.contains(root.elementFromPoint(
                  box.left + box.width / 2,
                  box.top + box.height / 2,
                )),
              };
            }"""
        )
        assert shadow_popover == {
            "visibility": "hidden",
            "opacity": "0",
            "hit": False,
        }, f"authored shadow popover escaped before replay: {shadow_popover}"
        assert page.locator("#stale-dialog").evaluate(
            "dialog => dialog.open && !dialog.matches(':modal')"
        ), "the held light dialog became modal before replay"
        assert page.evaluate(
            """() => {
              const dialog = document.querySelector('#shadowed').shadowRoot
                .querySelector('#shadow-stale-dialog');
              return dialog.open && !dialog.matches(':modal');
            }"""
        ), "the held shadow dialog became modal before replay"
        assert page.evaluate(
            """() => {
              const dialog = document.querySelector('#shadowed').shadowRoot
                .querySelector('#shadow-final-nonmodal');
              return dialog.open && !dialog.matches(':modal');
            }"""
        ), "the widget's final non-modal state did not stand before replay"
        assert page.get_by_role("button", name=re.compile("^Threads")).evaluate(
            "button => { button.focus(); return document.activeElement === button; }"
        ), "a held authored modal disabled the usable Threads chrome"
        page.evaluate(
            "document.querySelector('#shadowed').shadowRoot"
            ".querySelector('#shadow-stale-popover').hidePopover()"
        )
        assert all("Applying current decisions" in frame["note"] for frame in frames), (
            f"the boundary replaced the page with no useful visible state: {frames}"
        )
        painted = [i for i, frame in enumerate(frames) if frame["waitingPainted"]]
        assert painted, f"the waiting explanation was never painted: {frames}"
        assert painted == list(range(painted[0], len(frames))), (
            f"the waiting explanation disappeared while replay was still held: {frames}"
        )

        held.pop(0).continue_()
        page.wait_for_function(BOTH_STAMPS)
        expect(page.locator("#sug")).to_have_attribute("data-lf-state", "accept")
        expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
        expect(page.locator("#sug lf-old")).to_be_hidden()
        assert not page.locator("#stale-dialog").evaluate(
            "dialog => dialog.open || dialog.matches(':modal')"
        ), "replay retired a dialog but presentation promoted it anyway"
        assert page.evaluate(
            "document.querySelector('#shadowed').shadowRoot"
            ".querySelector('#shadow-stale-dialog').matches(':modal')"
        ), "a still-current deferred dialog was not promoted after replay"
        assert page.evaluate(
            """() => {
              const dialog = document.querySelector('#shadowed').shadowRoot
                .querySelector('#shadow-final-nonmodal');
              return dialog.open && !dialog.matches(':modal');
            }"""
        ), "a dialog whose final state was non-modal was promoted after replay"
        page.evaluate(
            "document.querySelector('#shadowed').shadowRoot"
            ".querySelector('#shadow-stale-dialog').close()"
        )
        assert page.evaluate("() => window.__lfPresentation.releases") == 1
        assert errors == []
    finally:
        page.close()


def test_a_current_workspace_choice_replaces_a_persisted_tray_during_replay(
    browser, serve
):
    """Restored chrome may neither publish stale asks nor replace a current choice.

    The tray was open on the prior visit and the log has since accepted its one
    suggestion. Holding the first replay makes the dangerous interval deterministic:
    discussion stays available, but the stale count, row, and bulk action stay withheld.
    Opening Threads during that interval replaces the remembered tray, and replay leaves
    the current workspace standing while it paints the accepted state directly.
    """
    url = serve(SHORT_SUGGESTION)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug",
            "action": "accept",
            "detail": {},
        },
    )
    context = browser.new_context(viewport={"width": 1200, "height": 900})
    priming = context.new_page()
    priming.goto(url, wait_until="load")
    priming.wait_for_function(BOTH_STAMPS)
    priming.evaluate("localStorage.setItem('lf-tray-up', 'decisions')")
    priming.close()

    held = []
    page = context.new_page()
    errors = watched(page)
    page.route("**/api/state*", lambda route: held.append(route))
    try:
        page.goto(url, wait_until="load")
        page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
        page.wait_for_function(
            "() => Number(getComputedStyle(document.body, '::after').opacity) > 0"
        )
        assert held, "the positive control did not hold the first state response"
        body = page.locator("body")
        expect(body).to_have_attribute("data-lf-tray", "decisions")
        expect(page.locator(".lf-decisions")).to_be_hidden()
        expect(page.locator(".lf-decisions-panel")).to_be_hidden()
        expect(page.locator(".lf-answer-all")).to_be_hidden()

        comments = page.get_by_role("button", name=re.compile("^Threads"))
        expect(comments).to_be_enabled()
        comments.click()
        expect(body).not_to_have_attribute("data-lf-tray", "decisions")
        expect(page.locator(".lf-general textarea")).to_be_editable()

        held.pop(0).continue_()
        page.wait_for_function(BOTH_STAMPS)
        expect(page.locator("#sug")).to_have_attribute("data-lf-state", "accept")
        expect(page.locator(".lf-decisions")).to_be_hidden()
        expect(page.locator(".lf-decisions-panel")).to_be_hidden()
        expect(page.locator(".lf-panel")).to_be_visible()
        expect(page.locator("button.lf-decisions-row")).to_have_count(0)
        expect(page.locator(".lf-answer-all")).to_be_hidden()
        assert errors == []
    finally:
        context.close()


def test_comments_wait_for_the_first_log_to_be_renderable(browser, serve):
    """Receiving state is not readiness while its message renderer is still loading."""
    url = serve(SHORT_SUGGESTION)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "text": "A preloaded **comment**",
        },
    )
    held = []
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.route("**/vendor/marked.esm.js", lambda route: held.append(route))
    try:
        with page.expect_request("**/vendor/marked.esm.js"):
            page.goto(url, wait_until="load")
        page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
        assert held, "the positive control did not hold the Markdown renderer"

        page.get_by_role("button", name=re.compile("^Threads")).click()
        expect(page.locator(".lf-empty")).to_have_text("Loading current threads…")
        expect(page.locator(".lf-thread")).to_have_count(0)

        held.pop(0).continue_()
        page.wait_for_function(BOTH_STAMPS)
        expect(page.locator(".lf-empty")).to_have_count(0)
        expect(page.locator(".lf-thread")).to_have_count(1)
        expect(page.locator(".lf-msg-body strong")).to_have_text("comment")
        assert errors == []
    finally:
        page.close()


def test_an_unavailable_first_poll_releases_a_useful_page(browser, serve):
    """Presentation waits for an answer, not necessarily state.

    When the first poll cannot reach the server there is no log to apply, so the honest
    page is the authored one under an offline banner. It must be visible rather than
    stranded behind the replay boundary, and the one failed answer releases it once."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.add_init_script(FIRST_PRESENTATION)
    page.route("**/api/state*", refuse)
    try:
        page.goto(serve(SHORT_SUGGESTION), wait_until="load")
        page.wait_for_function(
            "() => document.body.dataset.lfUpgraded === '1'"
            " && document.body.dataset.lfPresented === '1'"
        )
        expect(page.locator("main")).to_be_visible()
        expect(page.locator(".lf-status-text")).to_have_text(
            "Server offline — reconnecting. Keep this page open so pending changes can send."
        )
        assert page.locator("body").get_attribute("data-lf-applied") is None
        assert page.evaluate("() => window.__lfPresentation.releases") == 1
        assert errors == []
    finally:
        page.close()


def test_a_fast_first_replay_does_not_flash_the_waiting_surface(browser, serve):
    """A useful wait must not become a one-frame flash when there is no wait.

    The held first-poll test above proves that the waiting surface is a real useful
    screen. This takes its pixels as a reference, then records Chrome's actual compositor
    frames while the same local page opens and reloads with an immediate successful
    answer. Neither navigation may paint Leaf's held screen on its way to the ready page.
    Playwright disables Chrome's PaintHolding, so its reload may still contribute a blank
    platform frame; that is not a Leaf surface this runtime can remove. A DOM sample or a
    duration would only say the wait was paintable; the screencast says whether the
    reader's display was actually given its contentful pixels."""
    import base64

    from PIL import Image

    # The banner carries changing connection text and controls; the center of the page
    # is the stable region where Leaf's waiting explanation either did or did not reach
    # the compositor. Cropping both screenshots and screencast frames to that same region
    # makes exact pixels evidence about the surface under test rather than chrome churn.
    content_crop = (240, 140, 960, 800)

    def pixels(raw):
        image = Image.open(io.BytesIO(raw)).convert("RGB")
        return image.crop(content_crop).tobytes()

    def compositor_frames(page, navigate, ready):
        cdp = page.context.new_cdp_session(page)
        encoded = []

        def record(event):
            encoded.append(event["data"])
            cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})

        cdp.on("Page.screencastFrame", record)
        cdp.send(
            "Page.startScreencast",
            {"format": "png", "quality": 100, "everyNthFrame": 1},
        )
        navigate()
        ready()
        page.evaluate(RENDERED)
        cdp.send("Page.stopScreencast")
        assert encoded, "the compositor-frame positive control recorded nothing"
        return [pixels(base64.b64decode(frame)) for frame in encoded]

    delay_waiting_surface = """
      const setDelay = () => {
        if (!document.documentElement) return false;
        document.documentElement.style.setProperty('--lf-presentation-delay', '2s');
        return true;
      };
      if (!setDelay()) {
        const delayObserver = new MutationObserver(() => {
          if (setDelay()) delayObserver.disconnect();
        });
        delayObserver.observe(document, {childList: true});
      }
    """

    url = serve(SHORT_SUGGESTION)
    held = []
    waiting = browser.new_page(viewport={"width": 1200, "height": 900})
    waiting.route("**/api/state*", lambda route: held.append(route))

    def wait_until_loader_is_painted():
        waiting.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
        waiting.wait_for_function(
            """() => document.getAnimations().some(animation =>
              animation.animationName === 'lf-presentation-wait'
              && animation.playState === 'finished'
            )"""
        )

    held_frames = compositor_frames(
        waiting,
        lambda: waiting.goto(url, wait_until="load"),
        wait_until_loader_is_painted,
    )
    assert held, "the reference page never held the first state response"
    assert "Applying current decisions" in waiting.evaluate(
        "() => getComputedStyle(document.body, '::after').content"
    )
    waiting_pixels = pixels(waiting.screenshot())
    assert waiting_pixels in held_frames, (
        "the stable-content compositor detector missed a waiting surface held on screen"
    )
    held.pop(0).continue_()
    waiting.wait_for_function(BOTH_STAMPS)
    waiting.close()

    fresh = browser.new_page(viewport={"width": 1200, "height": 900})
    fresh.add_init_script(delay_waiting_surface)
    fresh_frames = compositor_frames(
        fresh,
        lambda: fresh.goto(url, wait_until="load"),
        lambda: fresh.wait_for_function(BOTH_STAMPS),
    )
    fresh.close()

    reloaded = browser.new_page(viewport={"width": 1200, "height": 900})
    reloaded.add_init_script(delay_waiting_surface)
    reloaded.goto(url, wait_until="load")
    reloaded.wait_for_function(BOTH_STAMPS)
    reload_frames = compositor_frames(
        reloaded,
        lambda: reloaded.reload(wait_until="load"),
        lambda: reloaded.wait_for_function(BOTH_STAMPS),
    )
    reloaded.close()

    failures = []
    if waiting_pixels in fresh_frames:
        failures.append("fresh open painted Leaf's waiting surface")
    if waiting_pixels in reload_frames:
        failures.append("reload painted Leaf's waiting surface")
    assert not failures, "; ".join(failures)


@pytest.mark.parametrize("reduced_motion", ["no-preference", "reduce"])
def test_a_slow_first_replay_releases_when_state_is_ready(
    browser, serve, reduced_motion
):
    """The delayed wait is real pixels, but it never holds a ready page.

    A paused CSS timeline makes both sides of the paint threshold observable without a
    race against module load or screenshot speed. An enormous dwell override is the
    bug-back: a runtime that still consults it cannot present within the test boundary,
    while replay readiness releases the current page directly.
    """
    from PIL import Image, ImageChops

    held = []
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion=reduced_motion
    )
    page = context.new_page()
    errors = watched(page)
    page.route("**/api/state*", lambda route: held.append(route))
    try:
        page.goto(serve(SHORT_SUGGESTION), wait_until="load")
        page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
        page.evaluate(
            """async () => {
              const wait = document.getAnimations()
                .find(a => a.animationName === 'lf-presentation-wait');
              wait.pause();
              await wait.ready;
              wait.currentTime = 0;
            }"""
        )
        before = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
        assert (
            page.evaluate(
                "() => Number(getComputedStyle(document.body, '::after').opacity)"
            )
            == 0
        ), "the waiting explanation painted before its threshold"

        page.evaluate(
            """() => {
              const wait = document.getAnimations()
                .find(a => a.animationName === 'lf-presentation-wait');
              const timing = wait.effect.getTiming();
              wait.currentTime = timing.delay + timing.duration;
            }"""
        )
        assert (
            page.evaluate(
                "() => Number(getComputedStyle(document.body, '::after').opacity)"
            )
            == 1
        ), "the waiting explanation did not paint beyond its threshold"
        after = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
        changed = ImageChops.difference(before, after)
        assert changed.getbbox() is not None, (
            "the computed waiting state changed without painting any pixels"
        )
        assert (
            sum(pixel != (0, 0, 0) for pixel in changed.get_flattened_data()) > 100
        ), "the waiting surface did not paint enough pixels to be a useful explanation"
        assert held, "the positive control did not hold the first state response"
        page.evaluate(
            """() => document.documentElement.style.setProperty(
              '--lf-presentation-dwell', '86400000ms'
            )"""
        )
        held.pop(0).continue_()
        page.wait_for_function("() => document.body.dataset.lfPresented === '1'")
        expect(page.locator("body > main")).to_be_visible()
        assert errors == []
    finally:
        context.close()


def test_a_startup_failure_never_presents_unapplied_authored_state(browser, serve):
    """A failed runtime may explain itself; it may not present a state it never read.

    A decision already stands in the log, then the registry fails after leaf.js has
    evaluated and taken responsibility for presentation. The reader must receive a
    fixed explanation rather than the authored alternatives underneath it: those words
    predate the decision, and showing them as the live page would be a false answer."""
    url = serve(SHORT_SUGGESTION)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug",
            "action": "accept",
            "detail": {},
        },
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.route(
        "**/registry.json",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body="{}"
        ),
    )
    try:
        with page.expect_console_message(
            predicate=lambda message: "page failed to start" in message.text
        ):
            page.goto(url, wait_until="load")
        page.wait_for_function(
            "() => Number(getComputedStyle(document.body, '::after').opacity) > 0"
        )

        explanation = page.evaluate("""() => {
            const pseudo = getComputedStyle(document.body, '::after');
            const fixed = pseudo.visibility !== 'hidden'
              && Number(pseudo.opacity) > 0
              && !['none', 'normal', ''].includes(pseudo.content);
            const named = [...document.body.querySelectorAll('*')].some(el =>
              el.checkVisibility({visibilityProperty: true})
              && /failed|offline|unavailable|reload/i.test(el.textContent));
            return fixed || named;
        }""")
        assert explanation, "startup failed into a blank page with no recourse"
        assert not page.locator("#sug lf-old").is_visible(), (
            "startup failed before the log was read, but the authored alternative was "
            "presented as though it were the reader's current decision"
        )
    finally:
        page.close()


def test_a_malformed_first_state_never_presents_unapplied_authored_state(
    browser, serve
):
    """A successful response that cannot be replayed must retain the safety gate."""
    url = serve(
        SHORT_SUGGESTION.replace(
            "</title>", '</title><meta name="lf-review" content="sign-off">', 1
        )
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug",
            "action": "accept",
            "detail": {},
        },
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.route(
        "**/api/state*",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body="not-json"
        ),
    )
    try:
        with page.expect_console_message(
            predicate=lambda message: "read failed" in message.text
        ):
            page.goto(url, wait_until="load")
        page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
        page.wait_for_function(
            "() => Number(getComputedStyle(document.body, '::after').opacity) > 0"
        )
        expect(page.locator(".lf-status-text")).to_have_text(
            "Page couldn't apply current state — reload"
        )
        expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
        expect(page.locator("body")).not_to_have_attribute("data-lf-applied", "1")
        assert not page.locator("#sug lf-old").is_visible(), (
            "state processing failed before replay, but authored state was presented"
        )
        expect(page.locator(".lf-signoff")).to_be_disabled()
    finally:
        page.close()


def test_a_root_module_failure_leaves_visible_recovery(browser, serve):
    """The CSS boundary takes responsibility before the root module evaluates.

    If that module itself throws, no runtime code exists to report the failure. The
    stylesheet must still keep authored decisions withheld and paint its fixed recovery
    message, so the safety boundary cannot turn a broken import into a blank page.
    """
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    failures = []
    page.on("pageerror", lambda error: failures.append(error))
    page.route(
        "**/leaf.js",
        lambda route: route.fulfill(
            status=200,
            content_type="text/javascript",
            body="throw new Error('root module failed')",
        ),
    )
    try:
        page.goto(serve(SHORT_SUGGESTION), wait_until="load")
        assert failures and "root module failed" in str(failures[0])
        page.wait_for_function(
            "() => Number(getComputedStyle(document.body, '::after').opacity) > 0"
        )
        recovery = page.evaluate(
            "() => getComputedStyle(document.body, '::after').content"
        )
        assert "Applying current decisions" in recovery and "reload" in recovery
        assert (
            page.locator("main").evaluate(
                "element => getComputedStyle(element).opacity"
            )
            == "0"
        )
    finally:
        page.close()


def test_a_page_the_suite_opens_has_read_the_log(browser, serve):
    """`open_page` promises a page that has finished becoming itself, and the log is half
    of what that means. The instrument is a refusal of the first `/api/state`. Replay then
    lands on the 2s retry, past the document's stamp, which is where a loaded Linux runner
    put it — so this press meets the same page those runs handed the test above, on any
    machine and in a second.

    Only a press can state it. A read lives through the interval, since `expect` re-decisions
    for five seconds and the retry lands in two; a keystroke into a page that has no
    versions yet is gone, and the chooser never opens."""
    url = serve(LONG_PAGE)
    _publish(
        serve.page_dir,
        2,
        LONG_PAGE.replace("Paragraph 3.", "Paragraph three."),
        "reworded a paragraph",
    )
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, color_scheme="light"
    )
    polls = itertools.count()
    context.route(
        "**/api/state*",
        lambda route: refuse(route) if next(polls) == 0 else route.continue_(),
    )
    try:
        page, errors = open_page(
            browser, url.replace("v1.html", "v2.html"), context=context
        )
        page.keyboard.press("v")
        expect(page.locator(".lf-version-menu")).to_be_visible()
        assert errors == []
    finally:
        context.close()


def test_restating_a_widget_is_how_a_version_takes_the_pen_back(browser, serve):
    """The other end of the rule above. Since the log outranks the markup, a
    version cannot revise a draft the user has rewritten — replay would paint
    their words straight back over it, and Claude's correction would reach nobody.
    `restated` is the one way markup wins: it retracts what came before it, so
    the new words render and the user sees the widget marked as one whose
    decision this version undid.

    It costs a word, where losing a decision used to cost nothing, which is the
    whole asymmetry: the failure that stays silent is now the one that needs
    saying out loud."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"text": DRAFT_EDITED},
        },
    )
    corrected = "Run the migration after deploying — it needs the new column."
    _publish(
        d,
        2,
        _draft_says(JOURNEY_V2, corrected, " restated"),
        "0041 needs the column; rewrote the draft",
    )

    page, errors = open_page(browser, url.replace("v1.html", "v2.html"))
    body = page.locator("#draft-ops .lf-draft-body")
    expect(body).to_have_text(corrected)
    # And the user is told, rather than left to notice: their edit is gone,
    # which without a mark reads exactly like a draft they never touched. Told in
    # words as well as in ink — the mark is an outline, which is the whole of what a
    # reader listening was getting, and this is the one paint on the page that says
    # something was taken away from them.
    expect(page.locator("#draft-ops[data-lf-restated]")).to_have_count(1)
    assert "rewritten since your decision" in page.locator("#draft-ops").aria_snapshot()
    assert errors == []
    page.close()


def test_a_retraction_outlives_the_version_that_made_it(browser, serve):
    """`restated` belongs to the version that rewrote the words, and to no other:
    v3 has nothing to declare, because it is not the one taking anything back.

    So the retraction cannot live in the markup, or v3's silence would read as
    "carry the decision" and hand the user's edit straight back — the same
    resurrection the branch removed, one version later and just as quiet.
    Stamping records it in the log instead, where it is a fact with a revision
    on it and every later revision inherits it for free."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"text": DRAFT_EDITED},
        },
    )
    corrected = "Run the migration after deploying — it needs the new column."
    _publish(d, 2, _draft_says(JOURNEY_V2, corrected, " restated"), "rewrote the draft")
    # v3 keeps v2's words and says nothing about the retraction, because
    # saying it again would be claiming to undo a decision already undone.
    _publish(d, 3, _draft_says(JOURNEY_V2, corrected), "unrelated copy edits")

    page, errors = open_page(browser, url.replace("v1.html", "v3.html"))
    expect(page.locator("#draft-ops .lf-draft-body")).to_have_text(corrected)
    assert errors == []
    page.close()

    # And the careful author who carries the attribute forward anyway — the habit
    # this whole design exists to break — is told which version already did it.
    (d / "index.html").write_text(_draft_says(JOURNEY_V2, corrected, " restated"))
    result = CliRunner().invoke(
        cli_model.cli,
        ["version", "stamp", str(d), "--text", "again"],
    )
    assert result.exit_code != 0
    assert "r2 already took that back" in result.output


def test_a_decision_not_yet_honored_wears_the_pending_mark(browser, serve):
    """One pass, every widget alike: a decided-and-unhonored state wears
    data-lf-pending, driven by the registry's x-state rather than remembered per
    widget — choose had its mark, edit its tint, and move had nothing, which is
    how a dragged card's fate stayed invisible once the toast faded. The mark
    clears the moment a version carries the decision, and the diff stays quiet
    about an honored move: the user's own drag is not news to them."""
    page, errors = open_page(browser, live_url(serve(JOURNEY_V1)))

    # A real drag — the pointer path, where the gesture gate and the poll meet.
    grip = page.locator("#card-x .lf-grip").bounding_box()
    dest = page.locator("#col-done").bounding_box()
    page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
    page.mouse.down()
    page.mouse.move(
        dest["x"] + dest["width"] / 2, dest["y"] + dest["height"] / 2, steps=15
    )
    page.mouse.up()
    expect(page.locator("#card-x[data-lf-pending]")).to_have_count(1)

    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    draft.locator("textarea").fill(DRAFT_EDITED)
    draft.get_by_role("button", name="Save").click()
    expect(page.locator("#draft-ops[data-lf-pending]")).to_have_count(1)

    # Both actions must be in the log before the honoring version publishes, and the
    # page is what says so: it sent them, and counts what has come back.
    d = serve.page_dir
    round_trip(page)

    _publish(
        d,
        2,
        _card_done(_draft_says(JOURNEY_V2, DRAFT_EDITED)),
        "honors the move and the edit",
    )
    wait_for_revision(page, 2)
    page.wait_for_function("() => document.querySelector('.lf-banner') !== null")
    # A poll has run once the status text resolves, so the pending pass has too.
    page.wait_for_function(
        "() => !document.querySelector('.lf-status-text').textContent.startsWith('Connecting')"
    )
    expect(page.locator("[data-lf-pending]")).to_have_count(0)

    # The diff's state half is quiet about the honored move: base state is the
    # base markup plus the fold as of it, which already has the card in Done.
    compare_with(page)
    page.wait_for_function(
        "() => document.querySelector('.lf-banner .lf-btn.on') !== null"
    )
    assert not page.evaluate(
        "document.getElementById('card-x').classList.contains('lf-ins-block')"
    ), "the user's own honored drag marked as a change"
    assert errors == []
    page.close()


def test_foreign_state_waits_until_a_live_drag_releases_the_page(browser, serve):
    """A poll may finish while Sortable owns real page nodes. Reconciliation leaves
    the whole page alone until the pointer releases them, then paints the same logged
    edit on the next pass."""
    page, errors = open_page(browser, serve(JOURNEY_V1))
    grip = page.locator("#card-x .lf-grip").bounding_box()
    page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
    page.mouse.down()
    page.mouse.move(grip["x"] + grip["width"] / 2 + 12, grip["y"] + 12, steps=4)
    expect(page.locator(".lf-dragging")).to_have_count(1)

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"text": "Foreign words held behind the drag."},
        },
    )
    told(page)
    expect(page.locator("#draft-ops .lf-draft-body")).to_have_text(DRAFT_TEXT)
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "0")

    page.mouse.up()
    told(page)
    expect(page.locator("#draft-ops .lf-draft-body")).to_have_text(
        "Foreign words held behind the drag."
    )
    assert errors == []
    page.close()


def test_the_diff_marks_a_card_the_author_relocated(browser, serve):
    """A pure state change has no text of its own, so the content diff was blind
    to it: a card in a new column read as nothing changed. The state half
    compares declared facets, so the author moving a card between versions —
    with no user action behind it — marks the card itself. The card alone:
    an id'd element nested inside it rode along rather than changing columns,
    and marking it too would double-tint one move."""
    noted = _CARD.replace(
        "</lf-card>", '<p id="card-x-note">A nested aside.</p></lf-card>'
    )
    v1 = JOURNEY_V1.replace(_CARD, noted)
    url = serve(v1)
    d = serve.page_dir
    _publish(
        d, 2, _card_done(JOURNEY_V1).replace(_CARD, noted), "moved the card to Done"
    )
    page, errors = open_page(browser, url.replace("v1.html", "v2.html"))
    compare_with(page)
    page.wait_for_function(
        "() => document.getElementById('card-x').classList.contains('lf-ins-block')"
    )
    assert not page.evaluate(
        "document.getElementById('card-x-note').classList.contains('lf-ins-block')"
    ), "the card's passenger marked as its own move"
    assert errors == []
    page.close()


def test_accepting_a_suggestion_resolves_its_thread_in_one_event(browser, serve):
    """Accepting answers the thread the change was written for, and the answer
    rides the accept itself — the wrapper holding the `resolves` mapping is
    retired by the honoring version, and a second POST could fail alone, leaving
    the outcome and the resolution disagreeing with no repair path. One event,
    read by both thread builders."""
    url = serve(
        JOURNEY_V1.replace('<h2 id="notes">', SUGGEST_BLOCK + '<h2 id="notes">'),
        events=(
            {
                "kind": "comment",
                "id": "c1",
                "author": "user",
                "revision": 1,
                "text": "does this take downtime?",
            },
        ),
    )
    d = serve.page_dir
    page, errors = open_page(browser, url)
    page.get_by_role("button", name=re.compile("^Accept the suggested change")).click()
    page.get_by_role("button", name=re.compile("^Threads")).click()
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    events = [
        json.loads(line) for line in (d / "comments.jsonl").read_text().splitlines()
    ]
    accept = next(e for e in events if e.get("kind") == "action")
    assert accept["action"] == "accept" and accept["detail"] == {"resolves": "c1"}
    assert not any(e.get("kind") == "resolve" for e in events)
    assert errors == []
    page.close()


def test_the_thread_follows_the_decision_that_still_stands(browser, serve):
    """The panel reports where the question currently stands, not that it was once
    answered. A second tab can reject a suggestion the first has already accepted —
    the controls are gone in the tab that decided, not in the one that hasn't
    polled — and the reader who turned the fix down would otherwise find their
    question filed away as answered by it, while the suggestion beside it read as
    rejected. Both readings come off the same log; here is where they have to
    agree in front of the reader.

    Then the same rule read the other way: `z` takes the reject back, the accept it
    superseded is the widget's answer once more, and the thread closes under it. The
    two ways an answer stops standing compose, and nothing is written down to say so:
    an `unresolve` posted where the thread reopened would be a second record of the
    same fact, and taking the reject back would leave it standing against the accept."""
    url = serve(
        JOURNEY_V1.replace('<h2 id="notes">', SUGGEST_BLOCK + '<h2 id="notes">'),
        events=(
            {
                "kind": "comment",
                "id": "c1",
                "author": "user",
                "revision": 1,
                "text": "does this take downtime?",
            },
        ),
    )
    d = serve.page_dir
    page, errors = open_page(browser, url)
    page.get_by_role("button", name=re.compile("^Accept the suggested change")).click()
    page.get_by_role("button", name=re.compile("^Threads")).click()
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")

    # What the other tab's press leaves in the log, made against the same version:
    # its own accept and reject controls are still standing, because it has not
    # heard about this one's decision yet.
    events_model.append_event(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-fix",
            "action": "reject",
            "detail": {},
        },
    )
    told(page)
    expect(page.locator("#sug-fix")).to_have_attribute("data-lf-state", "reject")
    expect(page.locator(".lf-details")).to_have_count(0)
    reopened = page.locator('.lf-threads > .lf-thread[data-id="c1"]')
    expect(reopened.locator(".lf-resolve")).to_have_count(1)

    # Offered here because the log says the reader made the reject; which tab they
    # were in is not something the log records, and not something a withdrawal
    # could turn on. The widget goes back to the markup and the surviving log is
    # replayed onto it, so what the press restores is the accept, not a blank slate.
    undo(page)
    expect(page.locator("#sug-fix")).to_have_attribute("data-lf-state", "accept")
    expect(reopened).to_have_count(0)
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    # What the log holds is the three gestures and not one word about the thread:
    # it was reopened and closed again by that log being read.
    assert [
        e.get("action", e["kind"])
        for e in events_model.read_events(d)
        if e["kind"] in ("action", "undo", "resolve", "unresolve")
    ] == ["accept", "reject", "undo"]
    assert errors == []
    page.close()


def test_startup_continues_while_the_registry_fetch_is_held(browser, serve):
    """The chrome and initial state read do not wait behind widget startup.

    That interval is real state, not a missing-registry fallback: the state answer waits
    unapplied until upgrades have captured the authored page, general Threads accepts a
    send but holds it until the layer identity arrives, and an anchored comment waits until
    upgrades have made the page's final words. The explicit gate proves each assertion runs
    on the intended side of the fetch rather than racing a timer.
    """
    gate_registry = """
      const nativeFetch = window.fetch.bind(window);
      window.lfRegistryGate = new Promise(resolve => window.lfReleaseRegistry = resolve);
      window.fetch = async (...args) => {
        const input = args[0];
        const url = typeof input === 'string' ? input : input.url;
        const path = new URL(url, location.href).pathname;
        if (path === '/registry.json') {
          window.lfRegistryBlocked = true;
          return window.lfRegistryGate.then(() => nativeFetch(...args));
        }
        const response = await nativeFetch(...args);
        if (path === '/api/state') window.lfInitialStateReceived = true;
        return response;
      };
    """
    html = JOURNEY_V1.replace(
        '<h2 id="notes">',
        """
<lf-milestones>
  <lf-milestone id="gate-milestone" status="active" tags="wood,solar">
    <strong>Build feeders</strong> Two classic models.
  </lf-milestone>
</lf-milestones>
<h2 id="notes">""",
    )
    page, errors = open_page(
        browser,
        serve(html, anchored=[("intro", SENTENCE)]),
        init_script=gate_registry,
        wait_until="domcontentloaded",
        # The held registry is this test's subject, so the upgrade stamp never lands and
        # waiting for it would hang out a whole timeout.
        upgraded=False,
    )
    page.wait_for_function("() => window.lfRegistryBlocked === true")
    page.wait_for_function("() => window.lfInitialStateReceived === true")
    expect(page.locator("body")).not_to_have_attribute(
        "data-lf-applied", re.compile(".")
    )
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    page.wait_for_function(
        "() => Number(getComputedStyle(document.body, '::after').opacity) > 0"
    )
    expect(page.locator("body > main")).to_be_hidden()
    expect(page.locator(".lf-banner")).to_be_visible()
    expect(page.get_by_role("button", name=re.compile("^Threads"))).to_be_enabled()
    expect(page.locator("#gate-milestone .lf-chips")).to_have_count(0)
    expect(page.locator("#draft-ops .lf-draft-body")).to_have_count(0)

    page.get_by_role("button", name=re.compile("^Threads")).click()
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(page.locator(".lf-empty")).to_have_text("Loading current threads…")
    expect(page.locator(".lf-thread")).to_have_count(0)
    page.locator(".lf-general textarea").fill("General comment during startup")
    page.locator(".lf-general").get_by_role("button", name="Send").click()
    expect(page.locator(".lf-thread")).to_have_count(0)
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0

    # Authored content is deliberately not selectable until replay can make it honest.
    expect(page.locator(".lf-composer")).to_be_hidden()

    page.evaluate("window.lfReleaseRegistry()")
    expect(page.locator(".lf-thread")).to_have_count(2)
    expect(page.locator("#gate-milestone .lf-chips")).to_have_count(1)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    page.wait_for_function("() => document.body.dataset.lfPresented === '1'")
    words = page.locator("#gate-milestone strong").bounding_box()
    assert words, "the upgraded milestone never produced selectable words"
    y = words["y"] + words["height"] / 2
    select(
        page,
        (words["x"] + 2, y),
        (words["x"] + words["width"] - 2, y),
    )
    expect(page.locator(".lf-fab")).to_be_visible()
    page.locator(".lf-fab").click()
    page.locator(".lf-composer textarea").fill("Still anchored?")
    page.locator(".lf-composer").get_by_role("button", name="Comment").click()

    expect(page.locator(".lf-thread")).to_have_count(3)
    expect(page.locator(".lf-thread .lf-quote.detached")).to_have_count(0)
    assert errors == []
    page.close()


def test_overlapping_polls_never_move_the_log_backwards(browser, serve):
    """Timer polls can overlap when one response is delayed. The append-only event
    sequence makes the older response unambiguously stale."""
    delay_second_state = """
      const nativeFetch = window.fetch.bind(window);
      let stateCalls = 0;
      window.fetch = async (...args) => {
        const input = args[0];
        const url = typeof input === 'string' ? input : input.url;
        const response = await nativeFetch(...args);
        if (new URL(url, location.href).pathname !== '/api/state') return response;
        stateCalls += 1;
        if (stateCalls !== 2) return response;
        const body = await response.text();
        window.lfDelayedPollCaptured = true;
        await new Promise(resolve => setTimeout(resolve, 3000));
        window.lfDelayedPollReleased = true;
        return new Response(body, {
          status: response.status,
          statusText: response.statusText,
          headers: response.headers,
        });
      };
    """
    # open_page's traffic watcher goes on outside this, so what it counts as answered is
    # what the page was handed — the held poll included, which is the whole subject here.
    page, errors = open_page(browser, serve(JOURNEY_V1), init_script=delay_second_state)
    page.get_by_role("button", name=re.compile("^Threads")).click()
    page.locator(".lf-general textarea").fill("Starts the slow poll")
    page.locator(".lf-general button").click()
    round_trip(page)
    # The second read, which the script above holds. The post's own append would
    # usually prompt it, but the post's answer can apply first and leave the stream
    # naming a reading the page already holds; this is a cause of its own.
    nudge(serve.page_dir)
    page.wait_for_function("() => window.lfDelayedPollCaptured === true")

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "newest-snapshot",
            "author": "user",
            "revision": 1,
            "text": "Newest snapshot stays rendered",
        },
    )
    # A later poll overtakes the held one and renders the newest log.
    told(page)
    expect(
        page.locator(".lf-thread", has_text="Newest snapshot stays rendered")
    ).to_have_count(1)
    # Then the stale answer arrives. One more poll after it is what proves the page
    # handled it and kept the thread, rather than being asked before it ever landed.
    page.wait_for_function("() => window.lfDelayedPollReleased === true")
    told(page)
    expect(
        page.locator(".lf-thread", has_text="Newest snapshot stays rendered")
    ).to_have_count(1)
    assert errors == []
    page.close()


def test_a_state_waiting_for_markdown_cannot_overwrite_a_newer_one(browser, serve):
    """Sequence order is judged again after the lazy Markdown import. A newer POST
    response can enter that await before an older held poll; when the shared import
    finishes, the older continuation must not repaint the log backwards."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.get_by_role("button", name=re.compile("^Threads")).click()
    panel_settled(page)

    older = []

    def hold_older_state(route):
        if older:
            refuse(route)
            return
        older.append(route)

    page.route("**/api/state*", hold_older_state)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Older **snapshot**",
        },
    )
    with page.expect_request("**/api/state"):
        pass
    page.wait_for_timeout(0)  # yield from the request event to its route callback
    assert len(older) == 1
    old_route = older[0]
    old_state = old_route.fetch().json()

    marked = []
    page.route("**/vendor/marked.esm.js", lambda route: marked.append(route))
    page.locator(".lf-general textarea").fill("Newest **snapshot**")
    with page.expect_request("**/vendor/marked.esm.js"):
        page.locator(".lf-general button").click()
    page.wait_for_timeout(0)  # yield from the request event to its route callback
    assert len(marked) == 1

    old_route.fulfill(json=old_state)
    page.title()  # let the old response join the shared import before releasing it
    marked[0].continue_()
    page.unroute("**/vendor/marked.esm.js")

    expect(page.locator(".lf-thread", has_text="Older snapshot")).to_have_count(1)
    expect(page.locator(".lf-thread", has_text="Newest snapshot")).to_have_count(1)
    assert errors == []
    page.close()


def test_a_page_hears_news_without_asking_for_it(browser, serve):
    """The page asks for state when its news stream says the page has moved, and
    otherwise not at all. A quiet page therefore makes no request — the poll made
    one every two seconds whether or not anything had happened — and an append
    reaches it in the time the stream takes to look (fifty milliseconds, where the
    poll left it up to two seconds), which `told` below waits through. The quiet
    three seconds are the half of this no faster poll could pass."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.get_by_role("button", name=re.compile("^Threads")).click()
    panel_settled(page)
    asked = _traffic(page).asked
    page.wait_for_timeout(3000)
    assert _traffic(page).asked == asked, "a quiet page asked for state on a timer"

    events_model.append_event(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "News."},
    )
    told(page)
    assert _traffic(page).asked == asked + 1
    expect(page.locator(".lf-thread", has_text="News.")).to_have_count(1)
    assert errors == []
    page.close()


def test_the_later_answer_wins_whichever_ask_it_answers(browser, serve):
    """Two reads cross on two sockets: the earlier ask is answered later, with the
    newer state. Nothing the log orders tells such answers apart when neither carries
    a new event — the status is not in the log — and the order the decisions went out in
    is the wrong order. Each answer says when the server took it, and the page keeps
    the later one without asking again."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    d = serve.page_dir
    text = page.locator(".lf-status-text")

    def declare(detail):
        files_model.write_json(
            d / "status.json",
            {"state": "working", "detail": detail, "ts": events_model.now_iso()},
        )

    # Every ask is held; the test answers them by hand, in the order that goes wrong.
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    with page.expect_request("**/api/state*"):
        declare("first")
    with page.expect_request("**/api/state*"):
        declare("second")
    page.wait_for_timeout(0)  # yield from the request event to its route callback
    # The stream restates its word every few seconds, and each restatement is a decision
    # while these stay unanswered, so there may be more than two. The first and the
    # last went out in that order, which is all that is asked of them.
    assert len(held) >= 2
    earlier, later = held[0], held[-1]
    # The later request is answered first; the earlier one after the page moves again.
    second = later.fetch().json()
    with page.expect_request("**/api/state*"):
        declare("third")
    page.wait_for_timeout(0)
    stale_request = held[-1]
    assert stale_request is not later
    third = earlier.fetch().json()
    later.fulfill(json=second)
    expect(text).to_have_text(re.compile(r"^Claude is working — second"))
    earlier.fulfill(json=third)
    told(page)
    expect(text).to_have_text(re.compile(r"^Claude is working — third"))
    # And an answer taken before the one the page holds is turned away however late
    # it lands and whichever request it answers: the third request, answered with the second
    # answer, must not put the status back.
    with page.expect_response("**/api/state*"):
        stale_request.fulfill(json=second)
    page.title()  # let the stale answer settle before reading the page again
    expect(text).to_have_text(re.compile(r"^Claude is working — third"))
    told(page)
    assert errors == []
    page.close()


def test_a_page_whose_read_failed_asks_again_on_its_own(browser, serve):
    """A wake-up the page could not act on is not lost. The stream says when the
    page has moved and cannot say it twice, so a read that failed — refused here, a
    dropped request in the world — is asked again on the page's own tick, the
    spacing a failed exchange has always had. Without that a page would sit under
    an offline banner until something else happened to it."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.get_by_role("button", name=re.compile("^Threads")).click()
    panel_settled(page)
    page.route("**/api/state*", refuse)
    with page.expect_event(
        "requestfailed", predicate=lambda request: "/api/state" in request.url
    ):
        events_model.append_event(
            serve.page_dir,
            {"kind": "comment", "author": "user", "revision": 1, "text": "Missed."},
        )
    expect(page.locator(".lf-status-text")).to_have_text(
        "Server offline — reconnecting. Keep this page open so pending changes can send."
    )
    page.unroute("**/api/state*")
    told(page)
    expect(page.locator(".lf-thread", has_text="Missed.")).to_have_count(1)
    expect(page.locator(".lf-status-text")).not_to_have_text(
        "Server offline — reconnecting. Keep this page open so pending changes can send."
    )
    assert errors == []
    page.close()


def test_a_page_hears_again_when_its_server_comes_back(browser, serve):
    """A server is stopped and started under an open tab whenever its layer is
    re-vendored, and the tab finds the new one on its own: the stream it held ended
    with the old server, and the browser reopens it. The page says the server is
    gone while it is, and reads again when the stream comes back, because the last
    thing it knew about the server is from before the silence."""
    url = serve(LONG_PAGE)
    page, errors = open_page(browser, url)
    page.get_by_role("button", name=re.compile("^Threads")).click()
    panel_settled(page)
    status = page.locator(".lf-status-text")
    port = serve.httpd.server_address[1]
    serve.httpd.shutdown()
    serve.httpd.server_close()
    expect(status).to_have_text(
        "Server offline — reconnecting. Keep this page open so pending changes can send."
    )

    httpd = hosting_model.LeafHTTPServer(
        ("127.0.0.1", port), http_model.handler_for(serve.page_dir, TOKEN)
    )
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    serve.servers.append(httpd)
    events_model.append_event(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Back."},
    )
    told(page)
    expect(page.locator(".lf-thread", has_text="Back.")).to_have_count(1)
    expect(status).not_to_have_text(
        "Server offline — reconnecting. Keep this page open so pending changes can send."
    )
    # The requests that failed while the server was down are the one thing the
    # console may hold; a page fault of the runtime's own would say something else.
    assert all("net::ERR" in error for error in errors), errors
    page.close()


def test_the_help_overlay_answers_to_one_owner(browser, serve):
    """Open or closed is state with one writer now — it was three writers and
    two classList read-backs, the exact shape the first norm forbids.

    A section is its title, so two drafts on a page are one heading and a project
    widget declaring under a heading a standard one already uses joins it. That is
    the scope talking rather than the declaration: "On a draft" names where the
    reader would be standing, and there is one such place however many modules
    have something to say about it. Sections used to key on their exact rows, so
    the same heading twice was two headings — and the reader, who has one keyboard
    and one draft in front of them, got the reference split in half."""
    html = JOURNEY_V1.replace(
        "</main>",
        '<lf-draft id="draft-second"><pre>A second editable draft.</pre></lf-draft></main>',
    )
    page, errors = open_page(browser, serve(html))
    page.evaluate(
        """async () => {
          const { keys } = await import('/runtime/widget-api.js');
          keys(document.body, 'On a draft',
               [{ id: 'test.project-widget', keys: ['F2'],
                  does: 'a project widget using the same heading' }]);
        }"""
    )
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_be_visible()
    expect(page.locator(".lf-help h3", has_text="On a draft")).to_have_count(1)
    expect(
        page.locator(".lf-help", has_text="a project widget using the same heading")
    ).to_be_visible()
    expect(page.locator(".lf-help", has_text="Edit the text in place")).to_be_visible()
    # Help is a scope: the table stands down behind it, so c must not work the
    # panel under the sheet.
    page.keyboard.press("c")
    expect(page.locator(".lf-panel")).to_be_hidden()
    expect(page.locator(".lf-help")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-help")).to_be_hidden()
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_be_visible()
    page.mouse.click(300, 600)
    expect(page.locator(".lf-help")).to_be_hidden()
    assert errors == []
    page.close()


def test_banner_reports_whether_anyone_is_attending(browser, serve, tmp_path, dead_pid):
    """The banner may claim no more than the page directory can prove. A watch that
    has stopped must read differently from a watch with nothing to report, because
    otherwise the user's only way to tell them apart is to ask.

    And a page nothing is behind must read differently from either, without reading as
    a fault: a standing page spends the night that way, so the words are the plain
    computed fact and the dot is not the amber it wears for a session falling behind."""
    page, _ = open_page(browser, serve(LONG_PAGE, comments=1))
    d = serve.page_dir
    # The banner's own dot: the leaves panel mirrors this page as a row, so a
    # bare .lf-dot resolves to that row's copy too.
    text, dot = page.locator(".lf-status-text"), page.locator(".lf-banner .lf-dot")
    UNHELD = (
        "No session holds this page. 1 update waiting."
        " It picks up again when a session does."
    )

    def declare(
        state,
        detail="",
        *,
        agent="Claude",
        handoff=False,
        quiet_for=0,
        turn_ended=None,
        session_pid=None,
        claimed=True,
    ):
        """`quiet_for` ages the claim; `turn_ended` says how long ago the Stop hook
        watched the turn behind it end. Separate seconds, because the case the second
        exists for is a claim that is not old at all."""
        ts = datetime.now().astimezone() - timedelta(seconds=quiet_for)
        status = {
            "state": state,
            "detail": detail,
            "ts": ts.isoformat(timespec="seconds"),
        }
        if handoff:
            status["handoff"] = True
        if claimed:
            record_claim(
                d,
                pid=session_pid or os.getpid(),
                agent=agent,
                turn_closed=None
                if turn_ended is None
                else (
                    datetime.now().astimezone() - timedelta(seconds=turn_ended)
                ).isoformat(timespec="seconds"),
            )
        else:
            service_model.claim_path(d).unlink(missing_ok=True)
        files_model.write_json(d / "status.json", status)
        told(page)

    declare("working", "revising the plan")
    expect(text).to_have_text(
        re.compile(r"^Claude is working — revising the plan \(.+\)$")
    )
    expect(dot).to_have_class(re.compile(r"\bworking\b"))

    declare("waiting")
    with live_watcher(d, page):
        expect(text).to_have_text("Claude awaits — select text to comment")
        expect(dot).to_have_class(re.compile(r"\blistening\b"))

        # A claim of work that has gone quiet is still a claim of work, and a live
        # watcher does not turn it into one. This read "Claude awaits — select text to
        # comment" once, which invited the reader to start something on a page already
        # mid-answer and dropped the only news it had: a delegate had been holding the
        # question for twenty minutes and nothing on the page said so. The words are
        # the ones the branch with no watcher uses for the same silence, minus its
        # remedy — nobody needs to touch a terminal for a comment to reach a live wait.
        declare("working", "revising the plan", quiet_for=20 * 60)
        expect(text).to_have_text(
            "Claude last checked in 20m ago: revising the plan. 1 update waiting."
        )
        expect(dot).to_have_class(re.compile(r"\baway\b"))

        # And with no detail it is the bare silence, which is the same sentence with
        # nothing to say after the colon rather than a second wording for it.
        declare("working", quiet_for=20 * 60)
        expect(text).to_have_text("Claude last checked in 20m ago. 1 update waiting.")

        # The same silence reached by evidence rather than by the clock. A claim is
        # written by a model's turn, and a turn ends without running anything — so
        # nothing writes its close, and the page could only ever find an abandoned
        # claim by outwaiting the rope above. The Stop hook watches that ending, and a
        # claim written before it is one no next turn and no delegate renewed across
        # it. Dated by the ending and not by the claim's own last word: "last checked
        # in just now" under an amber dot is the line arguing with the dot.
        declare("working", "revising the plan", quiet_for=6 * 60, turn_ended=5 * 60)
        expect(text).to_have_text(
            "Claude left this when its turn ended 5m ago: revising the plan."
            " 1 update waiting."
        )
        expect(dot).to_have_class(re.compile(r"\baway\b"))

        # The agent's own last word about the work and the ending of the turn that
        # wrote it land in the same second, which is what an ordinary turn looks like:
        # written no later than the ending is written by the turn that ended, and
        # renewed by nothing after it.
        declare("working", "revising the plan", quiet_for=5 * 60, turn_ended=5 * 60)
        expect(text).to_have_text(
            "Claude left this when its turn ended 5m ago: revising the plan."
            " 1 update waiting."
        )

        # A turn that has only just ended still holds it. The agent claims the work,
        # hands it to a delegate and ends the turn in the same second, and the
        # delegate's first note is a minute or so behind that — with no margin the
        # page would report every handoff as an abandonment and take it back again.
        declare("working", "revising the plan", quiet_for=60, turn_ended=30)
        expect(text).to_have_text(re.compile(r"^Claude is working — revising the plan"))
        expect(dot).to_have_class(re.compile(r"\bworking\b"))

        # And a delegate that does check in carries the claim past the ending on its
        # own: its note is written after the turn closed, by the one command that
        # writes both. The claim stops being the closed turn's to answer for, and the
        # rope above is what judges it from there.
        declare("working", "revising the plan", quiet_for=60, turn_ended=5 * 60)
        expect(text).to_have_text(re.compile(r"^Claude is working — revising the plan"))

        # What the page wants back, in the agent's words, where the reader arrives.
        # The whole line is the tooltip too: it is the first thing on the row to be
        # clipped, and a narrow window must not be why the decision goes unread.
        declare("waiting", "pick a storage engine")
        expect(text).to_have_text("Claude awaits — pick a storage engine")
        expect(text).to_have_attribute("title", "Claude awaits — pick a storage engine")

    # No watcher, but Claude checked in moments ago, so it is between turns.
    declare("waiting")
    expect(text).to_have_text(
        "Claude isn't watching right now. 1 update waiting. It picks them up next turn."
    )

    # The failure the whole mechanism exists for: `leaf wait` printed, set this
    # status, and Claude never came back. The handoff mark is what dates it.
    declare("working", "picking up 1 update", handoff=True, quiet_for=20 * 60)
    expect(text).to_have_text(
        "Claude last checked in 20m ago. 1 update waiting. Nudge it in the terminal."
    )
    expect(dot).to_have_class(re.compile(r"\baway\b"))

    # With nobody listening the same ending carries the remedy, because the reader's
    # next word has nowhere to land until a session picks the page up again.
    declare("working", "running the migration", quiet_for=6 * 60, turn_ended=5 * 60)
    expect(text).to_have_text(
        "Claude left this when its turn ended 5m ago. 1 update waiting."
        " Nudge it in the terminal."
    )
    expect(dot).to_have_class(re.compile(r"\baway\b"))

    # Claude's own status gets a far longer rope: the same silence is just a long turn.
    # No turn has closed under this claim, so the rope is the whole of what judges it.
    declare("working", "running the migration", quiet_for=10 * 60)
    expect(text).to_have_text(re.compile(r"^Claude is working — running the migration"))

    # A dead session needs no timeout at all — the owning pid is simply gone, so the
    # claim it left has nothing behind it however lately it was written.
    declare("working", "running the migration", session_pid=dead_pid)
    expect(text).to_have_text(UNHELD)
    # Grey, not the amber a session falling behind wears: nobody is on the line, which
    # is a page's arrangement rather than something for the user to chase.
    expect(dot).to_have_class(re.compile(r"^lf-dot\s*$"))

    # Nothing ever claimed the page — a server started outside an agent host. There is
    # no pid to ask after, so a claim made moments ago is evidence and still stands.
    declare("working", "running the migration", claimed=False)
    expect(text).to_have_text(re.compile(r"^Claude is working — running the migration"))

    # Once that claim goes quiet there is nothing left holding the page, and an hour of
    # silence on a page that stands for weeks is not a fault to report.
    declare("working", "running the migration", quiet_for=60 * 60, claimed=False)
    expect(text).to_have_text(UNHELD)

    declare("working", "revising the plan", agent="Codex")
    expect(text).to_have_text(re.compile(r"^Codex is working — revising the plan"))

    declare("idle")
    expect(text).to_have_text("Leaf closed")
    page.close()


def test_the_page_dates_a_claim_by_the_clock_that_wrote_it(browser, serve):
    """Every timestamp a seat reads out was written by the server; `Date.now()` is the
    machine holding the tab. A laptop an hour fast therefore called a claim made this
    minute an hour stale — on the banner, on a roster row and under every question at
    once, always in the same direction, with nothing in the timestamp to give it away.
    The poll carries the server's own now, so the offset is measured rather than
    assumed.

    It is the reader's clock that moves here, because that is the one of the two a page
    has to survive: the server writes the timestamps it later reads back and cannot
    disagree with itself, while the reader's machine is not the page's to correct."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    d = serve.page_dir
    text = page.locator(".lf-status-text")
    dot = page.locator(".lf-banner .lf-dot")

    def claim(detail):
        record_claim(d)
        files_model.write_json(
            d / "status.json",
            {"state": "working", "detail": detail, "ts": events_model.now_iso()},
        )
        told(page)

    claim("running the migration")
    expect(text).to_have_text(
        re.compile(r"^Claude is working — running the migration \(just now\)$")
    )

    # An hour fast. A fixed time rather than an installed clock, so the page's own
    # polling keeps running and the next reading is a real one.
    page.clock.set_fixed_time(datetime.now().astimezone() + timedelta(hours=1))
    # New words, so the line under test can only be one this reader painted after the
    # clock moved: an unchanged sentence would pass on the render before it.
    claim("waiting on the shard")
    expect(text).to_have_text(
        re.compile(r"^Claude is working — waiting on the shard \(just now\)$")
    )
    expect(dot).to_have_class(re.compile(r"\bworking\b"))
    assert errors == []
    page.close()


def test_a_thread_says_what_the_agent_is_doing_about_it(
    browser, serve, tmp_path, dead_pid
):
    """The banner says what the agent is doing; a work line says which of the reader's
    questions it is doing it about. Both are one claim written by one command
    (`leaf status … --on`), which is what makes a delegate's check-in keep the page's
    line true as well as its own thread's.

    A reader with three questions open and no replies under any of them cannot tell a
    question being worked from a question nobody has looked at, and the page holds the
    answer: the agent said so. What the log holds is what happened, so this is not in
    it — a sentence somebody rewrites every few minutes is a claim, and it is painted
    as provisional news rather than as a message, because the answer is still owed.

    Nothing deletes the line directly. The agent's next reply answers the claim;
    resolution hides it while the conversation is closed, and reopening reveals it
    again."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=2))
    d = serve.page_dir
    comments = [e for e in events_model.read_events(d) if e["kind"] == "comment"]
    held, other = comments[0]["id"], comments[1]["id"]
    page.keyboard.press("c")
    expect(page.locator(".lf-panel")).to_be_visible()
    work_line = page.locator(".lf-work-line")
    expect(work_line).to_have_count(0)

    def status(*args):
        assert (
            CliRunner().invoke(cli_model.cli, ["status", str(d), *args]).exit_code == 0
        )
        told(page)

    status("working", "reading the reconnect traces", "--on", held)
    # One line, on the thread it names: a mark that stood on every open thread would
    # say only that the agent is busy, which the banner above already says.
    expect(work_line).to_have_count(1)
    expect(work_line).to_have_text(
        re.compile(r"^Claude is on this — reading the reconnect traces\s*just now$")
    )
    expect(page.locator(f'.lf-thread[data-id="{held}"] .lf-work-line')).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{other}"] .lf-work-line')).to_have_count(
        0
    )
    # Under the words that asked and above the box that answers, so it reads in the
    # thread's own order: what you said, what has been said back, what is being done.
    assert page.evaluate(
        f"""() => {{
        const thread = document.querySelector('.lf-thread[data-id="{held}"]');
        const kids = [...thread.children];
        return kids.findIndex((el) => el.matches('.lf-work-line'))
                > kids.findLastIndex((el) => el.matches('.lf-msg.user'))
            && kids.findIndex((el) => el.matches('.lf-work-line'))
                < kids.findIndex((el) => el.matches('.lf-compose'));
    }}"""
    ), "the work line is not between the thread's last message and its reply box"

    # A later claim about the page as a whole is not an answer to the thread, so the
    # line stands: the two seats are one claim, and only one of them has been rewritten.
    status("working", "drafting v2")
    expect(page.locator(".lf-status-text")).to_have_text(
        re.compile(r"^Claude is working — drafting v2")
    )
    expect(work_line).to_have_count(1)
    expect(work_line).to_contain_text("reading the reconnect traces")

    # The answer is what ends it.
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": held,
            "revision": 1,
            "text": "The traces say it is the vendor's timer, not ours.",
        },
    )
    told(page)
    expect(page.locator(f'.lf-thread[data-id="{held}"] .lf-msg.claude')).to_have_count(
        1
    )
    expect(work_line).to_have_count(0)

    # And a claim the agent renews after answering stands again: its line is on the thread
    # a second time, which is a fact about now rather than about what was said.
    status("working", "re-running it against the rolling deploy", "--on", held)
    expect(work_line).to_have_count(1)

    # A conversation the reader has closed asks nothing and shows nothing, for the same
    # reason its reply box is gone.
    events_model.append_event(d, {"kind": "resolve", "author": "user", "parent": held})
    told(page)
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    expect(work_line).to_have_count(0)

    # Reopening restores a claim that no reply answered. The local line still goes
    # with the page claim it is part of: once nothing holds the page, it cannot keep
    # claiming work under a banner that says the opposite.
    events_model.append_event(
        d, {"kind": "unresolve", "author": "user", "parent": held}
    )
    told(page)
    expect(work_line).to_have_count(1)
    record_claim(d, pid=dead_pid)
    told(page)
    expect(page.locator(".lf-status-text")).to_have_text(
        re.compile(r"^No session holds this page\.")
    )
    expect(work_line).to_have_count(0)
    assert errors == []
    page.close()


def test_a_work_line_says_when_its_claim_has_gone_quiet(browser, serve, tmp_path):
    """One page holds one answer to how long is too long, at every seat that shows a
    claim of work.

    The banner cannot answer for this seat. Every `leaf status … --on` write refreshes
    the page's own line as well as the thread's, so one delegate still checking in keeps
    the banner green while another's claim ages beside the reader's question — the
    roster's dead-row failure one level down, reached by exactly the command that makes
    two delegates possible.

    The roster's answer is a word on the shared rope, and this says it the same way: a
    tint alone is silence to whoever is listening rather than looking, and a number
    alone leaves the reader doing the arithmetic against a threshold only the page
    knows. `ago` stays rendered whole beside the word rather than reworded to absorb
    it, so one elapsed line reads the same wherever it appears."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=1))
    d = serve.page_dir
    held = next(e for e in events_model.read_events(d) if e["kind"] == "comment")["id"]
    page.keyboard.press("c")
    expect(page.locator(".lf-panel")).to_be_visible()
    work_line = page.locator(".lf-work-line")

    def claim(claim_ts, session="s"):
        """A page claim made now, carrying local work last renewed whenever."""
        files_model.write_json(
            d / "status.json",
            {
                "state": "working",
                "detail": "rerunning the failing shard",
                "ts": events_model.now_iso(),
                "work": [
                    {
                        "id": "trace-check",
                        "subject": {"kind": "thread", "id": held},
                        "detail": "reading the reconnect traces",
                        "ts": claim_ts,
                        "after": next(
                            e["seq"]
                            for e in events_model.read_events(d)
                            if e["id"] == held
                        ),
                        "agent": "Claude",
                        "session": session,
                    }
                ],
            },
        )
        told(page)

    claim(events_model.now_iso())
    # A claim somebody is keeping says nothing about silence.
    expect(work_line).to_have_count(1)
    expect(work_line).not_to_contain_text("quiet")

    quiet_ts = (datetime.now().astimezone() - timedelta(minutes=40)).isoformat(
        timespec="seconds"
    )
    claim(quiet_ts)
    # The page's own line is as fresh as it was, which is the whole case: this is two
    # delegates diverging, not a page that has gone quiet all over.
    expect(page.locator(".lf-status-text")).to_have_text(
        re.compile(r"^Claude is working — rerunning the failing shard")
    )
    expect(work_line).to_contain_text("quiet")
    expect(work_line.locator("time")).to_have_text("40m ago")

    # The other question the banner asks, asked here too: a claim left behind by a turn
    # that ended is quiet without waiting out the rope. Six minutes is nothing on that
    # rope — what dates this one is the ending, and the page's own line stays green
    # beside it because a second delegate is still renewing the claim.
    record_claim(
        d,
        turn_closed=(datetime.now().astimezone() - timedelta(minutes=5)).isoformat(
            timespec="seconds"
        ),
    )
    claim(
        (datetime.now().astimezone() - timedelta(minutes=6)).isoformat(
            timespec="seconds"
        )
    )
    expect(page.locator(".lf-status-text")).to_have_text(
        re.compile(r"^Claude is working — rerunning the failing shard")
    )
    expect(work_line).to_contain_text("quiet")
    expect(work_line.locator("time")).to_have_text("6m ago")

    # Turn closure belongs to one exact session. An orchestrator ending its turn is
    # no evidence that a delegate abandoned a different update.
    record_claim(
        d,
        id="orchestrator",
        turn_closed=(datetime.now().astimezone() - timedelta(minutes=5)).isoformat(
            timespec="seconds"
        ),
    )
    claim(
        (datetime.now().astimezone() - timedelta(minutes=6)).isoformat(
            timespec="seconds"
        ),
        session="delegate",
    )
    expect(work_line).not_to_contain_text("quiet")
    expect(work_line.locator("time")).to_have_text("6m ago")

    # And it goes when the claim is kept again, so the word tracks the claim rather
    # than latching on the first time it is late.
    record_claim(d)
    claim(events_model.now_iso())
    expect(work_line).not_to_contain_text("quiet")
    expect(work_line).to_have_count(1)
    assert errors == []
    page.close()


def test_the_tab_wears_what_the_banner_says(browser, serve, tmp_path, dead_pid):
    """The judgment's third seat, and the only one a reader with six leaves open in a
    row of tabs can see without opening any. The mark is the vendored icon.svg and the
    runtime paints the element it declares in whatever colour the dot is wearing, so the
    tab and the banner are one fact read twice: a palette written out again for the tab
    would be free to drift from the theme the day a project overrode a token, and drift
    silently, since a tab nobody is watching closely is exactly the case this is for.

    What a copy does with all of it is the export section's
    (test_a_copy_wears_the_mark_and_claims_no_session)."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    d = serve.page_dir

    def tone(want, why):
        try:
            return page.wait_for_function(TAB_TONE, arg=want).json_value()
        except PlaywrightTimeout:
            # The console with it: a mark the runtime refuses reads here as a tab with
            # no tone on it, and the reason it refused is the only thing that says why.
            found = page.evaluate(TAB_AND_DOT, want)
            pytest.fail(
                f"the tab never said {why} as the banner does: {found} {errors}"
            )

    def declare(state, **status):
        files_model.write_json(
            d / "status.json",
            {"state": state, "ts": events_model.now_iso(), **status},
        )
        told(page)

    # `page init` leaves a fresh working claim, so the tab arrives already saying so.
    working = tone("working", "working")
    declare("waiting")
    with live_watcher(d, page):
        awaits = tone("listening", "awaits")
    # The distinctness is the half agreement alone can't prove: a tab painted once and
    # never again agrees with a dot that never moved either, and the two states a reader
    # is choosing between — this page wants me, that one is busy — are exactly the pair
    # that would collapse.
    assert awaits != working, (
        f"a page awaiting its reader wears the same tab as one that is working ({awaits})"
    )

    # The claimant is gone, so nothing is behind the page: grey in the banner, and grey
    # in the tab, which is the whole of what the reader can see of it from a tab strip.
    record_claim(d, pid=dead_pid)
    unheld = tone("", "unheld")
    assert unheld not in (
        working,
        awaits,
    ), f"a page nothing holds wears a tab claiming a session ({unheld})"

    # And the mark itself is an image the browser will render, which is the one thing
    # a string comparison above cannot say: an SVG this file mangles decodes to nothing
    # and shows as a blank tab, with no error anywhere to find it by.
    page.evaluate("""() => {
        const img = new Image();
        globalThis.__lfTabMarkWidth = null;
        globalThis.__lfTabMarkImage = img;
        const done = (width) => {
          globalThis.__lfTabMarkWidth = width;
          delete globalThis.__lfTabMarkImage;
        };
        img.onload = () => done(img.naturalWidth);
        img.onerror = () => done(0);
        img.src = document.querySelector('link[rel=icon]').getAttribute('href');
    }""")
    page.wait_for_function(
        "() => globalThis.__lfTabMarkWidth !== null",
        timeout=render_checks_model.SERVED_TIMEOUT_MS,
    )
    drawn = page.evaluate("() => globalThis.__lfTabMarkWidth")
    assert drawn > 0, "the tab's mark is not an image the browser can decode"
    assert errors == []
    page.close()


def test_a_comment_follows_one_runtime_datum_through_reconciliation(browser, serve):
    """Runtime-supplied words are readable but are not authored prose, and their stable
    key—not a text node, equal display text, or current order—owns an anchored comment.

    Reconciliation replaces every row to exercise the destructive path. The first
    refresh reorders two equal values; a quote-only anchor either follows document order
    or detaches. The second changes the intended value while leaving its old text on the
    other row; silently following that text would move the comment to another fact. The
    honest result is an outline on the same datum, with the original quote retained in
    the thread as what the reader commented on.
    """
    url = data_projection_page(serve)
    page, errors = open_page(browser, url)

    readings = page.evaluate("""() => import('/runtime/widget-api.js').then(leaf => {
      const lede = document.querySelector('#lede');
      const datum = document.querySelector('[data-lf-datum="api"]');
      return {
        prose: [leaf.says(lede), leaf.wrote(lede)],
        datum: [leaf.says(datum), leaf.wrote(datum), datum.textContent],
      };
    })""")
    assert readings == {
        "prose": ["Live status follows.", "Live status follows."],
        "datum": ["Ready", "", "ReadyInspect"],
    }, "authored prose, projected data, and runtime apparatus became conflated"

    api = page.locator('[data-lf-datum="api"]')
    api.click(click_count=3)
    expect(page.locator(".lf-fab")).to_be_visible()
    page.locator(".lf-fab").click()
    page.locator(".lf-composer textarea").fill("Which readiness check is this?")
    page.get_by_role("button", name="Comment", exact=True).click()
    round_trip(page)

    comment = next(e for e in sent_events(serve.page_dir) if e["kind"] == "comment")
    assert comment["anchor"] == {
        "section": "deployments",
        "datum": "api",
        "quote": "Ready",
    }

    data_model.cmd_data_set(
        serve.page_dir,
        "deployments",
        [
            {"key": "worker", "value": "Ready"},
            {"key": "api", "value": "Ready"},
        ],
    )
    page.wait_for_function("""() => {
      const mark = [...(CSS.highlights.get('lf-mark') ?? [])][0];
      return mark?.startContainer?.isConnected
        && mark.startContainer.parentElement.dataset.lfDatum === 'api'
        && document.querySelector('#deployments').firstElementChild.dataset.lfDatum
          === 'worker';
    }""")

    data_model.cmd_data_set(
        serve.page_dir,
        "deployments",
        [
            {"key": "worker", "value": "Ready"},
            {"key": "api", "value": "Running"},
        ],
    )
    expect(page.locator('[data-lf-datum="api"]')).to_have_class(
        re.compile(r"\blf-mark-el\b")
    )
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0, (
        "the comment followed its old display text onto the other datum"
    )
    expect(page.locator(".lf-thread .lf-quote")).to_contain_text("Ready")
    expect(page.locator(".lf-thread .lf-quote")).not_to_have_class(
        re.compile(r"\bdetached\b")
    )

    screen = render_checks_model.evaluate_probe(page, "paperWords")
    page.emulate_media(media="print")
    paper = render_checks_model.evaluate_probe(page, "paperWords")
    assert paper == screen, "paper dropped or rewrote projected data"
    assert errors == []
    page.close()


def test_an_export_carries_runtime_data_as_a_labelled_snapshot(
    browser, serve, tmp_path, monkeypatch
):
    """Export cannot refresh data after its scripts leave, so it preserves the rendered
    snapshot and the projection/key labels that say what kind of words these are. Dropping
    the generated rows would make the file incomplete; keeping the widget module would
    make it pretend the dead snapshot was still live.
    """
    url = data_projection_page(serve)
    module = serve.page_dir / "widgets" / "lf-feed.js"
    module.write_text(
        module.read_text()
        .replace(
            "import {offer, projectData, watchData}",
            "import {offer, projectData, settle, watchData}",
        )
        .replace(
            "  connectedCallback() {",
            "  connectedCallback() {\n"
            "    settle(new Promise(resolve => setTimeout(resolve, 750)));",
        )
    )
    native_page_state = http_model.Handler.page_state

    def delayed_page_state(handler, view_revision=None):
        time.sleep(0.5)
        return native_page_state(handler, view_revision)

    monkeypatch.setattr(http_model.Handler, "page_state", delayed_page_state)
    out = tmp_path / "data-copy.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir))

    page = browser.new_page()
    errors = watched(page)
    page.goto(out.as_uri(), wait_until="load")
    rows = page.locator('#deployments > [data-lf-projection="deployments"]')
    expect(rows).to_have_count(2)
    assert rows.evaluate_all(
        "els => els.map(el => [el.dataset.lfDatum, el.textContent])"
    ) == [["api", "Ready"], ["worker", "Ready"]]
    assert page.locator("script").count() == 0, (
        "the snapshot still claims it can refresh"
    )
    assert errors == []
    page.close()


def test_an_older_data_response_cannot_replace_a_newer_snapshot(browser, serve):
    """Overlapping reads order data by its own revision, not by arrival time."""
    delay_second_state = """
      const nativeFetch = window.fetch.bind(window);
      let stateCalls = 0;
      window.fetch = async (...args) => {
        const input = args[0];
        const url = typeof input === 'string' ? input : input.url;
        const response = await nativeFetch(...args);
        if (new URL(url, location.href).pathname !== '/api/state') return response;
        stateCalls += 1;
        if (stateCalls !== 2) return response;
        const body = await response.text();
        window.lfOldDataCaptured = true;
        await new Promise(resolve => setTimeout(resolve, 3000));
        window.lfOldDataReleased = true;
        return new Response(body, {
          status: response.status,
          statusText: response.statusText,
          headers: response.headers,
        });
      };
    """
    page, errors = open_page(
        browser, data_projection_page(serve), init_script=delay_second_state
    )
    # The second read, which the script above holds: the page reads when told to.
    nudge(serve.page_dir)
    page.wait_for_function("() => window.lfOldDataCaptured === true")

    data_model.cmd_data_set(
        serve.page_dir,
        "deployments",
        [
            {"key": "api", "value": "Running"},
            {"key": "worker", "value": "Ready"},
        ],
    )
    expect(page.locator('[data-lf-datum="api"]')).to_contain_text("Running")
    page.wait_for_function("() => window.lfOldDataReleased === true")
    told(page)
    expect(page.locator('[data-lf-datum="api"]')).to_contain_text("Running")
    assert errors == []
    page.close()


def test_new_data_in_a_stale_event_response_is_still_accepted(browser, serve):
    """Event sequence and source revision are independent coordinates.

    A crossed response may be behind the rendered log while carrying the latest source.
    Dropping the whole response at the event gate would make live data depend on an
    unrelated comment arriving first.
    """
    page, errors = open_page(browser, data_projection_page(serve))
    older = page.evaluate("async () => await (await fetch('/api/state')).json()")
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "newer-event",
            "author": "user",
            "revision": 1,
            "text": "This event must not disappear.",
        },
    )
    told(page)
    expect(
        page.locator(".lf-thread", has_text="This event must not disappear")
    ).to_have_count(1)

    crossed = []

    def older_events_with_new_data(route):
        response = route.fetch()
        state = response.json()
        if state["data"]["revision"] < 2:
            route.fulfill(status=response.status, json=state)
            return
        state["events"] = older["events"]
        state["browser"] = older["browser"]
        crossed.append(True)
        route.fulfill(status=response.status, json=state)

    page.route("**/api/state*", older_events_with_new_data)
    data_model.cmd_data_set(
        serve.page_dir,
        "deployments",
        [
            {"key": "api", "value": "Running"},
            {"key": "worker", "value": "Ready"},
        ],
    )
    expect(page.locator('[data-lf-datum="api"]')).to_contain_text("Running")
    assert crossed, "the data revision never arrived beside the stale event tail"
    expect(
        page.locator(".lf-thread", has_text="This event must not disappear")
    ).to_have_count(1)
    assert errors == []
    page.close()


def test_data_subscriptions_use_own_keys_and_failed_mounts_leave_no_listener(
    browser, serve
):
    """Source names are data, including names inherited by a plain JS object.

    A subscriber is also a package mount boundary: if its first render fails, later
    polls must not keep calling a listener whose widget never finished connecting.
    """
    page, errors = open_page(browser, data_projection_page(serve))
    result = page.evaluate(
        """async () => {
          const {watchData} = await import('/runtime/widget-api.js');
          const widget = document.querySelector('lf-feed');
          widget.removeAttribute('source');
          let unbound = 'not-called';
          const stopUnbound = watchData(widget, 'rows', snapshot => { unbound = snapshot; });
          stopUnbound();
          widget.setAttribute('source', 'constructor');
          let absent = 'not-called';
          const stop = watchData(widget, 'rows', snapshot => { absent = snapshot; });
          stop();

          const captured = [];
          const stopCaptured = watchData(widget, 'rows', snapshot => { captured.push(snapshot); });
          widget.setAttribute('source', 'deployments');
          document.dispatchEvent(new Event('lf-data'));
          stopCaptured();

          let failedCalls = 0;
          let message = null;
          try {
            watchData(widget, 'rows', () => {
              failedCalls += 1;
              throw new Error('mount failed');
            });
          } catch (error) {
            message = error.message;
          }
          document.dispatchEvent(new Event('lf-data'));
          return {unbound, absent, captured, failedCalls, message};
        }"""
    )
    assert result == {
        "unbound": None,
        "absent": None,
        "captured": [None, None],
        "failedCalls": 1,
        "message": "mount failed",
    }
    assert errors == []
    page.close()


def test_data_notification_waits_for_a_version_activation(browser, serve):
    """A crossed data response may advance its revision during activation, but its
    subscribers cannot paint the old or half-upgraded document.

    Hold the view transition after the replacement document has mounted. A newer source
    response arrives while that activation still owns the page. Its value should render
    only after the activation releases.
    """
    activation_probe = """
      window.__lfTransitionHeld = false;
      window.__lfDataDuringActivation = false;
      window.__lfSawDataRevisionTwo = false;
      const nativeFetch = window.fetch.bind(window);
      window.fetch = async (...args) => {
        const response = await nativeFetch(...args);
        const input = args[0];
        const url = typeof input === 'string' ? input : input.url;
        if (new URL(url, location.href).pathname === '/api/state') {
          response.clone().json().then(state => {
            if (state.data?.revision >= 2) window.__lfSawDataRevisionTwo = true;
          });
        }
        return response;
      };
      document.addEventListener('lf-data', () => {
        const datum = document.querySelector('[data-lf-datum="api"]');
        if (window.__lfTransitionHeld && datum?.textContent.includes('Running'))
          window.__lfDataDuringActivation = true;
      });
      document.startViewTransition = update => {
        const ready = Promise.resolve();
        const finished = Promise.resolve()
          .then(update)
          .then(() => {
            window.__lfTransitionHeld = true;
            return new Promise(resolve => {
              window.__lfReleaseTransition = () => {
                window.__lfTransitionHeld = false;
                resolve();
              };
            });
          });
        return {ready, finished};
      };
    """
    page, errors = open_page(
        browser, live_url(data_projection_page(serve)), init_script=activation_probe
    )
    d = serve.page_dir
    current = (d / "versions" / "v1.html").read_text()
    _publish(
        d,
        2,
        current.replace("Live status follows.", "Live status follows now."),
        "refreshed the page",
    )
    page.wait_for_function("() => window.__lfTransitionHeld === true")

    data_model.cmd_data_set(
        d,
        "deployments",
        [
            {"key": "api", "value": "Running"},
            {"key": "worker", "value": "Ready"},
        ],
    )
    page.wait_for_function("() => window.__lfSawDataRevisionTwo === true")
    page.wait_for_timeout(100)
    assert not page.evaluate("() => window.__lfDataDuringActivation"), (
        "a source subscriber painted while version activation still owned the document"
    )

    page.evaluate("() => window.__lfReleaseTransition()")
    expect(page.locator('[data-lf-datum="api"]')).to_contain_text("Running")
    expect(page.locator("#lede")).to_have_text("Live status follows now.")
    assert errors == []
    page.close()
