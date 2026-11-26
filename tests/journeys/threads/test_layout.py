"""Tests scheduled by the measured cost of their boundary."""

import io

import pytest
from browser.threads import LANDING_WORDS, summarize_thread
from interact_support import append_carried_log_record
from PIL import Image, ImageStat
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_harness import open_page, resized

from leaf.source.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("forced", [False, True])
@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_words_scrolled_past_a_card_head_show_nowhere_above_it(
    engine, forced, request, serve
):
    """Wherever the card's transcript is scrolled, its stuck head stands on the line
    of the card's actions, and the focus-ring room above that line shows no words,
    in forced colours too, which drop shadows. Firefox can stick a head at its subgrid
    scroller's edge, past the room, so the name stands above the actions and words
    show over Resolve; in Chromium they can show above the name. Nor do words show
    beneath the actions, a summary's included, and the head row holding the line
    lends them its ground: an arriving message's tint runs behind them rather than
    being cut by the actions' own paper box whenever the card is scrolled."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Opening turn. " + LANDING_WORDS, {"section": "how-store"}
    )
    turns = [
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent" if turn % 2 else "user",
                "parent": root,
                "text": f"Turn {turn}. " + LANDING_WORDS,
            },
        )
        for turn in range(1, 10)
    ]
    # A summary's words have no head of their own, and pass beneath the actions too.
    summarize_thread(serve.page_dir, turns[0]["id"], turns[1]["id"], LANDING_WORDS)
    page = open_page(request.getfixturevalue(engine), url)
    resized(page, 1200, 600)
    if forced:
        page.emulate_media(forced_colors="active")
    page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
    transcript = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'
        " > .lf-thread-transcript"
    )
    expect(transcript).to_be_visible()
    rendered(page)
    travel = transcript.evaluate("box => box.scrollHeight - box.clientHeight")
    # Through the first messages, including where one pushes the last one's head off.
    assert travel > 300, travel
    actions = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'
        " > .lf-margin-thread-controls"
    )

    def shot(clip, hidden=None):
        toggle = "row => { for (const c of row.children) c.style.visibility = '%s'; }"
        if hidden:
            hidden.evaluate(toggle % "hidden")
        image = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
        if hidden:
            hidden.evaluate(toggle % "")
        return image

    def spread(image):
        low, high = image.convert("L").getextrema()
        return high - low

    for scroll in range(0, 300, 7):
        transcript.evaluate("(box, y) => { box.scrollTop = y; }", scroll)
        rendered(page)
        reading = transcript.evaluate(
            r"""box => {
              const controls = box.parentElement
                .querySelector(':scope > .lf-margin-thread-controls');
              const edge = box.getBoundingClientRect().top + box.clientTop;
              const head = [...box.querySelectorAll('.lf-msg-head')]
                .find(head => head.getBoundingClientRect().bottom > edge + 1);
              const at = head.getBoundingClientRect();
              const card = box.parentElement.getBoundingClientRect();
              return {edge, head: at.top, left: card.left, right: card.right,
                pushed: at.bottom >= head.parentElement.getBoundingClientRect().bottom - 1,
                line: controls.getBoundingClientRect().top,
                actions: controls.getBoundingClientRect().toJSON(),
                // The focus-ring room, which the transcript's landings also keep.
                ring: parseFloat(getComputedStyle(box).scrollPaddingTop),
                event: head.parentElement.dataset.lfEvent};
            }"""
        )
        # A head the next message pushes off rises with it; every other stands on the
        # actions' line or below it.
        assert reading["pushed"] or reading["head"] >= reading["line"] - 0.5, (
            scroll,
            reading,
        )
        assert reading["line"] - reading["edge"] >= reading["ring"], reading
        # Beneath the controls, with the paper their row lays under the heads.
        beneath = {
            side: reading["actions"][side] for side in ("x", "y", "width", "height")
        }
        ground = shot(beneath, hidden=actions)
        assert spread(ground) < 40, (scroll, reading)
        # Where no head holds the line, as over a summary, words run to the edge as
        # they do anywhere a transcript is cut.
        if reading["head"] > reading["line"] + 0.5:
            continue
        if not forced and not reading["pushed"]:
            # The head holding the line lends its arrival tint to the actions' track.
            held = transcript.locator(f'.lf-msg[data-lf-event="{reading["event"]}"]')
            held.evaluate("m => m.style.setProperty('--lf-msg-arrival', '1')")
            rendered(page)
            tinted = shot(beneath, hidden=actions)
            held.evaluate("m => m.style.removeProperty('--lf-msg-arrival')")
            rendered(page)
            assert spread(tinted) < 40, (scroll, reading)
            blue = ImageStat.Stat(ground).mean[2] - ImageStat.Stat(tinted).mean[2]
            assert blue > 20, (scroll, blue, reading)
        room = reading["head"] - reading["edge"]
        if room < 1:
            continue
        band = shot(
            {
                "x": reading["left"],
                "y": reading["edge"],
                "width": reading["right"] - reading["left"],
                "height": room,
            }
        )
        assert spread(band) < 40, (scroll, reading)
