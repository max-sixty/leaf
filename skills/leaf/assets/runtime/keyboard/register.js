/* Page command registration and ordering. Keyboard policy lives in AGENTS.md.
 *
 * Owners contribute pageScope, pageCommand, and pageRung declarations during construction,
 * before the first scope read. This module stores declarations and order; owners supply
 * command behavior. Widget element scopes join STACK at ELEMENTS. Every table ranks
 * constructed features; an absent feature registers no scope, rung or command.
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
import {
  answersTouch,
  bindings,
  checked,
  touchPresses as pressesOf,
  titleOf,
  descriptionOf,
  lineOf,
  word,
} from "./bindings.js";
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
  "expanded shortcut bar",
  "page map",
  "go to",
  "response options",
  "reactions",
  "page search",
  "target picker",
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
  "drawer", // the drawer that holds the edge
  "narrowing", // the narrowing the user put on the thread list
  "panel", // the thread panel
  "draw mode", // the drawing surface over the page
  "design mode", // the mode that comments on the layer
  "page", // whatever is left, in the chrome, and back onto the page
];

const PAGE_COMMANDS = [
  "comment.create",
  "writing.resume",
  "selection.restore",
  "target.picker.open",
  "reaction.open",
  "page.search.open",
  "page.search.repeat",
  "thread.walk",
  "ask.walk",
  // Scrolling is available in the page and in a covering auxiliary surface, which reuses
  // the rows marked `covering` while the modal floor suspends the rest of page scope.
  "page.move",
  "scroll.move",
  "reading.align.top",
  "history.undo",
  // Below the walks that reach one list at a time, because `g` opens a door to all of
  // them: on a narrow window the sequence hides a second way to somewhere the user can
  // already get to, where a walk it crowded out would be the only one.
  "navigation.go-to.open",
  "draw.mode.enter",
  "design.mode.enter",
  "annotations.toggle",
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

/** Declare a scope at one place in the page's command order. Several instances of an
 * owner may contribute there; each declaration answers whether its own element is
 * active. The returned function removes that instance's declaration. */
export function pageScope(name, declaration) {
  place(STACK, name);
  const declarations = scopes.get(name) ?? [];
  declarations.push(declaration);
  scopes.set(name, declarations);
  resolved = null;
  validated = false;
  return () => {
    const remaining = scopes.get(name)?.filter((item) => item !== declaration) ?? [];
    if (remaining.length) scopes.set(name, remaining);
    else scopes.delete(name);
    resolved = null;
    validated = false;
  };
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

/** Declare one instance's step of Escape's fallback ladder: a function answering what the press would
 * take off right now, as `{title, description?, line?, out}` plus an optional `root` for the surface the
 * step is inside and the `lineWhen` and `promoteEscape` this step wants on the compact
 * line, or null where this step has nothing to take. `RUNG_LADDER` orders the steps. */
export function pageRung(name, reading) {
  place(RUNG_LADDER, name);
  const readings = rungs.get(name) ?? [];
  readings.push(reading);
  rungs.set(name, readings);
  return () => {
    const remaining = rungs.get(name)?.filter((item) => item !== reading) ?? [];
    if (remaining.length) rungs.set(name, remaining);
    else rungs.delete(name);
  };
}

// Resolve from current focus and state. The innermost containing surface takes priority;
// RUNG_LADDER breaks ties within it and orders steps when focus is outside every surface.
function rung() {
  const steps = [];
  for (const name of RUNG_LADDER) {
    for (const reading of rungs.get(name) ?? []) {
      const step = reading();
      if (step) steps.push({ ...step, name });
    }
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
  title: () => (rung() ? titleOf(rung()) : "Back"),
  description: () => (rung() ? descriptionOf(rung()) : undefined),
  line: () => (rung() ? lineOf(rung()) : false),
  lineWhen: () => word(rung()?.lineWhen) !== false,
  promoteEscape: () => word(rung()?.promoteEscape) !== false,
  when: () => Boolean(rung()),
  run: () => rung().out(),
};

function assemble() {
  const rows = PAGE_COMMANDS.flatMap((id) =>
    commands.has(id) ? [commands.get(id)] : [],
  );
  // Every page command answers whether a finger needs a stand-in for its keys (AGENTS.md,
  // "Touch routes"), so a new one meets the question where it is declared.
  const unanswered = rows.filter((row) => !answersTouch(row)).map((row) => row.id);
  if (unanswered.length)
    throw new Error(
      `leaf: ${unanswered.join(", ")} must declare \`touch\`: its words under a finger, or false where a finger reaches it directly`,
    );
  const covering = rows.filter((row) => row.covering);
  return STACK.flatMap((name) => {
    if (name === PAGE) return { rows };
    // Rooted at the surface the live step is inside, so a step off a covering panel or
    // drawer survives the floor that surface establishes while the page below it does not.
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
    return scopes.get(name) ?? [];
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
// The presses a finger reaches through a banner control rather than a key (AGENTS.md,
// "Touch routes"): each a page command declares, in line order, and each a page scope's
// rows declare, scope by scope in STACK order, so the first that stands is the one the
// user is innermost in. Read from the live register, since a scope may join or leave it.
export function touchPresses() {
  pageScopes();
  return {
    commands: PAGE_COMMANDS.flatMap((id) =>
      commands.has(id) ? pressesOf(commands.get(id)) : [],
    ),
    steps: STACK.flatMap((name) =>
      typeof name === "string"
        ? (scopes.get(name) ?? []).map((scope) => ({
            scope,
            presses: scope.rows.flatMap(pressesOf),
          }))
        : [],
    ).filter(({ presses }) => presses.length),
  };
}
export const universalCommandReference = () => commands.get(COMMAND_REFERENCE);
export const textEntryScope = () => scopes.get("text entry")?.[0];
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
