/* The panel's keyed Lit list and complete committed presentation reading.
   Native card roots are retained by stable thread identity. Only their ThreadView
   owns generated descendants; retention re-renders values, never captured DOM.
   Count and narrowing paint share the rows' checkpoint and update boundary.
   The list owns the one expanded visible thread; native named details enforce the
   same choice in the DOM while cards retain their message and editor nodes. This
   mechanical state never publishes a new application epoch. Narrowing keeps the
   selected card when visible and otherwise selects the first visible card. */
import { LitElement, html, repeat } from "../../vendor/browser-runtime.js";
import { focused } from "../keyboard/scopes.js";
import { ThreadView } from "./thread-card.js";
import { layoutChanged } from "../widget-elements.js";
import { foldOut, finishFold, isFolding } from "./folding.js";

const TAG = "leaf-thread-list";
const EMPTY_MODEL = Object.freeze({ rows: Object.freeze([]), pageSeats: new Map() });

class ThreadListView extends LitElement {
  static properties = {
    model: { attribute: false },
  };
  #commands = null;
  #views = new Map();
  #committedModel = EMPTY_MODEL;
  #failure = null;
  #focusListAfterPaint = false;
  #generation = 0;
  #rows = [];
  #retaining = false;
  #rollbackFocus = null;
  #expandedKey = null;

  #visibleRows() {
    const eligible = new Set(
      this.model.rows
        .filter(
          (row) =>
            row.kind === "thread" && row.descriptor.visible && !row.descriptor.folding,
        )
        .map((row) => row.key),
    );
    return this.#rows.filter((row) => row.kind === "thread" && eligible.has(row.key));
  }

  #showExpanded() {
    const visible = this.#visibleRows();
    if (!visible.length) return;
    const chosen = visible.find((row) => row.key === this.#expandedKey) ?? visible[0];
    this.#expandedKey = chosen.key;
    chosen.node.open = true;
  }

  #chooseFromSummary(card, event) {
    event.preventDefault();
    const row = this.#visibleRows().find((row) => row.node === card);
    if (!row) return;
    // An open title is still the user's focus stop for the conversation. A
    // second press leaves it selected; choosing another title moves disclosure.
    this.#expandedKey = row.key;
    this.#showExpanded();
  }

  navigationThreads() {
    return this.#visibleRows().map((row) => row.node);
  }

  // The shown cards in the page's order, whichever order the list stands in.
  inPageOrder(cards) {
    const seats = this.model.pageSeats;
    return [...cards].sort((a, b) => seats.get(a.dataset.id) - seats.get(b.dataset.id));
  }

  revealNavigation(id) {
    const node = this.querySelector(
      `[data-id="${CSS.escape(id)}"], [data-mid="${CSS.escape(id)}"]`,
    );
    const card = node?.closest(".lf-thread");
    const row = this.#rows.find((row) => row.kind === "thread" && row.node === card);
    // Narrowing owns hidden rows. Its completed reveal calls back here; opening
    // one before that would paint no disclosure and invalidate the same transition.
    if (!row || card.hidden) return;
    this.#expandedKey = row.key;
    this.#showExpanded();
  }

  constructor() {
    super();
    this.model = EMPTY_MODEL;
  }
  get committedReading() {
    return this.#committedModel;
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
    this.#focusListAfterPaint ||= this.contains(focused());
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
      if (!view) {
        this.#views.set(row.key, (view = new ThreadView("panel", this.#commands.card)));
        view.node.addEventListener("toggle", () => layoutChanged(this));
        view.node.addEventListener("click", (event) => {
          if (event.target.closest(".lf-thread-summary")?.parentElement === view.node)
            this.#chooseFromSummary(view.node, event);
        });
      }
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
      view.node.name = folding ? "" : "threads";
      view.setNavigation({
        draftChanged: () => view.present(view.model),
      });
      view.present(descriptor);
      if ((descriptor.visible || descriptor.folding) && row.group.key !== group) {
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
    this.#showExpanded();
    const active = focused();
    const recover = this.#focusListAfterPaint;
    this.#focusListAfterPaint = false;
    if ((recover && !this.contains(active)) || active?.closest?.(".lf-thread[hidden]"))
      this.focus({ preventScroll: true });
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
