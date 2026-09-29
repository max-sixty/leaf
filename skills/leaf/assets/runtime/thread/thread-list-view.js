/* The panel's keyed Lit list and complete committed presentation reading.
   Native card roots are retained by stable thread identity. Only their ThreadView
   owns generated descendants; retention re-renders values, never captured DOM.
   Count and narrowing paint share the rows' checkpoint and update boundary.
   The list owns the one expanded visible thread and writes every shown card's
   disclosure from that choice, while cards retain their message and editor nodes; a
   card the browser opens itself, as find-in-page does, becomes the choice. The cards
   carry no native `name`: its exclusivity closes a card the moment it is named beside
   an open one, which the list's own choice then opens again. This mechanical state
   never publishes a new application epoch. Narrowing keeps the
   selected card when visible and otherwise selects the first visible card. */
import { html, repeat } from "../../vendor/browser-runtime.js";
import { focused } from "../keyboard/scopes.js";
import { RetainedFace } from "../retained-face.js";
import { ThreadView } from "./thread-card.js";
import { layoutChanged } from "../widget-elements.js";
import { nextRender } from "../rendering.js";
import { foldOut, finishFold, isFolding } from "./folding.js";

const TAG = "leaf-thread-list";
const EMPTY_MODEL = Object.freeze({ rows: Object.freeze([]), pageSeats: new Map() });

class ThreadListView extends RetainedFace {
  #commands = null;
  #views = new Map();
  #focusListAfterPaint = false;
  #generation = 0;
  #rows = [];
  #retaining = false;
  #rollbackFocus = null;
  #expandedKey = null;
  #draftViews = new Set();
  #draftFrame = 0;

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
    for (const row of visible) row.node.toggleAttribute("open", row === chosen);
  }

  #chooseFromSummary(card, event) {
    event.preventDefault();
    const row = this.#visibleRows().find((row) => row.node === card);
    if (!row) return;
    // An open title is still the user's focus stop for the thread. A
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
    super(EMPTY_MODEL);
  }
  configure(commands, initialModel) {
    if (this.#commands) return;
    this.#commands = commands;
    this.model = initialModel;
    super.commit();
  }

  // Forward gestures paint their complete generated result in their sending turn.
  async present(model) {
    const generation = ++this.#generation;
    this.#rollbackFocus ??= this.contains(focused()) ? focused() : null;
    await this.paint(model, { now: true });
    return generation === this.#generation && this.model === model;
  }

  commit(model) {
    if (this.model !== model) return false;
    super.commit();
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
    try {
      await this.paint(this.committed, { now: true });
      if (generation !== this.#generation) return false;
      if (this.#rollbackFocus?.isConnected)
        this.#rollbackFocus.focus({ preventScroll: true });
      this.#rollbackFocus = null;
      return this.committed;
    } finally {
      this.#retaining = false;
    }
  }

  willUpdate(changed) {
    if (!changed.has("model") || !this.#commands) return;
    this.#focusListAfterPaint ||= this.contains(focused());
    const rows = [];
    const wanted = new Set();
    for (const row of this.model.rows) {
      if (row.kind !== "thread") {
        rows.push(row);
        continue;
      }
      wanted.add(row.key);
      let view = this.#views.get(row.key);
      if (!view) {
        this.#views.set(row.key, (view = new ThreadView("panel", this.#commands.card)));
        view.node.addEventListener("toggle", () => {
          layoutChanged(this);
          const row = this.#visibleRows().find((row) => row.node === view.node);
          if (!view.node.open || !row || row.key === this.#expandedKey) return;
          this.#expandedKey = row.key;
          this.#showExpanded();
        });
        view.node.addEventListener("click", (event) => {
          if (event.target.closest(".lf-thread-summary")?.parentElement === view.node)
            this.#chooseFromSummary(view.node, event);
        });
      }
      let descriptor = row.descriptor;
      const prior = view.model;
      if (this.#retaining || !descriptor.resolved) finishFold(view.node);
      const folding =
        !this.#retaining &&
        descriptor.resolved &&
        (isFolding(view.node) ||
          (prior &&
            !prior.resolved &&
            !prior.folding &&
            prior.visible &&
            !descriptor.visible &&
            foldOut(view.node, this.#commands.repaintThread)));
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
      view.setNavigation({ draftChanged: () => this.#draftChanged(view) });
      view.present(descriptor);
      rows.push({ kind: "thread", key: row.key, node: view.node });
    }
    for (const [key, view] of this.#views) if (!wanted.has(key)) view.retire();
    this.#rows = rows;
  }

  // A folded row says whether its reply holds a draft. A send empties the box in the
  // same turn that publishes the message it sent, so the row repaints from what that
  // turn ends on rather than once for the emptied box and again for the message.
  #draftChanged(view) {
    this.#draftViews.add(view);
    this.#draftFrame ||= nextRender(() => {
      this.#draftFrame = 0;
      for (const changed of this.#draftViews)
        if ([...this.#views.values()].includes(changed)) changed.present(changed.model);
      this.#draftViews.clear();
    });
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
    return html`<div class="lf-system" data-id=${row.id}>${row.text}</div>`;
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
