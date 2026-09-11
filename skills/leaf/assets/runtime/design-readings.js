/* Passive names and constants shared by design mode and its renderers.
 *
 * Command owners receive the live mode query from createDesignMode. These
 * document readings remain directly importable so a message or label renderer never
 * reaches design gestures, composition, panel sync, or page geometry.
 */

import { addressableWord } from "./anchor-resolution.js";
import { layerPart } from "./passages.js";

// Kept per tab across document travel and reload, the way the panel's open state is.
export const DESIGN_MODE_KEY = "lf-design-mode";

// How long a name may run where chrome writes one on a line of its own.
export const CONTROL_WORD_CAP = 24;

// The name a design target wears — under the pointer, in the composer, beside its
// thread. A widget is its tag and id, because both are what a fix is written against; a
// page element takes the reader's word for its kind; a runtime part is its name, the id
// minus the runtime's prefix.
export function designName(element) {
  if (layerPart(element)) return element.id.replace(/^lf-/, "").replace(/-/g, " ");
  const tag = element.tagName.toLowerCase();
  return `${tag.startsWith("lf-") ? tag : addressableWord(element)} · ${element.id}`;
}
