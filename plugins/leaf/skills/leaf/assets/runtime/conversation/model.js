/* The conversation log's version-independent thread fold. */
export function createThreadModel(dependencies) {
  const { elementById, retractedIds, retractionFloors, runtime, takenBack } =
    dependencies;

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

  // ---------- whose turn a thread is ----------
  // The agent spoke last and the thread waits on the reader; anyone else spoke last and it
  // waits on the agent. A resolved thread waits on nobody, so neither reading is the
  // other's negation and both have to say so.
  //
  // Not the agent, rather than the reader: `author` is an open string on every message
  // contract, and the two written today are `user` and `claude`. A line from anywhere else
  // reads as owed an answer, which is the direction to err in — an unanswered word is
  // invisible to everyone, while one answer too many costs a reply. interact.py's
  // `awaits_agent` is the same sentence for the same reason.
  const awaitsReader = (t) => !t.resolved && t.msgs.at(-1).author === "claude";
  const awaitsAgent = (t) => !t.resolved && t.msgs.at(-1).author !== "claude";

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

  return { awaitsAgent, awaitsReader, buildThreads, seatRoot };
}
