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
import { anchorLabel } from "./messages.js";
import { awaitsAgent, awaitsUser } from "./model.js";

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

// Each panel owns its view intent. The reading above remains pure so package views can
// apply their own intent to the same threads without sharing this panel's controls.
export function createThreadNarrowing({ view, listRoot, readThreads, ready, repaint }) {
  // Replace the whole value on every change. A retained arrival can then distinguish
  // its own transition from a later choice by identity.
  let intent = DEFAULT_INTENT;
  const threadSearchActive = () => Boolean(intent.finding);
  const needsYou = () => intent.waiting === "user";
  const listedInPageOrder = () => intent.order === "page";
  const narrowed = () =>
    Boolean(intent.finding) ||
    intent.status !== "open" ||
    intent.waiting !== "all" ||
    intent.scope !== "all" ||
    intent.subject !== "all" ||
    intent.onlyGone;
  // Capture intent once for each list candidate. Its rows, summary and facets all
  // derive from the same reading.
  const model = (threads, groups = new Map()) =>
    narrowingReading(intent, threads, groups);

  function renarrow() {
    if (!ready()) return;
    const ticket = repaint();
    // Reset after the keyed list commits. The coordinator reports rejection; observe
    // either outcome because event listeners can discard this ticket.
    void ticket.then(
      () => (listRoot.scrollTop = 0),
      () => {},
    );
    return ticket;
  }

  function replaceIntent(changes) {
    intent = Object.freeze({ ...intent, ...changes });
  }

  function chooseFacet(kind, value) {
    if (kind === "order") {
      if (intent.order === value) return;
      replaceIntent({ order: value });
      return renarrow();
    }
    const next = transition(
      intent,
      kind,
      kind !== "gone" && intent[kind] === value ? "all" : value,
    );
    if (next === intent) return;
    intent = next;
    return renarrow();
  }

  function mount() {
    view.configure({
      initial: model([], new Map()).presentation,
      changeWords: (words) => {
        replaceIntent({ words, finding: words.trim().toLowerCase() });
        renarrow();
      },
      chooseFacet,
      toggleUser: () => chooseFacet("waiting", "user"),
      reset: () => widen(),
    });
  }

  // Order is the user's view of the list; it hides nothing and survives a reset.
  function clearNarrowing(nextStatus = "open") {
    const changed = narrowed() || intent.status !== nextStatus;
    intent = Object.freeze({
      ...DEFAULT_INTENT,
      status: nextStatus,
      order: intent.order,
    });
    view.setSearchWords("");
    return changed;
  }

  // A fallible optimistic arrival can put back the exact view the user was using.
  function retainNarrowing() {
    const retained = intent;
    let replacement = null;
    return {
      replaced: () => {
        replacement = intent;
      },
      restore: async (before = null) => {
        if (intent !== replacement) return false;
        // The arrival can reveal the refused thread before its first await. Renew the
        // lease then, but reject any user choice made while it awaits presentation.
        const preparing = before?.();
        const prepared = intent;
        await preparing;
        if (intent !== prepared) return false;
        intent = retained;
        view.setSearchWords(retained.words);
        await renarrow();
        return true;
      },
    };
  }

  function widen() {
    if (!clearNarrowing()) return false;
    renarrow();
    return true;
  }

  // A direct destination selects the lifecycle that contains the requested thread.
  function revealThread(id) {
    const thread = readThreads().find(
      (candidate) =>
        candidate.id === id || candidate.msgs.some((message) => message.id === id),
    );
    if (!thread) return false;
    clearNarrowing(thread.resolved ? "resolved" : "open");
    return renarrow();
  }

  return Object.freeze({
    model,
    mount,
    narrowed,
    needsYou,
    listedInPageOrder,
    threadSearchActive,
    retainNarrowing,
    revealThread,
    widen,
  });
}
