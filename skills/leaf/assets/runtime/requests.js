/* Durable one-shot requests projected by the server for their owning document. */
let publishedRequests;

export const requestAvailable = (...args) =>
  publishedRequests.requestAvailable(...args);
export const sendRequest = (...args) => publishedRequests.sendRequest(...args);
export const watchRequestLifecycle = (...args) =>
  publishedRequests.watchRequestLifecycle(...args);

export function createRequests(runtime, dependencies) {
  const { inChrome, post, quoted, registry } = dependencies;

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

  const projectedLifecycle = (owner) => {
    const document = documentFor(owner);
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
    if (!requestMatches(owner, action)) return null;
    if (projectedLifecycle(owner).phase !== "ready") return null;
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
    const update = () => {
      if (!owner.isConnected) {
        document.removeEventListener("lf-actions", update);
        return;
      }
      callback(structuredClone(projectedLifecycle(owner)));
    };
    document.addEventListener("lf-actions", update);
    update();
    return () => document.removeEventListener("lf-actions", update);
  };

  publishedRequests = {
    requestAvailable,
    sendRequest,
    watchRequestLifecycle,
  };
  return publishedRequests;
}
