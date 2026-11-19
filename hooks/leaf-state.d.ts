// The values Leaf's hooks module (hooks/claude-code.ts) keeps in the session through
// `$.state`, which survive a reload of the module's code: the contract plugin.json's
// `types` names, which merges into Claude Code's module declaration.
declare module "claude-code" {
  interface PluginState {
    leaf: {
      // The forks the module spawned or resumed to do a thread's work, by agent id,
      // with when each one's present run started, in milliseconds since the epoch,
      // the instruction it ran, which its run's end reports under
      // (`src/leaf/carrier.py`), and, once the run ended and until Leaf has heard,
      // how it ended (`endFork`).
      forks: Record<
        string,
        {
          started: number;
          id: string;
          do: string;
          basis: unknown;
          ended?: { answer: string } | { failed: string };
        }
      >;
    };
  }
}
