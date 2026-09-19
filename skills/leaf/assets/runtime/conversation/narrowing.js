/* Search and faceted narrowing for the thread panel.

   State is one exclusive question: Open, On you, On agent, or Resolved. Scope and
   subject are optional refinements, so a reader cannot construct the impossible old
   combination "waiting on you and resolved". The conditional placement chip appears
   only when this page has a detached anchored thread to find.

   The panel title stays fixed. The search row discloses the controls; a narrowed
   view states its result and active facets even while those controls are closed.
   Reset clears every facet and the search together.

   These are the panel's own view. The page's marks, inline conversation seats and
   banner counts keep reading the whole log. No narrowing is stored: returning to a
   page should not silently hide conversation. Cards remain in the document while
   filtered so reply widgets keep their identity and the rest of the runtime can still
   read them by id. The list captures one immutable reader intent and checkpoints the
   resulting summary and facets with its rows; repainting that reading does not change
   native editing or disclosure state. */
import { runtime } from "../context.js";
import { anchorLabel } from "./messages.js";
import { awaitsAgent, awaitsReader } from "./model.js";
import { narrowingView, threadsBox } from "./panel-elements.js";
import { threadList } from "./state.js";

const choice = (kind, value, label, className = "") =>
  Object.freeze({ kind, value, label, className });
const group = (kind, label, choices) =>
  Object.freeze({ kind, label, choices: Object.freeze(choices) });

// Labels and choices are declarations, not facts recovered from rendered buttons.
const FACETS = Object.freeze([
  group("state", "Thread state", [
    choice("state", "open", "Open"),
    choice("state", "reader", "On you", "lf-needs"),
    choice("state", "agent", "On agent"),
    choice("state", "resolved", "Resolved"),
  ]),
  group("scope", "Thread scope", [
    choice("scope", "page", "Page"),
    choice("scope", "local", "Anchored"),
  ]),
  group("subject", "Thread subject", [
    choice("subject", "content", "Content"),
    choice("subject", "design", "Design"),
  ]),
  group("gone", "Thread placement", [choice("gone", "gone", "No longer here")]),
]);

const DEFAULT_INTENT = Object.freeze({
  words: "",
  finding: "",
  state: "open",
  scope: null,
  subject: null,
  onlyGone: false,
});
let intent = DEFAULT_INTENT;

// The narrowing as a value, replaced whole on every change, so a holder can ask whether
// the reader has changed it since by identity, as `retainNarrowing` does.
export const narrowingIntent = () => intent;
export const threadSearchActive = () => Boolean(intent.finding);
export const needsYou = () => intent.state === "reader";
export const narrowed = () =>
  Boolean(intent.finding) ||
  intent.state !== "open" ||
  Boolean(intent.scope || intent.subject || intent.onlyGone);

const labelFor = (kind, value) =>
  FACETS.find((facet) => facet.kind === kind)?.choices.find(
    (candidate) => candidate.value === value,
  )?.label;

const threadWords = (thread, threadGroup) =>
  [
    anchorLabel(thread.detached_from ?? thread.anchor, thread.root.about),
    threadGroup.label,
    ...thread.msgs.map((message) => message.text ?? message.token),
  ]
    .join("\n")
    .toLowerCase();

const matchesSearch = (reading, thread, threadGroup) =>
  !reading.finding || threadWords(thread, threadGroup).includes(reading.finding);
const matchesState = (reading, thread, value = reading.state) =>
  value === "resolved"
    ? Boolean(thread.resolved)
    : !thread.resolved &&
      (value === "reader"
        ? awaitsReader(thread)
        : value === "agent"
          ? awaitsAgent(thread)
          : true);
const matchesScope = (reading, thread, value = reading.scope) =>
  !value ||
  (value === "page"
    ? !thread.anchor && !thread.detached_from
    : Boolean(thread.anchor) || Boolean(thread.detached_from));
const matchesSubject = (reading, thread, value = reading.subject) =>
  !value || (value === "design") === (thread.root.about === "design");
const matchesGone = (reading, _thread, threadGroup, value = reading.onlyGone) =>
  !value || threadGroup.key === "gone";

const includesThread = (reading, thread, threadGroup) =>
  matchesSearch(reading, thread, threadGroup) &&
  matchesState(reading, thread) &&
  matchesScope(reading, thread) &&
  matchesSubject(reading, thread) &&
  matchesGone(reading, thread, threadGroup);

const count = (rows, predicate) => rows.filter(predicate).length;
const entryReading = (declaration, selected, amount, disabled, hidden = false) =>
  Object.freeze({ ...declaration, selected, amount, disabled, hidden });

