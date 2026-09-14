/* The Lit-rendered face inside the banner shelf's stable native approval button. The
 * shelf owns the button's identity and position; this owner paints one complete approval
 * reading without replacing the control a reader may be holding. */
import { LitElement, html } from "../vendor/browser-runtime.js";

const TAG = "leaf-banner-approval-face";
const INITIAL = Object.freeze({
  disabled: true,
  text: "Approve version",
  title: "Approve this work; the page stays open for follow-up",
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

  updated() {
    const control = this.parentElement;
    if (!(control instanceof HTMLButtonElement)) return;
    control.disabled = this.model.disabled;
    control.title = this.model.title;
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
