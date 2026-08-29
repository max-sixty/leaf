"""Shared navigation browser-integration cases and readings."""

import json
from contextlib import contextmanager

import pytest
from click.testing import CliRunner
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import leases as leases_model
from leaf import service as service_model
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_interaction import (
    SUGGESTION_PAGE,
)
from render_cases_layout import (
    SHOT_SRC,
)
from render_harness import (
    LONG_PAGE,
    leaf_page,
    told,
)

ADDRESS_PAGE = leaf_page(
    "addresses",
    """
<h1 id="h">Two questions, two forms</h1>
<lf-options id="cards" choose>
  <lf-option id="c-heater"><strong>Immersion heater</strong> Drops into the basin.</lf-option>
  <lf-option id="c-cable"><strong>Heated cable</strong> A cord across the base.</lf-option>
  <lf-option id="c-hand"><strong>Break the ice</strong> Someone goes out each morning.</lf-option>
</lf-options>
<p id="plan">The camera mount is the part nobody has costed.</p>
<lf-options id="rows" choose>
  <lf-option id="r-now" for="plan">Cost it now</lf-option>
  <lf-option id="r-later" for="plan">Leave it for the spring</lf-option>
</lf-options>
""",
)

# The first ancestor that cuts this element, and by how much. `overflow` and `clip-path`
# cut at the padding box, so the border comes off the ancestor's own box before the
# comparison; half a pixel of tolerance for subpixel layout.
CLIPPED_BY = """el => {
    const r = el.getBoundingClientRect();
    for (let p = el.parentElement; p; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (s.overflow === "visible" && s.clipPath === "none") continue;
      const b = p.getBoundingClientRect();
      const box = {left: b.left + parseFloat(s.borderLeftWidth),
                   right: b.right - parseFloat(s.borderRightWidth),
                   top: b.top + parseFloat(s.borderTopWidth),
                   bottom: b.bottom - parseFloat(s.borderBottomWidth)};
      const cut = {left: box.left - r.left, right: r.right - box.right,
                   top: box.top - r.top, bottom: r.bottom - box.bottom};
      const worst = Math.max(...Object.values(cut));
      if (worst > 0.5)
        return {by: p.tagName.toLowerCase() + (p.id ? "#" + p.id : ""),
                overflow: s.overflow, px: +worst.toFixed(1)};
    }
    return null;
}"""


# Any of the group's own words this element is drawn over, taken a rendered line at a
# time (a wrapped run's box spans the whole column and would answer for a line the chip
# is nowhere near). The runtime's own chrome is not the page's words, so it is skipped.
OVER_WORDS = """(el, id) => {
    const group = document.getElementById(id).closest("lf-options");
    const r = el.getBoundingClientRect();
    const walk = document.createTreeWalker(group, NodeFilter.SHOW_TEXT);
    for (let n = walk.nextNode(); n; n = walk.nextNode()) {
      if (!n.textContent.trim() || n.parentElement.closest(".lf-ui")) continue;
      const range = document.createRange();
      range.selectNodeContents(n);
      for (const b of range.getClientRects())
        if (r.right > b.left && r.left < b.right && r.bottom > b.top && r.top < b.bottom)
          return n.textContent.trim().slice(0, 24);
    }
    return null;
}"""

# Where the chip sits in the option holding it: from its corner, against the option's own
# middle, and whether it reaches past the bottom. Every rect in one pass, because these are
# differences between boxes and a difference is only a fact if both sides were read at one
# instant.
#
# `level` is the middle of the box the row's words fill, not the middle of the first line,
# which is what the row's rule actually promises: a label long enough to wrap carries its
# digit down with it, 13.7px below that first line on a two-line row. Asked of the first
# line this would fail a perfectly good layout the day a shipped label grew a word. It is
# the content box and not the border box, so that a row whose padding stopped being
# symmetric — which is the whole of why centring on the box centres on the words — is a
# failure and not a pass.
#
# Two `bounding_box()` calls are two instants, and the page moves between them: a viewport
# rect is relative to the scroller, so a scroll landing between the two reads is subtracted
# straight into the answer. `a` scrolls to the ask it steps to, the body is the scroller,
# and a page whose content sits on fractional pixels settles that scroll across a frame —
# so the chip's offset came back a pixel out on about half of the runs, on whichever row
# the frame happened to fall between. Nothing had moved by then except the window, which is
# the one thing this measurement is not about.
#
# Every reading is stated from the option's padding box, because that is where the chip is
# placed from and where the option's own room starts: a joined cell wears the hairline
# below it as its own border, so measured from the border box, the last cell of every
# group would sit one pixel apart from the rest while the page shows them level.
#
# The gutter the chip stands in comes back with it, because where the chip belongs is a
# relation to the two boxes either side of it rather than a number. The status rule is the
# option's own `::before` and the prose opens at the column the option pads to, so
# `afterStatus` and `opens` are read where the theme spends them. Written as the number
# they came to, the reading would have to be re-pinned every time either neighbour moved,
# and a re-pinned number proves only that somebody ran the test.
INSIDE_ITS_OPTION = """el => {
    const chip = el.getBoundingClientRect();
    const opt = el.parentElement.getBoundingClientRect();
    const s = getComputedStyle(el.parentElement);
    const status = getComputedStyle(el.parentElement, '::before');
    const top = opt.y + parseFloat(s.borderTopWidth);
    const left = opt.x + parseFloat(s.borderLeftWidth);
    const bottom = opt.bottom - parseFloat(s.borderBottomWidth);
    const above = parseFloat(s.paddingTop), below = parseFloat(s.paddingBottom);
    const words = top + above + (bottom - top - above - below) / 2;
    return {x: chip.x - left, ends: chip.right - left,
            y: chip.y - top, past: chip.bottom - bottom,
            level: (chip.y + chip.height / 2) - words,
            afterStatus: parseFloat(status.left) + parseFloat(status.width),
            opens: parseFloat(s.paddingInlineStart)};
}"""


