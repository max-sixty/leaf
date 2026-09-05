/* This module owns declared shadow roots, their theme slice, and the shared highlight
 * rules. */
import { tagsDeclaring } from "./registry.js";

// The open shadow roots under some root that hold the page's own words, from what the
// registry declares rather than from a sweep of every element: an x-shadow widget is
// making a promise about whose words those are, and a root some other library happened
// to attach is not covered by it. `getComposedRanges` is told exactly these, so what the
// capture can see and what the reading walks are one list.
//
// Which root to look under is the axis, because the whole document is not the only
// answer: a message arriving in the panel carries widget markup that upgrades in a
// subtree, so a pass over that subtree has the same boundary to cross and no document
// to ask about.
export const shadowRootsIn = (root) =>
  tagsDeclaring((entry) => entry["x-shadow"])
    .flatMap((tag) => [
      ...(root.nodeType === Node.ELEMENT_NODE && root.matches(tag) ? [root] : []),
      ...root.querySelectorAll(tag),
    ])
    .map((host) => host.shadowRoot)
    .filter(Boolean);
export const pageShadowRoots = () => shadowRootsIn(document);
// The parent, crossing a shadow root's boundary on the way up: the one walk every reading
// that climbs out of a widget takes.
export const upFrom = (node) =>
  node?.parentElement ?? node?.getRootNode()?.host ?? null;

// Which layer a node stands in — the runtime's chrome, a declared label, or the
// document — is asked by every reading that climbs out of a widget, so it is answered
// here, beside the climb, where geometry.js and widget-elements.js can ask it without
// importing the passage readings back.
// Is `node` inside `root`? `Element.contains` stops at a shadow boundary and these
// readings walk through one, so the climb is the same one `closestAcross` makes.
export const under = (node, root) => {
  for (let a = node; a; a = a.parentNode ?? a.host ?? null) if (a === root) return true;
  return false;
};

// The chrome over a node, read within one frame: above the frame it is nobody's, and with
// no frame at all it is the document's own reading, unchanged.
export const overIn = (el, selector, frame) => {
  const near = el.closest(selector);
  return near && (!frame || under(near, frame)) ? near : null;
};
// A label a widget declared as the page speaking (relabel), which the anchor pass reads
// over the chrome it sits in.
const SAID = "[data-lf-said]";
// The same question one node at a time: is this the runtime's own chrome rather than the
// document? Every affordance asks it before acting on where the pointer or the caret is.
// The nearest element that answers wins: a declared label is the page's words inside the
// control it labels, and a control nested inside one is chrome again. `.lf-ui` alone was
// the answer once, and it is a look — which is how a user ended up reading a heading
// they could not point at, twice.
//
// Bounded or not, by the second argument, and that is the whole difference between the
// two ways this gets asked. Unbounded — `inUi` — the answer is about the page: a
// control is the runtime's apparatus wherever it stands, which is what a pointer or a
// caret needs to know. Bounded at an element, the answer is about that element's own
// insides, which is what a reading of one widget needs: the panel holding a widget an
// agent sent in a reply is itself `.lf-ui`, so asked the unbounded way every child of
// such a widget answers yes, and the widget reads as having nothing of its own left.
// The text readings took the same seam (quotable, shownParts, settledAway, authored);
// it is stated once here so
// that what a mark may hang on, what a settlement has emptied, and what a quote may
// name cannot come apart.
export const uiInside = (el, within) => {
  const near = el && overIn(el, `.lf-ui, ${SAID}`, within);
  return Boolean(near) && !near.matches(SAID);
};
export const inUi = (node) =>
  uiInside(node?.nodeType === 1 ? node : node?.parentElement, null);

// The theme's rules for shadow trees, sliced out once at load (see the markers in
// theme.css). Every layer may contribute a block; concatenating them in theme order
// preserves the same cascade inside a declared shadow root as in the document. Read
// from the theme rather than written here so a project override travels with the widget,
// and fetched during upgrade so the stage below stays synchronous for its callers.
export let shadowRules = "";
const SHADOW_CSS = /\/\* lf-shadow:start \*\/([\s\S]*?)\/\* lf-shadow:end \*\//g;
// A top-layer element no longer composites through its light/shadow ancestors, so the
// document's rules cannot withhold a dialog or popover promoted out of an x-shadow
// widget. Every legitimate page shadow tree is built here; repeat that narrow boundary
// inside it, together with transition suppression. The shadow's ordinary contents still
// paint before presentation, just like authored light DOM.
export const SHADOW_STARTUP_CSS = `
@layer {
  @media screen {
    :host-context(body:not([data-lf-presented])) *,
    :host-context(body:not([data-lf-presented])) *::before,
    :host-context(body:not([data-lf-presented])) *::after {
      transition: none !important;
    }
    :host-context(body:not([data-lf-presented])) :is(dialog, [popover]),
    :host-context(body:not([data-lf-presented])) :is(dialog, [popover])::backdrop {
      visibility: hidden !important;
      opacity: 0 !important;
      transition: none !important;
      interactivity: inert !important;
    }
  }
}`;
// One read for the tab. The three boundaries that import widget modules each ask for the
// rules the widgets they are about to upgrade render under, and an x-shadow widget can
// arrive at any of them — in the document, in a later version, or in an agent's reply —
// so the ask is repeated and the answer is not. Sharing the promise rather than the text
// also holds a second caller behind the first read instead of starting another.
let loading = null;
export function loadShadowRules() {
  loading ??= readShadowRules();
  return loading;
}
async function readShadowRules() {
  const response = await fetch("/theme.css");
  if (!response.ok) throw new Error(`leaf: theme failed to load (${response.status})`);
  // Refused rather than defaulted to nothing. A project theme that drops the markers
  // still styles the document, so the page looks right everywhere except inside the
  // widgets this slice feeds — which would arrive unstyled with no error anywhere, the
  // failure that reads as a widget nobody finished rather than as a theme missing a
  // block. Whichever theme is vendored, either it carries these or the page says so.
  const found = [...(await response.text()).matchAll(SHADOW_CSS)];
  if (!found.length)
    throw new Error(
      "leaf: the theme carries no /* lf-shadow:start */…/* lf-shadow:end */ block, " +
        "which is where the rules an x-shadow widget renders under are read from",
    );
  shadowRules = found.map((match) => match[1]).join("\n");
}

import marksSheet from "./marks.css" with { type: "css" };

export { marksSheet };
