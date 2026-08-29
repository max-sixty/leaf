import { shownBox, shownParts } from "/runtime/widget-api.js";

// A widget that upgraded into no room to be read in. The floor is two numbers, and
// which of them a widget is held to is the widget's to declare (x-inline), because
// the two kinds are laid out by different rules: one reserves a region and the other
// is set among the words around it, where the box is the words and there is no width
// it was supposed to reach. Held to the region's floor, an inline widget fails for
// being short — a chip reading a price is 31px wide and correct, and the gate reported
// the author's own words as a collapse. The height floor is both kinds': a line of
// words is a line tall wherever it is laid out, which leaves a flattened chip caught.
//
// Declared, not read off the computed display, because a custom element with no rule
// left standing computes as inline: a theme that lost the chip block would silence the
// check that exists to catch it.
//
// [hidden] needs its own exclusion: hidden="until-found" (what a closed tab wears)
// resolves to content-visibility, which checkVisibility reports as visible while the
// box measures zero. That collapse is the point of a closed tab; the collapse being
// hunted here is the one nothing asked for.
// A control drawn where no reader can reach it. `TINY_BOXES` asks whether a widget got a
// box at all; this asks the question one level down, of the chrome inside it, and the
// difference is which failure each catches: a widget with no box is a widget that didn't
// render, and a control with a box its own container clips away is a widget that rendered
// and then hid its offer behind the frame it drew.
//
// It is the failure with no witness. Nothing overflows the page, so the sideways-scroll
// check is quiet; nothing is past the column, so that gate is quiet; the words are in a
// text node and technically selectable, so the unreachable-words gate is quiet. What the
// reader gets is a question with no visible way to answer it — which is exactly what
// shipped: a `choose` group in its row form states `width: 100%` on options that a
// live-page rule gives a 30px keyboard-address rail, and under the default box-sizing
// those are the row's width *plus* its padding, so every row ran 28px wider than the
// group whose `overflow: hidden` keeps its cells' hairlines square. The last cell is the
// pick mark, so all of it went over the edge: every row-form decision on every live page
// drew no dot, no "chosen", nothing. Paper and an exported copy were right throughout,
// the rail being live-pages-only, so no medium outside a browser could see it.
//
// Only where the clip cannot be scrolled away. A board's columns run past the board and
// are reached by scrolling, which is the arrangement rather than a fault, so an ancestor
// with something to scroll answers for what it holds. And only for controls the page
// offers (data-lf-offer), which keeps it clear of everything deliberately clipped to
// nothing — the paint pass's quiet words, the line counting a block's comments — whose
// whole point is to be read and not seen.
export function clippedControls() {
  const out = [];
  for (const el of document.querySelectorAll("[data-lf-offer]")) {
    // checkOpacity too: a control faded to nothing is as unreachable as one clipped
    // away, and reporting it against a box it is inside would name the wrong fault.
    if (!el.checkVisibility({ checkOpacity: true }) || el.closest("[hidden]")) continue;
    const b = el.getBoundingClientRect();
    if (b.width < 1 && b.height < 1) continue;
    // Where the clip is escaped rather than suffered. An absolutely-positioned
    // control whose containing block is above the clipping ancestor is painted
    // outside it on purpose, exactly as MISPLACED_BOXES' own resident is.
    if (getComputedStyle(el).position === "absolute") continue;
    // Up to the body and no further: the document's own scrolling arrangement is
    // the page's, not a widget's. The runtime scrolls body rather than the
    // viewport so the panel has room beside it, which leaves <html> clipping and
    // with nothing of its own to scroll — so a walk that ran to the root reported
    // every control below the fold as hidden by the page it is on.
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      const s = getComputedStyle(a);
      // Asked of the overflow value, per axis, and not of the scroll extent. A
      // box that clips always has something to scroll — that is what clipping
      // means — so `scrollWidth > clientWidth` is true of exactly the boxes this
      // is about and would wave every one of them through. What separates a
      // board, whose columns run past it and are reached by dragging, from a
      // group that swallowed its own pick marks is whether the box offers the
      // reader a way in: auto and scroll do, hidden and clip do not. Paint
      // containment clips both axes while `overflow` computes `visible`
      // (MISPLACED_BOXES reads the same fact for its ancestors), and it denies
      // the way in exactly where the axis has no scroller of its own.
      const contained = /paint|strict|content/.test(s.contain);
      const scrollX = s.overflowX === "auto" || s.overflowX === "scroll";
      const scrollY = s.overflowY === "auto" || s.overflowY === "scroll";
      const across =
        s.overflowX === "hidden" || s.overflowX === "clip" || (contained && !scrollX);
      const down =
        s.overflowY === "hidden" || s.overflowY === "clip" || (contained && !scrollY);
      if (across || down) {
        const f = a.getBoundingClientRect();
        const lost = Math.round(
          Math.max(
            across ? Math.max(b.right - f.right, f.left - b.left) : 0,
            down ? Math.max(b.bottom - f.bottom, f.top - b.top) : 0,
          ),
        );
        if (lost > 1) {
          out.push({
            ctrl: el.className,
            id: el.id,
            by: `<${a.tagName.toLowerCase()}${a.id ? " id=" + a.id : ""}>`,
            lost,
          });
          break;
        }
      }
      // And the walk stops at the first box the reader can move. Above a
      // scroller, a control outside an ancestor's rect is a control that ancestor
      // will show once the scroller is dragged, so measuring it there would
      // report a press that is one gesture away as one drawn nowhere.
      if (
        (s.overflowX !== "visible" && !across) ||
        (s.overflowY !== "visible" && !down)
      )
        break;
    }
  }
  return out;
}

