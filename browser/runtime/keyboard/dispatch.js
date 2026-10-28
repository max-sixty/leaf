/* The dispatcher: which scope answers a press, what it owes the platform, and the one
   unwind step Escape takes.

   Scopes nest by focus. `scopesFor` produces the active stack and element scopes are
   spliced where their elements stand. The dispatcher walks innermost first. A scope owns
   every ordinary binding it declares while the user is in that scope, whether or
   not the command is currently live. A live command runs and prevents the platform
   default; an unavailable command suppresses outer Leaf meanings but leaves any browser
   default intact. Escape instead continues to the next live semantic unwind. A `native`
   row runs and stops the scope walk but leaves that default intact. Undeclared keys
   continue outward through ancestor scopes to the page.

   Leaf must not block standard platform or browser shortcuts. A handler prevents a
   default only after a Leaf command owns the complete modified press; secondary clicks
   and the native context menu remain the browser's too.

   `claims` lists platform keys a scope consumes even when no registered row answers them.
   A text entry scope uses `takesLetters` and claims character keys plus the keys that
   edit that specific control: Enter, deletion, caret movement, Home/End, and page
   movement. The claim follows the base key through modifiers, so Shift+Arrow selection,
   Alt character composition, and Mod editing commands remain native. It does not blanket
   checkbox, Escape, or unrelated function keys merely because they are form-related.
   Radio and slider navigation has its own narrow claim at the focused control, so
   an arrow changes that control without also moving its containing widget. Open select
   options retain typeahead when focus moves into their list. Native activation, such as
   Enter on a link or Space on a button, is the narrowest claim: it withholds its press
   from every outer row that would run something else and leaves the rows that only name
   the press (`nativeActivationAt`). An exact element scope stands before these native
   claims, so a wired text field keeps its own Escape or submit binding; the claims then
   stand before ancestor widget scopes.

   One box inside another scope states only what it does differently. The find box
   registers Enter on the exact input to enter the first search result. Its Escape uses
   the ordinary text-entry row to return to the panel, keeping the query. Exact input
   rows stand before the general text-entry claim, which stands before ancestor widgets.

   `activeCommandLabel` projects the
   dispatcher's live result into the destination composition box's placeholder. Each
   box's `aria-label` remains its shortcut-free accessible name.

   Escape is an ordinary binding in each row and a semantic ordering in the dispatcher.
   It unwinds the state standing in front of the user rather than a history of how they
   reached it, so nothing here records a press. An active mode and the focused control's
   specific inner step stand first; then the surface holding focus with whatever stands
   inside it, and last the steps rooted outside that surface, in the register's order.
   The innermost live row owns exactly one unwind step. A query clear, box return, panel
   dismissal, decision release, and return to the page cannot cascade from one keypress.
   A scope does not need a private `keydown` listener or hand-written `preventDefault` to
   protect that contract.

   Auto popovers and modal dialogs are the platform's modes, and the layer stack holds
   them in the order they opened. The dispatcher tiers the scopes over that stack from the
   top down: each layer takes the scopes rooted inside it, the topmost layer also takes
   the focused element's scopes and explicitly inner modes, and a boundary follows each
   layer. A modal is a floor, so every scope below the newest one is dropped and the inert
   document cannot answer. A popover is nonmodal, so the scopes it did not take stay
   reachable for keys its boundary does not claim, while its Escape cannot fall through
   into the covered page. An inner Leaf row can therefore unwind a step in that layer,
   while an unhandled Escape reaches the browser and cannot fall through. The universal
   reference is the boundary's one route through to another layer.

   A popover hands focus back to whatever had it when the popover showed — not to its
   invoker, and not to `showPopover({source})`, which buys the anchor and the nesting of
   popovers and nothing about focus. So a key that opens a layer runs the press from
   the control itself rather than opening it from the page, and every door leaves the same
   way out. Where Leaf has to hand focus back itself, scope that to the door that needs it
   rather than to focus landing on the body: a light dismissal restores nothing on
   purpose, and a user who pressed away into the page is not asking to be moved to the
   control they pressed away from. Nor does a `source` spare its own press from light
   dismissal; only a declared invoker (`popovertarget`, `commandfor`) is spared, so a
   control whose second press puts its layer away declares itself the invoker.

   A declared native button's click and keyboard route invoke the same semantic `run`.
   Native inputs and links retain their platform activation. Arrival may focus or reveal
   a control before activation. Modality checks belong only to gesture guards before
   activation, such as refusing the mouseup that ends a text-selection drag. */
