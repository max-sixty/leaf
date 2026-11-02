"""Document geometry is complete before runtime modules activate."""

import pytest
from render_harness import displayed, leaf_page, open_page, wait_until_ready

DOCUMENT = """
<aside id="route"><div class="layout-track">
  <p>Read the evidence before deciding.</p><nav><a href="#evidence">Evidence</a></nav>
</div></aside>
<div class="layout-column layout-notes" id="body">
  <h1>Review</h1>
  <section id="evidence" class="layout-flow">
    <h2>Evidence</h2>
    <div class="layout-note"><p id="prose">The passage keeps its reading measure.</p>
      <aside class="note" id="note">A short qualification.</aside></div>
    <lf-worktree-diffs id="wide"><lf-worktree id="tree" label="Changes" path="/work/leaf"
      status="clean" files="0" additions="0" deletions="0" open>
      <p>Readable before JavaScript.</p>
    </lf-worktree></lf-worktree-diffs>
  </section>
  <p id="after">The next paragraph keeps its place.</p>
</div>
"""


def test_native_sidebar_and_note_are_placed_before_widget_activation(browser, serve):
    source = leaf_page("native startup", DOCUMENT, layout="sidebar")
    url = serve(source)
    for width in (1600, 720):
        page = browser.new_page(viewport={"width": width, "height": 900})
        held = []
        page.route("**/leaf.js", lambda route, _request, held=held: held.append(route))
        page.goto(url, wait_until="commit")
        page.locator("#prose").wait_for(state="visible")
        page.locator("#after").wait_for(state="attached")
        displayed(page)
        read = """() => Object.fromEntries(['route','body','prose','note','wide','after']
          .map(id => [id,document.getElementById(id).getBoundingClientRect().toJSON()]))"""
        before = page.evaluate(read)
        assert before["prose"]["width"] == min(720, width - 48)
        assert (before["route"]["top"] < before["body"]["top"]) == (width == 720)
        assert (before["note"]["left"] >= before["prose"]["right"]) == (width == 1600)
        for route in held:
            route.continue_()
        page.unroute("**/leaf.js")
        wait_until_ready(page)
        assert page.evaluate(read) == before


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_annotations_read_the_native_prose_track_with_authored_geometry(
    browser, serve, direction
):
    source = leaf_page(
        "authored tracks",
        '<h1>Reading</h1><p id="prose">A paragraph on the prose track.</p>',
        head=f"""<style>main {{direction:{direction};width:1000px;max-width:100%;
          box-sizing:border-box;padding-inline:43px;--col:34rem;
          transform:scale(.85);transform-origin:top left}}</style>""",
    )
    page = open_page(browser, serve(source))
    reading = page.evaluate("""async () => {
      const {proseRect}=await import('/runtime/bundle-content-layout.js');
      const prose=document.querySelector('#prose').getBoundingClientRect();
      return {computed:proseRect(),actual:{left:prose.left,right:prose.right}};
    }""")
    assert reading["computed"]["left"] == pytest.approx(
        reading["actual"]["left"], abs=0.5
    )
    assert reading["computed"]["right"] == pytest.approx(
        reading["actual"]["right"], abs=0.5
    )


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_note_rows_fit_their_column_without_moving_other_columns(
    browser, serve, subtests, direction
):
    source = leaf_page(
        "note tracks",
        """<section class="layout-column layout-notes" id="noted">
          <p id="intro">The passage and its note share a reading axis.</p>
          <section class="layout-flow"><section class="layout-flow">
            <div class="layout-note" id="row">
              <p id="passage">A passage with a qualification.</p>
              <aside class="note" id="qualification">The qualification belongs to
                this passage, before the next exhibit.</aside>
            </div>
            <div id="exhibit">The next exhibit.</div>
          </section></section>
          <div class="layout-column" id="nested"><p id="nested-prose">
            An independent nested column keeps its own axis.</p></div>
        </section>
        <section class="layout-column"><p id="plain">
          An unrelated column has no notes and remains centered.</p></section>
        <section class="layout-column"><p id="outer-prose">
          An inner column's note never moves this outer prose.</p>
          <section class="layout-column layout-notes" id="inner">
            <div class="layout-note"><p id="inner-prose">An independent passage.</p>
              <aside class="note" id="inner-note">Its independent qualification.</aside>
            </div>
          </section>
        </section>""",
        layout=None,
        head=f"""<style>body {{margin:0}} main {{direction:{direction}}}
          #nested, #inner {{grid-column:full}}</style>""",
    )
    page = open_page(browser, serve(source))
    for width in (1600, 1200, 1152, 1151, 900, 390):
        with subtests.test(width=width):
            page.set_viewport_size({"width": width, "height": 900})
            boxes = page.evaluate("""() => Object.fromEntries(
              ['intro','passage','qualification','exhibit','plain','nested','nested-prose','outer-prose','inner-prose','inner-note']
                .map(id => [id,document.getElementById(id).getBoundingClientRect().toJSON()]))""")
            passage, note = boxes["passage"], boxes["qualification"]
            assert passage["width"] == min(720, width - 48)
            assert note["width"] <= passage["width"]
            assert boxes["intro"]["left"] == passage["left"]
            assert boxes["plain"]["left"] == max(24, (width - 720) / 2)
            assert boxes["outer-prose"]["left"] == boxes["plain"]["left"]
            inner, inner_note = boxes["inner-prose"], boxes["inner-note"]
            assert inner["width"] == min(720, width - 96)
            assert inner_note["width"] <= inner["width"]
            nested = boxes["nested"]
            assert boxes["nested-prose"]["left"] == nested["left"] + max(
                24, (nested["width"] - 720) / 2
            )
            assert boxes["exhibit"]["top"] - note["bottom"] >= 24
            if width >= 1152:
                assert note["top"] == passage["top"]
                if direction == "ltr":
                    assert note["left"] - passage["right"] == 24
                else:
                    assert passage["left"] - note["right"] == 24
            else:
                assert note["top"] - passage["bottom"] == 8
                assert note["left"] == passage["left"]


