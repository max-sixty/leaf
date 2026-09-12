/* The Leaves tray's generated light-DOM list.

   The caller derives complete immutable row models. This owner keys their DOM by the
   page URL, registers each native link's command scope once, preserves a surviving
   link and its focus through reordering, and moves focus to a neighbouring link or
   the tray when the focused page disappears. Each assigned reading opens the Leaves
   presentation region before Lit schedules its update. A failed update restores the
   last committed list before the coordinator reports and settles the attempt. */
import { LitElement, html, repeat } from "../vendor/browser-runtime.js";
import { attachApplicationPresentation } from "./semantic-state.js";
import { keys, paintKeys } from "./keyboard/scopes.js";

const TAG = "lf-leaves-list";

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
    rows: { attribute: false },
  };

  #committedRows = Object.freeze([]);
  #failure = null;
  #focusAfterPaint = undefined;
  #generation = 0;
  #handle = null;
  #linksOffered = false;
  #wiredLinks = new WeakSet();

  constructor() {
    super();
    this.rows = this.#committedRows;
  }

  // Every descendant is generated chrome. Light DOM keeps native links visible to
  // tray styling, keyboard scopes, export, and the render gate.
  createRenderRoot() {
    return this;
  }

  connectedCallback() {
    super.connectedCallback();
    this.#handle ??= attachApplicationPresentation("leaves", this);
    void this.present(this.rows);
  }

  disconnectedCallback() {
    this.#handle?.disconnect();
    this.#handle = null;
    super.disconnectedCallback();
  }

  async #commit(rows, generation) {
    const prior = this.#committedRows;
    this.#failure = null;
    this.rows = rows;
    try {
      await this.updateComplete;
      if (this.#failure) throw this.#failure;
      if (generation !== this.#generation) return this;
      this.#committedRows = rows;
      return this;
    } catch (error) {
      if (generation !== this.#generation) throw error;
      this.#failure = null;
      this.#focusAfterPaint = undefined;
      this.rows = prior;
      try {
        await this.updateComplete;
        if (this.#failure) throw this.#failure;
      } catch (restoreError) {
        throw new AggregateError(
          [error, restoreError],
          "Leaves presentation and fail-soft restoration failed",
        );
      }
      throw error;
    }
  }

  present(rows) {
    if (!Array.isArray(rows))
      throw new TypeError("Leaves presentation needs an array of row models");
    if (!this.#handle) throw new Error("Leaves presentation needs its connected tray");
    const generation = ++this.#generation;
    let resolve;
    let reject;
    const completion = new Promise((done, failed) => {
      resolve = done;
      reject = failed;
    });
    // `present` writes the ticket synchronously before assigning `rows`, so a waiter
    // cannot resume between semantic publication and Lit scheduling.
    const ready = this.#handle.present(rows, completion, () => this);
    void this.#commit(rows, generation).then(resolve, reject);
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
    if (!changed.has("rows")) return;
    const focused = document.activeElement?.closest?.("a.lf-others-row");
    if (!focused || !this.contains(focused)) return;
    const next = this.rows.filter((row) => !row.self).map((row) => row.href);
    const held = focused.getAttribute("href");
    if (next.includes(held)) return;
    const prior = this.#committedRows.filter((row) => !row.self).map((row) => row.href);
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
      this.rows,
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

export function createLiveLeavesList() {
  return document.createElement(TAG);
}
