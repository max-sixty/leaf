"""How each margin entry is drawn, labelled and kept through repaints. The bounds on a
repaint's work are held on the corpus (`journeys/test_render_gate.py`), and the feature
gallery's margin atlas is read on the gallery's one journey
(`journeys/test_render_navigation.py`)."""

import re

import pytest
from interact_support import append_command
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE
from render_cases_layout import token_colour
from render_harness import (
    draft_control,
    leaf_page,
    margins_laid_out,
    open_page,
    open_threads,
    panel_settled,
    resized,
    sending,
)

from browser.margin import (
    DENSE_SUGGESTIONS_PAGE,
    _comment_on,
)
from leaf import event_log as events_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def _refreshes_restate_no_margin_name(page, population):
    """A viewport refresh must not rewrite a name, state, word, or place it is not changing.

    `render` follows semantic and viewport refreshes, so an unconditional write here
    restates itself on a page nobody has touched: the mutation stream a
    screen reader rebuilds its buffer from, and a dirty box for whatever reads
    next. The corpus used to restate 205 attributes and the margin entry's
    words on every pass.

    What the pass wrote without changing anything is one reading rather than two.
    An attribute the pass leaves carrying the value it opened with said nothing,
    whether one writer restated it or two took turns over it — and the turns are
    the reading a same-value predicate cannot take, because each leg differs from
    the value before it. Both are records a reader rebuilds from, and the second
    kind is what `leaf.js`'s disclosure watch reads as news. So `news` stays as
    its own reading: a watched attribute that ends the pass somewhere new repaints
    the page's keys, and that is a change rather than a restatement.

    Every row lives in the margin layer, whatever it holds, and `syncInlineOffers`
    builds another host in place wherever an offer's target stands in chrome. So
    the watch is rooted at the layer, the Map door, the inline hosts, and the page's
    boxes. The reach is asserted the way the
    population is: a run where rows stood somewhere the watch does not reach would
    otherwise return the same clean `[]` it returns when nothing is wrong.

    Half of `render` runs in a frame callback — `scheduleMarginLayout`,
    `scheduleRoving` and `scheduleMarginEntryLabels` are its whole tail — and five
    refreshes in one synchronous task never reach it. Each refresh is therefore
    read across a settled frame, which both pages now allow. The layout pass
    places every row from what it writes, so a refresh that restated a posture, an
    offset or a push shows up here as a restatement.
    """
    for selector, least in population.items():
        assert page.locator(selector).count() >= least, selector
    refresh = page.evaluate(
        """async ({refreshes}) => {
          const frame = () => new Promise(
            resolve => requestAnimationFrame(() => setTimeout(resolve, 0)));
          const text = nodes => [...nodes].map(node => node.textContent).join('');
          const layer = document.querySelector('nav.lf-margin-projection');
          const hosts = [...document.querySelectorAll('.lf-margin-cluster')];
          // Viewer.js owns its inline viewer's geometry during a resize.
          // This reading covers Leaf's placement writes on authored boxes.
          const pageBoxes = [...document.querySelectorAll('main, main *')]
            .filter(box => !box.closest('.viewer-container'));
          const roots = [layer, ...document.querySelectorAll(
              'div.lf-ui[data-lf-margin-for]:not(.lf-margin-cluster)')];
          // Collected from the callback rather than by `takeRecords` alone: letting a
          // frame settle passes a microtask checkpoint, which delivers the records to
          // the callback and empties the queue a bare `takeRecords` would read.
          const seen = [];
          const observer = new MutationObserver(list => seen.push(...list));
          for (const root of roots)
            observer.observe(root, {subtree: true, childList: true,
              characterData: true, characterDataOldValue: true,
              attributes: true, attributeOldValue: true});
          // A placement pass must not restate authored style on any content box.
          for (const box of pageBoxes)
            observer.observe(box, {attributes: true, attributeOldValue: true,
              attributeFilter: ['style']});
          const on = record => record.target.className || record.target.nodeName;
          const unchanged = [];
          const news = [];
          for (let i = 0; i < refreshes; i++) {
            window.dispatchEvent(new Event('resize'));
            await frame();
            await frame();
            seen.push(...observer.takeRecords());
            const records = seen.splice(0);
            // The value each attribute carried before this pass touched it.
            const opened = new Map();
            for (const record of records) {
              if (record.type !== 'attributes') continue;
              let byName = opened.get(record.target);
              if (!byName) opened.set(record.target, byName = new Map());
              if (!byName.has(record.attributeName))
                byName.set(record.attributeName, record.oldValue);
            }
            for (const record of records) {
              if (record.type === 'attributes') {
                const now = record.target.getAttribute(record.attributeName);
                const opening = opened.get(record.target).get(record.attributeName);
                if (opening === now)
                  unchanged.push({on: on(record), wrote: record.attributeName,
                                  said: opening});
                if (['open', 'aria-expanded'].includes(record.attributeName)
                    && now !== record.oldValue)
                  news.push({on: on(record), wrote: record.attributeName,
                             was: record.oldValue, now});
              } else if (record.type === 'characterData') {
                if (record.oldValue === record.target.data)
                  unchanged.push({on: on(record), wrote: 'text',
                                  said: record.oldValue});
              } else if (text(record.removedNodes) === text(record.addedNodes)
                         && record.removedNodes.length > 0)
                unchanged.push({on: on(record), wrote: 'children',
                                said: text(record.addedNodes)});
            }
          }
          observer.disconnect();
          return {
            unchanged, news,
            outside: hosts.filter(host => !layer.contains(host)).length,
            pageBoxes: pageBoxes.length,
          };
        }""",
        {"refreshes": 5},
    )
    assert refresh["unchanged"] == [], refresh["unchanged"]
    assert refresh["news"] == [], refresh["news"]
    # The reach the readings above are worth: every row stands in the watched layer,
    # and every authored box is watched too.
    assert refresh["outside"] == 0, refresh
    assert refresh["pageBoxes"] > 0, refresh


