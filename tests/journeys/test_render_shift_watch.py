"""The browser fixture fails the layout shifts the "Stability" rule forbids
(`shift_watch.js`): a shift without input, and typing that carries its field."""

from datetime import datetime, timedelta

import pytest
from browser.test_render_shift_watch import held_stretch, paint, shift_evidence
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import ASK_PAGE
from render_harness import (
    is_problem,
    judge_watches,
    leaf_page,
    open_page,
    resized,
    take_browser_errors,
)


@pytest.mark.parametrize("surface", ["card", "inline"])
def test_message_age_may_shift_metadata_but_leaves_the_thread_in_place(
    browser, serve, surface
):
    """Age advances while the thread and its controls stay put.

    Metadata may move or stay reserved. The passive-region fault controls above
    exercise the watcher's permitted motion independently of this surface's layout.
    """
    source = (
        leaf_page(
            "Inline task thread",
            '<h1 id="title">Before the frost</h1><lf-test-plan id="jobs" label="Jobs">'
            '<lf-test-task id="bracket" status="active" talk>'
            "<strong>Which jobs can share a visit?</strong></lf-test-task></lf-test-plan>",
        )
        if surface == "inline"
        else ASK_PAGE
    )
    page = open_page(
        browser,
        serve(
            source,
            events=[
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "Check whether these jobs can share one visit.",
                    "anchor": {"section": "bracket"},
                }
            ],
        ),
    )
    resized(page, 1440, 900)
    if surface == "card":
        page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
        surface_root = page.locator(".lf-margin-preview")
    else:
        surface_root = page.locator(".lf-page-thread[data-lf-runtime]")
    header = surface_root.locator(".lf-msg-head").first
    receipt = header.locator(".lf-msg-sending")
    timestamp = header.locator("time")
    expect(receipt).to_have_text("Sent")
    expect(timestamp).to_have_text("just now")
    # Age changes are news after Chrome's recent-input grace, even when opening the
    # surface and resizing it happened immediately before this clock transition.
    rendered(page)
    page.wait_for_function(
        "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
    )
    protected = surface_root.locator("b, button, leaf-text, .lf-msg-body")
    boxes = "nodes => nodes.map(node => node.getBoundingClientRect().toJSON())"
    before = protected.evaluate_all(boxes)
    assert before
    thread_before = surface_root.bounding_box()
    owner = header.locator("xpath=..")
    owner_before = owner.bounding_box()
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    now = datetime.now().astimezone()
    for delta, age in [
        (timedelta(minutes=1), "1m ago"),
        (timedelta(minutes=10), "10m ago"),
        (timedelta(hours=3), "3h ago"),
    ]:
        # Advance Leaf's calibrated server clock without changing the browser's
        # monotonic clock: native LayoutShift and frame readings must share time.
        page.evaluate(
            """async now => {
              const clock = await window.__lfRuntimeImport('/runtime/presence.js');
              const {reportPageError} = await window.__lfRuntimeImport('/runtime/layer-client.js');
              clock.observeServerNow(now);
              await clock.tickClock(reportPageError);
            }""",
            (now + delta).isoformat(),
        )
        expect(timestamp).to_have_text(age)
        expect(receipt).to_have_text("Sent")
        judge_watches()
        assert surface_root.bounding_box() == thread_before
        assert owner.bounding_box() == owner_before
        assert protected.evaluate_all(boxes) == before


