/* Scopes: where a group of rows applies, registered against an element and gathered by
   title for the surfaces that project them.

   Current location inside a surface is determined by focus, not merely that the surface is open. A view's
   own button lives in the floating panel, so opening by pointer leaves the user
   outside it, and a key, a Tab or a click on its contents is what puts them in. Inside a
   text box the letter is a character, Shift+Enter writes a newline in a composer, and arrows move the caret.
   The typing scope claims those text-editing keys, so a user reaches a surface's
   letters and walks from its list rather than from its composer.

   Core registers scopes through internal `keys(el, title, rows)`; a package widget
   declares the same scope as data on its element, `lfCommands`, which this module reads
   when the widget says it changed (`commandsChanged`, widget-upgrade.js). A module
   loaded on a page with no instance must contribute no scope or reference section. Runtime
   scopes live in `SCOPES`; the command reference gathers their section presentations.
   A scope may declare `ready` for incomplete inputs shared by its rows; a row or
   route may override that reading. Decision commands queue until the first saved read
   answers; their owning actions supply availability, including after a failed read.
   Normal element and page command declarations share native button activation. A
   sequence's `control` is a travel destination and arrival seat, not an activation
   declaration; native editing scopes may likewise name only the input's key route.
   An executable command owns its button's availability through its predicates;
   disabled attributes are outputs. ARIA refusal retains current keyboard location while
   activation checks the current command. Withdrawal returns both original attributes.
   Preserve the order of that list because the dispatcher and hints walk inward to
   outward while the full reference groups the same scopes for reading.

   Scopes stand wherever their element does, but this module follows only the trees
   arrivals.js observes: the document, open shadow trees, and stages (`x-shadow`,
   `shadowStage`). In a closed tree that isn't a stage, a scope still answers its keys,
   but `commandsWithin` doesn't find it, and once the tree's host leaves the page a
   button outside it that the scope names keeps showing that command's availability
   until a paint or `paintKeys()` reaches it; a press no longer runs it. Nothing in
   Leaf declares scopes in such a tree.

   A press finds a button's commands from what each source named when it was last read,
   whether or not it stood then, and counts those standing now. A source that comes to
   name another button while out of the page, with no write reported, and is put back
   and pressed in one task, is found by the frame after its arrival, not by that press:
   the gap a getter that queries the document has wherever its writer reports nothing. */
import { focusDestination, focusRevision, followingFocus } from "../focus.js";
import {
  AsyncDirective,
  PartType,
  computed,
  directive,
  effect,
  nothing,
  untracked,
} from "/runtime/framework.js";
import {
  activeRows,
  ariaShortcuts,
  bindings,
  checked,
  commandAvailable,
  commandBinding,
  commandRun,
  controlAvailabilityOutput,
  declaredCommandAvailable,
  contextualRoute,
  contextBindings,
  commandRoutes,
  declaredBindings,
  titleOf,
  descriptionOf,
  live,
  parsed,
  spokenBinding,
  validateRows,
  word,
} from "./bindings.js";
import { nativeActivationAt, nativeClaimAt } from "./text-entry.js";
import { composedParentNode, renderedParent } from "../shadow.js";
import { isElement, renderedChildElements } from "../shadow-tree.js";
import { repaint } from "../repaint.js";
import { installMoveKeys } from "../dom-move.js";
import { keeps } from "../keeps.js";
import { stageOf, watchOwner } from "../arrivals.js";
import { COMMANDS, commandsChangedOn, refuseCommands } from "../widget-upgrade.js";

/** @typedef {import("./bindings.js").Command} Command
 * @typedef {import("./bindings.js").CommandRoute} CommandRoute
 * @typedef {import("./bindings.js").Scope} Scope
 * @typedef {Scope & {el: Element, validated: boolean}} AttachedScope
 * @typedef {{source: Element, scope: Scope, rows?: readonly Command[]}} Declaration
 * @typedef {{source: Element, scope: Scope, row: Command, entry: CommandRoute}} ButtonCommand
 * @typedef {ButtonCommand & {run: () => unknown}} RunnableCommand
 * @typedef {{when?: () => boolean, ready?: () => boolean, escape?: "inner", claims?: (binding: string) => boolean}} ScopeOptions
 * @typedef {{scope: Scope}} CommandCapability
 */

// The scopes still owed a first paint. A declaration joins here and `reflectFirstScopes`
// takes it out again, so one reading is owed per declaration whether that reading stands
// or refuses it. Transient by construction: `attachScope` schedules the frame that drains
// the set in the same breath as it adds to it.
/** @type {Map<Element, AttachedScope>} */
const unpainted = new Map();
// Native button activation belongs to the same row as its keyed invocation. Resolve
// getters and attachments again at the press: a retained listener must not retain a
// replaced command or invoke a control its owner no longer declares. The weak set
// prevents duplicate listeners when one capability is attached in several places.
const wiredButtons = new WeakSet();
/** @type {WeakMap<Element, ButtonCommand>} */
const buttonReadings = new WeakMap();
/** @param {Element} control */
export const buttonCommand = (control) => buttonReadings.get(control);
/** @type {WeakMap<Element, {disabled: boolean, ariaDisabled: string | null}>} */
const buttonBaselines = new WeakMap();
const BUTTON_AVAILABILITY = Symbol("native command availability");
/** @type {Set<() => void>} */
const commandAvailabilityReaders = new Set();
/** @param {() => void} read */
export function watchCommandAvailability(read) {
  commandAvailabilityReaders.add(read);
  availabilityDirty = true;
  return () => commandAvailabilityReaders.delete(read);
}
const reflectCommandAvailability = () => {
  for (const read of commandAvailabilityReaders) read();
};
/** @type {Set<() => Iterable<Scope>>} */
const commandScopeReaders = new Set();
/** @param {() => Iterable<Scope>} read */
export function watchCommandScopes(read) {
  commandScopeReaders.add(read);
  return () => commandScopeReaders.delete(read);
}
// Which buttons a source's commands name is one computed reading per source
// (`readingOf`), read again when a signal its getters read moves. A mechanical change
// marks its source (`mark`): a declaration attached, withdrawn, projected or said
// changed, a paint in or around it, its arrival or departure, and `paintKeys()` for
// every source. Marks gather as a set, which the frame or a press takes
// (`takeChanges`): each marked source's reading is retired once, after what read it is
// disposed, so a take notifies nothing and asks for no frame, and the next ask makes it
// again. The element's reflection keeps membership both ways
// (`nameButtons`), and each button reads only its slice (`commandsAt`). Membership is a
// record of what each source last named, whether or not it stood, held weakly; a
// source counts only while it stands, which is read when it is asked, so a press reads
// established state and runs no lifecycle callback. An element that declares or
// carries a projection is tied to its lifetime (`watchOwner`) when it does: its
// departure ends what subscribed through it, and its placement, the first or a return,
// marks it. The page's own scopes stand under
// `PAGE_SOURCE`, which every paint marks, since their getters may read anywhere.
const PAGE_SOURCE = Object.freeze({ page: true });
/** @typedef {Element | typeof PAGE_SOURCE} ButtonSource */
/** @type {WeakMap<ButtonSource, {readonly value: Map<HTMLButtonElement, ButtonCommand[]>}>} */
const readings = new WeakMap();
/** @type {WeakMap<ButtonSource, Map<HTMLButtonElement, ButtonCommand[]>>} */
const named = new WeakMap();
/** @type {WeakMap<HTMLButtonElement, Set<WeakRef<ButtonSource>>>} */
const namers = new WeakMap();
/** @type {WeakMap<ButtonSource, WeakRef<ButtonSource>>} */
const sourceRefs = new WeakMap();
/** @param {ButtonSource} source */
const refOf = (source) => {
  let ref = sourceRefs.get(source);
  if (!ref) sourceRefs.set(source, (ref = new WeakRef(source)));
  return ref;
};
/** @type {WeakSet<Element>} */
const lifetimes = new WeakSet();
/** @type {Set<ButtonSource>} */
const marked = new Set();
// Contribution controls have a native activation adapter that retains the projected
// surface and gesture intent. Its registration is also the row's semantic callback, so a
// scope projected onto its own control adds no second activation.
/** @param {Element} control @param {Scope} scope */
const projectedOnto = (control, scope) =>
  [...(projectedScopes.get(control)?.values() ?? [])].some(
    (projected) => scopeIdentity(projected) === scopeIdentity(scope),
  );