def painted(page, name):
    """What the page is painting under a highlight name, whitespace-flattened. Marks are
    ranges in the highlight registry, not elements, so this is where a test looks."""
    return " ".join(
        page.evaluate(
            """(name) => {
        const h = CSS.highlights.get(name);
        return h ? [...h].map(r => r.toString()).join('') : '';
    }""",
            name,
        ).split()
    )


def pending_text(page):
    return painted(page, "lf-pending")


def mark_point(page, name, index=0):
    """A point inside a painted range, for a real mouse press. A highlight is not an
    element, so there is nothing for a locator to click.

    On screen, and asserted here, because a press the reader cannot make proves nothing
    about what a press does. A range keeps its client rects while it is scrolled away —
    they simply go negative — so the arithmetic above will hand back a point above the
    window as readily as one in it, and `page.mouse` will press there. Nothing in the
    page hears that press: `elementFromPoint` answers null outside the window, the
    runtime's hit test declines a point that is over none of the page's words, and the
    click arrives at `<html>`. A caller pressing 141px above the top edge therefore read
    the silence that followed as the mark's thread refusing to open, 30 seconds later
    and in another function."""
    box = page.evaluate(
        """([name, index]) => {
        const r = [...CSS.highlights.get(name)][index].getClientRects()[0];
        return {x: r.left + r.width / 2, y: r.top + r.height / 2,
                w: innerWidth, h: innerHeight};
    }""",
        [name, index],
    )
    assert 0 <= box["x"] < box["w"] and 0 <= box["y"] < box["h"], (
        f"the {name} mark at index {index} is painted at ({box['x']:.0f}, "
        f"{box['y']:.0f}), off a {box['w']:.0f}×{box['h']:.0f} window — scroll the "
        f"passage into view before pressing it"
    )
    return box["x"], box["y"]


def composer_quote(page):
    """What the composer says about its own passage, and whether the reader can see it.
    The node stays in the accessibility tree either way — a painted mark has no exposure,
    so it is the box's aria description — which is why this asks the class, not the text."""
    return page.evaluate("""() => {
        const q = document.getElementById('lf-composer-quote');
        return {text: q.textContent, shown: !q.classList.contains('lf-unseen')};
    }""")


def mark_shows_beside_composer(page):
    """Whether any of the composer's own mark is on screen and not behind the box. The mark
    is the only thing naming the passage the box is about, so a box covering all of it is a
    box about nothing — which no state may reach."""
    return page.evaluate("""() => {
        const box = document.querySelector('.lf-composer').getBoundingClientRect();
        const rects = [...(CSS.highlights.get('lf-pending') ?? [])]
            .flatMap(r => [...r.getClientRects()])
            .concat([...document.querySelectorAll('.lf-mark-el.lf-pending')]
                .map(e => e.getBoundingClientRect()));
        const onScreen = (r) => r.right > 0 && r.left < innerWidth
                             && r.bottom > 48 && r.top < innerHeight;
        const behind = (r) => r.left >= box.left && r.right <= box.right
                           && r.top >= box.top && r.bottom <= box.bottom;
        return rects.some(r => onScreen(r) && !behind(r));
    }""")


# Every kind of destination the g chord offers, on one page: the tests add comments, this
# fixture supplies an ask, and the authored document supplies links and a disclosure.
# They stand together so one chord must distinguish direct panels from numbered lists.
ADDRESSED_PAGE = leaf_page(
    "addressed",
    """
<h1 id="t">Addressed</h1>
<p id="p1">The first passage under discussion, with words
enough for two separate remarks to land in it.</p>
<p id="refs">See <a id="lk1" href="#p1">the first passage, whose link text is long
enough that it runs past the end of one line and carries on onto the next</a>, and then
<a id="lk2" href="#p2">the second</a>.</p>
<details id="dsc"><summary id="dsc-head">What the store costs</summary>
<p id="dsc-body">A replica in each region, and a read on every request that carries a
session.</p></details>
<lf-options id="opts" choose>
  <lf-option id="opt-a"><strong>Keep the store</strong> Sessions stay where they are,
  which costs a replica and buys revocation for free.</lf-option>
  <lf-option id="opt-b"><strong>Signed tokens</strong> No store at all, until revocation
  quietly puts one back.</lf-option>
</lf-options>
<p id="p2">A short second passage.</p>
{tail}
""",
).format(
    # Enough page below the ask that it can be scrolled up under the banner, which is where
    # a chip placed from the page's geometry alone lands on the status line.
    tail="\n".join(
        f"<p id='t{i}'>Tail {i}. " + "Words. " * 20 + "</p>" for i in range(12)
    )
)
# What the chord is offering right now, in the order it drew it. Read through the
# retrying assertion rather than evaluated: the chips are painted on a frame of the
# runtime's own (paintHere), so a press and a plain read race each other. Each chip says
# a whole address, so one reading answers which lists are on offer, which members of
# each, and in what order — three facts a count and a bare digit answered separately.
CHIPS = ".lf-addresses > .lf-address"
# The half of each address already behind the reader. A chip carries the whole motion, so
# how far in they are is the split rather than the text: `g` alone once the window is up,
# and `g h` once a letter has named a list. The selector arrives as an argument so the one
# spelling above is the one this reads.
SPENT = """(sel) => [...document.querySelectorAll(sel)]
    .map(chip => chip.querySelector('.lf-spent').textContent)"""
