/* The Leaves banner control and tray's generated light-DOM list.

   The caller derives one immutable model for the control's presence and words and the
   keyed tray rows. The native control remains the banner shelf and tray owner's stable
   node; a retained face paints inside it. This owner registers each native link's
   command scope once, preserves a surviving link and its focus through reordering, and
   moves focus to a neighbouring link or the tray when the focused page disappears.
   Each assigned reading opens one Leaves presentation region before either face
   schedules an update. A failed update restores both committed faces before the
   coordinator reports and settles the attempt. */
import { html, repeat } from "../vendor/browser-runtime.js";
import {
  attachApplicationPresentation,
  failSoftAfterRetention,
  PresentationRetentionError,
} from "./semantic-state.js";
import { showNews } from "./banner-shelf.js";
import { keys, paintKeys } from "./keyboard/scopes.js";
import { RetainedFace, RowFocus } from "./retained-face.js";

const TAG = "lf-leaves-list";
const FACE_TAG = "lf-leaves-banner-face";
const LINK = "a.lf-others-row";
const EMPTY_ROWS = Object.freeze([]);
const EMPTY_MODEL = Object.freeze({
  offered: false,
  label: "All leaves (0)",
  rows: EMPTY_ROWS,
});

class LeavesBannerFace extends RetainedFace {
  constructor() {
    super(EMPTY_MODEL);
  }

  updated() {
    const control = this.parentElement;
    if (control) showNews(control, this.model.offered);
  }

  render() {
    return html`${this.model.label}`;
  }
}

if (!customElements.get(FACE_TAG)) customElements.define(FACE_TAG, LeavesBannerFace);

const openCommand = Object.freeze([
  Object.freeze({
    id: "leaf.open",
    keys: ["Enter"],
    does: "Open that leaf in a tab",
    line: "open it in a tab",
  }),
]);

const rowBody = (row) => html`
  <div class="lf-others-head">
    <span class=${`lf-dot${row.tone ? ` ${row.tone}` : ""}`}></span>
    <span class="lf-others-title">${row.title}</span>
    ${row.self ? html`<span class="lf-chip">this page</span>` : ""}
  </div>
  <div class="lf-others-line">${row.line}</div>
`;

class LiveLeavesList extends RetainedFace {
  #face = null;
  #focus = new RowFocus(this, {
    rows: LINK,
    key: "href",
    keys: (model) => model.rows.filter((row) => !row.self).map((row) => row.href),
  });
  #generation = 0;
  #handle = null;
  #linksOffered = false;
  #wiredLinks = new WeakSet();

  constructor() {
    super(EMPTY_MODEL);
  }

  connectedCallback() {
    super.connectedCallback();
    this.#handle ??= attachApplicationPresentation("leaves", this);
    void this.present(this.model);
  }

  disconnectedCallback() {
    this.#handle?.disconnect();
    this.#handle = null;
    super.disconnectedCallback();
  }

  configure(control) {
    if (this.#face) throw new Error("Leaves presentation is already configured");
    this.#face = document.createElement(FACE_TAG);
    this.#face.style.display = "contents";
    control.append(this.#face);
  }

  commit() {
    super.commit();
    this.#face.commit();
  }

  async retainCommitted() {
    this.#focus.drop();
    const [committed] = await Promise.all([
      super.retainCommitted(),
      this.#face.retainCommitted(),
    ]);
    return committed;
  }

  async #commit(model, generation) {
    try {
      await this.#face.present(model);
      if (generation !== this.#generation) return this;
      await this.paint(model);
      if (generation !== this.#generation) return this;
      this.commit();
      return this;
    } catch (error) {
      if (generation !== this.#generation) throw error;
      try {
        await this.retainCommitted();
      } catch (restoreError) {
        throw new PresentationRetentionError(
          [error, restoreError],
          "Leaves presentation and retention failed",
        );
      }
      throw error;
    }
  }

  present(model) {
    if (!model || !Array.isArray(model.rows))
      throw new TypeError("Leaves presentation needs a model with row models");
    if (!this.#face) throw new Error("Leaves presentation needs its banner control");
    if (!this.#handle) throw new Error("Leaves presentation needs its connected tray");
    const generation = ++this.#generation;
    let resolve;
    let reject;
    const completion = new Promise((done, failed) => {
      resolve = done;
      reject = failed;
    });
    // `present` writes the ticket synchronously before assigning either face, so a
    // waiter cannot resume between semantic publication and Lit scheduling.
    const ready = this.#handle.present(model, completion, failSoftAfterRetention(this));
    void this.#commit(model, generation).then(resolve, reject);
    return ready;
  }

  willUpdate(changed) {
    if (changed.has("model")) this.#focus.hold(this.model, this.committed);
  }

  updated() {
    for (const link of this.querySelectorAll(LINK)) {
      if (this.#wiredLinks.has(link)) continue;
      this.#wiredLinks.add(link);
      keys(link, "In the leaves tray", openCommand);
    }
    const offered = this.querySelector(LINK) !== null;
    if (offered !== this.#linksOffered) {
      this.#linksOffered = offered;
      paintKeys();
    }
    this.#focus.restore(this.closest(".lf-others-panel"));
  }

  render() {
    return html`${repeat(
      this.model.rows,
      (row) => row.key,
      (row) =>
        row.self
          ? html`<div class="lf-others-row lf-others-self" title=${row.account}>
              ${rowBody(row)}
            </div>`
          : html`<a
              class="lf-others-row"
              href=${row.href}
              target="_blank"
              rel="noopener"
              title=${row.account}
              >${rowBody(row)}</a
            >`,
    )}`;
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, LiveLeavesList);

export function createLiveLeavesList(control) {
  const list = document.createElement(TAG);
  list.configure(control);
  return list;
}
