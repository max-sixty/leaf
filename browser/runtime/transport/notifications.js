/* Notices and announcements.

   News arriving without the user's send gesture may show a notice but does not move
   focus or scroll the panel. `notice` is the one visible surface for a moment's news,
   such as an arrived version or an undo, and it stands in one seat: the floating
   panel's seat for passing words, whose own words come back when the notice's time is
   up (panel/field-readings.js). A walk's step holds the seat for the same moment,
   said in the walk's live position rather than words given here (`answerStep`). A
   notice is text, but for the one press it may carry (`press`): after the user's own
   gesture, the press that matters most next, such as the next open thread after a
   Resolve or the undo that takes a gesture back (records/thread/folding.js, `nextStep`; records/undo.js,
   `offerUndo`), and with news, the press that shows what it reports, as Show changes
   does for the changes since the version the user last saw (host/since-seen.js). The
   floating panel's field says the press at its end, after the words, as "Resolved “One
   reconnect in about 40” … Next thread t". The press names a command (`command`),
   whose press it makes unless it brings its own `run`, as Show changes compares with
   the version the user last saw under Compare's keys (host/since-seen.js). It names none
   while no command would make its press, as Undo names ⌘Z only while ⌘Z would take
   the gesture its notice reports (records/undo.js, `offerUndo`). The field shows the press
   with the keys that would make that command now, and only while some would
   (panel/floating-panel.js, `pressReading`): so never on a touchscreen, where the panel's
   menu and lists reach
   what it does. The live region hears the words alone, and a screen reader meets the
   press as the button it is, its key inside. So a notice's words name no key: one
   written into them would stand where it makes no press, as on a touchscreen or with
   the caret in a box.
   A notice of a gesture stands no longer than its gesture does, so its press never
   acts for anything else. Any notice stands no longer than what its words say holds
   (`stands`), shown or waiting: news that a comparison would show changes goes once a
   comparison stands, and "No changes marked" once one marks some, rather than saying
   for the rest of its moment what the screen beside it contradicts. A notice of a change
   to where the user stands names that fact (`about`), as "Annotations hidden" names
   the annotations, so a surface whose words already say where the user stands, as the
   page field's do (panel/floating-panel.js, `standing`), leaves it to them, unless it offers
   a press, which those words don't, while the folded leaf's peek and a thread's field,
   which say none, show it. Only the panel knows which
   surface draws the seat, so such a notice holds it as any other does, unseen on the
   page field for its moment, with news waiting behind it there too. The user chose a
   notice's press, so a Resolve that moves the
   panel on leaves something there offering to take it back, over a notice of text
   alone, whose subject only the panel's own controls reach. There is no second surface
   for news, so nothing floats in a corner to become a stale pointer target. A failure
   is no news: it goes through errors.js, which keeps it until the user has dealt with
   it.

   The moments the panel's leaf answers with a gesture (`Moment`) pass through here too
   (`gesture`), each with its ordinal, so the leaf plays once for each, a repeat
   included (panel/floating-panel.js, `GESTURES`). A notice of the user's own command is
   one; each other moment's producer gives it, news as it arrives rather than when its
   notice shows. */
import { el } from "../lib/elements.js";
import { elementDirective } from "../lib/controls.js";
import { keeps } from "../lib/keeps.js";
import { effect, signal, untracked } from "/vendor/signals-core.js";
import { ANNOUNCE } from "../lib/widget-events.js";
import { leafSays, wordsText } from "../base/voice.js";
import { onUserInput } from "../dom/focus.js";
import { saying } from "../dom/keyboard/control-keys.js";

/** @typedef {import("../base/voice.js").Words} Words
 * @typedef {import("../../types/domain.js").SemanticNews} SemanticNews
 * @typedef {"notice" | "walk" | "error" | "pickup" | "version" | "reply" | "new-on-me" | "on-me-empty"} Moment
 * @typedef {{key: "semantic-news", value: readonly SemanticNews[],
 * combine: (older: readonly SemanticNews[], newer: readonly SemanticNews[]) => readonly SemanticNews[],
 * format: (value: readonly SemanticNews[]) => Words}} SemanticBackground
 * @typedef {SemanticBackground | {key: "text", value: Words, stands: (() => boolean) | null,
 * press: NoticePress | null}} Background
 * @typedef {{action: string, command: string | null, run?: () => unknown, stands: () => boolean}} NoticePress
 */

export const liveEl = el("div", "lf-ui lf-live");
liveEl.setAttribute("aria-live", "polite");

// How long a notice holds its seat before the seat's own words come back: long
// enough to read a recorded acknowledgement, short enough that the state behind it is
// never far away.
export const NOTICE_MS = 4000;

