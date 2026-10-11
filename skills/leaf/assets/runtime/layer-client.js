/* The vendored-generation gate, the event and media doors, the page's JSON requests,
   and the page's error channel to the agent.

   A vendored runtime and registry are one generation. This module carries the
   epoch from `layer-generation.js` and the registry carries the same epoch
   after `page init`. `admitResponse` observes every response's session metadata and
   checks every successful payload against the document's layer and website release,
   including a freshness token whose body has not changed. A foreign answer is always refused;
   whether the page also reloads is the document source's to answer, through the same
   probe startup recovery uses, because only a source that has moved on has a different
   document to give and a page that reloads without one never stops. Active responses
   also establish the private server incarnation, so an ephemeral replacement reloads
   before its new event sequence meets the old DOM. Do not let one delivery interpret
   another's state. A refused key is read here too, for every response: it is the page
   cut off from its log rather than an answer about any request, so the event door
   throws it as it throws a lost connection and the banner names the link that ends it.

   `reportPageError` is the common runtime error surface. A widget failure may `failSoft`
   its own element so the rest of the page and Threads remain usable, but a presentation
   failure neither rolls back accepted semantic state nor proves pending receipts were
   shown. The window error listener, module load failures, a widget's `failSoft`, and the
   render gate all report through the same page-level evidence. Do not catch an error merely to stamp readiness
   or continue accounting for pending attempts.

   A fault that leaves part of the page not working as authored, such as the tab icon,
   an interaction demo that fails to load or run a command, or a code block that fails
   to highlight, reports here so the agent hears of it, not only the console. On
   leaf.page a passive session reads the published page, so the Worker answers that
   report at the edge and logs it for the site's maintainers instead
   (`worker/src/index.ts`, `pageFault`). A failed
   user-view observer stays silent: that context is optional and must not become agent
   work. Code running inside a sample's child page reports to the child's own
   disposable log, not the page that embeds it. */

import { describeFailure } from "../vendor/browser-runtime.js";
import { countTraffic } from "./traffic.js";
import { recordInteraction } from "./interaction-log.js";
import { offlineInteractive, pageUrl, runtime } from "./context.js";
import { notice } from "./notifications.js";
import { layerGeneration } from "./layer-generation.js";
import { DELIVERY } from "./storage.js";

const { layer: documentLayer, release, probe } = DELIVERY;

if (documentLayer && documentLayer !== layerGeneration) {
  window.dispatchEvent(
    new CustomEvent("lf-startup-failed", {
      detail: { reason: "document and runtime belong to different layers" },
    }),
  );
  throw new Error("Leaf's document and runtime belong to different layers");
}

// Which delivery this page belongs to is settled by whatever serves its documents, not
// by whoever answered last. An answer naming another generation may come from a party a
// reload will never reach — a website container still starting the release the edge has
// already moved past — and reloading at each such answer lands on the same document and
// is told again, so the user spends the rollout watching the page restart. The probe
// is the document source's own reading, as it is for startup recovery: the page's
// release-scoped assets are gone once the edge has moved on, and the registry still
// answers with this document's `Leaf-Layer` while it has not.
// True when the source has a different document, false when it does not, and undefined
// when the probe could not be read or names no layer, which settles nothing and leaves
// the question open for the next foreign answer.
async function sourceMovedOn() {
  if (!probe) return true;
  let response;
  try {
    response = await fetch(probe, { cache: "no-store" });
  } catch {
    return undefined;
  }
  if (response.status === 404) return Boolean(release);
  if (!response.ok) return undefined;
  const servedRelease = response.headers.get("Leaf-Release");
  if (release && servedRelease) return servedRelease !== release;
  const generation = response.headers.get("Leaf-Layer");
  return generation ? generation !== layerGeneration : undefined;
}

let layerReloading = false;
// A replaced private incarnation is not a question about generations: its record
// is gone, so the old DOM has to go whatever the document source says.
function reloadNow(message) {
  if (layerReloading) return;
  layerReloading = true;
  notice(message);
  location.reload();
}

