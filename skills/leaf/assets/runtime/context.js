/* Shared mechanical runtime context and read-only views of the semantic root.
   Accepted facts are never installed here independently of application publication. */
import { readApplication } from "./semantic-state.js";

export const runtime = {
  get active() {
    return readApplication().authoritative?.active ?? null;
  },
  get activity() {
    return readApplication().effective.activity;
  },
  get agent() {
    return readApplication().authoritative?.agent || "Claude";
  },
  get browser() {
    return readApplication().authoritative?.browser ?? null;
  },
  currentLabel: null,
  get currentRevision() {
    return readApplication().document.revision;
  },
  currentStamp: null,
  get data() {
    return readApplication().data;
  },
  get events() {
    return readApplication().authoritative?.events ?? [];
  },
  get lastEventSeq() {
    return readApplication().authoritative?.browser.basis.through_seq ?? -1;
  },
  // A chrome placement is moving a box the reader may be standing in, so the focus it
  // takes off and hands straight back is the layer's own, not the reader going
  // anywhere. Standing here rather than beside the one placer, because what has to know
  // is every reader of where the reader stands.
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
  versions: [],
  get view() {
    return runtime.browser?.views[String(runtime.currentRevision)] ?? null;
  },
};

// A contained page is a Leaf document rendered as a picture inside another one. The
// interaction gallery frames the chrome that is singleton by design, so a replay can
// drive the production controls without moving the gallery around it;
// `loadFrameDocument` stamps the document it writes. The reader is standing in that
// outer document, so a contained page arrives without restoring their arrangements and
// without placing focus: either would take the page they are actually on somewhere they
// did not ask to go. Focus its chrome would place later is refused by the frame's body
// rather than by this flag — `loadFrameDocument` writes that body `inert`, so a shown
// dialog's focusing steps return against an inert subject and the reader never leaves
// the page around the picture. It takes one initial state reading so its production
// chrome has real data, then leaves the continuing state/news feed to the outer page.
export const containedPage = document.body.hasAttribute("data-lf-contained");

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
