"""The document's shared, semantic margin map."""

import re
from datetime import datetime, timedelta

import pytest
from axe_playwright_python.sync_playwright import Axe
from click.testing import CliRunner
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import service as service_model
from leaf import session as session_model
from playwright.sync_api import expect
from render_support import (
    ASK_PAGE,
    BOTH_STAMPS,
    EXAMPLES,
    FEATURE_GALLERY,
    GENERIC_VISUAL_LAYER,
    GENERIC_VISUAL_PAGE,
    GENERIC_VISUAL_WIDGETS,
    PANEL_PAGE,
    SUGGESTION_PAGE,
    _publish,
    _traffic,
    _until,
    compare_with,
    leaf_page,
    live_url,
    margins_laid_out,
    open_page,
    panel_comment,
    panel_settled,
    resized,
    round_trip,
    select,
    sending,
    stamp_page,
    ticked,
    told,
    undo,
    wait_for_revision,
)

pytestmark = pytest.mark.nightly

COMMENT_ON_ASK = {
    "kind": "comment",
    "author": "user",
    "revision": 1,
    "text": "Check whether these jobs can share one visit.",
    "anchor": {"section": "bracket"},
}
ACTION_ON_ASK = {
    "kind": "action",
    "author": "user",
    "revision": 1,
    "widget": "bracket",
    "action": "choose",
    "detail": {"options": ["br-steel"]},
    "generated": [],
    "meaning": {
        "document": {"kind": "page", "revision": 1},
        "coordinate": ["bracket", "bracket", "selection"],
        "depends": ["br-steel", "bracket"],
        "answer": None,
    },
}
RECEIPT_PHASES = {
    "Sent": "sent",
    "Waiting for pickup": "waiting",
    "Picked up": "pickup",
}
COMMENT_ON_SUGGESTION = {
    "kind": "comment",
    "author": "user",
    "revision": 1,
    "text": "Check this wording before accepting it.",
    "anchor": {"section": "sug-refill"},
}
COMMENT_ON_SECOND_SUGGESTION = {
    "kind": "comment",
    "author": "agent",
    "revision": 1,
    "text": "This one can wait for the autumn order.",
    "anchor": {"section": "sug-thistle"},
}


def test_margin_layout_batches_the_composed_page_without_refolding_controls(
    browser, serve
):
    """Layout work is bounded by phases, not the number of contributed controls.

    The corpus used to force 26 layouts and 44 style recalculations per unchanged
    pass (about 45 ms in local Chrome). Count the browser's work rather than time;
    the contributor's primary/overflow state must also remain untouched.
    """
    corpus = next(example for example in EXAMPLES if example.stem == "corpus")
    page, errors = open_page(browser, serve(corpus))
    resized(page, 1440, 900)
    margins_laid_out(page)
    assert page.locator(".lf-margin-item").count() >= 15
    session = page.context.new_cdp_session(page)
    session.send("Performance.enable")
    before = {
        metric["name"]: metric["value"]
        for metric in session.send("Performance.getMetrics")["metrics"]
    }
    reading = page.evaluate(
        """async () => {
          const {layoutMarginRows} = await import('/runtime/margin-layout.js');
          const rows = [...document.querySelectorAll('.lf-margin-item')];
          const boxes = () => rows.map(row => {
            const {x, y, width, height} = row.getBoundingClientRect();
            return {x, y, width, height};
          });
          const before = boxes();
          // Collected from the callback rather than by `takeRecords` alone: letting a
          // frame settle passes a microtask checkpoint, which delivers the records to
          // the callback and empties the queue a bare `takeRecords` would read.
          const seen = [];
          const observer = new MutationObserver(list => seen.push(...list));
          observer.observe(document.body, {subtree: true, attributes: true,
            attributeFilter: ['data-lf-button-primary', 'data-lf-button-overflow']});
          for (let i = 0; i < 5; i++) layoutMarginRows();
          const mutations = seen.length + observer.takeRecords().length;
          observer.disconnect();
          return {before, after: boxes(), mutations};
        }"""
    )
    after = {
        metric["name"]: metric["value"]
        for metric in session.send("Performance.getMetrics")["metrics"]
    }
    session.detach()
    assert reading["mutations"] == 0
    assert reading["after"] == reading["before"]
    work = {
        name: after[name] - before[name] for name in ("LayoutCount", "RecalcStyleCount")
    }
    assert all(count <= 30 for count in work.values()), work
    assert errors == []
    page.close()


def test_a_settled_page_with_a_standing_reaction_stops_rendering_its_margin(
    browser, serve
):
    """A chrome layout pass repacks the margin's rows; it does not restate its offers.

    `syncLayout` ends in the anchor runtime's `dockSeats`, and the here-paint frame
    ends in `syncLayout`; a margin render ends in `paintKeys`, which ends in the next
    `paintHere`. So a `dockSeats` that restated every seat's offer closed a cycle —
    chrome layout, margin render, paint, chrome layout — on any page carrying a
    standing reaction, and the gallery ran a whole margin render every frame with
    nothing dispatched and nothing on the page moving. Measured then: ~350ms of main
    thread per frame, which is also long enough that every Playwright read of that
    page waits on it.

    The reaction seat is asserted first, because it is the ingredient the cycle needed:
    with no seat `dockSeats` visits nothing and a page passes this without saying
    anything. The heartbeat is the one render a settled page is allowed here, and it
    comes every two seconds, so at most one of these frames can carry it.
    """
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    resized(page, 1280, 900)
    margins_laid_out(page)
    assert page.locator(".lf-react-mark").count() >= 1

    layouts = page.evaluate(
        """async frames => {
          const frame = () => new Promise(resolve => requestAnimationFrame(resolve));
          for (let i = 0; i < 10; i++) await frame();
          let seen = 0;
          const count = () => { seen += 1; };
          document.addEventListener('lf-margin-layout', count);
          for (let i = 0; i < frames; i++) await frame();
          document.removeEventListener('lf-margin-layout', count);
          return seen;
        }""",
        30,
    )

    assert layouts <= 1, layouts
    assert errors == []
    page.close()


def test_unchanged_margin_refresh_cost_is_bounded_by_refresh_count(browser, serve):
    """A heartbeat refresh cannot force layout once per Page-map location."""
    corpus = next(example for example in EXAMPLES if example.stem == "corpus")
    page, errors = open_page(browser, serve(corpus))
    resized(page, 1440, 900)
    margins_laid_out(page)
    assert page.locator(".lf-margin-item").count() >= 15
    session = page.context.new_cdp_session(page)
    session.send("Performance.enable")
    before = {
        metric["name"]: metric["value"]
        for metric in session.send("Performance.getMetrics")["metrics"]
    }
    refreshes = 5
    geometry_reads = page.evaluate(
        """refreshes => {
          const main = document.querySelector('main');
          const rect = main.getBoundingClientRect.bind(main);
          let reads = 0;
          main.getBoundingClientRect = () => {
            reads += 1;
            return rect();
          };
          for (let i = 0; i < refreshes; i++)
            document.dispatchEvent(new CustomEvent('lf-actions'));
          main.getBoundingClientRect = rect;
          return reads;
        }""",
        refreshes,
    )
    after = {
        metric["name"]: metric["value"]
        for metric in session.send("Performance.getMetrics")["metrics"]
    }
    session.detach()
    work = {
        name: after[name] - before[name]
        for name in (
            "LayoutCount",
            "RecalcStyleCount",
        )
    }
    # The write-on-change guards keep the corpus at 8 layouts and 57–58 style
    # recalculations over five refreshes. These bounds leave room for browser
    # bookkeeping while refusing the 33 / 127–128 regression from unconditional writes.
    assert work["LayoutCount"] <= refreshes * 4, work
    assert work["RecalcStyleCount"] <= refreshes * 18, work
    assert geometry_reads == refreshes, geometry_reads
    assert errors == []
    page.close()


# Both pages stand still with nothing dispatched, so both give the settled reading:
# ten frames on an untouched page report no record at all. That is a property of the
# runtime rather than of either fixture, and a recent one — before #298 stopped
# `dockSeats` restating every seat's offer, the same ten frames on the gallery
# reported about 1700 records with nothing dispatched.
HEARTBEAT_PAGES = (
    # The corpus is the widest margin the examples draw: 31 items on this viewport,
    # more than half of them docked out in the document beside their targets. It is
    # also the page whose rows are withheld — 29 of the 31 it draws wear `lf-waiting`
    # at this viewport — so the posture clear and the rail re-read are read here.
    # None of the two that hang stands beside the other, so nothing is pushed.
    pytest.param(
        next(example for example in EXAMPLES if example.stem == "corpus"),
        {".lf-margin-item": 15},
        {"row posture", "rail width", "fold rule"},
        id="corpus",
    ),
    # The gallery draws the fittings the corpus has none of, and the writers that only
    # run for those are watched nowhere else: a reading option under an entry holding
    # several readings, and the readings whose move is made, which wear the `status`
    # behavior on a span seat rather than a button. Every row it draws hangs, so no
    # posture is cleared off one and the rail is not re-read; two of them stand where
    # they would overlap, so the push measurement is read here and nowhere else.
    pytest.param(
        FEATURE_GALLERY,
        {
            ".lf-margin-item": 10,
            ".lf-margin-reading-option": 1,
            '.lf-margin-button[data-lf-behavior="status"]': 2,
        },
        {"row push", "fold rule"},
        id="gallery",
    ),
)


@pytest.mark.parametrize("page_source, population, measurements", HEARTBEAT_PAGES)
def test_an_unchanged_heartbeat_restates_no_margin_name(
    browser, serve, page_source, population, measurements
):
    """The heartbeat must not rewrite a name, state, or word it is not changing.

    `render` is bound to `lf-actions`, so an unconditional write here restates
    itself every two seconds on a page nobody has touched: the mutation stream a
    screen reader rebuilds its buffer from, and a dirty box for whatever reads
    next. The corpus used to restate 205 attributes and the Page-map button's
    words on every pass.

    What the pass wrote without changing anything is one reading rather than two.
    An attribute the pass leaves carrying the value it opened with said nothing,
    whether one writer restated it or two took turns over it — and the turns are
    the reading a same-value predicate cannot take, because each leg differs from
    the value before it. Both are records a reader rebuilds from, and the second
    kind is what `leaf.js`'s disclosure watch reads as news. So `news` stays as
    its own reading: a watched attribute that ends the pass somewhere new repaints
    the page's keys, and that is a change rather than a restatement.

    The margin is not the nav: `render` docks every host with offers beside its
    own perch out in the document, which on both pages is more of the margin than
    the nav holds, and `syncInlineOffers` builds another host in place wherever an
    offer's target stands in chrome. So the watch is rooted at every host of
    either kind, and the reach is asserted the way the population is — a run where
    the docked hosts stopped being watched would otherwise return the same clean
    `[]` it returns when nothing is wrong. No shipped page draws an inline host at
    rest, so that second root is reach rather than a reading taken here.

    One page cannot state the reach on its own either: the corpus draws no reading
    option and no status reading, so the writers those two fittings reach ran
    unwatched until the gallery was read beside it. Each page therefore names the
    population it is here for.

    Half of `render` runs in a frame callback — `scheduleMarginLayout`,
    `scheduleRoving` and `scheduleButtonLabels` are its whole tail — and five
    dispatches in one synchronous task never reach it. Each beat is therefore read
    across a settled frame, which both pages now allow. The measurements each page
    is expected to show are named beside its population and asserted exactly, so a
    run that stopped letting the frame run could not return `[]` and look clean.

    What remains on that reading is not a name being restated: each entry in the
    probe table is a measurement that modifies the DOM to read it and puts it back.
    Naming them here rather than filtering them keeps the account honest in both
    directions — a new unchanged write cannot arrive unnamed, and closing a probe
    turns this red rather than passing quietly.
    """
    page, errors = open_page(browser, serve(page_source))
    resized(page, 1440, 900)
    margins_laid_out(page)
    for selector, least in population.items():
        assert page.locator(selector).count() >= least, selector
    heartbeat = page.evaluate(
        """async ({refreshes}) => {
          const frame = () => new Promise(
            resolve => requestAnimationFrame(() => setTimeout(resolve, 0)));
          const text = nodes => [...nodes].map(node => node.textContent).join('');
          const hosts = [...document.querySelectorAll('.lf-margin-item'),
            ...document.querySelectorAll(
              'div.lf-ui[data-lf-margin-for]:not(.lf-margin-item)')];
          const roots = [document.querySelector('nav.lf-living-margin'),
                         document.querySelector('.lf-page-map-toggle'), ...hosts];
          // Collected from the callback rather than by `takeRecords` alone: letting a
          // frame settle passes a microtask checkpoint, which delivers the records to
          // the callback and empties the queue a bare `takeRecords` would read.
          const seen = [];
          const observer = new MutationObserver(list => seen.push(...list));
          for (const root of roots)
            observer.observe(root, {subtree: true, childList: true,
              characterData: true, characterDataOldValue: true,
              attributes: true, attributeOldValue: true});
          const on = record => record.target.className || record.target.nodeName;
          const hangs = value => /lf-(docked|waiting)/.test(value ?? '');
          const pushed = value => /transform:/.test(value ?? '');
          const probes = [
            ['row posture',
             'margin-layout clears the docked and waiting classes off a row '
             + 'to measure where it can hang',
             (record, pass) => record.attributeName === 'class'
               && record.target.matches('.lf-margin-item')
               // Asked of the write rather than of the row: a docked row carries the
               // tokens from one end of the pass to the other, so reading them off
               // the target files every same-value `class` write on that row under
               // this probe, including one from a writer that has nothing to do with
               // the measurement. The clear moves a token off and the re-mark moves
               // it back; a name restated moves neither.
               && hangs(record.oldValue) !== hangs(pass.wrote.get(record))],
            ['row push',
             'margin-layout clears the push off a hanging row to measure where it '
             + 'naturally sits, then pushes it clear of the row above again',
             // Asked of the write for the same reason the posture is: a pushed row
             // carries its transform across the whole pass, so reading `style` off
             // the target would file a restated `top` from another writer here. The
             // clear takes the transform off and the pack puts it back.
             (record, pass) => record.attributeName === 'style'
               && record.target.matches('.lf-margin-item')
               && pushed(record.oldValue) !== pushed(pass.wrote.get(record))],
            ['rail width',
             'margin-layout reads the rail again once the docked rows are back in flow',
             record => record.attributeName === 'style'
               && record.target.matches('nav.lf-living-margin')],
            ['fold rule',
             'controlsShownByOwner lifts the fold rule off a contributed control to '
             + 'read how its owner paints it',
             record => record.attributeName === 'data-lf-button-primary'
               && record.target.matches('.lf-margin-button')],
          ];
          const probe = (record, pass) =>
            probes.find(([, , holds]) => holds(record, pass))?.[0] ?? null;
          const unchanged = [];
          const news = [];
          for (let i = 0; i < refreshes; i++) {
            document.dispatchEvent(new CustomEvent('lf-actions'));
            await frame();
            await frame();
            seen.push(...observer.takeRecords());
            const records = seen.splice(0);
            // The value each attribute carried before this pass touched it, and the
            // last write of it, so the pass can be asked what it left standing rather
            // than what each write said.
            const opened = new Map();
            // What each write said, which no record carries: a record holds the value
            // it replaced, so the next write of that attribute holds this one's
            // result, and the last write's result is what the attribute reads now.
            const wrote = new Map();
            for (const record of records) {
              if (record.type !== 'attributes') continue;
              let byName = opened.get(record.target);
              if (!byName) opened.set(record.target, byName = new Map());
              let entry = byName.get(record.attributeName);
              if (!entry)
                byName.set(record.attributeName,
                  entry = {opening: record.oldValue, last: null});
              if (entry.last) wrote.set(entry.last, record.oldValue);
              entry.last = record;
            }
            for (const [target, byName] of opened)
              for (const [name, entry] of byName)
                wrote.set(entry.last, target.getAttribute(name));
            const pass = {wrote};
            for (const record of records) {
              if (record.type === 'attributes') {
                const now = record.target.getAttribute(record.attributeName);
                const {opening} =
                  opened.get(record.target).get(record.attributeName);
                if (opening === now)
                  unchanged.push({on: on(record), wrote: record.attributeName,
                                  said: opening, probe: probe(record, pass)});
                if (['open', 'aria-expanded'].includes(record.attributeName)
                    && now !== record.oldValue)
                  news.push({on: on(record), wrote: record.attributeName,
                             was: record.oldValue, now});
              } else if (record.type === 'characterData') {
                if (record.oldValue === record.target.data)
                  unchanged.push({on: on(record), wrote: 'text',
                                  said: record.oldValue, probe: null});
              } else if (text(record.removedNodes) === text(record.addedNodes)
                         && record.removedNodes.length > 0)
                unchanged.push({on: on(record), wrote: 'children',
                                said: text(record.addedNodes), probe: null});
            }
          }
          observer.disconnect();
          return {
            unchanged, news,
            probes: probes.map(([name]) => name),
            docked: hosts.filter(host => !host.closest('nav.lf-living-margin')).length,
            hosts: hosts.length,
          };
        }""",
        {"refreshes": 5},
    )
    unnamed = [row for row in heartbeat["unchanged"] if row["probe"] is None]
    assert unnamed == [], unnamed
    assert heartbeat["news"] == [], heartbeat["news"]
    # The reach the readings above are worth: the nav alone would leave more than
    # half of either page's hosts, and every writer under them, unwatched, and a
    # reading that stopped settling would see none of the frame's measurements.
    assert heartbeat["docked"] >= heartbeat["hosts"] / 2, heartbeat
    assert measurements <= set(heartbeat["probes"]), measurements
    assert {row["probe"] for row in heartbeat["unchanged"]} == measurements, heartbeat[
        "unchanged"
    ]
    assert errors == []
    page.close()


def test_an_unchanged_heartbeat_re_marks_no_docked_row(browser, serve):
    """A row the pass leaves docked is not marked docked again.

    `layoutMarginRows` reads the standing posture before it clears anything and
    leaves a row that still cannot hang where it is, so that row skips the clear
    and reaches the placement loop already carrying `lf-docked`. `add`
    re-serializes `class` whether or not the token is new, and this pass runs on
    the heartbeat through `render`'s tail, so the unguarded mark was a same-value
    `class` write per docked row every two seconds: a record a screen reader
    rebuilds its buffer from, for a row that did not move. Measured on this
    fixture before the guard, five beats wrote `class` five times.

    Neither page the heartbeat reading above is taken on can state it. The corpus
    stands still, but every row it draws hangs, and the compact posture that would
    dock them withholds them as `lf-waiting` instead; the gallery stands still too
    now, but it docks no row at that viewport at all — measured, none of the
    eighteen it draws wears `lf-docked`. The posture is therefore reached directly:
    under `COVERING` a contributed row cannot hang whatever the local room, and a
    page with one target settles.

    The guard must not cost the mark, so the narrowing is read too — the row
    arrives hanging, and it is the pass that docks it. The pass itself is counted
    off `lf-margin-layout`, which `layoutMarginRows` dispatches after the marks:
    a window that stopped reaching the layout would otherwise return the same
    clean reading a guarded one does.
    """
    fixture = leaf_page("Docked reading", '<p id="target">Target passage</p>')
    page, errors = open_page(browser, serve(fixture))
    resized(page, 1440, 900)
    page.evaluate(
        """async () => {
          const {offer, marginButton, registerMarginItem} =
            await import('/runtime/widget-api.js');
          const controls = document.createElement('span');
          controls.append(marginButton(offer('button', ''), {
            key: 'act', icon: 'dot', label: 'Act on the target', role: 'primary'}));
          registerMarginItem({key: 'target', target: document.getElementById('target'),
            controls});
        }"""
    )
    margins_laid_out(page)
    row = page.locator(".lf-margin-item")
    expect(row).to_have_count(1)
    expect(row).not_to_have_class(re.compile(r"lf-docked"))
    # Inside the covering boundary, which is 840px wide.
    resized(page, 800, 900)
    margins_laid_out(page)
    expect(row).to_have_class(re.compile(r"lf-docked"))
    marks = page.evaluate(
        """async refreshes => {
          const frame = () => new Promise(
            resolve => requestAnimationFrame(() => setTimeout(resolve, 0)));
          const wrote = [];
          // The reading has to say the pass ran: a window that never reaches
          // `layoutMarginRows` returns the same clean `[]` a guarded one does.
          let passes = 0;
          document.addEventListener('lf-margin-layout', () => passes++);
          const observer = new MutationObserver(list => wrote.push(...list));
          observer.observe(document.body, {subtree: true, attributes: true,
            attributeOldValue: true, attributeFilter: ['class']});
          for (let i = 0; i < refreshes; i++) {
            document.dispatchEvent(new CustomEvent('lf-actions'));
            await frame(); await frame();
          }
          wrote.push(...observer.takeRecords());
          observer.disconnect();
          return {passes, marks: wrote
            .filter(record => record.target.matches('.lf-margin-item'))
            .map(record => ({was: record.oldValue,
                             now: record.target.getAttribute('class')}))};
        }""",
        5,
    )
    assert marks == {"passes": 5, "marks": []}, marks
    expect(row).to_have_class(re.compile(r"lf-docked"))
    assert errors == []
    page.close()


