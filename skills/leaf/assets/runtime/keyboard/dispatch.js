import {
  MODIFIER_KEYS,
  answers,
  bindings,
  commandRoutes,
  live,
  word,
} from "./bindings.js";

export function createDispatch({
  beforeCommand,
  claimsEsc,
  ELEMENTS,
  focused,
  isChordArmed,
  paintHere,
  REACT,
  recoveredLabelFocus,
  RETURN,
  returnStack,
  SCOPES,
  scopesFor,
  setChord,
  setReact,
  takesLetters,
  TYPING,
}) {
  // The two questions a scope answers, named apart because the surfaces ask them apart: the
  // reference lists a scope the page *has* and filters its rows by liveness only where the reader
  // is standing in it, while the dispatcher and the line want both at once. Spelled `!x || x()`
  // in three places before, which is a rule written three times and named nowhere.
  const pageHas = (scope) => !scope.when || scope.when();
  const readerIn = (scope) => !scope.at || scope.at();
  // Where the reader is first, and what the page has second: both are pure and the and is
  // the same either way round, but `at` is a class check and a `when` may be the whole event
  // log folded — so the walk asks the cheap question of every scope and the dear one only of
  // the scopes it is already standing in. That is the rule the dispatcher's row loop already
  // keeps and the control scope's own comment already claims ("`at` is asked first and answers
  // false wherever this could be in doubt, so a paint never reaches it"), and the scope walk
  // was the one place it was not true. The chord is what made it bite: its `when` reaches the
  // decisions fold and then every link on the page, once per keydown, from the first keystroke of
  // the first comment.
  const standing = (scope) => readerIn(scope) && pageHas(scope);
  // Every scope the reader is standing in, innermost first. The whole list: what a nearer
  // scope takes out of reach is the walk's own business, and both walkers say it the same
  // way — a binding some nearer row has already named, or one a nearer scope claims. Cutting
  // the list here instead was the same statement made where only one of the two shadowings
  // could be seen.
  function stack() {
    const active = focused();
    const elementStack = scopesFor(active);
    const typing = takesLetters(active);
    return SCOPES.flatMap((scope) => {
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
      // RETURN is declared in SCOPES so every projection sees it. The element placeholder
      // above has already placed it at the dynamic boundary between the exact control and
      // the generic/ancestor scopes, so the static slot contributes no second copy.
      if (scope === RETURN) return [];
      if (scope === TYPING && typing) return [];
      return scope;
    }).filter(standing);
  }
  // The claims of every scope nearer the reader than this one, accumulated as either walk
  // steps outward. A scope's own claim is pushed after its rows, because what it takes from
  // the page it does not take from itself.
  const shadow = () => {
    const claims = [];
    return {
      takes: (binding) => claims.some((c) => c(binding)),
      past: (scope) => {
        if (scope.claims) claims.push(scope.claims);
      },
    };
  };

  // ---------- the dispatcher ----------
  // One listener. Scoping is still the DOM's — an element scope holds while focus is inside
  // it — but the walk is the stack's rather than the bubble's, so which scope wins is a
  // statement here instead of an ordering between nine listeners. `isComposing` is the one
  // guard that stays an event's rather than a scope's: an IME's own Escape is not the
  // runtime's to take.
  document.addEventListener("keydown", (ev) => {
    if (ev.isComposing) return;
    if (run(ev)) return;
    // Any other key disarms the chord and keeps its ordinary meaning, so a mistyped g costs
    // nothing: g T is a panel trip and g g re-arms. A letter naming no list disarms the same
    // way, and so does a digit past the end of the list a letter named. Spelled as walking
    // again rather than as a rule, so the meaning a key keeps is the meaning the register
    // gives it. A modifier alone is half a press rather than a key: the Shift that
    // capitalizes G arrives as a keydown of its own ahead of it, and disarming on that
    // took the window down before the G it was armed for.
    if ((isChordArmed() || standing(REACT)) && !MODIFIER_KEYS.includes(ev.key)) {
      setChord(false);
      setReact(false);
      run(ev);
    }
  });
  function run(ev) {
    const recovered = recoveredLabelFocus(ev);
    const nearer = shadow();
    for (const scope of stack()) {
      let matched = null;
      for (const row of scope.rows) {
        // The key first, then the claim, then the liveness: a `when` may be the whole event
        // log folded (`a` asks what the page is still waiting on), and asking it of every row
        // the press is not for makes the cost of a keystroke the size of the table rather
        // than the size of the match. A row that matches and is dead still falls through to
        // the scope behind it, which is what `continue` says either way round.
        if (!row.run && !recovered) continue;
        const binding = bindings(row).find((b) => answers(b, ev));
        if (!binding || nearer.takes(binding) || !live(row)) continue;
        if (matched)
          throw new Error(
            `leaf: ${scope.title ?? "a scope"} has two live meanings for ${binding}: ` +
              `${word(matched.row.does)}; ${word(row.does)}`,
          );
        matched = { row, binding };
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
        if (!matched.row.native) ev.preventDefault();
        if (ev.repeat && !matched.row.repeat) return true;
        beforeCommand?.(matched.row);
        returnStack.invoke(matched.row, matched.binding, () => {
          if (matched.row.run) return matched.row.run(matched.binding);
          return recovered.click();
        });
        return true;
      }
      nearer.past(scope);
    }
    return false;
  }

  // An action chosen from the reference has no keydown to match, but it still belongs to
  // exactly one live scope. Resolve it through the same innermost-first stack and the same
  // shadowing as a key press. The stable id is the route, while the first declared binding
  // supplies the argument used by rows whose equivalent keys share one implementation
  // (Enter/Space).
  function commandFor(id) {
    const nearer = shadow();
    for (const scope of stack()) {
      const row = scope.rows.find((candidate) => {
        const ids = [
          candidate.id,
          ...commandRoutes(candidate).map((route) => route.id),
        ];
        return ids.includes(id) && candidate.run && live(candidate);
      });
      if (row) {
        const route = commandRoutes(row).find((candidate) => candidate.id === id);
        const active = bindings(row);
        const binding = route?.binding ?? active[0];
        if (
          binding != null &&
          (!route || active.includes(binding)) &&
          !nearer.takes(binding)
        )
          return { row, binding };
      }
      nearer.past(scope);
    }
    return null;
  }
  // Snapshot every executable route while focus is still on the page. The reference is a
  // modal scope and correctly shadows the page once it opens; asking after that point would
  // make every page command look unavailable merely because the chooser itself is standing.
  function availableCommands() {
    const available = new Set();
    const nearer = shadow();
    for (const scope of stack()) {
      for (const row of scope.rows) {
        if (!row.run || !live(row)) continue;
        const active = bindings(row);
        const first = active[0];
        const routes = [
          { id: row.id, binding: first },
          ...commandRoutes(row).filter((route) => active.includes(route.binding)),
        ];
        for (const route of routes)
          if (route.binding != null && !nearer.takes(route.binding))
            available.add(route.id);
      }
      nearer.past(scope);
    }
    return available;
  }
  function executeCommand(id, origin = null) {
    const command = commandFor(id);
    if (!command) return false;
    beforeCommand?.(command.row);
    returnStack.invoke(
      command.row,
      command.binding,
      () => command.row.run(command.binding),
      origin,
    );
    return true;
  }

  // A focus move is the one change in where the reader is standing that no state writer
  // sees, so it asks for the paint itself — the ring and the line both, which is why one
  // call answers for it. Focus entering a box, or a control that claims Escape, also disarms
  // the chord — a digit typed in a box is text, and a chip left blooming would promise a
  // cancel the control would consume.
  document.addEventListener("focusin", () => {
    // The same question `setChord` asks before arming, so it takes the same answer: two
    // readings of where the reader is standing would refuse to arm somewhere they then
    // failed to disarm.
    const active = focused();
    if (standing(REACT) && (takesLetters(active) || claimsEsc(active))) setReact(false);
    if (isChordArmed() && (takesLetters(active) || claimsEsc(active))) {
      setChord(false);
    }
    paintHere();
  });
  document.addEventListener("focusout", () => paintHere());

  return { availableCommands, executeCommand, readerIn, shadow, stack };
}
