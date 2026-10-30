"""File-authored anchors, drawings, width, and handover tests."""

import json
import re

import pytest
from interact_support import (
    append_carried_log_record,
)
from playwright.sync_api import expect
from render_cases_interaction import (
    live_url,
)
from render_cases_widgets import (
    FRAMED_SCROLLER_PAGE,
    OWN_MARGIN_FURNITURE,
    written_anchors,
)
from render_harness import (
    ANCHOR_SOURCES,
    CORPUS_SOURCES,
    EXAMPLES,
    INLINE_PAGE,
    PANEL_THREAD,
    leaf_page,
    open_page,
    page_registry,
    panel_settled,
    resized,
    root_overflow,
    sending,
    wide_width,
    write,
)

from leaf import event_log as events_model
from leaf import events as thread_model
from leaf import render_checks as render_checks_model
from leaf import structure as structure_model
from leaf.hosting import TemporaryPageServer
from leaf.passages import enclosing_ids, page_passages
from leaf.registry import storage as registry_storage
from leaf.render_checks import wait_until_ready
from leaf.render_gate import version as render_gate_model

pytestmark = pytest.mark.shifts_unsurveyed

from browser.threads import open_panel_thread

from journeys import detached_threads, listed_threads


def test_sort_film_comment_restores_its_input_and_step(browser, serve):
    """A moment thread returns to the trace it described after input changes."""
    example = next(path for path in EXAMPLES if path.stem == "rust-sort")
    context = browser.new_context(
        reduced_motion="reduce", viewport={"width": 1715, "height": 1046}
    )
    page = open_page(browser, serve(example), context=context)
    moment = page.locator("#sort-film .sort-moment")
    play = page.locator("#sort-film .sort-play")

    play.focus()
    page.keyboard.press("ArrowRight")
    expect(moment).to_have_attribute("data-part", "moment:random:7:1")
    page.keyboard.press("ArrowLeft")
    expect(moment).to_have_attribute("data-part", "moment:random:7:0")
    page.locator("#sort-film .sort-scrub").focus()
    page.keyboard.press("ArrowRight")
    expect(moment).to_have_attribute("data-part", "moment:random:7:1")
    page.keyboard.press("ArrowLeft")
    expect(moment).to_have_attribute("data-part", "moment:random:7:0")

    moment.click(modifiers=["Alt"])
    composer = page.locator(".lf-composer[data-lf-open]")
    expect(composer).to_be_visible()
    expect(composer.locator("blockquote")).to_contain_text("Random, shuffle 7, step 1")
    write(composer.locator("leaf-text"), "Why does this run start here?")
    composer.locator("leaf-text").press("Enter")
    expect(page.get_by_role("dialog", name=re.compile("Thread for"))).to_be_visible()
    events = events_model.read_events(serve.page_dir)
    assert next(event for event in events if event["kind"] == "comment")["anchor"] == {
        "section": "sort-film",
        "visual": "moment:random:7:0",
    }

    page.get_by_role("button", name="Dismiss thread view").click()
    layout = page.evaluate(
        """async () => {
          const film = document.querySelector('#sort-film');
          const play = film.querySelector('.sort-play');
          const host = document.querySelector('.lf-margin-cluster[data-lf-margin-for="sort-film"]');
          const states = new Set();
          play.click();
          const until = performance.now() + 900;
          while (performance.now() < until) {
            await new Promise(requestAnimationFrame);
            // The marker stands on the film, from the margin layer, whatever step
            // the film shows.
            const f = film.getBoundingClientRect(), h = host.getBoundingClientRect();
            states.add(JSON.stringify([
              document.documentElement.scrollHeight,
              h.top >= f.top - 1 && h.top < f.bottom && h.left < f.right + 40,
            ]));
          }
          play.click();
          return [...states].map(JSON.parse);
        }"""
    )
    assert layout == [[1046, True]]
    page.locator('#sort-film input[value="nearly"]').check()
    expect(moment).to_have_attribute("data-part", "moment:nearly:7:0")
    comment = next(event for event in events if event["kind"] == "comment")
    view = open_panel_thread(page, comment["id"])
    expect(view.locator(".lf-fp-quote")).to_contain_text("Random, shuffle 7, step 1")
    page.locator(".lf-fp-close").click()
    page.get_by_role("button", name="1 comment").press("Enter")
    expect(moment).to_have_attribute("data-part", "moment:random:7:0")


