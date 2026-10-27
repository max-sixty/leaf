"""A heading the page gives an address offers a link to it (heading-links.js)."""

import re

from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import leaf_page, open_page, told

LINK = ".lf-chrome .lf-heading-link"
SOURCE = leaf_page(
    "Heading links",
    '<section id="rates%2Flimits"><h2>Rate limits <a id="plans" href="#words">by plan</a></h2>'
    '<p id="words">The limits, by plan.</p></section>'
    "<section><h2>Unaddressed</h2><p>Words.</p></section>",
)


def shown(page):
    return page.locator(LINK).evaluate_all(
        "nodes => nodes.filter(node => getComputedStyle(node).opacity === '1').length"
    )


def copied(page):
    return page.evaluate("navigator.clipboard.readText()")


def until_copied(page, link):
    page.wait_for_function(
        "link => navigator.clipboard.readText().then(text => text === link)", arg=link
    )


def test_a_heading_copies_the_link_to_the_section_it_opens(browser, serve):
    url = live_url(serve(SOURCE))
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = open_page(browser, url, context=context)

    # A pointer over the heading shows its link, which takes the pointer onto it.
    page.locator("section[id] > h2").hover()
    expect(page.locator(LINK)).to_have_count(1)
    assert shown(page) == 1
    page.locator(LINK).get_by_role("button", name="Copy link to section").click()
    link = page.url.split("#")[0] + "#rates%252Flimits"
    # The page's own address, which carries no access key (bootstrap.js), and a
    # fragment that names the section.
    until_copied(page, link)
    page.evaluate("link => { location.href = link }", link)
    expect(page.locator("section[id]")).to_be_focused()

    # A heading the page gave no address has no link.
    page.locator("section:not([id]) > h2").hover()
    expect(page.locator(LINK)).to_have_count(1)

    # Being on the section shows no mark, since a route such as `m` lands there to act
    # on it. Enter copies its link and shows the mark with its result, and the command
    # reference names it.
    page.evaluate("navigator.clipboard.writeText('')")
    page.locator("section[id]").focus()
    assert shown(page) == 0
    page.keyboard.press("Enter")
    until_copied(page, link)
    assert shown(page) == 1
    page.evaluate("navigator.clipboard.writeText('')")
    page.keyboard.press("?")
    page.locator(".lf-command-reference").get_by_role(
        "button", name="Copy link to section", exact=True
    ).click()
    until_copied(page, link)

    # On the words inside the section, and on a link in its heading, Enter is theirs.
    page.keyboard.press("Escape")
    page.evaluate("navigator.clipboard.writeText('')")
    page.evaluate(
        "const p = document.getElementById('words'); p.tabIndex = -1; p.focus()"
    )
    page.keyboard.press("Enter")
    page.locator("#plans").focus()
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"#words$"))
    assert copied(page) == ""

    # A revision that takes the section's address away takes its link with it.
    (serve.page_dir / "index.html").write_text(
        SOURCE.replace(' id="rates%2Flimits"', "")
    )
    told(page)
    page.mouse.move(2, 2)
    page.locator("h2").first.hover()
    expect(page.locator(LINK)).to_have_count(0)


def test_a_tap_shows_a_headings_link_and_a_second_tap_copies_it(browser, serve):
    url = live_url(serve(SOURCE))
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        has_touch=True,
        is_mobile=True,
        permissions=["clipboard-read", "clipboard-write"],
    )
    page = open_page(browser, url, context=context)
    page.evaluate("navigator.clipboard.writeText('')")
    heading = page.locator("section[id] > h2")
    box = heading.bounding_box()
    # The tap lands where the link will show: the heading's far end, since a phone's
    # gutter has no room for it. Showing the link copies nothing.
    page.touchscreen.tap(box["x"] + box["width"] - 8, box["y"] + box["height"] / 2)
    expect(page.locator(LINK)).to_have_count(1)
    assert shown(page) == 1
    assert copied(page) == ""
    page.locator(LINK).get_by_role("button", name="Copy link to section").tap()
    until_copied(page, page.url.split("#")[0] + "#rates%252Flimits")


def test_enter_copies_a_link_no_pointer_has_shown(browser, serve):
    """Enter on a decision `m` landed on copies its link, though the press itself makes
    the link's control, which has not drawn its button yet."""
    source = leaf_page(
        "A decision's link",
        '<lf-ask id="q"><h3>Which store?</h3><lf-options id="c" choose>'
        '<lf-option id="a">Redis</lf-option><lf-option id="b">Postgres</lf-option>'
        "</lf-options></lf-ask>",
    )
    url = live_url(serve(source))
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = open_page(browser, url, context=context)
    page.keyboard.press("m")
    expect(page.locator("#q")).to_be_focused()
    page.keyboard.press("Enter")
    until_copied(page, page.url.split("#")[0] + "#q")
