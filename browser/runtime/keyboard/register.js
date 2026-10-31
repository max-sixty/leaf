/* Page command registration and ordering. Keyboard policy lives in AGENTS.md.
 *
 * Owners contribute pageScope, pageCommand, and pageRung declarations during construction,
 * before the first scope read. This module stores declarations and order; owners supply
 * command behavior. Widget element scopes join STACK at ELEMENTS. Every table ranks
 * constructed features; an absent feature registers no scope, rung or command.
 *
 * STACK orders ordinary dispatch, innermost first; the command reference reads it in
 * reverse. Escape additionally resolves inner claims and focused-surface containment.
 * PAGE_COMMANDS orders the page's commands wherever they are listed.
 *
 * RUNG_LADDER orders sibling fallback steps. `rung` selects the step inside the focused
 * surface first and exposes it as one navigation.back command, so dispatch and every
 * presentation describe the same available step. The current scope handles letting go
 * of a page destination before the fallback ladder.
 */
import {
  bindings,
  checked,
  declareCommandReadiness,
  touchPresses as pressesOf,
  titleOf,
  descriptionOf,
} from "./bindings.js";
import { focused } from "../focus.js";
import { paintKeys, watchCommandScopes } from "./scopes.js";
// Native activation reads declarations without assembling or validating the keyboard
// during feature construction. Both element and page commands share one control owner.
watchCommandScopes(() => [
  ...[...scopes.values()].flat(),
  { rows: [...commands.values()] },
]);
import { renderedUnder } from "../shadow.js";
import { offlineInteractive } from "../context.js";

export const ELEMENTS = Symbol("the scopes of the focused element");
const PAGE = Symbol("the page's own keys");
const RUNGS = Symbol("Escape's fallback ladder");

// The universal route out of a native layer's keyboard boundary, named here because the
// boundary is the dispatcher's rather than a presentation's.
const COMMAND_REFERENCE = "command.reference.open";
const GO_TO = "navigation.go-to.open";

const STACK = [
  "command reference",
  "page map",
  "go to",
  "response options",
  "reactions",
  "page search",
  "target picker",
  ELEMENTS,
  "region capture",
  // Among inner scopes the order is moot, since the modes and the Page Map stand it down
  // themselves.
  "current-location",
  "versions",
  "composer",
  "text entry",
  "thread",
  "link",
  "disclosure",
  // A heading or the section it opens, whose link Enter copies (heading-links.js).
  "heading",
  // The modes keep their own letters here and declare their Escape on the ladder,
  // because a mode is the stance the whole page is in and a surface opened while one
  // holds is opened inside it: a view the floating panel opens in Design mode comes off
  // first.
  "draw mode",
  "design mode",
  // A to-do on the user at the walk’s current location, whose Done this scope carries.
  // It stands outside the modes, so a mode entered on a to-do keeps the panel's way
  // out (touch-controls.js, the innermost stance).
  "todo",
  PAGE,
  // Outermost, so a page command still ranks ahead of the way out.
  RUNGS,
];

// Each rung names what the press takes off, innermost first. This is the order among
// siblings; `rung` reads containment over it, so the surface the user is in
// comes off before one they are not.
const RUNG_LADDER = [
  "selection", // the selection, or the target a click captured
  "margin options", // the margin entry cluster the user unfolded
  "floating panel", // the menu or view the floating panel opened above its row
  "draw mode", // the drawing surface over the page
  "design mode", // the mode that comments on the layer
  "page", // whatever is left, in the chrome, and back onto the page
];

const PAGE_COMMANDS = [
  "comment.create",
  "writing.resume",
  "message.edit.restore",
  "selection.restore",
  "target.picker.open",
  "reaction.open",
  "page.search.open",
  "page.search.repeat",
  "thread.walk",
  "queue.walk",
  "change.walk",
  "page.move",
  "scroll.move",
  "reading.align.top",
  "thread.unread.first",
  "navigation.panel.threads",
  "navigation.panel.queue",
  "navigation.panel.leaves",
  "navigation.page-map",
  "version.open",
  "history.undo",
  // Below the walks that reach one list at a time, because `g` opens a door to all of
  // them: a second way to somewhere the user can already get to.
  GO_TO,
  "draw.mode.enter",
  "capture.region.open",
  "design.mode.enter",
  "annotations.toggle",
  "panel.floating.fold",
  COMMAND_REFERENCE,
  // A real key the browser owns, and one gesture that is not a key at all.
  "browser.caret",
  "aim.comment",
];

const scopes = new Map();
const commands = new Map();
const rungs = new Map();
let resolved = null;
let validated = false;

const place = (where, name) => {
  if (!where.includes(name))
    throw new Error(`leaf: ${String(name)} has no place in the page's keyboard`);
};

/** Declare a scope at one place in the page's command order. Several instances of an
 * owner may contribute there; each declaration answers whether its own element is
 * active. The returned function removes that instance's declaration. */
