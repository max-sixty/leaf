export function createLiveLeaves({
  ago,
  el,
  keys,
  leavesList,
  openTray,
  othersBtn,
  othersPanel,
  pagePresented,
  paintKeys,
  presented,
  showNews,
  toneFor,
  walkRows,
}) {
  let others = [];

  // The tray's one offer: something to show, or the tray already standing — the key that
  // opened it must still close it, and its button must still be pressable. The button's
  // visibility and the key both ask the tray's own predicate, so the two surfaces cannot
  // disagree about whether there is a tray to open. A leaves tray of one — the page the
  // reader is already on — is not worth a control.
  const leavesOffered = () =>
    pagePresented() && (others.length > 0 || openTray("leaves"));

  // The tray's own scope. The walk is the tray's rather than the page's, because ArrowUp
  // and ArrowDown anywhere else are the page's own scroll and stay so; Enter is the
  // browser's, a row being a link, and the row says so with no `run` to give. The reader
  // arrives here by key — `l` lands focus on the first neighbour — so the scope names what
  // activating does rather than leaving it to the platform's own contract.
  const othersLinks = () => [...othersPanel.querySelectorAll("a.lf-others-row")];
  keys(
    othersPanel,
    "In the leaves tray",
    [
      {
        keys: ["ArrowUp", "ArrowDown"],
        does: "Walk the leaves",
        line: "walk the leaves",
        repeat: true,
        run: (binding) => walkRows(othersLinks(), binding === "ArrowDown" ? 1 : -1),
      },
      // Enter is the browser's here, the row being a link — no `run`, because binding it
      // would click a control the platform has already activated. It carries a word all the
      // same: the press is real and immediate where the reader is standing, which is what
      // the line is for.
      { keys: ["Enter"], does: "Open that leaf in a tab", line: "open it in a tab" },
    ],
    leavesOffered, // the scope's own liveness: a tray with something to walk
  );

  // A row's whole account of a page: the dot's tone and one line of words, from the
  // same judgment the banner's sentences come from — the judgment is shared, the
  // wording is the seat's.
  function rowPresence(entry) {
    const { kind, quiet, dropped, detail } = presented(entry);
    // The same join for both kinds that have words of their own. The reader opens this
    // panel to find which page needs them, so a bare `Awaits` beside a neighbour's
    // `Working — recording the demo` said least about the one row they are here to act
    // on: three pages waiting rendered as three identical rows, and which to go to
    // first is the whole question the panel was opened to answer.
    const stated = (word) => word + (detail ? " — " + detail : "");
    // The banner's two silences, dated the same way and worded for a row.
    const silence = dropped
      ? `Left (${ago(entry.turn_closed)})`
      : `Quiet (${ago(entry.status.ts)})`;
    const line =
      kind === "working"
        ? stated("Working")
        : kind === "listening"
          ? stated("Awaits")
          : kind === "stalled"
            ? stated(silence)
            : kind === "away"
              ? quiet
                ? silence
                : "Away"
              : kind === "unheld"
                ? "Unheld"
                : kind === "unattended"
                  ? "Unattended"
                  : "Closed";
    return { tone: toneFor(kind), line };
  }

  // The whole of what the tray knows about one page, for its hover. Everything drawn
  // on a row is cut to the panel's fixed width — the title ellipsizes, the line
  // ellipsizes — and the fact that tells two rows apart is not drawn at all: where the
  // session behind the leaf is working. A title is a sentence somebody wrote and two
  // pages a week apart share one; the work each came out of is the thing the reader
  // already holds in their head, so it is worth the room a hover has and a row hasn't.
  //
  // One tooltip for the row rather than one per part. The innermost title wins where two
  // overlap, so a title left on the line would answer the hover most likely to be asking
  // this question — a reader pointing at the words that ran out of room — with the one
  // part of the account they can already read.
  const rowAccount = (entry, title, line) =>
    [
      title,
      entry.session_cwd,
      line,
      // The reader's own words that page's agent hasn't taken in. The banner says this
      // number for this page; the tray says it for every page, which is the seat's
      // whole point — a leaf holding something of yours that nobody has read is a
      // reason to go there, and nothing else on the row says so.
      entry.pending &&
        `${entry.pending} update${entry.pending === 1 ? "" : "s"} waiting`,
    ]
      .filter(Boolean)
      .join("\n");

  const othersRows = new Map(); // keyed by URL; the self row under its own key
  function renderOthers(state) {
    const offeredBefore = leavesOffered();
    // An older server ships no list, which is an empty one. A closed leaf is not
    // one of the machine's live pages and drops out of the tray on the poll that says
    // so: its server stays up so the page stays readable — a standing one for good —
    // so nothing else would ever take the row off, and a count the reader glances at
    // to find who needs them would silently become a tally of everything that has run
    // here. Judged by the same `presented` the rows read, never by a second reading of
    // the status the server ships. This page's own row is not in the list and so is
    // never dropped: a reader looking at a closed page is still looking at it.
    others = (state.others ?? []).filter((entry) => presented(entry).kind !== "closed");
    // While the panel stands its button stands too, whatever the count just did.
    showNews(othersBtn, leavesOffered());
    const wanted = [
      { key: "self", title: document.title, entry: state },
      ...others.map((entry) => ({ key: entry.url, title: entry.title, entry })),
    ];
    // The button names the tray it opens, so the count is these rows — the list the
    // press will show, headed by this page's own row — and never arithmetic beside
    // them. "Other leaves" counted the neighbours alone, one off the list it
    // promised: a machine with one neighbour said (1) over a tray of two.
    othersBtn.textContent = `All leaves (${wanted.length})`;
    let anchor = null; // the row before this one, so order holds without rebuilding
    for (const { key, title, entry } of wanted) {
      let row = othersRows.get(key);
      if (!row) {
        // The self row is a marked div — the reader is already here, so there is
        // nothing to open; every other row is a link to its page's own tab.
        row =
          key === "self"
            ? el("div", "lf-others-row lf-others-self")
            : Object.assign(el("a", "lf-others-row"), {
                href: key,
                target: "_blank",
                rel: "noopener",
              });
        const head = el("div", "lf-others-head");
        head.append(el("span", "lf-dot"), el("span", "lf-others-title"));
        if (key === "self") head.append(el("span", "lf-pill", "this page"));
        row.append(head, el("div", "lf-others-line"));
        othersRows.set(key, row);
      }
      const { tone, line } = rowPresence(entry);
      const [rowDot, rowTitle] = row.querySelectorAll(".lf-dot, .lf-others-title");
      const rowLine = row.querySelector(".lf-others-line");
      // Written only on change: an unchanged poll must not feed the mutation stream
      // a screen reader rebuilds its buffer on.
      const dotCls = "lf-dot" + (tone ? " " + tone : "");
      if (rowDot.className !== dotCls) rowDot.className = dotCls;
      if (rowTitle.textContent !== title) rowTitle.textContent = title;
      if (rowLine.textContent !== line) rowLine.textContent = line;
      // Everything the row was too narrow to say, on the row itself (see rowAccount).
      const account = rowAccount(entry, title, line);
      if (row.title !== account) row.title = account;
      const place = anchor ? anchor.nextElementSibling : leavesList.firstElementChild;
      if (place !== row) leavesList.insertBefore(row, place);
      anchor = row;
    }
    for (const [key, row] of othersRows)
      if (!wanted.some((w) => w.key === key)) {
        row.remove();
        othersRows.delete(key);
      }
    if (offeredBefore !== leavesOffered()) paintKeys();
  }

  return { leavesOffered, othersLinks, renderOthers };
}
