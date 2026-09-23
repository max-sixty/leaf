/* Page command registration and ordering. Keyboard policy lives in AGENTS.md.
 *
 * Owners contribute pageScope, pageCommand, and pageRung declarations during construction,
 * before the first scope read. This module stores declarations and order; owners supply
 * command behavior. Widget element scopes join STACK at ELEMENTS.
 *
 * STACK orders ordinary dispatch, innermost first; the command reference reads it in
 * reverse. Escape additionally resolves inner claims and focused-surface containment.
 * PAGE_COMMANDS orders shortcut-bar hints. Escape is promoted unless its row waives
 * promotion; that waiver leaves its binding and reference entry available.
 *
 * RUNG_LADDER orders sibling fallback steps. `rung` selects the step inside the focused
 * surface first and exposes it as one navigation.back command, so dispatch and every
 * presentation describe the same available step. The standing scope handles letting go
 * of a page destination before the fallback ladder.
 */
import { bindings, checked, word } from "./bindings.js";
import { focused } from "./scopes.js";
import { under } from "../shadow.js";

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
  // Among inner scopes the order is moot, since the modes and the Page Map stand it down
  // themselves.
  "standing",
  "versions",
  "composer",
  "text entry",
  "thread",
  "panel",
  COVERING,
  "link",
  "disclosure",
  // The modes keep their own letters here and declare their Escape on the ladder,
  // because a mode is the stance the whole page is in and a surface opened while one
  // holds is opened inside it: a send made in Design mode opens Threads, and the panel
  // comes off first.
  "draw mode",
  "design mode",
  PAGE,
  // Outermost, so a page command still ranks ahead of the way out on the line.
  RUNGS,
];

// Each rung names what the press takes off, innermost first. This is the order among
// siblings; `rung` reads containment over it, so the surface the user is standing in
// comes off before one they are not.
const RUNG_LADDER = [
  "selection", // the selection, or the target a click captured
  "margin options", // the margin entry cluster the user unfolded
  "tray", // the tray that holds the edge
  "narrowing", // the narrowing the user put on the thread list
  "panel", // the thread panel
  "draw mode", // the drawing surface over the page
  "design mode", // the mode that comments on the layer
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
  // them: on a narrow window the sequence hides a second way to somewhere the user can
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
 * user is standing. `name` is the place `STACK` holds for it; `declaration` carries the
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

// Resolve from current focus and state. The innermost containing surface takes priority;
// RUNG_LADDER breaks ties within it and orders steps when focus is outside every surface.
function rung() {
  const steps = [];
  for (const name of RUNG_LADDER) {
    const step = rungs.get(name)();
    if (step) steps.push({ ...step, name });
  }
  const here = focused();
  let surface = null;
  for (const { root } of steps) {
    if (!root || root === document || !under(here, root)) continue;
    if (!surface || under(root, surface)) surface = root;
  }
  const holds = (step) => under(step.root ?? document, surface);
  return (surface && steps.find(holds)) ?? steps[0] ?? null;
}
// The page's own Escape, said and run off that one object: each rung states the act, the
// word the line paints over it, and the sentence the reference lists. The sentence is the
// rung's for the reason `c`'s is the destination's — the user can see which branch they
// are in, so a word covering all of them tells them nothing.
const BACK_OUT = {
  id: "navigation.back",
  keys: ["Escape"],
  does: () => rung()?.does,
  line: () => rung()?.says,
  lineWhen: () => word(rung()?.lineWhen) !== false,
  promoteEscape: () => word(rung()?.promoteEscape) !== false,
  when: () => Boolean(rung()),
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

// The auxiliary layer's surface reading, held here because the dispatcher's own closure
// stops at this register: it resolves a press against the register and the focused scope,
// and an edge to the surface owner would give it that owner's whole initialization graph.
export function registerAuxiliaryModality(modality) {
  auxiliaryModality = modality;
}
export const coveringAuxiliarySurface = () => auxiliaryModality.coveringSurface();
