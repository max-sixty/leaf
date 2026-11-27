// @ts-check
/* Readings kept by what each was read from.

   `kept` keeps a reading of the state or the page, and `keptEach` one for each key, as
   On Me keeps each item's seat. A reading holds one value, made again only where
   something it was made from has moved: an argument it was given, compared by
   identity and two lists by their items; a signal it read, the application state's
   (`readPart`) and a widget module's own among them, since a reading is a `computed`;
   a version it read; or a reading it read, so a reading made around another stands no
   longer than the one inside it. It is never told what it reads, so it stays current
   however its code changes. A key is an object held weakly, so a reading goes with the
   record or element it is about, and nothing sweeps keys.

   A fact outside any signal, such as the page's reading or the threads' placement, has
   a `version`: a count its owner moves when the fact changes, which a reader of the
   fact reads. A view drawn from such a fact isn't told when it moves, since Leaf draws
   a view of the page when the page is presented (`presentDocument`), not on each
   change the page hears, as on each frame a widget redraws a counter. So a reading
   that read a version asks it again when it is next read, and is made afresh where it
   moved. Every move of any version moves one count, and a reading asked again at the
   count it was last checked at stands without asking anything, so reading a kept value
   costs a lookup while nothing moved.

   The browser tells the page's watcher of a change a microtask late, and placement
   settles only when asked, so their versions move only when their owners catch up.
   Such a version names its catch-up, and a reading that read one, itself or through a
   reading inside it, runs that catch-up when read from outside any other reading,
   before it is checked: a reading read inside another was caught up with it. Leaf
   can't take the changes once for a batch of reads instead, since a write after that
   in the same task would go unheard. A reading that read no such version, as the
   publication's fold reads none, catches nothing up. What the page's watcher doesn't
   hear, such as a datum's source or a role making a press, is read beside what
   announces its change, the document presented or a widget's layout changing
   (readings/anchor-resolution.js, `currentDatums`, `claimsVisualGesture`).

   The publication's fold keeps each record it makes this way, keyed by the served
   record it is made from, so a publication about one thing makes only that thing's
   records again: the served reading keeps every record the server didn't change
   (`completeState` in `transport/layer-client.js`), and publication gives each unchanged part
   its old identity (base/snapshot.js, `share`). A make at module scope reads only
   its arguments, so a fold can't read more than it is kept by.

   This module imports nothing but signals, so the pure folds can use it. */
import { computed } from "/vendor/signals-core.js";

/** @typedef {() => void} CatchUp
 * @typedef {{read(): number, move(): void, [AT]: () => number}} Version
 * @typedef {{
 *   args: readonly unknown[],
 *   value: import("@preact/signals-core").ReadonlySignal<unknown>,
 *   versions: Map<Version, number> | null,
 *   within: Set<Entry> | null,
 *   catchUps: Set<CatchUp> | null,
 *   fresh: boolean,
 *   checked: number,
 * }} Entry */

// Every move of any version, so a reading checked since the last one stands.
let moves = 0;
// Where a version stands, asked without saying a reading read it.
const AT = Symbol("at");
// The reading being made, which records what it reads.
/** @type {Entry | null} */
let making = null;
// The catch-ups run since a reading was read from outside every other, so a reading
// read inside it runs only those it adds, and how many readings are being read.
/** @type {CatchUp[]} */
const caughtUp = [];
let depth = 0;

/** A count of a fact no signal carries, which its owner moves when the fact changes:
 * `read()` answers it, and says the reading being made, if one is, read it. An owner
 * whose version moves only when it catches up, as the page's watcher takes what the
 * browser reports late, passes `catchUp`, which a reading runs as it first reads the
 * version, so it records where the fact stands, and again before it is checked. A
 * catch-up that reads its own version, as the page's does, is asked once.
 * @param {CatchUp | null} [catchUp] @returns {Version} */
export function version(catchUp = null) {
  let at = 0;
  /** @type {Version} */
  const counted = {
    read() {
      const versions = making && (making.versions ??= new Map());
      if (making && versions && !versions.has(counted)) {
        if (catchUp) {
          (making.catchUps ??= new Set()).add(catchUp);
          versions.set(counted, NaN);
          catchUp();
        }
        versions.set(counted, at);
      }
      return at;
    },
    move() {
      at += 1;
      moves += 1;
    },
    [AT]: () => at,
  };
  return counted;
}

