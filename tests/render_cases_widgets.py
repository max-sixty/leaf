"""Shared widgets browser-integration cases and readings."""

from leaf import passages as passages_model
from leaf import registry as registry_model
from render_harness import (
    leaf_page,
)

# ---------- anchors written without a browser ----------
# `leaf comment` writes an anchor by reading the version file; the runtime
# resolves it against the DOM that file becomes. Nothing static can check that those
# two readings agree, and every way they can come apart — a widget's upgrade, an
# attribute rendered as text, the space a block boundary stands for — only exists
# once the page is loaded.


def written_anchors(page_dir, html, limit=40):
    """Anchors `leaf comment` would write for windows over a page's own prose. A
    window the page says twice, or one crossing a fence, is refused on purpose —
    skipping those here is that refusal, and what survives is exactly what the command
    promises to place."""
    registry = registry_model.load_registry(page_dir)
    text = passages_model.page_passages(html, registry).text
    words = text.split(" ")
    anchors = []
    for start in range(0, len(words), 3):
        quote = " ".join(words[start : start + 8])
        if len(quote) < 20:
            continue
        try:
            anchors.append(
                (quote, passages_model.capture_anchor(html, registry, quote, None))
            )
        except ValueError:
            continue
        if len(anchors) == limit:
            break
    return anchors


