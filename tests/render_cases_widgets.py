"""Shared widgets browser-integration cases and readings."""

from leaf import anchor_capture as anchor_capture_model
from leaf import passages as passages_model
from leaf.registry import storage as registry_storage
from render_harness import (
    RENDERED,
    leaf_page,
)

# ---------- anchors written without a browser ----------
# `leaf comment` writes an anchor by reading the mapped revision; the runtime
# resolves it against the DOM that revision becomes. Nothing static can check that those
# two readings agree, and every way they can come apart — a widget's upgrade, an
# attribute rendered as text, the space a block boundary stands for — only exists
# once the page is loaded.


def written_anchors(page_dir, html, limit=40):
    """Anchors `leaf comment` would write for windows over a page's own prose. A
    window the page says twice, or one crossing a fence, is refused on purpose —
    skipping those here is that refusal, and what survives is exactly what the command
    promises to place."""
    registry = registry_storage.load_registry(page_dir)
    text = passages_model.page_passages(html, registry).text
    words = text.split(" ")
    anchors = []
    for start in range(0, len(words), 3):
        quote = " ".join(words[start : start + 8])
        if len(quote) < 20:
            continue
        try:
            anchors.append(
                (
                    quote,
                    anchor_capture_model.capture_anchor(html, registry, quote, None),
                )
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
</pre></lf-diagram>
""",
)
GENERIC_VISUAL_PAGE = leaf_page(
    "registered visual parts",
    """
<h1 id="title">Registered visual parts</h1>
<lf-test-visual id="visual" parts="outer inner html"></lf-test-visual>
""",
)
GENERIC_VISUAL_LAYER = {
    "lf-test-visual": {
        "description": "A generic rendered visual used to exercise Leaf's package contract.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
            "parts": {"type": "string", "minLength": 1},
        },
        "required": ["id", "parts"],
        "additionalProperties": False,
        "x-content": "none",
        "x-upgrade": True,
        "x-visual": {"parts": "parts"},
        "x-example": '<lf-test-visual id="visual" parts="outer inner html"></lf-test-visual>',
    }
}
GENERIC_VISUAL_WIDGETS = {
    "lf-test-visual.js": """
import { once, registerVisualParts } from '/runtime/widget-api.js';

customElements.define('lf-test-visual', class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    this.innerHTML = `<svg viewBox="0 0 240 120" width="240" height="120">
      <g id="outer">
        <rect id="outer-surface" x="10" y="10" width="220" height="100" rx="8"
              fill="#dbeafe" stroke="#2563eb" stroke-width="2"></rect>
        <line id="outer-decoration" x1="25" y1="36" x2="215" y2="36"
              stroke="#2563eb" stroke-width="2"></line>
        <g id="inner">
          <path d="M120 44 L158 76 L120 104 L82 76 Z"
                fill="#fef3c7"></path>
          <line x1="100" y1="76" x2="140" y2="76"
                stroke="#d97706" stroke-width="2"></line>
        </g>
      </g>
    </svg>
    <div id="html" style="width: 220px; padding: 8px;">
      <span id="html-surface" style="display: inline-block; border-radius: 12px; padding: 4px 10px; background: #dbeafe;">HTML surface</span>
      <span id="html-decoration"> · decoration</span>
    </div>`;
    const outer = this.querySelector('#outer');
    const inner = this.querySelector('#inner');
    const outerSurface = this.querySelector('#outer-surface');
    const html = this.querySelector('#html');
    const htmlSurface = this.querySelector('#html-surface');
    this.parts = [
      { id: 'outer', element: outer, surface: outerSurface, label: 'Outer store' },
      { id: 'inner', element: inner, label: 'Inner decision' },
      { id: 'html', element: html, surface: htmlSurface, label: 'HTML target' },
    ];
    this.visualRegistration = registerVisualParts(this, () => this.parts);
    this.redraw = () => {
      outerSurface.setAttribute('rx', '28');
      this.visualRegistration.update();
    };
  }
});
"""
}
SHADOW_VISUAL_PAGE = leaf_page(
    "shadow visual clipping",
    """
