// A DOM-only probe that also runs against exported file:// pages, where the runtime and
// its public API have deliberately been removed. Kept as a real module so both the HTTP
// render gate and standalone-copy tests execute this one implementation.
export function coveredWords({
  holdFloating = true,
  holdHidden = true,
  holdLabelLines = true,
} = {}) {
  const runs = [];
  const at = (el) => {
    const named = el.closest("[id]");
    return named
      ? `<${named.tagName.toLowerCase()} id=${named.id}>`
      : `<${el.tagName.toLowerCase()}>`;
  };
  const outOfFlow = (style) =>
    style.position === "absolute" || style.position === "fixed";
  const floating = (el) => {
    // The offer may be only one contribution inside a shared positioned host. Walk
    // its actual ancestry rather than jumping from offer to offer, so the geometry
    // owner can remain a generated container without making its children's words
    // look like ordinary in-flow prose.
    for (let ancestor = el.closest("[data-lf-offer]"); ancestor;) {
      if (outOfFlow(getComputedStyle(ancestor))) return true;
      ancestor = ancestor.parentElement;
    }
    return false;
  };
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walk.nextNode(); node; node = walk.nextNode()) {
    const el = node.parentElement;
    if (
      !node.data.trim() ||
      el.closest(".lf-chrome, .lf-quiet") ||
      (holdHidden && el.closest("[hidden]"))
    )
      continue;
    if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
      continue;
    if (holdFloating && floating(el)) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const label = el.closest("text");
    for (const box of range.getClientRects())
      if (box.width > 1 && box.height > 1)
        runs.push({ el, label, box, text: node.data.trim().slice(0, 40) });
  }
  const found = [];
  for (let i = 0; i < runs.length; i++)
    for (let j = i + 1; j < runs.length; j++) {
      const a = runs[i];
      const b = runs[j];
      if (a.el === b.el || a.el.contains(b.el) || b.el.contains(a.el)) continue;
      if (holdLabelLines && a.label && a.label === b.label) continue;
      const across =
        Math.min(a.box.right, b.box.right) - Math.max(a.box.left, b.box.left);
      const down =
        Math.min(a.box.bottom, b.box.bottom) - Math.max(a.box.top, b.box.top);
      if (across <= 2 || down <= 2) continue;
      found.push(
        `${at(a.el)} draws ${JSON.stringify(a.text)} in the same place as ` +
          `${at(b.el)}'s ${JSON.stringify(b.text)}`,
      );
    }
  return [...new Set(found)];
}

// ---------- export: the page as one file ----------

