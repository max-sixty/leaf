/* Explicitly bound files belong to the host filesystem, outside page event state.
   The page's state answer carries each bound file as the server last read it
   (`file_bindings.bound_files`), so an editor shows its file with the page and hears
   a write elsewhere on the page's own news. A save goes to the file's own address
   within the current page, including samples, and applies the same delivery-generation
   gate as Leaf's other HTTP consumers. A captured document or export never gains write
   access to a live file. */
import { offlineInteractive, pageUrl } from "./context.js";
import { LayerRefused, RequestError, requestJson } from "./layer-client.js";
import { applicationState, readPart } from "./semantic-state.js";

const live = readPart((root) => root.document.live);

/** @param {string} binding */
export function boundFile(binding) {
  const writable = () => !offlineInteractive && Boolean(live());
  // Undefined before the page has a state, and null where its state binds no such file.
  const selected = applicationState.select((root) =>
    root.authoritative ? (root.authoritative.files[binding] ?? null) : undefined,
  );
  const label = readPart((root) => root.authoritative?.files[binding]?.label ?? null);
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
    // The file as the page's state carries it, or null before the page has a state.
    // Throws, in words the editor can show, where it has no file to give: an export, a
    // binding the page lacks, or a file the server can't read.
    /** @returns {import("../types/contract.js").ServedFileSnapshot | null} */
    read() {
      if (!writable()) throw new Error("File editing is available in live pages.");
      const file = selected.read();
      if (file === undefined) return null;
      if (file === null) throw new Error(`No file is bound as '${binding}'.`);
      const { text, revision, error, taken } = file;
      if (text === undefined || revision === undefined) throw new Error(error);
      return { label: file.label, text, revision, taken };
    },
    /** @param {Pick<import("../types/contract.js").ServedFileSnapshot, "revision" | "text">} snapshot
     * @returns {Promise<import("../types/contract.js").ServedFileSnapshot>} */
    async save(snapshot) {
      if (!writable()) throw new Error("File editing is available in live pages.");
      try {
        return await requestJson(
          pageUrl(`api/files/${encodeURIComponent(binding)}`),
          {
            cache: "no-store",
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(snapshot),
          },
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
    },
    // Calls back each time an adopted state answer carries this binding otherwise,
    // the tab's first answer included, whether or not it binds the file, until the
    // returned function stops it.
    /** @param {() => void} callback */
    watch(callback) {
      let subscribing = true;
      const stop = selected.subscribe(() => {
        if (!subscribing) callback();
      });
      subscribing = false;
      return stop;
    },
  };
}