import {
  answers,
  bindings,
  bindingEnabledFor,
  quickShortcuts,
  declaredBindings,
  allBindings,
  titleOf,
  descriptionOf,
  commandEntries,
  commandRoutes,
  commandReady,
  scopeAvailable,
  live,
  routedCommand,
  referencedCommandEntry,
  spell,
  word,
} from "./bindings.js";
import {
  ELEMENTS,
  pageScopes,
  stances,
  textEntryScope,
  universalCommandReference,
} from "./register.js";
import { EVERYTHING, nativeActivationAt, nativeClaimAt } from "./text-entry.js";
import { takesLetters, focused, recoveredLabelFocus } from "../focus.js";
import { runLanding, scopesAt, scopesFor, scopeIdentity } from "./scopes.js";
import { nativeLayers } from "./layer-stack.js";
import { composedParentNode, renderedUnder, excludedByInert } from "../shadow.js";

// The two questions a scope answers, named apart because the surfaces ask them apart: the
// reference lists a scope the page *has* and filters its rows by liveness only where the user
// is in it, while the dispatcher wants both at once. Spelled `!x || x()`
// in three places before, which is a rule written three times and named nowhere.
const pageHas = scopeAvailable;
export const userIn = (scope) => {
  // Native modality excludes everything below its layer floor. An explicitly inert
  // subtree can also stand inside that floor,
  // and none of its latent scopes may answer a key or advertise a live command.
  if (excludedByInert(scopeRoot(scope))) return false;
  return !scope.at || scope.at();
};
// Where the user is first, and what the page has second: both are pure and the and is
// the same either way round, but `at` is a class check and a `when` may be the whole event
// log folded — so the walk asks the cheap question of every scope and the dear one only of
// the scopes containing the current location. That is the rule the dispatcher's row loop already
// keeps and the control scope's own comment already claims ("`at` is asked first and answers
// false wherever this could be in doubt, so a paint never reaches it"), and the scope walk
// was the one place it was not true. The sequence is what made it bite: its `when` reaches the
// decisions fold and then every link on the page, once per keydown, from the first keystroke of
// the first comment.
const currentLocation = (scope) => userIn(scope) && pageHas(scope);
/** The stance the user is in, innermost, with its way out (register.js, `stances`),
 * or null. */
export const innermostStance = () =>
  stances().find(({ scope }) => currentLocation(scope)) ?? null;
