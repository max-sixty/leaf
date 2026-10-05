/* The generated owner of the banner's complete status surface.
 *
 * `banner.js` derives one immutable reading. This synchronous light-DOM Lit view
 * retains the native disclosure controls while placing them in the ordinary and
 * publication layouts; no outside code writes or reparents anything inside it.
 *
 * The queue counts (`queues`) are the view's second box, which the banner places
 * beside the status rather than inside it, so the banner can give them whichever row
 * leaves the sentence its room (chrome.css). The box is reserved for the counts they
 * usually reach (`queuesWidest`), so the sentence changing never carries them and their
 * changing moves nothing. Counts past that widen the box once, and it keeps the width
 * while the page is open. The counts are a press, one of the Queue panel's doors
 * (drawers.js wires it), so the panel they count is one press from where they are read.
 */
import { html, nothing, render } from "../vendor/browser-runtime.js";
import { el, reserve } from "./widget-elements.js";
import { keeps } from "./keeps.js";

// `lf-*` is reserved for authored widgets. This is generated runtime chrome.
const TAG = "leaf-banner-status";
const INITIAL = Object.freeze({
  tone: "",
  summary: "Connecting…",
  queues: "",
  queuesWidest: "",
  explanation: "Connecting…",
  publication: null,
});

class BannerStatusView extends HTMLElement {
  #button = el("button", "lf-status-button");
  #detail = el("div", "lf-ui lf-status-detail");
  #dot = el("span", "lf-dot");
  #onToggle = null;
  #queues = el("button", "lf-status-queues");
  #queuesWidest = "";
  #queuesReserved = "";
  #text = el("span", "lf-status-text");

  constructor() {
    super();
    this.#button.type = "button";
    this.#button.setAttribute("aria-expanded", "false");
    this.#button.setAttribute("aria-describedby", "lf-status-detail");
    this.#queues.type = "button";
    this.#queues.title = "Show or hide the Queue panel";
    this.#queues.setAttribute("aria-controls", "lf-queue");
    this.#queues.setAttribute("aria-expanded", "false");
    this.#detail.id = "lf-status-detail";
    this.#detail.tabIndex = -1;
    this.#detail.setAttribute("popover", "auto");
    this.#detail.setAttribute("role", "group");
    this.#detail.setAttribute("aria-label", "Page status");
    this.#button.popoverTargetElement = this.#detail;
    this.#detail.lfInvoker = this.#button;
    this.#detail.addEventListener("toggle", (event) => {
      const open = event.newState === "open";
      keeps(this.#button, "aria-expanded", open);
      // Focus the scrollable explanation so keyboard users can reach long details.
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

  get queues() {
    return this.#queues;
  }

  present(model) {
    if (
      !Object.isFrozen(model) ||
      (model.publication && !Object.isFrozen(model.publication))
    )
      throw new Error("Banner status presentation models must be immutable");
    if (model.publication && this.#detail.matches(":popover-open"))
      this.#detail.hidePopover();

    this.#queues.toggleAttribute("hidden", !model.queues);
    keeps(this.#dot, "class", "lf-dot" + (model.tone ? " " + model.tone : ""));
    keeps(this.#button, "title", model.explanation);
    keeps(this.#text, "title", model.explanation);
    render(model.explanation, this.#detail);

    if (model.publication) {
      // Relinquish the ordinary Lit seat before its retained nodes move into the
      // publication row. Returning to it can then claim them afresh rather than
      // trusting a part whose nodes another container has moved.
      render(nothing, this.#button);
      render(html`${this.#dot}${this.#text}${this.#detail}`, this);
      render(
        html`<span class="lf-publication-copy">${model.publication.copy}</span>${
            model.publication.examplesUrl
              ? html`<a
                  class="lf-publication-link"
                  href=${model.publication.examplesUrl}
                  >${model.publication.examples + " "}</a
                >`
              : nothing
          }<a class="lf-publication-install" href=${model.publication.installUrl}
            >${model.publication.install}</a
          >`,
        this.#text,
      );
      return;
    }

    render(html`${this.#button}${this.#detail}`, this);
    render(html`${this.#dot}${this.#text}`, this.#button);
    render(model.summary, this.#text);
    render(model.queues, this.#queues);
    // The reservation only grows: its digits are tabular, so the longest counts yet
    // shown are the widest, and a box that shrank back would move them on the next.
    if (model.queues) {
      const kept =
        model.queuesWidest === this.#queuesWidest
          ? this.#queuesReserved
          : model.queuesWidest;
      const reserved = model.queues.length > kept.length ? model.queues : kept;
      if (
        model.queuesWidest !== this.#queuesWidest ||
        reserved !== this.#queuesReserved
      ) {
        this.#queuesWidest = model.queuesWidest;
        this.#queuesReserved = reserved;
        reserve(this.#queues, [reserved]);
      }
    }
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, BannerStatusView);

export function createBannerStatusView(onToggle) {
  const view = document.createElement(TAG);
  view.className = "lf-banner-status";
  view.configure({ onToggle });
  return view;
}