<h1 id="title">Shadow visual clipping</h1>
<lf-test-shadow-visual id="shadow-visual" parts="wide"></lf-test-shadow-visual>
""",
)
SHADOW_VISUAL_LAYER = {
    "lf-test-shadow-visual": {
        "description": "A clipped shadow-root visual used to exercise Leaf's package contract.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
            "parts": {"type": "string", "minLength": 1},
        },
        "required": ["id", "parts"],
        "additionalProperties": False,
        "x-content": "none",
        "x-upgrade": True,
        "x-shadow": True,
        "x-visual": {"parts": "parts"},
        "x-example": '<lf-test-shadow-visual id="shadow-visual" parts="wide"></lf-test-shadow-visual>',
    }
}
SHADOW_VISUAL_WIDGETS = {
    "lf-test-shadow-visual.js": """
import { once, registerVisualParts, shadowStage } from '/runtime/widget-api.js';

customElements.define('lf-test-shadow-visual', class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    Object.assign(this.style, {
      display: 'block',
      width: '100px',
      height: '60px',
      overflow: 'hidden',
    });
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 220 60');
    svg.setAttribute('width', '220');
    svg.setAttribute('height', '60');
    svg.style.cssText = 'display: block; max-width: none';
    svg.innerHTML = `<rect id="wide-surface" x="10" y="10" width="200" height="40"
      rx="8" fill="#dcfce7" stroke="#16a34a" stroke-width="2"></rect>`;
    shadowStage(this, [svg]);
    const surface = this.shadowRoot.querySelector('#wide-surface');
    this.visualRegistration = registerVisualParts(this, () => [
      { id: 'wide', element: surface, label: 'Clipped wide surface' },
    ]);
  }
});
""",
}
# Every supported structural diagram whose authored ids reach a drawn box. State
# machines carry nested boxes and ER entities carry attribute tables, while sequence
# and class diagrams exercise source ids outside the flowchart renderer.
TYPED_PARTS_PAGE = leaf_page(
    "typed diagram parts",
    """
<h1 id="t">One runner</h1>
<lf-diagram id="life" parts="node:Queued node:Working node:Build"><pre>
stateDiagram-v2
  [*] --&gt; Queued
  Queued --&gt; Working
  state Working {
    Fetch --&gt; Build
  }
  Working --&gt; Done