def test_an_option_proxy_writes_no_relation_its_source_has_no_writer_for(
    browser, serve
):
    """A Button rebuilt from a record keeps the relation writer the record names.

    `optionControlNode` builds the options group's proxy from `buttonRecord`, so a
    declaration that stops at the call site is re-inferred there: the proxy takes
    the disclosure default, writes `aria-expanded`, and `syncForwardedButtonState`
    reads `null` off the source and strips it again the same pass. That is an add
    and a remove every heartbeat, and news to the document's disclosure watch, for
    exactly the fitting the declaration was added for — a module contributing a
    reading whose relation another writer owns. No shipped page draws one, so the
    seam is stated here rather than on the corpus.
    """
    fixture = leaf_page("Forwarded reading", '<p id="target">Target passage</p>')
    page, errors = open_page(browser, serve(fixture))
    resized(page, 1440, 900)
    page.evaluate(
        """async () => {
          const {offer, marginButton, registerMarginItem} =
            await import('/runtime/widget-api.js');
          const controls = document.createElement('span');
          controls.append(
            marginButton(offer('button', ''), {
              key: 'act', icon: 'dot', label: 'Act on the target', role: 'primary'
            }),
            // The reading whose `aria-expanded` this module owns rather than the
            // margin: a disclosure that declares its writer away.
            marginButton(offer('span', ''), {
              key: 'read', icon: 'dot', label: 'Read the target',
              behavior: 'disclosure', role: 'reading', writesRelation: false
            }),
          );
          registerMarginItem({key: 'target', target: document.getElementById('target'),
            controls});
        }"""
    )
    margins_laid_out(page)
    proxy = page.locator(".lf-margin-option-proxy")
    expect(proxy).to_have_count(1)
    relation = page.evaluate(
        """refreshes => {
          const group = document.querySelector('.lf-margin-options');
          const records = [];
          const observer = new MutationObserver(list => records.push(...list));
          observer.observe(group, {subtree: true, attributes: true,
            attributeOldValue: true, attributeFilter: ['aria-expanded']});
          for (let i = 0; i < refreshes; i++)
            document.dispatchEvent(new CustomEvent('lf-actions'));
          records.push(...observer.takeRecords());
          observer.disconnect();
          return {
            wrote: records.map(record => ({
              on: record.target.className,
              was: record.oldValue,
              now: record.target.getAttribute('aria-expanded'),
            })),
            standing: document.querySelector('.lf-margin-option-proxy')
              .getAttribute('aria-expanded'),
          };
        }""",
        5,
    )
    assert relation["wrote"] == [], relation["wrote"]
    assert relation["standing"] is None, relation
    assert errors == []
    page.close()


def test_an_unchanged_compact_margin_keeps_the_reader_at_the_document_end(
    browser, serve
):
    """Re-laying docked controls cannot pull a reader back from the bottom."""
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    resized(page, 700, 500)
    margins_laid_out(page)
    assert page.locator(".lf-margin-item.lf-docked").count() >= 10

    position = page.evaluate(
        """async () => {
          const frame = () => new Promise(resolve => requestAnimationFrame(resolve));
          window.scrollTo(0, document.documentElement.scrollHeight);
          await frame();
          const reading = () => ({
            y: window.scrollY,
            end: document.documentElement.scrollHeight - window.innerHeight,
          });
          const before = reading();
          const laidOut = new Promise(resolve =>
            document.addEventListener('lf-margin-layout', resolve, {once: true})
          );
          document.dispatchEvent(new CustomEvent('lf-actions'));
          await laidOut;
          await frame();
          return {before, after: reading()};
        }"""
    )

    assert position["before"]["y"] == position["before"]["end"]
    assert position["after"] == position["before"]
    assert errors == []
    page.close()


def test_a_docked_cluster_keeps_later_margin_buttons_beside_their_targets(
    browser, serve
):
    """A wide cluster that has to dock stays with its target inside a section."""
    fixture = leaf_page(
        "Mixed margin postures",
        '<section><p id="first">First target</p>'
        '<p id="between">Unrelated intervening prose</p>'
        '<p id="second">Second target</p></section>',
    )
    page, errors = open_page(browser, serve(fixture))
    page.evaluate(
        """async () => {
          const {offer, marginButton, registerMarginItem} =
            await import('/runtime/widget-api.js');
          for (const [id, count] of [['first', 8], ['second', 1]]) {
            const controls = document.createElement('span');
            for (let i = 0; i < count; i++) controls.append(
              marginButton(offer('button', ''), {
                key: `action-${i}`, icon: 'dot', label: `Action ${i} for ${id}`,
                role: i ? 'secondary' : 'primary'
              })
            );
            registerMarginItem({key: id, target: document.getElementById(id), controls,
              claim: false, state: count > 1 ? 'engaged' : 'idle'});
          }
        }"""
    )
    first = page.locator('[data-lf-margin-for="first"]')
    second = page.locator('[data-lf-margin-for="second"]')
    for width in (1440, 1200, 1000, 1440):
        resized(page, width, 900)
        margins_laid_out(page)
        assert ("lf-docked" in first.get_attribute("class")) == (width <= 1000)
        expect(second).not_to_have_class(re.compile(r"\blf-docked\b"))
        assert second.bounding_box()["y"] == pytest.approx(
            page.locator("#second").bounding_box()["y"], abs=1
        )
        if width <= 1000:
            assert first.evaluate(
                "item => item.previousElementSibling === document.querySelector('#first')"
            ), "the docked controls were severed from their target by later prose"
        else:
            assert first.evaluate(
                "item => item.parentElement === document.querySelector('main')"
            )
    assert errors == []
    page.close()


def test_a_transient_button_label_avoids_the_next_margin_button(browser, serve):
    """A tooltip moves rather than covering a neighboring Button."""
    fixture = leaf_page(
        "Close margin labels",
        '<p id="first">First target</p><p id="second">Second target</p>',
    )
    page, errors = open_page(browser, serve(fixture))
    resized(page, 1440, 900)
    page.evaluate(
        """async () => {
          const {offer, marginButton, registerMarginItem} =
            await import('/runtime/widget-api.js');
          for (const id of ['first', 'second']) {
            registerMarginItem({key: id, target: document.getElementById(id),
              controls: marginButton(offer('button', ''), {
                key: 'act', icon: 'dot', label: `Act on ${id}`
              })});
          }
        }"""
    )
    first = page.locator('[data-lf-margin-for="first"]')
    second = page.locator('[data-lf-margin-for="second"]')
    button = first.get_by_role("button", name="Act on first", exact=True)
    button.hover()
    expect(button).to_have_attribute("data-lf-label-side", re.compile(".+"))
    label = button.locator(".lf-margin-button-label")
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
    assert errors == []
    page.close()


@pytest.mark.parametrize("width", [1440, 390])
def test_dense_suggestion_labels_cover_no_neighboring_button(browser, serve, width):
    """Every label in a tightly stacked real cluster finds a clear side."""
    page, errors = open_page(browser, serve(DENSE_SUGGESTIONS_PAGE))
    resized(page, width, 900)
    page.locator("#bg-neighbors").scroll_into_view_if_needed()
    for target in ("bg-neighbor-a", "bg-neighbor-b", "bg-neighbor-c"):
        buttons = page.locator(
            f'[data-lf-margin-for="{target}"] .lf-margin-button:visible'
        )
        for index in range(buttons.count()):
            button = buttons.nth(index)
            button.hover()
            expect(button).to_have_attribute("data-lf-label-side", re.compile(".+"))
            reading = button.evaluate(
                """control => {
                  const label = control.querySelector('.lf-margin-button-label');
                  const box = label.getBoundingClientRect();
                  const overlap = (left, right) => left.left < right.right &&
                    left.right > right.left && left.top < right.bottom &&
                    left.bottom > right.top;
                  const neighbors = [...document.querySelectorAll('.lf-margin-button')]
                    .filter(candidate => candidate !== control && candidate.checkVisibility())
                    .map(candidate => candidate.getBoundingClientRect());
                  return {inside: box.left >= 4 && box.right <= innerWidth - 4 &&
                    box.top >= 4 && box.bottom <= innerHeight - 4,
                    overlaps: neighbors.filter(neighbor => overlap(box, neighbor)).length};
                }"""
            )
            assert reading == {"inside": True, "overlaps": 0}
    assert errors == []
    page.close()


def test_an_unchanged_repaint_cannot_cancel_a_button_press(browser, serve):
    """The retained Button keeps its hit-tested descendants through reconciliation."""
    comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "Hold this Thread Button across a state repaint.",
        "anchor": {"section": "how-cap"},
    }
    another = {
        **comment,
        "text": "Keep the count badge under the same pointer too.",
    }
    page, errors = open_page(browser, serve(PANEL_PAGE, events=[comment, another]))
    resized(page, 1280, 900)
    marker = page.locator('[data-lf-margin-for="how-cap"] > .lf-margin-marker')
    icon = marker.locator(":scope > .lf-margin-button-icon")
    badge = marker.locator(":scope > .lf-margin-count")
    icon.evaluate("node => { window.__heldButtonIcon = node; }")
    badge.evaluate("node => { window.__heldButtonBadge = node; }")
    marker.evaluate(
        """button => button.addEventListener('click', () => {
          button.dataset.testClicks = String(Number(button.dataset.testClicks || 0) + 1);
        })"""
    )
    box = badge.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.evaluate("() => document.dispatchEvent(new CustomEvent('lf-actions'))")
    assert icon.evaluate("node => node === window.__heldButtonIcon")
    assert badge.evaluate("node => node === window.__heldButtonBadge")
    page.mouse.up()
    expect(marker).to_have_attribute("data-test-clicks", "1")
    assert errors == []
    page.close()


def resized_shell(page, inline_size, height):
    """Resize by the container's own width, independent of scrollbar posture."""
    viewport_width = page.viewport_size["width"]
    resized(page, viewport_width, height)
    for _ in range(3):
        shell_width = page.evaluate("() => document.body.getBoundingClientRect().width")
        difference = inline_size - shell_width
        if abs(difference) <= 0.5:
            return
        viewport_width += round(difference)
        resized(page, viewport_width, height)
    assert page.evaluate(
        "() => document.body.getBoundingClientRect().width"
    ) == pytest.approx(inline_size, abs=0.5)


ACTION_PAGE = SUGGESTION_PAGE.replace(
    "<main>", '<main><section id="action-section">'
).replace(
    "</main>",
    """
<lf-draft id="draft-ops"><pre>
  Run the migration before deploying.
</pre></lf-draft>
<div style="height: 500px" aria-hidden="true"></div>
    </section></main>""",
)
BUTTON_KEYBOARD_PAGE = SUGGESTION_PAGE.replace(
    '<p id="replace">',
    '<a id="before-buttons" href="#replace">Before Buttons</a><p id="replace">',
    1,
).replace(
    '<p id="insert">',
    '<a id="after-buttons" href="#insert">After Buttons</a><p id="insert">',
    1,
)
UNID_SELECTION_PAGE = PANEL_PAGE.replace('<p id="how-cap">', "<p>")
DENSE_SUGGESTIONS_PAGE = leaf_page(
    "Dense suggestions",
    """<p id="bg-neighbors">Pack
  <lf-suggestion id="bg-neighbor-a"><lf-old>two</lf-old><lf-new>three</lf-new></lf-suggestion>
  pencils,
  <lf-suggestion id="bg-neighbor-b"><lf-old>red</lf-old><lf-new>blue</lf-new></lf-suggestion>
  paper, and a
  <lf-suggestion id="bg-neighbor-c"><lf-old>large</lf-old><lf-new>small</lf-new></lf-suggestion>
  map.</p>""",
)
PAGE_MAP_PAGE = leaf_page(
    "Twelve Page-map locations",
    "".join(
        f'<section id="map-{n}" style="min-height: 420px">'
        f"<h2>Location {n}</h2><p>Body {n}</p></section>"
        for n in range(1, 13)
    ),
)
PAGE_MAP_EVENTS = [
    {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": f"Map note {n}",
        "anchor": {"section": f"map-{n}"},
    }
    for n in range(1, 13)
]


@pytest.mark.parametrize("width", [1200, 390])
def test_ask_addresses_follow_the_feature_gallery_s_visible_margin_controls(
    browser, serve, width
):
    """A secondary action's visible proxy gets its canonical Ask address."""
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    resized(page, width, 900)
    margins_laid_out(page)

    # Twice: the gallery's core surfaces open on a decision, which is the page's first
    # ask and carries no address of its own, and the suggestions this case is about
    # begin after it.
    page.keyboard.press("a")
    expect(page.locator("#bg-choice-ask")).to_be_focused()
    page.keyboard.press("a")
    expect(page.locator("#bg-replace")).to_be_focused()
    expect(page.locator(".lf-ask-addresses > .lf-ask-address")).to_have_text(["1", "2"])
    geometry = page.evaluate(
        """() => {
          const item = document.querySelector('[data-lf-margin-for="bg-replace"]');
          const boxes = (nodes) => nodes.map((node) => {
            const box = node.getBoundingClientRect();
            return {x: box.left + box.width / 2, y: box.top + box.height / 2};
          });
          const controls = [...item.querySelectorAll('button')].filter((button) => {
            const box = button.getBoundingClientRect();
            return box.width && /^(Accept|Reject) the /.test(button.ariaLabel);
          });
          return {
            controls: controls.map((control) => {
              const box = control.getBoundingClientRect();
              return {x: box.left, y: box.top};
            }),
            chips: boxes([...document.querySelectorAll(
              '.lf-ask-addresses > .lf-ask-address'
            )]),
          };
        }"""
    )
    assert len(geometry["controls"]) == len(geometry["chips"]) == 2, geometry
    for control, chip in zip(geometry["controls"], geometry["chips"], strict=True):
        assert abs(control["x"] - chip["x"]) <= 2, geometry
        assert abs(control["y"] - chip["y"]) <= 2, geometry

    assert errors == []
    page.close()


@pytest.mark.parametrize("width", [1440, 1200, 700, 390])
def test_the_feature_gallery_keeps_its_real_actions_reachable(browser, serve, width):
    """The developer sampler stays usable after edits, verdicts, and dense overflow."""
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    resized(page, width, 900)

    for target, outcome, receipt in (
        ("bg-replace", "accept", "Accepted"),
        ("bg-insert", "reject", "Rejected"),
        ("bg-delete", "accept", "Accepted"),
    ):
        item = page.locator(f'[data-lf-margin-for="{target}"]')
        controls = page.locator(f'.lf-sug-actions[data-lf-for="{target}"]')
        item.get_by_role("button", name=re.compile(f"^{outcome.title()} the ")).click()
        round_trip(page)
        expect(controls.locator(".lf-sug-receipt")).to_have_text(receipt)
        controls.get_by_role("button", name=re.compile("^Undo ")).click()
        round_trip(page)
        expect(
            item.get_by_role("button", name=re.compile("^Accept the "))
        ).to_be_visible()
        expect(
            item.get_by_role("button", name=re.compile("^Reject the "))
        ).to_be_visible()

    draft_item = page.locator('[data-lf-margin-for="bg-draft"]')
    draft_item.locator(".lf-draft-pencil").click()
    editor = page.locator("#bg-draft textarea")
    body = "The workshop moved outdoors.\nBring a folding chair."
    editor.fill(body)
    page.locator("#bg-editing-guide").click()
    expect(draft_item.get_by_role("button", name="Save", exact=True)).to_be_visible()
    expect(draft_item.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    expect(draft_item.locator(".lf-margin-more")).to_be_hidden()
    draft_item.get_by_role("button", name="Save", exact=True).click()
    round_trip(page)
    expect(page.locator("#bg-draft .lf-draft-body")).to_have_text(body)
    page.reload(wait_until="load")
    page.wait_for_function(BOTH_STAMPS)
    expect(page.locator("#bg-draft .lf-draft-body")).to_have_text(body)

    crowded = page.locator('[data-lf-margin-for="bg-crowded"]')
    expect(crowded.locator(".lf-margin-button:visible")).to_have_count(2)
    crowded.locator(".lf-margin-more").click()
    expect(crowded.locator(".lf-margin-button:visible")).to_have_count(6)
    spill = crowded.locator(".lf-margin-spill")
    spill.click()
    sheet = page.get_by_role("dialog", name="Page map", exact=True)
    reaction = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("token") == "this"
        and event.get("anchor", {}).get("section") == "bg-crowded"
    )
    take_back = sheet.locator(f'[data-lf-map-button$=":take-back:{reaction["id"]}"]')
    expect(take_back).to_have_attribute("aria-label", "this — take it back")
    with sending(page, "the withdrawal of the spilled reaction"):
        take_back.click()
    expect(sheet).to_be_hidden()
    expect(crowded.locator(f'[data-event="{reaction["id"]}"]')).to_have_count(0)
    last = events_model.read_events(serve.page_dir)[-1]
    assert (last["kind"], last["undoes"]) == ("undo", reaction["id"])
    assert errors == []
    page.close()


def test_the_feature_gallery_displays_the_complete_button_grammar(browser, serve):
    """The atlas keeps every Button axis and lifecycle witness visible together."""
    page, errors = open_page(browser, live_url(serve(FEATURE_GALLERY)))
    resized(page, 1440, 900)

    atlas = page.locator("#bg-button-atlas")
    expect(atlas).to_be_visible()
    buttons = atlas.locator(".lf-margin-button")
    expect(buttons).to_have_count(12)
    records = buttons.evaluate_all(
        """buttons => buttons.map(button => ({
          behavior: button.dataset.lfBehavior,
          tone: button.dataset.lfTone,
          role: button.dataset.lfRole,
          state: button.dataset.lfState,
        }))"""
    )
    assert {record["behavior"] for record in records} == {
        "action",
        "disclosure",
        "status",
    }
    assert {record["tone"] for record in records} == {
        "neutral",
        "positive",
        "negative",
    }
    assert {record["role"] for record in records} == {
        "complete",
        "escape",
        "primary",
        "secondary",
        "reading",
        "overflow",
    }
    assert {record["state"] for record in records} == {
        "idle",
        "engaged",
        "busy",
        "failed",
        "settled",
    }

    def specimen(name):
        return atlas.locator(f'[data-button-specimen="{name}"] > .lf-margin-button')

    engaged = specimen("engaged")
    busy = specimen("busy")
    failed = specimen("failed")
    settled = specimen("settled")
    marks = {
        name: control.evaluate(
            """button => {
              const style = getComputedStyle(button, '::after');
              return {
                width: style.width,
                radius: style.borderRadius,
                transform: style.transform,
                animation: style.animationName,
                playState: style.animationPlayState,
              };
            }"""
        )
        for name, control in {
            "engaged": engaged,
            "busy": busy,
            "failed": failed,
            "settled": settled,
        }.items()
    }
    assert marks["engaged"]["width"] == "6px"
    assert marks["engaged"]["radius"] == "50%"
    assert marks["busy"]["width"] == "8px"
    assert "button-busy" in marks["busy"]["animation"]
    assert marks["busy"]["playState"] == "running"
    assert marks["failed"]["transform"] != "none"
    assert marks["settled"]["radius"] == "1px"
    expect(busy).to_have_attribute("aria-busy", "true")
    expect(
        atlas.locator('[data-button-specimen="sent"] > .lf-margin-button')
    ).to_have_attribute("role", "status")
    expect(atlas.locator(".button-atlas-name")).to_have_text(
        [
            "Save",
            "Cancel",
            "Accept",
            "Reject",
            "Thread",
            "More",
            "Sent",
            "Idle",
            "Engaged",
            "Busy",
            "Failed",
            "Settled",
        ]
    )

    assert errors == []
    page.close()


