/* The generated owner of the banner's complete status surface.
 *
 * `banner.js` derives one immutable reading. This synchronous light-DOM Lit view
 * retains the native disclosure controls while placing them in the ordinary and
 * publication layouts; no outside code writes or reparents anything inside it.
 *
 * The agent's Tasks count (`queues`) is the view's second box, which the banner places
 * beside the status rather than inside it, so the banner can give it whichever row
 * leaves the sentence its room (chrome.css). The box is reserved for the count it
 * usually reaches (`queuesWidest`), so the sentence changing never carries it and its
 * changing moves nothing. A count past that widens the box once, and it keeps the width
 * while the page is open. The count is a press, one of the Questions panel's doors
 * (drawers.js wires it), so the panel listing those tasks is one press from where they
 * are counted.
 *
 * A passing notice shares the words' box (`presentNotice`), and on a phone stands over
 * them while it lasts; elsewhere the bottom status shows it (chrome.css,
 * `--lf-notice-seat`).
 */
import { html, nothing, render } from "../vendor/browser-runtime.js";
import { el, reserve } from "./widget-elements.js";
import { keeps, keepsText } from "./keeps.js";

// `lf-*` is reserved for authored widgets. This is generated runtime chrome.
const TAG = "leaf-banner-status";
const website = document.querySelector("script[data-lf-server][data-lf-release]");
const connecting = website ? "Connecting to the Leaf website…" : "Connecting…";
const INITIAL = Object.freeze({
  tone: "",
  summary: connecting,
  queues: "",
  queuesWidest: "",
  explanation: website
    ? "Loading this website page. Website examples can take longer to connect than a usual Leaf page."
    : connecting,
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
  // A passing notice, which takes the words' place on a phone (chrome.css,
  // `--lf-notice-seat`). It stands over them in one box, so the press and its accessible
  // name stay the status's; the live region has already spoken the notice.
  #notice = el("span", "lf-status-notice");
  #words = el("span", "lf-status-words");

  constructor() {
    super();
    this.#notice.setAttribute("aria-hidden", "true");
    this.#words.append(this.#text, this.#notice);
    this.#button.type = "button";
    this.#button.setAttribute("aria-expanded", "false");
    this.#button.setAttribute("aria-describedby", "lf-status-detail");
    this.#queues.type = "button";
    this.#queues.title = "Show or hide the agent's tasks and your questions";
    this.#queues.setAttribute("aria-controls", "lf-queue");
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

  // The notice keeps its words after it fades, so the stylesheet alone decides what shows.
  presentNotice({ message, visible }) {
    keepsText(this.#notice, message);
    keeps(this, "data-lf-notice", visible ? "" : null);
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
      render(html`${this.#dot}${this.#words}${this.#detail}`, this);
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
    render(html`${this.#dot}${this.#words}`, this.#button);
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
