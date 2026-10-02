/* This module owns declared shadow roots, the shadow.css rules they render under, and
 * the shared highlight rules. */
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
// The host of `root` when it is a shadow root, else null: the one test of whether a climb
// crosses to a host. It asks the root's kind, since other roots answer `host` too — a
// document names its `<form name="host">` there, and a detached subtree's root is an
// element, an `<a>` or `<area>` whose `host` is its URL's. The kind is its node type
// rather than `instanceof ShadowRoot`, whose class belongs to one window: an iframe's
// runtime climbs its parent document's elements out to the frame's place in the page.
export const shadowHost = (root) =>
  root?.nodeType === Node.DOCUMENT_FRAGMENT_NODE ? (root.host ?? null) : null;
// The parent, crossing a shadow root's boundary on the way up: the ordinary parent within
// a tree, and the host where a tree runs out. It is the one walk every reading that
// climbs out of a widget takes. Every question the runtime asks about where a node sits —
// which section, which block, which passage cell, whether it is chrome — is asked of the
// page, and a climb that stops at a shadow root answers about the widget's own markup
// instead.
export const upFrom = (node) => node?.parentElement ?? shadowHost(node?.getRootNode());
// The same step through the tree as rendered: a node slotted into a shadow tree renders
// inside its slot, so the slot is where it is scrolled and ordered, not its light parent.
export const renderedParent = (node) => node?.assignedSlot ?? upFrom(node);

// Which layer a node stands in — the runtime's chrome, a declared label, or the
// document — is asked by every reading that climbs out of a widget, so it is answered
// here, beside the climb, where geometry.js and widget-elements.js can ask it without
// importing the passage readings back.
// Is `node` inside `root`, or `root` itself? `Element.contains` stops at a shadow
// boundary and these readings walk through one, so the climb is the same one
// `closestAcross` makes. The boundary decides whether a quote is found at all: a section
// holding an x-shadow widget does not `contains` the words that widget renders, so
// narrowing a search to that section threw away every candidate inside it and the
// passage resolved to nothing — the anchor captured, the mark never painted.
export const under = (node, root) => {
  for (let a = node; a; a = a.parentNode ?? shadowHost(a)) if (a === root) return true;
  return false;
};

// What stands for `node` in the tree `root` roots (a Document or a ShadowRoot): the node
// itself when it is in that tree, else the host of the shadow tree holding it, climbed
// out until one is. Null when none is: a detached node, or one outside `root`
// altogether. A shadow tree renders where its host stands, so order and range
// questions, which the platform answers only within one tree, are asked of this.
export const hostIn = (node, root) => {
  let at = node;
  while (at && at.getRootNode() !== root) at = shadowHost(at.getRootNode());
  return at;
};

// The chrome over a node, read within one frame: above the frame it is nobody's, and with
// no frame at all it is the document's own reading, unchanged.
export const overIn = (el, selector, frame) => {
  const near = el.closest(selector);
  return near && (!frame || under(near, frame)) ? near : null;
};
// A label a widget declared as the page speaking (relabel), which the anchor pass reads
// over the chrome it sits in.
export const SAID = "[data-lf-said]";
// The pair `uiInside` weighs, the nearer deciding. The passage walk reads the same pair one
// element at a time on its way down (passages.js, `chromeMark`).
export const UI_MARKS = `.lf-ui, ${SAID}`;
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
  const near = el && overIn(el, UI_MARKS, within);
  return Boolean(near) && !near.matches(SAID);
};
export const inUi = (node) =>
  uiInside(node?.nodeType === 1 ? node : node?.parentElement, null);

// The layer's rules for shadow trees: every root's shadow.css, above adopted defaults,
// followed by semantic state.css (layer.py's `composed_sheets`). Read from the layer
// rather than written here so a project override travels with the widget, and fetched
// during upgrade so the stage below stays synchronous for its callers.
export let shadowRules = "";
// Every legitimate page shadow tree is built here, so repeat the generated-interface
// boundary and transition suppression inside it. The shadow's ordinary contents paint
// immediately and its generated interface paints after upgrade, on the same boundaries
// as authored and generated light DOM.
export const SHADOW_STARTUP_CSS = `
@layer {
  @media screen {
    :host-context(body:not([data-lf-presented])) *,
    :host-context(body:not([data-lf-presented])) *::before,
    :host-context(body:not([data-lf-presented])) *::after {
      transition: none !important;
    }
    :host-context(body:not([data-lf-upgraded])) .lf-ui {
      visibility: hidden !important;
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
  const { runtimeResource } = await import("./context.js");
  const response = await fetch(runtimeResource("/shadow.css"));
  if (!response.ok)
    throw new Error(`leaf: shadow.css failed to load (${response.status})`);
  shadowRules = await response.text();
}
