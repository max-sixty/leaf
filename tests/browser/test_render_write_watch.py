"""The DOM-write sensor judges native mutation batches rather than API calls."""

from urllib.parse import quote

from render_harness import (
    WRITE_WATCH_SOURCE,
    consume_browser_errors,
    take_browser_errors,
)


def test_child_list_restatements_are_judged_across_one_delivery(browser):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<div hidden id="changed-shadow"><span></span></div>'
            '<div hidden id="retained-shadow"><span></span></div>'
            '<div hidden id="changed-text"><span>before</span></div>'
            '<div hidden id="changed-attribute"><span title="before"></span></div>'
            '<div hidden id="changed-descendants"><span><i>before</i></span></div>'
            '<div hidden id="membership"><i data-for="old"></i></div>'
            '<div hidden id="order"><i data-for="a"></i><i data-for="b"></i></div>'
            '<div hidden id="measurement"><i></i></div>'
            '<div hidden id="frame"><iframe></iframe></div>'
            '<div hidden id="frame-parent"><span><iframe></iframe></span></div>'
            '<div hidden id="frame-shadow"><span></span></div>'
            '<div hidden id="frame-mixed"><span>same</span><iframe></iframe></div>'
            '<div hidden id="frame-and-restatement"><span>same</span><iframe></iframe></div>'
            '<div hidden id="frame-between-restatement"><span>same</span><iframe></iframe></div>'
            '<div hidden id="retained-content"><span title="before">before</span></div>'
            '<div hidden id="nested-roundtrip"><span><i>before</i></span></div>'
            '<div hidden id="before-restore"><span>before</span></div>'
            '<div hidden id="after-restore"><span>before</span></div>'
            '<div hidden id="retained"><i></i><b></b></div>'
            '<div hidden id="cloned"><i></i><b></b></div>'
            '<div hidden id="replaced"><i></i><b></b></div>'
            '<div hidden id="mixed"><i></i></div>'
            '<div hidden id="split-mixed"><i></i><b></b></div>'
            '<div hidden id="cloned-run"><i></i><b></b></div>'
            '<div hidden id="markers"><!----><i></i><!----></div>'
            '<div hidden id="mixed-markers"><!----><i></i><!----></div>'
            '<div hidden id="marker-order"><!----><i></i><!----></div>'
            '<div hidden id="textual">Text</div>'
        )
    )
    page.evaluate("""() => {
      for (const id of ['changed-shadow', 'retained-shadow']) {
        const root = document.getElementById(id).firstChild.attachShadow({mode: 'closed'});
        root.innerHTML = '<b>before</b>';
        if (id === 'changed-shadow') {
          root.host.remove();
          root.firstChild.firstChild.data = 'after';
          document.getElementById(id).append(root.host);
        }
      }
      const text = document.getElementById('changed-text');
      const words = text.firstChild;
      words.remove();
      words.textContent = 'after';
      text.append(words);
      const attributes = document.getElementById('changed-attribute');
      const labelled = attributes.firstChild;
      labelled.remove();
      labelled.title = 'after';
      labelled.setAttributeNS('urn:test', 'p:state', 'after');
      labelled.setAttributeNS('urn:another', 'q:state', 'before');
      document.getElementById('retained-content').firstChild.setAttributeNS(
        'urn:test', 'p:state', 'before',
      );
      attributes.append(labelled);
      const descendants = document.getElementById('changed-descendants');
      const changed = descendants.firstChild;
      changed.remove();
      changed.firstChild.firstChild.data = 'after';
      descendants.append(changed);
      const membership = document.getElementById('membership');
      const arrival = document.createElement('i');
      arrival.dataset.for = 'new';
      membership.firstChild.remove();
      membership.append(arrival);
      const order = document.getElementById('order');
      order.append(order.firstChild);
      const measurement = document.getElementById('measurement');
      const probe = document.createElement('i');
      measurement.append(probe);
      probe.remove();
      // Detachment resets a frame's browsing context even when its node returns.
      const frame = document.getElementById('frame');
      const iframe = frame.firstChild;
      iframe.remove();
      frame.append(iframe);
      const frameParent = document.getElementById('frame-parent');
      const enclosing = frameParent.firstChild;
      enclosing.remove();
      frameParent.append(enclosing);
      const frameShadow = document.getElementById('frame-shadow');
      const frameHost = frameShadow.firstChild;
      frameHost.attachShadow({mode: 'closed'}).innerHTML = '<iframe></iframe>';
      frameHost.remove();
      frameShadow.append(frameHost);
      const frameMixed = document.getElementById('frame-mixed');
      frameMixed.replaceChildren(...frameMixed.childNodes);
      const markers = document.getElementById('markers');
      markers.firstChild.replaceWith(document.createComment(''));
      markers.lastChild.remove();
      markers.append(document.createComment(''));
    }""")
    assert take_browser_errors(page) == []

    page.evaluate("""() => {
      const namespaced = document.getElementById('changed-attribute').firstChild;
      namespaced.setAttributeNS('urn:test', 'p:state', 'new');
      namespaced.setAttributeNS('urn:another', 'q:state', 'before');
      const shadow = document.getElementById('retained-shadow');
      const host = shadow.firstChild;
      host.remove();
      shadow.append(host);
      const content = document.getElementById('retained-content');
      const repeated = content.firstChild;
      repeated.remove();
      repeated.setAttributeNS('urn:test', 'p:state', 'before');
      repeated.title = 'after';
      repeated.firstChild.data = 'after';
      repeated.title = 'before';
      repeated.firstChild.data = 'before';
      content.append(repeated);
      const nested = document.getElementById('nested-roundtrip');
      const parent = nested.firstChild;
      parent.remove();
      const inner = parent.firstChild;
      inner.remove();
      parent.append(inner);
      nested.append(parent);
      const before = document.getElementById('before-restore');
      before.firstChild.firstChild.data = 'after';
      const beforeChild = before.firstChild;
      beforeChild.remove();
      before.append(beforeChild);
      const after = document.getElementById('after-restore');
      const afterChild = after.firstChild;
      afterChild.remove();
      after.append(afterChild);
      afterChild.firstChild.data = 'after';
      const retained = document.getElementById('retained');
      const same = retained.firstChild;
      same.remove();
      retained.prepend(same);
      const cloned = document.getElementById('cloned');
      const twin = cloned.firstChild.cloneNode(true);
      cloned.firstChild.remove();
      cloned.prepend(twin);
      const replaced = document.getElementById('replaced');
      replaced.firstChild.replaceWith(replaced.firstChild.cloneNode(true));
      const mixed = document.getElementById('mixed');
      mixed.firstChild.replaceWith(mixed.firstChild.cloneNode(true));
      mixed.append(document.createElement('b'));
      const split = document.getElementById('split-mixed');
      const first = split.firstChild;
      first.remove();
      split.prepend(first);
      split.append(document.createElement('span'));
      const run = document.getElementById('cloned-run');
      const twins = [...run.children].map(node => node.cloneNode(true));
      while (run.firstChild) run.firstChild.remove();
      for (const twin of twins) run.append(twin);
      const mixedMarkers = document.getElementById('mixed-markers');
      const markedTwins = [...mixedMarkers.childNodes].map(node => node.cloneNode(true));
      while (mixedMarkers.firstChild) mixedMarkers.firstChild.remove();
      for (const twin of markedTwins) mixedMarkers.append(twin);
      const markerOrder = document.getElementById('marker-order');
      const rendered = markerOrder.children[0];
      rendered.remove();
      markerOrder.prepend(rendered);
      const textual = document.getElementById('textual');
      const words = textual.firstChild.cloneNode(true);
      textual.firstChild.remove();
      textual.append(words);
      const frameAndRestatement = document.getElementById('frame-and-restatement');
      const sameSpan = frameAndRestatement.firstChild;
      sameSpan.remove();
      frameAndRestatement.prepend(sameSpan);
      frameAndRestatement.append(frameAndRestatement.lastChild);
      const frameBetweenRestatement = document.getElementById('frame-between-restatement');
      const interleavedSpan = frameBetweenRestatement.firstChild;
      const interleavedFrame = frameBetweenRestatement.lastChild;
      interleavedSpan.remove();
      interleavedFrame.remove();
      frameBetweenRestatement.append(interleavedFrame);
      frameBetweenRestatement.prepend(interleavedSpan);
    }""")
    failures = consume_browser_errors(page, {"code": "unchanged-write"})
    assert {
        (failure.values["what"], *failure.values["node"]) for failure in failures
    } == {
        ("children", "div#retained-shadow"),
        ("children", "div#retained-content"),
        ("title", "span", "div#retained-content"),
        ("state", "span", "div#retained-content"),
        ("state", "span", "div#changed-attribute"),
        ("text", "#text", "span", "div#retained-content"),
        ("children", "div#nested-roundtrip"),
        ("children", "span", "div#nested-roundtrip"),
        ("children", "div#before-restore"),
        ("children", "div#after-restore"),
        ("children", "div#retained"),
        ("children", "div#cloned"),
        ("children", "div#replaced"),
        ("children", "div#mixed"),
        ("children", "div#split-mixed"),
        ("children", "div#cloned-run"),
        ("children", "div#mixed-markers"),
        ("children", "div#marker-order"),
        ("children", "div#textual"),
        ("children", "div#frame-and-restatement"),
        ("children", "div#frame-between-restatement"),
    }


