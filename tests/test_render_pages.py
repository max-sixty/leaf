"""File-authored anchors, drawings, width, and handover tests."""

import json
import re

import pytest
from click.testing import CliRunner
from leaf import cli as cli_model
from leaf import events as events_model
from leaf import registry as registry_model
from leaf import render_checks as render_checks_model
from leaf import rendering as rendering_model
from leaf import schema as schema_model
from leaf import structure as structure_model
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_support import (
    AT_THE_HANDOVER,
    BOTH_STAMPS,
    BROKEN_DIAGRAM_PAGE,
    CHROME_ROOM,
    DIAGRAM_AND_RAIL_PAGE,
    DIAGRAM_ROOM,
    DRAWING_PLACEMENT,
    DRAWN_PAST_A_RAIL_PAGE,
    EXAMPLES,
    FRAMED_SCROLLER_PAGE,
    FRAMED_WIDE_PAGE,
    INLINE_PAGE,
    INLINE_REPLY_MARKUP,
    LATE_MARGIN_PAGE,
    LATE_MARGIN_WIDGET,
    LONG_PAGE,
    NOTE_AND_WIDE_PAGE,
    NOTE_BAND,
    OWN_MARGIN_FURNITURE,
    PICTURE_PAGE,
    RAIL_AND_WIDE_PAGE,
    RAIL_BAND_PAGE,
    RAIL_BANDS,
    RAIL_FIT,
    REPLY_HOST_PAGE,
    ROOM_GEOMETRY,
    TOKEN,
    TWIN_V1,
    TWIN_V2,
    WIDE_AND_NARROW_PAGE,
    WIDE_DIAGRAM_PAGE,
    author_test_widget,
    composer_quote,
    leaf_page,
    open_page,
    page_registry,
    panel_settled,
    record_claim,
    resized,
    told,
    watched,
    written_anchors,
)

pytestmark = pytest.mark.nightly


def test_a_shipped_log_opens_its_example_on_a_live_thread(browser, serve):
    """An example that ships a companion log opens mid-conversation.

    A thread is the one thing the corpus could not hold: it is log state, no markup
    describes one, and `version export` drops the layer that draws it — so a static
    copy cannot carry a thread however it is written, and for a long time nothing
    under examples/ showed the comment loop at all. What an example *can* ship is
    the log itself, beside it, exactly as one that wants a screenshot ships the
    bytes beside it. `scripts/preview.py <example>` is then a page that opens on a
    real exchange rather than an empty panel.

    The anchor in that log is the part that can rot quietly. It is captured from
    the version file, and it has to name the same passage once the browser has
    built the page; a rewritten sentence leaves the quote resolving to nothing and
    the thread standing there detached, which is a broken demo and no error
    anywhere. The corpus's own anchor sweep does not cover it, because that sweep
    writes its own anchors. This is what reads the shipped one.

    A log can also carry a widget, and that is the second thing read here. Markup
    in a message renders in the panel and nowhere else, so no authored page can
    stand in for it — which is exactly how it stayed unrendered: every example's
    widgets are authored into <main>, and a module that never reached a message
    would have left all eight corpus sweeps green.

    The third is what the reader did to one. A decision on such a widget is folded
    through a projection of its own and replayed into a tree the panel built, and a
    seed carrying the question but not the answer reads only the untouched half —
    which is the same gap as the widget's, one turn further in. It is read against
    the neighbour that separates a replay from a rendering: the same page, the same
    log with the decisions removed. A widget that says the same either way was never
    reached, and every assertion above this one passes just the same.

    Looped rather than parametrized so an empty corpus fails here instead of
    collecting no tests and reporting green."""
    seeded = [p for p in EXAMPLES if p.with_suffix(".jsonl").exists()]
    assert seeded, "no example ships a log; this gate is reading nothing"
    drawn = []
    decided = []
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
        assert len(events) >= 2, f"{example.stem}: a thread is a comment and a reply"

        page, errors = open_page(browser, url)
        # A reaction nobody has answered is a mark and not a thread: its anchor paints
        # through its own registry entry and a glyph seated at its block, and it takes
        # no card. Split here so each half is read against the paint it owes.
        answered = {e["parent"] for e in events if e.get("parent")}
        reacted = [
            e
            for e in events
            if e["kind"] == "comment" and e.get("token") and e["id"] not in answered
        ]
        anchored = [e for e in events if e.get("anchor") and e not in reacted]
        # The thread node first, because it arrives whether or not the quote found a
        # home — a stranded one renders wearing `detached`. Waiting on the mark here
        # instead spends the whole timeout on exactly the failure this gate is for
        # and then reports it as "wait_for_function timed out", which says nothing
        # about the anchor.
        # Every comment with words opens a thread; an anchor only decides whether it
        # also paints a mark. Counting threads against the anchored ones would red
        # this gate the day a seed carries a general comment, which is a thing a page
        # may hold.
        expect(page.locator(".lf-thread")).to_have_count(
            len([e for e in events if e["kind"] == "comment" and not e.get("token")])
        )
        for reaction in reacted:
            glyph = page.locator(
                f'.lf-reacts > .lf-react-mark[data-event="{reaction["id"]}"]'
            )
            expect(glyph).to_be_visible()
            expect(glyph.locator("..")).to_have_attribute(
                "data-lf-for", reaction["anchor"]["section"]
            )
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
        detached = page.eval_on_selector_all(
            ".lf-thread .lf-quote.detached", "els => els.map(e => e.textContent)"
        )
        assert detached == [], (
            f"{example.stem} ships an anchor that resolves to nothing: {detached}. "
            "The passage it quotes has been rewritten; recapture it with "
            "`leaf comment --quote` against the current file."
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
        # shape the corpus otherwise never shows. The class is what the reader
        # follows and what the ring is drawn on, so it is what is read here.
        for event in anchored:
            if event in quoted:
                continue
            section = event["anchor"]["section"]
            expect(page.locator(f"#{section}.lf-mark-el")).to_have_count(1)
        # The exchange is both voices, and the mark is on the words the log named.
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
        expect(page.locator(".lf-thread .lf-msg.claude")).not_to_have_count(0)

        # The other thing a log carries. A widget can arrive as a message's markup
        # rather than as authored page content, and it draws in the body the panel
        # builds — so its module has to reach a tree the runtime made, in a column
        # narrower than the document's. Every example's own widgets stand in
        # <main>, which is why the eight sweeps could all be green while nothing
        # had rendered one here. It needs the panel open: shut, the fragment is in
        # the DOM with no box at all, so a reading that walks text nodes sees it
        # and every reading that measures one does not.
        page.locator(".lf-comments").click()
        registry = registry_model.load_registry(serve.page_dir)
        carried_ids = set()
        for carried in [e for e in events if e.get("markup")]:
            for wid, rec in structure_model.parse_structure(
                carried["markup"]
            ).by_id.items():
                drawn.append(wid)
                carried_ids.add(wid)
                shown = page.locator(f"#{wid}")
                expect(shown).to_be_visible()
                # Where the registry says the element holds a request for the
                # reader, whatever answers it has to have been built here too:
                # data-lf-offer is the runtime's own mark for a thing to work, so
                # this asks the declaration and never the tag.
                if registry[rec["tag"]].get("x-awaits"):
                    expect(shown.locator("[data-lf-offer]")).not_to_have_count(0)

        # The panel is open, which is the only state in which a widget a message
        # carries has a box at all — so this is where the gate's own geometry readings
        # can be put to one. They cannot be put there by the gate: `version check
        # --render` is pointed at a version file and never opens the panel, and a fault
        # in a frozen fragment is not one the version's author could edit away, so a
        # finding there would red their handover for good. The readings are the
        # product's own rather than test-side copies, for the reason tests/CLAUDE.md
        # gives: a variant here would drift from what the gate actually refuses.
        # The two gate readings that a widget in a message escapes only because the
        # panel is shut — both stop at `checkVisibility()`, and a message body in a
        # shut panel has no boxes at all. Every other geometry reading passes over the
        # panel structurally, by `.lf-chrome` or by starting at `main`, and stays
        # passed over. The gate cannot make up the difference: it is pointed at a
        # version file and never opens the panel, and a fault in markup frozen in the
        # log is not one that version's author could edit away — a finding there would
        # red their handover with no edit that clears it. Here the panel is open,
        # which is the one state in which such a widget has a box to be wrong about.
        #
        # The product's own readings, not test-side copies, and the population is
        # asserted first: a widget with no controls in it would make both come back
        # clean for having been handed nothing.
        offers = page.evaluate(
            """(ids) => ids.flatMap((id) => {
                 const el = document.getElementById(id);
                 return el ? [...el.querySelectorAll('[data-lf-offer]')] : [];
               }).length""",
            sorted(carried_ids),
        )
        assert offers, (
            f"{example.stem}: no widget a message carries built a control, so the two "
            "readings below were handed nothing of the panel's to look at"
        )
        for name, reading, arg in (
            (
                "draws a box of no size",
                render_checks_model.TINY_BOXES,
                page_registry(page),
            ),
            (
                "has a control clipped out of its box",
                render_checks_model.CLIPPED_CONTROLS,
                None,
            ),
        ):
            found = page.evaluate(reading, arg) if arg else page.evaluate(reading)
            assert found == [], (
                f"{example.stem}: with the panel open, something {name}: {found}"
            )

        # And the third thing a log carries: what the reader did to one of those
        # widgets. A decision on a widget a message carries is folded from thread
        # markup rather than from the version, through a projection of its own
        # (`thread_state`), and replayed into a tree the panel built — so a corpus
        # that seeds the question and not the answer reads the untouched half of
        # every such widget and leaves the whole standing-decision route to
        # unit-style fixtures. The seed is what puts it under the sweeps.
        decided_here = [
            e["widget"]
            for e in events
            if e["kind"] == "action" and e["widget"] in carried_ids
        ]
        # Named among what the runtime hands the render gate, which is where a
        # standing winner has to appear for the gate to reapply it at all. Read once:
        # the fold is the whole log's, not one widget's.
        standing = page.evaluate(
            "async () => (await import('/runtime/widget-api.js')).standingState().map((s) => s.unit)"
        )
        for wid in decided_here:
            decided.append(wid)
            assert wid in standing, (
                f"{example.stem}: the log decides #{wid} and the runtime's standing "
                f"state names only {standing} — the panel's fold reached the gate for "
                "nothing the reader did"
            )
            read_as[wid] = page.locator(f"#{wid}").inner_text()
        assert errors == []
        page.close()

        # The single-factor neighbour: the same page under the same log with the
        # decisions taken out. A widget that reads the same either way is one the
        # replay never reached, and every assertion above it would still pass —
        # a drawn widget and a built control say nothing about whose state is on it.
        if decided_here:
            plain = serve(example.read_text())
            for event in [e for e in events if e["kind"] != "action"]:
                events_model.append_event(serve.page_dir, event)
            undecided, errors = open_page(browser, plain)
            undecided.locator(".lf-comments").click()
            for wid in decided_here:
                shown = undecided.locator(f"#{wid}")
                expect(shown).to_be_visible()
                assert shown.inner_text() != read_as[wid], (
                    f"{example.stem}: #{wid} reads the same with the log's decision "
                    f"and without it ({read_as[wid]!r}) — the seed proves nothing"
                )
            assert errors == []
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


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_an_anchor_written_from_the_file_lands_on_the_page(browser, serve, example):
    """The claim `leaf comment` makes is that a quote read out of the version file
    names the same passage in the browser. Checked on the pages people actually write,
    because the ways it can fail are all theirs: a diagram that renders to a picture, an
    attribute the runtime turns into text, two paragraphs whose join is a space in one
    reading and nothing in the other."""
    # The markup rather than the example, so a shipped log stays out. This sweep
    # writes its own anchors and then compares the whole painted mark against
    # exactly those quotes; a seeded thread paints into the same highlight and
    # every example that ever ships one would read as painting text it does not
    # name. The seeded anchor has its own reader in
    # test_a_shipped_log_opens_its_example_on_a_live_thread.
    html = example.read_text()
    url = serve(html)
    d = serve.page_dir
    anchors = written_anchors(d, html)
    assert len(anchors) >= 10, (
        f"only {len(anchors)} anchors over {example.stem}; sweep too thin"
    )
    for i, (_, anchor) in enumerate(anchors):
        events_model.append_event(
            d,
            {
                "kind": "comment",
                "author": "claude",
                "version": 1,
                "id": f"written{i}",
                "anchor": anchor,
                "text": f"note {i}",
            },
        )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    # The runtime's own record of which threads it found a home for.
    detached = page.eval_on_selector_all(
        ".lf-thread .lf-quote.detached", "els => els.map(e => e.textContent)"
    )
    assert detached == [], (
        f"{len(detached)} anchors resolved to nothing in {example.stem}: {detached}"
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
    assert painted == wanted, f"anchors in {example.stem} painted text they don't name"
    assert errors == []
    page.close()


def test_a_written_anchor_keeps_its_copy_when_the_page_grows_another(browser, serve):
    """A quote unique when it was written is not unique forever. The neighbours a written
    anchor stores are what hold it on the passage it was made about — without them the
    search takes the first copy, and a comment ends up on words nobody wrote it about."""
    url = serve(TWIN_V1)
    d = serve.page_dir
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "comment",
            str(d),
            "--quote",
            "The version stamp never lands",
            "--text",
            "capped where?",
        ],
    )
    assert result.exit_code == 0, result.output
    anchor = json.loads(result.output)["anchor"]
    assert anchor["prefix"] and anchor["suffix"], (
        f"nothing stored to tell copies apart: {anchor}"
    )

    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    (d / "versions" / "v2.html").write_text(TWIN_V2)
    events_model.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "a twin"}
    )
    page.wait_for_url("**/v2.html")
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    where = page.evaluate(
        "() => [...CSS.highlights.get('lf-mark')][0].startContainer.parentElement.id"
    )
    assert where == "p-original", f"the new copy took the comment ({where})"
    assert errors == []
    page.close()


