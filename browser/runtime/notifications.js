/* Notices and announcements.

   News arriving without the user's send gesture may show a notice but does
   not move focus or scroll the panel. `notice` is the one visible surface for a
   moment's news, such as an arrived version or an undo, and it stands in
   one seat: the floating panel's seat for passing words, in place of the current walk
   position, which returns when the notice's time is up (floating-panel.js, `passing`). The
   live region hears the same words. It is text, but for the one press a notice of the
   user's own gesture may carry: the press that matters most after that gesture
   (`press`), the next open thread after a Resolve or the undo that takes a gesture
   back (thread/folding.js, `nextStep`; undo.js, `offerUndo`), which the floating
   panel's field says at its end with the key of the page command that makes it too,
   after the words, as "Resolved “One reconnect in about 40” … Next thread t"
   (floating-panel.js, `noticePress`). The notice stands no longer than its gesture
   does, so its press never acts for anything else. The user chose a notice's press on
   31 October, after a Resolve that moved the panel on left nothing there offering to
   take it back; until then a notice was text alone, and what it named the panel's own
   controls reached. A gesture whose next step needs no words of its own, as an answer
   with more on the user, offers its press alone (`offerPress`), which the field says at
   its end after the words it already says. There is no second surface for news, so
   nothing floats in a corner to become a stale pointer target. A failure is no news: it
   goes through errors.js, which keeps it until the user has dealt with it.

   The moments the panel's leaf answers with a gesture pass through here too (`gesture`),
   each with its ordinal, so the leaf plays once for each, a repeat included
   (floating-panel.js, `GESTURES`): a notice of the user's own command, a walk's step,
   an error about no field, the agent picking up work, and the news a shown notice
   carries, whose moment its producer names (`moment`). Everything else, a notice of
   a failed response among them, moves nothing. */
import { el, elementDirective } from "./widget-elements.js";
import { keeps } from "./keeps.js";
import { effect, signal, untracked } from "/runtime/framework.js";
import { ANNOUNCE } from "./widget-upgrade.js";
import { leafSays, wordsText } from "./voice.js";
import { onUserInput } from "./focus.js";

/** @typedef {import("./voice.js").Words} Words
 * @typedef {import("./semantic-news.js").SemanticNews} SemanticNews
 * @typedef {"notice" | "walk" | "error" | "pickup" | "version" | "reply" | "new-on-me" | "on-me-empty"} Moment
 * @typedef {{key: "semantic-news", value: readonly SemanticNews[],
 * combine: (older: readonly SemanticNews[], newer: readonly SemanticNews[]) => readonly SemanticNews[],
 * format: (value: readonly SemanticNews[]) => Words,
 * moment?: (value: readonly SemanticNews[]) => Moment | null}} SemanticBackground
 * @typedef {SemanticBackground | {key: "text", value: Words, moment: Moment | null}} Background
 * @typedef {{action: string, command: string, run: () => unknown, stands: () => boolean}} NoticePress
 */

export const liveEl = el("div", "lf-ui lf-live");
liveEl.setAttribute("aria-live", "polite");

// How long a notice holds its seat before the seat's own words come back: long
// enough to read a recorded acknowledgement, short enough that the state behind it is
// never far away.
const NOTICE_MS = 4000;

let noticeTimer = 0;
// Ends the watch on the standing notice's press (`showNotice`).
let stopWatchingPress = () => {};
/** @type {Background | null} */
let showingBackground = null;
// The news the leaf has answered already (`showNotice`).
/** @type {WeakSet<Background>} */
const gestured = new WeakSet();
/** @type {Background[]} */
const waitingBackground = [];
let userContext = false;
let userHoldTimer = 0;
// What the seat says, whether it shows, and the press it offers, or null: the action
// it is, the page command whose key makes the same press, what it does, and whether it
// still can, as `{action, command, run, stands}`. Errors are no notices: they go
// through errors.js, which keeps them until they are dealt with.
/** @type {import("@preact/signals-core").Signal<Readonly<{message: Words, visible: boolean, press: NoticePress | null}>>} */
const noticePresentation = signal(
  Object.freeze({ message: "", visible: false, press: null }),
);

export const noticeReading = () => noticePresentation.value;

// The latest moment the leaf answers, with its ordinal among them (`beat`).
/** @type {import("@preact/signals-core").Signal<Readonly<{moment: Moment | null, beat: number}>>} */
const gestures = signal(Object.freeze({ moment: null, beat: 0 }));
export const gestureReading = () => gestures.value;
/** @param {Moment} moment */
export function gesture(moment) {
  gestures.value = Object.freeze({ moment, beat: gestures.peek().beat + 1 });
}
const noticeVisible = () => noticePresentation.peek().visible;

// A notice is Leaf's news, so a notice given as a string is Leaf's words; one that
// relays the agent's words too is given as parts, each said by whoever says it
// (semantic-news.js), which the seat draws apart and the live region hears as one line
// (voice.js).
/** @param {Words} message */
export const noticeWords = (message) =>
  typeof message === "string" ? [leafSays(message)] : message;

// The reading changes in the gesture's task. Its seat paints visible news immediately
// and coalesces a withdrawal until the script ends, so replacing a notice paints once.
/** @param {Words} message @param {boolean} visible @param {NoticePress | null} [press] */
const presentNotice = (message, visible, press = null) => {
  noticePresentation.value = Object.freeze({ message, visible, press });
};

