"""Compatibility facade for browser integration support.

The harness owns server and browser mechanics. Case libraries own authored pages,
runtime probes, and domain-specific readings. Existing tests import this facade so a
fixture can move between those owners without making test modules coordinate it.
"""

from render_cases_interaction import (
    ASK_PAGE,
    ASK_ROW_SAYS,
    ASK_WITH_CONTEXT_PAGE,
    ASKED_PAGE,
    ASKS_IN_ORDER,
    ASKS_PAGE,
    BOXLESS_SECTION_PAGE,
    CHANGE_SHAPES_PAGE,
    CHIP_PAGE,
    COLLAPSED_PAGE,
    COMMAND_HUB_PAGE,
    CONVERSATION_DIFF_PAGE,
    DRIFT_MODULE,
    DRIFT_PAGE,
    EXHIBIT_EXTENT,
    FRAME_BY_FRAME,
    HOLD_MOTION,
    INLINE_CASE_PAGE,
    KEPT_SECTION_PAGE,
    LIST_RUNS,
    LIST_STATE,
    LIVE_READING,
    LIVE_V1,
    LIVE_V2,
    LIVE_V3,
    MARKDOWN_REPLY,
    MESSAGE_ROOM_PAGE,
    NESTED_ASK_PAGE,
    PAINTED_PAGE,
    PANEL_PAGE,
    PROPOSED_PAGE,
    REBUILT_INLINE_PAGE,
    REF_PAGE,
    RELATIVE_WIDGET_MODULE,
    RELATIVE_WIDGET_PAGE,
    REPORT_PAGE,
    RETIRED_WIDGET_PAGE,
    RING,
    ROOM_HELD,
    ROOM_WIDGETS,
    ROOMS,
    ROSTER_PAGE,
    SCROLL_SETTLED,
    SETTLED_ASK_PAGE,
    SHORT_SUGGESTION,
    SPECIMEN_EXAMPLES,
    STACKED_OPTIONS_PAGE,
    STANDING_ACTIONS,
    STANDING_ASK,
    STANDING_PAGE,
    SUGGESTION_PAGE,
    SWAP_PAGE,
    TABLE_REPLY,
    THREAD_ASKS,
    TRAVEL_PAGE,
    TWO_HOLDER_PAGE,
    TWO_HOLDER_SPARE_PAGE,
    WRAP_TOP,
    backdate_note,
    drifting_widget,
    live_url,
    panel_comment,
    sent_events,
    stale_report,
    trial_family,
)
from render_cases_layout import (
    AIM_CURSOR,
    AIM_PAINT_PAGE,
    AIM_POINT,
    AIMED,
    ARRANGE,
    ARRANGEMENTS,
    BADGE_CHROME,
    BANNER_WATCH,
    COLORED_CODE_PAGE,
    CORNER_PAGE,
    CUSTOM_WIDGET_PAGE,
    DEFINE_BOXES,
    DRAFT_MARK,
    EDGE_IDS,
    EDGES,
    FAINT_CODE_PAGE,
    FLAT_SHADOW_PAGE,
    FLOATING_PAGE,
    FOCUS_IN_PAGE,
    LEGEND_TRUE,
    MANY_ASKS_PAGE,
    MARK_NEAR,
    MARK_PAD,
    NAMED,
    NEIGHBOUR,
    NEIGHBOURHOOD,
    NOTE_BESIDE_A_CHANGE,
    ON_SCREEN,
    OUT_OF_REACH_PAGE,
    OVER_ITS_CONTAINER,
    PAGE_MARKUP,
    PAINTED_IN_SILENCE_PAGE,
    PANEL_DIFF_MARKUP,
    PRESS,
    PRINT_LOSS_PAGE,
    RENDERED,
    RESIZE_LOOP_EVENT,
    ROOM_EVERY_FRAME,
    SCROLL_SETTLE_MS,
    SCROLL_STILL,
    SCROLLED_CONTAINER,
    SHADOW_CODE_PAGE,
    SHADOW_HOST_PAGE,
    SHADOWED_DIFF,
    SHORT_CHIP_PAGE,
    SHOT_PAGE,
    SHOT_SRC,
    SHOTS,
    SIDENOTE_IN_A_WIDGET,
    SPILLING_PAGE,
    TINTED_LINE_PAGE,
    UNANSWERED_CODE_PAGE,
    UNBREAKABLE_PAGE,
    UNMARKABLE_PAGE,
    UNPARSABLE_DIAGRAM,
    WIDE_DIFF_PAGE,
    WIDE_TABLE_PAGE,
    aim_targets,
    arrival_findings,
    displaced,
    draw_edge,
    edge_settled,
    flip_point,
    geometry,
    in_threads_scrollport,
    live_leaf,
    mark_edges,
    motions,
    moved_at,
    other_leaf,
    page_at_rest,
    resize_notice_after_last_probe,
    serious_axe_violations,
    shown_frames,
    solid_png,
    token_colour,
)
from render_cases_navigation import (
    _CARD,
    ADDRESS_PAGE,
    ADDRESSED_PAGE,
    ASTRAL_PAGE,
    CEILING_PAGE,
    CHIPS,
    CLIPPED_BY,
    CODE_PAGE,
    CONTROL_LABEL_PAGE,
    CROWDED_PAGE,
    DATA_PROJECTION_MODULE,
    DATA_PROJECTION_PAGE,
    DIFF_PAGE,
    DISCLOSED_PAGE,
    DRAFT_EDITED,
    DRAFT_TEXT,
    DRIFT_V1,
    DRIFT_V2,
    EDGE_PAGE,
    FENCED_CAPTURE_PAGE,
    FIRST_PRESENTATION,
    FOOTED_PAGE,
    HOVERED,
    INSIDE_ITS_OPTION,
    JOURNEY_SCAFFOLD,
    JOURNEY_V1,
    JOURNEY_V2,
    KEYS_PAGE,
    LONG_PASSAGE,
    MARKERS,
    MOVED_WORDS_PAGE,
    NATIVE_CONTROL_PAGE,
    NESTED_SUGGESTION,
    NOTED_PAGE,
    OVER_WORDS,
    PAD,
    PASSAGE,
    SENTENCE,
    SMOOTH_LONG_PAGE,
    SPENT,
    STANDING,
    STANDS_BACK,
    SUGGEST_BLOCK,
    TAB_AND_DOT,
    TAB_TONE,
    TAIL_PAGE,
    TARGETS_PAGE,
    THIN_V1,
    THIN_V2,
    TWICE_PAGE,
    TWO_COPIES_PAGE,
    UNDO_PAGE,
    _card_done,
    _draft_says,
    _publish,
    actions,
    card_body,
    compose,
    composer_quote,
    data_projection_page,
    live_watcher,
    mark_point,
    mark_shows_beside_composer,
    one_reader,
    painted,
    pending_text,
    standing_mark,
    wait_hovered,
    wait_standing,
)
from render_cases_widgets import (
    AT_THE_HANDOVER,
    BROKEN_DIAGRAM_PAGE,
    CHROME_ROOM,
    DIAGRAM_AND_RAIL_PAGE,
    DIAGRAM_ROOM,
    DRAWING_PLACEMENT,
    DRAWN_PAST_A_RAIL_PAGE,
    FRAMED_SCROLLER_PAGE,
    FRAMED_WIDE_PAGE,
    INLINE_REPLY_MARKUP,
    LATE_MARGIN_PAGE,
    LATE_MARGIN_WIDGET,
    NOTE_AND_WIDE_PAGE,
    NOTE_BAND,
    OWN_MARGIN_FURNITURE,
    PICTURE_PAGE,
    RAIL_AND_WIDE_PAGE,
    RAIL_BAND_PAGE,
    RAIL_BANDS,
    RAIL_FIT,
    ROOM_GEOMETRY,
    SCROLLED,
    TWIN_V1,
    TWIN_V2,
    WHERE_I_STAND_PAGE,
    WIDE_AND_NARROW_PAGE,
    WIDE_DIAGRAM_PAGE,
    _painted_line,
    written_anchors,
)
from render_harness import (
    BOARD_PAGE,
    BOTH_STAMPS,
    CARRIED_PAGE,
    COMMAND_HUB_PACKAGE,
    EXAMPLE_MEDIA,
    EXAMPLE_PACKAGES,
    EXAMPLES,
    IMPORTER_CARD,
    INLINE_PAGE,
    LONG_PAGE,
    REPLAYED_PAGE,
    REPLY_HOST_PAGE,
    ROOT,
    SAID_PAGE,
    SETTLED_PAGE,
    SPECIMEN_MARKUP,
    SPECIMEN_PAGE,
    SPECIMEN_TEXT,
    STORED_DRAFT_SETTLED,
    STORED_DRAFT_TEXT,
    TOKEN,
    CutOff,
    Traffic,
    _traffic,
    _until,
    author_test_widget,
    compare_with,
    held_stale,
    key_line,
    leaf_page,
    link_example_packages,
    navigate,
    open_page,
    page_registry,
    panel_settled,
    post_event,
    primed,
    record_claim,
    refuse,
    resized,
    round_trip,
    select,
    serve,
    told,
    undo,
    watched,
)

