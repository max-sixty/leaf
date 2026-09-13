/* The Leaves banner control and tray's generated light-DOM list.

   The caller derives one immutable model for the control's presence and words and the
   keyed tray rows. The native control remains the banner shelf and tray owner's stable
   node; a light-DOM Lit face paints inside it. This owner registers each native link's
   command scope once, preserves a surviving link and its focus through reordering, and
   moves focus to a neighbouring link or the tray when the focused page disappears.
   Each assigned reading opens one Leaves presentation region before either face
   schedules an update. A failed update restores both committed faces before the
   coordinator reports and settles the attempt. */
import { LitElement, html, repeat } from "../vendor/browser-runtime.js";
import {
  attachApplicationPresentation,
  failSoftAfterRetention,
  PresentationRetentionError,
} from "./semantic-state.js";
import { foldShelf, showNews } from "./banner-shelf.js";
import { keys, paintKeys } from "./keyboard/scopes.js";

const TAG = "lf-leaves-list";
const FACE_TAG = "lf-leaves-banner-face";
const EMPTY_ROWS = Object.freeze([]);
const EMPTY_MODEL = Object.freeze({
  offered: false,
  label: "All leaves (0)",
  rows: EMPTY_ROWS,
});

class LeavesBannerFace extends LitElement {
  static properties = { model: { attribute: false } };

  #committed = EMPTY_MODEL;
  #failure = null;

  constructor() {
    super();
    this.model = EMPTY_MODEL;
  }

  createRenderRoot() {
    return this;
  }

  async present(model) {
    this.#failure = null;
    this.model = model;
    await this.updateComplete;
    if (this.#failure) throw this.#failure;
    return model;
  }

  commit() {
    this.#committed = this.model;
  }

  async retainCommitted() {
    this.#failure = null;
    this.model = this.#committed;
    await this.updateComplete;
    if (this.#failure) throw this.#failure;
    return this.#committed;
  }

  async scheduleUpdate() {
    try {
      await super.scheduleUpdate();
    } catch (error) {
      this.#failure = error;
    }
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

class LiveLeavesList extends LitElement {
  static properties = {
    model: { attribute: false },
  };

  #committed = EMPTY_MODEL;
  #failure = null;
  #face = null;
  #focusAfterPaint = undefined;
  #generation = 0;
  #handle = null;
  #linksOffered = false;
  #wiredLinks = new WeakSet();

  constructor() {
    super();
    this.model = EMPTY_MODEL;
  }

  // Every descendant is generated chrome. Light DOM keeps native links visible to
  // tray styling, keyboard scopes, export, and the render gate.
  createRenderRoot() {
    return this;
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

  async #retainCommitted() {
    this.#failure = null;
    this.#focusAfterPaint = undefined;
    this.model = this.#committed;
    await Promise.all([this.updateComplete, this.#face.retainCommitted()]);
    if (this.#failure) throw this.#failure;
    foldShelf();
    return this.#committed;
  }

  async #commit(model, generation) {
    try {
      await this.#face.present(model);
      if (generation !== this.#generation) return this;
      this.#failure = null;
      this.model = model;
      await this.updateComplete;
      if (this.#failure) throw this.#failure;
      if (generation !== this.#generation) return this;
      foldShelf();
      this.#committed = model;
      this.#face.commit();
      return this;
    } catch (error) {
      if (generation !== this.#generation) throw error;
      try {
        await this.#retainCommitted();
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

  async scheduleUpdate() {
    try {
      await super.scheduleUpdate();
    } catch (error) {
      // Lit would otherwise surface a second rejected internal update beside the
      // coordinator's one owned failure. The completion below reports it once.
      this.#failure = error;
    }
  }

  willUpdate(changed) {
    if (!changed.has("model")) return;
    const focused = document.activeElement?.closest?.("a.lf-others-row");
    if (!focused || !this.contains(focused)) return;
    const next = this.model.rows.filter((row) => !row.self).map((row) => row.href);
    const held = focused.getAttribute("href");
    if (next.includes(held)) return;
    const prior = this.#committed.rows
      .filter((row) => !row.self)
      .map((row) => row.href);
    const at = prior.indexOf(held);
    const after = prior.slice(at + 1).find((href) => next.includes(href));
    const before = prior
      .slice(0, at)
      .reverse()
      .find((href) => next.includes(href));
    this.#focusAfterPaint = after ?? before ?? null;
  }

  updated() {
    for (const link of this.querySelectorAll("a.lf-others-row")) {
      if (this.#wiredLinks.has(link)) continue;
      this.#wiredLinks.add(link);
      keys(link, "In the leaves tray", openCommand);
    }
    const offered = this.querySelector("a.lf-others-row") !== null;
    if (offered !== this.#linksOffered) {
      this.#linksOffered = offered;
      paintKeys();
    }
    if (this.#focusAfterPaint === undefined) return;
    const href = this.#focusAfterPaint;
    this.#focusAfterPaint = undefined;
    const destination = href
      ? [...this.querySelectorAll("a.lf-others-row")].find(
          (link) => link.getAttribute("href") === href,
        )
      : null;
    (destination ?? this.closest(".lf-others-panel"))?.focus();
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
