/* Scopes: where a group of rows applies, registered against an element and gathered by
   title for the surfaces that project them.

   Standing in a surface is where focus is, not merely that the surface is open. A drawer's
   or panel's own button lives in the banner, so opening by pointer leaves the user
   outside it, and a key, a Tab or a click on its contents is what puts them in. Inside a
   text box the letter is a character, Shift+Enter writes a newline in a composer, and arrows move the caret.
   The typing scope claims those text-editing keys, so a user reaches a surface's
   letters and walks from its list rather than from its composer.

   Core registers scopes through internal `keys(el, title, rows)`; package widgets receive
   the same register as `commands(el, title, rows)` in `connectedCallback`. A module
   loaded on a page with no instance must contribute no scope or reference section. Runtime
   scopes live in `SCOPES`; `merge` is the only function that gathers scope sections.
   A scope may declare `ready` for incomplete inputs shared by its rows; a row or
   route may override that reading. Decision commands queue until the first saved read
   answers; their owning actions supply availability, including after a failed read.
   Normal element and page command declarations share native button activation. A
   sequence's `control` is a travel destination and arrival seat, not an activation
   declaration; native editing scopes may likewise name only the input's key route.
   An executable command owns its button's availability through its predicates;
   disabled attributes are outputs. ARIA refusal retains keyboard standing while
   activation checks the current command. Withdrawal returns both original attributes.
   Preserve the order of that list because the dispatcher and shortcut bar walk inward to
   outward while the full reference groups the same scopes for reading. */
import {
  AsyncDirective,
  PartType,
  directive,
  effect,
  nothing,
} from "../../vendor/browser-runtime.js";
import {
  activeRows,
  ariaShortcuts,
  bindings,
  checked,
  commandAvailable,
  commandBinding,
  controlAvailabilityOutput,
  declaredCommandAvailable,
  contextualRoute,
  contextBindings,
  commandRoutes,
  declaredBindings,
  titleOf,
  descriptionOf,
  lineOf,
  live,
  parsed,
  spokenBinding,
  validateRows,
  word,
} from "./bindings.js";
import { nativeActivationAt, nativeClaimAt } from "./text-entry.js";
import { onStanding } from "../focus.js";
import { renderedParent, under } from "../shadow.js";
import { repaint } from "../repaint.js";
import { keeps } from "../keeps.js";

// The scopes still owed a first paint. A declaration joins here and `reflectFirstScopes`
// takes it out again, so one reading is owed per declaration whether that reading stands
// or refuses it. Transient by construction: `attachScope` schedules the frame that drains
// the set in the same breath as it adds to it.
const unpainted = new Set();
// Whether native button availability is owed a reflection (`reflectButtonsTracked`).
let buttonsDirty = true;

