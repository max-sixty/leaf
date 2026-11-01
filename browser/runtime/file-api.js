/* Explicitly bound files belong to the host filesystem, outside page event state.
   This transport keeps their addresses within the current page, including samples,
   and applies the same delivery-generation gate as Leaf's other HTTP consumers.
   A captured document or export never gains write access to a live file. The state
   answer stamps each binding (`file_bindings.binding_stamps`), so `watch` hears a
   file move on the page's own news rather than by reading it on a timer. */
import { offlineInteractive, pageUrl } from "./context.js";
import { LayerRefused, RequestError, requestJson } from "./layer-client.js";
import { applicationState, readPart } from "./semantic-state.js";

const live = readPart((root) => root.document.live);

/** @param {string} binding */
export function boundFile(binding) {
  const writable = () => !offlineInteractive && Boolean(live());
  /** @template T @param {RequestInit} [options] @returns {Promise<T>} */
  async function request(options = {}) {
    if (!writable()) throw new Error("File editing is available in live pages.");
    try {
      return await requestJson(
        pageUrl(`api/files/${encodeURIComponent(binding)}`),
        { cache: "no-store", ...options },
        "file",
      );
    } catch (error) {
      // Each failure reads as one sentence the editor can show and follow with its
      // own: the server's words where it gave any, and these where it gave none. A
      // request that got no answer rejects in the engine's words ("Failed to fetch",
      // "Load failed"), and a proxy's page names only a status.
      if (error instanceof LayerRefused)
        throw new Error("Leaf changed while accessing the file.", { cause: error });
      if (!(error instanceof RequestError))
        throw new Error("The page's server did not answer.", { cause: error });
      if (error.said === undefined)
        throw new Error(
          error.status < 400
            ? "The page's server answered in a form the page cannot read."
            : `The page's server answered HTTP ${error.status}.`,
          { cause: error },
        );
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
      /** @type {import("../types/contract.js").ServedFileSnapshot | null} */
      const file = await request();
      if (file === null) throw new Error(`No file is bound as '${binding}'.`);
      return file;
    },
    /** @param {Pick<import("../types/contract.js").ServedFileSnapshot, "revision" | "text">} snapshot
     * @returns {Promise<import("../types/contract.js").ServedFileSnapshot>} */
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
    /** @param {() => void} callback */
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
