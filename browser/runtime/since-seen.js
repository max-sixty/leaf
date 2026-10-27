// @ts-check
/* What the page changed since the user was last shown it.

   The server reads the newest revision a tab showed the user before they left it (the
   state's `seen`, `read_state.seen_revision`). This owner adds the evidence only a tab
   has: when the user leaves, it posts a `seen` event naming the live revision it showed
   them in a visible document. When they arrive at the page or come back to it, it marks
   what changed since that revision, through the version comparison (version.js,
   `offerComparison`), whose block marks, Change margin entries and `h` walk
   (change-walk.js) every comparison shares.

   Only an arrival or a return compares: a load, or the first refreshed reading after
   the tab was hidden (reading-continuity.js), which has installed whatever the agent
   revised meanwhile. A revision landing while the reader watches is shown by the tint
   its install gives each block it changed (version.js, `activateRevision`); marking it
   too would pile marks under a reader who saw each change arrive. The comparison holds
   its base for the life of this document, so the marks stand until the reader stops
   them in Versions or leaves.

   The post waits for the user to leave, the page lifecycle's last reliable moment:
   the tab going hidden, which also comes before it closes or reloads, sent with
   `keepalive` so it outlives the document. One post a visit, rather than one for each
   revision shown, keeps the log to what a later visit reads. A post that never lands
   leaves the older revision as the base, which marks more than the user missed but
   nothing they hadn't.

   Whether the user was shown a revision is a logged fact, not browser storage, for the
   reason a message's read is: the page has one user, who reads it in more than one
   browser and tab, and a mark of what they already saw in another would be wrong
   (`events.md`, "Read state"). A reader of a hosted copy has no private page to record
   it in, so the post needs an active session (layer-client.js), as thread/read.js's
   does. */
import { LIVE_ROOT, runtime } from "./context.js";
import { effect } from "/runtime/framework.js";
import { onReadingInterrupted, readingIsContinuous } from "./reading-continuity.js";
import { sessionIsActive } from "./layer-client.js";
import { whenDocumentPresented } from "./semantic-state.js";
import { offerComparison, revisionBase } from "./version.js";

/** @param {{ markSeen: (revision: number) => unknown }} capabilities */
export function createSinceSeen({ markSeen }) {
  // An arrival or a return the comparison has not yet answered.
  let arriving = true;
  // The newest live revision this tab has shown in a visible document.
  let shown = 0;

  function present() {
    const seen = runtime.seen;
    const current = runtime.currentRevision;
    if (
      !LIVE_ROOT ||
      runtime.state === null ||
      current === null ||
      !runtime.showsActive ||
      !readingIsContinuous()
    )
      return;
    shown = Math.max(shown, current);
    if (!arriving) return;
    arriving = false;
    if (seen !== null && seen.revision < current) {
      const base = revisionBase(seen);
      void whenDocumentPresented().then(() => offerComparison(base));
    }
  }

  function leave() {
    if (shown > (runtime.seen?.revision ?? 0) && sessionIsActive()) {
      markSeen(shown);
      shown = 0;
    }
  }

  onReadingInterrupted(() => {
    arriving = true;
  });
  // Continuity returns on a document event rather than a signal; the state's readers
  // are signals, which the effect follows.
  document.addEventListener("lf-reading-continuity", present);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") leave();
  });
  window.addEventListener("pagehide", leave);
  effect(present);
}
