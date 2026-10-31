"Where an open margin thread card stands beside its target, and how it holds still\nthrough news, presses, reflows and scrolls, panes included."

from datetime import datetime, timedelta

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import HOLD_MOTION, PANEL_PAGE, panel_comment
from render_harness import (
    ROOT,
    leaf_page,
    open_page,
    regions_side_by_side,
    resized,
    scroll_settled,
    ticked,
    told,
)

from leaf import thread as thread_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.watch_shifts
def test_an_open_card_takes_news_without_moving_its_controls(browser, serve):
    """The card keeps the width it opened at, so a longer step wraps inside it rather
    than carrying Resolve, Close and Send sideways. Read idle, a step shows at once and
    the card grows down past its reply row. While the user writes, a step and an
    answer wait behind the thread's notice, as a held reply does in a seat, so nothing
    moves. Pressing the notice shows them under the press: the head row stays and
    the card grows down, keeping the draft's words."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Make the banner quieter", {"section": "h-how"}
    )
    address = {"parent": root, "responds": root}
    thread_model.post_reply(
        serve.page_dir, address, "Reading the banner's styles.", ephemeral=True
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-margin-marker").first.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    words = preview.locator(".lf-thread-working-words")
    expect(words).to_have_text("Reading the banner's styles")
    rendered(page)
    controls = {
        name: preview.get_by_role("button", name=name, exact=True)
        for name in ("Resolve thread", "Dismiss thread view")
    }
    opened = preview.bounding_box()
    boxes = {name: control.bounding_box() for name, control in controls.items()}

    long_step = (
        "Comparing the lighter weight against every banner the gallery shows, at each "
        "width the panel takes, before and after the change."
    )
    thread_model.post_reply(serve.page_dir, address, long_step, ephemeral=True)
    told(page)
    expect(words).to_contain_text("before and after the change")
    rendered(page)
    grown = preview.bounding_box()
    assert grown["width"] == pytest.approx(opened["width"], abs=0.5), (opened, grown)
    assert grown["y"] == pytest.approx(opened["y"], abs=0.5), (opened, grown)
    assert grown["height"] > opened["height"]
    for name, control in controls.items():
        assert control.bounding_box() == pytest.approx(boxes[name], abs=0.5), name

    editor = preview.locator("leaf-text")
    preview.get_by_role("textbox", name="Reply", exact=True).click()
    page.keyboard.type("Also check the dark scheme")
    rendered(page)
    writing = preview.bounding_box()
    send = preview.locator(".lf-thread-reply .lf-compose-submit")
    pinned = {name: control.bounding_box() for name, control in controls.items()}
    pinned["Send"] = send.bounding_box()
    pinned["editor"] = editor.bounding_box()

    thread_model.post_reply(
        serve.page_dir,
        address,
        "Measuring the status line's contrast in both schemes, against the paper and "
        "against the banner's own ground.",
        ephemeral=True,
    )
    told(page)
    notice = preview.locator(".lf-thread-news")
    expect(notice).to_have_count(0)
    expect(words).to_contain_text("before and after the change")
    thread_model.post_reply(
        serve.page_dir,
        address,
        "Done: the banner's status line is one weight lighter, and its title sets in "
        "the muted ink, so the banner reads as chrome rather than as the page's first "
        "heading in both schemes.",
    )
    told(page)
    expect(notice).to_contain_text("new reply")
    # It reads whole in the head row, before the card's actions.
    expect(
        preview.locator(".lf-margin-thread-controls .lf-thread-news")
    ).to_be_visible()
    assert notice.evaluate("node => node.scrollWidth <= node.clientWidth")
    rendered(page)
    assert preview.bounding_box() == pytest.approx(writing, abs=0.5)
    held = {name: control.bounding_box() for name, control in controls.items()}
    held["Send"] = send.bounding_box()
    held["editor"] = editor.bounding_box()
    for name, box in pinned.items():
        assert held[name] == pytest.approx(box, abs=0.5), name

    notice.click()
    expect(preview).to_contain_text("one weight lighter")
    assert editor.evaluate("box => box.value") == "Also check the dark scheme"
    rendered(page)
    for name, control in controls.items():
        assert control.bounding_box() == pytest.approx(held[name], abs=0.5), name
    assert editor.bounding_box()["y"] > held["editor"]["y"] + 20


@pytest.mark.watch_shifts
@pytest.mark.parametrize("how", ["press", "key"])
def test_a_press_in_the_card_keeps_the_pressed_spot_still(browser, serve, how):
    """What a press shows grows the card from where the user pressed, as a seat on
    the page grows: opening pending progress, by pointer or key, grows the card up
    past the disclosure, which stays where it was pressed. The hold ends with that
    input, so a draft typed next grows the card down from its head row."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Make the banner quieter", {"section": "h-how"}
    )
    address = {"parent": root, "responds": root}
    for words in ("Comparing the banner.", "Checking both schemes.", "Measuring."):
        thread_model.post_reply(serve.page_dir, address, words, ephemeral=True)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": root,
            "text": "And check the dark scheme?",
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-margin-marker").first.click()
    preview = page.locator(".lf-margin-preview")
    disclosure = preview.locator(".lf-summary-expand")
    expect(disclosure).to_have_text("Show 3 progress messages")
    rendered(page)
    pressed = disclosure.bounding_box()
    compact = preview.bounding_box()
    original_motion = page.evaluate_handle("() => Element.prototype.animate")
    page.evaluate("() => {" + HOLD_MOTION + "}")

    def expect_pressed_spot():
        for progress in (0, 0.5, 1):
            page.evaluate(
                """progress => window.__lfHeld.forEach(m => {
                  if (m.playState !== 'idle')
                    m.currentTime = m.effect.getTiming().duration * progress;
                })""",
                progress,
            )
            box = disclosure.bounding_box()
            assert (box["x"], box["y"]) == pytest.approx(
                (pressed["x"], pressed["y"]), abs=0.5
            ), progress
        page.evaluate(
            """() => window.__lfHeld.splice(0).forEach(m => {
              if (m.playState !== 'idle') m.finish();
            })"""
        )

    if how == "key":
        disclosure.focus()
        page.keyboard.press("Enter")
    else:
        disclosure.click()
    expect(disclosure).to_have_text("Hide 3 progress messages")
    expect(preview).to_contain_text("Checking both schemes")
    rendered(page)
    expect_pressed_spot()

    expanded = preview.bounding_box()
    assert expanded["height"] > compact["height"]
    if how == "key":
        page.keyboard.press("Enter")
    else:
        disclosure.click()
    expect(disclosure).to_have_text("Show 3 progress messages")
    rendered(page)
    assert preview.bounding_box()["height"] == pytest.approx(compact["height"], abs=0.5)
    expect(disclosure).to_be_focused()
    expect_pressed_spot()
    page.evaluate(
        "original => { Element.prototype.animate = original; }", original_motion
    )
    original_motion.dispose()

    close = preview.get_by_role("button", name="Dismiss thread view", exact=True)
    head = close.bounding_box()
    preview.get_by_role("textbox", name="Reply", exact=True).click()
    page.keyboard.type("Also check the dark scheme, " * 6, delay=0)
    rendered(page)
    assert close.bounding_box() == pytest.approx(head, abs=0.5)

    if how == "press":
        age = preview.locator(".lf-msg-meta time").last
        timestamp = datetime.fromisoformat(age.get_attribute("datetime"))
        page.clock.set_fixed_time(timestamp + timedelta(seconds=30))
        ticked(page)
        expect(age).to_have_text("just now")
        before_tick = disclosure.bounding_box()
        page.clock.set_fixed_time(timestamp + timedelta(seconds=60))
        ticked(page)
        expect(age).to_have_text("1m ago")
        rendered(page)
        assert disclosure.bounding_box()["x"] == pytest.approx(
            before_tick["x"], abs=0.5
        )


