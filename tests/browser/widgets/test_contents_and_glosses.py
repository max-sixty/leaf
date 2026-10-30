"""The table of contents, its document map and glosses: the widgets that route a reader
through the page's outline and explain its phrases."""

import re
from itertools import pairwise

import pytest
from interact_support import append_command
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    RELEASE_FOCUS,
    leaf_page,
    open_page,
    open_threads,
    resized,
    scroll_settled,
    told,
)

from leaf.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


def contents_page(title, body, *, toc_id="contents"):
    """A native sidebar track beside the authored document column."""
    return leaf_page(
        title,
        '<aside id="route"><div class="layout-track" id="route-track">'
        f'<lf-toc id="{toc_id}"></lf-toc></div></aside>'
        f'<div class="layout-column">{body}</div>',
        layout="sidebar",
    )


def test_a_table_of_contents_reads_the_page_outline_and_reveals_its_heading(
    browser, serve
):
    """The authored element is only a request for navigation. The module reads the
    page's headings in document order, keeps their relative depth, and gives an
    id-less heading an id reserved for the runtime, on the heading itself, so nothing
    is added among the page's own elements. A real fragment link lets the browser reveal
    a heading in a closed disclosure, so it is reachable rather than merely named."""
    source = leaf_page(
        "contents",
        """
<h1>Migration plan</h1>
<lf-toc id="contents"></lf-toc>
<section><h2 id="prepare">Prepare <lf-gloss tip="One cohort at a time.">gradually</lf-gloss></h2><p>Take a snapshot.</p></section>
<details style="margin-top: 110vh">
  <summary>Implementation detail</summary>
  <h3>Move the readers</h3>
  <p>Shift one cohort at a time.</p>
</details>
<section style="margin-bottom: 110vh"><h2>Verify</h2><p>Compare the totals.</p></section>
""",
    )
    url = serve(source)
    page = open_page(browser, url)
    toc = page.get_by_role("navigation", name="On this page")
    toc.locator("summary").click()

    expect(toc.get_by_role("link")).to_have_count(3)
    assert toc.get_by_role("link").all_text_contents() == [
        "Prepare gradually",
        "Move the readers",
        "Verify",
    ]
    assert toc.locator("li").evaluate_all(
        "nodes => nodes.map(node => node.dataset.lfDepth)"
    ) == ["0", "1", "0"]
    assert page.locator("h2, h3").evaluate_all(
        "nodes => nodes.map(node => node.getAttribute('id'))"
    ) == ["prepare", "lf-contents-section-2", "lf-contents-section-3"]

    hrefs = toc.get_by_role("link").evaluate_all(
        "links => links.map(link => link.getAttribute('href'))"
    )
    assert hrefs[0] == "#prepare"
    assert hrefs[1] == "#lf-contents-section-2"

    # The heading stays its section's first child, so its collapsed top margin is not
    # trapped inside an otherwise transparent section: both begin at the same edge.
    verify_geometry = page.get_by_role("heading", name="Verify").evaluate(
        """heading => ({
          sectionTop: heading.parentElement.getBoundingClientRect().top,
          headingTop: heading.getBoundingClientRect().top,
        })"""
    )
    assert max(verify_geometry.values()) - min(verify_geometry.values()) < 0.5, (
        verify_geometry
    )

    details = page.locator("main > details")
    expect(details).not_to_have_attribute("open", "")
    toc.get_by_role("link", name="Move the readers").click()
    expect(details).to_have_attribute("open", "")
    expect(page).to_have_url(re.compile(f"{re.escape(hrefs[1])}$"))
    scroll_settled(page)
    top = page.locator("h3").evaluate("heading => heading.getBoundingClientRect().top")
    assert 0 <= top < 150, f"the revealed heading stopped at {top}px"

    # The title is a visible page label, while each repeated heading is the label of a
    # browser-owned link under .lf-ui. The authored heading remains the one passage.
    spoken = page.locator("main").evaluate(
        "async main => (await window.__lfWidgetApi()).says(main)"
    )
    assert spoken.count("Prepare gradually") == 1
    assert spoken.count("Move the readers") == 1
    assert spoken.count("Verify") == 1
    expect(toc).to_have_class(re.compile(r"\blf-ui\b"))
    expect(toc).to_have_attribute("data-lf-gen", "1")
    page.close()

    # On first parse this id does not exist yet. The shared arrival pass runs after every
    # widget settles, so a copied link still reveals and reaches the heading it names.
    direct = open_page(browser, url + hrefs[1])
    expect(direct.locator("main > details")).to_have_attribute("open", "")
    expect(direct).to_have_url(re.compile(f"{re.escape(hrefs[1])}$"))
    direct.wait_for_function(
        "heading => { const box = heading.getBoundingClientRect(); "
        "return box.top >= 0 && box.bottom <= innerHeight; }",
        arg=direct.locator("h3").element_handle(),
    )
    assert direct.locator("h3").evaluate(
        "heading => { const box = heading.getBoundingClientRect(); "
        "return box.top >= 0 && box.bottom <= innerHeight; }"
    )


def test_contents_in_a_view_lists_its_topic_and_reveals_closed_details(
    browser, serve, subtests
):
    """Each view owns its outline, including a view nested inside another view.

    Visibility is not scope: a closed disclosure's heading remains a destination.
    """
    source = leaf_page(
        "topic contents",
        """
<h1>Field guide</h1>
<lf-tabs id="topics">
  <lf-tab id="prepare-topic" label="Prepare">
    <lf-toc id="prepare-contents"></lf-toc>
    <h2 id="inventory">Take inventory</h2>
    <details id="preparation-details">
      <summary>Detailed preparation</summary>
      <h3 id="snapshot">Save a snapshot</h3>
    </details>
  </lf-tab>
  <lf-tab id="operate-topic" label="Operate">
    <h2 id="operation">Run the operation</h2>
    <lf-tabs id="operation-views">
      <lf-tab id="monitor-view" label="Monitor">
        <lf-toc id="monitor-contents"></lf-toc>
        <h3 id="watch">Watch the readers</h3>
      </lf-tab>
      <lf-tab id="finish-view" label="Finish">
        <h3 id="verify">Verify the result</h3>
      </lf-tab>
    </lf-tabs>
  </lf-tab>
</lf-tabs>
""",
    )
    page = open_page(browser, serve(source))
    contents = page.locator("#prepare-contents")
    contents.locator("summary").click()
    with subtests.test(scope="topic"):
        assert contents.locator("li a").all_text_contents() == [
            "Take inventory",
            "Save a snapshot",
        ]
    contents.get_by_role("link", name="Save a snapshot").click()
    expect(page.locator("#preparation-details")).to_have_attribute("open", "")
    expect(page.locator("#snapshot")).to_be_visible()

    page.get_by_role("tab", name="Operate", exact=True).click()
    nested_contents = page.locator("#monitor-contents")
    nested_contents.locator("summary").click()
    with subtests.test(scope="nested view"):
        assert nested_contents.locator("li a").all_text_contents() == [
            "Watch the readers"
        ]
    nested_contents.get_by_role("link", name="Watch the readers").click()
    expect(page).to_have_url(re.compile(r"#watch$"))


