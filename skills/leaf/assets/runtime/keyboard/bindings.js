/* One reading of every binding and row in the register: how a binding is spelled and
   parsed, what a row's fields mean, and the checks a declaration passes on its way in.

   Binding spelling is canonical: modifiers are ordered `Mod`, `Alt`, `Shift`, and
   single-letter keys are lowercase. A produced punctuation glyph carries no Shift prefix
   because the keyboard layout owns that modifier. Validate that form when a scope enters
   the register and compare canonical identities when checking ownership; modifier order
   and letter case do not make distinct presses in the dispatcher.

   A row has these meanings:

   - `id` is its stable dotted identity. Words and keys may change without changing the
     route the reference and the other projections use.
   - `keys` is a binding or computed list of bindings: "a", "Escape", "Mod+Enter",
     "Shift+a", "d"; a function where the set is the page's (an option group's 1–N).
   - `routes` are optional stable subcommands when those bindings mean different things.
     The key line keeps the compact row; the reference presents each route separately. A
     route may override `line` and `label` for the case where a nearer scope shadows only
     its sibling binding.
   - `label` optionally overrides the compact keycap in the command's own scope. A keyless
     Decision command falls back to its `decision` action name in the complete reference.
     An Ask instead shows the resolved binding beside that separate action name, so an
     inline hint always says what the reader actually presses.
   - `control` is the visible element that activates the capability. `decision` is a
     non-empty action-name string or a function returning one; it includes that command in
     its containing Ask. The row may carry an existing `address` and has zero or one live
     binding. A keyless decision command receives its contextual number from the Ask
     projection. Routes may carry the same fields when one row describes a parameterized
     family of controls.
   - `does` is the sentence for the press, or a function when the current state changes
     the sentence.
   - `line` is the key line's word: a row carrying one stands on the key line, and a row
     that has a `run` must carry one. That is the failure this register was built for, at
     its smallest — page travel worked, and no always-visible surface named it, because
     the field was optional and its absence read exactly like a decision. A row with no
     `run` may carry one all the same, since a press can be real and immediate without
     being the runtime's: Enter opens the focused leaf because the row is a link. What
     carries no word is reference, named in the "?" overlay and never promised as the
     next press — F7, ⌥ click, a press on a draft's own box.
   - `lineWhen` is optional projection-only visibility on the key line. Unlike `when`, it
     never changes whether the command dispatches or appears in the reference, and an
     active chord shows every live row regardless of it.
   - `promoteEscape` says whether an Escape row takes the line's second visible slot. On
     by default; a local action that happens to clear state can leave the slot to the
     next action on that state.
   - `when` says whether the capability exists. When a destination surface is available
     independently of its members, its row stays live and opens the surface even when the
     collection is empty. Member-dependent rows use the collection as their capability.
   - `at`, expressed by the current `readerIn` predicate, says whether this press can act
     at the reader's current position.
   - `run` performs one result. A run-less row names a press it does not make: the
     platform's own on a link, or one another scope's row already runs.
   - `returnFrame`, when the result enters a temporary layer, returns its `active`,
     `close`, `does`, and `line` contract. The dispatcher captures the origin before
     `run`, validates the descriptor, and pushes it only if the layer is active
     afterwards. Do not call the return stack from a command or restore focus in the
     command's close path; declaring the frame is what makes keyboard invocation and
     reference invocation obey the same stack. A command surface that already displaced
     the reader, such as the modal reference, passes its saved origin into dispatcher
     invocation instead of letting a closing implementation control become the origin.
   - `native: true` performs `run` without preventing the platform default. Use it when
     Leaf must change state before the browser completes the same press, not to leave an
     otherwise owned press half-handled. Off by default: a row normally owns the press it
     answers. It still follows the ordinary `repeat` policy; declare `repeat: true` when
     repeated keydowns must also run — off by default, because a held `]` was a page
     navigation per repeat and a held pick a `choose` per repeat, and it applies to native
     rows too, independently of whether their platform default repeats.

   `live` answers the declared liveness once for every projection. Do not repeat a guard
   inside `run` if the guard changes whether the key should be shown. When the reference
   needs to describe a page capability while the key line needs to promise an immediate
   press, keep `pageHas` and `readerIn` separate.

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
   chooses the sentence. Repaint through `paintHere` when any fact used by a word or
   liveness predicate changes.

   A run-less row may still project a native press when that meaning is worth naming in
   help, but it never reimplements the press.

   `aria-keyshortcuts` is another projection of the register. Element scopes expose their
   currently available rows, including the scope's capability gate, and a row's `control`
   exposes the key that duplicates it. `Mod` expands to both Meta and Control because the
   dispatcher accepts both. The attribute cannot express a sequential chord: spaces
   separate alternatives. An associated `control` in a chord scope therefore omits
   `aria-keyshortcuts` and exposes the complete route through its title and the keyboard
   reference. Call `paintKeys` when a state change moves row liveness so this projection
   and the visible surfaces change together. */
