/* One reading of every binding and row in the register: how a binding is spelled and
   parsed, what a row's fields mean, and the checks a declaration passes on its way in.

   Binding spelling is canonical: modifiers are ordered `Mod`, `Alt`, `Shift`, and
   single-letter keys are lowercase. A produced punctuation glyph carries no Shift prefix
   because the keyboard layout owns that modifier. Validate that form when a scope enters
   the register and compare canonical identities when checking ownership; modifier order
   and letter case do not make distinct presses in the dispatcher.

   A row has these meanings:

   - `id` is its stable dotted identity. Words and keys may change without changing the
     route the command reference and the other projections use.
   - `keys` is a binding or computed list of bindings: "a", "Escape", "Mod+Enter",
     "Shift+a", "d"; a function where the set is the page's (an option group's 1–N).
   - `routes` are optional stable subcommands when those bindings mean different things.
     The shortcut bar keeps the compact row; the command reference presents each route separately. A
     route may override `title`, `description`, `line` and `label` for the case where a nearer scope shadows only
     its sibling binding. A route without a description of its own lists under the
     row's, so the row's says what every route shares ("Filter visible targets by kind"),
     never what tells them apart ("Next / previous match").
   - `title` is the command's required concise name, or a function when state changes
     it. `description` optionally explains information the title cannot carry. The Ask,
     shortcut bar, reference, and announcements read these same words. `line` overrides
     the bar's word only when it needs a shorter name; false makes a reference-only row.
   - `label` overrides the compact keycap, independently of the action name. A keyless
     command remains named by its title in the reference.
   - `contextKeys` are explicit aliases that work inside the widget and may be forwarded
     to its question and visible representatives. They always follow native editing,
     including on an exact editor scope. A route declares its own aliases when one row
     owns several results. No caller allocates or renumbers another widget's bindings.
   - `control` is the visible element activating the command. `decision: true` marks a
     command that starts, advances, answers, or revises an Ask; the role does not assign
     bindings. `bindingBadge` independently requests an inline hint: an Element lends
     the widget's seat, null requests a corner badge, absence requests none. A route
     inherits its row's seat only when its own field is undefined.
   - `lineWhen` is optional projection-only visibility on the shortcut bar. Unlike `when`, it
     never changes whether the command dispatches or appears in the command reference, and an
     active sequence offers every live row regardless of it.
   - `promoteEscape` says whether an Escape row takes the line's second visible slot. On
     by default; a local action that happens to clear state can leave the slot to the
     next action on that state. A step of the ladder sets the same field for the shared
     Escape row it answers through while it is the innermost one.
   - `when` says whether the capability exists. An owned native button derives its
     disabled state from this reading; a route may declare its own `when` for a sibling
     control. A control's platform or ARIA disabled state also makes its command
     unavailable. When a destination surface is available
     independently of its members, its row stays live and opens the surface even when the
     collection is empty. Member-dependent rows use the collection as their capability.
   - `covering`, on a row of the page's own scope, keeps that command reachable while an
     auxiliary surface covers the document: the surface replaces the page the user is
     reading rather than ending the reading, so travel and the go-to sequence answer
     inside it while the rest of page scope stays under the modal floor.
   - `at`, expressed by the current `userIn` predicate, says whether this press can act
     at the user's current position.
   - `run` performs one result. A run-less row names a press it does not make: the
     platform's own on a link, or one another scope's row already runs.
   - `touch` is the words of the banner control that stands in for a press under a
     finger, or a function when state chooses them, on a page command or a page-scope row
     a finger has no other way to reach (keyboard/AGENTS.md, "Touch routes"). A row with
     `routes` makes a different press per route, so its words go on each route that needs
     a control, and the row's own `touch` can only be `false`. Every page command
     answers it, `false` where a finger reaches the result directly.
   - A command that enters a layer declares no way back out of it. The layer's own
     owner declares that step, against the layer standing rather than against the press
     that opened it, so one state has one way out however the user reached it.
   - `native: true` performs `run` without preventing the platform default. Use it when
     Leaf must change state before the browser completes the same press, not to leave an
     otherwise owned press half-handled. Off by default: a row normally owns the press it
     answers. It still follows the ordinary `repeat` policy; declare `repeat: true` when
     repeated keydowns must also run — off by default, because a held `]` was a page
     navigation per repeat and a held pick a `choose` per repeat, and it applies to native
     rows too, independently of whether their platform default repeats.

   `live` answers the declared liveness once for every projection. Do not repeat a guard
   inside `run` if the guard changes whether the key should be shown. When the command reference
   needs to describe a page capability while the shortcut bar needs to promise an immediate
   press, keep `pageHas` and `userIn` separate.

   `checked` validates declarations when they enter the register. `activeRows` also
   refuses two live meanings for one binding in the same scope; rows may reuse a binding
   only when their `when` predicates make the states exclusive. `parsed` and `answers`
   share the supported modifiers `Mod`, `Alt`, and `Shift`. Unknown modifier names are
   errors rather than bindings that accidentally fire on a bare key. `spell` is the one
   platform-aware display of a binding. `PRESS` states the native key behavior of
   controls, and `DISCLOSE` reads the whole set a disclosure answers off the element it is
   asked about; links retain their platform distinction from buttons.

   A label names this press, not the broad feature. Prefer "Comment on selection" or "Hide
   comments" to "Comment" or "Toggle". Compute the word through `word` when visible state
   chooses the sentence. Request a repaint when any fact used by a word or
   liveness predicate changes.

   A run-less row may still project a native press when that meaning is worth naming in
   help. An explicit control delegates the keyboard route to that platform activation;
   it never reimplements the press.

   `aria-keyshortcuts` is another projection of the register. Element scopes expose their
   currently available rows, including the scope's capability gate. Projected shortcuts
   on native command buttons describe the dispatcher's currently reachable routes,
   including contextual aliases and nearer key reservations. A directly attached element
   scope also names its local keys. `Mod` expands to both Meta and Control because the
   dispatcher accepts both. The attribute cannot express a sequential sequence: spaces
   separate alternatives. An associated `control` in a sequence scope therefore omits
   `aria-keyshortcuts` and exposes the complete route through its title and the keyboard
   command reference. Call `paintKeys` when a state change moves row liveness so this projection
   and the visible surfaces change together. */
