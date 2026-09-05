/* `ARRANGEMENTS` declares each stored runtime arrangement the render suite must visit,
   and supplies one for each persisted tray. Add a new remembered surface here when the
   surface is introduced. */

let publishedArrangements = [];
export { publishedArrangements as ARRANGEMENTS };

export function createArrangements({
  CHARACTER_SHORTCUTS_KEY,
  DESIGN_KEY,
  PANEL_KEY,
  TRAY_KEY,
  commentsEdge,
  readerStore,
  tabStore,
  trayNames,
  traysEdge,
}) {
  publishedArrangements = [
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
}
