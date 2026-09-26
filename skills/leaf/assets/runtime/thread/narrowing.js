/* Search and faceted narrowing for the thread panel.

   Status, waiting party, location and subject are independent questions. Each has one
   optional selection; pressing the active choice clears that restriction. Resolved
   clears waiting because a resolved thread cannot owe a turn. Selecting a waiting
   party leaves Resolved for Open, preserving an already Open or unrestricted status.
   Counts describe the named subset under the other filters, including those status
   and waiting transitions. The
   conditional placement refinement finds detached anchored threads. Waiting choices
   select predicates, not exclusive ownership: a thread can await both parties, so
   their counts can overlap and an unrestricted view includes threads awaiting neither.

   Order is the panel's other view question: Page reads the list in the page's order,
   and Recent puts the thread spoken in last first. It hides nothing, so it is not a
   narrowing: it has no count, and Reset and a direct arrival keep it. Its day headings
   say which order the list is in.

   The panel title stays fixed. The search row's View button discloses the controls; a
   narrowed view states its result and active facets even while those controls are
   closed.
   Reset restores Open and clears the other refinements and search together.

   These are the panel's own view. The page's marks, inline thread seats and
   banner counts keep reading the whole log. No narrowing is stored: returning to a
   page should not silently hide thread. Cards remain in the document while
   filtered so reply widgets keep their identity and the rest of the runtime can still
   read them by id. The list captures one immutable user intent and checkpoints the
   resulting summary and facets with its rows; repainting that reading does not change
   native editing or disclosure state. */
import { runtime } from "../context.js";
import { anchorLabel } from "./messages.js";
import { awaitsAgent, awaitsUser } from "./model.js";
import { narrowingView, threadsBox } from "./panel-elements.js";
import { threadList } from "./state.js";

const choice = (kind, value, label, className = "") =>
  Object.freeze({ kind, value, label, className });
const group = (kind, label, choices) =>
  Object.freeze({ kind, label, choices: Object.freeze(choices) });

// Labels and choices are declarations, not facts recovered from rendered buttons.
const FACETS = Object.freeze([
  group("status", "Status", [
    choice("status", "open", "Open"),
    choice("status", "resolved", "Resolved"),
  ]),
  group("waiting", "Waiting on", [
    choice("waiting", "user", "You", "lf-needs"),
    choice("waiting", "agent", "Agent"),
  ]),
  group("scope", "Location", [
    choice("scope", "page", "Page"),
    choice("scope", "local", "Anchored"),
  ]),
  group("subject", "Subject", [
    choice("subject", "content", "Content"),
    choice("subject", "design", "Design"),
  ]),
  group("gone", "Placement", [choice("gone", "gone", "No longer here")]),
]);

const ORDER = group("order", "Order", [
  choice("order", "page", "Page"),
  choice("order", "recent", "Recent"),
]);

export const DEFAULT_INTENT = Object.freeze({
  order: "page",
  words: "",
  finding: "",
  status: "open",
  waiting: "all",
  scope: "all",
  subject: "all",
  onlyGone: false,
});
// The narrowing as a value, replaced whole on every change, so a holder can ask whether
// the user has changed it since by identity, as `retainNarrowing` does.
let intent = DEFAULT_INTENT;
export const threadSearchActive = () => Boolean(intent.finding);
export const needsYou = () => intent.waiting === "user";
export const inPageOrder = () => intent.order === "page";
export const narrowed = () =>
  Boolean(intent.finding) ||
  intent.status !== "open" ||
  intent.waiting !== "all" ||
  intent.scope !== "all" ||
  intent.subject !== "all" ||
  intent.onlyGone;

const labelFor = (kind, value) =>
  FACETS.find((facet) => facet.kind === kind)?.choices.find(
    (candidate) => candidate.value === value,
  )?.label;

const messageWords = (message) => {
  return [message.text ?? message.token, message.body.text]
    .filter(Boolean)
    .join("\n")
    .toLowerCase();
};

const threadWords = (thread, threadGroup) =>
  [
    anchorLabel(thread.detached_from ?? thread.anchor, thread.root.about),
    threadGroup.label,
    thread.title,
    ...thread.msgs.map(messageWords),
    ...(thread.summaries ?? []).map((summary) => summary.text),
  ]
    .join("\n")
    .toLowerCase();

// Exact message matches travel with the same immutable query that admits the card.
// Presentation can therefore disclose a covered original without reading words back
// from hidden DOM or turning a temporary search into retained user disclosure.
export const threadSearchReading = (thread, finding) =>
  Object.freeze({
    finding,
    messages: Object.freeze(
      finding
        ? thread.msgs
            .filter((message) => messageWords(message).includes(finding))
            .map((message) => message.id)
        : [],
    ),
  });

