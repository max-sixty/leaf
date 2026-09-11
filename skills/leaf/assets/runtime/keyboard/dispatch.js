/* The dispatcher: which scope answers a press, what it owes the platform, and the one
   unwind step Escape takes.

   Scopes nest by focus. `scopesFor` produces the active stack and element scopes are
   spliced where their elements stand. The dispatcher walks innermost first. A scope owns
   every binding it declares while the reader stands in that scope, whether or not the
   command is currently live. A live command runs and prevents the platform default; an
   unavailable command suppresses outer Leaf meanings but leaves any browser default
   intact. A `native` row runs and stops the scope walk but leaves that default intact.
   Undeclared keys continue outward through ancestor scopes to the page.

   Leaf must not block standard platform or browser shortcuts. A handler prevents a
   default only after a Leaf command owns the complete modified press; secondary clicks
   and the native context menu remain the browser's too.

   `claims` lists platform keys a scope consumes even when no registered row answers them.
   A text entry scope uses `takesLetters` and claims character keys plus the keys that
   edit that specific control: Enter, deletion, caret movement, Home/End, and page
   movement. The claim follows the base key through modifiers, so Shift+Arrow selection,
   Alt character composition, and Mod editing commands remain native. It does not blanket
   radio, checkbox, slider, Escape, or unrelated function keys merely because they are
   form-related. An exact element scope is nearer than that claim, so a wired textarea
   keeps its own Escape or submit binding; the typing claim then stands before any scope on an
   ancestor widget. This ordering lets a widget contain an editor without taking letters,
   newlines, or caret keys from it.

   One box inside another scope states only what it does differently. The find box
   registers its Escape and Enter on the exact input element, so those rows stand before
   the command return frame; that frame stands before `TYPING`, and the general text-entry
   claim stands before any ancestor widget. Escape therefore lets a live query go, then
   leaves the box through the `/` frame, then leaves the panel through its entry frame. A
   plain composer with no control-specific Escape goes directly through the command frame
   instead of paying a generic “leave the textarea” step the entry never made.

   A key may repeat across nesting scopes to mean the same intent in context. `c` reads
   that way: from the page it enters the nearest comment box; from the Threads list it
   enters the page-comment box one frame below that list. `g T`, not `c`, is what enters
   Threads as a navigable surface and leaves `w` and `/` live. `activeRowLabel` projects
   the dispatcher's live result into the destination composition box's placeholder. Each
   box's `aria-label` remains its shortcut-free accessible name.

   Escape is an ordinary binding in each row and a semantic ordering in the dispatcher.
   An active mode and the focused control's specific inner step stand first, the latest
   eligible command return frame next, then scene-derived and containing-scope fallbacks.
   Declaration order cannot move a fallback ahead of that frame. The innermost live row
   owns exactly one unwind step. A query clear, box return, panel dismissal, decision
   release, and return to the page cannot cascade from one keypress. A scope does not need
   a private `keydown` listener or hand-written `preventDefault` to protect that contract.

   Auto popovers and modal dialogs are the platform's modes. Each scope and return frame
   belongs to its document or native-layer root. A modal keeps only scopes rooted in that
   layer before the platform boundary and drops the inert document's scopes. A popover is
   nonmodal: active command modes and focused scopes retain their order, later scopes owned
   by the popover move ahead of the boundary, and the boundary reserves an otherwise
   unhandled Escape while letting other page commands through. When that popover stands
   inside a modal, the enclosing modal remains the floor and document scopes stay inert.
   An inner Leaf row can therefore unwind a step in that layer, while an unhandled Escape
   reaches the browser and cannot fall through. Covered return frames are suspended;
   closing the layer exposes the same frame again. The universal reference is the
   boundary's one route through to another layer.

   A covering auxiliary surface uses the same modal command floor without entering the browser's
   top layer. Its owner makes the background DOM inert, and this dispatcher keeps only
   scopes rooted in the auxiliary surface plus the return frame that can close it. A native layer
   opened above the auxiliary surface keeps its own scopes above that floor.

   A popover hands focus back to whatever had it when the popover showed — not to its
   invoker, and not to `showPopover({source})`, which buys the anchor and the invoker
   relationship and nothing about focus. So a key that opens a layer runs the press from
   the control itself rather than opening it from the page, and every door leaves the same
   way out. Where Leaf has to hand focus back itself, scope that to the door that needs it
   rather than to focus landing on the body: a light dismissal restores nothing on
   purpose, and a reader who pressed away into the page is not asking to be moved to the
   control they pressed away from.

   When Leaf handles a binding that promises a visible control's activation, its command
   path calls that control's `click()`; it does not call the handler or reproduce its
   result. A platform-native press stays native. Arrival may focus or reveal the control
   before activation. Modality checks belong only to gesture guards before activation,
   such as refusing the mouseup that ends a text-selection drag. */
