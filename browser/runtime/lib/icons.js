/* Lit templates of Leaf's icons and of the actions that show them (icon-paths.js, which
   also draws either as a plain element). */

import { html, unsafeSVG } from "/vendor/lit.js";

import { actionIcon, iconMarkup } from "./icon-paths.js";

/** A Lit icon template; a parent refresh keeps its SVG and rewrites only a changed icon.
 * @param {Parameters<typeof iconMarkup>[0]} icon */
export function iconTemplate(icon, className = "lf-margin-entry-icon") {
  return html`<svg
    viewBox="0 0 16 16"
    focusable="false"
    aria-hidden="true"
    class=${className}
    data-lf-icon=${icon}
  >
    ${unsafeSVG(iconMarkup(icon))}
  </svg>`;
}

/** The template of `action`'s symbol (icon-paths.js, `ACTIONS`) where it is not a
    press's whole face, such as a menu row's icon or the second of two symbols a press
    swaps by CSS. A press that shows one symbol takes it and its name together, from a
    role or `nameAction` (controls.js). */
/** @param {Parameters<typeof actionIcon>[0]} action @param {string} [className] */
export const actionTemplate = (action, className) =>
  iconTemplate(actionIcon(action), className);