import { coarsePointer } from "../pointer.js";

// Which platform's spelling, and which modifier is the sequence's. Up here rather than beside
// the text inputs because the spelling table below is the first thing that needs it.
const MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

// How a key is spelled, in one column. The line said "esc" where the overlay said "Esc"
// for the same binding, and lf-options declared one pair of arrows twice, as "↑ / ↓" and
// "↑ ↓" — which is what a spelling kept per surface costs.
const GLYPH = {
  Enter: "⏎",
  " ": "space",
  Escape: "esc",
  ArrowUp: "↑",
  ArrowDown: "↓",
  ArrowLeft: "←",
  ArrowRight: "→",
  Home: "home",
  End: "end",
  Tab: "⇥",
  // Mod is the platform's own modifier, and the matcher takes either it or Ctrl
  // (below): a chip says ⌘⏎ on a Mac and Ctrl+⏎ answers there too. A key that works
  // beyond what a surface promises is not a surface promising what does not work, which
  // is the rule this layer keeps.
  Mod: MAC ? "⌘" : "Ctrl",
  Shift: MAC ? "⇧" : "Shift",
  Alt: MAC ? "⌥" : "Alt",
};
// The modifiers the matcher implements, which is the whole of what a binding may carry.
// Read off `answers` rather than chosen here, so the list cannot claim more than the
// dispatcher does — a fourth name would have to be taught to both.
const MODIFIERS = ["Mod", "Alt", "Shift"];
// The same modifiers as the platform's own keydowns: what `ev.key` says when a modifier
// goes down alone, ahead of the key it modifies. The dispatcher's sequence asks this to tell
// half a press from a key of its own.
export const MODIFIER_KEYS = ["Shift", "Alt", "Control", "Meta"];
// One reading of a binding's syntax, for the three questions asked of it: how it is
// spelled, whether a press answers it, and whether a text box's letters cover it. Three
// hand-agreed splits is one representation too few — the moment one of them had to state
// the modifier set, the other two were free to disagree about what a modifier is.
export const parsed = (binding) => {
  const mods = binding.split("+");
  return { key: mods.pop(), mods };
};
// A modifier joins its key with nothing between them where its glyph is a symbol and with
// a + where it is a word, so "⌘⏎" and "Ctrl+⏎" are each their own platform's spelling.
// Shift on a letter is the letter's own uppercase, which is how a keyboard draws it and
// how this page's command reference always has: the binding says Shift+a because that is what the
// dispatcher must ask for, and the chip says A because that is what the user presses.
export const spell = (binding) => {
  const { key, mods } = parsed(binding);
  if (mods.length === 1 && mods[0] === "Shift" && /^[a-z]$/.test(key))
    return key.toUpperCase();
  return mods.reduceRight((rest, mod) => {
    const glyph = GLYPH[mod] ?? mod;
    return /^\w/.test(glyph) ? `${glyph}+${rest}` : `${glyph}${rest}`;
  }, GLYPH[key] ?? key);
};
// A soft keyboard has no Shift key with which to make a newline. A coarse pointer
// is the available signal for that surface: leave its Return native, while a
// fine-pointer keyboard can submit with Return and edit with Shift+Return.
const softKeyboard = () => coarsePointer.matches;
export const submitBindings = () =>
  softKeyboard() ? ["Mod+Enter"] : ["Enter", "Mod+Enter"];
