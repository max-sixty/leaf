/* Notices and announcements.

   News arriving without the user's send gesture may show a notice but does
   not move focus or scroll the panel. `notice` is the one visible surface for a
   moment's news — a recorded gesture, an arrived version, a refused send — and it
   stands in the bottom status line in place of the current walk position, which returns
   when the notice fades; the live region hears the same words. It is text rather than a
   control: what a notice names, the banner's own buttons reach. There is no second
   surface for news, so nothing floats in a corner to become a stale pointer target. */
import { nothing, render } from "../vendor/browser-runtime.js";

import { el } from "./widget-elements.js";

export const liveEl = el("div", "lf-ui lf-live");
liveEl.setAttribute("aria-live", "polite");
render(nothing, liveEl);

// How long a notice holds the status line before the line's own words come back: long
// enough to read a recorded acknowledgement, short enough that the state behind it is
// never far away.
const NOTICE_MS = 4000;

let noticeTimer = 0;
let showingBackground = null;
const waitingBackground = [];
let userContext = false;
let userHoldTimer = 0;
let noticePresentation = Object.freeze({ message: "", visible: false });
let invalidateNoticePresentation = null;

export const noticeReading = () => noticePresentation;
export const noticeVisible = () => noticePresentation.visible;

// The complete bottom-status renderer registers one synchronous invalidation door. A
// notice acknowledges a gesture before its caller returns; routing this through the
// shared frame repaint would turn that same-turn contract into eventual feedback.
export function registerNoticePresentation(invalidate) {
  if (invalidateNoticePresentation)
    throw new Error("The notice presentation already has an owner");
  invalidateNoticePresentation = invalidate;
}

const presentNotice = (message, visible) => {
  noticePresentation = Object.freeze({ message, visible });
  invalidateNoticePresentation?.();
};

export function announce(msg) {
  // Removing and restoring the text node makes repeated identical announcements a
  // fresh live-region change rather than a value Lit can correctly leave untouched.
  render(nothing, liveEl);
  setTimeout(() => {
    // Each arrival owns a fresh insertion, including two equal announcements whose
    // delays overlap. Lit would otherwise correctly reuse the first callback's text.
    render(nothing, liveEl);
    render(msg, liveEl);
  }, 30);
}

// The acknowledgement of a gesture ("Moved to Done — sent"), an arrival ("Updated
// to v3"), a refusal ("Nothing to send — the box is empty"): the quiet status at the page
// foot. A sentence that is also a button for four seconds is a target
// the user cannot learn.
function showNotice(msg, background = null) {
  presentNotice(msg, true);
  showingBackground = background;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => {
    if (!userContext && !userHoldTimer && showBackground(waitingBackground.shift()))
      return;
    presentNotice(noticePresentation.message, false);
    showingBackground = null;
  }, NOTICE_MS);
}

// A producer may retire a deferred assertion before it reaches the status line.
// Skip it without spending a visible interval, then take the next queued group.
function showBackground(entry) {
  while (entry) {
    const message = entry.format(entry.value);
    if (message) {
      showNotice(message, entry);
      return true;
    }
    entry = waitingBackground.shift();
  }
  return false;
}

const textBackground = (message) => ({
  key: "text",
  value: message,
  combine: (_older, newer) => newer,
  format: (value) => value,
});

// The producer supplies what makes two deferred notices one piece of news. An
// interrupted displayed entry is older than anything already waiting under its key;
// ordinary new arrivals are newer. One pending entry per key bounds the backlog.
function queueBackground(entry, front = false) {
  const index = waitingBackground.findIndex((waiting) => waiting.key === entry.key);
  if (index >= 0) {
    const [waiting] = waitingBackground.splice(index, 1);
    entry = {
      ...entry,
      value: front
        ? entry.combine(entry.value, waiting.value)
        : entry.combine(waiting.value, entry.value),
    };
  }
  if (front) waitingBackground.unshift(entry);
  else waitingBackground.push(entry);
}

// User commands own the next brief interval. Background arrivals wait behind one,
// while a command can interrupt an arrival and let it return after the acknowledgement.
// A held status line coalesces each producer's news; the live region announces it now.
export function notice(
  msg,
  { background = false, announce: speak = true, group = null } = {},
) {
  // The live region is not the contended surface. Announce at arrival even when the
  // visual line has to wait, and never announce again when a waiting notice is shown.
  if (speak) announce(msg);
  if (background) {
    const entry = group ?? textBackground(msg);
    if (userContext || userHoldTimer || noticeVisible()) return queueBackground(entry);
    return showBackground(entry);
  }
  if (!background && showingBackground) queueBackground(showingBackground, true);
  showNotice(msg);
}

// A semantic walk is an immediate user command even though its feedback is the live
// ordinal rather than a timed notice. Hold arriving news for one boundary interval;
// beginWalk calls this only for gestures, so ordinary repaints never restart the hold.
export function holdStatus(ms) {
  if (noticeVisible()) {
    if (showingBackground) queueBackground(showingBackground, true);
    clearTimeout(noticeTimer);
    noticeTimer = 0;
    presentNotice(noticePresentation.message, false);
    showingBackground = null;
  }
  clearTimeout(userHoldTimer);
  userHoldTimer = setTimeout(() => {
    userHoldTimer = 0;
    if (userContext || noticeVisible() || !waitingBackground.length) return;
    showBackground(waitingBackground.shift());
  }, ms);
}

// Persistent command context outranks background news and pauses its visible interval.
// A foreground notice may still replace the context briefly, then the context returns.
export function setNoticeContext(active) {
  userContext = active;
  if (active && showingBackground) {
    queueBackground(showingBackground, true);
    clearTimeout(noticeTimer);
    noticeTimer = 0;
    presentNotice(noticePresentation.message, false);
    showingBackground = null;
  } else if (
    !active &&
    !userHoldTimer &&
    waitingBackground.length &&
    !noticeVisible()
  ) {
    showBackground(waitingBackground.shift());
  }
}
