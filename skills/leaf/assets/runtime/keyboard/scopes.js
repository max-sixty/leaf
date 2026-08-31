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

let publishedScopes;
export const focused = (...args) => publishedScopes.focused(...args);
export const keys = (...args) => publishedScopes.keys(...args);
export const paintKeys = (...args) => publishedScopes.paintKeys(...args);
export const saying = (...args) => publishedScopes.saying(...args);

export function createScopes({ paintHere, upFrom }) {
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
  const elementScopes = new WeakMap();
  // The weak map is the dispatcher's lookup. The reference also has to enumerate every
  // connected contributor, so keep weak references beside it. A live-version replacement
  // can then be collected, while an element temporarily moved out of the document keeps
  // its declaration when it reconnects. Holding the elements or merged closures here
  // retained an entire prior version.
  const scopeRefs = new Set();
  const scopeRefFor = new WeakMap();
  const pruneScopedElements = () => {
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
  const byCommand = (rows) => rows.map((row) => [row.id, row]);
  // One section per title, gathered from every contributor. Written once because the gathering
  // happens twice and used to be spelled three times: here at declaration, where a widget's
  // contributors arrive an upgraded element at a time, and at each open of the reference, where
  // core's scopes and the widgets' are gathered into one list of sections. The rules above are
  // this function — rows keyed by command id, `when` and `at` joined by or — and a near-copy of a
  // merge is a merge that drifts on the day one of the three learns something.
  function merge(sections, { title, when, at, claims, rows }) {
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
   * (null for one the reference has no room to name), `rows` are its bindings, and `when` is
   * whether the page has this scope at all.
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
   * Returns the rows, so a widget that says its own keys out loud — a grip announcing what a
   * grabbed card answers — reads them back off the declaration rather than restating them.
   */
  function keys(where, title, rows, when) {
    const scope = {
      title,
      el: where,
      rows: checked(rows, title ?? "a scope"),
      when,
    };
    // Validate before publishing to either index. A rejected declaration must not leave a
    // bad scope installed where every later paint fails on it. A capability-gated scope may
    // depend on state its owner is still initializing, so its first paint remains the gate;
    // an immediately readable scope can be checked in full now.
    if (!scope.when) validateRows(scope.rows, title ?? "a scope");
    scope.validated = !scope.when;
    const shortcuts = !scope.when
      ? ariaShortcuts(scope.rows, true, scope.title ?? "a scope")
      : "";
    elementScopes.set(where, scope);
    rememberScopedElement(where);
    // A scope capability may read state whose owner has not finished initializing while
    // modules are still registering. State renderers call paintKeys once that boundary is
    // complete; scopes with no capability gate are safe to expose immediately.
    if (shortcuts) where.setAttribute("aria-keyshortcuts", shortcuts);
    else where.removeAttribute("aria-keyshortcuts");
    paintHere();
    return rows;
  }
  function reflectShortcuts(scope) {
    const available = !scope.when || scope.when();
    try {
      if (available) validateRows(scope.rows, scope.title ?? "a scope");
    } catch (error) {
      // Capability-gated scopes may only become readable after registration. If that first
      // validation fails, retract the unpublished contract completely; leaving it in the
      // weak map would make every later paint fail after the caller handled the one error.
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
  const paintKeys = () => {
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
  const saying = (rows) =>
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
  const focused = () => {
    const active = deepestFocus();
    return labelPress?.held.isConnected ? labelPress.held : active;
  };
  // Document readings want the host of a control staged in a shadow tree. Retarget the
  // logical reading every time, so a label transaction and an ordinary shadow focus take
  // the same path and no painted surface invents its own exception.
  const documentFocused = () => {
    let held = focused();
    for (let root = held?.getRootNode(); root?.host; root = held.getRootNode())
      held = root.host;
    return held;
  };
  const recoveredLabelFocus = (event) => recoveredLabelKeys.get(event);

  // The element scopes covering a node, innermost first — the climb crosses a shadow
  // boundary the way `closest` climbs inside one, so a widget staging its controls in a
  // shadow tree declares them the same way.
  function scopesFor(node) {
    const found = [];
    for (let a = node; a; a = upFrom(a)) {
      const scope = elementScopes.get(a);
      if (scope) found.push(scope);
    }
    return found;
  }
  // Whether the focused control has claimed Escape for itself. Asked of the control's own
  // scopes and not of the stack, because both callers mean "this press already has an owner
  // where the reader is standing": the chord refuses to arm there, and focus entering one
  // disarms it. Every panel and mode in the runtime carries a rung of some kind, so a
  // question asked of the whole stack would answer yes almost everywhere and the chord would
  // never arm at all.
  const claimsEsc = (node) =>
    scopesFor(node).some((scope) =>
      scope.rows.some((row) => live(row) && bindings(row).includes("Escape")),
    );

  const scopes = {
    byCommand,
    claimsEsc,
    documentFocused,
    elementScopes,
    focused,
    keys,
    merge,
    paintKeys,
    pruneScopedElements,
    recoveredLabelFocus,
    saying,
    scopeRefs,
    scopesFor,
  };
  publishedScopes = scopes;
  return scopes;
}
