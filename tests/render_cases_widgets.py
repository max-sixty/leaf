"""Shared widgets browser-integration cases and readings."""

import html

from leaf import anchor_capture as anchor_capture_model
from leaf import passages as passages_model
from leaf.registry import storage as registry_storage
from leaf.render_checks import rendered
from leaf.schema import ELEMENT_ID
from leaf.structure import SourceDocument
from render_harness import (
    SHELL_BOX,
    leaf_page,
)

# ---------- anchors written without a browser ----------
# `leaf thread open` writes an anchor by reading the mapped revision; the runtime
# resolves it against the DOM that revision becomes. Nothing static can check that those
# two readings agree, and every way they can come apart — a widget's upgrade, an
# attribute rendered as text, the space a block boundary stands for — only exists
# once the page is loaded.


def written_anchors(page_dir, html, limit=40):
    """Anchors `leaf thread open` would write for windows over a page's own prose. A
    window the page says twice, or one crossing a fence, is refused on purpose —
    skipping those here is that refusal, and what survives is exactly what the command
    promises to place."""
    registry = registry_storage.load_registry(page_dir)
    text = passages_model.page_passages(SourceDocument(html), registry).text
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
                    anchor_capture_model.capture_anchor(
                        SourceDocument(html), registry, quote, None
                    ),
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
            "id": {"type": "string", "pattern": f"^{ELEMENT_ID}$"},
            "parts": {"type": "string", "minLength": 1},
        },
        "required": ["id", "parts"],
        "additionalProperties": False,
        "x-content": "empty",
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
# The same visual drawn in two steps, as an animation or stepper draws it: `inner`
# appears only in the second, which its registration's `reveal` draws on request.
STAGED_VISUAL_WIDGETS = {
    "lf-test-visual.js": GENERIC_VISUAL_WIDGETS["lf-test-visual.js"].replace(
        "    this.visualRegistration = registerVisualParts(this, () => this.parts);",
        """    inner.style.display = 'none';
    this.visualRegistration = registerVisualParts(
      this,
      () => this.parts.filter((part) => part.id !== 'inner' || inner.style.display !== 'none'),
      {
        reveal: (id) => {
          if (id !== 'inner') return;
          inner.style.display = '';
          this.visualRegistration.update();
        },
      },
    );""",
    )
}


# The same visual with its part ids declared by prefix rather than authored: the
# element names none of them, and the module's inventory is bounded by the prefixes.
PREFIXED_VISUAL_PAGE = GENERIC_VISUAL_PAGE.replace(' parts="outer inner html"', "")


def prefixed_visual_layer(*prefixes):
    entry = GENERIC_VISUAL_LAYER["lf-test-visual"]
    return {
        "lf-test-visual": {
            **entry,
            "properties": {"id": entry["properties"]["id"]},
            "required": ["id"],
            "x-visual": {"prefixes": list(prefixes)},
            "x-example": '<lf-test-visual id="visual"></lf-test-visual>',
        }
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
            "id": {"type": "string", "pattern": f"^{ELEMENT_ID}$"},
            "parts": {"type": "string", "minLength": 1},
        },
        "required": ["id", "parts"],
        "additionalProperties": False,
        "x-content": "empty",
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
<lf-diagram id="life" parts="node:Queued node:Working node:Fetch node:Build node:Done"><pre>
stateDiagram-v2
  [*] --&gt; Queued
  Queued --&gt; Working
  state Working {
    Fetch --&gt; Build
  }
  Working --&gt; Done
