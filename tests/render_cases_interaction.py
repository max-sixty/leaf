"""Shared interaction browser-integration cases and readings."""

import json
from datetime import datetime, timedelta

from leaf_interact import events as events_model
from render_harness import (
    EXAMPLES,
    TOKEN,
    author_test_widget,
    leaf_page,
)

# A page with an outline: three headings, and passages under each to hang threads on.
# LONG_PAGE has one heading and sixty paragraphs, which cannot tell an order that
# follows the page from one that follows the log — every thread on it is in the same run.
PANEL_PAGE = leaf_page(
    "panel",
    """
<h1 id="t">Shipping offline editing</h1>
<p id="lede">The lede, which is the first thing anybody reads on the way in.</p>
<section id="s-how">
  <h2 id="h-how">How it works</h2>
  <p id="how-store">A queue holds every edit until the connection comes back.</p>
  <p id="how-cap">The store is capped at forty megabytes a workspace.</p>
  <lf-diff id="how-patch"><pre>
diff --git a/gateway/limits.py b/gateway/limits.py
--- a/gateway/limits.py
+++ b/gateway/limits.py
@@ -1,3 +1,4 @@
 def ceiling(limit, approvals):
-    return limit
+    # the ceiling doubles per approval
+    return "over" if approvals > 12 else limit
</pre></lf-diff>
</section>
<section id="s-merge">
  <h2 id="h-merge">The merge rule</h2>
  <p id="merge-both">Two people editing one document offline is the case to answer.</p>
  """
    + "\n".join(
        f"<p id='m{i}'>Filler {i}. " + "Words. " * 24 + "</p>" for i in range(20)
    )
    + """
</section>
""",
)

# The panel's list, in the order it stands, with the headings among the threads: a
# heading is its own words, a thread its id. One query, because what is asserted about
# the order is always about both — a run is a heading and the threads it names.
LIST_RUNS = """() => [...document.querySelector(".lf-threads").children]
  .map((n) => (n.dataset.group ? "§ " + n.textContent : n.dataset.id))
  .filter(Boolean)"""


def panel_comment(d, text, anchor=None, author="user"):
    """One thread's opening message, written straight to the log."""
    event = {"kind": "comment", "author": author, "version": 1, "text": text}
    if author == "claude":
        event["agent"] = "Claude"
    if anchor:
        event["anchor"] = anchor
    return events_model.append_event(d, event)["id"]


# What the list is holding, from the one query that answers both halves of the
# question a departing thread raises: what stands where, and what the keys can still
# reach. The two lists differ by exactly the thread on its way out.
LIST_STATE = """() => {
  const list = document.querySelector(".lf-threads");
  return {
    standing: [...list.children].map((n) => n.dataset.id).filter(Boolean),
    walkable: [...list.querySelectorAll(":scope > .lf-thread")].map(
      (n) => n.dataset.id,
    ),
  };
}"""
# Every frame the fold paints, sampled from the page because there is nowhere else to
# sample it: what a motion looks like is a sequence, and every other check here reads a
# state. One height per animation frame until the node leaves the page, which is the
# fold's own end and so the wait's fact.
FRAME_BY_FRAME = """(sel) => {
  window.__seen = [];
  window.__done = false;
  const tick = () => {
    const el = document.querySelector(sel);
    if (!el) return void (window.__done = true);
    window.__seen.push(+el.getBoundingClientRect().height.toFixed(1));
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}"""
STACKED_OPTIONS_PAGE = leaf_page(
    "stacked options",
    """
<h1 id="h">Clip storage</h1>
<lf-options id="stacked" choose>
  <lf-option id="st-sd"><lf-chip>effort: low</lf-chip><lf-chip tone="danger">risk: high</lf-chip>
    <strong>SD card only</strong>
    <dl class="facts"><dt>Keeps</dt><dd>nine days</dd><dt>Retrieval</dt><dd>a ladder</dd></dl>
    <p>Clips stay on the camera's card and overwrite oldest-first.</p>
  </lf-option>
  <lf-option id="st-pi" recommended><lf-chip>effort: med</lf-chip><lf-chip>risk: low</lf-chip>
    <strong>Pi in the shed</strong>
    <dl class="facts"><dt>Keeps</dt><dd>a season</dd><dt>Retrieval</dt><dd>the couch</dd></dl>
    <p>A nightly pull over the garden wifi; the link is the weak span.</p>
  </lf-option>
</lf-options>
<lf-options id="terse">
  <lf-option id="t-paper"><lf-chip>effort: low</lf-chip><lf-chip>risk: high</lf-chip><strong>Paper maps</strong> Nothing
  to charge.</lf-option>
  <lf-option id="t-gps"><lf-chip>£240</lf-chip><lf-chip>a week of battery</lf-chip><lf-chip>resellable if the season ends early</lf-chip><strong>GPS</strong> A week of
  battery.</lf-option>
</lf-options>
<lf-compare id="pair">
  <lf-variant id="cv-cedar"><strong>Cedar</strong>
    <dl class="facts"><dt>Seal</dt><dd>never</dd></dl>
    <p>Weathers silver; no sealant, no schedule.</p></lf-variant>
  <lf-variant id="cv-pine"><strong>Pine</strong>
    <dl class="facts"><dt>Seal</dt><dd>yearly</dd></dl>
    <p>Cheaper up front; seal it every autumn.</p></lf-variant>
</lf-compare>
<lf-compare id="terse-pair">
  <lf-variant id="cv-oiled"><strong>Oiled</strong> Darker, and a spring job.</lf-variant>
  <lf-variant id="cv-bare"><strong>Bare</strong> Silver by June.</lf-variant>
</lf-compare>
<lf-compare id="spread">
  <lf-variant id="cv-oak"><strong>Oak</strong> Heavy.</lf-variant>
  <lf-variant id="cv-ash"><strong>Ash</strong> Pale, and it moves in damp, so a board
    laid in March stands proud of the one beside it by June and the fixings work
    loose over the winter after that.</lf-variant>
  <lf-variant id="cv-elm"><strong>Elm</strong> Scarce.</lf-variant>
  <lf-variant id="cv-yew"><strong>Yew</strong> Slow.</lf-variant>
  <lf-variant id="cv-fir"><strong>Fir</strong> Cheap, and it rots at the ground.</lf-variant>
</lf-compare>
""",
)
# A question carried on the group rather than in a heading beside it, in every shape a
# group takes it in: the two forms, the joined control and the plain stack, and the
# settled collapse. One page, because the shapes are independent axes and a rule written
# against one governs the rest without saying so — which is how the joined control came
# to give the question none of the padding it gives every other cell while a corpus
# holding one labelled card group stayed green (examples/CLAUDE.md).
ASKED_PAGE = leaf_page(
    "asked",
    """
<h1 id="t">Asked</h1>
<lf-options id="cards" choose label="Where should a session live?">
  <lf-option id="c-redis"><strong>Redis</strong>
  <p>A store we already run, keyed by an opaque id.</p></lf-option>
  <lf-option id="c-pg"><strong>Postgres</strong>
  <p>One fewer moving part, at the cost of write load.</p></lf-option>
</lf-options>
<lf-options id="rows" choose multiple label="Which jobs are worth starting?">
  <lf-option id="r-drill">A revocation drill</lf-option>
  <lf-option id="r-rotate">Key rotation for the fallback cookie</lf-option>
</lf-options>
<lf-options id="done" choose settled label="How do parallel sessions merge?">
  <lf-option id="d-serial" chosen><strong>A branch each</strong>
  <p>Merged one at a time against current main.</p></lf-option>
  <lf-option id="d-shared"><strong>One shared branch</strong>
  <p>Cheapest to set up, and conflicts are the norm.</p></lf-option>
</lf-options>
""",
)
# The other form of a question, on one page beside the first: options that are bare
# labels, naming the blocks of the page they are about, and a group taking more than one.
# One label runs into inline markup and one row carries a chip, because both are things a
# row lays out beside its own apparatus and neither is anything a card would notice.
#
# Form and arity are independent, so the page carries both values of each: `multiple` is
# on a list (#jobs) and on a titled group (#tools), against single-pick cards
# (#bracket). Which is what makes a claim about arity testable on its own — #jobs against
# #bracket differs in two things at once, and a rule that was really the list form's
# would pass that pair either way.
ASK_PAGE = leaf_page(
    "ask",
    """
<h1 id="h">Three jobs</h1>
<lf-options id="jobs" choose multiple>
  <lf-option id="job-mounts" for="sec-mounts">Replace the <code>M8</code> mounts</lf-option>
  <lf-option id="job-heater" for="sec-heater"><lf-chip tone="ok">reversible</lf-chip>Heat the bird bath</lf-option>
  <lf-option id="job-camera">Neither — the camera first</lf-option>
</lf-options>
<section id="sec-mounts"><h2>The mounts</h2><p id="mounts-p">Plastic, and one came
down in January.</p></section>
<section id="sec-heater"><h2>The bird bath</h2><p id="heater-p">Frozen eleven
mornings last winter.</p></section>
<lf-options id="bracket" choose>
  <lf-option id="br-steel"><strong>Steel</strong> Galvanised, drop-in.</lf-option>
  <lf-option id="br-cedar"><strong>Cedar</strong> Cheap; needs sealing.</lf-option>
</lf-options>
<lf-options id="tools" choose multiple>
  <lf-option id="tl-clamp"><strong>Bar clamp</strong> Holds the rail while it sets.</lf-option>
  <lf-option id="tl-torque"><strong>Torque wrench</strong> The mounts are rated.</lf-option>
</lf-options>
<lf-options id="ordered">
  <lf-option id="ord-mounts">Mounts, before the frost</lf-option>
  <lf-option id="ord-heater">Heater, after it</lf-option>
</lf-options>
""",
)