@pytest.mark.parametrize("engine", ["browser", "firefox_browser", "webkit_browser"])
def test_reading_flow_track_chain_names_only_visible_broken_flows(
    request, serve, engine
):
    """Native computed tracks distinguish broken flows from valid containment/flex."""
    from leaf import render_checks
    from leaf.render_gate.readings import swept_faults

    source = leaf_page(
        "Flow track boundaries",
        """<section class="layout-column" id="column">
          <section id="correct" class="layout-flow"><p>Complete tracks.</p></section>
          <section id="contained" class="layout-flow" style="contain:inline-size"><p>Size containment keeps tracks.</p></section>
          <section id="container-type" class="layout-flow" style="container-type:inline-size"><p>Container tracks.</p></section>
          <section id="narrow" class="layout-flow" style="grid-column:prose-start / full-end"><p>Narrowed tracks.</p></section>
          <section id="explicit" class="layout-flow" style="grid-column:full-start / full-end"><p>Explicit full-track names.</p></section>
          <section id="no-subgrid" class="layout-flow" style="grid-template-columns:1fr"><p>Independent columns.</p></section>
          <section id="numeric" class="layout-flow" style="grid-column:1 / -1"><p>Equivalent numeric span.</p></section>
          <div><section id="standalone" class="layout-flow"><p>Owns the wrapper's room.</p></section></div>
          <section id="hidden-own" class="layout-flow" hidden="until-found" style="grid-column:prose"><p>Hidden own box.</p></section>
          <div hidden="until-found"><section id="hidden" class="layout-flow" style="container-type:inline-size"><p>Hidden.</p></section></div>
        </section>
        <section class="layout-sidebar"><aside>Navigation</aside>
          <div class="layout-column"><section id="sidebar" class="layout-flow"><p>Sidebar reading.</p></section></div>
        </section>
        <section class="layout-workspace"><div id="workspace" class="layout-flow" style="display:flex"><p>Flex workspace.</p></div></section>""",
        layout=None,
    )
    page = open_page(request.getfixturevalue(engine), serve(source, packages=()))
    reading = render_checks.evaluate_probe(page, "geometryReading", [])
    flows = [row for row in reading["contained"] if row["code"] == "flow-tracks"]
    expected = {"<section id=narrow>", "<section id=no-subgrid>"}
    # This advice reads the computed track declaration. Engines differ on whether
    # container-type suppresses that declaration; used-layout validation is separate.
    columns = page.locator("#container-type").evaluate(
        "e => getComputedStyle(e).gridTemplateColumns"
    )
    if not columns.startswith("subgrid"):
        expected.add("<section id=container-type>")
    assert {row["at"] for row in flows} == expected
    assert (
        next(row for row in flows if row["at"] == "<section id=narrow>")["start"]
        == "prose-start"
    )
    advice = [
        finding
        for finding in swept_faults([(1280, reading)])
        if finding.code == "flow-tracks"
    ]
    assert len(advice) == len(expected)
    assert all(finding.severity == "advice" for finding in advice)
    assert "grid-template-columns: subgrid" in str(advice[0])