</pre></lf-diagram>
<lf-diagram id="shape" parts="node:RUNNER node:JOB"><pre>
erDiagram
  RUNNER {
    string id PK
    string name
  }
  RUNNER ||--o{ JOB : runs
</pre></lf-diagram>
<lf-diagram id="path" parts="node:A node:B"><pre>
graph LR
  A["Bold and plain"] --&gt; B[after]
</pre></lf-diagram>
<lf-diagram id="exchange" parts="node:User node:Server"><pre>
sequenceDiagram
  participant User
  participant Server
  User-&gt;&gt;Server: Request
</pre></lf-diagram>
<lf-diagram id="model" parts="node:Job node:Runner"><pre>
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
<lf-diagram id="life" parts="node:Fresh node:Queued node:Working node:Fetch node:Build node:Done"><pre>
stateDiagram-v2
  [*] --&gt; Fresh
  Fresh --&gt; Queued
  Queued --&gt; Working
  state Working {
    Fetch --&gt; Build
  }
  Working --&gt; Done
</pre></lf-diagram>
<lf-diagram id="shape" parts="node:RUNNER node:JOB"><pre>
erDiagram
  RUNNER {
    string id PK
    string name
  }
  RUNNER ||--o{ JOB : runs
</pre></lf-diagram>
<lf-diagram id="exchange" parts="node:User node:Server"><pre>
sequenceDiagram
  participant User
  participant Server
  User-&gt;&gt;Server: Request
</pre></lf-diagram>
<lf-diagram id="model" parts="node:Job node:Runner"><pre>
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
# and whether that box had to scroll. Whether the page did is `root_overflow`'s.
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
             scrolls: holder.scrollWidth > holder.clientWidth };
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
sankey-beta
  POST /api/event {kind: "action", widget: "lf-board", detail: {card: "card-heater"}},Board,1
</pre></lf-diagram>
""",
)


def chart_markup(chart_id: str, body: str) -> str:
    """An lf-chart whose body is `body`, a Plot expression for Plot.plot's options."""
    return f'<lf-chart id="{chart_id}"><pre>\n{html.escape(body, quote=False)}\n</pre></lf-chart>'


# One chart per shape of Plot call the body can make — a mark over rows, a faceted mark,
# marks Plot stacks, a line over dates, dots — each small enough to count the marks it
# should have produced by hand. Two use what only code can say: a function Plot calls,
# and the width the host draws at.
CHART_PAGE = leaf_page(
    "charts",
    "\n".join(
        [
            '<h1 id="t">Charts</h1>',
            chart_markup(
                "c-bars",
                """{
  ariaLabel: "Merged by quarter: apps 12, 19, 14; infra 7, 11, 17",
  fx: {label: null},
  y: {grid: true, label: "merged"},
  color: {legend: true, range: ["var(--series-1)", "var(--series-2)"]},
  marks: [
    Plot.barY(
      [["apps", [12, 19, 14]], ["infra", [7, 11, 17]]].flatMap(([team, row]) =>
        row.map((merged, i) => ({quarter: `Q${i + 1}`, team, merged})),
      ),
      {fx: "quarter", x: "team", y: "merged", fill: "team"},
    ),
    Plot.ruleY([0]),
  ],
}""",
            ),
            chart_markup(
                "c-rows",
                """{
  ariaLabel: "Open by area: platform infrastructure 42, billing 19",
  marginLeft: 150,
  marginBottom: 40,
  x: {label: width > 500 ? "open issues" : "open"},
  marks: [
    Plot.barX(
      [{area: "platform infrastructure", open: 42}, {area: "billing", open: 19}],
      {x: "open", y: "area", fill: "var(--series-1)"},
    ),
  ],
}""",
            ),
            chart_markup(
                "c-stack",
                """{
  ariaLabel: "Hours by week: features 21 and 18, fixes 9 and 14",
  color: {range: ["var(--series-1)", "var(--series-2)"]},
  y: {tickFormat: (hours) => `${hours}h`},
  marks: [
    Plot.barY(
      [
        {week: "w1", kind: "features", hours: 21},
        {week: "w2", kind: "features", hours: 18},
        {week: "w1", kind: "fixes", hours: 9},
        {week: "w2", kind: "fixes", hours: 14},
      ],
      {x: "week", y: "hours", fill: "kind"},
    ),
  ],
}""",
            ),
            chart_markup(
                "c-line",
                """{
  ariaLabel: "Hours to review by week: 31, 26, 19",
  x: {type: "utc"},
  marks: [
    Plot.lineY(
      [
        {week: "2026-06-01", hours: 31},
        {week: "2026-06-08", hours: 26},
        {week: "2026-06-15", hours: 19},
      ],
      {x: "week", y: "hours", stroke: "var(--series-1)"},
    ),
  ],
}""",
            ),
            chart_markup(
                "c-dots",
                # A continuous scale's legend is a colour ramp: an <svg> of its own beside
                # the drawing.
                """{
  ariaLabel: "Review minutes against lines changed: 12 and 4, 90 and 26, 310 and 71",
  marginBottom: 40,
  color: {legend: true, scheme: "blues"},
  marks: [
    Plot.dot(
      [{lines: 12, minutes: 4}, {lines: 90, minutes: 26}, {lines: 310, minutes: 71}],
      {x: "lines", y: "minutes", fill: "minutes"},
    ),
  ],
}""",
            ),
        ]
    ),
)
# What a chart drew, read off the composed drawing rather than off the body it came from:
# each mark group Plot drew, by the name it gives the group, with the shapes in it and
# the colours they wear, beside what each series token resolves to on this page now.
CHART_MARKS = """(id) => {
    const root = document.getElementById(id).querySelector('.lf-chart-drawing');
    const svg = root && root.querySelector('svg[role="img"]');
    if (!svg) return null;
    const probe = document.createElement('span');
    document.body.append(probe);
    const tokens = [1, 2].map((n) => {
        probe.style.color = `var(--series-${n})`;
        return getComputedStyle(probe).color;
    });
    probe.remove();
    const marks = {};
    for (const g of svg.querySelectorAll('g[data-lf-part]')) {
        const shapes = [...g.querySelectorAll('rect, path, circle')];
        if (!shapes.length) continue;
        const part = g.dataset.lfPart;
        (marks[part] ??= []).push(...shapes.map((shape) => {
            const paint = getComputedStyle(shape);
            return [shape.tagName.toLowerCase(), paint.fill, paint.stroke];
        }));
    }
    return {
        marks,
        tokens,
        // A colour written into the drawing as a value, which would freeze the scheme
        // this browser happened to be in when the drawing was made.
        painted: root.innerHTML.match(/(?:fill|stroke)="#[0-9a-fA-F]{3,8}"/g) || [],
        // The painted box of the first tick label. Its computed font-size is the theme's
        // and cannot move; what a scaled drawing changes is the box.
        tick: (() => { const r = svg.querySelector('text').getBoundingClientRect();
                       return [Math.round(r.width), Math.round(r.height)]; })(),
        width: Number(svg.getAttribute('width')),
        room: Math.round(document.getElementById(id).clientWidth),
    };
}"""
# The bodies the module refuses, each for its own reason and each on a page of its own:
# the refusal is taller than the body it replaces, and a chart below it would move.
BAD_CHARTS = {
    "bad-syntax": '{ariaLabel: "merged", marks: [}',
    "bad-label": "{marks: [Plot.ruleY([0])]}",
    "bad-mark": '{ariaLabel: "merged", marks: [Plot.barz([{n: 1}], {y: "n"})]}',
    "bad-shape": '[{ariaLabel: "merged", marks: []}]',
    "bad-drawn": 'Plot.plot({ariaLabel: "merged", marks: [Plot.ruleY([0])]})',
    "bad-height": '{ariaLabel: "merged", height: 200, marks: [Plot.ruleY([0])]}',
}
# A chart an agent sent in a reply, which upgrades inside a panel nobody has opened yet.
MESSAGE_CHART = """{
  ariaLabel: "Merged by quarter: Q1 12, Q2 19",
  marks: [
    Plot.barY(
      [{quarter: "Q1", merged: 12}, {quarter: "Q2", merged: 19}],
      {x: "quarter", y: "merged", fill: "var(--series-1)"},
    ),
  ],
}"""
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
    const acts = document.querySelector('[data-lf-margin-for="sug-copy"]');
    // The drawing's own rect and the box's. A drawing wider than its box keeps a rect
    // that runs on past it — the layout's answer, not the user's — so what is painted
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
    return { col, place: acts.closest('.lf-margin-cluster')?.dataset.lfPlace,
             rail: acts.getBoundingClientRect().left,
             small: at('small'), flow: at('flow') };
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
    + '<lf-diff id="patch" source="review-patch" review><pre></pre></lf-diff>'
    + _filler("tail", 30),
)