def sent_events(page_dir):
    return [
        json.loads(line)
        for line in (page_dir / "comments.jsonl").read_text().splitlines()
    ]


NESTED_ASK_PAGE = leaf_page(
    "nested",
    """
<h1 id="h">Two jobs</h1>
<lf-options id="outer" choose multiple>
  <lf-option id="out-drill"><strong>The revocation drill</strong>
    <p id="drill-p">Support wants it run at their own volume.</p>
    <lf-options id="inner" choose>
      <lf-option id="in-now">This sprint</lf-option>
      <lf-option id="in-next">Next sprint</lf-option>
    </lf-options>
  </lf-option>
  <lf-option id="out-keys"><strong>Key rotation</strong>
    <p id="keys-p">Cheap, and overdue since the split.</p>
  </lf-option>
</lf-options>
""",
)
# An option arguing its case with the evidence inside it, which is the whole reason the
# card is more than a label. Three things to work stand in one option, one per vocabulary
# the guard reads: a widget's own control (the shot's frame, a label injected through
# `offer` that covers the whole image, so this is most of the card's area rather than a
# corner of it), a
# widget's own words (the draft's body, which is deliberately not chrome and so is reached
# only by being inside a widget the option contains), and an element HTML calls
# interactive that no widget put there (the disclosure). A page holding one of the three
# would leave the other two to a guard that had never been asked about them.
INLINE_CASE_PAGE = leaf_page(
    "inline case",
    """
<h1 id="h">The status column</h1>
<lf-options id="rollout" choose>
  <lf-option id="ro-column"><strong>Ship the column</strong>
    <lf-shot id="ro-shot" alt="the run list, before and after the status column"
      before="/media/051bee487bfb5d13.png" after="/media/a99a1b63048502d0.png"></lf-shot>
    <details id="ro-numbers"><summary>What it costs</summary>
      <p id="ro-cost">One join, 40ms at the list's own volume.</p></details>
    <lf-draft id="ro-note"><pre>
Run status now shows on the run list itself.
</pre></lf-draft>
    <p id="ro-column-p">A failure reads off the list instead of costing a click.</p>
  </lf-option>
  <lf-option id="ro-leave"><strong>Leave it</strong>
    <p id="ro-leave-p">A failure stays one click away.</p>
  </lf-option>
</lf-options>
""",
)
CHIP_PAGE = leaf_page(
    "chips",
    """
<h1 id="h">Short facts</h1>
<p id="intro">The store is <span class="tag">experimental</span> for now.</p>
<lf-options id="picks" choose>
  <lf-option id="p-keep"><lf-chip>reversible</lf-chip><strong>Keep the store</strong></lf-option>
</lf-options>
<lf-tasks id="plan">
  <lf-task id="t-camera" status="active" owner="finch"><strong>Mount the camera</strong></lf-task>
</lf-tasks>
""",
)
PAINTED_PAGE = leaf_page(
    "painted",
    """
<h1 id="h">What the paint says</h1>
<lf-timeline id="tl">
  <lf-event id="e-dark" at="09:12" kind="failure"><strong>Feed stopped</strong>
  The north camera went dark and the alert never fired.</lf-event>
</lf-timeline>
<lf-options id="picks">
  <lf-option id="p-stage" recommended><strong>Migrate in stages</strong> Table by table.</lf-option>
  <lf-option id="p-once"><strong>Migrate at once</strong> One window, one cutover.</lf-option>
</lf-options>
<lf-tasks id="plan">
  <lf-task id="t-baffles" status="blocked" owner="finch"><strong>Fit squirrel baffles</strong>
  Waiting on the brackets.</lf-task>
</lf-tasks>
""",
)
SETTLED_ASK_PAGE = ASK_PAGE.replace(
    '<lf-options id="jobs" choose multiple>',
    '<lf-options id="jobs" choose multiple settled>',
)
# Where an exhibit's own boxes begin and end, which is what the marking beside them has
# to meet. A widget that generates no box hands its boxes to the flow — any wrapper a
# style leaves `display: contents` — so a child with no rect is walked through rather
# than skipped, and that is the case no selector in the theme can reach for itself. The runtime's own
# layer is not the exhibit: `.lf-ui` is chrome standing in the page's blocks, and a
# marking drawn around it would be marking the reading rather than the page.
EXHIBIT_EXTENT = """
(id) => {
  const el = document.getElementById(id);
  const label = el.querySelector(':scope > [data-lf-said="label"]');
  let top = Infinity, bottom = -Infinity;
  const walk = (n) => {
    for (const c of n.children) {
      if (c === label || c.classList.contains('lf-ui')) continue;
      const r = c.getBoundingClientRect();
      if (r.height) { top = Math.min(top, r.top); bottom = Math.max(bottom, r.bottom); }
      else walk(c);
    }
  };
  walk(el);
  return {top, bottom, note: label ? label.getBoundingClientRect().bottom : null};
}
"""