def test_the_feature_gallery_carries_a_button_through_its_whole_lifecycle(
    browser, serve
):
    """The Button specimen shows the stable endpoints and exercises each transition.

    Busy and Active depend on a request in flight and an external work claim, so the
    source names those conditions while this browser journey holds each one long enough
    to prove that the real Button draws its moving state.
    """
    page, errors = open_page(browser, live_url(serve(FEATURE_GALLERY)))
    resized(page, 1440, 900)

    seeded = page.locator('[data-lf-margin-for="bg-button-accepted"]')
    expect(page.locator("#bg-button-accepted")).to_have_attribute(
        "data-lf-state", "accept"
    )
    expect(seeded.locator(".lf-sug-receipt")).to_have_text("Accepted")

    draft = page.locator('[data-lf-margin-for="bg-draft"]')
    draft.locator(".lf-draft-pencil").click()
    save = draft.get_by_role("button", name="Save", exact=True)
    cancel_draft = draft.get_by_role("button", name="Cancel", exact=True)
    expect(save).to_have_attribute("data-lf-state", "engaged")
    expect(cancel_draft).to_have_attribute("data-lf-state", "engaged")
    cancel_draft.click()
    picked_up = page.locator('[data-lf-margin-for="bg-history"]').get_by_role(
        "status", name=re.compile(r"^Picked up for ")
    )
    expect(picked_up).to_have_attribute("data-lf-state", "settled")

    workflow = page.locator('[data-lf-margin-for="bg-button-workflow"]')
    accept = workflow.get_by_role(
        "button", name=re.compile(r"^Accept the suggested change")
    )
    expect(accept).to_have_attribute("data-lf-state", "idle")

    def reject(route):
        route.fulfill(
            status=400,
            json={"ok": False, "error": "gallery transport refusal", "final": True},
        )

    page.route("**/api/event", reject)
    accept.click()
    retry = workflow.get_by_role("button", name="Retry", exact=True)
    cancel_failure = workflow.get_by_role("button", name="Cancel", exact=True)
    expect(retry).to_have_attribute("data-lf-state", "failed")
    expect(cancel_failure).to_have_attribute("data-lf-state", "failed")
    expect(workflow).to_contain_text("Failed")
    cancel_failure.click()
    page.unroute("**/api/event")
    expect(accept).to_have_attribute("data-lf-state", "idle")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    sends = _traffic(page).sends
    accept.click()
    _until(page, lambda traffic: traffic.sends > sends, "held the acceptance")
    expect(accept).to_have_attribute("data-lf-state", "busy")
    expect(accept).to_have_attribute("aria-busy", "true")
    assert accept.evaluate(
        """button => {
          const style = getComputedStyle(button, '::after');
          return style.animationName.includes('button-busy') &&
            style.animationPlayState === 'running';
        }"""
    ), "the gallery's busy Button has no running lifecycle animation"

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator("#bg-button-workflow")).to_have_attribute(
        "data-lf-state", "accept"
    )
    expect(workflow.locator(".lf-sug-receipt")).to_have_text("Accepted")
    undo_button = workflow.get_by_role("button", name=re.compile(r"^Undo accepting"))
    expect(undo_button).to_have_attribute("data-lf-state", "settled")
    sent = workflow.get_by_role("status", name=re.compile(r"^Sent for "))
    expect(sent).to_be_visible()
    expect(sent).to_have_attribute("data-lf-state", "busy")
    assert sent.evaluate(
        """button => {
          const style = getComputedStyle(button, '::after');
          return style.animationName.includes('button-busy') &&
            style.animationPlayState === 'running';
        }"""
    ), "the gallery's Sent status has no running lifecycle animation"

    claimed = CliRunner().invoke(
        cli_model.cli,
        [
            "status",
            str(serve.page_dir),
            "working",
            "applying the selected route",
            "--on",
            "bg-button-workflow",
        ],
    )
    assert claimed.exit_code == 0, claimed.output
    told(page)
    active = workflow.locator(
        '.lf-margin-button[data-lf-kinds="activity"][data-lf-state="busy"]:visible'
    )
    expect(active).to_be_visible()
    expect(active).to_have_attribute("aria-label", re.compile(r"^Active"))
    assert active.evaluate(
        """button => {
          const style = getComputedStyle(button, '::after');
          return style.animationName.includes('button-busy') &&
            style.animationPlayState === 'running';
        }"""
    ), "the gallery's Active Button has no running lifecycle animation"

    stamp_page(
        serve.page_dir,
        FEATURE_GALLERY.read_text(encoding="utf-8"),
        "Apply the selected route",
        completes=("bg-button-workflow",),
    )
    wait_for_revision(page, 3)
    expect(active).to_have_count(0)
    expect(workflow.locator(".lf-sug-receipt")).to_have_text("Accepted")
    expect(
        workflow.get_by_role("button", name=re.compile(r"^Undo accepting"))
    ).to_have_count(0)

    assert errors and all("400" in error for error in errors)
    page.close()


def test_the_feature_gallery_balances_one_button_sample_with_feature_sections(
    browser, serve
):
    """One compact sample collects the Button grammar; feature sections keep examples."""
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    resized(page, 1440, 900)
    expect(page.locator("#bg-grammar")).to_have_count(0)
    sections = {
        "bg-clusters": (
            "Button atlas: every role, tone, and state",
            "#bg-button-atlas-guide",
            "#bg-button-atlas",
        ),
        "bg-changes": (
            "Suggestions: proposed text changes",
            "#bg-changes-guide",
            "#bg-replace",
        ),
        "bg-editing": (
            "Drafts: editable passages and history",
            "#bg-editing-guide",
            "#bg-draft",
        ),
        "bg-conversations": (
            "Threads: anchored conversations",
            "#bg-conversations-guide",
            "#bg-thread-text",
        ),
        "bg-reactions": (
            "Reactions: short verdicts on a passage",
            "#bg-reactions-guide",
            "#bg-react-ok",
        ),
        "bg-readings": (
            "Decisions: answers in context",
            "#bg-readings-guide",
            "#bg-outcome-ask",
        ),
        "bg-version-changes": (
            "Version changes: comparison evidence",
            "#bg-version-guide",
            "#bg-change",
        ),
    }
    for section_id, (heading, guide_selector, example_selector) in sections.items():
        section = page.locator(f"#{section_id}")
        expect(section.get_by_role("heading", name=heading, exact=True)).to_be_visible()
        expect(section.locator(guide_selector)).to_be_visible()
        expect(section.locator(example_selector)).to_be_visible()

    change_forms = page.locator("#bg-change-forms")
    expect(change_forms.locator(":scope > span")).to_have_count(3)
    expect(change_forms.locator("#bg-replace, #bg-insert, #bg-delete")).to_have_count(3)
    expect(page.locator("#bg-changes lf-suggestion")).to_have_count(4)

    headings = page.locator("main section :is(h2, h3)").all_text_contents()
    assert [
        " ".join(heading.split()) for heading in headings if "Button" in heading
    ] == [
        "Button atlas: every role, tone, and state",
        "Button workflow: act, fail, settle, and hand off",
    ]
    expect(page.locator("#bg-buttons-line #bg-crowded")).to_be_visible()
    expect(page.locator("#bg-button-workflow")).not_to_have_attribute(
        "data-lf-state", re.compile(".+")
    )
    expect(page.locator("#bg-button-accepted")).to_have_attribute(
        "data-lf-state", "accept"
    )
    expect(
        page.locator('[data-lf-margin-for="bg-button-accepted"] .lf-sug-receipt')
    ).to_have_text("Accepted")

    feature_headings = page.locator(
        "main section h2:has(> .bg-feature-detail), "
        "main section h3:has(> .bg-feature-detail)"
    )
    emphasis = feature_headings.evaluate_all(
        """headings => headings.map(heading => {
          const detail = heading.querySelector('.bg-feature-detail');
          const names = [...heading.children].filter(child => child.tagName === 'STRONG');
          const eyebrow = heading.parentElement.querySelector(
            ':scope > .eyebrow.bg-feature-elements'
          );
          return {
            label: heading.textContent.trim(),
            detailCount: heading.querySelectorAll('.bg-feature-detail').length,
            nameWeights: names.map(name => Number.parseInt(
              getComputedStyle(name).fontWeight, 10
            )),
            detailWeight: detail
              ? Number.parseInt(getComputedStyle(detail).fontWeight, 10)
              : null,
            eyebrow: eyebrow?.textContent.trim() || '',
          };
        })"""
    )
    assert emphasis
    unclear = [
        heading
        for heading in emphasis
        if not (
            heading["detailCount"] == 1
            and heading["nameWeights"]
            and all(
                weight > heading["detailWeight"] for weight in heading["nameWeights"]
            )
            and heading["eyebrow"]
        )
    ]
    assert not unclear, unclear

    button_sample = '[data-lf-margin-for="bg-crowded"]'
    examples = {
        "action": page.locator(f"{button_sample} .lf-sug-accept"),
        "disclosure": page.locator(f"{button_sample} .lf-margin-marker"),
        "more": page.locator(f"{button_sample} > .lf-margin-more"),
        "settled": page.locator(f"{button_sample} .lf-react-mark").first,
    }
    expect(examples["action"]).to_have_attribute("data-lf-behavior", "action")
    for disclosure in (examples["disclosure"], examples["more"]):
        expect(disclosure).to_have_attribute("data-lf-behavior", "disclosure")
    expect(examples["action"]).to_have_attribute("data-lf-tone", "positive")
    expect(examples["settled"]).to_have_attribute("data-lf-state", "settled")
    expect(
        page.locator(
            '[data-lf-margin-for="bg-react-lost"] '
            '.lf-react-mark[data-token="lost"] > .lf-margin-button-glyph'
        )
    ).to_have_text("??")
    expect(
        page.locator(
            '[data-lf-margin-for="bg-choice-ask"] '
            '.lf-margin-marker[data-lf-kinds="ask"] '
            'svg[data-lf-icon="question"]'
        )
    ).to_be_visible()
    assert page.locator("#bg-reactions p strong").all_text_contents() == [
        "1 · ok · settled.",
        "2 · no · wrong.",
        "3 · lost · unclear.",
        "4 · cut · too long.",
        "5 · more · needs detail.",
        "6 · this · look here.",
    ]
    assert errors == []
    page.close()


def test_margin_registration_rejects_ambiguous_button_identity(browser, serve):
    """One owner plus one Button key must identify exactly one activation source."""
    page, errors = open_page(browser, serve(PANEL_PAGE))
    message = page.evaluate(
        """async () => {
          const {offer, marginButton, registerMarginItem} =
            await import('/runtime/widget-api.js');
          const controls = document.createElement('span');
          for (const label of ['First', 'Second'])
            controls.append(marginButton(offer('button', ''), {
              key: 'same', icon: 'dot', label
            }));
          try {
            registerMarginItem({
              key: 'ambiguous', target: document.querySelector('#how-cap'), controls
            });
          } catch (error) {
            return error.message;
          }
          return null;
        }"""
    )
    assert message == 'Duplicate Button key "same" in margin item "ambiguous"'
    expect(page.locator('[data-lf-margin-for="how-cap"]')).to_have_count(0)
    assert errors == []
    page.close()