export function tinyBoxes(widgets) {
  const inline = new Set(
    Object.entries(widgets)
      .filter(([tag, entry]) => entry["x-inline"])
      .map(([tag]) => tag),
  );
  return [...document.querySelectorAll("*")]
    .filter(
      (el) =>
        el.tagName.toLowerCase().startsWith("lf-") &&
        el.textContent.trim() &&
        el.checkVisibility() &&
        !el.closest("[hidden]"),
    )
    .map((el) => ({
      tag: el.tagName.toLowerCase(),
      id: el.id,
      w: Math.round(el.getBoundingClientRect().width),
      h: Math.round(el.getBoundingClientRect().height),
    }))
    .filter((box) => box.h < 10 || (!inline.has(box.tag) && box.w < 40));
}

// An element the reader can see and no mark can be shown on. The gate presses no keys, so
// it never watches the decision walk paint a ring or a comment paint an outline. It can still
// read whether either would have had anywhere to land, which is the same fault one step
// earlier, before it turns into a mark nobody can see.
//
// The fault is a box that isn't there. An element with `display: contents` lays its
// children out in its parent's flow and generates no box of its own, so its rect is the
// empty one every rect starts as — zero-sized, at the document's origin, a real-looking
// answer naming a place it is not. An outline drawn on it draws nothing, and a scroll
// aimed at it lands at the top of the page: a page whose open decisions were all suggestions
// answered `d` by appearing to do nothing at all, and that reached its reader rather than
// this gate. The runtime answers it by hanging a mark on the boxes an element shows
// through (shownParts) — which leaves one case that answer cannot reach, an element whose
// words are in no child element at all, where there is nothing to hang anything on.
//
// TINY_BOXES is next door and cannot see this: `checkVisibility()` is false for an element
// with no box, so the very elements at issue are the ones it filters out. Both readings are
// imported rather than restated, so what the gate refuses a handover for and what the page
// actually paints cannot come apart — the whole point of the pair being that there is one
// answer to where an element is.
export function unmarkableItems() {
  const HTML = "http://www.w3.org/1999/xhtml";
  const found = [];
  for (const el of document.querySelectorAll("[id]")) {
    // The document's own elements, which is what an anchor can name and a walk can
    // step to. A rendered diagram's insides are none of those — they are one
    // picture, whose <lf-diagram> is the thing to point at and has a box of its
    // own — and they are full of shapes with ids and no layout box: every <marker>
    // in a mermaid flowchart's <defs> read as an item showing 11x11px of words.
    if (el.namespaceURI !== HTML) continue;
    if (el.closest(".lf-chrome")) continue;
    const box = shownBox(el);
    // Nothing on screen is nothing to mark, and nothing the reader can point at
    // either: a collapsed tab's contents, a slot a decision retired.
    if (!(box.width && box.height)) continue;
    if (shownParts(el).length) continue;
    found.push({
      tag: el.tagName.toLowerCase(),
      id: el.id,
      w: Math.round(box.width),
      h: Math.round(box.height),
    });
  }
  return found;
}

