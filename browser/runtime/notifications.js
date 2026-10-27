/* Notices and announcements.

   News arriving without the user's send gesture may show a notice but does
   not move focus or scroll the panel. `notice` is the one visible surface for a
   moment's news, such as an arrived version or an undo, and it stands in
   one seat: the floating panel's seat for passing words, in place of the current walk
   position, which returns when the notice's time is up (floating-panel.js, `passing`). The
   live region hears the same words. It is text rather than a control: what a notice
   names, the panel's own controls reach. There is no second surface for news, so
   nothing floats in a corner to become a stale pointer target. A failure is no news:
   it goes through errors.js, which keeps it until the user has dealt with it. */
import { el } from "./widget-elements.js";
import { signal } from "/runtime/framework.js";

export const liveEl = el("div", "lf-ui lf-live");
liveEl.setAttribute("aria-live", "polite");

// How long a notice holds its seat before the seat's own words come back: long
// enough to read a recorded acknowledgement, short enough that the state behind it is
// never far away.
const NOTICE_MS = 4000;

let noticeTimer = 0;
let showingBackground = null;
const waitingBackground = [];
let userContext = false;
let userHoldTimer = 0;
// What the seat says and whether it shows. Errors are no notices: they go through
// errors.js, which keeps them until they are dealt with.
const noticePresentation = signal(Object.freeze({ message: "", visible: false }));

export const noticeReading = () => noticePresentation.value;
const noticeVisible = () => noticePresentation.peek().visible;

// The reading changes in the gesture's task. Its seat paints visible news immediately
// and coalesces a withdrawal until the script ends, so replacing a notice paints once.
const presentNotice = (message, visible) => {
  noticePresentation.value = Object.freeze({ message, visible });
};

export function announce(msg) {
  // Removing and restoring the text node makes repeated identical announcements a
  // fresh live-region change, including when two arrivals' delays overlap.
  if (liveEl.firstChild) liveEl.replaceChildren();
  setTimeout(() => {
    if (liveEl.firstChild) liveEl.replaceChildren();
    liveEl.append(msg);
  }, 30);
}

// An undo ("Undid: Chose “Fast” · just now"), an arrival ("Updated to v3"): the
// quiet words in the panel's seat. A widget's gesture is no notice, since the widget
// draws it where it was made; the live region alone hears it (application.js,
// `named`). A sentence that is also a button for
// four seconds is a target
// the user cannot learn.
function showNotice(msg, background = null) {
  presentNotice(msg, true);
  showingBackground = background;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => {
    if (!userContext && !userHoldTimer && showBackground(waitingBackground.shift()))
      return;
    presentNotice(noticePresentation.peek().message, false);
    showingBackground = null;
  }, NOTICE_MS);
}

// A producer may retire a deferred assertion before it reaches the seat.
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
  if (showingBackground) queueBackground(showingBackground, true);
  showNotice(msg);
}

// Take the notice down for something the user asked for, putting a background notice
// it was showing back at the front of the queue. Unlike the notice's own timer, which
// retires it, this keeps the news for later.
function yieldNotice() {
  if (showingBackground) queueBackground(showingBackground, true);
  clearTimeout(noticeTimer);
  presentNotice(noticePresentation.peek().message, false);
  showingBackground = null;
}

// A semantic walk is an immediate user command even though its feedback is the live
// ordinal rather than a timed notice. Hold arriving news for a moment after the step;
// beginWalk calls this only for gestures, so ordinary repaints never restart the hold.
export function holdStatus(ms) {
  if (noticeVisible()) yieldNotice();
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
  if (active && showingBackground) yieldNotice();
  else if (!active && !userHoldTimer && waitingBackground.length && !noticeVisible()) {
    showBackground(waitingBackground.shift());
  }
}