# And that the split runs the way it has to, in both channels that carry it: the keys
# already pressed stand back from the chip's own paper, and the ones still to come sit on a
# ground of their own. Contrast rather than two colours being different, which a change
# painting the spent half brighter would satisfy while saying the opposite thing; and the
# ground beside it because muted against accent is 1.45:1 in the light palette and 1.28:1 in
# the dark — a colour-only split reads as one word on a key this small, and to a reader who
# does not separate those hues it is one word.
#
# `flat` and `sized` are the other half of that sentence, and they are what keeps this from
# passing on a chip that says the split twice. The ground belongs to the live keys alone, so
# a rule that painted both says nothing; and both halves are read for size, not just the
# spent one, because the fault the ground replaced was two type sizes in one box and a rule
# enlarging the lit half would be that fault back with the halves swapped.
# Where a chip sits and where each of its glyphs sits inside it, in one reading.
#
# A Range and not the two spans' rects, because the spans are the thing that moves: a key
# crosses from the spent half to the lit one on the press, so an element reading answers
# about a different element at each stage and cannot see a glyph step. That is the reading
# the chip's first version passed under while its letter jumped three pixels.
#
# The box comes back with the glyphs rather than from a second `bounding_box()`, for the
# reason the layer states about itself: the chord's chips are rebuilt on every repaint, and
# an armed window repaints on a frame of its own — so a node read across two round trips can
# be detached by the second, which answers None. Both halves of a difference have to be read
# at one instant to be a difference at all.
GLYPH_OFFSETS = r"""(sel) => {
    const chip = document.querySelector(sel);
    if (!chip) return null;
    const box = chip.getBoundingClientRect();
    const glyphs = {};
    const walk = document.createTreeWalker(chip, NodeFilter.SHOW_TEXT);
    for (let n; (n = walk.nextNode()); ) {
      const s = n.textContent;
      for (let i = 0; i < s.length; i++) {
        if (s[i] === " ") continue;
        const r = document.createRange();
        r.setStart(n, i); r.setEnd(n, i + 1);
        glyphs[s[i]] = Math.round((r.getBoundingClientRect().left - box.left) * 100) / 100;
      }
    }
    return {glyphs, left: Math.round(box.left * 100) / 100,
            width: Math.round(box.width * 100) / 100};
  }"""


STANDS_BACK = r"""(sel) => {
    const chip = document.querySelector(sel), face = getComputedStyle(chip);
    const spent = getComputedStyle(chip.querySelector('.lf-spent'));
    const lit = getComputedStyle(chip.querySelector('.lf-lit'));
    const lum = c => { const [r, g, b] = c.match(/[\d.]+/g).slice(0, 3).map(Number)
        .map(v => { const s = v / 255;
                    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
    const against = c => { const [hi, lo] = [lum(c), lum(face.backgroundColor)]
        .sort((a, b) => b - a);
      return (hi + 0.05) / (lo + 0.05); };
    // A ground of its own: painted at all, and not the chip's own paper.
    const painted = s => !/^rgba\(.*,\s*0\)$/.test(s.backgroundColor)
        && s.backgroundColor !== face.backgroundColor;
    // Each half against the ground it is actually drawn on. The chip's own `color` is a
    // colour no glyph of a chord chip paints in — both halves override it — so reaching
    // the comparison through it would pass a lit half whose ink had gone to anything.
    const on = (ink, ground) => { const [hi, lo] = [lum(ink), lum(ground)]
        .sort((a, b) => b - a);
      return (hi + 0.05) / (lo + 0.05); };
    return {quieter: on(spent.color, face.backgroundColor)
                       < on(lit.color, lit.backgroundColor),
            lit: painted(lit),
            flat: !painted(spent),
            sized: parseFloat(spent.fontSize) === parseFloat(face.fontSize)
                     && parseFloat(lit.fontSize) === parseFloat(face.fontSize)};
  }"""


NOTED_PAGE = leaf_page(
    "noted",
    """
<h1 id="t">Noted</h1>
<p id="p1">The first passage under discussion, with words
enough for two separate remarks to land in it.</p>
<p id="p2">A short second passage.</p>
<figure id="fig"><svg viewBox="0 0 120 40" width="120" height="40" role="img"
aria-label="specimen"><rect x="2" y="2" width="116" height="36" fill="none"
stroke="currentColor"></rect></svg><figcaption>A figure, for element anchors.</figcaption></figure>
""",
)


def standing_mark(page):
    """Which passage the page is painting as the comment the reader is standing in, and
    which elements wear the same fact as an outline. One reading, because the two are one
    paint over two kinds of anchor and a test that asked for only the text half would go
    green on a page whose element marks had stopped answering."""
    return {
        "text": painted(page, "lf-mark-here"),
        "elements": page.evaluate(
            "() => [...document.querySelectorAll('.lf-mark-here')].map(e => e.id)"
        ),
    }


STANDING = """([text, ids]) => {
    const h = CSS.highlights.get('lf-mark-here');
    const said = (h ? [...h].map(r => r.toString()).join('') : '').split(/\\s+/)
        .filter(Boolean).join(' ');
    const on = [...document.querySelectorAll('.lf-mark-here')].map(e => e.id);
    return said === text && String(on) === String(ids);
}"""


