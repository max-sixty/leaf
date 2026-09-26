/* Where the user stands: the page node a focused node stands at, one reading every
   feature takes (glossary, Standing target).

   A node on the page stands at itself. So does a node inside any Ask of the inventory,
   answered or not, wherever it is drawn: an Ask frozen into a reply is where a user
   working it is, never the page Ask its thread is about. Other chrome stands at the page
   target it shows, as each side's owner declares (`declareSide`): the margin for its
   cluster controls, the thread card, and a thread in the Threads panel; the Asks tray
   for its rows. A side's answer drawn in the chrome itself, such as a margin control on
   a widget frozen into a reply, stands only where an Ask holds it. Chrome no side
   claims — the banner, a tray's own controls, the panel's list — stands nowhere, and a
   press made from it means the page whole.

   Each feature takes what it needs from that place by its own rule: the Ask view the
   innermost Ask holding it, `c` and `e` the addressable element, the walks its document
   position. The chrome stands over the page rather than in it and is appended after it,
   so a chrome node measured as a place would put the user behind every Ask and thread
   there is; no reader measures from one that does not stand in an Ask. */
import { documentFocused } from "./keyboard/scopes.js";
import { elementById, inChrome } from "./passages.js";
import { allAsks } from "./asks/model.js";
import { under } from "./shadow.js";

const sides = [];

// A chrome owner's reading of the page target a node inside its chrome shows, or null.
export function declareSide(bridge) {
  sides.push(bridge);
}

// The innermost of `asks` whose element is or holds `node`. The list is in document
// order, so the last container in it is the nearest.
export const askHolding = (asks, node) =>
  (node &&
    asks.findLast((ask) => {
      const at = elementById(ask.id);
      return at && (at === node || under(node, at));
    })) ??
  null;

export function placeOf(node) {
  const at = node?.nodeType === 1 ? node : node?.parentElement;
  if (!at || at === document.body) return null;
  if (!inChrome(at) || askHolding(allAsks(), at)) return at;
  for (const side of sides) {
    const place = side(at);
    if (place) return inChrome(place) && !askHolding(allAsks(), place) ? null : place;
  }
  return null;
}

// Where the user stands now: where focus stands, or else the end of the selection, a
// caret a click left included, since a click that placed one is the user saying where
// they are.
export const standingPlace = () =>
  placeOf(documentFocused()) ?? placeOf(getSelection()?.focusNode);

// The Ask the user stands in, answered or not: where letting go lands, and the extent
// of what `c` counts as the element they stand at.
export function heldAsk() {
  const ask = askHolding(allAsks(), placeOf(documentFocused()));
  return ask ? elementById(ask.id) : null;
}