export function pageScope(name, declaration) {
  place(STACK, name);
  if (declaration.ready !== undefined)
    declareCommandReadiness(declaration.rows, declaration.ready);
  const declarations = scopes.get(name) ?? [];
  declarations.push(declaration);
  scopes.set(name, declarations);
  resolved = null;
  validated = false;
  paintKeys();
  return () => {
    const remaining = scopes.get(name)?.filter((item) => item !== declaration) ?? [];
    if (remaining.length) scopes.set(name, remaining);
    else scopes.delete(name);
    resolved = null;
    validated = false;
    paintKeys();
  };
}

/** Declare one row of the page's own scope. `PAGE_COMMANDS` ranks it against every other
 * feature's. */
export function pageCommand(row) {
  place(PAGE_COMMANDS, row.id);
  if (commands.has(row.id)) throw new Error(`leaf: ${row.id} is declared twice`);
  commands.set(row.id, row);
  resolved = null;
  validated = false;
  paintKeys();
  return row;
}

/** Declare one instance's step of Escape's fallback ladder: a function answering what the press would
 * take off right now, as `{title, description?, out}` plus an optional `root` for the surface the
 * step is inside, or null where this step has nothing to take. `RUNG_LADDER` orders the steps. */
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
    if (!root || root === document || !renderedUnder(here, root)) continue;
    if (!surface || renderedUnder(root, surface)) surface = root;
  }
  const holds = (step) => renderedUnder(step.root ?? document, surface);
  return (surface && steps.find(holds)) ?? steps[0] ?? null;
}
// The page's own Escape, said and run off that one object: each rung states the act, its
// word, and the sentence the reference lists. The sentence is the rung's for the reason
// `c`'s is the destination's — the user can see which branch they are in, so a word
// covering all of them tells them nothing.
const BACK_OUT = {
  id: "navigation.back",
  keys: ["Escape"],
  title: () => (rung() ? titleOf(rung()) : "Back"),
  description: () => (rung() ? descriptionOf(rung()) : undefined),
  when: () => Boolean(rung()),
  run: () => rung().out(),
};

function assemble() {
  const rows = PAGE_COMMANDS.flatMap((id) =>
    commands.has(id) ? [commands.get(id)] : [],
  );
  // Every page command answers whether a finger needs a row of the menu for its keys,
  // and every row of a page scope that makes a press how a finger reaches its result
  // without one: it is its stance's way out, which the panel's ✕ runs, or `touch:
  // false`, where a finger acts on what the row acts on (AGENTS.md, "Touch routes"). So
  // a new one meets the question where it is declared, whatever keys it has now.
  const unanswered = rows.filter((row) => row.touch === undefined).map((row) => row.id);
  if (unanswered.length)
    throw new Error(
      `leaf: ${unanswered.join(", ")} must declare \`touch\`: its words under a finger, or false where a finger reaches it directly`,
    );
  const scopeRows = [...scopes.values()].flat().flatMap((scope) => scope.rows);
  const unreached = scopeRows
    .filter((row) => row.run && !row.exit && row.touch !== false)
    .map((row) => row.id);
  if (unreached.length)
    throw new Error(
      `leaf: ${unreached.join(", ")} must be its stance's \`exit\` or declare \`touch: false\`: only a page command takes a finger's words`,
    );
  return STACK.flatMap((name) => {
    if (name === PAGE) return { rows };
    // Rooted at the surface the live step is inside.
    if (name === RUNGS)
      return { root: () => rung()?.root ?? document, rows: [BACK_OUT] };
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
  // Exports retain widget scopes and the native input claims the dispatcher places
  // among them. Page navigation and chrome have no surfaces in that document.
  if (offlineInteractive) return [ELEMENTS];
  resolved ??= assemble();
  if (!validated) {
    validated = true;
    for (const scope of resolved)
      if (typeof scope !== "symbol")
        checked(scope.rows, scope.title ?? "the page's own keys");
  }
  return resolved;
}
const namedScopes = () =>
  STACK.flatMap((name) => (typeof name === "string" ? (scopes.get(name) ?? []) : []));
const exitOf = (scope) => scope.rows.find((row) => row.exit) ?? null;
// The presses a finger reaches through a row of the page's menu rather than a key
// (AGENTS.md, "Touch routes"): each a page command declares, in line order.
export function touchPresses() {
  pageScopes();
  return PAGE_COMMANDS.flatMap((id) =>
    commands.has(id) ? pressesOf(commands.get(id)) : [],
  );
}
// The stances, innermost first: each scope with a row marked `exit`, its way out.
export function stances() {
  pageScopes();
  return namedScopes().flatMap((scope) => {
    const exit = exitOf(scope);
    return exit ? [{ scope, exit }] : [];
  });
}
export const universalCommandReference = () =>
  offlineInteractive ? undefined : commands.get(COMMAND_REFERENCE);
export const textEntryScope = () => scopes.get("text entry")?.[0];
// What an interaction claiming the whole keyboard still lets through: the one route to
// another layer, read off the row so a fact about a binding cannot be written where the
// binding cannot correct it.
export const allButCommandReference = (binding) =>
  !bindings(universalCommandReference()).includes(binding);
// What a surface resting the page's keys still lets through: the reference, and Go-to,
// whose doors open a surface or put it away from inside it.
export const pageDoor = (binding) =>
  [COMMAND_REFERENCE, GO_TO].some(
    (id) => commands.has(id) && bindings(commands.get(id)).includes(binding),
  );