def wait_standing(page, text, ids=()):
    """Wait for the page to be marking exactly this comment's passage.

    The paint follows the focus through the runtime's one coalesced repaint (paintHere),
    so it lands a frame after the press that moved the reader. Reading straight after the
    key reads the press before its answer, and passes or fails on how loaded the machine
    is. The failure carries what was painted instead, since a timeout on a predicate says
    only that it never came true."""
    try:
        page.wait_for_function(STANDING, arg=[text, list(ids)], timeout=4000)
    except PlaywrightTimeout:
        raise AssertionError(
            f"the page should be marking {text or list(ids)!r} as the comment the reader"
            f" is standing in; it is marking {standing_mark(page)}"
        ) from None


HOVERED = """(text) => {
    const h = CSS.highlights.get('lf-mark-hover');
    const said = (h ? [...h].map(r => r.toString()).join('') : '').split(/\\s+/)
        .filter(Boolean).join(' ');
    return said === text;
}"""


def wait_hovered(page, text):
    """Wait for the page to be lighting exactly this passage under the pointer.

    Answered in a coalesced frame rather than in the move itself: the page's half reads
    layout, and the panel's half reads the browser's own :hover, which that frame is also
    what settles. Reading straight after the move reads the move before its answer."""
    try:
        page.wait_for_function(HOVERED, arg=text, timeout=4000)
    except PlaywrightTimeout:
        raise AssertionError(
            f"the pointer should be lighting {text!r} on the page; it is lighting"
            f" {painted(page, 'lf-mark-hover')!r}"
        ) from None


def card_body(page, says):
    """A point low on a comment's card, below the quote — where a reader's hand rests
    while they read the comment, and where nothing presses."""
    box = page.locator(".lf-thread").filter(has_text=says).first.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] - 8


# Addressable things that start within a chip's width of each other: a run of footnote
# markers, and a link that is the whole of a summary — the second being a member of two
# lists at one corner, which nothing could produce while only one list painted at a time.
CROWDED_PAGE = leaf_page(
    "crowded",
    """
<h1 id="t">Crowded</h1>
<p id="notes">Claims rest on sources<a id="fn1" href="#s1">1</a><a id="fn2" href="#s2">2</a><a
id="fn3" href="#s3">3</a> and are checked below.</p>
<details id="dsc"><summary id="dsc-head"><a id="lk-sum" href="#s1">The sources</a></summary>
<p id="s1">One.</p><p id="s2">Two.</p><p id="s3">Three.</p></details>
""",
)
# Links all the way down, so one of them starts in the corner the key line stands in.
FOOTED_PAGE = leaf_page(
    "footed",
    """
<h1 id="t">Footed</h1>
"""
    + "\n".join(
        f'<p id="p{i}"><a id="lk{i}" href="#t">Source {i}</a> says so, at some length, with '
        + "words enough to carry the paragraph onto a second line. " * 2
        + "</p>"
        for i in range(9)
    ),
)
# c's three destinations on one page: prose to select, a visual to click (no words to
# quote, so it anchors on the element), and the page itself with neither in hand.
TARGETS_PAGE = leaf_page(
    "targets",
    """
<h1 id="t">Targets</h1>
<p id="prose">A paragraph with enough words in it to select by dragging across, which
is what raises the button the key then presses.</p>
<figure id="fig"><svg viewBox="0 0 240 60" width="240" height="60" role="img"
aria-label="specimen"><rect x="2" y="2" width="236" height="56" fill="none"
stroke="currentColor"></rect></svg><figcaption>A specimen.</figcaption></figure>
""",
)
UNDO_PAGE = leaf_page(
    "undo",
    """
<h1 id="h">Undo</h1>
<lf-draft id="note-cli"><pre>
First line of the note.

Second paragraph of the note.
</pre></lf-draft>
<lf-options id="picks" choose>
  <lf-option id="opt-a">Keep the mounts</lf-option>
  <lf-option id="opt-b" chosen>Replace the mounts</lf-option>
</lf-options>
""",
)


def actions(page_dir):
    return [e for e in events_model.read_events(page_dir) if e["kind"] == "action"]


