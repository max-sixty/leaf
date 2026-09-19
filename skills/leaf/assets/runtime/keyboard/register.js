/* The page's keyboard register: the orders core's keyboard has, and the doors each feature
   owner contributes through.

   A command belongs to the layer that implements its result, so that layer declares it
   where its code is: `pageScope` for a scope of the feature's own — a mode, a surface, an
   interaction holding the keyboard — `pageCommand` for a row in the page's own scope, and
   `pageRung` for a step of Escape's fallback ladder. Contribution runs as each owner is
   constructed, before anything reads a scope. This module holds names, rows and order and
   never a capability, so a feature adds a command without editing it. Widgets use the
   element register (`keys`, `commandScope`) and are spliced in at ELEMENTS; these doors
   are the same idea for a scope whose condition is the page's rather than where the
   reader is standing.

   The orders below are what no single owner can state. `STACK` is the order the
   dispatcher walks, innermost first: element scopes splice in where ELEMENTS stands and
   the return stack where RETURN does. For Escape the dispatcher reads an explicit
   `escape: "inner"` on active modes and the exact focused element, then RETURN, then every
   unmarked fallback, so a place in this list grants no causal priority over those. Every
   reading starts from these scopes, and the reference walks them backwards, so a mode this
   list leaves out is one the reference never names.

   `PAGE_COMMANDS` is the page's own scope, and table order is the line's priority order —
   a total order every row has already, rather than a field one can forget — so the first
   live rows are the short hints. Escape is the default promotion over this order, because
   the way out of a current scene must survive beside its way in. A row can waive only that
   promotion when two local actions on the current state belong together; the binding
   remains live and stays in the reference.

   `RUNG_LADDER` is Escape's fallback for state the reader reached without a registered
   entry: a captured target, a pointer-opened tray, a panel open on arrival, ordinary
   focus traversal. Standing on something is not a rung but the "standing" scope ahead of
   the frames, since letting go is the newest thing the reader can undo. Its rungs
   are contributed like everything else, each by the owner of the state it takes off, and
   `rung` resolves them into the one `navigation.back` row every surface reads. One row
   rather than one per step, because the ladder is one capability whose sentence changes:
   a reference listing each step whose own condition happens to hold would promise presses
   the innermost step has already taken, and a guard on each step against the steps behind
   it would be this list written out once per step. Being the fallback is also what its
   `when` says — no step answers while a commanded entry stands, because that entry is the
   registered way back. */
import { bindings, checked, word } from "./bindings.js";
import { current, RETURN } from "./layer-stack.js";

export const ELEMENTS = Symbol("the scopes of the focused element");
const PAGE = Symbol("the page's own keys");
const COVERING = Symbol("the page's keys inside a covering auxiliary surface");
const RUNGS = Symbol("Escape's fallback ladder");

// The universal route out of a native layer's keyboard boundary, named here because the
// boundary is the dispatcher's rather than the shortcut bar's.
const COMMAND_REFERENCE = "command.reference.open";

const STACK = [
  "command reference",
  "shortcut shelf",
  "page map",
  "go to",
  "response options",
  "reactions",
  "page search",
  "target chooser",
  ELEMENTS,
  RETURN,
  // Right after the frames, so the line's Escape chip keeps the front of the line
  // whichever of the two owns it; among inner scopes the order is moot, since the modes
  // and the Page Map stand it down themselves.
  "standing",
  "versions",
  "composer",
  "text entry",
  "thread",
  "panel",
  COVERING,
  "link",
  "disclosure",
  "draw mode",
  "design mode",
  PAGE,
  // Outermost, so a page command still ranks ahead of the way out on the line.
  RUNGS,
];

// Each rung names what the press takes off, innermost first.
const RUNG_LADDER = [
  "selection", // the selection, or the target a click captured
  "tray", // the tray that holds the edge
  "narrowing", // the narrowing the reader put on the thread list
  "panel", // the thread panel
  "page", // whatever is left, in the chrome, and back onto the page
];

const PAGE_COMMANDS = [
  "ask.activate-nth",
  "comment.create",
  "target.chooser.open",
  "reaction.open",
  "page.search.open",
  "page.search.repeat",
  "thread.walk",
  "ask.walk",
  // Scrolling is available in the page and in a covering auxiliary surface, which reuses
  // the rows marked `covering` while the modal floor suspends the rest of page scope.
  "page.move",
  "scroll.move",
  "history.undo",
  // Below the walks that reach one list at a time, because `g` opens a door to all of
  // them: on a narrow window the sequence hides a second way to somewhere the reader can
  // already get to, where a walk it crowded out would be the only one.
  "navigation.go-to.open",
  "draw.mode.enter",
  "design.mode.enter",
  // The reference's own binding. Its place here is nominal: renderShortcutBar gives it the
  // permanent More control instead of spending a hint slot on it.
  COMMAND_REFERENCE,
  // A real key the browser owns, and one gesture that is not a key at all. Neither says a
  // word for the line, so neither is ever promised as the next press.
  "browser.caret",
  "aim.comment",
];

const scopes = new Map();
const commands = new Map();
const rungs = new Map();
let resolved = null;
let validated = false;
let auxiliaryModality = null;

const place = (where, name) => {
  if (!where.includes(name))
    throw new Error(`leaf: ${String(name)} has no place in the page's keyboard`);
};

