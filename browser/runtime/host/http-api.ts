/* A page names an explicit host grant; credentials and HTTP policy stay there.
   Fetching neither changes page state nor retries a failed request. */
import { offlineInteractive, pageUrl } from "../state/context.js";
import { requestJson } from "../transport/layer-client.js";
import { readPart } from "../state/semantic-state.js";

const live = readPart((root) => root.document.live);

export function connection(name: string) {
  return {
    async fetch(path: string) {
      if (offlineInteractive || !live())
        throw new Error("HTTP connections are available in live pages.");
      return requestJson(
        pageUrl(`api/connections/${encodeURIComponent(name)}`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path }),
        },
        "HTTP connection",
      );
    },
  };
}
