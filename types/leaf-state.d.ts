// The values Leaf's hooks module (hooks/claude-code.ts) keeps in the session through
// `$.state`, which survive a reload of the module's code.
import "claude-code";

declare module "claude-code" {
  interface PluginState {
    leaf: {
      // The forks the module spawned to do a thread's work, by agent id, with when
      // each started, in milliseconds since the epoch.
      forks: Record<string, number>;
    };
  }
}