const nativeBoundary = (claims) => ({
  get rows() {
    const reference = universalCommandReference();
    return reference ? [reference] : [];
  },
  claims,
  escapeBoundary: true,
});
const MODAL_BOUNDARY = nativeBoundary(EVERYTHING);
const POPOVER_BOUNDARY = nativeBoundary((binding) => binding === "Escape");
const scopeRoot = (scope) => {
  const declared = scope.root ?? scope.el ?? document;
  return typeof declared === "function" ? declared() : declared;
};
const innerEscape = (scope, active) => scope.escape === "inner" || scope.el === active;
// Every scope the user is in, innermost first. The whole list: what a nearer
// scope takes out of reach is the walk's own business, and both walkers say it the same
// way — a binding some nearer row has already named, or one a nearer scope claims. Cutting
// the list here instead was the same statement made where only one of the two shadowings
// could be seen.
//
// How far a node sits above the user, or -1 where it is not above them at all. The
// document is above every user, at the top of the walk.
const above = (node, active) => {
  let depth = 0;
  for (let up = active; up; up = composedParentNode(up)) {
    if (up === node) return depth;
    depth += 1;
  }
  return -1;
};
// Containment before kind, the same rule the ladder reads over its own steps. The
// register's order says which of two steps is the inner one; it cannot say which of them
// the user is inside, and a composer left open out on the page is older than the panel
// they are reading a thread in however the register ranks the two. So the surface holding
// focus answers first, with every step rooted inside it, innermost root first — the reply
// box in a margin card is inside the card, so leaving the box comes before dismissing it
// — and the steps rooted outside that surface keep the register's order behind them.
//
// One reading of each root, because a root may be a thunk over the whole ladder.
const escapeOrder = (scopes, active) => {
  const boundaryAt = scopes.findIndex((scope) => scope.escapeBoundary);
  const end = boundaryAt < 0 ? scopes.length : boundaryAt;
  const layer = scopes.slice(0, end);
  const inner = layer.filter((scope) => innerEscape(scope, active));
  const outer = layer.filter((scope) => !inner.includes(scope));
  const root = new Map(outer.map((scope) => [scope, scopeRoot(scope)]));
  const depth = new Map(outer.map((scope) => [scope, above(root.get(scope), active)]));
  // The innermost surface the user is in, among the ones offering a step. A
  // scope rooted at the user's own focus, or at the document, names no surface: the
  // first is wherever they are and the second is everywhere.
  let surface = null;
  for (const scope of outer) {
    const at = root.get(scope);
    if (depth.get(scope) < 1 || at === document) continue;
    if (!surface || renderedUnder(at, surface)) surface = at;
  }
  const within = surface
    ? outer.filter((s) => renderedUnder(root.get(s), surface))
    : [];
  // Stable, so two scopes rooted at the same node keep the register's order.
  within.sort((a, b) => depth.get(a) - depth.get(b));
  const rest = outer.filter((scope) => !within.includes(scope));
  return [...inner, ...within, ...rest, ...scopes.slice(end)];
};

export function stack(binding = null) {
  const active = focused();
  const elementStack = scopesFor(active);
  const typing = takesLetters(active);
  const TYPING = textEntryScope();
  const nativeClaims = nativeClaimAt(active);
  const activation = nativeActivationAt(active);
  const controlScope =
    (nativeClaims || activation) && !typing
      ? {
          root: active,
          rows: [],
          claims: nativeClaims,
          activation,
        }
      : null;
  const expanded = pageScopes().flatMap((scope) => {
    if (scope === ELEMENTS) {
      if (!typing && !controlScope) return elementStack;
      const own = elementStack.filter(
        ({ el, contextual }) => el === active && !contextual,
      );
      const ancestors = elementStack.filter(
        ({ el, contextual }) => el !== active || contextual,
      );
      return [...own, ...(typing ? [TYPING] : [controlScope]), ...ancestors];
    }
    if (scope === TYPING && typing) return [];
    return scope;
  });
  const ordered = (scopes) => {
    const activeScopes = scopes.filter(currentLocation);
    return binding === "Escape" ? escapeOrder(activeScopes, active) : activeScopes;
  };
  // One tier per layer the browser holds, newest first. Everything below the newest modal
  // is inert, so those layers are the only ones a scope can still be active in.
  const layers = nativeLayers();
  const modalAt = layers.findLastIndex((layer) => layer.kind === "modal");
  const visible = modalAt < 0 ? layers : layers.slice(modalAt);
  // The newest native modal is the one boundary the browser makes inert behind it.
  const floor = modalAt < 0 ? null : visible[0].root;
  const aboveFloor = (scope) => !floor || renderedUnder(scopeRoot(scope), floor);
  const top = visible.at(-1) ?? null;
  // The topmost layer also holds the focused control and explicitly inner modes: they
  // stand above the browser's light-dismiss boundary whatever their own root is.
  const foreground = (scope) =>
    elementStack.includes(scope) ||
    scopeRoot(scope) === active ||
    innerEscape(scope, active);
  const parts = [];
  let pool = expanded;
  const take = (keep) => {
    const rest = [];
    for (const scope of pool) (keep(scope) ? parts : rest).push(scope);
    pool = rest;
  };
  for (let index = visible.length - 1; index >= 0; index -= 1) {
    const layer = visible[index];
    take(
      (scope) =>
        renderedUnder(scopeRoot(scope), layer.root) ||
        (layer === top && foreground(scope) && aboveFloor(scope)),
    );
    parts.push(layer.kind === "modal" ? MODAL_BOUNDARY : POPOVER_BOUNDARY);
  }
  if (modalAt < 0) parts.push(...pool);
  return ordered(parts);
}
// The ownership of every scope nearer the user than this one, accumulated as either
// walk steps outward. An element scope owns both its broad native claims and every exact
// binding for which it implements a Leaf invocation: a `run`, a routed command, or a
// `control` it or one of its routes names, which Leaf presses with `click()`.
// Presentation-only rows have neither a `run` nor a control: they name a native press or
// reword an outer core handler, so they do not shadow that handler. Add ownership after examining the scope itself: declarations in one scope may
// be mutually exclusive, while every implemented ordinary binding keeps the same outer
// meaning from appearing or firing when its local command is temporarily unavailable.
// Escape is the semantic unwind, so a dead declaration cannot reserve it and strand the
// next live return. Static page scopes are ordered contributors at one outer level rather
// than DOM ancestors, so their rows retain the existing live-command resolution instead
// of shadowing siblings.
//
// Native activation at the focused control is narrower. It takes its press from every
// row beyond the control that would run something else, whether its own `run`, a routed
// command, or a click on another `control`, and leaves the rows that only name the press.
// A scope rooted at the focused control speaks for that control, as its exact element
// scope does: a disclosure's toggle or a thread title's reply keeps its press. A page
// scope rooted at focus that stands over a whole surface, as the thread scope does,
// therefore keeps its Enter and Space rows dead anywhere but on its own subject. A
// contextual alias follows native activation as it follows native editing. So `takes`
// asks about the row and its scope where it has them, and an ancestor's implemented
// binding that activation took owns nothing further out: a link's Follow still names the
// press under a container's Enter.
const ownsLeafInvocation = (row) =>
  Boolean(row.run) ||
  [row, ...commandRoutes(row)].some((part) => part.control != null) ||
  commandRoutes(row).some((route) => routedCommand(route));
