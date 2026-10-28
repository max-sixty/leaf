/* The element that draws one of the layer's icons (icon-paths.js), and its Lit template.
   A base module: composing/selection.js builds its response button with an icon as it
   evaluates. */

import { html } from "/runtime/framework.js";

import { actionIcon, iconMarkup } from "./icon-paths.js";

export { actionElement, iconElement, showAction } from "./icon-paths.js";

/** A Lit icon template; a parent refresh keeps its SVG and rewrites only a changed icon. */
export function iconTemplate(icon, className = "lf-margin-entry-icon") {
  return html`<svg
    viewBox="0 0 16 16"
    focusable="false"
    aria-hidden="true"
    class=${className}
    data-lf-icon=${icon}
    .innerHTML=${iconMarkup(icon)}
  ></svg>`;
}

/** The template of `action`'s symbol (icon-paths.js, `ACTIONS`), for a press whose
    face no role draws, such as the floating panel's. */
export const actionTemplate = (action, className) =>
  iconTemplate(actionIcon(action), className);
