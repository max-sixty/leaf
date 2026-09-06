/* Scopes: where a group of rows applies, registered against an element and gathered by
   title for the surfaces that project them.

   Standing in a surface is where focus is, not merely that the surface is open. A tray's
   or panel's own button lives in the banner, so opening by pointer leaves the reader
   outside it, and a key, a Tab or a click on its contents is what puts them in. Inside a
   text box the letter is a character, Enter writes a newline, and arrows move the caret.
   The typing scope claims those text-editing keys, so a reader reaches a surface's
   letters and walks from its list rather than from its composer.

   Core registers scopes through internal `keys(el, title, rows)`; package widgets receive
   the same register as `commands(el, title, rows)` in `connectedCallback`. A module
   loaded on a page with no instance must contribute no scope or help section. Runtime
   scopes live in `SCOPES`; `merge` is the only function that gathers scope sections.
   Preserve the order of that list because the dispatcher and key line walk inward to
   outward while the full reference groups the same scopes for reading. */
import {
  MODIFIER_KEYS,
  activeRows,
  ariaShortcuts,
  bindings,
  checked,
  live,
  parsed,
  spokenBinding,
  validateRows,
  word,
} from "./bindings.js";
import { upFrom } from "../shadow.js";

// The frame that repaints where the reader is standing. The frame is the register's;
// the painting is standing.js's, registered by leaf.js at boot. Every module that
// declares keys imports this register, so the register imports no painter back.
//
// Coalesced to a frame: a focus move is a focusout then a focusin, and painting between
// them would flash the scope of nowhere and drop the ring for a frame. The frame is also
// what puts the first paint after every module has evaluated, which is what makes it the
// boundary a declaration's rows are first read at (`keys`, below).
let painter = null;
export function paintsHere(paint) {
  painter = paint;
}
// The scopes still owed a first paint. A declaration joins here and `reflectShortcuts`
// takes it out again, so one reading is owed per declaration whether that reading stands
// or refuses it. Transient by construction: `keys` schedules the frame that drains the set
// in the same breath as it adds to it, and a `paintKeys` landing before that frame reads
// the connected ones on its own way through.
const unpainted = new Set();
let herePending = false;
export function paintHere() {
  if (herePending) return;
  herePending = true;
  requestAnimationFrame(() => {
    herePending = false;
    // No default: a frame with nothing registered means leaf.js's body never ran — its
    // first step registers the painter — and it fails here rather than painting nothing.
    if (!painter)
      throw new Error("leaf: leaf.js did not boot; nothing paints the standing chrome");
    // Ahead of the painting, so an ambiguous scope is refused under its own title rather
    // than under whichever surface reads its rows first.
    for (const scope of unpainted) reflectShortcuts(scope);
    painter();
  });
}

// The scopes declared against an element — a WeakMap, so a scope leaves with the element
// that owns it — and, for the overlay, their rows gathered under each title. A section is
// its sentences: the tenth grip on a page says what the first one says, so it is one
// section, while a widget whose keys are declared in two places (a draft's way in, and the
// editor it opens) contributes to one section from both.
// Two contributors to one section are live where either is, and the reader is in it where
// either says so — a `when` or an `at` nobody wrote means always, which is what makes the
// first contributor's silence carry rather than the second's answer.
const either = (a, b) => (a && b ? () => a() || b() : undefined);
// The same or, for a predicate whose silence means no rather than yes: what any contributor
// claims, the section claims. `either`'s identity is the wrong one here, and using it was
// this file's own bug one field over — a scope's claim deleted by a contributor that stated
// none, which is what `In a text box` is, the typing scope claiming the keys that put a
// character in a box and every wired box contributing a second section under its title
// claiming nothing. Takes the binding its callers take, where `when` and `at` take none.
const anyOf = (a, b) => (a && b ? (...args) => a(...args) || b(...args) : (a ?? b));
export const elementScopes = new WeakMap();
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
function forgetScopedElement(el) {
  const ref = scopeRefFor.get(el);
  if (ref) scopeRefs.delete(ref);
  scopeRefFor.delete(el);
}
export const byCommand = (rows) => rows.map((row) => [row.id, row]);
// One section per title, gathered from every contributor. Written once because the gathering
// happens twice and used to be spelled three times: here at declaration, where a widget's
// contributors arrive an upgraded element at a time, and at each open of the reference, where
// core's scopes and the widgets' are gathered into one list of sections. The rules above are
// this function — rows keyed by command id, `when` and `at` joined by or — and a near-copy of a
// merge is a merge that drifts on the day one of the three learns something.
export function merge(sections, { title, when, at, claims, rows }) {
  // A contributor the page hasn't got brings nothing. A section's `when` is the OR of its
  // contributors, so a live one otherwise carried a dead one's keys into the reference
  // under the shared title — the versions menu named a walk on a page with one version,
  // where the only key it really has is the way out. That is the same "a key on screen is
  // a key that works" the row `when` keeps for the line, asked one level up, and it is
  // what lets two capabilities of different liveness share a heading: the walk states
  // "somewhere to step" and the mode carrying the Escape states "there is a menu", which
  // is what a layer's way out has to hold wherever the layer does.
  //
  // Asked here rather than at the reader, because the section is built once per open —
  // declaredStack has one caller, showHelp — where a `when` may be the whole event log
  // folded and the line's own walk avoids it for exactly that reason.
  if (when && !when()) return;
  const seen = sections.get(title);
  if (!seen) {
    sections.set(title, { title, when, at, claims, rows: new Map(rows) });
    return;
  }
  for (const [key, row] of rows) seen.rows.set(key, row);
  seen.when = either(seen.when, when);
  seen.at = either(seen.at, at);
  // The claim travels because the reference reads it: a section that takes the keyboard
  // whole is one the reader is in or is not near at all, and its rows are then read by
  // their own liveness (showHelp). Dropped here, the chord's section arrived claiming
  // nothing, was listed whole, and named a list the page had not got — a fact stated on
  // the scope and lost on the way to the one surface that asks for it.
  seen.claims = anyOf(seen.claims, claims);
}