# Input attribution, the plane moved to, and the extra motion are independent, so each
# guard mode is paired with one destination, and each fault kind and axis with one mode,
# rather than crossed.
@pytest.mark.parametrize(
    "fault, guard_mode, destination",
    [
        ("", "typing", "window"),
        ("", "passive", "page"),
        ("holder_x", "typing", "window"),
        ("child_y", "typing", "window"),
        ("inset_y", "passive", "page"),
    ],
)
def test_real_floating_plane_retains_local_motion(
    browser, serve, fault, guard_mode, destination
):
    """Owned plane changes excuse their placement, never extra holder/child motion.

    The two planes belong to the shared placement factory. An editing presenter need
    not use both: its following policy is independent of this guard's attribution.
    """
    source = leaf_page(
        "Plane evidence",
        '<p id="subject" style="position:fixed;left:100px;top:280px;'
        'width:80px;height:30px;margin:0">Exact subject</p>'
        '<div id="holder" style="visibility:hidden;position:fixed;width:220px;height:90px;'
        'padding:12px;border:1px solid;box-sizing:border-box;background:white">'
        '<textarea id="field" style="display:block;width:160px;height:36px;'
        'box-sizing:border-box;resize:none"></textarea></div>'
        '<p id="evidence" style="position:fixed;left:10px;top:440px;'
        'width:300px;height:30px;margin:0">Paint evidence</p>',
        layout=None,
    )
    page = open_page(browser, serve(source))
    resized(page, 900, 600)
    # An unplaced surface has dimensions for its solver, but no reading to move.
    paint(page)
    expect(page.locator("#field")).to_be_hidden()
    initial = "page" if destination == "window" else "window"
    first = page.evaluate(
        """async initial => {
          const module = await window.__lfRuntimeImport('/runtime/annotation-overlay/floating.js');
          const ui = await module.floatingUi();
          const holder = document.querySelector('#holder');
          const subject = document.querySelector('#subject');
          let plane = initial, answer;
          const selection = () => module.floatingSelections().find(s => s.floating === holder);
          const owner = module.floatingPlacement({floating:holder, update:()=>void place()});
          async function place() {
            owner.begin();
            const reference = {
              contextElement:subject,
              getBoundingClientRect:()=>plane === 'page'
                ? subject.getBoundingClientRect() : new DOMRect(410,150,80,30),
            };
            const placed = await owner.position(ui.computePosition, reference,
              {placement:'right-start',middleware:[]}, ()=>plane, subject);
            if (placed) {owner.stand(placed); answer = placed;}
          }
          owner.watch(subject, subject, ui.autoUpdate);
          await place();
          holder.style.removeProperty('visibility');
          const original = selection();
          window.planeControl = {
            to:async destination => {plane=destination; await place(); window.injectPlaneFault?.();},
            read:() => {
              const current = selection();
              return {plane:current.plane, edge:current.edges.top, sameSubject:current.subject===original.subject,
                sameAnchor:current.anchor===original.anchor, sameTenure:current.tenure===original.tenure,
                expected:{x:answer.x,y:answer.y}};
            },
          };
          return planeControl.read();
        }""",
        initial,
    )
    assert first["plane"] == initial
    field, holder = page.locator("#field"), page.locator("#holder")
    field.fill("Keep these words.")
    paint(page)
    judge_watches()
    assert take_browser_errors(page) == []
    if guard_mode == "passive":
        page.keyboard.press("Shift")
        paint(page)
    held_stretch(page)
    before, holder_before = field.bounding_box(), holder.bounding_box()
    page.evaluate("window.beforeField=document.querySelector('#field')")
    page.evaluate("""()=>{
      window.nativePlaneEntries=[];
      new PerformanceObserver(list=>nativePlaneEntries.push(...list.getEntries().map(e=>({
        at:e.startTime,sources:e.sources.map(s=>({kind:s.node?.nodeName,
          previous:s.previousRect.toJSON(),current:s.currentRect.toJSON()}))
      })))).observe({type:'layout-shift'});
    }""")
    page.evaluate(
        """fault=>{
          window.planeChanges=0;
          const holder=document.querySelector('#holder');
          let previous=holder.dataset.lfPlane;
          new MutationObserver(()=>{
            if(holder.dataset.lfPlane===previous) return;
            previous=holder.dataset.lfPlane;
            planeChanges++;
          }).observe(holder,{attributes:true,attributeFilter:['data-lf-plane']});
          window.injectPlaneFault = () => {
            if(fault==='holder_x') holder.style.transform='translateX(80px)';
            if(fault==='holder_y') holder.style.transform='translateY(80px)';
            if(fault==='child_x') document.querySelector('#field').style.transform='translateX(80px)';
            if(fault==='child_y') document.querySelector('#field').style.transform='translateY(80px)';
            if(fault==='inset_y') {
              const edge=planeControl.read().edge;
              holder.style[edge]=`calc(${edge==='top'?80:-80}px + ${holder.style[edge]})`;
            }
            // Transform-only faults need a native paint signal; this extra source
            // cannot establish the independently asserted field displacement.
            if(fault) document.querySelector('#evidence').style.marginLeft='30px';
          };
        }""",
        fault,
    )
    if guard_mode == "typing":
        field.evaluate(
            "(node,destination)=>node.addEventListener('beforeinput',()=>void planeControl.to(destination),{once:true})",
            destination,
        )
        page.keyboard.insert_text("x")
    else:
        page.evaluate("destination=>planeControl.to(destination)", destination)
    page.wait_for_function(
        "destination=>planeControl.read().plane===destination", arg=destination
    )
    paint(page)
    state = page.evaluate("planeControl.read()")
    assert state["sameSubject"] and state["sameAnchor"] and state["sameTenure"], state
    assert page.evaluate("planeChanges") == 1
    judge_watches()
    errors = take_browser_errors(page)
    entries = page.evaluate("nativePlaneEntries")
    assert entries, (fault, guard_mode, destination, "no Chrome paint admission")
    after, holder_after = field.bounding_box(), holder.bounding_box()
    assert page.evaluate("beforeField===document.querySelector('#field')")
    assert after["width"] == before["width"]
    assert after["height"] == before["height"]
    assert holder_after["width"] == holder_before["width"]
    assert holder_after["height"] == holder_before["height"]
    assert state["expected"] != {axis: holder_before[axis] for axis in ["x", "y"]}
    for axis in ["x", "y"]:
        shifted = 80 if fault.endswith("_" + axis) else 0
        assert holder_after[axis] == pytest.approx(
            state["expected"][axis]
            + (shifted if fault.startswith("holder") or fault == "inset_y" else 0),
            abs=1,
        )
        assert after[axis] == pytest.approx(
            state["expected"][axis] + before[axis] - holder_before[axis] + shifted,
            abs=1,
        )
    expected = {"node": "textarea#field"} | (
        {"code": "typing-moved", "field": "textarea#field"}
        if guard_mode == "typing"
        else {"code": "moved-without-input"}
    )
    if fault:
        error = next(error for error in errors if is_problem(error, expected))
        evidence = shift_evidence(error)
        assert evidence["kind"] == guard_mode
        comparisons = evidence["comparisons"]
        assert comparisons
        terms = [
            term for comparison in comparisons for term in comparison["scroll_terms"]
        ]
        assert any(
            term["branch"] == "floating_plane"
            and term["owner"] == "div#holder"
            and term["inputs"]["before"]["plane"] == initial
            and term["inputs"]["after"]["plane"] == destination
            and term["inputs"]["same_attachment"]
            and not term["inputs"]["crosses_fixed"]
            and term["inputs"][
                "before_origin" if initial == "page" else "after_origin"
            ]["camera"]["left"]
            is not None
            for term in terms
        ), terms
        assert any(
            abs(comparison["scroll_credit"][axis]) >= 1
            for comparison in comparisons
            for axis in ["left", "top"]
        ), comparisons
    else:
        assert errors == [], errors