@pytest.mark.watch_shifts
def test_sort_film_playback_keeps_the_stage_and_controls_still(browser, serve):
    """Each trace step paints inside a fixed layout at both wide pane widths."""
    example = next(path for path in EXAMPLES if path.stem == "rust-sort")
    context = browser.new_context(
        reduced_motion="reduce", viewport={"width": 1715, "height": 1046}
    )
    page = open_page(browser, serve(example), context=context)

    for width in (1715, 1200):
        page.set_viewport_size({"width": width, "height": 1046})
        page.locator("#sort-film .sort-play").focus()
        page.keyboard.press("Home")
        layouts = page.evaluate(
            """async () => {
              const film = document.querySelector('#sort-film');
              const stage = film.querySelector('.sort-stage');
              const moment = film.querySelector('.sort-moment');
              const bar = film.querySelector('.sort-bar');
              const play = film.querySelector('.sort-play');
              const samples = new Set();
              play.click();
              const until = performance.now() + 900;
              while (performance.now() < until) {
                await new Promise(requestAnimationFrame);
                const top = stage.getBoundingClientRect().top;
                samples.add(JSON.stringify([
                  Math.round(stage.getBoundingClientRect().height),
                  Math.round(moment.getBoundingClientRect().top - top),
                  Math.round(bar.getBoundingClientRect().top - top),
                ]));
              }
              play.click();
              return [...samples];
            }"""
        )
        assert len(layouts) == 1, (width, layouts)


