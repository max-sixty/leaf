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
   read them by id. The list checkpoints this owner's immutable summary and facet
   reading with its rows; repainting a retained reading does not change reader intent. */
import { anchorLabel } from "./messages.js";
import { awaitsAgent, awaitsReader } from "./model.js";
import {
  filterControls,
  findInput,
  goneBtn,
  filterToggle,
  resetFilters,
  viewSummary,
  viewRow,
  scopeButtons,
  stateButtons,
  subjectButtons,
  threadsBox,
} from "./panel-elements.js";
import { runtime } from "../context.js";
import { threadList } from "./state.js";

let finding = "";
let state = "open";
let scope = null;
let subject = null;
let onlyGone = false;
export const threadSearchActive = () => Boolean(finding);

export const needsYou = () => state === "reader";
export const narrowed = () =>
  Boolean(finding) || state !== "open" || Boolean(scope || subject || onlyGone);

const threadWords = (thread, group) =>
  [
    anchorLabel(thread.detached_from ?? thread.anchor, thread.root.about),
    group.label,
    ...thread.msgs.map((message) => message.text ?? message.token),
  ]
    .join("\n")
    .toLowerCase();

const matchesSearch = (thread, group) =>
  !finding || threadWords(thread, group).includes(finding);
const matchesState = (thread, value = state) =>
  value === "resolved"
    ? Boolean(thread.resolved)
    : !thread.resolved &&
      (value === "reader"
        ? awaitsReader(thread)
        : value === "agent"
          ? awaitsAgent(thread)
          : true);
const matchesScope = (thread, value = scope) =>
  !value ||
  (value === "page"
    ? !thread.anchor && !thread.detached_from
    : Boolean(thread.anchor) || Boolean(thread.detached_from));
const matchesSubject = (thread, value = subject) =>
  !value || (value === "design") === (thread.root.about === "design");
const matchesGone = (_thread, group, value = onlyGone) =>
  !value || group.key === "gone";

export const inFilter = (thread, group) =>
  matchesSearch(thread, group) &&
  matchesState(thread) &&
  matchesScope(thread) &&
  matchesSubject(thread) &&
  matchesGone(thread, group);

export function noMatchText() {
  return finding
    ? `No shown thread matches “${finding}”.`
    : scope || subject || onlyGone
      ? "No threads match these filters."
      : state === "reader"
        ? "Nothing is waiting on you."
        : state === "agent"
          ? "Nothing is waiting on the agent."
          : state === "resolved"
            ? "No resolved threads."
            : "No open threads.";
}

const entries = (threads, groups) =>
  threads.map((thread) => ({ thread, group: groups.get(thread) }));
const count = (rows, predicate) => rows.filter(predicate).length;
const setButton = (button, { selected, amount, disabled }) => {
  button.setAttribute("aria-pressed", String(selected));
  button.classList.toggle("on", selected);
  const label = button.dataset.filterLabel;
  button.textContent = amount ? `${label} (${amount})` : label;
  button.disabled = disabled;
};

// Counts are faceted: each chip answers how many results switching that facet to its
// value would show while every other standing filter remains. A static all-page count
// on "Page" would promise threads the selected Open/Resolved state then hid.
export function narrowingReading(threads, shown, groups = new Map()) {
  const rows = entries(threads, groups);
  const baseline = threads.filter((thread) =>
    state === "resolved" ? thread.resolved : !thread.resolved,
  ).length;
  const lifecycle = state === "resolved" ? "resolved" : "open";
  const amount =
    shown.length === baseline ? `${shown.length}` : `${shown.length} of ${baseline}`;
  const facets = [
    `${amount} ${lifecycle} ${baseline === 1 ? "thread" : "threads"}`,
    state === "reader" || state === "agent"
      ? stateButtons[state].dataset.filterLabel
      : null,
    scope ? scopeButtons[scope].dataset.filterLabel : null,
    subject ? subjectButtons[subject].dataset.filterLabel : null,
    onlyGone ? goneBtn.dataset.filterLabel : null,
  ].filter(Boolean);
  const states = {};
  for (const value of Object.keys(stateButtons)) {
    const amount = count(
      rows,
      ({ thread, group }) =>
        matchesSearch(thread, group) &&
        matchesState(thread, value) &&
        matchesScope(thread) &&
        matchesSubject(thread) &&
        matchesGone(thread, group),
    );
    states[value] = Object.freeze({
      selected: state === value,
      amount,
      disabled: state !== value && !amount,
    });
  }
  const scopes = {};
  for (const value of Object.keys(scopeButtons)) {
    const amount = count(
      rows,
      ({ thread, group }) =>
        matchesSearch(thread, group) &&
        matchesState(thread) &&
        matchesScope(thread, value) &&
        matchesSubject(thread) &&
        matchesGone(thread, group),
    );
    scopes[value] = Object.freeze({
      selected: scope === value,
      amount,
      disabled: scope !== value && !amount,
    });
  }
  const subjects = {};
  for (const value of Object.keys(subjectButtons)) {
    const amount = count(
      rows,
      ({ thread, group }) =>
        matchesSearch(thread, group) &&
        matchesState(thread) &&
        matchesScope(thread) &&
        matchesSubject(thread, value) &&
        matchesGone(thread, group),
    );
    subjects[value] = Object.freeze({
      selected: subject === value,
      amount,
      disabled: subject !== value && !amount,
    });
  }
  const gone = count(
    rows,
    ({ thread, group }) =>
      matchesSearch(thread, group) &&
      matchesState(thread) &&
      matchesScope(thread) &&
      matchesSubject(thread) &&
      matchesGone(thread, group, true),
  );
  return Object.freeze({
    summary: facets.join(" · "),
    hidden: !narrowed(),
    states: Object.freeze(states),
    scopes: Object.freeze(scopes),
    subjects: Object.freeze(subjects),
    gone: Object.freeze({
      hidden: !gone && !onlyGone,
      selected: onlyGone,
      amount: gone,
      disabled: !onlyGone && !gone,
    }),
    readerTitle: needsYou()
      ? "Show open threads"
      : states.reader.disabled
        ? "Nothing is waiting on you"
        : "Show threads waiting on you",
  });
}