__all__ = (
    "ADDRESSED_PAGE",
    "ADDRESS_PAGE",
    "AIMED",
    "AIM_CURSOR",
    "AIM_PAINT_PAGE",
    "AIM_POINT",
    "ARRANGE",
    "ARRANGEMENTS",
    "ASKED_PAGE",
    "ASKS_IN_ORDER",
    "ASKS_PAGE",
    "ASK_PAGE",
    "ASK_ROW_SAYS",
    "ASK_WITH_CONTEXT_PAGE",
    "ASTRAL_PAGE",
    "AT_THE_HANDOVER",
    "BADGE_CHROME",
    "BANNER_WATCH",
    "BOARD_PAGE",
    "BOTH_STAMPS",
    "BOXLESS_SECTION_PAGE",
    "BROKEN_DIAGRAM_PAGE",
    "CARRIED_PAGE",
    "CEILING_PAGE",
    "CHANGE_SHAPES_PAGE",
    "CHIPS",
    "CHIP_PAGE",
    "CHROME_ROOM",
    "CLIPPED_BY",
    "CODE_PAGE",
    "COLLAPSED_PAGE",
    "COLORED_CODE_PAGE",
    "COMMAND_HUB_PACKAGE",
    "COMMAND_HUB_PAGE",
    "CONTROL_LABEL_PAGE",
    "CONVERSATION_DIFF_PAGE",
    "CORNER_PAGE",
    "CROWDED_PAGE",
    "CUSTOM_WIDGET_PAGE",
    "DATA_PROJECTION_MODULE",
    "DATA_PROJECTION_PAGE",
    "DEFINE_BOXES",
    "DIAGRAM_AND_RAIL_PAGE",
    "DIAGRAM_ROOM",
    "DIFF_PAGE",
    "DISCLOSED_PAGE",
    "DRAFT_EDITED",
    "DRAFT_MARK",
    "DRAFT_TEXT",
    "DRAWING_PLACEMENT",
    "DRAWN_PAST_A_RAIL_PAGE",
    "DRIFT_MODULE",
    "DRIFT_PAGE",
    "DRIFT_V1",
    "DRIFT_V2",
    "EDGES",
    "EDGE_IDS",
    "EDGE_PAGE",
    "EXAMPLES",
    "EXAMPLE_MEDIA",
    "EXAMPLE_PACKAGES",
    "EXHIBIT_EXTENT",
    "FAINT_CODE_PAGE",
    "FENCED_CAPTURE_PAGE",
    "FIRST_PRESENTATION",
    "FLAT_SHADOW_PAGE",
    "FLOATING_PAGE",
    "FOCUS_IN_PAGE",
    "FOOTED_PAGE",
    "FRAMED_SCROLLER_PAGE",
    "FRAMED_WIDE_PAGE",
    "FRAME_BY_FRAME",
    "HOLD_MOTION",
    "HOVERED",
    "IMPORTER_CARD",
    "INLINE_CASE_PAGE",
    "INLINE_PAGE",
    "INLINE_REPLY_MARKUP",
    "INSIDE_ITS_OPTION",
    "JOURNEY_SCAFFOLD",
    "JOURNEY_V1",
    "JOURNEY_V2",
    "KEPT_SECTION_PAGE",
    "KEYS_PAGE",
    "LATE_MARGIN_PAGE",
    "LATE_MARGIN_WIDGET",
    "LEGEND_TRUE",
    "LIST_RUNS",
    "LIST_STATE",
    "LIVE_READING",
    "LIVE_V1",
    "LIVE_V2",
    "LIVE_V3",
    "LONG_PAGE",
    "LONG_PASSAGE",
    "MANY_ASKS_PAGE",
    "MARKDOWN_REPLY",
    "MARKERS",
    "MARK_NEAR",
    "MARK_PAD",
    "MESSAGE_ROOM_PAGE",
    "MOVED_WORDS_PAGE",
    "NAMED",
    "NATIVE_CONTROL_PAGE",
    "NEIGHBOUR",
    "NEIGHBOURHOOD",
    "NESTED_ASK_PAGE",
    "NESTED_SUGGESTION",
    "NOTED_PAGE",
    "NOTE_AND_WIDE_PAGE",
    "NOTE_BAND",
    "NOTE_BESIDE_A_CHANGE",
    "ON_SCREEN",
    "OUT_OF_REACH_PAGE",
    "OVER_ITS_CONTAINER",
    "OVER_WORDS",
    "OWN_MARGIN_FURNITURE",
    "PAD",
    "PAGE_MARKUP",
    "PAINTED_IN_SILENCE_PAGE",
    "PAINTED_PAGE",
    "PANEL_DIFF_MARKUP",
    "PANEL_PAGE",
    "PASSAGE",
    "PICTURE_PAGE",
    "PRESS",
    "PRINT_LOSS_PAGE",
    "PROPOSED_PAGE",
    "RAIL_AND_WIDE_PAGE",
    "RAIL_BANDS",
    "RAIL_BAND_PAGE",
    "RAIL_FIT",
    "REBUILT_INLINE_PAGE",
    "REF_PAGE",
    "RELATIVE_WIDGET_MODULE",
    "RELATIVE_WIDGET_PAGE",
    "RENDERED",
    "REPLAYED_PAGE",
    "REPLY_HOST_PAGE",
    "REPORT_PAGE",
    "RESIZE_LOOP_EVENT",
    "RETIRED_WIDGET_PAGE",
    "RING",
    "ROOMS",
    "ROOM_EVERY_FRAME",
    "ROOM_GEOMETRY",
    "ROOM_HELD",
    "ROOM_WIDGETS",
    "ROOT",
    "ROSTER_PAGE",
    "SAID_PAGE",
    "SCROLLED",
    "SCROLLED_CONTAINER",
    "SCROLL_SETTLED",
    "SCROLL_SETTLE_MS",
    "SCROLL_STILL",
    "SENTENCE",
    "SETTLED_ASK_PAGE",
    "SETTLED_PAGE",
    "SHADOWED_DIFF",
    "SHADOW_CODE_PAGE",
    "SHADOW_HOST_PAGE",
    "SHORT_CHIP_PAGE",
    "SHORT_SUGGESTION",
    "SHOTS",
    "SHOT_PAGE",
    "SHOT_SRC",
    "SIDENOTE_IN_A_WIDGET",
    "SMOOTH_LONG_PAGE",
    "SPECIMEN_EXAMPLES",
    "SPECIMEN_MARKUP",
    "SPECIMEN_PAGE",
    "SPECIMEN_TEXT",
    "SPENT",
    "SPILLING_PAGE",
    "STACKED_OPTIONS_PAGE",
    "STANDING",
    "STANDING_ACTIONS",
    "STANDING_ASK",
    "STANDING_PAGE",
    "STANDS_BACK",
    "STORED_DRAFT_SETTLED",
    "STORED_DRAFT_TEXT",
    "SUGGESTION_PAGE",
    "SUGGEST_BLOCK",
    "SWAP_PAGE",
    "TABLE_REPLY",
    "TAB_AND_DOT",
    "TAB_TONE",
    "TAIL_PAGE",
    "TARGETS_PAGE",
    "THIN_V1",
    "THIN_V2",
    "THREAD_ASKS",
    "TINTED_LINE_PAGE",
    "TOKEN",
    "TRAVEL_PAGE",
    "TWICE_PAGE",
    "TWIN_V1",
    "TWIN_V2",
    "TWO_COPIES_PAGE",
    "TWO_HOLDER_PAGE",
    "TWO_HOLDER_SPARE_PAGE",
    "UNANSWERED_CODE_PAGE",
    "UNBREAKABLE_PAGE",
    "UNDO_PAGE",
    "UNMARKABLE_PAGE",
    "UNPARSABLE_DIAGRAM",
    "WHERE_I_STAND_PAGE",
    "WIDE_AND_NARROW_PAGE",
    "WIDE_DIAGRAM_PAGE",
    "WIDE_DIFF_PAGE",
    "WIDE_TABLE_PAGE",
    "WRAP_TOP",
    "_CARD",
    "CutOff",
    "Traffic",
    "_card_done",
    "_draft_says",
    "_painted_line",
    "_publish",
    "_traffic",
    "_until",
    "actions",
    "aim_targets",
    "arrival_findings",
    "author_test_widget",
    "backdate_note",
    "card_body",
    "compare_with",
    "compose",
    "composer_quote",
    "data_projection_page",
    "displaced",
    "draw_edge",
    "drifting_widget",
    "edge_settled",
    "flip_point",
    "geometry",
    "held_stale",
    "in_threads_scrollport",
    "key_line",
    "leaf_page",
    "link_example_packages",
    "live_leaf",
    "live_url",
    "live_watcher",
    "mark_edges",
    "mark_point",
    "mark_shows_beside_composer",
    "motions",
    "moved_at",
    "navigate",
    "one_reader",
    "open_page",
    "other_leaf",
    "page_at_rest",
    "page_registry",
    "painted",
    "panel_comment",
    "panel_settled",
    "pending_text",
    "post_event",
    "primed",
    "record_claim",
    "refuse",
    "resize_notice_after_last_probe",
    "resized",
    "round_trip",
    "select",
    "sent_events",
    "serious_axe_violations",
    "serve",
    "shown_frames",
    "solid_png",
    "stale_report",
    "standing_mark",
    "token_colour",
    "told",
    "trial_family",
    "undo",
    "wait_hovered",
    "wait_standing",
    "watched",
    "written_anchors",
)


