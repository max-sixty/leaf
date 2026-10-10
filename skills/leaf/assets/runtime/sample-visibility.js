/* Whether an isolated sample can be seen and admits reading.
 * The containing page supplies admission (tab visibility, inertness and modal reach),
 * never cached geometry. An implicit-root native observer answers whether this
 * document intersects all containing viewports, including cross-origin ones. Exact
 * message exposure asks each containing geometry owner for a fresh band. */
const child = document.documentElement.lfSample;
let visibility = child ? { visible: false } : null;
let admitted = false;
let intersecting = false;
const observers = new Set();
const readings = new Map();
let readingId = 0;

export const sampleVisibility = () => visibility;
export function onSampleVisibility(callback) {
  observers.add(callback);
  return () => observers.delete(callback);
}
// Exposure asks the containing geometry owner for its current visible band. A port
// notification only invalidates that reading; it cannot supply a rectangle a later
// scan is entitled to reuse. A nested sample's containing owner obtains this same
// reading from its own owner before answering.
export function readSampleVisibility() {
  if (!child) return Promise.resolve(null);
  return new Promise((resolve, reject) => {
    const id = ++readingId;
    readings.set(id, { resolve, reject });
    child.send({ type: "visibility-read", detail: { id } });
  });
}
function publish() {
  visibility = { visible: admitted && intersecting };
  for (const callback of observers) callback(visibility);
}
if (child) {
  child.receive(({ type, detail }) => {
    if (type === "visibility-reading") {
      const reading = readings.get(detail.id);
      readings.delete(detail.id);
      if (detail.error)
        reading?.reject(
          Object.assign(new Error(detail.error.message), { name: detail.error.name }),
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
  const seen = new IntersectionObserver(
    ([entry]) => {
      const { width, height } = entry.intersectionRect;
      intersecting = width > 0 && height > 0;
      publish();
    },
    // Edge adjacency is already "intersecting" at zero area. A positive threshold
    // makes the first painted pixel a delivery rather than leaving visibility stale.
    { threshold: [0, Number.EPSILON] },
  );
  seen.observe(document.documentElement);
  addEventListener("pagehide", () => seen.disconnect(), { once: true });
}