// Each row with a handler, under each button it or its routes name.
/** @param {ButtonSource} source */
function buttonNames(source) {
  const [element, scopes] =
    source instanceof Element
      ? [
          source,
          [
            ...[elementScopes.get(source) ?? []].flat(),
            ...(projectedScopes.get(source)?.values() ?? []),
          ],
        ]
      : [
          document.documentElement,
          [...commandScopeReaders].flatMap((read) => [...read()]),
        ];
  /** @type {Map<HTMLButtonElement, ButtonCommand[]>} */
  const names = new Map();
  for (const scope of scopes) {
    if (scope.contextual || scope.sequence) continue;
    for (const row of scope.rows) {
      if (!row.run && !row.runKey) continue;
      const routes = commandRoutes(row);
      for (const entry of routes.length ? routes : [row]) {
        const control = word(entry.control ?? row.control);
        if (!(control instanceof HTMLButtonElement)) continue;
        names.set(control, [
          ...(names.get(control) ?? []),
          { source: element, scope, row, entry },
        ]);
      }
    }
  }
  return names;
}
/** @param {Map<HTMLButtonElement, ButtonCommand[]>} before @param {Map<HTMLButtonElement, ButtonCommand[]>} after */
const sameNames = (before, after) =>
  before.size === after.size &&
  [...after].every(([control, now]) => {
    const was = before.get(control) ?? [];
    return (
      was.length === now.length &&
      now.every(
        ({ scope, row, entry }, index) =>
          was[index]?.scope === scope &&
          was[index]?.row === row &&
          was[index]?.entry === entry,
      )
    );
  });
