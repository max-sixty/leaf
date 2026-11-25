// @ts-check
/* What changed since the user last saw the page, and the version Versions names for it.

   A revision counts as seen when it is on the page while the user is there: the
   document visible, holding focus, and its reading continuous (base/reading-continuity.js).
   Focus is the same evidence a message's read waits for (records/thread/read.js): a browser
   standing beside the terminal the user types into is visible but not being read, so
   revisions landing then are not seen. When the user leaves, the tab going hidden or
   closing or the window losing focus to another application, the tab posts a `seen`
   event naming the newest revision it showed them, with `keepalive` so a closing
   document's send arrives, and hands the same revision to the document a reload brings
   (tab storage, read once), so a reload does not count as unseen what the user watched
   land. Whether the user saw a revision is a logged fact, not browser storage, for the
   reason a message's read is: the page has one user, who reads it in more than one
   browser and tab (`events.md`, "Read state").

   The version the user last saw is the newest stamped one at or before the newest
   revision they saw: the higher of the server's `seen` (`read_state.seen_revision`),
   which every tab of the page's one user writes, and what this tab showed itself. The
   user chose to count from a version, which a notice can name, rather
   than from the revision they left, from the previous version, or from each change
   until they looked at it. So drafts between versions add up, and a page with no
   version at or before what the user saw has nothing to say.

   When the user comes back, by a load, a return to a hidden tab once its first
   refreshed reading is in, or focus returning to the window, to a revision newer than
   any they saw, a notice says how much changed since the version they last saw ("3
   changes since v12") and offers Show changes as its press (transport/notifications.js,
   `press`), which marks those changes. A return to a draft they watched land says
   nothing, though it differs from that version, since nothing in it is news. The
   notice is news, as a version's arrival is: it waits behind the user's own commands
   and passes with its press after a notice's time (transport/notifications.js), and Versions
   keeps the lasting route. A revision landing while the notice is counted starts the
   count again. The page arrives unmarked: the user chose to call the marks
   up with a key rather than have them waiting, and to be told on return that there is
   something to call up, in a notice that passes like the others. Rejected: holding the
   notice and its press until the user's next input, as an Undo's is held, which held
   the panel's seat for the agent's status until the user acted. The count waits until
   the document is presented, so the comparison it runs (features/version.js, `changesSince`)
   stays off the path to first showing the page.

   Versions names the version the user last saw "last seen" while the page holds
   changes since then, and opens on it, else on the newest older version (features/version.js,
   `sawLast`). `v` there presses the Compare of the version the user stands on, so
   `g V v` marks what Show changes does, and the same keys take the marks off again,
   since Versions opens on the version compared with. Show changes names Versions'
   Compare key, so its keys read `g V v` (dom/keyboard/control-keys.js, `pressNow`). The
   user chose to keep this comparison in Versions, where every other base is, at the
   cost of three presses rather than one. Rejected:
   a page key of its own, a bare `v` toggling it on every page, which set the
   comparison apart from Versions. The version is the one found at the user's arrival,
   so watching a revision land doesn't move what Versions names until they leave and
   come back.

   Only the page itself takes part: a sample or other framed page is part of the page
   around it, and a reader of a hosted copy, who has no private page until they act
   (transport/layer-client.js), neither records nor is told. */
import { LIVE_ROOT, runtime } from "../state/context.js";
import { effect, signal } from "/vendor/signals-core.js";
import {
  onReadingInterrupted,
  readingIsContinuous,
} from "../base/reading-continuity.js";
import { sessionIsActive } from "../transport/layer-client.js";
import { whenDocumentPresented } from "../state/semantic-state.js";
import { tabStore } from "../state/tab-store.js";
import { notice } from "../transport/notifications.js";
import {
  changesSince,
  comparable,
  revisionBase,
  sawLast,
  selectedBase,
  showComparison,
  versionsShown,
} from "../features/version.js";
import { counted } from "../lib/words.js";

const HANDOFF_KEY = "lf-seen-handoff";

/** @typedef {import("../../types/contract.js").ServedRevision} Seen
 * @typedef {import("../../types/contract.js").ServedReading["versions"][number]} Version */

/** @param {{ markSeen: (revision: number) => unknown }} capabilities */
export function createSinceSeen({ markSeen }) {
  // A load or a return the user hasn't yet been told about.
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
  // The newest revision this tab has posted, so a blur and the hide after it send once.
  let posted = 0;
  // Counts arrivals, so a count in flight answers only the arrival that started it, and
  // its notice stands only until the next (transport/notifications.js, `stands`).
  const arrival = signal(0);

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
  /** @param {{revision: number} | null} seen */
  const versionAt = (seen) =>
    seen
      ? (runtime.versions.findLast((entry) => entry.revision <= seen.revision) ?? null)
      : null;
  // The notice of what changed since `since`, said once the count of the revision
  // being read is in, and only while no later arrival has come, nothing is marked
  // meanwhile and the page still holds changes since that version.
  /** @param {Version} since @param {number} mine */
  async function tell(since, mine) {
    const holds = () =>
      mine === arrival.value && !selectedBase() && comparable(since.revision);
    await whenDocumentPresented();
    const n = await changesSince(revisionBase(since), holds).catch(() => null);
    if (n && holds())
      notice(`${counted(n, "change")} since v${since.version}`, {
        background: true,
        stands: holds,
        press: {
          action: "show-changes",
          // Versions' Compare key, `g V v`, which compares the version Versions opens
          // at, this one. While Versions stands, its `v` compares whichever version
          // the user is on, so the press names no command and shows no keys there.
          get command() {
            return versionsShown() ? null : "panel.floating.versions.compare";
          },
          run: () => showComparison(revisionBase(since)),
          stands: holds,
        },
      });
  }

  function present() {
    const current = runtime.currentRevision;
    if (!takesPart() || current === null || !runtime.showsActive || !attended()) return;
    if (arriving) {
      arriving = false;
      const mine = arrival.peek() + 1;
      arrival.value = mine;
      const seen = newestSeen();
      const since = versionAt(seen);
      sawLast(since);
      if (since && seen && seen.revision < current && comparable(since.revision))
        void tell(since, mine);
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
