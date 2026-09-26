/* Shared mechanical runtime context and read-only views of the semantic root.
   Accepted facts are never installed here independently of application publication. */
import { readApplication } from "./semantic-state.js";
import { PAGE_ROOT } from "./storage.js";

// Code may be shared by several documents, including a specimen and its parent.
// Page operations belong to the document's declared root, never to the module's asset
// URL.
export const pageUrl = (path) => new URL(path, PAGE_ROOT).href;

const offlineMarker = document.querySelector(
  'script[type="application/json"][data-lf-runtime][data-lf-offline]',
);
const offlinePayload = offlineMarker
  ? JSON.parse(offlineMarker.textContent || "null")
  : null;
if (
  offlineMarker &&
  (!offlinePayload ||
    typeof offlinePayload !== "object" ||
    !offlinePayload.state ||
    !offlinePayload.data ||
    !offlinePayload.resources)
)
  throw new TypeError("Leaf's interactive export payload is incomplete");

export const offlineInteractive = offlinePayload !== null;
export const offlineState = () =>
  offlineInteractive ? structuredClone(offlinePayload.state) : null;
// The fragment reader never mutates this captured authority. Keep one in-memory copy:
// cloning a multi-megabyte split source for each opened file would defeat fragmentation.
export const offlineData = () => (offlineInteractive ? offlinePayload.data : null);
export const runtimeModule = (path) =>
  offlineInteractive ? `leaf:${path.startsWith("/") ? path : `/${path}`}` : path;
export const runtimeResource = (path) => {
  if (!offlineInteractive) return path;
  const resource = offlinePayload.resources[path];
  if (typeof resource !== "string")
    throw new Error(`Leaf's interactive export is missing ${path}`);
  return resource;
};

export const runtime = {
  get active() {
    return readApplication().authoritative?.active ?? null;
  },
  get activity() {
    return readApplication().effective.activity;
  },
  get agent() {
    // The claimant's own name where a claim answers for the page. Nothing has
    // claimed an exported or never-served page, and "Agent" is what the
    // thread already calls a message whose author left no name
    // (`UNCLAIMED_AGENT`, `thread/messages.js`).
    return readApplication().authoritative?.agent || "Agent";
  },
  get browser() {
    return readApplication().authoritative?.browser ?? null;
  },
  get currentLabel() {
    return readApplication().document.live &&
      runtime.currentRevision === runtime.active?.revision
      ? runtime.active.label
      : runtime.currentStamp === null
        ? null
        : `v${runtime.currentStamp}`;
  },
  get currentRevision() {
    return readApplication().document.revision;
  },
  get currentStamp() {
    return readApplication().document.live &&
      runtime.currentRevision === runtime.active?.revision
      ? runtime.active.version
      : (readApplication().document.stamp ?? null);
  },
  get data() {
    return readApplication().data;
  },
  get events() {
    return readApplication().authoritative?.events ?? [];
  },
  get lastEventSeq() {
    return readApplication().authoritative?.browser.basis.through_seq ?? -1;
  },
  // A chrome placement is moving a box the user may be standing in, so the focus it
  // takes off and hands straight back is the layer's own, not the user going
  // anywhere. Standing here rather than beside the one placer, because what has to know
  // is every reader of where the user stands.
  placingChrome: false,
  get reading() {
    return readApplication().authoritative?.reading ?? null;
  },
  sessionReference: null,
  get state() {
    return readApplication().authoritative;
  },
  restoringState: false,
  registry: {},
  get statePhase() {
    return readApplication().phase;
  },
  undoing: false,
  get versions() {
    return readApplication().authoritative?.versions ?? [];
  },
  get workflows() {
    return readApplication().effective.workflows;
  },
  get view() {
    return runtime.browser?.views[String(runtime.currentRevision)] ?? null;
  },
};

// A specimen arrives without the surrounding user's arrangements. Passive gallery
// replays stay inert and take one state reading; operable specimens run the ordinary
// live feed.
export const passiveSpecimen = document.body.hasAttribute("data-lf-specimen-passive");

export const agentName = () => runtime.agent;

export const revisionLabel = (revision) => {
  const stamped = runtime.versions.find((candidate) => candidate.revision === revision);
  if (stamped) return `v${stamped.version}`;
  let previous = null;
  for (const candidate of runtime.versions) {
    if (
      candidate.revision < revision &&
      (previous === null || candidate.revision > previous.revision)
    )
      previous = candidate;
  }
  return previous ? `Draft after v${previous.version}` : "Draft";
};