TWIN_V1 = leaf_page(
    "twin",
    """
<h1 id="t">Twin</h1>
<section id="twin">
<p id="p-original">Cache warmup runs first. The version stamp never lands. Retries are capped at three.</p>
</section>
""",
)
# A copy the anchor was not made on, added above it — so first-match now finds the wrong
# one, and only the neighbours the capture stored say which was meant.
TWIN_V2 = TWIN_V1.replace(
    '<p id="p-original">',
    '<p id="p-added">Queue drain runs first. The version stamp never lands. Retries are capped at four.</p>\n'
    '<p id="p-original">',
)
PICTURE_PAGE = leaf_page(
    "pictures",
    """
<h1 id="t">Pictures</h1>
<p id="p">Two renderings, neither of them the page's own words.</p>
<lf-diagram id="flow"><pre>
graph LR
  A --> B
</pre></lf-diagram>
<lf-tree id="tree"><pre>
feeders/
  mount.py  +2 -2
</pre></lf-tree>
""",
)
PART_DIAGRAM_PAGE = leaf_page(
    "diagram parts",
    """
<h1 id="t">Request path</h1>
<lf-diagram id="flow" parts="node:S node:H"><pre>
graph LR
  S[Start request] --> H[Handle request] --> U[Unlisted result]
  click H href "https://example.com/handler" "Open handler"
</pre></lf-diagram>
""",
)
PART_DIAGRAM_V2 = leaf_page(
    "diagram parts",
    """
<h1 id="t">Request path</h1>
<lf-diagram id="flow" parts="node:S node:H"><pre>
graph LR
  U[Unlisted result]
  H[Handle request]
  S[Start request]
  S --> H
  H --> U
  click H href "https://example.com/handler" "Open handler"
</pre></lf-diagram>
""",
)
# A drawing wider than the column on purpose — six nodes across lay out near 1150px
# against 720 — and a board beside it, so what the assertions turn on is which kind each
# widget declares rather than that both are widgets.
WIDE_DIAGRAM_PAGE = leaf_page(
    "wide diagram",
    """
<h1 id="t">Flow</h1>
<lf-diagram id="flow"><pre>
graph LR
  R[request] --> C{cookie valid?}
  C -->|yes| S[read session from Redis]
  S -->|hit| H[handle]
  S -->|miss/outage| F[verify signed fallback]
  F --> H
  C -->|no| L[login]
</pre></lf-diagram>
<lf-board id="plan">
  <lf-column id="d1" label="Todo"><lf-card id="dk1"><strong>One</strong></lf-card></lf-column>
  <lf-column id="d2" label="Doing"></lf-column>
  <lf-column id="d3" label="Done"></lf-column>
</lf-board>
""",
)
# What a diagram is doing with the width it was given, beside what the board on the same
# page is doing with the width it was given: the drawing's own size, the box around it,
# and whether either had to scroll.
DIAGRAM_ROOM = """() => {
    const holder = document.getElementById('flow');
    const svg = holder.querySelector('svg');
    const board = document.getElementById('plan');
    const main = document.querySelector('main'), ms = getComputedStyle(main);
    const mb = main.getBoundingClientRect();
    return { drawn: svg.getBoundingClientRect().width,
             natural: svg.viewBox.baseVal.width,
             box: holder.clientWidth,
             room: parseFloat(getComputedStyle(document.documentElement)
                       .getPropertyValue('--lf-room')),
             wide: parseFloat(getComputedStyle(document.body)
                       .getPropertyValue('--wide')),
             board: board.getBoundingClientRect().width,
             column: mb.width - parseFloat(ms.paddingLeft) - parseFloat(ms.paddingRight),
             scrolls: holder.scrollWidth > holder.clientWidth,
             sideways: document.body.scrollWidth - document.body.clientWidth };
}"""
# A diagram whose source mermaid refuses, which is the shape of every soft failure: the
# module replaces the element's body with the message and the source it choked on. Its
# first line is the length a real source has, because that line is what the box under
# test is floored at: written short, this page passed the assertion below with the rule
# it stands on deleted.
BROKEN_DIAGRAM_PAGE = leaf_page(
    "broken diagram",
    """
<h1 id="t">Broken</h1>
<lf-diagram id="bad"><pre>
sequenceDiagram
  Reader-&gt;&gt;Server: POST /api/event {kind: "action", widget: "lf-board", detail: {card: "card-heater"}}
  Server--&gt;&gt;&gt;--- {{{ not mermaid at all ]]]
</pre></lf-diagram>
""",
)
# A margin with the page's own apparatus in it, and drawings either side of what the free
# margin can hold. A rail is what most shipped pages that carry a wide widget also carry,
# so this is the ordinary case rather than a corner.
DIAGRAM_AND_RAIL_PAGE = leaf_page(
    "diagram and rail",
    """
<h1 id="t">Sessions</h1>
<lf-suggestion id="sug-copy">
  <lf-old><p id="old-line">Refill every feeder each morning.</p></lf-old>
  <lf-new><p>Refill a feeder when its camera shows it half-empty.</p></lf-new>
</lf-suggestion>
<lf-diagram id="small"><pre>
graph LR
  S[Redis] -->|hit| H[handle]
  S -->|miss| F[cookie]
  F --> H
</pre></lf-diagram>
<lf-diagram id="flow"><pre>
graph LR
  R[request] --> C{cookie valid?}
  C -->|yes| S[read session from Redis]
  S -->|hit| H[handle]
  S -->|miss/outage| F[verify signed fallback]
  F --> H
  C -->|no| L[login]
</pre></lf-diagram>
""",
)

