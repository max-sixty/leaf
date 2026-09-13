/* Search and faceted narrowing for the thread panel.

   State is one exclusive question: Open, On you, On agent, or Resolved. Scope and
   subject are optional refinements, so a reader cannot construct the impossible old
   combination "waiting on you and resolved". The conditional placement chip appears
   only when this page has a detached anchored thread to find.

   These are the panel's own view. The page's marks, inline conversation seats and
   banner counts keep reading the whole log. No narrowing is stored: returning to a
   page should not silently hide conversation. Cards remain in the document while
   filtered so reply widgets keep their identity and the rest of the runtime can still
   read them by id. */
import { anchorLabel } from "./messages.js";
import { awaitsAgent, awaitsReader } from "./model.js";
import {
  filterControls,
  findInput,
  goneBtn,
  panelTitle,
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
const setButton = (button, selected, amount) => {
  button.setAttribute("aria-pressed", String(selected));
  button.classList.toggle("on", selected);
  const label = button.dataset.filterLabel;
  button.textContent = amount ? `${label} (${amount})` : label;
};

// Counts are faceted: each chip answers how many results switching that facet to its
// value would show while every other standing filter remains. A static all-page count
// on "Page" would promise threads the selected Open/Resolved state then hid.
export function paintNarrowing(threads, shown, groups = new Map()) {
  const rows = entries(threads, groups);
  const baseline =
    state === "resolved"
      ? threads.length
      : threads.filter((thread) => !thread.resolved).length;
  panelTitle.textContent =
    narrowed() && baseline ? `Showing ${shown.length} of ${baseline}` : "Threads";

  for (const [value, button] of Object.entries(stateButtons)) {
    const amount = count(
      rows,
      ({ thread, group }) =>
        matchesSearch(thread, group) &&
        matchesState(thread, value) &&
        matchesScope(thread) &&
        matchesSubject(thread) &&
        matchesGone(thread, group),
    );
    setButton(button, state === value, amount);
    button.disabled = state !== value && !amount;
  }
  for (const [value, button] of Object.entries(scopeButtons)) {
    const amount = count(
      rows,
      ({ thread, group }) =>
        matchesSearch(thread, group) &&
        matchesState(thread) &&
        matchesScope(thread, value) &&
        matchesSubject(thread) &&
        matchesGone(thread, group),
    );
    setButton(button, scope === value, amount);
    button.disabled = scope !== value && !amount;
  }
  for (const [value, button] of Object.entries(subjectButtons)) {
    const amount = count(
      rows,
      ({ thread, group }) =>
        matchesSearch(thread, group) &&
        matchesState(thread) &&
        matchesScope(thread) &&
        matchesSubject(thread, value) &&
        matchesGone(thread, group),
    );
    setButton(button, subject === value, amount);
    button.disabled = subject !== value && !amount;
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
  goneBtn.hidden = !gone && !onlyGone;
  setButton(goneBtn, onlyGone, gone);
  goneBtn.disabled = !onlyGone && !gone;

  // Through the key-title seat paintCoreControls appends `w` while the panel owns it.
  stateButtons.reader.dataset.lfKeyTitle = needsYou()
    ? "Show open threads"
    : stateButtons.reader.disabled
      ? "Nothing is waiting on you"
      : "Show threads waiting on you";
  stateButtons.reader.title = stateButtons.reader.dataset.lfKeyTitle;
}

function renarrow(refreshNarrowing) {
  if (runtime.statePhase !== "ready") return;
  refreshNarrowing();
  threadsBox.scrollTop = 0;
}

const choose = (kind, value, refreshNarrowing) => {
  if (kind === "state") state = state === value && value !== "open" ? "open" : value;
  else if (kind === "scope") scope = scope === value ? null : value;
  else if (kind === "subject") subject = subject === value ? null : value;
  else if (kind === "gone") onlyGone = !onlyGone;
  renarrow(refreshNarrowing);
};

export function wireNarrowing(refreshNarrowing) {
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
    restore: (before = null) => {
      if (!same(reading(), replacement)) return false;
      before?.();
      ({ finding, state, scope, subject, onlyGone } = retained);
      findInput.value = retained.words;
      renarrow(refreshNarrowing);
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
  renarrow(refreshNarrowing);
  return true;
}