SPECIMEN_EXAMPLES = [p for p in EXAMPLES if "<lf-specimen" in p.read_text()]
assert SPECIMEN_EXAMPLES, (
    "no shipped example holds a specimen — the sweep below would drive the fixture "
    "page alone, and the rule it holds is one the corpus is the whole test of"
)
TABLE_REPLY = """The ceilings, unchanged:

| Plan | A minute | Burst | Counted against | Reference |
| --- | --- | --- | --- | --- |
| Free | 60 | 120 | the token | GW-LIMITS-FREE-2026 |
| Enterprise | 6,000 | 12,000 | the token, per environment | GW-LIMITS-ENTERPRISE-2026 |

Taken from https://example.com/gateway/limits/reference/by-plan/current/table
"""
# Two pending changes a line apart, and a third inside a widget that positions
# its own contents — the case where `left: 100%` resolves against the card rather
# than the column, and drops the controls back into the text, unless the row is
# the column's own child.
SUGGESTION_PAGE = leaf_page(
    "suggestions",
    """
<h1 id="h">Feeder notes</h1>
<p id="replace">The camera survey found two dead zones.
  <lf-suggestion id="sug-refill">
    <lf-old>Refill every feeder each morning.</lf-old>
    <lf-new>Refill a feeder when its camera shows it half-empty.</lf-new>
  </lf-suggestion></p>
<p id="insert">Seed mix stays through the migration.
  <lf-suggestion id="sug-thistle">
    <lf-new>Switch the north feeder to thistle in autumn.</lf-new>
  </lf-suggestion></p>
<lf-board id="feeders">
  <lf-column id="col-todo" label="To do">
    <lf-card id="card-heater"><strong>Heated perch</strong>
      <lf-suggestion id="sug-in-card">
        <lf-old>Wire the south feeder.</lf-old>
        <lf-new>Wire the south feeder to the porch circuit.</lf-new>
      </lf-suggestion></lf-card>
  </lf-column>
  <lf-column id="col-done" label="Done"></lf-column>
</lf-board>
""",
)
# All three shapes, because what says "nobody has decided this" differs in each and
# only one of them has a second half to lean on. A replace shows the pair, an insert
# shows a tint against the prose around it, and a pending deletion is a struck line
# with an empty margin beside it — which is also exactly what a deletion looks like
# once it has happened.
PROPOSED_PAGE = leaf_page(
    "proposed",
    """
<h1 id="h">Feeder notes</h1>
<p id="replace">The camera survey found two dead zones.
  <lf-suggestion id="sug-replace">
    <lf-old>Refill every feeder each morning.</lf-old>
    <lf-new>Refill a feeder when its camera shows it half-empty.</lf-new>
  </lf-suggestion></p>
<p id="insert">Seed mix stays through the migration.
  <lf-suggestion id="sug-insert">
    <lf-new>Switch the north feeder to thistle in autumn.</lf-new>
  </lf-suggestion></p>
<p id="delete">The heater runs from the porch circuit.
  <lf-suggestion id="sug-delete">
    <lf-old>Check the thermostat every Sunday.</lf-old>
  </lf-suggestion></p>
""",
)
# A proposal inside an exhibition: the change is a phrase in one of the cases, so the
# variant holding it is as terse as the one beside it. A suggestion is also the one
# family a decision is taken back by rebuilding — no verb can state its authored value,
# so undo hands the widget a pristine clone of the version's markup, and everything the
# runtime had painted on it is on the node the clone replaced.
REBUILT_INLINE_PAGE = leaf_page(
    "stores",
    """
<h1 id="h">Session store</h1>
<lf-compare id="cmp-stores">
  <lf-variant id="v-service"
    ><lf-suggestion id="sug-store"><lf-old>Redis</lf-old><lf-new>Valkey</lf-new></lf-suggestion
    >, one hop from the app</lf-variant
  >
  <lf-variant id="v-cookie">A signed cookie, with nothing to run</lf-variant>
</lf-compare>
""",
)
SWAP_PAGE = leaf_page(
    "swap",
    """
<h1 id="h">Feeder notes</h1>
<p id="swapped">Plans changed.
  <lf-suggestion id="sug-swap">
    <lf-old>Refill every feeder each morning.</lf-old>
    <lf-new>The cameras watch seed levels overnight instead.</lf-new>
  </lf-suggestion></p>
""",
)
COLLAPSED_PAGE = leaf_page(
    "collapsed",
    """
<h1 id="h">Winter</h1>
<p id="stocked">The feeders are stocked.
  <lf-suggestion id="sug-now">
    <lf-new>Thistle goes out in October.</lf-new>
  </lf-suggestion></p>
<details id="later"><summary id="sum">Deferred</summary>
<p id="deferred">Nest boxes wait for spring.
  <lf-suggestion id="sug-boxes">
    <lf-new>Order them in February.</lf-new>
  </lf-suggestion></p>
</details>
""",
)
SHORT_SUGGESTION = leaf_page(
    "short suggestion",
    """
<h1 id="t">Short</h1>
<section id="s">
<lf-suggestion id="sug">
  <lf-old><p id="was">Retry twice.</p></lf-old>
  <lf-new><p id="now">Retry three times.</p></lf-new>
</lf-suggestion>
<p id="after">The backoff is unchanged either way.</p>
</section>
""",
)
# Every animation the page starts, held at time zero so a test can read it rather than
# race it. What it catches is everything through `motion()`, which is the layer's only
# caller of `animate` — the folds and the board's FLIP, each started synchronously
# inside the gesture that causes it. CSS animations run outside it and are never seen,
# `grow` among them. Installed before anything runs, so the first frame is already held.
HOLD_MOTION = """
  window.__lfHeld = [];
  const inner = Element.prototype.animate;
  Element.prototype.animate = function (...args) {
    const motion = inner.apply(this, args);
    motion.pause();
    motion.currentTime = 0;
    window.__lfHeld.push(motion);
    return motion;
  };
"""
# Every shape the ask predicate has to tell apart, on one page: four things the page is
# waiting on the reader for, and, beneath them, one of each way of not being one. The
# four are in document order, because that is the order the walk below must take them in.
ASKS_PAGE = leaf_page(
    "asks",
    """
<h1 id="h">What is still open</h1>
<lf-options id="live-question" label="Where should sessions live?" choose>
  <lf-option id="lq-keep"><strong>Keep the store</strong> Sessions stay where they are.</lf-option>
  <lf-option id="lq-token"><strong>Signed tokens</strong> No store at all.</lf-option>
</lf-options>
<lf-suggestion id="sug-refill">
  <lf-old><p id="refill-was">Refill every feeder each morning.</p></lf-old>
  <lf-new><p id="refill-now">Refill a feeder when its camera says so.</p></lf-new>
</lf-suggestion>
<lf-tasks id="plan">
  <lf-task id="t-mounts" status="done"><strong>Replace the mounts</strong></lf-task>
  <lf-task id="t-baffles" status="review" owner="finch"><strong>Fit squirrel baffles</strong></lf-task>
  <lf-task id="t-bath" status="blocked"><strong>Heat the bird bath</strong></lf-task>
  <lf-task id="t-camera" status="active"><strong>Mount the camera</strong></lf-task>
</lf-tasks>
<lf-options id="honored" choose>
  <lf-option id="hon-tiers" chosen><strong>Two-tier gates</strong></lf-option>
  <lf-option id="hon-one"><strong>One gate</strong></lf-option>
</lf-options>
<lf-options id="retired" choose settled>
  <lf-option id="ret-lax"><strong>Lax cookie</strong></lf-option>
</lf-options>
<lf-options id="exhibited">
  <lf-option id="exh-paper"><strong>Paper maps</strong></lf-option>
</lf-options>
<lf-milestones id="rail">
  <lf-milestone id="m-survey" status="done"><strong>Survey the sites</strong></lf-milestone>
  <lf-milestone id="m-build" status="active"><strong>Build the feeders</strong></lf-milestone>
  <lf-milestone id="m-install" status="blocked"><strong>Install and watch</strong></lf-milestone>
</lf-milestones>
<lf-specimen id="spec" label="a decision">
  <lf-options id="spec-opts" choose>
    <lf-option id="spec-paper"><strong>Paper maps</strong></lf-option>
  </lf-options>
</lf-specimen>
""",
)
ASKS_IN_ORDER = ["live-question", "sug-refill", "t-baffles", "t-bath"]