def test_contents_addresses_a_title_group_and_maps_its_complete_box(browser, serve):
    """The heading supplies words; its group supplies the destination and map origin.

    A grouped section title still belongs to the identified section it titles. Marker
    centers and the viewport lens share one coordinate, including the track's origin.
    """
    source = contents_page(
        "grouped contents titles",
        """
<hgroup id="page-title">
  <p class="eyebrow">Eval consolidation</p>
  <h1 id="title-label">One catalog, with short cases and complete workflows</h1>
</hgroup>

<div style="height: 110vh"></div>
<hgroup id="standalone-title">
  <p class="eyebrow">One vocabulary</p>
  <h2 id="standalone-label">Name each case</h2>
</hgroup>
<p>The whole title arrives together.</p>
<div style="height: 110vh"></div>
<section id="owned-section">
  <hgroup id="owned-title">
    <p class="eyebrow">One command</p>
    <h2 id="owned-label">Run each case</h2>
  </hgroup>
  <p>The fragment names the section that owns this title.</p>
</section>
<div style="height: 110vh"></div>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page")
    start = nav.locator(".lf-toc-start a")
    expect(start).to_have_text("One catalog, with short cases and complete workflows")
    expect(start).to_have_attribute("href", "#page-title")
    standalone = nav.get_by_role("link", name="Name each case", exact=True)
    expect(standalone).to_have_attribute("href", "#standalone-title")
    expect(nav.get_by_role("link", name="Run each case", exact=True)).to_have_attribute(
        "href", "#owned-section"
    )

    geometry = nav.evaluate(
        """nav => {
          const rows = nav.querySelector('.lf-toc-rows');
          const start = nav.querySelector('.lf-toc-start');
          const marker = getComputedStyle(start, '::before');
          const title = document.querySelector('#page-title');
          return {
            trackTop: rows.getBoundingClientRect().top,
            markerCenter: start.getBoundingClientRect().top +
              parseFloat(marker.top) + new DOMMatrixReadOnly(marker.transform).m42 +
              parseFloat(marker.height) / 2,
            lensTop: nav.querySelector('.lf-toc-window').getBoundingClientRect().top,
            titleTop: title.getBoundingClientRect().top,
            headingTop: title.querySelector('h1').getBoundingClientRect().top,
            nextTitleTop: document.querySelector('#standalone-title').getBoundingClientRect().top,
            startSpan: Number(start.style.getPropertyValue('--lf-toc-span')),
          };
        }"""
    )
    assert geometry["headingTop"] > geometry["titleTop"], geometry
    assert geometry["startSpan"] == pytest.approx(
        geometry["nextTitleTop"] - geometry["titleTop"], abs=1
    ), geometry
    assert geometry["markerCenter"] == pytest.approx(geometry["trackTop"], abs=1), (
        geometry
    )
    assert geometry["lensTop"] == pytest.approx(geometry["markerCenter"], abs=1), (
        geometry
    )

    # Native fragment navigation brings the eyebrow with the heading; the viewport
    # lens meets that destination's marker rather than the top of its link box.
    standalone.focus()
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"#standalone-title$"))
    scroll_settled(page)
    expect(standalone).to_have_attribute("aria-current", "location")
    alignment = standalone.evaluate(
        """link => {
          const row = link.parentElement;
          const marker = getComputedStyle(row, '::before');
          return {
            markerCenter: row.getBoundingClientRect().top +
              parseFloat(marker.top) + new DOMMatrixReadOnly(marker.transform).m42 +
              parseFloat(marker.height) / 2,
            lensTop: link.closest('nav').querySelector('.lf-toc-window')
              .getBoundingClientRect().top,
            eyebrowTop: document.querySelector('#standalone-title .eyebrow')
              .getBoundingClientRect().top,
          };
        }"""
    )
    assert alignment["eyebrowTop"] >= 0, alignment
    assert alignment["lensTop"] == pytest.approx(alignment["markerCenter"], abs=2), (
        alignment
    )


def test_contents_with_every_destination_hidden_returns_when_the_disclosure_opens(
    browser, serve
):
    """An empty displayed route has no current destination, then recovers on reveal."""
    source = leaf_page(
        "closed contents",
        """
<details>
  <summary>Open the migration plan</summary>
  <div class="layout-sidebar"><aside><div class="layout-track">
    <lf-toc id="contents"></lf-toc>
  </div></aside><div class="layout-column"><h1>Migration plan</h1>
  <h2 id="prepare">Prepare the readers</h2>
  <div style="height: 110vh"></div>
  <h2 id="verify">Verify both copies</h2>
  <div style="height: 110vh"></div>
</div></div></details>
""",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page", include_hidden=True)
    expect(nav).to_be_hidden()
    expect(nav.locator("[aria-current]")).to_have_count(0)
    page.evaluate("""() => {
      window.firstContentsReveal = null;
      const observer = new ResizeObserver(() => {
        if (!document.querySelector('main > details').open) return;
        const nav = document.querySelector('#contents');
        firstContentsReveal = {
          hidden: nav.querySelectorAll('[data-lf-toc-hidden]').length,
          current: nav.querySelector('[aria-current]')?.textContent,
        };
        observer.disconnect();
      });
      observer.observe(document.querySelector('main'));
    }""")
    page.get_by_text("Open the migration plan", exact=True).click()
    expect(nav).to_be_visible()
    page.wait_for_function("firstContentsReveal !== null")
    first_reveal = page.evaluate("firstContentsReveal")
    assert first_reveal == {"hidden": 0, "current": "Migration plan"}
    expect(nav.locator(".lf-toc-start a")).to_have_attribute("aria-current", "location")
    expect(nav.locator("[data-lf-toc-hidden]")).to_have_count(0)
    page.get_by_text("Open the migration plan", exact=True).click()
    expect(nav).to_be_hidden()
    expect(nav.locator("[aria-current]")).to_have_count(0)


def test_contents_reconciles_live_title_boundaries_and_preserves_its_reading_position(
    browser, serve
):
    """A retained ToC follows the current authored outline without replacing its links.

    Grouping a title changes its destination, and adding, dropping or renaming a heading
    changes the route. Surviving links retain focus and the outline's native scroll.
    """
    title = '<p class="eyebrow">Stage</p><h1 id="title">Report</h1>'
    sections = [
        f'<section id="part-{index}"><h2 id="label-{index}">Migration part {index}</h2></section>'
        for index in range(1, 81)
    ]
    source = contents_page(
        "live contents",
        title + '<h2 id="body-title">Body</h2>' + "".join(sections),
    )
    page = open_page(browser, live_url(serve(source)))
    resized(page, 1400, 900)
    toc = page.locator("#contents")
    nav = page.get_by_role("navigation", name="On this page")
    start = nav.locator(".lf-toc-start a")
    expect(start).to_have_attribute("href", "#title")
    expect(toc).to_have_attribute("data-lf-outline", "")
    expect(nav.locator("a")).to_have_count(82)
    body = nav.get_by_role("link", name="Body", exact=True)
    expect(body).to_have_attribute("href", "#body-title")
    held_body = body.element_handle()
    survivor = nav.get_by_role("link", name="Migration part 80", exact=True)
    survivor.focus()
    expect(survivor).to_be_focused()
    held_survivor = survivor.element_handle()
    reading_position = nav.evaluate("node => node.scrollTop")
    assert reading_position > 0

    grouped = source.replace(
        title, f'<hgroup id="title-group">{title}</hgroup>'
    ).replace(
        '<h2 id="body-title">Body</h2>',
        '<hgroup id="body-group"><p class="eyebrow">One section</p>'
        '<h2 id="body-title">Named body</h2></hgroup>',
    )
    (serve.page_dir / "index.html").write_text(grouped, encoding="utf-8")
    told(page)
    rendered(page)
    expect(start).to_have_attribute("href", "#title-group")
    renamed_body = nav.get_by_role("link", name="Named body", exact=True)
    expect(renamed_body).to_have_attribute("href", "#body-group")
    assert held_body.evaluate(
        "held => held === document.querySelector('#contents a[href=\"#body-group\"]')"
    )
    assert held_survivor.evaluate("held => held === document.activeElement")
    assert nav.evaluate("node => node.scrollTop") == pytest.approx(
        reading_position, abs=1
    )

    changed = grouped.replace(
        sections[39],
        '<section id="new-part"><h2>New destination</h2></section>',
    ).replace("Migration part 41", "Renamed destination")
    (serve.page_dir / "index.html").write_text(changed, encoding="utf-8")
    told(page)
    rendered(page)
    expect(nav.locator("a")).to_have_count(82)
    expect(nav.get_by_role("link", name="Migration part 40", exact=True)).to_have_count(
        0
    )
    expect(
        nav.get_by_role("link", name="New destination", exact=True)
    ).to_have_attribute("href", "#new-part")
    expect(
        nav.get_by_role("link", name="Renamed destination", exact=True)
    ).to_have_attribute("href", "#part-41")
    assert held_survivor.evaluate(
        "held => held === document.activeElement && held === "
        "document.querySelector('#contents a[href=\"#part-80\"]')"
    )
    assert nav.evaluate("node => node.scrollTop") == pytest.approx(
        reading_position, abs=1
    )

    reordered = changed.replace(
        sections[78] + sections[79], sections[79] + sections[78]
    )
    (serve.page_dir / "index.html").write_text(reordered, encoding="utf-8")
    told(page)
    rendered(page)
    expect(survivor).to_be_focused()
    assert (
        survivor.evaluate(
            "link => link.closest('li').nextElementSibling.querySelector('a').hash"
        )
        == "#part-79"
    )

    replacement = nav.get_by_role("link", name="New destination", exact=True)
    replacement.focus()
    changed_level = reordered.replace(
        "<h2>New destination</h2>", "<h3>New destination</h3>"
    )
    (serve.page_dir / "index.html").write_text(changed_level, encoding="utf-8")
    told(page)
    rendered(page)
    expect(replacement).to_have_attribute("href", "#new-part")
    expect(replacement).to_be_focused()

    renamed_body.focus()
    ungrouped = changed_level.replace(
        '<hgroup id="body-group"><p class="eyebrow">One section</p>'
        '<h2 id="body-title">Named body</h2></hgroup>',
        '<h2 id="body-title">Named body</h2>',
    )
    (serve.page_dir / "index.html").write_text(ungrouped, encoding="utf-8")
    told(page)
    rendered(page)
    expect(renamed_body).to_have_attribute("href", "#body-title")
    expect(renamed_body).to_be_focused()

    # An address edit on the current heading changes its Lit key. The new link
    # still stands for the same place the user was on.
    page.locator("#body-title").evaluate("node => node.id = 'renamed-body'")
    expect(renamed_body).to_have_attribute("href", "#renamed-body")
    expect(renamed_body).to_be_focused()


def test_an_empty_contents_route_follows_headings_arriving_and_leaving(browser, serve):
    """A ToC with no initial outline can present one later and retire it again."""
    source = contents_page(
        "changing contents",
        '<h1>Report</h1><p id="body">The body has no section headings.</p>',
    )
    page = open_page(browser, live_url(serve(source)))
    nav = page.get_by_role("navigation", name="On this page", include_hidden=True)
    expect(nav).to_be_hidden()
    expect(nav.locator("li a")).to_have_count(0)

    headed = source.replace(
        '<p id="body">', '<h2 id="arrived">An arriving section</h2><p id="body">'
    )
    (serve.page_dir / "index.html").write_text(headed, encoding="utf-8")
    told(page)
    rendered(page)
    expect(nav).to_be_visible()
    expect(nav.get_by_role("link", name="An arriving section")).to_have_attribute(
        "href", "#arrived"
    )

    shared_destination = headed.replace(
        '<h2 id="arrived">An arriving section</h2>',
        '<hgroup id="group"><h2>First title</h2><h3>Second title</h3></hgroup>',
    )
    (serve.page_dir / "index.html").write_text(shared_destination, encoding="utf-8")
    told(page)
    rendered(page)
    expect(nav.locator("li a")).to_have_text(["First title", "Second title"])
    assert nav.locator("li a").evaluate_all(
        "links => links.map(link => link.hash)"
    ) == ["#group", "#group"]
    second = nav.get_by_role("link", name="Second title", exact=True)
    second.focus()
    reordered = shared_destination.replace(
        "<h2>First title</h2><h3>Second title</h3>",
        "<h3>Second title</h3><h2>First title</h2>",
    )
    (serve.page_dir / "index.html").write_text(reordered, encoding="utf-8")
    told(page)
    rendered(page)
    expect(nav.locator("li a")).to_have_text(["Second title", "First title"])
    expect(second).to_be_focused()

    (serve.page_dir / "index.html").write_text(headed, encoding="utf-8")
    told(page)
    rendered(page)
    expect(nav.locator("li a")).to_have_text(["An arriving section"])

    (serve.page_dir / "index.html").write_text(source, encoding="utf-8")
    told(page)
    rendered(page)
    expect(nav).to_be_hidden()
    expect(nav.locator("li a")).to_have_count(0)
    expect(nav.locator("[aria-current]")).to_have_count(0)


def test_a_table_of_contents_link_is_a_finger_s_aim(browser, serve):
    """The open outline stacks its links with no gap between them, so each link's box
    is all there is to land on. Under a finger they stood 24px tall where the layer's
    floor is 44; a mouse keeps its compact rows."""
    source = leaf_page(
        "contents",
        """
<h1>Migration plan</h1>
<lf-toc id="contents"></lf-toc>
<section><h2 id="prepare">Prepare</h2><p>Take a snapshot.</p></section>
<section><h2 id="verify">Verify</h2><p>Compare the totals.</p></section>
""",
    )
    url = serve(source)
    heights = "links => links.map(link => link.getBoundingClientRect().height)"
    touch = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=touch)
    page.locator("lf-toc summary").tap()
    links = page.get_by_role("navigation", name="On this page").get_by_role("link")
    expect(links).to_have_count(2)
    assert all(h >= 44 for h in links.evaluate_all(heights))
    mouse = open_page(browser, url)
    mouse.locator("lf-toc summary").click()
    links = mouse.get_by_role("navigation", name="On this page").get_by_role("link")
    expect(links).to_have_count(2)
    assert all(24 <= h < 30 for h in links.evaluate_all(heights))


def test_a_table_of_contents_can_stop_at_an_authored_heading_level(browser, serve):
    """The author decides which semantic levels belong in the page route.

    Deeper headings remain ordinary page headings: the contents widget neither links
    them nor gives them a fragment id. A linked heading without an id of its own takes
    one reserved for the runtime, and nothing stands beside it, so a page rule about
    which element follows which still finds the page's own."""
    source = leaf_page(
        "bounded contents",
        """
<h1>Migration plan</h1>
<lf-toc id="contents" max-level="3"></lf-toc>
<section>
  <h2 id="prepare">Prepare the readers</h2>
  <h3>Move one cohort</h3>
  <h4>Verify its checksum</h4>
</section>
""",
    )
    page = open_page(browser, serve(source))
    toc = page.get_by_role("navigation", name="On this page")
    toc.locator("summary").click()

    assert toc.get_by_role("link").all_text_contents() == [
        "Prepare the readers",
        "Move one cohort",
    ]
    assert page.locator("h2, h3, h4").evaluate_all(
        "nodes => nodes.map(node => [node.localName, node.getAttribute('id'), "
        "node.previousElementSibling?.className || null])"
    ) == [
        ["h2", "prepare", None],
        ["h3", "lf-contents-section-2", None],
        ["h4", None, None],
    ]
    # That id is the runtime's, so a passage in the heading is addressed by the
    # section the page wrote, which the file can resolve too.
    # The user selects the heading's words.
    page.locator("h3").click(click_count=3)
    anchor = page.evaluate(
        """async () => {
          const { selectionAnchor } = await window.__lfCheckApi();
          return selectionAnchor(getSelection());
        }"""
    )
    assert anchor["quote"] == "Move one cohort", anchor
    assert not (anchor.get("section") or "").startswith("lf-"), anchor

    # A revision can give the heading an id of its own, or take it away again; the
    # row's link follows whichever id the heading carries.
    link = toc.get_by_role("link", name="Move one cohort")
    page.locator("h3").evaluate("heading => { heading.id = 'move'; }")
    expect(link).to_have_attribute("href", "#move")
    page.locator("h3").evaluate("heading => heading.removeAttribute('id')")
    expect(link).to_have_attribute("href", "#lf-contents-section-2")
    expect(page.locator("h3")).to_have_attribute("id", "lf-contents-section-2")


def test_generated_page_interface_reconciles_before_semantic_interaction(
    browser, serve
):
    """Generated interface paints while replay waits, then reconciles its geometry
    against the complete presented page before semantic interaction opens.

    The recorded draft makes the first section much taller during replay. The contents
    map has already painted the short authored form, so the presentation signal must
    replace that stale span in the same turn that releases durable interaction."""
    source = contents_page(
        "stable generated interface",
        """
<h1>Migration plan</h1>

<section>
  <h2 id="prepare">Prepare the readers</h2>
  <lf-draft id="notes"><pre>One short line.</pre></lf-draft>
</section>
<section>
  <h2 id="verify">Verify the readers</h2>
  <div style="height: 600px"></div>
</section>
""",
    )
    url = serve(source)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "notes",
            "action": "edit",
            "detail": {
                "value": "\n".join(
                    f"Migration checkpoint {number}." for number in range(1, 17)
                )
            },
        },
    )
    held = []
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.add_init_script(
        """
        window.__tocFirstPaint = null;
        new MutationObserver((records, observer) => {
          if (document.body?.dataset.lfPresented !== '1') return;
          const first = document.getElementById('prepare');
          const second = document.getElementById('verify');
          const nav = document.querySelector('.lf-toc-nav');
          const row = nav.querySelector('a[href="#prepare"]').parentElement;
          window.__tocFirstPaint = {
            visible: nav.checkVisibility({visibilityProperty: true}),
            span: Number(row.style.getPropertyValue('--lf-toc-span')),
            actual: second.getBoundingClientRect().top
              - first.getBoundingClientRect().top,
          };
          observer.disconnect();
        }).observe(document, {
          subtree: true,
          attributes: true,
          attributeFilter: ['data-lf-presented'],
        });
        """
    )
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(url, wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    assert held, "the positive control did not hold the first state response"
    nav = page.locator(".lf-toc-nav")
    expect(nav).to_be_visible()
    prepare = nav.locator('a[href="#prepare"]')
    page.wait_for_function(
        "link => Number(link.parentElement.style"
        ".getPropertyValue('--lf-toc-span')) > 0",
        arg=prepare.element_handle(),
    )
    authored_span = prepare.evaluate(
        "link => Number(link.parentElement.style.getPropertyValue('--lf-toc-span'))"
    )

    held.pop(0).continue_()
    page.wait_for_function("() => window.__tocFirstPaint !== null")
    first_paint = page.evaluate("() => window.__tocFirstPaint")
    assert first_paint["visible"], first_paint
    assert first_paint["actual"] > authored_span + 200, (
        authored_span,
        first_paint,
    )
    assert first_paint["span"] == pytest.approx(first_paint["actual"], abs=1)
    wait_until_ready(page)


def test_an_eyebrow_and_heading_keep_one_title_rhythm_through_contents(browser, serve):
    """An eyebrow is the heading's label, so its small bottom margin is the room inside
    the title while the heading level's larger top margin remains outside the pair.

    An identified section owns the contents destination while its heading supplies the
    label. The clean section fragment brings the whole title into view and needs no
    generated node between the eyebrow and heading."""
    source = leaf_page(
        "eyebrow title rhythm",
        """
<h1>Two labeled sections</h1>
<lf-toc id="contents"></lf-toc>
<div style="height: 110vh"></div>
<p id="before-two">First section follows.</p>
<section id="section-two" aria-labelledby="title-two">
  <p class="eyebrow">release shape</p>
  <h2 id="title-two">Prepare the readers</h2>
  <p>Take a snapshot.</p>
</section>
<div style="height: 110vh"></div>
<p id="before-three">A subsection follows.</p>
<section id="section-three">
  <p class="eyebrow">first cohort</p>
  <h3>Move the readers</h3>
  <p>Shift one cohort at a time.</p>
</section>
<div style="height: 110vh"></div>
""",
    )
    page = open_page(browser, serve(source))
    rhythm = page.evaluate(
        """() => Object.fromEntries([
          ['h2', ['section-two', 'before-two']],
          ['h3', ['section-three', 'before-three']],
        ].map(([level, [sectionId, beforeId]]) => {
          const section = document.getElementById(sectionId);
          const eyebrow = section.querySelector(':scope > .eyebrow');
          const heading = section.querySelector(`:scope > ${level}`);
          const before = document.getElementById(beforeId);
          const between = [];
          for (let node = eyebrow.nextElementSibling; node !== heading;
               node = node.nextElementSibling) between.push(node.className);
          const eyebrowBox = eyebrow.getBoundingClientRect();
          const headingBox = heading.getBoundingClientRect();
          return [level, {
            outer: eyebrowBox.top - before.getBoundingClientRect().bottom,
            inner: headingBox.top - eyebrowBox.bottom,
            between,
          }];
        }))"""
    )
    assert rhythm == {
        "h2": {"outer": 48, "inner": 10, "between": []},
        "h3": {"outer": 32, "inner": 10, "between": []},
    }

    toc = page.get_by_role("navigation", name="On this page")
    toc.locator("summary").click()
    assert toc.get_by_role("link").evaluate_all(
        "links => links.map(link => link.getAttribute('href'))"
    ) == ["#section-two", "#section-three"]
    expect(page.locator("#section-two")).to_have_attribute(
        "aria-labelledby", "title-two"
    )
    expect(page.locator("#section-two > h2")).to_have_attribute("id", "title-two")
    toc.get_by_role("link", name="Move the readers").click()
    expect(page).to_have_url(re.compile(r"#section-three$"))
    scroll_settled(page)
    arrival = page.locator("#section-three").evaluate(
        """section => {
          const root = document.scrollingElement;
          const eyebrow = section.querySelector(':scope > .eyebrow');
          const heading = section.querySelector(':scope > h3');
          return {
            clear: parseFloat(getComputedStyle(root).scrollPaddingTop),
            margin: parseFloat(getComputedStyle(section).scrollMarginTop),
            section: section.getBoundingClientRect().top,
            eyebrow: eyebrow.getBoundingClientRect().top,
            heading: heading.getBoundingClientRect().top,
          };
        }"""
    )
    destination_top = arrival["clear"] + arrival["margin"]
    assert arrival["section"] == pytest.approx(destination_top, abs=1)
    assert arrival["eyebrow"] == pytest.approx(destination_top, abs=1)
    assert arrival["heading"] > arrival["eyebrow"]


def test_table_of_contents_history_is_native_back_and_forward(browser, serve):
    """A map link creates an ordinary fragment-history entry on the root scrollport.

    Back restores the reading position from before the click and Forward restores the
    fragment destination. The shared travel pass reveals the destination while the
    browser retains each entry's reading position."""
    source = contents_page(
        "native contents history",
        """
<h1>Migration plan</h1>

<section><h2 id="prepare">Prepare the readers</h2><div style="height: 900px"></div></section>
<section><h2 id="move">Move the readers</h2><div style="height: 900px"></div></section>
<section><h2 id="verify">Verify the readers</h2><div style="height: 600px"></div></section>
""",
        toc_id="history-contents",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 800)
    assert page.evaluate("history.scrollRestoration") == "auto"

    bookmark = 420
    page.evaluate(
        "top => document.scrollingElement.scrollTo({top, behavior: 'instant'})",
        bookmark,
    )
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 1", arg=bookmark
    )
    navigation = page.get_by_role("navigation", name="On this page")
    move = navigation.get_by_role("link", name="Move the readers")
    navigation_box = navigation.bounding_box()
    assert navigation_box is not None
    # At rest the map takes the pointer on its spine alone.
    page.mouse.move(
        navigation_box["x"] + 2,
        navigation_box["y"] + navigation_box["height"] / 2,
    )
    expect(move).to_have_css("pointer-events", "auto")
    move.click()
    expect(page).to_have_url(re.compile(r"#move$"))
    page.wait_for_function(
        "() => document.getElementById('move').getBoundingClientRect().top < 150"
    )
    destination = page.evaluate("document.scrollingElement.scrollTop")
    assert destination > bookmark + 400

    page.evaluate("history.back()")
    page.wait_for_function("() => location.hash === ''")
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2", arg=bookmark
    )

    page.evaluate("history.forward()")
    page.wait_for_function("() => location.hash === '#move'")
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2",
        arg=destination,
    )


