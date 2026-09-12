/* The Asks tray's generated list. Its immutable row models contain only the words and
   identities the view has already derived; this owner keys those rows by Ask id and
   keeps the native light-DOM buttons stable across presentations. */
import { LitElement, html, repeat } from "../../vendor/browser-runtime.js";
import { PRESS } from "../keyboard/bindings.js";
import { keys } from "../keyboard/scopes.js";

export const ASK_AT = "data-lf-at";
const TAG = "lf-asks-tray-list";

const EMPTY_MODEL = Object.freeze({ open: false, rows: Object.freeze([]) });

class AskTrayList extends LitElement {
  static properties = { model: { attribute: false } };

  #activate = null;
  #committed = EMPTY_MODEL;
  #failure = null;
  #fallback = null;
  #focusAfterPaint = undefined;
  #wired = new WeakSet();

  constructor() {
    super();
    this.model = EMPTY_MODEL;
  }

  createRenderRoot() {
    return this;
  }

  configure({ activate, fallback }) {
    this.#activate = activate;
    this.#fallback = fallback;
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
      // Lit otherwise reports a rejected internal update in addition to the application
      // presentation coordinator. Capture it here; present() rejects the one owned
      // completion and the coordinator reports that failure once before retaining the
      // last committed keyed list.
      this.#failure = error;
    }
  }

  willUpdate(changed) {
    if (!changed.has("model")) return;
    if (
      this.model.open &&
      !this.#committed.open &&
      document.activeElement === this.parentElement &&
      this.model.rows.length
    ) {
      this.#focusAfterPaint = this.model.rows[0].id;
      return;
    }
    const focused = document.activeElement?.closest?.(`button[${ASK_AT}]`);
    if (!focused || !this.contains(focused)) return;
    const nextIds = new Set(this.model.rows.map(({ id }) => id));
    const heldId = focused.getAttribute(ASK_AT);
    if (nextIds.has(heldId)) return;
    const priorIds = this.#committed.rows.map(({ id }) => id);
    const at = priorIds.indexOf(heldId);
    const after = priorIds.slice(at + 1).find((id) => nextIds.has(id));
    const before = priorIds
      .slice(0, at)
      .reverse()
      .find((id) => nextIds.has(id));
    this.#focusAfterPaint = after ?? before ?? null;
  }

  updated() {
    for (const row of this.querySelectorAll(`button[${ASK_AT}]`)) {
      if (this.#wired.has(row)) continue;
      this.#wired.add(row);
      keys(row, "In the Asks tray", [
        {
          id: "ask.open",
          keys: PRESS,
          does: "Go to this ask",
          line: "go to this ask",
        },
      ]);
    }
    if (this.#focusAfterPaint === undefined) return;
    const id = this.#focusAfterPaint;
    this.#focusAfterPaint = undefined;
    const destination = id
      ? [...this.querySelectorAll(`button[${ASK_AT}]`)].find(
          (row) => row.getAttribute(ASK_AT) === id,
        )
      : null;
    (destination ?? this.#fallback)?.focus();
  }

  #activateRow = (event) => {
    const id = event.currentTarget.getAttribute(ASK_AT);
    if (id) this.#activate?.(id);
  };

  render() {
    if (!this.model.open) return html``;
    if (!this.model.rows.length)
      return html`<div class="lf-empty">
        Nothing is waiting on you. A question the page needs an answer for appears here
        when the agent asks one.
      </div>`;
    return repeat(
      this.model.rows,
      ({ id }) => id,
      ({ id, kind, says, answer, answerState, title }) =>
        html`<button
          type="button"
          class="lf-asks-row"
          data-lf-at=${id}
          data-lf-answer-state=${answerState}
          title=${title}
          @click=${this.#activateRow}
        >
          <span class="lf-asks-kind">${kind}</span>
          <span class="lf-asks-says">${says}</span>
          <span class="lf-asks-answer">${answer}</span>
        </button>`,
    );
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, AskTrayList);

export function createAskTrayList() {
  return document.createElement(TAG);
}
