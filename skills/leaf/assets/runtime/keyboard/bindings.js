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
// A row's rendering is made of its own bindings, so it cannot advertise a key it does not
// answer. Three rows existed only to carry a partner key — `u`, `k` and `]`, each
// invisible on both surfaces and reachable only through a sibling's hand-typed spelling —
// and folded into the rows that name them when this replaced those labels.
export const labelOf = (row) => word(row.label) ?? bindings(row).map(spell).join(" / ");
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
    for (const route of commandRoutes(row)) {
      if (!route?.id || typeof route.id !== "string" || !COMMAND_ID.test(route.id))
        throw new Error(
          `leaf: route of ${row.id} names ${String(route?.id)}, which is not a stable command id`,
        );
      if (ids.has(route.id))
        throw new Error(`leaf: ${where} declares ${route.id} twice`);
      ids.add(route.id);
      if (!declaredBindings(row).includes(route.binding))
        throw new Error(
          `leaf: route ${route.id} uses ${String(route.binding)}, which ${row.id} does not bind`,
        );
      if (!route.does)
        throw new Error(`leaf: route ${route.id} has no action sentence`);
    }
    if (row.run && !row.line)
      throw new Error(
        `leaf: row ${i} of ${where} presses with no word for the key line`,
      );
    for (const binding of declaredBindings(row)) {
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

// A clamped walk over a list of focusable rows: the row `dir` steps to from wherever
// focus stands, or the end it is already on. Clamped rather than wrapping, because ↓ on
// the last row must land where it already stands — the press stays the panel's, so the
// list doesn't scroll out from under a walk that reached its end, which is also how t/T
// walks threads. A walk that wraps is a fact about that walk (lf-tabs, per the ARIA tabs
// pattern) and states its own; this is the one two panels share. It hands back the row it
// landed on, for a walk that does more than move — the versions menu states a comparison
// from it, and against the row focus was on, since the clamped press moved nothing.
export const walkRows = (rows, dir) => {
  const row =
    rows[
      Math.max(0, Math.min(rows.length - 1, rows.indexOf(document.activeElement) + dir))
    ];
  row?.focus();
  return row;
};
