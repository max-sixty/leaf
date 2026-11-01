// @ts-check
/* What the page changed since the user last saw it.

   Turned off: application.js no longer mounts this owner, at the user's request on
   31 October, while marks tied to Versions are considered. Nothing below runs, and no
   tab posts `seen`.

   A revision counts as seen when it is on the page while the user is there: the
   document visible, holding focus, and its reading continuous (reading-continuity.js).
   Focus is the same evidence a message's read waits for (thread/read.js): a browser
   standing beside the terminal the user types into is visible but not being read, so
   revisions landing then are not seen. A revision that lands while the user is there
   is shown by the tint its install gives each block it changed (version.js,
   `activateRevision`), and is seen.

   When the user comes back, by a load, a return to a hidden tab once its first
   refreshed reading is in, or focus returning to the window, this owner marks what
   changed since the version they last saw, through the version comparison (version.js,
   `offerComparison`), whose block marks, Change margin entries and `h` walk
   (change-walk.js) every comparison shares. That version is the newest stamped one at
   or before the newest revision they saw, which is the higher of two readings: the
   server's `seen` (`read_state.seen_revision`), which every tab and browser of the
   page's one user writes, and the one this tab saw itself. The marks count from a
   version rather than the revision itself so they move on at a point the leaf's row
   names, once the user has seen a newer version, rather than at a departure they can't
   see; the user chose this on 31 October over counting from the revision they left,
   from the previous version, and from each change until they looked at it. So drafts
   between versions add up in the marks, and a page with no version at or before what
   the user saw marks nothing. A revision installed into a fresh document (a changed
   executable reloads the tab, version.js, `reloadInto`) never animates, so it was not
   seen and is marked once the new document is there.

   When the user leaves, the tab going hidden or closing or the window losing focus to
   another application, it posts a `seen` event naming the newest revision it saw, with
   `keepalive` so a closing document's send arrives, and hands the same revision to the
   document a reload brings (tab storage, read once), so a reload does not mark what the
   user watched land because its first reading came before the send.

   The marks are annotations and have no stop of their own (change-walk.js). An offer
   stands, taking in each revision that lands while the user watches, until a return
   finds a newer version seen: then it starts again from that version, or ends where
   that version is the page. A return before then keeps the marks and the walk's place.
   An offer also follows the server's reading as it catches up, as when another tab's
   send lands after this one's reading. A comparison the reader chose in Versions
   outranks the offer and is left alone.

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

/** @typedef {import("../types/contract.js").ServedRevision} Seen */

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
  /** @type {number | null} */
  let offered = null;
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
  // The newest stamped version at or before a revision the user saw, which the marks
  // count from.
  /** @param {{revision: number} | null} seen */
  const versionAt = (seen) =>
    seen
      ? (runtime.versions.findLast((entry) => entry.revision <= seen.revision) ?? null)
      : null;

  function present() {
    const current = runtime.currentRevision;
    if (!takesPart() || current === null || !runtime.showsActive) return;
    // An offer follows the server's reading as it catches up: another tab's or a
    // departing document's send that landed after this tab's first reading. What this
    // tab saw itself and posted is no news to its own offer, which stands until a
    // return finds a newer version seen.
    const seen = runtime.seen;
    const caught = versionAt(seen);
    if (
      offered !== null &&
      seen &&
      seen.revision > posted &&
      caught &&
      caught.revision > offered &&
      comparisonBase()?.revision === offered
    ) {
      stopComparison();
      offered = caught.revision < current ? caught.revision : null;
      if (offered !== null) offerComparison(revisionBase(caught));
    }
    if (!attended()) return;
    if (arriving) {
      arriving = false;
      const since = versionAt(newestSeen());
      const standing = comparisonBase();
      const movesOn =
        since !== null &&
        (standing === null ||
          (offered !== null &&
            standing.revision === offered &&
            since.revision > offered));
      if (movesOn) {
        if (standing !== null) stopComparison();
        offered = null;
        if (since.revision < current) {
          const base = revisionBase(since);
          offered = base.revision;
          void whenDocumentPresented().then(() => offerComparison(base));
        }
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
