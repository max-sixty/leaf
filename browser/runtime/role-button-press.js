/* A button's keys for an element Leaf offers as a button without being one: a span
 * with `role="button"` and `data-lf-offer="button"`, such as a selectable offer
 * (element-markers.js), whose words must stay selectable, or a margin reading entry
 * (annotation-overlay/margin-projection.js), which turns between a press and a status
 * in place.
 *
 * The browser gives such a span no keys, so this module gives it a button's: Enter
 * presses it on keydown, and Space on keyup, its keydown kept from scrolling the page.
 * Only a press on the element itself, with no modifier; a repeat presses nothing more,
 * and neither does a press on one marked `aria-disabled="true"`, as on a disabled
 * button.
 *
 * It is the press's default action rather than a handler of the element's own: one
 * listener for every such element, on the window, so it hears a key after every
 * listener on the document and the element, and presses only where none of them
 * prevented the key's default. So a command bound to the same key on the element
 * replaces the press, as it would a native button's. Leaf's dispatcher, which listens
 * on the document, prevents and stops a key it runs, except for a `native` row, which
 * runs and leaves the default; no `native` row binds Enter or Space. A listener on the
 * element would press first, and a page whose widget still binds the press itself
 * would press twice. One gap is accepted: a listener that stops the key's propagation
 * without preventing its default silences the press, where a native button would still
 * activate.
 *
 * It loads in any document, so the press works on a page without Leaf, and the
 * dispatcher counts it as native activation (keyboard/text-entry.js). */

export const ROLE_BUTTON_OFFER = '[role="button"][data-lf-offer="button"]:not(button)';

const offerPressed = (ev) => {
  const target = ev.composedPath()[0];
  return target instanceof HTMLElement &&
    target.matches(ROLE_BUTTON_OFFER) &&
    target.getAttribute("aria-disabled") !== "true" &&
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
