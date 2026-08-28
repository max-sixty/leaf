import { says } from "/runtime/widget-api.js";

export const shownVerbatim = ({ widgets, touched }) =>
  Object.entries(widgets)
    .filter(([, entry]) => entry["x-verbatim"])
    .flatMap(([tag]) =>
      [...document.querySelectorAll(tag)]
        .filter((el) => el.id && !touched.includes(el.id))
        .map((el) => ({ tag, id: el.id, says: says(el) })),
    );

// What the page says, and whether each run of it is showing. Read once in each medium
// and compared by walk order: media change what is displayed, never the DOM, so the nth
// run on screen is the nth run on paper. What a page says has to survive being printed,
// and the ways it can fail to are all silent — a widget's control that is a statement as
// well as a thing to press (the pick mark, which took the only words naming the option a
// group carried), a rule of the page's own that hides its content in print. The whole
// page rather than the widgets in it, because a user's printout losing a paragraph is
// no better than losing a widget's word. Declared offers are excluded because paper has
// nothing to press; the runtime's own layer is excluded because it was never the
// document, and a widget rendered inside it (a reply's markup) is the panel's, not the
// page's.
export function paperWords() {
  const out = [];
  const at = (el) => {
    const named = el.closest("[id]");
    return named
      ? `<${named.tagName.toLowerCase()} id=${named.id}>`
      : `<${el.tagName.toLowerCase()}>`;
  };
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const el = n.parentElement;
    if (!n.data.trim() || el.closest(".lf-chrome, [data-lf-offer]")) continue;
    out.push({
      at: at(el),
      text: n.data.trim().slice(0, 40),
      shown: el.checkVisibility(),
    });
  }
  return out;
}

// Words the page draws in the same place as other words. A copy went out with a settled
// group's cards laid across the heading above them — the cards kept the collapsed
// padding, which is the room the group is laid out in — and the user saw it in the
// first second while every assertion passed: the words were all present, all shown, and
// all of a usable size. They were in the same place, and nothing was asking about place.
//
// Boxes rather than a hit test, which is the other way to ask: a press landing on the
// wrong element is a different fault with its own test, and the medium this has to hold
// up in is the copy, where there is nothing left to press. Text against text, because
// text over a background, a border, or a picture is how a page is built.
//
// What floats over the document on purpose is answered for, and that is one exemption
// rather than two. It reads as the runtime's, because for a long time the runtime owned
// every float there was; the sentence is about the float and not about the owner. A
// suggestion's controls hang out of the flow, level with the change they decide, and a
// sidenote hangs out of the flow level with the block it annotates — both in the right
// margin now, both pinned by what they belong to, so where a page stands them level the
// controls are drawn over the note and neither can move. Reporting that would refuse
// every page that writes a note beside a change, which is a composition the vocabulary
// is meant to have; so the float is exempt and the note is what it may cover. Where the
// same row docks back into the flow it is a resident again, and covering a word there is
// a fault this still reports.
//
// A pair where one element contains the other is skipped: a paragraph and the <em>
// inside it are one run of words that the flow lays out together, and their boxes
// overlap by construction. Two pixels of slack, since a line box carries its leading and
// adjacent blocks can round into each other by a hair. The runtime's layer is skipped
// too: it floats over the document on purpose, and where that costs the user a press
// it is the hit test that says so.
//
// The same fact one element over: an SVG <text> lays out its own lines, a tspan each,
// every one of them a sibling of the last. Where a chart's date axis names the month a
// week begins — the tick reading 1 over Dec — the two lines are offset by the dy the
// drawing asked for and each reports a line box carrying the font's own leading, which
// is a couple of pixels taller than that step. So the pair overlapped by construction on
// a drawing where no glyph comes near another. A wrapped paragraph is the identical
// shape and never reported, because its lines are boxes of one text node and the
// same-element skip takes them; two lines of one label are two nodes only because SVG
// spells a line break as an element. The <text> is the label, so a pair inside one of
// them is one word of the page's, and this asks about two.
//
// The layer is in two places and the float rule reaches both, which is why only one of
// them is named. The line counting a passage's comments lives inside the page's own
// elements by design — it is what a screen reader hears where a painted mark says
// nothing — and it is clipped to nothing on screen. checkVisibility answers for display,
// visibility and opacity and knows nothing of clip-path, so that line read as drawn, and
// its text lays out past the 1px box holding it: an anchor on a container put "1 comment"
// across the paragraph below the widget and failed the gate on a page with nothing wrong
// with it. It wore a name in this selector for a while, next to the container's, and the
// name went the day the rule below could answer for it — the line is a control the
// runtime hangs absolutely, which is the whole of what `floating` asks. Two skips over
// one element is a guarantee kept twice, and the weaker of them is the one that has to be
// remembered when the next float is written.
//
// checkVisibility knows nothing of content-visibility either, which is what a collapse
// wears: an inactive tab's panel and a settled group's cards are hidden="until-found" so
// that find-in-page still reaches inside, and the text in one reports the boxes it last
// laid out in — every sibling's at the same place. So a page with a collapsed group on it
// failed about half the runs and passed the rest, which is the worst way for a gate to be
// wrong: the page that goes out is whichever one the coin was kind to. A collapse is asked
// for, and words nobody can see are not drawn over anything, so [hidden] is held out here
// the way the size check holds it out. The coin comes down the same side every time on a
// group that has been opened and closed, which is where the test pins it.
export { coveredWords } from "./standalone.js";