def test_a_shipped_log_replays_its_example_state(browser, serve):
    """An example that ships a companion log opens with its event state.

    Threads and user decisions are log state: markup alone cannot describe what
    happened, and `page export` drops the layer that draws it. What an example
    *can* ship is the log itself, beside it, exactly as one that wants a screenshot
    ships the bytes beside it. `leaf-dev preview <example>` then opens with those
    events replayed. A thread-bearing log opens mid-thread; an action-only log
    can replay a page-owned decision without inventing a thread.

    The anchor in that log is the part that can rot quietly. It is captured from
    the mapped revision, and it has to name the same passage once the browser has
    built the page; a rewritten sentence leaves the quote resolving to nothing and
    the thread left there detached, which is a broken demo and no error
    anywhere. A sample can instead explicitly retain a historical quote after a
    reply detaches it from a section the current page removed. The corpus's own
    anchor sweep does not cover shipped anchors, because that sweep writes its own.

    A log can also carry a widget, and that is the second thing read here. Markup
    in a message renders in the panel and nowhere else, so no authored page can
    stand in for it — which is exactly how it stayed unrendered: every example's
    widgets are authored into <main>, and a module that never reached a message
    would have left all eight corpus sweeps green.

    Looped rather than parametrized so an empty corpus fails here instead of
    collecting no tests and reporting green."""
    seeded = [p for p in CORPUS_SOURCES if p.with_suffix(".jsonl").exists()]
    assert seeded, "no corpus source ships a log; this gate is reading nothing"
    drawn = []
    replied = []

    for example in seeded:
        url = serve(example)
        # The log's grammar is events joined by "\n" — never splitlines(), whose
        # wider class reads a U+2028 inside a comment's text as a break.
        events = [
            json.loads(line)
            for line in example.with_suffix(".jsonl")
            .read_text(encoding="utf-8")
            .split("\n")
            if line.strip()
        ]
        assert events, f"{example.stem}: the shipped log is empty"

        page = open_page(browser, url)
        logged = events_model.read_events(serve.page_dir)
        previous = set()
        for event in logged:
            references = [
                event[key] for key in ("parent", "undoes", "message") if key in event
            ] + event.get("events", [])
            assert set(references) <= previous, (
                f"{example.stem}: {event['id']} refers to missing earlier events: "
                f"{set(references) - previous}"
            )
            assert event["id"] not in previous, (
                f"{example.stem}: duplicate {event['id']}"
            )
            previous.add(event["id"])
        assert {event["id"] for event in events} <= previous
        by_id = {event["id"]: event for event in logged}

        def thread_of(event_id, by_id=by_id):
            """The thread an event stands in: its root comment, up its parents."""
            event = by_id[event_id]
            while event.get("parent"):
                event = by_id[event["parent"]]
            return event["id"]

        # Read the roots in force through the same fold as the page. A resolved root keeps
        # its thread and attachment but owes no paint; a withdrawn reaction owes neither.
        page_ids = enclosing_ids(structure_model.SourceDocument(example.read_text()))
        threads = thread_model.build_threads(logged, page_ids)
        reacted = [
            thread["root"]
            for thread in threads.values()
            if thread_model.bare_reaction(thread)
            and not thread["resolved"]
            and thread["anchor"]
        ]
        listed = [
            thread
            for thread in threads.values()
            if not thread_model.bare_reaction(thread)
        ]
        sample_threads = set(
            page.eval_on_selector_all(
                "template[data-sample-threads]",
                "els => els.flatMap(el => el.dataset.sampleThreads.split(/\\s+/))",
            )
        )
        # A sample may deliberately demonstrate a quote retained after its original
        # section was removed. It names that historical thread explicitly; ordinary
        # shipped anchors must still resolve in the current page.
        retained = {
            thread["id"]
            for thread in listed
            if thread["id"] in sample_threads
            and thread["detached_from"]
            and thread["detached_from"]["section"] not in page_ids
        }
        anchored = [
            thread["root"]
            for thread in listed
            if not thread["resolved"] and thread["anchor"]
        ]
        # The thread node first, because it arrives whether or not the quote found a
        # home — a stranded one renders wearing `detached`. Waiting on the mark here
        # instead spends the whole timeout on exactly the failure this gate is for
        # and then reports it as "wait_for_function timed out", which says nothing
        # about the anchor.
        # Every comment with words opens a thread; an anchor only decides whether it
        # also paints a mark. Counting threads against the anchored ones would red
        # this gate the day a seed carries a general comment, which is a thing a page
        # may hold.
        assert len(listed_threads(page)) == len(listed), (
            f"{example.stem}: Threads lists another number of threads than the log holds"
        )
        open_targets = {event["anchor"]["section"] for event in anchored}
        for thread in listed:
            if not thread["resolved"]:
                continue
            open_panel_thread(page, thread["id"])
            expect(page.locator(".lf-fp-settle")).to_have_accessible_name("Reopen")
            page.locator(".lf-fp-close").click()
            panel_settled(page, open=False)
            anchor = thread["anchor"]
            if anchor and anchor["section"] not in open_targets:
                item = page.locator(f'[data-lf-margin-for="{anchor["section"]}"]')
                expect(
                    item.locator(
                        '.lf-margin-marker[data-lf-kinds~="comment"], '
                        '[data-lf-margin-entry-key="reading:threads"]'
                    )
                ).to_have_count(0)
        for reaction in reacted:
            section = reaction["anchor"]["section"]
            tab = page.locator(f"#{section}").evaluate(
                "el => el.closest('lf-tab')?.getAttribute('label')"
            )
            if tab:
                page.get_by_role("tab", name=tab, exact=True).click()
            page.locator(f"#{section}").scroll_into_view_if_needed()
            item = page.locator(f'.lf-margin-cluster[data-lf-margin-for="{section}"]')
            expect(item).to_have_count(1)
            # A crowded target may expose this exact reaction through overflow. Follow
            # its visible route rather than requiring every margin entry to stand at rest.
            visible = item.locator(
                f'[data-lf-margin-entry-key="reaction:{reaction["id"]}:open"]:visible'
            )
            more = item.locator(":scope > .lf-margin-more")
            if not visible.count() and more.is_visible():
                more.click()
                expect(item).to_have_attribute("data-lf-options-open", "")
            if visible.count():
                expect(visible).to_be_visible()
            else:
                item.locator(".lf-margin-spill").click()
                sheet = page.get_by_role("dialog", name="Page Map", exact=True)
                expect(
                    sheet.locator(
                        '[data-lf-margin-entry-owner="reactions"]'
                        f'[data-lf-margin-entry-key="reaction:{reaction["id"]}:open"]'
                    )
                ).to_be_visible()
                page.keyboard.press("Escape")
                expect(sheet).to_be_hidden()
            if reaction["anchor"].get("quote"):
                painted = re.sub(
                    r"\s",
                    "",
                    page.evaluate(
                        "() => [...CSS.highlights.get('lf-react')]"
                        ".map(r => r.toString()).join('')"
                    ),
                )
                assert re.sub(r"\s", "", reaction["anchor"]["quote"]) in painted, (
                    f"{example.stem}: the reaction's passage is painted nowhere; the "
                    f"wash reads {painted[:120]!r}"
                )
        detached = detached_threads(page, [thread["id"] for thread in listed])
        assert detached == retained, (
            f"{example.stem} has unexpected detached anchors: {detached - retained}. "
            "Recapture unintended quotes with `leaf thread create --quote` against "
            f"the current file; missing historical sample quotes: {retained - detached}."
        )
        # Only where the log named a passage. The thread count above already allows a
        # seed of general comments, which a page may hold; waiting unconditionally for
        # a mark spends the whole timeout on such a seed and then reports it as
        # "wait_for_function timed out", which is the failure the count's own note
        # says this gate must not produce.
        quoted = [e for e in anchored if e["anchor"].get("quote")]
        if quoted:
            page.wait_for_function(
                "() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0"
            )
        # An anchor that names an element and quotes nothing marks the box rather
        # than the words, so it makes no range and no highlight: a diagram or a
        # board has no sentence to point at, and a comment on the whole of one is a
        # shape the corpus otherwise never shows. The class is what the user
        # follows and what the ring is drawn on, so it is what is read here.
        for event in anchored:
            if event in quoted:
                continue
            section = event["anchor"]["section"]
            target = page.locator(f"#{section}")
            if datum := event["anchor"].get("datum"):
                target = target.locator(f"[data-lf-datum={json.dumps(datum)}]")
            expect(target).to_have_class(re.compile(r"\blf-mark-el\b"))
        # Where the log carries an exchange, its agent voice reaches the thread.
        for event in quoted:
            quote = event["anchor"]["quote"]
            painted = re.sub(
                r"\s",
                "",
                page.evaluate(
                    "() => [...CSS.highlights.get('lf-mark')]"
                    ".map(r => r.toString()).join('')"
                ),
            )
            assert re.sub(r"\s", "", quote) in painted, (
                f"{example.stem}: `{quote}` is quoted in the shipped log and painted "
                f"nowhere on the page; the mark reads {painted[:120]!r}"
            )
        # An action-only log owes no thread: inventing one would misstate the history
        # whose decisions this same gate is meant to replay.
        if any(
            event["kind"] == "reply" and event["author"] == "agent" for event in events
        ):
            replied.append(example.stem)
            answered = next(
                event["parent"]
                for event in events
                if event["kind"] == "reply" and event["author"] == "agent"
            )
            open_panel_thread(page, thread_of(answered))
            expect(page.locator(f"{PANEL_THREAD} .lf-msg.agent")).not_to_have_count(0)

        # The other thing a log carries. A widget can arrive as a message's markup
        # rather than as authored page content, and it draws in the body the panel
        # builds — so its module has to reach a tree the runtime made, in a column
        # narrower than the document's. Every example's own widgets stand in
        # <main>, which is why the eight sweeps could all be green while nothing
        # had rendered one here. It needs its thread open in the panel: shut, the
        # fragment has no box at all, so a reading that walks text nodes sees it
        # and every reading that measures one does not.
        registry = registry_storage.load_registry(serve.page_dir)
        carried_ids = set()
        carried_threads = set()
        for carried in [e for e in events if e.get("markup")]:
            for wid, rec in structure_model.SourceDocument(
                carried["markup"]
            ).by_id.items():
                drawn.append(wid)
                carried_ids.add(wid)
                thread_id = thread_of(carried["id"])
                carried_threads.add(thread_id)
                view = open_panel_thread(page, thread_id)
                shown = view.locator(f"#{wid}")
                expect(shown).to_be_visible()
                # Where the registry says the element holds a request for the
                # user, whatever answers it has to have been built here too:
                # data-lf-offer is the runtime's own mark for a thing to work, so
                # this asks the declaration and never the tag.
                if "value" in registry[rec["tag"]].get("x-awaits", {}):
                    expect(shown.locator("[data-lf-offer]")).not_to_have_count(0)

        # Each carried thread must be disclosed for the gate's geometry readings:
        # hidden bodies have no boxes. The public page check never opens Threads,
        # so exercise its own probes here against every frozen message's widgets.
        # A question answered in words has no control of its own.
        if carried_ids:
            for thread_id in sorted(carried_threads):
                open_panel_thread(page, thread_id)
                for finding, probe, arg in (
                    (
                        "draws a box of no size",
                        "tinyBoxes",
                        page_registry(page),
                    ),
                    (
                        "has a control clipped out of its box",
                        "clippedControls",
                        None,
                    ),
                ):
                    found = (
                        render_checks_model.evaluate_probe(page, probe, arg)
                        if arg
                        else render_checks_model.evaluate_probe(page, probe)
                    )
                    assert found == [], (
                        f"{example.stem}: with the panel open, something {finding}: {found}"
                    )

        page.close()

    assert drawn, (
        "no shipped log carries a widget in a message. That is the other place "
        "markup renders, no authored page can stand in for it, and with none in "
        "the corpus this is the whole of what reads one."
    )
    assert replied, (
        "no shipped log carries an agent reply, so no example exercises the live "
        "thread exchange that authored markup cannot represent"
    )