@pytest.mark.parametrize("annotations", ["overlay", "page"])
def test_an_inline_contribution_name_needs_no_physical_margin(
    browser, serve, annotations
):
    """The shared control's native name remains readable when a page owns annotations."""
    source = leaf_page("Inline names", '<button id="inline">Read</button>').replace(
        "<body>", f'<body data-annotations="{annotations}">'
    )
    page = open_page(browser, serve(source))
    page.evaluate(
        """async () => {
          const {contributionEntry, presentContributionEntry} =
            await window.__lfWidgetApi();
          presentContributionEntry(document.getElementById('inline'),
            contributionEntry({key: 'inline', icon: 'dot', label: 'Read inline name'}));
        }"""
    )
    control = page.get_by_role("button", name="Read inline name", exact=True)
    control.focus()
    expect(control.locator(".lf-margin-entry-label")).to_be_visible()
    page.mouse.move(0, 0)
    page.keyboard.press("Tab")
    expect(control.locator(".lf-margin-entry-label")).to_be_hidden()


def test_a_margin_entry_label_starts_at_its_settled_place(browser, serve):
    """A name has one visible position from its first reveal, whatever its border
    or whether its control stands in the rail or as a pin."""
    page = open_page(
        browser,
        serve(leaf_page("Steady margin names", '<p id="target">Read this target.</p>')),
    )
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          registerContribution({key: 'names', target: document.getElementById('target'),
            read: () => ({entries: ['action', 'disclosure'].map(behavior =>
              contributionEntry({key: behavior, behavior, icon: 'dot',
                label: `Read ${behavior}`}))}), activate: () => {}});
        }"""
    )
    for width in (1440, 390):
        resized(page, width, 900)
        for behavior in ("action", "disclosure"):
            control = page.get_by_role("button", name=f"Read {behavior}", exact=True)
            expect(control).to_be_visible()
            page.wait_for_function(
                "Object.values(document.querySelector('script[data-lf-entry]').lfRenderingState()).every(Boolean)"
            )
            reading = control.evaluate(
                """async control => {
                  const label = control.querySelector('.lf-margin-entry-label');
                  const frames = [];
                  const read = () => {
                    const style = getComputedStyle(label);
                    if (style.visibility !== 'visible' || Number(style.opacity) === 0)
                      return;
                    const box = label.getBoundingClientRect();
                    frames.push({x: box.x, y: box.y});
                  };
                  control.focus();
                  read();
                  for (let n = 0; n < 8; n++) {
                    await new Promise(requestAnimationFrame);
                    read();
                  }
                  const posture = control.closest('.lf-margin-cluster').dataset.lfPlace;
                  control.blur();
                  await new Promise(requestAnimationFrame);
                  return {frames, posture};
                }"""
            )
            assert len(reading["frames"]) >= 2, reading
            assert all(frame == reading["frames"][0] for frame in reading["frames"]), (
                reading
            )
            assert reading["posture"] == ("rail" if width == 1440 else "pin")


def test_a_transient_margin_entry_label_avoids_the_next_margin_entry(browser, serve):
    """A tooltip moves rather than covering a neighboring margin entry."""
    fixture = leaf_page(
        "Close margin labels",
        '<p id="first">First target</p><p id="second">Second target</p>',
    )
    page = open_page(browser, serve(fixture))
    resized(page, 1440, 900)
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          for (const id of ['first', 'second']) {
            registerContribution({key: id, target: document.getElementById(id),
              read: () => ({entries: [contributionEntry({
                key: 'act', icon: 'dot', label: `Act on ${id}`
              })]}), activate: () => {}});
          }
        }"""
    )
    first = page.locator('[data-lf-margin-for="first"]')
    second = page.locator('[data-lf-margin-for="second"]')
    button = first.get_by_role("button", name="Act on first", exact=True)
    button.hover()
    expect(button).to_have_attribute("data-lf-label-side", re.compile(".+"))
    label = button.locator(".lf-margin-entry-label")
    expect(label).to_be_visible()
    button_box, label_box, second_box = [
        locator.bounding_box() for locator in (button, label, second)
    ]
    default_label_box = {
        "x": button_box["x"] + button_box["width"] - label_box["width"],
        "y": button_box["y"] + button_box["height"] + 6,
        "width": label_box["width"],
        "height": label_box["height"],
    }

    def overlaps(left, right):
        return (
            left["x"] < right["x"] + right["width"]
            and left["x"] + left["width"] > right["x"]
            and left["y"] < right["y"] + right["height"]
            and left["y"] + left["height"] > right["y"]
        )

    assert overlaps(default_label_box, second_box), (
        "the fixture no longer exercises overlapping margin rows"
    )
    assert not overlaps(label_box, second_box)
    page.mouse.move(0, 0)
    button.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(button).to_be_focused()
    assert label.evaluate("node => node.getAnimations().length") == 0, (
        "a keyboard destination delayed its label behind paint-only motion"
    )