def test_open_page_map_uses_the_canonical_button_record_and_live_state(browser, serve):
    """One retained proxy follows Button semantics and ARIA without owning activation."""
    page, errors = open_page(browser, serve(PANEL_PAGE))
    page.evaluate(
        """async () => {
          const {offer, marginButton, marginButtonState, registerMarginItem} =
            await import('/runtime/widget-api.js');
          const control = marginButton(offer('button', ''), {
            key: 'inspect', icon: 'question', label: 'Inspect source',
            behavior: 'disclosure', tone: 'negative', role: 'reading',
            state: 'engaged'
          });
          control.setAttribute('aria-controls', 'how-cap');
          control.setAttribute('aria-expanded', 'true');
          control.setAttribute('aria-haspopup', 'dialog');
          control.setAttribute('aria-pressed', 'true');
          control.onclick = () => window.lfCanonicalPresses += 1;
          window.lfCanonicalPresses = 0;
          window.lfCanonicalButton = {
            control,
            registration: registerMarginItem({
              key: 'fixture', target: document.querySelector('#how-cap'), controls: control
            }),
            update() {
              marginButtonState(control, 'busy');
              control.setAttribute('aria-expanded', 'false');
              control.setAttribute('aria-haspopup', 'menu');
              control.removeAttribute('aria-pressed');
              this.registration.update({immediate: true});
            }
          };
        }"""
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    sheet = page.get_by_role("dialog", name="Page map", exact=True)
    proxy = sheet.get_by_role("button", name="Inspect source", exact=True)
    expect(proxy).to_be_visible()
    assert proxy.evaluate(
        """button => ({
          behavior: button.dataset.lfBehavior,
          tone: button.dataset.lfTone,
          role: button.dataset.lfRole,
          state: button.dataset.lfState,
          label: button.querySelector('.lf-page-map-action-label').textContent,
          expanded: button.getAttribute('aria-expanded'),
          pressed: button.getAttribute('aria-pressed'),
          popup: button.getAttribute('aria-haspopup'),
          controls: button.getAttribute('aria-controls'),
        })"""
    ) == {
        "behavior": "disclosure",
        "tone": "negative",
        "role": "reading",
        "state": "engaged",
        "label": "Inspect source…",
        "expanded": "true",
        "pressed": "true",
        "popup": "dialog",
        "controls": "how-cap",
    }

    proxy.evaluate("button => button.dataset.stableProof = 'same-proxy'")
    proxy.focus()
    page.evaluate("() => window.lfCanonicalButton.update()")
    expect(proxy).to_be_focused()
    expect(proxy).to_have_attribute("data-stable-proof", "same-proxy")
    expect(proxy).to_have_attribute("data-lf-state", "busy")
    expect(proxy).to_have_attribute("aria-busy", "true")
    expect(proxy).to_have_attribute("aria-expanded", "false")
    expect(proxy).to_have_attribute("aria-haspopup", "menu")
    expect(proxy).not_to_have_attribute("aria-pressed", re.compile(".+"))

    page.evaluate(
        """() => {
          const fixture = window.lfCanonicalButton;
          fixture.control.setAttribute('aria-disabled', 'true');
          fixture.registration.update({immediate: true});
        }"""
    )
    expect(proxy).to_be_disabled()
    page.evaluate(
        """() => {
          const fixture = window.lfCanonicalButton;
          fixture.control.removeAttribute('aria-disabled');
          fixture.registration.update({immediate: true});
        }"""
    )
    expect(proxy).to_be_enabled()
    proxy.click()
    expect(sheet).to_be_hidden()
    assert page.evaluate("() => window.lfCanonicalPresses") == 1
    assert errors == []
    page.close()


def test_g_m_addresses_the_visible_window_and_g_shift_m_opens_the_complete_page_map(
    browser, serve
):
    """Visible locations start at one while the complete Map keeps every location."""
    page, errors = open_page(browser, serve(PAGE_MAP_PAGE, events=PAGE_MAP_EVENTS))
    resized(page, 1440, 300)

    page.keyboard.press("g")
    page.keyboard.press("m")
    route = page.locator(
        '.lf-keyline [data-lf-commands~="navigation.page-map-item"] .lf-key-sequence'
    )
    expect(route.locator(":scope > kbd")).to_have_text(["g", "m", "1"])
    expect(page.locator(".lf-page-map-sheet")).to_be_hidden()
    expect(page.locator(".lf-chord-address")).to_have_text(["gm1"])

    # When the motion settles, number the newly visible window from one. Location 11 is
    # outside the document's old one-digit prefix.
    page.evaluate(
        """() => new Promise(resolve => {
          addEventListener('scrollend', resolve, {once: true});
          const target = document.querySelector('#map-11');
          document.scrollingElement.scrollTo(0, target.offsetTop - 100);
        })"""
    )
    expect(route.locator(":scope > kbd")).to_have_text(["g", "m", "1"])
    expect(page.locator(".lf-chord-address")).to_have_text(["gm1"])
    page.keyboard.press("1")
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    expect(preview).to_contain_text("Map note 11")
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    page.keyboard.press("Escape")

    page.evaluate(
        """() => new Promise(resolve => {
          addEventListener('scrollend', resolve, {once: true});
          document.scrollingElement.scrollTo(0, 0);
        })"""
    )
    before_sheet = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    sheet = page.get_by_role("dialog", name="Page map", exact=True)
    expect(sheet).to_be_visible()
    expect(sheet.locator(".lf-page-map-group")).to_have_count(12)
    expect(sheet).to_contain_text("Map note 12")
    search = sheet.get_by_role(
        "searchbox", name="Find a Button or location in Page map"
    )
    expect(search).to_be_focused()
    search.fill("Map note 12")
    expect(sheet.locator(".lf-page-map-group:visible")).to_have_count(1)
    expect(sheet.locator(".lf-page-map-group:visible")).to_contain_text("Map note 12")
    search.fill("")
    expect(sheet.locator(".lf-page-map-group:visible")).to_have_count(12)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before_sheet
    assert errors == []
    page.close()


def test_g_m_numbers_a_late_visible_action_only_location_from_one(browser, serve):
    """A late action-only location is reachable while it is visible."""
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    resized(page, 1440, 900)
    margins_laid_out(page)
    page.evaluate(
        """() => new Promise(resolve => {
          addEventListener('scrollend', resolve, {once: true});
          const heading = document.querySelector('#bg-quoted-and-visual-heading');
          document.scrollingElement.scrollTo(0, heading.offsetTop - 100);
        })"""
    )
    page.locator("body").focus()
    show_after = page.get_by_role(
        "button", name="Show after — a sample run list with and without a status column"
    )
    expect(show_after).to_be_visible()

    page.keyboard.press("g")
    page.keyboard.press("m")
    route = page.locator(
        '.lf-keyline [data-lf-commands~="navigation.page-map-item"] .lf-key-sequence'
    )
    expect(route.locator(":scope > kbd")).to_have_text(["g", "m", "1"])
    expect(page.locator(".lf-chord-address")).to_have_text(["gm1"])
    page.keyboard.press("1")
    expect(
        page.get_by_role(
            "button",
            name="Show before — a sample run list with and without a status column",
        )
    ).to_be_focused()
    assert errors == []
    page.close()


def test_margin_target_hover_requires_pointer_movement(browser, serve):
    """Page motion under a parked pointer cannot take ownership from the keyboard."""
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    resized(page, 1280, 720)
    margins_laid_out(page)
    host = page.locator('[data-lf-margin-for="bg-choice-ask"]')
    initial = host.bounding_box()
    pointer = {"x": int(initial["x"] + initial["width"] / 2), "y": 70}
    assert not initial["y"] < pointer["y"] < initial["y"] + initial["height"], (
        "the pointer starts inside the Ask margin host"
    )
    page.mouse.move(pointer["x"], pointer["y"])

    page.keyboard.press("g")
    page.keyboard.press("m")
    page.keyboard.press("1")
    page.keyboard.press("Escape")

    page.wait_for_function(
        """({x, y}) => {
          const host = document.querySelector(
            '[data-lf-margin-for="bg-choice-ask"]'
          );
          const box = host?.getBoundingClientRect();
          return document.activeElement === document.body && box &&
            box.left < x && x < box.right && box.top < y && y < box.bottom;
        }""",
        arg=pointer,
    )
    target = page.locator("#bg-choice-ask")
    assert "lf-margin-target" not in (target.get_attribute("class") or "").split(), (
        "moving the margin under a stationary pointer claimed pointer ownership"
    )

    page.mouse.move(pointer["x"] + 1, pointer["y"])
    expect(target).to_have_class(re.compile(r"\blf-margin-target\b"))
    assert errors == []
    page.close()


def test_margin_target_pointer_ownership_ends_with_its_host(browser, serve):
    """Replacing a hovered margin host cannot transfer its pointer ownership."""
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    resized(page, 1280, 720)
    margins_laid_out(page)
    target = page.locator("#bg-draft")
    target.scroll_into_view_if_needed()
    host = page.locator('[data-lf-margin-for="bg-draft"]')
    box = host.bounding_box()
    pointer = {
        "x": int(box["x"] + box["width"] / 2),
        "y": int(box["y"] + box["height"] / 2),
    }
    page.mouse.move(pointer["x"], pointer["y"])
    expect(target).to_have_class(re.compile(r"\blf-margin-target\b"))

    draft = target.element_handle()
    old_host = host.element_handle()
    assert draft is not None and old_host is not None
    draft.evaluate("node => node.remove()")
    assert not old_host.evaluate("node => node.isConnected")
    page.evaluate(
        "node => document.querySelector('#bg-editing-guide').before(node)",
        draft,
    )
    page.wait_for_function(
        """({x, y}) => {
          const host = document.querySelector('[data-lf-margin-for="bg-draft"]');
          const box = host?.getBoundingClientRect();
          return host?.isConnected && host.checkVisibility() && box &&
            box.bottom > 0 && box.top < innerHeight &&
            !(box.left < x && x < box.right && box.top < y && y < box.bottom);
        }""",
        arg=pointer,
    )
    assert page.evaluate(
        "old => document.querySelector('[data-lf-margin-for=\"bg-draft\"]') !== old",
        old_host,
    )
    assert "lf-margin-target" not in (target.get_attribute("class") or "").split(), (
        "the replacement host inherited pointer ownership from its disconnected peer"
    )

    replacement = page.locator('[data-lf-margin-for="bg-draft"]')
    replacement_box = replacement.bounding_box()
    page.mouse.move(
        int(replacement_box["x"] + replacement_box["width"] / 2),
        int(replacement_box["y"] + replacement_box["height"] / 2),
    )
    expect(target).to_have_class(re.compile(r"\blf-margin-target\b"))
    assert errors == []
    page.close()


def test_g_m_presses_the_first_button_at_each_location(browser, serve):
    """A location address has the same native press as its first available Button."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "Page-map Button behavior",
                """
<p>Replace
  <lf-suggestion id="address-action">
    <lf-old>the first phrase</lf-old><lf-new>the second phrase</lf-new>
  </lf-suggestion>.</p>
<lf-draft id="address-disclosure"><pre>Keep this text editable.</pre></lf-draft>
""",
            )
        ),
    )
    resized(page, 1440, 900)
    action = page.get_by_role(
        "button", name="Accept the suggested change: the second phrase", exact=True
    )
    disclosure = page.get_by_role("button", name="Edit address-disclosure", exact=True)
    with sending(page, "the addressed suggestion's acceptance"):
        page.keyboard.press("g")
        page.keyboard.press("m")
        page.keyboard.press("1")
    expect(page.locator("#address-action lf-old")).to_be_hidden()
    expect(page.locator("#address-action lf-new")).to_be_visible()

    with sending(page, "the withdrawal of the addressed action"):
        page.keyboard.press("z")
    expect(action).to_be_visible()
    expect(page.locator("#address-action lf-old")).to_be_visible()

    disclosure.evaluate(
        """button => {
          button.setAttribute('aria-disabled', 'true');
          button.dataset.lfState = 'busy';
          button.tabIndex = -1;
        }"""
    )
    page.keyboard.press("g")
    page.keyboard.press("m")
    page.keyboard.press("2")
    expect(page.locator("#address-disclosure textarea")).to_have_count(0)

    disclosure.evaluate(
        """button => {
          button.setAttribute('aria-disabled', 'false');
          button.dataset.lfState = 'idle';
          button.tabIndex = 0;
        }"""
    )
    page.keyboard.press("g")
    page.keyboard.press("m")
    page.keyboard.press("2")
    expect(page.locator("#address-disclosure textarea")).to_be_focused()
    expect(disclosure).to_be_hidden()

    assert errors == []
    page.close()


def test_g_shift_m_exposes_dense_suggestion_verdicts_as_real_buttons(browser, serve):
    """Late action-only targets keep their verbs in the complete Page map."""
    page, errors = open_page(browser, serve(DENSE_SUGGESTIONS_PAGE))
    resized(page, 1440, 900)
    page.evaluate(
        """() => {
          const prefix = document.createElement('span');
          prefix.textContent = 'A deliberately long introduction places the remembered words later: ';
          document.querySelector('#bg-neighbors').prepend(prefix);
        }"""
    )

    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    sheet = page.get_by_role("dialog", name="Page map", exact=True)
    expect(sheet).to_be_visible()
    for title, word in (
        ("rewrite · two → three", "three"),
        ("rewrite · red → blue", "blue"),
        ("rewrite · large → small", "small"),
    ):
        group = sheet.locator(".lf-page-map-group").filter(has_text=title)
        expect(
            group.get_by_role("button", name=f"Accept the suggested change: {word}")
        ).to_be_visible()
        expect(
            group.get_by_role("button", name=f"Reject the suggested change: {word}")
        ).to_be_visible()

    search = sheet.get_by_role(
        "searchbox", name="Find a Button or location in Page map"
    )
    search.fill("Pack")
    expect(sheet.locator(".lf-page-map-group:visible")).to_have_count(3)
    expect(sheet.locator(".lf-page-map-group:visible")).to_contain_text(
        ["two → three", "red → blue", "large → small"]
    )
    sheet.locator(".lf-page-map-group:visible").first.get_by_role(
        "button", name="Accept the suggested change: three"
    ).focus()
    page.evaluate(
        """() => {
          const passage = document.querySelector('#bg-neighbors');
          const word = [...passage.childNodes].find(
            node => node.nodeType === Node.TEXT_NODE && node.textContent.includes('Pack')
          );
          word.textContent = word.textContent.replace('Pack', 'Carry');
          document.dispatchEvent(new CustomEvent('lf-actions'));
        }"""
    )
    expect(search).to_be_focused()
    expect(sheet.locator(".lf-page-map-group:visible")).to_have_count(0)
    expect(sheet.get_by_text("No matching Buttons or locations")).to_be_visible()
    page.evaluate(
        """() => {
          const passage = document.querySelector('#bg-neighbors');
          const word = [...passage.childNodes].find(
            node => node.nodeType === Node.TEXT_NODE && node.textContent.includes('Carry')
          );
          word.textContent = word.textContent.replace('Carry', 'Pack');
          document.dispatchEvent(new CustomEvent('lf-actions'));
        }"""
    )
    expect(sheet.locator(".lf-page-map-group:visible")).to_have_count(3)
    search.fill("red → blue")
    expect(sheet.locator(".lf-page-map-group:visible")).to_have_count(1)
    red = sheet.locator(".lf-page-map-group").filter(has_text="rewrite · red → blue")
    reject = red.get_by_role(
        "button", name="Reject the suggested change: blue", exact=True
    )
    reject.evaluate("button => button.dataset.testIdentity = 'held'")
    page.evaluate("() => document.dispatchEvent(new CustomEvent('lf-actions'))")
    expect(reject).to_have_attribute("data-test-identity", "held")
    reject.focus()
    page.keyboard.press("Enter")
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["widget"], sent["action"]) == (
        "action",
        "bg-neighbor-b",
        "reject",
    )
    assert errors == []
    page.close()


def test_tab_into_a_button_cluster_replaces_ellipsis_with_all_buttons(browser, serve):
    """Keyboard arrival expands one target's peers instead of focusing its overflow."""
    page, errors = open_page(browser, serve(BUTTON_KEYBOARD_PAGE))
    resized(page, 1440, 900)
    page.evaluate(
        """async () => {
          const {offer, marginButton, registerMarginItem} =
            await import('/runtime/widget-api.js');
          registerMarginItem({key: 'extra', target: document.querySelector('#sug-refill'),
            controls: marginButton(offer('button', ''), {
              key: 'details', icon: 'comment', label: 'Details',
              behavior: 'disclosure', role: 'reading'
            })});
        }"""
    )
    page.locator("#before-buttons").focus()

    page.keyboard.press("Tab")

    item = page.locator('[data-lf-margin-for="sug-refill"]')
    accept = item.get_by_role("button", name=re.compile(r"Accept"))
    expect(accept).to_be_focused()
    expect(item.locator(":scope > .lf-margin-more")).to_be_hidden()
    expect(item.locator(":scope > .lf-margin-options")).to_be_visible()
    reject = item.get_by_role("button", name=re.compile(r"Reject"))
    expect(reject).to_be_visible()
    page.keyboard.press("Tab")
    expect(reject).to_be_focused()
    expect(item.locator(":scope > .lf-margin-more")).to_be_hidden()

    page.keyboard.press("Escape")
    expect(item.locator(":scope > .lf-margin-more")).to_be_focused()
    page.locator("#after-buttons").focus()
    page.keyboard.press("Shift+Tab")
    expect(
        item.locator(":scope > .lf-margin-options .lf-margin-button:visible").last
    ).to_be_focused()
    more = item.locator(":scope > .lf-margin-more")
    options = item.locator(":scope > .lf-margin-options")
    expect(more).to_be_hidden()

    page.keyboard.press("Tab")
    expect(page.locator("#after-buttons")).to_be_focused()
    expect(more).to_be_visible()
    expect(options).to_be_hidden()

    more.click()
    expect(options).to_be_visible()
    page.locator("#insert").click()
    expect(more).to_be_visible()
    expect(options).to_be_hidden()
    assert errors == []
    page.close()


def test_left_and_right_walk_the_revealed_button_cluster(browser, serve):
    """Horizontal arrows move between the peer Buttons revealed on keyboard entry."""
    page, errors = open_page(browser, serve(BUTTON_KEYBOARD_PAGE))
    resized(page, 1440, 900)
    page.locator("#before-buttons").focus()
    page.keyboard.press("Tab")

    item = page.locator('[data-lf-margin-for="sug-refill"]')
    accept = item.get_by_role("button", name=re.compile(r"Accept"))
    reject = item.get_by_role("button", name=re.compile(r"Reject"))
    expect(accept).to_be_focused()
    page.keyboard.press("ArrowRight")
    expect(reject).to_be_focused()
    page.keyboard.press("ArrowLeft")
    expect(accept).to_be_focused()

    assert errors == []
    page.close()


def test_settling_a_secondary_action_exposes_its_lifecycle(browser, serve):
    """A settled outcome and its unsettled handoff stay one engaged cluster."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    resized(page, 1440, 900)
    item = page.locator('[data-lf-margin-for="sug-refill"]')
    options = item.locator(":scope > .lf-margin-options")

    options.get_by_role("button", name=re.compile(r"Reject")).click()
    round_trip(page)

    expect(item.locator(".lf-sug-receipt")).to_have_text("Rejected")
    expect(item.locator(":scope > .lf-margin-more")).to_be_hidden()
    expect(options).to_be_visible()
    expect(
        options.get_by_role("status", name=re.compile(r"^Sent for "))
    ).to_be_visible()
    expect(item.locator(".lf-margin-button:visible")).to_have_count(2)
    expect(
        item.get_by_role("button", name=re.compile(r"^Undo rejecting"))
    ).to_be_focused()
    assert errors == []
    page.close()


CLUSTER_SHAPE = """() => [...document.querySelectorAll('.lf-margin-item')].map(
  (host) => [
    host.dataset.lfMarginFor,
    host.querySelectorAll('.lf-margin-button').length,
    Boolean(host.querySelector('.lf-margin-options')?.hidden),
  ])"""


def test_a_print_preview_leaves_the_clusters_as_it_found_them(browser, serve):
    """Paper takes every injected control out of the page, so the one
    contributor-visibility reading a margin render is built on comes back empty there
    and folds every cluster to nothing. That is a reading of the medium rather than of
    the page: news arriving while the reader stands in the print preview leaves the
    Buttons where they were, and reaches them when the screen comes back.

    The shape is read as markup rather than as visibility, because on paper nothing in
    the margin is visible either way; what the fold does is empty the option group and
    take the Buttons out of the host."""
    page, errors = open_page(
        browser, serve(ACTION_PAGE, events=[COMMENT_ON_SUGGESTION])
    )
    resized(page, 1440, 900)
    margins_laid_out(page)
    standing = page.evaluate(CLUSTER_SHAPE)
    assert [host for host in standing if host[1] > 1], (
        f"no cluster here holds the Buttons a paper reading would fold away: {standing}"
    )

    page.emulate_media(media="print")
    events_model.append_event(serve.page_dir, COMMENT_ON_SECOND_SUGGESTION)
    told(page)
    assert page.evaluate(CLUSTER_SHAPE) == standing

    page.emulate_media(media="screen")
    thistle = page.locator('[data-lf-margin-for="sug-thistle"]')
    expect(thistle.locator(".lf-margin-marker")).to_have_attribute(
        "aria-label", re.compile(r"^Thread, ")
    )
    assert errors == []
    page.close()


def test_the_page_map_walk_stops_at_both_visible_edges(browser, serve):
    """The page map is a vertical list: its arrows stop at its first and last markers,
    while Home and End remain direct routes to those edges."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK])
    )
    markers = page.locator(".lf-margin-marker:visible")
    assert markers.count() > 1, "the page map has no pair of visible markers to walk"

    markers.first.focus()
    page.keyboard.press("Home")
    first = page.locator(":focus").get_attribute("aria-label")
    assert first and page.locator(":focus").evaluate(
        "node => node.matches('.lf-margin-marker')"
    )
    page.keyboard.press("ArrowUp")
    assert page.locator(":focus").get_attribute("aria-label") == first

    page.keyboard.press("End")
    last = page.locator(":focus").get_attribute("aria-label")
    assert last and last != first
    page.keyboard.press("ArrowDown")
    assert page.locator(":focus").get_attribute("aria-label") == last

    page.keyboard.press("Home")
    assert page.locator(":focus").get_attribute("aria-label") == first
    assert errors == []
    page.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_button_tone_colors_only_the_icon(browser, serve, scheme):
    """State keeps its distinct shape; tone never recolors the shell or state mark."""
    page, errors = open_page(
        browser, serve(leaf_page("Button tones", '<p id="target">A shared target</p>'))
    )
    page.emulate_media(color_scheme=scheme, reduced_motion="reduce")
    resized(page, 1440, 900)
    page.evaluate(
        """async () => {
          const {offer, marginButton, marginButtonState} =
            await import('/runtime/widget-api.js');
          const controls = document.createElement('div');
          controls.className = 'lf-ui';
          for (const tone of ['neutral', 'positive', 'negative']) {
            controls.append(marginButton(offer('button', ''), {
              key: tone, icon: 'check', label: tone, tone
            }));
          }
          const buttons = Array.from(controls.children);
          document.querySelector('main').append(controls);
          window.setToneState = state => {
            for (const button of buttons) {
              marginButtonState(button, state);
              button.setAttribute('aria-disabled', String(state === 'busy'));
            }
          };
        }"""
    )
    buttons = [
        page.get_by_role("button", name=tone, exact=True)
        for tone in ("neutral", "positive", "negative")
    ]
    read = """button => {
      const face = getComputedStyle(button);
      const mark = getComputedStyle(button, '::after');
      return {
        shell: [face.color, face.borderTopColor, face.backgroundColor,
                face.outlineColor, face.outlineStyle, face.outlineWidth],
        mark: mark.content === 'none' ? null :
          [mark.color, mark.borderTopColor, mark.backgroundColor],
        shape: mark.content === 'none' ? null :
          [mark.width, mark.height, mark.borderRadius,
           mark.transform !== 'none', mark.borderRightWidth],
        icon: getComputedStyle(button.querySelector('svg')).color
      };
    }"""

    def assert_icon_only(readings):
        assert readings[0]["shell"] == readings[1]["shell"] == readings[2]["shell"]
        assert readings[0]["mark"] == readings[1]["mark"] == readings[2]["mark"]
        assert len({reading["icon"] for reading in readings}) == 3

    shapes = {
        "idle": None,
        "engaged": ["6px", "6px", "50%", False, "1px"],
        "busy": ["8px", "8px", "50%", False, "2px"],
        "failed": ["6px", "6px", "1px", True, "1px"],
        "settled": ["6px", "6px", "1px", False, "1px"],
    }
    for state, shape in shapes.items():
        page.evaluate("state => window.setToneState(state)", state)
        for button in buttons:
            expect(button).to_have_attribute("data-lf-state", state)
        readings = [button.evaluate(read) for button in buttons]
        assert all(
            (reading["mark"] is None) == (state == "idle") for reading in readings
        )
        assert [reading["shape"] for reading in readings] == [shape] * len(buttons)
        assert_icon_only(readings)

    page.evaluate("() => window.setToneState('idle')")
    hovered = []
    focused = []
    for button in buttons:
        button.hover()
        hovered.append(button.evaluate(read))
        page.mouse.move(0, 0)
        button.focus()
        page.keyboard.press("Tab")
        page.keyboard.press("Shift+Tab")
        expect(button).to_be_focused()
        assert button.evaluate("node => node.matches(':focus-visible')")
        focused.append(button.evaluate(read))
    assert_icon_only(hovered)
    assert_icon_only(focused)
    assert errors == []
    page.close()