// Each foreign answer gets its own reading of the source, because the source may move
// while the page waits — this very page can be re-vendored during the hold — and an
// answer carried over from an earlier reading would leave the tab with no way back. One
// probe is in the air at a time, so a burst of refusals costs one. The words are said
// once for the page rather than once an answer: a standing condition explained once is
// enough, and repeating a transient status line would hold the page's foot for as long
// as the disagreement lasts.
let asking = false;
let saidWaiting = false;
function reloadDelivery(message) {
  if (layerReloading || asking) return;
  asking = true;
  void (async () => {
    try {
      const moved = await sourceMovedOn();
      if (moved === undefined) return;
      if (!moved) {
        // The answers stay refused, which is the offline reading this page already knows
        // how to hold: authored content stays readable and the feed keeps asking, so the
        // page rejoins the log by itself once the server is back on this delivery.
        if (saidWaiting) return;
        saidWaiting = true;
        notice("Waiting for the server to finish updating.");
        return;
      }
      reloadNow(message);
    } finally {
      asking = false;
    }
  })();
}

export function layerHeaders(headers = {}) {
  return {
    "Leaf-Layer": layerGeneration,
    ...(runtime.currentRevision && {
      "Leaf-View-Revision": String(runtime.currentRevision),
    }),
    ...(release && { "Leaf-Release": release }),
    ...headers,
  };
}

// An answer `admitResponse` refused: it came from another delivery, and whether the page
// reloads is already settled there. Each caller says what that means for its request.
export class LayerRefused extends Error {}

// The page's JSON requests beside the event door and the state reads: the layer's
// headers out, the answer admitted, and the JSON read off the text so an error page a
// proxy wrote fails as its status rather than as a parse. A failure throws the server's
// `error`, or `<what>: HTTP <status>`, carrying the status, the raw body and, for a
// file the server holds newer than the draft, its `current`.
export async function requestJson(url, init, what) {
  const response = await fetch(url, { ...init, headers: layerHeaders(init.headers) });
  if (!admitResponse(response))
    throw new LayerRefused(`Leaf's layer changed while requesting ${what}`);
  const text = await response.text();
  const failed = (message, cause) =>
    Object.assign(new Error(message, { cause }), {
      status: response.status,
      body: text,
    });
  let answer = null;
  if (
    response.ok ||
    response.headers.get("Content-Type")?.split(";")[0].trim() === "application/json"
  )
    try {
      answer = JSON.parse(text);
    } catch (error) {
      throw failed(`${what}: HTTP ${response.status}`, error);
    }
  if (!response.ok)
    throw Object.assign(failed(answer?.error ?? `${what}: HTTP ${response.status}`), {
      current: answer?.current,
    });
  return answer;
}

export function sameLayer(generation) {
  if (generation === layerGeneration) return true;
  // Say what is about to happen before it happens. The user is looking at a page
  // that re-vendoring has moved out from under, and a tab that reloads itself with
  // nothing said is a page that appears to have lost their place for no reason.
  reloadDelivery("Leaf has been updated — reloading this page.");
  return false;
}

export function admitResponse(response) {
  observeSession(response);
  observeKey(response);
  // Failure responses still name session activation and its public reference. Their
  // status and error body belong to the caller, not to successful-payload admission.
  if (!response.ok) return true;
  if (layerReloading) return false;
  const generation = response.headers.get("Leaf-Layer");
  const responseRelease = response.headers.get("Leaf-Release");
  if (generation && !sameLayer(generation)) return false;
  if (release && responseRelease && responseRelease !== release) {
    reloadDelivery("Leaf has been updated — reloading this page.");
    return false;
  }
  return true;
}

