/* The shared chrome homes. leaf.js owns assembly and cross-owner wiring at boot.
 * Document-attached annotations are inserted before the permanent native foreground:
 * a CSS anchor can position only a box laid out after the target it names. Keeping
 * this order at insertion lets foreground chips anchor to newly created margin rows
 * without moving the foreground's live editors or embedded browsing contexts. */

// The one scope root for the chrome's private rules: they match nothing outside this
// container. A div, not a lf-* element — the render gate reads a lf-* ancestor as
// "inside a widget", and the runtime's layer is inside none.
export const chromeRoot = document.createElement("div");
chromeRoot.className = "lf-chrome";

export const chromeForeground = document.createElement("dialog");
