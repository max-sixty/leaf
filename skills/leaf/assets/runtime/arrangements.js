/* `ARRANGEMENTS` declares each stored runtime arrangement the render suite must visit,
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
import { readerStore, tabStore } from "./storage.js";
import { commentsEdge, PANEL_KEY, setPanel } from "./chrome-layout.js";
import { restoreTrays, TRAY_KEY, trayNames, traysEdge } from "./trays.js";
import { CHARACTER_SHORTCUTS_KEY } from "./keyboard/bindings.js";
import { DESIGN_KEY, setDesign } from "./design.js";

let publishedArrangements = [];

export const ARRANGEMENTS = [
  { name: "the thread panel open", ...readerStore.where(PANEL_KEY), value: "1" },
  {
    name: "the thread panel at the width the reader drew it to",
    ...readerStore.where(commentsEdge.key),
    value: "560",
  },
  {
    name: "the tray panel at the width the reader drew it to",
    ...readerStore.where(traysEdge.key),
    value: "260",
  },
  ...trayNames.map((tray) => ({
    name: `the ${tray} tray standing`,
    ...readerStore.where(TRAY_KEY),
    value: tray,
  })),
  {
    name: "character shortcuts off",
    ...readerStore.where(CHARACTER_SHORTCUTS_KEY),
    value: "0",
  },
  { name: "design mode on", ...tabStore.where(DESIGN_KEY), value: "1" },
];

// The chrome put back the way this reader left it, before the page is presented: the
// widths first, so a panel or tray put back open is open at the width they left it at
// rather than sliding to it afterwards.
export function restoreArrangements() {
  // The widths first, so a panel or a tray put back open is open at the width the reader
  // left it at rather than sliding to it afterwards.
  commentsEdge.restore();
  traysEdge.restore();
  if (readerStore.get(PANEL_KEY) === "1") setPanel(true);
  restoreTrays();
  if (tabStore.get(DESIGN_KEY) === "1") setDesign(true, { spoken: false });
}