def test_a_written_comment_keeps_its_originating_agent(browser, serve, monkeypatch):
    """An agent's side of a thread is the user's side with the author flipped.
    Its label belongs to the message — the poster's own environment stamps it as
    the comment is written — so another host claiming the page later cannot
    rewrite who said it."""
    url = serve(TWIN_V1)
    d = serve.page_dir
    monkeypatch.setenv("LEAF_SESSION_ID", "codex")
    monkeypatch.setenv("LEAF_AGENT", "Codex")
    assert (
        CliRunner()
        .invoke(
            cli_model.cli,
            [
                "comment",
                str(d),
                "--quote",
                "Retries are capped at three",
                "--text",
                "is three right?",
            ],
        )
        .exit_code
        == 0
    )
    record_claim(d, id="claude")
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    toggle = page.locator(".lf-comments")
    expect(toggle).to_have_text(
        "Comments (1)"
    )  # counted as open, like any other thread
    toggle.click()
    thread = page.locator(".lf-thread").first
    expect(thread.locator(".lf-msg.claude .lf-msg-head b")).to_have_text("Codex")
    expect(thread.locator(".lf-quote")).to_have_text("“Retries are capped at three”")

    thread.locator("textarea").fill("three is the retry budget, not a guess")
    thread.get_by_role("button", name="Send", exact=True).click()
    expect(page.locator(".lf-msg.user")).to_have_count(1)
    page.locator(".lf-thread").first.get_by_role("button", name="Resolve").click()
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")

    kinds = [(e["kind"], e.get("author")) for e in events_model.read_events(d)]
    assert ("comment", "claude") in kinds
    assert ("reply", "user") in kinds and ("resolve", "user") in kinds
    assert errors == []
    page.close()


def test_a_reply_toast_keeps_its_originating_agent(browser, serve):
    url = serve(TWIN_V1)
    d = serve.page_dir
    root = events_model.append_event(
        d,
        {
            "kind": "comment",
            "author": "user",
            "version": 1,
            "text": "which host answers?",
        },
    )
    record_claim(d, id="claude")
    page, errors = open_page(browser, url)
    expect(page.locator(".lf-comments")).to_have_text("Comments (1)")

    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Codex",
            "parent": root["id"],
            "text": "this one does",
        },
    )
    told(page)
    expect(page.locator(".lf-toast")).to_have_text("Codex replied — open Comments")
    assert errors == []
    page.close()


def test_a_widget_declaring_it_renders_a_picture_takes_a_click(browser, serve):
    """A rendering has no text of the page's in it to select, so the click anchors on the
    whole element. Which widgets those are is theirs to declare (x-visual): the runtime
    names none of them, so a widget added to the vocabulary is clickable on the strength
    of its entry — the failure this rules out is the quiet one, where a consumer taught
    one widget by name keeps working on that widget and does nothing for the next."""
    url = serve(PICTURE_PAGE)
    registry = json.loads((serve.page_dir / "registry.json").read_text())
    assert registry["lf-diagram"]["x-visual"], "this test needs the shipped declaration"
    registry["lf-tree"]["x-visual"] = True  # a widget the runtime has never heard of
    (serve.page_dir / "registry.json").write_text(json.dumps(registry))
    page, errors = open_page(browser, url)

    # The inner svg is mermaid's, carrying a generated id; the anchor belongs to the
    # widget that holds it, which is the element the page gave a name.
    page.locator("#flow svg").click()
    page.locator(".lf-fab").click()
    page.locator("#flow.lf-mark-el.lf-pending").wait_for()
    assert not composer_quote(page)["shown"], "a picture has no words to quote back"
    page.get_by_role("button", name="Cancel").click()

    page.locator("#tree").click()
    page.locator(".lf-fab").click()
    page.locator("#tree.lf-mark-el.lf-pending").wait_for()
    page.get_by_role("button", name="Cancel").click()

    # And a paragraph is still text: the click reaches no picture and raises nothing.
    page.locator("#p").click()
    expect(
        page.locator(".lf-fab"), "a click on prose was read as a click on a picture"
    ).not_to_be_visible()
    assert errors == []
    page.close()


def test_a_diagram_follows_the_scheme_it_is_read_in(browser, serve):
    """The SVG's principal surfaces are written back as var() over the tokens they
    were seeded from (retheme), so a scheme flip repaints them with the rest of the
    page and a copy exported in a light browser opens honestly for a dark reader —
    each used to keep the palette it was rendered under, a light slab in a dark
    page. Only colors mermaid derives from the seeds itself stay frozen, and no
    principal surface is one."""
    page, errors = open_page(browser, serve(WIDE_DIAGRAM_PAGE))
    node = page.locator("#flow svg .node rect").first
    expect(node).to_be_visible()
    fill = "el => getComputedStyle(el).fill"
    light = node.evaluate(fill)
    page.emulate_media(color_scheme="dark")
    assert node.evaluate(fill) != light, (
        "a diagram's node surface must follow the page's scheme"
    )
    assert errors == []
    page.close()


def test_a_diagram_takes_the_room_and_scrolls_only_past_it(browser, serve):
    """Mermaid fits a diagram to its holder by scaling the whole drawing down, glyphs
    included — this flowchart rendered at 63% in the column, its 16px labels
    effectively 10px and unreadable. The module strips that, so the drawing keeps the
    size mermaid laid it out at and what is in question is only how much of it shows.

    Which is the whole of it wherever the window has the room. A drawing is not a box
    that fills whatever it is given, so the one width the vocabulary shares is no promise
    about it: held to that number, this 1147px flowchart was cut off at 1080 on a window
    with 470px to spare. The board on the
    same page is the half that says the declaration is doing this rather than the tag —
    it lays its columns out into whatever it is given, so it takes that shared number and
    stops there on the same window that hands the diagram half as much again.

    Past the room there is nothing left to give, and the answer is the theme's for any
    wide content: the widget's own box scrolls sideways and the document does not."""
    page, errors = open_page(browser, serve(WIDE_DIAGRAM_PAGE))

    resized(page, 1600, 900)
    wide = page.evaluate(DIAGRAM_ROOM)
    assert wide["natural"] > wide["wide"], (
        f"the fixture must lay out wider than the shared width ({wide['wide']:.0f}px), "
        "or the window having room says nothing"
    )
    assert wide["natural"] < wide["room"], (
        "and inside the room this window has, or nothing here is about being cut off"
    )
    assert round(wide["drawn"]) == round(wide["natural"]), (
        f"the drawing was scaled to fit: natural {wide['natural']:.0f}px, "
        f"drawn {wide['drawn']:.0f}px"
    )
    assert not wide["scrolls"], (
        f"a window with the room for the whole drawing still cut it off: "
        f"{wide['natural']:.0f}px of diagram in a {wide['box']:.0f}px box"
    )
    assert wide["board"] <= wide["wide"] + 1, (
        f"the board took the room too, so what grew was the tag and not what it "
        f"declares: board {wide['board']:.0f}px against {wide['wide']:.0f}px"
    )
    assert wide["board"] > wide["column"] + 1, (
        "and the board must still be growing, or its half of this proves nothing"
    )
    assert wide["sideways"] == 0, "the page itself must not scroll sideways"

    resized(page, 1000, 900)
    narrow = page.evaluate(DIAGRAM_ROOM)
    assert narrow["natural"] > narrow["room"], (
        "the narrow half proves nothing unless the drawing outgrows the room"
    )
    assert round(narrow["drawn"]) == round(narrow["natural"]), (
        "a drawing that no longer fits is still not scaled down"
    )
    assert narrow["scrolls"], "a drawing wider than the room must scroll inside its box"
    assert narrow["sideways"] == 0, "nor may the page scroll sideways for it"
    assert errors == []
    page.close()