ASK_WITH_CONTEXT_PAGE = leaf_page(
    "ask with context",
    f"""
<h1 id="h">A decision with context</h1>
{"".join(f"<p id='lead-{i}'>Earlier finding {i}. " + "Background. " * 18 + "</p>" for i in range(8))}
<lf-ask id="storage-ask">
  <h2 id="storage-heading">How the full store behaves</h2>
  <p id="storage-context-1">The beta never reached the cap, so this is the first
  reader's experience of it. The recommendation follows the observed reopen rate.</p>
  <p id="storage-context-2">The options are useful only after that premise is in view;
  arriving straight at them starts in the middle of the question.</p>
  <lf-options id="storage-options" choose label="What should a full store do?">
    <lf-option id="storage-evict"><strong>Drop the oldest documents</strong>
    Editing continues and the server keeps the work.</lf-option>
    <lf-option id="storage-stop"><strong>Pause offline editing</strong>
    Nothing leaves, but the editor becomes read-only.</lf-option>
  </lf-options>
</lf-ask>
{"".join(f"<p id='tail-{i}'>Later finding {i}. " + "Background. " * 18 + "</p>" for i in range(8))}
""",
)
# The ask the walk is standing on. One ask wears the mark, on however many boxes it
# shows through — every shipped widget draws one, and a wrapper a page styles boxless
# hangs it on the boxes its contents make — so what says the walk is in one place is
# the outermost page element wearing it, never the count of elements that do. Scoped to
# main because the asks tray's row mirrors the same fact in the chrome.
STANDING_ASK = "main [data-lf-ask]:not([data-lf-ask] [data-lf-ask])"
# The document's scroll once it has stopped moving. A leaf's travel is a glide, so any
# reading taken while it runs is of a place the gesture passes through rather than of
# where it went — and "the ask is on screen" is one of those places, true for a moment
# in the wrong position before the glide has started. A test that waited on that passed
# with the travel bug put back, which is how this came to be written.
SCROLL_SETTLED = """(hold) => {
  const now = document.body.scrollTop;
  if (now !== window.__lfScroll) {
    window.__lfScroll = now;
    window.__lfScrollSince = performance.now();
    return false;
  }
  return performance.now() - window.__lfScrollSince > hold;
}"""
# Where the tray's rows say their ask's own words, which is the half of a row a static
# lint can never read: the words are whatever the page renders, after every upgrade.
# Every widget that measures a number off a live box, authored into the page and sent in
# a reply, so the two readings of each can be compared instead of pinned to a number. The
# words are the same in both, which is what makes the room they need the same.
ROOM_WIDGETS = """<lf-options id="{id}-q" choose label="Which extras go in?">
  <lf-option id="{id}-tray">A seed tray under the feeder</lf-option>
  <lf-option id="{id}-pole">A second pole for the north pair</lf-option>
</lf-options>
<lf-board id="{id}-b">
  <lf-column id="{id}-todo" label="To do">
    <lf-card id="{id}-brackets"><strong>Steel brackets</strong> For the north pair.</lf-card>
  </lf-column>
  <lf-column id="{id}-done" label="Done">
    <lf-card id="{id}-mounts"><strong>South mounts</strong></lf-card>
  </lf-column>
</lf-board>
<lf-roster id="{id}-r">
  <lf-agent id="{id}-wren" state="working">
    <strong>wren</strong> Fitting the brackets.
  </lf-agent>
</lf-roster>"""

