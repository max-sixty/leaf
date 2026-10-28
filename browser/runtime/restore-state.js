/* `USER_VIEW_RESTORE_CASES` declares each stored runtime arrangement the render suite
   must visit. Add a new remembered surface here when the surface is introduced.

   Every way this page can come up that is not a first visit, each named by the fact its
   store holds. The browser gate arrives once in each, because every other reading it
   takes is of a first visit: a fresh context holds nothing, so the mode is off. So the
   restores are the one road onto the page the gate does not walk on its own. Declared
   here rather than listed in the gate, because a list over there stops at the surfaces
   it was taught; this one is read on the day a surface starts remembering something.
   One stored fact each rather than the combinations of them: what a finding has to name
   is the restore that broke, and the geometry the combinations would add is measured on
   the first visit already. */
import { tabStore } from "./tab-store.js";
import { DESIGN_MODE_KEY } from "./design-readings.js";
// The tab coordinate is shared by restoration evidence and the optional owner.
export const ANNOTATIONS_KEY = "lf-annotations";

export const USER_VIEW_RESTORE_CASES = [
  { name: "design mode on", ...tabStore.where(DESIGN_MODE_KEY), value: "1" },
  { name: "annotations hidden", ...tabStore.where(ANNOTATIONS_KEY), value: "hidden" },
];

// The chrome put back the way this user left it, before the page is presented. A view
// of the floating panel lasts only while it is used, so none comes back with the page.
export function restoreUserView({ setDesignMode }) {
  if (tabStore.get(DESIGN_MODE_KEY) === "1") setDesignMode(true, { spoken: false });
}