// Made on first ask.
/** @param {ButtonSource} source */
function readingOf(source) {
  let reading = readings.get(source);
  if (!reading) {
    // The same names as before stay the same reading, so its readers read again only
    // when one moved.
    /** @type {Map<HTMLButtonElement, ButtonCommand[]>} */
    let last = new Map();
    reading = computed(() =>
      followingFocus(() => {
        const next = buttonNames(source);
        if (!sameNames(last, next)) last = next;
        return last;
      }),
    );
    readings.set(source, reading);
  }
  return reading.value;
}
// A mechanical change to `source`: it and the buttons it names are read again. A mark
// asks for no frame, since a painter's is read at the tail of the frame it paints in;
// a change outside the frame asks for one where it is reported.
/** @param {ButtonSource} source */
function mark(source) {
  marked.add(source);
  if (source instanceof Element) dirtyElements.add(source);
  for (const control of named.get(source)?.keys() ?? []) dirtyButtons.add(control);
}
// Leaving the page or arriving in it marks the source. Registering reads the arrivals
// already made, whose owners' callbacks no reading may subscribe to.
/** @param {Element} source */
function stand(source) {
  if (lifetimes.has(source)) return;
  lifetimes.add(source);
  let registered = false;
  untracked(() =>
    watchOwner(source, {
      connect() {
        if (registered) reread(source);
      },
      disconnect: () => reread(source),
    }),
  );
  registered = true;
}
/** @param {ButtonSource} source */
function reread(source) {
  mark(source);
  repaint();
}
// Take the marks made since the last take, a full paint's and a paint's included, and
// retire each marked source's reading.
function takeChanges() {
  claimPaintedRoots();
  if (keysDirty) {
    keysDirty = false;
    pruneScopedElements();
    mark(PAGE_SOURCE);
    for (const ref of scopeRefs) {
      const scoped = ref.deref();
      if (!scoped) continue;
      mark(scoped);
      dirtyButtons.add(scoped);
    }
  }
  for (const source of marked) retire(source);
  marked.clear();
}
// What read the source's reading stops first, its element's reflection and its buttons'
// availability, which its mark owes a reading again, so dropping it notifies nothing.
/** @param {ButtonSource} source */
function retire(source) {
  if (!readings.delete(source)) return;
  if (source instanceof Element) {
    tracked.get(source)?.();
    tracked.delete(source);
  }
  for (const control of named.get(source)?.keys() ?? []) {
    buttonAvailability.get(control)?.();
    buttonAvailability.delete(control);
  }
}
// Keep membership to the source's reading, and mark the buttons it names or stops naming.
/** @param {ButtonSource} source */
function nameButtons(source) {
  const now = readingOf(source);
  const before = named.get(source);
  if (now === before) return;
  named.set(source, now);
  const ref = refOf(source);
  for (const control of before?.keys() ?? [])
    if (!now.has(control)) {
      namers.get(control)?.delete(ref);
      dirtyButtons.add(control);
    }
  for (const control of now.keys()) {
    namers.set(control, (namers.get(control) ?? new Set()).add(ref));
    dirtyButtons.add(control);
  }
}
// The commands `control` can run now: its slice of the reading of each naming source
// that stands, in the order the sources came to name it.
/** @param {HTMLButtonElement} control @returns {RunnableCommand[]} */
function commandsAt(control) {
  /** @type {RunnableCommand[]} */
  const found = [];
  const refs = namers.get(control);
  for (const ref of refs ?? []) {
    const source = ref.deref();
    if (!source) refs?.delete(ref);
    if (!source || (source instanceof Element && !source.isConnected)) continue;
    for (const candidate of readingOf(source).get(control) ?? []) {
      const { scope, row, entry } = candidate;
      if (
        projectedOnto(control, scope) ||
        found.some((prior) => prior.row === row && prior.entry.id === entry.id)
      )
        continue;
      const run = commandRun(
        row,
        commandBinding(row, entry === row ? null : entry),
        null,
      );
      if (run) found.push({ ...candidate, run });
    }
  }
  return found;
}
// The one command a button answers now: the available declaration, or the first where
// none is. Two available at once is an ambiguous button.
/** @template {ButtonCommand} T @param {[T, ...T[]]} candidates @returns {T} */
function chosenCommand(candidates) {
  const available = candidates.filter(
    ({ scope, row, entry }) =>
      (!scope.when || scope.when()) &&
      declaredCommandAvailable(row, entry === row ? null : entry),
  );
  const [first, second] = available;
  if (first && second)
    throw new TypeError(
      `leaf: ${second.entry.id} shares a button with ${first.entry.id}`,
    );
  return first ?? candidates[0];
}
// A button no declaration names any more gets its own attributes back.
/** @param {Element} control */
function releaseButton(control) {
  const baseline = buttonBaselines.get(control);
  if (!(control instanceof HTMLButtonElement) || !baseline) return;
  buttonReadings.delete(control);
  buttonAvailability.get(control)?.();
  buttonAvailability.delete(control);
  const { disabled, ariaDisabled } = baseline;
  if (control.disabled !== disabled) control.disabled = disabled;
  keeps(control, "aria-disabled", ariaDisabled);
  buttonBaselines.delete(control);
  controlAvailabilityOutput(control, BUTTON_AVAILABILITY);
  reflectElementShortcuts(control);
  forgetScopedElement(control);
}
// One button's availability, as a tracked effect over its slice of its sources'
// readings and its command's predicates: a signal either reads moving marks this
// button alone for the next frame. The effect holds the button only while it first
// reads them, and a later run that finds the button gone disposes it.
/** @type {WeakMap<Element, () => void>} */
const buttonAvailability = new WeakMap();
/** @param {HTMLButtonElement} control */
function reflectButton(control) {
  buttonAvailability.get(control)?.();
  const ref = new WeakRef(control);
  /** @type {HTMLButtonElement | null} */
  let reading = control;
  let failure = null;
  const dispose = effect(() => {
    if (reading) {
      const read = reading;
      reading = null;
      try {
        followingFocus(() => {
          // A button nothing can run is let go by the pass this marks.
          const [first, ...rest] = commandsAt(read);
          if (!first) return;
          const command = chosenCommand([first, ...rest]);
          const { scope, row, entry } = command;
          const disabled =
            (scope.when && !scope.when()) ||
            !commandAvailable(row, entry === row ? null : entry);
          keeps(read, "aria-disabled", disabled ? "true" : null);
          buttonReadings.set(read, command);
        });
      } catch (error) {
        failure = error;
      }
      return;
    }
    const moved = ref.deref();
    if (moved) {
      dirtyButtons.add(moved);
      repaint();
    } else dispose();
  });
  buttonAvailability.set(control, dispose);
  if (failure) throw failure;
}
/** @param {HTMLButtonElement} control */
function claimButton(control) {
  if (!buttonBaselines.has(control))
    buttonBaselines.set(control, {
      disabled: control.disabled,
      ariaDisabled: control.getAttribute("aria-disabled"),
    });
  controlAvailabilityOutput(control, BUTTON_AVAILABILITY, {
    disabled: true,
    ariaDisabled: true,
  });
  if (control.disabled) control.disabled = false;
  rememberScopedElement(control);
}
// Run a row's result and put the user where it says they land (`lands`, bindings.js),
// given the element the press came from.
/** @param {Command} row @param {() => unknown} run @param {Element | null} from */
export function runLanding(row, run, from) {
  run();
  const to = row.lands?.(from);
  if (to) focusDestination(to, "move");
}
/** @param {HTMLButtonElement} control */
function wireButton(control) {
  claimButton(control);
  if (wiredButtons.has(control)) return;
  wiredButtons.add(control);
  control.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || !control.isConnected) return;
    // The membership this task changed is read first: the marks, and every source owed
    // a reading, in the page or not.
    takeChanges();
    for (const source of [...dirtyElements, PAGE_SOURCE]) nameButtons(source);
    const [first, ...rest] = commandsAt(control);
    if (!first) return;
    const { scope, row, entry, run } = chosenCommand([first, ...rest]);
    const route = entry === row ? null : entry;
    event.preventDefault();
    if ((scope.when && !scope.when()) || !commandAvailable(row, route)) return;
    runLanding(row, run, control);
  });
}
// A button is pressed as soon as it can be reached, which can be before the frame that
// paints its declaration: a key run in the same task that focused a new thread card
// clicked a Resolve the paint had not yet wired, and nothing happened. So a declaration
// wires the buttons it names as elements when it is made; the press reads its command
// from the declaration's reading. A control named by a getter may not exist yet, and is
// wired at the element's reading as before.
/** @param {Scope} scope */
function wireDeclaredButtons(scope) {
  if (scope.contextual || scope.sequence) return;
  for (const row of scope.rows) {
    if ((!row.run && !row.runKey) || typeof row.routes === "function") continue;
    for (const entry of row.routes?.length ? row.routes : [row]) {
      const control = entry.control ?? row.control;
      if (control instanceof HTMLButtonElement && !projectedOnto(control, scope)) {
        wireButton(control);
        // The pass reads whether the declaration names it after all.
        dirtyButtons.add(control);
      }
    }
  }
}