// Which platform's spelling, and which modifier is the chord's. Up here rather than beside
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
  // Mod is the platform's own send modifier, and the matcher takes either it or Ctrl
  // (below): the chip says ⌘⏎ on a Mac and Ctrl+⏎ answers there too. A key that works
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
// goes down alone, ahead of the key it modifies. The dispatcher's chord asks this to tell
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
// how this page's reference always has: the binding says Shift+a because that is what the
// dispatcher must ask for, and the chip says A because that is what the reader presses.
export const spell = (binding) => {
  const { key, mods } = parsed(binding);
  if (mods.length === 1 && mods[0] === "Shift" && /^[a-z]$/.test(key))
    return key.toUpperCase();
  return mods.reduceRight((rest, mod) => {
    const glyph = GLYPH[mod] ?? mod;
    return /^\w/.test(glyph) ? `${glyph}+${rest}` : `${glyph}${rest}`;
  }, GLYPH[key] ?? key);
};
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
// Readers who use speech input or are prone to stray presses must be able to turn off
// character-only shortcuts. Keep that preference inside the binding vocabulary so the
// dispatcher and every projection lose the same keys together. Shift still produces a
// character and does not exempt a shortcut; Mod and Alt make it a modified command.
let characterShortcuts = () => true;
export const configureBindings = ({ characterShortcuts: enabled }) => {
  characterShortcuts = enabled;
};
export const characterBinding = (binding) => {
  const { key, mods } = parsed(binding);
  // Space activates native and offered buttons; it is not the letter/number/punctuation
  // shortcut the preference promises to silence.
  return key !== " " && [...key].length === 1 && mods.every((mod) => mod === "Shift");
};
export const declaredBindings = (row) => word(row.keys) ?? [];
export const commandRoutes = (row) => word(row.routes) ?? [];
export const bindings = (row) =>
  declaredBindings(row).filter(
    (binding) => characterShortcuts() || !characterBinding(binding),
  );
// The command identities under one row. Equivalent bindings keep the row's identity
// and share its implementation; distinct results are routes and expose only those exact
// identities. Dispatch and every command-facing projection consume this split.
export const commandEntries = (row, active = bindings(row)) => {
  const routes = commandRoutes(row);
  if (!routes.length) return [{ id: row.id, binding: active[0], route: null }];
  return routes
    .filter((route) => active.includes(route.binding))
    .map((route) => ({ id: route.id, binding: route.binding, route }));
};
// The command identities a visual presentation gives one row. Rows whose bindings are
// distinct commands expand into routes; a compact row and one deliberately unavailable
// from the reference keep their own identity. The reference and key line both consume this
// projection so route additions cannot reach one surface without the other.
export const commandPresentations = (row, active = bindings(row)) => {
  if (row.runFromReference === false) return [{ id: row.id, route: null }];
  return commandEntries(row, active);
};
// A row's rendering is made of its own bindings, so it cannot advertise a key it does not
// answer. Three rows existed only to carry a partner key — `u`, `k` and `]`, each
// invisible on both surfaces and reachable only through a sibling's hand-typed spelling —
// and folded into the rows that name them when this replaced those labels.
export function decisionName(row, where = "the command register") {
  const value = word(row.decision);
  const name = typeof value === "string" ? value.trim() : "";
  if (!name)
    throw new TypeError(
      `leaf: ${row.id ?? "a command"} in ${where} has no Decision action name`,
    );
  return name;
}
export const labelOf = (row) => {
  const label = word(row.label);
  if (label !== undefined && label !== null) return label;
  const bound = bindings(row).map(spell).join(" / ");
  if (bound || declaredBindings(row).length) return bound;
  return row.decision !== undefined ? decisionName(row) : "";
};
// Whether a row is live right now, asked through one predicate by the dispatcher, the line
// and the overlay alike, so no surface can promise a press the dispatcher refuses. A guard
// inside `run` instead is a liveness no surface can see.
export const live = (row) => !row.when || row.when();

// Prose is allowed to change; a command's identity is not. The register uses this name
// to merge repeated widget instances and to route an action chosen in the reference back
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
            `${word(prior.does)}; ${word(row.does)}`,
        );
      owners.set(identity, row);
    }
  return active;
}

