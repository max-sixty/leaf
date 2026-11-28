"Where an open margin thread card stands beside its target, and how it holds still\nthrough news, reflows and scrolls, panes included."

import json
import re

import pytest
from browser.margin import WORDS_RIGHT, _comment_on, leave_card, resized_shell
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_harness import (
    PANEL,
    ROOT,
    leaf_page,
    open_page,
    panel_settled,
    regions_side_by_side,
    resized,
    scroll_settled,
    ticked,
    told,
    write,
)

from leaf.agents import thread as thread_model
from leaf.source.render_checks import rendered, wait_for_probe
from leaf_dev.browser import text_field
from leaf_dev.example_data import named_source

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
    # The step's arrival carries the reply row down over 300ms. A click while the row
    # travels scrolls the page before it lands, by Playwright's reveal of its target
    # and no scroll of Leaf's, and the boxes read after it stand off the window.
    wait_for_probe(page, "restingIn", ".lf-margin-preview")
    text_field(preview, name="Reply", exact=True).click()
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
    expect(notice).to_contain_text("1 new")
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


# The sweep: one card per kind of place a commented row can stand in, each read in the
# states a reader's scroll puts it in, against the rules every placement keeps
# (placement-rules.json). Each finding names its case and the rule it breaks, so one run
# reports every rule a placement breaks rather than the first.
PLACEMENT_RULES = json.loads(
    (
        ROOT / "browser/runtime/annotations/annotation-overlay/placement-rules.json"
    ).read_text()
)
# Each finding the sweep can report, by the one rule that names it (`swept`).
SWEEP_RULE = {
    finding: rule
    for section in PLACEMENT_RULES["sections"]
    for rule in section.get("rules", section.get("rows"))
    for finding in rule.get("swept", [])
}
SWEEP_REPORTS = set()


def swept(finding):
    """The name of a finding the sweep reports, which a rule must name."""
    assert finding in SWEEP_RULE, f"no rule in placement-rules.json sweeps {finding!r}"
    SWEEP_REPORTS.add(finding)
    return finding


IN_WINDOW = swept("in-window")
UNCUT = swept("uncut-while-shown")
PAST_TOP = swept("leaves-past-top")
PAST_FOOT = swept("leaves-past-foot")
OVER_PANE = swept("over-another-pane")
CAPPED = swept("capped")
JUMPS = swept("jumps")
SIDE_CHANGED = swept("side-changed")
CLOSED = swept("closed")


def sweep_report(findings):
    """Each finding, under the rule it breaks."""
    lines = []
    for case in findings:
        rule = SWEEP_RULE[case[4]]
        lines.append(
            f"{case}\n  breaks {rule['id']}: {rule.get('says', rule.get('cut'))}"
        )
    return "\n".join(lines)


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
    "screenshot": (named_source("release-notes"), ["rn-console-shot"]),
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
  if (!card) return null;
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
  const head = parseFloat(getComputedStyle(document.documentElement)
    .getPropertyValue('--lf-card-line'));
  return {gap, head, row: plain(row.getBoundingClientRect()), line: row.getBoundingClientRect().top,
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
    """Each rule a reading breaks, by its finding, with the numbers that break it."""
    found = []
    shown, box, seen, win = read["shown"], read["box"], read["seen"], read["win"]
    whole = sweep_area(shown) >= sweep_area(read["row"]) - 1
    if whole:
        if not (
            box["top"] >= win["top"] - 1
            and box["bottom"] <= win["bottom"] + 1
            and box["left"] >= win["left"] - 1
            and box["right"] <= win["right"] + 1
        ):
            found.append((IN_WINDOW, box))
        # Its top stands a gap above the row's line, and beside the row a head line
        # higher, so it passes an edge that much before the line does, and the cut
        # grows from nothing there.
        lead = read["gap"] + (read["head"] if read["side"] in ("left", "right") else 0)
        if read["cut"]["top"] > lead + 0.5 or any(
            read["cut"][edge] for edge in ("right", "bottom", "left")
        ):
            found.append((UNCUT, read["cut"]))
    # The boxes around the row that clip it, each cutting the card once the row's line
    # has crossed its edge.
    for edge in read["boxes"]:
        if sweep_area(seen) < 1:
            break
        if read["line"] < edge["top"] and seen["top"] < edge["top"] - 1:
            found.append((PAST_TOP, edge["id"], seen["top"], edge["top"]))
        if read["line"] > edge["bottom"] and seen["bottom"] > edge["bottom"] + 1:
            found.append((PAST_FOOT, edge["id"], seen["bottom"], edge["bottom"]))
    if read["pane"] and any(
        p["id"] == read["pane"] and p["bounded"] for p in read["panes"]
    ):
        for other in read["panes"]:
            if other["id"] != read["pane"] and sweep_area(_meet(seen, other)) >= 1:
                found.append((OVER_PANE, other["id"]))
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
        [(CAPPED, round(read["box"]["bottom"] - read["box"]["top"]), round(free))]
        if free > 24
        else []
    )


