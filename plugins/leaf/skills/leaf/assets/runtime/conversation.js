/* Conversation folding and panel reconciliation. */
export function createConversation(dependencies) {
  const {
    COMMENTS,
    FOLD_MS,
    MARKED_ANYWHERE,
    SCROLL,
    addressLabel,
    addressed,
    agentName,
    ago,
    captureAuthoredFacets,
    claimState,
    designIsOn,
    designName,
    droppedAt,
    el,
    elementById,
    findInput,
    focused,
    generalRow,
    highlightBlocks,
    inChrome,
    isMarked,
    itemSays,
    itemWord,
    landTyping,
    layerPart,
    loadDraft,
    markDeclared,
    matchesWhen,
    mirrorDraft,
    motion,
    needsBtn,
    offer,
    pageParts,
    pageQueryAll,
    paintAnchors,
    paintHere,
    panelIsOpen,
    panelTitle,
    placedAt,
    post,
    quietSince,
    reachScrollers,
    reachedForWords,
    reactDone,
    reactPills,
    refreshHover,
    registry,
    rememberAuthoredMarkup,
    renderQuiet,
    renderSaid,
    reportPageError,
    retractedIds,
    retractionFloors,
    runtime,
    saveDraft,
    scrollToElement,
    scrollToThread,
    sectionOf,
    sendDraft,
    sendReaction,
    setPanel,
    settling,
    takenBack,
    tellDraft,
    threadsBox,
    toggleBtn,
    updateSequence,
    wireInput,
    withdraw,
  } = dependencies;
  let threadList = [];

  // A reaction is a message carrying a token in place of words ($events): a mark on its
  // target rather than a turn in the conversation. `spoken` is a thread's turns; one with
  // none is a bare reaction — paint on the page, no card in the panel — until somebody
  // replies to it, from which point it is a conversation whose root happens to be a mark.
  // interact.py reads the log by the same three names (events.py), so the panel and
  // `page state` cannot come to list different threads.
  const isReaction = (m) => Boolean(m.token);
  const spoken = (t) => t.msgs.filter((m) => !isReaction(m));
  // What a card shows: the turns, and the root whatever it is — a thread that grew out
  // of a reaction opens on the mark that started it, which is what the agent answered.
  const turns = (t) => t.msgs.filter((m) => m === t.root || !isReaction(m));
  const bareReaction = (t) => isReaction(t.root) && !spoken(t).length;
  const conversational = (t) => !bareReaction(t);
  const tokenEntry = (name) => registry.$reactions.tokens[name];
  // Whether a reaction still paints, and so can still be taken back: in an unresolved
  // thread, and answered by no turn — the same three the door refuses (`undo_error`).
  // Read off the last reconcile's fold rather than a fresh one, this being asked on
  // every key-line paint.
  let lastThreads = [];
  // The bare reactions standing on exactly this anchor — the bar's own question, asked
  // so its pills can say which tokens are already there. Anchors are compared as
  // records, the way the file compares them.
  const sameAnchor = (a, b) =>
    JSON.stringify(a, Object.keys(a ?? {}).sort()) ===
    JSON.stringify(b, Object.keys(b ?? {}).sort());
  const reactionsOn = (anchor) =>
    lastThreads
      .filter(
        (t) => bareReaction(t) && !t.resolved && sameAnchor(t.root.anchor, anchor),
      )
      .map((t) => t.root);
  const reactionStanding = (e) => {
    const thread = lastThreads.find((t) => t.msgs.some((m) => m.id === e.id));
    return (
      Boolean(thread) &&
      !thread.resolved &&
      !thread.msgs.some((m) => m.parent === e.id && !isReaction(m))
    );
  };

  // ---------- threads ----------
  function buildThreads() {
    const threads = new Map();
    const threadFor = new Map();
    // The whole log, not this version's window: a conversation is not version-scoped, so
    // the panel shows the same threads whichever version is pinned and a retraction
    // settles a thread's state from wherever it was declared. interact.py's callers pass
    // upto=None for the same reason. Replay windows to currentVersion instead, and on any version
    // but the newest the two are meant to disagree — the rule binds both sites, so it is
    // stated once in the skill's CLAUDE.md, under "A pinned version scopes the document,
    // never the conversation".
    const floors = retractionFloors(Infinity);
    const withdrawn = takenBack();
    // widget id -> its last action the log still lets stand: not one the reader took
    // back, not one a version retracted under it. The widget is what an ask is
    // (x-awaits), so what answers one is that widget's own last word; and it is the
    // only key the log carries by itself, which is why the page projection cannot be
    // borrowed for this: it drops an action whose widget the page no longer holds, and the
    // version that honors a decision retires the widget that made it, precisely when the
    // thread it settled most needs to stay settled. x-state holds a verb declaring
    // `resolves` to a widget-absolute unit so the two keys are the same one.
    const answers = new Map();
    const settlingActions = new Set();
    for (const e of runtime.events)
      if (
        e.kind === "action" &&
        !withdrawn.has(e.id) &&
        !retractedIds(e, floors, elementById(e.widget)).length
      ) {
        answers.set(e.widget, e);
        if (e.detail.resolves) settlingActions.add(e.id);
      }
    for (const e of runtime.events) {
      // A gesture the reader took back settles nothing, whichever way it settled: the
      // log holds it and no reading of the log stands on it. The same sentence
      // interact.py's build_threads reads, because it is the same reading.
      if (withdrawn.has(e.id)) continue;
      if (e.kind === "comment") {
        // `resolved` is the event that currently closes the thread, or null. Either
        // side can close one, so a flag beside a second field naming who would be two
        // readings of one fact; the event answers both and carries its own author.
        const thread = { root: e, msgs: [e], resolved: null };
        threads.set(e.id, thread);
        threadFor.set(e.id, thread);
        continue;
      }
      // The widget's standing answer closes the thread it names. The answer snapshots the thread
      // it was made in, because the honoring version retires the wrapper that held the
      // mapping and one atomic event cannot half-arrive the way a second POST could.
      // The log is the only place that pairing survives.
      //
      // Read off the detail rather than the verb, because the naming is the
      // mechanism's and the verb is a member's: `accept` stood here once, which was
      // exactly right for the one widget that says that word and silently nothing
      // for the next widget whose answer closes the question it was asked in. That
      // is the failure the widget list's norm names — it arrives as a feature
      // nobody wired up rather than as an error. A verb carries only the detail
      // keys its entry declares (additionalProperties: false), so a `resolves` is
      // one on purpose, and an answer that settles no thread carries none.
      //
      // Standing is every way the log currently holds an answer: not retracted by a
      // version that rewrote what the decision rested on (`restated`), not taken back
      // by the reader (the skip above), and not superseded by a later action on the
      // same widget. Without that last one, a
      // reject after an accept left the reader's question filed away as answered by
      // the fix they had just turned down, while the fold reported the suggestion
      // rejected: the log held one thing, the panel showed another, and nothing on
      // either side said so.
      //
      // Folded at the answer's own place in the walk rather than after it: a resolve
      // pressed between two decisions remains the last current word on the thread,
      // while every surviving settlement keeps its causal position.
      if (e.kind === "action") {
        const answered = threads.get(e.detail.resolves);
        if (answered && settlingActions.has(e.id)) {
          if (answers.get(e.widget) === e) answered.resolved = e;
        }
        continue;
      }
      // A reply whose message the log lost opens the thread that message would have
      // opened, under the id it was known by — the same answer interact.py's
      // build_threads gives, because it is the same reading. The log is read line by
      // line and a torn one is skipped, so a reply can outlive the message above it;
      // throwing here took the whole panel down over one lost line.
      if (e.kind === "reply") {
        let thread = threadFor.get(e.parent);
        if (!thread) {
          thread = { root: e, msgs: [], resolved: null };
          threads.set(e.parent, thread);
          threadFor.set(e.parent, thread);
        }
        thread.msgs.push(e);
        threadFor.set(e.id, thread);
      } else if (e.kind === "resolve") {
        // A resolve names a message rather than opening one, so a conversation the log
        // lost whole has nothing for it to close.
        const thread = threadFor.get(e.parent);
        if (thread) thread.resolved = e;
      } else if (e.kind === "unresolve") {
        const thread = threadFor.get(e.parent);
        if (thread) thread.resolved = null;
      }
    }
    return [...threads.values()];
  }

  const escapeHtml = (s) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // Lazily, like the tokenizer: a page is usually handed over before anyone has said
  // anything, and one with no messages never pays the parse. poll() awaits this before
  // the panel builds a body, which is what keeps msgNode synchronous.
  //
  // Raw HTML — block and inline both route through the one `html` renderer — escapes to
  // the characters it was written in: prose says `Vec<T>`, and a message injects widgets
  // only through its gate-validated `markup` field, never through text. breaks: a single
  // newline is a line break, because a message is typed prose and nobody types two
  // spaces to mean the line they just ended.
  // Plain escaped text until the renderer arrives, so a failed vendor import
  // degrades a body's Markdown to its own words instead of refusing the poll
  // that carries it.
  let renderMarkdown = (text) => escapeHtml(text);
  let markedReady;
  const loadMarked = () =>
    (markedReady ??= import("/vendor/marked.esm.js")
      .then((m) => {
        const md = new m.Marked({
          breaks: true,
          renderer: { html: (t) => escapeHtml(t.text) },
        });
        renderMarkdown = (text) => md.parse(text);
      })
      .catch((error) => {
        // Retry on a later poll rather than caching the rejection for the life
        // of the load — one transient failure otherwise left every body plain.
        markedReady = undefined;
        reportPageError(`markdown renderer failed to load: ${error?.message ?? error}`);
      }));

  // Bodies are cached per event id and re-adopted when a thread node is rebuilt — which
  // the reconcile leaves one occasion for, a thread resolving. The log is append-only,
  // so a message's text never changes, and re-adopting the node keeps a widget in a reply
  // (a rendered diagram) from re-upgrading across that rebuild.
  const msgBodies = new Map();
  function buildMsgBody(m) {
    const body = el("div", "lf-msg-body");
    if (isReaction(m)) {
      // A thread whose root is a mark: the glyph and its word, in the chrome's own
      // face, where a comment's words would be. What it meant is the entry's `means`,
      // said on hover the way the bar says it.
      const said = el(
        "span",
        "lf-react-said",
        `${tokenEntry(m.token)?.glyph ?? ""} ${m.token}`.trim(),
      );
      said.title = tokenEntry(m.token)?.means ?? "";
      body.append(said);
    } else if (m.suggestion) {
      // Verbatim: a suggestion's characters are bound for the page as typed, and a
      // rendering would show an italic where the next version carries the asterisks.
      body.classList.add("lf-suggest-body");
      body.textContent = m.text;
    } else {
      body.innerHTML = renderMarkdown(m.text);
      // The widget markup beside the text, injected as the CLI gate validated it. A
      // template is deliberately inert: an already-defined custom element's constructor
      // runs even in a detached ordinary div, which would make generated state look like
      // the thread event's authored baseline. Capture the literal event markup first,
      // then move those same nodes into the body; they upgrade when the body is connected.
      // The passes below don't come along with that upgrade — the said and quiet passes
      // write a widget's declared words, spoken and silent, and a fenced block is a
      // <pre><code class="language-…"> like any the page holds.
      //
      // The declared marks come along by the half that holds here (MARKED_ANYWHERE):
      // whether a widget is set among the words is true of it in a reply as much as on
      // the page, and a chip-led comparison quoted into one stacks without it. The width
      // model is the half that stays behind, and the reason is what it hands out: the room
      // the *document* has, which is not the room in here. A diagram in a reply is a widget
      // the vocabulary calls wide, and marked as one it would lay itself out to the page's
      // measure inside the panel. The room a message has is the message's, and it already
      // has it.
      if (m.markup) {
        const authored = document.createElement("template");
        authored.innerHTML = m.markup;
        rememberAuthoredMarkup(authored.content);
        captureAuthoredFacets(authored.content);
        body.append(authored.content);
      }
      markDeclared(body, MARKED_ANYWHERE);
      renderSaid(body);
      renderQuiet(body);
      // Not settle()d: that queue holds the page's geometry still for the first anchor
      // pass, and a message colors in the panel, where no anchor is captured and nothing
      // waits. Each block already fails soft to its own plain source.
      highlightBlocks(body);
    }
    return body;
  }

  function msgNode(m) {
    const div = el("div", `lf-msg ${m.author}`);
    div.dataset.mid = m.id; // the reconcile's key, and revealThread's address for it
    const head = el("div", "lf-msg-head");
    // "3 hours ago" is not a datetime, so the machine-readable one goes in the attribute
    // the element has for it — which is also what `saidAt` reads back when a widget the
    // message carries needs to know when it was said.
    const when = el("time", "", ago(m.ts));
    when.dateTime = m.ts;
    head.append(el("b", "", m.author === "claude" ? m.agent || "Agent" : "You"), when);
    let body = msgBodies.get(m.id);
    if (!body) {
      body = buildMsgBody(m);
      msgBodies.set(m.id, body); // the id is server-minted, on every event
    }
    div.append(head);
    if (m.suggestion)
      div.append(el("div", "lf-suggest-label", "suggested replacement"));
    div.append(body);
    return div;
  }

  // How an anchor reads where it has to be printed rather than pointed at — every thread in
  // the panel, and the open composer when the page has no passage left to mark. A quote-less
  // anchor points at an element (a diagram or image commented on by click rather than by
  // selection) and names its section instead of quoting it. One function, so the two places
  // can't come to say it differently.
  //
  // An id is the page's name for an item and not the user's. `card-migration` says
  // nothing they wrote, and pointing at an item is an ordinary gesture rather than the
  // diagram's special case, so anchors reading this way are ordinary in the panel too.
  // An element anchor is labelled with the item's own opening words, and falls
  // back to the id where this version has no such element. The kind goes before the words
  // because the two together are a name, where the words alone read as a quote the thread
  // does not hold.
  //
  // A design comment (`about: "layer"`) reads "layer ·" first, because what follows names
  // the thing whose look or behaviour is in question rather than the words on it: the
  // control the press landed on where it landed on one (`part`), then the item — a
  // widget by its tag and id, a runtime part by its name — since a design comment's
  // subject is the element itself and its opening words would read as a quote.
  function anchorLabel(anchor, about) {
    if (about === "layer") {
      const item = anchor?.section ? elementById(anchor.section) : null;
      const name = item ? designName(item) : anchor?.section || "the page";
      const on = anchor?.part ? `${anchor.part} · ${name}` : name;
      return anchor?.quote ? `layer · ${on} · “${anchor.quote}”` : `layer · ${on}`;
    }
    if (anchor?.quote) return `“${anchor.quote}”`;
    if (!anchor?.section) return "";
    const item = elementById(anchor.section);
    const says = itemSays(item);
    return `§ ${says ? `${itemWord(item)} · ${says}` : anchor.section}`;
  }

  // The open threads, in the order j/k walk and `g c` addresses. The list is the panel's own
  // children rather than a record kept beside them: a thread the log settles is renamed out
  // of them in that frame (foldOut), which takes it out of the walk, out of the addresses and
  // out of x's press in one stroke. A map of id → address stood here once, written by
  // renderThreads and read back by the chip and the placeholder — one list held twice, and
  // the copy free to be a reconcile behind the panel it described.
  const openThreads = () => [...threadsBox.querySelectorAll(":scope > .lf-thread")];

  // ---------- where the panel puts a thread ----------
  // The list reads in the page's order, not the log's. A page is a document with a
  // beginning and an end, and the reader walks the conversation the way they walk the
  // prose it is about: the thread on the lede is the first one, the thread on the punch
  // list is the last, and j/k, the g c digits, the marks out on the page and the panel's
  // own scroll all say the same order. Log order answered a different question — when a
  // thread was opened — which is a question about one thread rather than about a list, and
  // the message clocks already answer it.
  //
  // Where a thread stands is where the anchor pass resolved its passage to (`placed`) — the
  // same resolution the marks are drawn from, so the list and the page cannot disagree about
  // which of two threads comes first.
  //
  // A passage this version has rewritten falls back to the element the anchor names, which
  // is the whole point of an anchor carrying one: an id survives a rewrite that takes the
  // quote down with it, so a thread whose words are gone still belongs where it was about.
  // It reads as detached in the list and sits under its own heading, which are two true
  // things rather than one true and one lost.
  //
  // What is left resolves nowhere at all: a general comment, which names nowhere, and an
  // anchor whose element this version no longer holds either. Both go under the list rather
  // than at some point in the middle of it.
  // Where a thread stands, said in the document's own tree. A passage a widget renders into
  // a declared shadow root is placed inside that root, and `compareDocumentPosition` answers
  // across trees with "disconnected, in an implementation-specific order" — an order no
  // reader has ever seen, and one `contains` cannot correct. The host is the element the
  // page holds, and where the page holds it is where those words are. A place in no tree at
  // all — an element a version activation has replaced — is no place, which is the same
  // answer an anchor that resolves nowhere gets.
  const inPage = (el) => {
    let at = el;
    while (at && at.getRootNode() !== document) at = at.getRootNode().host ?? null;
    return at;
  };

  const threadPlace = (t) =>
    inPage(placedAt(t.root.id) ?? (t.root.anchor ? sectionOf(t.root.anchor) : null));

  // Which of two elements the reader reaches first. `compareDocumentPosition` answers for
  // a containing element too — a section reaches the reader before the paragraph inside it
  // — which is what makes it the whole reading rather than a comparison of two indexes
  // into a list this file would have to keep.
  const pageOrder = (a, b) =>
    a === b
      ? 0
      : a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING
        ? -1
        : 1;

  // The log's order is the tiebreak, so two threads on one paragraph read in the order they
  // were opened, and a page that gave nothing an id keeps exactly the list it had.
  function inPageOrder(threads) {
    const seat = new Map(threads.map((t, i) => [t, i]));
    const place = new Map(threads.map((t) => [t, threadPlace(t)]));
    return [...threads].sort((a, b) => {
      const pa = place.get(a);
      const pb = place.get(b);
      if (!pa || !pb) return (pa ? 0 : 1) - (pb ? 0 : 1) || seat.get(a) - seat.get(b);
      return pageOrder(pa, pb) || seat.get(a) - seat.get(b);
    });
  }

  // The page's own outline, in document order. Read off the headings the author wrote
  // rather than off <section> nesting, because both shapes are in the corpus and a heading
  // is the thing a reader navigates by in either — a page written as one flow of h2s has an
  // outline just as much as one written as nested sections. The runtime's own chrome
  // contributes none (pageParts), which also keeps a heading inside a reply's Markdown out
  // of the page's outline.
  const pageOutline = () => pageParts("h1, h2, h3, h4, h5, h6");

  // Which part of the page an element is in: the heading that names everything from itself
  // to the next one. A place that contains a heading takes that heading rather than the one
  // before it — an anchor on a whole <section> is about that section, not about the end of
  // the one above.
  function headingFor(place, outline) {
    let above = null;
    for (const heading of outline) {
      if (heading === place || place.contains(heading)) return heading;
      if (heading.compareDocumentPosition(place) & Node.DOCUMENT_POSITION_FOLLOWING)
        above = heading;
      else break;
    }
    return above;
  }

  // The run of threads a heading stands over, named. The key is what the panel reconciles
  // the heading node by, so it is positional (the outline's own index) rather than an id the
  // author may not have written. The named keys below it are the places a page has no seat
  // for; none of them ever carries a target, so a group's node keeps its kind — a button
  // where there is somewhere to go, a plain line where there is not — across every
  // reconcile.
  function groupFor(t, outline) {
    const place = threadPlace(t);
    if (!place)
      return t.root.anchor
        ? { key: "gone", label: "No longer in this version" }
        : { key: "page", label: "About the page as a whole" };
    if (inChrome(place))
      return layerPart(place)
        ? { key: "layer", label: "The page's own layer" }
        : { key: "sent", label: "Sent in the conversation" };
    const heading = headingFor(place, outline);
    // A page its author wrote no headings into has no runs to name, and a run with no name
    // gets no line: "Above the first heading" over the whole list would be a landmark
    // naming a landmark the page hasn't got. The list is still the page's order.
    if (!heading)
      return { key: "top", label: outline.length ? "Above the first heading" : "" };
    return {
      key: "h" + outline.indexOf(heading),
      label: itemSays(heading) || itemWord(heading),
      target: heading,
    };
  }

  // ---------- narrowing the list ----------
  // Two narrowings, and they compose: the words a reader is looking for, and whether the
  // thread is one the agent has left with them. Neither is stored — see the find row's own
  // comment for why a remembered narrowing is the trap rather than the convenience.
  let finding = "";
  let needsYou = false;
  const narrowed = () => Boolean(finding) || needsYou;

  // A thread the agent spoke in last is a thread waiting on the reader; one the reader spoke
  // in last is waiting on the agent. A resolved thread waits on nobody. Turns, not marks:
  // a reaction on a message is not the reader speaking, with one declared exception — a
  // token whose entry says `settles`, standing on the agent's latest message, is the
  // reader saying "seen, go on", and takes the thread out of the waiting list without a
  // second event. Take the ok back and the wait comes back, this being a reading of the
  // log rather than a state anything wrote; core reads the flag and never the name.
  const awaitsReader = (t) => {
    if (t.resolved) return false;
    const last = spoken(t).at(-1);
    if (last?.author !== "claude") return false;
    return !t.msgs.some(
      (m) =>
        isReaction(m) &&
        m.author === "user" &&
        m.parent === last.id &&
        tokenEntry(m.token)?.settles,
    );
  };

  // What a search reads: everything the panel shows of a thread, plus the part of the page
  // it is on — so "merge rule" finds the threads under that heading as well as the ones
  // that say the words. The label is the panel's own rendering of the anchor, which is what
  // the reader can see and therefore what they would search for.
  const threadWords = (t, group) =>
    [
      anchorLabel(t.root.anchor, t.root.about),
      group.label,
      ...t.msgs.map((m) => m.text ?? m.token),
    ]
      .join("\n")
      .toLowerCase();

  const inFilter = (t, group) =>
    (!needsYou || awaitsReader(t)) &&
    (!finding || threadWords(t, group).includes(finding));

  // The reconcile's one mover, shared by the list and the resolved disclosure: make
  // `parent`'s children `nodes`, in that order, touching nothing already in its place.
  // Not touching it matters beyond economy: reinserting a node restarts its CSS
  // animations, drops any focus and caret inside it, and swaps it out from under a
  // pressed pointer, which swallows the click. Stale nodes go first for the same
  // reason — with one removed mid-list, everything after it is exactly one place
  // forward, so the walk keeps those where they stand instead of reinserting each.
  function setChildren(parent, nodes) {
    const keep = new Set(nodes);
    for (const child of [...parent.children]) if (!keep.has(child)) child.remove();
    let cursor = parent.firstChild;
    for (const node of nodes) {
      if (node === cursor) cursor = cursor.nextSibling;
      else parent.insertBefore(node, cursor);
    }
  }

  const emptyNote = el(
    "div",
    "lf-empty",
    "No comments yet. Select any text on the page to comment on it, or use the box below.",
  );
  const waitingNote = el("div", "lf-empty", "Loading current comments…");
  // The page has comments and the reader's narrowing is standing between them and it. It
  // names the narrowing rather than saying nothing was found, because the reader may have
  // arrived here from a key or from a second tab and what is on screen has to say why.
  const noMatch = el("div", "lf-empty");
  function noMatchNote() {
    const said = finding
      ? needsYou
        ? `Nothing waiting on you says “${finding}”.`
        : `No comment says “${finding}”.`
      : "Nothing is waiting on you.";
    if (noMatch.textContent !== said) noMatch.textContent = said;
    return noMatch;
  }

  // The heading over a run of threads, kept across reconciles so a scroll position, a focus
  // ring and the sticky pin survive a poll. A button where the page still holds the heading
  // it names — pressing it takes the reader there, which is the same move a thread's quote
  // makes — and a plain line for the three runs that name no place (groupFor). A key never
  // changes kind, so the node a key holds never has to.
  const groupNodes = new Map();
  function groupNode(key, group) {
    let node = groupNodes.get(key);
    if (!node) {
      node = group.target
        ? el("button", "lf-group lf-pinned")
        : el("div", "lf-group lf-pinned");
      if (group.target) {
        node.type = "button";
        node.title = "Jump to this part of the page";
      }
      node.dataset.group = key;
      groupNodes.set(key, node);
    }
    if (node.textContent !== group.label) node.textContent = group.label;
    // The press is rewired on every reconcile and the word is not: a version activation
    // replaces the heading the group names with a new element, and the same sentence.
    if (group.target) node.onclick = () => scrollToElement(group.target);
    return node;
  }

  // A terminal event's row, keyed like everything else in the list so its clock can
  // refresh in place.
  function systemNode(e, text) {
    let div = threadsBox.querySelector(`:scope > .lf-system[data-id="${e.id}"]`);
    if (!div) {
      div = el("div", "lf-system");
      div.dataset.id = e.id;
    }
    if (div.textContent !== text) div.textContent = text;
    return div;
  }

  // The resolved disclosure, one <details> for the page's life: the user's
  // open/closed toggle is the browser's state, and it survives arrivals only if the
  // element does — the rebuild this replaced snapped it shut on every one.
  let resolvedBox = null;

  // A thread has one send in flight even though its reply draft has two views. wireInput's
  // private hold is still the right scope for every other composer, which has one control;
  // a reply adds this thread-scoped hold and announces it on the document bus so both Send
  // controls render the same fact. The promise is the post itself, because a queue would
  // serialize the duplicate rather than refuse it.
  const REPLY_FLIGHT_NEWS = "lf-reply-flight";
  const replyFlights = new Map(); // thread id -> post in flight
  const replyBusy = (id) => replyFlights.has(id);
  const tellReplyFlight = (id) =>
    document.dispatchEvent(new CustomEvent(REPLY_FLIGHT_NEWS, { detail: { id } }));

  function mirrorReplyFlight(ta, sync, id) {
    const update = (ev) => {
      if (ev.detail.id !== id) return;
      if (!ta.isConnected)
        return document.removeEventListener(REPLY_FLIGHT_NEWS, update);
      sync();
    };
    document.addEventListener(REPLY_FLIGHT_NEWS, update);
  }

  async function sendReply(t, text, raw, owns) {
    const id = t.root.id;
    if (replyBusy(id)) return null;
    const draftCtx = "reply:" + id;
    const flight = sendDraft(draftCtx, owns, (attempt) =>
      post({
        kind: "reply",
        parent: id,
        version: runtime.currentVersion,
        text,
        attempt,
      }),
    );
    replyFlights.set(id, flight);
    tellReplyFlight(id);
    try {
      return await flight;
    } finally {
      replyFlights.delete(id);
      tellReplyFlight(id);
    }
  }

  // One reply draft and one send path, however many views the thread has. The panel adds
  // an address and reveals the sent message; an inline conversation supplies neither.
  // Everything else — persistence, mirroring, the wire event and the focus landing — is
  // the thread's and is therefore stated once.
  function wireReply(t, input, send, { address, landed } = {}) {
    const draftCtx = "reply:" + t.root.id;
    input.value = loadDraft(draftCtx) ?? "";
    const sync = wireInput(input, {
      hint: "Reply",
      sends: "send",
      address,
      sendBtn: send,
      busy: () => replyBusy(t.root.id),
      // localStorage notifies other tabs but skips this document. A conversation's
      // inline and panel boxes are two views here, so reply drafts take the same bus
      // directly. Other draft kinds still have one view per document.
      save: (v) => {
        saveDraft(draftCtx, v);
        tellDraft(draftCtx, v);
      },
      send: async (text, raw) => {
        const sent = await sendReply(t, text, raw, () => input.value === raw);
        if (!sent) return;
        landed?.(sent);
        landTyping(input);
      },
    });
    sync();
    mirrorDraft(input, sync, draftCtx);
    mirrorReplyFlight(input, sync, t.root.id);
    return sync;
  }

  function conversationMessageNode(thread, message) {
    let node = thread.querySelector(
      `:scope > .lf-conversation-msg[data-event="${message.id}"]`,
    );
    if (node) {
      const time = node.querySelector("time");
      const when = ago(message.ts);
      if (time.textContent !== when) time.textContent = when;
      return node;
    }
    node = offer("div", `lf-conversation-msg ${message.author}`);
    node.dataset.event = message.id;
    const head = el("div", "lf-conversation-head");
    head.append(
      el("b", "", message.author === "claude" ? message.agent || "Agent" : "You"),
      el("time", "", ago(message.ts)),
    );
    const body = el("div", "lf-conversation-body");
    if (isReaction(message))
      body.append(
        el(
          "span",
          "lf-react-said",
          `${tokenEntry(message.token)?.glyph ?? ""} ${message.token}`.trim(),
        ),
      );
    else if (message.suggestion) body.textContent = message.text;
    else body.innerHTML = renderMarkdown(message.text);
    node.append(head, body);
    if (message.markup) {
      const open = offer("button", "lf-btn lf-conversation-open", "Open in Comments");
      open.onclick = () => showThread(message.id);
      node.append(open);
    }
    return node;
  }

  function conversationThreadNode(host, t) {
    let thread = host.querySelector(
      `:scope > .lf-conversation-thread[data-thread="${t.root.id}"]`,
    );
    if (!thread) {
      thread = offer("div", "lf-conversation-thread");
      thread.dataset.thread = t.root.id;
      thread.tabIndex = -1;
    }
    // Turns only: a reaction on a message is the panel's strip to show, and the seat is
    // the textual projection of the exchange.
    const messages = turns(t).map((message) =>
      conversationMessageNode(thread, message),
    );
    let tail;
    if (t.resolved) {
      const compose = thread.querySelector(":scope > .lf-say");
      if (compose?.contains(focused())) thread.focus({ preventScroll: true });
      tail = thread.querySelector(":scope > .lf-conversation-resolved");
      const settledBy =
        t.resolved.author === "claude"
          ? `✓ Resolved by ${t.resolved.agent || "Agent"}`
          : "✓ Resolved";
      if (!tail) tail = offer("div", "lf-conversation-resolved");
      if (tail.textContent !== settledBy) tail.textContent = settledBy;
    } else {
      tail = thread.querySelector(":scope > .lf-say");
      if (!tail) {
        tail = offer("div", "lf-say");
        const input = offer("textarea");
        const send = offer("button", "lf-btn primary", "Send");
        tail.append(input, send);
        wireReply(t, input, send);
      }
    }
    const work = thread.querySelector(":scope > .lf-work-line");
    setChildren(thread, [...messages, ...(work ? [work] : []), tail]);
    return thread;
  }

  function renderConversations(threads) {
    for (const host of document.querySelectorAll(
      ".lf-conversation[data-lf-conversation]",
    )) {
      const owner = elementById(host.dataset.lfConversation);
      const owned = threads.filter((thread) => {
        const anchor = thread.root.anchor;
        return (
          !thread.root.about &&
          anchor?.section === owner.id &&
          Object.keys(anchor).length === 1
        );
      });
      // Before the first comment, conversationBox's first-message composer is already
      // the complete view. An externally arriving root may find unsent first-message
      // words here, so the root does not get to take their only box. A hold-capable seat
      // stays reachable after every root so an ordinary conversation cannot remove the
      // stronger send route.
      if (!owned.length) continue;
      const first = host.lfFirstMessage;
      const hold = registry[owner.localName]?.["x-conversation"]?.hold;
      const pending = hold || loadDraft("say:" + owner.id) !== null ? first : null;
      const work = host.querySelector(":scope > .lf-work-line");
      setChildren(host, [
        ...(work ? [work] : []),
        ...owned.map((thread) => conversationThreadNode(host, thread)),
        ...(pending ? [pending] : []),
      ]);
    }
  }

  // The one number in the list's scroll-padding that CSS cannot work out: a run heading
  // sticks over the top of this box, and a long one wraps, so how much of the top is
  // covered is a measurement rather than a constant. The tallest, not the stuck one — the
  // browser is given one number to scroll by and cannot be told which heading will be under
  // the landing, and reserving more than a shorter heading needs only lands the thread a few
  // pixels lower.
  //
  // It follows the box rather than the log. Wrapping is a function of the list's width, and
  // the reader sets that themselves by dragging the panel's edge — a drag posts no event, so
  // a reconcile never came, and a heading that had grown from one line to two went on being
  // reserved for at one. Threads then landed under it, which is the whole defect this
  // number exists to prevent. Writing a custom property does not resize the observed box,
  // so the observer cannot feed itself.
  function paintHeadRoom() {
    // Not while the panel is shut, which is most of a page's life. Every heading measures
    // zero in `display: none`, so the answer is never the room a heading takes — it is the
    // absence of a panel, written at the cost of a forced layout on every reconcile for a
    // number no reader can be standing in. That cost is not theoretical: under a loaded
    // machine it delayed an event's acknowledgement past the window an undo is offered in,
    // and `test_an_action_response_accounts_for_its_gesture_without_a_follow_up_poll` lost
    // its press to a gesture that had not settled yet. The observer fires when the panel
    // opens — a box arriving is a resize — so the measurement lands the moment it means
    // something, which is also the only moment it can be right.
    if (!panelIsOpen()) return;
    const heads = [...threadsBox.querySelectorAll(".lf-pinned")];
    threadsBox.style.setProperty(
      "--lf-head-room",
      `${Math.max(0, ...heads.map((h) => h.offsetHeight))}px`,
    );
  }
  new ResizeObserver(paintHeadRoom).observe(threadsBox);

  // A thread's node is found where it already stands — the open list or the resolved
  // disclosure — and kept: the log is append-only, so a kept node only ever gains
  // messages and refreshes its clocks. A settlement transition reshapes a node: resolving
  // removes the reply box and reopening restores it, so either one rebuilds the node;
  // msgBodies carries the rendered bodies across. `grow` animates what this call creates,
  // for arrivals into a list the user is already looking at.
  function threadNode(t, grow) {
    const existing = threadsBox.querySelector(`.lf-thread[data-id="${t.root.id}"]`);
    const existingResolved =
      existing && !existing.querySelector(":scope > .lf-compose");
    if (existing && existingResolved === Boolean(t.resolved)) {
      const compose = existing.querySelector(":scope > .lf-compose");
      const tail =
        existing.querySelector(":scope > .lf-work-line") ??
        compose ??
        existing.querySelector(":scope > .lf-thread-actions");
      for (const m of turns(t)) {
        let msg = existing.querySelector(`:scope > .lf-msg[data-mid="${m.id}"]`);
        if (!msg) {
          msg = msgNode(m);
          if (grow) msg.classList.add("grow");
          existing.insertBefore(msg, tail);
        }
        // The head's clock, not any <time> a reply's own markup might carry.
        const time = msg.querySelector(":scope > .lf-msg-head time");
        const when = ago(m.ts);
        if (time.textContent !== when) time.textContent = when;
      }
      paintReactStrips(existing, t);
      return existing;
    }

    const div = el("div", "lf-thread");
    div.tabIndex = -1; // j/k focus target; the thread scope's Enter drops into its reply box
    div.dataset.id = t.root.id;
    if (grow) div.classList.add("grow");
    const label = anchorLabel(t.root.anchor, t.root.about);
    if (label) {
      const quote = el("blockquote", "lf-quote", label);
      // The quote is words and a press at once: it says which passage the comment is
      // about, and pressing it travels there. A drag across it is the reader taking the
      // words, so the travel stands down — the reading `offer` makes of its own
      // controls, which this is not one of.
      quote.onclick = (ev) => {
        if (ev.detail === 0 || !reachedForWords(quote)) scrollToThread(t.root.id);
      };
      div.append(quote);
    }
    turns(t).forEach((m) => div.append(msgNode(m)));
    paintReactStrips(div, t);
    if (!t.resolved) {
      const row = el("div", "lf-compose");
      const input = document.createElement("textarea");
      const send = el("button", "lf-btn primary lf-thread-send", "Send");
      row.append(input);
      div.lfSync = wireReply(t, input, send, {
        // The box's address, spoken by its own placeholder at all times ("Reply · g c 2")
        // — which is what a screen reader hears, the chip the chord paints being the eye's
        // copy of the same fact. Read off the list rather than off a number written here,
        // because the address is positional: resolving an early thread renumbers every one
        // after it without touching their nodes, and renderThreads repaints them all.
        address: () => {
          const num = addressed(COMMENTS).indexOf(div) + 1;
          return num ? addressLabel(COMMENTS, num) : "";
        },
        landed: (sent) => revealThread(sent.id),
      });
      const actions = el("div", "lf-thread-actions");
      const resolve = el("button", "lf-btn lf-resolve", "Resolve");
      // Resolving takes this node out of the open list and focus with it — the blind
      // drive fell to body here. Land where j would have gone: the thread that now
      // holds this one's place, else the previous, else the list. Which is read after
      // the trip, off the list the fold has already left (foldOut renames the node the
      // frame the log settles it), so the landing is a thread rather than the room the
      // pressed one is still giving back.
      // Disabled for the flight (the bulk-answer buttons' shape): the r key repeats while
      // held, and every repeat before the poll replaces this node would post the
      // same resolve again. Re-enabled for the one path that keeps the node — a
      // send that failed, where the press must stay pressable; where it went through,
      // the fold has made the whole node inert and there is nothing to re-enable into.
      resolve.onclick = async () => {
        const at = openThreads().indexOf(div);
        resolve.disabled = true;
        try {
          await post({ kind: "resolve", parent: t.root.id });
        } finally {
          resolve.disabled = false;
        }
        const kept = openThreads();
        (kept[at] ?? kept[at - 1] ?? threadsBox).focus({ preventScroll: true });
      };
      actions.append(send, resolve);
      div.append(row, actions);
    } else {
      const actions = el("div", "lf-thread-actions");
      const status = el("span");
      if (t.resolved.author === "claude") {
        // Said only where the reader was not the one who closed it. Their own resolve
        // needs no telling: they pressed it, and the disclosure they find it under is
        // already headed "Resolved". A thread closed from the other side settles with
        // nothing in this tab to watch it happen, so the page is the only thing that can
        // say who did.
        const by = t.resolved.agent || "Agent";
        status.append(el("span", "lf-resolved-by", `✓ Resolved by ${by}`));
      }
      const reopen = el("button", "lf-reopen lf-thread-action", "Reopen");
      reopen.onclick = async () => {
        reopen.disabled = true;
        try {
          await post({ kind: "unresolve", parent: t.root.id });
        } finally {
          reopen.disabled = false;
        }
        threadsBox
          .querySelector(`:scope > .lf-thread[data-id="${t.root.id}"]`)
          ?.focus({ preventScroll: true });
        showThread(t.root.id);
      };
      actions.append(status, reopen);
      div.append(actions);
    }
    return div;
  }

  // The strip under each of the agent's messages: every token the layer declares, the
  // ones the reader has put on that message reading pressed and wearing their word.
  // Press one to put it there — a reply carrying the token, on that message — and press it
  // again to take it back, an ordinary undo naming the reply. Rebuilt from the thread on
  // each reconcile rather than from the press, so a reaction arriving from another tab,
  // and an undo, land the same way. A resolved thread offers none: resolve is the floor
  // after which a reaction stops painting, on the page and here alike.
  function paintReactStrips(node, t) {
    for (const msg of node.querySelectorAll(":scope > .lf-msg")) {
      const m = t.msgs.find((x) => x.id === msg.dataset.mid);
      if (!m || m.author !== "claude") continue;
      let strip = msg.querySelector(":scope > .lf-react-strip");
      if (t.resolved) {
        strip?.remove();
        continue;
      }
      if (!strip) {
        strip = el("div", "lf-react-strip");
        strip.setAttribute("role", "group");
        strip.setAttribute("aria-label", "React to this reply");
        for (const pill of reactPills((name, pill) => pressStrip(m, name, pill)))
          strip.append(pill);
        msg.append(strip);
      }
      paintStanding(
        strip,
        t.msgs.filter((x) => isReaction(x) && x.author === "user" && x.parent === m.id),
      );
    }
  }
  // Which tokens stand on a target, painted on its strip: pressed, wearing the word, and
  // carrying the event a second press takes back. The reaction rides the pill rather than
  // a map beside it, so a reconcile that keeps the node keeps the fact with it.
  function paintStanding(strip, standing) {
    const by = new Map(standing.map((x) => [x.token, x]));
    for (const pill of strip.querySelectorAll(":scope > .lf-react")) {
      const on = by.get(pill.dataset.token) ?? null;
      pill.setAttribute("aria-pressed", on ? "true" : "false");
      pill.lfReaction = on;
    }
  }
  async function pressStrip(m, name, pill) {
    if (pill.lfReaction) await withdraw(pill.lfReaction);
    else
      await sendReaction(
        { kind: "reply", parent: m.id, version: runtime.currentVersion, token: name },
        pill,
        `${m.agent || "the agent"}'s reply`,
      );
    reactDone();
  }
  // The page whole, from the panel: the same strip, above the general box, aimed at
  // nothing in particular — the shape an unanchored comment already has. What stands
  // here is every bare reaction with no anchor; a press puts one there or takes it back.
  let pageStrip = null;
  function paintPageStrip(threads) {
    if (!Object.keys(registry.$reactions.tokens).length) return;
    if (!pageStrip) {
      pageStrip = el("div", "lf-react-strip lf-page-strip");
      pageStrip.setAttribute("role", "group");
      pageStrip.setAttribute("aria-label", "React to the page");
      for (const pill of reactPills(pressPage)) pageStrip.append(pill);
      generalRow.before(pageStrip);
    }
    paintStanding(
      pageStrip,
      threads
        .filter((t) => bareReaction(t) && !t.resolved && !t.root.anchor)
        .map((t) => t.root),
    );
  }
  // About the layer in design mode, as the general box's own comment is: the subject is
  // decided at the send, by the mode standing then.
  async function pressPage(name, pill) {
    if (pill.lfReaction) {
      await withdraw(pill.lfReaction);
      reactDone();
      return;
    }
    const event = { kind: "comment", version: runtime.currentVersion, token: name };
    if (designIsOn()) event.about = "layer";
    await sendReaction(event, pill, "the page");
    reactDone();
  }

  // A thread the log has resolved and the open list is still holding. Its place is not
  // given up in the frame the log settles it: the node stays where it stood, says what
  // was done to it on the control that was pressed, and folds, so the threads under it
  // rise where the eye can follow instead of arriving somewhere else. The disclosure
  // gets the thread when the fold is over, which is what keeps one node per thread the
  // whole way through.
  //
  // Driven from the reconcile rather than from the press, because the log is what
  // resolves a thread and a resolve with no gesture behind it — a second tab's, or the
  // agent's — takes the same room out of the same list. That is the case that needs the
  // motion more: nothing in this tab moved, so the fold is the only thing saying so.
  //
  // Everything that walks the list asks for .lf-thread, so the one rename takes the
  // node out of j/k, out of the g addresses, out of x's press and out of what the panel
  // repaints, in a stroke: what stands there is room, not a thread. `inert` says the
  // same to the pointer and the tab order, so the fold can't be pressed a second time
  // or typed into on its way out.
  //
  // Null where there is nothing to fold: a thread this page never drew open, or a
  // reader who asked for less motion, for whom the room goes in the frame it always did.
  const folding = new Map(); // thread id -> the node folding out of the open list
  function foldOut(t) {
    const going = folding.get(t.root.id);
    // For as long as it stands in the list, which is the whole of what the record
    // claims. A reader who reopens a thread mid-fold has that render drop the folding
    // node from the list, and the entry left behind names a node in nothing: handed
    // back when they settle the thread again, it would stand a spent animation where
    // the thread is, saying what the thread said before it reopened, and the thread
    // would leave with no fold at all. The node's own connectedness is that fact, read
    // here rather than written from wherever a node leaves the list, which is the
    // difference between one writer and every caller of setChildren remembering.
    // Dropped rather than passed over, because the two returns below leave without
    // setting one, and an entry over a thread nothing is folding hides that thread
    // from the disclosure that should be holding it by then.
    if (going?.isConnected) return going;
    folding.delete(t.root.id);
    const node = threadsBox.querySelector(
      `:scope > .lf-thread[data-id="${t.root.id}"]`,
    );
    if (!node) return null;
    // Measured before anything about the node changes, and stated as a border box —
    // the measurement to hand is the rendered one, and .lf-going sizes to match. The
    // border and padding go with the height because border-box floors the box at
    // their sum: left standing, they would hold 22px open under a height of zero.
    const style = getComputedStyle(node);
    const from = {
      height: node.getBoundingClientRect().height + "px",
      marginBottom: style.marginBottom,
      borderTopWidth: style.borderTopWidth,
      borderBottomWidth: style.borderBottomWidth,
      paddingTop: style.paddingTop,
      paddingBottom: style.paddingBottom,
      opacity: 1,
    };
    const to = Object.fromEntries(Object.keys(from).map((k) => [k, "0px"]));
    to.opacity = 0;
    const played = motion(node, [from, to], FOLD_MS);
    if (!played) return null;
    // The control the press was made on states the outcome where it stood. It needs no
    // reservation for the longer word: Send and Resolve hold the two edges, so the
    // longer outcome takes room from the gap and moves neither edge. Send stays in the
    // row with visibility hidden, keeping the same room without reading as live.
    node.querySelector(":scope > .lf-thread-actions > .lf-resolve").textContent =
      "✓ Resolved";
    node.className = "lf-going";
    node.inert = true;
    // A key on screen is a key that works, and this box's placeholder was still
    // offering the address the thread under it has just taken: the repaint every other
    // reply box gets is the trailing loop's, which asks for .lf-thread and so no longer
    // finds this one. Painted here, from the same map, at the one moment the answer
    // changes — the address is gone the frame the log settles the thread, and what the
    // box says on its way out is "Reply" and no promise.
    node.lfSync();
    folding.set(t.root.id, node);
    // Straight off the promise, and nothing between: motion() holds the last keyframe
    // while this direct reaction makes that frame true by removing the node, then its
    // shared reaction releases the effect. Deferring this cleanup past that contract
    // would put the whole thread back before it goes. What holds the line is
    // test_the_fold_never_paints_a_frame_that_undoes_the_last, since no held frame can
    // see it.
    played.finished.then(() => {
      // This node's own entry, never whatever the thread's key holds now: a fold the
      // line above superseded is still running, and the older one finishing must not
      // take the live one's record with it.
      if (folding.get(t.root.id) === node) folding.delete(t.root.id);
      node.remove();
      renderPanel();
    });
    return node;
  }

  // One writer for every local work line. Which box it stands in is the subject's — a
  // thread's complete or inline seat, a widget's declared conversation, or a prose
  // widget itself — while the sentence, silence word, and clock are identical. Lines are
  // kept across polls so an unchanged claim is not announced again every two seconds.
  function paintWorkLine(host, update, before, wanted) {
    if (!host) return;
    const { kind, id } = update.target;
    let line = [...host.children].find(
      (child) =>
        child.matches(".lf-work-line") &&
        child.dataset.subjectKind === kind &&
        child.dataset.subjectId === id,
    );
    if (!line) {
      line = el("div", "lf-work-line lf-ui");
      line.dataset.lfGen = "1";
      line.dataset.subjectKind = kind;
      line.dataset.subjectId = id;
      line.append(el("span"), el("time"));
    }
    const next = before ?? null;
    if (line.parentElement !== host || line.nextSibling !== next)
      host.insertBefore(line, next);
    wanted.add(line);
    const what = line.firstElementChild;
    const when = line.lastElementChild;
    // Written only on change, like the message clocks beside it: an unchanged poll must
    // not hand the reader's screen reader the same sentence every two seconds.
    const said = `${update.agent || agentName()} is on this — ${update.text}`;
    if (what.textContent !== said) what.textContent = said;
    // A claim of work nobody has renewed, said in a word. The banner cannot answer for
    // this seat: every `leaf status … --on` write refreshes the page's own line, so one
    // delegate still reporting keeps the banner green while another's claim ages here —
    // the fleet's dead-row failure one level down, and the reason the roster says this
    // in words rather than leaving it to a tint. Both of the banner's own questions,
    // asked here by the same two predicates: gone unrenewed too long, or left behind by
    // a turn that ended. A local line is written by the command that writes the claim, so a
    // seat answering either question differently would have the page arguing with
    // itself about one silence. `ago` is still rendered whole beside the word rather
    // than reworded to absorb it. The cell is added and removed rather than hidden,
    // because a hidden one still reads out in the thread's text.
    let cold = line.querySelector(":scope > .lf-work-quiet");
    const turnClosed =
      update.session && update.session === claimState().claimingSession
        ? claimState().agentTurnClosed
        : null;
    if (quietSince(update.ts) || droppedAt(update.ts, turnClosed)) {
      if (!cold) line.insertBefore(el("span", "lf-work-quiet", "quiet"), when);
    } else cold?.remove();
    const age = ago(update.ts);
    if (when.textContent !== age) when.textContent = age;
  }

  function widgetWorkSeat(owner) {
    const work = registry[owner.localName]?.["x-work"];
    if (!work || !matchesWhen(owner, work.when)) return null;
    if (work.seat === "content") return { host: owner, before: null };
    const conversation = registry[owner.localName]["x-conversation"];
    if (!matchesWhen(owner, conversation.when)) return null;
    const host = [...owner.children].find(
      (child) =>
        child.matches(".lf-conversation[data-lf-conversation]") &&
        child.dataset.lfConversation === owner.id,
    );
    if (!host) return null;
    const before = [...host.children].find((child) => !child.matches(".lf-work-line"));
    return { host, before: before ?? null };
  }

  // Every local seat for every typed subject. The merged x-work declaration decided at
  // the CLI boundary whether a widget could safely carry one and tells this reading which
  // of the two general seats to use. Core still knows no content-widget tag name. A claim
  // created on a later version cannot leak backward into a pinned historical page.
  function paintWorkLines() {
    const wanted = new Set();
    const claims = claimState().claimsHeld
      ? updateSequence().filter(
          (update) => update.source === "claim" && update.disposition === "effective",
        )
      : [];
    for (const update of claims) {
      const { kind, id } = update.target;
      if (kind === "thread") {
        const thread = threadList.find((candidate) => candidate.root.id === id);
        if (!thread || thread.resolved) continue;
        const complete = threadsBox.querySelector(`.lf-thread[data-id="${id}"]`);
        paintWorkLine(
          complete,
          update,
          complete?.querySelector(":scope > .lf-compose"),
          wanted,
        );
        for (const inline of document.querySelectorAll(
          `.lf-conversation-thread[data-thread="${id}"]`,
        ))
          paintWorkLine(
            inline,
            update,
            inline.querySelector(":scope > .lf-say"),
            wanted,
          );
        continue;
      }
      if (kind !== "widget" || update.version > runtime.currentVersion) continue;
      const owner = elementById(id);
      if (!owner || inChrome(owner)) continue;
      const seat = widgetWorkSeat(owner);
      if (seat) paintWorkLine(seat.host, update, seat.before, wanted);
    }
    for (const line of pageQueryAll(".lf-work-line"))
      if (!wanted.has(line)) line.remove();
  }

  // The DOM is the one record of what's rendered, reconciled against the log: nodes the
  // list already holds are kept, and only what the log changed is added, moved, or
  // dropped. The rebuild this replaced destroyed every node on every render and then
  // hand-restored the reader's place — scroll offset, focused thread, caret — and what
  // no restore could give back was identity: nothing could animate, one send route kept
  // focus and the other dropped it, and a user's own comment landed below the fold
  // of a list put back exactly where it was. Nodes surviving is what deleted all of it.
  function renderThreads(all) {
    // The conversations. A bare reaction is paint on the page and a pill on the page
    // row, and counts for nothing here: no card, no address, no place in the walk.
    const threads = all.filter(conversational);
    const open = threads.filter((t) => !t.resolved);
    // The page's outline, read once for the whole reconcile: every thread asks it where it
    // stands and which run it belongs to.
    const outline = pageOutline();
    const group = new Map(threads.map((t) => [t, groupFor(t, outline)]));
    // Where the reader's own narrowing applies, and the only place it does: the page's
    // marks, the inline conversation seats and the banner's count are readings of the log
    // and go on saying what the log says. What the panel shows is the panel's business.
    const shown = inPageOrder(threads).filter((t) => inFilter(t, group.get(t)));
    const resolved = shown.filter((t) => t.resolved);
    // Newcomers settle in (`grow`) only when the user already has the list in front
    // of them: the first populated render is the page loading, not news arriving, and a
    // node animated while the panel is closed would replay the moment it opens.
    // (Reduced motion isn't asked here: grow is a CSS animation, and those are the
    // theme's one global guard's to stop.)
    const grow =
      panelIsOpen() && Boolean(threadsBox.querySelector(":scope > .lf-thread"));

    const wanted = [];
    if (!threads.length) wanted.push(emptyNote);
    else if (!shown.length) wanted.push(noMatchNote());
    // Walked in the page's order rather than the log's (inPageOrder), because that is the
    // order every other reading of these threads is in: the marks down the page, the walk
    // j/k makes, the digits g c spells. A thread on its way out still stands between its
    // neighbours while it folds (foldOut), which is why the walk is over the whole list
    // with the resolved ones taken at their own place. The first nine open threads are
    // addressable (g c 1–9), in the order j/k walk; past nine, digits stop and j/k still
    // reach everything. A folding thread takes no address and is walked by nothing: the log
    // has already settled it, and only its room is still here.
    //
    // A heading goes in wherever the run changes, so the reader scrolling a list four
    // thousand pixels long is told which part of the page they are reading about — and,
    // the headings being sticky, is still told halfway down a long run.
    let standing = null;
    for (const t of shown) {
      // A resolved thread is either still giving its room back in place, or gone from this
      // list entirely and rebuilt under the disclosure below.
      const node = t.resolved ? foldOut(t) : threadNode(t, grow);
      if (!node) continue;
      const here = group.get(t);
      if (here.key !== standing) {
        standing = here.key;
        if (here.label) wanted.push(groupNode(here.key, here));
      }
      wanted.push(node);
    }
    for (const e of runtime.events) {
      if (e.kind === "done") wanted.push(systemNode(e, `✓ Approved ${ago(e.ts)}`));
    }
    if (resolved.length) {
      if (!resolvedBox) {
        resolvedBox = el("details", "lf-details");
        resolvedBox.append(el("summary", "lf-pinned"));
      }
      const summary = resolvedBox.firstChild;
      // Counted off what the panel is showing, listed off the page: a thread still folding
      // out of the open list is resolved and says so in the count from the first frame, and
      // is rebuilt in here when its fold is done rather than standing in two places at
      // once. Under a narrowing the count is of the resolved threads that match it, for the
      // same reason the head says "Showing 3 of 24" — a disclosure promising five where the
      // list holds one is the trap the head exists to close.
      const said = `Resolved (${resolved.length})`;
      if (summary.textContent !== said) summary.textContent = said;
      setChildren(resolvedBox, [
        summary,
        ...resolved
          .filter((t) => !folding.has(t.root.id))
          .map((t) => threadNode(t, false)),
      ]);
      wanted.push(resolvedBox);
    }
    // A narrowing can take the thread the reader is standing in out of the list —
    // answering the last one waiting on the reader is exactly that — and a removed node drops
    // focus to body, which hands the next Space to the page behind the panel. Land them on
    // the list, where Escape lands them and j/k can walk on from.
    const standingIn = threadsBox.contains(focused());
    setChildren(threadsBox, wanted);
    if (standingIn && !threadsBox.contains(focused()))
      threadsBox.focus({ preventScroll: true });
    paintHeadRoom();
    // A thread's widget markup is authored too, but it arrives after the page's startup
    // capture. Take its baseline on the first frame it is connected, before a reader can
    // act on it; later reconciles keep the first capture rather than mistaking a live
    // choice for authored state. Thread markup is frozen in its event, so unlike page
    // markup it has no version window to move under.
    captureAuthoredFacets(threadsBox);
    // A comment carries whatever widget markup the gate allows, so the panel holds the
    // same scroll boxes the page does, in a column half the width — and reachScrollers
    // wants two things that are only true here, after this line. A message body is built
    // detached, where `getComputedStyle` answers "" for every property, so a sweep at the
    // point the body is filled tagged nothing at all and had done since it was written,
    // reading like coverage the whole time. And a widget in that body upgrades on being
    // connected, not on being written, so the queue it registers its render with
    // (`settling`) has the promise only once this reconcile has appended it — which is
    // why the wait is here rather than a snapshot taken earlier. The queue is read, never
    // joined: nothing about the page's own first anchor pass waits on a message.
    Promise.allSettled(settling).then(() => reachScrollers(threadsBox));

    // Each reply box speaks its own address, repainted after ordering because resolving an
    // early thread renumbers everything after it — and read off the list this reconcile has
    // just written, which is why the loop is here and not where the boxes were built.
    for (const div of openThreads()) div.lfSync();
    toggleBtn.textContent = `Comments (${open.length})`;
    paintNarrowing(open, shown);
    // The anchor pass wrote its record before this list existed, and this reconcile may have
    // built the nodes that wear it. Both passes therefore repaint it: the one that changes
    // the record, and the one that changes what the record is painted on.
    paintThreadQuotes();
    paintHere(); // the j/k and g rows, and an armed window's chips, stand on this list
    // Narrowing and reconciliation can move another card under a pointer that did not
    // move. Read :hover after the browser has laid out this list, in refreshHover's frame.
    refreshHover();
  }

  // An unresolved hold thread is the pause. Derive the mark from the thread fold so
  // resolution removes it and undo restores it without a second state store.
  function renderHolds(threads) {
    for (const node of document.querySelectorAll("[data-lf-held]"))
      node.removeAttribute("data-lf-held");
    for (const thread of threads) {
      if (thread.resolved || !thread.root.holds) continue;
      const target = elementById(thread.root.holds);
      if (target && !inChrome(target)) target.dataset.lfHeld = thread.root.id;
    }
  }

  // The two surfaces that say what the narrowing is doing, written together because they
  // are one fact told twice: how much of the conversation is in front of the reader, and
  // how much of it is still theirs to answer. One writer, so the phase before the log has
  // been read and the phase after it cannot come to spell the same state differently.
  //
  // The banner counts what the page has; the head says how much of that is on screen. They
  // differ only while a narrowing stands, which is exactly when the reader needs telling
  // that the list is not the whole of it — and there is nothing to tell where the page has
  // no open threads to narrow.
  function paintNarrowing(open, shown) {
    const showing = shown.filter((t) => !t.resolved).length;
    panelTitle.textContent =
      narrowed() && open.length ? `Showing ${showing} of ${open.length}` : "Comments";
    const waiting = open.filter(awaitsReader).length;
    needsBtn.textContent = waiting ? `Waiting on you (${waiting})` : "Waiting on you";
    // Pressable while it stands pressed, so the reader can always let it go; dead only when
    // there is nothing for it to show and it is not the thing hiding the list.
    needsBtn.disabled = !needsYou && !waiting;
  }

  // Re-render the list alone, for the one change that is the panel's own rather than the
  // log's: the reader narrowing it. Nothing about the page moved, so the anchor pass is not
  // asked again — the list is rebuilt from the record it already wrote.
  function renarrow() {
    if (runtime.statePhase !== "ready") return;
    renderThreads(threadList);
    paintWorkLines();
    // A new set of results starts at its own beginning. Keeping the old offset lands the
    // reader in the middle of a shorter list, or past the end of it, over a change they
    // made a keystroke at a time.
    threadsBox.scrollTop = 0;
  }
  findInput.addEventListener("input", () => {
    finding = findInput.value.trim().toLowerCase();
    renarrow();
  });
  needsBtn.onclick = () => {
    needsYou = !needsYou;
    needsBtn.setAttribute("aria-pressed", String(needsYou));
    needsBtn.classList.toggle("on", needsYou);
    renarrow();
  };
  // Everything the reader narrowed, let go at once — what Escape in the find box does, and
  // what a thread arriving from outside the narrowing needs before it can be revealed.
  function widen() {
    if (!narrowed()) return false;
    finding = "";
    needsYou = false;
    findInput.value = "";
    needsBtn.setAttribute("aria-pressed", "false");
    needsBtn.classList.remove("on");
    renarrow();
    return true;
  }

  // The panel's side of what the anchor pass drew, read off that pass's own record so the
  // two views can't disagree: a passage rewritten in a later version has no home to jump to,
  // and a dead-looking link is worse than one that says so. Called by the pass that writes
  // the record, and again by a narrowing that rebuilt the nodes the record was painted on.
  function paintThreadQuotes() {
    const threads = new Map(threadList.map((t) => [t.root.id, t]));
    for (const div of openThreads()) {
      const quote = div.querySelector(".lf-quote");
      if (!quote) continue;
      // The words too, for the same reason the class below is repainted here rather than
      // written where the node was built. An element anchor is labelled with its item's
      // own opening words, and the item may be a widget an agent sent — built by this
      // same reconcile and not yet in the document when the node wearing the label was
      // made, so the reading came back empty and the label fell to the bare id. The
      // reconcile keeps a node it has already built, so nothing else ever asked again:
      // `§ off-slip` stood where `§ options · If their release comes and goes…` belonged,
      // for the life of the tab.
      const thread = threads.get(div.dataset.id);
      const said = thread && anchorLabel(thread.root.anchor, thread.root.about);
      if (said && quote.textContent !== said) quote.textContent = said;
      const found = isMarked(div.dataset.id);
      quote.classList.toggle("detached", !found);
      quote.title = found
        ? "Jump to this passage"
        : "This passage can't be identified in the version you're viewing";
    }
  }

  // A kept node may still be moved by a later reconcile, and reinsertion restarts CSS
  // animations — so the class comes off the moment its animation has run. A node grown
  // while its list was off-screen never ran one; the panelOpen gate above is what keeps
  // that replay from greeting the panel's next open.
  threadsBox.addEventListener("animationend", (ev) =>
    ev.target.classList.remove("grow"),
  );

  // Landing belongs to the list, not to whatever moved the focus. The list already says
  // which of its own edges cannot be stood on — `scroll-padding`, room for a stuck
  // heading and for a ring — and every route that could reach a thread was scrolling it
  // into that band for itself, so a route that did not scroll got nothing. A press does
  // not: the browser focuses the card under the pointer and scrolls nothing, so a list
  // nudged a dozen pixels leaves the first card of a run two pixels under its heading,
  // which is the whole of an inset ring's top run and reads as a card with three sides.
  // The routes that resolve a thread rather than press one — a page mark's comment note,
  // the thread a resolve or a reopen hands the reader on to — landed only by chance of
  // having remembered the line.
  //
  // Focus is the one fact all of them share, so the landing hangs off that and each of
  // them gives up its copy. Three callers still write this list's scroll, and each says
  // something focus cannot: `stepThread` for the press at either end of the walk, which
  // moves no focus at all; `revealThread` for a deliberate centring, which runs after
  // the focus it follows and wins; and `landIn`, which puts the reader in a thread's box
  // and lands the thread around it, the same correction this makes and the reason a
  // reply box reached by key was never the case that was wrong.
  //
  // The thread holding the focus, not the card alone: the ring is the thread's, drawn
  // for `:focus-within`, so it is cut in the same place whether the reader is standing
  // on the card or writing in its box. `block: "nearest"` moves the least that clears
  // the band, so a control at the card's foot comes with it rather than going under.
  //
  // A press is the reader's hand, and it may be the start of a drag across the comment's
  // own words. Focus lands on the way down, so scrolling there takes the words out from
  // under the pointer and the selection runs on past where they stopped — measured at
  // three times the run the reader drew. A press therefore holds its landing until the
  // hand comes up, and gives it up altogether where the press was a drag for the
  // thread's own words: the question `offer` already asks of a click, read the same way,
  // since the selection's focus end is the character the button came up on.
  //
  // The hand comes up before the press's click, which is where a deliberate placement
  // begins — a quote jumping to its passage, a travel centring a widget in a reply. So
  // the order holds without a word between them: the landing is a correction under the
  // gesture, and whatever the gesture then asks for is later and wins.
  //
  // What the press lands is where it left the reader, which is not the same question as
  // which thread the focus moved to. A press on the thread the reader is already in
  // moves no focus and so was heard as nothing at all — and that is the reader's own
  // gesture: they are standing in a comment, the list carries a little, and they press
  // the card to bring it back. Asking the completed gesture instead of the focus event
  // costs a variable rather than buying one, and the walk's own end-of-clamp press is
  // the same shape one scope out.
  let pressing = false;
  const standing = () => focused()?.closest?.(".lf-thread");
  const land = (thread) => {
    if (thread && threadsBox.contains(thread))
      thread.scrollIntoView({ behavior: SCROLL, block: "nearest" });
  };
  threadsBox.addEventListener("pointerdown", () => (pressing = true));
  addEventListener(
    "pointerup",
    () => {
      const began = pressing;
      pressing = false;
      const thread = began && standing();
      if (thread && !reachedForWords(thread)) land(thread);
    },
    true,
  );
  threadsBox.addEventListener("focusin", () => {
    if (!pressing) land(standing());
  });

  // The panel and the page marks are two views of the same threads, and the paint pass
  // reports back to the list renderThreads just reconciled — always render them as a pair.
  function renderPanel() {
    if (runtime.statePhase !== "ready") {
      waitingNote.textContent =
        runtime.statePhase === "offline"
          ? "Current comments are unavailable while the server is offline."
          : "Loading current comments…";
      setChildren(threadsBox, [waitingNote]);
      toggleBtn.textContent = "Comments";
      // Nothing read yet, so nothing to count and nothing to narrow. The same writer, so
      // the button says exactly what it will say the moment the log arrives empty.
      paintNarrowing([], []);
      threadList = [];
      paintHere();
      return;
    }
    const threads = buildThreads();
    lastThreads = threads;
    renderHolds(threads);
    threadList = threads.filter(conversational);
    // The marks first, because the list is ordered by where they landed: one resolution of
    // every anchor, read by the page for its paint and by the panel for its order. Resolving
    // a second time for the order would be a second answer to where a thread is, free to
    // disagree with the first over a page that changed between them — and it would walk the
    // document's whole text again to say it.
    paintAnchors(threads);
    renderThreads(threads);
    renderConversations(threadList);
    paintPageStrip(threads);
    paintWorkLines();
  }

  // One answer to "show me that thread", whoever asks: a click on a mark out on the page
  // and a send that just landed both come here, with a thread's id or a message's. The
  // panel scrolls its own list — moving the page to a thread's passage is scrollToThread,
  // a different question — and flashes the thread. The flash takes over from a running
  // grow explicitly: both classes bind the element's one animation declaration, and the
  // send's confirmation is the one the gesture asked for.
  const listNode = (id) =>
    threadsBox.querySelector(`.lf-thread[data-id="${id}"], .lf-msg[data-mid="${id}"]`);

  function revealThread(id) {
    setPanel(true);
    const node = listNode(id);
    if (!node) return;
    const thread = node.closest(".lf-thread");
    node.scrollIntoView({
      behavior: SCROLL,
      block: node === thread ? "center" : "nearest",
    });
    thread.classList.remove("grow");
    thread.classList.add("flash");
    setTimeout(() => thread.classList.remove("flash"), 1300);
  }

  // The same ask, insisted on. Two callers mean the thread has to be on screen and cannot
  // see the narrowing they would be asking past: a press out on the page or in a message,
  // which knows nothing of the panel at all, and a comment the reader has just written,
  // which cannot be allowed to vanish into a narrowing it does not match. So the narrowing
  // goes rather than the thread.
  //
  // Every other reveal is a confirmation of something the reader was already watching — a
  // reply landing in a thread in front of them — and takes the list as it stands. A
  // narrowing that let go for having been used would be worse than one that hid something:
  // answering a thread is exactly how the reader empties the waiting-on-you list.
  function showThread(id) {
    setPanel(true);
    if (!listNode(id)) widen();
    // Showing a thread is an arrival in the panel, not a glimpse from the page. Focus is
    // the standing fact shared by the card and its mark, so the route that begins on a
    // painted passage has to end on the same focus target as j/k and the address chord.
    // preventScroll keeps this call out of the scroll: the list lands a thread that takes
    // the focus, and the reveal below is the deliberate placement that follows and wins.
    listNode(id)?.closest(".lf-thread")?.focus({ preventScroll: true });
    revealThread(id);
  }

  return {
    buildThreads,
    bareReaction,
    paintStanding,
    reactionsOn,
    reactionStanding,
    loadMarked,
    anchorLabel,
    openThreads,
    narrowed,
    awaitsReader,
    setChildren,
    paintWorkLines,
    widen,
    paintThreadQuotes,
    renderPanel,
    showThread,
    get threadList() {
      return threadList;
    },
    get needsYou() {
      return needsYou;
    },
    get pageStrip() {
      return pageStrip;
    },
  };
}