def test_one_target_has_one_primary_button_and_inline_secondary_buttons(browser, serve):
    """A primary action acts; the ellipsis unfolds the remaining Buttons in place."""
    page, errors = open_page(
        browser, serve(ACTION_PAGE, events=[COMMENT_ON_SUGGESTION])
    )
    resized(page, 1440, 900)

    suggestion = page.locator("[data-lf-for='sug-refill'].lf-sug-actions")
    suggestion_item = suggestion.locator("xpath=..")
    expect(suggestion_item).to_have_class(re.compile(r"lf-margin-item"))
    expect(suggestion_item.locator(":scope > .lf-margin-marker")).to_have_count(1)
    expect(suggestion_item.locator(".lf-sug-accept")).to_be_visible()
    expect(suggestion_item.locator(".lf-sug-reject")).to_be_hidden()
    expect(suggestion_item.locator(":scope > .lf-margin-marker")).to_be_hidden()
    more = suggestion_item.locator(":scope > .lf-margin-more")
    expect(more).to_be_visible()
    for button in (suggestion_item.locator(".lf-sug-accept"), more):
        expect(button).to_have_class(re.compile(r"lf-margin-button"))
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-button-label")
    ).to_be_hidden()
    expect(suggestion_item.locator(".lf-sug-accept")).to_have_attribute(
        "data-lf-behavior", "action"
    )
    expect(suggestion_item.locator(".lf-sug-accept")).not_to_have_attribute(
        "aria-expanded", re.compile(".+")
    )
    expect(more).to_have_attribute("data-lf-behavior", "disclosure")
    expect(more).to_have_attribute("aria-expanded", "false")

    more.click()
    preview = page.locator(".lf-margin-preview")
    options = suggestion_item.locator(":scope > .lf-margin-options")
    expect(options).to_be_visible()
    expect(preview).to_be_hidden()
    expect(more).to_have_attribute("aria-expanded", "true")
    expect(more).to_be_hidden()
    reject = options.get_by_role("button", name=re.compile(r"Reject"))
    expect(reject).to_be_focused()
    expect(page.locator(".lf-keyline")).to_contain_text("close options")
    page.keyboard.press("?")
    page.keyboard.press("?")
    reference = page.locator(".lf-help")
    expect(reference).to_be_visible()
    back = reference.locator('.lf-help-command[data-lf-command="margin.back"]')
    expect(back).to_have_text("Fold the secondary page actions")
    back.click()
    expect(reference).to_be_hidden()
    expect(options).to_be_hidden()
    expect(more).to_be_focused()
    more.click()
    expect(reject).to_be_visible()
    expect(options.get_by_role("button", name=re.compile(r"Ask for"))).to_have_count(0)
    expect(reject).to_be_focused()
    page.keyboard.press("Escape")
    expect(options).to_be_hidden()
    expect(more).to_be_focused()

    draft_controls = page.locator("[data-lf-for='draft-ops'].lf-draft-controls")
    draft_item = draft_controls.locator("xpath=..")
    expect(draft_item).to_have_class(re.compile(r"lf-margin-item"))
    expect(draft_item.locator(":scope > .lf-margin-marker")).to_have_count(1)
    expect(draft_item.locator(":scope > .lf-margin-marker")).to_be_hidden()
    expect(draft_item.locator(".lf-draft-pencil")).to_be_visible()
    expect(draft_item.locator(":scope > .lf-margin-more")).to_be_hidden()
    expect(draft_item.locator(".lf-draft-pencil")).to_have_class(
        re.compile(r"lf-margin-button")
    )
    expect(draft_item.locator(".lf-draft-pencil")).to_have_attribute(
        "data-lf-behavior", "disclosure"
    )
    expect(draft_item.locator(".lf-draft-pencil")).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(draft_item.locator(".lf-draft-pencil .lf-margin-button-label")).to_have_text(
        "Edit…"
    )
    edit = draft_item.locator(".lf-draft-pencil")
    accept = suggestion.locator(".lf-sug-accept")
    expect(edit.locator(":scope > .lf-margin-button-icon")).to_be_visible()
    expect(edit.locator(":scope > *:visible")).to_have_count(1)
    expect(page.locator(".lf-margin-button[title]")).to_have_count(0)
    page.mouse.move(0, 0)
    page.evaluate("() => document.activeElement.blur()")
    expect(accept).to_have_attribute("data-lf-tone", "positive")
    expect(edit).to_have_attribute("data-lf-tone", "neutral")
    offer_backgrounds = [
        control.evaluate("el => getComputedStyle(el).backgroundColor")
        for control in (accept, edit, more)
    ]
    assert len(set(offer_backgrounds)) == 1, (
        "interactive offers should share one unfilled resting surface"
    )
    borders = [
        control.evaluate(
            "el => { const s = getComputedStyle(el); "
            "return [s.borderTopWidth, s.borderRightWidth, "
            "s.borderBottomWidth, s.borderLeftWidth]; }"
        )
        for control in (accept, edit, more)
    ]
    assert borders == [
        ["2px"] * 4,
        ["1px"] * 4,
        ["1px"] * 4,
    ], "the whole ring no longer distinguishes immediate actions from context"
    border_colors = [
        control.evaluate("el => getComputedStyle(el).borderTopColor")
        for control in (accept, edit, more)
    ]
    assert border_colors[1] == border_colors[2] != border_colors[0], (
        "disclosures should share their firmer line while Action uses elevation"
    )
    shadows = [
        control.evaluate("el => getComputedStyle(el).boxShadow")
        for control in (accept, edit, more)
    ]
    assert shadows[0] != "none" and shadows[1:] == ["none", "none"], (
        "only an immediate Action should rise off the shared paper surface"
    )

    before_hover = edit.bounding_box()
    edit.hover()
    expect(edit.locator(".lf-margin-button-label")).to_be_visible()
    assert edit.bounding_box() == before_hover, "the transient label moved its Button"
    page.mouse.move(0, 0)
    expect(edit.locator(".lf-margin-button-label")).to_be_hidden()

    shapes = page.locator(
        ".lf-sug-accept:visible, .lf-draft-pencil:visible, .lf-margin-more:visible, "
        ".lf-margin-marker:visible"
    ).evaluate_all(
        "els => els.map(el => { const box = el.getBoundingClientRect(); "
        "const style = getComputedStyle(el); "
        "return [Math.round(box.width), Math.round(box.height), style.borderRadius]; })"
    )
    assert len({tuple(shape) for shape in shapes}) == 1, (
        "actions, disclosures, and overflow no longer share one Button shape"
    )

    rail_left = accept.evaluate(
        "el => el.closest('.lf-margin-item').getBoundingClientRect().left"
    )
    assert abs(edit.bounding_box()["x"] - rail_left) <= 1, (
        "the draft's resting Edit Button no longer shares the action rail's left edge"
    )
    edit.click()
    save = draft_item.get_by_role("button", name="Save", exact=True)
    expect(save).to_be_visible()
    expect(draft_item.locator(":scope > .lf-margin-more")).to_be_hidden()
    expect(draft_item.locator(":scope > .lf-margin-options")).to_be_visible()
    cancel = draft_item.locator(":scope > .lf-margin-options").get_by_role(
        "button", name="Cancel", exact=True
    )
    expect(cancel).to_be_visible()
    expect(cancel.locator("xpath=..")).to_have_attribute(
        "aria-label", re.compile(r"^Actions for ")
    )
    assert abs(save.bounding_box()["x"] - rail_left) <= 1, (
        "the draft's Save Button no longer shares the action rail's left edge"
    )
    page.mouse.move(0, 0)
    assert save.evaluate(
        "el => { const s = getComputedStyle(el); "
        "return [s.backgroundColor, s.borderColor, s.borderTopWidth]; }"
    ) == accept.evaluate(
        "el => { const s = getComputedStyle(el); "
        "return [s.backgroundColor, s.borderColor, s.borderTopWidth]; }"
    ), "Save and Accept no longer share the canonical immediate-action ring"
    cancel.click()
    expect(edit).to_be_visible()

    accept.focus()
    # Reconciliation that does not change the target order leaves the complete item in
    # place, so a focused contribution remains focused.
    page.evaluate("() => document.dispatchEvent(new CustomEvent('lf-actions'))")
    expect(accept).to_be_focused()
    rail = page.locator("html").evaluate("el => el.style.getPropertyValue('--rail')")
    column = page.locator("main").evaluate(
        "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
    )
    page.keyboard.press("r")
    reactions = options.locator(".lf-margin-reactions")
    expect(options).to_be_visible()
    expect(preview).to_be_hidden()
    expect(suggestion_item.locator(".lf-margin-button:visible")).to_have_count(6)
    expect(reactions.locator(".lf-react").first).to_have_class(
        re.compile(r"lf-margin-button")
    )
    ok = reactions.locator('.lf-react[data-token="ok"]')
    expect(ok).to_have_attribute("aria-label", "ok — settled — no change asked")
    expect(ok).not_to_have_attribute("title", re.compile(".+"))
    ok.hover()
    expect(ok.locator(".lf-margin-button-label")).to_have_text(
        "ok — settled — no change asked"
    )
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    assert (
        page.locator("html").evaluate("el => el.style.getPropertyValue('--rail')")
        == rail
    ), "temporary reaction choices permanently widened the page rail"
    assert (
        page.locator("main").evaluate(
            "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
        )
        == column
    ), "opening reaction choices moved the readable column"
    assert reactions.evaluate(
        "surface => surface.closest('.lf-margin-options') !== null"
    ), "r did not expand the target's canonical Button options"

    # Labels remain transient even with abundant room; options never widen the rail.
    resized(page, 2400, 900)
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-button-label")
    ).to_be_visible()
    page.evaluate("() => document.activeElement.blur()")
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-button-label")
    ).to_be_hidden()
    accept.hover()
    expect(
        suggestion_item.locator(".lf-sug-accept .lf-margin-button-label")
    ).to_be_visible()
    page.mouse.move(0, 0)
    accept.focus()
    page.keyboard.press("r")
    expect(suggestion_item.locator(".lf-margin-button:visible")).to_have_count(6)

    page.keyboard.press("Escape")
    more.click()
    thread_button = options.locator(
        '.lf-margin-reading-option[data-lf-kinds="comment"]'
    )
    expect(thread_button).to_be_visible()
    thread_button.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(options).to_be_visible()
    expect(page.locator(".lf-keyline")).to_contain_text("close thread")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(options).to_be_visible()
    expect(thread_button).to_be_focused()
    expect(page.locator(".lf-keyline")).to_contain_text("close options")
    page.keyboard.press("Escape")
    expect(options).to_be_hidden()
    expect(more).to_be_focused()

    # The shared behavior belongs to the target item, not specifically to a
    # suggestion: focusing the draft's resting Edit action extends that same item.
    draft_controls.locator(".lf-draft-pencil").focus()
    page.keyboard.press("r")
    expect(draft_item.locator(".lf-margin-button:visible")).to_have_count(6)
    expect(draft_item.locator(":scope > .lf-margin-more")).to_be_hidden()

    # On a narrow screen each item docks directly after the rendered block that owns its
    # target. It does not join every other action at the end of their common section, and
    # the desktop map marker leaves the compact action row to the Map sheet.
    page.keyboard.press("Escape")
    page.evaluate("() => document.activeElement.blur()")
    resized(page, 390, 900)
    suggestion.locator(".lf-sug-accept").focus()
    expect(page.locator("#sug-refill")).to_be_in_viewport()
    assert suggestion_item.evaluate(
        "item => item.previousElementSibling === document.querySelector('#replace')"
    ), "the first proposal's controls were hoisted past later targets in its section"
    assert draft_item.evaluate(
        "item => item.previousElementSibling === document.querySelector('#draft-ops')"
    ), "the draft's Edit action no longer follows the draft"
    expect(suggestion_item.locator(":scope > .lf-margin-marker")).to_be_hidden()
    page.keyboard.press("r")
    expect(suggestion_item.locator(".lf-margin-button:visible")).to_have_count(6)
    expect(suggestion_item).to_have_class(re.compile(r"lf-docked"))
    reactions.locator('.lf-react[data-token="ok"]').click()
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["token"] == "ok" and sent["anchor"] == {"section": "sug-refill"}

    assert errors == []
    page.close()


def test_a_buttons_walk_position_stays_out_of_its_visible_word(browser, serve):
    """Which location of how many, and how far down, is how a reader listening places a
    Button in the walk. Painted, the same words read as progress toward something, which
    is not what they say, so they belong to the accessible name alone."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK])
    )
    resized(page, 1440, 900)
    buttons = page.evaluate(
        """() => [...document.querySelectorAll('.lf-margin-button')].map(control => ({
          name: control.getAttribute('aria-label'),
          word: control.querySelector(':scope > .lf-margin-button-label').textContent,
        }))"""
    )
    placed = [button for button in buttons if re.search(r"\d+ of \d+", button["name"])]
    assert placed, "no Button announced where it stands in the walk"
    for button in placed:
        assert "percent down" in button["name"], button
    for button in buttons:
        assert not re.search(r"\d+ of \d+|percent down", button["word"]), button

    assert errors == []
    page.close()


def test_an_acknowledgment_uses_status_until_an_active_claim_restores_a_disclosure(
    browser, serve
):
    """A fitting keeps the Button family visible without promising a press.

    Sent, Waiting for pickup, and Picked up report a move already made. Their status
    fitting therefore keeps the circular silhouette and full ink, while leaving the
    accessibility tree as a status rather than a control and showing no hover fill.
    Hovering the status draws a soft neutral trace to the
    target without making the fitting respond like a control. The walk still arrives,
    because the phase is what a reader listening came for. A real claim — work the
    reader can watch — restores the same fitting's activation semantics, in the same
    seat, so the cluster's identity survives the change of promise. Once the handoff and
    claim are complete, the fitting leaves instead of restating widget state.
    """
    page, errors = open_page(browser, live_url(serve(ASK_PAGE)))
    page_dir = serve.page_dir
    resized(page, 1440, 900)
    marker = page.locator('[data-lf-margin-for="jobs"] > .lf-margin-marker')

    page.locator("#job-mounts").click()
    round_trip(page)
    logged_action = next(
        event
        for event in reversed(events_model.read_events(page_dir))
        if event.get("widget") == "jobs" and event.get("action") == "choose"
    )
    marker.evaluate("node => { node.dataset.identityProbe = 'kept' }")

    def face(control=marker):
        return control.evaluate(
            """node => {
              const style = getComputedStyle(node);
              const word = node.querySelector(':scope > .lf-margin-button-label');
              const wordStyle = getComputedStyle(word);
              return {
                tag: node.tagName,
                offer: node.dataset.lfOffer,
                behavior: node.dataset.lfBehavior,
                role: node.getAttribute('role'),
                icon: node.querySelector(':scope > .lf-margin-button-icon')
                  .dataset.lfIcon,
                word: word.querySelector(':scope > .lf-margin-button-label-word').textContent,
                context: word.querySelector(':scope > .lf-margin-button-context')?.textContent ?? null,
                tabIndex: node.tabIndex,
                cursor: style.cursor,
                background: style.backgroundColor,
                border: style.borderTopColor,
                ink: style.color,
                opacity: style.opacity,
                width: style.width,
                wordOpacity: wordStyle.opacity,
                wordPosition: wordStyle.position,
                wordBackground: wordStyle.backgroundColor,
                wordInk: wordStyle.color,
              };
            }"""
        )

    def resolved_color(name):
        return page.evaluate(
            """name => {
              const probe = document.createElement('span');
              probe.style.color = `var(${name})`;
              document.body.append(probe);
              const read = getComputedStyle(probe).color;
              probe.remove();
              return read;
            }""",
            name,
        )

    expected_ink = resolved_color("--ink-2")
    expected_paper = resolved_color("--paper")
    expected_rule = resolved_color("--rule")
    expected_label_ink = resolved_color("--paper")
    expected_label_background = resolved_color("--ink")
    target = page.locator("#jobs")

    def words_still():
        """The label's reveal is a 90ms transition behind a 90ms delay, so the frame the
        delay ends on is a box the reader can see drawn at the opacity it is leaving —
        which is what `to_be_visible` is satisfied by, and what the paint read behind it
        then reports as the status's own ink. Ask the transitions instead: the call
        flushes pending style, so a reveal that has been started is in the list on the
        first read and a control that never moves reports empty at once."""
        page.wait_for_function(
            """() => [...document.querySelectorAll('.lf-margin-button-label')]
                 .every((label) => label.getAnimations().length === 0)"""
        )

    def assert_status(phase, context, control=marker):
        if control is marker:
            expect(marker).to_have_attribute("data-identity-probe", "kept")
        page.evaluate("() => document.activeElement.blur()")
        page.mouse.move(0, 0)
        expect(page.locator(".lf-margin-status-trace")).to_be_hidden()
        expect(control.locator(":scope > .lf-margin-button-label")).to_be_hidden()
        words_still()
        current = face(control)
        assert current == {
            "tag": "SPAN",
            "offer": "",
            "behavior": "status",
            "role": "status",
            "icon": RECEIPT_PHASES[phase],
            "word": phase,
            "context": context,
            "tabIndex": -1,
            "cursor": "default",
            "background": expected_paper,
            "border": expected_rule,
            "ink": expected_ink,
            "opacity": "1",
            "width": "32px",
            "wordOpacity": "0",
            "wordPosition": "absolute",
            "wordBackground": expected_label_background,
            "wordInk": expected_label_ink,
        }
        named = re.compile(rf"^{re.escape(phase)}(?:,| for )")
        expect(page.get_by_role("button", name=named)).to_have_count(0)
        expect(page.get_by_role("status", name=named)).to_have_count(1)
        # Hover reveals the full-strength label without dimming or lifting the fitting.
        fitting = {
            key: current[key] for key in ("background", "border", "ink", "opacity")
        }
        control.hover()
        trace_box = page.locator('.lf-margin-status-trace[data-for="jobs"]')
        expect(trace_box).to_be_visible()
        label = control.locator(":scope > .lf-margin-button-label")
        expect(label).to_be_visible()
        words_still()
        expect(label).to_have_css("opacity", "1")
        hovered = face(control)
        assert {
            key: hovered[key] for key in ("background", "border", "ink", "opacity")
        } == fitting
        assert hovered["wordOpacity"] == "1"
        assert hovered["wordPosition"] == "absolute"
        assert hovered["wordBackground"] != "rgba(0, 0, 0, 0)"
        trace = control.evaluate(
            """node => {
              const line = getComputedStyle(node.closest('.lf-margin-item'), '::before');
              const box = getComputedStyle(document.querySelector('.lf-margin-status-trace'));
              return {
                declaredWidth: box.getPropertyValue('--status-trace-w').trim(),
                boxWidth: box.borderTopWidth,
                boxColor: box.borderTopColor,
                lineWidth: line.borderTopWidth,
                lineColor: line.borderTopColor,
              };
            }"""
        )
        assert trace == {
            "declaredWidth": "1.5px",
            "boxWidth": trace["lineWidth"],
            "boxColor": trace["lineColor"],
            "lineWidth": trace["boxWidth"],
            "lineColor": trace["boxColor"],
        }

    assert_status("Sent", "just now")
    result = Axe().run(
        page,
        options={
            "runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a"]},
            "resultTypes": ["violations"],
        },
    )
    assert [
        violation["id"]
        for violation in result.response["violations"]
        if violation["impact"] in {"serious", "critical"}
    ] == []
    assert page.locator(".lf-margin-marker:visible").evaluate_all(
        "rows => rows.some(row => row.tabIndex === 0)"
    ), "no Button is left for Tab to enter the rail by"

    # The reader listening still reaches the phase by its numbered address.
    place = int(re.search(r"(\d+) of ", marker.get_attribute("aria-label")).group(1))
    page.keyboard.press("g")
    page.keyboard.press("m")
    page.keyboard.press(str(place))
    expect(marker).to_be_focused()

    # Standing there is not the same as being the way in. A repaint under the reader
    # leaves the rail's one stop on a Button that acts, and the status without one.
    page.evaluate("() => document.dispatchEvent(new CustomEvent('lf-actions'))")
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame("
        "() => requestAnimationFrame(done)))"
    )
    expect(marker).to_be_focused()
    stops = page.locator(".lf-margin-marker:visible").evaluate_all(
        "rows => rows.map(row => [row.dataset.lfBehavior, row.tabIndex])"
    )
    assert ["status", -1] in stops, stops
    assert [behavior for behavior, index in stops if index == 0] == ["disclosure"], (
        stops
    )

    page.clock.set_fixed_time(datetime.now().astimezone() + timedelta(minutes=3))
    page.evaluate("() => document.dispatchEvent(new CustomEvent('lf-actions'))")
    expect(marker).to_have_attribute("aria-label", re.compile(r"^Waiting for pickup,"))
    assert_status("Waiting for pickup", "Sent 3m ago")

    with service_model.PageTransaction(page_dir) as transaction:
        session_model.record_pickup(transaction, [logged_action])
    told(page)
    assert_status("Picked up", "just now")

    # A direct action makes the acknowledgment a secondary reading. It keeps the same
    # status semantics and full-strength circular fitting instead of falling back to a
    # dim disclosure with an ellipsis, which is the feature gallery's Edit + Picked up
    # arrangement.
    page.evaluate(
        """async () => {
          const {offer, marginButton, registerMarginItem} =
            await import('/runtime/widget-api.js');
          const control = marginButton(offer('button', ''), {
            key: 'edit', icon: 'edit', label: 'Edit', behavior: 'disclosure'
          });
          control.classList.add('lf-receipt-primary-probe');
          window.lfReceiptSecondary = registerMarginItem({
            key: 'receipt-primary-probe', target: document.querySelector('#jobs'),
            controls: control
          });
        }"""
    )
    secondary = page.locator(
        '[data-lf-margin-for="jobs"] .lf-margin-reading-option[data-lf-kinds="pickup"]'
    )
    expect(marker).to_be_hidden()
    expect(secondary).to_be_visible()
    assert_status("Picked up", "just now", secondary)

    page.evaluate("() => document.activeElement.blur()")
    page.mouse.move(0, 0)
    expect(target).not_to_have_class(re.compile(r"lf-margin-target"))
    expect(page.locator(".lf-margin-status-trace")).to_be_hidden()
    secondary.hover()
    expect(page.locator('.lf-margin-status-trace[data-for="jobs"]')).to_be_visible()
    expect(target).not_to_have_class(re.compile(r"\blf-margin-target\b"))
    page.locator(".lf-receipt-primary-probe").hover()
    expect(target).to_have_class(re.compile(r"\blf-margin-target\b"))
    expect(page.locator(".lf-margin-status-trace")).to_be_hidden()
    page.evaluate("() => window.lfReceiptSecondary.unregister()")
    expect(marker).to_be_visible()

    claimed = CliRunner().invoke(
        cli_model.cli,
        [
            "status",
            str(page_dir),
            "working",
            "checking the mounts",
            "--on",
            "jobs",
        ],
    )
    assert claimed.exit_code == 0, claimed.output
    told(page)

    expect(marker).to_have_attribute("data-identity-probe", "kept")
    active = face()
    assert active["tag"] == "SPAN"
    assert active["offer"] == "button"
    assert active["behavior"] == "disclosure"
    assert active["role"] == "button"
    assert active["icon"] == "activity"
    assert active["word"] == "Active…"
    assert active["context"] == "Checked in just now · checking the mounts"
    assert active["cursor"] == "pointer"
    assert active["opacity"] == "1"
    assert active["background"] != "rgba(0, 0, 0, 0)"
    assert active["border"] != "rgba(0, 0, 0, 0)"
    expect(page.get_by_role("button", name=re.compile(r"^Active,"))).to_have_count(1)

    honored = ASK_PAGE.replace(
        '<lf-option id="job-mounts"', '<lf-option id="job-mounts" chosen'
    )
    stamp_page(page_dir, honored, "Honor the mounts choice", completes=("jobs",))
    wait_for_revision(page, 2)
    expect(page.locator('[data-lf-margin-for="jobs"]')).to_have_count(0)
    expect(page.locator("#job-mounts[chosen]")).to_have_count(1)

    assert errors == []
    page.close()


def test_secondary_button_proxies_preserve_disabled_and_focus_contract(browser, serve):
    """Proxy presses preserve a reader's explicit fold until they leave or close it."""
    page, errors = open_page(browser, serve(PANEL_PAGE))
    page.evaluate(
        """async () => {
          const {offer, marginButton, registerMarginItem} =
            await import('/runtime/widget-api.js');
          const controls = document.createElement('span');
          const primary = marginButton(offer('button', ''), {
            key: 'act', glyph: 'A', label: 'Act', behavior: 'action'
          });
          const backup = marginButton(offer('button', ''), {
            key: 'backup', glyph: 'B', label: 'Backup', behavior: 'action', role: 'secondary'
          });
          const locked = marginButton(offer('button', ''), {
            key: 'locked', glyph: 'L', label: 'Locked', behavior: 'action', role: 'secondary'
          });
          const details = marginButton(offer('button', ''), {
            key: 'details', glyph: 'D', label: 'Details', behavior: 'disclosure', role: 'reading'
          });
          details.setAttribute('aria-expanded', 'true');
          locked.setAttribute('aria-disabled', 'true');
          primary.onclick = () => window.lfPrimaryClicks += 1;
          backup.onclick = () => window.lfBackupClicks += 1;
          controls.append(primary, backup, locked, details);
          window.lfPrimaryClicks = 0;
          window.lfBackupClicks = 0;
          window.lfButtonFixture = {
            primary, backup, locked, details,
            registration: registerMarginItem({
              key: 'fixture', target: document.querySelector('#how-cap'), controls
            })
          };
        }"""
    )
    item = page.locator('[data-lf-margin-for="how-cap"]')
    more = item.locator(":scope > .lf-margin-more")
    options = item.locator(":scope > .lf-margin-options")
    more.click()
    backup = options.get_by_role("button", name="Backup")
    expect(options.get_by_role("button", name="Locked")).to_be_disabled()
    expect(options.get_by_role("button", name="Details")).to_have_attribute(
        "aria-expanded", "true"
    )

    primary = item.locator("[data-lf-button-primary]")
    primary.focus()
    page.keyboard.press("Enter")
    assert page.evaluate("() => window.lfPrimaryClicks") == 1
    expect(options).to_be_hidden()
    expect(primary).to_be_focused()

    more.click()
    backup.focus()
    page.keyboard.press("Enter")
    assert page.evaluate("() => window.lfBackupClicks") == 1
    expect(options).to_be_visible()
    expect(backup).to_be_focused()
    page.keyboard.press("Escape")
    expect(options).to_be_hidden()
    expect(more).to_be_focused()

    more.click()
    backup.focus()
    page.evaluate(
        """() => {
          const fixture = window.lfButtonFixture;
          fixture.backup.hidden = true;
          fixture.details.hidden = true;
          fixture.registration.update({immediate: true});
        }"""
    )
    expect(options.get_by_role("button", name="Locked")).to_be_visible()
    expect(more).to_be_hidden()
    expect(primary).to_be_focused()

    page.keyboard.press("Escape")
    expect(more).to_be_hidden()
    expect(options.get_by_role("button", name="Locked")).to_be_visible()
    primary.focus()

    page.evaluate(
        """() => {
          const fixture = window.lfButtonFixture;
          fixture.locked.hidden = true;
          fixture.registration.update({immediate: true});
        }"""
    )
    expect(more).to_be_hidden()
    expect(primary).to_be_focused()

    assert errors == []
    page.close()


