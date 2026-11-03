/* Stable obligation-view chrome and selectors.
 *
 * These values are safe for composition and current location interpretation to import without
 * evaluating the obligation controller or any of its navigation and command dependencies.
 */

// Focusable offered chrome: native buttons carry their tab stop implicitly, while the
// selectable-control exception states one explicitly.
export const OBLIGATION_CONTROL =
  ":is(button[data-lf-offer], [data-lf-offer][tabindex])";
// An On card or line in the floating panel that shows an obligation, naming it in
// `data-obligation` and its item in `data-key`. A user on it is on that obligation
// (current-target.js, `currentLocationOrigin`), wherever it stands on the page, if
// anywhere.
export const ON_CARD = ".lf-fp-on-item[data-obligation]";