/** @param {Words} msg */
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
// `named`). A notice offering a press (`press`) has the field's end say that press's
// word and key, where Comment and its key stand at rest.
/** @param {Words} msg @param {Background | null} background @param {NoticePress | null} [press] */
function showNotice(msg, background = null, press = null) {
  presentNotice(msg, true, press);
  // A notice of the user's own command answers their key; news shows its own moment,
  // when it shows rather than when it arrived, so the leaf moves with its words, and
  // only the first time, not again once a command it waited behind has passed.
  const moment = !background
    ? "notice"
    : gestured.has(background)
      ? null
      : background.key === "text"
        ? background.moment
        : (background.moment?.(background.value) ?? null);
  if (background) gestured.add(background);
  if (moment) gesture(moment);
  showingBackground = background;
  clearTimeout(noticeTimer);
  stopWatchingPress();
  if (!press) noticeTimer = setTimeout(retireNotice, NOTICE_MS);
  // A notice another has replaced is no longer this watch's to retire.
  else
    stopWatchingPress = effect(() => {
      if (!press.stands() && noticePresentation.peek().press === press)
        untracked(retireNotice);
    });
}
function retireNotice() {
  stopWatchingPress();
  if (!userContext && !userHoldTimer && showBackground(waitingBackground.shift()))
    return;
  presentNotice(noticePresentation.peek().message, false);
  showingBackground = null;
}
// A press offered alone, with no words of its own (`offerPress`), or null.
/** @type {import("@preact/signals-core").Signal<NoticePress | null>} */
const offered = signal(null);
export const offeredPress = () => offered.value;
// Ends the watch on the offered press.
let stopWatchingOffer = () => {};
/** Offer `press` alone, as a notice offers its own: for the moment after a gesture of
 * the user's whose next step it is. @param {NoticePress} press */
export function offerPress(press) {
  stopWatchingOffer();
  offered.value = press;
  stopWatchingOffer = effect(() => {
    if (!press.stands() && offered.peek() === press) untracked(withdrawOffer);
  });
}
function withdrawOffer() {
  stopWatchingOffer();
  stopWatchingOffer = () => {};
  offered.value = null;
}
// A press stands until the user's next input rather than for its time, and no longer
// than it can act: a gesture the log refused, or one taken back by any route, takes its
// notice away, and an offered press goes once it has nowhere to go. The panel says the
// press at the field's end (floating-panel.js, `fieldReading`), so one leaving on a
// timer would take it from under a hand on its way there. An input on the press itself,
// which `keepsNotice` marks, keeps it.
const NOTICE_PRESS = "data-lf-notice-press";
export const keepsNotice = elementDirective("keepsNotice", (element) =>
  keeps(element, NOTICE_PRESS, ""),
);
onUserInput((event) => {
  const pressing = Boolean(noticePresentation.peek().press);
  if (!pressing && !offered.peek()) return;
  const path = event.composedPath?.() ?? [];
  if (path.some((node) => node instanceof Element && node.hasAttribute(NOTICE_PRESS)))
    return;
  if (pressing) retireNotice();
  withdrawOffer();
});

// A producer may retire a deferred assertion before it reaches the seat.
// Skip it without spending a visible interval, then take the next queued group.
/** @param {Background | undefined} entry */
function showBackground(entry) {
  while (entry) {
    const message = entry.key === "text" ? entry.value : entry.format(entry.value);
    if (wordsText(message)) {
      showNotice(message, entry);
      return true;
    }
    entry = waitingBackground.shift();
  }
  return false;
}

/** @param {Words} message @param {Moment | null} moment @returns {Background} */
const textBackground = (message, moment) => ({
  key: "text",
  value: message,
  moment,
});

// The producer supplies what makes two deferred notices one piece of news. An
// interrupted displayed entry is older than anything already waiting under its key;
// ordinary new arrivals are newer. One pending entry per key bounds the backlog.
/** @param {Background} entry */
function queueBackground(entry, front = false) {
  const waiting = waitingBackground.find((waiting) => waiting.key === entry.key);
  if (waiting) {
    waitingBackground.splice(waitingBackground.indexOf(waiting), 1);
    if (entry.key === "semantic-news" && waiting.key === "semantic-news")
      entry = {
        ...entry,
        value: front
          ? entry.combine(entry.value, waiting.value)
          : entry.combine(waiting.value, entry.value),
      };
    else if (front) entry = waiting;
  }
  if (front) waitingBackground.unshift(entry);
  else waitingBackground.push(entry);
}

// User commands own the next brief interval. Background arrivals wait behind one,
// while a command can interrupt an arrival and let it return after the acknowledgement.
// A held status line coalesces each producer's news; the live region announces it now.
// Background news names the moment the leaf answers it with (`moment`), or none.
/** @param {Words} msg @param {{background?: boolean, announce?: boolean, group?: SemanticBackground | null,
 * press?: NoticePress | null, moment?: Moment | null}} options */
export function notice(
  msg,
  {
    background = false,
    announce: speak = true,
    group = null,
    press = null,
    moment = null,
  } = {},
) {
  // The live region is not the contended surface. Announce at arrival even when the
  // visual line has to wait, and never announce again when a waiting notice is shown.
  if (speak) announce(msg);
  if (background) {
    const entry = group ?? textBackground(msg, moment);
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
  stopWatchingPress();
  presentNotice(noticePresentation.peek().message, false);
  showingBackground = null;
}

// A semantic walk is an immediate user command even though its feedback is the live
// ordinal rather than a timed notice. Hold arriving news for a moment after the step;
// beginWalk calls this only for gestures, so ordinary repaints never restart the hold.
/** @param {number} ms */
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
/** @param {boolean} active */
export function setNoticeContext(active) {
  userContext = active;
  if (active && showingBackground) yieldNotice();
  else if (!active && !userHoldTimer && waitingBackground.length && !noticeVisible()) {
    showBackground(waitingBackground.shift());
  }
}