// What a standalone copy drops. Scripts go because there is no server behind a file
// and nothing left for them to reach; the runtime's own layer goes with them, since a
// comment box that swallows what you type and a banner claiming someone is listening
// are worse than no chrome at all — a copy that lies about being a live page. What stays
// is everything the widgets built, and the controls they injected where the browser is
// what works them: a `lf-shot` flips on a checkbox with no script running. A press a handler
// answered leaves the words it stated and takes the rest of itself with it, below.
//
// `lf-copy` is the medium, declared the way `@media print` is and read the same way —
// by the theme, per widget. A widget whose control needed a handler puts the affordance
// behind a guard this class fails, so a copy gets the page its markup describes; one
// whose control the browser owns has no guard and keeps working. That is why no widget
// is named here: this marks the medium, and the widgets answer for themselves.
export function bake() {
  document.documentElement.classList.add("lf-copy");
  // A receipt is runtime chrome even where its seat is in the page rather
  // than under .lf-chrome. Remove it from the document and every open shadow root
  // before those roots are serialized below: a file has no agent behind the claim,
  // so preserving the rendered sentence would turn provisional news into a lie.
  const roots = [document];
  for (const root of roots)
    for (const element of root.querySelectorAll("*"))
      if (element.shadowRoot) roots.push(element.shadowRoot);
  for (const root of roots)
    root.querySelectorAll(".lf-receipt").forEach((el) => el.remove());
  document.querySelectorAll("script, .lf-chrome").forEach((el) => el.remove());
  // A measurement of this window is not a fact about the reader's. The live page states
  // each drawn edge's width inline on the root, and an inline value outranks every rule
  // a stylesheet could write, so a
  // copy carrying one holds whatever width the exporter's headless window happened to
  // have, on a file whose whole point is being opened somewhere else. Each rule that
  // reads one falls back to the viewport, which is honest in a copy: no panel takes a
  // strip from a file, and no session grows one. Taken off the way the chrome above
  // is, rather than guarded against in the theme, because the stale number is the
  // thing that is wrong here and a rule written around it would leave it there to be
  // read by the next thing that asks.
  //
  // Named, and the names are the point. What goes is a measurement whose subject
  // this file no longer has: the panel and the tray are removed with the chrome
  // above. A copy drops what it hasn't got. Page room is not in this list: CSS resolves
  // it from the copy's own shell.
  //
  // It keeps what it still has, which is why `--rail` is not on this list and must
  // not be added to it. The rail is the width of the margin a suggestion's controls
  // stand in, and a decided change keeps that row's receipt — the record of what was
  // decided is the whole reason the margin was reserved. Cleared, the copy reads its
  // room off the viewport, knows nothing of the row still sitting in the margin, and
  // spends the surplus on the free side: the exported board stood 35px outside the
  // page's box at a laptop's width and 47px at a narrow one, off the left, where
  // overflow scrolls nothing and the columns are not cut off with a way to reach
  // them but simply gone. `test_a_copy_keeps_the_rail_a_decided_change_left` is
  // that, and it is what a sweep of every inline custom property on the root ran
  // into: read as a stale number, the rail is the one that is not.
  for (const stale of ["--lf-panel-w", "--lf-tray-w"])
    document.documentElement.style.removeProperty(stale);
  // The tab icon is the third seat of the banner's status (paintTab), and a file has
  // no session behind it — a copy keeping the tone it was exported under would claim
  // one, which is the same lie the chrome above is dropped for. So it drops back to
  // the mark as authored, which the runtime left here for exactly this.
  const icon = document.querySelector('link[rel="icon"][data-lf-rest]');
  if (icon) {
    icon.href = icon.dataset.lfRest;
    icon.removeAttribute("data-lf-rest");
  }
  // hidden="until-found" is the page saying "collapsed, but the reader can still
  // get here" — a tab's inactive panel, a settled group's cards. In a copy the
  // control that would get them there is inert, so the attribute is a promise
  // nothing can keep, and it takes the collapsed element's layout down with it:
  // the theme zeroes a hidden card's padding, which is the room its chips are
  // positioned into. Dropping it opens the element on the terms it was authored
  // with, which is the layout the theme's live-page guard was withholding anyway.
  document
    .querySelectorAll('[hidden="until-found"]')
    .forEach((el) => el.removeAttribute("hidden"));
  // A press a widget injected is the runtime's own element — a <button> `offer` built, or
  // a span `selectableOffer` gave a role and a tab stop — and either was a promise a
  // handler kept. The handlers left with the scripts above, so a copy that carried them
  // offered a press nothing can take — and the first Tab into an exported decision page
  // landed on one. It was a `choose` group's pick mark, which
  // drew the keyboard address for a key that answers nothing, into a row holding no
  // column for it: the 30px an option reserves is live-page-only, so the digit came
  // down 8px over the option's own first word.
  //
  // So the control goes and its word stays, which is the bargain paper struck first
  // (the runtime's @media print rule, on these same two markers). A mark reading
  // "chosen" is the page stating which option won, and it stays with the role and the
  // tab stop taken off it; "choose one" is an invitation, and it leaves with the grips,
  // the pills and the pencils. Where the words a removal takes with it are the page's —
  // a settled group's disclosure names its chosen card, a tab's button names its panel —
  // the copy has those open underneath saying it themselves, which is why paper drops
  // the same two.
  //
  // A copy parts from paper on one thing: it is still a document the browser runs, so a
  // control the browser drives keeps working, and lf-shot flips its frames on a checkbox in
  // a file with no script behind it. What tells the two apart is the marker's *value*,
  // which is `offer` naming what it built: "button" for the one tag whose whole effect was
  // the handler that left with the scripts, and the empty string for every other tag — so a
  // checkbox, a label and a § link stay, keeping the role that says what they are. A press
  // that was never native carries a word too, `selectableOffer` writing there the role it
  // gave its span, since a span is pressable only while a handler is there to answer it.
  //
  // Asked of the marker rather than of the role, because a press does not end up wearing
  // one role: a widget with an ARIA pattern to keep names its own, so every press in
  // lf-tabs' strip says role="tab", and naming a single role would have left that widget's
  // out or the next one's. The author's roles are untouched, being on the author's
  // elements: a board's columns stay a list of cards to a screen reader.
  //
  // The box a press hung in goes with it when that is all it held. A pending suggestion's
  // row is nothing but its two controls; a decided one also holds the visible receipt
  // the copy must keep. Asked of what each removal empties rather than of an empty box,
  // since a widget's own empty box is
  // a real thing: that row hangs off an anchor span which takes no space and says
  // nothing, and `anchor(top)` is measured from it.
  // A reaction is the reader's mark on the page, and a copy keeps a mark the way it
  // keeps a chosen option's word: the glyph stays in the margin with its press taken
  // off — the button element it was built as, and the marker and title that promised it.
  // The remaining glyph becomes a named static image, and the wash on the words,
  // which is a highlight-registry entry no serialization carries, is written into
  // the words as a <mark> for this copy alone (the theme's html.lf-copy rule paints
  // it). Each painted range lies within one text node
  // (anchors.js paints a range per segment), which is what lets surroundContents
  // wrap it; the ranges are live, so an earlier wrap moves a later one's offsets.
  for (const offeredMark of document.querySelectorAll(".lf-react-mark")) {
    let mark = offeredMark;
    if (mark.matches("button")) {
      const staticMark = document.createElement("span");
      for (const attr of [...mark.attributes])
        staticMark.setAttribute(attr.name, attr.value);
      staticMark.replaceChildren(...mark.childNodes);
      mark.replaceWith(staticMark);
      mark = staticMark;
    }
    for (const attr of ["tabindex", "data-lf-offer", "title", "type"])
      mark.removeAttribute(attr);
    mark.setAttribute("role", "img");
    mark.setAttribute("aria-label", mark.dataset.token);
  }
  // Two reactions on overlapping words leave the second range straddling the first's
  // mark, which no element can wrap; that range keeps its glyph and loses its wash.
  for (const range of CSS.highlights.get("lf-react") ?? []) {
    const wrap = document.createElement("mark");
    wrap.className = "lf-react";
    try {
      range.surroundContents(wrap);
    } catch {
      /* straddles a mark */
    }
  }
  // Runtime-owned controls are native by default on the live page. In a script-free
  // copy their browser activation would still fire, but its result would not, so remove
  // them by the offer marker rather than by the tabindex attribute pseudo-controls used
  // to carry. A wrapper around a non-offered native control is the exception: the browser
  // still owns that complete interaction in the copy.
  //
  // A *valued* marker, because `offer` writes the empty one on the boxes a widget builds
  // to hold its controls — a suggestion's ✓/✗ row among them — and those are not presses
  // to take away. Matched on the bare attribute this loop removed the box outright, with
  // whatever the copy keeps still inside it: the "Accepted" receipt a decided change
  // speaks through went out with the row it stood in, and the rail the copy holds open for that
  // record had nothing left to show. What empties a box is the walk below, which is the
  // reading that was already right.
  const browserControl =
    "input:not([data-lf-offer]), select:not([data-lf-offer]), textarea:not([data-lf-offer]), " +
    "a[href]:not([data-lf-offer]), button:not([data-lf-offer]), summary:not([data-lf-offer])";
  for (const control of [
    ...document.querySelectorAll(
      "[data-lf-offer]:not([data-lf-offer='']):not([data-lf-said])",
    ),
  ].reverse()) {
    if (
      control.querySelector(browserControl) ||
      [...control.querySelectorAll("label")].some(
        (label) => label.control && !label.control.matches("[data-lf-offer]"),
      )
    )
      continue;
    let dead = control,
      box = dead.parentElement?.closest("[data-lf-offer]");
    dead.remove();
    while (box && !box.firstChild) {
      dead = box;
      box = dead.parentElement?.closest("[data-lf-offer]");
      dead.remove();
    }
  }
  document.querySelectorAll("[data-lf-offer][data-lf-said]").forEach((offered) => {
    let el = offered;
    if (el.matches("button, input, select, textarea, a[href], summary")) {
      const staticWord = document.createElement("span");
      for (const attr of [...el.attributes])
        staticWord.setAttribute(attr.name, attr.value);
      staticWord.replaceChildren(...el.childNodes);
      el.replaceWith(staticWord);
      el = staticWord;
    }
    el.removeAttribute("role");
    el.removeAttribute("tabindex");
    for (const attr of [
      "href",
      "type",
      "name",
      "value",
      "disabled",
      "popover",
      "popovertarget",
      "popovertargetaction",
    ])
      el.removeAttribute(attr);
    // The states and relations rode the role: pressed="true" on a plain span is
    // ARIA nothing may interpret (axe calls it critical), where the label is the
    // word's accessible copy and stands on its own.
    for (const attr of [...el.attributes])
      if (
        attr.name.startsWith("aria-") &&
        !["aria-label", "aria-hidden"].includes(attr.name)
      )
        el.removeAttribute(attr.name);
  });
  // Target items are generated containers rather than offers themselves. A pending
  // action leaves the container empty when its inert controls are stripped above; take
  // that shell too, or :has(.lf-margin-item) reserves the live page's rail in a copy
  // that kept nothing in it. Decided records and standing reaction marks remain as
  // children and therefore retain both their shared item and its rail.
  //
  // The fold `…` unfolds is a container of the same kind, and it stands in every item
  // whether or not anything is folded into it. Emptied of its stand-in Buttons, it is a
  // child the item still has, so an item holding nothing else is no longer `:empty` and
  // kept the rail open on the strength of a shell. Take the emptied fold first, then ask
  // the item.
  document
    .querySelectorAll(".lf-margin-options:empty")
    .forEach((fold) => fold.remove());
  document.querySelectorAll(".lf-margin-item:empty").forEach((item) => item.remove());
  // What the runtime painted, as against what a widget built, goes the same way. An
  // element-anchored comment's mark is a class the kept stylesheet answers with a
  // ring and a pointer hand, and the panel that hand promised left with the chrome —
  // while a text-anchored mark, painted through the highlight registry by script, is
  // already gone. One fact — a comment is anchored here — leaves the copy whole.
  document
    .querySelectorAll(".lf-mark-el")
    .forEach((el) => el.classList.remove("lf-mark-el"));
  // A tab stop still standing on a widget element is module paint — the registry's
  // schemas admit no authored tabindex on one — promising focus to chrome whose
  // handler left with the scripts: a tabs panel's roving stop, a decision-lend. Asked
  // of the tag's dash, the platform's own mark of a custom element, so no widget
  // is named and the author's own elements are untouched. Scroll stops go with
  // the rest and come back below, where every scrollable box is answered at once.
  document.querySelectorAll("[tabindex]").forEach((el) => {
    if (el.tagName.includes("-")) el.removeAttribute("tabindex");
  });
  // Then what the removals uncovered: a box that scrolls whose way in was the
  // chrome just taken out — a board whose grips were its only focusable content,
  // a diagram whose stop the sweep above stripped — has no keyboard into it, and
  // scrolling needs no handler (the lf-shot bargain). The live page's one grantor
  // is reachScrollers; its predicate is restated here because the runtime's
  // module scope left with the scripts, and this pass runs where the removals
  // have already settled what remains. Of its two products only the stop is
  // restated: the hold it marks rides into the copy as the attribute and the
  // theme rule reading it, and nothing removed above turns a box into a scroller.
  for (const root of roots)
    for (const el of root.querySelectorAll("*")) {
      if (el.tabIndex >= 0) continue;
      const style = getComputedStyle(el);
      if (
        !/^(auto|scroll)$/.test(style.overflowX) &&
        !/^(auto|scroll)$/.test(style.overflowY)
      )
        continue;
      if (
        !el.querySelector(
          "a[href], button, input, select, textarea, " +
            '[tabindex]:not([tabindex="-1"])',
        )
      )
        el.tabIndex = 0;
    }
  // getHTML and not outerHTML: a widget that renders the page's words into a shadow
  // root (x-shadow) has them in no element's outerHTML, so a copy taken that way
  // arrives with an empty element where a diff's lines were — silently, since the
  // element and its ids are all still there. Asking for serializable roots writes each
  // one as a declarative <template shadowrootmode>, which the browser rebuilds on open
  // with no script, the same bargain every other widget's chrome makes here.
  //
  // It is innerHTML's counterpart, though, so the root's own tag is not in what it
  // returns and has to be written back: <html> carries the lang the document is read
  // in and the lf-copy class the theme reads its medium from, and a copy missing them
  // opens as a live page whose affordances press nothing. Rebuilt from the attributes
  // rather than sliced off outerHTML's opening tag, because an attribute value may
  // hold the very > that slicing would stop at.
  const root = document.documentElement;
  const attrs = [...root.attributes]
    .map(
      (a) =>
        ` ${a.name}="${a.value.replaceAll("&", "&amp;").replaceAll('"', "&quot;")}"`,
    )
    .join("");
  return `<html${attrs}>${root.getHTML({ serializableShadowRoots: true })}</html>`;
}