def test_a_finger_holding_a_margin_entry_reads_its_label_above_it(browser, serve):
    """A margin entry's label and status show to a resting pointer and the keyboard,
    and a finger holds the entry to read them, with whatever else its title says. The
    label stands clear of the finger, above the entry or else beside it, while the
    press lasts, and a row arriving meanwhile doesn't move it. An
    action's release presses it once, and the browser's own click after it reaches
    nothing the press put under the finger. A phone keeps the entry a finger last
    pressed hovered and focused until the next tap elsewhere, so neither reveals its
    label there: a tap leaves none behind, and the label goes with the hold."""
    lead = "<p>Text before the target, so the label has room above it.</p>" * 4
    url = serve(
        leaf_page(
            "Held margin labels",
            f'{lead}<p id="before">Just before.</p><p id="target">Read this target.</p>',
        )
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=context)
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          window.pressed = [];
          registerContribution({key: 'held', target: document.getElementById('target'),
            read: () => ({entries: [
              contributionEntry({key: 'sent', behavior: 'status', icon: 'sent',
                label: 'Sent', context: '2m ago'}),
              contributionEntry({key: 'act', icon: 'dot', label: 'Act on it',
                title: 'Acts at once'}),
            ]}), activate: (key) => {
              window.pressed.push(key);
              // What the press opens lands under the finger.
              const beneath = document.createElement('button');
              beneath.style = 'position: fixed; inset: 0; z-index: 2147483647';
              beneath.onclick = () => window.pressed.push('beneath');
              document.body.append(beneath);
            }});
        }"""
    )
    cdp = context.new_cdp_session(page)
    tapped = page.locator(".lf-margin-entry").filter(has_text="Sent")
    tapped.tap()
    expect(tapped).to_be_focused()
    expect(tapped.locator(":scope > .lf-margin-entry-label")).to_be_hidden()
    for name, words in (("Sent", "Sent2m ago"), ("Act on it", "Act on itActs at once")):
        entry = page.locator(".lf-margin-entry").filter(has_text=name)
        expect(entry).to_be_visible()
        label = entry.locator(":scope > .lf-margin-entry-label")
        expect(label).to_be_hidden()
        box = entry.bounding_box()
        point = {"x": box["x"] + box["width"] / 2, "y": box["y"] + box["height"] / 2}
        cdp.send(
            "Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [point]}
        )
        expect(label).to_be_visible()
        expect(label).to_have_text(words)
        expect(entry).to_have_attribute(
            "data-lf-label-side",
            "above" if name == "Sent" else re.compile("above|before"),
        )
        held = label.bounding_box()
        # Clear of the finger: wholly above the entry, or wholly left of it.
        assert (
            held["y"] + held["height"] <= box["y"]
            or held["x"] + held["width"] <= box["x"]
        ), (held, box)
        if name == "Sent":
            # A row arriving beside the held one leaves the label where it is.
            page.evaluate(
                """async () => {
                  const {contributionEntry, registerContribution} =
                    await window.__lfWidgetApi();
                  registerContribution({key: 'arriving',
                    target: document.getElementById('before'),
                    read: () => ({entries: [contributionEntry({key: 'note',
                      icon: 'dot', label: 'Arrived'})]}), activate: () => {}});
                }"""
            )
            expect(
                page.locator(".lf-margin-entry").filter(has_text="Arrived")
            ).to_be_visible()
            rendered(page)
            expect(entry).to_have_attribute("data-lf-label-side", "above")
            assert label.bounding_box() == held
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        expect(entry).not_to_have_attribute("data-lf-held-word", "")
        expect(label).to_be_hidden()
    rendered(page)
    assert page.evaluate("window.pressed") == ["act"]


OBLIGATION_MARKERS_PAGE = leaf_page(
    "Question markers",
    """
<h1 id="h">Two open questions</h1>
<lf-ask id="short-ask"><h2>Where should sessions live?</h2>
<lf-options id="short-choice" choose>
  <lf-option id="short-a"><strong>Keep the store</strong></lf-option>
  <lf-option id="short-b"><strong>Signed tokens</strong></lf-option>
</lf-options></lf-ask>
<p id="between">Between the two questions, a paragraph of ordinary prose.</p>
<lf-ask id="long-ask"><h2>Should the nightly export keep writing one file per tenant,
or roll every tenant into a single partitioned archive?</h2>
<lf-options id="long-choice" choose>
  <lf-option id="long-a"><strong>One file per tenant</strong></lf-option>
  <lf-option id="long-b"><strong>One archive</strong></lf-option>
