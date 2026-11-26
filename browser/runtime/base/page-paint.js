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
  restated: "data-lf-restated",
  retired: "data-lf-retired",
  settlement: "data-lf-state",
  applied: "data-lf-applied",
  reading: "data-lf-reading",
  dataVersion: "data-lf-data-version",
  source: "data-lf-source",
  sourceRevision: "data-lf-source-revision",
  // A data widget that has reported a draw (records/projection/data.js, `projectMarked`), so
  // its source stamps say which revision it shows (readings/anchor-resolution.js).
  drawReported: "data-lf-draw-reported",
  userOverride: "data-lf-user-override",
  presented: "data-lf-presented",
  reported: "data-lf-reported",
  upgraded: "data-lf-upgraded",
  // A box the runtime or a module opts into scroll reach (dom/reach.js), as the page's
  // `scroll` class does for its own boxes. A value names the box a reading region,
  // and the frame around one names the region it holds (readings/reading-regions.js).
  scrollSurface: "data-lf-scroll",
  scrollHost: "data-lf-scroll-host",
  scrolls: "data-lf-scrolls",
  moreBefore: "data-lf-more-before",
  moreAfter: "data-lf-more-after",
  scrollDirection: "data-lf-scroll-direction",
  moreAbove: "data-lf-more-above",
  moreBelow: "data-lf-more-below",
  goto: "data-lf-go-to-active",
  // On the root while the user is in an editor a floating surface holds
  // (annotations/annotation-overlay/floating.js).
  floatingEditor: "data-lf-floating-editor",
  traffic: "data-lf-traffic",
  // The marks the runtime draws round a box as its outline (readings/target-paint.js,
  // surfaces.css): the aim, the trace a margin entry draws on what it concerns, the proxy
  // ring and the location ring. Attributes rather than classes, so an observer of the
  // page's classes, such as the margin's (margin-layout.js), hears none of them.
  aimed: "data-lf-aimed",
  traced: "data-lf-traced",
  proxied: "data-lf-proxied",
  location: "data-lf-projected-location",
  // On a marked box whose marks reach over a list marker (dom/geometry.js, `markerReach`),
  // which surfaces.css reads to draw them.
  besideMarker: "data-lf-beside-marker",
  // The cursor's paint, on the element under the pointer, which the margin likewise does
  // not hear: the hand over a thread's mark (annotations/anchor-paint.js,
  // annotation-chrome.css), and the aim's hand where it has an item and the crosshair of
  // Draw mode and Capture area (panel/page-geometry.js).
  overMark: "data-lf-over-mark",
  overItem: "data-lf-over-item",
  crosshair: "data-lf-crosshair",
  // The anchor name a heading holds while its link shows (records/heading-links.js, marks.css),
  // which the margin likewise does not hear.
  headingLink: "data-lf-heading-link",
  // A typeset formula's `<code>`, `inline` or `display`, whose rules stop drawing
  // code's face round it and round a display formula's `<pre>` (readings/formulas.js).
  formula: "data-lf-formula",
  // An element holding words a passage highlight paints, which the highlights' rules
  // name (annotations/anchor-paint.js, `holdWords`; marks.css).
  markedWords: "data-lf-marked-words",
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
  // runtime writes there (records/declared-words.js, `watchQuietWords`). Paint even on an
  // authored element, a suggestion's slot, since the word follows the slot's state.
  quiet: "data-lf-quiet",
});

// Whether the page has presented: the stamp readings/presentation.js writes once on `body` and
// never takes back.
export const pagePresented = () =>
  document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented);

// Whether widgets and anchor preparation have finished, independently of state.
export const pageUpgraded = () =>
  document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.upgraded);