// The scopes declared against an element — a WeakMap, so a scope leaves with the element
// that owns it — and, for the command reference dialog, their rows gathered under each title. A section is
/** @type {WeakMap<Element, AttachedScope>} */
const elementScopes = new WeakMap();
// The scopes other owners project onto an element, keyed by the owner, so one control can
// carry several: a margin entry holds its widget's scope and an obligation's digit route at once.
/** @type {WeakMap<Element, Map<object | symbol, Scope>>} */
const projectedScopes = new WeakMap();
const commandScopeCapabilities = new WeakSet();
/** @param {Scope} scope */
export const scopeIdentity = (scope) => scope.identity ?? scope;
/** @param {unknown} capability @returns {capability is CommandCapability} */
export const isCommandScope = (capability) =>
  capability != null &&
  (typeof capability === "object" || typeof capability === "function") &&
  commandScopeCapabilities.has(capability);
// Context aliases are their own scope so native text entry always precedes them,
// even when the original declaration is attached to the exact editor. They remain
// references to that attachment, not copied handlers or a second command inventory.
/** @type {WeakMap<Element, WeakMap<Scope, Scope>>} */
const localContexts = new WeakMap();
/** @param {Element} source @param {Scope} scope @returns {Scope} */
function localContext(source, scope) {
  let contexts = localContexts.get(source);
  if (!contexts) localContexts.set(source, (contexts = new WeakMap()));
  let contextual = contexts.get(scope);
  if (!contextual) {
    contextual = {
      identity: Object.freeze({}),
      title: scope.title,
      contextual: true,
      el: source,
      when: scope.when,
      ready: scope.ready,
      get rows() {
        return contextRows([{ source, scope }]);
      },
    };
    contexts.set(scope, contextual);
  }
  return contextual;
}
/** @param {Element} element @returns {Scope[]} */
export const scopesAt = (element) => {
  const original = [
    elementScopes.get(element),
    ...(projectedScopes.get(element)?.values() ?? []),
  ].filter((scope) => scope !== undefined);
  return original.flatMap((scope) =>
    scope.contextual ? [scope] : [scope, localContext(element, scope)],
  );
};

// Compile only the explicitly declared aliases. Availability is kept on the referenced
// owner, so a disabled action keeps its keys reserved; removing/replacing an attachment
// withdraws its old commands at invocation and at the next reading. Both a local widget
// and a question representative use this same compiler.
/** @type {WeakMap<Element, WeakMap<Scope, WeakMap<Command, Command>>>} */
const contextRowsBySource = new WeakMap();
/** @param {readonly Declaration[]} declarations @returns {Command[]} */
function contextRows(declarations) {
  return declarations.flatMap(({ source, scope, rows = scope.rows }) => {
    let scopes = contextRowsBySource.get(source);
    if (!scopes) contextRowsBySource.set(source, (scopes = new WeakMap()));
    let rowsBySource = scopes.get(scope);
    if (!rowsBySource) scopes.set(scope, (rowsBySource = new WeakMap()));
    return rows.flatMap((row) => {
      /** @returns {readonly CommandRoute[]} */
      const contributions = () =>
        commandRoutes(row).length ? commandRoutes(row) : [row];
      if (!contributions().some((contribution) => contextBindings(contribution).length))
        return [];
      let contextual = rowsBySource.get(row);
      if (!contextual) {
        contextual = {
          id: row.id,
          title: () => titleOf(row),
          description: () => descriptionOf(row),
          get keys() {
            return commandRoutes(this).flatMap(({ binding }) =>
              binding === undefined ? [] : [binding],
            );
          },
          get routes() {
            return contributions().flatMap((contribution) => {
              const aliases = contextBindings(contribution);
              const reference = Object.freeze({
                id: contribution.id,
                source,
                scope,
                row,
                binding:
                  commandBinding(row, contribution === row ? null : contribution) ??
                  null,
                get control() {
                  return word(contribution.control ?? row.control);
                },
              });
              return aliases.map((binding) =>
                contextualRoute(
                  {
                    id: contribution.id,
                    binding,
                    title: () => titleOf(contribution),
                    description: () => descriptionOf(contribution),
                    control: contribution.control ?? row.control,
                    bindingBadge:
                      contribution.bindingBadge !== undefined
                        ? contribution.bindingBadge
                        : row.bindingBadge,
                    intrinsicBindings:
                      contribution === row
                        ? declaredBindings(row)
                        : contribution.binding
                          ? [contribution.binding]
                          : [],
                  },
                  reference,
                ),
              );
            });
          },
          when: () =>
            source.isConnected &&
            scopesAt(source).includes(scope) &&
            (!scope.when || scope.when()) &&
            scope.rows.includes(row) &&
            live(row),
        };
        rowsBySource.set(row, contextual);
      }
      return [contextual];
    });
  });
}

// A contextual owner relates the current focus to an original command region.
// Resolve that relation as part of the scope reading, never as a paint effect:
// restoring focus and invoking a command in the same turn sees the same routes.
/** @type {Set<(origin: Element | null) => Scope | null>} */
const contextScopeReaders = new Set();
/** @param {string} title @param {(origin: Element | null) => {root: Element, declarations: import("./bindings.js").Cell<readonly Declaration[]>} | null} resolve */
export function contextScopes(title, resolve) {
  const identity = Object.freeze({});
  /** @param {Element | null} origin */
  const read = (origin) => {
    const projection = resolve(origin);
    if (!projection) return null;
    return {
      identity,
      title,
      contextual: true,
      el: projection.root,
      get rows() {
        return contextRows(word(projection.declarations));
      },
    };
  };
  contextScopeReaders.add(read);
  return () => contextScopeReaders.delete(read);
}

