/* The shared chrome homes. leaf.js owns assembly and cross-owner wiring at boot.
 * Document-attached annotations are inserted before the permanent native foreground:
 * a CSS anchor can position only a box laid out after the target it names. Keeping
 * this order at insertion lets foreground chips anchor to newly created margin rows
 * without moving the foreground's live editors or embedded browsing contexts. */

// The permanent home of the chrome's private rules. A native modal seated inside
// an authored popover carries another instance of this styling scope for its opening
// (keyboard/layer-stack.js). A div, not a lf-* element — the render gate reads an
// lf-* ancestor as "inside a widget", and the runtime's layer is inside none.
export const chromeRoot = document.createElement("div");
chromeRoot.className = "lf-chrome";

// The foreground: the floating panel, the hint layers and the chrome's own dialogs and
// popovers, over the margin's rows. It is an open, nonmodal dialog, so the native layers
// opened inside it join the browser's own layer order. Opened by its markup rather than
// `show()`, it performs no dialog focusing steps, so mounting the chrome borrows no
// author's focus.
export const chromeForeground = document.createElement("dialog");
chromeForeground.className = "lf-ui lf-foreground";
chromeForeground.setAttribute("open", "");
chromeForeground.setAttribute("role", "presentation");