@pytest.mark.parametrize("source", ANCHOR_SOURCES, ids=lambda p: p.stem)
def test_an_anchor_written_from_the_mapped_revision_lands_on_the_page(
    browser, serve, source
):
    """The claim `leaf thread create` makes is that a quote read out of the mapped revision
    names the same passage in the browser. Four unlike authored pages cover native
    blocks, representative widgets, and projected text that can make the file and
    browser readings disagree. The generated corpus derives its tab bodies from these
    sources, and its generation check owns that composition. A page that authors only a
    data-backed widget has no file passage to compare, so it does not belong in this
    file-to-browser reading."""
    # Suppress the shipped log while retaining companion data. This sweep
    # writes its own anchors and then compares the whole painted mark against
    # exactly those quotes; a seeded thread paints into the same highlight and
    # every example that ever ships one would read as painting text it does not
    # name. The seeded anchor has its own reader in
    # test_a_shipped_log_replays_its_example_state.
    html = source.read_text()
    url = serve(source, seed_log=False)
    d = serve.page_dir
    anchors = written_anchors(d, html)
    document = structure_model.SourceDocument(html)
    registry = registry_storage.load_registry(d)
    authored = page_passages(document, registry).text
    assert authored.strip(), f"{source.stem} has no file passage for this sweep"
    # Nine overlapping anchors exercise section, prefix, and suffix resolution across
    # a compact authored passage without forcing filler prose into the page.
    assert len(anchors) >= 9, (
        f"only {len(anchors)} anchors over {source.stem}; sweep too thin"
    )
    for i, (_, anchor) in enumerate(anchors):
        append_carried_log_record(
            d,
            {
                "kind": "comment",
                "author": "agent",
                "revision": 1,
                "id": f"written{i}",
                "anchor": anchor,
                "text": f"note {i}",
            },
        )
    page = open_page(browser, live_url(url))
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    # The runtime's own record of which threads it found a home for, as each
    # thread's view in the panel quotes it.
    detached = sorted(
        detached_threads(page, [f"written{i}" for i in range(len(anchors))])
    )
    assert detached == [], (
        f"{len(detached)} anchors resolved to nothing in {source.stem}: {detached}"
    )
    # And that the homes are the right ones. Painted in thread order, one range per
    # segment, so the passages concatenate: whitespace aside, because a quote's is
    # elastic to the search by design — a block boundary is a space in the file's
    # reading and no character at all in the page's.
    painted = re.sub(
        r"\s",
        "",
        page.evaluate(
            "() => [...CSS.highlights.get('lf-mark')].map(r => r.toString()).join('')"
        ),
    )
    wanted = re.sub(r"\s", "", "".join(quote for quote, _ in anchors))
    assert painted == wanted, f"anchors in {source.stem} painted text they don't name"