# Which element holds each room, and the custom property the theme spends it through.
ROOMS = [("-q", "--lf-word-room"), ("-b", "--lf-grip-room"), ("-r", "--lf-state-room")]

# What the theme is given, asked of the element that states it.
ROOM_HELD = """([id, prop]) => {
  const el = document.getElementById(id);
  return el && getComputedStyle(el).getPropertyValue(prop).trim();
}"""

MESSAGE_ROOM_PAGE = leaf_page(
    "message-room",
    """
<h1 id="mr-h">Bracket order</h1>
"""
    + ROOM_WIDGETS.format(id="mr-page"),
)


ASK_ROW_SAYS = """() => [...document.querySelectorAll('button.lf-asks-row')].map((r) => ({
  at: r.getAttribute('data-lf-at'),
  kind: r.querySelector('.lf-asks-kind').textContent,
  says: r.querySelector('.lf-asks-says').textContent,
  w: Math.round(r.getBoundingClientRect().width),
  h: Math.round(r.getBoundingClientRect().height),
}))"""
CHANGE_SHAPES_PAGE = leaf_page(
    "retry policy",
    """
<h1 id="title">Retry policy</h1>
<lf-suggestion id="sug-rewrite">
  <lf-old><p id="p-job">The worker retries a failed job three times.</p></lf-old>
  <lf-new><p>The worker retries a failed job, then parks it.</p></lf-new>
</lf-suggestion>
<lf-suggestion id="sug-insert">
  <lf-new><p>Parked jobs are listed on the run page.</p></lf-new>
</lf-suggestion>
<lf-suggestion id="sug-delete">
  <lf-old><p id="p-logs">Retries are logged at debug level.</p></lf-old>
</lf-suggestion>
<lf-options id="shapes-q" label="How long should a parked job wait?" choose>
  <lf-option id="wait-day"><strong>A day</strong></lf-option>
  <lf-option id="wait-week"><strong>A week</strong></lf-option>
</lf-options>
""",
)
# A group that takes a pick, so the layer seats a conversation in it (x-conversation),
# and a paragraph beside it so the diff below has one real change to find.
CONVERSATION_DIFF_PAGE = leaf_page(
    "conversation-diff",
    """
<h1 id="cd-h">Bracket order</h1>
<p id="cd-lede">The south pair is up and drawing traffic.</p>
<lf-options id="cd-q" choose label="Which extras go in?">
  <lf-option id="cd-tray">A seed tray under the feeder</lf-option>
  <lf-option id="cd-pole">A second pole for the north pair</lf-option>
</lf-options>
""",
)
LIVE_READING = (
    "The reader is halfway through this account of the cutover and its evidence."
)
LIVE_V1 = leaf_page(
    "Live first",
    """
<h1 id="live-title">Live first</h1>
{lead}
<p id="live-reading">{reading}</p>
{tail}
""",
    head='<meta name="description" content="first">',
).format(
    lead="\n".join(
        f'<p id="live-lead-{i}">Lead {i}. ' + "Context. " * 18 + "</p>"
        for i in range(18)
    ),
    reading=LIVE_READING,
    tail="\n".join(
        f'<p id="live-tail-{i}">Tail {i}. ' + "Context. " * 18 + "</p>"
        for i in range(18)
    ),
)
LIVE_V2 = (
    LIVE_V1.replace("<title>Live first</title>", "<title>Live second</title>")
    .replace(
        'name="description" content="first"', 'name="description" content="second"'
    )
    .replace('<html lang="en">', '<html lang="fr" data-live-root="second">')
    .replace(
        "<body>",
        '<body class="live-second" data-live-body="second" style="--live-body: 2">',
    )
    .replace(
        '<h1 id="live-title">Live first</h1>',
        '<h1 id="live-title">Live second</h1>'
        + "\n".join(
            f'<p id="live-new-{i}">New finding {i}. ' + "Fresh context. " * 18 + "</p>"
            for i in range(5)
        ),
    )
    .replace(
        '<script type="module" src="/leaf.js"></script>',
        '<meta name="lf-review" content="sign-off">\n'
        "<style>#live-reading { --live-cut: 2; }</style>\n"
        '<script type="module" src="/leaf.js"></script>',
    )
)
LIVE_V3 = (
    LIVE_V2.replace("<title>Live second</title>", "<title>Live third</title>")
    .replace(
        'name="description" content="second"', 'name="description" content="third"'
    )
    .replace('<html lang="fr" data-live-root="second">', '<html lang="en">')
    .replace(
        '<body class="live-second" data-live-body="second" style="--live-body: 2">',
        "<body>",
    )
    .replace(
        '<h1 id="live-title">Live second</h1>', '<h1 id="live-title">Live third</h1>'
    )
    .replace('<meta name="lf-review" content="sign-off">\n', "")
    .replace("<style>#live-reading { --live-cut: 2; }</style>\n", "")
)


def live_url(version_url):
    """The stable handover address for a served fixture's authenticated origin."""
    return version_url.split("/versions/", 1)[0] + f"/?t={TOKEN}"


# A section that generates no box of its own, holding blocks that carry no id. The
# reading position's landmark is whichever id stands nearest the block the reader was
# on, so the wrapper is it — which is what a suggestion around whole sections is, and
# what any layer's wrapper may be.
BOXLESS_SECTION_PAGE = leaf_page(
    "boxless section",
    """
<h1 id="t">Boxless</h1>
{lead}
<div id="wrap" style="display: contents">
{held}
</div>
{tail}
""",
).format(
    lead="\n".join(
        f"<p id='lead{i}'>Lead {i}. " + "Filler. " * 20 + "</p>" for i in range(30)
    ),
    held="\n".join(
        f"<p>Held paragraph {i}, standing under a wrapper with no box of its own. "
        + "More words. " * 12
        + "</p>"
        for i in range(6)
    ),
    tail="\n".join(
        f"<p id='tail{i}'>Tail {i}. " + "Filler. " * 20 + "</p>" for i in range(30)
    ),
)
# The same page with the held blocks' opening word changed, so the quote landmark cannot
# re-resolve and the restore falls to the section — the only branch that reads the
# wrapper's own box. The word is the same length, so the two versions lay out
# identically and whatever moves is the restore's doing.
KEPT_SECTION_PAGE = BOXLESS_SECTION_PAGE.replace("Held paragraph", "Kept paragraph")
# Where the wrapper's words are, which is the reading its own rect cannot give.
WRAP_TOP = """() => { const r = document.createRange();
  r.selectNodeContents(document.getElementById('wrap'));
  return Math.round(r.getBoundingClientRect().top); }"""