# Where each drawing sits against the column it explains and the controls it must not
# reach. The axis is the column's, because that is the line the prose is centred on and
# the one an exhibit off it reads as having slipped.
DRAWING_PLACEMENT = """() => {
    const main = document.querySelector('main'), ms = getComputedStyle(main);
    const mb = main.getBoundingClientRect();
    const col = { left: mb.left + parseFloat(ms.paddingLeft),
                  right: mb.right - parseFloat(ms.paddingRight) };
    col.axis = (col.left + col.right) / 2;
    const acts = document.querySelector('.lf-sug-actions');
    // The drawing's own rect and the box's. A drawing wider than its box keeps a rect
    // that runs on past it — the layout's answer, not the reader's — so what is painted
    // over the margin is the box's edge and what is lost off the scroll's start edge is
    // the drawing's left against the box's.
    const at = (id) => {
        const holder = document.getElementById(id);
        const b = holder.querySelector('svg').getBoundingClientRect();
        const h = holder.getBoundingClientRect();
        return { left: b.left, right: b.right, width: b.width,
                 offAxis: (b.left + b.right) / 2 - col.axis,
                 box: { left: h.left, right: h.right },
                 scrolls: holder.scrollWidth > holder.clientWidth };
    };
    return { col, docked: acts.classList.contains('lf-docked'),
             rail: acts.getBoundingClientRect().left,
             small: at('small'), flow: at('flow'),
             sideways: document.body.scrollWidth - document.body.clientWidth };
}"""
# A widget that declares width beside one that doesn't, so what the assertions turn on is
# the declaration and not the tag: both are widgets, both hold more than the column shows
# comfortably, and only one of them is entitled to more of the window than the prose gets.
WIDE_AND_NARROW_PAGE = leaf_page(
    "room",
    """
<h1 id="t">Release</h1>
<p id="prose">The board is as wide as its columns are; this sentence is not.</p>
<lf-board id="sprint">
  <lf-column id="col-todo" label="Todo">
    <lf-card id="card-heater"><strong>Heated perch</strong> Wire the south feeder.</lf-card>
  </lf-column>
  <lf-column id="col-doing" label="Doing">
    <lf-card id="card-baffle"><strong>Squirrel baffle</strong></lf-card>
  </lf-column>
  <lf-column id="col-review" label="Review"></lf-column>
  <lf-column id="col-done" label="Done"></lf-column>
</lf-board>
<lf-diff id="patch"><pre>
diff --git a/feeders/mount.py b/feeders/mount.py
--- a/feeders/mount.py
+++ b/feeders/mount.py
@@ -1,3 +1,3 @@
 def bracket():
-    return "plastic"
+    return "steel"
</pre></lf-diff>
""",
)

