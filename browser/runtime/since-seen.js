// @ts-check
/* What the page changed since the user last saw it.

   A revision counts as seen when it is on the page while the user is there: the
   document visible, holding focus, and its reading continuous (reading-continuity.js).
   Focus is the same evidence a message's read waits for (thread/read.js): a browser
   standing beside the terminal the user types into is visible but not being read, so
   revisions landing then are not seen. A revision that lands while the user is there
   is shown by the tint its install gives each block it changed (version.js,
   `activateRevision`), and is seen.

   When the user comes back, by a load, a return to a hidden tab once its first
   refreshed reading is in, or focus returning to the window, this owner marks what
   changed since the newest revision they saw, through the version comparison
   (version.js, `offerComparison`), whose block marks, Change margin entries and `h` walk
   (change-walk.js) every comparison shares. That newest revision is the higher of two
   readings: the server's `seen` (`read_state.seen_revision`), which every tab and
   browser of the page's one user writes, and the one this tab saw itself. A revision
   installed into a fresh document (a changed executable reloads the tab, version.js,
   `reloadInto`) never animates, so it was not seen and is marked once the new document
   is there: what the user did not watch land is marked, whichever way it landed.

   When the user leaves, the tab going hidden or closing or the window losing focus to
   another application, it posts a `seen` event naming the newest revision it saw, with
   `keepalive` so a closing document's send arrives, and hands the same revision to the
   document a reload brings (tab storage, read once), so a reload does not mark what the
   user watched land because its first reading came before the send. A comparison this
   owner offered follows the server's reading as it catches up, as when another tab's
   send lands after this one's reading: it re-bases where the newer seen revision is
   still behind the page, and stops where it reaches it. A comparison the reader chose
   in Versions outranks the offer and is left alone.

   Whether the user saw a revision is a logged fact, not browser storage, for the reason
   a message's read is: the page has one user, who reads it in more than one browser and
   tab, and a mark of what they already saw in another would be wrong (`events.md`,
   "Read state"). Only the page itself takes part: a sample or other framed page is part
   of the page around it, and a reader of a hosted copy, who has no private page until
   they act (layer-client.js), neither records nor compares. */
import { LIVE_ROOT, runtime } from "./context.js";
import { effect } from "/runtime/framework.js";
import { onReadingInterrupted, readingIsContinuous } from "./reading-continuity.js";
import { sessionIsActive } from "./layer-client.js";
import { whenDocumentPresented } from "./semantic-state.js";
import { tabStore } from "./tab-store.js";
import {
  comparisonBase,
  offerComparison,
  revisionBase,
  stopComparison,
} from "./version.js";

const HANDOFF_KEY = "lf-seen-handoff";

/** @typedef {{revision: number, version: number | null, url: string, activated_at?: string}} Seen */

/** @param {{ markSeen: (revision: number) => unknown }} capabilities */
export function createSinceSeen({ markSeen }) {
  // An arrival or a return the comparison has not yet answered.
  let arriving = true;
  // The newest live revision this tab showed the user, or the one a reload handed over.
  /** @type {Seen | null} */
  let shown = null;
  try {
    shown = JSON.parse(tabStore.get(HANDOFF_KEY) || "null");
  } catch {
    shown = null;
  }
  tabStore.set(HANDOFF_KEY, null);
  // The base of the comparison this owner offered, while it may still stand.
  let offered = /** @type {number | null} */ (null);
  // The newest revision this tab has posted, so a blur and the hide after it send once.
  let posted = 0;

  const takesPart = () =>
    window === window.top && LIVE_ROOT && sessionIsActive() && runtime.state !== null;
  const attended = () =>
    document.visibilityState === "visible" &&
    document.hasFocus() &&
    readingIsContinuous();
  const newestSeen = () => {
    const seen = runtime.seen;
    return !shown || (seen && seen.revision >= shown.revision) ? seen : shown;
  };

  function present() {
    const current = runtime.currentRevision;
    if (!takesPart() || current === null || !runtime.showsActive) return;
    // An offer follows the server's reading as it catches up: another tab's or a
    // departing document's send that landed after this tab's first reading. What this
    // tab saw itself and posted is no news to its own offer, whose marks stand until
    // the reader stops them.
    const seen = runtime.seen;
    if (
      offered !== null &&
      seen &&
      seen.revision > Math.max(offered, posted) &&
      comparisonBase()?.revision === offered
    ) {
      stopComparison();
      offered = seen.revision < current ? seen.revision : null;
      if (offered !== null) offerComparison(revisionBase(seen));
    }
    if (!attended()) return;
    const base = newestSeen();
    if (arriving) {
      arriving = false;
      if (base && base.revision < current && comparisonBase() === null) {
        const since = revisionBase(base);
        offered = since.revision;
        void whenDocumentPresented().then(() => offerComparison(since));
      }
    }
    if (runtime.active && (shown?.revision ?? 0) < current) shown = runtime.active;
  }

  function leave() {
    arriving = true;
    if (!shown || !takesPart()) return;
    tabStore.set(HANDOFF_KEY, JSON.stringify(shown));
    if (shown.revision > Math.max(runtime.seen?.revision ?? 0, posted)) {
      posted = shown.revision;
      markSeen(shown.revision);
    }
  }

  onReadingInterrupted(() => {
    arriving = true;
  });
  // Continuity and focus return on document and window events rather than signals; the
  // state's readers are signals, which the effect follows.
  document.addEventListener("lf-reading-continuity", present);
  addEventListener("focus", present);
  // Focus moving into a frame of this page blurs the window but keeps the user here,
  // which `hasFocus` answers once the move is done.
  addEventListener("blur", () =>
    setTimeout(() => {
      if (!document.hasFocus()) leave();
    }),
  );
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") leave();
  });
  addEventListener("pagehide", leave);
  effect(present);
}