// The weak map is the dispatcher's lookup. The reference also has to enumerate every
// connected contributor, so keep weak references beside it. A live-version replacement
// can then be collected, while an element temporarily moved out of the document keeps
// its declaration when it reconnects. Holding the elements or merged closures here
// retained an entire prior version.
/** @type {Set<WeakRef<Element>>} */
export const scopeRefs = new Set();
/** @type {WeakMap<Element, WeakRef<Element>>} */
const scopeRefFor = new WeakMap();
// Each element's place in `scopeRefs`, which orders declarations wherever they are merged.
/** @type {WeakMap<Element, number>} */
const scopeOrder = new WeakMap();
let remembered = 0;
export const pruneScopedElements = () => {
  for (const ref of scopeRefs) if (!ref.deref()) scopeRefs.delete(ref);
};
/** @param {Element} el */
function rememberScopedElement(el) {
  if (scopeRefFor.has(el)) return;
  const ref = new WeakRef(el);
  scopeRefFor.set(el, ref);
  scopeRefs.add(ref);
  scopeOrder.set(el, (remembered += 1));
}
// The reference stops enumerating an element once nothing stands on it: no local
// declaration, no projected one, and no native button ownership still owed a handback.
/** @param {Element} el */
function forgetScopedElement(el) {
  if (elementScopes.has(el) || projectedScopes.has(el) || buttonBaselines.has(el))
    return;
  const ref = scopeRefFor.get(el);
  if (ref) scopeRefs.delete(ref);
  scopeRefFor.delete(el);
}
/** Declare a scope's keys where the code implementing them is.
 *
 * `where` is the element focus must be inside, `title` names the scope in the command reference dialog
 * (null for one the reference has no room to name), `rows` are its bindings, and the
 * optional configuration carries `when` (whether the page has this scope at all),
 * `ready` (whether its shared input is complete), and `escape: "inner"` when this scope owns a cancellation step ahead of every step the
 * ladder offers. A function in the fourth position is shorthand for `{when: function}`.
 * A link, button or other native control inside `where` keeps its own activation
 * press (`nativeActivationAt`).
 *
 * A scope's `when` and a row's `when` are different questions, and keeping them apart is
 * what lets one declaration feed both surfaces. The scope's is the capability — does this
 * machine have neighbours to walk, does this page have a second version — and it gates the
 * reference. The row's is whether this press would move now — is a card held, has this
 * thread a box to reply into — and it gates the press, and the reference's rows where the
 * user is in the scope and can see the answer. So the reference names Enter
 * wherever the page has threads, and Enter answers only on a focused thread with a reply
 * or reopen action.
 * One `when` answering both left Enter live over the whole page, where the press no-opped.
 *
 * A control whose keys change with its state declares every state's rows at once, each
 * gated by its own row `when`, and holds that state in a signal, or calls
 * `paintKeysWithin` where the state is the document's — a grab is Enter on an
 * already-focused grip, so no focus event would repaint its keys.
 *
 * Registering at upgrade rather than at module load is what keeps the reference honest:
 * a module stays loaded after the last element it upgraded leaves — a version activation
 * replaces the page's content, a panel body is rebuilt — so a scope declared at the top level would go
 * on as reference content for a widget the page no longer has. The dispatch scope leaves through the weak map; the
 * enumerable reference prunes its element when it disconnects. A connected control that
 * stops answering a key says so in the row's `when`, where every surface can read it.
 *
 * Declaring is not reading. `checked` reads the rows as written — ids, shapes, canonical
 * spellings — and refuses a malformed declaration here, where the caller wrote it. What
 * those rows mean right now waits for the scope's first paint: the scene is the scope's
 * `when` and each row's own, callbacks over their owner's state, and a scope declared
 * while modules are still evaluating would run them against an owner that has not
 * evaluated yet. The frame is after every module body, so the ambiguous scene and the
 * `aria-keyshortcuts` projection are both settled there; a first paint that refuses a
 * scope retracts it from both indexes. That first paint reads this element alone: a
 * declaration changes no other element's shortcuts, so attaching one asks for no
 * page-wide reflection. One a painter attaches mid-frame is read at the head of the
 * frame its repaint schedules.
 *
 * Passing a `commandScope()` capability in place of `title` attaches that one
 * declaration to retained widget DOM as well as its generated projections. Returns the
 * rows, so a widget that says its own keys out loud — a grip announcing what a grabbed
 * card answers — reads them back off the declaration rather than restating them.
 */
// Stand a declaration on `where` in place of whatever stood there, owed its first
// reading. A scope is never changed once it stands: its contextual aliases are built
// from it once (`localContext`), so a new reading is a new scope.
/** @param {Element} where @param {Scope} declaration */
function attachScope(where, declaration) {
  const scope = { ...declaration, el: where, validated: false };
  unpainted.delete(where);
  elementScopes.set(where, scope);
  unpainted.set(where, scope);
  wireDeclaredButtons(scope);
  rememberScopedElement(where);
  stand(where);
  reread(where);
  return scope;
}

// Withdraw an element's own declaration if `scope` is still the one standing there,
// and re-read the element's shortcuts from what remains: projected scopes on it stand,
// and an element the reference forgets is never read again. Returns whether anything
// was withdrawn.
/** @param {Element} element @param {Scope | null | undefined} scope */
function detachScope(element, scope) {
  if (elementScopes.get(element) !== scope) return false;
  unpainted.delete(element);
  elementScopes.delete(element);
  forgetScopedElement(element);
  mark(element);
  reflectElementShortcuts(element);
  return true;
}

// Both element-bound keys and a reusable command capability declare the same scope.
// Attachment decides when its scene is validated, not what a declaration may contain.
/** @param {string | null} title @param {readonly Command[]} rows @param {ScopeOptions | (() => boolean) | undefined} options */
function declaredScope(title, rows, options) {
  const { when, escape, ready, claims } =
    typeof options === "function" ? { when: options } : (options ?? {});
  if (escape !== undefined && escape !== "inner")
    throw new TypeError(
      `A command scope's Escape ownership must be "inner", got ${String(escape)}`,
    );
  // `claims` takes the bindings it answers true for from every scope further out
  // while the user is in this one, as a menu standing over the page does.
  return {
    title,
    rows: checked(rows, title ?? "a scope", ready),
    when,
    escape,
    ready,
    claims,
  };
}

/** @overload @param {Element} where @param {CommandCapability} title @returns {readonly Command[]} */
/** @overload @param {Element} where @param {string | null} title @param {readonly Command[]} rows @param {ScopeOptions | (() => boolean)} [options] @returns {readonly Command[]} */
/** @param {Element} where @param {[capability: CommandCapability, rows?: undefined, options?: undefined] | [title: string | null, rows: readonly Command[], options?: ScopeOptions | (() => boolean) | undefined]} declaration */
export function keys(where, ...declaration) {
  if (declaration[1] === undefined)
    return attachScope(where, declaration[0].scope).rows;
  const [title, rows, options] = declaration;
  return attachScope(where, declaredScope(title, rows, options)).rows;
}