# The sweep: one card per kind of place a commented row can stand in, each read in the
# states a reader's scroll puts it in, against the rules every placement keeps
# (comment-placement.js, the header). Each finding names its case, so one run reports
# every rule a placement breaks rather than the first.
SWEEP_LEAD = "<p>The export copies each tenant into its own archive overnight.</p>" * 3
SWEEP_ROWS = "".join(
    f'<p id="{{prefix}}-{n}">The export wrote tenant {n} to its archive.</p>'
    for n in range(30)
)
SWEEP_ANSWER = "Its first copy missed four rows, so the export copied it again. " * 9
SWEEP_PAGES = {
    "column": (
        leaf_page(
            "Placement sweep",
            f"<h1>Nightly export</h1>{SWEEP_LEAD}"
            f'<p id="para">The export checks each copy against its source.</p>'
            f"{SWEEP_LEAD}"
            f'<div id="log" data-bound="start" style="--lf-bound: 10rem">'
            f"{SWEEP_ROWS.format(prefix='log')}</div>{SWEEP_LEAD}"
            '<lf-pane id="notes" label="Notes"><div id="notes-body">'
            '<p id="note">Retries land on the largest tenants.</p>'
            f"{SWEEP_LEAD}</div></lf-pane>{SWEEP_LEAD}"
            f'<div id="outer" data-bound="start" style="--lf-bound: 14rem">{SWEEP_LEAD}'
            '<div id="inner" data-bound="start" style="--lf-bound: 7rem">'
            f"{SWEEP_ROWS.format(prefix='in')}</div>{SWEEP_LEAD * 8}</div>"
            f"{SWEEP_LEAD * 4}",
        ),
        ["para", "log-6", "note", "in-4"],
    ),
    "workspace": (
        leaf_page(
            "Placement sweep",
            '<div id="split"><lf-pane id="findings" label="Findings">'
            '<div id="findings-body">'
            f"{SWEEP_ROWS.format(prefix='find')}"
            '<div id="wlog" data-bound="start" style="--lf-bound: 10rem">'
            f"{SWEEP_ROWS.format(prefix='wlog')}</div>"
            f"{SWEEP_ROWS.format(prefix='more')}</div></lf-pane>"
            '<lf-pane id="side" label="Notes"><div id="side-body">'
            "<p>Notes open the pane.</p>"
            '<p id="wnote">Retries land on the largest tenants.</p></div></lf-pane>'
            "</div>",
            head=regions_side_by_side("split"),
            layout="workspace",
        ),
        ["find-20", "wlog-6", "wnote"],
    ),
    "screenshot": (ROOT / "examples/release-notes.html", ["rn-console-shot"]),
}

