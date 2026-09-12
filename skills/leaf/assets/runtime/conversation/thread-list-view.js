/* The comment panel's generated child-order owner.

   The caller derives one immutable mechanical row model from the current conversation
   reading. This light-DOM Lit owner materializes retained thread cards inside its update,
   keys every row, and is the only code that inserts, moves, or removes direct children of
   `.lf-threads`. The cards themselves remain owned by thread-card.js. A failed update can
   restore the last committed rows and the retained light-DOM card trees before the
   conversation presentation ticket settles fail-soft. */
import { LitElement, html, repeat } from "../../vendor/browser-runtime.js";
import { focused } from "../keyboard/scopes.js";

const TAG = "lf-thread-list";
const EMPTY_MODEL = Object.freeze({ rows: Object.freeze([]) });

const ordinaryElement = (node) =>
  node.nodeType === Node.ELEMENT_NODE && !node.localName.includes("-");

// A card rebuild may move a cached frozen message body from the committed card into its
// replacement. Preserve the conversation-owned light tree so a failed candidate can move
// those exact nodes back. Custom-element internals remain their own owners and are not
// captured or rewritten.
function captureTree(nodes) {
  const elements = [];
  const texts = [];
  const capture = (node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      texts.push([node, node.data]);
      return;
    }
    if (!ordinaryElement(node)) return;
    elements.push([
      node,
      [...node.attributes].map(({ name, value }) => [name, value]),
      [...node.childNodes],
    ]);
    for (const child of node.childNodes) capture(child);
  };
  for (const node of nodes) capture(node);
  return { elements, texts };
}

function restoreTree(snapshot) {
  for (const [node, attributes] of snapshot.elements) {
    const retained = new Set(attributes.map(([name]) => name));
    for (const { name } of [...node.attributes])
      if (!retained.has(name)) node.removeAttribute(name);
    for (const [name, value] of attributes) node.setAttribute(name, value);
  }
  for (const [node, data] of snapshot.texts) node.data = data;
  // Parent first: a cached body may currently stand in a discarded replacement card.
  // Restoring its committed parent puts that parent back before the body's own children
  // are checked.
  for (const [node, , children] of snapshot.elements) node.replaceChildren(...children);
}

class ThreadListView extends LitElement {
  static properties = { model: { attribute: false } };

  #activateGroup = null;
  #committedModel = EMPTY_MODEL;
  #committedRows = Object.freeze([]);
  #failure = null;
  #focusListAfterPaint = false;
  #generation = 0;
  #materialize = null;
  #renderRows = Object.freeze([]);
  #retire = null;
  #rollback = null;
  #rollbackFocus = undefined;
  #retaining = 0;

  constructor() {
    super();
    this.model = EMPTY_MODEL;
  }

  createRenderRoot() {
    return this;
  }

  configure({ activateGroup, materialize, retire }) {
    this.#activateGroup = activateGroup;
    this.#materialize = materialize;
    this.#retire = retire;
  }

  async present(model) {
    if (!this.#materialize || !this.#retire)
      throw new Error("Thread list presentation needs its view commands");
    const generation = ++this.#generation;
    this.#failure = null;
    this.model = model;
    await this.updateComplete;
    if (this.#failure) throw this.#failure;
    return generation === this.#generation && this.model === model;
  }

  commit(model) {
    if (this.model !== model) return false;
    this.#committedModel = model;
    this.#committedRows = this.#renderRows;
    this.#rollback = null;
    this.#rollbackFocus = undefined;
    return true;
  }

  async retainCommitted(candidate) {
    if (this.model !== candidate) return false;
    const generation = ++this.#generation;
    const rollback = this.#rollback;
    this.#failure = null;
    this.#focusListAfterPaint = false;
    this.#retaining = generation;
    this.model = this.#committedModel;
    try {
      await this.updateComplete;
      if (this.#failure) throw this.#failure;
      if (generation !== this.#generation) return false;
      if (rollback) restoreTree(rollback);
      if (this.#rollbackFocus?.isConnected)
        this.#rollbackFocus.focus({ preventScroll: true });
      this.#rollback = null;
      this.#rollbackFocus = undefined;
      return this.#committedModel;
    } finally {
      if (this.#retaining === generation) this.#retaining = 0;
    }
  }

  async scheduleUpdate() {
    try {
      await super.scheduleUpdate();
    } catch (error) {
      // Lit would otherwise report its rejected internal update beside the conversation
      // coordinator. The existing ticket owns the one fail-soft report.
      this.#failure = error;
    }
  }

  willUpdate(changed) {
    if (!changed.has("model")) return;
    const priorRows = this.#renderRows;
    if (this.#retaining === this.#generation && this.model === this.#committedModel) {
      this.#renderRows = this.#committedRows;
      return;
    }

    this.#focusListAfterPaint ||= this.contains(focused());
    this.#rollback ??= captureTree(
      this.#committedRows
        .filter(({ kind }) => kind === "thread")
        .map(({ node }) => node),
    );
    if (this.#rollbackFocus === undefined)
      this.#rollbackFocus = this.contains(focused()) ? focused() : null;

    const rows = [];
    let group = null;
    for (const row of this.model.rows) {
      if (row.kind !== "thread") {
        rows.push(row);
        continue;
      }
      const node = this.#materialize(row);
      if (!node) continue;
      const leaving = node.matches(".lf-going");
      const hiding = !row.visible && !leaving && !node.hidden;
      node.hidden = !row.visible && !leaving;
      if (hiding)
        document.dispatchEvent(
          new CustomEvent("lf-thread-hidden", { detail: { node } }),
        );
      if (!node.hidden && row.group.key !== group) {
        group = row.group.key;
        if (row.group.label)
          rows.push({
            kind: "group",
            ...row.group,
            key: `group:${row.group.key}`,
          });
      }
      rows.push({ kind: "thread", key: row.key, node });
    }
    const nextNodes = new Set(
      rows.filter(({ kind }) => kind === "thread").map(({ node }) => node),
    );
    for (const { node } of priorRows.filter(({ kind }) => kind === "thread"))
      if (!nextNodes.has(node)) this.#retire(node);
    this.#renderRows = Object.freeze(rows);
  }

  updated() {
    if (!this.#focusListAfterPaint) return;
    this.#focusListAfterPaint = false;
    const standing = focused();
    if (!this.contains(standing) || standing?.closest?.(".lf-thread[hidden]"))
      this.focus({ preventScroll: true });
  }

  #activate = (event) => {
    this.#activateGroup?.(event.currentTarget.lfTarget);
  };

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
        .lfTarget=${row.target}
        .textContent=${row.label}
        @click=${this.#activate}
      ></button>`;
    return html`<div
      class="lf-group lf-pinned"
      data-group=${row.key.slice("group:".length)}
      .textContent=${row.label}
    ></div>`;
  }

  render() {
    return repeat(
      this.#renderRows,
      ({ key }) => key,
      (row) => this.#row(row),
    );
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, ThreadListView);

export function createThreadListView() {
  return document.createElement(TAG);
}