NESTED_SUGGESTION = SUGGESTION_PAGE.replace(
    "<lf-new>Switch the north feeder to thistle in autumn.</lf-new>",
    "<lf-new>Switch the north feeder to thistle in autumn."
    '<lf-options id="blend" choose>'
    '<lf-option id="blend-nyjer">Nyjer only</lf-option>'
    '<lf-option id="blend-mixed">Mixed thistle</lf-option>'
    "</lf-options></lf-new>",
)
FENCED_CAPTURE_PAGE = leaf_page(
    "fenced capture",
    """
<h1 id="h">Roadmap</h1>
<lf-milestones>
  <lf-milestone id="gate-milestone" status="active" when="week-1" tags="wood,solar">
    <strong>Build feeders</strong> Two classic models.
  </lf-milestone>
</lf-milestones>
<p id="after-milestone">Ready next.</p>
<lf-options id="fence-options">
  <lf-option id="fence-option"><lf-chip>effort: low</lf-chip><lf-chip>risk: high</lf-chip>
    <strong>Classic feeder</strong> Easy to clean.
  </lf-option>
</lf-options>
""",
)
# A label a widget renders into a control it also built. The tab strip is the case with
# nowhere else to say it: once the strip exists the panel heading stands down, so the
# button is the panel's only name. Every word here is distinct, so a quote can only
# anchor where it was picked, and the panels are long enough that a drag across one of
# these labels is an ordinary drag.
CONTROL_LABEL_PAGE = leaf_page(
    "labels",
    """
<h1 id="h">Aviary projects</h1>
<p id="lede">Two workstreams, one page.</p>
<lf-tabs id="projects">
  <lf-tab id="tab-feeders" label="Winter feeders">
    <p id="p-feeders">Two of the four feeders are mounted; the south pair waits on brackets.</p>
  </lf-tab>
  <lf-tab id="tab-bath" label="Heated bird bath">
    <p id="p-bath">The thermostat arrived cracked and a replacement is on order.</p>
  </lf-tab>
</lf-tabs>
""",
)
CODE_PAGE = leaf_page(
    "code",
    """
<h1 id="t">Code</h1>
<section id="walk">
<p id="lede">The key changes shape:</p>
<lf-code id="walk-code" language="python" hi="2"><pre>
def bucket_key(request):
    if request.token:
        return f"tok:{request.token.id}"
    return "anon"
</pre>
<lf-note at="2">A token id shaped like an address would collide.</lf-note>
</lf-code>
<pre><code class="language-bash"># apply the migration, then run the marked suite
cd gateway &amp;&amp; alembic upgrade head</code></pre>
<lf-code id="plain-code"><pre>
$ leaf version check ./page --render
v1.html: renders clean
</pre></lf-code>
</section>
""",
)
# A diff of three files, one per thing the colouring has to get right: a Python file
# whose second hunk moves a docstring across lines and whose two sides disagree about
# what is open, a yaml file (the grammar that reads a leading `-` as a sequence bullet
# and a leading `+` as a string, so the prefix column has to be off before it looks),
# and a file whose extension names no language at all.
DIFF_PAGE = leaf_page(
    "diff",
    """
<h1 id="t">Diff</h1>
<lf-diff id="patch"><pre>
diff --git a/gateway/limits.py b/gateway/limits.py
--- a/gateway/limits.py
+++ b/gateway/limits.py
@@ -38,2 +38,3 @@ class Limiter:
     def bucket_key(self, request):
-        return request.remote_addr
\\ No newline at end of file
+        if request.token:
+            return f"tok:{request.token.id}"
@@ -71,4 +73,6 @@ class Limiter:
     def reset(self, key):
-        \"\"\"Drop one bucket.
-        Called on logout.\"\"\"
+        \"\"\"Drop one bucket, prefix and all.
+
+        Called on logout, and once per renamed key.
+        \"\"\"
         self.buckets.pop(key, None)
diff --git a/gateway/config.yaml b/gateway/config.yaml
--- a/gateway/config.yaml
+++ b/gateway/config.yaml
@@ -4,2 +4,2 @@ ratelimit:
-  burst: 20
+  burst: 40
   window: 60
diff --git a/deploy/Dockerfile b/deploy/Dockerfile
--- a/deploy/Dockerfile
+++ b/deploy/Dockerfile
@@ -9 +9 @@ COPY gateway /srv/gateway
-RUN pip install -r requirements.txt
+RUN pip install --no-cache-dir -r requirements.txt
</pre></lf-diff>
""",
)
# A page carrying both kinds of native control a widget injects: a checkbox in the light
# DOM and a <summary> the widget staged in a shadow tree.
NATIVE_CONTROL_PAGE = DIFF_PAGE.replace(
    "</main>",
    f"""<lf-shot id="shot-keys" alt="the navigation rail"
         before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>
</main>""",
)
# A page that says the same thing twice *within one section*, which is the only case a
# quote alone cannot place — scoping to a section already separates copies that live under
# different ids. A unified diff is the case that matters and the reason the section can't
# help: it holds the changed line on both sides, under one id, so the two occurrences are a
# bug and its fix, and landing on the wrong one inverts what the comment means.
TWICE_PAGE = leaf_page(
    "twice",
    """
<h1 id="t">Twice</h1>
<section id="repeat">
<p>Ahead of the repeat, so the copies have different neighbours before them.</p>
<p>A first copy follows. The version stamp never lands. And a first tail after it.</p>
<p>Something else entirely, so the two copies do not touch each other.</p>
<p>A second copy follows. The version stamp never lands. And a second tail after it.</p>
</section>
<lf-diff id="patch"><pre>
diff --git a/gateway/cache.py b/gateway/cache.py
--- a/gateway/cache.py
+++ b/gateway/cache.py
@@ -18,3 +18,3 @@ class Bucket:
 def key(self, request):
-    return request.path
+    return request.path, request.headers.get("Accept")
 def store(self, request):
</pre></lf-diff>
""",
)
DRIFT_V1 = leaf_page(
    "drift",
    """
<h1 id="t">Drift</h1>
<section id="drift">
<p>Cache warmup runs first. {phrase}. Retries are capped at three.</p>
<p>Queue drain runs first. {phrase}. Retries are capped at four.</p>
</section>
""",
).replace("{phrase}", "The version stamp never lands")
# v2 rewrites the words on both sides of the *commented* copy and leaves the other alone,
# so the untouched copy is now the better match for the context the comment stored.
DRIFT_V2 = DRIFT_V1.replace(
    "Cache warmup runs first.", "Cache warmup is gone now."
).replace("lands. Retries are capped at three.", "lands. Backoff is capped at three.")
# A passage among padded emoji, which is the only shape that catches the seam between how a
# context is stored and how it is compared: astral characters make the stored string longer
# in code units than in the code points the capture counted, and the padding makes the
# search's window collapse to less than it read. Both are needed, and the padding is tuned
# rather than decorative — a marker plus three spaces collapses 5 units to 3, which leaves
# the pre-fix window just short of the stored length. Two spaces and it is already long
# enough; five and the window doubles and overshoots. Tied to CONTEXT = 24, and to markers
# outside the BMP: ✅ and ⚠ are one code unit each and will not do it.
# The two inputs a well-meaning edit would touch, asserted so the fixture can't quietly
# stop guarding: BMP symbols and padding outside the band both leave the pre-fix code
# passing, and neither shows up as a failure anywhere.
MARKERS = "🔴🟢🟡🔵🟣🟤🟠🟥🟩🟦🔴🟢🟡🔵🟣🟤"
PAD = "   "
assert all(ord(c) > 0xFFFF for c in MARKERS), "BMP markers will not reproduce this"
assert len(PAD) in (3, 4), "outside the band the window is long enough either way"
ASTRAL_PAGE = (
    leaf_page(
        "astral",
        """
<h1 id="t">Astral</h1>
<section id="astral">
<p>Ordinary prose ahead of the first copy here. {phrase} and a tail.</p>
<p>A divider paragraph between the copies.</p>
<p>{run}{phrase} and a tail.</p>
</section>
""",
    )
    .replace("{run}", "".join(m + PAD for m in MARKERS))
    .replace("{phrase}", "TARGET PHRASE")
)
# Two copies of one phrase behind an identical lead, the second closing its section. The
# words that tell them apart are the next section's, which only a capture reading past the
# section edge can store.
EDGE_PAGE = leaf_page(
    "edge",
    """
<h1 id="t">Edge</h1>
<section id="edge">
<p>First pass: when the deploy fails again in the night, the run is retried until it lands. Nothing else moves.</p>
<p>Second pass: when the deploy fails again in the night, the run is retried until it lands.</p>
</section>
<section id="tail">
<p>Rollout resumes once the queue drains completely.</p>
</section>
""",
)