def test_the_reading_map_returns_when_a_hidden_sidebar_comes_back(browser, serve):
    """A wrapper that leaves the box tree and returns leaves the map as it found it.

    An author whose sidebar has nothing to say on a narrow shell hides it, which is
    what the developer gallery does; narrowing the window across that floor and back
    removes the map's whole wrapper and puts it back. The
    map is restored from the page's own posture, not from anything the wrapper
    remembers, because a box that has been away answers a style query with the reading
    it left with: asking the wrapper cost the user the spine for the rest of the
    session — an outline of thirteen laid rows became a fifteen-pixel heading stub that
    no settle, scroll, or further toggle brought back."""
    source = contents_page(
        "hidden sidebar map",
        """
<style>
  @media (max-width: 1000px) { #route { display: none; } }
</style>
<h1>Migration plan for the readers already in flight</h1>

<section><h2 id="prepare">Prepare the copy</h2><p>Take a snapshot.</p></section>
<div style="height: 600px"></div>
<section><h2 id="move">Move each cohort</h2><p>Shift one cohort at a time.</p></section>
<div style="height: 600px"></div>
<section><h2 id="verify">Verify both readings</h2><p>Compare the totals.</p></section>
<div style="height: 600px"></div>
""",
    )
    context = browser.new_context(viewport={"width": 1200, "height": 900})
    page = open_page(browser, serve(source), context=context)
    toc = page.locator("#contents")
    nav = page.get_by_role("navigation", name="On this page")
    heading = nav.locator(".lf-toc-heading")

    def rows():
        return nav.locator("li").evaluate_all(
            "items => items.filter(item => item.getBoundingClientRect().height > 0)"
            ".length"
        )

    expect(toc).to_have_css("position", "fixed")
    expect(heading).to_be_hidden()
    settled = toc.bounding_box()
    assert settled is not None
    laid = rows()
    assert laid >= 3, f"the fixture laid only {laid} map rows to begin with"

    resized(page, 800, 900)
    # The authored media rule hides the complete native navigation track.
    expect(page.locator("#route")).to_have_css("display", "none")
    expect(toc).to_be_hidden()

    resized(page, 1200, 900)
    # The wrapper itself holds no height in this posture — the map inside it is fixed —
    # so its return is a display reading rather than a visible box.
    expect(page.locator("#route")).not_to_have_css("display", "none")
    expect(toc).to_have_css("position", "fixed")
    expect(heading).to_be_hidden()
    assert toc.bounding_box() == settled, (
        f"the map came back as {toc.bounding_box()} rather than {settled}"
    )
    assert rows() == laid, "the map came back without its rows"


