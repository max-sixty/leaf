// Compiled from rank.ts by build/typescript.mjs; edit that file.
/* Rank keys: where a unit stands among its container's siblings, as a coordinate of its
   own. Nothing here reads the page: each function takes the state it works on.

   A position record carries a rank rather than an index. A rank is a base-36 fraction
   written as its digits after the point, `0-9a-z`, never ending in `0`, so ordinary
   string order is numeric order and there is always a key strictly between two others.
   A container lists its units by rank, ties by id (`byRank`). An index counts siblings,
   so it means something only against the order the other moves left; a rank means the
   same thing whichever of the other moves stand, so undoing or superseding one card's
   move never shifts another card.

   Authored units rank by their authored index, `authoredRank(i)`, a key that does not
   depend on how many siblings follow. A widget computes the rank of a unit it drops
   with `rankAt`, from the position verb's state it drew. `projection.py`'s
   `authored_rank` and `registry/contract.py`'s `RANK` state the same two rules for
   the Python fold and the append door, and `tests/rank_cases.json` holds both
   runtimes to the same cases.

   A rank lies among the container's authored units on the revision the user moved on,
   so it holds while a revision authors them the same way. A revision that authors them
   differently absorbs the move: it writes the unit where the move left it, and its
   markup places the unit. The server marks such an entry `absorbed` for the document
   it reads, and it no longer places its unit. */

const DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz";

/** The rank of the unit at `index` in its authored container. */
export const authoredRank = (index) =>
  "z".repeat(Math.floor(index / 35)) + DIGITS.charAt((index % 35) + 1);

/** The order a container lists its units in: by rank, ties by id.
 * @param ranks each unit's rank by id */
export const byRank = (ranks) => (a, b) => {
  const left = ranks[a];
  const right = ranks[b];
  if (left !== undefined && right !== undefined && left !== right)
    return left < right ? -1 : 1;
  return a < b ? -1 : a > b ? 1 : 0;
};

// A key strictly between `before` ("" is the start) and `after` (null is the end).
// Equal bounds have nothing between them, so the key ties and ids decide. An open end
// steps one digit past its neighbour rather than halving the gap, so a column that only
// ever grows at one end gains a character per 35 drops rather than per 5; an empty
// container starts in the middle.
function rankBetween(before, after) {
  if (after === null) return before ? rankAfter(before) : "i";
  if (!before) return rankBefore(after);
  if (before >= after) return before;
  return midpoint(before, after);
}

function rankAfter(key) {
  const digit = DIGITS.indexOf(key.charAt(0));
  if (digit < DIGITS.length - 1) return DIGITS.charAt(digit + 1);
  return "z" + (key.length > 1 ? rankAfter(key.slice(1)) : "1");
}

function rankBefore(key) {
  if (key.length > 1 && key.charAt(0) !== "0") return key.charAt(0);
  const digit = DIGITS.indexOf(key.charAt(0));
  if (digit > 1) return DIGITS.charAt(digit - 1);
  return "0" + (key.length > 1 ? rankBefore(key.slice(1)) : "z");
}

function midpoint(before, after) {
  if (after !== null) {
    let n = 0;
    while ((before[n] ?? "0") === after[n]) n += 1;
    if (n > 0) return after.slice(0, n) + midpoint(before.slice(n), after.slice(n));
  }
  const low = before ? DIGITS.indexOf(before.charAt(0)) : 0;
  const high = after !== null ? DIGITS.indexOf(after.charAt(0)) : DIGITS.length;
  if (high - low > 1) return DIGITS.charAt(Math.round((low + high) / 2));
  if (after !== null && after.length > 1) return after.charAt(0);
  return DIGITS.charAt(low) + midpoint(before.slice(1), null);
}

/** The rank that puts `unit` at `index` among the other units a position verb's state
 * lists in `container`, and keeps it there however other units move: a widget's own
 * reading of where a gesture dropped it. `value` maps each container's id to its
 * units' ids in order, and `ranks` gives each unit's rank. */
export function rankAt({ value, ranks }, container, index, unit) {
  const members = value[container];
  if (!members) throw new Error(`Unknown position container ${container}`);
  const others = members.filter((id) => id !== unit);
  const before = others[index - 1];
  const after = others[index];
  return rankBetween(
    before ? (ranks[before] ?? "") : "",
    after ? (ranks[after] ?? null) : null,
  );
}
