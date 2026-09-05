/* The stage an x-shadow widget renders into. A module never calls attachShadow itself,
   because the marks the runtime paints come from a registry that is the document's while
   the ::highlight() rules styling them are not — they reach no shadow tree. A root
   attached anywhere else would show words the reader can select and no mark could ever
   paint, which is the one failure this whole capability exists to avoid.

   The two sheets arrive differently on purpose. The theme's rules go in as a <style>
   element, because that is markup and a copy keeps it; the marks are adopted, because
   they are the live comment layer, which a copy drops with the rest of the chrome — an
   adopted sheet is in no element's markup and would not survive the export either way.

   It takes the nodes rather than handing back a root to fill, so the style cannot be
   left out: a module that wrote its own children would replace the one thing holding its
   look, and it would look right in exactly the session where someone remembered. Same
   reasoning as renderSaid — a rule each widget has to remember is a rule that gets
   forgotten, and the forgetting is invisible until a page ships without it. */
import { marksSheet, SHADOW_STARTUP_CSS, shadowRules } from "./shadow.js";
import { watchDisclosures } from "./keyboard/disclosure.js";
import { setChildren } from "./conversation/reconcile.js";
import { watchExternalLinks } from "./presentation.js";

export function shadowStage(host, nodes) {
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
}