def test_a_widget_that_failed_soft_claims_no_room(browser, serve):
    """A wide widget's room is for the thing it draws, and a widget whose upgrade failed
    has not drawn it: what stands there is the message and the source it choked on, which
    is prose and belongs in the measure the page's prose is set to. Taking the room
    anyway put a parse error across the whole window with its message on one line."""
    # The console carries mermaid's refusal, which is what the fixture is for.
    page, _ = open_page(browser, serve(BROKEN_DIAGRAM_PAGE))
    resized(page, 1600, 900)
    at = page.evaluate("""() => {
        const box = document.getElementById('bad').querySelector('.lf-error');
        const main = document.querySelector('main'), ms = getComputedStyle(main);
        const mb = main.getBoundingClientRect();
        return { failed: !!box,
                 box: box ? box.getBoundingClientRect().width : 0,
                 widget: document.getElementById('bad').getBoundingClientRect().width,
                 // What the box would be floored at if nothing said otherwise: the
                 // source is a `pre`, so its longest line is its minimum width.
                 source: box ? box.querySelector('pre').scrollWidth : 0,
                 column: mb.width - parseFloat(ms.paddingLeft)
                         - parseFloat(ms.paddingRight) };
    }""")
    assert at["failed"], "the fixture must fail to render, or this proves nothing"
    assert at["source"] > at["column"], (
        f"the fixture's source must be wider than the {at['column']:.0f}px column at the "
        f"size it is set in, or the box has nothing to be floored at"
    )
    assert at["box"] <= at["column"] + 1, (
        f"the message stands {at['box']:.0f}px wide in a {at['column']:.0f}px column"
    )
    assert at["widget"] <= at["column"] + 1, (
        f"and the widget with it: {at['widget']:.0f}px, so the message hangs into the "
        "margin behind a scrollbar"
    )
    page.close()