// Declaration-time validation deliberately ignores the reader's character-shortcut
// preference. A saved preference must not let an ambiguous register install successfully
// and then fail halfway through turning the commands back on.
export const validateRows = (rows, where = "a scope") =>
  validateActive(rows.filter(live), where, declaredBindings);

// A scope may reuse a key across mutually exclusive states, but never in the scene the
// reader is in. Resolve liveness before any surface projects the rows, and refuse an
// ambiguous scene instead of letting declaration order choose a meaning silently.
export function activeRows(rows, where = "a scope") {
  const active = rows.filter((row) => live(row) && bindings(row).length > 0);
  return validateActive(active, where, bindings);
}

// The controls one ordered command set contributes to an Ask. `decision` names the
// command's action in that Ask; it is not another command registry. The dispatcher, key
// line, reference and Ask projection all read the same row. Routes may name distinct
// controls when one compact row owns a family of parameterized bindings (numbered
// options). A command with no binding receives its contextual number from the Ask
// projection.
export function decisionControls(commands, where = "an Ask") {
  const controls = new Map();
  for (const { source, row } of commands) {
    const routes = commandRoutes(row);
    const candidates = [
      ...(row.decision !== undefined ? [{ row, route: null }] : []),
      ...routes
        .filter((route) => route.decision !== undefined)
        .map((route) => ({ row, route })),
    ];
    for (const { route } of candidates) {
      const contribution = route ?? row;
      const control = word(contribution.control ?? row.control);
      const label = decisionName(contribution, where);
      const address = word(contribution.address ?? row.address) ?? null;
      const active = route ? [route.binding] : bindings(row);
      if (!(control instanceof Element))
        throw new TypeError(`leaf: ${contribution.id} in ${where} has no control`);
      if (address !== null && !(address instanceof Element))
        throw new TypeError(
          `leaf: ${contribution.id} in ${where} has no Element address`,
        );
      if (active.length > 1)
        throw new TypeError(
          `leaf: ${contribution.id} in ${where} has ${active.length} live bindings; ` +
            "an Ask control needs zero or one",
        );
      const record = {
        id: contribution.id,
        source,
        control,
        label,
        binding: active[0] ?? null,
        address,
      };
      const prior = controls.get(control);
      if (prior) {
        if (
          prior.id !== record.id ||
          prior.label !== record.label ||
          prior.binding !== record.binding ||
          prior.address !== record.address
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
// Control or Meta; aria-keyshortcuts therefore states both working chords. Native Space
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
export const ariaShortcuts = (rows, current = true, where) =>
  [
    ...new Set(
      (current ? activeRows(rows, where) : rows).flatMap((row) =>
        bindings(row).flatMap(ariaBindings),
      ),
    ),
  ].join(" ");

// Does this press answer this binding? Modifiers are matched exactly, so ⌘D is the
// browser's bookmark rather than a page command, and ⌥ stays the aim chord's alone.
//
// A letter matches on its lowercase with Shift asked for separately, because caps lock
// writes an uppercase key out of an unshifted press and reads an unshifted one out of a
// shifted press. Read off the glyph, `D` would match the shifted decision walk from a
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
  // is on a letter. Shift+→ is how a reader extends a selection through the words of a
  // <summary> they are standing on, and the laxity here was closing the section under
  // them and eating the extension.
  return key === " " || key.length > 1
    ? ev.key === key && ev.shiftKey === shift
    : ev.key === key && (!shift || ev.shiftKey);
}

// Checked where a scope is declared, which is the edge this data enters at: a row that
// presses must carry the word the line says over it. This is the whole failure the
// register was built for, wearing its smallest form — a page step existed for as
// long as the runtime has had them and no always-visible surface ever named them, because
// the word was an optional field and its absence read exactly like a decision. So the
// absence is refused rather than defaulted: falling back to the reference's sentence would
// have kept the row visible and spent the room of the four behind it, and there is nothing
// to compute a short word from. A row with no `run` is asked for none, since the press it
// names is not the runtime's — it either belongs to the platform, and says a word anyway
// because Enter really does open the focused leaf, or it is not a key at all.
// The other way a declaration can promise a press nothing will make, and the quieter one.
// `answers` asks after the three modifiers by name and treats every other prefix as absent,
// so a binding written `Ctrl+k` or `Cmd+Enter` is not a key that never fires — it is a
// different key that does. `Ctrl+k` spells itself "Ctrl+k" on both surfaces, matches a bare
// `k`, and refuses the press the chip is naming. A key on screen is a key that works, and
// nothing was reading the half of a binding that decides which key it is.
export function checked(rows, where) {
  const ids = new Set();
  rows.forEach((row, i) => {
    if (
      row.decision !== undefined &&
      !(
        (typeof row.decision === "string" && row.decision.trim()) ||
        typeof row.decision === "function"
      )
    )
      throw new Error(
        `leaf: ${row.id ?? `row ${i} of ${where}`} has invalid Decision action name ` +
          `${String(row.decision)}; expected a non-empty string or function returning one`,
      );
    if (row.decision !== undefined && row.control == null)
      throw new Error(
        `leaf: ${row.id ?? `row ${i} of ${where}`} is a Decision command with no control`,
      );
    if (row.returnFrame !== undefined && typeof row.returnFrame !== "function")
      throw new Error(
        `leaf: ${row.id ?? `row ${i} of ${where}`} has a returnFrame that is not a function`,
      );
    if (row.returnFrame && !row.run)
      throw new Error(
        `leaf: ${row.id ?? `row ${i} of ${where}`} declares a return frame but runs no entry`,
      );
    if (row.native && !row.run)
      throw new Error(
        `leaf: row ${i} of ${where} leaves the native press to the platform but runs no result`,
      );
    if (!row.id) throw new Error(`leaf: row ${i} of ${where} has no stable command id`);
    if (typeof row.id !== "string" || !COMMAND_ID.test(row.id))
      throw new Error(
        `leaf: row ${i} of ${where} names ${String(row.id)}, which is not a stable command id`,
      );
    if (ids.has(row.id)) throw new Error(`leaf: ${where} declares ${row.id} twice`);
    ids.add(row.id);
    const declared = declaredBindings(row);
    const routes = commandRoutes(row);
    const routed = new Set();
    for (const route of routes) {
      if (
        route.decision !== undefined &&
        !(
          (typeof route.decision === "string" && route.decision.trim()) ||
          typeof route.decision === "function"
        )
      )
        throw new Error(
          `leaf: route ${route.id ?? "without an id"} of ${row.id} has invalid Decision ` +
            `action name ${String(route.decision)}; expected a non-empty string or function returning one`,
        );
      if (route.decision !== undefined && route.control == null && row.control == null)
        throw new Error(
          `leaf: route ${route.id ?? "without an id"} of ${row.id} is a Decision command with no control`,
        );
      if (!route?.id || typeof route.id !== "string" || !COMMAND_ID.test(route.id))
        throw new Error(
          `leaf: route of ${row.id} names ${String(route?.id)}, which is not a stable command id`,
        );
      if (ids.has(route.id))
        throw new Error(`leaf: ${where} declares ${route.id} twice`);
      ids.add(route.id);
      if (!declared.includes(route.binding))
        throw new Error(
          `leaf: route ${route.id} uses ${String(route.binding)}, which ${row.id} does not bind`,
        );
      if (routed.has(route.binding))
        throw new Error(`leaf: ${row.id} routes ${route.binding} twice`);
      routed.add(route.binding);
      if (!route.does)
        throw new Error(`leaf: route ${route.id} has no action sentence`);
    }
    if (routes.length) {
      const missing = declared.filter((binding) => !routed.has(binding));
      if (missing.length)
        throw new Error(`leaf: ${row.id} has no route for ${missing.join(", ")}`);
    }
    if (row.run && !row.line)
      throw new Error(
        `leaf: row ${i} of ${where} presses with no word for the key line`,
      );
    if (row.chordControl != null && row.chordControl !== true)
      throw new Error(
        `leaf: row ${i} of ${where} has invalid chord-control presentation ${String(row.chordControl)}`,
      );
    for (const binding of declared) {
      for (const mod of parsed(binding).mods)
        if (!MODIFIERS.includes(mod))
          throw new Error(
            `leaf: row ${i} of ${where} binds ${binding}, and ${mod} is no modifier ` +
              `this dispatcher answers (${MODIFIERS.join(", ")})`,
          );
      const canonical = canonicalBinding(binding);
      if (binding !== canonical)
        throw new Error(
          `leaf: row ${i} of ${where} binds ${binding}; write the canonical ${
            canonical.endsWith(" ") ? JSON.stringify(canonical) : canonical
          }`,
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
// page, so the leaves tray binds Enter alone and is right to — the shared fact is what a
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

// Focus the clamped row and return it for list walks that also project something from the
// landing, such as the version comparison.
export const walkRows = (rows, dir) => {
  const row = clampedRow(rows, document.activeElement, dir, 0);
  row?.focus();
  return row;
};
