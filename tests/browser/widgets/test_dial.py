"""A detail dial: Skim folds all but the headings and gists and keeps the reader's place,
⋯ unfolds one section, Everything opens every closed detail, and Read takes back
exactly what the dial changed."""

import pytest
from playwright.sync_api import expect
from render_harness import leaf_page, open_page

pytestmark = pytest.mark.shifts_unsurveyed


def section(name, paragraphs):
    body = "".join(
        f'<p id="{name}-{n}">{f"Supporting detail for {name}. " * 30}</p>'
        for n in range(paragraphs)
    )
    return (
        f'<section id="{name}"><h2>{name.title()}</h2>'
        f'<p class="gist" id="{name}-gist">The {name} section concludes this.</p>'
        f'{body}<details id="{name}-more"><summary>Method</summary><p>How.</p></details>'
        "</section>"
    )


# Long enough that the page still scrolls at Skim, so the place can be kept.
SECTIONS = ("impact", "cause", "fix", "timeline", "method", "owners", "followups")
DIAL_PAGE = leaf_page(
    "Dial",
    '<h1>Report</h1><p class="lede">What happened.</p><lf-dial id="dial"></lf-dial>'
    + "".join(section(name, 3) for name in SECTIONS),
)


def depth(page, label):
    """Press a depth with the pointer where it stands, as the reader does."""
    box = page.locator("lf-dial .lf-dial-depth", has_text=label).bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def top(page, selector):
    """Where the node stands once the blocks have finished gliding into place."""
    page.wait_for_function("() => document.getAnimations().length === 0")
    return page.locator(selector).evaluate("node => node.getBoundingClientRect().top")


def test_depths_fold_keep_the_place_and_restore(browser, serve):
    """Skim leaves the headings, lede and gists, and the gist of the paragraph at the
    reading line lands where that paragraph stood; ⋯ shows one section; Everything opens
    the closed details; Read takes every fold, marker and opened detail back."""
    page = open_page(browser, serve(DIAL_PAGE))
    folded = page.locator("[data-lf-dial-folded]")
    markers = page.locator(".lf-dial-more")

    page.locator("#cause-1").evaluate(
        "p => document.scrollingElement.scrollTop += "
        "p.getBoundingClientRect().top - innerHeight * 0.25 + 10"
    )
    reading = top(page, "#cause-1")
    depth(page, "Skim")
    expect(page.locator("lf-dial .lf-dial-depth", has_text="Skim")).to_have_attribute(
        "aria-pressed", "true"
    )
    # Each section's three paragraphs and its closed detail.
    expect(folded).to_have_count(4 * len(SECTIONS))
    for name in ("impact", "cause", "fix"):
        expect(page.locator(f"#{name} h2")).to_be_visible()
        expect(page.locator(f"#{name}-gist")).to_be_visible()
        expect(page.locator(f"#{name}-0")).to_be_hidden()
    expect(markers).to_have_count(len(SECTIONS))
    assert abs(top(page, "#cause-gist") - reading) < 2

    page.locator("#cause-gist + .lf-dial-more button").click()
    expect(page.locator("#cause-0")).to_be_visible()
    expect(page.locator("#impact-0")).to_be_hidden()
    expect(page.locator("#cause-0")).to_be_focused()

    depth(page, "Everything")
    expect(folded).to_have_count(0)
    expect(page.locator("details[open]")).to_have_count(len(SECTIONS))

    depth(page, "Read")
    expect(folded).to_have_count(0)
    expect(markers).to_have_count(0)
    expect(page.locator("details[open]")).to_have_count(0)
    expect(page.locator("main [hidden]")).to_have_count(0)