def test_available_space_is_a_generic_package_capacity(browser, serve):
    """An available surface with no sidebar receives the page room even when it is
    ordinary compound markup. Diagram's source-sized layout must not be the mechanism
    that grants the shared capacity. An ordinary prose-adjacent sidebar then withholds
    its whole side, unlike the contents spine that declares its shell-edge occupancy."""
    entry = {
        "description": "A project package's compound review surface.",
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "markup",
        "x-space": "available",
        "x-upgrade": False,
        "x-example": '<lf-roomy id="roomy"><section>One</section></lf-roomy>',
    }
    source = leaf_page(
        "Available package surface",
        """
<style>
lf-roomy { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
lf-roomy > section { min-height: 80px; border: 1px solid currentColor; }
</style>
<h1 id="t">Available package surface</h1>
<lf-roomy id="roomy"><section>One</section><section>Two</section></lf-roomy></div></div>
""",
    )
    page = open_page(browser, serve(source, layer_registry={"lf-roomy": entry}))
    resized(page, 1762, 900)
    at = page.locator("#roomy").evaluate("""el => {
      const box = el.getBoundingClientRect();
      const children = [...el.children].map(node => node.getBoundingClientRect().width);
      return {
        left: box.left, right: box.right, width: box.width, children,
        room: (() => {
          const probe = document.createElement('i');
          probe.style.cssText = 'position:fixed;visibility:hidden;width:var(--lf-room)';
          // Children of a breakout reset --lf-room to 100%; read its parent's
          // allocation, which is the room the breakout itself received.
          el.parentElement.append(probe);
          const width = probe.getBoundingClientRect().width;
          probe.remove();
          return width;
        })(),
      };
    }""")
    assert abs(at["width"] - at["room"]) <= 1, at
    assert at["width"] > 1600, at
    assert abs(at["children"][0] - at["children"][1]) <= 1, at
    assert at["children"][0] > 750, at
    assert root_overflow(page) == 0, at
    page.close()

    source = leaf_page(
        "Available package surface with ordinary sidebar",
        """
<style>
lf-roomy { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
lf-roomy > section { min-height: 300px; border: 1px solid currentColor; }
</style>
<div class="layout-sidebar"><aside><div class="layout-track">
  <p>Reference</p><p>Supporting information</p><p>Helpful link</p>
  <p>Further notes</p><p>Useful actions</p>
</div></aside><div class="layout-column">
<h1 id="t">Available package surface</h1>
<lf-roomy id="roomy"><section>One</section><section>Two</section></lf-roomy></div></div>
""",
    )
    page = open_page(browser, serve(source, layer_registry={"lf-roomy": entry}))
    resized(page, 1726, 900)
    at = page.evaluate("""() => {
      const sidebar = document.querySelector('.layout-sidebar > aside').getBoundingClientRect();
      const surface = document.querySelector('lf-roomy').getBoundingClientRect();
      return {
        sidebar: {left: sidebar.left, right: sidebar.right,
                  top: sidebar.top, bottom: sidebar.bottom},
        surface: {left: surface.left, right: surface.right,
                  top: surface.top, bottom: surface.bottom, width: surface.width},
      };
    }""")
    assert at["surface"]["top"] < at["sidebar"]["bottom"], at
    assert at["surface"]["left"] >= at["sidebar"]["right"] + 23, at
    assert at["surface"]["width"] > 1080, at
    assert root_overflow(page) == 0, at


