/* Import-free vocabulary of runtime-painted attributes, and the readers of the
   readiness stamps. Readers of a paint name do not start presentation, import widgets
   or reach transport through its writers. */

// Attributes the runtime may paint onto elements the page owns: the source each runtime
// writer uses, and with the declared marks (`$marks`) the replay signature's exclusion
// vocabulary (`isPagePaint`), so a new kind of paint has one place to join. The rest of
// data-lf-* is not implicitly ours — a widget can carry real state there, and replay
// must see it.
// Attributes whose values belong entirely to runtime presentation. Source snapshots
// remove these, while retaining authored classes and delivery/module declarations.
export const RUNTIME_PAINT_ATTRIBUTE = Object.freeze({
  external: "data-lf-external",
  viewMember: "data-lf-view",
  obligation: "data-lf-obligation",
  done: "data-lf-done",
  restated: "data-lf-restated",
  retired: "data-lf-retired",
  settlement: "data-lf-state",
  applied: "data-lf-applied",
  reading: "data-lf-reading",
  dataVersion: "data-lf-data-version",
  source: "data-lf-source",
  sourceRevision: "data-lf-source-revision",
  userOverride: "data-lf-user-override",
  presented: "data-lf-presented",
  reported: "data-lf-reported",
  upgraded: "data-lf-upgraded",
  // A box the runtime opts into scroll reach (reach.js), as the page's `scroll` class
  // does for its own boxes.
  scrollSurface: "data-lf-scroll",
  scrolls: "data-lf-scrolls",
  moreBefore: "data-lf-more-before",
  moreAfter: "data-lf-more-after",
  scrollDirection: "data-lf-scroll-direction",
  moreBelow: "data-lf-more-below",
  goto: "data-lf-go-to-active",
  traffic: "data-lf-traffic",
  // A recording playing through the runtime's controls (video-controls.js).
  player: "data-lf-player",
});

export const PAGE_PAINT_ATTRIBUTE = Object.freeze({
  class: "class",
  viewMembers: "data-lf-view-members",
  ...RUNTIME_PAINT_ATTRIBUTE,
  // Delivery's, not a runtime writer's: the size of the page media an element names
  // (revision_delivery.py, `mark_declared`).
  mediaWidth: "data-lf-media-width",
  mediaHeight: "data-lf-media-height",
  // A module's, not a runtime writer's: the quiet word it declares on a part, which the
  // runtime writes there (declared-words.js, `watchQuietWords`). Paint even on an
  // authored element, a suggestion's slot, since the word follows the slot's state.
  quiet: "data-lf-quiet",
});

// The runtime's paint on elements the page owns changes how a box looks and moves none:
// the outline a mark draws (target-paint.js), an anchor name only the chrome positions by
// (css-anchors.js, `nameAnchor`). So it is written through `paint`, unheard by the
// observers that read where the page's boxes stand from its mutations (`readsLayout`):
// each is handed what it heard before the write, and what the write produced is dropped,
// as the margin's pass drops its own writes to its rows. An author's change, an anchor
// name included, is heard as any other.
/** @type {Map<MutationObserver, (records: MutationRecord[]) => void>} */
const layoutReaders = new Map();
let painting = 0;
/** @param {MutationObserver} observer @param {(records: MutationRecord[]) => void} read its callback */
export function readsLayout(observer, read) {
  layoutReaders.set(observer, read);
}
/** @template T @param {() => T} write @returns {T} */
export function paint(write) {
  if (!painting)
    for (const [observer, read] of layoutReaders) {
      const heard = observer.takeRecords();
      if (heard.length) read(heard);
    }
  painting += 1;
  try {
    return write();
  } finally {
    painting -= 1;
    if (!painting) for (const observer of layoutReaders.keys()) observer.takeRecords();
  }
}

// Whether the page has presented: the stamp presentation.js writes once on `body` and
// never takes back.
export const pagePresented = () =>
  document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented);

// Whether widgets and anchor preparation have finished, independently of state.
export const pageUpgraded = () =>
  document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.upgraded);

// Whether the decision `element`, which wears the location mark (`obligation`), has a
// control inside that carries the location itself, which it says on the decision with
// `--lf-obligation-ring: none`. The location ring (target-paint.js) and a landing that
// reveals it (landing-scroll.js) read it here.
/** @param {Element} element */
export const locationStandsDown = (element) =>
  getComputedStyle(element).getPropertyValue("--lf-obligation-ring").trim() === "none";
