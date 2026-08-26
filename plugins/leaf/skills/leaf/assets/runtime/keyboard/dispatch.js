import { MODIFIER_KEYS, answers, bindings, live } from "./bindings.js";

export function createDispatch({
  claimsEsc,
  containsAcross,
  ELEMENTS,
  focused,
  isChordArmed,
  isReactArmed,
  keepShown,
  paintHere,
  panel,
  SCOPES,
  scopesFor,
  setChord,
  setReact,
  takesLetters,
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
  // asks fold and then every link on the page, once per keydown, from the first keystroke of
  // the first comment.
  const standing = (scope) => readerIn(scope) && pageHas(scope);
  // Every scope the reader is standing in, innermost first. The whole list: what a nearer
  // scope takes out of reach is the walk's own business, and both walkers say it the same
  // way — a binding some nearer row has already named, or one a nearer scope claims. Cutting
  // the list here instead was the same statement made where only one of the two shadowings
  // could be seen.
  function stack() {
    return SCOPES.flatMap((scope) =>
      scope === ELEMENTS ? scopesFor(focused()) : scope,
    ).filter(standing);
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
    // nothing: g j is a thread step and g g re-arms. A letter naming no list disarms the same
    // way, and so does a digit past the end of the list a letter named. Spelled as walking
    // again rather than as a rule, so the meaning a key keeps is the meaning the register
    // gives it. A modifier alone is half a press rather than a key: the Shift that
    // capitalizes G arrives as a keydown of its own ahead of it, and disarming on that
    // took the window down before the G it was armed for.
    if ((isChordArmed() || isReactArmed()) && !MODIFIER_KEYS.includes(ev.key)) {
      setChord(false);
      setReact(false);
      run(ev);
    }
  });
  function run(ev) {
    const nearer = shadow();
    for (const scope of stack()) {
      for (const row of scope.rows) {
        // The key first, then the claim, then the liveness: a `when` may be the whole event
        // log folded (`a` asks what the page is still waiting on), and asking it of every row
        // the press is not for makes the cost of a keystroke the size of the table rather
        // than the size of the match. A row that matches and is dead still falls through to
        // the scope behind it, which is what `continue` says either way round.
        if (!row.run) continue;
        const binding = bindings(row).find((b) => answers(b, ev));
        if (!binding || nearer.takes(binding) || !live(row)) continue;
        // A held key repeats keydown where a real button fires once, so a row says whether
        // it repeats: a held `]` was a page navigation per repeat and a held pick a `choose`
        // per repeat, where a walk wants the repeat and is the reason the flag exists. The
        // repeat is still consumed — Space is a page scroll if it isn't, so holding it on a
        // control would send the page out from under the press the first one made.
        ev.preventDefault();
        if (ev.repeat && !row.repeat) return true;
        row.run(binding);
        return true;
      }
      nearer.past(scope);
    }
    return false;
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
    if (isReactArmed() && (takesLetters(active) || claimsEsc(active))) setReact(false);
    if (isChordArmed() && (takesLetters(active) || claimsEsc(active))) {
      // Focus arriving inside what the aim revealed is the reader landing in it, the same
      // arrival the digit makes, so the reveal is theirs to keep rather than the aim's to
      // take down. Without this a click into the panel `g c` had just opened closed it again
      // under the click.
      if (containsAcross(panel, active)) keepShown();
      setChord(false);
    }
    paintHere();
  });
  document.addEventListener("focusout", () => paintHere());

  return { readerIn, shadow, stack };
}