DEEP_FOCUS = """() => {
  let e = document.activeElement;
  while (e?.shadowRoot?.activeElement) e = e.shadowRoot.activeElement;
  return e;
}"""


RING_FAULTS = f"""async () => {{
  // shownBand, rather than a fourth reading of what a box clips to. Its own comment
  // carries why: version check --render imports it so the band a handover is refused
  // against and the band the page paints to are one reading, and written twice they
  // disagreed twice. This was the third copy and it was wrong in both of the ways that
  // comment names — it asked only about overflow, so paint containment and
  // content-visibility clipped a ring away with nothing said, and it measured the
  // padding box with the scrollbar's gutter still in it.
  const {{ shownBand }} = await import('/leaf.js');
  const el = ({DEEP_FOCUS})();
  if (!el || el === document.body || el === document.documentElement) return null;
  const holds = (a, b) => {{
    for (let n = b; n; n = n.parentNode || n.host) if (n === a) return true;
    return false;
  }};
  const named = {NAMED};
  // Straight off the computed style, which holds because no ring in this layer moves.
  // A ring on its way somewhere reads as wherever it has got to — mid-transition the
  // platform reports the animated value, which early on is the value the property is
  // leaving — and this once read every ring that way, because the theme's reduced-motion
  // guard shortened transitions rather than removing them and `transition-property` is
  // `all`, so a ring arriving was a ring in transit for two frames on every page. That
  // is fixed where it was made (theme.css). A layer that deliberately animates a ring
  // owes this reading a wait on `getAnimations()`; one written here now would wait on
  // nothing, in front of the reading it is meant to protect.
  const cs = getComputedStyle(el);
  const w = cs.outlineStyle === 'none' ? 0 : parseFloat(cs.outlineWidth) || 0;
  if (!w) return {{ who: named(el), ring: false, cuts: [], covers: [] }};
  const grow = w + (parseFloat(cs.outlineOffset) || 0);
  const b = el.getBoundingClientRect();
  const ring = {{ top: b.top - grow, left: b.left - grow,
                 bottom: b.bottom + grow, right: b.right + grow }};
  const cuts = [];
  let scrolled = false;
  const above = (n) => n.parentElement || n.getRootNode().host || null;
  // One side, one message, named for the innermost box that took it. A scroll region's
  // edge is often the window's to the pixel — .lf-threads' right edge is .lf-panel's is
  // innerWidth — and one ring reported twice reads as two defects. The innermost box is
  // the more useful of the two answers anyway: it is the box the control lives in.
  const taken = {{}};
  const took = (band, who) => {{
    const room = {{ w: band.right - band.left, h: band.bottom - band.top }};
    // Only the sides that could have been shown whole. A code block taller than the
    // window hangs out of it however the browser scrolls, and saying so on every one
    // would be noise standing where the findings are — so the claim is the one that can
    // be met: a ring that fits in the box is a ring the box has to show all of.
    const fits = {{
      top: b.bottom - b.top <= room.h,
      bottom: b.bottom - b.top <= room.h,
      left: b.right - b.left <= room.w,
      right: b.right - b.left <= room.w,
    }};
    for (const [side, by] of Object.entries({{
      top: band.top - ring.top,
      left: band.left - ring.left,
      bottom: ring.bottom - band.bottom,
      right: ring.right - band.right,
    }}))
      if (!taken[side] && by > 0.5 && fits[side])
        taken[side] =
          `its ${{side}} edge is ${{Math.round(by * 10) / 10}}px outside ` + who;
  }};
  // `clipped` in anchors.js is this walk, and this is its shape: from the box itself
  // rather than its parent, skipping the box's own band because an element is not clipped
  // by its own overflow, and stopping at the first fixed box. Its comment records what
  // starting at the parent cost — "the question of every ancestor of a fixed box and
  // never of the box" — which is the bug this reading had too.
  for (let a = el; a; a = above(a)) {{
    if (a !== el) {{
      if (a.scrollHeight > a.clientHeight) scrolled = true;
      const band = shownBand(a);
      if (band) took(band, named(a));
    }}
    if (getComputedStyle(a).position === 'fixed') break;
  }}
  // The window last, so an inner box that shares an edge with it is the one named, and
  // unconditionally, because the walk above may have stopped at a fixed box and every
  // box stops somewhere. It is the outermost clip there is: a fixed subtree is laid out
  // against it, and everything else reaches it through body, which is this page's
  // scroller. Not a claim that nothing else could clip a fixed box — a containing block
  // established by transform, filter or containment is a real case, and .lf-banner's
  // backdrop-filter is one such generator — but the walk covers that case now by asking
  // every box on the way up instead of branching on the focused one's own position.
  took({{ top: 0, left: 0, bottom: innerHeight, right: innerWidth }}, 'the window');
  for (const side of ['top', 'left', 'bottom', 'right'])
    if (taken[side]) cuts.push(taken[side]);
  const paints = (n) => {{
    const s = getComputedStyle(n);
    return s.backgroundImage !== 'none'
      || !/^(transparent$|rgba\\(.*,\\s*0\\))/.test(s.backgroundColor);
  }};
  const mid = (a, b) => (a + b) / 2;
  const covers = [];
  // Whether this reading has an order to read at all. It works by hit-testing the ring's
  // own pixels and taking whatever comes back as standing over them — but an outline is
  // painted by its control, at its control's level, and an outline's pixels are not
  // hit-testable. A pixel of ring outside the control's box therefore returns whatever
  // is beneath, and beneath is where the answer would have to come from.
  //
  // That is sound while the control's own surface takes hits, because then the ring's
  // sample either lands on the control's line or lands somewhere the line does not
  // reach. It stops being sound inside a surface declaring `pointer-events: none`: the
  // key line stands over the page at z-index 8940 and takes no hits, so its More button
  // is topmost where it lives and every line of code under the ring's top run read as
  // standing over it. `cuts` is geometry and still answers for these; this half says
  // nothing rather than saying the opposite of what the page shows.
  let ordered = true;
  for (let a = el; a; a = above(a))
    if (getComputedStyle(a).pointerEvents === 'none') {{ ordered = false; break; }}
  for (const [side, x, y] of ordered ? [
    ['top', mid(ring.left, ring.right), ring.top + 0.5],
    ['bottom', mid(ring.left, ring.right), ring.bottom - 0.5],
    ['left', ring.left + 0.5, mid(ring.top, ring.bottom)],
    ['right', ring.right - 0.5, mid(ring.top, ring.bottom)],
  ] : []) {{
    if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
    for (const over of document.elementsFromPoint(x, y)) {{
      if (over === el || holds(el, over) || holds(over, el)) break;
      if (!paints(over)) continue;
      // Is the control itself under this too? Where a control stands partly behind
      // something, the ring's run on that side is behind whatever the control is behind,
      // which is a fact about where the control was put rather than about the ring being
      // drawn outside its box. The claim worth making is the other one: where the control
      // can be seen, so can the ring that names it. Stated without a case on purpose —
      // the one this was written for was the tray's edge handle running the whole height
      // of the window under the banner, which stopped being true in 3a8f16f0, the commit
      // that added this comment and the handle's top inset together.
      //
      // The step in has to clear the ring's own band, and `grow + w` from the ring's edge
      // is what lands `w + 1` inside the box whichever side of it the ring is drawn on.
      // Written as `grow + 1` it cleared an outward ring, where grow is already at least
      // w, and landed inside an inset one, where grow is nought: every covered inset ring
      // answered that the control was behind the same thing and was dropped without a
      // word. The rings the panel's own list draws are all inset, so this went blind in
      // the same commit that made them so — a thread lying two pixels under its stuck run
      // heading is a card with three sides, and the gate written to catch exactly that
      // reported nothing.
      const step = grow + w + 1;
      const inx = x + (side === 'left' ? step : side === 'right' ? -step : 0);
      const iny = y + (side === 'top' ? step : side === 'bottom' ? -step : 0);
      if (document.elementsFromPoint(inx, iny).includes(over)) break;
      const o = over.getBoundingClientRect();
      const at = (r) => [r.left, r.top, r.right, r.bottom].map(Math.round).join();
      covers.push(`its ${{side}} edge is under ` + named(over)
                  + ` (ring ${{at(ring)}} vs ${{at(o)}}, sampled ${{Math.round(x)}},`
                  + `${{Math.round(y)}})`);
      break;
    }}
  }}
  return {{ who: named(el), ring: true, scrolled, cuts, covers }};
}}"""


COVERED_TOP = """() => {
  const el = document.activeElement;
  const box = document.querySelector('.lf-threads');
  if (!el || !box.contains(el)) return null;
  const r = el.getBoundingClientRect();
  const over = document.elementsFromPoint((r.left + r.right) / 2, r.top + 1)
    .find((n) => n !== el && !el.contains(n) && !n.contains(el)
                 && n.classList.contains('lf-pinned'));
  if (!over) return null;
  const o = over.getBoundingClientRect();
  return `${over.textContent.trim().slice(0, 32)} covers it down to `
         + `${Math.round(o.bottom - r.top)}px in`;
}"""


def ring_fault(page, where):
    """The complaint about where the keyboard is standing, or None if it is clean."""
    seen = page.evaluate(RING_FAULTS)
    if not seen or not seen["ring"] or not (seen["cuts"] or seen["covers"]):
        return None
    return f"{where}, the ring on {seen['who']} is not all there: " + "; ".join(
        seen["cuts"] + seen["covers"]
    )