# The ring, read as a computed style: whether it is drawn, how thick, and in what
# colour. The band is the fact under test, so the three are taken together — a stroke
# that matched in width and not in colour would be two rings that look like one.
RING = """(el) => { const s = getComputedStyle(el);
    return [s.outlineStyle, s.outlineWidth, s.outlineColor]; }"""
# One target of ordinary height and one taller than any viewport, both far enough down
# that arriving at either is a real scroll.
TRAVEL_PAGE = leaf_page(
    "travel",
    f"""
<h1 id="h">Placement</h1>
{"".join(f"<p>Fill paragraph {i}, long enough to take a line of its own.</p>" for i in range(10))}
<lf-diagram id="flow"><pre>
graph LR
  Cart --&gt; Pay
</pre></lf-diagram>
{"".join(f"<p>More fill, paragraph {i}.</p>" for i in range(10))}
<section id="long-part">
<h2>The long tail</h2>
{"".join(f"<p>Tail fill, paragraph {i}, deep enough that the section outgrows any viewport.</p>" for i in range(24))}
</section>
""",
)
# One parent over two leaves, so a status report has to move both the marker and
# the parent's computed done-fraction — the state a stylesheet cannot recount.
REPORT_PAGE = leaf_page(
    "reports",
    """
<h1 id="h">The feeders</h1>
<lf-tasks id="plan">
  <lf-task id="t-feeders" status="active" owner="wren"><strong>Rebuild the feeders</strong>
    <lf-task id="t-mounts" status="done"><strong>Replace the mounts</strong></lf-task>
    <lf-task id="t-parser" status="active"><strong>Fit squirrel baffles</strong></lf-task>
  </lf-task>
</lf-tasks>
""",
)
COMMAND_HUB_EXAMPLE = next(
    example for example in EXAMPLES if example.stem == "command-hub"
)
COMMAND_HUB_PAGE = COMMAND_HUB_EXAMPLE.read_text()
# Two workers, one claiming work and one idle, because silence is only news against a
# claim: the elapsed line is about what a row said it was doing, not about the clock.
ROSTER_PAGE = leaf_page(
    "fleet",
    """
<h1 id="h">The aviary crew</h1>
<lf-roster id="crew">
  <lf-agent id="ag-wren" state="working">
    <strong>wren</strong> The feeders.</lf-agent>
  <lf-agent id="ag-finch" state="idle"><strong>finch</strong> Free.</lf-agent>
  <lf-agent id="ag-siskin" state="working"><strong>siskin</strong> Has never reported.</lf-agent>
</lf-roster>
""",
)


def stale_report(page_dir, widget, doing, hours, state="working"):
    """A report the log took `hours` ago. The grace this is written against is a
    quarter of an hour, so nothing that waits can reach it and nothing that sleeps
    should: the fact under test is what the row does with a timestamp, and the log
    is where a timestamp comes from."""
    return events_model.append_event(
        page_dir,
        {
            "kind": "report",
            "author": "claude",
            "agent": "wren",
            "widget": widget,
            "action": "state",
            "detail": {"state": state, "doing": doing},
            "version": 1,
            "ts": (datetime.now().astimezone() - timedelta(hours=hours)).isoformat(
                timespec="seconds"
            ),
        },
    )


def backdate_note(page_dir, version, hours):
    """Age the version's own publish note. The floor under a row's freshness is when
    the version asserting it landed, and a version minted seconds ago cannot exercise
    it — so the log, which is a plain file the writer owns, is rewritten rather than
    waited out."""
    path = page_dir / "comments.jsonl"
    when = (datetime.now().astimezone() - timedelta(hours=hours)).isoformat(
        timespec="seconds"
    )
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line:
            event = json.loads(line)
            if event["kind"] == "note" and event["version"] == version:
                event["ts"] = when
            line = json.dumps(event, ensure_ascii=False)
        out.append(line)
    path.write_text("\n".join(out), encoding="utf-8")


# One instance for every verb the vocabulary declares an action or a report for, so a
# log holding one event apiece leaves the whole of it standing at once. Selection and
# completion share one option-group unit but occupy distinct facets, so both stand;
# accept and reject share the settlement facet, so two suggestions let both competing
# verbs stand. The floor below derives the list from the registry, so a twelfth widget's
# verb fails here rather than passing unexercised.
STANDING_PAGE = leaf_page(
    "standing state",
    """
<h1 id="ab-t">The v1 cutover</h1>
<lf-options id="ab-pick" choose>
  <lf-option id="ab-shim"><strong>Shim the old schema</strong> Fastest to ship.</lf-option>
  <lf-option id="ab-stage"><strong>Migrate in stages</strong> Table by table.</lf-option>
</lf-options>
<lf-options id="ab-scope" choose>
  <lf-option id="ab-all"><strong>Every caller</strong> Nobody is left on v1.</lf-option>
  <lf-option id="ab-ten"><strong>The top ten</strong> The rest follow in August.</lf-option>
</lf-options>
<lf-board id="ab-work">
  <lf-column id="ab-doing" label="Doing"><lf-card id="ab-importer"><strong>Wire the importer</strong></lf-card></lf-column>
  <lf-column id="ab-done" label="Done"><lf-card id="ab-notes"><strong>Draft the notes</strong></lf-card></lf-column>
</lf-board>
<lf-tasks id="ab-plan">
  <lf-task id="ab-baffles" status="active" owner="wren"><strong>Fit the baffles</strong></lf-task>
</lf-tasks>
<lf-roster id="ab-crew">
  <lf-agent id="ab-wren" state="working"><strong>wren</strong> The importer.</lf-agent>
</lf-roster>
<lf-draft id="ab-email"><pre>The words as this version authored them.</pre></lf-draft>
<lf-suggestion id="ab-sug-410">
  <lf-old><p id="ab-404">The retired response is a plain 404.</p></lf-old>
  <lf-new><p>The retired response is a 410 Gone.</p></lf-new>
</lf-suggestion>
<lf-suggestion id="ab-sug-logs">
  <lf-old><p id="ab-roll">Access logs roll off after 30 days.</p></lf-old>
  <lf-new><p>Access logs are kept for 90 days.</p></lf-new>
</lf-suggestion>
""",
)

