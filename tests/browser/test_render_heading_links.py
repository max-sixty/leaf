"""A heading the page gives an address offers a link to it (heading-links.js)."""

import re

from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import leaf_page, open_page, select_words, told

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
        "option", name="Copy link to section", exact=True
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


def test_each_shown_link_stands_by_its_heading(browser, serve):
    """A link stands in the gutter beside its own heading wherever it shows: for the
    heading the user is on and the one under the pointer at once, after a press while
    focus stays in it, beside a heading whose author named it for a box of their own,
    which stays where the author put it, after another box anchored to a heading while
    its link showed, and beside a heading the author's stylesheet names only after its
    link first showed."""
    source = leaf_page(
        "Links",
        '<section id="a"><h2>First</h2><p>Words.</p></section>'
        '<section id="b"><h2>Second</h2><p>Words.</p></section>'
        '<section id="c"><h2 id="named">Named</h2><p>Words.</p>'
        '<p class="tag">Tag</p></section>'
        '<section id="d"><h2>Fourth</h2><p>Words.</p></section>'
        '<section id="e"><h2 id="late">Late</h2><p>Words.</p></section>',
        head="<style>#named { anchor-name: --mine; } .tag { position: absolute;"
        " position-anchor: --mine; top: anchor(bottom); left: anchor(right); }"
        " #late.anchored { anchor-name: --late; }</style>",
    )
    page = open_page(browser, live_url(serve(source)))
    links = page.locator(LINK)

    def standing():
        """Each shown link's heading, by the heading's text, where it stands beside
        that heading's first line."""
        return page.evaluate(
            """(selector) => [...document.querySelectorAll(selector)]
              .filter((link) => getComputedStyle(link).opacity === "1")
              .map((link) => {
                const box = link.getBoundingClientRect();
                const middle = (box.top + box.bottom) / 2;
                const heading = [...document.querySelectorAll("h2")].find((h) => {
                  const at = h.getBoundingClientRect();
                  return at.top <= middle && middle <= at.bottom &&
                    box.right <= at.left + 0.5 && at.left - box.right < 48;
                });
                return heading?.textContent ?? null;
              })
              .sort()""",
            LINK,
        )

    tag = page.locator(".tag").bounding_box()
    page.locator("#named").hover()
    expect(links).to_have_count(1)
    assert standing() == ["Named"]
    assert page.locator(".tag").bounding_box() == tag

    page.evaluate(
        "const h = document.querySelector('#a > h2'); h.tabIndex = -1; h.focus()"
    )
    page.locator("#b > h2").hover()
    expect(links).to_have_count(3)
    assert standing() == ["First", "Second"]

    # A press leaves focus in the link's button, which keeps it shown when the pointer
    # moves on to another heading.
    links.nth(2).get_by_role("button").click()
    page.locator("#named").hover()
    assert standing() == ["Named", "Second"]
    page.mouse.move(2, 2)
    assert standing() == ["Second"]
    assert page.locator(".tag").bounding_box() == tag

    # Words selected in a heading under the pointer bring the anchored comment box,
    # which names the heading while its link shows. The link the pointer then shows
    # for an earlier heading stands by that heading, not by the one the box named.
    page.mouse.click(2, 2)
    select_words(page, "#d > h2")
    assert standing() == ["Fourth"]
    page.locator("#a > h2").hover()
    assert standing() == ["First"]

    # A rule of the author's that starts naming a heading after its link first showed,
    # here through a class the page's script adds, keeps its name and outranks the
    # runtime's sheet, so the link stands by the heading under a name beside it.
    page.locator("#late").hover()
    assert standing() == ["Late"]
    page.mouse.move(2, 2)
    page.evaluate("document.querySelector('#late').classList.add('anchored')")
    page.locator("#late").hover()
    assert standing() == ["Late"]
    names = page.locator("#late").evaluate("h => getComputedStyle(h).anchorName")
    assert "--late" in names.split(", ")


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