/** Declare a scope that stands wherever its own condition holds, rather than where the
 * reader is standing. `name` is the place `STACK` holds for it; `declaration` carries the
 * same fields an element scope does — `title`, `root`, `when`, `at`, `claims`, `escape`,
 * `rows`. Called as the owner is constructed, so a row may close over its state. */
export function pageScope(name, declaration) {
  place(STACK, name);
  if (scopes.has(name)) throw new Error(`leaf: ${name} is declared twice`);
  scopes.set(name, declaration);
  resolved = null;
  validated = false;
  return declaration;
}

/** Declare one row of the page's own scope. `PAGE_COMMANDS` ranks it against every other
 * feature's; `covering: true` keeps it reachable while an auxiliary surface covers the
 * document. */
export function pageCommand(row) {
  place(PAGE_COMMANDS, row.id);
  if (commands.has(row.id)) throw new Error(`leaf: ${row.id} is declared twice`);
  commands.set(row.id, row);
  resolved = null;
  validated = false;
  return row;
}

/** Declare one step of Escape's fallback ladder: a function answering what the press would
 * take off right now, as `{says, does, out}` plus an optional `root` for the surface the
 * step is inside and the `lineWhen` and `promoteEscape` this step wants on the compact
 * line, or null where this step has nothing to take. `RUNG_LADDER` orders the steps. */
export function pageRung(name, reading) {
  place(RUNG_LADDER, name);
  if (rungs.has(name)) throw new Error(`leaf: the ${name} rung is declared twice`);
  rungs.set(name, reading);
  return reading;
}

// The innermost step the reader can still take. Read fresh by every projection, so the
// sentence the reference lists, the word the line paints, and the press the dispatcher
// runs are one answer rather than three readings of the ladder.
function rung() {
  for (const name of RUNG_LADDER) {
    const step = rungs.get(name)();
    if (step) return step;
  }
  return null;
}

// The page's own Escape, said and run off that one object: each rung states the act, the
// word the line paints over it, and the sentence the reference lists. The sentence is the
// rung's for the reason `c`'s is the destination's — the reader can see which branch they
// are in, so a word covering all of them tells them nothing.
const BACK_OUT = {
  id: "navigation.back",
  keys: ["Escape"],
  does: () => rung()?.does,
  line: () => rung()?.says,
  lineWhen: () => word(rung()?.lineWhen) !== false,
  promoteEscape: () => word(rung()?.promoteEscape) !== false,
  when: () => !current() && Boolean(rung()),
  run: () => rung().out(),
};

const missing = (where, held) =>
  where.filter((name) => typeof name === "string" && !held.has(name)).map(String);

function assemble() {
  const absent = [
    ...missing(STACK, scopes),
    ...missing(PAGE_COMMANDS, commands),
    ...missing(RUNG_LADDER, rungs),
  ];
  if (absent.length)
    throw new Error(`leaf: the page's keyboard has no owner for ${absent.join(", ")}`);
  const rows = PAGE_COMMANDS.map((id) => commands.get(id));
  const covering = rows.filter((row) => row.covering);
  return STACK.map((name) => {
    if (name === PAGE) return { rows };
    // Rooted at the surface the live step is inside, so a step off a covering panel or
    // tray survives the floor that surface establishes while the page below it does not.
    if (name === RUNGS)
      return { root: () => rung()?.root ?? document, rows: [BACK_OUT] };
    if (name === COVERING)
      return {
        title: "In the covering auxiliary surface",
        root: coveringAuxiliarySurface,
        when: () => Boolean(coveringAuxiliarySurface()),
        at: () => Boolean(coveringAuxiliarySurface()),
        rows: covering,
      };
    if (typeof name !== "string") return name;
    return scopes.get(name);
  });
}

// Declaring is not reading, as it is not for an element scope: `checked` reads the rows as
// written, and a row's dynamic key set is its owner's state, which is not settled while the
// owners are still being constructed. So the stack is assembled and checked on the first
// read of it, by which time every owner stands. The assembled stack is published before
// that reading, because a row's key set may consult the register on its way to answering.
export function pageScopes() {
  resolved ??= assemble();
  if (!validated) {
    validated = true;
    for (const scope of resolved)
      if (typeof scope !== "symbol")
        checked(scope.rows, scope.title ?? "the page's own keys");
  }
  return resolved;
}
export const universalCommandReference = () => commands.get(COMMAND_REFERENCE);
export const textEntryScope = () => scopes.get("text entry");
// What an interaction claiming the whole keyboard still lets through: the one route to
// another layer, read off the row so a fact about a binding cannot be written where the
// binding cannot correct it.
export const allButCommandReference = (binding) =>
  !bindings(universalCommandReference()).includes(binding);

// The auxiliary layer's readings, held here because the dispatcher's own closure stops at
// this register: it resolves a press against the register and the focused scope, and an
// edge to the surface owner would give it that owner's whole initialization graph.
export function registerAuxiliaryModality(modality) {
  auxiliaryModality = modality;
}
export const coveringAuxiliarySurface = () => auxiliaryModality.coveringSurface();
export const coveringAuxiliaryFocus = () => auxiliaryModality.coveringFocus();
export const auxiliaryAllowsNativeLayer = (node, establishedOver) =>
  auxiliaryModality.allowsNativeLayer(node, establishedOver);
