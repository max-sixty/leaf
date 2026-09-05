/* Search and waiting-on-reader narrowing for the thread panel.

   Two narrowings compose: the words the reader is looking for (`finding`, over each
   thread's messages, its anchor label, and the part of the page it is on) and whether
   the latest agent message asks the reader to answer (`onlyNeedsYou`, through
   `awaitsReader`). Both are the panel's own view. The page's marks, the inline
   conversation seats and the banner's count go on saying what the log says, and the
   panel's head says `Showing N of M` for as long as a narrowing stands, because a list
   that goes quiet about what it is hiding is a trap.

   Neither is stored. A remembered narrowing greets a returning reader with part of a
   conversation and nothing on screen saying why. `ARRANGEMENTS` is for what the page
   restores; a look at a list is not one.

   Neither takes a card out of the document. An open thread the narrowing hides keeps
   its node, `hidden`: a widget an agent sent in a reply is instantiated once, in that
   card, and the banner's Asks count, the tray's rows and the `a`/`A` walk all find it
   by id. `openThreads` and the `t`/`T` walk read only the cards that show. */
import { anchorLabel } from "./messages.js";
import { awaitsReader } from "./model.js";
import { el } from "../widget-elements.js";
import { findInput, needsBtn, panelTitle, threadsBox } from "./panel.js";
import { runtime } from "../context.js";
import { renderThreads } from "./thread-list.js";
import { paintAcknowledgments, threadList } from "./reconcile.js";

// Whose turn a thread is (`awaitsReader`) belongs to the model rather than to this file,
// because the banner's decision count asks the same question from the other side: a request
// whose own conversation is with the agent is not the reader's to deal with. The panel
// saying so while the banner went on counting the decision was one fact told two ways.
let finding = "";
let onlyNeedsYou = false;
export const narrowed = () => Boolean(finding) || onlyNeedsYou;

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

export const inFilter = (t, group) =>
  (!onlyNeedsYou || awaitsReader(t)) &&
  (!finding || threadWords(t, group).includes(finding));

// The page has comments and the reader's narrowing is standing between them and it. It
// names the narrowing rather than saying nothing was found, because the reader may have
// arrived here from a key or from a second tab and what is on screen has to say why.
const noMatch = el("div", "lf-empty");
export function noMatchNote() {
  const said = finding
    ? onlyNeedsYou
      ? `Nothing waiting on you says “${finding}”.`
      : `No thread matches “${finding}”.`
    : "Nothing is waiting on you.";
  if (noMatch.textContent !== said) noMatch.textContent = said;
  return noMatch;
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
export function paintNarrowing(open, shown) {
  const showing = shown.filter((t) => !t.resolved).length;
  panelTitle.textContent =
    narrowed() && open.length ? `Showing ${showing} of ${open.length}` : "Threads";
  const waiting = open.filter(awaitsReader).length;
  needsBtn.textContent = waiting ? `Waiting on you (${waiting})` : "Waiting on you";
  // Pressable while it stands pressed, so the reader can always let it go; dead only when
  // there is nothing for it to show and it is not the thing hiding the list. A dead
  // control reads as a status until it says why — a blind drive took "Waiting on you",
  // greyed, for a verdict on the thread it had just written.
  needsBtn.disabled = !onlyNeedsYou && !waiting;
  // Through the key-title seat the core controls paint from (paintCoreControls), which
  // appends the binding while the row is live; written to `title` directly it was read
  // once as the base and the control went on saying " (w)".
  needsBtn.dataset.lfKeyTitle = onlyNeedsYou
    ? "Show every thread again"
    : waiting
      ? "Show only the threads waiting on you"
      : "Nothing is waiting on you";
  needsBtn.title = needsBtn.dataset.lfKeyTitle;
}

// Re-render the list alone, for the one change that is the panel's own rather than the
// log's: the reader narrowing it. Nothing about the page moved, so the anchor pass is not
// asked again — the list is rebuilt from the record it already wrote.
function renarrow() {
  if (runtime.statePhase !== "ready") return;
  renderThreads(threadList());
  paintAcknowledgments();
  // A new set of results starts at its own beginning. Keeping the old offset lands the
  // reader in the middle of a shorter list, or past the end of it, over a change they
  // made a keystroke at a time.
  threadsBox.scrollTop = 0;
}
// Mounted from chrome.js.
export function wireNarrowing() {
  findInput.addEventListener("input", () => {
    finding = findInput.value.trim().toLowerCase();
    renarrow();
  });
  needsBtn.onclick = () => {
    onlyNeedsYou = !onlyNeedsYou;
    needsBtn.setAttribute("aria-pressed", String(onlyNeedsYou));
    needsBtn.classList.toggle("on", onlyNeedsYou);
    renarrow();
  };
}

// Everything the reader narrowed, let go at once — what Escape in the find box does, and
// what a thread arriving from outside the narrowing needs before it can be revealed.
export function widen() {
  if (!narrowed()) return false;
  finding = "";
  onlyNeedsYou = false;
  findInput.value = "";
  needsBtn.setAttribute("aria-pressed", "false");
  needsBtn.classList.remove("on");
  renarrow();
  return true;
}

export const needsYou = () => onlyNeedsYou;
