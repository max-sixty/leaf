/* One-shot request lifecycle, combining pending gestures with the server's reading.
   The application supplies the pending ledger and send door; every lifecycle consumer
   sees the same immediate pending result, acceptance, or authoritative refusal. */
import { watchProjection } from "./projection-watch.js";
import { registry } from "./registry.js";
import { inChrome } from "./passages.js";
import { runtime } from "./context.js";
import { quoted } from "./widget-elements.js";

const requestMatches = (owner, action) => {
  const request = registry[owner.localName]?.["x-request"];
  if (!request?.verbs?.[action]) return false;
  return [...owner.children].some((child) => {
    const attribute = request.offers?.[child.localName];
    return attribute && child.getAttribute(attribute) === action;
  });
};

const documentFor = (owner) =>
  inChrome(owner)
    ? { kind: "thread" }
    : { kind: "page", revision: runtime.currentRevision };

export function createRequests({ post, pendingRequests }) {
  const projectedLifecycle = (owner) => {
    const document = documentFor(owner);
    const pending = pendingRequests().find(
      (event) =>
        event.widget === owner.id &&
        (document.kind === "thread" || event.revision === document.revision),
    );
    if (pending)
      return {
        seat: { document, widget: owner.id },
        attempts: [{ request: pending, receipt: null }],
        latest: { request: pending, receipt: null },
        phase: "pending",
      };
    const lifecycles =
      document.kind === "thread"
        ? runtime.browser?.conversation?.requests
        : runtime.view?.document?.requests;
    return (
      lifecycles?.find((item) => item.seat.widget === owner.id) ?? {
        seat: { document, widget: owner.id },
        attempts: [],
        latest: null,
        phase: "ready",
      }
    );
  };

  const requestAvailable = (owner, action) =>
    runtime.statePhase !== "waiting" &&
    !quoted(owner) &&
    requestMatches(owner, action) &&
    projectedLifecycle(owner).phase === "ready";

  async function sendRequest(owner, action, detail, { attempt } = {}) {
    if (quoted(owner)) {
      console.error(
        `leaf: <${owner.localName}> is exhibited (x-exhibit); request ${action} refused`,
      );
      return null;
    }
    if (!requestAvailable(owner, action)) return null;
    return post({
      kind: "request",
      revision: runtime.currentRevision,
      widget: owner.id,
      action,
      detail,
      ...(attempt && { attempt }),
    });
  }
  const watchRequestLifecycle = (owner, callback) => {
    if (typeof callback !== "function")
      throw new TypeError("A request watcher needs a callback");
    return watchProjection(owner, () =>
      callback(structuredClone(projectedLifecycle(owner))),
    );
  };
  return { requestAvailable, sendRequest, watchRequestLifecycle };
}
