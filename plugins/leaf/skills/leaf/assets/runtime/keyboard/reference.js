import { bindings, declaredBindings, labelOf, live, spell, word } from "./bindings.js";

export function createReference({
  bySentence,
  characterShortcutsOn,
  el,
  elementScopes,
  ELEMENTS,
  EVERYTHING,
  focused,
  helpClose,
  helpEl,
  merge,
  pageSelection,
  paintHere,
  pruneScopedElements,
  reachScrollers,
  readerIn,
  scopeRefs,
  SCOPES,
  setCharacterShortcuts,
  scopesFor,
}) {
  // Every scope the page has, gathered by title, for the reference. Not the stack: the
  // reference answers "what could I do here", so it names a card grip's keys whether or not
  // a grip has focus. What it does not name is a key that would refuse the press, which is
  // the rows' own liveness.
  //
  // The runtime's own modes come through the same door as a widget's, and the reference was
  // blind to them while they did not: the sharpest case was the overlay never saying how to
  // close the overlay, and a quiet page naming no Escape at all. So a section is its title
  // wherever the title comes from — the box a reply is typed into declares its send key from
  // wireInput and its way out from the typing mode, and they are one heading.
  //
  // The stack backwards, so a reader learning the keyboard starts from the page in front of them
  // and reads inward, and the widgets' sections land where their scopes stand in it rather than
  // wherever a second list happened to put them.
  function declaredStack() {
    pruneScopedElements();
    const sections = new Map();
    const named = (section) =>
      scopesFor(focused()).some((s) => s.title === section.title);
    // Carry a scope's chord down to each of its rows before sections with the same title
    // merge. The prefix belongs only to the rows that scope contributed; putting it on the
    // merged section would also put it in front of an unrelated widget that chose the same
    // heading.
    const referenceRows = (scope) =>
      bySentence(scope.rows).map(([sentence, row]) => [
        sentence,
        scope.chord ? { ...row, chord: scope.chord } : row,
      ]);
    for (const scope of SCOPES.toReversed()) {
      if (scope !== ELEMENTS) {
        merge(sections, { ...scope, rows: referenceRows(scope) });
        continue;
      }
      // Where the reader is, for a widget's section, is whether the focused element declares it
      // — the one thing core's own scopes state for themselves and an element scope cannot,
      // since it is gathered here by title and the elements wearing that title are many.
      const declared = new Map();
      // In the order the page holds them, not the order they registered. `scopeRefs` is
      // insertion-ordered and a widget registers at upgrade, so the sections came out in
      // whatever order the modules happened to finish in — the same build read twice put
      // "On a tab" above "On a card grip" once and below it the next time. A reference whose
      // headings move between loads is one a reader cannot learn the shape of, and any
      // assertion on it flakes rather than fails.
      const held = [...scopeRefs]
        .map((ref) => ref.deref())
        .filter((el) => el?.isConnected && elementScopes.get(el)?.title);
      held.sort((a, b) =>
        a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
      );
      for (const el of held) {
        const section = elementScopes.get(el);
        merge(declared, { ...section, rows: referenceRows(section) });
      }
      for (const section of declared.values())
        merge(sections, { ...section, at: () => named(section) });
    }
    // The way out reads last, after what the scope is for. A section gathers its rows from
    // wherever they were declared, and a mode contributing only its Escape would otherwise
    // put the exit above the walk it exits from.
    const exit = (row) => (bindings(row).includes("Escape") ? 1 : 0);
    return [...sections.values()].map((s) => ({
      ...s,
      rows: [...s.rows.values()].sort((a, b) => exit(a) - exit(b)),
    }));
  }

  // ---------- the reference ----------
  // Every scope the page has, live rows only, so nothing on screen is a key that does
  // nothing. It renders at open and can go stale while it stands, and the two directions
  // cost differently, both acceptably: a row going dead under it cannot be pressed, since
  // the overlay claims the keyboard and the page stands down beneath it, and a key going live under it
  // is merely unlisted until the next open, one press away.
  let helpOpen = false;
  // Where the reference was opened from, so closing it hands the reader back. Any dialog that
  // takes focus owes that; what makes it structural here is that a scope is *where focus is*,
  // so the overlay explaining a walk was also the way out of it — open the reference from a
  // version row or a held card and the row's keys, which it had just listed, reached nothing
  // afterwards. A mode over the page keeps this one key (`allButTheReference`), and a kept key
  // that costs the reader their place is not much of an exemption.
  let helpFrom = null;
  const helpWords = (value) =>
    String(value ?? "")
      .toLocaleLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  function showHelp(open, restoreFocus = true) {
    // Focusing a text input replaces the document selection. Keep a passage the reader has
    // in hand when `?` opens the reference, while an ordinary open lands directly in search.
    // The dialog itself remains a focus stop, so either route keeps the page suspended.
    const preserveSelection = open && Boolean(pageSelection());
    const restore =
      !open && restoreFocus && helpEl.contains(focused()) ? helpFrom : null;
    if (open && !helpOpen) helpFrom = focused();
    helpOpen = open;
    if (open) {
      helpEl.textContent = "";
      const head = el("div", "lf-help-head");
      head.append(el("div", "lf-help-title", "Keyboard reference"), helpClose);
      helpEl.append(head);
      const search = document.createElement("input");
      search.type = "search";
      search.className = "lf-help-search";
      search.placeholder = "Find a key or action";
      search.setAttribute("aria-label", "Search keyboard shortcuts");
      search.autocomplete = "off";
      search.spellcheck = false;
      const meta = el("div", "lf-help-meta");
      meta.setAttribute("aria-live", "polite");
      const preference = el("div", "lf-help-preference");
      const characterToggle = el("button", "lf-btn lf-help-shortcuts");
      characterToggle.type = "button";
      characterToggle.setAttribute("aria-label", "Character shortcuts");
      const paintCharacterToggle = () => {
        const on = characterShortcutsOn();
        characterToggle.setAttribute("aria-pressed", String(on));
        characterToggle.title = `Turn ${on ? "off" : "on"} letter, number, and punctuation shortcuts`;
        characterToggle.replaceChildren(
          document.createTextNode("Character shortcuts "),
          el("span", "", on ? "on" : "off"),
        );
      };
      paintCharacterToggle();
      characterToggle.onclick = () => {
        setCharacterShortcuts(!characterShortcutsOn());
        // Rebuild the reference from the newly available bindings. Keep focus on the
        // preference that caused the change instead of returning to search and making
        // the toggle feel like a navigation command.
        showHelp(true);
        helpEl.querySelector(".lf-help-shortcuts").focus({ preventScroll: true });
      };
      preference.append(meta, characterToggle);
      const results = el("div", "lf-help-results");
      const empty = el("div", "lf-help-empty", "No matching shortcuts");
      empty.hidden = true;
      const sections = [];
      let total = 0;
      // A chord row is reached from the standing page, so its cell shows every press. A
      // custom label already groups the row's remaining bindings (for example `c 1–2`);
      // an ordinary row is expanded binding by binding so `g / G` becomes the unambiguous
      // `g g / g G` rather than `g g / G`.
      const referenceLabel = (row) => {
        const chord = word(row.chord);
        if (!chord) return labelOf(row);
        const label = word(row.label);
        return label == null
          ? bindings(row)
              .map((binding) => `${chord} ${spell(binding)}`)
              .join(" / ")
          : `${chord} ${label}`;
      };
      const table = (rows, scopeTitle) => {
        const t = document.createElement("table");
        const entries = [];
        for (const row of rows) {
          const tr = document.createElement("tr");
          const kbd = document.createElement("kbd");
          const label = referenceLabel(row);
          kbd.textContent = label;
          const keyCell = document.createElement("td");
          keyCell.append(kbd);
          tr.append(keyCell, el("td", "", word(row.does)));
          t.append(tr);
          entries.push({
            el: tr,
            words: helpWords(
              `${scopeTitle} ${label} ${word(row.does)} ${word(row.line)}`,
            ),
          });
        }
        total += entries.length;
        return { el: t, entries };
      };
      for (const scope of declaredStack()) {
        // A scope the reader is standing in is filtered by each row's own liveness, because
        // they can see which state they are in and a row that would refuse the press must
        // not be on screen. A scope they are merely near is listed whole: a row's `when`
        // asks whether the press moves *here*, and here is not where they are, so a grip's
        // "arrows move" belongs in the reference though no card is held and `x` belongs in
        // it though no thread is focused. Filtering both by the same predicate is what took
        // the thread's own keys out of the reference altogether.
        //
        // A mode is the exception, and it is one because there is no standing near it: the
        // reader is in it or it is not there, so its rows answer about here whichever way the
        // reference was opened. The chord is what needs this said — its rows are the lists
        // the page has, and `?` reaches the reference only from a page nobody has armed, so
        // listed whole it would name `g l` on a page holding no link at all.
        const inIt = readerIn(scope) || scope.claims === EVERYTHING;
        // A declared section may merge many element instances under one title. Their
        // identical bindings are alternatives at different focus locations, not competing
        // meanings in one dispatch scope, so conflict validation stays on each registered
        // scope and this aggregate only filters the rows relevant to the current state.
        const rows = scope.rows.filter(
          (row) =>
            row.does &&
            // Pointer-native actions can deliberately carry a label but no key. Keep
            // those in the complete reference; only hide a row whose declared character
            // binding the reader has turned off.
            (bindings(row).length > 0 || declaredBindings(row).length === 0) &&
            (!inIt || live(row)),
        );
        if (!rows.length) continue;
        const title = scope.title ?? "On this page";
        const section = document.createElement("section");
        section.className = "lf-help-section";
        const heading = el("h3", "", title);
        const body = table(rows, title);
        section.append(heading, body.el);
        results.append(section);
        sections.push({
          el: section,
          heading,
          table: body.el,
          words: helpWords(title),
          entries: body.entries,
        });
      }
      results.append(empty);
      const filter = () => {
        const query = helpWords(search.value);
        let shown = 0;
        for (const section of sections) {
          const sectionMatch = query && section.words.includes(query);
          let sectionShown = 0;
          for (const entry of section.entries) {
            const match = !query || sectionMatch || entry.words.includes(query);
            entry.el.hidden = !match;
            if (match) sectionShown++;
          }
          section.el.hidden = sectionShown === 0;
          section.heading.hidden = sectionShown === 0;
          section.table.hidden = sectionShown === 0;
          shown += sectionShown;
        }
        empty.hidden = shown !== 0;
        meta.textContent = query
          ? `${shown} of ${total} shortcuts`
          : `${total} shortcuts`;
      };
      search.addEventListener("input", filter);
      filter();
      helpEl.append(search, preference, results);
    }
    helpEl.classList.toggle("open", open);
    // The reference is a list long enough to scroll, and anything a mouse can scroll a
    // keyboard has to reach. `reachScrollers` is the runtime's one answer to that and had
    // never been pointed at the chrome it builds after upgrade: its rows carry no control,
    // so a reader working from the keyboard could read the first screenful of the key
    // reference and had no way to the rest of it. Called with the overlay open, because the
    // sweep reads computed overflow and a hidden box has none.
    if (open) reachScrollers(helpEl);
    if (open)
      (preserveSelection ? helpEl : helpEl.querySelector(".lf-help-search")).focus({
        preventScroll: true,
      });
    // Only from inside the overlay: a mousedown somewhere else closes it (standDown), and the
    // press's own focus is the browser's default action, still to come — a restore made from
    // out here would be putting focus back for the click to take again.
    paintHere();
    if (!open && restore) {
      if (restore.isConnected) restore.focus({ preventScroll: true });
      else
        requestAnimationFrame(() => {
          if (restore.isConnected) restore.focus({ preventScroll: true });
        });
    }
  }

  const helpStops = () =>
    [
      ...helpEl.querySelectorAll('button, input, [tabindex]:not([tabindex="-1"])'),
    ].filter((node) => node.checkVisibility());
  function move(dir) {
    const stops = helpStops();
    if (!stops.length) return helpEl.focus({ preventScroll: true });
    const at = stops.indexOf(focused());
    const next =
      at < 0
        ? dir > 0
          ? stops[0]
          : stops.at(-1)
        : stops[(at + dir + stops.length) % stops.length];
    next.focus({ preventScroll: true });
  }
  helpClose.onclick = () => showHelp(false);

  return {
    get open() {
      return helpOpen;
    },
    move,
    show: showHelp,
  };
}