import {
  answers,
  bindings,
  commandEntries,
  commandRoutes,
  live,
  routedCommand,
  spell,
  word,
} from "./bindings.js";
import {
  coveringAuxiliarySurface,
  ELEMENTS,
  pageScopes,
  textEntryScope,
  universalCommandReference,
} from "./register.js";
import { EVERYTHING } from "./text-entry.js";
import { takesLetters } from "../focus.js";
import { elementScopes, focused, recoveredLabelFocus, scopesFor } from "./scopes.js";
import { RETURN, invoke } from "./return-stack.js";
import {
  currentModalLayer,
  currentNativeLayer,
  nativeLayerFor,
  nativeLayersFor,
} from "../native-layers.js";

// The two questions a scope answers, named apart because the surfaces ask them apart: the
// reference lists a scope the page *has* and filters its rows by liveness only where the reader
// is standing in it, while the dispatcher and the line want both at once. Spelled `!x || x()`
// in three places before, which is a rule written three times and named nowhere.
const pageHas = (scope) => !scope.when || scope.when();
export const readerIn = (scope) => !scope.at || scope.at();
// Where the reader is first, and what the page has second: both are pure and the and is
// the same either way round, but `at` is a class check and a `when` may be the whole event
// log folded — so the walk asks the cheap question of every scope and the dear one only of
// the scopes it is already standing in. That is the rule the dispatcher's row loop already
// keeps and the control scope's own comment already claims ("`at` is asked first and answers
// false wherever this could be in doubt, so a paint never reaches it"), and the scope walk
// was the one place it was not true. The sequence is what made it bite: its `when` reaches the
// decisions fold and then every link on the page, once per keydown, from the first keystroke of
// the first comment.
const standing = (scope) => readerIn(scope) && pageHas(scope);
const nativeBoundary = (claims) => ({
  get rows() {
    return [universalCommandReference()];
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
const innerEscape = (scope, active) => {
  if (scope.escape !== undefined && scope.escape !== "inner")
    throw new TypeError(
      `leaf: ${scope.title ?? "a scope"} has invalid Escape ownership ${String(scope.escape)}`,
    );
  return scope.escape === "inner" || scope.el === active;
};
// Every scope the reader is standing in, innermost first. The whole list: what a nearer
// scope takes out of reach is the walk's own business, and both walkers say it the same
// way — a binding some nearer row has already named, or one a nearer scope claims. Cutting
// the list here instead was the same statement made where only one of the two shadowings
// could be seen.
const escapeOrder = (scopes, active) => {
  const boundaryAt = scopes.findIndex((scope) => scope.escapeBoundary);
  const end = boundaryAt < 0 ? scopes.length : boundaryAt;
  const layer = scopes.slice(0, end).filter((scope) => scope !== RETURN);
  const inner = layer.filter((scope) => innerEscape(scope, active));
  const fallback = layer.filter((scope) => !inner.includes(scope));
  const causal = scopes.slice(0, end).includes(RETURN) ? [RETURN] : [];
  return [...inner, ...causal, ...fallback, ...scopes.slice(end)];
};

export function stack(binding = null) {
  const active = focused();
  const elementStack = scopesFor(active);
  const typing = takesLetters(active);
  const TYPING = textEntryScope();
  const expanded = pageScopes().flatMap((scope) => {
    if (scope === ELEMENTS) {
      if (!typing) return [...elementStack, RETURN];
      const own = elementStack.filter(({ el }) => el === active);
      const ancestors = elementStack.filter(({ el }) => el !== active);
      // A control's own state is the innermost layer. The command frame that entered
      // it comes next, before the generic text-box escape and any containing widget:
      // `/` in Threads can clear its query before returning, while `c` into a plain
      // composer returns in the same one Escape that entered it.
      return [...own, RETURN, TYPING, ...ancestors];
    }
    // RETURN is declared in pageScopes() so every projection sees it. The element placeholder
    // above has already placed it at the dynamic boundary between the exact control and
    // the generic/ancestor scopes, so the static slot contributes no second copy.
    if (scope === RETURN) return [];
    if (scope === TYPING && typing) return [];
    return scope;
  });
  const auxiliarySurface = coveringAuxiliarySurface();
  const layer = currentNativeLayer(active);
  const ordered = (scopes) => {
    const activeScopes = scopes.filter(standing);
    return binding === "Escape" ? escapeOrder(activeScopes, active) : activeScopes;
  };
  if (!layer) {
    if (!auxiliarySurface) return ordered(expanded);
    const owned = expanded.filter((scope) => {
      const root = scopeRoot(scope);
      return (
        scope === RETURN || root === auxiliarySurface || auxiliarySurface.contains(root)
      );
    });
    return ordered([...owned, MODAL_BOUNDARY]);
  }
  const modal = currentModalLayer(active);
  const inLayer = (scope) => nativeLayerFor(scopeRoot(scope)) === layer;
  if (layer !== modal) {
    // The popover, its focused controls, and explicitly inner modes stand above the
    // browser's light-dismiss boundary. Everything else remains reachable for keys the
    // boundary does not claim, but its Escape cannot fall through into the covered page.
    const aboveBoundary = modal
      ? (scope) => nativeLayersFor(scopeRoot(scope)).includes(modal)
      : auxiliarySurface
        ? (scope) => {
            const root = scopeRoot(scope);
            return (
              scope === RETURN ||
              inLayer(scope) ||
              root === auxiliarySurface ||
              auxiliarySurface.contains(root)
            );
          }
        : () => true;
    const available = expanded.filter(aboveBoundary);
    const foreground = (scope) =>
      inLayer(scope) ||
      elementStack.includes(scope) ||
      scopeRoot(scope) === active ||
      innerEscape(scope, active);
    const popoverStack = [
      ...available.filter(foreground),
      POPOVER_BOUNDARY,
      ...available.filter((scope) => !foreground(scope)),
    ];
    if (modal || auxiliarySurface) popoverStack.push(MODAL_BOUNDARY);
    return ordered(popoverStack);
  }
  const owned = expanded.filter((scope) =>
    nativeLayersFor(scopeRoot(scope)).includes(modal),
  );
  return ordered([...owned, MODAL_BOUNDARY]);
}
// The ownership of every scope nearer the reader than this one, accumulated as either
// walk steps outward. An element scope owns both its broad native claims and every exact
// binding for which it implements a Leaf invocation. Presentation-only rows have no `run`:
// they name a native press or reword an outer core handler, so they do not shadow that
// handler. Add ownership after examining the scope itself: declarations in one scope may
// be mutually exclusive, while every implemented one keeps the same outer meaning from
// appearing or firing when its local command is temporarily unavailable. Static page
// scopes are ordered contributors at one outer level rather than DOM ancestors, so their
// rows retain the existing live-command resolution instead of shadowing siblings.
const ownsLeafInvocation = (row) =>
  Boolean(row.run) || commandRoutes(row).some((route) => routedCommand(route));
export const shadow = () => {
  const claims = [];
  return {
    takes: (binding) => claims.some((c) => c(binding)),
    past: (scope) => {
      if (scope.claims) claims.push(scope.claims);
      const owned = scope.el
        ? scope.rows.filter(ownsLeafInvocation).flatMap(bindings)
        : [];
      if (owned.length) claims.push((binding) => owned.includes(binding));
    },
  };
};

// A contextual route points back to one command declaration rather than copying its
// callback. Resolve that reference at invocation time so replacement, disconnection,
// scope liveness, row liveness, and dynamic routes have the same meaning as they do for
// an intrinsic key press. The source scope need not be where focus stands: that is the
// point of an ancestor projection such as Ask.
function referencedInvocation(reference) {
  if (!reference?.source?.isConnected) return null;
  if (elementScopes.get(reference.source) !== reference.scope) return null;
  if (!pageHas(reference.scope) || !reference.scope.rows.includes(reference.row))
    return null;
  if (!live(reference.row)) return null;
  const current = commandEntries(reference.row, bindings(reference.row)).find(
    ({ id, binding }) => id === reference.id && (binding ?? null) === reference.binding,
  );
  if (!current) return null;
  const run = reference.row.run
    ? () => reference.row.run(reference.binding ?? undefined)
    : reference.control?.isConnected
      ? () => reference.control.click()
      : null;
  return run
    ? {
        row: reference.row,
        binding: reference.binding ?? undefined,
        run,
        native: false,
      }
    : null;
}

function invocationFor(row, binding, command, recovered = null) {
  const reference = routedCommand(command?.route);
  if (reference) return referencedInvocation(reference);
  const run = row.run
    ? () => row.run(binding)
    : recovered
      ? () => recovered.click()
      : null;
  return run ? { row, binding, run, native: Boolean(row.native) } : null;
}

function invokeCommand(command, origin, beforeCommand) {
  const invocation = invocationFor(command.row, command.binding, command.entry);
  if (!invocation) return false;
  beforeCommand?.(invocation.row);
  invoke(invocation.row, invocation.binding, invocation.run, origin);
  return true;
}

// The visible owner of one binding after its own ordering and claims. The shortcut line
// asks this once for Escape; its other bindings retain the cheaper single declaration-order
// walk. Keeping this resolution here makes the shown unwind step the one dispatch will run.
export function lineOwner(binding) {
  const nearer = shadow();
  for (const scope of stack(binding)) {
    const owners = scope.rows.filter(
      (row) =>
        row.line &&
        bindings(row).includes(binding) &&
        !nearer.takes(binding) &&
        live(row),
    );
    if (owners.length > 1)
      throw new Error(
        `leaf: ${scope.title ?? "a scope"} has two live meanings for ${binding}: ` +
          owners.map((owner) => word(owner.does)).join("; "),
      );
    if (owners.length)
      return {
        scope,
        row: owners[0],
        visible: !scope.sequence && word(owners[0].lineWhen) === false ? false : true,
      };
    nearer.past(scope);
  }
  return null;
}

// Reference invocation names a command directly, so another row on the same key does not
// hide it; a nearer claim still does. Resolve Escape claims once through its semantic
// scope order, then let every row in the outer walk read the same result.
function unclaimedScopes(binding) {
  const unclaimed = new Set();
  const nearer = shadow();
  for (const scope of stack(binding)) {
    if (!nearer.takes(binding)) unclaimed.add(scope);
    nearer.past(scope);
  }
  return unclaimed;
}

// ---------- the dispatcher ----------
// One listener. Scoping is still the DOM's — an element scope holds while focus is inside
// it — but the walk is the stack's rather than the bubble's, so which scope wins is a
// statement here instead of an ordering between nine listeners. `isComposing` is the one
// guard that stays an event's rather than a scope's: an IME's own Escape is not the
// runtime's to take.
export function dispatchKey(ev, { beforeCommand, captureOrigin }) {
  const recovered = recoveredLabelFocus(ev);
  const nearer = shadow();
  for (const scope of stack(answers("Escape", ev) ? "Escape" : null)) {
    let matched = null;
    for (const row of scope.rows) {
      // The key first, then the claim, then the liveness: a `when` may be the whole event
      // log folded (`a` asks what the page is still waiting on), and asking it of every row
      // the press is not for makes the cost of a keystroke the size of the table rather
      // than the size of the match. A dead matching row contributes no invocation here;
      // `nearer.past(scope)` still records its declaration before the walk reaches an
      // outer scope.
      const binding = bindings(row).find((b) => answers(b, ev));
      if (!binding || nearer.takes(binding) || !live(row)) continue;
      const entry = commandEntries(row, [binding])[0];
      const invocation = invocationFor(row, binding, entry, recovered);
      if (!invocation) continue;
      if (matched)
        throw new Error(
          `leaf: ${scope.title ?? "a scope"} has two live meanings for ${binding}: ` +
            `${word(matched.row.does)}; ${word(row.does)}`,
        );
      matched = invocation;
    }
    if (matched) {
      // A held key repeats keydown where a real button fires once, so a row says whether
      // it repeats: a held `]` was a page navigation per repeat and a held pick a `choose`
      // per repeat, where a walk wants the repeat and is the reason the flag exists. The
      // repeat is still consumed — a non-repeatable command must not be fired again merely
      // because its key remains held after the first press.
      //
      // A `native` row is the narrow converse: Leaf has a result to perform before the
      // platform completes the same press. The versions menu closes at its Tab boundary,
      // for example, and the browser then carries focus forward from its stable door. It
      // remains a registered press — and therefore visible, scoped and shadowed like every
      // other one — but does not claim the platform's half of it.
      if (!matched.native) ev.preventDefault();
      if (ev.repeat && !matched.row.repeat) return true;
      beforeCommand?.(matched.row);
      const origin = matched.row.returnFrame ? captureOrigin() : null;
      invoke(matched.row, matched.binding, matched.run, origin);
      return true;
    }
    nearer.past(scope);
  }
  return false;
}

// An action chosen from the reference has no keydown to match, but it still belongs to
// exactly one live scope. Resolve it through the same innermost-first stack and the same
// shadowing as a key press.
function commandMatching(matches) {
  const unclaimedEscape = unclaimedScopes("Escape");
  const nearer = shadow();
  for (const scope of stack()) {
    for (const row of scope.rows) {
      if (!live(row)) continue;
      const reachable = bindings(row).filter((binding) =>
        binding === "Escape" ? unclaimedEscape.has(scope) : !nearer.takes(binding),
      );
      const entry = commandEntries(row, reachable).find(
        (command) =>
          matches(command, row) && invocationFor(row, command.binding, command),
      );
      if (entry?.binding != null) return { row, binding: entry.binding, entry };
    }
    nearer.past(scope);
  }
  return null;
}
const commandFor = (id) => commandMatching((command) => command.id === id);
// A contextual surface asks the dispatcher which one of its command rows is reachable
// from the reader's current scope. This includes shadowing by native text entry and modes,
// not only each row's own liveness.
export function activeRowLabel(rows) {
  const candidates = new Set(rows);
  const command = commandMatching((_entry, row) => candidates.has(row));
  return command ? spell(command.binding) : "";
}
// Snapshot every executable route while focus is still on the page. Keep both readings:
// command ids answer whether a semantic result can be invoked, while row bindings answer
// whether this exact advertised route works. The distinction matters when a widget's
// intrinsic key and an Ask alias share one command id but only one binding is shadowed.
function availableRouteSnapshot() {
  const commands = new Set();
  const routes = new Map();
  const unclaimedEscape = unclaimedScopes("Escape");
  const nearer = shadow();
  for (const scope of stack()) {
    for (const row of scope.rows) {
      if (!live(row)) continue;
      const reachable = bindings(row).filter((binding) =>
        binding === "Escape" ? unclaimedEscape.has(scope) : !nearer.takes(binding),
      );
      for (const command of commandEntries(row, reachable)) {
        if (command.binding == null || !invocationFor(row, command.binding, command))
          continue;
        commands.add(command.id);
        if (!routes.has(row)) routes.set(row, new Set());
        routes.get(row).add(command.binding);
      }
    }
    nearer.past(scope);
  }
  return { commands, routes };
}
// The reference is a modal scope and correctly shadows the page once it opens; callers
// take this snapshot before that point.
export const availableCommands = () => availableRouteSnapshot().commands;
export const availableCommandRoutes = () => availableRouteSnapshot().routes;
// Exact route reachability for projections that deliberately reuse an intrinsic command
// identity. An Ask digit and the widget key it aliases have one id but different bindings;
// only the binding can say which route a nearer scope shadows.
export function reachableBindings(target) {
  return availableRouteSnapshot().routes.get(target) ?? new Set();
}
export function executeCommand(id, origin, beforeCommand) {
  const command = commandFor(id);
  if (!command) return false;
  return invokeCommand(command, origin, beforeCommand);
}
