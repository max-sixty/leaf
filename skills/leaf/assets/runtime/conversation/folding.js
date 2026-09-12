/* This module owns the shared Resolve/Reopen controls and resolution-fold state and
 * motion. Callers supply settlement commands and pending records so rendering never
 * imports delivery. */
import { measure, offer, reserve } from "../widget-elements.js";
import { iconElement } from "../icons.js";
import { keys, paintKeys } from "../keyboard/scopes.js";
import { PRESS } from "../keyboard/bindings.js";
import { threadsBox } from "./panel-elements.js";
import { FOLD_MS, motion } from "../motion.js";
import { pendingForParent } from "../pending/model.js";

/* Resolve and Reopen, in the panel and inline.

   Panel and inline settlement controls read supplied pending ledger records. The local
   projection resolves or reopens in the press that submits the request and disables
   the opposite control until the server accepts it; refusal restores the authoritative
   state. Resolving the last thread in an inline card closes it and returns focus to page
   navigation; a conversation seated in the page keeps a Reopen control. */
const news = "lf-thread-settlement";
// By either name the gesture's thread answers to: the send door rewrites a parent this
// page named itself into the log's name (`nameParent`) a beat before the card wearing
// the earlier one is renamed, and in that beat this control still asks by the earlier.
const pendingSettlement = (entries, id) =>
  pendingForParent(entries, id, ["resolve", "unresolve"]);
const tell = (id) => document.dispatchEvent(new CustomEvent(news, { detail: { id } }));

// `liveId` rather than the id this thread had when the control was built: a card the
// reader's own send drew is named by its attempt until the log answers, and the node is
// renamed in place rather than replaced, so a control that captured the earlier name
// would go on resolving a thread that no longer exists under it.
export function settlementControl(
  t,
  { prepareLanding, liveId, pendingEntries, setResolved },
) {
  const id = liveId ?? (() => t.root.id);
  const reopen = Boolean(t.resolved);
  const kind = reopen ? "unresolve" : "resolve";
  const word = reopen ? "Reopen" : "Resolve";
  const label = reopen ? word : "Resolve thread";
  const pendingWord = reopen ? "Reopening…" : "Resolving thread…";
  const button = offer(
    "button",
    reopen ? "lf-btn lf-reopen lf-thread-action" : "lf-btn lf-resolve lf-icon-action",
    reopen ? word : undefined,
  );
  if (!reopen) button.append(iconElement("check", "lf-action-icon"));
  const sync = () => {
    // A fold owns its accepted outcome until it removes the old control.
    if (button.closest(".lf-going")) return;
    const pending = pendingSettlement(pendingEntries(), id());
    button.setAttribute("aria-disabled", String(Boolean(pending)));
    button.setAttribute("aria-busy", String(Boolean(pending)));
    const currentLabel = pending?.event.kind === kind ? pendingWord : label;
    if (reopen) button.textContent = currentLabel;
    else {
      button.setAttribute("aria-label", currentLabel);
      button.title = currentLabel;
    }
  };
  const update = (ev) => {
    if (!button.isConnected) return document.removeEventListener(news, update);
    if (ev.detail.id !== id()) return;
    sync();
  };
  document.addEventListener(news, update);
  button.onclick = async () => {
    if (pendingSettlement(pendingEntries(), id())) return;
    const landing = prepareLanding?.();
    const sent = setResolved(id(), !reopen);
    landing?.optimistic?.();
    tell(id());
    paintKeys();
    try {
      if (!(await sent)) landing?.refused?.();
    } finally {
      tell(id());
      paintKeys();
    }
  };
  keys(button, `On a thread's ${word} button`, [
    {
      id: reopen ? "thread.reopen" : "thread.resolve",
      keys: PRESS,
      does: `${word} it`,
      line: word.toLowerCase(),
      when: () => !pendingSettlement(pendingEntries(), id()),
      run: () => button.click(),
    },
  ]);
  // Showing one view can release a hidden control's measurement during resize
  // delivery. Reserve outside that delivery because its thread also observes size.
  if (reopen) {
    const fit = () => reserve(button, [word, pendingWord]);
    measure(button, () => requestAnimationFrame(() => measure(button, fit)));
  }
  sync();
  return button;
}

/* Resolution-fold state and motion for comment-panel threads. */
// A thread the conversation projection has resolved and the open list is still holding.
// Its place is not given up in the frame the projection settles it: the node stays where
// it stood, says what
// was done to it on the control that was pressed, and folds, so the threads under it
// rise where the eye can follow instead of arriving somewhere else. The retained list
// gets its resolved card when the fold is over, which keeps one node per thread through
// every settled state.
//
// Driven from the reconcile rather than directly from the press, because local pending
// work and the accepted log share one projection. A resolve with no gesture behind it —
// a second tab's, or the agent's — therefore takes the same room out of the same list.
// That is the case that needs the motion more: nothing in this tab moved, so the fold is
// the only thing saying so.
//
// Everything that walks the list asks for .lf-thread, so the one rename takes the
// node out of t/T, out of the Go-to map, out of scoped presses and out of what the
// panel repaints, in a stroke: what stands there is room, not a thread. `inert` says the
// same to the pointer and the tab order, so the fold can't be pressed a second time
// or typed into on its way out.
//
// Null where there is nothing to fold: a thread this page never drew open, or a
// reader who asked for less motion, for whom the room goes in the frame it always did.
const folding = new Map(); // thread id -> the node folding out of the open list
export function foldOut(t, repaintConversation) {
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
  // setting one, and an entry over a thread nothing is folding would hide the retained
  // resolved card that should be holding it by then.
  if (going?.isConnected) return going;
  folding.delete(t.root.id);
  const node = threadsBox.querySelector(`:scope > .lf-thread[data-id="${t.root.id}"]`);
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
  // The pressed control states the outcome in the thread corner it already occupied.
  // Its checkmark changes from a quiet action to the green outcome without changing
  // the control's box, so the fold starts from the layout the reader was looking at.
  const resolve = node.querySelector(":scope > .lf-thread-head > .lf-resolve");
  resolve.setAttribute("aria-label", "Resolved");
  resolve.title = "Resolved";
  resolve.setAttribute("aria-busy", "false");
  node.className = "lf-going";
  if (node.matches(":focus-within")) threadsBox.focus({ preventScroll: true });
  node.inert = true;
  folding.set(t.root.id, node);
  // Straight off the promise, and nothing between: motion() holds the last keyframe
  // while this direct reaction reconciles the node away, then its shared reaction
  // releases the effect. `renderPanel` remains the list's one writer, so it can hold
  // a surviving card through the final removal. Deferring this cleanup past that
  // contract would put the whole thread back before it goes. What holds the line is
  // test_the_fold_never_paints_a_frame_that_undoes_the_last, since no held frame can
  // see it.
  played.finished.then(() => {
    // This node's own entry, never whatever the thread's key holds now: a fold the
    // line above superseded is still running, and the older one finishing must not
    // take the live one's record with it.
    if (folding.get(t.root.id) === node) folding.delete(t.root.id);
    repaintConversation();
  });
  return node;
}

export const finishFold = (id) => folding.delete(id);
export const hasFolding = () => [...folding.values()].some((node) => node.isConnected);
export const isFolding = (id) => folding.has(id);