# What the page shows of the row and the card, in client pixels: the row's box cut by
# every box around it that clips and by the window, the card's box cut by its own
# `--lf-cut-*` insets and the window, and each workspace pane, bounded or not.
SWEEP_READ = """async (id) => {
  const {COMMENT_GAP: gap} = await window.__lfOverlayApi();
  const meet = (a, b) => ({left: Math.max(a.left, b.left), top: Math.max(a.top, b.top),
    right: Math.min(a.right, b.right), bottom: Math.min(a.bottom, b.bottom)});
  const plain = ({left, top, right, bottom}) => ({left, top, right, bottom});
  const win = {left: 0, top: 0, right: document.documentElement.clientWidth,
    bottom: document.documentElement.clientHeight};
  const row = document.getElementById(id);
  const boxes = [];
  for (let at = row.parentElement; at && at !== document.body;
       at = at.parentElement ?? at.getRootNode().host) {
    const style = getComputedStyle(at);
    if (!/auto|scroll|hidden|clip/.test(style.overflowY)) continue;
    const box = at.getBoundingClientRect();
    const left = box.left + at.clientLeft, top = box.top + at.clientTop;
    boxes.push({id: at.id || at.localName, left, top, right: left + at.clientWidth,
      bottom: top + at.clientHeight});
  }
  let shown = meet(plain(row.getBoundingClientRect()), win);
  for (const box of boxes) shown = meet(shown, box);
  const card = document.querySelector('.lf-margin-preview:not([hidden])');
  const box = plain(card.getBoundingClientRect());
  const cut = Object.fromEntries(['top', 'right', 'bottom', 'left'].map((edge) =>
    [edge, Math.max(0, parseFloat(card.style.getPropertyValue(`--lf-cut-${edge}`)) || 0)]));
  // A card whose subject is not drawn withholds itself (thread-preview.js).
  const seen = getComputedStyle(card).visibility === 'hidden'
    ? {left: 0, top: 0, right: 0, bottom: 0}
    : meet({left: box.left + cut.left, top: box.top + cut.top,
        right: box.right - cut.right, bottom: box.bottom - cut.bottom}, win);
  const list = card.querySelector('.lf-thread-transcript');
  const pane = row.closest('lf-pane');
  return {gap, row: plain(row.getBoundingClientRect()), line: row.getBoundingClientRect().top,
    shown, boxes, win, box, cut, seen,
    side: card.getAttribute('data-lf-thread-placement'),
    scrolls: list.scrollHeight > list.clientHeight + 1,
    pane: pane?.id ?? null,
    panes: [...document.querySelectorAll('lf-pane')].map((node) => {
      const body = [...node.children].find((c) => !c.matches('header, footer'));
      return {id: node.id, bounded: /auto|scroll/.test(getComputedStyle(body).overflowY),
        ...plain(node.getBoundingClientRect())};
    })};
}"""