const runsElsewhere = (row, scope, control) => {
  if (!scope.contextual && scopeRoot(scope) === control) return false;
  const controls = [row, ...commandRoutes(row)].map((part) => word(part.control));
  if (controls.includes(control)) return false;
  return ownsLeafInvocation(row) || controls.some((each) => each != null);
};
const shadow = (quick = quickShortcuts()) => {
  const claims = [];
  let activation = null;
  return {
    takes: (binding, row, scope) =>
      claims.some((c) => c(binding)) ||
      (row !== undefined &&
        Boolean(activation?.claims(binding)) &&
        runsElsewhere(row, scope, activation.control)),
    past: (scope) => {
      if (scope.claims) claims.push(scope.claims);
      if (scope.activation)
        activation = { claims: scope.activation, control: scope.root };
      const owned = scope.el
        ? scope.rows
            .filter(ownsLeafInvocation)
            .flatMap((row) =>
              declaredBindings(row).filter((binding) =>
                bindingEnabledFor(binding, quick),
              ),
            )
            .filter((binding) => binding !== "Escape" && !activation?.claims(binding))
        : [];
      if (owned.length) claims.push((binding) => owned.includes(binding));
    },
  };
};

// A contextual route points back to one command declaration rather than copying its
// callback. Resolve that reference at invocation time so replacement, disconnection,
// scope liveness, row liveness, and dynamic routes have the same meaning as they do for
// an intrinsic key press. The source scope need not be where focus stands: that is the
// point of an ancestor projection such as an obligation.
// The press comes from where the user stands as the invocation runs.
const landing = (row, run) => () => runLanding(row, run, focused());

function referencedInvocation(reference) {
  if (!reference) return null;
  const current = referencedCommandEntry(reference);
  if (!current || !scopesAt(reference.source).includes(reference.scope)) return null;
  const run = reference.row.run
    ? () => reference.row.run(reference.binding ?? undefined)
    : current.route
      ? () => word(current.route.control ?? reference.row.control).click()
      : word(reference.row.control)?.isConnected
        ? () => word(reference.row.control).click()
        : null;
  return run
    ? {
        id: reference.id,
        row: reference.row,
        entry: current,
        binding: reference.binding ?? undefined,
        run: landing(reference.row, run),
        native: false,
      }
    : null;
}

