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
   when the element says it changed (`lf-commands`, lib/widget-events.js). A module
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
   dom/arrivals.js observes: the document, open shadow trees, and stages (`shadow`,
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
import {
  focusDestination,
  focusRevision,
  followingFocus,
  onCurrentLocation,
} from "../focus.js";
import { AsyncDirective, PartType, directive, nothing } from "/vendor/lit.js";
import { computed, effect, untracked } from "/vendor/signals-core.js";
import {
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
  validateRows,
  word,
} from "./bindings.js";
import { nativeActivationAt, nativeClaimAt } from "./text-entry.js";
import {
  eachRenderedElement,
  isElement,
  isHTML,
  isShadowRoot,
  composedParentNode,
  renderedParent,
} from "../../lib/shadow-tree.js";
import { repaint } from "../repaint.js";
import { installMoveKeys } from "../dom-move.js";
import { keeps } from "../../lib/keeps.js";
import { stageOf, watchOwner } from "../arrivals.js";
import { COMMANDS } from "../../lib/widget-events.js";
import { reportFailure } from "../../lib/failure.js";

import type { ScopeOptions, Cell } from "../../base/command-declaration.js";
import type { Command, CommandRoute, Scope } from "./bindings.js";
import type { ElementPart, PartInfo } from "lit/directive.js";

type AttachedScope = Scope & { el: Element; validated: boolean };
type Declaration = { source: Element; scope: Scope; rows?: readonly Command[] };
type ButtonCommand = {
  source: Element;
  scope: Scope;
  row: Command;
  entry: CommandRoute;
};
type RunnableCommand = ButtonCommand & { run: () => unknown };
export type CommandCapability = { scope: Scope };

// The scopes still owed a first paint. A declaration joins here and `reflectFirstScopes`
// takes it out again, so one reading is owed per declaration whether that reading stands
// or refuses it. Transient by construction: `attachScope` schedules the frame that drains
// the set in the same breath as it adds to it.
const unpainted = new Map<Element, AttachedScope>();
// Native button activation belongs to the same row as its keyed invocation. Resolve
// getters and attachments again at the press: a retained listener must not retain a
// replaced command or invoke a control its owner no longer declares. The weak set
// prevents duplicate listeners when one capability is attached in several places.
const wiredButtons = new WeakSet();
const buttonBaselines: WeakMap<
  Element,
  { disabled: boolean; ariaDisabled: string | null }
> = new WeakMap();
const BUTTON_AVAILABILITY = Symbol("native command availability");
const commandAvailabilityReaders: Set<() => void> = new Set();
export function watchCommandAvailability(read: () => void) {
  commandAvailabilityReaders.add(read);
  availabilityDirty = true;
  return () => commandAvailabilityReaders.delete(read);
}
const reflectCommandAvailability = () => {
  for (const read of commandAvailabilityReaders) read();
};
const commandScopeReaders: Set<() => Iterable<Scope>> = new Set();
export function watchCommandScopes(read: () => Iterable<Scope>) {
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
type ButtonSource = Element | typeof PAGE_SOURCE;
const readings: WeakMap<
  ButtonSource,
  { readonly value: Map<HTMLButtonElement, ButtonCommand[]> }
> = new WeakMap();
const named: WeakMap<
  ButtonSource,
  Map<HTMLButtonElement, ButtonCommand[]>
> = new WeakMap();
const namers = new WeakMap<HTMLButtonElement, Set<WeakRef<ButtonSource>>>();
const sourceRefs = new WeakMap<ButtonSource, WeakRef<ButtonSource>>();
const refOf = (source: ButtonSource) => {
  let ref = sourceRefs.get(source);
  if (!ref) sourceRefs.set(source, (ref = new WeakRef(source)));
  return ref;
};
const lifetimes = new WeakSet<Element>();
const marked = new Set<ButtonSource>();
// Contribution controls have a native activation adapter that retains the projected
// surface and gesture intent. Its registration is also the row's semantic callback, so a
// scope projected onto its own control adds no second activation.
const projectedOnto = (control: Element, scope: Scope) =>
  [...(projectedScopes.get(control)?.values() ?? [])].some(
    (projected) => scopeIdentity(projected) === scopeIdentity(scope),
  );
// Each row with a handler, under each button it or its routes name.
function buttonNames(source: ButtonSource) {
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
  const names = new Map<HTMLButtonElement, ButtonCommand[]>();
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
const sameNames = (
  before: Map<HTMLButtonElement, ButtonCommand[]>,
  after: Map<HTMLButtonElement, ButtonCommand[]>,
) =>
  before.size === after.size &&
  [...after].every(([control, now]) => {
    const was = before.get(control) ?? [];
    return (
      was.length === now.length &&
      now.every(
        ({ scope, row, entry }, index) =>
          was[index]?.scope === scope &&
          was[index].row === row &&
          was[index].entry === entry,
      )
    );
  });
// Made on first ask.
function readingOf(source: ButtonSource) {
  let reading = readings.get(source);
  if (!reading) {
    // The same names as before stay the same reading, so its readers read again only
    // when one moved.
    let last = new Map<HTMLButtonElement, ButtonCommand[]>();
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
function mark(source: ButtonSource) {
  marked.add(source);
  if (source instanceof Element) dirtyElements.add(source);
  for (const control of named.get(source)?.keys() ?? []) dirtyButtons.add(control);
}
// Leaving the page or arriving in it marks the source. Registering reads the arrivals
// already made, whose owners' callbacks no reading may subscribe to.
function stand(source: Element) {
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
function reread(source: ButtonSource) {
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
function retire(source: ButtonSource) {
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
function nameButtons(source: ButtonSource) {
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
function commandsAt(control: HTMLButtonElement): RunnableCommand[] {
  const found: RunnableCommand[] = [];
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
// none is. Two available at once is an ambiguous button. A row that only adds a key to
// press the button names it with no `run`, and claims nothing (control-keys.js).
function chosenCommand<T extends ButtonCommand>(candidates: [T, ...T[]]): T {
  const available = candidates.filter(
    ({ scope, row, entry }) =>
      (!scope.when || scope.when()) &&
      declaredCommandAvailable(row, entry === row ? null : entry),
  );
  const [first, second] = available;
  if (first && second)
    throw new TypeError(
      `leaf: ${second.entry.id} shares a button with ${first.entry.id}; ` +
        `a key that presses ${first.entry.id}'s button names it as \`control\` with no \`run\``,
    );
  return first ?? candidates[0];
}
// A button no declaration names any more gets its own attributes back.
function releaseButton(control: Element) {
  const baseline = buttonBaselines.get(control);
  if (!(control instanceof HTMLButtonElement) || !baseline) return;
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
const buttonAvailability: WeakMap<Element, () => void> = new WeakMap();
function reflectButton(control: HTMLButtonElement) {
  buttonAvailability.get(control)?.();
  const ref = new WeakRef(control);
  let reading: HTMLButtonElement | null = control;
  // What the effect's first run threw, which it runs before `effect` returns.
  let failure: unknown = null;
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
function claimButton(control: HTMLButtonElement) {
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
export function runLanding(row: Command, run: () => unknown, from: Element | null) {
  run();
  const to = row.lands?.(from);
  if (to) focusDestination(to, "move");
}
function wireButton(control: HTMLButtonElement) {
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
function wireDeclaredButtons(scope: Scope) {
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
const elementScopes = new WeakMap<Element, AttachedScope>();
// The scopes other owners project onto an element, keyed by the owner, so one control can
// carry several: a margin entry holds its widget's scope and an obligation's digit route at once.
const projectedScopes = new WeakMap<Element, Map<object | symbol, Scope>>();
const commandScopeCapabilities = new WeakSet();
export const scopeIdentity = (scope: Scope) => scope.identity ?? scope;
const isCommandScope = (capability: object): capability is CommandCapability =>
  commandScopeCapabilities.has(capability);
// Context aliases are their own scope so native text entry always precedes them,
// even when the original declaration is attached to the exact editor. They remain
// references to that attachment, not copied handlers or a second command inventory.
const localContexts = new WeakMap<Element, WeakMap<Scope, Scope>>();
function localContext(source: Element, scope: Scope): Scope {
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
export const scopesAt = (element: Element): Scope[] => {
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
const contextRowsBySource: WeakMap<
  Element,
  WeakMap<Scope, WeakMap<Command, Command>>
> = new WeakMap();
function contextRows(declarations: readonly Declaration[]): Command[] {
  return declarations.flatMap(({ source, scope, rows = scope.rows }) => {
    let scopes = contextRowsBySource.get(source);
    if (!scopes) contextRowsBySource.set(source, (scopes = new WeakMap()));
    let rowsBySource = scopes.get(scope);
    if (!rowsBySource) scopes.set(scope, (rowsBySource = new WeakMap()));
    return rows.flatMap((row) => {
      const contributions = (): readonly CommandRoute[] =>
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
const contextScopeReaders: Set<(origin: Element | null) => Scope | null> = new Set();
export function contextScopes(
  title: string,
  resolve: (
    origin: Element | null,
  ) => { root: Element; declarations: Cell<readonly Declaration[]> } | null,
) {
  const identity = Object.freeze({});
  const read = (origin: Element | null) => {
    const projection = resolve(origin);
    if (!projection) return null;
    // The reading stands for one walk of the scopes, which reads its rows many times.
    let rows: Command[] | undefined;
    return {
      identity,
      title,
      contextual: true,
      el: projection.root,
      get rows() {
        return (rows ??= contextRows(word(projection.declarations)));
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
export const scopeRefs = new Set<WeakRef<Element>>();
const scopeRefFor = new WeakMap<Element, WeakRef<Element>>();
// Each element's place in `scopeRefs`, which orders declarations wherever they are merged.
const scopeOrder = new WeakMap<Element, number>();
let remembered = 0;
export const pruneScopedElements = () => {
  for (const ref of scopeRefs) if (!ref.deref()) scopeRefs.delete(ref);
};
function rememberScopedElement(el: Element) {
  if (scopeRefFor.has(el)) return;
  const ref = new WeakRef(el);
  scopeRefFor.set(el, ref);
  scopeRefs.add(ref);
  scopeOrder.set(el, (remembered += 1));
}
// The reference stops enumerating an element once nothing stands on it: no local
// declaration, no projected one, and no native button ownership still owed a handback.
function forgetScopedElement(el: Element) {
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
function attachScope(where: Element, declaration: Scope) {
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
function detachScope(element: Element, scope: Scope | null | undefined) {
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
function declaredScope(
  title: string | null,
  rows: readonly Command[],
  options: ScopeOptions | (() => boolean) | undefined,
) {
  const { when, escape, ready, claims } =
    typeof options === "function" ? { when: options } : (options ?? {});
  if (escape !== undefined && escape !== "inner")
    throw new TypeError(
      `A command scope's Escape ownership must be "inner", got ${String(escape)}`,
    );
  // `claims` takes the bindings it answers true for from every scope further out
  // while the user is in this one, as a view of the floating panel does.
  return {
    title,
    rows: checked(rows, title ?? "a scope", ready),
    when,
    escape,
    ready,
    claims,
  };
}

export function keys(where: Element, title: CommandCapability): readonly Command[];
export function keys(
  where: Element,
  title: string | null,
  rows: readonly Command[],
  options?: ScopeOptions | (() => boolean),
): readonly Command[];
export function keys(
  where: Element,
  ...declaration:
    | [capability: CommandCapability, rows?: undefined, options?: undefined]
    | [
        title: string | null,
        rows: readonly Command[],
        options?: ScopeOptions | (() => boolean) | undefined,
      ]
) {
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
// that read the element they stand on come as a function of it, called on each render,
// since the template declaring them renders that element.
export const commandsOn = directive(
  class extends AsyncDirective {
    #reconnect = () => {};
    #disconnect = () => {};
    constructor(part: PartInfo) {
      super(part);
      if (part.type !== PartType.ELEMENT)
        throw new TypeError("commandsOn belongs in a template's element part");
    }
    render(
      _title: string | null | CommandCapability,
      _rows?: readonly Command[] | ((element: Element) => readonly Command[]),
      _options?: ScopeOptions | (() => boolean),
    ) {
      return nothing;
    }
    update(
      part: ElementPart,
      values:
        | [CommandCapability, undefined?, undefined?]
        | [
            string | null,
            readonly Command[] | ((element: Element) => readonly Command[]),
            (ScopeOptions | (() => boolean))?,
          ],
    ) {
      const element = part.element;
      const declaration =
        values[1] === undefined
          ? values[0].scope
          : declaredScope(
              values[0],
              typeof values[1] === "function" ? values[1](element) : values[1],
              values[2],
            );
      let scope: AttachedScope | null = null;
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
// scope's title, rows and options as `keys` takes them, in one object (`statedScope`).
// The element says when it sets or changes them, or anything its rows read, with an
// `lf-commands` event it dispatches on itself (`COMMANDS`, lib/widget-events.js), so a
// page without Leaf, which hears nothing, binds no key. The element is the one the event
// began at, read off its path, since the window sees a shadow host as the target of an
// event from inside its root; a closed root hides the element, and its host is read in
// its place. A declaration other than the one standing stands in its
// place, and none withdraws it; the same one standing means a row's reading moved, so
// the element reads its rows again (`mark`), and so does every reader of the register's
// availability. An element that says it drew (`detail.within`) has every scope at or
// under it read its rows again instead (`paintKeysWithin`), since what they read from
// the nodes it drew may have changed; the light children a slot of its shadow tree
// shows are their own renderers' to say (`markPaintedIn`). A malformed declaration is refused as `keys`
// refuses one, and since a listener's exception never reaches the element that
// dispatched, the refusal is reported as that element's failure.
//
// Nothing hears an element that says its keys before it is placed, and they bind
// nothing. Reading the property where it is needed instead would find it for a key,
// along the key's path, but a declaration also acts before any key arrives, wherever
// the user is: it wires the buttons its rows name and shows their availability, and
// writes the element's `aria-keyshortcuts`; and the command reference lists every
// scope in the page. Those need each declaration as it is made, and a property is
// found only by a walk. Reading it as each element arrives would be such a walk on
// every page at every mutation, and would still leave a later change to be said. So
// the element says it, and the render check walks once for one never heard
// (`commandsUnread`).
const declared = new WeakMap();
const heard = new WeakSet<Element>();
/** Whether `element` holds an `lfCommands` this module never read. */
export const commandsUnread = (element: Element) =>
  element.lfCommands != null && !heard.has(element);
addEventListener(COMMANDS, (event) => {
  const [element] = event.composedPath();
  if (!(element instanceof Element)) return;
  const declaration = element.lfCommands ?? null;
  if (declaration !== null) heard.add(element);
  const standing = declared.get(element);
  if (declaration === (standing?.declaration ?? null)) {
    if (event.detail?.within) return paintKeysWithin(element);
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
    const scope = attachScope(element, statedScope(declaration).scope);
    declared.set(element, { declaration, scope });
  } catch (error) {
    reportFailure(element, error);
  }
});

// One scope wherever it stands: every attachment and projection of a capability
// shares its identity, so the scopes around a place count its commands once.
function capabilityOf(declaration: Scope): CommandCapability {
  const capability = Object.freeze({
    scope: { ...declaration, identity: Object.freeze({}) },
  });
  commandScopeCapabilities.add(capability);
  return capability;
}

/** Declare a command scope that presentation owners attach to generated controls.
 *
 * The declaration is browser state, not a hidden source element. Margin and Page Map
 * may attach the same capability to independent controls while each active reading is
 * rooted at the visible control in its own native layer.
 */
export function commandScope(
  title: string | null,
  rows: readonly Command[],
  options?: ScopeOptions | (() => boolean),
) {
  const capability = capabilityOf(declaredScope(title, rows, options));
  validateRows(capability.scope.rows, title ?? "a scope");
  return capability;
}

// A package states a scope as data, an object holding its title, rows and options, and
// gives that object wherever the scope applies: as the `lfCommands` of each element it
// stands on, and as the `scope` of a margin entry Leaf draws for it. The object is the
// scope, so the capability built from it is kept by the object, for good: a draft and
// its editor holding one object share one set of commands, an entry that names the
// object projects the commands its widget declared, and an object withdrawn and given
// again is the scope it was. The rows are checked as written when the object is first
// given. What they mean now is read where each attachment or projection is first
// painted, as for `keys`, and not here as `commandScope` reads it: an element says its
// keys as it upgrades, which can be before the state its rows read is set.
const stated = new WeakMap<object, CommandCapability>();
export function statedScope(
  declaration: NonNullable<Element["lfCommands"]> | CommandCapability,
): CommandCapability {
  if (isCommandScope(declaration)) return declaration;
  let capability = stated.get(declaration);
  if (!capability) {
    capability = capabilityOf(
      declaredScope(declaration.title, declaration.rows, declaration),
    );
    stated.set(declaration, capability);
  }
  return capability;
}

// `projector` is whatever the projecting owner keys its projection by; projecting again
// under the same key replaces that owner's scope and leaves every other owner's scope in place,
// and a null capability withdraws it.
export function projectCommandScope(
  control: Element,
  projector: object | symbol,
  capability: CommandCapability | null = null,
) {
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
// the same rows directly, while projections such as On Me select the role they need.
// A scope may sit on a nested control rather than the widget itself, so the walk goes
// down from `root` as it renders (`eachRendered`). It costs the widget's size, not the
// page's, and returns the scopes in the order they were declared.
function scopesWithin(root: Element, activeOnly: boolean) {
  const scopedIn: Element[] = [];
  if (root.isConnected)
    eachRendered(root, (node) => {
      if (elementScopes.has(node) || projectedScopes.has(node)) scopedIn.push(node);
    });
  const found: Declaration[] = [];
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
export const commandDeclarationsWithin = (root: Element) => scopesWithin(root, false);
export function commandsWithin(root: Element) {
  return scopesWithin(root, true).flatMap(({ source, scope }) =>
    scope.rows.filter(live).map((row) => ({ source, scope, row })),
  );
}
// Every declaration on one element is painted as one native shortcut attribute. A local
// declaration and any number of projected ones can coexist, so none may erase another's
// bindings. Each scope's live rows are read and refused on their own; the attribute is
// their union, since two scopes on one control may name one press: an obligation's route names
// the intrinsic key of the command it routes to, which that command's own scope names. The
// union also holds every key that reaches the element as a control from where the user is
// now, which its preview draws as key chips (control-keys.js, `paintCoreControls`, which
// says so here with `projectControlShortcuts`, since it reads this module's readings).
let reaching: (element: Element) => string = () => "";
export function projectControlShortcuts(read: (element: Element) => string) {
  reaching = read;
}
export function reflectElementShortcuts(element: Element) {
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
    ...new Set([
      ...available.flatMap((scope) =>
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
      ...reaching(element).split(" ").filter(Boolean),
    ]),
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
// a reflection whose rows asked `focused` (dom/focus.js, `followingFocus`), so a move reads
// again only those, not every element on the page. So a module's own state that a row
// reads is a signal, a focus listener's included: a plain variable is read once, and a
// change to it reaches the element only when something else marks it. What it reads
// from the document is a mechanical change, and its writer says so: `paintKeys()` marks
// every element, and `paintKeysWithin(root)` the ones a renderer's paint touched. A
// publication that moves nothing an element read, and no renderer whose output it reads,
// leaves its reflection as it is.
//
// A package's rows ask the browser where focus is, as a tree's `activeElement`, which
// no signal tracks. So each change in where the user is also marks the scoped elements
// around the node they left and around the one they reached (`markAroundMove`): the
// scopes on those paths, never the page's. The scopes around a node are also kept from
// when the user arrived on it, since a change that takes the node out of the page, as a
// drop does, takes the climb to them with it.
let keysDirty = true;
const dirtyElements = new Set<Element>();
function scopesAround(node: Node | null) {
  const found: Element[] = [];
  for (let at = node; at; at = renderedParent(at))
    if (isElement(at) && scopeRefFor.has(at)) found.push(at);
  return found;
}
let aroundArrival: WeakRef<Element>[] = [];
function markAroundMove(node: Element | null, _cause: unknown, left: Element | null) {
  const around = scopesAround(node);
  const marks = [
    ...aroundArrival.map((ref) => ref.deref()),
    ...scopesAround(left),
    ...around,
  ];
  aroundArrival = around.map((scoped) => new WeakRef(scoped));
  for (const scoped of marks) if (scoped) mark(scoped);
  if (marks.length) repaint();
}
onCurrentLocation(markAroundMove);
const tracked: WeakMap<Element, () => void> = new WeakMap();
// Native buttons read the same predicates for their availability. A command may name a
// control outside the element declaring it, so which buttons it names comes from the
// element's reading (`readingOf`), not from the buttons. Each button's availability is
// its own tracked effect (`reflectButton`), read again when its slice of a reading or a
// signal its predicates read moves, or a key paint reaches it; where the user is is
// such a signal for a button whose rows asked (`followingFocus`). Every button is read
// again on `paintKeys()`. Contribution projections read the same predicates, as one
// tracked reader beside them.
const dirtyButtons = new Set<Element>();
let availabilityTracking: (() => void) | null = null;
let availabilityDirty = true;
function reflectAvailabilityReaders() {
  availabilityDirty = false;
  availabilityTracking?.();
  let first = true;
  // What the effect's first run threw, which it runs before `effect` returns.
  let failure: unknown = null;
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
function reflectTracked(element: Element) {
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
  let initial: Element | null = element;
  // What the effect's first run threw, which it runs before `effect` returns.
  let failure: unknown = null;
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
export const paintKeysWithin = (root: Node) => {
  paintedRoots.add(root);
  repaint();
};
// The roots renderers painted since the frame last reflected, resolved to the scoped
// elements inside them by a walk of each outermost root, so a frame costs what was
// painted however many renderers painted, where a scan per paint cost every widget's
// update the whole page's scoped elements. A placed node about to move out of a painted
// root takes the marks of the scoped elements it holds with it (dom/dom-move.js), so the
// frame finds them wherever they land.
const paintedRoots = new Set<Node>();
installMoveKeys((node) => {
  if (!paintedRoots.size) return;
  for (let at = node as Node | null; at; at = composedParentNode(at))
    if (paintedRoots.has(at)) return markScopedIn(node);
});
const markScopedIn = (node: Node) =>
  eachRendered(node, (element) => {
    if (!scopeRefFor.has(element)) return;
    mark(element);
    dirtyButtons.add(element);
  });
// Each element at or under `node` as it renders (`eachRenderedElement`), into a closed
// stage by its host (`stageOf`) too. `node` may be a painted shadow root, or a text
// node a move carries. A widget's scopes and a paint's marks are found by the same steps.
function eachRendered(node: Node, visit: (element: Element) => void) {
  if (isElement(node)) visit(node);
  eachRenderedElement(node, (child) => eachRendered(child, visit), stagedRoot);
}
const stagedRoot = (host: Element) => host.shadowRoot ?? stageOf(host);
// The scoped elements a renderer painted at `root`: as `markScopedIn`, short of the
// light children a slot in its shadow tree shows, which their own renderers paint. A
// set of tabs shows a page's panels through one slot, and its strip draws again on
// every answer, which would otherwise read every scope on the page again.
const markPaintedIn = (root: Node) =>
  eachPainted(root, (element) => {
    if (!scopeRefFor.has(element)) return;
    mark(element);
    dirtyButtons.add(element);
  });
function eachPainted(node: Node, visit: (element: Element) => void) {
  if (isElement(node)) visit(node);
  if (
    isHTML(node, "slot") &&
    isShadowRoot(node.getRootNode()) &&
    node.assignedNodes().length
  )
    return;
  eachRenderedElement(node, (child) => eachPainted(child, visit), stagedRoot);
}
function claimPaintedRoots() {
  if (!paintedRoots.size) return;
  // Whether a node is a painted root or stands in one, remembered for every node a climb
  // passes, so roots that share ancestors climb each of them once.
  const covered = new Map<Node, boolean>();
  const coveredFrom = (node: Node | null) => {
    const passed: Node[] = [];
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
  const around = new Set<Element>();
  for (const root of paintedRoots) {
    if (coveredFrom(composedParentNode(root))) continue;
    markPaintedIn(root);
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
// The element scopes covering a node, innermost first — the climb crosses a shadow
// boundary the way `closest` climbs inside one, so a widget staging its controls in a
// shadow tree declares them the same way. Generated margin controls own their visible
// position directly; they no longer borrow scopes from hidden source controls.
export function scopesFor(node: Element | null) {
  const contexts = [...contextScopeReaders]
    .map((read) => read(node))
    .filter((scope) => scope !== null);
  const found: Scope[] = [];
  const seen = new Set();
  const collect = (start: Element | null) => {
    for (let a = start; a; a = renderedParent(a)) {
      for (const scope of [...scopesAt(a), ...contexts.filter(({ el }) => el === a)]) {
        const identity = scopeIdentity(scope);
        if (seen.has(identity)) continue;
        found.push(scope.el ? scope : { ...scope, el: a });
        seen.add(identity);
      }
      if (a.hasAttribute("data-lf-thread-surface")) break;
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
export const claimsEsc = (node: Element | null) =>
  scopesFor(node).some((scope) =>
    scope.rows.some((row) => bindings(row).includes("Escape") && live(row)),
  );