def test_a_drawing_that_has_not_drawn_claims_no_room(browser, serve):
    """The room is for the drawing, and until the module has made one what stands in the
    box is the authored source: evidence, which reads at the column's width from the
    column's own edge. The mark is written before any module imports, so this is every
    page's first tenth of a second and not a corner — mermaid is fetched lazily — and
    for a page whose module never arrives it is the whole of what the reader sees. Held
    to the room, three sources came out centred at three indents, none of them the
    column's.

    The module is blocked outright here because that is the state the failure holds
    still: what the timed version of it measures is the machine."""
    url = serve(DIAGRAM_AND_RAIL_PAGE)
    page = browser.new_page(viewport={"width": 1600, "height": 900})
    page.route("**/widgets/lf-diagram.js", lambda route: route.abort())
    page.goto(url, wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    at = page.evaluate("""() => {
        const main = document.querySelector('main'), ms = getComputedStyle(main);
        const mb = main.getBoundingClientRect();
        const left = mb.left + parseFloat(ms.paddingLeft);
        const right = mb.right - parseFloat(ms.paddingRight);
        return { column: right - left, left,
                 sources: ['small', 'flow'].map((id) => {
                     const el = document.getElementById(id);
                     return { id, drawn: !!el.querySelector('svg'),
                              box: el.getBoundingClientRect().width,
                              at: el.querySelector('pre').getBoundingClientRect().left };
                 }) };
    }""")
    for source in at["sources"]:
        assert not source["drawn"], (
            f"#{source['id']} rendered anyway, so the blocked module proves nothing"
        )
        assert source["box"] <= at["column"] + 1, (
            f"#{source['id']}'s box took {source['box']:.0f}px of room for a drawing it "
            f"has not made, against a {at['column']:.0f}px column"
        )
        assert abs(source["at"] - at["left"]) <= 1, (
            f"#{source['id']}'s source starts at {source['at']:.0f}px and the column at "
            f"{at['left']:.0f}px: it is set as a drawing is placed rather than read"
        )
    page.close()


def test_a_drawing_stands_on_the_columns_axis_until_it_needs_the_free_margin(
    browser, serve
):
    """A drawing's box is the room, and a drawing is placed rather than the box: on the
    column's axis while it fits, out into the margins when it needs the room, and behind
    a reachable scrollbar when even the room is short. The rail's claim reaches only the
    rows' own bands, and neither drawing here stands level with the row — the change is
    a block above them — so both margins are the drawings' to take: the wide one held to
    the column's right edge with the margin beside it empty was the reading the claim's
    page-wide form produced, and is now the fault rather than the bargain.

    The narrow read is the other half. With the window closed in, the room genuinely
    runs short, the box scrolls, and the overflow must be laid out where the scroll can
    reach it: an overflow off the start edge is unreachable in any direction, and the
    drawing's first node is the one a reader follows the graph from."""
    page, errors = open_page(browser, serve(DIAGRAM_AND_RAIL_PAGE))
    resized(page, 1500, 900)
    at = page.evaluate(DRAWING_PLACEMENT)

    assert not at["docked"], (
        "the row docked, so there is no claim on the margin and nothing here is proved"
    )
    assert at["small"]["width"] < at["col"]["right"] - at["col"]["left"], (
        "the small drawing must fit the column, or its placement says nothing"
    )
    assert abs(at["small"]["offAxis"]) <= 1, (
        f"a drawing that fits sits off the axis of the prose it explains by "
        f"{at['small']['offAxis']:.0f}px: it reads as an exhibit that slipped"
    )

    assert at["flow"]["width"] > at["col"]["right"] - at["col"]["left"], (
        "the wide drawing must outgrow the column, or the margin is never asked for"
    )
    assert at["flow"]["box"]["left"] < at["col"]["left"] - 1, (
        "a drawing that needs the room must take the free margin: its box starts at "
        f"{at['flow']['box']['left']:.0f}px, the column at {at['col']['left']:.0f}px"
    )
    assert at["flow"]["box"]["right"] > at["col"]["right"] + 1, (
        f"a drawing no row is level with is held to the column's right edge: its box "
        f"ends at {at['flow']['box']['right']:.0f}px, the column at "
        f"{at['col']['right']:.0f}px — the rail claims the rows' bands, not the side"
    )
    assert not at["flow"]["scrolls"], (
        "with both margins the room holds this drawing whole, so a scrollbar here is "
        "room withheld"
    )
    assert abs(at["flow"]["offAxis"]) <= 1, (
        f"a drawing the room holds sits {at['flow']['offAxis']:.0f}px off the column's "
        "axis"
    )

    resized(page, 1200, 900)
    at = page.evaluate(DRAWING_PLACEMENT)
    assert at["flow"]["scrolls"], (
        "this drawing outgrows the narrow page's room, so its box must scroll"
    )
    assert abs(at["flow"]["left"] - at["flow"]["box"]["left"]) <= 1, (
        f"the overflow was laid out off the box's start edge, where no scroll reaches "
        f"it: drawing from {at['flow']['left']:.0f}px, box from "
        f"{at['flow']['box']['left']:.0f}px"
    )
    assert at["sideways"] == 0, "the page must not scroll sideways for either"
    assert errors == []
    page.close()


def test_a_widget_that_declares_width_takes_the_room_and_the_column_stays_put(
    browser, serve
):
    """A board's columns are as wide as what they hold and prose is set to a measure, so
    a page carrying both used to be a cramped board or a page widened past its own
    measure for one exhibit. x-wide is which of the two a widget is, and the theme spends
    the room the layout measured — so the exhibit grows, the prose does not move, and the
    axis they share is what keeps a page that mixes widths reading as one design.

    The diff is the half that says the declaration is doing this. It is a widget too, and
    its lines are written to a width source already fits, so it stays in the column: a
    rule that reached every widget, or one naming lf-board, would pass every other
    assertion here and fail this one."""
    page, errors = open_page(browser, serve(WIDE_AND_NARROW_PAGE))

    wide = page.evaluate(ROOM_GEOMETRY)
    assert wide["board"]["width"] > wide["column"]["width"], (
        "a widget declaring width must take more than the column: board "
        f"{wide['board']['width']:.0f}px, column {wide['column']['width']:.0f}px"
    )
    # Room to spare at this viewport, so a board stopping short of it is the shared cap
    # binding rather than the window — one width for the vocabulary, not each widget's own.
    assert wide["board"]["width"] < wide["room"]["width"], (
        "the breakout must stop at one stated width, not fill whatever is there"
    )
    assert wide["board"]["left"] >= wide["room"]["left"] - 1, (
        "past the page on the left"
    )
    assert wide["board"]["right"] <= wide["room"]["right"] + 1, "past the page, right"
    assert abs(wide["board"]["centre"] - wide["column"]["centre"]) <= 1, (
        "an exhibit that grows off the column's axis reads as one that slipped: "
        f"board centre {wide['board']['centre']:.0f}, column {wide['column']['centre']:.0f}"
    )
    assert abs(wide["diff"]["width"] - wide["column"]["width"]) <= 1, (
        "a widget that declares nothing keeps the column: diff "
        f"{wide['diff']['width']:.0f}px against {wide['column']['width']:.0f}px"
    )
    assert abs(wide["prose"]["width"] - wide["column"]["width"]) <= 1, (
        "prose keeps its measure whatever the exhibits beside it do"
    )
    assert wide["sideways"] == 0, "the page must not scroll sideways"

    # Under the column's own width there is no room to take, and the rule has to come out
    # as the layout the page already had — the same edge, not an inset approximation of it.
    resized(page, 700, 900)
    narrow = page.evaluate(ROOM_GEOMETRY)
    assert narrow["column"]["width"] < 720, (
        "the narrow half proves nothing unless the window is under the column"
    )
    assert abs(narrow["board"]["left"] - narrow["column"]["left"]) <= 1, (
        "a board on a narrow window must start where the prose starts: board at "
        f"{narrow['board']['left']:.0f}, column at {narrow['column']['left']:.0f}"
    )
    assert abs(narrow["board"]["width"] - narrow["column"]["width"]) <= 1, (
        "and be the column exactly: board "
        f"{narrow['board']['width']:.0f}px, column {narrow['column']['width']:.0f}px"
    )
    assert narrow["sideways"] == 0, "nor scroll sideways on a narrow window"
    assert errors == []
    page.close()


def test_paper_keeps_the_column(browser, serve):
    """Paper has no window to take room from: a printed page is the column's width,
    whatever the screen it was sent from was showing. The rule that grants the room is
    therefore screen-only, and leaving it out of print is the whole of what paper needs —
    the same bargain paper already has with every affordance a copy keeps.

    Asked here rather than left to the print gate beside it, which reads what a medium
    drops rather than how wide it sets what it keeps: a board printed at a screen's width
    loses its right-hand columns off the edge of the sheet, and every word of it is still
    in the document for that gate to find."""
    page, errors = open_page(browser, serve(WIDE_AND_NARROW_PAGE))
    on_screen = page.evaluate(
        "() => document.getElementById('sprint').getBoundingClientRect().width"
    )
    column = page.evaluate("""() => {
        const m = document.querySelector('main'), s = getComputedStyle(m);
        const b = m.getBoundingClientRect();
        return b.width - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight);
    }""")
    assert on_screen > column + 1, (
        "the board must be wider than the column on screen, or print proves nothing"
    )

    page.emulate_media(media="print")
    printed = page.evaluate(
        "() => document.getElementById('sprint').getBoundingClientRect().width"
    )
    assert abs(printed - column) <= 1, (
        f"paper set the board to {printed:.0f}px, past a {column:.0f}px column: a sheet "
        "has no window to take the room from, so what runs past it is off the page"
    )
    assert errors == []
    page.close()


def test_paper_holds_no_room_for_the_chrome_it_does_not_print(browser, serve):
    """The banner stands over the head of the document and the key line over its foot, so
    the document leaves each of them room. Neither bar is on a sheet — the runtime's whole
    layer is withheld from print — and the room went to paper anyway: written as body's
    own padding it printed as a blank strip at each end, the banner's height over the
    first line and the key line's under the last.

    Boxes in the document's flow fixed that, and the reason they are boxes is the other
    one: body's padding comes out of the box the room a wide widget spends is measured
    off, so the writer of that padding could not also be a reader of that box (the skill's
    CLAUDE.md). A box goes where the chrome goes; a padding on the scroll container stays
    behind.

    The screen half is read as room rather than as a covered last line, which is where a
    reader would meet it, because the column's own bottom padding is taller than the line:
    nothing is covered either way today, so an assertion about the last block would pass
    with the reservation deleted. The room is what the runtime answers for; the column's
    padding is the theme's to change."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    room = page.evaluate(CHROME_ROOM)
    assert room["banner"] > 0 and room["line"] > 0, (
        f"neither bar is standing, so there is nothing here to reserve for: {room}"
    )
    assert abs(room["head"] - room["banner"]) <= 1, (
        f"the document starts {room['head']:.0f}px down, under a "
        f"{room['banner']:.0f}px banner"
    )
    assert room["foot"] >= room["line"], (
        f"the document ends {room['foot']:.0f}px short of its own end, under a "
        f"{room['line']:.0f}px key line"
    )

    page.emulate_media(media="print")
    printed = page.evaluate(CHROME_ROOM)
    assert printed["head"] <= 1 and printed["foot"] <= 1, (
        f"a sheet held {printed['head']:.0f}px over the first line and "
        f"{printed['foot']:.0f}px under the last, for chrome it does not print"
    )
    assert errors == []
    page.close()


def test_a_copy_keeps_the_rail_a_decided_change_left(browser, serve, tmp_path):
    """A copy has no panel and no session, which is what makes reading its own window
    honest — but it does have one piece of the live page's furniture left. A decided
    change keeps the control that says so, because that record is what the margin was
    reserved for, so the rail is still held open in the file while the room read off the
    viewport knows nothing about it. The exported board stood 35px into that rail at a
    laptop's width and 47px at a narrow one.

    Both edges are asked about, and the left is the one that bites now: the rail claims
    the right margin, so a room read too wide is spent on the side that is free and the
    board runs off the left of the window rather than into the controls. That is the worse
    of the two directions and the reason this asks about the box rather than the strip —
    leftward overflow scrolls nothing in a page set left to right, so the columns that
    went past the edge are not cut off with a way to reach them, they are simply gone.

    Nothing could have caught it from the outside: the render gate runs on the live page
    rather than on a file, and on the live page the room is measured rather than guessed.
    The question has to be asked of the copy directly, which is what this does."""
    url = serve(RAIL_AND_WIDE_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "id": "a-accept",
            "author": "user",
            "version": 1,
            "widget": "sug-copy",
            "action": "accept",
            "detail": {},
        },
    )
    out = tmp_path / "decided.html"
    out.write_text(rendering_model.export_page(browser, url, serve.page_dir))

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.goto(out.as_uri(), wait_until="load")

    fit = page.evaluate(RAIL_FIT)
    rows = page.locator(".lf-sug-actions").count()
    assert rows == 1 and fit["rail"] != "0px", (
        "the decided control and its rail must survive into the copy, or the fault this "
        f"is about cannot arise — rows {rows}, rail {fit['rail']}"
    )
    assert fit["past"] <= 1, (
        f"the copied board stands {fit['past']:.0f}px outside the page's own box, having "
        f"been given a room that did not know about the rail: {fit['widget']:.0f}px of "
        "widget"
    )
    assert errors == []
    page.close()


def test_the_room_is_measured_after_a_late_rail(browser, serve):
    """A page carrying a change to decide gives up a rail of the controls' own width, and
    the width of those controls is a fact about their words — so lf-suggestion measures
    the first row it builds and states it, which is long after the layout first ran. The
    room a wide widget spends came from that first run, and nothing asked again: the
    exhibit kept the width of a page 189px wider than the one it was standing on and hung
    out over the rail.

    Stated rather than run for, and the route handler is where it is stated: it waits for
    the room the page states and only then lets the module through, so the ordering holds
    whichever way the machine would have gone. Releasing the held request from out here
    ordered nothing, since the module is asked for behind the registry's own round trip
    while the room needs no network at all — a loaded runner had the room stated with the
    request still to come, and the release reached for a request nobody had made.

    The reading is taken at the stamp, because a settled page is right either way: the
    rail is a claim on the page's own box and that box is watched, so the room is restated
    a frame later whatever the runtime's own call does, and every reading through the
    browser arrives after that frame. A MutationObserver on the stamp lands ahead of it.
    What the injection buys is the record and not the wait — the stamp is the runtime's
    own statement that the geometry it hands over is final, so this asks the page at the
    moment it makes the claim."""
    url = serve(RAIL_AND_WIDE_PAGE)
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.add_init_script(AT_THE_HANDOVER)

    laid_out = []

    def release_the_rail(route):
        page.wait_for_function(
            "() => getComputedStyle(document.documentElement)"
            ".getPropertyValue('--lf-room') !== ''"
        )
        laid_out.append(
            page.evaluate(
                "() => getComputedStyle(document.documentElement)"
                ".getPropertyValue('--rail')"
            )
        )
        route.continue_()

    page.route("**/widgets/lf-suggestion.js", release_the_rail)
    page.goto(url)
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")

    assert laid_out == [""], (
        "the module was never held behind the layout, so the rail's arrival is the "
        f"machine's ordering rather than this test's: {laid_out}"
    )
    fit = page.evaluate("() => window.__handover")
    assert fit["rail"] != "0px", (
        "no rail was reserved, so the late-arriving fact this is about never arrived"
    )
    assert fit["past"] <= 1, (
        f"the board stands {fit['past']:.0f}px outside the page's own box at the moment "
        f"the page says it is done, laid out to the width of a page 189px wider than "
        f"the one it is on: {fit['widget']:.0f}px of widget in {fit['content']:.0f}px "
        "of page"
    )
    assert errors == []
    page.close()


def test_the_room_follows_a_margin_taken_after_the_handover(
    browser, serve, tmp_path, monkeypatch
):
    """A wide widget spends the room, the room is measured off the page's own box, and a
    widget may take a strip of that box at any moment at all. The one above takes it while
    upgrading, and the call at the end of the upgrade chain is what answers that; a widget
    that takes one a frame later was answered by nothing, and the page went on stating the
    room of a box 160px wider than the one its exhibit was standing in — silently, since a
    room too wide is a board that fits everywhere except the page it is on.

    The list of the ways the box was known to move is what made that possible, and a list
    of the ways a widget may behave is the closed list the norms are about. So the box is
    watched instead, and what a widget does to it needs no entry anywhere.

    The fixture is the case in its smallest honest form — a project-layer widget claiming
    the margin theme.css already reserves for one. What holds it to the case is that the
    claim waits on a request this test answers, and answers only once the page has said it
    is done: a claim landing any earlier is the one the call at the end of upgrade already
    covers, and on a fast machine that is where an unheld one would land."""
    monkeypatch.chdir(tmp_path)
    author_test_widget(tmp_path, "lf-callout", upgrade=True)
    (tmp_path / ".leaf" / "widgets" / "lf-callout.js").write_text(LATE_MARGIN_WIDGET)

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.add_init_script(AT_THE_HANDOVER)
    answered = []

    def answer_after_the_handover(route):
        # Both stamps, not the first alone: what makes a claim late is not the handover
        # by itself but everything the page finishes around it, since the panel's first
        # render resizes a box this layout writer watches and would restate the room by
        # accident. The second stamp is the replay that render waits on.
        page.wait_for_function(BOTH_STAMPS)
        answered.append(True)
        route.fulfill(status=204)

    page.route("**/margin-width", answer_after_the_handover)
    page.goto(serve(LATE_MARGIN_PAGE))
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")

    at_stamp = page.evaluate("() => window.__handover")
    assert at_stamp["rail"] == "0px", (
        "the margin was taken before the page was handed over, which is the case the "
        f"call at the end of upgrade already covers: {at_stamp['rail']}"
    )
    # On the room being read again, not on the margin that prompts it: the claim lands a
    # frame ahead of the reading, and a wait on the padding would arrive in between. The
    # timeout is left to fall through because the geometry below is the verdict and says
    # what a timeout cannot — how far out the exhibit stood, and on what room.
    try:
        page.wait_for_function(
            "(was) => getComputedStyle(document.documentElement)"
            ".getPropertyValue('--lf-room') !== was",
            arg=at_stamp["room"],
            timeout=5000,
        )
    except PlaywrightTimeout:
        pass

    assert answered == [True], (
        "the widget never asked, so its claim rode nothing this test controls and the "
        f"moment it landed was the machine's: {answered}"
    )
    fit = page.evaluate(RAIL_FIT)
    assert fit["rail"] == "160px", (
        f"the widget never took its margin, so nothing here is tested: {fit['rail']}"
    )
    assert fit["past"] <= 1, (
        f"the board stands {fit['past']:.0f}px outside the page's own box, holding the "
        f"room of the box the widget then took 160px out of ({at_stamp['room']} at the "
        f"handover, {fit['room']} now): {fit['widget']:.0f}px of widget in "
        f"{fit['content']:.0f}px of page"
    )
    assert errors == []
    page.close()


def test_a_wide_widget_leaves_the_rail_its_controls(browser, serve):
    """The rail is reserved out of the right of the page and the controls hang 22px off
    the column, and those are the same place only when the column is flush against the
    strip. It never is — the column centres in what the strip leaves — so on any window
    wider than that the controls stand well inside the page's own box, and a widget
    grown to the edge of that box is drawn over them. Measured before the claim was
    written: 76px of board over the controls at 1200px and 134px at 1400 and 1600,
    which is the whole row.

    The claim is settled at the height it arises, which is what the two boards are for
    — the same pair the sidenote's margin keeps. One holds a change in its
    own card, so its row hangs level with it and the board declines the right side; the
    other is 600px further down with nothing beside it, and grows both ways where it
    stands. Asserting only the first would pass just as well for a page that refused
    every exhibit the margin because a change existed somewhere above it — the reading
    that held a board 1400px below the only row to the column's width with 345px of
    margin standing empty beside it.

    A range of windows rather than one, because the gap between the reservation and the
    occupancy is the column's leftover and grows with the window: a single viewport can
    be picked where the two happen to agree, and 1000px is that viewport here. What the
    controls are for is being pressed, so anything over them is the change undecidable —
    the page's own loop, stopped by its own exhibit."""
    url = serve(RAIL_BAND_PAGE)
    page, errors = open_page(browser, url)

    for width in (1000, 1200, 1400, 1600):
        resized(page, width, 900)
        at = page.evaluate(RAIL_BANDS)
        hanging = [r for r in at["rows"] if not r["docked"]]
        assert hanging, (
            f"at {width}px every row docked, so nothing is in the margin to run over"
        )
        for name in ("plan", "later"):
            b = at[name]
            for r in hanging:
                across = b["left"] < r["right"] and b["right"] > r["left"]
                down = b["top"] < r["bottom"] and b["bottom"] > r["top"]
                assert not (across and down), (
                    f"at {width}px the {name} board is drawn over the controls that "
                    f"decide a change: board {b['left']:.0f}–{b['right']:.0f}px across "
                    f"and {b['top']:.0f}–{b['bottom']:.0f}px down, controls "
                    f"{r['left']:.0f}–{r['right']:.0f}px and "
                    f"{r['top']:.0f}–{r['bottom']:.0f}px"
                )
            assert b["right"] <= at["pageRight"] + 1, (
                f"at {width}px the {name} board is past the page's box as well"
            )
        assert at["sideways"] == 0, f"at {width}px the page scrolls sideways"
        assert (
            at["plan"]["width"] >= at["column"]["right"] - at["column"]["left"] - 1
        ), (
            f"at {width}px the claim cost the exhibit its own measure: board "
            f"{at['plan']['width']:.0f}px inside the column"
        )

    # The claim reaches the rows' own heights and no further: with the whole left margin
    # free the near board still grows that way, and the far board, which no row is level
    # with, takes both margins where it stands.
    resized(page, 1600, 900)
    at = page.evaluate(RAIL_BANDS)
    assert at["plan"]["left"] < at["column"]["left"] - 1, (
        "a claim on one margin must cost that side only: with the whole left margin "
        "free the near board is still the column's width, so nothing grew at all"
    )
    assert at["later"]["right"] > at["column"]["right"] + 1, (
        "a board with no row anywhere near it is held to the column's right edge: a "
        "row claims the margin at its own height, not down the whole page"
    )
    assert errors == []
    page.close()


def test_a_copy_keeps_a_board_off_the_row_its_decided_change_left(
    browser, serve, tmp_path
):
    """The mark that holds an exhibit off a row beside it is measured by the module and
    painted on the widget, and a copy runs no script to measure anything: the mark rides
    into the file the way the rail does, and it is all that holds the copy's board off
    the decided control standing level with it. A decided change keeps that control —
    the record is what the margin was reserved for — so the collision the live page
    measured is still real in the file, while the exhibit 600px further down carries no
    mark and takes the room the copy's own reading grants it."""
    url = serve(RAIL_BAND_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "id": "a-accept",
            "author": "user",
            "version": 1,
            "widget": "sug-card",
            "action": "accept",
            "detail": {},
        },
    )
    out = tmp_path / "banded.html"
    out.write_text(rendering_model.export_page(browser, url, serve.page_dir))

    errors = []
    copy = browser.new_page(viewport={"width": 1600, "height": 900})
    copy.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    copy.on("pageerror", lambda e: errors.append(str(e)))
    copy.goto(out.as_uri(), wait_until="load")
    at = copy.evaluate(RAIL_BANDS)

    decided = [r for r in at["rows"] if not r["docked"]]
    assert decided, "no row survived into the copy, so there is nothing to stand over"
    b = at["plan"]
    for r in decided:
        across = b["left"] < r["right"] and b["right"] > r["left"]
        down = b["top"] < r["bottom"] and b["bottom"] > r["top"]
        assert not (across and down), (
            f"the copy draws the board over the decided control beside it: board "
            f"{b['left']:.0f}–{b['right']:.0f}px across and {b['top']:.0f}–"
            f"{b['bottom']:.0f}px down, control {r['left']:.0f}–{r['right']:.0f}px "
            f"and {r['top']:.0f}–{r['bottom']:.0f}px"
        )
    assert at["later"]["right"] > at["column"]["right"] + 1, (
        "the copy held the far board to the column: the mark is the one claim that "
        "travels, and it belongs only to the exhibits a row stands beside"
    )
    assert at["sideways"] == 0
    assert errors == []
    copy.close()