def sweep_motion(before, after):
    """A card beside its row that moved by other than the row's step. Where the window's
    edge holds it in, it may stand still instead, but never move further than the row."""
    if after["side"] not in ("left", "right"):
        return []
    win, box = after["win"], after["box"]
    row = after["row"]["top"] - before["row"]["top"]
    card = box["top"] - before["box"]["top"]
    held = (
        box["top"] <= win["top"] + 12 or box["bottom"] >= win["bottom"] - SWEEP_CHROME
    )
    moved = abs(card) > abs(row) + 1 if held else abs(card - row) > 1
    return [(JUMPS, round(row, 1), round(card, 1))] if moved else []


# The panel's row at the window's foot, which the room stops above.
SWEEP_CHROME = 72


# Where to turn the wheel, and by how much, to stand a row where `where` names, or to
# move it by `where` pixels: over the box that scrolls the row, or with `outer` the box
# around that one, at a spot where that box takes the wheel, or over the page's margin.
# A reader's wheel, since Leaf puts back a scroll no input made while a card's thread
# holds focus. Where no spot takes it, `covered` says whether the card stands over the
# box (`scroll-covers`).
SWEEP_AIM = """([id, where, outer]) => {
  const row = document.getElementById(id);
  const scrolls = (node) => /auto|scroll/.test(getComputedStyle(node).overflowY);
  const boxes = [];
  for (let at = row.parentElement; at && at !== document.body; at = at.parentElement) {
    if (scrolls(at)) boxes.push(at);
  }
  const box = boxes[outer ? 1 : 0] ?? null;
  if (outer && !box) return null;
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
  let covered = false;
  const takes = (x, y) => {
    const hit = document.elementFromPoint(x, y);
    if (hit?.closest('.lf-margin-preview')) covered = true;
    if (!hit || hit.closest('.lf-margin-preview, .lf-chrome, .lf-margin-cluster')) return false;
    let at = hit;
    while (at && at !== document.body && !scrolls(at)) at = at.parentElement;
    return box ? at === box : !at || at === document.body;
  };
  const area = box ? box.getBoundingClientRect()
    : {left: 4, right: 40, top: 80, bottom: document.documentElement.clientHeight - 80};
  for (let y = area.top + 6; y < area.bottom - 4; y += 10)
    for (let x = area.left + 8; x < area.right - 4; x += 30)
      if (takes(x, y)) return {box: box?.id ?? null, by, x, y};
  return {box: box?.id ?? null, by, x: null, y: null, covered};
}"""