</lf-options></lf-ask>
""",
)


def test_an_obligation_marker_s_label_and_name_identify_its_question(browser, serve):
    """Hovering an obligation's marker shows the obligation's question, where it used to show only
    "Ask…", which the marker's glyph already says. Its accessible name identifies
    the question too, independently of how the visible label fits."""
    page = open_page(browser, serve(OBLIGATION_MARKERS_PAGE))
    resized(page, 1440, 900)
    read = """(marker) => {
        const word = marker.querySelector('.lf-margin-entry-label-word');
        return {text: word.textContent, name: marker.getAttribute('aria-label'),
                cut: word.scrollWidth > word.clientWidth};
    }"""
    seen = {}
    for item in ("short-ask", "long-ask"):
        marker = page.locator(
            f'[data-lf-margin-for="{item}"] .lf-margin-marker[data-lf-kinds~="on-me"]'
        )
        marker.scroll_into_view_if_needed()
        marker.hover()
        expect(marker.locator(".lf-margin-entry-label")).to_be_visible()
        seen[item] = marker.evaluate(read)
    question = page.locator("#long-ask h2").evaluate(
        "h => h.textContent.replace(/\\s+/g, ' ').trim()"
    )
    assert seen["short-ask"]["text"] == "Where should sessions live?", seen
    assert not seen["short-ask"]["cut"], seen
    assert seen["long-ask"]["text"] == question, seen
    # The accessible route includes the question's distinguishing alternative.
    assert "roll every tenant" in seen["long-ask"]["name"], seen


def test_the_obligation_the_user_stands_in_selects_its_marker(browser, serve):
    """Arriving at an obligation with `m` paints its On me marker selected, and only its
    marker."""
    page = open_page(browser, serve(OBLIGATION_MARKERS_PAGE))
    resized(page, 1440, 900)

    def marker(item):
        return page.locator(
            f'[data-lf-margin-for="{item}"] .lf-margin-marker[data-lf-kinds~="on-me"]'
        )

    page.keyboard.press("m")
    expect(marker("short-ask")).to_have_attribute("data-lf-target-selected", "")
    expect(marker("long-ask")).not_to_have_attribute(
        "data-lf-target-selected", re.compile(".*")
    )


LABEL_CLEARANCE = """control => {
  const label = control.querySelector('.lf-margin-entry-label');
  const box = label.getBoundingClientRect();
  const overlap = (left, right) => left.left < right.right &&
    left.right > right.left && left.top < right.bottom &&
    left.bottom > right.top;
  const neighbors = [...document.querySelectorAll('.lf-margin-entry')]
    .filter(candidate => candidate !== control && candidate.checkVisibility())
    .map(candidate => candidate.getBoundingClientRect());
  return {inside: box.left >= 4 && box.right <= innerWidth - 4 &&
    box.top >= 4 && box.bottom <= innerHeight - 4,
    overlaps: neighbors.filter(neighbor => overlap(box, neighbor)).length};
}"""


def test_dense_suggestion_labels_cover_no_neighboring_margin_entry(
    browser, serve, subtests
):
    """Every label in a tightly stacked real cluster finds a clear side, at a desktop
    width and then a phone's on one page."""
    page = open_page(browser, serve(DENSE_SUGGESTIONS_PAGE))
    for width in (1440, 390):
        with subtests.test(width=width):
            resized(page, width, 900)
            page.locator("#bg-neighbors").scroll_into_view_if_needed()
            for target in ("bg-neighbor-a", "bg-neighbor-b", "bg-neighbor-c"):
                buttons = page.locator(
                    f'[data-lf-margin-for="{target}"] .lf-margin-entry:visible'
                )
                for index in range(buttons.count()):
                    button = buttons.nth(index)
                    button.hover()
                    expect(button).to_have_attribute(
                        "data-lf-label-side", re.compile(".+")
                    )
                    reading = button.evaluate(LABEL_CLEARANCE)
                    assert reading == {"inside": True, "overlaps": 0}


def test_an_unchanged_repaint_cannot_cancel_a_margin_entry_press(browser, serve):
    """The retained margin entry keeps its hit-tested descendants through reconciliation."""
    comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "Hold this thread margin entry across a state repaint.",
        "anchor": {"section": "how-cap"},
    }
    another = {
        **comment,
        "text": "Keep the count badge under the same pointer too.",
    }
    page = open_page(browser, serve(PANEL_PAGE, events=[comment, another]))
    resized(page, 1280, 900)
    marker = page.locator('[data-lf-margin-for="how-cap"] > .lf-margin-marker')
    icon = marker.locator(":scope > .lf-margin-entry-icon")
    badge = marker.locator(":scope > .lf-margin-count")
    icon.evaluate("node => { window.__heldMarginEntryIcon = node; }")
    badge.evaluate("node => { window.__heldMarginEntryBadge = node; }")
    marker.evaluate(
        """button => button.addEventListener('click', () => {
          button.dataset.testClicks = String(Number(button.dataset.testClicks || 0) + 1);
        })"""
    )
    box = badge.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.evaluate(
        """async () => {
          window.dispatchEvent(new Event('resize'));
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
        }"""
    )
    assert icon.evaluate("node => node === window.__heldMarginEntryIcon")
    assert badge.evaluate("node => node === window.__heldMarginEntryBadge")
    page.mouse.up()
    expect(marker).to_have_attribute("data-test-clicks", "1")