const matchesSearch = (reading, thread, threadGroup) =>
  !reading.finding || threadWords(thread, threadGroup).includes(reading.finding);
const matchesStatus = (reading, thread) =>
  reading.status === "all" ||
  Boolean(thread.resolved) === (reading.status === "resolved");
const matchesWaiting = (reading, thread) =>
  reading.waiting === "all" ||
  (reading.waiting === "user" ? awaitsUser(thread) : awaitsAgent(thread));
const matchesScope = (reading, thread) =>
  reading.scope === "all" ||
  (reading.scope === "page"
    ? !thread.anchor && !thread.detached_from
    : Boolean(thread.anchor) || Boolean(thread.detached_from));
const matchesSubject = (reading, thread) =>
  reading.subject === "all" ||
  (reading.subject === "design") === (thread.root.about === "design");
const matchesGone = (reading, _thread, threadGroup) =>
  !reading.onlyGone || threadGroup.key === "gone";

// Set one predicate. Counts describe that named subset, while a press on its active
// control clears it. Both paths share status transitions and their waiting reset.
export function transition(reading, kind, value) {
  const changes = kind === "gone" ? { onlyGone: value } : { [kind]: value };
  if (kind === "status" && value === "resolved") changes.waiting = "all";
  if (kind === "waiting" && value !== "all" && reading.status === "resolved")
    changes.status = "open";
  if (Object.entries(changes).every(([key, next]) => reading[key] === next))
    return reading;
  return Object.freeze({ ...reading, ...changes });
}

const includesThread = (reading, thread, threadGroup) =>
  matchesSearch(reading, thread, threadGroup) &&
  matchesStatus(reading, thread) &&
  matchesWaiting(reading, thread) &&
  matchesScope(reading, thread) &&
  matchesSubject(reading, thread) &&
  matchesGone(reading, thread, threadGroup);

const count = (rows, predicate) => rows.filter(predicate).length;
const entryReading = (declaration, selected, amount, disabled, hidden = false) =>
  Object.freeze({ ...declaration, selected, amount, disabled, hidden });

