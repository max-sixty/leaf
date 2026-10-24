/* Stable obligation-view chrome and selectors.
 *
 * These values are safe for composition and current location interpretation to import without
 * evaluating the obligation controller or any of its navigation and command dependencies.
 */

// Focusable offered chrome: native buttons carry their tab stop implicitly, while the
// selectable-control exception states one explicitly.
export const OBLIGATION_CONTROL =
  ":is(button[data-lf-offer], [data-lf-offer][tabindex])";
