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

   This module imports nothing, so the pure folds can use it. */

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
