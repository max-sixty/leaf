/* Notices and announcements.

   News arriving without the reader's send gesture may show a notice and count but does
   not move focus or scroll the panel. `notice` is the one visible surface for a
   moment's news — a recorded gesture, an arrived version, a refused send — and it
   stands in the bottom status line in place of the current walk position, which returns
   when the notice fades; the live region hears the same words. It is text rather than a
   control: what a notice names, the banner's own buttons reach. There is no second
   surface for news, so nothing floats in a corner to become a stale pointer target. */
import { el } from "./widget-elements.js";

// The notice this module writes; the bottom status line seats it.
export const noticeEl = el("span", "lf-ui lf-notice");

export const liveEl = el("div", "lf-ui lf-live");
liveEl.setAttribute("aria-live", "polite");

// How long a notice holds the status line before the line's own words come back: long
// enough to read a recorded acknowledgement, short enough that the state behind it is
// never far away.
const NOTICE_MS = 4000;

let noticeTimer = 0;
let showingBackground = false;
let waitingBackground = null;
let readerContext = false;
let readerHoldTimer = 0;

export function announce(msg) {
  liveEl.textContent = "";
  setTimeout(() => (liveEl.textContent = msg), 30);
}

// The acknowledgement of a gesture ("Moved to Done — sent"), an arrival ("Updated
// to v3"), a refusal ("Nothing to send — the box is empty"): the quiet status at the page
// foot. A sentence that is also a button for four seconds is a target
// the reader cannot learn.
function showNotice(msg, background) {
  announce(msg);
  noticeEl.textContent = msg;
  noticeEl.classList.add("show");
  showingBackground = background;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => {
    if (!readerContext && !readerHoldTimer && waitingBackground) {
      const waiting = waitingBackground;
      waitingBackground = null;
      return showNotice(waiting, true);
    }
    noticeEl.classList.remove("show");
    showingBackground = false;
  }, NOTICE_MS);
}

// Reader commands own the next brief interval. Background arrivals wait behind one,
// while a command can interrupt an arrival and let it return after the acknowledgement.
// Durable unread state remains on the banner and Threads control throughout.
export function notice(msg, { background = false } = {}) {
  if (
    background &&
    (readerContext ||
      readerHoldTimer ||
      (noticeEl.classList.contains("show") && !showingBackground))
  ) {
    waitingBackground = msg;
    return;
  }
  if (!background && showingBackground) waitingBackground = noticeEl.textContent;
  showNotice(msg, background);
}

// A semantic walk is an immediate reader command even though its feedback is the live
// ordinal rather than a timed notice. Hold arriving news for one boundary interval;
// beginWalk calls this only for gestures, so ordinary repaints never restart the hold.
export function holdStatus(ms) {
  if (showingBackground) {
    waitingBackground = noticeEl.textContent;
    clearTimeout(noticeTimer);
    noticeTimer = 0;
    noticeEl.classList.remove("show");
    showingBackground = false;
  }
  clearTimeout(readerHoldTimer);
  readerHoldTimer = setTimeout(() => {
    readerHoldTimer = 0;
    if (readerContext || noticeEl.classList.contains("show") || !waitingBackground)
      return;
    const waiting = waitingBackground;
    waitingBackground = null;
    showNotice(waiting, true);
  }, ms);
}

// Persistent command context outranks background news and pauses its visible interval.
// A foreground notice may still replace the context briefly, then the context returns.
export function setNoticeContext(active) {
  readerContext = active;
  if (active && showingBackground) {
    waitingBackground = noticeEl.textContent;
    clearTimeout(noticeTimer);
    noticeTimer = 0;
    noticeEl.classList.remove("show");
    showingBackground = false;
  } else if (
    !active &&
    !readerHoldTimer &&
    waitingBackground &&
    !noticeEl.classList.contains("show")
  ) {
    const waiting = waitingBackground;
    waitingBackground = null;
    showNotice(waiting, true);
  }
}