def test_lit_margin_projection_reorders_retained_controls_without_moving_the_user(
    browser, serve
):
    """One keyed Lit owner moves native controls across direct, option, and inline seats."""
    fixture = leaf_page("Retained margin controls", '<p id="target">Review this.</p>')
    page = open_page(browser, serve(fixture))
    resized(page, 1440, 900)
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          let swapped = false;
          let changed = false;
          const registration = registerContribution({
            key: 'retained', target: document.querySelector('#target'),
            read: () => ({entries: [
              contributionEntry({key: 'a', glyph: 'A', label: changed ? 'Action A now' : 'Action A',
                rank: swapped ? 'secondary' : 'primary'}),
              contributionEntry({key: 'b', glyph: 'B', label: 'Action B',
                rank: swapped ? 'primary' : 'secondary'}),
              contributionEntry({key: 'c', glyph: 'C', label: 'Action C', rank: 'secondary'}),
            ]}),
            activate: key => {
              window.lfRetainedMarginClicks.push(key);
            },
          });
          window.lfRetainedMarginClicks = [];
          window.lfRetainedMargin = {
            registration,
            swap() {
              swapped = true;
              registration.update({immediate: true});
            },
            change() {
              changed = true;
              registration.update({immediate: true});
            },
          };
        }"""
    )
    host = page.locator('[data-lf-margin-for="target"]')
    more = host.locator(":scope > .lf-margin-more")
    more.click()
    option_b = host.get_by_role("button", name="Action B", exact=True)
    option_b.focus()
    host.evaluate("node => window.lfRetainedMarginHost = node")
    option_b.evaluate("node => window.lfRetainedMarginB = node")

    reading = page.evaluate(
        """() => {
          window.lfRetainedMargin.swap();
          const host = document.querySelector('[data-lf-margin-for="target"]');
          const b = window.lfRetainedMargin.registration.control('b', 'margin', true);
          return {
            sameHost: host === window.lfRetainedMarginHost,
            sameControl: b === window.lfRetainedMarginB,
            focused: document.activeElement === b,
            open: host.hasAttribute('data-lf-options-open'),
            direct: host.querySelector(':scope > [data-lf-margin-entry-primary]')
              ?.dataset.lfMarginEntryKey,
            options: [...host.querySelectorAll(
              ':scope > .lf-margin-options > .lf-margin-entry')]
              .map(node => node.dataset.lfMarginEntryKey),
          };
        }"""
    )
    assert reading == {
        "sameHost": True,
        "sameControl": True,
        "focused": True,
        "open": True,
        "direct": "b",
        "options": ["a", "c"],
    }

    action_a = host.locator('[data-lf-margin-entry-key="a"]')
    expect(action_a).to_have_accessible_name("Action A")
    action_a.evaluate("node => window.lfRetainedMarginA = node")
    box = action_a.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    # Native pointer focus leaves B before arriving at A. That transfer stays
    # inside the cluster, so it must not fold the options under the held press.
    expect(action_a).to_be_focused()
    expect(host).to_have_attribute("data-lf-options-open", "")
    page.evaluate("() => window.lfRetainedMargin.change()")
    expect(action_a).to_have_accessible_name("Action A now")
    assert action_a.evaluate("node => node === window.lfRetainedMarginA")
    page.mouse.up()
    assert page.evaluate("() => window.lfRetainedMarginClicks") == ["a"]

    action_a.focus()
    resized(page, 820, 900)
    resized(page, 1440, 900)
    assert host.evaluate("node => node === window.lfRetainedMarginHost")
    assert action_a.evaluate("node => node === window.lfRetainedMarginA")
    expect(action_a).to_be_focused()
    expect(host).to_have_attribute("data-lf-options-open", "")


def test_lit_inline_margin_projection_keys_controls_inside_thread_chrome(
    browser, serve
):
    """The inline Lit seat reorders one retained control tree and completes its press."""
    page = open_page(browser, serve(PANEL_PAGE))
    open_threads(page)
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          let target = document.createElement('span');
          target.id = 'inline-margin-target';
          target.textContent = 'Inline decision';
          const nextTarget = document.createElement('span');
          nextTarget.id = 'inline-margin-next';
          nextTarget.textContent = 'Next inline decision';
          document.querySelector('.lf-fp-view[data-view="threads"] .lf-fp-list')
            .prepend(target, nextTarget);
          let swapped = false;
          let changed = false;
          const registration = registerContribution({
            key: 'inline-retained', target: () => target,
            read: () => ({entries: (swapped ? ['b', 'a'] : ['a', 'b']).map(key =>
              contributionEntry({key, glyph: key.toUpperCase(),
                label: key === 'a' && changed ? 'Inline A now' : `Inline ${key.toUpperCase()}`}))}),
            activate: key => window.lfInlineMarginClicks.push(key),
          });
          window.lfInlineMarginClicks = [];
          window.lfInlineMargin = {
            registration,
            swap() {
              swapped = true;
              registration.update({immediate: true});
            },
            change() {
              changed = true;
              registration.update({immediate: true});
            },
            retarget() {
              target = nextTarget;
              registration.update({immediate: true});
            },
          };
        }"""
    )
    host = page.locator('[data-lf-margin-for="inline-margin-target"]')
    action_a = host.locator('[data-lf-margin-entry-key="a"]')
    expect(action_a).to_have_accessible_name("Inline A")
    action_a.focus()
    host.evaluate("node => window.lfInlineMarginHost = node")
    action_a.evaluate("node => window.lfInlineMarginA = node")

    reading = page.evaluate(
        """() => {
          window.lfInlineMargin.swap();
          const host = document.querySelector(
            '[data-lf-margin-for="inline-margin-target"]');
          const a = window.lfInlineMargin.registration.control('a', 'inline', true);
          return {
            sameHost: host === window.lfInlineMarginHost,
            sameControl: a === window.lfInlineMarginA,
            focused: document.activeElement === a,
            order: [...host.querySelectorAll(':scope > .lf-margin-entry')]
              .map(node => node.dataset.lfMarginEntryKey),
          };
        }"""
    )
    assert reading == {
        "sameHost": True,
        "sameControl": True,
        "focused": True,
        "order": ["b", "a"],
    }

    # The Threads view grows to hold what was prepended; press where the control
    # stands once that motion has finished.
    rendered(page)
    panel_settled(page, view="threads")
    box = action_a.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.evaluate("() => window.lfInlineMargin.change()")
    expect(action_a).to_have_accessible_name("Inline A now")
    assert action_a.evaluate("node => node === window.lfInlineMarginA")
    page.mouse.up()
    assert page.evaluate("() => window.lfInlineMarginClicks") == ["a"]

    moved = page.evaluate(
        """() => {
          window.lfInlineMargin.retarget();
          const host = document.querySelector('[data-lf-margin-for="inline-margin-next"]');
          const a = window.lfInlineMargin.registration.control('a', 'inline', true);
          return {
            oldRetired: !document.querySelector(
              '[data-lf-margin-for="inline-margin-target"]'),
            newPresented: Boolean(host),
            sameControl: a === window.lfInlineMarginA,
            registered: Boolean(a),
          };
        }"""
    )
    assert moved == {
        "oldRetired": True,
        "newPresented": True,
        "sameControl": True,
        "registered": True,
    }


