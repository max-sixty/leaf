/* Whether this document can be seen, and how a page reads a frame it holds.

   A frame cannot tell from inside whether it shows, so the page that holds the frame
   element reads it (`watchFrame`). The frame shows when it is drawn and visible
   (`checkVisibility`), does not skip its own contents, and intersects every containing
   viewport. `content-visibility: hidden` on the iframe itself skips its document,
   which Chrome then stops rendering, yet `checkVisibility` counts only an ancestor's.
   An implicit-root IntersectionObserver of the frame element answers the last part,
   clipping through every containing scroller and viewport, cross-origin ones
   included, whatever the frame's document does with its own styles.

   Reading from inside fails in both browsers: an observer of a box fixed over the
   frame's own viewport reads that box scrolling away once the document's styles
   transform `html` (the root becomes the box's containing block, and a live page's
   root is one viewport tall), and Firefox reports such a box on screen in an owner
   under `content-visibility: hidden`.

   Who reads depends on the boundary between the two documents:

   - A sample's host reads its frame and adds admission: tab visibility, inertness,
     modal reach and `aria-hidden` (sample.js, `admitted`). It posts the answer across
     the sample's port, and the child publishes it here. Exact message exposure asks
     each containing geometry owner for a fresh band (`readSampleVisibility`).
   - Any other framed Leaf document has a same-origin parent, since a live page
     admits only those (`structure.FRAME_ANCESTORS_CSP`), so it watches its own
     `frameElement` and every frame element above it that it can reach, and shows
     when all of them do. Firefox reports a frame inside an outer iframe under
     `content-visibility: hidden` as intersecting, and tells the inner frame nothing
     when that changes.
   - A top-level document has no frame to read, and `frameVisibility` is null.

   The tab's own visibility is the reader's to add (`document.hidden`).

   The shift watch (tests/shift_watch.js) keeps an observer of a box fixed over each
   frame's viewport instead: it runs in every frame, Leaf's or not, before the runtime
   it judges, and has no host to ask. */
const child = document.documentElement.lfSample;
let admitted = false;
const observers = new Set();
const readings = new Map();
let readingId = 0;

/** What `frame`'s holding page shows of it: `shown()` says whether any of the frame is
 * drawn on screen. `callback` runs when the frame crosses into or out of the
 * containing viewports, and when an attribute that can hide or exclude it changes on
 * the frame or an element holding it, which no observer of geometry hears. `stop`
 * disconnects. */
export function watchFrame(frame, callback) {
  let intersecting = false;
  const seen = new IntersectionObserver(
    (entries) => {
      const { width, height } = entries.at(-1).intersectionRect;
      intersecting = width > 0 && height > 0;
      callback();
    },
    // Edge adjacency is already "intersecting" at zero area, so a positive threshold
    // makes the first painted pixel a delivery. A whole frame coming into view is one
    // too, which brings a sample's exposure reading round.
    { threshold: [0, Number.EPSILON, 1] },
  );
  seen.observe(frame);
  const styled = new MutationObserver((records) => {
    if (records.some(({ target }) => target === frame || target.contains(frame)))
      callback();
  });
  styled.observe(frame.ownerDocument, {
    subtree: true,
    attributes: true,
    attributeFilter: ["inert", "open", "hidden", "aria-hidden", "class", "style"],
  });
  return {
    shown: () =>
      intersecting &&
      frame.checkVisibility({ visibilityProperty: true }) &&
      getComputedStyle(frame).contentVisibility !== "hidden",
    stop: () => {
      seen.disconnect();
      styled.disconnect();
    },
  };
}

// A cross-origin ancestor's frame element reads null and ends the walk.
const owners = [];
if (!child)
  for (let view = /** @type {Window} */ (window); view.frameElement; view = view.parent)
    owners.push(watchFrame(view.frameElement, publish));

/** Null in a top-level document; otherwise whether its frame shows. */
export function frameVisibility() {
  if (child) return { visible: admitted };
  if (owners.length) return { visible: owners.every((owner) => owner.shown()) };
  return null;
}
export function onFrameVisibility(callback) {
  observers.add(callback);
  return () => observers.delete(callback);
}
// Exposure asks the containing geometry owner for its current visible band. A port
// notification only invalidates that reading; it cannot supply a rectangle a later
// scan is entitled to reuse. A nested sample's containing owner obtains this same
// reading from its own owner before answering. Null outside a sample.
export function readSampleVisibility() {
  if (!child) return null;
  return new Promise((resolve, reject) => {
    const id = ++readingId;
    readings.set(id, { resolve, reject });
    child.send({ type: "visibility-read", detail: { id } });
  });
}
function publish() {
  const visibility = frameVisibility();
  for (const callback of observers) callback(visibility);
}
if (child) {
  child.receive(({ type, detail }) => {
    if (type === "visibility-reading") {
      const reading = readings.get(detail.id);
      readings.delete(detail.id);
      if (detail.error)
        reading?.reject(
          Object.assign(
            new Error(detail.error.message),
            { stack: undefined },
            detail.error,
          ),
        );
      else reading?.resolve(detail);
      return;
    }
    if (type !== "visibility") return;
    admitted = detail.visible;
    // An unchanged admission also carries a containing layout or scroll change.
    // Exposure asks its containing geometry owner rather than reuse an old rect.
    publish();
  });
}
// A persisted pagehide is the containing page's, and its page cache brings this
// document back still standing where it stood (bootstrap.js).
addEventListener("pagehide", (event) => {
  if (!event.persisted) for (const owner of owners) owner.stop();
});
