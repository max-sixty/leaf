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
// observers that read where the page's boxes stand from its mutations (`readsLayout`).
// Each is handed what it heard before the write, and after it every record but the
// write's own: a record whose attribute changed by the paint's token alone, in a token
// list such as `class`, or by its property alone, in `style`. Any other change is heard,
// an author's anchor name included, and so is a change the page's own code makes in
// reaction to the paint, such as a custom element that moves a button when its class
// changes. A record says what it changed only through its old value, so such an observer
// observes `attributeOldValue`.
/** @typedef {{attribute: "class" | "part", token: string} | {attribute: "style", property: string}} Paint */
/** @type {Map<MutationObserver, (records: MutationRecord[]) => void>} */
const layoutReaders = new Map();
/** @param {MutationObserver} observer @param {(records: MutationRecord[]) => void} read its callback */
export function readsLayout(observer, read) {
  layoutReaders.set(observer, read);
}
// The paints of the write running now, a nested one's included.
/** @type {Paint[]} */
let painting = [];
/** @template T @param {Paint} change @param {() => T} write @returns {T} */
export function paint(change, write) {
  const outermost = !painting.length;
  if (outermost)
    for (const [observer, read] of layoutReaders) {
      const heard = observer.takeRecords();
      if (heard.length) read(heard);
    }
  painting.push(change);
  try {
    return write();
  } finally {
    if (outermost) {
      const paints = painting;
      painting = [];
      for (const [observer, read] of layoutReaders) {
        const heard = notPainted(observer.takeRecords(), paints);
        if (heard.length) read(heard);
      }
    }
  }
}
// The records a write produced that are not its paints' own. A record holds the value an
// attribute had before it; the value after it is the next record's for that attribute, or
// the attribute's value now.
/** @param {MutationRecord[]} records @param {Paint[]} paints */
function notPainted(records, paints) {
  /** @type {Map<Node, Map<string, string | null>>} */
  const later = new Map();
  /** @type {Set<MutationRecord>} */
  const own = new Set();
  for (const record of [...records].reverse()) {
    const { target, attributeName: name } = record;
    if (record.type !== "attributes" || !name || !(target instanceof Element)) continue;
    let values = later.get(target);
    if (!values) later.set(target, (values = new Map()));
    const after = values.has(name)
      ? (values.get(name) ?? null)
      : target.getAttribute(name);
    values.set(name, record.oldValue);
    if (paints.some((change) => changesOnly(change, name, record.oldValue, after)))
      own.add(record);
  }
  return records.filter((record) => !own.has(record));
}
/** @param {string | null} value */
const tokens = (value) => new Set((value ?? "").split(/\s+/).filter(Boolean));
/** @type {CSSStyleDeclaration | null} */
let scratch = null;
/** @param {string | null} value @param {string} property */
const without = (value, property) => {
  scratch ??= document.createElement("div").style;
  scratch.cssText = value ?? "";
  scratch.removeProperty(property);
  return scratch.cssText;
};
/** @param {Paint} change @param {string} name @param {string | null} before @param {string | null} after */
function changesOnly(change, name, before, after) {
  if (change.attribute !== name) return false;
  if (!("token" in change))
    return without(before, change.property) === without(after, change.property);
  const [was, now] = [tokens(before), tokens(after)];
  const changed = [...was, ...now].filter((token) => was.has(token) !== now.has(token));
  return changed.every((token) => token === change.token);
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