export function paintNarrowing(reading) {
  viewSummary.textContent = reading.summary;
  viewRow.hidden = reading.hidden;
  for (const [value, button] of Object.entries(stateButtons))
    setButton(button, reading.states[value]);
  for (const [value, button] of Object.entries(scopeButtons))
    setButton(button, reading.scopes[value]);
  for (const [value, button] of Object.entries(subjectButtons))
    setButton(button, reading.subjects[value]);
  goneBtn.hidden = reading.gone.hidden;
  setButton(goneBtn, reading.gone);

  // Through the key-title seat paintCoreControls appends `w` while the panel owns it.
  stateButtons.reader.dataset.lfKeyTitle = reading.readerTitle;
  stateButtons.reader.title = reading.readerTitle;
}

function renarrow(refreshNarrowing) {
  if (runtime.statePhase !== "ready") return;
  const ready = refreshNarrowing();
  // Reset after the keyed list has committed. The coordinator owns rejection reporting;
  // observe this continuation on both paths so an event listener that discards the
  // returned ticket cannot create another page-level rejection.
  void ready.then(
    () => (threadsBox.scrollTop = 0),
    () => {},
  );
  return ready;
}

const choose = (kind, value, refreshNarrowing) => {
  if (kind === "state") state = state === value && value !== "open" ? "open" : value;
  else if (kind === "scope") scope = scope === value ? null : value;
  else if (kind === "subject") subject = subject === value ? null : value;
  else if (kind === "gone") onlyGone = !onlyGone;
  renarrow(refreshNarrowing);
};

export function wireNarrowing(refreshNarrowing) {
  filterToggle.onclick = () => {
    filterControls.hidden = !filterControls.hidden;
    filterToggle.setAttribute("aria-expanded", String(!filterControls.hidden));
  };
  resetFilters.onclick = () => {
    // Reset retires its own control; keep the reader at the surviving disclosure.
    if (document.activeElement === resetFilters) filterToggle.focus();
    widen(refreshNarrowing);
  };
  findInput.addEventListener("input", () => {
    finding = findInput.value.trim().toLowerCase();
    renarrow(refreshNarrowing);
  });
  for (const button of filterControls.querySelectorAll(".lf-thread-filter"))
    button.onclick = () => {
      if (!button.disabled)
        choose(button.dataset.filterKind, button.dataset.filterValue, refreshNarrowing);
    };
}

function clearNarrowing(nextState = "open") {
  const changed =
    Boolean(finding) || state !== nextState || Boolean(scope || subject || onlyGone);
  finding = "";
  state = nextState;
  scope = null;
  subject = null;
  onlyGone = false;
  findInput.value = "";
  return changed;
}

// A direct destination may replace every panel refinement. A fallible optimistic
// transition captures this reading before it reveals that destination, so refusal can
// put back the exact list the reader was operating rather than merely selecting the
// thread's lifecycle again.
export function retainNarrowing(refreshNarrowing) {
  const reading = () => ({
    finding,
    words: findInput.value,
    state,
    scope,
    subject,
    onlyGone,
  });
  const same = (left, right) =>
    right && Object.keys(left).every((key) => left[key] === right[key]);
  const retained = reading();
  let replacement = null;
  return {
    replaced: () => {
      replacement = reading();
    },
    // Restore only while the direct arrival's view still stands. Typing in the
    // optimistic reply box does not change this reading and must not strand a refused
    // Reopen under the Open filter; changing the search or facets deliberately does.
    restore: async (before = null) => {
      if (!same(reading(), replacement)) return false;
      await before?.();
      ({ finding, state, scope, subject, onlyGone } = retained);
      findInput.value = retained.words;
      await renarrow(refreshNarrowing);
      return true;
    },
  };
}

export function widen(refreshNarrowing) {
  if (!clearNarrowing()) return false;
  renarrow(refreshNarrowing);
  return true;
}

// A direct destination overrides the current view, including the default Open state.
// It clears unrelated refinements and selects the lifecycle value that can contain the
// requested thread, rather than making Resolved a special disclosure outside filtering.
export function revealThread(id, refreshNarrowing) {
  const thread = threadList().find(
    (candidate) =>
      candidate.root.id === id || candidate.msgs.some((message) => message.id === id),
  );
  if (!thread) return false;
  clearNarrowing(thread.resolved ? "resolved" : "open");
  return renarrow(refreshNarrowing);
}