let sessionMode = release ? "unknown" : "active";
// Only an active private-session response establishes an ephemeral incarnation.
// An ordinary server can restart while its durable page and log remain current.
let sessionServer = null;
const sessionChannel =
  release &&
  !document.documentElement.lfSample &&
  typeof window.BroadcastChannel !== "undefined"
    ? new window.BroadcastChannel("leaf-session")
    : null;

function activateSession(broadcast, server = null) {
  if (server && sessionServer && server !== sessionServer) {
    reloadNow("This Leaf session restarted — reloading the page.");
    return;
  }
  const learnedServer = server && !sessionServer;
  if (server) sessionServer = server;
  const activated = sessionMode !== "active";
  sessionMode = "active";
  if (activated) document.dispatchEvent(new Event("lf-session-active"));
  if (broadcast && (activated || learnedServer))
    sessionChannel?.postMessage({ active: true, server });
}

sessionChannel?.addEventListener("message", (event) => {
  if (event.data?.active === true) activateSession(false, event.data.server);
});

function observeSession(response) {
  const reference = response.headers.get("Leaf-Session-Reference");
  if (/^\d{12}$/.test(reference)) runtime.sessionReference = reference;
  const mode = response.headers.get("Leaf-Session");
  const server = response.headers.get("Leaf-Server");
  if (mode === "active") activateSession(true, server);
  else if (mode === "passive" && sessionMode !== "active") sessionMode = "passive";
}

export const sessionIsActive = () => sessionMode === "active";

// The server answers a request without this page's key with 401 and nothing else does,
// whichever route was asked (`http.py`, `_answer`). Any other answer passed the key
// gate, so each response settles the reading afresh: the tab regains the key the moment
// the printed link is opened in any tab of this browser, since that sets the cookie its
// next request carries.
const KEY_REFUSED = 401;
function observeKey(response) {
  runtime.keyRefused = response.status === KEY_REFUSED;
}

const { promise: layerReady, resolve: revealLayer } = Promise.withResolvers();
export { revealLayer };