// Which trees are the page, for the two readings below that answer for what a widget
// renders rather than for what it declares. Every open root, found by walking rather than
// read off the registry's x-shadow list: a root a module attached without declaring one
// still holds words and code the reader has to read, and a reading that asked the
// registry would look away from exactly the tree nobody vouched for. Written once,
// because it is one claim about the page and two copies of it are two things to keep
// level.

// Code that came out the colour of the code around it. Colouring takes two halves that
// meet nowhere a static lint can reach: the runtime writes data-lf-syn in the browser,
// and the theme answers it with a var() the browser resolves. Either half can stop
// working with nothing said — the tokenizer failing throws, and the console error is
// already a finding here, but a stylesheet that no longer answers a role, or answers it
// with an ink too near the paper, is silent. What reaches the user is a page of code in
// one flat colour, which is what they report as the highlighting being gone; it was
// reported that way, on a comment that was 3.3:1 against the block it sat on.
//
// So both halves are asked of the drawn result rather than of the declarations behind it.
// A palette can be read out of the stylesheet; what a role came out as cannot, because a
// project overlays its own theme over this one and the browser is the only thing that
// knows which declaration won.
//
// Once per role and surface rather than once per span: the fault belongs to the role, not
// to the hundredth span wearing it, and a role reads differently on a diff's del tint than
// on the plain block, so the pair is what a reading answers for. A page of code costs a
// couple of dozen of them rather than one per token — measured at under 10ms across the
// examples. The line is per role, since the palette is where the fix goes and a role
// failing on two tints is one thing to change.
//
// What a colour is comes back from the browser painting it, not from a parse of how it
// wrote it down — getComputedStyle serializes a hex as rgb() in 0–255 and a color-mix as
// color(srgb …) in 0–1, and a probe reading one as the other reports a ratio against a
// colour nothing on the page is. Painting the backgrounds in order composites the
// translucent ones the way the page does, over the white the browser paints under
// everything, so a tint over a tint is the colour the reader actually has behind the
// glyphs. A marked passage is not among them: the highlight registry styles glyphs and
// not boxes, so a mark is no element's background, and it is the user's own paint over a
// page that had to be legible before they put it there.
//
// 4.5:1 is WCAG AA for body text, and body text is the threshold that applies — code is
// 13px. Axe runs over this corpus too and passes it, which is not the same guarantee:
// asked for colour-contrast alone on the example carrying the beige comment, it returned
// 44 passing elements, no violation, and not one of the spans among them.
//
// Which shadow roots it crosses into is OPEN_ROOTS' answer (the section note above says
// why it crosses at all), which is the choice everything else here makes — colour is
// asked of what the browser painted, so where it painted is too, and a root a widget
// attached without declaring one still holds code the reader has to read.
export function unreadSyntax() {
  const roots = (root) => [
    root,
    ...[...root.querySelectorAll("*")]
      .filter((el) => el.shadowRoot)
      .flatMap((el) => roots(el.shadowRoot)),
  ];
  const cx = document.createElement("canvas").getContext("2d");
  const paint = (...layers) => {
    cx.clearRect(0, 0, 1, 1);
    for (const c of ["white", ...layers]) {
      cx.fillStyle = c;
      cx.fillRect(0, 0, 1, 1);
    }
    return [...cx.getImageData(0, 0, 1, 1).data.slice(0, 3)];
  };
  const chan = (v) =>
    (v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  const lum = ([r, g, b]) => 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b);
  const ratio = (a, b) => {
    const [hi, lo] = [lum(a), lum(b)].sort((p, q) => q - p);
    return (hi + 0.05) / (lo + 0.05);
  };
  const up = (el) => el.parentElement ?? el.getRootNode().host ?? null;
  const under = (el) => {
    const layers = [];
    for (let a = el; a; a = up(a)) layers.unshift(getComputedStyle(a).backgroundColor);
    return layers;
  };
  const seen = new Set(),
    found = new Map();
  for (const span of roots(document).flatMap((r) => [
    ...r.querySelectorAll("[data-lf-syn]"),
  ])) {
    const role = span.dataset.lfSyn;
    if (found.has(role) || !span.textContent.trim()) continue;
    if (!span.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
      continue;
    const layers = under(span);
    const on = paint(...layers);
    if (seen.has(`${role} on ${on}`)) continue;
    seen.add(`${role} on ${on}`);
    const ink = paint(...layers, getComputedStyle(span).color);
    const plain = paint(...layers, getComputedStyle(up(span)).color);
    const read = ratio(ink, on);
    if (String(ink) === String(plain))
      found.set(
        role,
        `code marked ${role} is the ink of the code around it — ` +
          `nothing answered [data-lf-syn="${role}"]`,
      );
    else if (read < 4.5)
      found.set(
        role,
        `code marked ${role} reads at ${read.toFixed(1)}:1 ` +
          `against the block it is set on`,
      );
  }
  return [...found.values()];
}

// Words a declaration promised and the page never got. Every other reading here works
// from what the browser drew, and that is exactly what cannot see this one: a word that
// never arrived looks the same as an attribute with nothing to say, and a fact the page
// paints in colour alone is a fact no measurement of a drawn page has ever read. The
// registry is what knows the difference — x-says names the attributes whose values are
// words at the element's edge, x-paints the ones drawn as paint and spoken to a reader
// listening (renderQuiet) — so the declaration is what this asks against.
//
// Both passes run once at the upgrade, before an async widget's own render lands, so a
// module that rebuilds its body from a settle() promise takes the words out with it and
// nothing on the page says so. renderQuiet re-runs on each replay and renderSaid never
// does, which decides how long each stays gone rather than whether it goes.
//
// It reads every open root (OPEN_ROOTS) where both word passes stop at the boundary on
// purpose: which widgets the page holds is the document's question, and settling a
// staged widget's nesting in a sweep would be writing that contract where nobody would
// look for it (the layer's CLAUDE.md). So a staged element keeps its declarations and
// gets neither pass, which is exactly where a promised word reaches nobody in silence —
// reported here, to the module's author, at handover.
//
// Both halves ask the *rendered* page rather than the markup, and a shadow host is why:
// an element that stages a tree keeps its light DOM in the document and out of every box,
// so both passes find the host, write there, and leave `textContent` and `querySelector`
// reporting words the reader will never get. Each half gets to the rendered page its own
// way, because they read different things. Words are `says()`, the layer's one answer to
// what an element says rather than a second reading spelled here — asked of the host's
// root where there is one, since the walk behind it substitutes a declared root for a
// *child* and never for the element it was handed. The quiet word is in no such reading,
// wearing the .lf-ui that `says` skips on purpose, so what is asked of it is its box: a
// span clipped to a pixel still has one wherever it renders, and none at all where it
// doesn't. Which is only a question worth putting where the element renders at all — a
// collapsed card, a tab nobody opened and a shut comment panel all lay out nothing, and
// their rects report the ancestor rather than the widget. That is the *second* failure
// here, a word the widget wrote and then hid. The first one, a word it never wrote, is a
// fault wherever the element stands, since a tab the reader has not opened is a tab they
// can open. Splitting them that way is what retired the [hidden] exemption this carried:
// `hidden` and `hidden="until-found"` are two of the ways an element stops rendering, and
// asking whether it renders covers both and the panel besides.
export function silentWords(widgets) {
  const roots = (root) => [
    root,
    ...[...root.querySelectorAll("*")]
      .filter((el) => el.shadowRoot)
      .flatMap((el) => roots(el.shadowRoot)),
  ];
  const found = [];
  const all = roots(document);
  const at = (el) => `<${el.localName}${el.id ? " id=" + el.id : ""}>`;
  const every = (tag) => all.flatMap((r) => [...r.querySelectorAll(tag)]);
  for (const [tag, entry] of Object.entries(widgets)) {
    for (const attr of Object.keys(entry["x-says"] ?? {}))
      for (const el of every(tag)) {
        const value = el.getAttribute(attr);
        if (value !== null && !says(el.shadowRoot ?? el).includes(value))
          found.push(
            `${at(el)} declares ${attr} as x-says and never says ` + `"${value}"`,
          );
      }
    // The word itself is renderQuiet's to derive, and this asks only that the
    // element carries one: a widget painting a fact and saying nothing is the
    // whole of the failure, and all a second copy of the derivation would add is
    // a second place to change it.
    for (const attr of entry["x-paints"] ?? [])
      for (const el of every(tag)) {
        if (!el.hasAttribute(attr)) continue;
        const quiet = el.querySelector(":scope > .lf-quiet");
        // A missing word is the fault, and it is the fault wherever the
        // element stands: a tab the reader has not opened is still a tab
        // they can open. What the box is asked for is the second failure,
        // a word the widget wrote and then hid, and that question can only
        // be put to an element that is being laid out — a message in a shut
        // panel lays out nothing, so its rects report the panel's state and
        // would be read as the widget's.
        if (quiet && (quiet.getClientRects().length || !el.checkVisibility())) continue;
        found.push(
          `${at(el)} paints ${attr}="${el.getAttribute(attr)}" ` +
            `and says nothing a reader listening can hear`,
        );
      }
  }
  return found;
}
