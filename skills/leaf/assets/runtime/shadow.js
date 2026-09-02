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
// document's main gate cannot hide a dialog promoted out of an x-shadow widget. Every
// legitimate page shadow tree is built here; put the same subtree boundary inside it,
// in an anonymous first layer so later widget stylesheet rules cannot outrank it. The
// selector is already universal for that boundary, so it also withholds inner
// transitions until presentation.
const SHADOW_PRESENTATION_CSS = `
@layer {
  @media screen {
    :host-context(body:not([data-lf-presented])) *,
    :host-context(body:not([data-lf-presented])) *::before,
    :host-context(body:not([data-lf-presented])) *::after,
    :host-context(body:not([data-lf-presented])) *::backdrop {
      visibility: hidden !important;
      opacity: 0 !important;
      transition: none !important;
      interactivity: inert !important;
      pointer-events: none !important;
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

/* A marked passage is painted, not wrapped (see paintAnchors), so its rules reach it
   through the highlight registry — which styles glyphs, so the underline stands in for
   a border. The active visual is an element paint from the same pass. Both are stated
   once and installed twice: in the document and in every declared shadow root, where
   document rules cannot reach.

   Every name here carries an ink line, and the wash alone is never the mark. The washes
   are what the hue affords rather than what a floor asks: --mark composites to 1.13:1
   over the light paper and 1.34:1 over the dark, and --dfd1ed cannot reach 1.5:1 against
   --paper at any alpha at all — opaque it stands at 1.38:1. So what the reader sees a
   mark by is the line, at 9.0:1 light and 6.2:1 dark, exactly as the element anchors
   next door are seen by their hairline (.lf-mark-el, chrome-style.js). The wash then
   only has to separate one mark from another, which is a job it can do at 1.1:1.

   lf-react was the one name with no line, and it was the faintest wash of the set: a
   reacted passage stood at 1.08:1 over the light paper, which is a mark nobody sees.
   Dashed against the comment's solid, the pair the element anchors already draw
   (.lf-mark-el solid, .lf-react-el dashed) — same relation, said on glyphs. */
export const MARK_RULES = `
  ::highlight(lf-mark) { background-color: var(--mark);
    text-decoration: underline 2px solid var(--mark-ink); text-underline-offset: 3px; }
  ::highlight(lf-mark-hover) { background-color: var(--mark-hover); }
  ::highlight(lf-mark-here) {
    background-color: var(--mark-strong);
    text-decoration: underline 2px solid var(--accent); text-underline-offset: 3px; }
  ::highlight(lf-pending) { background-color: color-mix(in srgb, var(--accent) 20%, transparent);
    text-decoration: underline 2px solid var(--accent); text-underline-offset: 3px; }
  ::highlight(lf-react) { background-color: var(--react);
    text-decoration: underline 2px dashed var(--mark-ink); text-underline-offset: 3px; }
  .lf-action-target { outline: 1px solid var(--accent); outline-offset: -1px;
    cursor: pointer; }`;

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

export function createShadowStage(watchDisclosures, watchExternalLinks) {
  let markSheet;
  publishedShadowStage = function stageShadow(host, nodes) {
    if (!markSheet) {
      markSheet = new CSSStyleSheet();
      markSheet.replaceSync(MARK_RULES);
    }
    // serializable, because a copy is rendered DOM with the scripts dropped and a shadow
    // root is in no element's outerHTML: exported without this, a diff leaves an empty
    // element where its lines were, which is the one medium that cannot be re-rendered
    // later. With it, `version export` writes a declarative <template shadowrootmode>
    // the browser rebuilds on open, with nothing running.
    const root =
      host.shadowRoot ?? host.attachShadow({ mode: "open", serializable: true });
    root.adoptedStyleSheets = [markSheet];
    // A root is the one place the key line's watch cannot reach on its own: a `toggle`
    // from inside one is not composed, and a MutationObserver does not cross the
    // boundary either.
    watchDisclosures(root);
    const style = document.createElement("style");
    const presentationRules = document.documentElement.hasAttribute("data-lf-eager")
      ? ""
      : SHADOW_PRESENTATION_CSS;
    style.textContent = presentationRules + shadowRules;
    root.replaceChildren(style, ...nodes);
    watchExternalLinks(root);
    return root;
  };
}