function invocationFor(row, binding, command, recovered = null) {
  if (!command || !live(row)) return null;
  const current = commandEntries(row, [binding]).find(({ id }) => id === command.id);
  if (!current) return null;
  const reference = routedCommand(current.route);
  if (reference) return referencedInvocation(reference);
  const nativeControl = recovered ?? word(current.route?.control ?? row.control);
  const run = row.run
    ? () => row.run(current.route?.binding ?? binding)
    : nativeControl?.isConnected
      ? () => nativeControl.click()
      : null;
  return run
    ? {
        id: command?.id ?? row.id,
        row,
        entry: current,
        binding,
        run: landing(row, run),
        native: Boolean(row.native),
      }
    : null;
}

// `title` names a step the row took in place of its `run`, as a close request's `keep`.
function announceInvocation(invocation, title = null) {
  const { row, entry } = invocation;
  const route = entry.route;
  document.dispatchEvent(
    new window.CustomEvent("lf-command-invoked", {
      // Dynamic words are facts of this invocation. Reading the register later
      // would describe the state after the command changed it.
      detail: {
        id: invocation.id,
        binding: invocation.binding,
        title: title ?? titleOf(route?.title === undefined ? row : route),
        description: descriptionOf(route?.description === undefined ? row : route),
        travels: Boolean(row.travels),
      },
    }),
  );
}

function invokeCommand(command) {
  const invocation = invocationFor(command.row, command.binding, command.entry);
  if (!invocation) return false;
  announceInvocation(invocation);
  invocation.run();
  return true;
}

// Reference invocation names a command directly, so another row on the same key does not
// hide it; a nearer claim still does. Resolve Escape claims once through its semantic
// scope order, then let every row in the outer walk read the same result.
function unclaimedScopes(binding) {
  const unclaimed = new Set();
  const nearer = shadow();
  for (const scope of stack(binding)) {
    if (!nearer.takes(binding)) unclaimed.add(scopeIdentity(scope));
    nearer.past(scope);
  }
  return unclaimed;
}

// ---------- the dispatcher ----------
// One resolver decides the invocation, a command still waiting for its input, or
// an ordinary declined key. Startup capture and real dispatch share every scope,
// claim, contribution, and native-control check.
const INPUT_PENDING = Symbol("command input pending");
function resolveKey(ev) {
  const recovered = recoveredLabelFocus(ev);
  const nearer = shadow();
  for (const scope of stack(answers("Escape", ev) ? "Escape" : null)) {
    let matched = null;
    let pending = false;
    for (const row of scope.rows) {
      // Match the key before reading availability: its predicate may fold the whole
      // event log. A sibling route cannot make this contribution ready or live.
      const binding = bindings(row).find((b) => answers(b, ev));
      if (!binding || nearer.takes(binding, row, scope)) continue;
      const entries = commandEntries(row, [binding], { includeUnavailable: true });
      pending ||= entries.some(({ route }) => !commandReady(row, route));
      const entry = commandEntries(row, [binding])[0];
      const invocation = invocationFor(row, binding, entry, recovered);
      if (!invocation) continue;
      if (matched)
        throw new Error(
          `leaf: ${scope.title ?? "a scope"} has two live meanings for ${binding}: ` +
            `${titleOf(matched.row)}; ${titleOf(row)}`,
        );
      matched = invocation;
    }
    if (matched) return matched;
    if (pending) return INPUT_PENDING;
    nearer.past(scope);
  }
  return null;
}
export const keyReady = (ev) => resolveKey(ev) !== INPUT_PENDING;
// Escape with no key behind it, as the platform's close request asks for it
// (close-requests.js): whether a press would take a step now, and taking it, through
// the row's `keep` where it declares one (bindings.js).
const escapePress = () => new window.KeyboardEvent("keydown", { key: "Escape" });
export const escapeTakesAStep = () => {
  const matched = resolveKey(escapePress());
  return Boolean(matched) && matched !== INPUT_PENDING;
};
export function answerCloseRequest() {
  const matched = resolveKey(escapePress());
  if (!matched || matched === INPUT_PENDING) return;
  const keeps = Boolean(matched.row.keep);
  // The log names what ran: a row's `keep` is not its title's step.
  announceInvocation(matched, keeps ? "keep" : null);
  if (keeps) matched.row.keep();
  else matched.run();
}

