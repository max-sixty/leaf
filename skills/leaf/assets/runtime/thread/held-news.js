/* Where a thread's news may grow it, and where it waits.

   A turn arriving in a thread grows it at the foot of its last turn, and a thread on
   the page grows in the page's flow. Where that line stands above the screen, the
   browser's scroll anchoring takes the growth into what the user has scrolled past;
   where it stands below, the growth moves nothing they see. Where it stands on screen,
   everything after it would move under the reader, so the thread holds the arrivals
   back and says so in its head row, in room the row already takes (`ThreadView`,
   thread-card.js). The arrivals show once the user opens them, sends a turn of their
   own in the thread, or leaves the line off screen, where they grow as news does
   anywhere else.

   The two readings here are that geometry: whether the line is on screen now, and when
   it leaves. */
import { shownBand } from "../geometry.js";
import { scrollersOf } from "../reading-regions.js";

// Whether growth after `node` would move what the user sees: the node's foot stands
// inside every box that scrolls it. A node not drawn has no foot to grow from.
export function growthAfterIsSeen(node) {
  const { bottom, height } = node.getBoundingClientRect();
  if (!height) return false;
  for (const box of scrollersOf(node)) {
    const band = shownBand(box);
    if (!band || bottom <= band.top || bottom >= band.bottom) return false;
  }
  return true;
}

// Calls `leave` once none of `node` shows in the window, and returns the step that
// stops watching. A node partly shown may already hold its foot off screen; waiting for
// all of it to go keeps the arrivals held a little longer than they need, never
// shorter.
export function whenOffScreen(node, leave) {
  const observer = new IntersectionObserver((entries) => {
    if (!entries.at(-1).isIntersecting) leave();
  });
  observer.observe(node);
  return () => observer.disconnect();
}
