/* A page names an explicit host grant; credentials and HTTP policy stay there.
   Fetching neither changes page state nor retries a failed request. */
import { offlineInteractive, pageUrl } from "./context.js";
import { requestJson } from "./layer-client.js";
import { readPart } from "./semantic-state.js";

const live = readPart((root) => root.document.live);

export function connection(name) {
  return {
    async fetch(path) {
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
