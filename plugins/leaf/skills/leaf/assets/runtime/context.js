/* The mutable facts shared across the public runtime's internal domains.

   Collections keep stable identities so a projection can hold them while polling
   replaces their contents. Scalar transitions go through this record directly. */
export const runtime = {
  agent: "Claude",
  currentVersion: null,
  events: [],
  lastEventSeq: -1,
  latestVersion: null,
  projectingState: false,
  registry: {},
  statePhase: "waiting",
  undoing: false,
  versions: [],
};
