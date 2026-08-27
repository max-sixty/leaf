/* The mutable facts shared across the public runtime's internal domains.

   Collections keep stable identities so a projection can hold them while a state
   application replaces their contents. Scalar transitions go through this record
   directly. */
export const runtime = {
  active: null,
  agent: "Claude",
  currentLabel: null,
  currentRevision: null,
  currentStamp: null,
  data: { revision: -1, sources: {} },
  events: [],
  lastEventSeq: -1,
  reading: null,
  state: null,
  projectingState: false,
  registry: {},
  statePhase: "waiting",
  undoing: false,
  versions: [],
};

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