export const submitLabel = () => spell(submitBindings()[0]);
// Whether a surface advertises keys: a key drawn where the user has no keyboard names a
// press they cannot make, and costs room on the smallest window there is. The same
// finger reading hides the shortcut bar (chrome.css, `(pointer: coarse)`); every
// runtime surface that paints a key it was not asked for — a field's send key, the
// contextual key that enters it — asks this rather than the pointer. A map the user
// armed from a keyboard (Go-to, the target picker) is an answer, not an advert, and
// draws regardless.
export const advertisesKeys = () => !coarsePointer.matches;
// Speech keeps every declared modifier explicit. A compact keycap may show Shift+t as T,
// which is the keyboard's face, while a listener needs the physical press because many
// speech configurations do not distinguish letter case.
export const spokenBinding = (binding) => {
  const { key, mods } = parsed(binding);
  const spokenModifier = (mod) => {
    if (mod === "Mod") return MAC ? "Command" : "Control";
    return mod;
  };
  const spokenKey = key === " " ? "Space" : key;
  return [...mods.map(spokenModifier), spokenKey].join("+");
};
// A cell is read where it is painted, never where it is written, so it may be a function
// of the page. That is what lets a key whose meaning moves say the meaning it has: the
// surfaces render this press rather than the set of presses the key could be.
export const word = (cell) => (typeof cell === "function" ? cell() : cell);
export const declaredBindings = (row) => word(row.keys) ?? [];
export const contextBindings = (row) => word(row.contextKeys) ?? [];
export const titleOf = (row) => {
  const title = word(row.title);
  if (typeof title !== "string" || !title.trim())
    throw new TypeError(
      `leaf: ${row.id} has no command title; expected non-empty text`,
    );
  return title;
};
export const descriptionOf = (row) => word(row.description) ?? "";
export const lineOf = (row) => word(row.line) ?? titleOf(row);
export const allBindings = (row) => [
  ...new Set([
    ...declaredBindings(row),
    ...contextBindings(row),
    ...commandRoutes(row).flatMap(contextBindings),
  ]),
];
export const commandRoutes = (row) => word(row.routes) ?? [];
export const commandBinding = (row, route = null) =>
  route
    ? (route.binding ?? contextBindings(route)[0])
    : (declaredBindings(row)[0] ?? contextBindings(row)[0]);