def test_named_wide_is_the_evidence_width_of_a_document_layout(browser, serve):
    """`wide` is the shared capped evidence width wherever a block stands on a document
    page. A sidebar page's body is wider than `--wide` at a large window, so the
    breakout's growth alone left a named-wide block at the holder's width there. The
    cap holds an authored occurrence and a package default (a diff) alike, at the
    page's own `--wide`, while a block that names no width still fills its holder and
    `available` takes it all. At the theme's own `--wide`, which it derives from the
    code size, the diff's 100-column line at four-digit line numbers reads without
    scrolling. A workspace states no evidence width, so there both fill
    their pane as a block that names none does. A narrow window's holder still bounds
    the wide block."""
    line = '    return format!("{}: {}", self.bracket_name(), self.material.to_string()); // x'
    line = (line + "x" * 100)[:100]
    blocks = f"""
<div id="named" data-width="wide">Named wide.</div>
<lf-diff id="patch"><pre>
diff --git a/feeders/mount.py b/feeders/mount.py
--- a/feeders/mount.py
+++ b/feeders/mount.py
@@ -1201,2 +1201,2 @@
 def bracket():
-    return "plastic"
+{line}
</pre></lf-diff>
<div id="plain">No width named.</div>
<div id="available" data-width="available">Available.</div>
"""
    sidebar_page = leaf_page("Sidebar body", f"<div>{blocks}</div>", layout="sidebar")
    workspace_page = leaf_page(
        "Workspace pane",
        f'<lf-pane id="pane" label="Evidence"><div id="holder">{blocks}</div></lf-pane>',
        layout="workspace",
    )
    configured = leaf_page(
        "Configured width",
        f"<div>{blocks}</div>",
        head="<style>:root { --wide: 900px; }</style>",
        layout="sidebar",
    )
    measure = """() => Object.fromEntries(
      ['named', 'patch', 'plain', 'available'].map(id => {
        const box = document.getElementById(id).getBoundingClientRect();
        return [id, {width: Math.round(box.width), left: Math.round(box.left)}];
      }))"""
    scrolled = """() => {
      const text = document.getElementById('patch').shadowRoot
        .querySelector('code.lf-text-scroller');
      return text.scrollWidth - text.clientWidth;
    }"""
    for source, cap in (
        (sidebar_page, "theme"),
        (workspace_page, None),
        (configured, 900),
    ):
        page = open_page(browser, serve(source))
        resized(page, 1726, 900)
        at = page.evaluate(measure)
        if cap == "theme":
            cap = wide_width(page)
            expect(page.locator("#patch")).to_have_class(re.compile(r"\blf-rendered\b"))
            assert page.evaluate(scrolled) <= 0, at
        assert at["plain"]["width"] > 1080 + 200, at
        assert at["available"]["width"] == at["plain"]["width"], at
        for capped in ("named", "patch"):
            width = cap or at["plain"]["width"]
            assert at[capped]["width"] == pytest.approx(width, abs=1), (capped, at)
            assert at[capped]["left"] == at["plain"]["left"], (capped, at)
        assert root_overflow(page) == 0

        resized(page, 540, 720)
        narrow = page.evaluate(measure)
        assert narrow["named"]["width"] == narrow["plain"]["width"] < 540, narrow
        assert root_overflow(page) == 0