// Words the page shows that no user can select, and so no comment can be
// anchored on. A widget has two ways to leave them there, neither of which a
// static lint can see, and a page-local widget is where both keep happening.
//
// It can paint them: `content: attr(label)` puts a heading on screen and in no
// text node, so a selection can't cover it. The runtime says the attributes the
// registry marks x-says, and a widget's module says the rest (a chip row, a
// heading that doubles as a list's accessible name); either way, none of an
// element's own attribute values should still be reaching the reader as
// generated content.
//
// Or it can leave them under .lf-ui with nothing said about whose words they are.
// That class is the chrome face, a look — reaching for it as a general "this is
// chrome" marker is how a user ends up unable to comment on a heading they can
// see. The declaration is made where the label is written: data-lf-said for the page
// speaking, which the anchor pass reads over the box around it, data-lf-offer for a
// thing to work. So inside a widget, every word under .lf-ui has to be declared the
// page's, be a control's own label, or be the line the paint pass writes to say how
// many comments a block carries: that one is about the document rather than of it,
// which is the same reason it wears .lf-ui at all, and it lands inside a widget
// whenever a comment does. The thread panel is out of scope: a widget in a reply is
// markup frozen in the event log, not the document.
//
// And a declared label inside a form control is out of reach whatever it is marked:
// Chrome starts no pointer selection inside one, which is why `offer` builds a press
// as a span wearing role="button". A widget reaching for <button> anyway is the one
// mistake the marker cannot fix, so it is reported separately and says why.
export function unreachableWords() {
  const found = [];
  const at = (el) => `<${el.tagName.toLowerCase()}${el.id ? " id=" + el.id : ""}>`;
  for (const el of document.querySelectorAll("*")) {
    if (!el.tagName.startsWith("LF-")) continue;
    const shown = ["::before", "::after"]
      .map((w) => getComputedStyle(el, w).content)
      .filter((c) => c && c.startsWith('"'));
    for (const { name, value } of el.attributes)
      if (value.length > 1 && shown.some((c) => c.includes(value)))
        found.push(`${at(el)} paints ${name}="${value}" rather than saying it`);
  }
  // The lf-* element something stands in, if any. A .lf-ui is a widget's own
  // chrome by standing in one of these, and the runtime's layer is appended to
  // body and stands in none — but a widget riding a message stands in the
  // layer, so which of the two a .lf-ui is has to be asked of the .lf-ui and
  // never of the words beneath it, which are inside a widget either way.
  const widget = (el) => {
    for (let a = el; a; a = a.parentElement) if (a.tagName.startsWith("LF-")) return a;
  };
  // The anchor pass's own rule: the nearest element that answers wins.
  const speaks = (el) =>
    Boolean(el.closest(".lf-ui, [data-lf-said]")?.matches("[data-lf-said]"));
  const FORM = "button, textarea, input, select";
  // Where a control's own words may sit: the control a widget declared (data-lf-offer,
  // asked instead of the role it wears, because lf-tabs overwrites `offer`'s
  // role="button" with "tab" and a Δ badge in a tab then read as a heading somebody
  // hid while the identical badge in a settled row read as chrome), or a native
  // control. `label` is among those because a radio and a checkbox have nowhere else
  // to put their words: a button holds its own, an input cannot, and HTML's answer is
  // an element beside it. lf-shot's flip is a checkbox, so that it keeps working in a page
  // whose script is gone. The line counting a passage's comments is one of these too —
  // the runtime builds it through `offer`, as a widget builds its own.
  const CONTROL = `${FORM}, label, a[href], [data-lf-offer]`;
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const el = n.parentElement;
    if (!n.data.trim()) continue;
    // Whose the .lf-ui is, per `widget` above. A widget's own chrome is read
    // here wherever the widget stands, a message included; the panel around a
    // widget riding one is not, which is what the note on the panel means.
    const chrome = el.closest(".lf-ui");
    if (!chrome || !widget(chrome)) continue;
    if (speaks(el) || el.closest(CONTROL)) continue;
    // A local work line is runtime chrome about its owning widget, not authored
    // words of that widget. Its subject is the anchor; the provisional sentence
    // deliberately is not another passage the reader can thread.
    if (el.closest(".lf-work-line")) continue;
    // .lf-quiet is words for a reader listening, clipped to nothing: not on
    // screen, so there is nothing here the eye can see and the pointer can't
    // reach — the failure this check exists for.
    if (el.closest(".lf-quiet")) continue;
    found.push(
      `${at(widget(el))} puts ${JSON.stringify(n.data.trim().slice(0, 40))} ` +
        `under .lf-ui, where no comment can reach it`,
    );
  }
  // FORM rather than CONTROL: a <label>'s words select like any others, and a widget
  // that declared a box a control has said nothing about what element it is.
  for (const el of document.querySelectorAll("[data-lf-said]")) {
    if (!el.closest(FORM) || !widget(el)) continue;
    found.push(
      `${at(widget(el))} says ${JSON.stringify(el.textContent.trim().slice(0, 40))} ` +
        `inside a form control, where no selection can reach it`,
    );
  }
  return [...new Set(found)];
}