// Counts describe each named subset under the other standing filters, including
// Status clearing Waiting on. An active choice keeps its subset count; clearing it
// broadens the results rather than changing what its label counts.
function presentationReading(reading, threads, shown, groups) {
  const rows = threads.map((thread) => ({ thread, group: groups.get(thread) }));
  const baseline = threads.filter((thread) => matchesStatus(reading, thread)).length;
  const lifecycle = reading.status === "all" ? "" : `${reading.status} `;
  const amount =
    shown.length === baseline ? `${shown.length}` : `${shown.length} of ${baseline}`;
  const summary = [
    `${amount} ${lifecycle}${baseline === 1 ? "thread" : "threads"}`,
    reading.waiting === "all"
      ? null
      : `On ${reading.waiting === "user" ? "you" : "agent"}`,
    reading.scope !== "all" ? labelFor("scope", reading.scope) : null,
    reading.subject !== "all" ? labelFor("subject", reading.subject) : null,
    reading.onlyGone ? labelFor("gone", "gone") : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const order = Object.freeze({
    kind: ORDER.kind,
    label: ORDER.label,
    hidden: false,
    choices: Object.freeze(
      ORDER.choices.map((declaration) =>
        entryReading(declaration, reading.order === declaration.value, null, false),
      ),
    ),
  });
  const renderedGroups = FACETS.map((facet) =>
    Object.freeze({
      kind: facet.kind,
      label: facet.label,
      hidden: facet.kind === "waiting" && reading.status === "resolved",
      choices: Object.freeze(
        facet.choices.map((declaration) => {
          const selected =
            facet.kind === "gone"
              ? reading.onlyGone
              : reading[facet.kind] === declaration.value;
          const destination = transition(
            reading,
            facet.kind,
            facet.kind === "gone" ? true : declaration.value,
          );
          const switched = count(rows, ({ thread, group }) =>
            includesThread(destination, thread, group),
          );
          const recovery = facet.kind === "status" && declaration.value === "open";
          return entryReading(
            declaration,
            selected,
            switched,
            !selected && !recovery && !switched,
            facet.kind === "gone" && !switched && !selected,
          );
        }),
      ),
    }),
  );
  const userDestination = transition(reading, "waiting", "user");
  const userAvailable =
    reading.waiting === "user" ||
    rows.some(({ thread, group }) => includesThread(userDestination, thread, group));
  return Object.freeze({
    summary,
    hidden:
      !reading.finding &&
      reading.status === "open" &&
      reading.waiting === "all" &&
      reading.scope === "all" &&
      reading.subject === "all" &&
      !reading.onlyGone,
    groups: Object.freeze([order, ...renderedGroups]),
    userAvailable,
    userTitle:
      reading.waiting === "user"
        ? "Clear waiting filter"
        : userAvailable
          ? "Show threads waiting on you"
          : "Nothing shown is waiting on you",
  });
}

function emptyReading(reading) {
  return reading.finding
    ? `No ${reading.status === "all" ? "" : `${reading.status} `}threads match “${reading.finding}”.`
    : reading.scope !== "all" || reading.subject !== "all" || reading.onlyGone
      ? "No threads match these filters."
      : reading.waiting === "user"
        ? "Nothing is waiting on you."
        : reading.waiting === "agent"
          ? "Nothing is waiting on the agent."
          : reading.status === "resolved"
            ? "No resolved threads."
            : reading.status === "open"
              ? "No open threads."
              : "No threads.";
}

// Capture user intent once for the list candidate. Its rows, empty state, summary,
// counts, selections, availability, and keyboard title all derive from this one value.
export const narrowingModel = (threads, groups = new Map()) =>
  narrowingReading(intent, threads, groups);

export function narrowingReading(reading, threads, groups = new Map()) {
  const shown = Object.freeze(
    threads.filter((thread) => includesThread(reading, thread, groups.get(thread))),
  );
  return Object.freeze({
    intent: reading,
    shown,
    emptyText: emptyReading(reading),
    presentation: presentationReading(reading, threads, shown, groups),
  });
}

function renarrow(repaintThread) {
  if (runtime.statePhase !== "ready") return;
  const ready = repaintThread();
  // Reset after the keyed list has committed. The coordinator owns rejection reporting;
  // observe this continuation on both paths so an event listener that discards the
  // returned ticket cannot create another page-level rejection.
  void ready.then(
    () => (threadsBox.scrollTop = 0),
    () => {},
  );
  return ready;
}

function replaceIntent(changes) {
  intent = Object.freeze({ ...intent, ...changes });
}

const chooseFacet = (kind, value, repaintThread) => {
  if (kind === "order") {
    if (intent.order === value) return;
    replaceIntent({ order: value });
    return renarrow(repaintThread);
  }
  const next = transition(
    intent,
    kind,
    kind !== "gone" && intent[kind] === value ? "all" : value,
  );
  if (next === intent) return;
  intent = next;
  return renarrow(repaintThread);
};

export function mountNarrowing(repaintThread) {
  narrowingView.configure({
    initial: narrowingModel([], new Map()).presentation,
    changeWords: (words) => {
      replaceIntent({ words, finding: words.trim().toLowerCase() });
      renarrow(repaintThread);
    },
    chooseFacet: (kind, value) => chooseFacet(kind, value, repaintThread),
    toggleUser: () => chooseFacet("waiting", "user", repaintThread),
    reset: () => widen(repaintThread),
  });
}

// Order is kept: it is the user's view of the list, and hides nothing to recover.
function clearNarrowing(nextStatus = "open") {
  const changed = narrowed() || intent.status !== nextStatus;
  intent = Object.freeze({
    ...DEFAULT_INTENT,
    status: nextStatus,
    order: intent.order,
  });
  narrowingView.setSearchWords("");
  return changed;
}

// A direct destination may replace every panel refinement. A fallible optimistic
// transition captures this reading before it reveals that destination, so refusal can
// put back the exact list the user was operating rather than merely selecting the
// thread's lifecycle again.
export function retainNarrowing(repaintThread) {
  const retained = intent;
  let replacement = null;
  return {
    replaced: () => {
      replacement = intent;
    },
    // Restore only while the direct arrival's view still stands. Typing in the
    // optimistic reply box does not change this reading and must not strand a refused
    // Reopen under the Open filter; changing the search or facets deliberately does.
    restore: async (before = null) => {
      if (intent !== replacement) return false;
      // The supplied arrival may synchronously reveal the refused thread before its
      // first await, replacing the optimistic intent with another transition-owned one.
      // Renew the lease after that synchronous work, then reject any user change that
      // lands while the arrival is waiting.
      const preparing = before?.();
      const prepared = intent;
      await preparing;
      if (intent !== prepared) return false;
      intent = retained;
      narrowingView.setSearchWords(retained.words);
      await renarrow(repaintThread);
      return true;
    },
  };
}

export function widen(repaintThread) {
  if (!clearNarrowing()) return false;
  renarrow(repaintThread);
  return true;
}

// A direct destination overrides the current view, including the default Open state.
// It clears unrelated refinements and selects the lifecycle value that can contain the
// requested thread, rather than making Resolved a special disclosure outside filtering.
export function revealThread(id, repaintThread) {
  const thread = threadList().find(
    (candidate) =>
      candidate.root.id === id || candidate.msgs.some((message) => message.id === id),
  );
  if (!thread) return false;
  clearNarrowing(thread.resolved ? "resolved" : "open");
  return renarrow(repaintThread);
}
