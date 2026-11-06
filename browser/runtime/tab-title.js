/* The tab's title: the page's authored title, with what waits on the user counted in
   front of it while it is above zero ("(2) Finish the ship review").

   The user chose this (2026-11-05, "Count On me in the tab"): someone waiting on the
   agent has the terminal in front of them and the page in a tab, and the favicon says
   the agent's state but not whether anything waits on them. The count is On me's own
   (`onUserCount`, queue-api.js), so the tab and the panel's badge show one number.

   The authored `<title>` is never written. A revision replaces the authored head nodes
   when they differ from its source (version.js, `activateHead`), so a prefix written
   into that node would make every revision replace it. The count lives in a second,
   runtime-marked `<title>` placed first in the head, which the browser prefers
   (`document.title` reads the first), and which exists only while the count is above
   zero. At zero the authored title is the tab's, so a page that waits on nobody is
   untouched.

   `authoredTitle()` is what other readers of "this page's title" use (All pages,
   live-leaves.js; a thread card's trail, thread-card.js); `document.title` now says the
   tab's. A revision replaces the authored title node (version.js, `activateHead`), which
   the head observer follows: its work is one head's, not the page's size. */

const TAB = document.createElement("title");
TAB.dataset.lfRuntime = "";

/** @param {string} text */
const squash = (text) => text.replace(/\s+/g, " ").trim();

export const authoredTitle = () =>
  squash(
    document.head.querySelector("title:not([data-lf-runtime])")?.textContent ?? "",
  );

let counted = 0;
/** @type {MutationObserver | null} */
let watch = null;

function draw() {
  if (counted <= 0) {
    if (TAB.isConnected) TAB.remove();
    return;
  }
  const text = `(${counted}) ${authoredTitle()}`.trim();
  if (TAB.textContent !== text) TAB.textContent = text;
  if (document.head.firstChild !== TAB) document.head.prepend(TAB);
}

/** Show `count` in the tab's title; a repeated reading writes nothing.
    @param {number} count */
export function paintTabTitle(count) {
  counted = count;
  if (!watch) {
    watch = new MutationObserver(draw);
    watch.observe(document.head, {
      childList: true,
      characterData: true,
      subtree: true,
    });
  }
  draw();
}