@pytest.mark.watch_shifts
def test_a_margin_row_is_unseen_until_its_first_placement_lands(browser, serve):
    """A new row keeps its measurable box without painting at the viewport origin."""
    page = open_page(browser, serve(PANEL_PAGE))
    rendered(page)
    unplaced = page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          return new Promise(resolve => requestAnimationFrame(() => {
            const registration = registerContribution({
              key: 'first-placement', target: document.querySelector('#how-cap'),
              read: () => ({entries: [contributionEntry({
                key: 'act', icon: 'dot', label: 'New margin action'
              })]}), activate: () => {}
            });
            const row = registration.control('act', 'margin')
              .closest('.lf-margin-cluster');
            const rect = row.getBoundingClientRect();
            resolve({place: row.dataset.lfPlace ?? null,
              visibility: getComputedStyle(row).visibility,
              width: rect.width, height: rect.height});
          }));
        }"""
    )
    assert unplaced["place"] is None
    assert unplaced["width"] > 0 and unplaced["height"] > 0
    assert unplaced["visibility"] == "hidden"
    margins_laid_out(page)
    host = page.locator('[data-lf-margin-for="how-cap"]')
    expect(host).to_have_attribute("data-lf-place", re.compile("rail|pin"))
    expect(host.get_by_role("button", name="New margin action")).to_be_visible()


@pytest.mark.watch_shifts
def test_a_margin_row_leaves_with_its_target_before_the_next_paint(
    browser, serve, subtests
):
    """A row leaves with its anchored box; a move within one task keeps it.

    Each kind of target stands in a holder of its own on one page, and each case ends
    by removing its holder. Nothing stands below the last holder, so taking the cases
    from the foot of the page up moves nothing the shift watch reads."""
    kinds = ("box", "shadow", "contents")
    holders = []
    for kind in kinds:
        paragraph = '<p style="margin:0">The final target.</p>'
        target = (
            f'<div id="target-{kind}" style="display:contents">{paragraph}</div>'
            if kind == "contents"
            else paragraph.replace("<p ", f'<p id="target-{kind}" ')
        )
        holders.append(f'<div id="holder-{kind}" style="height:120px">{target}</div>')
    page = open_page(
        browser,
        serve(
            leaf_page("Target lifetime", "<h1>Target lifetime</h1>" + "".join(holders))
        ),
    )
    for kind in reversed(kinds):
        with subtests.test(target_kind=kind):
            page.evaluate(
                """async kind => {
              const {contributionEntry, registerContribution} =
                await window.__lfWidgetApi();
              const holder = document.getElementById(`holder-${kind}`);
              const target = document.getElementById(`target-${kind}`);
              if (kind === 'shadow') holder.attachShadow({mode: 'open'}).append(target);
              const anchor = kind === 'contents' ? target.firstElementChild : target;
              window.lifetime = {kind, holder, target, anchor, parent: anchor.parentNode,
                contribution: registerContribution({
                  key: `target-lifetime-${kind}`, target,
                  read: () => ({entries: [contributionEntry({
                    key: 'action', icon: 'dot', label: `Target action ${kind}`
                  })]}), activate: () => {}
                })};
            }""",
                kind,
            )
            margins_laid_out(page)
            action = page.get_by_role("button", name=f"Target action {kind}")
            expect(action).to_be_visible()
            stayed_visible = page.evaluate(
                """async () => {
              lifetime.row = lifetime.contribution.control('action', 'margin')
                .closest('.lf-margin-cluster');
              const destination = document.createElement('div');
              destination.style.display = 'contents';
              lifetime.parent.append(destination);
              lifetime.anchor.remove();
              destination.append(lifetime.anchor);
              lifetime.parent = destination;
              await Promise.resolve();
              return lifetime.row.checkVisibility();
            }"""
            )
            assert stayed_visible
            margins_laid_out(page)
            expect(action).to_be_visible()
            still_visible = page.evaluate(
                """async () => {
              lifetime.anchor.remove();
              await Promise.resolve();
              return lifetime.row.checkVisibility();
            }"""
            )
            assert not still_visible
            rendered(page)
            expect(action).to_be_hidden()
            page.evaluate("""() => {
              if (lifetime.target.style.display === 'contents')
                lifetime.anchor = lifetime.anchor.cloneNode(true);
              lifetime.parent.append(lifetime.anchor);
            }""")
            margins_laid_out(page)
            expect(action).to_be_visible()
            ancestor_visible = page.evaluate(
                """async () => {
              lifetime.holder.remove();
              await Promise.resolve();
              return lifetime.row.checkVisibility();
            }"""
            )
            assert not ancestor_visible
            rendered(page)
            expect(action).to_be_hidden()


def test_margin_projection_keeps_opaque_owner_and_entry_identities_distinct(
    browser, serve
):
    """Owner and entry keys are a coordinate, not a delimiter-encoded string."""
    page = open_page(browser, serve(PANEL_PAGE))
    readings = page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          const target = document.querySelector('#how-cap');
          const first = registerContribution({
            key: 'a:b', target,
            read: () => ({entries: [contributionEntry({
              key: 'c', glyph: '1', label: 'First opaque action'
            })]}), activate: () => {}
          });
          const second = registerContribution({
            key: 'a', target,
            read: () => ({entries: [contributionEntry({
              key: 'b:c', glyph: '2', label: 'Second opaque action'
            })]}), activate: () => {}
          });
          return {
            first: Boolean(first.control('c', 'margin', true)),
            second: Boolean(second.control('b:c', 'margin', true)),
          };
        }"""
    )
    assert readings == {"first": True, "second": True}
    host = page.locator('[data-lf-margin-for="how-cap"]')
    expect(host.get_by_role("button", name="First opaque action")).to_be_visible()
    expect(host.get_by_role("button", name="Second opaque action")).to_be_visible()