// A contextual route may invoke a command declared in another scope. Brand that private
// edge with a Symbol so an unrelated package route field cannot accidentally become an
// executable cross-scope reference. The dispatcher still validates the reference at use.
const ROUTED_COMMAND = Symbol("a routed command reference");
export const contextualRoute = (route, command) => ({
  ...route,
  [ROUTED_COMMAND]: command,
});
export const routedCommand = (route) => route?.[ROUTED_COMMAND] ?? null;
// Bindings are routes to commands, not their identity. A contextual projection may add a
// route without mutating this intrinsic set; dispatch still reads one spelling here.
export const bindings = declaredBindings;
// The command identities under one row. Equivalent bindings keep the row's identity
// and share its implementation; distinct results are routes and expose only those exact
// identities. Dispatch and every command-facing projection consume this split.
export const commandEntries = (
  row,
  active = bindings(row),
  { includeUnavailable = false } = {},
) => {
  const routes = commandRoutes(row);
  if (!routes.length)
    return includeUnavailable || commandAvailable(row)
      ? [{ id: row.id, binding: active[0], route: null }]
      : [];
  return routes
    .filter(
      (route) =>
        (includeUnavailable || commandAvailable(row, route)) &&
        (active.includes(route.binding) ||
          contextBindings(route).some((binding) => active.includes(binding))),
    )
    .map((route) => ({
      id: route.id,
      binding:
        route.binding ??
        active.find((binding) => contextBindings(route).includes(binding)),
      route,
    }));
};
// The command identities a visual presentation gives one row. Rows whose bindings are
// distinct commands expand into routes; a compact row and one deliberately unavailable
// from the command reference keep their own identity. The command reference and shortcut bar both consume this
// projection so route additions cannot reach one surface without the other.
export const commandPresentations = (row, active = bindings(row), options = {}) => {
  if (row.runFromCommandReference === false) return [{ id: row.id, route: null }];
  return commandEntries(row, active, options);
};
// A row's rendering is made of its own bindings, so it cannot advertise a key it does not
// answer. Three rows existed only to carry a partner key — `u`, `k` and `]`, each
// invisible on both surfaces and reachable only through a sibling's hand-typed spelling —
// and folded into the rows that name them when this replaced those labels.
export const labelOf = (row) => {
  const label = word(row.label);
  if (label !== undefined && label !== null) return label;
  return bindings(row).map(spell).join(" / ");
};
// Whether a row is live right now, asked through one predicate by the dispatcher, the line
// and the overlay alike, so no surface can promise a press the dispatcher refuses. A guard
// inside `run` instead is a liveness no surface can see. A declared visible control's
// native or ARIA disabled state is part of that same availability reading.
// Native and contribution painters identify their derived fields here. Availability
// never reads its own previous paint as an input; source ARIA and disabled fieldsets
// remain platform constraints. Each owner removes its claim when handing a node back.
const controlOutputs = new WeakMap();
export function controlAvailabilityOutput(control, owner, fields = null) {
  let outputs = controlOutputs.get(control);
  if (!fields) {
    outputs?.delete(owner);
    return;
  }
  if (!outputs) controlOutputs.set(control, (outputs = new Map()));
  outputs.set(owner, fields);
}
function disabledByFieldset(control) {
  for (let parent = control.parentElement; parent; parent = parent.parentElement) {
    if (parent.localName !== "fieldset" || !parent.disabled) continue;
    const legend = [...parent.children].find((child) => child.localName === "legend");
    if (!legend?.contains(control)) return true;
  }
  return false;
}
export function controlAvailable(control) {
  if (!control?.isConnected) return false;
  const outputs = [...(controlOutputs.get(control)?.values() ?? [])];
  const disabled = outputs.some((fields) => fields.disabled)
    ? disabledByFieldset(control)
    : control.matches(":disabled");
  const ariaDisabled =
    !outputs.some((fields) => fields.ariaDisabled) &&
    control.getAttribute("aria-disabled") === "true";
  return !disabled && !ariaDisabled;
}
export const declaredCommandAvailable = (row, route = null) =>
  (!row.when || row.when()) && (!route?.when || route.when());
