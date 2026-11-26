/* Explicitly bound files belong to the host filesystem, outside page event state.
   This transport keeps their addresses within the current page, including samples,
   and applies the same delivery-generation gate as Leaf's other HTTP consumers.
   A captured document or export never gains write access to a live file. The state
   answer names each binding (`file_bindings.bound_files`), so `label` names a file
   before it is read, and holds the file as the source under the binding's id
   (`data.file_sources`), whose run moves with each write, so `watch` hears a file move
   on the page's own news rather than by reading it on a timer. */
import { offlineInteractive, pageUrl } from "../state/context.js";
import { LayerRefused, RequestError, requestJson } from "../transport/layer-client.js";
import { applicationState, readPart } from "../state/semantic-state.js";

const live = readPart((root) => root.document.live);

/** @param {string} binding */
export function boundFile(binding) {
  const writable = () => !offlineInteractive && Boolean(live());
  const label = readPart((root) => root.authoritative?.files[binding]?.label ?? null);
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
    // The name the page shows for the file, a path below the folder holding every
    // file the page binds, or null before the server has named it or where the page
    // binds none.
    get label() {
      return label();
    },
    // The server answers a binding the page lacks as no file, keeping the console
    // clean for a designed state; the editor still shows it as unavailable.
    read: async () => {
      /** @type {import("../../types/contract.js").ServedFileSnapshot | null} */
      const file = await request();
      if (file === null) throw new Error(`No file is bound as '${binding}'.`);
      return file;
    },
    // Resolves the saved file, or a refusal in the server's own words, which wrote
    // nothing, with the newer file where the file had moved on from `revision`. It
    // rejects where the page can't write, and where no such answer came, when the save
    // may have reached the file.
    /** @param {Pick<import("../../types/contract.js").ServedFileSnapshot, "revision" | "text">} snapshot
     * @returns {Promise<import("../../types/contract.js").ServedFileSnapshot | {refused: string, current: import("../../types/contract.js").ServedFileSnapshot | null}>} */
    save: async (snapshot) => {
      try {
        return await request({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(snapshot),
        });
      } catch (error) {
        // `request` passes on a `RequestError` only where the server said why.
        if (!(error instanceof RequestError)) throw error;
        return { refused: error.message, current: error.current ?? null };
      }
    },
    // Calls back each time an adopted state answer carries a different label for this
    // binding, or a different run of its source, the tab's first answer included,
    // until the returned function stops it. A run says only that the file was
    // written; `read()`'s revision says whether its text moved.
    /** @param {() => void} callback */
    watch(callback) {
      let subscribing = true;
      const stop = applicationState
        .select((root) => {
          const name = root.authoritative?.files[binding]?.label ?? "";
          const file = Object.hasOwn(root.data.sources, binding)
            ? root.data.sources[binding]
            : null;
          return `${name}\n${file?.run ?? ""}`;
        })
        .subscribe(() => {
          if (!subscribing) callback();
        });
      subscribing = false;
      return stop;
    },
  };
}