# main's content box, body's, the page's own box, and where each named element stands in
# them. Read together in one pass because the whole subject is their relation: a width
# means nothing here except against the column it is or isn't wider than.
ROOM_GEOMETRY = """() => {
    const span = (el) => {
        const s = getComputedStyle(el), b = el.getBoundingClientRect();
        const left = b.left + parseFloat(s.paddingLeft);
        const right = b.right - parseFloat(s.paddingRight);
        return { left, right, width: right - left, centre: (left + right) / 2 };
    };
    const box = (id) => {
        const el = document.getElementById(id);
        if (!el) return null;
        const b = el.getBoundingClientRect();
        return { left: b.left, right: b.right, width: b.width,
                 top: b.top, bottom: b.bottom,
                 centre: (b.left + b.right) / 2 };
    };
    // The page's box: what body's padding is spent out of and the column centres in.
    // It is not the window. Body owns the document's scroll and reserves a stable
    // gutter for it (leaf.js), so wherever a scrollbar takes room the page is that
    // much narrower than the window and stands half of it to the window's left — a
    // settled decision made where the gutter is, and one no strip has a part in.
    // Padding included, because a strip taken here moves the column inside a box that
    // has not changed size; `room` above is what the strips left and so cannot say
    // where the edge they came out of is.
    const page = () => {
        const b = document.body, s = getComputedStyle(b);
        const left = b.getBoundingClientRect().left + parseFloat(s.borderLeftWidth);
        return { left, right: left + b.clientWidth, width: b.clientWidth,
                 centre: left + b.clientWidth / 2 };
    };
    return { column: span(document.querySelector('main')),
             room: span(document.body), pageBox: page(),
             board: box('sprint'), diff: box('patch'), prose: box('prose'),
             note: box('note'), later: box('later'),
             sideways: document.body.scrollWidth - document.body.clientWidth };
}"""
# A wide widget inside each of the two kinds of holder: a box that paints (the quoted
# frame, the option's card, the metric, the nested task's rail, the note a code block
# builds, the page's own div) and a wrapper that doesn't (a plain section). The div is
# the case the theme cannot name: it draws its box in the page's own style and declares
# the frame there, which is the whole of what a project writes to hold an exhibit inside
# its own card.
FRAMED_WIDE_PAGE = leaf_page(
    "framed",
    """
<h1 id="t">Framed</h1>
<section id="loose">
  <lf-board id="in-section">
    <lf-column id="s1" label="Todo"><lf-card id="sk1"><strong>One</strong></lf-card></lf-column>
    <lf-column id="s2" label="Done"></lf-column>
  </lf-board>
</section>
<lf-specimen id="quoted" label="a board">
  <lf-board id="in-specimen">
    <lf-column id="q1" label="Todo"><lf-card id="qk1"><strong>One</strong></lf-card></lf-column>
    <lf-column id="q2" label="Done"></lf-column>
  </lf-board>
</lf-specimen>
<lf-options id="pick" choose>
  <lf-option id="opt-a"><strong>With evidence</strong>
    <lf-diagram id="in-card"><pre>
graph LR
  A[request] --> B[queue]
  B --> C[worker]
</pre></lf-diagram>
  </lf-option>
  <lf-option id="opt-b"><strong>Without</strong></lf-option>
</lf-options>
<lf-options id="row-pick" choose>
  <lf-option id="row-a">Along the fence line
    <lf-diagram id="in-row"><pre>
graph LR
  A[house] --> B[shed]
  B --> C[feeder]
  C --> D[bath]
  D --> E[gate]
  E --> F[pole]
  F --> G[box]
</pre></lf-diagram>
  </lf-option>
  <lf-option id="row-b">Under the lawn in a trench</lf-option>
</lf-options>
<lf-board id="evidence">
  <lf-column id="e1" label="Todo"><lf-card id="ek1"><strong>With evidence</strong>
    <lf-diagram id="in-board-card"><pre>
graph LR
  A[request] --> B[queue]
  B --> C[worker]
</pre></lf-diagram>
  </lf-card></lf-column>
  <lf-column id="e2" label="Done"></lf-column>
</lf-board>
<lf-metrics id="nums">
  <lf-metric id="me1" value="410ms">p95, with the path it measures
    <lf-diagram id="in-metric"><pre>
graph LR
  A[request] --> B[queue]
  B --> C[worker]
</pre></lf-diagram>
  </lf-metric>
</lf-metrics>
<lf-tasks id="plan">
  <lf-task id="t-outer" status="active"><strong>Rebuild the feeders</strong>
    <lf-task id="t-inner" status="review"><strong>Fit the baffles</strong>
      <lf-diagram id="in-task"><pre>
graph LR
  A[request] --> B[queue]
  B --> C[worker]
</pre></lf-diagram>
    </lf-task>
  </lf-task>
</lf-tasks>
<lf-code id="walk" language="python" hi="2"><pre>
def bracket(temp):
    if temp &lt; 0:
        return "steel"
    return "cedar"
</pre>
  <lf-note id="line-note" at="2">Freezing is the only threshold that matters.
    <lf-diagram id="in-note"><pre>
graph LR
  A[request] --> B[queue]
  B --> C[worker]
</pre></lf-diagram>
  </lf-note>
</lf-code>
<div id="own-box" style="border: 1px solid #999; padding: 10px; --lf-frame: 1">
  <lf-diagram id="in-own-box"><pre>
graph LR
  A[request] --> B[queue]
  B --> C[worker]
</pre></lf-diagram>
</div>
""",
)

# A box of the page's own that both draws and scrolls, holding a wide widget. The theme
# has no rule for a project's box and cannot, so what stands between it and a page drawn
# wrong is the gate — and the gate could not see through the scroll: `answeredFor`
# excused anything inside one, which is every card on every board.
FRAMED_SCROLLER_PAGE = FRAMED_WIDE_PAGE.replace(
    "<main>",
    "<main>\n<div id='own-frame' style='border: 1px solid #999; overflow-x: auto'>"
    "<lf-board id='framed'><lf-column id='f1' label='Todo'>"
    "<lf-card id='fk1'><strong>One</strong></lf-card></lf-column>"
    "<lf-column id='f2' label='Done'></lf-column></lf-board></div>",
)