export const commandAvailable = (row, route = null) => {
  const control = route?.control ?? row.control;
  const reference = routedCommand(route);
  return (
    declaredCommandAvailable(row, route) &&
    (control === undefined || controlAvailable(word(control))) &&
    (!reference || referencedCommandEntry(reference) !== null)
  );
};
export function referencedCommandEntry(reference) {
  if (
    !reference.source.isConnected ||
    !reference.scope.rows.includes(reference.row) ||
    (reference.scope.when && !reference.scope.when())
  )
    return null;
  return (
    commandEntries(reference.row, allBindings(reference.row)).find(
      ({ id, binding }) =>
        id === reference.id && (binding ?? null) === reference.binding,
    ) ?? null
  );
}
export const live = (row) => {
  const routes = commandRoutes(row);
  return routes.length
    ? routes.some((route) => commandAvailable(row, route))
    : commandAvailable(row);
};
const availableBindings = (row, declared) =>
  declared.filter((binding) => commandEntries(row, [binding]).length > 0);

// The presses a finger needs a control for: the row's one press, or each route of a routed
// row that names its words. `id` is the command the press invokes.
export const touchPresses = (row) =>
  row.routes
    ? commandRoutes(row)
        .filter((route) => route.touch)
        .map((route) => ({
          id: route.id,
          row,
          binding: route.binding,
          words: route.touch,
        }))
    : row.touch
      ? [{ id: row.id, row, binding: undefined, words: row.touch }]
      : [];
// Whether a row has said which of its presses a finger needs: `false` on the row for none,
// or an answer on every route.
export const answersTouch = (row) =>
  row.touch !== undefined ||
  (commandRoutes(row).length > 0 &&
    commandRoutes(row).every((route) => route.touch !== undefined));

// Prose is allowed to change; a command's identity is not. The register uses this name
// to merge repeated widget instances and to route an action chosen in the command reference back
// through the scope that owns it. Dotted, lowercase names keep the namespace visible and
// rule out accidentally using the current sentence as an identifier.
const COMMAND_ID = /^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9-]*)+$/;

// One canonical spelling for one press. Modifier order and the case of an alphabetic key
// do not change what `answers` accepts, so allowing either to vary would let the same press
// enter the register twice under two Map keys. Declarations are required to use this form;
// the identity remains here too so every defensive conflict check compares meanings rather
// than source spelling.
export const canonicalBinding = (binding) => {
  const { key: declaredKey, mods } = parsed(binding);
  // KeyboardEvent names Space with a literal blank. "Space" is ARIA's spelling and a
  // tempting declaration, but `answers` can never match it; turn that known alias into
  // the real key here so the declaration edge can reject it with a useful correction.
  const key = declaredKey === "Space" ? " " : declaredKey;
  const letter = key.length === 1 && key.toLowerCase() !== key.toUpperCase();
  const named = key === " " || key.length > 1;
  const canonicalKey = letter ? key.toLowerCase() : key;
  // Punctuation already names the produced glyph (`?`, not the physical `/` key), and
  // `answers` deliberately leaves its Shift state to the keyboard layout. A Shift prefix
  // on such a glyph is therefore neither portable nor a distinct command.
  const canonicalMods = MODIFIERS.filter(
    (mod) => mods.includes(mod) && (mod !== "Shift" || letter || named),
  );
  return [...canonicalMods, canonicalKey].join("+");
};

