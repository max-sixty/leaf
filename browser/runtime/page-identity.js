/* The document's rendering identity, captured as structured data before any diagnostic
 * presentation. About and browser observations read this owner; retained checks keep
 * their own snapshot rather than borrowing a newer server or layer identity. */
import { DELIVERY, runtime } from "./context.js";

export function pageIdentity() {
  const state = runtime.state;
  const url = new URL(location.href);
  url.searchParams.delete("t");
  return structuredClone({
    url: String(url),
    delivery: DELIVERY,
    layer: state?.layer ?? null,
    preview: state?.preview ?? null,
    session_reference: runtime.sessionReference,
    browser: { user_agent: navigator.userAgent },
  });
}