# A page that reserves the margin rail and stands a wide widget in the flow beside it —
# the pair no shipped example had until ship-review, and the pair the room has to be
# measured after rather than before.
RAIL_AND_WIDE_PAGE = leaf_page(
    "rail",
    """
<h1 id="t">Release</h1>
<lf-suggestion id="sug-copy">
  <lf-old><p id="old-line">Refill every feeder each morning.</p></lf-old>
  <lf-new><p>Refill a feeder when its camera shows it half-empty.</p></lf-new>
</lf-suggestion>
<lf-board id="plan">
  <lf-column id="r1" label="Todo"><lf-card id="rk1"><strong>One</strong></lf-card></lf-column>
  <lf-column id="r2" label="Doing"></lf-column>
  <lf-column id="r3" label="Done"></lf-column>
</lf-board>
""",
)


# How far the exhibit stands outside the page's own box, and the rail it was supposed to
# leave — both edges, since a room read too wide spends itself on whichever side is free.
# One reading for the live page and for a copy of it, the fault being the same fault. The
# room the page states comes with it, so a test waiting for the box to be read again has
# the reading it is waiting to see changed.
RAIL_FIT = """() => {
    const b = document.body, s = getComputedStyle(b);
    const box = b.getBoundingClientRect();
    const r = document.getElementById('plan').getBoundingClientRect();
    return { rail: s.paddingRight, widget: r.width,
             room: getComputedStyle(document.documentElement)
                     .getPropertyValue('--lf-room'),
             past: Math.max(r.right - (box.right - parseFloat(s.paddingRight)),
                            (box.left + parseFloat(s.paddingLeft)) - r.left),
             content: box.width - parseFloat(s.paddingLeft)
                      - parseFloat(s.paddingRight) };
}"""
# The room the document leaves at each end for a bar standing over it. Both are boxes in
# the flow, so the reading is the flow's own: what stands above the page's first block and
# what is left under its last.
CHROME_ROOM = """() => {
    const body = document.body;
    const box = document.querySelector('main').getBoundingClientRect();
    return { head: box.top + body.scrollTop,
             foot: body.scrollHeight - (box.bottom + body.scrollTop),
             banner: document.querySelector('.lf-banner').offsetHeight,
             line: document.querySelector('.lf-keyline').offsetHeight };
}"""
# The same reading taken at the stamp, which is the one moment nothing out here can
# reach: a MutationObserver's callback is a microtask off the stamp's own write, and
# the frame after it is where the runtime's layout observer restates the room.
AT_THE_HANDOVER = (
    "window.__handover = null;\n"
    "new MutationObserver(() => { window.__handover ??= (" + RAIL_FIT + ")(); })\n"
    '  .observe(document, { subtree: true, attributeFilter: ["data-lf-upgraded"] });'
)
LATE_MARGIN_PAGE = leaf_page(
    "late margin",
    """
<h1 id="t">Release</h1>
<lf-callout id="marginal"><strong>Note</strong> Its controls hang in the margin.</lf-callout>
<lf-board id="plan">
  <lf-column id="r1" label="Todo"><lf-card id="rk1"><strong>One</strong></lf-card></lf-column>
  <lf-column id="r2" label="Doing"></lf-column>
  <lf-column id="r3" label="Done"></lf-column>
</lf-board>
""",
)

