import { activeRows, bindings, labelOf, word } from "./bindings.js";

export function createKeyline({
  announce,
  backRow,
  el,
  keylineEl,
  keylineMore,
  paintHere,
  reference,
  referenceRow,
  shadow,
  stack,
}) {
  // ---------- the key line ----------
  // What the next press does, walked outward from where the reader stands. The full register
  // has grown past what a glance can read, so this surface starts with two hints and unfolds
  // the current scene before opening the complete reference. Locality supplies the ranking:
  // the same innermost-first scope order the dispatcher uses. The default override is an
  // available Escape after the first hint, because a mode whose way in is visible and whose
  // way out is not is a trap. An Escape row may waive that promotion while remaining live
  // and present in the full reference.
  //
  // The rows the line shows, innermost scope first: the ones carrying a word for it. A row
  // is skipped where any of its bindings has been named already, so an inner scope's own
  // word for a press wins and the generic one behind it stays quiet — for example, a
  // numbered hyperlink address over an option's pick mark must not sit beside the mark's
  // own "1–5 toggle the nth" promise for the same digit.
  function lineRows(scopes) {
    const named = new Set();
    const nearer = shadow();
    const rows = [];
    for (const scope of scopes) {
      // Shadowing before liveness, for the reason the dispatcher matches the key first:
      // under the reference every page row is claimed away, and asking each one what the
      // page is waiting on to then say nothing about it is the table's cost per paint. A
      // dead row names nothing, so it shadows nothing either. Keep all unshadowed rows in
      // the batch so activeRows still rejects two live meanings inside this reachable scope.
      const reachable = scope.rows.filter((row) => {
        if (!row.line || word(row.lineWhen) === false) return false;
        const bound = bindings(row);
        return !bound.some((k) => named.has(k) || nearer.takes(k));
      });
      for (const row of activeRows(reachable, scope.title ?? "the page's keys")) {
        const bound = bindings(row);
        for (const k of bound) named.add(k);
        rows.push(row);
      }
      nearer.past(scope);
    }
    return rows;
  }
  let expanded = false;
  const shortcutAvailable = () => bindings(referenceRow).length > 0;
  const arrange = (rows) => {
    const referenceAt = rows.indexOf(referenceRow);
    const withoutReference =
      referenceAt === -1
        ? rows
        : [...rows.slice(0, referenceAt), ...rows.slice(referenceAt + 1)];
    const candidates = withoutReference;
    const first = candidates[0];
    const wayOut = candidates
      .slice(1)
      .find(
        (row) => bindings(row).includes("Escape") && word(row.promoteEscape) !== false,
      );
    const short = new Set([first, wayOut ?? candidates[1]].filter(Boolean));
    const tail = withoutReference.includes(backRow) ? backRow : null;
    return { candidates, referenceAt, short, tail };
  };
  function more() {
    if (!shortcutAvailable() || expanded) return reference.show(true);
    const { candidates, short } = arrange(lineRows(stack()));
    if (!candidates.some((row) => !short.has(row))) return reference.show(true);
    expanded = true;
    paintHere();
    announce(
      "More keyboard shortcuts shown. Press question mark again for all shortcuts, or Escape to show less.",
    );
  }
  function less({ silent = false } = {}) {
    if (!expanded) return;
    expanded = false;
    paintHere();
    if (!silent) announce("Fewer keyboard shortcuts shown.");
  }
  function renderLine() {
    // One walk, read twice: `at` and `when` are the page's own state and a second walk would
    // ask every one of them again for the same frame.
    const scopes = stack();
    const rows = lineRows(scopes);
    if (!shortcutAvailable()) expanded = false;
    const shelf = expanded && !reference.open;
    keylineEl.dataset.lfExpanded = String(shelf);
    // `?` has its own permanent More control, so its ordinary row remains in the DOM only as
    // the register's hidden projection. In the shelf, the current Escape is drawn after that
    // control so both disclosure choices finish the second row.
    const { candidates, referenceAt, short, tail } = arrange(rows);
    const ordered = [
      ...candidates.filter((row) => !shelf || row !== tail),
      ...(referenceAt === -1 ? [] : [referenceRow]),
    ];
    // Read where it is painted, like every other cell: the chord's chip says which stage the
    // reader is at (`g`, then `g h`), and a string fixed at declaration could only say one.
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
    const chip = (key, said, armed, afterMore = false) => {
      const span = el("span", "lf-key");
      span.setAttribute("aria-hidden", "true");
      const kbd = document.createElement("kbd");
      if (armed) kbd.className = "armed";
      kbd.textContent = key;
      span.append(kbd);
      if (said) span.append(el("span", "", said));
      if (afterMore && seated) keylineEl.append(span);
      else keylineEl.insertBefore(span, seated ? keylineMore : null);
      return span;
    };
    if (chord) chip(chord, "", true);
    const drawn = ordered.map((row) => {
      const span = chip(labelOf(row), word(row.line));
      span.hidden = row === referenceRow || (!shelf && !short.has(row));
      return span;
    });
    // The door is not useful behind the room it opens. While the reference stands, its
    // own Escape row is the short line and More leaves the focus order with the page. This
    // is the one removal that is meant: a reader standing on the door when the room opens
    // is a state change rather than a repaint, and the help takes the focus anyway.
    if (reference.open) keylineMore.remove();
    else if (!seated) keylineEl.append(keylineMore);

    if (shelf && tail) chip(labelOf(tail), word(tail.line), false, true);

    // Two hints, and then two rows, are ceilings rather than permission to clip. On a window
    // narrower than the compact sentences, yield the lower-ranked hint and then the first;
    // in the shelf, yield the lowest-ranked current commands until its two disclosure
    // controls fit on the second row. Hidden rows remain available to inspection and the
    // reference.
    if (shelf) {
      const visible = () =>
        [...keylineEl.children].filter(
          (node) => !node.hidden && node.checkVisibility(),
        );
      const rowsUsed = () => {
        const items = visible();
        const tolerance = Math.min(...items.map((node) => node.offsetHeight)) / 2;
        const tops = [];
        for (const node of items)
          if (tops.every((top) => Math.abs(top - node.offsetTop) > tolerance))
            tops.push(node.offsetTop);
        return tops.length;
      };
      const removable = drawn.filter((item) => !item.hidden).toReversed();
      while (rowsUsed() > 2 && removable.length) removable.shift().hidden = true;
      return;
    }
    // On a window narrower than those two
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

  return {
    get expanded() {
      return expanded && shortcutAvailable();
    },
    less,
    more,
    renderLine,
  };
}