@pytest.mark.parametrize("width", [1440, 1000])
@pytest.mark.parametrize("kind", ["column", "workspace", "screenshot"])
def test_every_card_keeps_the_placement_rules(browser, serve, kind, width):
    """A sweep of the places a commented row stands in (the page's flow, a bounded log,
    a flowing pane, a log inside another, a workspace pane, a log inside one, a short
    pane beside a long one, a screenshot) at a wide window and at one just wide enough
    for the margin rail, the narrowest that opens a card (a narrower one opens the
    thread in the floating panel), through the scrolls that carry the row to the
    window's foot and out of the box that scrolls it, against each rule
    placement-rules.json says it sweeps. Where the card covers all of that box, the
    sweep closes it to wheel the box, as `scroll-covers` has the reader do, and opens
    it again for the next state."""
    assert set(SWEEP_RULE) == SWEEP_REPORTS, (
        "rules name findings the sweep never reports",
        set(SWEEP_RULE) - SWEEP_REPORTS,
    )
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
    card = page.locator(".lf-margin-preview")

    def opened(target):
        page.evaluate(
            "(id) => document.getElementById(id)"
            ".scrollIntoView({block: 'center', behavior: 'instant'})",
            target,
        )
        scrolled(target, "middle")
        page.locator(f'[data-lf-margin-for="{target}"] .lf-margin-marker').click()
        expect(card.locator(".lf-msg")).to_have_count(2)
        rendered(page)

    def closed():
        # A click on the marker lands in the reply (records/thread/focus.js, `openingPart`);
        # Escape stands the user on the thread, from which the next takes the card down.
        expect(text_field(card, name="Reply", exact=True)).to_be_focused()
        page.keyboard.press("Escape")
        page.keyboard.press("Escape")
        expect(card).to_be_hidden()

    # Where the card covers all of the box the wheel is aimed at, the reader closes it
    # to scroll the box (`scroll-covers`), so `scrolled` does too and says so.
    covered = object()

    def scrolled(target, where, outer=False):
        aim = page.evaluate(SWEEP_AIM, [target, where, outer])
        if aim is None:
            return None
        if aim["x"] is None:
            assert aim["covered"], f"no spot takes the wheel for {target}"
            closed()
            scrolled(target, where, outer)
            return covered
        if abs(aim["by"]) >= 1:
            page.mouse.move(aim["x"], aim["y"])
            page.mouse.wheel(0, aim["by"])
            scroll_settled(page, f"#{aim['box']}" if aim["box"] else None)
        rendered(page)
        return aim["box"]

    def restored(target):
        """The row back at the middle of its box, with its card open."""
        if page.evaluate(SWEEP_READ, target) is not None:
            scrolled(target, "middle")
        if page.evaluate(SWEEP_READ, target) is None:
            opened(target)

    for target in targets:
        opened(target)
        at_open = page.evaluate(SWEEP_READ, target)
        case = (kind, width, target)
        findings += [(*case, "open", *f) for f in sweep_findings(at_open)]
        findings += [(*case, "open", *f) for f in sweep_room(at_open)]
        boxed = scrolled(target, "middle")
        states = ["low"] + (["top-crossed", "top-gone", "foot-gone"] if boxed else [])
        # The box around the row's own scroller, where the wheel can reach it.
        if (page.evaluate(SWEEP_AIM, [target, 0, True]) or {}).get("x") is not None:
            states.append("outer-top-gone")
        for state in states:
            restored(target)
            if state == "outer-top-gone":
                moved = scrolled(target, "top-gone", outer=True)
            else:
                moved = scrolled(target, state)
            if moved is covered:
                continue
            read = page.evaluate(SWEEP_READ, target)
            if read is None:
                findings.append((*case, state, CLOSED))
                break
            findings += [(*case, state, *f) for f in sweep_findings(read)]
            if read["side"] != at_open["side"]:
                findings.append(
                    (*case, state, SIDE_CHANGED, at_open["side"], read["side"])
                )
        # Beside its row, the card moves with it a few pixels at a time as the row
        # crosses the top or the foot of the box that scrolls it.
        for near, step in [("top-near", 4), ("foot-near", -4)] if boxed else []:
            restored(target)
            if scrolled(target, near) is covered:
                continue
            before = page.evaluate(SWEEP_READ, target)
            for _ in range(7):
                if scrolled(target, step) is covered:
                    break
                after = page.evaluate(SWEEP_READ, target)
                if after is None or before is None:
                    findings.append((*case, near, CLOSED))
                    break
                findings += [(*case, near, *f) for f in sweep_motion(before, after)]
                before = after
        if page.evaluate(SWEEP_READ, target) is not None:
            closed()
    assert not findings, sweep_report(findings)


