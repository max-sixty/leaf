"""Tests scheduled by the measured cost of their boundary."""

import itertools
import re

import pytest
from browser.navigation.test_comment_marks import (
    MARKED_PAGE,
    OWN_COLOURS,
    OWN_COLOURS_PAGE,
    PASSAGES,
    SEEN_APART,
    UNMARKED_STRING,
    WORDS_BOX,
    _apart,
    _comment_on,
    _contrast,
    _drawn,
    _point_at,
)
from playwright.sync_api import expect
from render_cases_navigation import (
    pending_text,
    wait_current_location,
    wait_for_pending_mark,
)
from render_harness import CHROME_ROOT, RELEASE_FOCUS, open_page, select

from leaf.source.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("engine", ["browser", "firefox_browser", "webkit_browser"])
def test_marked_words_are_seen_and_told_apart(request, serve, engine):
    """A mark on words is the user's notice that somebody said something about them,
    and each state a gesture puts it in is the answer to that gesture: the words the
    pointer rests on, those of the thread the user opened, and those their draft is on.

    The wash alone can't be that notice: --lf-mark composites to 1.13:1 over the light
    paper, and no alpha of its hue reaches 1.5:1. So the words take the mark's ink, and
    each state's paint, read off the drawn page in both schemes, is seen against the
    words' own colour, keeps its words legible on its ground, and differs from every
    other state's in its ground or its ink.

    Read from screenshots rather than computed styles, because what a highlight
    pseudo may carry is the browser's to decide, and a declaration that stopped
    applying would say nothing."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            MARKED_PAGE,
            events=[
                _comment_on(PASSAGES[state], id=f"c-{n}", text="Why these words?")
                for n, state in enumerate(("mark", "pointed at", "open thread"))
            ],
        ),
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) === 3")
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        drawn = {state: _drawn(page, PASSAGES[state]) for state in ("mark", "unmarked")}

        page.mouse.move(*_point_at(page, PASSAGES["pointed at"]))
        page.wait_for_function("() => (CSS.highlights.get('lf-mark-hover')?.size ?? 0)")
        drawn["pointed at"] = _drawn(page, PASSAGES["pointed at"])

        page.mouse.click(*_point_at(page, PASSAGES["open thread"]))
        wait_current_location(page, PASSAGES["open thread"][1])
        page.mouse.move(0, 0)
        page.wait_for_function("() => !CSS.highlights.get('lf-mark-hover')?.size")
        drawn["open thread"] = _drawn(page, PASSAGES["open thread"])
        # Out of the thread to its passage, then off the passage, so the card stands
        # over nothing the next gesture aims at.
        page.keyboard.press("Escape")
        page.keyboard.press("Escape")
        expect(page.locator(".lf-margin-preview")).to_be_hidden()

        box = page.evaluate(WORDS_BOX, list(PASSAGES["draft"]))["box"]
        middle = box["y"] + box["height"] / 2
        select(page, (box["x"] + 1, middle), (box["x"] + box["width"] - 1, middle))
        page.locator(".lf-fab-input").click()
        wait_for_pending_mark(page)
        assert pending_text(page) == PASSAGES["draft"][1]
        page.mouse.move(0, 0)
        drawn["draft"] = _drawn(page, PASSAGES["draft"])
        page.keyboard.press("Escape")
        page.wait_for_function("() => !CSS.highlights.get('lf-pending')?.size")

        # The control: words nobody marked come back in their own colour, so a reading
        # of marked words that does is reading words the mark left alone.
        _, ink, own = drawn.pop("unmarked")
        assert _apart(ink, own) < SEEN_APART, (scheme, ink, own)
        for state, (ground, words, own) in drawn.items():
            assert _apart(words, own) >= 10, (
                f"the {scheme} page's {state} words wear {words}, too near their own "
                f"{own} for the user to see that anything was said: {drawn}"
            )
            assert _contrast(words, ground) >= 3, (
                f"the {scheme} page's {state} words wear {words} on {ground}, "
                f"{_contrast(words, ground):.2f}:1: {drawn}"
            )
        for one, other in itertools.combinations(drawn, 2):
            assert (
                max(
                    _apart(drawn[one][0], drawn[other][0]),
                    _apart(drawn[one][1], drawn[other][1]),
                )
                >= SEEN_APART
            ), f"the {scheme} page draws {one} and {other} alike: {drawn}"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser", "webkit_browser"])
def test_hiding_annotations_gives_marked_words_their_own_colours_back(
    request, serve, engine
):
    """Hiding the annotations (`g H`) takes the durable marks down, and the words they
    covered wear the page's own colours again: a link's blue, prose's ink, and a text
    document's syntax colour, which is a highlight under the mark's. While the marks
    show, their ink is over the syntax colour however late the document colours the
    words, and showing them again brings the ink back. Standing in a thread while they
    are hidden washes its words and leaves them their own colour."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            OWN_COLOURS_PAGE,
            events=[
                _comment_on(PASSAGES["mark"], id="c-link", text="Why this link?"),
                # Words in a text document are anchored on its one datum, as capture
                # writes them.
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "anchor": {
                        "section": "doc",
                        "datum": "document",
                        "identity": "document",
                        "quote": 'message = "resend now"',
                    },
                    "id": "c-doc",
                    "text": "Why now?",
                },
            ],
        ),
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) === 2")
    assert not page.evaluate("CSS.highlights.has('lf-token-syn-string')"), (
        "the document coloured a string before it was scrolled to, so this page no "
        "longer registers a syntax colour after the marks"
    )
    page.evaluate(WORDS_BOX, list(UNMARKED_STRING))
    page.wait_for_function(
        "() => (CSS.highlights.get('lf-token-syn-string')?.size ?? 0) >= 2"
    )
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        # WebKit can screenshot the words before it paints a newly registered syntax
        # colour or the scheme's colours, so read them after a rendering update.
        rendered(page)
        owed = {"string": _drawn(page, UNMARKED_STRING)[1]}
        shown = {name: _drawn(page, passage) for name, passage in OWN_COLOURS.items()}
        for name, (_, words, own) in shown.items():
            assert _apart(words, owed.get(name, own)) >= 10, (
                f"the {scheme} {name} wears {words} under its mark, its own colour "
                f"{owed.get(name, own)}: {shown}"
            )
        page.evaluate(RELEASE_FOCUS)
        page.keyboard.press("g")
        page.keyboard.press("Shift+H")
        expect(page.locator(CHROME_ROOT)).to_have_attribute(
            "data-lf-annotations-hidden", ""
        )
        hidden = {name: _drawn(page, passage) for name, passage in OWN_COLOURS.items()}
        for name, (_, words, own) in hidden.items():
            assert _apart(words, owed.get(name, own)) < SEEN_APART, (
                f"with the annotations hidden, the {scheme} {name} wears {words}, "
                f"where its own colour is {owed.get(name, own)}: {hidden}"
            )
        # Standing in a thread with the annotations hidden washes its words, and they
        # keep their own colour under the wash rather than take the mark's ink. Read
        # against both, since a translucent wash shifts the drawn cores of thin strokes.
        # `t` walks from the reader's place, which the syntax colour's read left at the
        # document's last lines, so the reader goes back to the top, before the link.
        page.evaluate("scrollTo({top: 0, behavior: 'instant'})")
        rendered(page)
        page.keyboard.press("t")
        wait_current_location(page, PASSAGES["mark"][1])
        page.mouse.move(0, 0)
        ground, words, own = _drawn(page, PASSAGES["mark"])
        ink = shown["link"][1]
        assert ground != hidden["link"][0], (
            f"standing in the {scheme} link's thread drew no wash under its words"
        )
        assert _apart(words, own) < _apart(words, ink), (
            f"standing in the {scheme} link's thread with the annotations hidden, its "
            f"words wear {words}, nearer the mark's ink {ink} than their own {own}"
        )
        page.keyboard.press("Escape")
        page.keyboard.press("Escape")
        wait_current_location(page, "")
        expect(page.locator(".lf-margin-preview")).to_be_hidden()
        page.evaluate(RELEASE_FOCUS)
        page.keyboard.press("g")
        page.keyboard.press("Shift+H")
        expect(page.locator(CHROME_ROOT)).not_to_have_attribute(
            "data-lf-annotations-hidden", re.compile(".*")
        )
        page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) === 2")
        # The highlight is registered at once, but WebKit can screenshot the link before
        # it paints the re-registered mark, so read it after a rendering update.
        rendered(page)
        again = {name: _drawn(page, passage) for name, passage in OWN_COLOURS.items()}
        assert all(
            _apart(again[name][1], shown[name][1]) < SEEN_APART for name in shown
        ), (scheme, shown, again)