# A widget that hangs its controls in the page margin, and can only say how wide a margin
# once it has heard what they will say — so the claim rides an answer rather than the
# upgrade that asked for it. lf-suggestion is the same widget with a measurement it
# happens to be able to take on the spot, which is why the moment a claim lands was never
# anybody's subject. The request is answered by the test, which is what puts the claim
# after the handover on every machine rather than on a fast one.
LATE_MARGIN_WIDGET = """\
import { once } from "/runtime/widget-api.js";

customElements.define(
  "lf-callout",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      fetch("/margin-width").then(() =>
        document.body.style.setProperty("--strip-r", "160px"),
      );
    }
  },
);
"""
# Where the two things in the right margin stand, and how much of the board is over the
# controls. The controls are what the strip was reserved for, and they hang off the column
# rather than out of the strip, so the strip's own edge says nothing about where they are.
RAIL_BAND_PAGE = leaf_page(
    "rail band",
    """
<h1 id="t">Release</h1>
<lf-suggestion id="sug-copy">
  <lf-old><p id="old-line">Refill every feeder each morning.</p></lf-old>
  <lf-new><p>Refill a feeder when its camera shows it half-empty.</p></lf-new>
</lf-suggestion>
<lf-board id="plan">
  <lf-column id="r1" label="Todo"><lf-card id="rk1"><strong>One</strong>
    <lf-suggestion id="sug-card">
      <lf-old><p>By hand.</p></lf-old>
      <lf-new><p>On the timer.</p></lf-new>
    </lf-suggestion></lf-card></lf-column>
  <lf-column id="r2" label="Doing"></lf-column>
  <lf-column id="r3" label="Done"></lf-column>
</lf-board>
<p id="gap" style="margin-block: 600px">Prose far enough below the changes that no row
reaches this part of the page.</p>
<lf-board id="later">
  <lf-column id="l1" label="Todo"><lf-card id="lk1"><strong>Two</strong></lf-card></lf-column>
  <lf-column id="l2" label="Done"></lf-column>
</lf-board>
""",
)


RAIL_BANDS = """() => {
    const box = (el) => {
        const b = el.getBoundingClientRect();
        return { left: b.left, right: b.right, top: b.top, bottom: b.bottom,
                 width: b.width };
    };
    const body = document.body, bs = getComputedStyle(body);
    const bb = body.getBoundingClientRect();
    const m = document.querySelector('main');
    const ms = getComputedStyle(m), mb = m.getBoundingClientRect();
    return { rows: [...document.querySelectorAll('.lf-sug-actions')].map(r => ({
                 ...box(r), docked: r.classList.contains('lf-docked') })),
             plan: box(document.getElementById('plan')),
             later: box(document.getElementById('later')),
             column: { left: mb.left + parseFloat(ms.paddingLeft),
                       right: mb.right - parseFloat(ms.paddingRight) },
             pageRight: bb.right - parseFloat(bs.paddingRight),
             sideways: body.scrollWidth - body.clientWidth };
}"""