def test_a_drawing_scrolls_only_for_room_the_page_truly_lacks(browser, serve):
    """Scrolling is the theme's honest degrade when even the room runs short, so every
    other reading calls a page well whose drawing scrolls beside an empty margin —
    nothing is clipped without a scrollbar and nothing stands outside any box. That is
    the shape both margin claims' faults arrived in, and WITHHELD_ROOM is the reading
    that refuses it: a drawing that scrolls, inside room that would have held it, with
    nothing standing in the margin at its own band.

    The clean half proves the page this gate is for passes it: a change to decide above,
    a drawing the room holds below, and the gate finds nothing. The capped half is what
    makes that worth believing — the same page with the drawing's box held under its own
    graph fires the reading, so a clean answer is the layout's and not the probe going
    blind. The guard between them pins the premise: the graph is wider than the column
    and narrower than the room, or neither half asks the question."""
    url = serve(DRAWN_PAST_A_RAIL_PAGE)
    page, errors = open_page(browser, url)
    fit = page.evaluate("""() => {
        const el = document.getElementById('flow');
        const m = document.querySelector('main');
        const s = getComputedStyle(m), b = m.getBoundingClientRect();
        return { shows: el.clientWidth, drawn: el.scrollWidth,
                 room: parseFloat(getComputedStyle(el).getPropertyValue('--lf-room')),
                 column: b.width - parseFloat(s.paddingLeft)
                         - parseFloat(s.paddingRight) };
    }""")
    assert fit["column"] < fit["drawn"] <= fit["room"], (
        f"the premise is gone — the graph must need growing and fit the room, or "
        f"neither half of this test asks the question: drawn {fit['drawn']:.0f}px, "
        f"column {fit['column']:.0f}px, room {fit['room']:.0f}px"
    )
    assert fit["shows"] >= fit["drawn"] - 1, (
        f"the page had {fit['room']:.0f}px of room and no note or row beside the "
        f"drawing, and still shows {fit['shows']:.0f}px of its {fit['drawn']:.0f}px"
    )
    assert page.evaluate(render_checks_model.WITHHELD_ROOM) == []
    assert errors == []
    page.close()

    capped = DRAWN_PAST_A_RAIL_PAGE.replace(
        '<h1 id="t">Flow</h1>',
        '<style>#flow { max-width: 640px }</style>\n<h1 id="t">Flow</h1>',
    )
    failures = rendering_model.render_version(browser, serve(capped))
    assert [f for f in failures if "<lf-diagram id=flow> scrolls" in f], (
        f"a drawing held under its own graph beside an empty margin must be named at "
        f"handover, and the gate said: {failures or 'nothing'}"
    )


def test_the_render_gate_names_a_wide_widget_drawn_over_the_pages_own_margin(
    browser, serve
):
    """Two rules in the theme give a margin up to what stands in it, one per claimant,
    and a rule is only ever as complete as the list behind it. A project hangs its own
    apparatus out there and the theme has no rule for it, so this is what is left: the
    room the page states is measured against what is actually in the margin, and a widget
    drawn over any of it is named at handover with both boxes in the message.

    It reads a resident by the same test the pass above excuses one by — placed
    absolutely, or floated clear of the column — so this needs no vocabulary of its own
    and nothing has to be declared to it. That is what keeps the two theme rules honest:
    the next claimant that forgets one is a refusal with a name on it rather than a page
    somebody eventually notices is drawn over its own controls."""
    failures = rendering_model.render_version(browser, serve(OWN_MARGIN_FURNITURE))

    assert [
        f
        for f in failures
        if "<lf-board id=sprint> is drawn over <div id=own-rail>" in f
    ], (
        f"the gate said nothing about a board drawn over the page's own margin: {failures}"
    )
    assert not [f for f in failures if "own-rail" in f and "past the column" in f], (
        "the furniture itself was named for standing where it was put"
    )


def test_a_wide_widget_in_a_reply_takes_the_panels_room(browser, serve):
    """The room a wide widget spends is the document's, and a thread's message is the one
    place a widget of the page's vocabulary renders outside the document. The skill offers
    a diagram in a reply as the way to explain a fix in the margin, and a diagram is
    declared wide — so marked as one it would lay itself out to a 1080px page inside a
    420px panel, and the explanation would be the half of it the panel could show.

    The mark that would do that is the one deliberately left out of the message render
    (x-wide, the half of markDeclared the page keeps to itself). Nothing about a message
    says so, which is why this asks: the widget is in the panel, and the panel's width is
    what bounds it."""
    url = serve(REPLY_HOST_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-fix",
            "author": "user",
            "version": 1,
            "text": "How does the fallback read?",
        },
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "id": "r-fix",
            "author": "claude",
            "parent": "c-fix",
            "version": 1,
            "text": "Like this:",
            "markup": '<lf-diagram id="fallback-flow"><pre>\n'
            "graph LR\n  R[request] --> C{cookie}\n  C --> S[session]\n</pre></lf-diagram>",
        },
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()
    panel_settled(page)
    expect(page.locator("#fallback-flow svg")).to_be_visible()

    fit = page.evaluate("""() => {
        const el = document.getElementById('fallback-flow');
        const holder = el.closest('.lf-msg-body');
        const a = el.getBoundingClientRect(), b = holder.getBoundingClientRect();
        return { widget: a.width, message: b.width, past: a.right - b.right,
                 marked: el.hasAttribute('data-lf-wide') };
    }""")
    assert not fit["marked"], (
        "a widget in a thread was handed the page's room; the panel is not the page"
    )
    assert fit["past"] <= 1, (
        "the diagram stands past the message that holds it by "
        f"{fit['past']:.0f}px — widget {fit['widget']:.0f}px in a "
        f"{fit['message']:.0f}px panel"
    )
    assert errors == []
    page.close()


def test_a_widget_in_a_reply_is_still_set_among_the_words(browser, serve):
    """Whether a widget stands in an inline run is true of it wherever it renders, which
    is what separates that mark from the width model beside it: the room a wide widget
    spends is the document's and stays behind, while a chip quoted into a reply is as much
    a word there as on the page. The lists that ask whether a slot or a variant holds block
    content invert HTML's phrasing content, and every custom element falls outside a
    platform set — so with the mark withheld here, an exhibition the agent quotes to
    compare two stores would stack into rows in the panel and nowhere else.

    Asked of the group's own display rather than of its cells' geometry, because a
    420px panel has no room for two columns either way: the stacking rule is what
    replaces the grid, and it is visible whatever the reader has drawn the panel to."""
    url = serve(REPLY_HOST_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-stores",
            "author": "user",
            "version": 1,
            "text": "What did the two stores cost us?",
        },
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "id": "r-stores",
            "author": "claude",
            "parent": "c-stores",
            "version": 1,
            "text": "Side by side:",
            "markup": INLINE_REPLY_MARKUP,
        },
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()
    panel_settled(page)
    expect(page.locator("#rp-terse")).to_be_visible()

    forms = page.evaluate("""() => Object.fromEntries(
        ['rp-terse', 'rp-argued'].map(id => {
            const group = document.getElementById(id);
            return [id, { group: getComputedStyle(group).display,
                          variant: getComputedStyle(group.firstElementChild).display,
                          marked: [...group.querySelectorAll('lf-chip')]
                              .every(chip => chip.hasAttribute('data-lf-inline')) }];
        }))""")
    assert forms["rp-terse"]["marked"], (
        "a chip in a reply was left unmarked, so the panel reads it as block content"
    )
    assert (forms["rp-terse"]["group"], forms["rp-terse"]["variant"]) == (
        "grid",
        "block",
    ), f"a chip-led exhibition stacked in the panel: {forms['rp-terse']}"
    assert (forms["rp-argued"]["group"], forms["rp-argued"]["variant"]) == (
        "block",
        "flow-root",
    ), f"the stacking rule never reached the panel at all: {forms['rp-argued']}"
    assert errors == []
    page.close()


