/* The shared chrome homes. leaf.js owns assembly and cross-owner wiring at boot.
 * Document-attached annotations are inserted before the permanent foreground:
 * a CSS anchor can position only a box laid out after the target it names. Keeping
 * this order at insertion lets foreground chips anchor to newly created margin rows
 * without moving the foreground's live editors or embedded browsing contexts. */

// The permanent home of the chrome's private rules, mounted after `body`, where it
// stacks over every box the page writes (base.css). A native modal seated inside
// an authored popover carries another instance of this styling scope for its opening
// (keyboard/layer-stack.js). A div, not a lf-* element — the render gate reads an
// lf-* ancestor as "inside a widget", and the runtime's layer is inside none.
export const chromeRoot = document.createElement("div");
chromeRoot.className = "lf-chrome";

// The foreground: the floating panel, the hint layers and the chrome's own dialogs and
// popovers, over the margin's rows. A plain box, which the accessibility tree exposes
// as generic: the native layers opened inside it stand in the top layer whatever holds
// them, and their opening order is the browser's. Not an open nonmodal dialog: that
// adds nothing to the order, and exposes an unnamed dialog around the panel, since ARIA
// ignores `role="presentation"` on a focusable element and allows a dialog no generic
// role. `tabindex="-1"` keeps it out of the Tab order while a press between the
// panel's controls still focuses it rather than dropping focus to the body.
export const chromeForeground = document.createElement("div");
chromeForeground.className = "lf-ui lf-foreground";
chromeForeground.tabIndex = -1;