@pytest.mark.watch_shifts
def test_a_card_above_its_target_holds_news_it_would_grow_up_for(browser, serve):
    """A card standing above what it is about holds its foot, so a step grows it up
    past its head row and messages. With the user in its reply box, where a click's
    opening leaves the caret, or on the thread, where Escape from the box and a send
    leave them, which waits at its reply box, the step shows at once: the card rises
    from the box, which stays where it stands, and the watch credits the rise the card
    declares. With the user on a message, by a click on its words, the next step waits,
    with no notice, since progress is no unread news, and shows when the user opens the
    card again (thread-preview.js, `endNewsMoves`)."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Make the banner quieter", {"section": "m19"})
    address = {"parent": root, "responds": root}
    thread_model.post_reply(
        serve.page_dir, address, "Reading the banner's styles.", ephemeral=True
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.evaluate("scrollTo(0, document.scrollingElement.scrollHeight)")
    page.locator(".lf-margin-marker").first.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_have_attribute("data-lf-thread-placement", "above")
    box = preview.locator(".lf-thread-reply leaf-text")
    expect(box).to_be_focused()
    rendered(page)
    # Keep Chrome's native clock and deliver news after its 500 ms input grace period.
    page.wait_for_timeout(600)
    opened = preview.bounding_box()
    writing = box.bounding_box()
    thread_model.post_reply(
        serve.page_dir,
        address,
        "Comparing the lighter weight against every banner the gallery shows, at each "
        "width the panel takes, before and after the change.",
        ephemeral=True,
    )
    told(page)
    working = preview.locator(".lf-thread-working-words")
    expect(working).to_contain_text("the change")
    rendered(page)
    risen = preview.bounding_box()
    assert risen["y"] < opened["y"] - 10, (opened, risen)
    assert box.bounding_box() == pytest.approx(writing, abs=0.5)

    page.keyboard.press("Escape")
    expect(preview.locator(".lf-page-thread")).to_be_focused()
    rendered(page)
    page.wait_for_timeout(600)
    waiting = box.bounding_box()
    thread_model.post_reply(
        serve.page_dir, address, "Checking the banner in both schemes.", ephemeral=True
    )
    told(page)
    expect(working).to_contain_text("both schemes")
    rendered(page)
    assert box.bounding_box() == pytest.approx(waiting, abs=0.5)

    words = preview.locator(".lf-msg").first.bounding_box()
    page.mouse.click(words["x"] + 20, words["y"] + words["height"] - 8)
    expect(preview.locator(".lf-page-thread")).to_be_focused()
    rendered(page)
    page.wait_for_timeout(600)
    reading = preview.bounding_box()
    thread_model.post_reply(
        serve.page_dir, address, "Measuring the banner's contrast.", ephemeral=True
    )
    told(page)
    expect(working).to_contain_text("both schemes")
    expect(preview.locator(".lf-thread-news")).to_have_count(0)
    rendered(page)
    assert preview.bounding_box() == pytest.approx(reading, abs=0.5)
    preview.get_by_role("button", name="Dismiss thread view", exact=True).click()
    expect(preview).to_be_hidden()
    page.locator(".lf-margin-marker").first.click()
    expect(working).to_contain_text("contrast")


def test_the_shipped_long_thread_keeps_the_margin_and_its_height(browser, serve):
    """The shipped exchange stands beside its controls, and crosses them before it shrinks."""
    example = named_source("ship-review")
    page = open_page(browser, serve(example))
    page.emulate_media(reduced_motion="reduce")
    resized_shell(page, 1920, 900)
    marker = page.locator('[data-lf-margin-for="off-t-resync"] > .lf-margin-marker')
    expect(marker).to_have_count(1)
    expect(marker.locator("..")).to_have_attribute(
        "aria-label", re.compile(r"Page actions for item · iOS reconnect stall")
    )
    marker.evaluate(
        "marker => scrollBy(0, marker.getBoundingClientRect().top - innerHeight + 52)"
    )

    marker.click()
    preview = page.locator(".lf-margin-preview")
    thread = page.locator(".lf-margin-thread", has_text="One reconnect in forty")
    expect(preview).to_be_visible()
    expect(preview).to_have_attribute(
        "aria-label", "Thread for “One reconnect in about 40”"
    )
    expect(thread.locator(".lf-msg[data-lf-author=user]").first).to_be_visible()
    # The card draws the reply's interactive widgets in place.
    expect(thread.locator("#off-slip-chase [role=checkbox]")).to_be_checked()
    expect(thread.locator("leaf-text")).to_be_focused()
    geometry = marker.evaluate(
        """markerNode => {
          const main = document.querySelector('main').getBoundingClientRect();
          const controls = markerNode.closest('[data-lf-margin-for]').getBoundingClientRect();
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          const reply = document.querySelector('.lf-margin-thread .lf-thread-reply')
            .getBoundingClientRect();
          const cardStyle = getComputedStyle(document.querySelector('.lf-margin-preview-card'));
          return {mainLeft: main.left,
                  mainRight: main.right, controlsRight: controls.right,
                  controlsTop: controls.top, controlsBottom: controls.bottom,
                  cardLeft: card.left, cardRight: card.right, cardTop: card.top,
                  cardBottom: card.bottom, cardWidth: card.width,
                  viewportRight: document.documentElement.clientWidth,
                  borderLeft: cardStyle.borderLeftWidth,
                  borderRight: cardStyle.borderRightWidth,
                  replyTop: reply.top, replyBottom: reply.bottom,
                  panelOpen: 'lfOpen' in document.querySelector('.lf-floating-panel').dataset};
        }"""
    )
    minimum = page.evaluate("async () => (await window.__lfOverlayApi()).cardMinimum()")
    assert geometry["cardLeft"] >= page.evaluate(WORDS_RIGHT) + 7.5, geometry
    assert geometry["cardLeft"] < geometry["controlsRight"], geometry
    assert geometry["cardRight"] <= geometry["viewportRight"] - 7, geometry
    # No message the card shows stands taller than it is wide, so the card keeps its
    # least width (comment-placement.js, `standsTall`).
    assert geometry["cardWidth"] == pytest.approx(minimum, abs=0.5), geometry
    assert geometry["cardTop"] >= 7, geometry
    assert geometry["cardBottom"] <= 892, geometry
    assert geometry["replyTop"] >= geometry["cardTop"], geometry
    assert geometry["replyBottom"] <= geometry["cardBottom"], geometry
    assert geometry["borderLeft"] == geometry["borderRight"] == "1px", geometry
    assert not geometry["panelOpen"], geometry

    words = thread.locator(".lf-msg-body").first
    words_box = words.bounding_box()
    page.mouse.move(words_box["x"] + 1, words_box["y"] + 10)
    page.mouse.down()
    page.mouse.move(words_box["x"] + 180, words_box["y"] + 10, steps=10)
    page.mouse.up()
    selected = page.evaluate("getSelection().toString()")
    assert len(selected) > 10 and selected in words.inner_text(), selected

    text_field(thread, name="Reply", exact=True).click()
    send = preview.locator(".lf-compose-field > button:visible")
    send.focus()
    page.evaluate("() => dispatchEvent(new Event('resize'))")
    expect(send).to_be_focused()

    resized_shell(page, 1920, 480)
    # Containment is measured while the attached passage is in view; a card
    # follows its passage when that passage leaves the viewport.
    target = page.locator("#off-t-resync")
    target.scroll_into_view_if_needed()
    expect(target).to_be_in_viewport()
    rendered(page)
    expect(send).to_be_focused()
    expect(preview).to_be_visible()
    capped = preview.evaluate(
        """card => {
          const box = card.getBoundingClientRect();
          const list = card.querySelector('.lf-thread-transcript');
          return {top: box.top, bottom: box.bottom,
                  clientHeight: list.clientHeight, scrollHeight: list.scrollHeight};
        }"""
    )
    assert capped["top"] >= 7, capped
    assert capped["bottom"] <= 472.5, capped
    assert capped["scrollHeight"] > capped["clientHeight"], capped
    # The thread scrolls while its opening metadata and settlement remain usable.
    metadata = preview.locator(".lf-margin-thread-controls")
    resolve = preview.get_by_role("button", name="Resolve thread", exact=True)
    metadata_box = metadata.bounding_box()
    resolve_box = resolve.bounding_box()
    preview.locator(".lf-thread-transcript").evaluate(
        "node => { node.scrollTop = node.scrollHeight; }"
    )
    ticked(page)
    scrolled_metadata = metadata.bounding_box()
    scrolled_resolve = resolve.bounding_box()
    assert scrolled_metadata["y"] >= capped["top"], scrolled_metadata
    assert scrolled_resolve["y"] >= capped["top"], scrolled_resolve
    assert scrolled_resolve["y"] + scrolled_resolve["height"] <= capped["bottom"], (
        scrolled_resolve
    )
    assert scrolled_resolve["y"] - scrolled_metadata["y"] == pytest.approx(
        resolve_box["y"] - metadata_box["y"], abs=0.5
    )
    resized_shell(page, 1920, 900)

    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    # On Me opens in the panel over the page's foot, beside the card rather than in
    # its place, and the view's Escape puts it away to the page; the card's own
    # Escape follows.
    panel_settled(page, view="queue")
    expect(preview).to_be_visible()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement === document.body")
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    marker.click()
    expect(preview).to_be_visible()
    expect(thread.locator("leaf-text")).to_be_focused()

    expect(thread.locator("#off-slip-chase [role=checkbox]")).to_be_checked()

    # Tall enough for the whole thread, its reply's options drawn in the card.
    resized_shell(page, 1436, 1000)
    beside = page.evaluate(
        """() => {
          const main = document.querySelector('main').getBoundingClientRect();
          const marker = document.querySelector('[data-lf-kinds="comment"]')
          const controls = marker.closest('[data-lf-margin-for]').getBoundingClientRect();
          const cardNode = document.querySelector('.lf-margin-preview');
          const card = cardNode.getBoundingClientRect();
          const list = cardNode.querySelector('.lf-thread-transcript');
          return {mainLeft: main.left, mainRight: main.right,
                  controlsRight: controls.right, controlsTop: controls.top,
                  controlsBottom: controls.bottom, cardLeft: card.left,
                  cardRight: card.right, cardTop: card.top,
                  cardBottom: card.bottom, cardWidth: card.width,
                  clipped: list.scrollHeight - list.clientHeight,
                  shellWidth: document.body.getBoundingClientRect().width};
        }"""
    )
    # This shell leaves less than the card's minimum beside the wide cluster, and more
    # right of the words, so the card stands there, across the cluster, at its least
    # width and its whole height.
    assert beside["shellWidth"] - 8 - beside["controlsRight"] < minimum, beside
    assert beside["cardLeft"] >= page.evaluate(WORDS_RIGHT) + 15.5, beside
    assert beside["cardLeft"] < beside["controlsRight"], beside
    assert beside["cardRight"] <= beside["shellWidth"] - 8 + 0.5, beside
    assert beside["cardWidth"] == pytest.approx(minimum, abs=0.5), beside
    assert beside["clipped"] <= 0, beside

    resized(page, 1471, 900)
    expect(preview).to_be_visible()
    expect(marker).to_have_attribute("aria-controls", "lf-margin-preview")
    expect(marker).to_have_attribute("aria-expanded", "true")
    expect(page.locator(PANEL)).not_to_have_attribute("data-lf-open", re.compile(""))
    # Out of the reply the click left the caret in, and out of the card.
    expect(preview.locator("leaf-text")).to_be_focused()
    page.keyboard.press("Escape")
    leave_card(page)
    marker.hover()
    expect(preview).to_be_hidden()
    marker.click()
    expect(preview).to_be_visible()
    expect(page.locator(PANEL)).not_to_have_attribute("data-lf-open", re.compile(""))

    expect(preview.locator("leaf-text")).to_be_focused()
    page.keyboard.press("Escape")
    leave_card(page)
    resized(page, 1280, 600)
    marker.evaluate("node => scrollBy(0, node.getBoundingClientRect().top - 330)")
    marker.click()
    text_field(preview, name="Reply", exact=True).click()
    editor = preview.locator("leaf-text")
    draft = "\n".join(
        f"Line {n}: " + "The reply keeps its complete editor visible. " * 2
        for n in range(18)
    )
    write(editor, draft)
    for edge, caret in [("ArrowLeft", 0), ("ArrowRight", len(draft))]:
        editor.press("ControlOrMeta+a")
        editor.press(edge)
        expect(editor).to_have_js_property("value", draft)
        assert editor.evaluate("node => node.selectionStart") == caret
        # The reply box runs over the card's padding to its sides and foot, so the
        # card's own box is what must hold it.
        page.wait_for_function("""() => {
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          const editor = document.querySelector('.lf-margin-preview leaf-text').getBoundingClientRect();
          const send = document.querySelector('.lf-margin-preview .lf-compose-submit').getBoundingClientRect();
          return editor.top >= card.top - 1 && editor.bottom <= card.bottom + 1
            && send.top >= card.top && send.bottom <= card.bottom + 1;
        }""")


def test_the_rail_tab_stop_follows_a_carried_row_back_into_view(browser, serve):
    """The rail's one Tab stop is its highest row in view, whichever way the page got
    there. A row on a line a box scrolls sideways stands in a carrier, which the browser
    moves with the page's scroll but whose own box reads a frame late: read there, a
    scroll back to the top left the stop on the second row, below the first, until
    something else re-read the rail."""
    line = " ".join(["A line wider than its box, which scrolls it sideways."] * 4)
    filler = "".join(f"<p>Filler paragraph {n}.</p>" for n in range(30))
    body = (
        "<h1>Carried rows</h1>"
        f'<div style="overflow-x: auto"><p id="first" style="white-space: nowrap">{line}'
        f'</p></div>{filler[: len(filler) // 3]}<p id="second">The second finding.</p>'
        f"{filler}"
    )
    events = [_comment_on("first"), _comment_on("second")]
    page = open_page(browser, serve(leaf_page("Carried rows", body), events=events))
    resized(page, 1440, 900)
    rendered(page)
    first = page.locator('[data-lf-margin-for="first"] .lf-margin-marker')
    second = page.locator('[data-lf-margin-for="second"] .lf-margin-marker')
    assert first.evaluate("row => row.closest('.lf-margin-carrier') !== null"), (
        "the fixture's first row no longer stands in a carrier"
    )
    expect(first).to_have_attribute("tabindex", "0")

    page.mouse.move(300, 300)
    page.mouse.wheel(0, 600)
    scroll_settled(page)
    rendered(page)
    expect(second).to_have_attribute("tabindex", "0")
    page.mouse.wheel(0, -600)
    scroll_settled(page)
    rendered(page)
    expect(first).to_have_attribute("tabindex", "0")
    expect(second).to_have_attribute("tabindex", "-1")
