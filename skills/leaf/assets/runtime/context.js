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
  reading: null,
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
// did not ask to go. Focus the framed chrome places later is the gallery's to take back
// rather than this document's to refuse — a shown dialog runs the browser's own
// focusing steps whatever the page around it wants, and only that page knows where the
// reader was standing.
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
