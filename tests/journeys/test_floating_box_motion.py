"""How a floating box moves as the user edits its words: the margin card's reply, the
comment box beside a passage and the floating panel's field, which box-motion.js moves.

Each change the user makes moves what it moves one way: on each axis, from one input to
the next, every painted part travels toward where it comes to rest, or stands. A part
drawn somewhere for a frame and then sent back, or one that keeps vibrating, is a jerk
the user sees. Several rules place these boxes at once, their placement against the
window's edges, their growth with the words and their motion, so the jerks hide in
the cases where those rules meet: a box whose foot is a line from the window's, a key
that lands while the last one's motion runs. Hypothesis draws those cases, and
`motion_watch.js` records where each part is drawn at every frame.

Two jerks it caught stand as explicit examples: a margin card a new line held at the
window's foot drawn part of a line lower for a frame, the one reported on 31 October
2026, which also has its own test in `browser/margin/test_card_reply.py`; and a comment
box scrolled to the window's foot drawn where it stood before the scroll, hundreds of
pixels away, for a frame."""

from itertools import pairwise
from pathlib import Path

import pytest
from browser.margin import LONG_THREAD_ROOT, LOW_PASSAGE_PAGE
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st
from render_harness import open_page, resized, scroll_settled, write

from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed

MOTION_WATCH = (Path(__file__).parent.parent / "motion_watch.js").read_text()

# Each box, what opens it with the caret in its field, and its parts (`motion_watch.js`).
COMPOSERS = {
    "card": {
        "box": ".lf-margin-preview",
        "ring": ".lf-margin-preview-ground > .lf-box-ring",
    },
    "comment": {"box": ".lf-fab-bar", "ring": ".lf-fab-ground > .lf-box-ring"},
    "panel": {"box": ".lf-floating-panel", "ring": ".lf-fp-ground > .lf-box-ring"},
}

# How far a part may travel past the line from where it stood to where it rests, in CSS
# pixels: layout rounds a box to a fraction of a pixel each frame.
SLACK = 1

WORDS = st.sampled_from(
    "the card holds a reply while its words wrap past the corner where Send waits".split()
)
EDITS = st.one_of(
    st.just(("Shift+Enter",)),
    st.tuples(st.just("Backspace"), st.integers(1, 3)),
    st.tuples(st.just("type"), st.lists(WORDS, min_size=1, max_size=8).map(" ".join)),
    st.tuples(
        st.just("paste"),
        st.lists(WORDS, min_size=1, max_size=4).map(" ".join),
        st.integers(2, 4),
    ),
)


def at_rest(page, composer):
    """Wait until what the last input set moving in the box has stopped."""
    rendered(page)
    page.wait_for_function(
        """({box, ring}) => [box, ring].every(selector => {
          const node = document.querySelector(selector);
          return !node || !(node.closest('.lf-box-ground') ?? node)
            .getAnimations({subtree: true})
            .some(motion => Number.isFinite(motion.effect?.getComputedTiming().endTime));
        })""",
        arg=COMPOSERS[composer],
    )


def open_composer(page, composer):
    if composer == "card":
        page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
        page.locator(".lf-margin-preview").get_by_role(
            "textbox", name="Reply", exact=True
        ).click()
    elif composer == "comment":
        page.locator("#open").click(modifiers=["Alt"])
    else:
        page.locator(".lf-fp-field leaf-text").click()
    return page.locator(f"{COMPOSERS[composer]['box']} leaf-text").first


def stand_foot(page, composer, gap):
    """Scroll the page so the box beside the passage stands with its foot `gap` pixels
    above where the window's foot holds it, or held by that foot where `gap` is less
    than nothing. The panel stands at the window's foot whatever the page does."""
    if composer == "panel":
        return

    def foot(by):
        page.evaluate("by => document.scrollingElement.scrollBy(0, by)", by)
        scroll_settled(page)
        at_rest(page, composer)
        box = page.locator(COMPOSERS[composer]["box"]).bounding_box()
        return box["y"] + box["height"]

    page.locator("#open").evaluate("node => node.scrollIntoView({block: 'end'})")
    held = foot(0)
    beside = foot(600)
    foot(-(held - gap - beside))


