// The values Leaf's hooks module (hooks/claude-code.ts) keeps in the session through
// `$.state`, which survive a reload of the module's code: the contract plugin.json's
// `types` names, which merges into Claude Code's module declaration.
declare module "claude-code" {
  interface PluginState {
    leaf: {
      // The forks the module spawned or resumed to do a thread's work, by agent id,
      // with when each one's present run started, in milliseconds since the epoch,
      // and the turn Leaf opened for that run (`forks._take`).
      forks: Record<string, { started: number; turn: string }>;
    };
  }
}