# The same page with nothing after the section, so the closing copy ends the document —
# the one place no capture can supply a second side. What it stores there is an empty
# suffix, which says the passage had nothing after it anywhere on the page, and only one
# occurrence can be somewhere that is still true of.
TAIL_PAGE = EDGE_PAGE.replace(
    """<section id="tail">
<p>Rollout resumes once the queue drains completely.</p>
</section>
""",
    "",
)
assert TAIL_PAGE != EDGE_PAGE, (
    "the section this removes has moved; the contrast is gone"
)
# A passage longer than the search's pattern, twice over, so the pattern's own lead
# matches both copies and only their neighbours tell them apart. Prose rather than
# filler, because the walk that confirms the rest of a quote steps word by word.
LONG_PASSAGE = "Note: the migration replays on every deploy because the version stamp never lands, and the guard reads a column the writer never fills, and the whole batch runs again from the top on each release, and the counters disagree with the log and with each other, and the retry budget is spent before anyone looks at it, and the operator reads the dashboard at noon and files the incident, and the fix ships behind a flag nobody remembers to turn on, and the runbook still names a host that was retired last spring."
TWO_COPIES_PAGE = leaf_page(
    "long passages",
    """
<h1 id="t">Long passages</h1>
<section id="copies">
<p>Ahead of the first copy sits this line.</p>
<p id="first">{passage}</p>
<p>Between the copies sits this other line.</p>
<p id="second">{passage}</p>
</section>
""",
).replace("{passage}", LONG_PASSAGE)
# Prose past the pattern's own ceiling. One expression with a term per character stops
# compiling somewhere past ten thousand of them — measured on the gallery: 1.3ms at four
# hundred characters, 11.6ms at five thousand, a SyntaxError at twelve — and the throw
# would land inside the pass that draws every mark on the page, not just this one's. A
# reader reaches it in one keystroke, so the guard is a page long enough to prove it.
CEILING_PAGE = leaf_page(
    "everything",
    """
<h1 id="t">Everything</h1>
{paras}
""",
).format(
    paras="\n".join(
        f"<p>Paragraph {i} of the record. "
        + f"The deploy replays and the guard reads a column the writer never fills, "
        f"so the whole batch runs again from the top on release {i}. " * 3 + "</p>"
        for i in range(40)
    )
)
# A passage that opens its section stores no prefix — note there is no whitespace between
# the section tag and the paragraph, which is what makes the copy's leading context empty
# rather than short. Both copies carry the identical tail, so a suffix on its own is a bar
# the other copy clears just as well.
THIN_V1 = leaf_page(
    "thin",
    """
<h1 id="t">Thin</h1>
<section id="thin"><p>{phrase}. Retries are capped at three.</p>
<p>An unrelated middle paragraph.</p>
<p>Queue drain runs first. {phrase}. Retries are capped at three.</p>
</section>
""",
).replace("{phrase}", "The version stamp never lands")
# Only the commented copy's tail changes, so the untouched copy is now the better match for
# the one neighbour the comment stored.
THIN_V2 = THIN_V1.replace(
    "lands. Retries are capped at three.</p>\n<p>An unrelated",
    "lands. Backoff is capped at three.</p>\n<p>An unrelated",
)
# The journey's page: a passage to comment on, a board to drag, and a draft to
# edit. In v2 the commented paragraph moves below the notes heading — same text,
# new position — so the anchor has to re-find its passage rather than replay a
# location. The draft's source lines are indented like any other child content;
# the widget owes the user the text without them.
SENTENCE = "The version stamp never lands, so migration 0041 replays on every deploy."
DRAFT_TEXT = "Run the migration before deploying.\nIt is online."
DRAFT_EDITED = "Run the migration before deploying. It takes about a minute."
JOURNEY_SCAFFOLD = leaf_page(
    "journey",
    """
<h1 id="t">Journey</h1>
{before}
<lf-board id="board">
  <lf-column id="col-todo" label="Todo">
    <lf-card id="card-x"><strong>Guard the session delete</strong> One line.</lf-card>
  </lf-column>
  <lf-column id="col-done" label="Done"></lf-column>
</lf-board>
<lf-draft id="draft-ops"><pre>
    Run the migration before deploying.
    It is online.
</pre></lf-draft>
<h2 id="notes">Notes</h2>
{after}
""",
)
PASSAGE = f'<p id="intro">{SENTENCE}</p>'
JOURNEY_V1 = JOURNEY_SCAFFOLD.format(
    before=PASSAGE, after="<p id='p-filler'>Filler.</p>"
)
JOURNEY_V2 = JOURNEY_SCAFFOLD.format(
    before="<p id='p-filler'>Filler.</p>", after=PASSAGE
)