/** Declare a scope's keys where the code implementing them is.
 *
 * `where` is the element focus must be inside, `title` names the scope in the "?" overlay
 * (null for one the reference has no room to name), `rows` are its bindings, and the
 * optional configuration carries `when` (whether the page has this scope at all) and
 * `answer` (the concise current answer when this scope belongs to an Ask). A function in
 * the fourth position is shorthand for `{when: function}`.
 *
 * A scope's `when` and a row's `when` are different questions, and keeping them apart is
 * what lets one declaration feed both surfaces. The scope's is the capability — does this
 * machine have neighbours to walk, does this page have a second version — and it gates the
 * reference. The row's is whether this press would move now — is a card held, has this
 * thread a box to reply into — and it gates the line, where the reader is standing in the
 * scope and can see the answer. So the reference names `x` wherever the page has threads,
 * which is what a reader learning the keyboard needs, and the line offers it only on a
 * thread that has something to resolve, which is what "a key on screen is a key that
 * works" asks for. One `when` answering both left `x` and Enter live over the whole page,
 * where the press no-opped.
 *
 * A control whose keys change with its state declares every state's rows at once, each
 * gated by its own row `when`, and calls paintKeys() when the state moves — a grab is
 * Enter on an already-focused grip, so no focus event would repaint the line.
 *
 * Registering at upgrade rather than at module load is what keeps the reference honest:
 * every x-upgrade module loads on every page, so a scope declared at the top level is help
 * for a widget the page hasn't got. The dispatch scope leaves through the weak map; the
 * enumerable reference prunes its element when it disconnects. A connected control that
 * stops answering a key says so in the row's `when`, where every surface can read it.
 *
 * Declaring is not reading. `checked` reads the rows as written — ids, shapes, canonical
 * spellings — and refuses a malformed declaration here, where the caller wrote it. What
 * those rows mean right now waits for the scope's first paint: the scene is the scope's
 * `when` and each row's own, callbacks over their owner's state, and a scope declared
 * while modules are still evaluating would run them against an owner that has not
 * evaluated yet — the one evaluation-order path `leaf/evaluation-order` cannot see, since
 * the rule reads module bodies and not the callbacks another module runs. The frame is
 * after every module body, so the ambiguous scene and the `aria-keyshortcuts` projection
 * are both settled there; a first paint that refuses a scope retracts it from both
 * indexes.
 *
 * Returns the rows, so a widget that says its own keys out loud — a grip announcing what a
 * grabbed card answers — reads them back off the declaration rather than restating them.
 */
export function keys(where, title, rows, options) {
  const configuration =
    typeof options === "function" ? { when: options } : (options ?? {});
  if (typeof configuration !== "object")
    throw new TypeError("A command scope's options must be an object");
  const { when, answer } = configuration;
  if (answer !== undefined && typeof answer !== "function")
    throw new TypeError("A command scope's answer must be a function");
  const scope = {
    title,
    el: where,
    rows: checked(rows, title ?? "a scope"),
    when,
    answer,
    validated: false,
  };
  // A declaration this one replaces before its first paint is owed nothing: read at
  // the frame, a stale scope that refused would retract the element's standing
  // declaration along with itself.
  unpainted.delete(elementScopes.get(where));
  elementScopes.set(where, scope);
  rememberScopedElement(where);
  // Published unread, and read at the frame below. The element keeps whatever
  // `aria-keyshortcuts` it already stood with until that paint answers, rather than
  // losing it for a frame or claiming a set of keys this declaration has not been read
  // for.
  unpainted.add(scope);
  paintHere();
  return rows;
}

