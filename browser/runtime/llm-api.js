/* One generation against the host's model, independent of page state and data.
   The server owns credentials and request validation. A failed request is never
   retried here: it may already have incurred a charge. */
import { offlineInteractive, pageUrl } from "./context.js";
import { requestJson } from "./layer-client.js";
import { readPart } from "./semantic-state.js";

const live = readPart((root) => root.document.live);

export async function generate(request) {
  if (offlineInteractive || !live())
    throw new Error("LLM generation is available in live pages.");
  return requestJson(
    pageUrl("api/llm"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
    "LLM generation",
  );
}