def _draft_says(html, text, attrs=""):
    """The journey page with its draft rewritten — the source's indentation and
    all, since that is what the widget dedents back out."""
    return html.replace(
        '<lf-draft id="draft-ops"><pre>\n'
        + "\n".join(f"    {line}" for line in DRAFT_TEXT.split("\n")),
        f'<lf-draft id="draft-ops"{attrs}><pre>\n    {text}',
    )


def _publish(page_dir, version, html, note):
    """Save a revision and stamp it, asserting the expected public number."""
    source = html.replace("</body>", f"<!-- test revision {version} -->\n</body>")
    (page_dir / "index.html").write_text(source)
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "version",
            "stamp",
            str(page_dir),
            "--text",
            note,
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["version"] == version


@pytest.fixture
def one_reader(browser):
    """A browser context two pages can share, which is what makes them tabs.

    `Browser.new_page` opens each page in a context of its own, so two of them are two
    readers with no storage between them — and a draft lives in the reader's store now,
    which is the whole of what these tests are about."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, color_scheme="light"
    )
    yield context
    context.close()


def compose(page, passage, text=None):
    """Open the composer on a passage the way a reader does, and type into it.

    Without text it only opens, which is how a second tab meets a draft already
    standing on that passage: the two gestures are the same one, so the anchor the
    key is built from is the same in both tabs."""
    page.locator(passage).scroll_into_view_if_needed()
    page.locator(passage).click(click_count=3)
    page.wait_for_selector(".lf-fab", state="visible")
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer textarea")).to_be_focused()
    if text is not None:
        page.locator(".lf-composer textarea").fill(text)


# The two presses this asks about, on one page: a draft's ✎ (a thing to do) and a pick
# mark (a thing to do that becomes a thing the page says once it is pressed).
# Both spellings a page has for a folded section: the platform's <details>, and a settled
# option group, which is a span the widget wrote `aria-expanded` onto. They stand together
# because a reader standing on one cannot see which of the two it is — a fixture holding
# one of them proves the scope for that spelling and says nothing about the other.
DISCLOSED_PAGE = leaf_page(
    "disclosed",
    """
<h1 id="t">Disclosed</h1>
<p id="p1">A first passage, so the page reads as one rather than as two controls.</p>
<details id="dsc"><summary id="dsc-head">What the store costs</summary>
<p id="dsc-body">A replica in each region, and a read on every request that carries a
session.</p></details>
<lf-options id="settled" choose settled>
  <lf-option id="st-keep" chosen><strong>Keep it</strong> Decided last week.</lf-option>
  <lf-option id="st-drop"><strong>Drop it</strong> The alternative.</lf-option>
</lf-options>
""",
)
KEYS_PAGE = leaf_page(
    "keys",
    """
<h1 id="h">Session store</h1>
<lf-options id="opts" choose>
  <lf-option id="opt-keep"><strong>Keep the store</strong> Sessions stay where they are.</lf-option>
  <lf-option id="opt-token"><strong>Signed tokens</strong> No store at all.</lf-option>
</lf-options>
<lf-draft id="draft-ops"><pre>
    Run the migration before deploying.
</pre></lf-draft>
""",
)
SMOOTH_LONG_PAGE = LONG_PAGE.replace(
    "</head>", "<style>body { scroll-behavior: smooth; }</style>\n</head>"
)
FIRST_PRESENTATION = """
  window.__lfPresentation = { frames: [], releases: 0 };
  new MutationObserver((changes) => {
    window.__lfPresentation.releases += changes.length;
  }).observe(document, {
    subtree: true,
    attributeFilter: ["data-lf-presented"],
  });
  const sample = () => {
    const old = document.querySelector("#sug lf-old");
    if (old) {
      const box = old.getBoundingClientRect();
      window.__lfPresentation.frames.push({
        stale: old.checkVisibility({
          opacityProperty: true,
          visibilityProperty: true,
        }),
        interactive: old.contains(document.elementFromPoint(
          box.left + box.width / 2,
          box.top + box.height / 2,
        )),
        height: old.getBoundingClientRect().height,
        note: getComputedStyle(document.body, "::after").content,
        waitingPainted:
          getComputedStyle(document.body, "::after").visibility !== "hidden"
          && Number(getComputedStyle(document.body, "::after").opacity) > 0,
      });
    }
    if (document.body?.dataset.lfPresented === undefined)
      requestAnimationFrame(sample);
  };
  requestAnimationFrame(sample);