</pre></lf-diagram>
<lf-diagram id="shape" parts="node:RUNNER"><pre>
erDiagram
  RUNNER {
    string id PK
    string name
  }
  RUNNER ||--o{ JOB : runs
</pre></lf-diagram>
<lf-diagram id="path" parts="node:A"><pre>
graph LR
  A["Bold and plain"] --&gt; B[after]
</pre></lf-diagram>
<lf-diagram id="exchange" parts="node:Reader"><pre>
sequenceDiagram
  participant Reader
  participant Server
  Reader-&gt;&gt;Server: Request
</pre></lf-diagram>
<lf-diagram id="model" parts="node:Job"><pre>
classDiagram
  class Job {
    +run()
  }
  class Runner
  Runner --&gt; Job
</pre></lf-diagram>
<lf-diagram id="trend"><pre>
xychart-beta
  title "Checks"
  x-axis [One, Two, Three]
  y-axis "Complete" 0 --&gt; 12
  line [4, 9, 12]
</pre></lf-diagram>
""",
)
# One state inserted above the anchored one, which rebuilds the drawing around it. The
# authored token does not move.
TYPED_PARTS_V2 = leaf_page(
    "typed diagram parts",
    """
<h1 id="t">One runner</h1>
<lf-diagram id="life" parts="node:Queued node:Working node:Build"><pre>
stateDiagram-v2
  [*] --&gt; Fresh
  Fresh --&gt; Queued
  Queued --&gt; Working
  state Working {
    Fetch --&gt; Build
  }
  Working --&gt; Done
</pre></lf-diagram>
<lf-diagram id="shape" parts="node:RUNNER"><pre>
erDiagram
  RUNNER {
    string id PK
    string name
  }
  RUNNER ||--o{ JOB : runs
</pre></lf-diagram>
<lf-diagram id="exchange" parts="node:Reader"><pre>
sequenceDiagram
  participant Reader
  participant Server
  Reader-&gt;&gt;Server: Request
</pre></lf-diagram>
<lf-diagram id="model" parts="node:Job"><pre>
classDiagram
  class Job {
    +run()
  }
  class Runner
  Runner --&gt; Job
</pre></lf-diagram>
<lf-diagram id="trend"><pre>
xychart-beta
  title "Checks"
  x-axis [One, Two, Three]
  y-axis "Complete" 0 --&gt; 12
  line [4, 9, 12]
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
    const probe = document.createElement('i');
    probe.style.cssText = 'position:fixed;visibility:hidden;height:0;padding:0;border:0;width:var(--lf-room)';
    main.append(probe);
    const room = probe.getBoundingClientRect().width;
    probe.remove();
    return { drawn: svg.getBoundingClientRect().width,
             natural: svg.viewBox.baseVal.width,
             box: holder.clientWidth,
             room,
             wide: parseFloat(getComputedStyle(document.body)
                       .getPropertyValue('--wide')),
             board: board.getBoundingClientRect().width,
             column: mb.width - parseFloat(ms.paddingLeft) - parseFloat(ms.paddingRight),
             scrolls: holder.scrollWidth > holder.clientWidth,
             sideways: document.body.scrollWidth - document.body.clientWidth };
}"""
# A diagram whose renderer rejects the type, which is the shape of every soft failure: the
# module replaces the element's body with the message and the source it choked on. Its
# first line is the length a real source has, because that line is what the box under
# test is floored at: written short, this page passed the assertion below with the rule
# it stands on deleted.
BROKEN_DIAGRAM_PAGE = leaf_page(
    "broken diagram",
    """
<h1 id="t">Broken</h1>
<lf-diagram id="bad"><pre>
gantt
  title POST /api/event {kind: "action", widget: "lf-board", detail: {card: "card-heater", column: "ready"}}
  dateFormat YYYY-MM-DD
  unsupported renderer type :done, 2026-01-01, 1d
</pre></lf-diagram>
""",
)
# Every chart kind on one page, each body small enough to count the marks it should have
# produced by hand. A reading that only ever meets bars says nothing about the four other
# routes through the module, and each of them hands Plot a different mark.
CHART_PAGE = leaf_page(
    "charts",
    """
<h1 id="t">Charts</h1>
<lf-chart id="c-bars" kind="bars" y="merged"><pre>
quarter, apps, infra
Q1, 12, 7
Q2, 19, 11
Q3, 14, 17
</pre></lf-chart>
<lf-chart id="c-rows" kind="rows" y="open"><pre>
area, open
platform infrastructure, 42
billing, 19
</pre></lf-chart>
<lf-chart id="c-stack" kind="stack" y="hours"><pre>
week, features, fixes
w1, 21, 9
w2, 18, 14
</pre></lf-chart>
<lf-chart id="c-line" kind="line" y="hours to review"><pre>
week, backend
2026-06-01, 31
2026-06-08, 26
2026-06-15, 19
</pre></lf-chart>
<lf-chart id="c-dots" kind="dots" y="minutes"><pre>
lines changed, review
12, 4
90, 26
310, 71
</pre></lf-chart>
""",
)
# What a chart drew, read off the composed drawing rather than off the body it came from.
# Marks are found by the class the module puts on each series, because that class is the
# whole of its colour contract: nothing else in the drawing carries a series' identity,
# and the colour itself is the stylesheet's answer to it.
CHART_MARKS = """(id) => {
    const svg = document.getElementById(id).querySelector('svg');
    if (!svg) return null;
    const probe = document.createElement('span');
    document.body.append(probe);
    const token = (n) => {
        probe.style.color = `var(--series-${n})`;
        return getComputedStyle(probe).color;
    };
    const series = [...svg.querySelectorAll('[class^="lf-series-"]')].map((g) => {
        const n = Number(g.getAttribute('class').replace('lf-series-', ''));
        const shapes = [...g.querySelectorAll('rect, circle, path')];
        const paint = shapes.length ? getComputedStyle(shapes[0]) : null;
        return { n, shapes: shapes.length, tag: shapes[0] && shapes[0].tagName,
                 worn: paint && [paint.fill, paint.stroke], token: token(n) };
    });
    probe.remove();
    return {
        series,
        // A colour the module wrote into the drawing, which would freeze the scheme this
        // browser happened to be in when the copy was exported.
        painted: svg.outerHTML.match(/(?:fill|stroke)="#[0-9a-fA-F]{3,8}"/g) || [],
        // The painted box of the first tick label. Its computed font-size is the theme's
        // and cannot move; what a scaled drawing changes is the box.
        tick: (() => { const r = svg.querySelector('text').getBoundingClientRect();
                       return [Math.round(r.width), Math.round(r.height)]; })(),
        width: Number(svg.getAttribute('width')),
        room: Math.round(document.getElementById(id).clientWidth),
    };
}"""
# What the axes have to do when the room runs out: five names that each take about as much
# room as a band has, and a series whose numbers are wider than the axis they are labelled
# on. Read at a phone's width, where the column is a third of what the corpus is drawn at.
CROWDED_CHART_PAGE = leaf_page(
    "crowded charts",
    """
<h1 id="t">Crowded</h1>
<lf-chart id="crowd-band" kind="bars" y="gas, kWh a winter"><pre>
winter, meter
2021-22, 11840
2022-23, 10920
2023-24, 11510
2024-25, 12260
2025-26, 10480
</pre></lf-chart>
<lf-chart id="crowd-wide" kind="bars" y="bytes"><pre>
tier, bytes
cache, 128400000000
disk, 291000000000
</pre></lf-chart>
<lf-chart id="crowd-rows" kind="rows" y="watts lost"><pre>
element, loss
the single-glazed bay window in the front room, 410
uninsulated loft hatch, 265
</pre></lf-chart>
""",
)
# Every pair of words the drawing paints, and whether any two of them are in the same
# place. Rectangles rather than a sort along one axis: a value axis stacks its labels at
# one left edge, and a reading that compared neighbours by x alone called every one of
# those a collision.
CHART_COLLISIONS = """() => {
    const hit = (a, b) =>
        a.left < b.right - 0.5 && b.left < a.right - 0.5 &&
        a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5;
    const found = [];
    for (const el of document.querySelectorAll('lf-chart')) {
        const svg = el.querySelector('svg');
        if (!svg) { found.push({chart: el.id, pair: 'drew nothing'}); continue; }
        const words = [...svg.querySelectorAll('text')]
            .map((t) => [t.textContent, t.getBoundingClientRect()]);
        for (let i = 0; i < words.length; i++)
            for (let j = i + 1; j < words.length; j++)
                if (hit(words[i][1], words[j][1]))
                    found.push({chart: el.id, pair: `${words[i][0]} / ${words[j][0]}`});
    }
    return found;
}"""
# The bodies the module refuses, each for its own reason. The last three are the ones a
# count of marks cannot see: every one of them draws a chart that looks like a chart and
# says something the body does not.
BAD_CHART_PAGE = leaf_page(
    "bad charts",
    """
<h1 id="t">Bad</h1>
<lf-chart id="bad-cell" kind="bars" y="merged"><pre>
quarter, merged
Q1, 12
Q2, twelve
</pre></lf-chart>
<lf-chart id="bad-count" kind="bars" y="merged"><pre>
quarter, a, b, c, d, e, f
Q1, 1, 2, 3, 4, 5, 6
</pre></lf-chart>
<lf-chart id="bad-twice" kind="bars" y="merged"><pre>
quarter, merged
Q1, 12
Q1, 19
</pre></lf-chart>
<lf-chart id="bad-sign" kind="stack" y="hours"><pre>
week, features, fixes
w1, 21, -9
</pre></lf-chart>
<lf-chart id="bad-blank" kind="bars" y="merged"><pre>
quarter, apps, infra
Q1, 12,
Q2, 19,
</pre></lf-chart>
""",
)
# A chart an agent sent in a reply, which upgrades inside a panel nobody has opened yet.
CHART_MARKUP = (
    '<lf-chart id="{id}" kind="bars" y="merged"><pre>\n'
    "quarter, merged\nQ1, 12\nQ2, 19\n</pre></lf-chart>"
)
CHART_IN_A_MESSAGE_PAGE = leaf_page(
    "chart in a message",
    """
<h1 id="t">Sent</h1>
<p id="p">The reply carries the drawing.</p>
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
@@ -1,2 +1,2 @@
 def bracket():
-    return "plastic"
+    return "steel"
</pre></lf-diff>
""",
)

# A patch with the two things the shipped review has and a one-hunk fixture cannot: more
# than one hunk in a file, and a line far longer than the box it renders in. Every hunk is
# the same six lines — one leading context, the change, three trailing — so the `@@` counts
# are the same arithmetic each time and the line a walk should land on is the number in
# the header beside it. The long line is a real one: 46 files of Rust and Markdown put the
# worst overhang at 2,563px, and this is a comment sentence of about that width.
_LONG = (
    "The comparison base is the merge-base with the default branch, or with its "
    "upstream when the branch was pushed from a fork, so a review reads the same "
    "way whichever remote it came from and nothing here depends on the checkout."
)


def _hunk(start, was, now):
    """One hunk: context, the change, three more context. Old and new both count five."""
    return (
        f"@@ -{start},5 +{start},5 @@\n"
        f" def line_{start}():\n"
        f"-    return {was}\n"
        f"+    return {now}\n"
        f"     # first tail\n"
        f"     # second tail\n"
        f"     # third tail\n"
    )


MULTI_HUNK_PATCH = (
    "diff --git a/app/handlers.py b/app/handlers.py\n"
    "--- a/app/handlers.py\n"
    "+++ b/app/handlers.py\n"
    + _hunk(1, '"old first"', '"new first"')
    + _hunk(40, '"old second"', '"new second"')
    + _hunk(80, '"old third"', f'"{_LONG}"')
    + "diff --git a/app/routes.py b/app/routes.py\n"
    "--- a/app/routes.py\n"
    "+++ b/app/routes.py\n" + _hunk(200, '"old route"', '"new route"')
)


def _filler(name, count):
    return "".join(
        f"<p id='{name}-{n}'>The handler change, described at length, paragraph {n}.</p>"
        for n in range(count)
    )


# Bound to a feed rather than written inline, because that is the form a review arrives in
# and the only one whose lines are commentable data: `projectData` keys each row by file,
# side and source line, which is the coordinate a remark on a line is recorded at.
# Prose either side of it so the patch has somewhere to be scrolled from and somewhere to
# be scrolled to — a page whose whole diff fits on screen proves nothing about a header
# staying put while its rows go past, and one whose diff ends at the document's foot
# cannot be scrolled far enough to find out.
LONG_LINE_DIFF_PAGE = leaf_page(
    "patch",
    "<h1 id='t'>Review</h1>"
    + _filler("lead", 30)
    + '<lf-diff id="patch" source="review-patch"><pre></pre></lf-diff>'
    + _filler("tail", 30),
)

# The same review bound as a manifest of collapsed files, the form a captured patch
# arrives in on the shipped walkthrough: the module draws the file rows from the manifest
# alone and parses no line until a reader opens a file, which is where the renderer comes
# in. One diff and nothing else that draws lines, so what the page asks for at load is
# the manifest's answer and no other widget's.
MANIFEST_DIFF_PAGE = leaf_page(
    "manifest",
    "<h1 id='t'>Review</h1>"
    + '<lf-diff id="patch" source="review-patch" collapsed><pre></pre></lf-diff>',
)

# Which of a diff's source lines are cut off by the box they sit in. A row is one line of
# the patch however many line boxes it takes, so scrollWidth past clientWidth is text the
# reader cannot see without scrolling the file's own box sideways — and on paper, text
# that is simply gone. `worst` and `widest` are for the failure to say which line and by
# how much, since "some row overflows" sends its reader back to the browser.
DIFF_CLIPPING = """() => {
    const diff = document.querySelector('lf-diff');
    const rows = [...diff.shadowRoot.querySelectorAll('[data-content] [data-line]')];
    const cut = rows.filter((row) => row.scrollWidth > row.clientWidth);
    return { rows: rows.length, cut: cut.length,
             worst: rows.reduce((most, row) =>
                 Math.max(most, row.scrollWidth - row.clientWidth), 0),
             widest: cut.length
               ? cut.reduce((a, b) =>
                   a.scrollWidth - a.clientWidth > b.scrollWidth - b.clientWidth ? a : b
                 ).textContent.slice(0, 70)
               : null };
}"""

# Where each file's row starts against its own wrapper. The review press stands ahead of
# the row and the row is pulled back up over it, so the row starts where it would with no
# press at all — zero — on screen, and on paper, where an unreviewed press is not drawn
# and there is nothing for the pull to take back.
DIFF_ROW_PLACEMENT = """() => {
    const root = document.querySelector('lf-diff').shadowRoot;
    const files = [...root.querySelectorAll('.lf-diff-file')];
    const lifts = files.map((file) => {
        const row = file.querySelector(':scope > details, :scope > .lf-diff-rename');
        return Math.round(row.getBoundingClientRect().top
                          - file.getBoundingClientRect().top);
    });
    return { files: files.length, lift: Math.min(...lifts), drop: Math.max(...lifts) };
}"""

# Where the file the reader is in says its name, against the bar it has to clear, and
# where the keyboard just landed. One pass, because every number here means something only
# against the others. With nothing focused it answers for the first file, so the same
# reading covers a page nobody has pressed a key on yet.
# The first file's review press against its own header, and what a pointer at the
# press's centre would reach. Read through the shadow root, which is the tree the press
# is in.
DIFF_PRESS = """() => {
    const root = document.querySelector('lf-diff').shadowRoot;
    const file = root.querySelector('.lf-diff-file');
    const box = file.querySelector('.lf-diff-review').getBoundingClientRect();
    const head = file.querySelector('summary').getBoundingClientRect();
    const hit = root.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    return { top: Math.round(box.top), bottom: Math.round(box.bottom),
             headTop: Math.round(head.top),
             fileBottom: Math.round(file.getBoundingClientRect().bottom),
             hit: hit && hit.classList.contains('lf-diff-review') ? 'review'
                : hit && (hit.localName + '.' + hit.className) };
}"""

DIFF_LANDING = """() => {
    const diff = document.querySelector('lf-diff');
    const at = diff.shadowRoot.activeElement;
    const file =
      (at && at.closest('details')) || diff.shadowRoot.querySelector('details');
    const head = file && file.querySelector('summary');
    const banner = document.querySelector('.lf-banner').getBoundingClientRect();
    return { stop: at && at.localName, line: at && at.dataset.line,
             path: head && head.querySelector('.lf-diff-path').textContent,
             top: at && Math.round(at.getBoundingClientRect().top),
             headTop: head && Math.round(head.getBoundingClientRect().top),
             headBottom: head && Math.round(head.getBoundingClientRect().bottom),
             bannerBottom: Math.round(banner.bottom) };
}"""

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
    // The CSS shell's box. It is not the window: the root owns document scrolling and
    // reserves a stable gutter, while body margins yield room to standing workspaces.
    // `room` above is the body's content box; this reading includes the full shell so
    // the test can tell which edge that room came out of.
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
<lf-ask id="pick-decision"><h2>Should the option include evidence?</h2>
<lf-options id="pick" choose>
  <lf-option id="opt-a"><strong>With evidence</strong>
    <lf-diagram id="in-card"><pre>
graph LR
  A[request] --> B[queue]
  B --> C[worker]
</pre></lf-diagram>
  </lf-option>
  <lf-option id="opt-b"><strong>Without</strong></lf-option>
</lf-options></lf-ask>
<lf-ask id="row-pick-decision"><h2>Where should the cable run?</h2>
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
</lf-options></lf-ask>
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
    const b = document.body;
    const box = b.getBoundingClientRect();
    const main = document.querySelector('main');
    const length = (name) => {
      const probe = document.createElement('i');
      probe.style.cssText = `position:fixed;visibility:hidden;height:0;padding:0;border:0;width:var(${name})`;
      main.append(probe);
      const width = probe.getBoundingClientRect().width;
      probe.remove();
      return width;
    };
    const left = length('--strip-l'), right = length('--strip-r');
    const r = document.getElementById('plan').getBoundingClientRect();
    return { rail: `${right}px`, widget: r.width, room: length('--lf-room'),
             past: Math.max(r.right - (box.right - right), box.left + left - r.left),
             content: box.width - left - right };
}"""
# The room the document leaves at each end for a bar standing over it. Both are boxes in
# the flow, so the reading is the flow's own: what stands above the page's first block and
# what is left under its last.
CHROME_ROOM = """() => {
    const scroller = document.scrollingElement;
    const box = document.querySelector('main').getBoundingClientRect();
    return { head: box.top + scroller.scrollTop,
             foot: scroller.scrollHeight - (box.bottom + scroller.scrollTop),
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
        document.body.style.setProperty("--lf-claim-right", "160px"),
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

# Wide enough for an exhibit to grow after the live page's 520px conversation strip,
# but narrow enough that room, not the 1080px shared cap, binds in both live and copied
# media. With no surplus over prose, a board never asks to share the note's margin.
NOTE_BAND = 1400


def _painted_line(page):
    """Every row in the gesture's next key-line paint, including rows behind More.

    Consume the coalesced frame once: polling could pass on an unrelated later paint.
    Read rows rather than visible text because hidden rows still state liveness.
    """
    page.evaluate(RENDERED)
    return page.eval_on_selector_all(
        ".lf-keyline .lf-key",
        "els => els.map(e => [...e.children].map(c => c.textContent).join(' '))",
    )


SCROLLED = "() => document.scrollingElement.scrollTop > 0"


WHERE_I_STAND_PAGE = leaf_page(
    "where i stand",
    """
<h1 id="t">Standing</h1>
<p id="p1">A first passage, with a <a href="https://example.invalid/spec">link into the
spec</a> so the walk has somewhere to stand that is not a decision.</p>
<lf-ask id="shape-decision"><h2>Which material?</h2>
<lf-options id="shape" choose>
  <lf-option id="sh-steel"><strong>Steel</strong> Galvanised, and the
  <a href="https://example.invalid/steel">spec for it</a> is short.</lf-option>
  <lf-option id="sh-cedar"><strong>Cedar</strong> Cheap; needs sealing.</lf-option>
</lf-options></lf-ask>
<lf-ask id="settled-decision"><h2>Should we keep it?</h2>
<lf-options id="settled" choose settled>
  <lf-option id="st-keep" chosen><strong>Keep it</strong> Decided last week, with the
  <a href="https://example.invalid/keep">note behind it</a>.</lf-option>
  <lf-option id="st-drop"><strong>Drop it</strong> The alternative.</lf-option>
</lf-options></lf-ask>
<p id="p2">A passage carrying
<lf-suggestion id="sug-window">
  <lf-old>Refill every feeder each morning.</lf-old>
  <lf-new>Refill when the camera shows it half-empty.</lf-new>
</lf-suggestion></p>
""",
)