def test_a_wide_widget_stays_inside_a_box_that_frames_it(browser, serve):
    """The room is the page's to give, and a widget inside a box that paints is not held
    by the page. A quoted board that took the window stood outside the gutter marking it
    as quoted — the exhibit escaping its own exhibit — while a diagram in an option card
    was worse for being invisible: a choose group clips to its own cells, so the widest
    part of the evidence an option argued on was cut off at the card's edge rather than
    drawn past it, and nothing on the page said a word.

    A plain section is the control. It paints nothing and is the column's own width, so a
    board inside one takes the room exactly as it would standing alone — which is what
    says this is about the box and not about being nested.

    Which boxes those are is read off `--lf-frame`, the word a box already says where it
    draws its frame, so the metric here is held by declaring one and the page's own div by
    declaring the same one. A list of tags stood in for that reading and shadowed it: the
    metric declared the frame and was not in the list, and no list a layer writes can
    reach the div at all.

    The task and the note are the two a list of tags could not have named even in
    principle. A task's rail is drawn by `lf-task > lf-task`, so a task frames what it
    holds only where it is nested, and a note's box is `.lf-code-note`, built by the code
    block's module and worn by no tag at all. Each let a diagram out ~245px over the
    column until the rule that draws it declared the frame.

    The row form is the declaration's limit, and the reason the sizing is asserted
    too. A row option is a table hugging its words, and legacy table sizing answers
    to content where every modern layout clamps a scroll container — so with the
    frame declared all along, a diagram in a row grew the row, the row grew the
    shared track, and the group's clip cut the evidence off at its border. And a
    separated table adds its padding outside the width it is given, so every row on
    every joined group stood 30px past its group, diagram or no diagram, the clip
    spending the overhang out of the pick's word-room. The box a wide widget gets
    answers to the room and never to its content (contain: inline-size, theme.css),
    and the row keeps its reservation inside the width it states (box-sizing:
    border-box, packages/default/theme.css)."""
    page, errors = open_page(browser, serve(FRAMED_WIDE_PAGE))
    boxes = page.evaluate("""() => {
        const box = (sel) => {
            const r = document.querySelector(sel).getBoundingClientRect();
            return { left: r.left, right: r.right, width: r.width };
        };
        const main = document.querySelector('main');
        const s = getComputedStyle(main), b = main.getBoundingClientRect();
        return { column: b.right - parseFloat(s.paddingRight)
                         - b.left - parseFloat(s.paddingLeft),
                 loose: box('#in-section'), specimen: box('#quoted'),
                 quoted: box('#in-specimen'), card: box('#opt-a'),
                 diagram: box('#in-card'),
                 boardCard: box('#ek1'), inBoardCard: box('#in-board-card'),
                 metric: box('#me1'), inMetric: box('#in-metric'),
                 task: box('#t-inner'), inTask: box('#in-task'),
                 note: box('.lf-code-note'), inNote: box('#in-note'),
                 rowGroup: box('#row-pick'), rowCell: box('#row-a'),
                 inRow: box('#in-row'), rowPick: box('#row-a .lf-pick'),
                 ownBox: box('#own-box'), inOwnBox: box('#in-own-box') };
    }""")

    assert boxes["loose"]["width"] > boxes["column"] + 1, (
        "a transparent wrapper must not cost the exhibit its room: board "
        f"{boxes['loose']['width']:.0f}px in a {boxes['column']:.0f}px column"
    )
    assert boxes["quoted"]["left"] >= boxes["specimen"]["left"] - 1, (
        "the quoted board escaped its frame on the left"
    )
    assert boxes["quoted"]["right"] <= boxes["specimen"]["right"] + 1, (
        "the quoted board escaped its frame on the right: board out to "
        f"{boxes['quoted']['right']:.0f}, frame ends at {boxes['specimen']['right']:.0f}"
    )
    assert boxes["diagram"]["left"] >= boxes["card"]["left"] - 1, (
        "the diagram crossed the card's left edge, where the group's clip cuts it off"
    )
    assert boxes["diagram"]["right"] <= boxes["card"]["right"] + 1, (
        "the diagram crossed the card's right edge, where the group's clip cuts it off: "
        f"diagram out to {boxes['diagram']['right']:.0f}, card ends at "
        f"{boxes['card']['right']:.0f}"
    )
    assert boxes["rowCell"]["right"] <= boxes["rowGroup"]["right"] + 1, (
        "the row grew past the group that clips it: row out to "
        f"{boxes['rowCell']['right']:.0f}, group ends at {boxes['rowGroup']['right']:.0f}"
    )
    assert boxes["inRow"]["left"] >= boxes["rowCell"]["left"] - 1, (
        "the diagram crossed the row's left edge"
    )
    assert boxes["inRow"]["right"] <= boxes["rowCell"]["right"] + 1, (
        "the diagram crossed the row's right edge, where the group's clip cuts it off: "
        f"diagram out to {boxes['inRow']['right']:.0f}, row ends at "
        f"{boxes['rowCell']['right']:.0f}"
    )
    assert boxes["rowPick"]["right"] <= boxes["rowGroup"]["right"] + 1, (
        "the pick's word-room runs past the group and the clip spends it: pick out to "
        f"{boxes['rowPick']['right']:.0f}, group ends at {boxes['rowGroup']['right']:.0f}"
    )
    # A board's own card is the same box asked from inside a scroller, which is where the
    # gate below had been blind: this diagram stood 332px past its card and across the
    # next column of the board, and every reading of the page called it clean.
    assert boxes["inBoardCard"]["left"] >= boxes["boardCard"]["left"] - 1, (
        "the diagram crossed its card's left edge on the board"
    )
    assert boxes["inBoardCard"]["right"] <= boxes["boardCard"]["right"] + 1, (
        "the diagram crossed its card's right edge and is drawn over the next column: "
        f"diagram out to {boxes['inBoardCard']['right']:.0f}, card ends at "
        f"{boxes['boardCard']['right']:.0f}"
    )
    assert boxes["inMetric"]["left"] >= boxes["metric"]["left"] - 1, (
        "the diagram crossed the metric's left edge"
    )
    assert boxes["inMetric"]["right"] <= boxes["metric"]["right"] + 1, (
        "the diagram crossed the metric's right edge and is drawn over the metric "
        f"beside it: diagram out to {boxes['inMetric']['right']:.0f}, metric ends at "
        f"{boxes['metric']['right']:.0f}"
    )
    assert boxes["inTask"]["left"] >= boxes["task"]["left"] - 1, (
        "the diagram crossed the left edge of the task that holds it"
    )
    assert boxes["inTask"]["right"] <= boxes["task"]["right"] + 1, (
        "the diagram crossed the right edge of the task that holds it and is drawn past "
        "the rail marking it as nested: diagram out to "
        f"{boxes['inTask']['right']:.0f}, task ends at {boxes['task']['right']:.0f}"
    )
    assert boxes["inNote"]["left"] >= boxes["note"]["left"] - 1, (
        "the diagram crossed the left edge of the note that holds it"
    )
    assert boxes["inNote"]["right"] <= boxes["note"]["right"] + 1, (
        "the diagram crossed the right edge of the note that holds it and is drawn over "
        "the code block it annotates: diagram out to "
        f"{boxes['inNote']['right']:.0f}, note ends at {boxes['note']['right']:.0f}"
    )
    assert boxes["inOwnBox"]["left"] >= boxes["ownBox"]["left"] - 1, (
        "the diagram crossed the left edge of the box the page drew for it"
    )
    assert boxes["inOwnBox"]["right"] <= boxes["ownBox"]["right"] + 1, (
        "the diagram crossed the right edge of the box the page drew for it, so a "
        "project declaring the frame does not get the room held in: diagram out to "
        f"{boxes['inOwnBox']['right']:.0f}, box ends at {boxes['ownBox']['right']:.0f}"
    )
    assert errors == []
    page.close()


def test_the_render_gate_names_a_wide_widget_that_escapes_a_frame_that_scrolls(
    browser, serve
):
    """A wide widget is measured against the box that frames it, and everything else on
    the page is excused by a scroll container above it — a box inside one is drawn only
    as far as the scroller reaches, so it cannot spill onto the page. Asked in that order,
    the excuse ate the measurement: a board scrolls, so every card on every board was
    excused from the one reading that applies to what it holds, and a diagram drawn 332px
    across the next column passed the gate that exists to name it.

    The frame here is the page's own, because a project's box is what no theme rule can
    reach — the same place the margin-furniture gate above stands."""
    failures = rendering_model.render_version(browser, serve(FRAMED_SCROLLER_PAGE))

    assert [
        f for f in failures if "<lf-board id=framed>" in f and "<div id=own-frame>" in f
    ], (
        "the gate said nothing about a wide widget escaping a frame that scrolls: "
        f"{failures}"
    )


def test_a_wide_widget_gives_the_panel_its_strip(browser, serve):
    """The comment panel takes 420px of the window, and nothing in CSS can see that — so
    the room a wide widget spends is measured, and this is the measurement's hard case.
    The strip is handed over as motion, so at the moment the layout is written body still
    has the width it is leaving: a room read off the box in front of us states one 420px
    too wide, and the exhibit hangs over the panel that displaced it with a sideways
    scrollbar under it, for as long as it takes something else to remeasure — which, on a
    page nobody resizes again, is the rest of the session.

    Straddling the open is the whole of the test. A board already at the shared cap is
    the same 1080px either side of a room read wrongly, so what says the room moved is
    the exhibit coming down to fit a window that is 420px narrower than the one it was
    laid out in."""
    page, errors = open_page(browser, serve(WIDE_AND_NARROW_PAGE))
    closed = page.evaluate(ROOM_GEOMETRY)
    assert closed["board"]["width"] > closed["column"]["width"], (
        "the board must start wider than the column, or the shrink proves nothing"
    )

    page.locator(".lf-comments").click()
    panel_settled(page)
    opened = page.evaluate(ROOM_GEOMETRY)

    assert opened["board"]["width"] < closed["board"]["width"], (
        "the exhibit kept the width of a window it no longer has: board "
        f"{opened['board']['width']:.0f}px in {opened['room']['width']:.0f}px of room"
    )
    assert opened["board"]["right"] <= opened["room"]["right"] + 1, (
        "the exhibit hangs over the panel that displaced it"
    )
    assert opened["sideways"] == 0, (
        "the page scrolls sideways with the panel open — the strip was spent twice"
    )
    assert abs(opened["prose"]["width"] - opened["column"]["width"]) <= 1, (
        "prose still keeps the column beside an open panel"
    )

    # Closing is the same hand-over the other way, and the anticipation that is right on
    # the way in is wrong on the way out: the strip comes back over a fifth of a second,
    # and an exhibit that took it before the page had it scrolls the document sideways
    # for exactly as long. Read before the transition settles, because that is the whole
    # of the window in which it is wrong.
    page.get_by_role("button", name="Close comments").click()
    assert page.evaluate(
        "() => document.body.scrollWidth <= document.body.clientWidth"
    ), "the page scrolled sideways while the panel's strip was still coming back"
    panel_settled(page, open=False)
    closed_again = page.evaluate(ROOM_GEOMETRY)
    assert closed_again["board"]["width"] == closed["board"]["width"], (
        "the room the panel gave back never reached the exhibit: board "
        f"{closed_again['board']['width']:.0f}px, was {closed['board']['width']:.0f}px"
    )
    assert closed_again["sideways"] == 0
    assert errors == []
    page.close()