def test_the_render_gate_names_a_wide_widget_drawn_over_the_pages_own_margin(
    browser, serve
):
    """Two rules in the theme give a margin up to what stands in it, one per claimant,
    and a rule is only ever as complete as the list behind it. A project hangs its own
    apparatus out there and the theme has no rule for it, so this is what is left: the
    room the page states is measured against what is actually in the margin, and a widget
    drawn over any of it is named at handover with both boxes in the message.

    It reads margin content by the same test the pass above excuses one by — placed
    absolutely or fixed, or floated clear of the column — so this needs no vocabulary
    of its own and nothing has to be declared to it. That is what keeps the two theme
    rules honest: the next claimant that forgets one is a refusal with a name on it
    rather than a page somebody eventually notices is drawn over its own controls.

    The page's own frame is the same place: a wide widget is measured against the box
    that frames it, and everything else on the page is excused by a scroll container
    above it. The fixture deliberately overrides the board's width so it escapes the
    frame; the ordinary theme now holds it inside. Asked in the wrong order, the scroll
    container's excuse ate this measurement, so a wide widget escaping its frame went
    unnamed."""
    framed = FRAMED_SCROLLER_PAGE[FRAMED_SCROLLER_PAGE.index("<div id='own-frame'") :]
    framed = framed[: framed.index("</lf-board></div>") + len("</lf-board></div>")]
    source = OWN_MARGIN_FURNITURE.replace(
        "</head>", "<style>#framed { width: 1080px; }</style></head>"
    )
    failures = render_gate_model.render_version(
        browser, serve(source.replace("</main>", framed + "</main>"))
    ).failures

    assert [
        f
        for f in failures
        if f.code == "over-margin"
        and f.at == "<lf-board id=sprint>"
        and f.values["marginContent"] == "<div id=own-rail>"
    ], (
        f"the gate said nothing about a board drawn over the page's own margin: {failures}"
    )
    assert not [
        f for f in failures if f.code == "past-column" and "own-rail" in f.at
    ], "the furniture itself was named for standing where it was put"
    assert [
        f
        for f in failures
        if f.at == "<lf-board id=framed>"
        and f.values.get("frame") == "<div id=own-frame>"
    ], (
        "the gate said nothing about a wide widget escaping a frame that scrolls: "
        f"{failures}"
    )


def test_two_listener_keys_keep_both_tabs_authorized(browser, serve):
    """Cookie names distinguish real ports in one browser's shared cookie jar."""
    first_url = serve(INLINE_PAGE)
    with (
        TemporaryPageServer(serve.page_dir, token="another-listener-key") as other,
        browser.new_context() as context,
    ):
        first = open_page(browser, first_url, context=context)
        second = open_page(browser, other.url, context=context)
        for page in (first, second):
            assert page.evaluate("() => fetch('/api/state').then(r => r.status)") == 200
            page.reload()
            wait_until_ready(page)
            assert "?t=" not in page.url
            assert page.evaluate("() => fetch('/api/state').then(r => r.status)") == 200
        cookies = context.cookies()
        assert len({cookie["name"] for cookie in cookies}) == 2
        assert all(
            cookie["httpOnly"] and cookie["sameSite"] == "Strict" for cookie in cookies
        )
        assert first.evaluate("document.cookie") == ""

        # Native keyboard sends still use relative API requests after both arrivals.
        first.keyboard.press("c")
        first.keyboard.type("Both tabs remain usable")
        with sending(first, "comment"):
            first.keyboard.press("Control+Enter")
        assert any(
            event.get("text") == "Both tabs remain usable"
            for event in events_model.read_events(serve.page_dir)
        )
        assert second.evaluate("() => fetch('/api/state').then(r => r.status)") == 200