@pytest.mark.parametrize("width", [1440, 390])
def test_button_order_budget_and_spilled_actions_are_stable_at_both_widths(
    browser, serve, width
):
    """Semantic priority beats registration order; density never loses an action."""
    fixture = leaf_page(
        "Dense Button targets",
        '<p id="first">First target</p><p id="second">Second target</p>',
    )
    page, errors = open_page(browser, serve(fixture))
    resized(page, width, 900)
    page.evaluate(
        """async () => {
          const {offer, marginButton, marginButtonState, registerMarginItem} =
            await import('/runtime/widget-api.js');
          window.buttonFixtures = [];
          for (const [index, id] of ['first', 'second'].entries()) {
            const target = document.getElementById(id);
            const ordinary = document.createElement('span');
            const editor = document.createElement('span');
            const act = marginButton(offer('button', ''), {
              key: 'act', icon: 'check', label: `Act ${id}`, role: 'primary'
            });
            const details = Array.from({length: 5}, (_, n) => {
              const button = marginButton(offer('button', ''), {
                key: `detail-${n + 1}`, icon: 'dot',
                label: `Detail ${n + 1} ${id}` + (n === 1
                  ? ' with a longer explanation that must remain inside its tooltip' : ''),
                role: 'secondary'
              });
              button.onclick = () => target.dataset.lastAction = String(n + 1);
              return button;
            });
            const save = marginButton(offer('button', ''), {
              key: 'save', icon: 'check', label: `Save ${id}`, role: 'complete',
              tone: 'positive', state: 'engaged'
            });
            const cancel = marginButton(offer('button', ''), {
              key: 'cancel', icon: 'cross', label: `Cancel ${id}`, role: 'escape',
              state: 'engaged'
            });
            ordinary.append(...(index ? [...details, act].reverse() : [act, ...details]));
            editor.append(...(index ? [save, cancel] : [cancel, save]));
            const fixture = {act, details, save, cancel, engaged: true, registrations: []};
            const offers = [
              {key: 'ordinary', target, controls: ordinary},
              {key: 'editor', target, controls: editor,
                state: () => fixture.engaged ? 'engaged' : 'idle'}
            ];
            for (const offered of index ? offers.reverse() : offers)
              fixture.registrations.push(registerMarginItem(offered));
            fixture.rest = () => {
              fixture.engaged = false;
              save.hidden = cancel.hidden = true;
              details.slice(1).forEach(button => button.hidden = true);
              fixture.registrations.forEach(registration => registration.update());
            };
            fixture.busy = () => marginButtonState(save, 'busy');
            window.buttonFixtures.push(fixture);
          }
        }"""
    )
    for target in ("first", "second"):
        item = page.locator(f'[data-lf-margin-for="{target}"]')
        expect(item.locator(".lf-margin-button:visible")).to_have_count(6)
        assert item.locator(".lf-margin-button:visible").evaluate_all(
            "buttons => buttons.map(button => button.dataset.lfButtonKey.replace(/:proxy$/, ''))"
        ) == ["save", "cancel", "act", "detail-1", "detail-2", "all-options"]
        expect(item.locator(".lf-margin-more")).to_be_hidden()
        expect(item.locator(".lf-margin-spill")).to_have_attribute(
            "data-lf-spill-count", "3"
        )
        item.get_by_role("button", name=f"Save {target}", exact=True).focus()
        expect(page.locator(f"#{target}")).to_have_class(
            re.compile(r"lf-margin-target")
        )
        item.get_by_role("button", name=f"Save {target}", exact=True).hover()
        label = item.locator('[data-lf-button-key="save"] .lf-margin-button-label')
        expect(label).to_be_visible()
        box = label.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= width
        detail = item.locator('[data-lf-button-key="detail-2:proxy"]')
        detail.hover()
        expect(detail.locator(".lf-margin-button-label")).to_be_visible()
        assert detail.locator(".lf-margin-button-label").evaluate(
            "label => label.scrollWidth <= label.clientWidth"
        )
        item.locator(".lf-margin-spill").click()
        sheet = page.locator(".lf-page-map-sheet")
        expect(sheet).to_be_visible()
        expect(
            sheet.get_by_role("button", name=f"Detail 3 {target}", exact=True)
        ).to_be_focused()
        sheet.get_by_role("button", name=f"Detail 5 {target}", exact=True).click()
        expect(page.locator(f"#{target}")).to_have_attribute("data-last-action", "5")
        expect(sheet).to_be_hidden()

    first = page.locator('[data-lf-margin-for="first"]')
    second = page.locator('[data-lf-margin-for="second"]')
    save = first.get_by_role("button", name="Save first", exact=True)
    save.focus()
    save.hover()
    second.get_by_role("button", name="Save second", exact=True).focus()
    expect(page.locator("#second")).to_have_class(re.compile(r"lf-margin-target"))
    expect(page.locator("#first")).not_to_have_class(re.compile(r"lf-margin-target"))
    save.hover()
    expect(page.locator("#first")).to_have_class(re.compile(r"lf-margin-target"))
    ring = save.evaluate("button => getComputedStyle(button).borderTopWidth")
    page.evaluate("() => window.buttonFixtures[0].busy()")
    expect(save).to_have_attribute("aria-busy", "true")
    expect(save).to_have_attribute("data-lf-tone", "positive")
    assert save.evaluate("button => getComputedStyle(button).borderTopWidth") == ring
    page.emulate_media(forced_colors="active")
    assert (
        save.locator("svg").evaluate("icon => getComputedStyle(icon).stroke") != "none"
    )
    page.emulate_media(forced_colors="none")

    page.evaluate("() => window.buttonFixtures.forEach(fixture => fixture.rest())")
    for target in ("first", "second"):
        item = page.locator(f'[data-lf-margin-for="{target}"]')
        expect(item.locator(".lf-margin-button:visible")).to_have_count(2)
        expect(item.locator(".lf-margin-more")).to_be_hidden()
        expect(
            item.get_by_role("button", name=f"Act {target}", exact=True)
        ).to_be_visible()
        expect(
            item.get_by_role("button", name=f"Detail 1 {target}", exact=True)
        ).to_be_visible()
    assert errors == []
    page.close()


def test_a_reading_marker_counts_toward_the_expanded_button_budget(browser, serve):
    """A reading-only target never grows a seventh fitting beside its marker."""
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "Keep this thread visible.", {"section": "how-cap"})
    page, errors = open_page(browser, url)
    page.evaluate(
        """async () => {
          const {offer, marginButton, registerMarginItem} =
            await import('/runtime/widget-api.js');
          const controls = document.createElement('span');
          for (let index = 0; index < 6; index += 1)
            controls.append(marginButton(offer('button', ''), {
              key: `peer-${index}`, icon: 'dot', label: `Peer ${index}`,
              role: 'secondary'
            }));
          window.readingBudgetFixture = registerMarginItem({
            key: 'reading-budget', target: document.querySelector('#how-cap'),
            controls, side: 'after'
          });
        }"""
    )
    item = page.locator('[data-lf-margin-for="how-cap"]')
    item.locator(":scope > .lf-margin-more").click()
    expect(item.locator(".lf-margin-button:visible")).to_have_count(6)
    expect(item.locator(":scope > .lf-margin-marker")).to_be_visible()
    expect(item.locator(".lf-margin-spill")).to_have_attribute(
        "data-lf-spill-count", "2"
    )
    assert errors == []
    page.close()


def test_a_spilled_thread_opens_the_full_conversation_without_a_hidden_anchor(
    browser, serve
):
    """The Page map cannot anchor a thread card to a Button it has hidden."""
    page, errors = open_page(
        browser, serve(SUGGESTION_PAGE, events=[COMMENT_ON_SUGGESTION])
    )
    resized(page, 1440, 900)
    page.evaluate(
        """async () => {
          const {offer, marginButton, registerMarginItem} =
            await import('/runtime/widget-api.js');
          const controls = document.createElement('span');
          for (let i = 0; i < 5; i++) controls.append(marginButton(offer('button', ''), {
            key: `detail-${i}`, icon: 'dot', label: `Detail ${i}`, role: 'secondary'
          }));
          registerMarginItem({key: 'details', target: document.getElementById('sug-refill'),
            controls, state: 'engaged'});
        }"""
    )
    item = page.locator('[data-lf-margin-for="sug-refill"]')
    item.locator(".lf-margin-spill").click()
    sheet = page.locator(".lf-page-map-sheet")
    sheet.get_by_role("button", name=re.compile("^Open thread:")).click()
    expect(sheet).to_be_hidden()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-panel")).to_contain_text(COMMENT_ON_SUGGESTION["text"])
    assert errors == []
    page.close()


def test_a_secondary_thread_keeps_card_ownership_through_membership_and_posture(
    browser, serve
):
    """The semantic Thread Button owns its open card as a cluster reconfigures."""
    comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "First thread at this target.",
        "anchor": {"section": "how-cap"},
    }
    page, errors = open_page(browser, serve(PANEL_PAGE, events=[comment]))
    resized(page, 1440, 900)
    page.evaluate(
        """async () => {
          const {offer, marginButton, registerMarginItem} =
            await import('/runtime/widget-api.js');
          const primary = marginButton(offer('button', ''), {
            key: 'act', glyph: 'A', label: 'Act', behavior: 'action'
          });
          window.lfThreadOwner = {
            primary,
            registration: registerMarginItem({
              key: 'fixture', target: document.querySelector('#how-cap'), controls: primary, claim: true
            })
          };
        }"""
    )
    item = page.locator('[data-lf-margin-for="how-cap"]')
    marker = item.locator(":scope > .lf-margin-marker")
    more = item.locator(":scope > .lf-margin-more")
    options = item.locator(":scope > .lf-margin-options")
    thread = options.locator('.lf-margin-reading-option[data-lf-kinds="comment"]')
    thread.evaluate("node => node.dataset.stableProof = 'same-thread-button'")
    thread.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(thread).to_have_attribute("aria-expanded", "true")

    thread.focus()
    page.evaluate(
        """() => {
          const fixture = window.lfThreadOwner;
          fixture.primary.hidden = true;
          fixture.registration.update({immediate: true});
        }"""
    )
    expect(marker).to_be_visible()
    expect(marker).to_be_focused()
    expect(marker).to_have_attribute("aria-controls", "lf-margin-preview")
    expect(marker).to_have_attribute("aria-expanded", "true")
    expect(page.locator(".lf-margin-preview")).to_be_visible()

    page.evaluate(
        """() => {
          const fixture = window.lfThreadOwner;
          fixture.primary.hidden = false;
          fixture.registration.update({immediate: true});
        }"""
    )
    expect(options).to_be_visible()
    expect(thread).to_be_focused()
    expect(thread).to_have_attribute("data-stable-proof", "same-thread-button")
    expect(thread).to_have_attribute("aria-expanded", "true")

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "agent": "Claude",
            "revision": 1,
            "text": "Second thread joined while the first card was open.",
            "anchor": {"section": "how-cap"},
        },
    )
    told(page)
    expect(thread).to_have_attribute("data-stable-proof", "same-thread-button")
    expect(thread.locator(".lf-margin-count")).to_have_text("2")
    expect(page.locator(".lf-margin-thread")).to_have_count(2)
    expect(thread).to_have_attribute("aria-expanded", "true")

    resized(page, 1207, 900)
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(thread).to_have_attribute("aria-controls", "lf-threads")
    expect(thread).not_to_have_attribute("aria-expanded", re.compile(".+"))
    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, open=False)

    resized(page, 1440, 900)
    expect(thread).to_have_attribute("aria-controls", "lf-margin-preview")
    expect(thread).to_have_attribute("aria-expanded", "false")
    expect(options).to_be_visible()
    expect(more).to_be_hidden()
    expect(thread).to_have_attribute("data-stable-proof", "same-thread-button")
    thread.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(thread).to_be_focused()

    assert errors == []
    page.close()


def test_reaction_choices_and_their_receipt_share_an_unided_selected_block(
    browser, serve
):
    """The durable section coordinate does not pull the visible RHS item to its top."""
    page, errors = open_page(browser, serve(UNID_SELECTION_PAGE))
    resized(page, 1600, 900)
    paragraph = page.locator("#s-how > p:nth-of-type(2)")
    box = paragraph.bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 6),
        (box["x"] + box["width"] - 8, box["y"] + box["height"] - 6),
        steps=12,
    )
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    bar.locator(".lf-react-trigger").click()
    # The choices are the bar's own, raised on the selection where the reader is
    # pointing: an anchored response opens in place rather than docking a row of
    # options into the margin. What the margin holds for this block is the receipt.
    expect(bar).to_have_class(re.compile(r"\blf-react-open\b"))

    bar.locator('.lf-react[data-token="ok"]').click()
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["anchor"]["section"] == "s-how" and sent["anchor"]["quote"]
    receipt = page.locator(".lf-margin-item").filter(
        has=page.get_by_role("button", name=re.compile(r"^ok — take it back$"))
    )
    expect(receipt).to_have_count(1)
    assert abs(receipt.bounding_box()["y"] - paragraph.bounding_box()["y"]) <= 6
    assert errors == []
    page.close()


