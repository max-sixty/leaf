// @ts-check
/* What changed since the user last saw the page, and `v`, which marks it.

   A revision counts as seen when it is on the page while the user is there: the
   document visible, holding focus, and its reading continuous (reading-continuity.js).
   Focus is the same evidence a message's read waits for (thread/read.js): a browser
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
   user chose on 31 October to count from a version, which a notice can name, rather
   than from the revision they left, from the previous version, or from each change
   until they looked at it. So drafts between versions add up, and a page with no
   version at or before what the user saw has nothing to say.

   When the user comes back, by a load, a return to a hidden tab once its first
   refreshed reading is in, or focus returning to the window, to a revision newer than
   any they saw, a notice says how much changed since the version they last saw ("3
   changes since v12") and offers `v`. A return to a draft they watched land says
   nothing, though it differs from that version, since nothing in it is news. The notice
   stands until their next input, as a notice offering a press does (notifications.js),
   and no longer than its count holds: a revision landing takes it away, and one landing
   while it is counted starts the count again. The page arrives unmarked: the user chose on 3 November to call
   the marks up with a key rather than have them waiting, and on 4 November took up
   being told on return that there is something to call up. The count waits until the
   document is presented, so the comparison it runs (version.js, `changesSince`) stays
   off the path to first showing the page.

   `v` marks what changed since the version the user last saw while the page holds
   changes since then, and otherwise since the newest version older than the one being
   read; pressing it again takes off any comparison, whichever press started it. The
   user chose a toggle over a key that opens Versions and re-marks the page as its rows
   are walked. An older base stays with Versions, which `g V` opens. The version is the
   one found at the user's arrival, so watching a revision land doesn't move what `v`
   compares with until they leave and come back.

   Only the page itself takes part: a sample or other framed page is part of the page
   around it, and a reader of a hosted copy, who has no private page until they act
   (layer-client.js), neither records nor is told. */
import { LIVE_ROOT, runtime } from "./context.js";
import { effect, signal } from "/runtime/framework.js";
import { onReadingInterrupted, readingIsContinuous } from "./reading-continuity.js";
import { sessionIsActive } from "./layer-client.js";
import { whenDocumentPresented } from "./semantic-state.js";
import { tabStore } from "./tab-store.js";
import { notice } from "./notifications.js";
import { pageCommand } from "./keyboard/register.js";
import { savedReadingSettled } from "./keyboard/bindings.js";
import {
  changesSince,
  comparable,
  endComparison,
  revisionBase,
  selectedBase,
  showComparison,
} from "./version.js";
import { counted } from "./words.js";

const HANDOFF_KEY = "lf-seen-handoff";
const CHANGES = "changes.toggle";

/** @typedef {import("../types/contract.js").ServedRevision} Seen
 * @typedef {import("../types/contract.js").ServedReading["versions"][number]} Version */

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
  // Which arrival a count in flight answers, so a later one's news replaces it.
  let arrival = 0;
  // The version the user last saw, as their arrival found it.
  const lastSeen = signal(/** @type {Version | null} */ (null));

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
  // What `v` compares with: the version the user last saw while the page has changed
  // since, otherwise the newest version older than the one being read.
  const base = () => {
    const since = lastSeen.value;
    return since && comparable(since.revision)
      ? since
      : (runtime.versions.findLast((entry) => comparable(entry.revision)) ?? null);
  };
  const toggle = () => {
    if (selectedBase()) return endComparison();
    const since = base();
    if (since) return showComparison(revisionBase(since));
  };
  const named = () => {
    const since = base();
    return since ? ` since v${since.version}` : "";
  };
  pageCommand({
    id: CHANGES,
    ready: savedReadingSettled,
    keys: ["v"],
    title: () => (selectedBase() ? "hide changes" : `show changes${named()}`),
    touch: () => (selectedBase() ? "Hide changes" : `Show changes${named()}`),
    menu: "annotate",
    when: () => selectedBase() !== null || base() !== null,
    run: toggle,
  });

  // The notice of what changed since `since`, said once the count is in and while it
  // holds: no later arrival, nothing marked meanwhile, `v` still comparing with that
  // version, and the revision counted still the one being read.
  /** @param {Version} since */
  async function tell(since) {
    const mine = ++arrival;
    const holds = () =>
      mine === arrival && !selectedBase() && base()?.revision === since.revision;
    await whenDocumentPresented();
    while (holds()) {
      const revision = runtime.currentRevision;
      const n = await changesSince(revisionBase(since)).catch(() => undefined);
      if (n === undefined) return;
      if (n === null || runtime.currentRevision !== revision) continue;
      if (n && holds())
        notice(`${counted(n, "change")} since v${since.version}`, {
          press: {
            action: "show",
            command: CHANGES,
            run: toggle,
            stands: () => holds() && runtime.currentRevision === revision,
          },
        });
      return;
    }
  }

  function present() {
    const current = runtime.currentRevision;
    if (!takesPart() || current === null || !runtime.showsActive || !attended()) return;
    if (arriving) {
      arriving = false;
      const seen = newestSeen();
      const since = versionAt(seen);
      lastSeen.value = since;
      if (since && seen && seen.revision < current && comparable(since.revision))
        void tell(since);
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
