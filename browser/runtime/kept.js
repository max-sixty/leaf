// @ts-check
/* Readings kept by what each was read from.

   A fold that reads one record for each item of a collection on every publication
   would make each record again, and the publisher would then compare it with the last
   one to keep its identity, so a publication would cost what the page holds. A reader
   made here keeps each record beside its inputs and makes it again only where one of
   them has changed, compared by identity, so a reading costs the records it makes and
   a check of each one's inputs. The inputs have to name everything the record reads:
   a fold that reads more than it names keeps a stale record. They are compared by
   identity, so they keep it while unchanged, as the served reading does for every
   record the server didn't change (`completeState` in `layer-client.js`).

   `kept` keeps a reading of facts outside it, as On Me's groups read the page, the
   threads' placement and the server's lists, without being told what it reads, and
   `keptEach` keeps one for each key, made as each is first asked for, as On Me's seat
   for each item is. A reading is a `computed` signal, so every signal it reads, the
   application state's (`readPart`) and a widget module's own among them, makes it
   again when it changes, and a view reading it, kept or made, hears those signals.
   The page's reading and the threads' placement are not signals: a view drawn from
   them would draw again at every change the page heard, as on each frame a widget
   redraws a counter, where Leaf draws a view of the page when the page is presented
   (`presentDocument`). Their readers, and those of the other facts outside any
   signal, call `reads` with a function answering which version of the fact stands,
   and the reading is made afresh once a version it read answers otherwise: the page's
   readers (passages.js), placement's (`placedAt`), a visual's parts (visual-parts.js)
   and the other callers of `reads`. So a reading stays current however its code
   changes, as long as what it reads is a signal or has a reader that calls `reads`; a
   new kind of fact gets one. What the page's watcher doesn't hear, such as a datum's
   source or a role making a press, is read beside what announces its change, the
   document presented or a widget's layout changing (anchor-resolution.js,
   `currentDatums`, `claimsVisualGesture`).

   Each read asks every version the reading read again, so standing costs one call per
   such input, and an input that catches up when asked, as the page's watcher and
   placement do, has caught up before the reading answers. A version that moved makes
   a new reading rather than telling the old one's views, so a view draws the page's
   change when the page is presented.

   This module imports nothing but signals, so the pure folds can use it. */
import { computed } from "/vendor/signals-core.js";

// Between the lists one record's inputs hold, so an item that moves from one list to
// the next reads as a change.
export const BETWEEN = Symbol("between");

/** @param {readonly unknown[]} held @param {readonly unknown[]} inputs */
const same = (held, inputs) =>
  held.length === inputs.length &&
  inputs.every((input, at) => Object.is(input, held[at]));

/**
 * A reader of records by key. `read(key, inputs, make)` returns the value it kept for
 * `key` where `inputs` are the ones it was made from, else `make(earlier)`'s, where
 * `earlier` is the value kept for `key`, if any, for a value that keeps finer readings
 * of its own. `done()` ends a reading: what it read is kept, and every key it didn't
 * read is forgotten.
 *
 * @template V
 */
export function keptReadings() {
  /** @type {Map<unknown, {inputs: readonly unknown[], value: V}>} */
  let kept = new Map();
  /** @type {Map<unknown, {inputs: readonly unknown[], value: V}>} */
  let reading = new Map();
  return {
    /**
     * @param {unknown} key
     * @param {readonly unknown[]} inputs
     * @param {(earlier: V | undefined) => V} make
     * @returns {V}
     */
    read(key, inputs, make) {
      const held = kept.get(key);
      const value = held && same(held.inputs, inputs) ? held.value : make(held?.value);
      reading.set(key, { inputs, value });
      return value;
    },
    done() {
      kept = reading;
      reading = new Map();
    },
  };
}

/** @typedef {() => unknown} Input
 * @typedef {Map<Input, unknown>} Inputs */
// The inputs the reading being made has read so far, each with its answer.
/** @type {Inputs | null} */
let reading = null;
// What an input stands at while it is first asked.
const ASKING = Symbol("asking");

/** Says that the reading being made, if one is, reads `input`: a function of nothing
 * answering which version of a fact outside any signal stands, the same value while
 * the fact does (`kept`). An input that calls `reads` with itself as it answers, as the
 * page's reading does while it catches up, is asked once; one that throws is not kept.
 * @param {Input} input */
export function reads(input) {
  const into = reading;
  if (!into || into.has(input)) return;
  into.set(input, ASKING);
  try {
    into.set(input, input());
  } catch (error) {
    into.delete(input);
    throw error;
  }
}

/** @param {Inputs} held */
const stands = (held) => {
  for (const [input, was] of held) if (!Object.is(input(), was)) return false;
  return true;
};
// A signal of what `make` makes, each input it reads added to `held`.
/** @template T @param {Inputs} held @param {() => T} make */
const recording = (held, make) =>
  computed(() => {
    const outer = reading;
    reading = held;
    try {
      return make();
    } finally {
      reading = outer;
    }
  });
// Which of a reader's readings stands, kept as an input of the reading being made, if
// one is: asking it again checks the inputs the reader's reading has read by then,
// those it read only after a signal changed what it reads included, so a reading made
// around another stands no longer than the one inside it. A reader read inside its
// own make, as one key's make asks for another, is no input of itself.
/** @param {Input} standing @param {number} generation @param {Inputs} own */
const within = (standing, generation, own) => {
  if (reading && reading !== own && !reading.has(standing))
    reading.set(standing, generation);
};

/** A reader of what `derive` makes, kept while every signal it read is unchanged and
 * every input it read (`reads`) answers as it did. Read while another reading is
 * being made, it is one of that reading's inputs. A make that throws keeps nothing.
 * @template T @param {() => T} derive @returns {() => T} */
export function kept(derive) {
  /** @type {Inputs} */
  let inputs = new Map();
  /** @type {import("@preact/signals-core").ReadonlySignal<T> | null} */
  let made = null;
  let generation = 0;
  const standing = () => {
    if (!made || !stands(inputs)) {
      made = recording((inputs = new Map()), derive);
      generation += 1;
    }
    return generation;
  };
  return () => {
    within(standing, standing(), inputs);
    try {
      return /** @type {NonNullable<typeof made>} */ (made).value;
    } catch (error) {
      made = null;
      throw error;
    }
  };
}

/** A reader of what `make` makes of each key, made when the key is first asked for,
 * each kept while every signal it read is unchanged, and every key's together while
 * every input any of them read (`reads`) answers as it did. Each read asks those
 * inputs once and answers with a lookup by key, so reading every item of a list costs
 * one check of them, as `kept` does for one value; a lookup kept past a later read
 * answers from what that read found. A key is held no longer than whoever holds it.
 * @template {object} K @template V @param {(key: K) => V} make
 * @returns {() => (key: K) => V} */
export function keptEach(make) {
  /** @type {Inputs} */
  let inputs = new Map();
  /** @type {WeakMap<K, import("@preact/signals-core").ReadonlySignal<V>>} */
  let values = new WeakMap();
  let generation = 0;
  const standing = () => {
    if (!stands(inputs)) {
      [inputs, values] = [new Map(), new WeakMap()];
      generation += 1;
    }
    return generation;
  };
  /** @param {K} key */
  const lookup = (key) => {
    within(standing, generation, inputs);
    const [held, each] = [inputs, values];
    let value = each.get(key);
    if (!value) each.set(key, (value = recording(held, () => make(key))));
    try {
      return value.value;
    } catch (error) {
      each.delete(key);
      throw error;
    }
  };
  return () => {
    within(standing, standing(), inputs);
    return lookup;
  };
}