# The event that leaves each declared verb standing, written out because a detail is
# the verb's own shape and a schema is no help in inventing one.
#
# Two moves into one column, both to its head, because one move cannot say what this
# gate has to get right. `move` folds by card, so each is its own standing entry, and
# an absolute `#place` states one card's index and nothing about its neighbours: the
# column ends up holding the second above the first, and re-applying the first *alone*
# is supposed to lift it back over. Measured that way the gate called lf-board relative
# and refused a page with nothing wrong with it. The set has to be re-applied in the
# log's order, and with a single move on the page it passed either way.
STANDING_ACTIONS = [
    ("ab-pick", "choose", {"options": ["ab-stage"]}),
    ("ab-pick", "answer", {}),
    ("ab-work", "move", {"card": "ab-importer", "to": "ab-done", "index": 0}),
    ("ab-work", "move", {"card": "ab-notes", "to": "ab-done", "index": 0}),
    ("ab-email", "edit", {"text": "The words as the reader rewrote them."}),
    ("ab-sug-410", "accept", {}),
    ("ab-sug-logs", "reject", {}),
]
RELATIVE_WIDGET_PAGE = leaf_page(
    "relative widget",
    """
<h1 id="tally-title">Squirrel baffles</h1>
<lf-tally id="tally-fitted" count="2">
  <pre>Baffles fitted. Counted on the last walk round.</pre>
</lf-tally>
<lf-tally id="tally-seen" count="0">
  <pre>Nothing at the feeders this week.</pre>
</lf-tally>
""",
)

RELATIVE_WIDGET_MODULE = """\
import { once } from "/leaf.js";

customElements.define(
  "lf-tally",
  class extends HTMLElement {
    connectedCallback() {
      once(this);
    }
    applyAction(action, detail) {
      if (action === "step")
        this.setAttribute(
          "count",
          Number(this.getAttribute("count")) + Number(detail.count),
        );
      if (action === "caption") this.querySelector("pre").append(detail.text);
    }
  },
);
"""
# A widget that stands out of place and settles into it, for the two tests below. The
# distance is more than the blocks under it are tall, so while it is out of place its
# words are over a neighbour's — which is a page the gate reports, and the whole of
# what these tests measure. `offset` is the state and the transform is a rendering of
# it, so the module never reads a position back off the page.
DRIFT_PAGE = leaf_page(
    "a page still settling",
    """
<h1 id="drift-title">The feeders</h1>
<lf-drift id="drift-note" offset="120"><strong>Two greys at the north feeder</strong> They came over the fence at a run, took the sunflower hearts from the hanging tray, and were gone again before the camera on the shed had finished waking up.</lf-drift>
<p id="drift-four">They came back at four and stayed until dusk.</p>
<p id="drift-week">The baffles went up the following week.</p>
<p id="drift-seed">Nothing has been at the seed since.</p>
<p id="drift-count">The count runs again on Sunday.</p>
<p id="drift-sunday">Sunday is when the tally goes in.</p>
""",
)

DRIFT_MODULE = """\
import { motion, once } from "/leaf.js";

customElements.define(
  "lf-drift",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      // `deep` renders the same words from inside the widget's own root, and moves
      // them there: an animation a document-level reading cannot see.
      if (this.hasAttribute("deep")) {
        const root = this.attachShadow({ mode: "open" });
        // `bare` stages the words with no element over them — the page refuses that,
        // and the refusal is what one of the tests below reads.
        if (this.hasAttribute("bare")) {
          root.append(...this.childNodes);
          return;
        }
        const held = document.createElement("div");
        held.append(...this.childNodes);
        root.append(held);
        held.animate(
          [{ transform: "translateY(120px)" }, { transform: "none" }],
          { duration: 30000 },
        );
      }
      this.#place();
    }
    // Absolute, as every applyAction is: the offset is stated, never stepped.
    applyAction(action, detail) {
      if (action !== "settle") return;
      const from = this.getAttribute("offset");
      this.setAttribute("offset", String(detail.offset));
      this.#place();
      // Held at the old offset for nine tenths of the run, so the words are over
      // their neighbour's for as long as the motion lasts. A move that eased the
      // whole way would leave a last fifth of a second in which a reading taken
      // then happened to be clean, and the test would be measuring when the gate
      // looked rather than whether it waited.
      motion(
        this,
        [
          { transform: `translateY(${from}px)` },
          { transform: `translateY(${from}px)`, offset: 0.9 },
          { transform: "none" },
        ],
        1200,
      );
    }
    #place() {
      this.style.transform = `translateY(${this.getAttribute("offset")}px)`;
    }
  },
);
"""