// Commands whose scope stands in one widget, in declaration order. Preserve the
// declaring scope beside each row: a control presentation may be hoisted elsewhere,
// while Decision ownership still belongs to the source that declared the command.
// This is the shared capability reading: the dispatcher, key line and reference use
// the same rows directly, while projections such as Asks select the role they need.
// A scope may sit on a nested control rather than the widget itself, so containment
// follows the runtime's cross-shadow parent walk instead of a light-DOM selector.
function scopesWithin(root, activeOnly) {
  pruneScopedElements();
  const found = [];
  for (const ref of scopeRefs) {
    const scoped = ref.deref();
    if (!scoped?.isConnected) continue;
    let inside = false;
    for (let node = scoped; node; node = upFrom(node))
      if (node === root) {
        inside = true;
        break;
      }
    if (!inside) continue;
    const scope = elementScopes.get(scoped);
    if (!scope || (activeOnly && scope.when && !scope.when())) continue;
    found.push({ source: scoped, scope });
  }
  return found;
}
export function commandsWithin(root) {
  return scopesWithin(root, true).flatMap(({ source, scope }) =>
    scope.rows.filter(live).map((row) => ({ source, row })),
  );
}
// Command-scope metadata under one widget, in declaration order. The action rows and
// the current-answer reading are different projections of the same package
// declaration: row liveness controls what can be pressed now, while an answer remains
// readable after those controls have settled or become unavailable.
export const commandScopesWithin = (root) =>
  scopesWithin(root, false).map(({ source, scope }) => ({
    source,
    answer: scope.answer,
  }));
// One scope painted: its rows read for the scene they are in, and that reading projected
// onto the element. This is the whole of a scope's first paint, so the attempt is what
// takes it out of `unpainted` — a refusal retracts the scope rather than leaving it owed
// a second reading.
function reflectShortcuts(scope) {
  unpainted.delete(scope);
  const available = !scope.when || scope.when();
  try {
    if (available) validateRows(scope.rows, scope.title ?? "a scope");
  } catch (error) {
    // A scope is published before it is read, and a capability-gated one may only become
    // readable some paints later. If the reading that first reaches it fails, retract the
    // unpublished contract completely; leaving it in the weak map would make every later
    // paint fail after the caller handled the one error.
    if (!scope.validated) {
      elementScopes.delete(scope.el);
      forgetScopedElement(scope.el);
      scope.el.removeAttribute("aria-keyshortcuts");
    }
    throw error;
  }
  if (available) scope.validated = true;
  const shortcuts = available
    ? ariaShortcuts(scope.rows, true, scope.title ?? "a scope")
    : "";
  if (shortcuts) {
    if (scope.el.getAttribute("aria-keyshortcuts") !== shortcuts)
      scope.el.setAttribute("aria-keyshortcuts", shortcuts);
  } else scope.el.removeAttribute("aria-keyshortcuts");
}
export const paintKeys = () => {
  pruneScopedElements();
  for (const ref of scopeRefs) {
    const scoped = ref.deref();
    if (scoped?.isConnected) reflectShortcuts(elementScopes.get(scoped));
  }
  paintHere();
};
/** What a scope answers right now, as a listener hears it read out — key names rather than
 * the chips the eye reads, since a screen reader renders "esc" literally. Off the register,
 * so an announcement cannot name a key the rows stopped binding.
 */
export const saying = (rows) =>
  activeRows(rows, "an announced scope")
    .map((row) => `${spoken(row)} ${word(row.line)}`)
    .join(", ");
// A row's own label where it has one, read the way every other surface reads a cell, and
// the bindings where it has none — which is what keeps a listener hearing "Escape" rather
// than the line's "esc". Asking whether the label was written as a string made the same fact
// announce two ways by accident: an option group's digits are spelled "1–3" because its label
// happens to be a string, while the chord's were read out as "1 or 2 or 3" because its label
// counts what the page holds and so has to be a function.
const spoken = (row) => {
  const active = bindings(row);
  if (active.some((binding) => parsed(binding).mods.length))
    return active.map(spokenBinding).join(" or ");
  return word(row.label) ?? active.map(spokenBinding).join(" or ");
};