def jerks(frames, marks):
    """Each part an input moved two ways on an axis, from where it stood, farther than
    SLACK: drawn somewhere for a frame and then travelling back, turning back while it
    travels, or vibrating. `marks` holds the watch's input count before each input, so
    a frame belongs to the input whose events it has seen. An input landing while a part
    moves starts its new motion from where that frame draws it, which may carry it on as
    far as it was going (box-motion.js), so that step is not a turn."""
    found = []
    for at, start in enumerate(marks):
        end = marks[at + 1] if at + 1 < len(marks) else float("inf")
        before = [frame for frame in frames if frame["inputs"] <= start][-2:]
        after = [frame for frame in frames if start < frame["inputs"] <= end]
        for part in {key for frame in after for key in frame["parts"]}:
            path = [frame["parts"][part] for frame in after if part in frame["parts"]]
            was = [frame["parts"][part] for frame in before if part in frame["parts"]]
            if was:
                going = was[-1] - was[0]
                step = path[0] - was[-1]
                if not (step * going > 0 and abs(step) <= abs(going) + SLACK):
                    path = [was[-1], *path]
            travel = sum(abs(b - a) for a, b in pairwise(path))
            if travel > abs(path[-1] - path[0]) + SLACK:
                drawn = [path[0], *(b for a, b in pairwise(path) if b != a)]
                found.append(f"input {at}: {part} turned back, drawn at {drawn}")
    return found


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_every_part_of_a_floating_box_moves_one_way_per_input(engine, request, serve):
    """Whatever the edit, wherever the box stands against the window's foot, and
    whether the next key waits for the last one's motion or lands while it runs, each
    painted part of the box travels one way per input on each axis: its outline's
    edges, its controls and its words (`motion_watch.js`)."""
    browser = request.getfixturevalue(engine)
    url = serve(LOW_PASSAGE_PAGE, events=[LONG_THREAD_ROOT])

    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(
        composer=st.sampled_from(sorted(COMPOSERS)),
        gap=st.integers(-40, 120),
        draft=st.lists(WORDS, max_size=30).map(" ".join),
        edits=st.lists(EDITS, min_size=1, max_size=4),
        quick=st.booleans(),
    )
    @example(
        composer="card",
        gap=10,
        draft="A first line.",
        edits=[("Shift+Enter",), ("Backspace", 1)],
        quick=False,
    )
    @example(composer="comment", gap=0, draft="", edits=[("Shift+Enter",)], quick=False)
    def moves_one_way(composer, gap, draft, edits, quick):
        page = open_page(browser, url, init_script=MOTION_WATCH)
        try:
            page.emulate_media(reduced_motion="no-preference")
            resized(page, 1440, 900)
            field = open_composer(page, composer)
            if draft:
                write(field, draft)
            at_rest(page, composer)
            stand_foot(page, composer, gap)
            field.focus()
            page.evaluate("parts => lfMotionWatch.begin(parts)", COMPOSERS[composer])
            marks = []
            for edit in edits:
                for press in [edit[0]] * (edit[1] if edit[0] == "Backspace" else 1):
                    marks.append(page.evaluate("() => lfMotionWatch.inputs()"))
                    if press == "type":
                        page.keyboard.type(" " + edit[1])
                    elif press == "paste":
                        page.keyboard.insert_text("\n".join([edit[1]] * edit[2]))
                    else:
                        page.keyboard.press(press)
                    if quick:
                        page.wait_for_timeout(80)
                    else:
                        at_rest(page, composer)
            at_rest(page, composer)
            page.wait_for_timeout(100)
            frames = page.evaluate("() => lfMotionWatch.end()")
            assert sum("outline top" in frame["parts"] for frame in frames) > 3, (
                "the watch read no frames of the box"
            )
            found = jerks(frames, marks)
            assert not found, "\n".join(found[:8])
        finally:
            page.close()

    moves_one_way()