DRAWN_PAST_A_RAIL_PAGE = leaf_page(
    "drawn past a rail",
    """
<h1 id="t">Flow</h1>
<lf-suggestion id="sug-copy">
  <lf-old><p id="old-line">Refill every feeder each morning.</p></lf-old>
  <lf-new><p>Refill a feeder when its camera shows it half-empty.</p></lf-new>
</lf-suggestion>
<p id="gap" style="margin-block: 600px">Prose far enough below the change that its row
reaches nothing here.</p>
<lf-diagram id="flow"><pre>
graph LR
  R[request] --> C{cookie valid?}
  C -->|yes| S[read session from Redis]
  S -->|hit| H[handle]
  C -->|no| L[login]
</pre></lf-diagram>
""",
)
# A page hanging apparatus of its own in the margin, level with a wide widget. The theme
# has no rule for a project's own furniture and cannot — this is the case the two claims
# in it are declarations of, seen from the side where nobody has declared anything.
OWN_MARGIN_FURNITURE = WIDE_AND_NARROW_PAGE.replace(
    "<main>",
    "<main>\n<div id='own-rail' style='position: absolute; left: 100%;"
    " margin-left: 22px; top: 0; width: 160px; height: 600px'>Mine.</div>",
)
# One reply holding both answers to the question the block-content lists ask: chips are
# set among the words, a paragraph is not. The pair is the point — the stacking rule
# reaching neither group would read as a pass on the first half alone.
INLINE_REPLY_MARKUP = (
    '<lf-compare id="rp-terse">'
    '<lf-variant id="rp-redis"><lf-chip>a service</lf-chip>Redis</lf-variant>'
    '<lf-variant id="rp-cookie"><lf-chip>no service</lf-chip>Signed cookie</lf-variant>'
    "</lf-compare>"
    '<lf-compare id="rp-argued">'
    '<lf-variant id="rp-keep"><p>Keep the store, and the operator that comes with it.</p></lf-variant>'
    '<lf-variant id="rp-drop"><p>Drop it, and read sessions off the cookie alone.</p></lf-variant>'
    "</lf-compare>"
)
# The two things on this page that want a margin, on one page and level with each other.
# The note is written immediately before the board so they share a band of the page rather
# than stacking, which is the only arrangement in which either can be over the other.
NOTE_AND_WIDE_PAGE = leaf_page(
    "room and margin",
    """
<h1 id="t">Feeders</h1>
<p id="prose">The board is as wide as its columns are; this sentence is not.</p>
<aside class="sidenote" id="note">Counts are the warden's own, taken at dawn from the
south hide, and the perch numbers are the ones she disputes.</aside>
<lf-board id="sprint">
  <lf-column id="col-todo" label="Todo">
    <lf-card id="card-heater"><strong>Heated perch</strong> Wire the south feeder.</lf-card>
  </lf-column>
  <lf-column id="col-doing" label="Doing">
    <lf-card id="card-baffle"><strong>Squirrel baffle</strong></lf-card>
  </lf-column>
  <lf-column id="col-review" label="Review"></lf-column>
  <lf-column id="col-done" label="Done"></lf-column>
</lf-board>
<p id="gap" style="margin-block: 600px">Prose far enough below the note that nothing of
it reaches this part of the page.</p>
<lf-board id="later">
  <lf-column id="late-todo" label="Todo">
    <lf-card id="card-seed"><strong>Seed mix</strong> Switch to sunflower hearts.</lf-card>
  </lf-column>
  <lf-column id="late-done" label="Done"></lf-column>
</lf-board>
""",
)

# Wide enough that the note has its strip (1152px) and narrow enough that the room, not
# the shared cap, is what decides the board's width — above about 1560px the cap binds
# first and the two never compete. A window inside that band is where the question is live.
NOTE_BAND = 1280


def _painted_line(page):
    """Every row in the gesture's next key-line paint, including rows behind More.

    Consume the coalesced frame once: polling could pass on an unrelated later paint.
    Read rows rather than visible text because hidden rows still state liveness.
    """
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    return page.eval_on_selector_all(
        ".lf-keyline .lf-key",
        "els => els.map(e => [...e.children].map(c => c.textContent).join(' '))",
    )


SCROLLED = "() => document.body.scrollTop > 0"


WHERE_I_STAND_PAGE = leaf_page(
    "where i stand",
    """
<h1 id="t">Standing</h1>
<p id="p1">A first passage, with a <a href="https://example.invalid/spec">link into the
spec</a> so the walk has somewhere to stand that is not an ask.</p>
<lf-options id="shape" choose>
  <lf-option id="sh-steel"><strong>Steel</strong> Galvanised, and the
  <a href="https://example.invalid/steel">spec for it</a> is short.</lf-option>
  <lf-option id="sh-cedar"><strong>Cedar</strong> Cheap; needs sealing.</lf-option>
</lf-options>
<lf-options id="settled" choose settled>
  <lf-option id="st-keep" chosen><strong>Keep it</strong> Decided last week, with the
  <a href="https://example.invalid/keep">note behind it</a>.</lf-option>
  <lf-option id="st-drop"><strong>Drop it</strong> The alternative.</lf-option>
</lf-options>
<p id="p2">A passage carrying
<lf-suggestion id="sug-window">
  <lf-old>Refill every feeder each morning.</lf-old>
  <lf-new>Refill when the camera shows it half-empty.</lf-new>
</lf-suggestion></p>
""",
)
