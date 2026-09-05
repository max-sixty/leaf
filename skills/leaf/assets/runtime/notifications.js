/* Notices and announcements.

   News arriving without the reader's send gesture may show a notice and count but does
   not move focus or scroll the panel. `notice` is the one visible surface for a
   moment's news — a recorded gesture, an arrived version, a refused send — and it
   stands in the banner's status slot in place of the status line, which returns when
   the notice fades; the live region hears the same words. It is text rather than a
   control: what a notice names, the banner's own buttons reach. There is no second
   surface for news, so nothing floats in a corner to become a stale pointer target. */
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

  // The acknowledgement of a gesture ("Moved to Done — sent"), an arrival ("Updated
  // to v3"), a refusal ("Nothing to send — the box is empty"): the corner the reader
  // already watches for the page's state, rather than that corner and a toast at the
  // opposite one. A sentence that is also a button for four seconds is a target the
  // reader cannot learn.
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
