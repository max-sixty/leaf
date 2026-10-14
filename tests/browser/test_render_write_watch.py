"""The DOM-write sensor judges native mutation batches rather than API calls."""

from urllib.parse import quote

from render_harness import consume_browser_errors, take_browser_errors


def test_child_list_restatements_are_judged_across_one_delivery(browser):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<div hidden id="membership"><i data-for="old"></i></div>'
            '<div hidden id="order"><i data-for="a"></i><i data-for="b"></i></div>'
            '<div hidden id="measurement"><i></i></div>'
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