# The same review as the body of a workspace pane, where the pane's body is the box that
# scrolls the rows rather than the window under the banner.
PANE_DIFF_PAGE = leaf_page(
    "pane patch",
    "<header><h1 id='t'>Review</h1></header>"
    '<lf-pane id="patch-pane" label="Patch"><header><h2>Patch</h2></header>'
    '<lf-diff id="patch" source="review-patch" review><pre></pre></lf-diff></lf-pane>',
    layout="workspace",
)

# The same review bound as a manifest of collapsed files, the form a captured patch
# arrives in on the shipped walkthrough: the module draws the file rows from the manifest
# alone and parses no line until a user opens a file, which is where the renderer comes
# in. One diff and nothing else that draws lines, so what the page asks for at load is
# the manifest's answer and no other widget's.
MANIFEST_DIFF_PAGE = leaf_page(
    "manifest",
    "<h1 id='t'>Review</h1>"
    + '<lf-diff id="patch" source="review-patch" collapsed><pre></pre></lf-diff>',
)

# Which of a diff's source lines run past what the user can see. A row is one line of
# the patch however many line boxes it takes, and neither box in play is the line: the
# row is sized to the longest line in its file so its fill reaches the end of it, and the
# code box is the scrollport. So the room is measured out here — the code box's own width
# less the gutter standing in front of the content column — and the line is measured by a
# Range over the row's contents, which is what `_SELECT_IN_ROW` reads for the same reason.
# Reading the row's own box instead gives every row in a file the file's overhang, which
# is how this last went wrong: 18 of 24 rows counted cut where one line overflowed, and
# `widest` named a trailing-context line the user could see whole. Text wider than the
# room is text the user cannot reach without scrolling the file sideways, and on paper,
# text that is simply gone. `worst` and `widest` are for the failure to say which line and
# by how much, since "some row overflows" sends its user back to the browser.
DIFF_CLIPPING = """() => {
    const diff = document.querySelector('lf-diff');
    const rows = [];
    for (const code of diff.shadowRoot.querySelectorAll('code[data-code]')) {
        const gutter = code.querySelector('[data-gutter]');
        const room = code.clientWidth - (gutter ? gutter.getBoundingClientRect().width : 0);
        const range = document.createRange();
        for (const row of code.querySelectorAll('[data-content] [data-line]')) {
            range.selectNodeContents(row);
            rows.push({ row, over: Math.round(range.getBoundingClientRect().width - room) });
        }
    }
    const cut = rows.filter((entry) => entry.over > 0);
    return { rows: rows.length, cut: cut.length,
             worst: rows.reduce((most, entry) => Math.max(most, entry.over), 0),
             widest: cut.length
               ? cut.reduce((a, b) => (a.over > b.over ? a : b))
                   .row.textContent.slice(0, 70)
               : null };
}"""

