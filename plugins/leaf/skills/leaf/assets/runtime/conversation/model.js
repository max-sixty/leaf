/* The conversation log's version-independent thread fold. */
export function createThreadModel(dependencies) {
  const {
    elementById,
    markupAwaiting,
    registry,
    retractedIds,
    retractionFloors,
    runtime,
    takenBack,
  } = dependencies;

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

  // ---------- threads ----------
  // The fold this module last produced, which is what the reaction readings below
  // answer from: they are asked on every key-line paint and on every press of the bar,
  // and folding the whole log again for each would be a second answer to a question
  // the panel has just answered.
  let lastThreads = [];
  function buildThreads() {
    const threads = new Map();
    const threadFor = new Map();
    // The whole log, not this version's window: a conversation is not version-scoped, so
    // the panel shows the same threads whichever version is pinned and a retraction
    // settles a thread's state from wherever it was declared. interact.py's callers pass
    // upto=None for the same reason. Replay windows to currentRevision instead, and on any version
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
    const messages = new Map();
    for (const e of runtime.events) {
      // A gesture the reader took back settles nothing, whichever way it settled: the
      // log holds it and no reading of the log stands on it. The same sentence
      // interact.py's build_threads reads, because it is the same reading.
      if (withdrawn.has(e.id)) continue;
      if (e.kind === "comment") {
        // `resolved` is the event that currently closes the thread, or null. Either
        // side can close one, so a flag beside a second field naming who would be two
        // readings of one fact; the event answers both and carries its own author.
        const message = { ...e };
        messages.set(e.id, message);
        const thread = { root: message, msgs: [message], resolved: null };
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
      if (e.kind === "edit") {
        const message = messages.get(e.message);
        if (message) {
          message.text = e.text;
          message.edited = { id: e.id, seq: e.seq, ts: e.ts };
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
        const message = { ...e };
        messages.set(e.id, message);
        thread.msgs.push(message);
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
    lastThreads = [...threads.values()];
    return lastThreads;
  }

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
  // Whether a reaction still paints, and so can still be taken back: in an unresolved
  // thread, and answered by no turn — the same three the door refuses (`undo_error`).
  const reactionStanding = (e) => {
    const thread = lastThreads.find((t) => t.msgs.some((m) => m.id === e.id));
    return (
      Boolean(thread) &&
      !thread.resolved &&
      !thread.msgs.some((m) => m.parent === e.id && !isReaction(m))
    );
  };

  // ---------- whose turn a thread is ----------
  // A resolved thread waits on nobody. An agent comment opens a question; a reply leaves
  // one only when its prose flag says so or its own x-awaits markup still asks. Anyone
  // else speaking last hands the thread to the agent. Neither reading is the other's
  // negation, and both have to say so.
  //
  // Not the agent, rather than the reader: `author` is an open string on every message
  // contract, and the two written today are `user` and `claude`. A line from anywhere else
  // reads as owed an answer, which is the direction to err in — an unanswered word is
  // invisible to everyone, while one answer too many costs a reply. interact.py's
  // `awaits_agent` is the same sentence for the same reason.
  //
  // Turns, not marks: a reaction on a message is not the reader speaking. Structured
  // reply asks use the same x-awaits projection as the asks board rather than a parallel
  // event flag. The one declared exception runs the other way — a token whose entry
  // says `settles`, standing on the agent's latest message, is the reader saying "seen,
  // go on" and takes the thread out of the waiting list without a second event. Take the
  // ok back and the wait comes back, this being a reading of the log rather than a state
  // anything wrote; core reads the flag and never the token's name.
  //
  // `markupAwaiting` is the conversation reconciler's reading of those reply bodies. It
  // populates the map for every open last reply immediately before filtering or painting
  // the list; public callers use `awaitsReader` only after that render stage. Calling this
  // on a newly built fold before `renderThreads` would not yet have the structural half.
  const awaitsReader = (t) => {
    if (t.resolved) return false;
    const last = spoken(t).at(-1);
    if (last?.author !== "claude") return false;
    if (last.kind === "reply") {
      const structural = markupAwaiting(last);
      if (structural === false || (structural === null && !last.awaits)) return false;
    }
    return !t.msgs.some(
      (m) =>
        isReaction(m) &&
        m.author === "user" &&
        m.parent === last.id &&
        tokenEntry(m.token)?.settles,
    );
  };
  const awaitsAgent = (t) =>
    !t.resolved && spoken(t).length > 0 && spoken(t).at(-1).author !== "claude";

  // The widget whose seat a root stands in: an element anchor naming that widget and
  // carrying nothing else. `renderConversations` collects the seat's own view from this,
  // and the ask projection asks it of the same anchor — so the conversation the reader
  // can see standing in the cell is the one that takes the request off their list, and
  // the two surfaces cannot come to disagree about which conversation is the widget's.
  //
  // A reply whose root the log lost is its own root and carries no anchor, so it seats
  // nowhere. That is the honest answer: no cell on the page shows it either.
  const seatRoot = (t) =>
    !t.root.about && t.root.anchor && Object.keys(t.root.anchor).length === 1
      ? (t.root.anchor.section ?? null)
      : null;

  return {
    awaitsAgent,
    awaitsReader,
    bareReaction,
    buildThreads,
    conversational,
    isReaction,
    reactionStanding,
    reactionsOn,
    seatRoot,
    spoken,
    tokenEntry,
    turns,
  };
}