// Template scopes use the same attachment as `keys`. Each render stands its latest
// declaration — title, rows, callbacks and availability — in place of the last, owing
// one reading of this element alone, so an unchanged render costs that one element.
// Removing the directive withdraws only its own attachment, including when Lit keeps
// the element. Temporary disconnection restores that declaration on reconnection. Rows
// that read the element at their current location, as a disclosure's toggle does, come as a function
// of it, called on each render, since the template declaring them renders that element.
export const commandsOn = directive(
  class extends AsyncDirective {
    #reconnect = () => {};
    #disconnect = () => {};
    /** @param {import("lit/directive.js").PartInfo} part */
    constructor(part) {
      super(part);
      if (part.type !== PartType.ELEMENT)
        throw new TypeError("commandsOn belongs in a template's element part");
    }
    /** @param {string | null | CommandCapability} _title
     * @param {readonly Command[] | ((element: Element) => readonly Command[])} [_rows]
     * @param {ScopeOptions | (() => boolean)} [_options] */
    render(_title, _rows, _options) {
      return nothing;
    }
    /** @param {import("lit/directive.js").ElementPart} part
     * @param {[CommandCapability, undefined?, undefined?] | [string | null, readonly Command[] | ((element: Element) => readonly Command[]), (ScopeOptions | (() => boolean))?]} values */
    update(part, values) {
      const element = part.element;
      const declaration =
        values[1] === undefined
          ? values[0].scope
          : declaredScope(
              values[0],
              typeof values[1] === "function" ? values[1](element) : values[1],
              values[2],
            );
      /** @type {AttachedScope | null} */
      let scope = null;
      this.#reconnect = () => {
        scope = attachScope(element, declaration);
      };
      this.#disconnect = () => {
        if (detachScope(element, scope)) repaint();
      };
      if (this.isConnected) this.reconnected();
      return nothing;
    }
    reconnected() {
      this.#reconnect();
    }
    disconnected() {
      this.#disconnect();
    }
  },
);

// A package widget's keys are data on the element they apply in, `lfCommands`: the
// scope's title, rows and options as `keys` takes them, or a `commandScope()` value. The
// widget says when it sets or changes them, or anything its rows read, with
// `commandsChanged` (widget-upgrade.js), so a page without Leaf, which hears nothing,
// binds no key. A declaration other than the one standing stands in its place, and none
// withdraws it; the same one standing means a row's reading moved, so the element
// reads its rows again (`mark`), and so does every reader of the register's
// availability. A malformed declaration is refused where the widget made it, as `keys`
// refuses one: the refusal goes back on the event, and `commandsChanged` throws it.
const declared = new WeakMap();
addEventListener(COMMANDS, (event) => {
  const element = commandsChangedOn(event);
  const declaration = element.lfCommands ?? null;
  const standing = declared.get(element);
  if (declaration === (standing?.declaration ?? null)) {
    if (standing) mark(element);
    availabilityDirty = true;
    repaint();
    return;
  }
  if (!declaration) {
    declared.delete(element);
    if (detachScope(element, standing.scope)) repaint();
    return;
  }
  try {
    const scope = attachScope(
      element,
      isCommandScope(declaration)
        ? declaration.scope
        : declaredScope(declaration.title, declaration.rows, declaration),
    );
    declared.set(element, { declaration, scope });
  } catch (error) {
    refuseCommands(event, error);
  }
});

/** Declare a command scope that presentation owners attach to generated controls.
 *
 * The declaration is browser state, not a hidden source element. Margin and Page Map
 * may attach the same capability to independent controls while each active reading is
 * rooted at the visible control in its own native layer.
 */
/** @param {string | null} title @param {readonly Command[]} rows @param {ScopeOptions | (() => boolean)} [options] */
export function commandScope(title, rows, options) {
  const scope = {
    ...declaredScope(title, rows, options),
    identity: Object.freeze({}),
  };
  validateRows(scope.rows, title ?? "a scope");
  const capability = Object.freeze({ scope });
  commandScopeCapabilities.add(capability);
  return capability;
}

// `projector` is whatever the projecting owner keys its projection by; projecting again
// under the same key replaces that owner's scope and leaves every other owner's scope in place,
// and a null capability withdraws it.
/** @param {Element} control @param {object | symbol} projector @param {CommandCapability | null} [capability] */
export function projectCommandScope(control, projector, capability = null) {
  dirtyButtons.add(control);
  const projections = projectedScopes.get(control) ?? new Map();
  if (capability == null) {
    projections.delete(projector);
    if (!projections.size) {
      projectedScopes.delete(control);
      forgetScopedElement(control);
    }
  } else {
    projections.set(projector, capability.scope);
    projectedScopes.set(control, projections);
    wireDeclaredButtons(capability.scope);
    rememberScopedElement(control);
    stand(control);
  }
  // Read at once, so a projector outside the frame needs none.
  mark(control);
  takeChanges();
  reflectTracked(control);
}