let noticeTimer = 0;
// Whether the standing notice's time is up and it stays until the user's next input
// (`showNotice`).
let holding = false;
// Ends the watch on what the standing notice says (`showNotice`).
let stopWatching = () => {};
/** @type {Background | null} */
let showingBackground = null;
/** @type {Background[]} */
const waitingBackground = [];
let userContext = false;
// What the seat says, whether it shows, the press it offers, or null: the action it
// is, the keys that would make the same press now, what it does, and whether it still
// can, as `{action, keys, run, stands}`; and whether it is news, which answers
// no gesture of the user's. Errors are no notices: they go through errors.js, which
// keeps them until they are dealt with.
/** @type {import("@preact/signals-core").Signal<Readonly<{message: Words, visible: boolean, press: NoticePress | null, about: string | null, news: boolean}>>} */
const noticePresentation = signal(
  Object.freeze({
    message: "",
    visible: false,
    press: null,
    about: null,
    news: false,
  }),
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
// (host/semantic-news.js), which the seat draws apart and the live region hears as one line
// (base/voice.js).
/** @param {Words} message */
export const noticeWords = (message) =>
  typeof message === "string" ? [leafSays(message)] : message;

// The reading changes in the gesture's task. Its seat paints visible news immediately
// and coalesces a withdrawal until the script ends, so replacing a notice paints once.
/** @param {Words} message @param {boolean} visible @param {NoticePress | null} [press]
 * @param {string | null} [about] @param {boolean} [news] */
const presentNotice = (message, visible, press = null, about = null, news = false) => {
  noticePresentation.value = Object.freeze({ message, visible, press, about, news });
};

/** @param {Words | (() => Words)} msg */
export function announce(msg) {
  // Removing and restoring the text node makes repeated identical announcements a
  // fresh live-region change, including when two arrivals' delays overlap. Words read
  // off the page, as the keys an announcement names (`saying`), come as a function,
  // read as they are said: after the gesture's frame has laid the page out, so the
  // reading lays out nothing in the gesture's own task.
  if (liveEl.firstChild) liveEl.replaceChildren();
  setTimeout(() => {
    if (liveEl.firstChild) liveEl.replaceChildren();
    liveEl.append(wordsText(typeof msg === "function" ? msg() : msg).trim());
  }, 30);
}

// A widget's words for a listener (`ANNOUNCE`, lib/widget-events.js), said here: the
// words themselves, or `{words, rows}`, the words and the command rows whose keys a
// listener hears after them, named as a press would reach them when the words are said
// (dom/keyboard/control-keys.js, `saying`).
addEventListener(ANNOUNCE, ({ detail }) =>
  announce(
    typeof detail === "object" && "rows" in detail
      ? () => [detail.words, saying(detail.rows)].filter(Boolean).join(" — ")
      : detail,
  ),
);

// An undo ("Undone: Chose “Fast” just now"), an arrival ("Updated to v3"): the
// quiet words in the panel's seat. A widget's gesture is no notice, since the widget
// draws it where it was made; the live region alone hears it (host/application.js,
// `named`). A notice offering a press (`press`) has the field's end say that press's
// word and key, where the page's own press stands at rest.
/** @param {Words} msg @param {Background | null} background @param {NoticePress | null} [press]
 * @param {(() => boolean) | null} [stands] @param {string | null} [about] @param {boolean} [holds] */
function showNotice(
  msg,
  background = null,
  press = null,
  stands = null,
  about = null,
  holds = false,
) {
  presentNotice(msg, true, press, about, Boolean(background));
  if (!background) gesture("notice");
  showingBackground = background;
  clearTimeout(noticeTimer);
  stopWatching();
  holding = false;
  // How long a notice stands, decided here alone (below).
  const stays = holds || Boolean(press && !background);
  noticeTimer = setTimeout(
    () => (stays ? (holding = true) : retireNotice()),
    NOTICE_MS,
  );
  // What the words say, and that the press can still act.
  const premises = [stands, press?.stands].filter((premise) => premise != null);
  if (!premises.length) return;
  // A notice another has replaced is no longer this watch's to retire.
  const shown = noticePresentation.peek();
  stopWatching = effect(() => {
    if (!premises.every((holds) => holds()) && noticePresentation.peek() === shown)
      untracked(retireNotice);
  });
}
function retireNotice() {
  holding = false;
  stopWatching();
  if (!userContext && !stepping.peek() && showBackground(waitingBackground.shift()))
    return;
  presentNotice(noticePresentation.peek().message, false);
  showingBackground = null;
}
// How long a notice stands is one rule, kept in one place (`showNotice`) so a better
// guess at what the user still needs can replace it whole. Every notice stands its
// time. One answering the user's own gesture with a press, or one its caller holds
// (`holds`), as an undo's is (records/undo.js), then stays until the user's next input: the
// panel says the press at the field's end, so one leaving on its timer would take it
// from under a hand on its way there. The user's inputs within its time leave it
// standing, so the Escape that takes the caret out of a reply box, where the field shows
// no press, shows a discard's Undo rather than ending its notice. News passes on its time,
// its press with it, since it answers nothing the user did: the user chose that news
// never hold the seat until they act (host/since-seen.js). A press stands no longer than it
// can act: a gesture the log refused, or one taken back by any route, takes its notice
// away. An input on the press itself, which `keepsNotice` marks, keeps it.
const NOTICE_PRESS = "data-lf-notice-press";
export const keepsNotice = elementDirective("keepsNotice", (element) =>
  keeps(element, NOTICE_PRESS, ""),
);
onUserInput((event) => {
  if (!holding || !noticePresentation.peek().visible) return;
  const path = event.composedPath();
  if (path.some((node) => node instanceof Element && node.hasAttribute(NOTICE_PRESS)))
    return;
  retireNotice();
});

// A producer may retire a deferred assertion before it reaches the seat, as news whose
// words no longer hold has. Skip it without spending a visible interval, then take the
// next queued group.
/** @param {Background | undefined} entry */
function showBackground(entry) {
  while (entry) {
    const message = entry.key === "text" ? entry.value : entry.format(entry.value);
    const stands = entry.key === "text" ? entry.stands : null;
    const press = entry.key === "text" ? entry.press : null;
    if (wordsText(message) && (stands?.() ?? true)) {
      showNotice(message, entry, press, stands);
      return true;
    }
    entry = waitingBackground.shift();
  }
  return false;
}

/** @param {Words} message @param {(() => boolean) | null} stands
 * @param {NoticePress | null} press @returns {Background} */
const textBackground = (message, stands, press) => ({
  key: "text",
  value: message,
  stands,
  press,
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
// `stands` says whether what the words say still holds, by signals it reads; a notice
// offering a press stands while its press does too. `about` names the fact where the
// user stands that the notice reports a change to (the header). `holds` keeps a notice
// past its time until the user's next input, as one with a press stays (above).
/** @param {Words} msg @param {{background?: boolean, announce?: boolean, group?: SemanticBackground | null,
 * press?: NoticePress | null, stands?: (() => boolean) | null, about?: string | null,
 * holds?: boolean}} options */
export function notice(
  msg,
  {
    background = false,
    announce: speak = true,
    group = null,
    press = null,
    stands = null,
    about = null,
    holds = false,
  } = {},
) {
  // The live region is not the contended surface. Announce at arrival even when the
  // visual line has to wait, and never announce again when a waiting notice is shown.
  if (speak) announce(msg);
  if (background) {
    const entry = group ?? textBackground(msg, stands, press);
    if (userContext || stepping.peek() || noticeVisible())
      return queueBackground(entry);
    return showBackground(entry);
  }
  if (stands && !stands()) return;
  if (showingBackground) queueBackground(showingBackground, true);
  showNotice(msg, null, press, stands, about, holds);
}

// Take the notice down for something the user asked for, putting a background notice
// it was showing back at the front of the queue. Unlike the notice's own timer, which
// retires it, this keeps the news for later.
function yieldNotice() {
  if (showingBackground) queueBackground(showingBackground, true);
  clearTimeout(noticeTimer);
  stopWatching();
  presentNotice(noticePresentation.peek().message, false);
  showingBackground = null;
}

// A walk's step is a command of the user's whose answer is the walk's live position
// rather than words of its own (records/walk-position.js), so the seat says that position for
// a notice's moment from the latest step (panel/field-readings.js, "notice"), and news
// arriving meanwhile waits for it as it waits for a notice. The walk itself stands
// where it landed after the moment; only the seat goes back to its own words, and a
// place a widget said goes with the moment. A walk answers only a step
// (records/walk-position.js, `stepTo`), so ordinary repaints never restart the moment.
let stepTimer = 0;
const stepping = signal(false);
export const answeringStep = () => stepping.value;
export function answerStep() {
  if (noticeVisible()) yieldNotice();
  clearTimeout(stepTimer);
  stepping.value = true;
  stepTimer = setTimeout(() => {
    stepping.value = false;
    if (userContext || noticeVisible() || !waitingBackground.length) return;
    showBackground(waitingBackground.shift());
  }, NOTICE_MS);
}

// Persistent command context outranks background news and pauses its visible interval.
// A foreground notice may still replace the context briefly, then the context returns.
/** @param {boolean} active */
export function setNoticeContext(active) {
  userContext = active;
  if (active && showingBackground) yieldNotice();
  else if (
    !active &&
    !stepping.peek() &&
    waitingBackground.length &&
    !noticeVisible()
  ) {
    showBackground(waitingBackground.shift());
  }
}