def sweep_area(rect):
    return max(0, rect["right"] - rect["left"]) * max(0, rect["bottom"] - rect["top"])


def sweep_findings(read):
    """Each rule a reading breaks, by name, with the numbers that break it."""
    found = []
    shown, box, seen, win = read["shown"], read["box"], read["seen"], read["win"]
    whole = sweep_area(shown) >= sweep_area(read["row"]) - 1
    # While its row shows whole, the card stands whole inside the window, uncut.
    if whole:
        if not (
            box["top"] >= win["top"] - 1
            and box["bottom"] <= win["bottom"] + 1
            and box["left"] >= win["left"] - 1
            and box["right"] <= win["right"] + 1
        ):
            found.append(("in-window", box))
        # Beside, its top stands a gap above the row's line, so it passes an edge a
        # gap before the line does, and the cut grows from nothing there.
        if read["cut"]["top"] > read["gap"] + 0.5 or any(
            read["cut"][edge] for edge in ("right", "bottom", "left")
        ):
            found.append(("uncut-while-shown", read["cut"]))
    # Nothing of the card shows past an edge of a box around its row that the row's
    # line has crossed: it leaves with its row.
    for edge in read["boxes"]:
        if sweep_area(seen) < 1:
            break
        if read["line"] < edge["top"] and seen["top"] < edge["top"] - 1:
            found.append(("leaves-past-top", edge["id"], seen["top"], edge["top"]))
        if read["line"] > edge["bottom"] and seen["bottom"] > edge["bottom"] + 1:
            found.append(
                ("leaves-past-foot", edge["id"], seen["bottom"], edge["bottom"])
            )
    # A card on a row in a bounded workspace pane never stands over another pane.
    if read["pane"] and any(
        p["id"] == read["pane"] and p["bounded"] for p in read["panes"]
    ):
        for other in read["panes"]:
            if other["id"] != read["pane"] and sweep_area(_meet(seen, other)) >= 1:
                found.append(("over-another-pane", other["id"]))
    return found


def _meet(a, b):
    return {
        "left": max(a["left"], b["left"]),
        "top": max(a["top"], b["top"]),
        "right": min(a["right"], b["right"]),
        "bottom": min(a["bottom"], b["bottom"]),
    }


def sweep_room(read):
    """A card whose transcript scrolls while its room shows more below it: capped short
    of the room a row in its place has, which is a bounded workspace pane holding the
    row, or else the window, less Leaf's chrome at its foot."""
    if not read["scrolls"] or read["side"] == "above":
        return []
    pane = next(
        (p for p in read["panes"] if p["id"] == read["pane"] and p["bounded"]), None
    )
    foot = pane["bottom"] if pane else read["win"]["bottom"] - SWEEP_CHROME
    free = foot - read["box"]["bottom"]
    return (
        [("capped", round(read["box"]["bottom"] - read["box"]["top"]), round(free))]
        if free > 24
        else []
    )


def sweep_motion(before, after):
    """A card beside its row that moved by other than the row's step while clear of the
    window's edges, which may hold it in."""
    if after["side"] not in ("left", "right"):
        return []
    win, box = after["win"], after["box"]
    if box["top"] < win["top"] + 12 or box["bottom"] > win["bottom"] - SWEEP_CHROME:
        return []
    row = after["row"]["top"] - before["row"]["top"]
    card = box["top"] - before["box"]["top"]
    return [("jumps", round(row, 1), round(card, 1))] if abs(card - row) > 1 else []


# The panel's row at the window's foot, which the room stops above.
SWEEP_CHROME = 72


