/* Notices and announcements.

   News arriving without the user's send gesture may show a notice but does
   not move focus or scroll the panel. `notice` is the one visible surface for a
   moment's news, such as an arrived version or an undo, and it stands in
   one seat: the floating panel's seat for passing words, in place of the current walk
   position, which returns when the notice's time is up (floating-panel.js, `passing`). The
   live region hears the same words. It is text, but for the one press a notice of the
   user's own gesture may carry: the page command that takes it back (`press`), which
   the floating panel draws beside the words with its key, as "Resolved “One reconnect in
   about 40” · Undo z" (floating-panel.js, `rowNotice`). The user chose that on 31
   October, after a Resolve that moved the panel on left nothing there offering to take
   it back; until then a notice was text alone, and what it named the panel's own
   controls reached. There is no second surface for news, so nothing floats in a corner
   to become a stale pointer target. A failure is no news: it goes through errors.js,
   which keeps it until the user has dealt with it. */
import { el } from "./widget-elements.js";
import { signal } from "/runtime/framework.js";
import { ANNOUNCE } from "./widget-upgrade.js";
import { leafSays, wordsText } from "./voice.js";
import { onUserInput } from "./focus.js";

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
// What the seat says, whether it shows, and the press it offers, or null: the page
// command that takes back what it reports and the action that command is, as
// `{command, action}`. Errors are no notices: they go through errors.js, which keeps
// them until they are dealt with.
const noticePresentation = signal(
  Object.freeze({ message: "", visible: false, press: null }),
);

export const noticeReading = () => noticePresentation.value;
const noticeVisible = () => noticePresentation.peek().visible;

// A notice is Leaf's news, so a notice given as a string is Leaf's words; one that
// relays the agent's words too is given as parts, each said by whoever says it
// (semantic-news.js), which the seat draws apart and the live region hears as one line
// (voice.js).
export const noticeWords = (message) =>
  typeof message === "string" ? [leafSays(message)] : message;

// The reading changes in the gesture's task. Its seat paints visible news immediately
// and coalesces a withdrawal until the script ends, so replacing a notice paints once.
const presentNotice = (message, visible, press = null) => {
  noticePresentation.value = Object.freeze({ message, visible, press });
};

export function announce(msg) {
  // Removing and restoring the text node makes repeated identical announcements a
  // fresh live-region change, including when two arrivals' delays overlap.
  if (liveEl.firstChild) liveEl.replaceChildren();
  setTimeout(() => {
    if (liveEl.firstChild) liveEl.replaceChildren();
    liveEl.append(wordsText(msg));
  }, 30);
}

// A widget's words for a listener (`announce`, widget-upgrade.js), said here.
addEventListener(ANNOUNCE, (event) => announce(event.detail));

// An undo ("Undid: Chose “Fast” · just now"), an arrival ("Updated to v3"): the
// quiet words in the panel's seat. A widget's gesture is no notice, since the widget
// draws it where it was made; the live region alone hears it (application.js,
// `named`). A notice offering a press (`press`) ends in that press's word and key, so
// what pressing the words does reads in them.
function showNotice(msg, background = null, press = null) {
  presentNotice(msg, true, press);
  showingBackground = background;
  clearTimeout(noticeTimer);
  if (!press) noticeTimer = setTimeout(retireNotice, NOTICE_MS);
}
function retireNotice() {
  if (!userContext && !userHoldTimer && showBackground(waitingBackground.shift()))
    return;
  presentNotice(noticePresentation.peek().message, false);
  showingBackground = null;
}
// A notice offering a press stands until the user's next input rather than for its
// time. The panel gives its press room beside the field (floating-panel.js,
// `rowNotice`), so one leaving on a timer moved the field's controls under nobody's
// hand. An input on the press itself, which carries `NOTICE_PRESS`, keeps it.
const NOTICE_PRESS = "data-lf-notice-press";
onUserInput((event) => {
  if (!noticePresentation.peek().press) return;
  const path = event.composedPath?.() ?? [];
  if (path.some((node) => node instanceof Element && node.hasAttribute(NOTICE_PRESS)))
    return;
  retireNotice();
});

// A producer may retire a deferred assertion before it reaches the seat.
// Skip it without spending a visible interval, then take the next queued group.
function showBackground(entry) {
  while (entry) {
    const message = entry.format(entry.value);
    if (wordsText(message)) {
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
  { background = false, announce: speak = true, group = null, press = null } = {},
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
  showNotice(msg, null, press);
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