def test_every_pin_entry_shares_its_face_and_keeps_its_behavior(browser, serve):
    """The pin face marks placement; status, actions and disclosures keep their meanings."""
    source = leaf_page(
        "Pin controls",
        """
<h1>Pin controls</h1>
<p id="discussion">Check the feeder schedule.</p>
<p>Schedule:
  <lf-suggestion id="schedule">
    <lf-old>Refill each morning.</lf-old>
    <lf-new>Refill when the camera shows it half-empty.</lf-new>
  </lf-suggestion>
</p>
<lf-board id="packing">
  <lf-column id="ready" label="Ready">
    <lf-card id="map"><strong>Print the workshop map</strong></lf-card>
    <lf-card id="signs"><strong>Pack the direction signs</strong></lf-card>
  </lf-column>
</lf-board>
""",
        head="""<style>:root {
          --pin-fill: light-dark(#e7cbff, #4a236b);
          --pin-ink: light-dark(#241343, #fbe8a3);
        }</style>""",
    ).replace("<body>", '<body data-rail="none">')
    events = [
        _comment_on("discussion"),
        _comment_on("schedule"),
    ]
    url = serve(source, events=events)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "packing",
            "action": "move",
            "detail": {"unit": "map", "value": "ready", "rank": "z"},
        },
    )
    page = open_page(browser, url)
    resized(page, 1440, 900)
    cluster = page.locator('[data-lf-margin-for="schedule"]')
    accept = cluster.locator(".lf-sug-accept")
    more = cluster.locator(":scope > .lf-margin-more")
    thread = page.locator('[data-lf-margin-for="discussion"] .lf-margin-marker')
    status = page.locator('.lf-margin-entry[data-lf-kinds="sent"]')
    read_face = """control => {
      const style = getComputedStyle(control);
      const icon = control.querySelector('.lf-margin-entry-icon, .lf-margin-entry-glyph');
      return {
        radius: style.borderRadius,
        background: style.backgroundColor,
        border: [style.borderTopWidth, style.borderTopColor],
        shadow: style.boxShadow,
        ink: getComputedStyle(icon).color,
      };
    }"""

    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        page.mouse.move(0, 0)
        margins_laid_out(page)
        controls = (status, accept, thread, more)
        faces = []
        for control in controls:
            expect(control).to_be_visible()
            expect(control.locator("xpath=..")).to_have_attribute(
                "data-lf-place", "pin"
            )
            faces.append(control.evaluate(read_face))
        assert faces == [faces[0]] * len(faces), faces
        assert faces[0]["radius"] == "6px 6px 6px 0px", faces[0]
        assert faces[0]["background"] == token_colour(page, "--pin-fill"), faces[0]
        assert faces[0]["border"] == ["2px", token_colour(page, "--paper")], faces[0]
        assert faces[0]["ink"] == token_colour(page, "--pin-ink"), faces[0]
        status.hover()
        assert status.evaluate(read_face) == faces[0]
        page.mouse.move(0, 0)

        more.click()
        reject = cluster.locator(".lf-sug-reject")
        expect(reject).to_be_visible()
        page.mouse.move(0, 0)
        page.keyboard.press("Tab")
        assert reject.evaluate(read_face) == faces[0]
        page.keyboard.press("Escape")

    expect(status).to_have_attribute("data-lf-behavior", "status")
    assert status.evaluate(
        "control => control.localName === 'span' && control.tabIndex < 0"
    )
    expect(status).to_have_css("cursor", "default")
    before = events_model.read_events(serve.page_dir)
    status.click()
    assert events_model.read_events(serve.page_dir) == before

    thread.focus()
    thread.press("Enter")
    expect(page.locator(".lf-margin-preview")).to_contain_text(events[0]["text"])
    page.keyboard.press("Escape")
    more.click()
    with sending(page, "reject the suggestion from its pin"):
        reject.press("Enter")
    expect(page.locator("#schedule")).to_have_attribute("data-lf-state", "reject")
    with sending(page, "undo the suggestion rejection"):
        page.keyboard.press("z")
    with sending(page, "accept the suggestion from its pin"):
        accept.click()
    expect(page.locator("#schedule")).to_have_attribute("data-lf-state", "accept")


