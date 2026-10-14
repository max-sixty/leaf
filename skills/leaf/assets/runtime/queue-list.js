/* The On panel's generated list. EXPERIMENTAL: the panel is a first cut at one place
   for what waits on the user and on the agent, and its groups, rows and words are
   expected to change a lot.

   Its immutable reading holds only the words and identities `queue-panel.js` has
   already derived: the rows of the list in view, On me or On <agent>, whose tab in the
   panel's head names it, then what that list has done, folded behind a native
   disclosure at the foot. This retained face keys
   the rows by item and keeps their light-DOM buttons stable across presentations. A row
   standing at an element, an ask's or a widget's the user must act on, names it in
   `data-lf-at`, so the row stands at that element (`declareSide`, queue-panel.js) and
   mirrors the ring of the ask the user stands in (asks/view.js, `markHere`). The fold's
   open state is the disclosure's own, a browser fact the reading never holds.

   A row whose to-do the user ends with Done carries a Done button beside it, which Tab
   reaches from the row and a finger taps, and `x` on the row presses it. Pressing it
   puts focus on its row first, so focus follows the list as the row leaves for Done. */
import { html, nothing, repeat } from "../vendor/browser-runtime.js";
import { PRESS } from "./keyboard/bindings.js";
import { commandsOn } from "./keyboard/scopes.js";
import { RetainedFace } from "./retained-face.js";
import { focusDestination, holdFocus, focused } from "./focus.js";
import { closestAcross } from "./passages.js";

const QUEUE_AT = "data-lf-at";
const QUEUE_ROW = "data-lf-row";
const QUEUE_DONE = "data-lf-done";
const ROW = `button[${QUEUE_ROW}]`;
const TAG = "lf-queue-list";

const EMPTY_MODEL = Object.freeze({
  open: false,
  queue: Object.freeze({ id: "you", rows: Object.freeze([]), empty: "" }),
  done: Object.freeze({ label: "", rows: Object.freeze([]) }),
});
const rowKeys = (model) =>
  [...model.queue.rows, ...model.done.rows].map(({ key }) => key);

const rowTemplate = (row, activate, finish, end) =>
  html`<div class="lf-queue-item">
    <button
      type="button"
      class="lf-queue-row"
      data-lf-row=${row.key}
      data-lf-at=${row.at ?? nothing}
      data-lf-kind=${row.kind}
      data-lf-live=${row.live ? "" : nothing}
      title=${row.account}
      @click=${activate}
      ${commandsOn("In the On panel", [
        { id: "queue.row.open", keys: PRESS, title: "go to this item" },
        {
          id: "queue.row.done",
          keys: ["x"],
          title: "done",
          description: "Mark this to-do done",
          when: () => Boolean(row.done),
          run: () => end(row.key),
        },
      ])}
    >
      <span class="lf-queue-kind">${row.word}</span>
      <span class="lf-queue-title">${row.title}</span>
      <span class="lf-queue-where"
        >${row.where.map((part, index) => html`${index ? " · " : ""}${part.feedback ? html`<span class="lf-queue-feedback">${part.text}</span>` : part.text}`)}</span
      >
    </button>
    ${
      row.done
        ? html`<button
            type="button"
            class="lf-btn lf-queue-finish"
            data-lf-done=${row.key}
            aria-label=${`Done: ${row.title}`}
            @click=${finish}
            ${commandsOn("On a to-do's Done", [
              { id: "queue.done.press", keys: PRESS, title: "mark it done" },
            ])}
          >
            Done
          </button>`
        : nothing
    }
  </div>`;

const rowsTemplate = (rows, activate, finish, end) =>
  html`<div class="lf-queue-rows">
    ${repeat(
      rows,
      ({ key }) => key,
      (row) => rowTemplate(row, activate, finish, end),
    )}
  </div>`;

/** @typedef {QueueList} QueueListElement For its tag (`runtime-globals.d.ts`). */
class QueueList extends RetainedFace {
  #activate = null;
  #finish = null;
  #fallback = null;
  #observeFeedback = null;
  #feedbackStops = [];
  // Across a repaint the user keeps their row, or the nearest that survived it
  // (focus.js, keyed `holdFocus`); a panel opened from its edge lands on its first stop.
  #restoreFocus = null;
  #landing = false;

