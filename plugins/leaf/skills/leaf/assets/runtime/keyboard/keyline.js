import { bindings, labelOf, live, word } from "./bindings.js";

export function createKeyline({
  el,
  keylineEl,
  keylineMore,
  paintHere,
  reference,
  shadow,
  stack,
}) {
  // ---------- the key line ----------
  // What the next press does, walked outward from where the reader stands. The full register
  // has grown past what a glance can read, so this surface keeps two hints and leaves the rest
  // one press or click away. Locality supplies the ranking: the same innermost-first scope
  // order the dispatcher uses. The one override is an available Escape after the first hint,
  // because a mode whose way in is visible and whose way out is not is a trap.
  //
  // The rows the line shows, innermost scope first: the ones carrying a word for it. A row
  // is skipped where any of its bindings has been named already, so an inner scope's own
  // word for a press wins and the generic one behind it stays quiet — the case that names
  // this is `g c` aimed over an option's pick mark, where the chord's "1–3 comments" and the
  // mark's "1–5 toggle the nth" would otherwise stand side by side, two promises for one
  // press.
  function lineRows(scopes) {
    const named = new Set();
    const nearer = shadow();
    const rows = [];
    for (const scope of scopes) {
      for (const row of scope.rows) {
        // Shadowing before liveness, for the reason the dispatcher matches the key first:
        // under the reference every page row is claimed away, and asking each one what the
        // page is waiting on to then say nothing about it is the table's cost per paint. A
        // dead row names nothing, so it shadows nothing either.
        if (!row.line) continue;
        const bound = bindings(row);
        if (bound.some((k) => named.has(k) || nearer.takes(k))) continue;
        if (!live(row)) continue;
        for (const k of bound) named.add(k);
        rows.push(row);
      }
      nearer.past(scope);
    }
    return rows;
  }
  function renderLine() {
    // One walk, read twice: `at` and `when` are the page's own state and a second walk would
    // ask every one of them again for the same frame.
    const scopes = stack();
    const rows = lineRows(scopes);
    // `?` has its own permanent More control, so its ordinary row remains in the DOM only as
    // the register's hidden projection. Keeping every live row there preserves one inspectable
    // reading of the current key scene while only the two selected rows paint.
    const ref = rows.findIndex((row) => bindings(row).includes("?"));
    const ordered =
      ref === -1 ? rows : [...rows.slice(0, ref), ...rows.slice(ref + 1), rows[ref]];
    const candidates = ordered.filter((row) => !bindings(row).includes("?"));
    const first = candidates[0];
    const wayOut = candidates.slice(1).find((row) => bindings(row).includes("Escape"));
    const short = new Set([first, wayOut ?? candidates[1]].filter(Boolean));
    // Read where it is painted, like every other cell: the chord's chip says which stage the
    // reader is at (`g`, then `g c`), and a string fixed at declaration could only say one.
    const chord = word(scopes.find((s) => s.chord)?.chord);
    // Everything but More, which the reader may be standing on. `textContent = ""` takes
    // it out of the document, and removing a focused element blurs it: it returns on the
    // same line as the same node, connected again, with the reader dropped to `body`. That
    // lands one frame after they tabbed to it, because this runs under paintHere's frame —
    // so the walk is whole at synthetic speed and broken at every human one, which is the
    // way round that hides from a suite. The line is cleared around it instead, and the
    // chips are drawn in front of it.
    for (const node of [...keylineEl.childNodes])
      if (node !== keylineMore) node.remove();
    const seated = keylineMore.parentElement === keylineEl;
    const chip = (key, said, armed) => {
      const span = el("span", "lf-key");
      span.setAttribute("aria-hidden", "true");
      const kbd = document.createElement("kbd");
      if (armed) kbd.className = "armed";
      kbd.textContent = key;
      span.append(kbd);
      if (said) span.append(el("span", "", said));
      keylineEl.insertBefore(span, seated ? keylineMore : null);
      return span;
    };
    if (chord) chip(chord, "", true);
    const drawn = ordered.map((row) => {
      const span = chip(labelOf(row), word(row.line));
      span.hidden = !short.has(row);
      return span;
    });
    // The door is not useful behind the room it opens. While the reference stands, its
    // own Escape row is the short line and More leaves the focus order with the page. This
    // is the one removal that is meant: a reader standing on the door when the room opens
    // is a state change rather than a repaint, and the help takes the focus anyway.
    if (reference.open) keylineMore.remove();
    else if (!seated) keylineEl.append(keylineMore);

    // Two is a ceiling, not permission to clip them. On a window narrower than those two
    // computed sentences, yield the lower-ranked hint and then the first; More is the one
    // control that always survives. At most two layouts are spent, independent of the size
    // of the register, while all hidden rows stay available to inspection and the reference.
    for (const span of drawn.filter((item) => !item.hidden).toReversed()) {
      if (keylineEl.scrollWidth <= keylineEl.clientWidth) break;
      span.hidden = true;
    }
  }
  paintHere();
  // The room is the window's, so the window changing is a scope change like any other. It
  // was the one edge no writer reported: a reader who narrowed their window kept the wide
  // selection until they next moved focus, and the CSS clip did the cutting instead.
  addEventListener("resize", paintHere);

  return { renderLine };
}