// Scoping is the DOM's, but the resolver's stack, rather than listener order, says
// which command wins. The controller leaves composing input to the IME.
export function dispatchKey(ev) {
  const matched = resolveKey(ev);
  if (!matched || matched === INPUT_PENDING) return false;
  // Repeats are consumed even for a command that runs once. A native row performs
  // its own half before leaving the browser's half of the same press intact.
  if (!matched.native) ev.preventDefault();
  if (ev.repeat && !matched.row.repeat) return true;
  announceInvocation(matched);
  matched.run();
  return true;
}

// An action chosen from the reference has no keydown to match, but it still belongs to
// exactly one live scope. Resolve it through the same innermost-first stack and the same
// shadowing as a key press.
// A deliberately disabled shortcut leaves its command unbound and executable;
// nearer key claims still constrain every shortcut that remains enabled.
const reachableBindings = (
  row,
  scope,
  nearer,
  unclaimedEscape,
  commands,
  quick = quickShortcuts(),
) =>
  (commands ? declaredBindings(row) : bindings(row)).filter((binding) =>
    commands && !bindingEnabledFor(binding, quick)
      ? true
      : binding === "Escape"
        ? unclaimedEscape.has(scopeIdentity(scope))
        : !nearer.takes(binding, row, scope),
  );
function commandMatching(matches, commands = false) {
  const unclaimedEscape = unclaimedScopes("Escape");
  const nearer = shadow();
  for (const scope of stack()) {
    for (const row of scope.rows) {
      if (!live(row)) continue;
      const reachable = reachableBindings(
        row,
        scope,
        nearer,
        unclaimedEscape,
        commands,
      );
      const entry = commandEntries(row, reachable).find(
        (command) =>
          matches(command, row) && invocationFor(row, command.binding, command),
      );
      if (entry && (entry.binding != null || allBindings(row).length === 0))
        return { row, binding: entry.binding, entry };
    }
    nearer.past(scope);
  }
  return null;
}
const commandFor = (id) => commandMatching((command) => command.id === id, true);
// A contextual surface asks the dispatcher which of its routes to one capability is
// reachable from the user's current scope, and the box's placeholder names whichever one
// dispatch would answer. Asked by command id rather than by row, so the surface holds no
// reference into another scope's declaration. This includes shadowing by native text entry
// and modes, not only each row's own liveness.
export function activeCommandLabel(ids) {
  const wanted = new Set(ids);
  const command = commandMatching((entry) => wanted.has(entry.id));
  return command?.binding != null ? spell(command.binding) : "";
}
// Snapshot executable bindings by row while focus is still on the page. A widget's
// intrinsic key and an obligation alias can share a command id while only one is shadowed.
// The reference is a modal scope and shadows the page once it opens, so callers take
// this snapshot before opening it.
export function availableCommandRoutes({
  commands = false,
  quick = quickShortcuts(),
} = {}) {
  const routes = new Map();
  const unclaimedEscape = unclaimedScopes("Escape");
  const nearer = shadow(quick);
  for (const scope of stack()) {
    for (const row of scope.rows) {
      if (!live(row)) continue;
      const reachable = reachableBindings(
        row,
        scope,
        nearer,
        unclaimedEscape,
        commands,
        quick,
      );
      for (const binding of allBindings(row).length ? reachable : [undefined]) {
        for (const command of commandEntries(row, [binding])) {
          if (!invocationFor(row, binding, command)) continue;
          if (!routes.has(row)) routes.set(row, new Set());
          routes.get(row).add(binding);
        }
      }
    }
    nearer.past(scope);
  }
  return routes;
}
// A control standing in for a press (touch-controls.js) makes that press itself: the
// binding names which of a routed row's results it is, and a nearer claim on the key is
// about the key, not the command.
export function invokePress({ id, row, binding }) {
  const invocation = invocationFor(row, binding, { id });
  if (!invocation) return false;
  announceInvocation(invocation);
  invocation.run();
  return true;
}
export function executeCommand(id) {
  const command = commandFor(id);
  if (!command) return false;
  return invokeCommand(command);
}
