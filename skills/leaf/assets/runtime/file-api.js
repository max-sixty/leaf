/* Explicitly bound files belong to the host filesystem, outside page event state.
   This transport keeps their addresses within the current page, including samples,
   and applies the same delivery-generation gate as Leaf's other HTTP consumers.
   A captured document or export never gains write access to a live file. The state
   answer stamps each binding (`file_bindings.binding_stamps`), so `watch` hears a
   file move on the page's own news rather than by reading it on a timer. */
import { offlineInteractive, pageUrl } from "./context.js";
import { LayerRefused, requestJson } from "./layer-client.js";
import { applicationState, readApplication } from "./semantic-state.js";

export function boundFile(binding) {
  const writable = () => !offlineInteractive && readApplication().document.live;
  async function request(options = {}) {
    if (!writable()) throw new Error("File editing is available in live pages.");
    try {
      return await requestJson(
        pageUrl(`api/files/${encodeURIComponent(binding)}`),
        { cache: "no-store", ...options },
        "file",
      );
    } catch (error) {
      if (error instanceof LayerRefused)
        throw new Error("Leaf changed while accessing the file. Your draft is kept.");
      throw error;
    }
  }
  return {
    get writable() {
      return writable();
    },
    // The server answers a binding the page lacks as no file, keeping the console
    // clean for a designed state; the editor still shows it as unavailable.
    read: async () => {
      const file = await request();
      if (file === null) throw new Error(`No file is bound as '${binding}'.`);
      return file;
    },
    save: (snapshot) =>
      request({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(snapshot),
      }),
    // Calls back each time an adopted state answer carries a different stamp for this
    // binding, the tab's first answer included, until the returned function stops it.
    // A stamp says only that the file may have moved; `read()`'s revision says whether
    // it did.
    watch(callback) {
      let subscribing = true;
      const stop = applicationState
        .select((root) => root.authoritative?.files[binding])
        .subscribe(() => {
          if (!subscribing) callback();
        });
      subscribing = false;
      return stop;
    },
  };
}