# Where a changed row's fill ends, against the line it is painting and against the room
# the file's box gives it. A row's green or red is its own background, so it reaches
# exactly as far as the row's box does: a box narrower than the row's own text is a fill
# that stops mid-line and leaves the rest of the addition sitting on the file's plain
# paper, which is what a user who scrolls sideways finds. `short` counts those and
# `gap` is the worst. `narrow` is the same reading from the other side — a file whose
# lines all fit must still fill its box rather than end at its longest line. `scrolls`
# is the population: on a file that does not scroll, `short` is zero for free.
DIFF_ROW_FILL = """() => {
    const diff = document.querySelector('lf-diff');
    const out = { rows: 0, short: 0, gap: 0, narrow: 0, scrolls: 0, files: 0 };
    for (const code of diff.shadowRoot.querySelectorAll('code[data-code]')) {
        out.files += 1;
        if (code.scrollWidth > code.clientWidth) out.scrolls += 1;
        const gutter = code.querySelector('[data-gutter]');
        const room = code.clientWidth - (gutter ? gutter.getBoundingClientRect().width : 0);
        for (const row of code.querySelectorAll('[data-content] [data-line]')) {
            const painted = row.getBoundingClientRect().width;
            out.rows += 1;
            const gap = Math.round(row.scrollWidth - painted);
            if (gap > 1) { out.short += 1; out.gap = Math.max(out.gap, gap); }
            if (room - painted > 1) out.narrow += 1;
        }
    }
    return out;
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

# Where the file the user is in says its name, against the bar it has to clear, and
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
ROOM_GEOMETRY = (
    """() => {
    // A content box: inside the border as well as the padding.
    const span = (el) => {
        const s = getComputedStyle(el), b = el.getBoundingClientRect();
        const left = b.left + parseFloat(s.borderLeftWidth) + parseFloat(s.paddingLeft);
        const right = b.right - parseFloat(s.borderRightWidth)
            - parseFloat(s.paddingRight);
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
    // reserves a stable gutter.
    // `room` above is the body's content box; this reading includes the full shell so
    // the test can tell which edge that room came out of.
    return { column: span(document.querySelector('main')),
             room: span(document.body), pageBox: """
    + SHELL_BOX
    + """,
             board: box('sprint'), diff: box('patch'), prose: box('prose'),
             note: box('note'), later: box('later') };
}"""
)
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
<lf-sample id="quoted" label="a board">
  <lf-board id="in-sample">
    <lf-column id="q1" label="Todo"><lf-card id="qk1"><strong>One</strong></lf-card></lf-column>
    <lf-column id="q2" label="Done"></lf-column>
  </lf-board>
</lf-sample>
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
<div class="layout-tiles" id="nums">
  <lf-metric id="me1" value="410ms">p95, with the path it measures
    <lf-diagram id="in-metric"><pre>
graph LR
  A[request] --> B[queue]
  B --> C[worker]
</pre></lf-diagram>
  </lf-metric>
</div>
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
<div id="own-box" style="border: 1px solid #999; padding: 10px; --lf-block-frame: 1">
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
    '<main class="layout-column">',
    "<main class=\"layout-column\">\n<div id='own-frame' style='border: 1px solid #999; overflow-x: auto'>"
    "<lf-board id='framed'><lf-column id='f1' label='Todo'>"
    "<lf-card id='fk1'><strong>One</strong></lf-card></lf-column>"
    "<lf-column id='f2' label='Done'></lf-column></lf-board></div>",
)


# How far the exhibit stands into the room a margin resident states it takes
# (`--lf-taken-l`, `--lf-taken-r`, layouts.css), on both edges, since a room read too
# wide spends itself on whichever side is free. The room the page states comes with it,
# so a test waiting for the box to be read again has the reading it is waiting to see
# changed.
RAIL_FIT = """() => {
    const box = document.body.getBoundingClientRect();
    const main = document.querySelector('main');
    const length = (name) => {
      const probe = document.createElement('i');
      probe.style.cssText = `position:fixed;visibility:hidden;height:0;padding:0;border:0;width:var(${name}, 0px)`;
      main.append(probe);
      const width = probe.getBoundingClientRect().width;
      probe.remove();
      return width;
    };
    const left = length('--lf-taken-l'), right = length('--lf-taken-r');
    const r = document.getElementById('plan').getBoundingClientRect();
    return { taken: `${right}px`, widget: r.width, room: length('--lf-room'),
             right: r.right,
             past: Math.max(r.right - (box.right - right), box.left + left - r.left) };
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
             line: document.querySelector('.lf-shortcut-bar').offsetHeight };
}"""
# The same reading taken at the stamp, which is the one moment nothing out here can
# reach: a MutationObserver's callback is a microtask off the stamp's own write.
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

# A project widget that stands in the page's right margin and states the room it takes
# there, and can only say how wide once it has heard what its controls will say — so the
# statement rides an answer rather than the upgrade that asked for it. The request is
# answered by the test, which is what puts it after the handover on every machine rather
# than on a fast one.
LATE_MARGIN_WIDGET = """\
import { once } from "/runtime/widget-api.js";

