/* The Lit-rendered face inside the banner shelf's stable native approval button. The
 * shelf owns the button's identity and position; this owner paints one complete approval
 * reading without replacing the control a user may be holding.
 *
 * A reading that refuses the press says why (`reason`), and the control stays where the
 * user can ask it: `aria-disabled` rather than native `disabled`, so Tab still reaches it
 * and a screen reader reads the reason as its description, and a press is refused by the
 * banner's handler, which shows the reason in the status line. Native `disabled` left
 * the reason in `title` alone, which a keyboard user never reached, since Tab skipped the
 * control, and a finger never sees. */
import { LitElement, html } from "../vendor/browser-runtime.js";

const TAG = "leaf-banner-approval-face";
const INITIAL = Object.freeze({
  reason: "Approval waits until this page has read its current state",
  text: "Approve version",
  title: "Approval waits until this page has read its current state",
});

class BannerApprovalFace extends LitElement {
  static properties = { model: { attribute: false } };

  constructor() {
    super();
    this.model = INITIAL;
  }

  createRenderRoot() {
    return this;
  }

  present(model) {
    this.model = model;
    // Approval availability guards a press, so commit it in this call rather than leave
    // a stale enabled control until Lit's scheduled microtask. A detached initial face
    // paints when its stable button joins the banner.
    if (this.isConnected) this.performUpdate();
  }

  // Whether a press is refused, and the words that say why.
  get reason() {
    return this.model.reason;
  }

  updated() {
    const control = this.parentElement;
    if (!(control instanceof HTMLButtonElement)) return;
    const { reason, title } = this.model;
    if (reason) {
      control.setAttribute("aria-disabled", "true");
      control.setAttribute("aria-description", reason);
    } else {
      control.removeAttribute("aria-disabled");
      control.removeAttribute("aria-description");
    }
    control.title = title;
  }

  render() {
    return html`${this.model.text}`;
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, BannerApprovalFace);

export function createBannerApprovalFace(control) {
  const face = document.createElement(TAG);
  face.style.display = "contents";
  control.append(face);
  return face;
}