// Native button activation belongs to the same row as its keyed invocation. Resolve
// getters and attachments again at the press: a retained listener must not retain a
// replaced command or invoke a control its owner no longer declares. The weak set
// prevents duplicate listeners when one capability is attached in several places.
const wiredButtons = new WeakSet();
const buttonReadings = new WeakMap();
export const buttonCommand = (control) => buttonReadings.get(control);
const buttonBaselines = new WeakMap();
const BUTTON_AVAILABILITY = Symbol("native command availability");
const commandAvailabilityReaders = new Set();
export function watchCommandAvailability(read) {
  commandAvailabilityReaders.add(read);
  buttonsDirty = true;
  return () => commandAvailabilityReaders.delete(read);
}
const reflectCommandAvailability = () => {
  for (const read of commandAvailabilityReaders) read();
};
const commandScopeReaders = new Set();
export function watchCommandScopes(read) {
  commandScopeReaders.add(read);
  buttonsDirty = true;
  return () => commandScopeReaders.delete(read);
}
function* nativeCommandScopes() {
  for (const ref of scopeRefs) {
    const source = ref.deref();
    if (source?.isConnected)
      for (const scope of scopesAt(source)) yield { source, scope };
  }
  for (const read of commandScopeReaders)
    for (const scope of read()) yield { source: document.documentElement, scope };
}
// Every button a command names, with the declarations naming it. Gathering them reads no
// predicate, so it is cheap to do on every pass; choosing among them is what reads.
function buttonDeclarations() {
  const declarations = new Map();
  for (const { source, scope } of nativeCommandScopes()) {
    if (scope.contextual || scope.sequence) continue;
    for (const row of scope.rows) {
      if (!row.run) continue;
      const routes = commandRoutes(row);
      for (const entry of routes.length ? routes : [row]) {
        const control = word(entry.control ?? row.control);
        if (!(control instanceof HTMLButtonElement) || !control.isConnected) continue;
        // Contribution controls have a native activation adapter that retains the
        // projected surface and gesture intent. Its registration is also the row's
        // semantic callback; attaching its keyboard scope adds no second activation.
        if (
          [...(projectedScopes.get(control)?.values() ?? [])].some(
            (projected) => scopeIdentity(projected) === scopeIdentity(scope),
          )
        )
          continue;
        if (!declarations.has(control)) declarations.set(control, []);
        const candidates = declarations.get(control);
        if (
          !candidates.some(
            (candidate) => candidate.row === row && candidate.entry.id === entry.id,
          )
        )
          candidates.push({ source, scope, row, entry });
      }
    }
  }
  return declarations;
}
// The one command a button answers now: the available declaration, or the first where
// none is. Two available at once is an ambiguous button.
function chosenCommand(candidates) {
  const available = candidates.filter(
    ({ scope, row, entry }) =>
      (!scope.when || scope.when()) &&
      declaredCommandAvailable(row, entry === row ? null : entry),
  );
  if (available.length > 1)
    throw new TypeError(
      `leaf: ${available[1].entry.id} shares a button with ${available[0].entry.id}`,
    );
  return available[0] ?? candidates[0];
}
function buttonCommands() {
  return new Map(
    [...buttonDeclarations()].map(([control, candidates]) => [
      control,
      chosenCommand(candidates),
    ]),
  );
}
// A button no declaration names any more gets its own attributes back.
function releaseButtons(declarations) {
  for (const ref of scopeRefs) {
    const control = ref.deref();
    if (!control || !buttonBaselines.has(control) || declarations.has(control))
      continue;
    buttonReadings.delete(control);
    buttonAvailability.get(control)?.();
    buttonAvailability.delete(control);
    const { disabled, ariaDisabled } = buttonBaselines.get(control);
    if (control.disabled !== disabled) control.disabled = disabled;
    keeps(control, "aria-disabled", ariaDisabled);
    buttonBaselines.delete(control);
    controlAvailabilityOutput(control, BUTTON_AVAILABILITY);
    reflectElementShortcuts(control);
    forgetScopedElement(control);
  }
}
// One button's availability, as a tracked effect: a signal its command's predicates read
// moving marks this button alone for the next frame. The effect stays subscribed to
// those signals, so it holds the button and its declarations only while it first reads
// them, and a later run that finds the button gone disposes it.
const buttonAvailability = new WeakMap();
// The declarations each button's availability was last read from, so a pass reads a
// button again when what names it changed.
const buttonCandidates = new WeakMap();
const sameCandidates = (left, right) =>
  left?.length === right.length &&
  right.every(
    (candidate, index) =>
      candidate.scope === left[index].scope &&
      candidate.row === left[index].row &&
      candidate.entry === left[index].entry,
  );
