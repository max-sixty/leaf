# Focus rings cut at a scroller's edge

A focus ring is drawn outside its box, so a scroller that clips at its padding edge
cuts the ring of a control standing at that edge. Leaf answers this one box at a time.
The `browser/runtime/chrome.css` header states the rule "every scroll region a ringed
box can land in reserves `--focus-ring-room`", and each scroller declares that room
itself: the chrome, the parts list, tabs, the annotation chrome, a sidebar page's
stuck track body (#3939), and Copy's shadow button (#3916, its own `scroll-margin`).
The cases below are the ones found so far. Collect more here before choosing a
mechanism, since the user judged focus rings too central for another per-case patch
(2026-10-25).

Two mechanisms produce the cases:

- **A. The scroller reserves no room.** Each scroller has to declare the ring's room
  itself, so a scroller nobody declared it for cuts rings (cases 1–2).
- **B. The ring is drawn on a box other than the focused node.** Inside a Web Awesome
  control, focus lands on a node in the control's own shadow tree. Leaf's
  `:where(:focus, [data-lf-focus])` scroll margin doesn't reach that node, and
  `ringBox` (`browser/runtime/landing-scroll.js`) finds no `--lf-wears-ring` part. So
  the Tab-arrival correction reads a zero margin and decides the ring is already shown
  (cases 3–5).

## Cases

Measured in headless Chromium 153 and Firefox 155 on 2026-10-25. "Room" is the space
between the ring's outer edge and the clipping edge; negative means cut.

| #   | Where                                                                                                                                      | Today                                                                                                                                                                                      | Reproduce                                                                 |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------- |
| 1   | A sidebar page's stuck track body: `examples/live-progress.html`, 1440×900, scroll to 600, Tab five times onto the "Release notes" summary | Cut 5px left and 4.6px right before #3939. #3939's track-only rule in `browser/layouts.css` ("Sticking blocks") now holds the room                                                         | The fixture below, "a sidebar page's track", with that rule removed       |
| 2   | A column's margin `aside.sidebar` holding more than a contents map (a line-leading link, a summary), while it sticks                       | Cut 5px at the link's start and both sides of the summary, on main and before #3939                                                                                                        | The fixture below, "a column's margin sidebar"                            |
| 3   | A diff's file filter (`wa-input`, shown for a multi-file `lf-diff`) 3px past the foot of a 240px scroll pane, reached by Tab               | Room −0.6px (Chromium), −1.0px (Firefox); the ring ends 4.05px past the pane                                                                                                               | `EDGE_CONTROLS["filter"]` below in `tests/browser/controls/test_focus.py` |
| 4   | A package's `wa-select` 3px past a pane's foot                                                                                             | Room −2.8px / −3.2px                                                                                                                                                                       | `EDGE_CONTROLS["select"]` below                                           |
| 5   | A code block's Copy at a pane's top (#3916)                                                                                                | Held by Copy's own `scroll-margin` in `browser/styles/components/integration.css`; 4.7px outside before it. Measured before #3978 made Copy a 20px mark that rings its own edge: remeasure | `EDGE_CONTROLS["copy"]` below, with that rule removed                     |
| 6   | A single-thumb `wa-slider`: focus is on its 8px rail, the ring on its 22px thumb 7.2px below                                               | Cut about 2px in both engines. Nothing in the tree uses one yet                                                                                                                            | A `wa-slider` at a pane's foot, reached by Tab                            |

A playground's rail (`[data-lf-track]`) passes, since its panes inset their controls.
So does every Web Awesome control whose focus stays on its host, such as `wa-radio`.

## Candidates already tried

Neither landed. Each is described so it can be rebuilt.

- **One rule for every sticking block (A).** Move the stuck track body's `padding`,
  negative block `margin` and `scroll-padding` into the shared "Sticking blocks" rule
  in `browser/layouts.css`, so all three sticking blocks hold the room. The margin
  sidebar's float rule then needs `:where()` so its margin doesn't beat the shared
  one. This fixed cases 1–2. The cost: a stuck block's contents stand 5px in from
  each side, and a playground rail's panes narrow by 10px.
- **Read margins from the nearest host Leaf styles (B).** In `landing-scroll.js`,
  `scrollMargin` reads a node's margins through the nearest element Leaf's CSS
  reaches, which is a vendor control's host. `wa-input::part(base …)` and
  `wa-select::part(combobox …)` declare `--lf-wears-ring: 1`. This fixed cases 3–5
  and let Copy's own rule go. Case 6 stayed, because the thumb isn't an ancestor
  `ringBox` can find. A flat `--focus-ring-landing` floor was rejected, since it
  overrides the stuck-header rule that gives a control in a stuck header a top margin
  of zero or less.

## Reproductions

Cases 1–2, as a browser test using `tests/render_cases_layout.py`'s `rings_drawn` and
`ring_faults`:

```python
def test_a_sticking_block_shows_whole_the_rings_at_its_edges(browser, serve):
    held = (
        "<p id='edge-lead'><a id='edge-link' href='#body'>Jump to the findings</a></p>"
        "<details><summary id='edge-summary'>Related pages</summary>"
        "<p>None yet.</p></details>"
    )
    body = "<div id='body'>" + "<p>Body paragraph. " * 600 + "</p></div>"
    pages = {
        "a column's margin sidebar": leaf_page(
            "a column page", f"<aside class='sidebar'>{held}</aside>{body}"
        ),
        "a sidebar page's track": leaf_page(
            "a sidebar page",
            f"<header><h1>Review</h1></header><aside>{held}</aside>{body}",
            layout="sidebar",
        ),
    }
    holder = """() => getComputedStyle(
      document.getElementById('edge-lead').parentElement).position"""
    focused = "() => document.activeElement?.id ?? null"
    for where, source in pages.items():
        page = open_page(browser, serve(source))
        resized(page, 1440, 900)
        page.evaluate("scrollTo(0, 1500)")
        assert page.evaluate(holder) == "sticky", where
        for target in ("edge-link", "edge-summary"):
            for _ in range(20):
                page.keyboard.press("Tab")
                if page.evaluate(focused) == target:
                    break
            else:
                raise AssertionError(f"Tab never reached #{target} in {where}")
            drawn = [ring for ring in rings_drawn(page) if ring["focused"]]
            assert drawn, (where, target)
            assert not ring_faults(drawn, f"in {where}, #{target}"), drawn
```

Cases 3–5 extend `test_a_key_onto_a_control_at_a_scrollers_edge_shows_its_ring` in
`tests/browser/controls/test_focus.py`. Add these entries to its tables. The select
needs a layer widget, passed to the page through `EDGE_LAYERS`. Then add `copy-top`,
`filter-past` and `select-past` parameters in both engines:

```python
EDGE_CONTROLS |= {
    "copy": (
        '<lf-code id="cb" language="python"><pre>'
        + "\n".join(f"step_{i}()" for i in range(8))
        + "</pre></lf-code>"
    ),
    "filter": (
        '<lf-diff id="patch"><pre>'
        + "".join(
            f"diff --git a/{name} b/{name}\n--- a/{name}\n+++ b/{name}\n"
            "@@ -1,1 +1,1 @@\n-old\n+new\n"
            for name in ("one.py", "two.py")
        )
        + "</pre></lf-diff>"
    ),
    "select": '<lf-edge-select id="sel"></lf-edge-select>',
}
EDGE_TARGETS |= {
    "copy": "#cb .lf-code-copy [part~=button]",
    "filter": "#patch .lf-diff-search input",
    "select": "#sel wa-select [part~=display-input]",
}
EDGE_SIDES = {"table": "right", "copy": "top"}
# Copy takes focus only once the keyboard stands in its block.
EDGE_BEFORE = {"copy": "#cb pre"}
# lf-edge-select's module appends a `wa-select` labelled "Route" holding two
# `wa-option`s, after importing '/vendor/webawesome.esm.js'.
```