customElements.define(
  "lf-callout",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      fetch("/margin-width").then(() =>
        document.body.style.setProperty("--lf-taken-r", "160px"),
      );
    }
  },
);
"""
# Where the two things in the right margin stand, and how much of the board is over the
# controls. The controls stand in the rail, and they hang off the column rather than out
# of the rail's strip, so the strip's own edge says nothing about where they are.
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
    return { rows: [...document.querySelectorAll(
                 '[data-lf-margin-for="sug-copy"], [data-lf-margin-for="sug-card"]'
             )].map(r => ({
                 ...box(r), for: r.dataset.lfMarginFor, place: r.dataset.lfPlace,
                 pressable: r.contains(document.elementFromPoint(
                   (box(r).left + box(r).right) / 2, (box(r).top + box(r).bottom) / 2)) })),
             plan: box(document.getElementById('plan')),
             later: box(document.getElementById('later')),
             column: { left: mb.left + parseFloat(ms.paddingLeft),
                       right: mb.right - parseFloat(ms.paddingRight) },
             pageLeft: bb.left + parseFloat(bs.paddingLeft),
             pageGutter: parseFloat(ms.paddingLeft),
             pageRight: bb.right - parseFloat(bs.paddingRight) };
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
# A drawing inside a tab panel: the panel's card is the frame a wide exhibit may not
# leave, the graph is drawn wider than the frame's own inset, and no room the page has
# can be given to it — so scrolling is the layer's honest answer. Beside it a line of
# code short enough to fit, which must carry no mark. The cut box is a drawing on purpose: a cut line of code announces itself by being a
# line, where a graph that continues past its edge looks exactly like a graph that ends
# there.
CUT_BOXES_PAGE = leaf_page(
    "cut boxes",
    """