/** @param {unknown} a @param {unknown} b */
const sameArgument = (a, b) =>
  Object.is(a, b) ||
  (Array.isArray(a) &&
    Array.isArray(b) &&
    a.length === b.length &&
    a.every((item, at) => Object.is(item, b[at])));
/** @param {readonly unknown[]} held @param {readonly unknown[]} args */
const sameArguments = (held, args) =>
  held.length === args.length && args.every((arg, at) => sameArgument(arg, held[at]));

/** Whether every version an entry read, and every reading it read, stands.
 * @param {Entry} entry @returns {boolean} */
function stands(entry) {
  if (entry.fresh) return false;
  if (entry.checked === moves) return true;
  if (entry.versions)
    for (const [counted, at] of entry.versions) if (counted[AT]() !== at) return false;
  if (entry.within) for (const inner of entry.within) if (!stands(inner)) return false;
  entry.checked = moves;
  return true;
}

/** @template {object} K @template {unknown[]} A @template V
 * @param {(key: K, ...args: A) => V} make @param {K} key @param {A} args @returns {Entry} */
function entryOf(make, key, args) {
  /** @type {Entry} */
  const entry = {
    args,
    value: computed(() => {
      // A signal it read moved: what it reads now is all it reads.
      entry.versions = entry.within = entry.catchUps = null;
      entry.fresh = false;
      const outer = making;
      making = entry;
      try {
        return make(key, ...args);
      } finally {
        making = outer;
      }
    }),
    versions: null,
    within: null,
    catchUps: null,
    fresh: false,
    checked: moves,
  };
  return entry;
}

/** @param {Entry} entry */
function catchUp(entry) {
  if (!entry.catchUps) return;
  for (const each of entry.catchUps)
    if (!caughtUp.includes(each)) {
      caughtUp.push(each);
      each();
    }
}

/** A reader of what `make` makes of each key and the arguments it is read with, made
 * when the key is first asked for and kept while those arguments, every signal it read,
 * every version it read and every reading it read stand. A make that throws keeps
 * nothing, so it is made again, as is every reading made around it.
 * @template {object} K @template {unknown[]} A @template V
 * @param {(key: K, ...args: A) => V} make @returns {(key: K, ...args: A) => V} */
export function keptEach(make) {
  /** @type {WeakMap<K, Entry>} */
  const entries = new WeakMap();
  return (key, ...args) => {
    if (depth++ === 0) caughtUp.length = 0;
    try {
      let entry = entries.get(key);
      if (entry) catchUp(entry);
      if (!entry || !sameArguments(entry.args, args) || !stands(entry))
        entries.set(key, (entry = entryOf(make, key, args)));
      /** @type {V} */
      let value;
      try {
        value = /** @type {V} */ (entry.value.value);
      } catch (error) {
        // Made again when next asked for, as is a reading around it that caught the
        // throw.
        if (entries.get(key) === entry) entries.delete(key);
        if (making) making.fresh = true;
        throw error;
      }
      // One that read a fact nothing versions is kept for no later read.
      if (entry.fresh && entries.get(key) === entry) entries.delete(key);
      if (making && making !== entry) {
        if (entry.fresh) making.fresh = true;
        // Only a reading a version can move stands no longer than its own inputs; any
        // other changes only with its arguments or a signal, which the reading around it
        // hears for itself.
        if (entry.versions || entry.within) (making.within ??= new Set()).add(entry);
        if (entry.catchUps)
          for (const each of entry.catchUps) (making.catchUps ??= new Set()).add(each);
      }
      return value;
    } finally {
      depth -= 1;
    }
  };
}

/** Says that the reading being made, if one is, reads a fact no version tracks, such as
 * the words of an element no document reads, so it is made afresh each time it is read,
 * as is every reading around it. */
export function unkept() {
  if (making) making.fresh = true;
}

/** A reader of what `make` makes of the arguments it is read with, kept as `keptEach`
 * keeps each key's.
 * @template {unknown[]} A @template T @param {(...args: A) => T} make
 * @returns {(...args: A) => T} */
export function kept(make) {
  const one = {};
  const each = keptEach((/** @type {object} */ _, /** @type {A} */ ...args) =>
    make(...args),
  );
  return (...args) => each(one, ...args);
}