# Scrolls the box that scrolls a row, or with `outer` the box around that one, so the
# row stands where `where` names, or by `where` pixels; the id of the box it scrolled.
SWEEP_SCROLL = """([id, where, outer]) => {
  const row = document.getElementById(id);
  if (where === 'middle') row.scrollIntoView({block: 'center', behavior: 'instant'});
  const boxes = [];
  for (let at = row.parentElement; at && at !== document.body; at = at.parentElement) {
    if (/auto|scroll/.test(getComputedStyle(at).overflowY)) boxes.push(at);
  }
  const box = boxes[outer ? 1 : 0] ?? null;
  if (outer && !box) return null;
  const scroller = box ?? document.scrollingElement;
  const frame = box ? box.getBoundingClientRect()
    : {top: 0, bottom: document.documentElement.clientHeight};
  const r = row.getBoundingClientRect();
  const by = typeof where === 'number' ? where : {
    middle: r.top - (frame.top + (frame.bottom - frame.top) * 0.35),
    low: r.top - (frame.top + (frame.bottom - frame.top) * 0.8),
    'top-crossed': r.top - frame.top + 6,
    'top-gone': r.bottom - frame.top + 10,
    'foot-gone': r.top - frame.bottom - 10,
    'top-near': r.top - frame.top - 14,
    'foot-near': r.top - frame.bottom + 14,
  }[where];
  scroller.scrollTop += by;
  return box?.id ?? null;
}"""


@pytest.mark.parametrize("width", [1440, 820])
@pytest.mark.parametrize("kind", ["column", "workspace", "screenshot"])
def test_every_card_keeps_the_placement_rules(browser, serve, kind, width):
    """A sweep of the places a commented row stands in (the page's flow, a bounded log,
    a flowing pane, a log inside another, a workspace pane, a log inside one, a short
    pane beside a long one, a screenshot)
    at a width with the margin rail and one without, through the scrolls that carry the
    row to the window's foot and out of the box that scrolls it. Each card keeps three
    rules: while its row shows whole, it stands whole in the window, uncut; nothing of
    it shows past an edge its row has crossed; on a row in a bounded workspace pane it
    stands over no other pane; and beside its row it moves with the row, step for step,
    as the row crosses an edge of the box that scrolls it. A card whose transcript scrolls while the window has
    room is reported as well, by its card and room."""
    source, targets = SWEEP_PAGES[kind]
    url = serve(source)
    roots = {}
    for target in targets:
        roots[target] = panel_comment(
            serve.page_dir, f"Why {target}?", {"section": target}
        )
        thread_model.post_reply(
            serve.page_dir,
            {"parent": roots[target], "responds": roots[target]},
            SWEEP_ANSWER,
        )
    page = open_page(browser, url)
    resized(page, width, 900)
    findings = []

    def scrolled(target, where, outer=False):
        box = page.evaluate(SWEEP_SCROLL, [target, where, outer])
        scroll_settled(page)
        if box:
            scroll_settled(page, f"#{box}")
        rendered(page)
        return box

    for target in targets:
        scrolled(target, "middle")
        page.locator(f'[data-lf-margin-for="{target}"] .lf-margin-marker').click()
        card = page.locator(".lf-margin-preview")
        expect(card.locator(".lf-msg")).to_have_count(2)
        rendered(page)
        opened = page.evaluate(SWEEP_READ, target)
        case = (kind, width, target)
        findings += [(*case, "open", *f) for f in sweep_findings(opened)]
        findings += [(*case, "open", *f) for f in sweep_room(opened)]
        boxed = scrolled(target, "middle")
        states = ["low"] + (["top-crossed", "top-gone", "foot-gone"] if boxed else [])
        if page.evaluate(SWEEP_SCROLL, [target, 0, True]):
            states.append("outer-top-gone")
        for state in states:
            scrolled(target, "middle")
            if state == "outer-top-gone":
                scrolled(target, "top-gone", outer=True)
            else:
                scrolled(target, state)
            read = page.evaluate(SWEEP_READ, target)
            findings += [(*case, state, *f) for f in sweep_findings(read)]
            if read["side"] != opened["side"]:
                findings.append(
                    (*case, state, "side-changed", opened["side"], read["side"])
                )
        # Beside its row, the card moves with it a few pixels at a time as the row
        # crosses the top or the foot of the box that scrolls it.
        for near, step in [("top-near", 4), ("foot-near", -4)] if boxed else []:
            scrolled(target, "middle")
            scrolled(target, near)
            before = page.evaluate(SWEEP_READ, target)
            for _ in range(7):
                scrolled(target, step)
                after = page.evaluate(SWEEP_READ, target)
                findings += [(*case, near, *f) for f in sweep_motion(before, after)]
                before = after
        page.keyboard.press("Escape")
        expect(card).to_be_hidden()
    assert not findings, "\n".join(map(str, findings))
