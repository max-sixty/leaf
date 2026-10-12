"""File-authored anchors, drawings, width, and handover tests."""

import json
import re

import pytest
from interact_support import (
    append_carried_log_record,
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
from playwright.sync_api import expect
from render_cases_interaction import (
    live_url,
)
from render_cases_layout import banner_control
from render_cases_widgets import (
    FRAMED_SCROLLER_PAGE,
    OWN_MARGIN_FURNITURE,
    TWIN_V1,
    TWIN_V2,
    written_anchors,
)
from render_harness import (
    ANCHOR_SOURCES,
    CORPUS_SOURCES,
    EXAMPLES,
    INLINE_PAGE,
    leaf_page,
    margins_laid_out,
    nudge,
    open_page,
    page_registry,
    refuse,
    resized,
    root_overflow,
    sending,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


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
    expect(page.locator(".lf-thread")).to_contain_text("Random, shuffle 7, step 1")
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
    the thread standing there detached, which is a broken demo and no error
    anywhere. A sample can instead explicitly retain a historical quote after a
    reply detaches it from a section the current page removed. The corpus's own
    anchor sweep does not cover shipped anchors, because that sweep writes its own.

    A log can also carry a widget, and that is the second thing read here. Markup
    in a message renders in the panel and nowhere else, so no authored page can
    stand in for it — which is exactly how it stayed unrendered: every example's
    widgets are authored into <main>, and a module that never reached a message
    would have left all eight corpus sweeps green.

    The third is what the user did to one. A decision on such a widget is folded
    through a projection of its own and replayed into a tree the panel built, and a
    seed carrying the question but not the answer reads only the untouched half —
    which is the same gap as the widget's, one turn further in. It is read against
    the neighbour that separates a replay from a rendering: the same page, the same
    log with the decisions removed. A widget that says the same either way was never
    reached, and every assertion above this one passes just the same.

    Looped rather than parametrized so an empty corpus fails here instead of
    collecting no tests and reporting green."""
    seeded = [p for p in CORPUS_SOURCES if p.with_suffix(".jsonl").exists()]
    assert seeded, "no corpus source ships a log; this gate is reading nothing"
    drawn = []
    decided = []
    replied = []
    read_as = {}  # widget id -> how it reads with the log's decision standing

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
        # Read standing roots through the same fold as the page. A resolved root keeps
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
        expect(page.locator(".lf-thread")).to_have_count(len(listed))
        open_targets = {event["anchor"]["section"] for event in anchored}
        for thread in listed:
            if not thread["resolved"]:
                continue
            card = page.locator(f'.lf-thread[data-id="{thread["id"]}"]')
            expect(
                card.get_by_role(
                    "button",
                    name=re.compile(r"\bReopen(?: thread)?$"),
                    include_hidden=True,
                )
            ).to_have_count(1)
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
                        '[data-lf-margin-entry-owner="standing-reactions"]'
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
        detached = set(
            page.eval_on_selector_all(
                ".lf-thread .lf-quote.detached",
                "els => els.map(el => el.closest('.lf-thread').dataset.id)",
            )
        )
        assert detached == retained, (
            f"{example.stem} has unexpected detached anchors: {detached - retained}. "
            "Recapture unintended quotes with `leaf thread open --quote` against "
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
            expect(page.locator(".lf-thread .lf-msg.agent")).not_to_have_count(0)

        # The other thing a log carries. A widget can arrive as a message's markup
        # rather than as authored page content, and it draws in the body the panel
        # builds — so its module has to reach a tree the runtime made, in a column
        # narrower than the document's. Every example's own widgets stand in
        # <main>, which is why the eight sweeps could all be green while nothing
        # had rendered one here. It needs the panel open: shut, the fragment is in
        # the DOM with no box at all, so a reading that walks text nodes sees it
        # and every reading that measures one does not.
        page.locator(".lf-threads-toggle").click()
        registry = registry_storage.load_registry(serve.page_dir)
        carried_ids = set()
        carried_threads = set()
        for carried in [e for e in events if e.get("markup")]:
            for wid, rec in structure_model.SourceDocument(
                carried["markup"]
            ).by_id.items():
                drawn.append(wid)
                carried_ids.add(wid)
                shown = page.locator(f"#{wid}")
                card = page.locator(".lf-thread").filter(has=shown)
                carried_threads.add(card.get_attribute("data-id"))
                summary = card.locator(".lf-thread-summary")
                if card.get_attribute("open") is None:
                    summary.click()
                expect(shown).to_be_visible()
                # Where the registry says the element holds a request for the
                # user, whatever answers it has to have been built here too:
                # data-lf-offer is the runtime's own mark for a thing to work, so
                # this asks the declaration and never the tag.
                if registry[rec["tag"]].get("x-awaits"):
                    expect(shown.locator("[data-lf-offer]")).not_to_have_count(0)

        # Each carried thread must be disclosed for the gate's geometry readings:
        # hidden bodies have no boxes. The public page check never opens Threads,
        # so exercise its own probes here against every frozen message's widgets.
        # Assert the control population first so a clean reading cannot be vacuous.
        if carried_ids:
            offers = page.evaluate(
                """(ids) => ids.flatMap((id) => {
                     const el = document.getElementById(id);
                     return el ? [...el.querySelectorAll('[data-lf-offer]')] : [];
                   }).length""",
                sorted(carried_ids),
            )
            assert offers, (
                f"{example.stem}: no widget a message carries built a control, so the "
                "two readings below were handed nothing of the panel's to look at"
            )
            for thread_id in sorted(carried_threads):
                card = page.locator(f'.lf-thread[data-id="{thread_id}"]')
                if card.get_attribute("open") is None:
                    card.locator(".lf-thread-summary").click()
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

        # And the third thing a log carries: what the user did to one of those
        # widgets. A decision on a widget a message carries is folded from thread
        # markup rather than from the version, through a projection of its own
        # (`frozen_thread_reading`), and replayed into a tree the panel built — so
        # a corpus that seeds the question and not the answer reads the untouched
        # half of every such widget and leaves the whole standing-decision route
        # to unit-style fixtures. The seed is what puts it under the sweeps.
        decided_here = [
            e["widget"]
            for e in events
            if e["kind"] == "action" and e["widget"] in carried_ids
        ]
        # Named by each carried widget's public semantic reading, which is where a
        # standing winner has to appear for the gate to reapply it at all.
        standing = page.evaluate(
            """async ids => {
              const {widgetController} = await window.__lfRuntimeImport('/runtime/widget-api.js');
              return ids.filter(id => Object.values(
                widgetController(document.getElementById(id)).read().actions,
              ).some(action => action.standing.length));
            }""",
            decided_here,
        )
        for wid in decided_here:
            decided.append(wid)
            assert wid in standing, (
                f"{example.stem}: the log decides #{wid} and the runtime's standing "
                f"state names only {standing} — the panel's fold reached the gate for "
                "nothing the user did"
            )
            read_as[wid] = page.locator(f"#{wid}").inner_text()
        page.close()

        # The single-factor neighbour: the same page under the same log with the
        # decisions taken out. A widget that reads the same either way is one the
        # replay never reached, and every assertion above it would still pass —
        # a drawn widget and a built control say nothing about whose state is on it.
        if decided_here:
            plain = serve(example, seed_log=False)
            for event in [e for e in events if e["kind"] != "action"]:
                append_carried_log_record(serve.page_dir, event)
            undecided = open_page(browser, plain)
            undecided.locator(".lf-threads-toggle").click()
            for wid in decided_here:
                shown = undecided.locator(f"#{wid}")
                card = undecided.locator(".lf-thread").filter(has=shown)
                if card.get_attribute("open") is None:
                    card.locator(".lf-thread-summary").click()
                expect(shown).to_be_visible()
                assert shown.inner_text() != read_as[wid], (
                    f"{example.stem}: #{wid} reads the same with the log's decision "
                    f"and without it ({read_as[wid]!r}) — the seed proves nothing"
                )
            undecided.close()

    assert drawn, (
        "no shipped log carries a widget in a message. That is the other place "
        "markup renders, no authored page can stand in for it, and with none in "
        "the corpus this is the whole of what reads one."
    )
    assert decided, (
        "no shipped log carries a decision on a widget a message carries. The "
        "question is seeded and the answer is not, so every sweep reads that "
        "widget untouched and nothing here exercises the panel's own fold."
    )
    assert replied, (
        "no shipped log carries an agent reply, so no example exercises the live "
        "thread exchange that authored markup cannot represent"
    )


@pytest.mark.parametrize("source", ANCHOR_SOURCES, ids=lambda p: p.stem)
def test_an_anchor_written_from_the_mapped_revision_lands_on_the_page(
    browser, serve, source
):
    """The claim `leaf thread open` makes is that a quote read out of the mapped revision
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

    # The runtime's own record of which threads it found a home for.
    detached = page.eval_on_selector_all(
        ".lf-thread .lf-quote.detached", "els => els.map(e => e.textContent)"
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


def test_a_reply_notice_survives_a_failed_state_and_keeps_its_agent(browser, serve):
    """A failed candidate owns neither the agent name nor the reply count.

    The first read reaches panel and version rendering before malformed projection data
    rejects it. That candidate must announce nothing and leave no version behind; a
    complete retry announces the reply once with the agent recorded on the message.
    The rejected reply must also leave the visible thread until that retry.
    """
    url = serve(TWIN_V1)
    d = serve.page_dir
    root = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "which host answers?",
        },
    )
    page = open_page(browser, live_url(url))
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 1")
    stamp_page(d, TWIN_V2, "a twin")
    wait_for_revision(page, 2)
    expect(page.locator(".lf-notice")).not_to_have_class(re.compile(r"\bshow\b"))

    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-summary").first.click()
    reply_draft = page.locator(".lf-thread leaf-text")
    write(reply_draft, "keep this unfinished reply")
    page.locator(".lf-threads-toggle").click()

    broken = []

    def fail_after_rendering_the_panel(route):
        if broken:
            refuse(route)
            return
        response = route.fetch()
        state = response.json()
        state["agent"] = "Rejected agent"
        rejected_version = {
            **state["versions"][-1],
            "version": state["versions"][-1]["version"] + 100,
        }
        state["versions"].append(rejected_version)
        state["browser"].setdefault("version_notes", {})[
            str(rejected_version["version"])
        ] = "Rejected version"
        view = state["browser"]["views"][str(state["active"]["revision"])]
        view["document"]["projection"]["entries"].append(None)
        broken.append(True)
        route.fulfill(status=response.status, json=state)

    page.route("**/api/state*", fail_after_rendering_the_panel)
    with page.expect_console_message(
        lambda message: "read failed" in message.text
    ) as fault:
        append_carried_log_record(
            d,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": root["id"],
                "text": "this one does",
            },
        )
    assert (
        page.evaluate(
            "async () => (await window.__lfRuntimeImport('/runtime/context.js')).runtime.state.agent"
        )
        == "Agent"
    )
    assert fault.value.text in page.lf_errors
    page.lf_errors.remove(fault.value.text)

    expect(page.locator(".lf-msg.agent .lf-msg-body")).to_have_count(0)
    expect(page.locator(".lf-msg.user .lf-msg-body")).to_have_text(
        "which host answers?"
    )
    expect(reply_draft).to_have_js_property("value", "keep this unfinished reply")

    version_menu = page.locator(".lf-version-menu")
    banner_control(page, ".lf-version").click()
    expect(version_menu).not_to_contain_text("Rejected version")
    page.keyboard.press("Escape")

    notice_el = page.locator(".lf-notice")
    assert "show" not in notice_el.get_attribute("class").split()
    page.wait_for_timeout(100)
    assert "Codex replied" not in page.locator(".lf-live").text_content()

    page.unroute("**/api/state*")
    nudge(d)
    told(page)
    expect(notice_el).to_have_text("Codex replied")
    expect(notice_el).to_have_class(re.compile(r"\bshow\b"))
    expect(page.locator(".lf-msg.agent .lf-msg-body")).to_have_text("this one does")


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
<lf-roomy id="roomy"><section>One</section><section>Two</section></lf-roomy>
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
          el.append(probe);
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
<aside class="sidebar">
  <p>Reference</p><p>Supporting information</p><p>Helpful link</p>
  <p>Further notes</p><p>Useful actions</p>