const deepestFocus = () => {
  let el = document.activeElement;
  while (el?.shadowRoot?.activeElement) el = el.shadowRoot.activeElement;
  return el;
};
const FOCUS = "lf-focus";
const FOCUS_VISIBLE = "lf-focus-visible";
const FOCUS_WITHIN = "lf-focus-within";
// A label's mousedown can blur the already-focused element to body, or a containing
// thread can seat itself, before native activation focuses the control on mouseup. Those
// intermediate targets are not a new keyboard standing. Keep the prior focus as the
// JavaScript reading and project its CSS pseudo-classes while the pointer is inside that
// native transaction. Neither changes DOM focus or prevents pointer default, so a drag can
// still select a label's authored words.
let labelPress = null;
const markLabelPress = (held, pointerId) => {
  held.classList.add(FOCUS);
  const within = [];
  for (let node = held; node; node = upFrom(node)) {
    node.classList.add(FOCUS_WITHIN);
    within.push(node);
  }
  if (held.matches(":focus-visible")) held.classList.add(FOCUS_VISIBLE);
  labelPress = { held, pointerId, within };
};
const finishLabelPress = () => {
  const press = labelPress;
  if (!press) return null;
  labelPress = null;
  press.held.classList.remove(FOCUS);
  press.held.classList.remove(FOCUS_VISIBLE);
  for (const node of press.within) node.classList.remove(FOCUS_WITHIN);
  paintHere();
  return press;
};
document.addEventListener(
  "pointerdown",
  (event) => {
    if (labelPress || !event.isPrimary || event.button !== 0) return;
    const label = event
      .composedPath()
      .find((node) => node?.localName === "label" && node.control);
    if (!label) return;
    const active = deepestFocus();
    if (active && active !== document.body) markLabelPress(active, event.pointerId);
  },
  true,
);
const releaseLabelPress = (event) => {
  if (!labelPress) return;
  if ("pointerId" in event && event.pointerId !== labelPress.pointerId) return;
  finishLabelPress();
};
addEventListener("pointerup", releaseLabelPress, true);
addEventListener("pointercancel", releaseLabelPress, true);
addEventListener("blur", releaseLabelPress);

// A key changes the active input device and ends the pointer's provisional standing. Put
// physical focus back before the bubbling dispatcher and the platform default run. Text
// entry then remains the browser's; a platform activation row needs the event-specific
// target below because the key event itself was aimed at an intermediate focus target.
const recoveredLabelKeys = new WeakMap();
document.addEventListener(
  "keydown",
  (event) => {
    const active = deepestFocus();
    if (!labelPress || event.isComposing || MODIFIER_KEYS.includes(event.key)) return;
    const { held } = finishLabelPress();
    if (active === held) return;
    if (!held.isConnected) return;
    held.focus({ preventScroll: true });
    if (deepestFocus() === held) recoveredLabelKeys.set(event, held);
  },
  true,
);

// Where the reader is standing, which is not always what `document.activeElement`
// answers. Focus inside a shadow tree retargets to the host, while the label transition
// above can report body or a containing element until its click completes. The register
// needs the inner element in both cases so its scope stays the one the reader is leaving
// or working.
export const focused = () => {
  const active = deepestFocus();
  return labelPress?.held.isConnected ? labelPress.held : active;
};
// Document readings want the host of a control staged in a shadow tree. Retarget the
// logical reading every time, so a label transaction and an ordinary shadow focus take
// the same path and no painted surface invents its own exception.
export const documentFocused = () => {
  let held = focused();
  for (let root = held?.getRootNode(); root?.host; root = held.getRootNode())
    held = root.host;
  return held;
};
export const recoveredLabelFocus = (event) => recoveredLabelKeys.get(event);

// The element scopes covering a node, innermost first — the climb crosses a shadow
// boundary the way `closest` climbs inside one, so a widget staging its controls in a
// shadow tree declares them the same way.
export function scopesFor(node) {
  const found = [];
  for (let a = node; a; a = upFrom(a)) {
    const scope = elementScopes.get(a);
    if (scope) found.push(scope);
    if (a.hasAttribute?.("data-lf-thread-surface")) break;
  }
  return found;
}
// Whether the focused control has claimed Escape for itself. Asked of the control's own
// scopes and not of the stack, because both callers mean "this press already has an owner
// where the reader is standing": the chord refuses to arm there, and focus entering one
// disarms it. Every panel and mode in the runtime carries a rung of some kind, so a
// question asked of the whole stack would answer yes almost everywhere and the chord would
// never arm at all.
export const claimsEsc = (node) =>
  scopesFor(node).some((scope) =>
    scope.rows.some((row) => live(row) && bindings(row).includes("Escape")),
  );
