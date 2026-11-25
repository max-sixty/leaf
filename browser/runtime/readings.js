/* The page readings a package holds: `obligations`, `queues`, `threads` and
   `history`, each a selection of the application state its home derives
   (obligations/place.js, queue-api.js, thread/state.js, reports.js).

   A reading's `read()` returns its current value, immutable, and a `LeafElement`'s
   `render()` that calls it draws again as it moves, since the value is a signal's.
   The reading is also an `EventTarget` that dispatches `change` after its value
   moves, so an element that follows no signal, a plain `HTMLElement` among them,
   follows it with `addEventListener`. A reading starts watching its value at its
   first `change` listener and dispatches once per task however many publications
   moved it, after the publication that moved it has returned. It never stops
   watching, which costs one effect for the page's life.

   `threads` also writes the threads it reads, through Leaf's own path
   (thread/actions.js): `create`, `reply`, `resolve`, `reopen` and `setReaction`.
   Only widget-api.js reaches the application, so it adds those writes there. Taking
   the user to any reading's row is `go` (application.js). */
import { effect } from "/runtime/framework.js";
import { readObligations } from "./obligations/place.js";
import { readQueues } from "./queue-api.js";
import { readThreads } from "./thread/state.js";
import { readHistory } from "./reports.js";

/** @template {() => unknown} R */
class PageReading extends EventTarget {
  // The current value: the home's own function, so its overloads stand.
  /** @type {R} */
  read;
  #watching = false;
  #queued = false;
  /** @param {R} read */
  constructor(read) {
    super();
    this.read = read;
  }

  /** @type {EventTarget["addEventListener"]} */
  addEventListener(type, listener, options) {
    super.addEventListener(type, listener, options);
    if (type === "change" && !this.#watching) this.#watch();
  }

  #watch() {
    this.#watching = true;
    let first = true;
    effect(() => {
      this.read();
      if (first) {
        first = false;
        return;
      }
      if (this.#queued) return;
      this.#queued = true;
      queueMicrotask(() => {
        this.#queued = false;
        this.dispatchEvent(new Event("change"));
      });
    });
  }
}

export const obligations = new PageReading(readObligations);
export const queues = new PageReading(readQueues);
export const history = new PageReading(readHistory);
export const threadsReading = new PageReading(readThreads);
