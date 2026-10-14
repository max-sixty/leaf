"""The DOM-write sensor judges native mutation batches rather than API calls."""

from urllib.parse import quote

from render_harness import consume_browser_errors, take_browser_errors


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
    }""")
    failures = consume_browser_errors(page, {"code": "unchanged-write"})
    assert {
        (failure.values["what"], failure.values["node"]) for failure in failures
    } == {
        ("children", "div#retained-shadow"),
        ("children", "div#retained-content"),
        ("title", "span in div#retained-content"),
        ("state", "span in div#retained-content"),
        ("state", "span in div#changed-attribute"),
        ("text", "#text in span in div#retained-content"),
        ("children", "div#nested-roundtrip"),
        ("children", "span in div#nested-roundtrip"),
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
    }