// Counts are faceted: each chip answers how many results switching that facet to its
// value would show while every other standing filter remains. A static all-page count
// on "Page" would promise threads the selected Open/Resolved state then hid.
function presentationReading(reading, threads, shown, groups) {
  const rows = threads.map((thread) => ({ thread, group: groups.get(thread) }));
  const baseline = threads.filter((thread) =>
    reading.state === "resolved" ? thread.resolved : !thread.resolved,
  ).length;
  const lifecycle = reading.state === "resolved" ? "resolved" : "open";
  const amount =
    shown.length === baseline ? `${shown.length}` : `${shown.length} of ${baseline}`;
  const summary = [
    `${amount} ${lifecycle} ${baseline === 1 ? "thread" : "threads"}`,
    reading.state === "reader" || reading.state === "agent"
      ? labelFor("state", reading.state)
      : null,
    reading.scope ? labelFor("scope", reading.scope) : null,
    reading.subject ? labelFor("subject", reading.subject) : null,
    reading.onlyGone ? labelFor("gone", "gone") : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const stateAmounts = new Map();
  for (const declaration of FACETS[0].choices) {
    const switched = count(
      rows,
      ({ thread, group }) =>
        matchesSearch(reading, thread, group) &&
        matchesState(reading, thread, declaration.value) &&
        matchesScope(reading, thread) &&
        matchesSubject(reading, thread) &&
        matchesGone(reading, thread, group),
    );
    stateAmounts.set(declaration.value, switched);
  }
  const facetAmount = (kind, value) =>
    count(rows, ({ thread, group }) => {
      if (!matchesSearch(reading, thread, group) || !matchesState(reading, thread))
        return false;
      if (kind !== "scope" && !matchesScope(reading, thread)) return false;
      if (kind !== "subject" && !matchesSubject(reading, thread)) return false;
      if (kind !== "gone" && !matchesGone(reading, thread, group)) return false;
      if (kind === "scope") return matchesScope(reading, thread, value);
      if (kind === "subject") return matchesSubject(reading, thread, value);
      return matchesGone(reading, thread, group, true);
    });

  const renderedGroups = FACETS.map((facet) =>
    Object.freeze({
      kind: facet.kind,
      label: facet.label,
      choices: Object.freeze(
        facet.choices.map((declaration) => {
          if (facet.kind === "state") {
            const switched = stateAmounts.get(declaration.value);
            const selected = reading.state === declaration.value;
            return entryReading(
              declaration,
              selected,
              switched,
              !selected && !switched,
            );
          }
          const switched = facetAmount(facet.kind, declaration.value);
          const selected =
            facet.kind === "gone"
              ? reading.onlyGone
              : reading[facet.kind] === declaration.value;
          return entryReading(
            declaration,
            selected,
            switched,
            !selected && !switched,
            facet.kind === "gone" && !switched && !selected,
          );
        }),
      ),
    }),
  );
  const reader = renderedGroups[0].choices.find(
    (candidate) => candidate.value === "reader",
  );
  return Object.freeze({
    summary,
    hidden:
      !reading.finding &&
      reading.state === "open" &&
      !reading.scope &&
      !reading.subject &&
      !reading.onlyGone,
    groups: Object.freeze(renderedGroups),
    readerTitle:
      reading.state === "reader"
        ? "Show open threads"
        : reader.disabled
          ? "Nothing is waiting on you"
          : "Show threads waiting on you",
  });
}

function emptyReading(reading) {
  return reading.finding
    ? `No shown thread matches “${reading.finding}”.`
    : reading.scope || reading.subject || reading.onlyGone
      ? "No threads match these filters."
      : reading.state === "reader"
        ? "Nothing is waiting on you."
        : reading.state === "agent"
          ? "Nothing is waiting on the agent."
          : reading.state === "resolved"
            ? "No resolved threads."
            : "No open threads.";
}

// Capture reader intent once for the list candidate. Its rows, empty state, summary,
// counts, selections, availability, and keyboard title all derive from this one value.
export function narrowingModel(threads, groups = new Map()) {
  const reading = intent;
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

function renarrow(repaintConversation) {
  if (runtime.statePhase !== "ready") return;
  const ready = repaintConversation();
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

const chooseFacet = (kind, value, repaintConversation) => {
  if (kind === "state")
    replaceIntent({
      state: intent.state === value && value !== "open" ? "open" : value,
    });
  else if (kind === "scope")
    replaceIntent({ scope: intent.scope === value ? null : value });
  else if (kind === "subject")
    replaceIntent({ subject: intent.subject === value ? null : value });
  else if (kind === "gone") replaceIntent({ onlyGone: !intent.onlyGone });
  renarrow(repaintConversation);
};

export function mountNarrowing(repaintConversation) {
  narrowingView.configure({
    initial: narrowingModel([], new Map()).presentation,
    changeWords: (words) => {
      replaceIntent({ words, finding: words.trim().toLowerCase() });
      renarrow(repaintConversation);
    },
    chooseFacet: (kind, value) => chooseFacet(kind, value, repaintConversation),
    reset: () => widen(repaintConversation),
  });
}

function clearNarrowing(nextState = "open") {
  const changed =
    Boolean(intent.finding) ||
    intent.state !== nextState ||
    Boolean(intent.scope || intent.subject || intent.onlyGone);
  intent = Object.freeze({ ...DEFAULT_INTENT, state: nextState });
  narrowingView.setSearchWords("");
  return changed;
}

// A direct destination may replace every panel refinement. A fallible optimistic
// transition captures this reading before it reveals that destination, so refusal can
// put back the exact list the reader was operating rather than merely selecting the
// thread's lifecycle again.
export function retainNarrowing(repaintConversation) {
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
      // Renew the lease after that synchronous work, then reject any reader change that
      // lands while the arrival is waiting.
      const preparing = before?.();
      const prepared = intent;
      await preparing;
      if (intent !== prepared) return false;
      intent = retained;
      narrowingView.setSearchWords(retained.words);
      await renarrow(repaintConversation);
      return true;
    },
  };
}

export function widen(repaintConversation) {
  if (!clearNarrowing()) return false;
  renarrow(repaintConversation);
  return true;
}

// A direct destination overrides the current view, including the default Open state.
// It clears unrelated refinements and selects the lifecycle value that can contain the
// requested thread, rather than making Resolved a special disclosure outside filtering.
export function revealThread(id, repaintConversation) {
  const thread = threadList().find(
    (candidate) =>
      candidate.root.id === id || candidate.msgs.some((message) => message.id === id),
  );
  if (!thread) return false;
  clearNarrowing(thread.resolved ? "resolved" : "open");
  return renarrow(repaintConversation);
}