// The page's one door to the log, spelled once. Two callers reach it — `post`, which
// orders the user's own gestures through it, and the error report below, which
// deliberately doesn't — and what they share is the request rather than anything about
// the sending: same path, same method, same encoding, so a door that moved would move
// for both. Whether a send waits on the one before it belongs to the caller.
export const postEvent = async (event) => {
  if (offlineInteractive)
    throw new Error("no agent or server is available in an interactive export");
  await layerReady;
  countTraffic("sends");
  recordInteraction("event_post", { kind: event.kind, attempt: event.attempt ?? null });
  let response;
  try {
    response = await fetch(pageUrl("api/event"), {
      method: "POST",
      headers: layerHeaders({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(event),
    });
    recordInteraction("event_response", {
      kind: event.kind,
      attempt: event.attempt ?? null,
      status: response.status,
    });
  } catch (error) {
    recordInteraction("event_response", {
      kind: event.kind,
      attempt: event.attempt ?? null,
      error: String(error),
    });
    throw error;
  } finally {
    countTraffic("acked");
  }
  if (!admitResponse(response)) return null;
  // A refused key is no answer to the event: the server read none of it, so the send
  // failed the way a lost connection fails and is retried as one. The banner names the
  // link that ends it.
  if (response.status === KEY_REFUSED)
    throw new Error("the server refused this page's key");
  return response;
};

// Pasted pixels become page content before their Markdown reference enters a draft.
// The raw body keeps binary data out of JSON and the append-only log; the server
// derives the served extension and returns the canonical page-relative path. Like an
// event POST, this request waits for a known layer and accounts for its whole trip.
export const uploadMedia = async (file) => {
  if (offlineInteractive)
    throw new Error("no agent or server is available in an interactive export");
  await layerReady;
  countTraffic("sends");
  let answer;
  try {
    answer = await requestJson(
      pageUrl("api/media"),
      { method: "POST", headers: { "Content-Type": file.type }, body: file },
      "image upload",
    );
  } catch (error) {
    if (error instanceof LayerRefused) return null;
    throw error;
  } finally {
    countTraffic("acked");
  }
  if (typeof answer?.path !== "string")
    throw new Error("image upload returned no media path");
  return answer.path;
};

// The page reporting itself broken, to the party who can fix it: the agent
// authored the page and its widgets, and before this the only route for a
// live-session fault was the user pasting a console nobody told them to
// open. The event lands in the log as kind "error", author "page" — the
// watcher hears it beside comments and reports; the user's pending count
// never claims it. Logged once per message text per load (a reload may repeat
// one — bounded noise over silence), capped so a fault in a loop cannot flood
// the log, and sent bare rather than through post(): a poll fault reporting
// itself through the poll would recurse, and nothing here needs the answer.
// Not part of the helper surface a module gets: an upgrade that throws is already on
// this path through window.error, and a widget that wants to say so itself has
// failSoft, which puts the message where the user is looking and reports it here.
const reportedReasons = new WeakSet();
const reportedPrimitives = new Set();
const reportedErrors = new Set();
export function reportPageError(reason, context = "") {
  if (typeof reason === "object" && reason !== null) reportedReasons.add(reason);
  else reportedPrimitives.add(String(reason));
  const text = exceptionText(reason, context);
  console.error(`leaf: ${text}`);
  if (offlineInteractive) return;
  if (reportedErrors.has(text) || reportedErrors.size >= 20) return;
  reportedErrors.add(text);
  postEvent({
    kind: "error",
    text,
    ...(runtime.currentRevision != null && { revision: runtime.currentRevision }),
  }).catch(() => {});
}

// What a consumer reports of a fault it carries: a rejection that travelled up to it
// from the presentation coordinator or state application, say. Where the producer
// already reported that fault, a second report would add only the consumer's context
// and make one fault read as several, so it is dropped; for a fault no producer saw,
// such as a malformed state body, the consumer is the only reporter. A producer that
// shares one exception among owners, as a cached rejected load does among its widgets,
// reports through reportPageError, once per owner. A primitive reason has no identity,
// so its text stands for it.
export function reportCarried(reason, context = "") {
  const reported =
    typeof reason === "object" && reason !== null
      ? reportedReasons.has(reason)
      : reportedPrimitives.has(String(reason));
  if (!reported) reportPageError(reason, context);
}

// This is the only exception formatter. Callers pass the original exception (or
// its name/message/stack record across a realm boundary) and the operation's context.
// A diagnostic with no exception remains a string; no synthetic Error invents a site.
export function exceptionText(reason, context = "") {
  const message = reason?.message;
  const text =
    message === undefined ? String(reason) : `${reason.name || "Error"}: ${message}`;
  // Chrome includes the message in a stack; Firefox can supply frames alone.
  const stack = reason?.stack;
  let evidence = !stack ? text : stack.includes(text) ? stack : `${text}\n${stack}`;
  if (reason instanceof AggregateError)
    evidence += reason.errors.map((error) => `\n${exceptionText(error)}`).join("");
  if (reason?.cause !== undefined)
    evidence += `\nCaused by: ${exceptionText(reason.cause)}`;
  if (!context) return evidence;
  const summary =
    reason instanceof Error ? describeFailure(reason) : (message ?? String(reason));
  return `${context}: ${summary}${message === undefined ? "" : `\n${evidence}`}`;
}

window.addEventListener("error", (e) => {
  // Chrome also puts ResizeObserver loop notices on window.error without an
  // exception. This one live page cannot tell an occasional scheduling notice
  // from a layout feedback loop, so it persists neither in the user's log. The
  // render gate and test navigation take one complete confirming reading and
  // report a notice that recurs there.
  if (e.message?.startsWith("ResizeObserver loop")) return;
  reportPageError(
    e.error?.stack ? e.error : `${e.message} (${e.filename}:${e.lineno})`,
  );
});
window.addEventListener("unhandledrejection", (e) => {
  reportPageError(e.reason);
});