def test_a_copy_reads_the_room_from_its_own_window(browser, serve, tmp_path):
    """A copy keeps the breakout, because it is layout the markup describes rather than
    an affordance a handler kept — but it cannot keep the *number*. The room is measured
    on the live page and stated inline on the root, which outranks any rule, so a copy
    carrying it would hold the exporter's headless window forever and lay a file out for
    a window nobody is reading it in. BAKE takes it off and the theme states the copy's
    own, from a viewport that is honest there: a file has no comment panel to yield a
    strip to.

    The width that panel stands at is stated on the root by the same hand, and goes the
    same way — not because a copy reads it, having no panel, but because both numbers
    belong to a window and a reader that are not this file's. The reading asks for the
    root's whole style rather than for either name, so the day a third number is stated
    there is the day this says so.

    Both windows, because that estimate is the half that can be wrong in either
    direction, and it was: reading 96px off the viewport puts it under the true room on a
    narrow window, and the first draft of this stood every copied board 24px inside the
    prose it was set beneath. The floor at the column is what answers that, and this is
    what says the floor is still there."""
    url = serve(WIDE_AND_NARROW_PAGE)
    out = tmp_path / "standalone.html"
    out.write_text(rendering_model.export_page(browser, url, serve.page_dir))

    page = browser.new_page(viewport={"width": 1400, "height": 900})
    errors = watched(page)
    page.goto(out.as_uri(), wait_until="load")

    stated = page.evaluate("() => document.documentElement.getAttribute('style') ?? ''")
    assert stated.strip() == "", (
        "the copy carries this window's measurements into every window it is opened "
        f"in: {stated}"
    )

    wide = page.evaluate(ROOM_GEOMETRY)
    assert wide["board"]["width"] > wide["column"]["width"], (
        "a copy keeps the breakout: it is layout, not an affordance — board "
        f"{wide['board']['width']:.0f}px, column {wide['column']['width']:.0f}px"
    )
    assert wide["board"]["left"] >= wide["room"]["left"] - 1, (
        "past the page on the left"
    )
    assert wide["board"]["right"] <= wide["room"]["right"] + 1, "past the page, right"
    assert wide["sideways"] == 0, "a copy must not scroll sideways either"

    resized(page, 700, 900)
    narrow = page.evaluate(ROOM_GEOMETRY)
    assert abs(narrow["board"]["width"] - narrow["column"]["width"]) <= 1, (
        "the copy's own reading of the room came in under the column and shrank the "
        f"board inside the prose: board {narrow['board']['width']:.0f}px, column "
        f"{narrow['column']['width']:.0f}px"
    )
    assert narrow["sideways"] == 0, "nor on a narrow one"
    assert errors == []
    page.close()


def test_a_wide_widget_leaves_the_sidenote_its_margin(browser, serve, tmp_path):
    """The page has two claims on its right margin now: a note is read out there, and a
    wide widget expands into it. A widget drawn over a note is the note lost — it is the
    thing on top — and the reader loses words the page states, which is the same fault
    the clipped-float reading refuses a version for.

    The claim is settled at the height it arises and nowhere else, which is what the two
    boards are for. One stands level with the note and drops below it to take the margin;
    the other is 600px further down with nothing out there, and takes the margin where it
    stands. Asserting only the first would pass just as well for a page that refused every
    exhibit the margin because a note existed somewhere above it — the reading that held a
    diagram to the column's own width with the margin beside it empty.

    Both media, because they answer the question differently and only one of them
    measures. The live page reads the room off the box the layout actually produced, so a
    strip reserved by any rule at all is already out of it; a copy runs no script and the
    theme states the room from the viewport, which knows about a strip only if the rule
    that states the room subtracts the same one the padding added. `clear` is the same
    answer in both, being layout rather than measurement."""
    url = serve(NOTE_AND_WIDE_PAGE)
    out = tmp_path / "standalone.html"
    out.write_text(rendering_model.export_page(browser, url, serve.page_dir))

    page, errors = open_page(browser, url)
    resized(page, NOTE_BAND, 900)
    live = page.evaluate(ROOM_GEOMETRY)

    copy_errors = []
    copy = browser.new_page(viewport={"width": NOTE_BAND, "height": 900})
    copy.on(
        "console", lambda m: copy_errors.append(m.text) if m.type == "error" else None
    )
    copy.on("pageerror", lambda e: copy_errors.append(str(e)))
    copy.goto(out.as_uri(), wait_until="load")
    copied = copy.evaluate(ROOM_GEOMETRY)

    for medium, wide in (("the live page", live), ("a copy", copied)):
        assert wide["note"]["width"] > 0, (
            f"{medium} lost the note entirely, so this proves nothing about the margin"
        )
        note = wide["note"]
        for name in ("board", "later"):
            exhibit = wide[name]
            across = exhibit["left"] < note["right"] and exhibit["right"] > note["left"]
            down = exhibit["top"] < note["bottom"] and exhibit["bottom"] > note["top"]
            assert not (across and down), (
                f"{medium} stands the {name} board over the note it shares the margin "
                f"with: board {exhibit['left']:.0f}–{exhibit['right']:.0f}px across and "
                f"{exhibit['top']:.0f}–{exhibit['bottom']:.0f}px down, note "
                f"{note['left']:.0f}–{note['right']:.0f}px and "
                f"{note['top']:.0f}–{note['bottom']:.0f}px"
            )
        assert wide["later"]["right"] > wide["column"]["right"] + 1, (
            f"{medium} held a board with no note anywhere near it to the column's own "
            f"right edge: board to {wide['later']['right']:.0f}px, column to "
            f"{wide['column']['right']:.0f}px. A note claims the margin at its own height, "
            f"not down the whole page."
        )
        assert wide["sideways"] == 0, (
            f"{medium} scrolls sideways, so the room it took was not the room it had"
        )
        assert wide["board"]["width"] >= wide["column"]["width"] - 1, (
            f"{medium} shrank the board inside the measure its own prose is set to: "
            f"board {wide['board']['width']:.0f}px, column {wide['column']['width']:.0f}px"
        )

    assert errors == []
    assert copy_errors == []
    copy.close()
    page.close()


def test_a_note_sets_the_page_axis_with_its_whole_strip(browser, serve):
    """The strip a note claims comes out of body's right padding and the column centres
    in what is left, so the page's axis sits half a strip left of the window's. The note
    keeps that axis even on a window whose ordinary centring already left room beside the
    prose: this is a page with a right margin, not a centred page spending spare room.

    Both widths matter. The wide one proves the claim is the axis rather than only the
    shortfall, and the tighter one proves that keeping the whole claim still leaves the
    note on the page without horizontal scrolling.

    Every reading is against the page's box rather than the window, the two being the
    same width only where a scrollbar takes no room. Body owns the document's scroll and
    reserves a stable gutter for it, so on most platforms the page is 15px narrower than
    the window and sits 7.5px to its left — a settled fact about the scroll region
    (leaf.js) that the strip has no part in. Measured from the window this says that
    instead of what it is about: green wherever scrollbars overlay, red on the runner,
    and in both a note painted out in the gutter counted as a note still on the page."""
    url = serve(NOTE_AND_WIDE_PAGE)
    page, errors = open_page(browser, url)

    resized(page, 1600, 900)
    roomy = page.evaluate(ROOM_GEOMETRY)
    axis = roomy["pageBox"]["left"] + (roomy["pageBox"]["width"] - 384) / 2
    assert abs(roomy["column"]["centre"] - axis) <= 1, (
        f"the right strip did not set the page's axis: column centred at "
        f"{roomy['column']['centre']:.0f}px of a "
        f"{roomy['pageBox']['width']:.0f}px page"
    )
    assert roomy["note"]["right"] <= roomy["pageBox"]["right"], (
        f"the note is off the right edge of a "
        f"{roomy['pageBox']['width']:.0f}px page: {roomy['note']['right']:.0f}px"
    )

    resized(page, NOTE_BAND, 900)
    tight = page.evaluate(ROOM_GEOMETRY)
    axis = tight["pageBox"]["left"] + (tight["pageBox"]["width"] - 384) / 2
    assert abs(tight["column"]["centre"] - axis) <= 1, (
        f"the tighter page lost the note-set axis: column centred at "
        f"{tight['column']['centre']:.0f}px of a "
        f"{tight['pageBox']['width']:.0f}px page"
    )
    assert tight["note"]["right"] <= tight["pageBox"]["right"], (
        f"the note is off the right edge of a "
        f"{tight['pageBox']['width']:.0f}px page: {tight['note']['right']:.0f}px"
    )
    assert tight["sideways"] == 0

    assert errors == []
    page.close()