function validateActive(active, where, bindingOf) {
  const owners = new Map();
  for (const row of active)
    for (const binding of bindingOf(row)) {
      const identity = canonicalBinding(binding);
      const prior = owners.get(identity);
      if (prior)
        throw new Error(
          `leaf: ${where} has two live meanings for ${binding}: ` +
            `${titleOf(prior)}; ${titleOf(row)}`,
        );
      owners.set(identity, row);
    }
  return active;
}

// A scope's own validation, run when its first paint reads the rows, checks the declared
// vocabulary rather than a projection of it. A projection must not conceal an ambiguous
// register and let it fail only after the projection changes.
export const validateRows = (rows, where = "a scope") => {
  const active = rows.filter(live);
  validateActive(active, where, (row) => availableBindings(row, declaredBindings(row)));
  return validateActive(active, where, (row) =>
    availableBindings(row, [
      ...contextBindings(row),
      ...commandRoutes(row).flatMap(contextBindings),
    ]),
  );
};

// A scope may reuse a key across mutually exclusive states, but never in the scene the
// user is in. Resolve liveness before any surface projects the rows, and refuse an
// ambiguous scene instead of letting declaration order choose a meaning silently.
export function activeRows(rows, where = "a scope") {
  const active = rows.filter((row) => live(row) && bindings(row).length > 0);
  return validateActive(active, where, (row) => availableBindings(row, bindings(row)));
}

// The controls one ordered command set contributes to an Ask. `decision: true` marks
// its answering role; the command's title supplies its name. Ask reads these controls
// for arrival and visibility, while the shared compiler forwards context bindings from
// the original declarations. Routes may name distinct controls when one compact row
// owns a family of parameterized bindings. Each result retains its scoped identity so
// two declarations cannot present different meanings through the same control.
export function decisionControls(commands, where = "an Ask") {
  const controls = new Map();
  for (const { source, scope, row } of commands) {
    const routes = commandRoutes(row);
    const candidates = [
      ...(row.decision ? [{ row, route: null }] : []),
      ...routes.filter((route) => route.decision).map((route) => ({ row, route })),
    ];
    for (const { route } of candidates) {
      const contribution = route ?? row;
      const control = word(contribution.control ?? row.control);
      const label = titleOf(contribution);
      const bindingBadge =
        word(
          contribution.bindingBadge !== undefined
            ? contribution.bindingBadge
            : row.bindingBadge,
        ) ?? null;
      const active = route
        ? [route.binding, ...contextBindings(route)].filter(Boolean)
        : allBindings(row);
      // A semantic command may temporarily have no presented control: a compact
      // margin cluster can give its seat to another contribution, or the owning
      // widget can replace one state with the next. The Ask projects only controls
      // that exist in this reading; a non-Element value is still a malformed
      // declaration and fails at its owner.
      if (control == null) continue;
      if (!(control instanceof Element))
        throw new TypeError(`leaf: ${contribution.id} in ${where} has no control`);
      if (bindingBadge !== null && !(bindingBadge instanceof Element))
        throw new TypeError(
          `leaf: ${contribution.id} in ${where} has no Element binding badge`,
        );
      const binding = active[0] ?? null;
      const record = {
        id: contribution.id,
        source,
        control,
        label,
        bindingBadge,
        intrinsicBindings: active,
        command: Object.freeze({
          id: contribution.id,
          source,
          scope,
          row,
          binding,
          control,
        }),
      };
      const prior = controls.get(control);
      if (prior) {
        if (
          prior.id !== record.id ||
          prior.label !== record.label ||
          prior.bindingBadge !== record.bindingBadge ||
          prior.command.source !== record.command.source ||
          prior.command.scope !== record.command.scope ||
          prior.command.row !== record.command.row
        )
          throw new TypeError(
            `leaf: one control has two Decision commands in ${where}: ` +
              `${prior.id} and ${record.id}`,
          );
        continue;
      }
      controls.set(control, record);
    }
  }
  return [...controls.values()];
}