// Commands whose scope stands in one widget, in declaration order. Preserve the
// declaring scope beside each row: a control presentation may be hoisted elsewhere,
// while Decision ownership still belongs to the source that declared the command.
// This is the shared capability reading: the dispatcher, hints and reference use
// the same rows directly, while projections such as On me select the role they need.
// A scope may sit on a nested control rather than the widget itself, so the walk goes
// down from `root` as it renders (`eachRendered`). It costs the widget's size, not the
// page's, and returns the scopes in the order they were declared.
/** @param {Element} root @param {boolean} activeOnly */
function scopesWithin(root, activeOnly) {
  /** @type {Element[]} */
  const scopedIn = [];
  if (root.isConnected)
    eachRendered(root, (node) => {
      if (elementScopes.has(node) || projectedScopes.has(node)) scopedIn.push(node);
    });
  /** @type {Declaration[]} */
  const found = [];
  const seen = new Set();
  const declared = scopedIn.sort(
    (a, b) => (scopeOrder.get(a) ?? Infinity) - (scopeOrder.get(b) ?? Infinity),
  );
  for (const scoped of declared) {
    for (const scope of scopesAt(scoped)) {
      if (scope.contextual) continue;
      if (activeOnly && scope.when && !scope.when()) continue;
      const identity = scopeIdentity(scope);
      if (seen.has(identity)) continue;
      seen.add(identity);
      found.push({ source: scoped, scope });
    }
  }
  return found;
}
/** @param {Element} root */
export const commandDeclarationsWithin = (root) => scopesWithin(root, false);
/** @param {Element} root */
export function commandsWithin(root) {
  return scopesWithin(root, true).flatMap(({ source, scope }) =>
    scope.rows.filter(live).map((row) => ({ source, scope, row })),
  );
}
// Every declaration on one element is painted as one native shortcut attribute. A local
// declaration and any number of projected ones can coexist, so none may erase another's
// bindings. Each scope's live rows are read and refused on their own; the attribute is
// their union, since two scopes on one control may name one press: an obligation's route names
// the intrinsic key of the command it routes to, which that command's own scope names.
/** @param {Element} element */
function reflectElementShortcuts(element) {
  const available = scopesAt(element).filter((scope) => !scope.when || scope.when());
  for (const scope of available) {
    try {
      validateRows(scope.rows, scope.title ?? "a scope");
    } catch (error) {
      // A local declaration is published before its first read. If that first reading
      // fails, retract only that declaration; a projected capability on the same element
      // remains independently valid and enumerable.
      if (scope.el === element && !scope.validated) detachScope(element, scope);
      throw error;
    }
    if (scope.el === element) scope.validated = true;
  }
  const nativeClaims = nativeClaimAt(element);
  const activation = nativeActivationAt(element);
  const ownsControl = available.some((scope) =>
    scope.rows.some(
      (row) =>
        word(row.control) === element ||
        commandRoutes(row).some(
          (route) => word(route.control ?? row.control) === element,
        ),
    ),
  );
  const shortcuts = [
    ...new Set(
      available.flatMap((scope) =>
        ariaShortcuts(
          scope.rows,
          true,
          scope.title ?? "a scope",
          (binding, entry, row) => {
            if (scope.contextual && (nativeClaims?.(binding) || activation?.(binding)))
              return false;
            const control = word(entry.route?.control ?? row.control);
            return !ownsControl || control == null || control === element;
          },
        )
          .split(" ")
          .filter(Boolean),
      ),
    ),
  ].join(" ");
  keeps(element, "aria-keyshortcuts", shortcuts || null);
}
// Ahead of the page's content, so an ambiguous declaration is refused under its own title
// rather than under whichever surface reads its rows first.
export function reflectFirstScopes() {
  try {
    takeChanges();
    for (const [element, scope] of unpainted) {
      unpainted.delete(element);
      reflectTracked(scope.el);
    }
  } finally {
    reflectButtonsTracked();
  }
}
// Reflect after the page's content has projected all of its scopes in the current
// repaint frame. A focus move and a replacement can each ask for a paint, but the
// shortcut attribute should represent only the final current location in that frame.
// A scope refused here is reported, and the elements after it still paint.
//
// An element's reflection reads its rows' liveness, and that reads two kinds of input.
// What it reads from the semantic root or from a signal is tracked: each reflection runs
// as a signals effect, and a publication or signal that moves something it read marks
// that element alone for the next frame. Where the user is counts as such a signal for
// a reflection whose rows asked `focused` (focus.js, `followingFocus`), so a move reads
// again only those, not every element on the page. So a module's own state that a row
// reads is a signal, a focus listener's included: a plain variable is read once, and a
// change to it reaches the element only when something else marks it. What it reads
// from the document is a mechanical change, and its writer says so: `paintKeys()` marks
// every element, and `paintKeysWithin(root)` the ones a renderer's paint touched. A
// publication that moves nothing an element read, and no renderer whose output it reads,
// leaves its reflection as it is.
let keysDirty = true;
/** @type {Set<Element>} */
const dirtyElements = new Set();
/** @type {WeakMap<Element, () => void>} */
const tracked = new WeakMap();
// Native buttons read the same predicates for their availability. A command may name a
// control outside the element declaring it, so which buttons it names comes from the
// element's reading (`readingOf`), not from the buttons. Each button's availability is
// its own tracked effect (`reflectButton`), read again when its slice of a reading or a
// signal its predicates read moves, or a key paint reaches it; where the user is is
// such a signal for a button whose rows asked (`followingFocus`). Every button is read
// again on `paintKeys()`. Contribution projections read the same predicates, as one
// tracked reader beside them.
/** @type {Set<Element>} */
const dirtyButtons = new Set();
/** @type {(() => void) | null} */
let availabilityTracking = null;
let availabilityDirty = true;
function reflectAvailabilityReaders() {
  availabilityDirty = false;
  availabilityTracking?.();
  let first = true;
  let failure = null;
  availabilityTracking = effect(() => {
    if (first) {
      first = false;
      try {
        focusRevision();
        reflectCommandAvailability();
      } catch (error) {
        failure = error;
      }
      return;
    }
    availabilityDirty = true;
    repaint();
  });
  if (failure) throw failure;
}
function reflectButtonsTracked() {
  takeChanges();
  if (!dirtyButtons.size && !availabilityDirty) return;
  // Getter-named buttons may arrive after declaration. Claim their output fields before
  // availability readers project commands; otherwise their initial disabled paint is
  // mistaken for an input until the next frame. Readers may materialize more controls,
  // which the page's naming below then claims and presents.
  nameButtons(PAGE_SOURCE);
  for (const control of dirtyButtons)
    if (control instanceof HTMLButtonElement && commandsAt(control).length)
      claimButton(control);
  // Contribution projections read command predicates, some over a widget's nodes, so
  // any pass reads them again: a scoped paint is as likely to have moved one as a
  // signal the reader tracks.
  // A reader or button that fails is reported, and every other one still paints.
  const failures = [];
  try {
    reflectAvailabilityReaders();
  } catch (error) {
    failures.push(error);
  }
  // Taken after the readers, whose projections mark the controls they move.
  const dirty = [...dirtyButtons];
  dirtyButtons.clear();
  for (const control of dirty) {
    if (!(control instanceof HTMLButtonElement) || !commandsAt(control).length) {
      releaseButton(control);
      continue;
    }
    wireButton(control);
    try {
      reflectButton(control);
    } catch (error) {
      failures.push(error);
    }
  }
  for (const failure of failures) reportError(failure);
}
/** @param {Element} element */
function reflectTracked(element) {
  // This reading answers whatever owed the element one.
  dirtyElements.delete(element);
  tracked.get(element)?.();
  tracked.delete(element);
  if (!element.isConnected) {
    // One out of the page keeps the record of what it names, and nothing subscribes
    // through it, so it can be collected.
    untracked(() => {
      nameButtons(element);
      reflectElementShortcuts(element);
    });
    readings.delete(element);
    return;
  }
  const ref = new WeakRef(element);
  /** @type {Element | null} */
  let initial = element;
  let failure = null;
  const dispose = effect(() => {
    if (initial) {
      const current = initial;
      initial = null;
      try {
        followingFocus(() => {
          nameButtons(current);
          reflectElementShortcuts(current);
        });
      } catch (error) {
        failure = error;
      }
      return;
    }
    const moved = ref.deref();
    if (moved) {
      dirtyElements.add(moved);
      repaint();
    } else dispose();
  });
  tracked.set(element, dispose);
  if (failure) throw failure;
}
export function reflectKeys() {
  takeChanges();
  if (!dirtyElements.size) return;
  const elements = [...dirtyElements];
  dirtyElements.clear();
  for (const scoped of elements) {
    try {
      reflectTracked(scoped);
    } catch (error) {
      reportError(error);
    }
  }
  reflectButtonsTracked();
}
export const paintKeys = () => {
  keysDirty = true;
  availabilityDirty = true;
  repaint();
};
/** Mark for reflection the scoped elements inside `root`, as a renderer that has just
 * rewritten that part of the document does, and repaint the frame whose shared surfaces,
 * the hints among them, read the same rows. */