def test_a_left_sidebar_uses_the_margin_until_the_page_needs_it_back(browser, serve):
    """The sidebar is a page-level margin resident rather than a narrower prose column.

    On a roomy page it takes an explicit left strip, stands wholly outside the prose, and
    stays below the fixed banner while the page scrolls. The release-notes shot is the
    wide exhibit in the control: it may use the other margins but not the one the sticky
    sidebar can occupy at any scroll position.

    Opening the comment panel narrows the page without changing the viewport, which a
    media query cannot see. The shared cramped veto must return the aside to the flow and
    give its strip back. A narrow viewport proves the same fallback comes from CSS alone,
    and print proves paper reserves no blank margin for a posture it cannot use."""
    example = next(p for p in EXAMPLES if p.stem == "release-notes")
    page, errors = open_page(browser, serve(example))
    sidebar = page.locator("aside.sidebar")

    reading = """() => {
      const sidebar = document.querySelector('aside.sidebar');
      const main = document.querySelector('main');
      const exhibit = document.querySelector('lf-shot');
      const ms = getComputedStyle(main), ss = getComputedStyle(sidebar);
      const mb = main.getBoundingClientRect(), sb = sidebar.getBoundingClientRect();
      const eb = exhibit.getBoundingClientRect();
      return {
        cramped: document.body.hasAttribute('data-lf-cramped'),
        strip: parseFloat(getComputedStyle(document.body).paddingLeft),
        float: ss.float, position: ss.position,
        sidebar: {left: sb.left, right: sb.right, top: sb.top, width: sb.width},
        column: {
          left: mb.left + parseFloat(ms.paddingLeft),
          right: mb.right - parseFloat(ms.paddingRight),
        },
        exhibit: {left: eb.left, right: eb.right},
        sideways: document.documentElement.scrollWidth
          - document.documentElement.clientWidth,
      };
    }"""

    resized(page, 1400, 900)
    roomy = page.evaluate(reading)
    assert not roomy["cramped"]
    assert roomy["strip"] == 264
    assert roomy["float"] == "left" and roomy["position"] == "sticky"
    assert roomy["sidebar"]["right"] <= roomy["column"]["left"] - 23, (
        f"the sidebar entered the prose column: {roomy}"
    )
    assert roomy["sidebar"]["width"] == 240
    assert roomy["exhibit"]["left"] >= roomy["sidebar"]["right"] - 1, (
        f"a wide exhibit painted into the sidebar's standing margin: {roomy}"
    )
    assert roomy["sideways"] == 0

    page.evaluate(
        "document.body.style.scrollBehavior = 'auto'; document.body.scrollTo(0, 900)"
    )
    page.wait_for_function("() => document.body.scrollTop > 800")
    stuck = sidebar.evaluate("node => node.getBoundingClientRect().top")
    assert 64 <= stuck <= 68, (
        f"the sidebar stuck at {stuck:.0f}px, not below the banner"
    )

    page.evaluate("document.body.scrollTo(0, 0)")
    page.locator(".lf-comments").click()
    panel_settled(page)
    cramped = page.evaluate(reading)
    assert cramped["cramped"]
    assert cramped["strip"] == 0
    assert cramped["float"] == "none" and cramped["position"] == "static"
    assert abs(cramped["sidebar"]["left"] - cramped["column"]["left"]) <= 1
    assert cramped["sideways"] == 0
    assert errors == []
    page.close()

    page, errors = open_page(browser, serve(example))
    resized(page, 700, 900)
    narrow = page.evaluate(reading)
    assert narrow["strip"] == 0
    assert narrow["float"] == "none" and narrow["position"] == "static"
    assert abs(narrow["sidebar"]["left"] - narrow["column"]["left"]) <= 1
    assert narrow["sideways"] == 0

    resized(page, 1400, 900)
    page.emulate_media(media="print")
    printed = page.evaluate(reading)
    assert printed["strip"] == 0
    assert printed["float"] == "none" and printed["position"] == "static"
    assert abs(printed["sidebar"]["left"] - printed["column"]["left"]) <= 1
    assert errors == []
    page.close()


def test_opposite_margin_residents_wait_for_the_room_they_need(
    browser, serve, tmp_path
):
    """One margin floor buys one resident, not two strips at once.

    At the ordinary 1152px floor, the sidenote keeps its established right margin and
    the sidebar remains in flow. Giving both their full strips there leaves only 504px
    for prose. At the combined floor, both may stand outside the ordinary column, less
    only a live platform's stable scrollbar gutter. A script-free copy has to make the
    same choice from its viewport alone.

    The second sidebar is the other composition case: only the first direct child of
    main may take the sticky page-level slot, so an accidental second one remains in
    flow rather than covering the first after a scroll."""
    source = leaf_page(
        "margin residents",
        """
<h1>Migration plan</h1>
<aside class="sidebar" id="route"><nav aria-label="Route"><a href="#move">Move</a></nav></aside>
<aside class="sidebar" id="extra">Secondary reference</aside>
<aside class="sidenote" id="frequency">Support runs this twice a month.</aside>
<h2 id="move">Move</h2>
<p>Shift one cohort at a time while keeping the old readers available.</p>
<div style="height: 1500px"></div>
""",
    )
    url = serve(source)
    out = tmp_path / "margin-residents.html"
    out.write_text(rendering_model.export_page(browser, url, serve.page_dir))

    reading = """() => {
      const main = document.querySelector('main'), ms = getComputedStyle(main);
      const mb = main.getBoundingClientRect();
      return {
        sidebars: [...document.querySelectorAll('aside.sidebar')].map(node => {
          const s = getComputedStyle(node), b = node.getBoundingClientRect();
          return {float: s.float, position: s.position, left: b.left,
                  right: b.right, top: b.top, bottom: b.bottom};
        }),
        noteFloat: getComputedStyle(document.querySelector('aside.sidenote')).float,
        column: {
          left: mb.left + parseFloat(ms.paddingLeft),
          right: mb.right - parseFloat(ms.paddingRight),
          width: mb.width - parseFloat(ms.paddingLeft) - parseFloat(ms.paddingRight),
        },
        padding: {
          left: parseFloat(getComputedStyle(document.body).paddingLeft),
          right: parseFloat(getComputedStyle(document.body).paddingRight),
        },
        gutter: document.body.offsetWidth - document.body.clientWidth,
        sideways: document.documentElement.scrollWidth
          - document.documentElement.clientWidth,
      };
    }"""

    page, errors = open_page(browser, url)
    resized(page, 1200, 800)
    tight = page.evaluate(reading)
    assert [side["float"] for side in tight["sidebars"]] == ["none", "none"]
    assert tight["noteFloat"] == "right"
    assert tight["padding"] == {"left": 0, "right": 384}
    assert tight["column"]["width"] == 720
    assert tight["sideways"] == 0

    # The floor is a fact about the page's box, and the window is not that box wherever
    # the platform draws a classic scrollbar: body is the document's scroller, so its bar
    # comes out of the room the strips and the column divide between them. The column
    # keeps its full measure on both sides of that, which is what the strip is floored to
    # protect: given the room, both strips stand outside a full column, and short of it by
    # a bar's width the veto hands them back. So neither read subtracts a bar from what it
    # expects — the widths the page is driven at are where the bar is accounted for, and a
    # measure that fell short of 720 anywhere here would be the fault this floor exists to
    # prevent rather than a tolerance to write down.
    resized(page, 1416, 800)
    at_floor = page.evaluate(reading)
    assert at_floor["column"]["width"] == 720, (
        "the strip came out of the column at the combined floor, which is the one width "
        f"the floor exists to keep it out of: {at_floor}"
    )

    # The runtime's own reading of the gutter, asked of the module that owns it, so the
    # width this drives at is the one the veto is doing its arithmetic in by construction
    # rather than by a second spelling that agrees on inspection. Its own evaluate and not
    # a key on `reading`, which the script-free copy below shares and which has no module
    # to ask; the window against body's padding box, the other candidate, would agree only
    # while body carries no margin, and the panel's strip below is a body margin.
    bar = page.evaluate(
        "() => import('/runtime/scrolling.js').then(m => m.scrollerGutter())"
    )
    # Driving the page at a width the helper chose and then testing the veto that spends
    # the same helper leaves one thing the reads below cannot see: an error in the helper
    # itself, which lands on both sides and cancels. A gutter overread as 30 puts the page
    # at 1446 and has stateStrip take 30 off it, so the floor is met on the nose and every
    # measure here passes while the band from 1431 up is cramped for nothing. So the two
    # spellings are held to each other first, at the one viewport both are read at, and
    # `reading` keeps the key: it is a claim about what the gutter is rather than a second
    # copy nothing checks, and it is what the failure dumps report a short measure against.
    assert bar == at_floor["gutter"], (
        "the module's gutter and the page's own reading of it have come apart, which "
        f"would leave the widths below chosen and judged by the same error: {at_floor}"
    )
    resized(page, 1416 + bar, 800)
    roomy = page.evaluate(reading)
    assert [(s["float"], s["position"]) for s in roomy["sidebars"]] == [
        ("left", "sticky"),
        ("none", "static"),
    ]
    assert roomy["noteFloat"] == "right"
    assert roomy["padding"] == {"left": 264, "right": 384}
    assert roomy["column"]["width"] == 720, (
        f"the two strips cost the column more than the room they were granted: {roomy}"
    )
    assert roomy["sidebars"][0]["right"] <= roomy["column"]["left"] - 23
    assert roomy["sidebars"][1]["left"] >= roomy["column"]["left"] - 1
    assert roomy["sideways"] == 0

    resized(page, 1700, 800)
    page.locator(".lf-comments").click()
    panel_settled(page)
    panelled = page.evaluate(reading)
    assert page.locator("body").get_attribute("data-lf-cramped") == ""
    assert [side["float"] for side in panelled["sidebars"]] == ["none", "none"]
    assert panelled["noteFloat"] == "none"
    assert panelled["padding"] == {"left": 0, "right": 0}
    assert panelled["column"]["width"] == 720
    assert panelled["sideways"] == 0
    resized(page, 1699, 800)
    resized(page, 1700, 800)
    repeated = page.evaluate(reading)
    assert page.locator("body").get_attribute("data-lf-cramped") == ""
    assert [side["float"] for side in repeated["sidebars"]] == ["none", "none"]
    assert repeated["noteFloat"] == "none"
    assert repeated["column"]["width"] == 720
    assert errors == []
    page.close()

    copy = browser.new_page(viewport={"width": 1200, "height": 800})
    copy.goto(out.as_uri(), wait_until="load")
    copied = copy.evaluate(reading)
    assert [side["float"] for side in copied["sidebars"]] == ["none", "none"]
    assert copied["noteFloat"] == "right"
    assert copied["padding"] == {"left": 0, "right": 384}
    assert copied["column"]["width"] == 720
    assert copied["sideways"] == 0
    copy.close()


def test_the_handed_over_url_opens_the_latest_version(browser, serve):
    """The URL `server run` prints is the page root carrying the key, so every handover
    reads the latest version there while keeping the live address. Two things only a
    real browser can say have to hold: the arrival sets the cookie used by the page's
    relative polling requests, and that cookie still admits a later query-less arrival.
    A `SameSite` cookie withheld from either would leave the page open and frozen with
    no console error to show for it."""
    url = serve(INLINE_PAGE)
    root = url.rsplit("/versions/", 1)[0] + f"/?t={TOKEN}"

    page, errors = open_page(browser, root)

    expect(page).to_have_url(root)
    expect(page.locator(".lf-banner")).to_be_visible()
    # The poll is the page's own fetch, relative and query-less: it answers only if the
    # cookie rode along.
    assert page.evaluate("() => fetch('/api/state').then(r => r.status)") == 200

    # A later top-level arrival carries no query. A cookie the browser withheld from it
    # would land the user on a refusal rather than the same live page.
    page.evaluate("() => { location.href = '/' }")
    page.wait_for_url(root.rsplit("?", 1)[0])
    expect(page.locator(".lf-banner")).to_be_visible()

    assert errors == []
    page.close()


def test_a_page_refuses_a_browser_that_never_had_the_link(browser, serve):
    url = serve(INLINE_PAGE)

    page = browser.new_page()
    page.goto(url.rsplit("?", 1)[0], wait_until="load")

    assert schema_model.NO_KEY in page.locator("body").inner_text()
    page.close()
