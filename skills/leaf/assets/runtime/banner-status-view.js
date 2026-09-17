/* The generated owner of the banner's complete status surface.
 *
 * `banner.js` derives one immutable reading. This synchronous light-DOM Lit view
 * retains the native disclosure controls while placing them in the ordinary and
 * publication layouts; no outside code writes or reparents anything inside it.
 */
import { html, nothing, render } from "../vendor/browser-runtime.js";
import { anchorSurface } from "./anchoring.js";
import { el } from "./widget-elements.js";

// `lf-*` is reserved for authored widgets. This is generated runtime chrome.
const TAG = "leaf-banner-status";
const INITIAL = Object.freeze({
  tone: "",
  summary: "Connecting…",
  explanation: "Connecting…",
  publication: null,
});

class BannerStatusView extends HTMLElement {
  #button = el("button", "lf-status-button");
  #detail = el("div", "lf-ui lf-status-detail");
  #dot = el("span", "lf-dot");
  #onToggle = null;
  #text = el("span", "lf-status-text");

  constructor() {
    super();
    this.#button.type = "button";
    this.#button.setAttribute("aria-expanded", "false");
    this.#button.setAttribute("aria-describedby", "lf-status-detail");
    this.#detail.id = "lf-status-detail";
    this.#detail.tabIndex = -1;
    this.#detail.setAttribute("popover", "auto");
    this.#detail.setAttribute("role", "group");
    this.#detail.setAttribute("aria-label", "Page status");
    this.#button.popoverTargetElement = this.#detail;
    this.#detail.lfInvoker = this.#button;
    anchorSurface(this.#detail, { anchor: () => this.#button, gap: 8 });
    this.#detail.addEventListener("toggle", (event) => {
      const open = event.newState === "open";
      this.#button.setAttribute("aria-expanded", String(open));
      // Focus the scrollable explanation so keyboard readers can reach long details.
      if (open && document.activeElement === this.#button)
        this.#detail.focus({ preventScroll: true });
      this.#onToggle?.();
    });
  }

  configure({ onToggle }) {
    this.#onToggle = onToggle;
    this.present(INITIAL);
  }

  get dot() {
    return this.#dot;
  }

  present(model) {
    if (
      !Object.isFrozen(model) ||
      (model.publication && !Object.isFrozen(model.publication))
    )
      throw new Error("Banner status presentation models must be immutable");
    if (model.publication && this.#detail.matches(":popover-open"))
      this.#detail.hidePopover();

    this.#dot.className = "lf-dot" + (model.tone ? " " + model.tone : "");
    this.#button.title = model.explanation;
    this.#text.title = model.explanation;
    render(model.explanation, this.#detail);

    if (model.publication) {
      // Relinquish the ordinary Lit seat before its retained nodes move into the
      // publication row. Returning to it can then claim them afresh rather than
      // trusting a part whose nodes another container has moved.
      render(nothing, this.#button);
      render(html`${this.#dot}${this.#text}${this.#detail}`, this);
      render(
        html`<span class="lf-publication-copy">${model.publication.copy}</span
          ><a class="lf-publication-install" href=${model.publication.installUrl}
            >${model.publication.install}</a
          >`,
        this.#text,
      );
      return;
    }

    render(html`${this.#button}${this.#detail}`, this);
    render(html`${this.#dot}${this.#text}`, this.#button);
    render(model.summary, this.#text);
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, BannerStatusView);

export function createBannerStatusView(onToggle) {
  const view = document.createElement(TAG);
  view.className = "lf-banner-status";
  view.configure({ onToggle });
  return view;
}