def test_menu_line_measurement_only_credits_removing_and_restoring_limits(browser):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<div class="lf-fp-state" data-held>'
            '<span class="lf-fp-summary" style="--lines: 1">Away</span>'
            '<span class="lf-fp-explain" style="--lines: 3">Details</span>'
            "</div>"
        )
    )
    page.evaluate("""() => {
      const state = document.querySelector('.lf-fp-state');
      const lines = [...state.children];
      const limits = lines.map(line => line.getAttribute('style'));
      state.removeAttribute('data-held');
      for (const line of lines) line.removeAttribute('style');
      // A retained menu is measured without the previous opening's line limits.
      for (const line of lines) line.getBoundingClientRect();
      state.setAttribute('data-held', '');
      lines.forEach((line, i) => line.setAttribute('style', limits[i]));
    }""")
    assert take_browser_errors(page) == []

    # Direct restatements on those same nodes still fail the watch.
    page.evaluate("""() => {
      document.querySelector('.lf-fp-state').setAttribute('data-held', '');
      for (const line of document.querySelectorAll('.lf-fp-state > span'))
        line.setAttribute('style', line.getAttribute('style'));
    }""")
    failures = consume_browser_errors(page, {"code": "unchanged-write"})
    assert {(f.values["what"], *f.values["node"]) for f in failures} == {
        ("data-held", "div.lf-fp-state"),
        ("style", "span.lf-fp-summary"),
        ("style", "span.lf-fp-explain"),
    }


def test_shadow_observation_does_not_retain_discarded_components(browser):
    page = browser.unwatched.new_page()
    page.add_init_script(script=WRITE_WATCH_SOURCE.read_text())
    findings = []
    page.expose_binding(
        "__leafWatchFinding", lambda _source, found: findings.append(found)
    )
    page.goto("data:text/html,<body></body>")
    page.evaluate("""() => {
      const host = document.createElement('div');
      host.hidden = true;
      document.body.append(host);
      const root = host.attachShadow({mode: 'closed'});
      root.innerHTML = '<span>Kept</span>';
      host.remove();
      window.retainedRoot = root;
      window.discardedRoot = new WeakRef(root);
    }""")
    session = page.context.new_cdp_session(page)
    try:
        session.send("HeapProfiler.collectGarbage")
        # A detached root the page still owns remains watched, including closed roots.
        page.evaluate("retainedRoot.firstChild.textContent = 'Kept'")
        assert [finding["code"] for finding in findings] == ["unchanged-write"]
        page.evaluate("() => { delete window.retainedRoot; }")
        session.send("HeapProfiler.collectGarbage")
        assert page.evaluate("discardedRoot.deref() === undefined")
    finally:
        session.detach()
