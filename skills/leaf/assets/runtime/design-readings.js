/* Passive names and constants shared by design mode and its renderers.
 *
 * Command owners receive the live mode query from createDesignMode. These
 * document readings remain directly importable so a message or label renderer never
 * reaches design gestures, composition, panel sync, or page geometry.
 */

import { addressableWord } from "./anchor-resolution.js";

// Kept per tab across document travel and reload, the way the panel's open state is.
export const DESIGN_MODE_KEY = "lf-design-mode";

// The name a design target wears — under the pointer, in the composer, beside its
// thread. A widget is its tag and id, because both are what a fix is written against; a
// page element takes the user's word for its kind.
export function designName(element) {
  const tag = element.tagName.toLowerCase();
  return `${tag.startsWith("lf-") ? tag : addressableWord(element)} · ${element.id}`;
}
