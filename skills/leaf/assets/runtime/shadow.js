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

// The theme's rules for shadow trees, sliced out once at load (see the markers in
// theme.css). Every layer may contribute a block; concatenating them in theme order
// preserves the same cascade inside a declared shadow root as in the document. Read
// from the theme rather than written here so a project override travels with the widget,
// and fetched during upgrade so the stage below stays synchronous for its callers.
let shadowRules = "";
const SHADOW_CSS = /\/\* lf-shadow:start \*\/([\s\S]*?)\/\* lf-shadow:end \*\//g;
// A top-layer element no longer composites through its light/shadow ancestors, so the
// document's rules cannot withhold a dialog or popover promoted out of an x-shadow
// widget. Every legitimate page shadow tree is built here; repeat that narrow boundary
// inside it, together with transition suppression. The shadow's ordinary contents still
// paint before presentation, just like authored light DOM.
const SHADOW_STARTUP_CSS = `
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

// The stage an x-shadow widget renders into. A module never calls attachShadow itself,
// because the marks the runtime paints come from a registry that is the document's while
// the ::highlight() rules styling them are not — they reach no shadow tree. A root
// attached anywhere else would show words the reader can select and no mark could ever
// paint, which is the one failure this whole capability exists to avoid.
//
// The two sheets arrive differently on purpose. The theme's rules go in as a <style>
// element, because that is markup and a copy keeps it; the marks are adopted, because
// they are the live comment layer, which a copy drops with the rest of the chrome — an
// adopted sheet is in no element's markup and would not survive the export either way.
//
// It takes the nodes rather than handing back a root to fill, so the style cannot be
// left out: a module that wrote its own children would replace the one thing holding its
// look, and it would look right in exactly the session where someone remembered. Same
// reasoning as renderSaid — a rule each widget has to remember is a rule that gets
// forgotten, and the forgetting is invisible until a page ships without it.
let publishedShadowStage;
export const shadowStage = (...args) => publishedShadowStage(...args);

export function createShadowStage(watchDisclosures, watchExternalLinks, setChildren) {
  publishedShadowStage = function stageShadow(host, nodes) {
    // serializable, because a copy is rendered DOM with the scripts dropped and a shadow
    // root is in no element's outerHTML: exported without this, a diff leaves an empty
    // element where its lines were, which is the one medium that cannot be re-rendered
    // later. With it, `version export` writes a declarative <template shadowrootmode>
    // the browser rebuilds on open, with nothing running.
    const root =
      host.shadowRoot ?? host.attachShadow({ mode: "open", serializable: true });
    root.adoptedStyleSheets = [marksSheet];
    // A root is the one place the key line's watch cannot reach on its own: a `toggle`
    // from inside one is not composed, and a MutationObserver does not cross the
    // boundary either.
    watchDisclosures(root);
    const style = document.createElement("style");
    style.textContent = SHADOW_STARTUP_CSS + shadowRules;
    // Fragment hydration can add a sheet while the reader uses an existing control.
    // Keep retained nodes connected, preserving their focus and widget lifecycle.
    setChildren(root, [style, ...nodes]);
    watchExternalLinks(root);
    return root;
  };
}
