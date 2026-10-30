/* A button's keys for a selectable offer with a button's role (element-markers.js).
 *
 * The offer is a span so its words stay selectable, and the browser gives a span no
 * keys, so this module gives it a button's: Enter presses it on keydown, and Space on
 * keyup, its keydown kept from scrolling the page. Only a press on the offer itself,
 * with no modifier; a repeat presses nothing more.
 *
 * It is the press's default action rather than a handler of the offer's own: one
 * listener for every offer, on the window, so it hears a key after every listener on
 * the document and the offer, and presses only where none of them prevented the key's
 * default. So a command bound to the same key on the offer replaces the press, as it
 * would a native button's: Leaf's dispatcher, which listens on the document, prevents
 * and stops a key it runs. A listener on the offer would press first, and a page whose
 * widget still binds the press itself would press twice. It loads in any document, so
 * the offer works on a page without Leaf, and the dispatcher counts it as native
 * activation (keyboard/text-entry.js). */

export const SELECTABLE_BUTTON = '[role="button"][data-lf-offer="button"]:not(button)';

const offerPressed = (ev) => {
  const target = ev.composedPath()[0];
  return target instanceof HTMLElement &&
    target.matches(SELECTABLE_BUTTON) &&
    !(ev.altKey || ev.ctrlKey || ev.metaKey || ev.shiftKey)
    ? target
    : null;
};
let spaceOn = null;
addEventListener("keydown", (ev) => {
  const offer = offerPressed(ev);
  if (!offer || ev.defaultPrevented || ev.isComposing) return;
  if (ev.key === "Enter") {
    if (!ev.repeat) offer.click();
  } else if (ev.key === " ") {
    ev.preventDefault();
    spaceOn = offer;
  }
});
addEventListener("keyup", (ev) => {
  if (ev.key !== " ") return;
  const offer = spaceOn;
  spaceOn = null;
  if (offer && offer === offerPressed(ev) && !ev.defaultPrevented) offer.click();
});
