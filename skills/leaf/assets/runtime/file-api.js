/* Explicitly bound files belong to the host filesystem, outside page event state.
   This transport keeps their addresses within the current page, including samples,
   and applies the same delivery-generation gate as Leaf's other HTTP consumers.
   A captured document or export never gains write access to a live file. */
import { offlineInteractive, pageUrl } from "./context.js";
import { admitResponse, layerHeaders } from "./layer-client.js";
import { readApplication } from "./semantic-state.js";

export function boundFile(binding) {
  const writable = () => !offlineInteractive && readApplication().document.live;
  async function request(options = {}) {
    if (!writable()) throw new Error("File editing is available in live pages.");
    const response = await fetch(pageUrl(`api/files/${encodeURIComponent(binding)}`), {
      cache: "no-store",
      ...options,
      headers: layerHeaders(options.headers),
    });
    if (!admitResponse(response))
      throw new Error("Leaf changed while accessing the file. Your draft is kept.");
    const answer = await response.json();
    if (!response.ok) {
      const error = new Error(answer.error);
      error.current = answer.current;
      throw error;
    }
    return answer;
  }
  return {
    get writable() {
      return writable();
    },
    read: () => request(),
    save: (snapshot) =>
      request({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(snapshot),
      }),
  };
}
