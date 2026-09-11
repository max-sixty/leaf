/* The mutable facts shared across the public runtime's internal domains.

   Collections keep stable identities so a projection can hold them while a state
   application replaces their contents. Scalar transitions go through this record
   directly. */
export const runtime = {
  active: null,
  activity: null,
  agent: "Claude",
  browser: null,
  currentLabel: null,
  currentRevision: null,
  currentStamp: null,
  data: { revision: -1, sources: {} },
  events: [],
  lastEventSeq: -1,
  // A chrome placement is moving a box the reader may be standing in, so the focus it
  // takes off and hands straight back is the layer's own, not the reader going
  // anywhere. Standing here rather than beside the one placer, because what has to know
  // is every reader of where the reader stands.
  placingChrome: false,
  reading: null,
  sessionReference: null,
  state: null,
  restoringState: false,
  registry: {},
  statePhase: "waiting",
  undoing: false,
  versions: [],
  view: null,
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