def test_shadow_targets_keep_common_shape_identity_and_composed_order(browser, serve):
    """Nested, sibling, and slotted targets follow their rendered order."""
    page, errors = open_page(browser, serve(PANEL_PAGE))
    readings = page.evaluate(
        """async () => {
          const { marginButton, registerMarginItem } =
            await import('/runtime/living-margin.js');
          const makeRecord = label => {
            const shell = document.createElement('div');
            const root = shell.attachShadow({mode: 'open'});
            const target = document.createElement('p');
            target.textContent = `${label} target`;
            root.append(target);
            const controls = marginButton(document.createElement('button'), {
              key: label, glyph: '!', label: `${label} controls`
            });
            return {label, shell, target, controls};
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
            const controls = marginButton(document.createElement('button'), {
              key: label, glyph: '!', label: `${label} controls`
            });
            return {label, shell: slottedShell, target, controls};
          };
          const slotA = makeSlottedRecord('slot a', 'a');
          const slotB = makeSlottedRecord('slot b', 'b');
          slottedShell.append(slotA.target, slotB.target);
          const main = document.querySelector('main');
          main.append(first.shell, second.shell, slottedShell);
          const records = [slotA, nested, second, slotB, first];
          for (const record of records) {
            const {target, controls} = record;
            const margin = registerMarginItem({key: record.label, target, controls});
            record.margin = margin;
          }
          await new Promise(done =>
            requestAnimationFrame(() => requestAnimationFrame(done))
          );
          const readings = [first, nested, second, slotA, slotB].map(({shell, target, controls}) => ({
            ownsTarget: controls.parentElement?.lfEntry?.target === target,
            inDocument: controls.getRootNode() === document,
            itemCount: shell.shadowRoot.querySelectorAll('.lf-margin-item').length,
            commonAction: controls.matches('.lf-margin-button'),
            width: getComputedStyle(controls).width,
            minHeight: getComputedStyle(controls).minHeight,
            radius: getComputedStyle(controls).borderRadius,
            visibleWord: controls.querySelector('.lf-margin-button-label')?.textContent,
          }));
          const testTargets = new Set(records.map(({target}) => target));
          const itemOrder = [...main.querySelectorAll(':scope > .lf-margin-item')]
            .filter(item => testTargets.has(item.lfEntry?.target))
            .map(item => item.lfEntry.target.textContent);
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
                "radius": "50%",
                "visibleWord": "first controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "width": "32px",
                "minHeight": "32px",
                "radius": "50%",
                "visibleWord": "nested controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "width": "32px",
                "minHeight": "32px",
                "radius": "50%",
                "visibleWord": "second controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "width": "32px",
                "minHeight": "32px",
                "radius": "50%",
                "visibleWord": "slot a controls",
            },
            {
                "ownsTarget": True,
                "inDocument": True,
                "itemCount": 0,
                "commonAction": True,
                "width": "32px",
                "minHeight": "32px",
                "radius": "50%",
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
    assert errors == []
    page.close()


def test_status_hover_trace_uses_a_registered_visual_surface(browser, serve):
    """A status follows a package's surface instead of its decorated semantic part."""
    url = serve(
        GENERIC_VISUAL_PAGE,
        layer_registry=GENERIC_VISUAL_LAYER,
        layer_widgets=GENERIC_VISUAL_WIDGETS,
    )
    page, errors = open_page(browser, url)
    resized(page, 1280, 720)
    page.evaluate(
        """async () => {
          const {marginButton, registerMarginItem} =
            await import('/runtime/living-margin.js');
          const status = marginButton(document.createElement('span'), {
            key: 'shape-status', icon: 'pickup', label: 'Picked up', behavior: 'status'
          });
          registerMarginItem({
            key: 'shape-status', target: document.querySelector('#outer'),
            controls: status
          });
        }"""
    )
    margins_laid_out(page)

    status = page.locator('[data-lf-button-key="shape-status"]')
    status.hover()
    trace = page.locator('.lf-margin-status-trace[data-for="outer"]')
    expect(trace).to_be_visible()
    expect(trace).to_have_class(re.compile(r"\blf-shaped\b"))
    assert trace.locator(".lf-margin-status-trace-shape > g > *").evaluate_all(
        "nodes => nodes.map(node => node.localName)"
    ) == ["rect"]
    geometry = page.evaluate(
        """() => {
          const surface = document.querySelector('#outer-surface').getBoundingClientRect();
          const trace = document.querySelector('.lf-margin-status-trace');
          const box = trace.getBoundingClientRect();
          const shape = trace.querySelector('rect');
          const style = getComputedStyle(shape);
          const swatch = document.createElement('span');
          swatch.style.color = 'var(--status-trace-ink)';
          document.head.append(swatch);
          const traceInk = getComputedStyle(swatch).color;
          swatch.remove();
          return {
            sameCenter: Math.abs(box.x + box.width / 2 - (surface.x + surface.width / 2)) < .5
              && Math.abs(box.y + box.height / 2 - (surface.y + surface.height / 2)) < .5,
            surrounds: box.width > surface.width && box.height > surface.height,
            stroke: style.stroke,
            traceInk,
            fill: style.fill,
          };
        }"""
    )
    assert geometry == {
        "sameCenter": True,
        "surrounds": True,
        "stroke": geometry["traceInk"],
        "traceInk": geometry["stroke"],
        "fill": "none",
    }

    page.mouse.move(0, 0)
    expect(trace).to_be_hidden()
    assert errors == []
    page.close()


def test_one_information_button_does_not_raise_a_preview(browser, serve):
    """A single non-thread reading travels directly; cards are reserved for threads."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK])
    )
    resized(page, 1600, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="ask"]').first
    expect(marker).not_to_have_attribute("aria-controls", re.compile(".+"))
    expect(marker).not_to_have_attribute("aria-expanded", re.compile(".+"))
    marker.hover()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_hidden()
    marker.click()
    expect(preview).to_be_hidden()

    assert errors == []
    page.close()


def test_the_margin_groups_meanings_at_one_destination_without_moving_the_page(
    browser, serve
):
    """One location groups its thread and engaged handoff without moving the page."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK])
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    expect(marker).to_have_count(1)
    expect(marker.locator(".lf-margin-count")).to_have_count(0)
    expect(marker).to_have_attribute("aria-label", re.compile(r"Thread, \d+ of"))
    expect(marker).not_to_have_attribute("title", re.compile(".+"))
    more = marker.locator("xpath=..").locator(":scope > .lf-margin-more")
    expect(more).to_be_hidden()
    claim = marker.locator("xpath=..").evaluate(
        """item => {
          const style = getComputedStyle(item);
          const buttons = [...item.querySelectorAll(':scope > .lf-margin-button')]
            .filter(button => button.checkVisibility());
          const needed = buttons.reduce(
            (total, button) => total + button.getBoundingClientRect().width, 0
          ) + (parseFloat(style.columnGap || style.gap) || 0)
            * Math.max(0, buttons.length - 1)
            + (parseFloat(style.paddingLeft) || 0)
            + (parseFloat(style.paddingRight) || 0);
          return {
            needed,
            rail: parseFloat(document.documentElement.style.getPropertyValue('--rail'))
          };
        }"""
    )
    assert claim["rail"] >= claim["needed"] - 0.5, claim

    before = page.evaluate("() => document.scrollingElement.scrollTop")
    marker.hover()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_hidden()
    expect(marker.locator(".lf-margin-button-label")).to_be_visible()
    marker.focus()
    expect(preview).to_be_hidden()

    marker.click()
    expect(marker).to_have_attribute("aria-expanded", "true")
    expect(preview).to_be_visible()
    expect(marker.locator(".lf-margin-button-label")).to_be_hidden()
    expect(page.locator("#bracket")).to_have_class(re.compile(r"lf-margin-target"))
    main_box = page.locator("main").bounding_box()
    preview_box = preview.bounding_box()
    assert preview_box["x"] >= main_box["x"] + main_box["width"]
    assert preview_box["x"] >= 0
    assert preview_box["x"] + preview_box["width"] <= page.evaluate("innerWidth")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(preview).not_to_contain_text("options · choose")
    page.locator(".lf-margin-preview-close").click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(marker).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-keyline")).to_contain_text("close thread")
    expect(preview.locator("textarea")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(marker).to_be_focused()
    held = marker.get_attribute("aria-label")
    page.keyboard.press("ArrowDown")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    assert page.evaluate("() => document.activeElement.matches('.lf-margin-marker')")
    assert page.locator(":focus").get_attribute("aria-label") != held

    options = marker.locator("xpath=..").locator(":scope > .lf-margin-options")
    expect(options).to_be_visible()
    status = options.get_by_role("status", name=re.compile(r"Sent for"))
    expect(status).to_be_visible()
    expect(preview).to_be_hidden()
    status.click()
    expect(options).to_be_visible()
    expect(preview).to_be_hidden()

    assert errors == []
    page.close()


def test_design_mode_retires_and_suppresses_the_top_layer_margin_preview(
    browser, serve
):
    """Ordinary design paint never promises to rise above the browser's top layer."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK])
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()

    preview.get_by_role("button", name="Close thread").focus()
    page.keyboard.press("l")
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))
    expect(preview).to_be_hidden()
    page.mouse.move(4, 200)
    page.locator("body").focus()
    marker.hover()
    expect(preview).to_be_hidden()
    page.locator("body").focus()
    marker.focus()
    expect(preview).to_be_hidden()
    page.keyboard.press("Enter")
    expect(preview).to_be_hidden()
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))

    assert errors == []
    page.close()


def test_a_thread_can_be_answered_in_the_right_margin_without_opening_threads(
    browser, serve
):
    """The anchored thread is a complete conversation beside its source."""
    page, errors = open_page(browser, serve(ASK_PAGE, events=[COMMENT_ON_ASK]))
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    expect(marker.locator(".lf-margin-button-icon")).to_have_attribute(
        "data-lf-icon", "comment"
    )
    first_frame = marker.evaluate(
        """async marker => {
          const card = document.querySelector('.lf-margin-preview');
          const painted = new Promise(resolve => requestAnimationFrame(() => {
            const box = card.getBoundingClientRect();
            resolve({open: card.matches(':popover-open'),
                     thread: card.hasAttribute('data-lf-thread'),
                     left: box.left,
                     top: box.top,
                     placedLeft: card.style.getPropertyValue('--lf-thread-left'),
                     placed: card.style.getPropertyValue('--lf-thread-top')});
          }));
          marker.focus();
          marker.click();
          return painted;
        }"""
    )
    preview = page.locator(".lf-margin-preview")
    thread = page.locator(".lf-margin-thread")
    reply = thread.locator("textarea")

    assert first_frame["open"] and first_frame["thread"], first_frame
    assert first_frame["placed"], first_frame
    assert first_frame["placedLeft"], first_frame
    assert first_frame["left"] == pytest.approx(
        float(first_frame["placedLeft"].removesuffix("px")), abs=0.5
    ), first_frame
    assert first_frame["top"] == pytest.approx(
        float(first_frame["placed"].removesuffix("px")), abs=0.5
    ), first_frame
    expect(thread.locator(".lf-conversation-body")).to_have_text(COMMENT_ON_ASK["text"])
    expect(preview.get_by_role("button", name=re.compile(r"Threads?"))).to_have_count(0)
    expect(thread.locator(".lf-conversation-open")).to_have_count(0)
    geometry = page.evaluate(
        """() => {
          const main = document.querySelector('main').getBoundingClientRect();
          const marker = document.querySelector('[data-lf-kinds="comment"]')
            .getBoundingClientRect();
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          return {mainRight: main.right, markerRight: marker.right,
                  cardLeft: card.left, cardWidth: card.width};
        }"""
    )
    assert geometry["cardLeft"] == pytest.approx(
        geometry["markerRight"] + 8, abs=0.5
    ), geometry
    assert geometry["cardLeft"] >= geometry["mainRight"], geometry
    assert geometry["cardWidth"] >= 459, geometry
    expect(reply).to_be_focused()
    reply.fill("Yes. One visit can cover both jobs.")
    ticked(page)
    expect(reply).to_have_value("Yes. One visit can cover both jobs.")
    expect(reply).to_be_focused()
    thread.get_by_role("button", name="Send").click()
    round_trip(page)

    expect(thread.locator(".lf-conversation-thread")).to_contain_text(
        "Yes. One visit can cover both jobs."
    )
    expect(page.locator(".lf-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    expect(preview).to_be_visible()
    expect(marker).to_have_attribute("aria-controls", "lf-margin-preview")
    expect(marker).to_have_attribute("aria-expanded", "true")
    root_id = thread.locator(".lf-conversation-thread").get_attribute("data-thread")
    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("kind") == "reply" and event.get("parent") == root_id
    ]
    assert [event["text"] for event in replies] == [
        "Yes. One visit can cover both jobs."
    ]
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(preview).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))

    preview.evaluate(
        """card => {
          window.__openedMarginModes = [];
          card.addEventListener('toggle', event => {
            if (event.newState === 'open')
              window.__openedMarginModes.push(card.hasAttribute('data-lf-thread'));
          });
        }"""
    )
    marker.click()
    panel_settled(page)
    expect(preview).to_be_hidden()
    expect(page.locator(f'.lf-thread[data-id="{root_id}"] textarea')).to_be_focused()
    assert page.evaluate("() => window.__openedMarginModes") == []

    assert errors == []
    page.close()


@pytest.mark.parametrize(
    ("width", "panel_open"), [(760, False), (1000, True), (1440, False), (1440, True)]
)
def test_a_new_anchored_comment_keeps_the_readers_conversation_view(
    browser, serve, width, panel_open
):
    """A send continues in the open panel or beside the passage, keeping the page put."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    resized(page, width, 900)
    if panel_open:
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
    page.locator("#mounts-p").click(click_count=3)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    page.locator(".lf-composer textarea").fill("Check the January failure mode.")
    passage_before = page.locator("#mounts-p").bounding_box()
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)

    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["text"]) == (
        "comment",
        "Check the January failure mode.",
    )
    preview = page.locator(".lf-margin-preview")
    if panel_open:
        expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
        expect(preview).to_be_hidden()
        thread = page.locator(f'.lf-thread[data-id="{sent["id"]}"]')
        expect(thread).to_contain_text(sent["text"])
    else:
        expect(preview).to_be_visible()
        thread = preview.locator(
            f'.lf-margin-thread .lf-conversation-thread[data-thread="{sent["id"]}"]'
        )
        expect(thread.locator(".lf-conversation-body")).to_have_text(sent["text"])
        expect(page.locator(".lf-panel")).not_to_have_class(re.compile(r"\bopen\b"))
        expect(page.locator(".lf-keyline")).to_contain_text("close thread")
        preview_box = preview.bounding_box()
        assert preview_box["x"] >= 0, preview_box
        assert preview_box["x"] + preview_box["width"] <= width, preview_box
    expect(thread.locator("textarea")).to_be_focused()
    page.keyboard.type("the next thought")
    expect(thread.locator("textarea")).to_have_value("the next thought")
    passage_after = page.locator("#mounts-p").bounding_box()
    for coordinate in ("x", "y", "width", "height"):
        assert passage_after[coordinate] == pytest.approx(
            passage_before[coordinate], abs=1
        )
    if width == 760:
        page.keyboard.press("Escape")
        expect(preview).to_be_hidden()
        expect(page.locator(".lf-page-map-toggle")).to_be_focused()

    assert errors == []
    page.close()


# What the card came out as, beside the two facts that decide how wide it was allowed to
# be: the posture the cascade granted, and the floor the theme declares. The floor is read
# from the root, where the theme states it, so the test cannot disagree with the layout
# about which number it is. Where the card stands is asked of the column rather than of
# the marker: the card is placed once, in the turn it opens, and a claim landing after
# that moves the marker without moving the card — a race of its own, and not this
# number's.
THREAD_CARD_GEOMETRY = """() => {
  const main = document.querySelector('main').getBoundingClientRect();
  const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
  const reply = document.querySelector('.lf-margin-thread textarea')
    .getBoundingClientRect();
  return {
    mainRight: main.right,
    cardLeft: card.left, cardRight: card.right, cardWidth: card.width,
    replyWidth: reply.width, innerWidth: window.innerWidth,
    beside: getComputedStyle(document.querySelector('main'))
      .getPropertyValue('--lf-thread-beside').trim(),
    floor: parseFloat(getComputedStyle(document.documentElement)
      .getPropertyValue('--thread-card-floor')),
  };
}"""


def send_anchored_comment(page, text):
    """The gesture the contract's sentence is about: a comment accepted on a passage."""
    page.locator("#mounts-p").click(click_count=3)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    page.locator(".lf-composer textarea").fill(text)
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)


def test_a_narrow_margin_gives_the_inline_thread_the_page_not_a_sliver(browser, serve):
    """An accepted comment opens a conversation the reader can answer, at any width.

    The card is placed off its marker and takes whatever room the window leaves to the
    right of that edge. On a page whose left strip is already spoken for, that room runs
    out while the marker is still on screen, and nothing was asking how much was left:
    the shipped pr-walkthrough gave a 72px thread and a 22px reply box at 1200, the quote
    wrapping one word to a line and the placeholder one character. The theme's
    --thread-card-floor is where the margin stops being a margin — under it the card comes
    off its marker and covers the page, which is the posture an accepted comment's thread
    is already allowed (theme.css, on `--thread-card-floor`).
    It does not hand the reader to the Threads panel instead, so a card is what both
    halves of this test read.

    The second half is the other edge of the same number: where the cascade did grant the
    conversation margin, the floor must change nothing, or a fix for the narrow page would
    have taken the margin posture away from the wide one.

    Both halves open on a page that already carries a comment, so the conversation margin
    is claimed and the column has stopped moving before the gesture. Sent into a page
    claiming that strip for the first time, the card is placed against a marker the claim
    then slides, and what the read catches is that race rather than this floor.
    """
    sidebar_page = ASK_PAGE.replace(
        "<main>", '<main><aside class="sidebar">Page reference</aside>', 1
    )
    page, errors = open_page(browser, serve(sidebar_page, events=[COMMENT_ON_ASK]))
    resized(page, 1200, 900)
    send_anchored_comment(page, "Check the January failure mode.")

    narrow = page.evaluate(THREAD_CARD_GEOMETRY)
    assert narrow["beside"] == "0", narrow
    assert narrow["cardWidth"] >= narrow["floor"] - 0.5, narrow
    assert narrow["replyWidth"] >= 160, narrow
    assert narrow["cardLeft"] >= 0, narrow
    assert narrow["cardRight"] <= narrow["innerWidth"] + 0.5, narrow
    # No margin was reserved at this width, so the room came out of the page.
    assert narrow["cardLeft"] < narrow["mainRight"], narrow

    assert errors == []
    page.close()

    page, errors = open_page(browser, serve(ASK_PAGE, events=[COMMENT_ON_ASK]))
    resized(page, 1440, 900)
    send_anchored_comment(page, "Check the January failure mode.")

    wide = page.evaluate(THREAD_CARD_GEOMETRY)
    assert wide["beside"] == "1", wide
    # Beside the column at the card's own width: the floor took nothing away here.
    assert wide["cardLeft"] >= wide["mainRight"], wide
    assert wide["cardWidth"] >= 459, wide

    assert errors == []
    page.close()


def test_a_shared_passage_keeps_all_of_its_threads_in_one_quiet_card(browser, serve):
    """Several roots need no repeated category label or local panel handoff."""
    second_comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "Keep the second conversation separate.",
        "anchor": {"section": "bracket"},
    }
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[COMMENT_ON_ASK, second_comment])
    )
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
    preview = page.locator(".lf-margin-preview")

    expect(preview.locator(".lf-margin-thread")).to_have_count(2)
    expect(preview.locator(".lf-conversation-open")).to_have_count(0)
    expect(preview.get_by_role("button", name=re.compile(r"Threads?"))).to_have_count(0)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    expect(preview).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-thread.flash")).to_have_count(0)

    assert errors == []
    page.close()


def test_the_shipped_long_thread_opens_beside_its_source_in_the_right_margin(
    browser, serve
):
    """The shipped exchange fits beside its source and the contents sidebar.

    Ship review now stands a contents map, and a sidebar claims the opposite strip: the
    thread margin waits for 1472px of shell there rather than 1208px (theme.css), so
    1440 is a window this page opens Threads in rather than the one this case is
    about."""
    example = next(page for page in EXAMPLES if page.stem == "ship-review")
    page, errors = open_page(browser, serve(example))
    resized_shell(page, 1536, 900)
    marker = page.get_by_role(
        "group", name=re.compile(r"Page actions for task · iOS reconnect stall")
    ).locator(":scope > .lf-margin-marker")
    expect(marker).to_have_count(1)
    marker.evaluate(
        "marker => scrollBy(0, marker.getBoundingClientRect().top - innerHeight + 52)"
    )

    marker.click()
    preview = page.locator(".lf-margin-preview")
    thread = page.locator(".lf-margin-thread", has_text="One reconnect in forty")
    expect(preview).to_be_visible()
    expect(preview.locator(".lf-margin-preview-title")).to_have_text(
        "iOS reconnect stall"
    )
    expect(thread.locator(".lf-conversation-msg.user").first).to_be_visible()
    expect(
        thread.get_by_role("button", name="Open interactive reply in Threads")
    ).to_have_count(1)
    geometry = marker.evaluate(
        """markerNode => {
          const main = document.querySelector('main').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          const marker = markerNode.getBoundingClientRect();
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          const title = document.querySelector('.lf-margin-preview-title')
            .getBoundingClientRect();
          const cardStyle = getComputedStyle(document.querySelector('.lf-margin-preview'));
          return {bannerBottom: banner.bottom, mainRight: main.right,
                  markerRight: marker.right,
                  markerMiddle: (marker.top + marker.bottom) / 2,
                  cardLeft: card.left, cardRight: card.right, cardTop: card.top,
                  cardBottom: card.bottom, cardWidth: card.width,
                  shellWidth: document.body.getBoundingClientRect().width,
                  borderLeft: cardStyle.borderLeftWidth,
                  borderRight: cardStyle.borderRightWidth,
                  titleLeft: title.left, titleTop: title.top,
                  cardScroll: document.querySelector('.lf-margin-preview').scrollTop,
                  panelOpen: document.querySelector('.lf-panel').classList.contains('open')};
        }"""
    )
    assert geometry["cardLeft"] >= geometry["markerRight"] - 0.5, geometry
    assert geometry["cardLeft"] >= geometry["mainRight"], geometry
    assert geometry["cardRight"] <= geometry["shellWidth"], geometry
    # Narrower than the 460px --thread-card the pages without a sidebar get, and it is
    # the strip's arithmetic rather than this window: a sidebar page keeps the document
    # exactly --thread-margin (520px) from the right edge at every width, and the marker,
    # the gutter beside it and the card's own 8px inset all come out of that 520.
    assert geometry["cardWidth"] >= 439, geometry
    assert geometry["cardTop"] >= geometry["bannerBottom"] + 7, geometry
    assert geometry["cardBottom"] <= 892, geometry
    assert geometry["cardTop"] <= geometry["markerMiddle"] <= geometry["cardBottom"], (
        geometry
    )
    assert geometry["cardScroll"] == 0, geometry
    assert geometry["borderLeft"] == geometry["borderRight"] == "1px", geometry
    assert geometry["titleLeft"] == pytest.approx(geometry["cardLeft"] + 13, abs=0.5)
    assert not geometry["panelOpen"], geometry

    send = preview.get_by_role("button", name="Send")
    send.focus()
    page.evaluate("() => dispatchEvent(new Event('resize'))")
    expect(send).to_be_focused()

    resized_shell(page, 1536, 480)
    capped = preview.evaluate(
        """card => {
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          const box = card.getBoundingClientRect();
          return {bannerBottom: banner.bottom, top: box.top, bottom: box.bottom,
                  clientHeight: card.clientHeight, scrollHeight: card.scrollHeight};
        }"""
    )
    assert capped["top"] >= capped["bannerBottom"] + 7, capped
    assert capped["bottom"] <= 472.5, capped
    assert capped["scrollHeight"] > capped["clientHeight"], capped
    resized_shell(page, 1536, 900)

    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    expect(preview).to_be_hidden()
    expect(page.locator(".lf-asks-panel")).to_have_class(re.compile(r"\bopen\b"))
    page.keyboard.press("Escape")

    marker.click()
    expect(preview).to_be_visible()

    page.keyboard.press("Shift+Tab")
    expect(
        thread.get_by_role("button", name="Open interactive reply in Threads")
    ).to_be_focused()
    page.keyboard.press("Enter")
    panel_settled(page)
    expect(preview).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator("#off-slip")).to_be_in_viewport()
    expect(page.locator("#off-slip-chase [role=checkbox]")).to_be_checked()
    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, open=False)
    marker.focus()
    page.keyboard.press("Enter")
    expect(preview).to_be_visible()
    expect(preview.locator("textarea")).to_be_focused()

    # 1208 plus the sidebar's 264: the floor a page standing a contents map waits for.
    resized_shell(page, 1472, 900)
    beside = page.evaluate(
        """() => {
          const main = document.querySelector('main').getBoundingClientRect();
          const marker = document.querySelector('[data-lf-kinds="comment"]')
            .getBoundingClientRect();
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          return {mainRight: main.right, markerRight: marker.right, cardLeft: card.left,
                  cardRight: card.right, cardWidth: card.width,
                  shellWidth: document.body.getBoundingClientRect().width};
        }"""
    )
    assert beside["mainRight"] <= beside["cardLeft"] + 0.5, beside
    assert beside["cardLeft"] == pytest.approx(beside["markerRight"] + 8, abs=0.5)
    assert beside["cardRight"] <= beside["shellWidth"] - 8 + 0.5, beside
    # At the sidebar floor the document is down to its own 640px floor and the strip is
    # exactly --thread-margin, so the card takes what the marker, the gutter, main's
    # 24px padding and its own 8px inset leave of that 520.
    assert beside["cardWidth"] >= 423, beside

    resized(page, 1471, 900)
    expect(preview).to_be_hidden()
    expect(marker).to_have_attribute("aria-controls", "lf-threads")
    expect(marker).not_to_have_attribute("aria-expanded", re.compile(".+"))
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, open=False)
    marker.hover()
    expect(preview).to_be_hidden()
    marker.click()
    expect(preview).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))

    assert errors == []
    page.close()