def test_a_layout_on_a_child_of_main_arranges_it_as_it_would_main(browser, serve):
    """A page Layout's box is `main`, or a child of a `main` that carries none, and its
    parent is the shell it is placed in. A column whose box is a child of `main` takes
    the same column, margin content, contents map and breakouts as one on `main`
    itself, at a width where the shell must shift the column for its sidebar, and a
    root workspace fills the window while a child keeps document end room. A `main` the
    page narrows, borders or gives scrollbar gutters is the shell the child column
    measures, so nothing it holds stands past its edges or over its border or gutters."""
    column_body = """
<h1>Migration plan</h1>
<div class="layout-sidebar"><aside id="route"><div class="layout-track"><nav aria-label="Route"><a href="#move">Move</a></nav></div></aside><div class="layout-column layout-notes">
<div class="layout-note"><p>Support cadence.</p><aside class="note" id="frequency">Support runs this twice a month.</aside></div>
<h2 id="move">Move</h2>
<p>Shift one cohort at a time while keeping the old readers available.</p>
<div id="room" data-width="available">Available evidence.</div>
<div style="height: 1200px"></div></div></div>
"""
    workspace_body = """
<header><h1>Queue</h1></header>
<div id="regions"><p>Work one item at a time.</p></div>
"""
    reading = """() => {
      const box = document.getElementById('box'), main = document.querySelector('main');
      const target = box ?? main;
      const rect = (node) => {
        const b = node.getBoundingClientRect();
        return [Math.round(b.left), Math.round(b.right), Math.round(b.top),
                Math.round(b.bottom)];
      };
      const measured = {
        box: rect(target),
        regions: rect(document.getElementById('regions') ?? target),
        main: rect(main),
        inner: [Math.round(rect(main)[0] + main.clientLeft),
                Math.round(rect(main)[0] + main.clientLeft + main.clientWidth)],
      };
      for (const id of ['route', 'frequency', 'room', 'contents']) {
        const node = document.getElementById(id);
        if (node) {
          const style = getComputedStyle(node);
          measured[id] = [rect(node), style.float, style.position];
        }
      }
      return measured;
    }"""

    def without_main(reading):
        return {k: v for k, v in reading.items() if k not in ("main", "inner")}

    def measured(body, layout, width, head=""):
        on_main = leaf_page("layout box", body, layout=layout, head=head)
        in_child = leaf_page(
            "layout box",
            f'<section id="box" class="layout-{layout}">{body}</section>',
            layout=None,
            head=head,
        )
        readings = []
        for source in (on_main, in_child):
            page = open_page(browser, serve(source))
            resized(page, width, 800)
            readings.append(page.evaluate(reading))
            assert root_overflow(page) == 0, readings[-1]
            page.close()
        return readings

    on_main, in_child = measured(column_body, "column", 1160)
    assert without_main(in_child) == without_main(on_main)
    mapped = column_body.replace(
        '<nav aria-label="Route"><a href="#move">Move</a></nav>',
        '<lf-toc id="contents"></lf-toc>',
    )
    on_main, in_child = measured(mapped, "column", 1440)
    assert on_main["contents"][2] == "fixed", on_main
    assert without_main(in_child) == without_main(on_main)
    on_main, in_child = measured(workspace_body, "workspace", 1280)
    assert {
        k: v for k, v in without_main(in_child).items() if k not in ("box", "regions")
    } == {k: v for k, v in without_main(on_main).items() if k not in ("box", "regions")}
    for key in ("box", "regions"):
        assert in_child[key][:3] == on_main[key][:3]
        assert in_child[key][3] < on_main[key][3]
    assert on_main["regions"][3] == 800, on_main

    narrowed = "<style>main { max-width: 900px; margin-inline: auto; }</style>"
    _, in_child = measured(column_body, "column", 1440, head=narrowed)
    left, right = in_child["main"][:2]
    assert right - left == 900, in_child
    for edges in (in_child["box"], in_child["room"][0]):
        assert left <= edges[0] and edges[1] <= right, in_child

    bordered = (
        "<style>main { border-inline: 100px solid; height: 700px; overflow-y: auto;"
        " scrollbar-gutter: stable both-edges; }"
        " main::-webkit-scrollbar { width: 40px; }</style>"
    )
    _, in_child = measured(column_body, "column", 1400, head=bordered)
    left, right = in_child["inner"]
    assert left - in_child["main"][0] == 140, in_child
    for edges in (in_child["box"], in_child["route"][0], in_child["room"][0]):
        assert left <= edges[0] and edges[1] <= right, in_child