def test_a_crowded_document_map_reveals_every_heading_on_one_fitted_scale(
    browser, serve
):
    """Crowded destinations remain a complete route when the user enters it.

    The raw document positions leave less than half a line between neighbors. The
    fitted scale keeps every heading, marker, and label distinct without overflowing."""
    sections = "\n".join(
        f"<section><h2 id='part-{index}'>Migration part {index}</h2>"
        f"<p>Move cohort {index} only after its reading is stable.</p></section>"
        for index in range(1, 31)
    )
    source = contents_page(
        "dense contents map",
        f"""
<h1>A migration with many independently verifiable steps</h1>

{sections}
<div style="height: 1200px"></div>
""",
        toc_id="dense-contents",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page")
    toc = page.locator("#dense-contents")

    expect(toc).to_have_attribute("data-lf-compact", "")
    nav_box = nav.bounding_box()
    assert nav_box is not None
    assert nav.evaluate("node => node.scrollHeight <= node.clientHeight + 1")
    markers = nav.locator(".lf-toc-start, li").evaluate_all(
        "items => items.map(item => { const s = getComputedStyle(item, '::before'); "
        "const r = item.getBoundingClientRect(); return r.y + parseFloat(s.top) "
        "+ new DOMMatrixReadOnly(s.transform).m42; })"
    )
    assert markers[-1] <= nav_box["y"] + nav_box["height"]
    shifts = nav.locator(".lf-toc-start, li").evaluate_all(
        "items => items.map(item => "
        "parseFloat(item.style.getPropertyValue('--lf-toc-row-shift')) || 0)"
    )
    assert any(abs(shift) > 1 for shift in shifts), shifts

    page.mouse.move(nav_box["x"] + 2, nav_box["y"] + 100)
    page.wait_for_function(
        """nav => {
          const links = [...nav.querySelectorAll('.lf-toc-start a, li a')];
          return links.every(link => getComputedStyle(link).opacity === '1'
            && link.getAnimations().every(m => m.playState === 'finished'));
        }""",
        arg=nav.element_handle(),
    )
    shown = nav.locator(".lf-toc-start a, li a").evaluate_all(
        "links => links.filter(link => getComputedStyle(link).opacity === '1')"
        ".map(link => link.textContent || link.getAttribute('aria-label'))"
    )
    assert len(shown) == nav.locator("a").count(), shown
    label_boxes = nav.locator(".lf-toc-start a, li a").evaluate_all(
        "links => links.map(link => { const box = link.getBoundingClientRect(); "
        "return {top: box.top, bottom: box.bottom}; })"
    )
    assert all(
        right["top"] >= left["bottom"] - 1 for left, right in pairwise(label_boxes)
    ), label_boxes
    first = nav.locator("li a").first
    expect(first).to_have_css("-webkit-line-clamp", "1")
    expect(first).to_have_css("pointer-events", "auto")
    href = first.get_attribute("href")
    first.click()
    expect(page).to_have_url(re.compile(rf"{re.escape(href)}$"))


def test_co_located_headings_share_the_current_title_and_lens_position(browser, serve):
    """The last title at one document position owns both readings of that position."""
    source = contents_page(
        "co-located contents destinations",
        """
<h1>A migration with a shared handoff point</h1>

<div style="height: 500px"></div>
<section style="position: relative; height: 120px">
  <h2 id="handoff" style="position: absolute; top: 0; margin: 0">Handoff</h2>
  <h3 id="checks" style="position: absolute; top: 0; margin: 0">Checks at handoff</h3>
</section>
<div style="height: 1200px"></div>
""",
        toc_id="shared-contents",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page")
    handoff = nav.get_by_role("link", name="Handoff", exact=True)
    checks = nav.get_by_role("link", name="Checks at handoff", exact=True)

    assert handoff.bounding_box()["y"] < checks.bounding_box()["y"]
    page.locator("#checks").evaluate(
        "node => node.scrollIntoView({block: 'start', behavior: 'instant'})"
    )
    expect(checks).to_have_attribute("aria-current", "location")
    alignment = checks.evaluate(
        "node => ({label: node.getBoundingClientRect().top "
        "+ parseFloat(getComputedStyle(node).lineHeight) / 2, "
        "lens: node.closest('nav').querySelector('.lf-toc-window')"
        ".getBoundingClientRect().top})"
    )
    assert alignment["lens"] == pytest.approx(alignment["label"], abs=2), alignment


def test_the_lens_follows_the_scroll_without_a_scroll_timeline(browser, serve):
    """A browser without `ScrollTimeline`, as Firefox ships, still shows the reader's place.

    The same page in a context with the API removed draws the lens where the scroll
    timeline draws it, at the top, the middle and the foot of the document."""
    source = contents_page(
        "contents lens without a scroll timeline",
        """
<h1>A migration read in every browser</h1>

<section><h2 id="prepare">Prepare</h2><div style="height: 900px"></div></section>
<section><h2 id="move">Move</h2><div style="height: 1400px"></div></section>
<section><h2 id="verify">Verify</h2><div style="height: 700px"></div></section>
""",
        toc_id="lens-contents",
    )
    url = serve(source)

    def lens_track(init_script=None):
        page = open_page(browser, url, init_script=init_script)
        resized(page, 1400, 900)
        lens = page.locator("#lens-contents .lf-toc-window")
        expect(lens).to_be_visible()
        track = []
        for fraction in (0, 0.5, 1):
            page.evaluate(
                "fraction => { const s = document.scrollingElement; "
                "s.scrollTop = (s.scrollHeight - s.clientHeight) * fraction; "
                "return new Promise(done => requestAnimationFrame("
                "() => requestAnimationFrame(done))); }",
                fraction,
            )
            box = lens.bounding_box()
            track.append((box["y"], box["height"]))
        page.close()
        return track

    native = lens_track()
    fallback = lens_track("delete globalThis.ScrollTimeline;")
    assert native[2][0] > native[0][0] + 300, native
    for (native_top, native_height), (top, height) in zip(native, fallback):
        assert top == pytest.approx(native_top, abs=1), (native, fallback)
        assert height == pytest.approx(native_height, abs=1), (native, fallback)


@pytest.mark.parametrize(
    ("layout", "holder"),
    [
        # A sidebar page's track, as pr-walkthrough holds its contents.
        ("sidebar", '<section class="panel">{toc}</section>'),
        # A column's margin sidebar holding the map beside other notes.
        ("column", "{toc}<p>Owner: platform.</p>"),
    ],
)
def test_the_current_entry_follows_the_document_from_a_sticking_track(
    browser, serve, layout, holder
):
    """A track that sticks beside the body scrolls only what it holds, so the outline
    focusing it marks the section the window shows, from the page's scroll."""
    sections = "".join(
        f'<section><h2 id="{name.lower()}">{name}</h2><div style="height: 1200px">'
        "</div></section>"
        for name in ("Prepare", "Move", "Verify")
    )
    source = leaf_page(
        "contents in a sticking track",
        '<aside><div class="layout-track">'
        + holder.format(toc='<lf-toc id="track-contents"></lf-toc>')
        + "</div></aside>"
        + f'<div class="{"layout-column" if layout == "column" else ""}">'
        + f"<header><h1>A migration</h1></header>{sections}</div>",
        layout="sidebar",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 900)
    current = page.locator("#track-contents a[aria-current='location']")
    for name in ("Prepare", "Move"):
        page.locator(f"#{name.lower()}").evaluate(
            "node => node.scrollIntoView({block: 'start', behavior: 'instant'})"
        )
        expect(current).to_have_text(name)


def test_a_route_taller_than_the_map_returns_to_an_open_outline(browser, serve):
    """A route that cannot physically fit keeps every heading in one honest form."""
    sections = "\n".join(
        f"<section><h2 id='part-{index}'>Migration part {index}</h2></section>"
        for index in range(1, 81)
    )
    source = contents_page(
        "long contents route",
        f"""
<h1>A migration with more steps than the margin can show at once</h1>

{sections}
""",
        toc_id="long-contents",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 1800)
    toc = page.locator("#long-contents")
    nav = page.get_by_role("navigation", name="On this page")
    links = nav.locator("a")
    expect(links).to_have_count(81)
    expect(toc).not_to_have_attribute("data-lf-outline", "")
    links.last.focus()
    expect(links.last).to_be_focused()

    resized(page, 1400, 900)
    expect(toc).to_have_attribute("data-lf-outline", "")
    expect(nav.locator(".lf-toc-heading")).to_be_visible()
    assert nav.evaluate("node => node.scrollHeight > node.clientHeight")
    for link in (links.first, links.last):
        expect(link).to_have_css("opacity", "1")
        expect(link).to_have_css("pointer-events", "auto")
    expect(links.last).to_be_focused()
    expect(links.last).to_be_in_viewport()

    resized(page, 1400, 700)
    expect(toc).to_have_attribute("data-lf-outline", "")
    expect(links.last).to_be_focused()
    expect(links.last).to_be_in_viewport()

    resized(page, 1188, 600)
    expect(toc).to_have_attribute("data-lf-outline", "")
    nav_box = nav.bounding_box()
    column_left = page.locator("h1").bounding_box()["x"]
    assert nav_box["x"] + nav_box["width"] <= column_left - 16, (
        "the persistent outline covers the document instead of fitting its gutter: "
        f"outline ends at {nav_box['x'] + nav_box['width']:.0f}px, "
        f"column starts at {column_left:.0f}px"
    )
    assert nav.evaluate("node => getComputedStyle(node).backgroundColor") != (
        "rgba(0, 0, 0, 0)"
    )


def test_outline_measurement_preserves_manual_reading_position(browser, serve):
    sections = "\n".join(
        f"<section><h2 id='part-{index}'>Migration part {index}</h2></section>"
        for index in range(1, 81)
    )
    source = contents_page(
        "long contents route",
        f"<h1>Migration</h1>{sections}",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page")
    links = nav.locator("a")
    links.last.focus()
    nav.evaluate("node => { node.scrollTop = 0; }")
    assert nav.evaluate("node => node.scrollTop") == 0
    page.evaluate("""async () => {
      window.dispatchEvent(new Event('resize'));
      await new Promise(requestAnimationFrame);
      await new Promise(requestAnimationFrame);
    }""")
    assert nav.evaluate("node => node.scrollTop") == 0
    resized(page, 1400, 700)
    assert nav.evaluate("node => node.scrollTop") == 0


def test_the_document_map_remeasures_tab_swaps_and_skips_hidden_headings(
    browser, serve
):
    """An equal-height panel swap changes the map without resizing the document.

    Both panels occupy the same outer height but put their heading at a different point.
    The active panel's heading must own the remaining span and the hidden panel must own
    none; at the bottom, current location means the last visible heading rather than the
    last heading in DOM order."""
    source = contents_page(
        "tabbed contents map",
        """
<h1>Two routes through the same migration window</h1>
<style>#first-route, #second-route { height: 1100px; overflow: hidden; }</style>

<lf-tabs id="routes">
  <lf-tab id="first-route" label="First route">
    <h2 id="first-heading">Prepare the readers before opening the window</h2>
    <div style="height: 900px"></div>
  </lf-tab>
  <lf-tab id="second-route" label="Second route">
    <div style="height: 420px"></div>
    <h2 id="second-heading">Verify the readers after closing the window</h2>
    <div style="height: 480px"></div>
  </lf-tab>
</lf-tabs>
""",
        toc_id="tab-contents",
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page")
    first = nav.locator('a[href="#first-heading"]')
    second = nav.locator('a[href="#second-heading"]')
    span = "node => Number(node.parentElement.style.getPropertyValue('--lf-toc-span'))"
    main_height = page.locator("main").evaluate("node => node.scrollHeight")
    assert first.evaluate(span) > 500
    assert second.evaluate(span) == 0
    expect(first).to_be_visible()
    expect(second).to_be_hidden()

    page.evaluate(
        "document.scrollingElement.scrollTop = document.scrollingElement.scrollHeight"
    )
    expect(first).to_have_attribute("aria-current", "location")
    expect(second).not_to_have_attribute("aria-current", "location")

    page.get_by_role("tab", name="Second route").click()
    page.wait_for_function(
        "() => Number(document.querySelector('a[href=\"#second-heading\"]')"
        ".parentElement.style.getPropertyValue('--lf-toc-span')) > 400"
    )
    assert page.locator("main").evaluate("node => node.scrollHeight") == main_height
    assert first.evaluate(span) == 0
    assert second.evaluate(span) > 400
    expect(first).to_be_hidden()
    expect(second).to_be_visible()
    page.evaluate(
        "document.scrollingElement.scrollTop = document.scrollingElement.scrollHeight"
    )
    expect(second).to_have_attribute("aria-current", "location")
    expect(first).not_to_have_attribute("aria-current", "location")


def test_a_gloss_opens_at_its_phrase_for_pointer_keyboard_and_touch(browser, serve):
    """The explanation is a glance, not a mouse-only tooltip: the phrase opens it on
    hover, Tab reaches its Explain control, and a click pins it for mouse or touch. In
    every form the top-layer card remains inside the viewport, and both the phrase and
    explanation remain the page's authored words."""
    source = leaf_page(
        "gloss",
        """
<h1>Rollout</h1>
<p style="margin-top: 110vh; text-align: right">
  Start with a
  <lf-gloss id="gloss-path" tip="A thin, end-to-end path through the real system."
    >walking skeleton</lf-gloss
  >.
</p>
""",
    )
    url = serve(source)
    page = open_page(browser, url)
    gloss = page.locator("#gloss-path")
    mark = gloss.get_by_role("button", name="Explain “walking skeleton”")
    bubble = page.locator("#lf-gloss-tip-1")

    expect(bubble).to_be_hidden()
    affordance = gloss.evaluate(
        """el => {
          const phrase = getComputedStyle(el);
          const mark = el.querySelector('.lf-gloss-mark');
          const words = document.createRange();
          words.selectNodeContents(el.childNodes[0]);
          const tokens = document.createElement('span');
          tokens.style.cssText = 'color: var(--accent)';
          document.body.append(tokens);
          const tokenStyle = getComputedStyle(tokens);
          const accent = tokenStyle.color;
          tokens.remove();
          return {
            accent,
            extraWidth: el.getBoundingClientRect().width - words.getBoundingClientRect().width,
            underline: phrase.textDecorationColor,
            markOpacity: getComputedStyle(mark).opacity,
            markText: mark.textContent,
            markWidth: mark.getBoundingClientRect().width,
            pointer: phrase.cursor,
          };
        }"""
    )
    assert affordance["markText"] == ""
    assert affordance["markWidth"] == 1
    assert affordance["markOpacity"] == "0"
    assert affordance["pointer"] == "help"
    assert affordance["extraWidth"] == pytest.approx(0, abs=1)
    assert affordance["underline"] == affordance["accent"]
    gloss.hover()
    expect(bubble).to_be_visible()
    expect(bubble).to_have_text("A thin, end-to-end path through the real system.")

    # Auto popovers light-dismiss on a press outside the card. The phrase is outside
    # the card too, so the click that pins a hovered explanation must reconcile the
    # browser's just-closed popover with the widget state before the pointer leaves.
    gloss.click(position={"x": 20, "y": 8})
    page.mouse.move(0, 0)
    expect(bubble).to_be_visible()
    page.locator("h1").click()
    expect(bubble).to_be_hidden()
    gloss.hover()
    expect(bubble).to_be_visible()

    rect = bubble.evaluate("el => el.getBoundingClientRect()")
    viewport = page.evaluate("() => ({ width: innerWidth, height: innerHeight })")
    assert rect["left"] >= 0 and rect["right"] <= viewport["width"]
    assert rect["top"] >= 0 and rect["bottom"] <= viewport["height"]
    bubble.hover()
    expect(bubble).to_be_visible()

    # A real pointer crosses the space between the phrase and its card; a single
    # hover jump skips that space and cannot establish the hover-content route.
    page.mouse.move(0, 0)
    expect(bubble).to_be_hidden()
    gloss.hover()
    expect(bubble).to_be_visible()
    card = bubble.bounding_box()
    page.mouse.move(
        card["x"] + card["width"] / 2,
        card["y"] + card["height"] / 2,
        steps=20,
    )
    expect(bubble).to_be_visible()

    # WCAG's hover-content route: Escape dismisses the card without requiring the
    # pointer to move away or transferring focus to a control the user never used.
    page.keyboard.press("Escape")
    expect(bubble).to_be_hidden()

    page.mouse.move(0, 0)
    expect(bubble).to_be_hidden()
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("Tab")
    expect(mark).to_be_focused()
    expect(bubble).to_be_visible()
    expect(gloss).to_have_css("outline-style", "solid")
    page.keyboard.press("Escape")
    expect(bubble).to_be_hidden()

    assert gloss.evaluate("el => el.childNodes[0].textContent.trim()") == (
        "walking skeleton"
    )
    page.close()

    # A real touch context, not a mouse click standing in for one: the tap pins the
    # explanation without a hover state, and a tap elsewhere light-dismisses it.
    context = browser.new_context(
        viewport={"width": 420, "height": 900}, has_touch=True
    )
    touch = open_page(browser, url, context=context)
    touch_gloss = touch.locator("#gloss-path")
    touch_bubble = touch.locator("#lf-gloss-tip-1")
    touch_gloss.tap(position={"x": 20, "y": 8})
    expect(touch_bubble).to_be_visible()
    touch.locator("h1").tap()
    expect(touch_bubble).to_be_hidden()


def test_a_nested_platform_control_does_not_pin_its_gloss(browser, serve):
    """A nested control owns its click even when its platform contract is an ARIA role."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "gloss control",
                '<h1>Term</h1><p><lf-gloss tip="An explanation.">'
                'term <span role="button" tabindex="0">work it</span>'
                "</lf-gloss></p>",
            )
        ),
    )
    control = page.get_by_role("button", name="work it", exact=True)
    bubble = page.get_by_role("note")
    control.hover()
    expect(bubble).to_be_visible()
    control.click()
    page.mouse.move(0, 0)
    page.evaluate(RELEASE_FOCUS)
    expect(bubble).to_be_hidden()


def test_a_comment_on_a_gloss_reopens_its_explanation(browser, serve):
    """The tip is x-says page text, so a comment can rest on it like a tab's rendered
    label. Following that comment from its thread (Show on page) must reveal the
    otherwise hidden popover before the anchor scrolls; a durable thread cannot point to
    words the page then keeps closed."""
    tip = "A thin, end-to-end path through the real system."
    source = leaf_page(
        "gloss comment",
        f"""
<h1>Rollout</h1>
<p>Start with a <lf-gloss id="gloss-path" tip="{tip}">walking skeleton</lf-gloss>.</p>
""",
    )
    page = open_page(browser, serve(source, anchored=[("gloss-path", tip)]))
    bubble = page.locator("#lf-gloss-tip-1")

    expect(bubble).to_be_hidden()
    open_threads(page)
    page.locator(".lf-fp-thread").click()
    page.locator(".lf-fp-controls").get_by_role("button", name="Show on page").click()
    expect(bubble).to_be_visible()