</aside>
<h1 id="t">Available package surface</h1>
<lf-roomy id="roomy"><section>One</section><section>Two</section></lf-roomy>
""",
    )
    page = open_page(browser, serve(source, layer_registry={"lf-roomy": entry}))
    resized(page, 1726, 900)
    at = page.evaluate("""() => {
      const sidebar = document.querySelector('aside.sidebar').getBoundingClientRect();
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


def test_named_wide_is_the_evidence_width_in_every_layout(browser, serve):
    """`wide` is the shared capped evidence width wherever a block stands. A sidebar
    page's body and a workspace pane are wider than `--wide` at a large window, so the
    breakout's growth alone left a named-wide block at the holder's width there: 1442px
    in a pane at 1726px. The cap holds an authored
    occurrence and a package default (a board) alike, at the page's own `--wide`, while
    a block that names no width still fills its holder and `available` takes it all. A
    narrow window's pane still bounds the wide block."""
    blocks = """
<div id="named" data-width="wide">Named wide.</div>
<lf-board id="board">
<lf-column id="todo" label="Todo"><lf-card id="card">One</lf-card></lf-column>
<lf-column id="two" label="Two"></lf-column><lf-column id="three" label="Three"></lf-column>
<lf-column id="four" label="Four"></lf-column><lf-column id="five" label="Five"></lf-column>
<lf-column id="six" label="Six"></lf-column>
</lf-board>
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
      ['named', 'board', 'plain', 'available'].map(id => {
        const box = document.getElementById(id).getBoundingClientRect();
        return [id, {width: Math.round(box.width), left: Math.round(box.left)}];
      }))"""
    for source, cap in (
        (sidebar_page, 1080),
        (workspace_page, 1080),
        (configured, 900),
    ):
        page = open_page(browser, serve(source))
        resized(page, 1726, 900)
        at = page.evaluate(measure)
        assert at["plain"]["width"] > cap + 200, at
        assert at["available"]["width"] == at["plain"]["width"], at
        for capped in ("named", "board"):
            assert at[capped]["width"] == pytest.approx(cap, abs=1), (capped, at)
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

    It reads a resident by the same test the pass above excuses one by — placed
    absolutely or fixed, or floated clear of the column — so this needs no vocabulary
    of its own and nothing has to be declared to it. That is what keeps the two theme
    rules honest: the next claimant that forgets one is a refusal with a name on it
    rather than a page somebody eventually notices is drawn over its own controls.

    The page's own frame is the same place: a wide widget is measured against the box
    that frames it, and everything else on the page is excused by a scroll container
    above it. Asked in that order, the excuse ate the measurement: a board scrolls, so
    every card on every board was excused from the one reading that applies to what it
    holds, and a diagram drawn 332px across the next column passed the gate that
    exists to name it. So a board in a frame of the page's own that scrolls is named
    too."""
    framed = FRAMED_SCROLLER_PAGE[FRAMED_SCROLLER_PAGE.index("<div id='own-frame'") :]
    framed = framed[: framed.index("</lf-board></div>") + len("</lf-board></div>")]
    failures = render_gate_model.render_version(
        browser, serve(OWN_MARGIN_FURNITURE.replace("</main>", framed + "</main>"))
    ).failures

    assert [
        f
        for f in failures
        if f.code == "over-margin"
        and f.at == "<lf-board id=sprint>"
        and f.values["resident"] == "<div id=own-rail>"
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


def test_a_left_sidebar_uses_the_margin_until_the_page_needs_it_back(browser, serve):
    """The sidebar is a page-level margin resident rather than a narrower prose column.

    On a roomy page a contents map stands in the left margin, fixed below the banner, and
    rests as its spine: it claims nothing, so the column keeps the page's axis, and its
    labels reveal over the page without moving anything. The spine states the room it
    takes, so the release-notes shot, the wide exhibit in the control, grows left only
    to stop short of it.

    The Questions panel stands over the page from the right and moves nothing in the left
    margin. A narrow viewport returns the aside to the flow, and print proves paper
    reserves no blank margin for a posture it cannot use.

    A sidebar that holds only the map has nothing for a float to hold, so wherever the
    map stands in the margin that sidebar stands as the map alone and takes no room in
    the flow: the block after it stands where it would with the sidebar gone."""
    # Compose the wide release-note exhibit with a sidebar holding the map and a line of
    # its own; the short public draft no longer needs one of its own.
    release = next(p for p in EXAMPLES if p.stem == "release-notes").read_text()

    def with_sidebar(holds):
        return release.replace(
            '<section id="rn-cli-section">',
            f'<aside class="sidebar" id="test-sidebar">{holds}'
            '<lf-toc id="test-sidebar-toc"></lf-toc></aside>'
            '<section id="rn-cli-section">',
        )

    example = with_sidebar('<p id="test-sidebar-release">Release 4.2</p>')
    page = open_page(browser, serve(example))
    sidebar = page.locator("aside.sidebar")

    reading = """() => {
      const sidebar = document.querySelector('aside.sidebar');
      const main = document.querySelector('main');
      const exhibit = document.querySelector('lf-shot');
      const ms = getComputedStyle(main), ss = getComputedStyle(sidebar);
      const mb = main.getBoundingClientRect(), sb = sidebar.getBoundingClientRect();
      const eb = exhibit.getBoundingClientRect();
      const toc = document.querySelector('lf-toc').getBoundingClientRect();
      const nav = document.querySelector('lf-toc .lf-toc-nav').getBoundingClientRect();
      const marginClusters = [...document.querySelectorAll('.lf-margin-cluster')]
        .filter(node => node.checkVisibility());
      const marginRight = Math.max(0,
        ...marginClusters.map(node => node.getBoundingClientRect().right));
      const measure = (value) => {
        const probe = document.createElement('i');
        probe.style.cssText = 'position:fixed;left:0;top:0;visibility:hidden;height:0;padding:0;border:0;width:'
          + value;
        main.append(probe);
        const width = probe.getBoundingClientRect().width;
        probe.remove();
        return width;
      };
      return {
        taken: measure('var(--lf-taken-l, 0px)'), pageWidth: measure('100cqi'),
        float: ss.float, position: ss.position,
        sidebar: {left: sb.left, right: sb.right, top: sb.top, width: sb.width},
        toc: {left: toc.left, right: toc.right, width: toc.width},
        nav: {left: nav.left, right: nav.right, width: nav.width},
        column: {
          left: mb.left + parseFloat(ms.paddingLeft),
          right: mb.right - parseFloat(ms.paddingRight),
        },
        marginCount: marginClusters.length, marginRight,
        document: {
          width: document.documentElement.scrollWidth,
          height: document.documentElement.scrollHeight,
        },
        viewportWidth: document.documentElement.clientWidth,
        exhibit: {left: eb.left, right: eb.right},
      };
    }"""
    resized(page, 1400, 900)
    margins_laid_out(page)
    roomy = page.evaluate(reading)
    # At rest the map is its spine: it takes a strip of the margin, not its labels' width.
    assert 0 < roomy["taken"] < roomy["toc"]["width"], roomy
    assert roomy["float"] == "left" and roomy["position"] == "sticky"
    assert roomy["sidebar"]["right"] <= roomy["column"]["left"] - 23, (
        f"the sidebar's box reached into the reading column: {roomy}"
    )
    assert (
        abs(
            (roomy["column"]["left"] + roomy["column"]["right"]) / 2
            - roomy["pageWidth"] / 2
        )
        <= 1
    ), f"the contents map moved the reading column off the page's axis: {roomy}"
    assert roomy["toc"]["width"] == 320
    assert roomy["exhibit"]["left"] >= roomy["toc"]["left"] + roomy["taken"] - 1, (
        f"a wide exhibit painted over the contents map's spine: {roomy}"
    )
    assert root_overflow(page) == 0

    # The real pointer route reveals labels inside the map's settled rectangle. Its
    # complete reservation and every unrelated box remain fixed under the user's aim.
    # At rest the map takes the pointer on its spine alone.
    nav_box = page.locator("lf-toc .lf-toc-nav").bounding_box()
    page.mouse.move(nav_box["x"] + 2, nav_box["y"] + nav_box["height"] / 2)
    page.wait_for_function(
        "() => Number(getComputedStyle(document.querySelector('lf-toc a')).opacity) === 1"
    )
    expanded = page.evaluate(reading)
    assert expanded["taken"] == roomy["taken"]
    assert expanded["toc"]["width"] == 320
    assert expanded["nav"]["width"] == 320
    assert expanded["column"] == roomy["column"]
    assert expanded["exhibit"] == roomy["exhibit"]
    assert expanded["document"] == roomy["document"]
    page.locator("h1").hover()
    page.wait_for_function(
        "() => Number(getComputedStyle(document.querySelector('lf-toc a')).opacity) === 0"
    )
    page.keyboard.press("g")
    expect(page.locator("body")).to_have_attribute("data-lf-go-to-active", "")
    page.wait_for_function(
        "() => Number(getComputedStyle(document.querySelector('lf-toc a')).opacity) === 1"
    )
    revealed_by_keyboard = page.evaluate(reading)
    assert revealed_by_keyboard["column"] == roomy["column"]
    assert revealed_by_keyboard["exhibit"] == roomy["exhibit"]
    assert revealed_by_keyboard["document"] == roomy["document"]
    page.keyboard.press("Escape")
    expect(page.locator("body")).not_to_have_attribute("data-lf-go-to-active", "")
    page.wait_for_function(
        "() => Number(getComputedStyle(document.querySelector('lf-toc a')).opacity) === 0"
    )

    # The Questions panel stands over the page from the right and moves nothing in the left
    # margin: the fixed ToC and the sidebar stay where the page put them while it stands.
    resized(page, 1700, 900)
    margin = """() => {
          const sidebar = document.querySelector('aside.sidebar').getBoundingClientRect();
          const toc = document.querySelector('lf-toc .lf-toc-nav').getBoundingClientRect();
          return {sidebarLeft: sidebar.left, tocLeft: toc.left};
        }"""
    before = page.evaluate(margin)
    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_be_visible()
    page.wait_for_function(
        """() => document.querySelector('.lf-queue-panel').getAnimations().length === 0"""
    )
    assert page.evaluate(margin) == before
    geometry = page.evaluate(
        """() => {
          const sidebar = document.querySelector('aside.sidebar').getBoundingClientRect();
          const toc = document.querySelector('lf-toc .lf-toc-nav').getBoundingClientRect();
          const line = document.querySelector('.lf-shortcut-bar').getBoundingClientRect();
          return {sidebarLeft: sidebar.left, tocLeft: toc.left,
                  tocTop: toc.top, tocBottom: toc.bottom, lineTop: line.top,
                  sidebarPosition: getComputedStyle(document.querySelector('aside.sidebar')).position,
                  tocPosition: getComputedStyle(document.querySelector('lf-toc')).position};
        }"""
    )
    assert geometry["sidebarPosition"] == "sticky"
    assert geometry["tocPosition"] == "fixed"
    assert 64 <= geometry["tocTop"] <= 68
    # The map ends above the bottom bar, as every region does: its foot is the window's
    # less the band and the map's own inset, so the keyboard's line never covers its last
    # entry.
    assert abs(geometry["tocBottom"] - (geometry["lineTop"] - 24)) <= 1, (
        f"the map's foot is not the band's top less its inset: {geometry}"
    )
    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_be_hidden()

    resized(page, 1400, 900)

    # Halfway through the stretch where the box stands on its own offset: past the
    # scroll that lifts it off where it was authored, and short of the one where main's
    # own end starts carrying it back up. Both edges are the page's, so they are read
    # off it — a named scroll fell past the far one when the release page grew shorter.
    parked = page.evaluate(
        """() => {
          const scroller = document.scrollingElement;
          scroller.style.scrollBehavior = 'auto';
          const sidebar = document.querySelector('aside.sidebar');
          const main = sidebar.parentElement;
          const box = sidebar.getBoundingClientRect();
          const style = getComputedStyle(sidebar);
          const offset = parseFloat(style.top);
          const stands = scroller.scrollTop + box.top - offset;
          const carried = scroller.scrollTop + main.getBoundingClientRect().bottom
            - parseFloat(getComputedStyle(main).paddingBottom)
            - parseFloat(style.marginBottom) - box.height - offset;
          const lastScroll = scroller.scrollHeight - scroller.clientHeight;
          const at = Math.round((stands + Math.min(carried, lastScroll)) / 2);
          scroller.scrollTo(0, at);
          return { at, stands, carried, lastScroll };
        }"""
    )
    # The stretch has to exist before a point halfway along it says anything. A page
    # too short to lift the box off where it was authored parks the scroll behind
    # `stands`, and the ring assertion below would then report a position rather than
    # the page that made it meaningless.
    assert min(parked["carried"], parked["lastScroll"]) > parked["stands"], (
        f"the page is too short for the sidebar to stand on its own offset: {parked}"
    )
    page.wait_for_function(
        "at => document.scrollingElement.scrollTop >= at - 1", arg=parked["at"]
    )
    stuck = sidebar.evaluate("node => node.getBoundingClientRect().top")
    assert 64 <= stuck <= 68, (
        f"the sidebar stuck at {stuck:.0f}px, not below the banner"
    )

    page.close()

    page = open_page(browser, serve(with_sidebar("")))
    for width in (1100, 1400):
        resized(page, width, 900)
        margins_laid_out(page)
        band = page.evaluate(
            """() => lfUnwatched(() => {
              const sidebar = document.querySelector('aside.sidebar');
              const next = sidebar.nextElementSibling;
              const kept = next.getBoundingClientRect().top;
              sidebar.style.display = 'none';
              const gone = next.getBoundingClientRect().top;
              sidebar.style.display = '';
              return {kept, gone, float: getComputedStyle(sidebar).float,
                      toc: getComputedStyle(sidebar.querySelector('lf-toc')).position};
            })"""
        )
        assert band["toc"] == "fixed" and band["float"] == "none", (width, band)
        assert band["kept"] == band["gone"], (
            f"at {width}px the sidebar the map left opened a gap in the flow: {band}"
        )
    page.close()

    page = open_page(browser, serve(example))
    resized(page, 700, 900)
    narrow = page.evaluate(reading)
    assert narrow["taken"] == 0
    assert narrow["float"] == "none" and narrow["position"] == "static"
    assert abs(narrow["sidebar"]["left"] - narrow["column"]["left"]) <= 1
    assert root_overflow(page) == 0

    resized(page, 1400, 900)
    page.emulate_media(media="print")
    printed = page.evaluate(reading)
    assert printed["taken"] == 0
    assert printed["float"] == "none" and printed["position"] == "static"
    assert abs(printed["sidebar"]["left"] - printed["column"]["left"]) <= 1


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


def test_margin_residency_ignores_concealed_ancestors(browser, serve):
    """An own hidden note can reserve a margin, but skipped ancestors cannot."""
    cases = [
        (
            '<details><summary>More</summary><aside class="sidenote" style="display:none">Concealed note.</aside></details>',
            False,
        ),
        (
            '<div style="content-visibility:hidden"><aside class="sidenote" style="display:none">Skipped note.</aside></div>',
            False,
        ),
        (
            '<div style="display:none"><aside class="sidenote">Concealed note.</aside></div>',
            False,
        ),
        (
            '<div style="display:contents"><aside class="sidenote">Visible note.</aside></div>',
            True,
        ),
        ('<aside class="sidenote" style="display:none">Own hidden note.</aside>', True),
        (
            '<aside class="sidenote" style="display:contents">Boxless note.</aside>',
            False,
        ),
    ]
    for contents, admitted in cases:
        source = leaf_page(
            "Concealed residents",
            "<h1>Migration</h1>" + contents + "<p>Advance one cohort at a time.</p>",
        )
        page = open_page(browser, serve(source))
        resized(page, 1440, 900)
        assert (
            "note"
            in (page.locator("main").get_attribute("data-lf-margin") or "").split()
        ) is admitted
