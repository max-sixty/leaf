/* The panel's keyed Lit list and complete committed presentation reading.
   Native card roots are retained by stable thread identity. Only their ThreadView
   owns generated descendants; retention re-renders values, never captured DOM.
   Count and narrowing paint share the rows' checkpoint and update boundary. */
import { LitElement, html, repeat } from "../../vendor/browser-runtime.js";
import { focused } from "../keyboard/scopes.js";
import { ThreadView } from "./thread-card.js";
import { foldOut, finishFold, isFolding } from "./folding.js";

const TAG = "leaf-thread-list";
const EMPTY_MODEL = Object.freeze({ rows: Object.freeze([]) });

class ThreadListView extends LitElement {
  static properties = { model: { attribute: false } };
  #commands = null;
  #views = new Map();
  #committedModel = EMPTY_MODEL;
  #failure = null;
  #generation = 0;
  #rows = [];
  #retaining = false;
  #rollbackFocus = null;

  constructor() {
    super();
    this.model = EMPTY_MODEL;
  }
  createRenderRoot() {
    return this;
  }
  configure(commands, initialModel) {
    if (this.#commands) return;
    this.#commands = commands;
    this.#committedModel = initialModel;
    this.model = initialModel;
  }

  async present(model) {
    const generation = ++this.#generation;
    this.#failure = null;
    this.#rollbackFocus ??= this.contains(focused()) ? focused() : null;
    this.model = model;
    // Forward gestures paint their complete generated result in their sending turn.
    this.performUpdate();
    await this.updateComplete;
    if (this.#failure) throw this.#failure;
    return generation === this.#generation && this.model === model;
  }

  commit(model) {
    if (this.model !== model) return false;
    this.#committedModel = model;
    const wanted = new Set(
      model.rows.filter((row) => row.kind === "thread").map((row) => row.key),
    );
    for (const [key, view] of this.#views) {
      if (wanted.has(key)) view.commit();
      else {
        view.dispose();
        this.#views.delete(key);
      }
    }
    this.#rollbackFocus = null;
    return true;
  }

  async retainCommitted(candidate) {
    if (this.model !== candidate) return false;
    const generation = ++this.#generation;
    this.#retaining = true;
    this.#failure = null;
    this.model = this.#committedModel;
    try {
      this.performUpdate();
      await this.updateComplete;
      if (this.#failure) throw this.#failure;
      if (generation !== this.#generation) return false;
      if (this.#rollbackFocus?.isConnected)
        this.#rollbackFocus.focus({ preventScroll: true });
      this.#rollbackFocus = null;
      return this.#committedModel;
    } finally {
      this.#retaining = false;
    }
  }

  async scheduleUpdate() {
    try {
      await super.scheduleUpdate();
    } catch (error) {
      this.#failure = error;
    }
  }

  willUpdate(changed) {
    if (!changed.has("model") || !this.#commands) return;
    const rows = [];
    const wanted = new Set();
    let group = null;
    for (const row of this.model.rows) {
      if (row.kind !== "thread") {
        rows.push(row);
        continue;
      }
      wanted.add(row.key);
      let view = this.#views.get(row.key);
      if (!view)
        this.#views.set(row.key, (view = new ThreadView("panel", this.#commands.card)));
      let descriptor = row.descriptor;
      const prior = view.model;
      if (this.#retaining || !descriptor.resolved) finishFold(descriptor.id);
      const folding =
        !this.#retaining &&
        descriptor.resolved &&
        (isFolding(descriptor.id) ||
          (prior &&
            !prior.resolved &&
            !prior.folding &&
            prior.visible &&
            !descriptor.visible &&
            foldOut(descriptor.id, view.node, this.#commands.repaintConversation)));
      if (folding) {
        view.retire();
        descriptor = Object.freeze({
          ...prior,
          id: descriptor.id,
          folding: true,
          grow: false,
          settlement: Object.freeze({ ...prior.settlement, pending: false }),
        });
        if (view.node.contains(focused())) this.focus({ preventScroll: true });
      }
      view.present(descriptor);
      if (
        (!descriptor.visible && !descriptor.folding) === false &&
        row.group.key !== group
      ) {
        group = row.group.key;
        if (row.group.label)
          rows.push({ kind: "group", ...row.group, key: `group:${row.group.key}` });
      }
      rows.push({ kind: "thread", key: row.key, node: view.node });
    }
    for (const [key, view] of this.#views) if (!wanted.has(key)) view.retire();
    this.#rows = rows;
  }

  updated() {
    const active = focused();
    if (active?.closest?.(".lf-thread[hidden]")) this.focus({ preventScroll: true });
    this.#commands?.presentSummary(this.model);
  }

  #row(row) {
    if (row.kind === "thread") return row.node;
    if (row.kind === "empty") return html`<div class="lf-empty">${row.text}</div>`;
    if (row.kind === "system")
      return html`<div class="lf-system" data-id=${row.id}>${row.text}</div>`;
    if (row.target)
      return html`<button
        type="button"
        class="lf-group lf-pinned"
        data-group=${row.key.slice("group:".length)}
        title="Jump to this part of the page"
        @click=${() => this.#commands.activateGroup(row.target)}
        .textContent=${row.label}
      ></button>`;
    return html`<div
      class="lf-group lf-pinned"
      data-group=${row.key.slice("group:".length)}
      .textContent=${row.label}
    ></div>`;
  }
  render() {
    return repeat(
      this.#rows,
      (row) => row.key,
      (row) => this.#row(row),
    );
  }
}
if (!customElements.get(TAG)) customElements.define(TAG, ThreadListView);
export const createThreadListView = () => document.createElement(TAG);
