/* The shared chrome root. leaf.js owns assembly and cross-owner wiring at boot. */

// The one scope root for the chrome's private rules: they match nothing outside this
// container. A div, not a lf-* element — the render gate reads a lf-* ancestor as
// "inside a widget", and the runtime's layer is inside none.
export const chromeRoot = document.createElement("div");
chromeRoot.className = "lf-chrome";
