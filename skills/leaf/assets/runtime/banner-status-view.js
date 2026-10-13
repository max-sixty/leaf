/* The generated owner of the banner's complete status surface.
 *
 * `banner.js` derives one immutable reading. This synchronous light-DOM Lit view
 * paints the ordinary and publication layouts from one template; no outside code
 * writes or reparents anything inside it. The ordinary layout is a native disclosure:
 * the status is a `popovertarget` button over its explanation, so the browser alone
 * keeps and announces whether it is open. A publication has no explanation to open,
 * so its layout renders neither, and removing an open explanation closes it.
 *
 * The agent's Tasks count (`queues`) is the view's second box, which the banner places
 * beside the status rather than inside it, so the banner can give it whichever row
 * leaves the sentence its room (chrome.css). The box is reserved for the count it
 * usually reaches (`queuesWidest`), so the sentence changing never carries it and its
 * changing moves nothing. A count past that widens the box once, and it keeps the width
 * while the page is open. The count is a press, one of the On panel's doors
 * (drawers.js wires it), so the panel listing those tasks is one press from where they
 * are counted.
 *
 * A passing notice shares the words' box (`presentNotice`), and on a phone stands over
 * them while it lasts; elsewhere the bottom status shows it, or in the floating panel
 * its empty field does (chrome.css and floating-panel.css, `--lf-notice-seat`).
 */
import {
  html,
  nothing,
  render,
  classMap,
  createRef,
  ref,
} from "../vendor/browser-runtime.js";
import { el, reserve } from "./widget-elements.js";
import { keeps } from "./keeps.js";
import { focusDestination, focused } from "./focus.js";
import { agentName } from "./semantic-state.js";

// `lf-*` is reserved for authored widgets. This is generated runtime chrome.
const TAG = "leaf-banner-status";

class BannerStatusView extends HTMLElement {
  #button = createRef();
  #detail = createRef();
  #dot = createRef();
  #onToggle = null;
  #notice = { message: "", visible: false };
  #model = null;
  #queues = el("button", "lf-status-queues");
  #queuesWidest = "";
  #queuesReserved = "";

  constructor() {
    super();
    this.#queues.type = "button";
    this.#queues.setAttribute("aria-controls", "lf-queue");
  }

  #toggled = (event) => {
    // Focus the scrollable explanation so keyboard users can reach long details.
    if (event.newState === "open" && focused() === this.#button.value)
      focusDestination(this.#detail.value, "move");
    this.#onToggle?.();
  };

  configure({ onToggle, initial }) {
    this.#onToggle = onToggle;
    this.present(initial);
  }

  get dot() {
    return this.#dot.value;
  }

  get queues() {
    return this.#queues;
  }

  // The notice keeps its words after it fades, so the stylesheet alone decides what shows.
  presentNotice(notice) {
    this.#notice = notice;
    keeps(this, "data-lf-notice", notice.visible ? "" : null);
    this.#paint();
  }

  present(model) {
    this.#model = model;
    this.#paint();
    render(model.queues, this.#queues);
    keeps(this.#queues, "title", `Show or hide what's on me and on ${agentName()}`);
    this.#queues.toggleAttribute("hidden", !model.queues);
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

  #paint() {
    const model = this.#model;
    const publication = model.publication;
    const dot = html`<span
      class=${classMap({ "lf-dot": true, [model.tone]: Boolean(model.tone) })}
      ${ref(this.#dot)}
    ></span>`;
    const words = (text) =>
      html`<span class="lf-status-words"
        ><span class="lf-status-text" title=${model.explanation}>${text}</span
        ><span class="lf-status-notice" aria-hidden="true"
          >${this.#notice.message}</span
        ></span
      >`;
    const summary = publication
      ? html`<span class="lf-publication-copy">${publication.copy}</span>${
            publication.examplesUrl
              ? html`<a class="lf-publication-link" href=${publication.examplesUrl}
                  >${publication.examples + " "}</a
                >`
              : nothing
          }<a class="lf-publication-install" href=${publication.installUrl}
            >${publication.install}</a
          >`
      : model.summary;
    const status = html`${dot}${words(summary)}`;
    render(
      publication
        ? status
        : html`<button
              type="button"
              class="lf-status-button"
              title=${model.explanation}
              aria-describedby="lf-status-detail"
              popovertarget="lf-status-detail"
              ${ref(this.#button)}
            >
              ${status}
            </button>
            <div
              id="lf-status-detail"
              class="lf-ui lf-status-detail"
              tabindex="-1"
              popover="auto"
              role="group"
              aria-label="Page status"
              @toggle=${this.#toggled}
              ${ref(this.#detail)}
            >
              ${model.explanation}
            </div>`,
      this,
    );
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, BannerStatusView);

export function createBannerStatusView(onToggle, initial) {
  const view = document.createElement(TAG);
  view.className = "lf-banner-status";
  view.configure({ onToggle, initial });
  return view;
}