function reflectButton(control, candidates) {
  buttonAvailability.get(control)?.();
  buttonCandidates.set(control, candidates);
  const ref = new WeakRef(control);
  let reading = candidates;
  let failure = null;
  const dispose = effect(() => {
    if (reading) {
      const read = reading;
      reading = null;
      try {
        const command = chosenCommand(read);
        const { scope, row, entry } = command;
        const disabled = Boolean(
          (scope.when && !scope.when()) ||
          !commandAvailable(row, entry === row ? null : entry),
        );
        keeps(ref.deref(), "aria-disabled", disabled ? "true" : null);
        buttonReadings.set(ref.deref(), command);
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
function wireButton(control) {
  claimButton(control);
  if (wiredButtons.has(control)) return;
  wiredButtons.add(control);
  control.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0) return;
    const command = buttonCommands().get(control);
    if (!command) return;
    event.preventDefault();
    if (
      (command.scope.when && !command.scope.when()) ||
      !commandAvailable(
        command.row,
        command.entry === command.row ? null : command.entry,
      )
    )
      return;
    command.row.run(
      commandBinding(command.row, command.entry === command.row ? null : command.entry),
    );
  });
}
// A button is pressed as soon as it can be reached, which can be before the frame that
// paints its declaration: a key run in the same task that focused a new thread card
// clicked a Resolve the paint had not yet wired, and nothing happened. So a declaration
// wires the buttons it names as elements when it is made. A control named by a getter
// may not exist yet, and is wired at paint as before; the listener resolves its command
// at the press either way.
function wireDeclaredButtons(scope) {
  if (scope.contextual || scope.sequence) return;
  for (const row of scope.rows) {
    if (!row.run || typeof row.routes === "function") continue;
    for (const entry of row.routes?.length ? row.routes : [row]) {
      const control = entry.control ?? row.control;
      if (control instanceof HTMLButtonElement) wireButton(control);
    }
  }
}

// The scopes declared against an element — a WeakMap, so a scope leaves with the element
// that owns it — and, for the command reference dialog, their rows gathered under each title. A section is
// its sentences: the tenth grip on a page says what the first one says, so it is one
// section, while a widget whose keys are declared in two places (a draft's way in, and the
// editor it opens) contributes to one section from both.
// Two contributors to one section are live where either is, and the user is in it where
// either says so — a `when` or an `at` nobody wrote means always, which is what makes the
// first contributor's silence carry rather than the second's answer.
const either = (a, b) => (a && b ? () => a() || b() : undefined);
export const elementScopes = new WeakMap();
// The scopes other owners project onto an element, keyed by the owner, so one control can
// carry several: a margin entry holds its widget's scope and an ask's digit route at once.
const projectedScopes = new WeakMap();
const commandScopeCapabilities = new WeakSet();
export const scopeIdentity = (scope) => scope.identity ?? scope;
export const isCommandScope = (capability) =>
  capability != null && commandScopeCapabilities.has(capability);
// Context aliases are their own scope so native text entry always precedes them,
// even when the original declaration is attached to the exact editor. They remain
// references to that attachment, not copied handlers or a second command inventory.
const localContexts = new WeakMap();
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
export const scopesAt = (element) => {
  const original = [
    elementScopes.get(element),
    ...(projectedScopes.get(element)?.values() ?? []),
  ].filter(Boolean);
  return original.flatMap((scope) =>
    scope.contextual ? [scope] : [scope, localContext(element, scope)],
  );
};

// Compile only the explicitly declared aliases. Availability is kept on the referenced
// owner, so a disabled action keeps its keys reserved; removing/replacing an attachment
// withdraws its old commands at invocation and at the next reading. Both a local widget
// and a question representative use this same compiler.
const contextRowsBySource = new WeakMap();
function contextRows(declarations) {
  return declarations.flatMap(({ source, scope, rows = scope.rows }) => {
    let scopes = contextRowsBySource.get(source);
    if (!scopes) contextRowsBySource.set(source, (scopes = new WeakMap()));
    let rowsBySource = scopes.get(scope);
    if (!rowsBySource) scopes.set(scope, (rowsBySource = new WeakMap()));
    return rows.flatMap((row) => {
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
          get line() {
            return row.line;
          },
          get keys() {
            return this.routes.map(({ binding }) => binding);
          },
          get routes() {
            return contributions().flatMap((contribution) => {
              const aliases = contextBindings(contribution);
              const reference = Object.freeze({
                id: contribution.id,
                source,
                scope,
                row,
                binding: commandBinding(
                  row,
                  contribution === row ? null : contribution,
                ),
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
                    line: contribution.line,
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
const contextScopeReaders = new Set();
export function contextScopes(title, resolve) {
  const identity = Object.freeze({});
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
export const scopeRefs = new Set();
const scopeRefFor = new WeakMap();
export const pruneScopedElements = () => {
  for (const ref of scopeRefs) if (!ref.deref()) scopeRefs.delete(ref);
};
function rememberScopedElement(el) {
  if (scopeRefFor.has(el)) return;
  const ref = new WeakRef(el);
  scopeRefFor.set(el, ref);
  scopeRefs.add(ref);
}
// The reference stops enumerating an element once nothing stands on it: no local
// declaration, no projected one, and no native button ownership still owed a handback.
function forgetScopedElement(el) {
  if (elementScopes.has(el) || projectedScopes.has(el) || buttonBaselines.has(el))
    return;
  const ref = scopeRefFor.get(el);
  if (ref) scopeRefs.delete(ref);
  scopeRefFor.delete(el);
}
// One section per title, gathered from every contributor. Written once because the gathering
// happens twice and used to be spelled three times: here at declaration, where a widget's
// contributors arrive an upgraded element at a time, and at each open of the reference, where
// core's scopes and the widgets' are gathered into one list of sections. The rules above are
// this function — rows keyed by command id, `when` and `at` joined by or — and a near-copy of a
// merge is a merge that drifts on the day one of the three learns something.
export function merge(sections, { title, when, at, liveInCommandReference, rows }) {
  // A contributor the page hasn't got brings nothing. A section's `when` is the OR of its
  // contributors, so a live one otherwise carried a dead one's keys into the reference
  // under the shared title — the versions menu named a walk on a page with one version,
  // where the only key it really has is the way out. That is the same "a key on screen is
  // a key that works" the row `when` keeps for the line, asked one level up, and it is
  // what lets two capabilities of different liveness share a heading: the walk states
  // "somewhere to step" and the mode carrying the Escape states "there is a menu", which
  // is what a layer's way out has to hold wherever the layer does.
  //
  // Asked here rather than at the user, because the section is built once per open —
  // declaredStack has one caller, showCommandReference — where a `when` may be the whole event log
  // folded and the line's own walk avoids it for exactly that reason.
  if (when && !when()) return;
  const seen = sections.get(title);
  if (!seen) {
    sections.set(title, {
      title,
      when,
      at,
      liveInCommandReference,
      rows: new Map(rows),
    });
    return;
  }
  for (const [key, row] of rows) seen.rows.set(key, row);
  seen.when = either(seen.when, when);
  seen.at = either(seen.at, at);
  seen.liveInCommandReference ||= liveInCommandReference;
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
 * thread a box to reply into — and it gates the line, where the user is standing in the
 * scope and can see the answer. So the reference names Enter wherever the page has
 * threads, and the line offers it only on a focused thread with a reply or reopen action.
 * One `when` answering both left Enter live over the whole page, where the press no-opped.
 *
 * A control whose keys change with its state declares every state's rows at once, each
 * gated by its own row `when`, and calls paintKeys() when the state moves — a grab is
 * Enter on an already-focused grip, so no focus event would repaint the line.
 *
 * Registering at upgrade rather than at module load is what keeps the reference honest:
 * a module stays loaded after the last element it upgraded leaves — a version activation
 * replaces main, a panel body is rebuilt — so a scope declared at the top level would go
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
 * page-wide reflection. One a painter attaches mid-frame, as the banner's touch
 * controls are, is read at the head of the frame its repaint schedules.
 *
 * Passing a `commandScope()` capability in place of `title` attaches that one
 * declaration to retained widget DOM as well as its generated projections. Returns the
 * rows, so a widget that says its own keys out loud — a grip announcing what a grabbed
 * card answers — reads them back off the declaration rather than restating them.
 */
// Stand a declaration on `where` in place of whatever stood there, owed its first
// reading. A scope is never changed once it stands: its contextual aliases are built
// from it once (`localContext`), so a new reading is a new scope.
function attachScope(where, declaration) {
  const scope = { ...declaration, el: where, validated: false };
  unpainted.delete(elementScopes.get(where));
  elementScopes.set(where, scope);
  unpainted.add(scope);
  wireDeclaredButtons(scope);
  rememberScopedElement(where);
  buttonsDirty = true;
  repaint();
  return scope;
}

// Withdraw an element's own declaration if `scope` is still the one standing there,
// and re-read the element's shortcuts from what remains: projected scopes on it stand,
// and an element the reference forgets is never read again. Returns whether anything
// was withdrawn.
function detachScope(element, scope) {
  if (elementScopes.get(element) !== scope) return false;
  unpainted.delete(scope);
  elementScopes.delete(element);
  forgetScopedElement(element);
  buttonsDirty = true;
  reflectElementShortcuts(element);
  return true;
}

// Both element-bound keys and a reusable command capability declare the same scope.
// Attachment decides when its scene is validated, not what a declaration may contain.
function declaredScope(title, rows, options) {
  const { when, escape, ready } =
    typeof options === "function" ? { when: options } : (options ?? {});
  if (escape !== undefined && escape !== "inner")
    throw new TypeError(
      `A command scope's Escape ownership must be \"inner\", got ${String(escape)}`,
    );
  return {
    title,
    rows: checked(rows, title ?? "a scope", ready),
    when,
    escape,
    ready,
  };
}

export function keys(where, title, rows, options) {
  if (rows === undefined && isCommandScope(title))
    return attachScope(where, title.scope).rows;
  // A declaration this one replaces before its first paint is owed nothing: read at
  // the frame, a stale scope that refused would retract the element's standing
  // declaration along with itself.
  return attachScope(where, declaredScope(title, rows, options)).rows;
}

// Template scopes use the same attachment as `keys`. Each render stands its latest
// declaration — title, rows, callbacks and availability — in place of the last, owing
// one reading of this element alone, so an unchanged render costs that one element.
// Removing the directive withdraws only its own attachment, including when Lit keeps
// the element. Temporary disconnection restores that declaration on reconnection. Rows
// that read the element they stand on, as a disclosure's toggle does, come as a function
// of it, called on each render, since the template declaring them renders that element.
export const commandsOn = directive(
  class extends AsyncDirective {
    #element;
    #declaration;
    #scope = null;
    constructor(part) {
      super(part);
      if (part.type !== PartType.ELEMENT)
        throw new TypeError("commandsOn belongs in a template's element part");
    }
    render() {
      return nothing;
    }
    update(part, [title, rows, options]) {
      this.#element = part.element;
      this.#declaration =
        rows === undefined && isCommandScope(title)
          ? title.scope
          : declaredScope(
              title,
              typeof rows === "function" ? rows(part.element) : rows,
              options,
            );
      if (this.isConnected) this.reconnected();
      return nothing;
    }
    reconnected() {
      this.#scope = attachScope(this.#element, this.#declaration);
    }
    disconnected() {
      if (detachScope(this.#element, this.#scope)) repaint();
    }
  },
);

/** Declare a command scope that presentation owners attach to generated controls.
 *
 * The declaration is browser state, not a hidden source element. Margin and Page Map
 * may attach the same capability to independent controls while each active reading is
 * rooted at the visible control in its own native layer.
 */
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
// under the same key replaces that owner's scope and leaves every other owner's standing,
// and a null capability withdraws it.
export function projectCommandScope(control, projector, capability = null) {
  dirtyButtons.add(control);
  const projections = projectedScopes.get(control) ?? new Map();
  if (capability == null) {
    projections.delete(projector);
    if (!projections.size) {
      projectedScopes.delete(control);
      forgetScopedElement(control);
    }
    reflectElementShortcuts(control);
    return;
  }
  projections.set(projector, capability.scope);
  projectedScopes.set(control, projections);
  rememberScopedElement(control);
  reflectTracked(control);
}

// Commands whose scope stands in one widget, in declaration order. Preserve the
// declaring scope beside each row: a control presentation may be hoisted elsewhere,
// while Decision ownership still belongs to the source that declared the command.
// This is the shared capability reading: the dispatcher, shortcut bar and reference use
// the same rows directly, while projections such as Questions select the role they need.
// A scope may sit on a nested control rather than the widget itself, so containment
// follows the runtime's cross-shadow parent walk instead of a light-DOM selector.
function scopesWithin(root, activeOnly) {
  pruneScopedElements();
  const found = [];
  const seen = new Set();
  for (const ref of scopeRefs) {
    const scoped = ref.deref();
    if (!scoped?.isConnected) continue;
    let inside = false;
    for (let node = scoped; node; node = renderedParent(node))
      if (node === root) {
        inside = true;
        break;
      }
    if (!inside) continue;
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
export const commandDeclarationsWithin = (root) => scopesWithin(root, false);
export function commandsWithin(root) {
  return scopesWithin(root, true).flatMap(({ source, scope }) =>
    scope.rows.filter(live).map((row) => ({ source, scope, row })),
  );
}
// Every declaration on one element is painted as one native shortcut attribute. A local
// declaration and any number of projected ones can coexist, so none may erase another's
// bindings. Each scope's live rows are read and refused on their own; the attribute is
// their union, since two scopes on one control may name one press: an ask's route names
// the intrinsic key of the command it routes to, which that command's own scope names.
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
// Ahead of standing content, so an ambiguous declaration is refused under its own title
// rather than under whichever surface reads its rows first.
export function reflectFirstScopes() {
  reflectButtonsTracked();
  for (const scope of [...unpainted]) {
    unpainted.delete(scope);
    reflectTracked(scope.el);
  }
}
// Reflect after standing content has projected all of its scopes in the current
// repaint frame. A focus move and a replacement can each ask for a paint, but the
// shortcut attribute should represent only the final standing of that frame.
// A scope refused here is reported, and the elements after it still paint.
//
// An element's reflection reads its rows' liveness, and that reads two kinds of input.
// What it reads from the semantic root is tracked: each reflection runs as a signals
// effect, and a publication that moves something it read marks that element alone for
// the next frame. What it reads from the document is a mechanical change, and its writer
// says so: `paintKeys()` marks every element, and `paintKeysWithin(root)` the ones a
// renderer's paint touched. A publication that moves nothing an element read, and no
// renderer whose output it reads, leaves its reflection standing.
let keysDirty = true;
const dirtyElements = new Set();
const tracked = new WeakMap();
// Native buttons read the same predicates for their availability. Which button a
// command names is gathered across every scope on each pass, since a command may name a
// control outside the element declaring it; each button's availability is its own
// tracked effect (`reflectButton`), read again when a signal it read moves or a key
// paint reaches it. Every button is read again when a declaration is attached, projected
// or withdrawn, on `paintKeys()`, and when the user's standing moves, which predicates
// read without a signal. Contribution projections read the same predicates, as one
// tracked reader beside them.
const dirtyButtons = new Set();
let availabilityTracking = null;
let availabilityDirty = true;
onStanding(() => {
  buttonsDirty = true;
});
function reflectAvailabilityReaders() {
  availabilityDirty = false;
  availabilityTracking?.();
  let first = true;
  let failure = null;
  availabilityTracking = effect(() => {
    if (first) {
      first = false;
      try {
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
  if (!buttonsDirty && !dirtyButtons.size && !availabilityDirty) return;
  const every = buttonsDirty;
  buttonsDirty = false;
  // Getter-named buttons may arrive after declaration. Claim their output fields before
  // availability readers project commands; otherwise their initial disabled paint is
  // mistaken for an input until the next frame. Readers may materialize more controls,
  // which the gathering below then claims and presents.
  for (const control of buttonDeclarations().keys()) claimButton(control);
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
  const dirty = new Set(dirtyButtons);
  dirtyButtons.clear();
  const declarations = buttonDeclarations();
  releaseButtons(declarations);
  for (const [control, candidates] of declarations) {
    claimButton(control);
    rememberScopedElement(control);
    wireButton(control);
    if (
      !every &&
      !dirty.has(control) &&
      buttonAvailability.has(control) &&
      sameCandidates(buttonCandidates.get(control), candidates)
    )
      continue;
    try {
      reflectButton(control, candidates);
    } catch (error) {
      failures.push(error);
    }
  }
  for (const failure of failures) reportError(failure);
}
function reflectTracked(element) {
  tracked.get(element)?.();
  const ref = new WeakRef(element);
  let first = true;
  let failure = null;
  const dispose = effect(() => {
    if (first) {
      first = false;
      try {
        reflectElementShortcuts(ref.deref());
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
  if (!keysDirty && !dirtyElements.size) return;
  const every = keysDirty;
  keysDirty = false;
  const dirty = [...dirtyElements];
  dirtyElements.clear();
  reflectButtonsTracked();
  pruneScopedElements();
  const elements = every ? [...scopeRefs].map((ref) => ref.deref()) : dirty;
  for (const scoped of elements) {
    if (!scoped?.isConnected) continue;
    try {
      reflectTracked(scoped);
    } catch (error) {
      reportError(error);
    }
  }
}
export const paintKeys = () => {
  keysDirty = true;
  buttonsDirty = true;
  repaint();
};
/** Mark for reflection the scoped elements inside `root`, as a renderer that has just
 * rewritten that part of the document does, and repaint the frame whose shared surfaces,
 * the shortcut bar among them, read the same rows. */
export const paintKeysWithin = (root) => {
  for (const ref of scopeRefs) {
    const scoped = ref.deref();
    if (scoped && under(scoped, root)) {
      dirtyElements.add(scoped);
      dirtyButtons.add(scoped);
    }
  }
  repaint();
};
/** What a scope answers right now, as a listener hears it read out — key names rather than
 * the chips the eye reads, since a screen reader renders "esc" literally. Off the register,
 * so an announcement cannot name a key the rows stopped binding.
 */
export const saying = (rows) =>
  activeRows(rows, "an announced scope")
    .map((row) => `${spoken(row)} ${lineOf(row)}`)
    .join(", ");
// A row's own label where it has one, read the way every other surface reads a cell, and
// the bindings where it has none — which is what keeps a listener hearing "Escape" rather
// than the line's "esc". Asking whether the label was written as a string made the same fact
// announce two ways by accident: an option group's digits are spelled "1–3" because its label
// happens to be a string, while the sequence's were read out as "1 or 2 or 3" because its label
// counts what the page holds and so has to be a function.
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
export function scopesFor(node) {
  const contexts = [...contextScopeReaders].map((read) => read(node)).filter(Boolean);
  const found = [];
  const seen = new Set();
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
// where the user is standing": the sequence refuses to arm there, and focus entering one
// disarms it. Every panel and mode in the runtime carries a rung of some kind, so a
// question asked of the whole stack would answer yes almost everywhere and the sequence would
// never arm at all.
export const claimsEsc = (node) =>
  scopesFor(node).some((scope) =>
    scope.rows.some((row) => live(row) && bindings(row).includes("Escape")),
  );