/** @param {Node} root */
export const paintKeysWithin = (root) => {
  paintedRoots.add(root);
  repaint();
};
// The roots renderers painted since the frame last reflected, resolved to the scoped
// elements inside them by a walk of each outermost root, so a frame costs what was
// painted however many renderers painted, where a scan per paint cost every widget's
// update the whole page's scoped elements. A placed node about to move out of a painted
// root takes the marks of the scoped elements it holds with it (dom-move.js), so the
// frame finds them wherever they land.
/** @type {Set<Node>} */
const paintedRoots = new Set();
installMoveKeys((node) => {
  if (!paintedRoots.size) return;
  for (let at = /** @type {Node | null} */ (node); at; at = composedParentNode(at))
    if (paintedRoots.has(at)) return markScopedIn(node);
});
/** @param {Node} node */
const markScopedIn = (node) =>
  eachRendered(node, (element) => {
    if (!scopeRefFor.has(element)) return;
    mark(element);
    dirtyButtons.add(element);
  });
// Each element at or under `node` as it renders: down the step `renderedParent` takes
// up (`renderedChildElements`), and into a closed stage by its host (`stageOf`). A
// widget's scopes and a paint's marks are found by the same steps.
/** @param {Node} node @param {(element: Element) => void} visit */
function eachRendered(node, visit) {
  if (!isElement(node)) {
    // A painted shadow root, or a text node a move carries.
    const { children = [] } = /** @type {Partial<ParentNode>} */ (node);
    for (const child of children) eachRendered(child, visit);
    return;
  }
  visit(node);
  for (const child of renderedChildElements(node)) eachRendered(child, visit);
  if (!node.shadowRoot)
    for (const child of stageOf(node)?.children ?? []) eachRendered(child, visit);
}
function claimPaintedRoots() {
  if (!paintedRoots.size) return;
  // Whether a node is a painted root or stands in one, remembered for every node a climb
  // passes, so roots that share ancestors climb each of them once.
  /** @type {Map<Node, boolean>} */
  const covered = new Map();
  /** @param {Node | null} node */
  const coveredFrom = (node) => {
    /** @type {Node[]} */
    const passed = [];
    let answer = false;
    for (let at = node; at; at = composedParentNode(at)) {
      const known = covered.get(at);
      if (known !== undefined) {
        answer = known;
        break;
      }
      passed.push(at);
      if (paintedRoots.has(at)) {
        answer = true;
        break;
      }
    }
    for (const at of passed) covered.set(at, answer);
    return answer;
  };
  /** @type {Set<Element>} */
  const around = new Set();
  for (const root of paintedRoots) {
    if (coveredFrom(composedParentNode(root))) continue;
    markScopedIn(root);
    // A paint changes what the elements around it hold, so a declaration querying its
    // own subtree for a control reads again; a shared ancestor is climbed once.
    for (
      let at = renderedParent(root);
      at && !around.has(at);
      at = renderedParent(at)
    ) {
      around.add(at);
      if (scopeRefFor.has(at)) mark(at);
    }
  }
  paintedRoots.clear();
  mark(PAGE_SOURCE);
}
/** What a scope answers right now, as a listener hears it read out — key names rather than
 * the chips the eye reads, since a screen reader renders "esc" literally. Off the register,
 * so an announcement cannot name a key the rows stopped binding.
 */
/** @param {readonly Command[]} rows */
export const saying = (rows) =>
  activeRows(rows, "an announced scope")
    .map((row) => `${spoken(row)} ${titleOf(row)}`)
    .join(", ");
// A row's own label where it has one, read the way every other surface reads a cell, and
// the bindings where it has none — which is what keeps a listener hearing "Escape" rather
// than the keycap's "esc". Asking whether the label was written as a string made the same fact
// announce two ways by accident: an option group's digits are spelled "1–3" because its label
// happens to be a string, while the sequence's were read out as "1 or 2 or 3" because its label
// counts what the page holds and so has to be a function.
/** @param {Command} row */
const spoken = (row) => {
  const active = bindings(row);
  if (active.some((binding) => parsed(binding).mods.length))
    return active.map(spokenBinding).join(" or ");
  return word(row.label) ?? active.map(spokenBinding).join(" or ");
};

// The element scopes covering a node, innermost first — the climb crosses a shadow
// boundary the way `closest` climbs inside one, so a widget staging its controls in a
// shadow tree declares them the same way. Generated margin controls own their visible
// position directly; they no longer borrow scopes from hidden source controls.
/** @param {Element | null} node */
export function scopesFor(node) {
  const contexts = [...contextScopeReaders]
    .map((read) => read(node))
    .filter((scope) => scope !== null);
  /** @type {Scope[]} */
  const found = [];
  const seen = new Set();
  /** @param {Element | null} start */
  const collect = (start) => {
    for (let a = start; a; a = renderedParent(a)) {
      for (const scope of [...scopesAt(a), ...contexts.filter(({ el }) => el === a)]) {
        const identity = scopeIdentity(scope);
        if (seen.has(identity)) continue;
        found.push(scope.el ? scope : { ...scope, el: a });
        seen.add(identity);
      }
      if (a.hasAttribute?.("data-lf-thread-surface")) break;
    }
  };
  collect(node);
  return found;
}
// Whether the focused control has claimed Escape for itself. Asked of the control's own
// scopes and not of the stack, because both callers mean "this press already has an owner
// where the user is ": the sequence refuses to arm there, and focus entering one
// disarms it. Every panel and mode in the runtime carries a rung of some kind, so a
// question asked of the whole stack would answer yes almost everywhere and the sequence would
// never arm at all.
/** @param {Element | null} node */
export const claimsEsc = (node) =>
  scopesFor(node).some((scope) =>
    scope.rows.some((row) => live(row) && bindings(row).includes("Escape")),
  );
