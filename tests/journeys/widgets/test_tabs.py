"""Tests scheduled by the measured cost of their boundary."""

from playwright.sync_api import expect
from render_harness import (
    leaf_page,
    open_page,
    resized,
    scroll_settled,
)

from leaf.render_checks import rendered


def test_a_side_list_workspace_scrolls_its_list_and_its_item_apart(browser, serve):
    """A side list that is a workspace's body fills the window, and its list and its open
    item each scroll on their own, as a mail client's do: the page does not scroll,
    reading keys in the item move the item and not the list, and walking down a long
    list keeps the selected row in view and leaves the item where it stands. Where the
    list stacks over the item, as a large root font makes it in a narrow workspace, the
    item takes the room below the list rather than standing over it."""
    tickets = "".join(
        f'<lf-tab id="t-{n}" label="Ticket {n}" summary="sev {n % 3}">'
        + "".join(
            f'<p id="p-{n}-{line}">Line {line} of what went wrong with ticket {n}.</p>'
            for line in range(40)
        )
        + "</lf-tab>"
        for n in range(30)
    )
    source = leaf_page(
        "a long queue",
        f'<header><h1>Queue</h1></header><lf-tabs id="queue" list="side">{tickets}'
        "</lf-tabs>",
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 1280, 720)
    state = """() => {
      const strip = document.querySelector('#queue > .lf-tabstrip');
      const item = document.querySelector('#queue > lf-tab:not([hidden])');
      const selected = strip.querySelector('[aria-selected="true"]').getBoundingClientRect();
      const room = strip.getBoundingClientRect();
      return {page: document.scrollingElement.scrollHeight - innerHeight,
              list: [strip.scrollTop, strip.scrollHeight - strip.clientHeight],
              item: [item.scrollTop, item.scrollHeight - item.clientHeight],
              itemTop: item.getBoundingClientRect().top,
              stripBottom: room.bottom,
              selectedShown: selected.top >= room.top - 1 && selected.bottom <= room.bottom + 1};
    }"""
    before = page.evaluate(state)
    assert before["page"] <= 0, before
    assert before["list"][1] > 0 and before["item"][1] > 0, before

    page.locator("#p-0-2").click()
    page.keyboard.press("d")
    page.wait_for_function("() => document.querySelector('#t-0').scrollTop > 0")
    read = page.evaluate(state)
    assert read["list"][0] == 0 and read["page"] <= 0, read
    # Reading on while the window is too narrow to fill, where the page carries the
    # item, moves the place the item keeps when the workspace fills the window again.
    top_line = """() => {
      const item = document.querySelector('#t-0');
      const top = Math.max(item.getBoundingClientRect().top, 60);
      return [...item.querySelectorAll('p')]
        .findIndex(p => p.getBoundingClientRect().bottom > top + 2);
    }"""
    resized(page, 700, 720)
    rendered(page)
    narrow = page.evaluate(top_line)
    page.keyboard.press("d")
    page.wait_for_function(f"() => ({top_line})() > {narrow + 4}")
    # The place is recorded once the scroll rests, so the read and the resize wait
    # for that rather than landing mid-scroll.
    scroll_settled(page)
    rendered(page)
    read_on = page.evaluate(top_line)
    resized(page, 1280, 720)
    rendered(page)
    widened = page.evaluate(top_line)
    assert abs(widened - read_on) <= 2, (narrow, read_on, widened)

    page.get_by_role("tab", name="Ticket 0").focus()
    for _ in range(20):
        page.keyboard.press("ArrowDown")
    expect(page.get_by_role("tab", name="Ticket 20")).to_have_attribute(
        "aria-selected", "true"
    )
    walked = page.evaluate(state)
    assert walked["list"][0] > 0 and walked["selectedShown"], walked
    assert walked["itemTop"] == before["itemTop"] and walked["page"] <= 0, walked

    # A reader's large root font, there from first paint: a script setting it on the
    # open page would move the page without input.
    large = "<style>html { font-size: 20px }</style></head>"
    page = open_page(browser, serve(source.replace("</head>", large, 1)))
    resized(page, 730, 600)
    page.wait_for_function(
        """() => {
          const strip = document.querySelector('#queue > .lf-tabstrip').getBoundingClientRect();
          const item = document.querySelector('#queue > lf-tab:not([hidden])').getBoundingClientRect();
          return strip.right > item.left + 1 && item.top >= strip.bottom - 1;
        }"""
    )
    stacked = page.evaluate(state)
    assert stacked["page"] <= 0 and stacked["item"][1] > 0, stacked