// The register's machine-readable spelling for assistive technology. `Mod` is the one
// visual key the platform chooses, while the dispatcher deliberately accepts either
// Control or Meta; aria-keyshortcuts therefore states both working sequences. Native Space
// uses the named key ARIA expects rather than a literal blank token.
const ariaBindings = (binding) => {
  const { key, mods } = parsed(binding);
  const variants = mods.includes("Mod") ? ["Meta", "Control"] : [null];
  return variants.map((modKey) =>
    [...mods.map((mod) => (mod === "Mod" ? modKey : mod)), key === " " ? "Space" : key]
      .filter(Boolean)
      .join("+"),
  );
};
export const ariaShortcuts = (rows, current = true, where, includes = () => true) =>
  [
    ...new Set(
      (current ? activeRows(rows, where) : rows).flatMap((row) =>
        bindings(row)
          .filter(
            (binding) =>
              !current ||
              commandEntries(row, [binding]).some((entry) =>
                includes(binding, entry, row),
              ),
          )
          .flatMap(ariaBindings),
      ),
    ),
  ].join(" ");

// Does this press answer this binding? Modifiers are matched exactly, so ⌘D is the
// browser's bookmark rather than a page command, and ⌥ stays the aim sequence's alone.
//
// A letter matches on its lowercase with Shift asked for separately, because caps lock
// writes an uppercase key out of an unshifted press and reads an unshifted one out of a
// shifted press. Read off the glyph, `A` would match the shifted queue walk from a
// bare letter under caps lock, and could no longer be reached with the Shift the chip
// names. Asking
// for the modifier is what makes the chip true in both directions.
export function answers(binding, ev) {
  const { key, mods } = parsed(binding);
  if (mods.includes("Mod") !== (ev.metaKey || ev.ctrlKey)) return false;
  if (mods.includes("Alt") !== ev.altKey) return false;
  const shift = mods.includes("Shift");
  if (key.length === 1 && key.toLowerCase() !== key.toUpperCase())
    return ev.key.toLowerCase() === key.toLowerCase() && ev.shiftKey === shift;
  // A punctuation key is reached with Shift on some layouts and without it on others
  // ("?" is Shift+/ here and a key of its own there), so its Shift is the layout's
  // business rather than the binding's. A named key carries no such ambiguity — no layout
  // hides ArrowLeft behind Shift — so there the modifier is asked for exactly, the way it
  // is on a letter. Shift+→ is how a user extends a selection through the words of a
  // <summary> they are standing on, and the laxity here was closing the section under
  // them and eating the extension.
  return key === " " || key.length > 1
    ? ev.key === key && ev.shiftKey === shift
    : ev.key === key && (!shift || ev.shiftKey);
}