<h1 id="t">Flow</h1>
<lf-tabs id="views">
  <lf-tab id="flow-tab" label="Behaviour">
    <lf-diagram id="flow"><pre>
graph LR
  R[a request arrives at the edge] --> C{is the session cookie still valid?}
  C -->|yes| S[read the session record from Redis]
  S -->|hit| H[hand the request to the application]
  C -->|no| L[send the user to the login page]
</pre></lf-diagram>
  </lf-tab>
</lf-tabs>
<pre id="short">one short line</pre>
""",
)
# A five-step plan drawn left to right, the shape three agent-written pages gave their
# plan, and the same five steps drawn top-down beside it: the chain runs past the room a
# 1440px window gives it, and the stack fits the column, so it is the control a shaded
# edge must not appear on.
PLAN_STEPS = """\
  A[1. Snapshot the primary and restore it on the new cluster] --> B[2. Start logical replication from the old primary]
  B --> C[3. Verify row counts and checksums on every table]
  C --> D[4. Cut writes over during the maintenance window]
  D --> E[5. Retire the old primary after seven quiet days]
"""
LONG_CHAIN_PAGE = leaf_page(
    "long chain",
    f"""
<h1 id="t">Plan</h1>
<lf-diagram id="chain"><pre>
flowchart LR
{PLAN_STEPS}</pre></lf-diagram>
<lf-diagram id="stack"><pre>
flowchart TD
{PLAN_STEPS}</pre></lf-diagram>
""",
)


# A board with more columns than the room holds, so every one of them is at the floor the
# theme states and the board scrolls for the rest — the case the floor exists to decide.
# The cards carry ordinary English rather than identifiers: a path or a sha has nowhere to
# break and breaking one is the page-wide bargain, where `documented` breaking across two
# lines is a column narrower than the word it has to show.
SQUEEZED_BOARD_PAGE = leaf_page(
    "squeezed board",
    """
<h1 id="t">Sprint</h1>
<lf-board id="crowd">
"""
    + "".join(
        f"""  <lf-column id="sq-col-{i}" label="Lane {i}">
    <lf-card id="sq-card-{i}"><strong>Perch {i}</strong>
    The warden has documented every reading she takes at dawn.</lf-card>
  </lf-column>
"""
        for i in range(8)
    )
    + """</lf-board>
""",
)


# A page hanging apparatus of its own in the margin, level with a wide widget. The theme
# has no rule for a project's own furniture and cannot — this is the case the two claims
# in it are declarations of, seen from the side where nobody has declared anything.
OWN_MARGIN_FURNITURE = WIDE_AND_NARROW_PAGE.replace(
    '<main class="layout-column">',
    "<main class=\"layout-column\">\n<div id='own-rail' style='position: absolute; left: 100%;"
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

# Wide enough for a note to hang in the margin with the column centred, the room
# either side of it holding the note's 384px, with an exhibit growing past prose into
# that same margin.
NOTE_BAND = 1600


def _painted_line(page):
    """Every row in the gesture's next shortcut-bar paint, including rows behind More.

    Consume the coalesced frame once: polling could pass on an unrelated later paint.
    Read rows rather than visible text because hidden rows still state liveness.
    """
    rendered(page)
    return page.eval_on_selector_all(
        ".lf-shortcut-bar .lf-shortcut",
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