def drifting_widget(tmp_path, monkeypatch, deep=False, bare=False):
    """Vendor <lf-drift> as a project widget, and hand back the page it renders."""
    monkeypatch.chdir(tmp_path)
    author_test_widget(tmp_path, "lf-drift", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    entries = json.loads(registry_path.read_text())
    entries["lf-drift"]["properties"]["offset"] = {
        "type": "string",
        "pattern": "^[0-9]+$",
    }
    entries["lf-drift"].setdefault("required", []).append("offset")
    entries["lf-drift"]["x-example"] = entries["lf-drift"]["x-example"].replace(
        'id="drift-example"', 'id="drift-example" offset="120"'
    )
    entries["lf-drift"]["properties"]["deep"] = {"type": "boolean"}
    entries["lf-drift"]["properties"]["bare"] = {"type": "boolean"}
    deep = deep or bare
    if deep:
        # The body is rendered from the widget's own root, so the entry stops
        # claiming the reader gets it verbatim from the markup.
        entries["lf-drift"]["x-shadow"] = True
        del entries["lf-drift"]["x-verbatim"]
    # The registry holds a widget-unit verb to the attribute a version retracts a
    # decision with, so a state channel arrives with its way out of one.
    entries["lf-drift"]["properties"]["restated"] = {"type": "boolean"}
    entries["lf-drift"]["x-state"] = {
        "settle": {
            "detail": {
                "type": "object",
                "properties": {"offset": {"type": "string", "pattern": "^[0-9]+$"}},
                "required": ["offset"],
                "additionalProperties": False,
            },
            "facet": "offset",
            "unit": "widget",
            "record": {"kind": "value", "attr": "offset", "value": "offset"},
        }
    }
    registry_path.write_text(json.dumps(entries, indent=2))
    (tmp_path / ".leaf" / "widgets" / "lf-drift.js").write_text(DRIFT_MODULE)
    if not deep:
        return DRIFT_PAGE
    opens = "<lf-drift deep bare id=" if bare else "<lf-drift deep id="
    return DRIFT_PAGE.replace("<lf-drift id=", opens)


# A suggestion whose losing slot holds a widget. lf-old takes prose, and prose takes
# widgets, so the mark on a chosen option can sit inside the half a decision removes.
# `choose`, because that is the shape that bites: a group offering a pick renders the
# mark as a press, which wears the chrome class *and* declares its word the page's.
RETIRED_WIDGET_PAGE = leaf_page(
    "retired",
    """
<h1 id="h">Session transport</h1>
<p id="lede">Replacing the whole decision block below.</p>
<lf-suggestion id="sug-swap">
  <lf-old id="was">
    <lf-options id="old-group" choose>
      <lf-option id="old-lax" chosen><strong>Lax cookie</strong> The way it stands.</lf-option>
    </lf-options>
  </lf-old>
  <lf-new id="now"><p id="p-now">A bearer header, settled elsewhere.</p></lf-new>
</lf-suggestion>
""",
)


TWO_HOLDER_PAGE = leaf_page(
    "two holders",
    """
<h1 id="th-t">The cache trial</h1>
<lf-trial id="th-cache">
  <lf-current><p id="th-now">The cache is warmed on every deploy.</p></lf-current>
  <lf-proposed><p id="th-next">The cache is warmed on the first request.</p></lf-proposed>
</lf-trial>
""",
)


def trial_family(tmp_path):
    """A third-party settlement family in one project package.

    Registry declarations relate its holders and slots. The holder modules only define
    their elements, so anything a test sees settle is the layer's doing. Only
    lf-proposed names two holders, for the selector case that test exercises.
    """
    for tag, upgrade in (
        ("lf-trial", True),
        ("lf-pilot", True),
        ("lf-current", False),
        ("lf-proposed", False),
    ):
        author_test_widget(tmp_path, tag, upgrade=upgrade)
    source = tmp_path / ".leaf" / "registry.json"
    entries = json.loads(source.read_text())
    verb = {
        "detail": {"type": "object", "additionalProperties": False},
        "facet": "settlement",
        "unit": "widget",
    }
    example = {
        "lf-trial": '<lf-trial id="x-trial"><lf-current><p>As it stands.</p></lf-current>'
        "<lf-proposed><p>As proposed.</p></lf-proposed></lf-trial>",
        "lf-pilot": '<lf-pilot id="x-pilot"><lf-proposed><p>As proposed.</p>'
        "</lf-proposed></lf-pilot>",
    }
    # `pause` settles nothing: the widget-unit verb that displaces a decision in
    # the fold, there for the test that holds the mark to following it out.
    for tag, state in (
        ("lf-trial", ("adopt", "shelve", "pause")),
        ("lf-pilot", ("run", "shelve")),
    ):
        entries[tag]["x-state"] = {name: dict(verb) for name in state}
        entries[tag]["properties"]["restated"] = {"type": "boolean"}
        entries[tag]["x-content"] = "items"
        entries[tag]["x-example"] = example[tag]
    for tag, holders, outcome in (
        ("lf-current", ["lf-trial"], "adopt"),
        ("lf-proposed", ["lf-trial", "lf-pilot"], "shelve"),
    ):
        entries[tag] |= {"x-parent": holders, "x-retired-when": outcome}
        entries[tag].pop("x-example", None)
        entries[tag].pop("required", None)
    source.write_text(json.dumps(entries))
    # The fixture styles every tag as a card; a slot is a slot, the way the shipped
    # family's lf-old/lf-new draw no box of their own. Left as cards, the slots carry
    # margins that stand trapped under the holder's frame once a settled sibling is
    # hidden — a real TRAPPED_MARGINS finding about the fixture, not about the gate.
    theme = tmp_path / ".leaf" / "theme.css"
    theme.write_text(
        theme.read_text() + "\nlf-current, lf-proposed "
        "{ display: block; margin: 0; padding: 0; border: none; --lf-frame: initial; }\n"
    )


# The two-holder page with a second, undecided trial beside the first: the instance a
# module that invents settlement gets caught on, since on the decided one its mark
# only repeats the log.
TWO_HOLDER_SPARE_PAGE = TWO_HOLDER_PAGE.replace(
    "</main>",
    """<lf-trial id="th-spare">
  <lf-current><p id="sp-now">The spare stands as it is.</p></lf-current>
  <lf-proposed><p id="sp-next">The spare would move.</p></lf-proposed>
</lf-trial>
</main>""",
)
MARKDOWN_REPLY = """Two things, then the fix — details in https://example.com/notes:

- the poll drops a response **behind** the one already rendered
- `lastEventSeq` is what it compares, a Vec<T> of them

```python
def resolve(a, b):
    return a if a.seq > b.seq else b
```

> which one wins?
"""
REF_PAGE = leaf_page(
    "refs",
    f"""
<h1 id="h">Feeder placement</h1>
{"".join(f"<p>Fill paragraph {i}, long enough to take a line of its own.</p>" for i in range(10))}
<lf-tabs id="projects">
  <lf-tab id="tab-feeders" label="Winter feeders">
    <p id="p-feeders">Two of the four feeders are mounted.</p>
  </lf-tab>
  <lf-tab id="tab-bath" label="Heated bird bath">
    <p id="p-bath">The thermostat arrived cracked and a replacement is on order.</p>
  </lf-tab>
</lf-tabs>
<section id="tail">
{"".join(f"<p>Tail fill, paragraph {i}, long enough to stand as a landmark of its own.</p>" for i in range(16))}
<p id="tail-end">The last words on the page, where a reader who read to the end is.</p>
</section>
""",
)
THREAD_ASKS = [
    {
        "kind": "comment",
        "id": "c-which",
        "author": "claude",
        "version": 1,
        "text": "Which store?",
        "markup": '<lf-options id="tq-one" choose>'
        '<lf-option id="tq-redis">Redis</lf-option>'
        '<lf-option id="tq-cookie">Signed cookie</lf-option>'
        "</lf-options>",
    },
    {
        "kind": "comment",
        "id": "c-any",
        "author": "claude",
        "version": 1,
        "text": "Pick any that apply.",
        "markup": '<lf-options id="tq-set" choose multiple>'
        '<lf-option id="tq-logs">Logs</lf-option>'
        '<lf-option id="tq-metrics">Metrics</lf-option>'
        "</lf-options>",
    },
]
