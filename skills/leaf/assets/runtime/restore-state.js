/* `USER_VIEW_RESTORE_CASES` declares each stored runtime arrangement the render suite must visit,
   and supplies one for each persisted tray. Add a new remembered surface here when the
   surface is introduced.

   Every way this page can come up that is not a first visit, each named by the fact its
   store holds. The browser gate arrives once in each, because every other reading it
   takes is of a first visit: a fresh context holds nothing, so the panel is shut, no
   tray stands and the mode is off. So the restores are the one road onto the page the
   gate does not walk on its own. Declared here rather than listed in the gate, because a list over there stops at the surfaces it
   was taught; this one is read on the day a surface starts remembering something. One
   stored fact each rather than the combinations of them: what a finding has to name is
   the restore that broke, and the geometry the combinations would add is measured on
   the first visit already. */
import { userStore, tabStore } from "./storage.js";
import { AUXILIARY_SURFACE_KEY } from "./auxiliary-surfaces.js";
import { DESIGN_MODE_KEY } from "./design-readings.js";

export const USER_VIEW_RESTORE_CASES = [
  {
    name: "the thread panel open",
    ...userStore.where(AUXILIARY_SURFACE_KEY),
    value: "threads",
  },
  {
    name: "the thread panel at the width the user drew it to",
    ...userStore.where("lf-thread-panel-width"),
    value: "560",
  },
  {
    name: "the tray panel at the width the user drew it to",
    ...userStore.where("lf-tray-slot-width"),
    value: "260",
  },
  ...["leaves", "asks"].map((tray) => ({
    name: `the ${tray} tray standing`,
    ...userStore.where(AUXILIARY_SURFACE_KEY),
    value: tray,
  })),
  { name: "design mode on", ...tabStore.where(DESIGN_MODE_KEY), value: "1" },
];

// The chrome put back the way this user left it, before the page is presented: the
// widths first, so a panel or tray put back open is open at the width they left it at
// rather than sliding to it afterwards.
export function restoreUserView({
  commentsEdge,
  traysEdge,
  restoreAuxiliarySurface,
  setDesignMode,
}) {
  // The widths first, so a panel or a tray put back open is open at the width the user
  // left it at rather than sliding to it afterwards.
  commentsEdge.restore();
  traysEdge.restore();
  restoreAuxiliarySurface();
  if (tabStore.get(DESIGN_MODE_KEY) === "1") setDesignMode(true, { spoken: false });
  delete document.documentElement.dataset.lfRestoreSurface;
}