// Validate the declaration's identities, metadata shapes, route coverage, and
// canonical key spelling at registration. Computed titles and live conflicts are
// validated when read, under the owner's current state. A title is mandatory;
// bar wording defaults to it and additional reference detail is optional.
export function checked(rows, where) {
  const ids = new Map();
  const named = (command) => {
    if (typeof command.id !== "string" || !COMMAND_ID.test(command.id))
      throw new Error(
        `leaf: ${where} names ${String(command.id)}, which is not a stable command id`,
      );
    const prior = ids.get(command.id);
    if (
      prior &&
      (!routedCommand(command) || routedCommand(prior) !== routedCommand(command))
    )
      throw new Error(`leaf: ${where} declares ${command.id} twice`);
    ids.set(command.id, command);
    if (!(
      typeof command.title === "function" ||
      (typeof command.title === "string" && command.title.trim())
    ))
      throw new Error(`leaf: ${command.id} has no command title`);
    if (
      command.description !== undefined &&
      typeof command.description !== "string" &&
      typeof command.description !== "function"
    )
      throw new Error(`leaf: ${command.id} has invalid command description`);
    if (command.decision !== undefined && typeof command.decision !== "boolean")
      throw new Error(
        `leaf: ${command.id} has invalid Decision role; expected a boolean`,
      );
  };
  rows.forEach((row, i) => {
    if (!row) throw new TypeError(`${where}: row ${i + 1} is missing`);
    named(row);
    if (row.decision && row.control == null)
      throw new Error(`leaf: ${row.id} is a Decision command with no control`);
    if (row.native && !row.run)
      throw new Error(
        `leaf: row ${i} of ${where} leaves the native press to the platform but runs no result`,
      );
    if (row.touch && (!row.run || row.routes))
      throw new Error(
        `leaf: ${row.id} stands in for its keys under a finger, so it needs a run, and a routed row names its words on each route`,
      );
    const routes = commandRoutes(row);
    if (routes.some((route) => route.touch) && (!row.run || row.touch === false))
      throw new Error(
        `leaf: ${row.id} gives a route a finger's words, so it needs a run and no row-level touch: false`,
      );
    if (routes.length && contextBindings(row).length)
      throw new Error(
        `leaf: ${row.id} owns distinct routes; declare contextKeys on each route`,
      );
    const declared = declaredBindings(row);
    const routed = new Map();
    const contextual = new Map();
    for (const route of routes) {
      named(route);
      if (route.decision && route.control == null && row.control == null)
        throw new Error(
          `leaf: route ${route.id} of ${row.id} is a Decision command with no control`,
        );
      if (!declared.includes(route.binding) && !contextBindings(route).length)
        throw new Error(
          `leaf: route ${route.id} uses ${String(route.binding)}, which ${row.id} does not bind`,
        );
      for (const [bindings, owners] of [
        [[route.binding].filter(Boolean), routed],
        [contextBindings(route), contextual],
      ]) {
        for (const binding of bindings) {
          const prior = owners.get(binding);
          if (prior && prior !== route)
            throw new Error(`leaf: ${row.id} routes ${binding} twice`);
          owners.set(binding, route);
        }
      }
    }
    if (routes.length) {
      const missing = declared.filter((binding) => !routed.has(binding));
      if (missing.length)
        throw new Error(`leaf: ${row.id} has no route for ${missing.join(", ")}`);
    }
    if (row.sequenceControl != null && row.sequenceControl !== true)
      throw new Error(
        `leaf: row ${i} of ${where} has invalid sequence-control presentation ${String(row.sequenceControl)}`,
      );
    for (const binding of allBindings(row)) {
      for (const mod of parsed(binding).mods)
        if (!MODIFIERS.includes(mod))
          throw new Error(
            `leaf: row ${i} of ${where} binds ${binding}, and ${mod} is no modifier this dispatcher answers (${MODIFIERS.join(", ")})`,
          );
      const canonical = canonicalBinding(binding);
      if (binding !== canonical)
        throw new Error(
          `leaf: row ${i} of ${where} binds ${binding}; write the canonical ${canonical.endsWith(" ") ? JSON.stringify(canonical) : canonical}`,
        );
    }
  });
  return rows;
}

// What activates a focused button, stated once because it is the platform's fact and not
// any one row's. Four rows spelled it by hand — the runtime's own control scope, a card
// grip in each of its two states, and the version menu's row — and the fourth spelled it
// short, naming Enter over a real <button> that answers Space too. A near-copy that has to
// change whenever the original does is a primitive not yet extracted, and the drift here
// was invisible: the key worked and the page under-promised it.
//
// A link is the case that keeps this honest. Enter follows an <a> and Space scrolls the
// page, so the leaves drawer binds Enter alone and is right to — the shared fact is what a
// button answers, not what a control does.
export const PRESS = ["Enter", " "];

// The one-dimensional list policy. Every step inside the list clamps; a caller may name
// the row where its own off-list arrival enters. Tabs and spatial grids own their cyclic
// policies instead of passing through this primitive.
export const clampedRow = (
  rows,
  current,
  dir,
  entry = dir > 0 ? 0 : rows.length - 1,
) => {
  if (!rows.length) return undefined;
  const at = rows.indexOf(current);
  const next = at < 0 ? entry : at + dir;
  return rows[Math.max(0, Math.min(rows.length - 1, next))];
};
