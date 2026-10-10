/* Stable Question-view chrome and selectors.
 *
 * These values are safe for composition and standing interpretation to import without
 * evaluating the Question controller or any of its navigation and command dependencies.
 */

// Focusable offered chrome: native buttons carry their tab stop implicitly, while the
// selectable-control exception states one explicitly.
export const QUESTION_CONTROL = ":is(button[data-lf-offer], [data-lf-offer][tabindex])";
