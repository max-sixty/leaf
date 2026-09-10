/* Capture and restore the reader’s auxiliary workspace and its stable control route. */
import { currentTray, asksPanel, othersPanel } from "./trays.js";
import { focused } from "./keyboard/scopes.js";
import { panel } from "./conversation/panel-elements.js";

// Returning to a workspace can reopen an inline thread. Those effects are supplied
// by application composition; capturing a place only reads the current DOM and state.
export function createWorkspaceNavigation({
  panelIsOpen,
  setPanel,
  showTray,
  openInlineThread,
}) {
  function workspaceControlRoute(control) {
    if (!control || control === document.body) return () => null;
    const inline = control.closest?.(
      ".lf-margin-preview .lf-conversation-thread[data-thread]",
    );
    if (inline) {
      const id = inline.dataset.thread;
      return () => openInlineThread(id);
    }
    const ask = control?.closest?.(".lf-asks-row[data-lf-at]");
    if (ask) {
      const target = ask.dataset.lfAt;
      return () =>
        [...asksPanel.querySelectorAll(".lf-asks-row[data-lf-at]")].find(
          (row) => row.dataset.lfAt === target,
        ) ?? null;
    }
    const thread = control?.closest?.(".lf-thread[data-id]");
    if (thread) {
      const id = thread.dataset.id;
      return () =>
        [...panel.querySelectorAll(".lf-thread[data-id]:not([hidden])")].find(
          (row) => row.dataset.id === id,
        ) ?? null;
    }
    const leaf = control?.closest?.(".lf-others-panel a[href]");
    if (leaf) {
      const href = leaf.href;
      return () =>
        [...othersPanel.querySelectorAll("a[href]")].find(
          (link) => link.href === href,
        ) ?? null;
    }
    return () => (control?.isConnected ? control : null);
  }

  function workspaceState() {
    return {
      panel: panelIsOpen(),
      tray: currentTray(),
      // A widget-local Thread lives inside a shadow root, so the document reading is only
      // its host. Capture the actual control to reopen that exact inline conversation when
      // an auxiliary workspace closes.
      control: workspaceControlRoute(focused()),
    };
  }

  function restoreWorkspace(state) {
    const { panel: hadPanel, tray } = state;
    if (tray) showTray(tray);
    else if (hadPanel) {
      showTray(null, { returnFocus: false });
      setPanel(true);
    } else {
      showTray(null, { returnFocus: false });
      setPanel(false);
    }
    return state.control();
  }

  return { workspaceState, restoreWorkspace };
}