def test_an_open_thread_refresh_keeps_the_current_button_target_highlighted(
    browser, serve
):
    """An open card does not own the highlight after the reader aims elsewhere."""
    page, errors = open_page(
        browser, serve(ACTION_PAGE, events=[COMMENT_ON_SUGGESTION])
    )
    resized(page, 1440, 900)
    suggestion = page.locator('[data-lf-margin-for="sug-refill"]')
    suggestion.locator(".lf-margin-more").click()
    suggestion.locator('.lf-margin-reading-option[data-lf-kinds="comment"]').click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.get_by_role("button", name="Edit draft-ops", exact=True).hover()
    target = page.locator("#draft-ops")
    expect(target).to_have_class(re.compile(r"lf-margin-target"))
    ticked(page)
    assert "lf-margin-target" in target.get_attribute("class").split()
    assert errors == []
    page.close()


def test_focusing_a_thread_button_does_not_open_its_card(browser, serve):
    """Walking the Page map never inserts an unrequested thread into the Tab order."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK])
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    preview = page.locator(".lf-margin-preview")

    marker.focus()
    expect(preview).to_be_hidden()
    toggle = page.locator(".lf-threads-toggle")
    toggle.focus()

    expect(toggle).to_be_focused()
    expect(preview).to_be_hidden()
    expect(page.locator("#bracket")).not_to_have_class(re.compile(r"lf-margin-target"))
    assert errors == []
    page.close()


@pytest.mark.parametrize(("width", "room"), [(1000, 59), (1440, 520)])
def test_a_live_page_reserves_conversation_room_before_its_first_thread(
    browser, serve, width, room
):
    """Creating and resolving the first thread cannot shift the passage being read."""
    page, errors = open_page(
        browser,
        serve(leaf_page("A passage", '<p id="passage">A passage to discuss.</p>')),
    )
    resized(page, width, 900)

    # The strip is a claim main resolves from the shell, so it is read off main rather
    # than off body's padding. A custom property computes to its unresolved expression,
    # so the reading is taken from a probe the layout actually sizes.
    def strip_right():
        return page.evaluate(
            """() => {
              const main = document.querySelector('main');
              const probe = document.createElement('i');
              probe.style.cssText = 'position:fixed;visibility:hidden;height:0;'
                + 'padding:0;border:0;width:var(--strip-r)';
              main.append(probe);
              const width = probe.getBoundingClientRect().width;
              probe.remove();
              return width;
            }"""
        )

    assert strip_right() == room

    comment = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "A first thought",
            "anchor": {"section": "passage"},
        },
    )
    told(page)
    assert strip_right() == room

    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": comment["id"]},
    )
    told(page)
    assert strip_right() == room

    assert errors == []
    page.close()


def test_a_page_that_can_grow_margin_status_reserves_its_rail_before_the_first_gesture(
    browser, serve
):
    """The reader's first move must not be the gesture that pays for the margin.

    Moving a card raises an acknowledgment status at the page edge. Reserved only while
    that status stood, the strip arrived with the move and left again with the undo, and
    the column moved 29px each way — for a reading the page had always been going to
    offer. So the reservation is read off what the page declares, a tag whose registry
    entry has an action or work channel, and the column stands where it will stand
    before the reader touches anything.

    Measured on the shipped board rather than a fixture, because the strip is only worth
    reserving where a real page's width, its claims and its exhibits meet; a fixture
    built to make those agree would prove nothing about any page a reader opens."""
    example = next(page for page in EXAMPLES if page.stem == "triage-board")
    page, errors = open_page(browser, live_url(serve(example)))
    margins_laid_out(page)
    column = page.locator("main").evaluate(
        "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
    )

    page.locator("#card-ie .lf-grip").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    round_trip(page)
    expect(page.locator("#col-fixed #card-ie")).to_have_count(1)
    margins_laid_out(page)
    # Without a status in the margin the readings below would agree for the wrong reason.
    expect(page.locator(".lf-margin-item")).to_have_count(1)
    assert (
        page.locator("main").evaluate(
            "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
        )
        == column
    ), "raising the acknowledgment status moved the readable column"

    undo(page)
    expect(page.locator("#col-wont #card-ie")).to_have_count(1)
    margins_laid_out(page)
    assert (
        page.locator("main").evaluate(
            "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
        )
        == column
    ), "withdrawing the move handed the strip back and moved the column with it"

    assert errors == []
    page.close()


def test_the_full_thread_posture_follows_the_page_container_and_left_claims(
    browser, serve
):
    """A tray or authored sidebar spends room before the contextual thread does."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK])
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)

    page.locator(".lf-asks").click()
    expect(page.locator("body")).to_have_attribute("data-lf-tray", "asks")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, open=False)
    if page.locator("body").get_attribute("data-lf-tray") == "asks":
        page.locator(".lf-asks").click()
    expect(page.locator("body")).not_to_have_attribute("data-lf-tray", "asks")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    marker.click()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(page.locator(".lf-margin-preview")).to_be_visible()

    assert errors == []
    page.close()

    sidebar_page = ASK_PAGE.replace(
        "<main>", '<main><aside class="sidebar">Page reference</aside>', 1
    )
    page, errors = open_page(
        browser,
        serve(sidebar_page, events=[ACTION_ON_ASK, COMMENT_ON_ASK]),
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(page.locator(".lf-panel")).to_have_class(re.compile(r"\bopen\b"))
    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, open=False)
    resized_shell(page, 1472, 900)
    marker.click()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    composition = page.evaluate(
        """() => {
          const main = document.querySelector('main').getBoundingClientRect();
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          return {mainWidth: main.width - 48, mainRight: main.right,
                  cardLeft: card.left, cardRight: card.right,
                  shellWidth: document.body.getBoundingClientRect().width};
        }"""
    )
    assert composition["mainWidth"] >= 639.5, composition
    assert composition["mainRight"] <= composition["cardLeft"] + 0.5, composition
    assert composition["cardRight"] <= composition["shellWidth"] + 0.5, composition

    assert errors == []
    page.close()


def test_the_margin_keeps_its_page_coordinate_while_the_reader_scrolls(browser, serve):
    """Runtime chrome and authored content share one document-space coordinate."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK])
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    target = page.locator("#bracket")

    def offset():
        return marker.bounding_box()["y"] - target.bounding_box()["y"]

    before = offset()
    page.evaluate(
        "() => document.scrollingElement.scrollBy({top: 320, behavior: 'instant'})"
    )
    margins_laid_out(page)
    assert offset() == pytest.approx(before, abs=1)

    assert errors == []
    page.close()


@pytest.mark.parametrize("opener", ["keyboard", "pointer"])
def test_the_small_screen_map_is_a_complete_accessible_sheet(browser, serve, opener):
    """The rail becomes a touch-sized index when the margin no longer exists."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK])
    )
    resized(page, 390, 760)
    expect(page.locator(".lf-living-margin")).to_be_hidden()
    toggle = page.locator(".lf-page-map-toggle")
    expect(toggle).to_be_visible()
    expect(toggle).to_have_text(re.compile(r"Map \(\d+\)"))
    # The row keeps one order at every width and folds what it cannot fit into its menu;
    # the index stays on the row itself, one press away, rather than behind the door.
    assert toggle.evaluate(
        "button => button.parentElement.matches('.lf-banner-actions')"
    ), "the small-screen map was folded behind the banner's door"
    text_insets = page.locator(".lf-banner-actions > .lf-btn:visible").evaluate_all(
        """buttons => buttons.map(button => {
          const box = button.getBoundingClientRect();
          const range = document.createRange();
          range.selectNodeContents(button);
          const text = range.getBoundingClientRect();
          return {label: button.textContent.trim(),
                  above: text.top - box.top, below: box.bottom - text.bottom};
        })"""
    )
    assert text_insets
    for inset in text_insets:
        assert inset["above"] == pytest.approx(inset["below"], abs=1.5), (
            f"{inset['label']} is not vertically centred in the compact banner: {inset}"
        )

    before = page.evaluate("() => document.scrollingElement.scrollTop")
    if opener == "keyboard":
        page.keyboard.press("g")
        expect(page.locator(".lf-keyline")).to_contain_text("Page map")
        page.keyboard.press("Shift+m")
    else:
        toggle.click()
    sheet = page.locator(".lf-page-map-sheet")
    expect(sheet).to_be_visible()
    expect(
        sheet.get_by_role("searchbox", name="Find a Button or location in Page map")
    ).to_be_focused()
    expect(sheet.locator(".lf-page-map-action").first).to_have_css("min-height", "44px")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before

    result = Axe().run(
        page,
        options={
            "runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a"]},
            "resultTypes": ["violations"],
        },
    )
    assert [
        violation["id"]
        for violation in result.response["violations"]
        if violation["impact"] in {"serious", "critical"}
    ] == []

    page.keyboard.press("Escape")
    expect(sheet).to_be_hidden()
    return_focus = page.locator("body") if opener == "keyboard" else toggle
    expect(return_focus).to_be_focused()
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    assert errors == []
    page.close()


def test_a_folded_compact_map_returns_to_the_banner_overflow(browser, serve):
    """A modal returns to the visible door that exposed its folded Map address."""
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    resized(page, 390, 700)
    more = page.get_by_role("button", name="More page addresses", exact=True)
    more.click()
    toggle = page.locator(".lf-page-map-toggle")
    expect(toggle).to_be_visible()
    toggle.click()
    sheet = page.get_by_role("dialog", name="Page map", exact=True)
    expect(sheet).to_be_visible()
    page.keyboard.press("Escape")
    expect(sheet).to_be_hidden()
    expect(more).to_be_focused()
    expect(more).to_have_attribute("aria-expanded", "false")
    assert errors == []
    page.close()


def test_crossing_to_the_small_screen_retires_the_desktop_preview(browser, serve):
    """A responsive posture exposes one map surface, never both at once."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK])
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()

    resized(page, 390, 760)
    expect(page.locator(".lf-living-margin")).to_be_hidden()
    expect(page.locator(".lf-page-map-toggle")).to_be_visible()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    assert errors == []
    page.close()


def test_the_complete_page_map_survives_a_crossing_to_the_wide_screen(browser, serve):
    """The Page map is one destination while its compact rail changes posture."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK])
    )
    resized(page, 390, 760)
    page.locator(".lf-page-map-toggle").click()
    sheet = page.locator(".lf-page-map-sheet")
    expect(sheet).to_be_visible()

    resized(page, 1200, 900)
    expect(page.locator(".lf-living-margin")).to_be_visible()
    expect(page.locator(".lf-page-map-toggle")).to_be_hidden()
    expect(sheet).to_be_visible()
    expect(sheet.locator(".lf-page-map-action")).to_have_count(4)

    assert errors == []
    page.close()


def test_an_open_small_screen_map_reconciles_arriving_meanings(browser, serve):
    """The open sheet is a live projection, not a snapshot from its opening press."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK])
    )
    resized(page, 390, 760)
    page.locator(".lf-page-map-toggle").click()
    sheet = page.locator(".lf-page-map-sheet")
    actions = sheet.locator(".lf-page-map-action")
    expect(actions).to_have_count(4)
    page.keyboard.press("Tab")
    expect(actions.first).to_be_focused()

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "agent": "Claude",
            "revision": 1,
            "text": "A second reading arrived while the map was open.",
            "anchor": {"section": "bracket"},
        },
    )
    told(page)
    expect(
        page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').locator(
            ".lf-margin-count"
        )
    ).to_have_text("2")
    expect(actions).to_have_count(5)
    expect(actions.first).to_be_focused()

    assert errors == []
    page.close()


def test_an_open_desktop_preview_reconciles_arriving_meanings(browser, serve):
    """A pinned marker card stays current while its semantic location is retained."""
    page, errors = open_page(
        browser,
        serve(
            ASK_PAGE,
            events=[
                ACTION_ON_ASK,
                {**COMMENT_ON_ASK, "id": "f" * 32},
            ],
        ),
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "agent": "Claude",
            "revision": 1,
            "text": "A second reading arrived while the preview was pinned.",
            "id": "0" * 32,
            "anchor": {"section": "bracket"},
        },
    )
    told(page)
    expect(marker.locator(".lf-margin-count")).to_have_text("2")
    expect(page.locator(".lf-margin-thread")).to_have_count(2)
    expect(page.locator(".lf-margin-thread").last).to_contain_text(
        "A second reading arrived while the preview was pinned."
    )

    assert errors == []
    page.close()


def test_a_reflow_that_moves_a_marker_carries_its_open_card(browser, serve):
    """The card beside a marker follows the marker when the page moves under it.

    A margin row is placed at its target on the next layout pass, and that pass runs
    whenever the column's size changes — a diagram finishing, an image arriving, a
    disclosure opening above the marker. The card was placed once, when it opened, so
    the page moved and the card stood beside where its marker had been. The reflow here
    is a section growing, which is what every one of those cases is to the margin.
    """
    page, errors = open_page(browser, serve(ASK_PAGE, events=[COMMENT_ON_ASK]))
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    marker.click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    # Where the card is and where its marker would have it: placeThreadPreview's own sum,
    # centred on the marker and held inside the window under the banner.
    beside = """() => {
      const marker = document.querySelector('.lf-margin-marker[data-lf-kinds="comment"]');
      const card = document.querySelector('.lf-margin-preview');
      const m = marker.getBoundingClientRect();
      const c = card.getBoundingClientRect();
      const bannerBottom = document.querySelector('.lf-banner').getBoundingClientRect().bottom;
      const centred = (m.top + m.bottom - c.height) / 2;
      return {marker: m.top,
              want: Math.max(bannerBottom + 8, Math.min(centred, innerHeight - c.height - 8)),
              placed: parseFloat(card.style.getPropertyValue('--lf-thread-top'))};
    }"""
    before = page.evaluate(beside)
    assert abs(before["placed"] - before["want"]) < 1, before

    page.evaluate(
        "() => { document.getElementById('sec-mounts').style.paddingBottom = '48px'; }"
    )
    page.wait_for_function(
        """was => document.querySelector('.lf-margin-marker[data-lf-kinds="comment"]')
                 .getBoundingClientRect().top > was + 40""",
        arg=before["marker"],
    )
    after = page.evaluate(beside)
    assert after["marker"] > before["marker"] + 40, (before, after)
    assert abs(after["placed"] - after["want"]) < 1, (before, after)

    assert errors == []
    page.close()


def test_a_live_version_keeps_the_reader_on_the_same_margin_location(browser, serve):
    """Replacing authored main must not discard focus held by retained map chrome."""
    version_url = serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK])
    page, errors = open_page(browser, live_url(version_url))
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.focus()
    expect(marker).to_be_focused()

    (serve.page_dir / "index.html").write_text(
        ASK_PAGE.replace("Three jobs", "Four jobs")
    )
    told(page)
    expect(page.get_by_role("heading", name="Four jobs")).to_be_visible()
    expect(marker).to_be_focused()

    assert errors == []
    page.close()


def test_a_live_version_retargets_an_open_margin_preview(browser, serve):
    """A retained preview must outline the new document's matching destination."""
    version_url = serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK])
    page, errors = open_page(browser, live_url(version_url))
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    close = page.locator(".lf-margin-preview-close")
    close.focus()
    expect(close).to_be_focused()
    expect(page.locator("#bracket")).to_have_class(re.compile(r"lf-margin-target"))

    (serve.page_dir / "index.html").write_text(
        ASK_PAGE.replace("Three jobs", "Four jobs")
    )
    told(page)
    expect(page.get_by_role("heading", name="Four jobs")).to_be_visible()
    expect(close).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator("#bracket")).to_have_class(re.compile(r"lf-margin-target"))

    assert errors == []
    page.close()


def test_a_version_comparison_joins_the_same_map_and_leaves_with_it(browser, serve):
    """Comparison marks are another projection, not DOM scraped by the map."""
    url = serve(ASK_PAGE)
    _publish(
        serve.page_dir,
        2,
        ASK_PAGE.replace("Three jobs", "Four jobs"),
        "The heading now names four jobs.",
    )
    page, errors = open_page(browser, url.replace("v1.html", "v2.html"))

    compare_with(page, 1)
    expect(
        page.locator('.lf-margin-marker[data-lf-kinds~="change"]')
    ).not_to_have_count(0)
    page.locator(".lf-version").click()
    page.locator('.lf-version-diff[data-lf-version="1"]').click()
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="change"]')).to_have_count(0)

    assert errors == []
    page.close()


def test_closing_the_panel_lands_the_margin_where_the_column_lands(browser, serve):
    """The margin's rows ride the shell carry and are laid out once more at rest.

    Closing Threads carries the reading column back across the window. The body's
    width change laid the margin rows out on the carry's first frame, against a
    column a few pixels into its move, and nothing asked again once it had arrived:
    a resize observer hears a box change size, not place. So two thread Buttons
    stood over the prose the column had moved under them, until the next poll or
    pointer move — a screenshot a blind drive took, and the kind of frame the
    movement tests do not compare because no control was pressed.

    On the shipped page it happened on: a thread on plain prose stands in the
    toolbar host, which is placed off the column's box, where a contributed
    cluster is hoisted into the column and rides it for free."""
    page, errors = open_page(
        browser, serve(next(p for p in EXAMPLES if p.stem == "log-retention"))
    )
    resized(page, 1440, 900)
    margins_laid_out(page)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]').first
    rest = marker.bounding_box()["x"]
    # Every margin layout the page makes, timestamped, and the carry's end from the
    # animation itself: the fact to consume is a layout after the column came to
    # rest, not a number of frames.
    page.evaluate(
        """() => {
          window.__lfLayouts = [];
          document.addEventListener('lf-margin-layout',
            () => window.__lfLayouts.push(performance.now()));
        }"""
    )
    for close in ("Close threads", "toggle", "Escape"):
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        if close == "toggle":
            page.locator(".lf-threads-toggle").click()
        elif close == "Escape":
            page.locator(".lf-threads").focus()
            page.keyboard.press("Escape")
        else:
            page.get_by_role("button", name=close, exact=True).click()
        # The carry runs to its own end rather than being finished for it: the stale
        # placement is the one the body's resize laid out two frames into the move,
        # and finishing the carry before that frame would settle the column first
        # and read a page the reader never sees.
        page.evaluate(
            """() => {
              window.__lfCarryEnd = null;
              const carries = document.querySelector('body > main').getAnimations();
              if (!carries.length) { window.__lfCarryEnd = performance.now(); return; }
              Promise.all(carries.map(carry => carry.finished)).then(
                () => { window.__lfCarryEnd = performance.now(); });
            }"""
        )
        page.wait_for_function(
            "() => !document.querySelector('.lf-panel').classList.contains('open')"
        )
        page.wait_for_function(
            "() => window.__lfCarryEnd !== null"
            " && window.__lfLayouts.some(t => t >= window.__lfCarryEnd)",
            timeout=5000,
        )
        landed = marker.bounding_box()["x"]
        assert landed == pytest.approx(rest, abs=1), (
            f"after {close}: the Thread Button stands at {landed}, the column's rest is {rest}"
        )
    assert errors == []
    page.close()