"""
_CARD = (
    '<lf-card id="card-x"><strong>Guard the session delete</strong> One line.</lf-card>'
)


def _card_done(html):
    """The journey page with its card written in Done — the honoring of a
    recorded drag, or the author's own relocation."""
    return html.replace(
        f'    {_CARD}\n  </lf-column>\n  <lf-column id="col-done" label="Done"></lf-column>',
        f'  </lf-column>\n  <lf-column id="col-done" label="Done">{_CARD}</lf-column>',
    )


SUGGEST_BLOCK = (
    '<lf-suggestion id="sug-fix" resolves="c1">'
    '<lf-old><p id="old-claim">It is not online.</p></lf-old>'
    "<lf-new><p>It takes a minute of downtime.</p></lf-new>"
    "</lf-suggestion>"
)


@contextmanager
def live_watcher(page_dir, page):
    """Hold the exact lease `leaf wait` uses for the duration of the block."""
    session = service_model.page_claim(page_dir)
    lease = leases_model.take_waiter_lease(
        leases_model.waiter_lease_path(page_dir, session)
    )
    assert lease
    told(page)
    try:
        yield
    finally:
        lease.close()
    # Outside the finally: a block that raised has its own failure to report, and
    # nothing after it to wait for.
    told(page)


# What the tab is wearing, once the banner has judged `want` and the tab agrees with it.
# The runtime builds the href, so reading it back is reading what the browser was handed;
# null until both hold, which is what makes this a wait — a status arrives on a poll, and
# the tab is repainted in the pass that repaints the dot.
#
# Naming the state is what keeps a read off one the page is passing through: dropping the
# watcher takes a waiting page through `away` on its way to `unheld`, and a wait asking
# only for agreement is answered from there, by a tab that is perfectly correct about a
# state the test is not about.
#
# The tone read is the sheet the runtime appended, never the mark's own — and the two are
# not told apart by their colours. The mark is authored in the accent, so a working page
# paints it the shade it already was, and a reading that took the first rule it found
# agreed with the banner on the one state where nothing had to have happened.
TAB_TONE = """(want) => {
    const el = document.querySelector('.lf-banner .lf-dot');
    const judged = el.className.replace('lf-dot', '').trim();
    const prefix = 'data:image/svg+xml,';
    const href = document.querySelector('link[rel=icon]').getAttribute('href');
    const svg = href.startsWith(prefix)
        ? new DOMParser().parseFromString(
              decodeURIComponent(href.slice(prefix.length)), 'image/svg+xml',
          ).documentElement
        : null;
    const sheets = svg ? [...svg.querySelectorAll('style')] : [];
    const tone =
        sheets.length > 1 ? /fill: ([^}]+) \\}/.exec(sheets.at(-1).textContent)?.[1] : null;
    const dot = getComputedStyle(el).backgroundColor;
    return VERDICT;
}"""
# The same reading with nothing required of it, for a failure that says what it found.
TAB_AND_DOT = TAB_TONE.replace("VERDICT", "[judged, tone, dot]")
TAB_TONE = TAB_TONE.replace("VERDICT", "judged === want && tone === dot ? tone : null")
# A project widget whose body is entirely supplied at runtime. Two rows deliberately say
# the same word: text and document order cannot identify either one, while each record's
# key can.
DATA_PROJECTION_PAGE = leaf_page(
    "data projection",
    """
<h1 id="title">Deployments</h1>
<p id="lede">Live status follows.</p>
<lf-feed id="deployments" source="deployments"></lf-feed>
""",
)

DATA_PROJECTION_MODULE = """
import {offer, projectData, watchData} from '/runtime/widget-api.js';
customElements.define('lf-feed', class extends HTMLElement {
  connectedCallback() {
    if (!this.stopWatching)
      this.stopWatching = watchData(
        this,
        'rows',
        snapshot => this.show(snapshot?.value ?? []),
      );
  }
  disconnectedCallback() {
    this.stopWatching?.();
    this.stopWatching = null;
  }
  show(rows) {
    projectData(this, rows, row => row.key, ({value}) => {
      const row = document.createElement('p');
      row.append(value, offer('button', 'inspect', 'Inspect'));
      return row;
    });
  }
});
"""


def data_projection_page(serve):
    feed = {
        "description": "A project-supplied live feed.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
            "source": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
        },
        "required": ["id", "source"],
        "additionalProperties": False,
        "x-content": "none",
        "x-data": {"rows": {"contract": "deployment-rows", "source": "source"}},
        "x-upgrade": True,
        "x-example": ('<lf-feed id="feed-example" source="deployments"></lf-feed>'),
    }
    contract = {
        "description": "Current deployment status rows.",
        "schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "minLength": 1},
                    "value": {"type": "string"},
                },
                "required": ["key", "value"],
                "additionalProperties": False,
            },
        },
    }
    url = serve(
        DATA_PROJECTION_PAGE,
        layer_registry={
            "lf-feed": feed,
            "$data": {"contracts": {"deployment-rows": contract}},
        },
        layer_widgets={"lf-feed.js": DATA_PROJECTION_MODULE},
    )
    d = serve.page_dir
    data_model.cmd_data_set(
        d,
        "deployments",
        [
            {"key": "api", "value": "Ready"},
            {"key": "worker", "value": "Ready"},
        ],
    )
    return url