  constructor() {
    super(EMPTY_MODEL);
  }

  configure({ activate, finish, fallback, observeFeedback }) {
    this.#activate = activate;
    this.#finish = finish;
    this.#fallback = fallback;
    this.#observeFeedback = observeFeedback;
  }

  willUpdate(changed) {
    if (!changed.has("model")) return;
    // A panel opened from its edge lands on its first stop once one exists: the list's
    // first row, or with none, its Done's door.
    if (
      this.model.open &&
      !this.committed.open &&
      focused() === this.parentElement &&
      rowKeys(this.model).length > 0
    ) {
      this.#landing = true;
      return;
    }
    this.#restoreFocus = holdFocus(this, { key: QUEUE_ROW });
  }

  // Done on the row keyed `key`, from its button or its key, standing on the row first.
  #end = (key) => {
    const row = this.querySelector(`${ROW}[${QUEUE_ROW}="${CSS.escape(key)}"]`);
    if (row) focusDestination(row, "move");
    this.#finish?.(key);
  };

  updated() {
    for (const stop of this.#feedbackStops) stop();
    this.#feedbackStops = [];
    if (this.#observeFeedback) {
      for (const row of this.model.queue.rows) {
        const feedback = row.where.find((part) => part.feedback)?.feedback;
        if (!feedback) continue;
        const words = this.querySelector(
          `${ROW}[${QUEUE_ROW}="${CSS.escape(row.key)}"] .lf-queue-feedback`,
        );
        this.#feedbackStops.push(this.#observeFeedback(words, feedback));
      }
    }
    const [landing, restore] = [this.#landing, this.#restoreFocus];
    [this.#landing, this.#restoreFocus] = [false, null];
    if (landing) {
      const place = walkStops(this)[0] ?? this.#fallback;
      if (place) focusDestination(place, "move");
    }
    restore?.(this.#fallback);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    for (const stop of this.#feedbackStops) stop();
    this.#feedbackStops = [];
  }

  #activateRow = (event) => {
    const key = event.currentTarget.getAttribute(QUEUE_ROW);
    if (key) this.#activate?.(key);
  };

  #finishRow = (event) => {
    const key = event.currentTarget.getAttribute(QUEUE_DONE);
    if (key) this.#end(key);
  };

  render() {
    if (!this.model.open) return html``;
    const { queue, done } = this.model;
    return html`<div class="lf-queue-group" data-lf-queue=${queue.id}>
        ${
          queue.rows.length
            ? rowsTemplate(queue.rows, this.#activateRow, this.#finishRow, this.#end)
            : html`<div class="lf-queue-empty">${queue.empty}</div>`
        }
      </div>
      ${
        done.rows.length
          ? html`<details class="lf-queue-group lf-queue-done" data-lf-queue="done">
              <summary class="lf-queue-heading">${done.label}</summary>
              ${rowsTemplate(done.rows, this.#activateRow, this.#finishRow, this.#end)}
            </details>`
          : nothing
      }`;
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, QueueList);

export function createQueueList() {
  return document.createElement(TAG);
}

// The row standing at the element `id` names in an open list, or null: the row an
// ask's ring is mirrored on and an arrival at that ask reveals.
export const rowAt = (list, id) =>
  [...list.querySelectorAll(`${ROW}[${QUEUE_AT}]`)].find(
    (row) => row.getAttribute(QUEUE_AT) === id,
  ) ?? null;

// The id of the element the row holding `node` stands at, or null.
export const standsAt = (node) =>
  closestAcross(node, `${ROW}[${QUEUE_AT}]`)?.getAttribute(QUEUE_AT) ?? null;

// The items an open list shows, in order: the rows of the list in view, and its Done's
// while that is open.
export const shownItems = (list) =>
  [...list.querySelectorAll(ROW)].filter(
    (row) => !row.closest(".lf-queue-done:not([open])"),
  );

// What a walk down the list stops at: its items, with Done's door in its place
// between them.
export const walkStops = (list) =>
  [...list.querySelectorAll(`${ROW}, .lf-queue-done > summary`)].filter(
    (stop) => stop.matches("summary") || !stop.closest(".lf-queue-done:not([open])"),
  );