def test_shadow_targets_keep_common_shape_identity_and_composed_order(browser, serve):
    """Nested, sibling, and slotted targets follow their rendered order."""
    page = open_page(browser, serve(PANEL_PAGE))
    readings = page.evaluate(
        """async () => {
              const { contributionEntry, registerContribution } =
                await window.__lfWidgetApi();
          const makeRecord = label => {
            const shell = document.createElement('div');
            const root = shell.attachShadow({mode: 'open'});
            const target = document.createElement('p');
            target.textContent = `${label} target`;
            root.append(target);
            return {label, shell, target};
          };
          const first = makeRecord('first');
          const nested = makeRecord('nested');
          first.shell.shadowRoot.append(nested.shell);
          const second = makeRecord('second');
          const slottedShell = document.createElement('div');
          const slottedRoot = slottedShell.attachShadow({mode: 'open'});
          slottedRoot.innerHTML = '<slot name="b"></slot><slot name="a"></slot>';
          const makeSlottedRecord = (label, slot) => {
            const target = document.createElement('p');
            target.slot = slot;
            target.textContent = `${label} target`;
            return {label, shell: slottedShell, target};
          };
          const slotA = makeSlottedRecord('slot a', 'a');
          const slotB = makeSlottedRecord('slot b', 'b');
          slottedShell.append(slotA.target, slotB.target);
          const main = document.querySelector('main');
          main.append(first.shell, second.shell, slottedShell);
          const records = [slotA, nested, second, slotB, first];
          for (const record of records) {
            const {target} = record;
            const margin = registerContribution({key: record.label, target,
              read: () => ({entries: [contributionEntry({
                key: record.label, glyph: '!', label: `${record.label} controls`
              })]}), activate: () => {}});
            record.margin = margin;
          }
          await new Promise(done =>
            requestAnimationFrame(() => requestAnimationFrame(done))
          );
          const readings = [first, nested, second, slotA, slotB].map(
            ({label, shell, target, margin}) => {
            const controls = margin.control(label, 'margin');
            return {
            ownsTarget: controls.parentElement?.lfTarget === target,
            inDocument: controls.getRootNode() === document,
            itemCount: shell.shadowRoot.querySelectorAll('.lf-margin-cluster').length,
            commonAction: controls.matches('.lf-margin-entry'),
            width: getComputedStyle(controls).width,
            minHeight: getComputedStyle(controls).minHeight,
            radius: getComputedStyle(controls).borderRadius,
            visibleWord: controls.querySelector('.lf-margin-entry-label')?.textContent,
          }});
          const testTargets = new Set(records.map(({target}) => target));
          const itemOrder = [...document.querySelectorAll(
              '.lf-margin-projection .lf-margin-cluster')]
            .filter(item => testTargets.has(item.lfTarget))
            .map(item => item.lfTarget.textContent);
          records.forEach(({margin, shell}) => { margin.unregister(); shell.remove(); });
          return {readings, itemOrder};
        }"""
    )
    assert readings == {
        "readings": [
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "width": "32px",
                "minHeight": "32px",
                "radius": "6px",
                "visibleWord": "first controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "width": "32px",
                "minHeight": "32px",
                "radius": "6px",
                "visibleWord": "nested controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "width": "32px",
                "minHeight": "32px",
                "radius": "6px",
                "visibleWord": "second controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "width": "32px",
                "minHeight": "32px",
                "radius": "6px",
                "visibleWord": "slot a controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "width": "32px",
                "minHeight": "32px",
                "radius": "6px",
                "visibleWord": "slot b controls",
            },
        ],
        "itemOrder": [
            "first target",
            "nested target",
            "second target",
            "slot b target",
            "slot a target",
        ],
    }


def page_annotation_action_source():
    return leaf_page(
        "Page-owned annotations",
        """
      <h1>Page-owned annotations</h1><p id="subject">A source for contributed actions.</p>
      <lf-draft id="draft"><pre>A draft to revise.</pre></lf-draft>
    """,
    ).replace("<body>", '<body data-annotations="page">')


def test_draw_mode_leaves_page_annotation_controls_usable(browser, serve):
    page = open_page(browser, serve(page_annotation_action_source()))
    page.locator("#subject").hover()
    page.keyboard.press("w")
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    edit = draft_control(page, "edit", "draft")
    assert edit.evaluate("el => getComputedStyle(el).cursor") != "crosshair"
    edit.click()
    expect(page.locator("#draft leaf-text")).to_be_focused()
    draft_control(page, "cancel", "draft").click()
    expect(edit).to_be_visible()
    expect(page.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    expect(page.locator(".lf-drawing-pending")).to_have_count(0)
