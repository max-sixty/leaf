/* This module owns visual and assistive announcements: the live region, and the notice
 * that stands in the status line for a moment. */
let publishedNotifications;
export const announce = (...args) => publishedNotifications.announce(...args);
export const notice = (...args) => publishedNotifications.notice(...args);

// How long a notice holds the status line before the line's own words come back: long
// enough to read a recorded acknowledgement, short enough that the state behind it is
// never far away.
const NOTICE_MS = 4000;

export function createNotifications({ liveEl, noticeEl }) {
  let noticeTimer = 0;

  function announce(msg) {
    liveEl.textContent = "";
    setTimeout(() => (liveEl.textContent = msg), 30);
  }

  // A notice is the status line saying something else for a moment: the acknowledgement
  // of a gesture ("Moved to Done — recorded"), an arrival ("Updated to v3"), a refusal
  // ("Nothing to send — the box is empty"). It stands in the banner's status slot in the
  // line's place and the line returns when it fades, so the page has one place for news
  // — the corner the reader already watches for its state — rather than that corner and a
  // toast at the opposite one. The live region hears it as it appears.
  //
  // Text, not a control. What a notice names — Threads, the versions — the banner's own
  // buttons beside it already reach, and a sentence that is also a button for four
  // seconds is a target the reader cannot learn.
  function notice(msg) {
    announce(msg);
    noticeEl.textContent = msg;
    // The line it stands in for is the one thing on the row that gives up width when it
    // runs out — the addresses fold instead (see the theme) — so what a narrow window
    // clips is a hover away, as the line's own words are.
    noticeEl.title = msg;
    noticeEl.classList.add("show");
    clearTimeout(noticeTimer);
    noticeTimer = setTimeout(() => noticeEl.classList.remove("show"), NOTICE_MS);
  }

  const notifications = { announce, notice };
  publishedNotifications = notifications;
  return notifications;
}
