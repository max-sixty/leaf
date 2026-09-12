/* The vendored-generation gate, the event and media doors, and the page's error channel
   to the agent.

   A vendored runtime and registry are one generation. This module carries the
   `__LEAF_LAYER_GENERATION__` placeholder (quoted, once) and the registry carries the same epoch
   after `page init`. `sameDelivery` checks every successful state read and POST response
   against the document's layer and website release. Active responses also establish the
   private server incarnation, so an ephemeral replacement reloads before its new event
   sequence meets the old DOM. Do not let one delivery interpret another's state.

   `reportPageError` is the common runtime error surface. A widget failure may `failSoft`
   its own element so the rest of the page and Threads remain usable, but it does not
   convert a partial state read into a committed one. The window error listener, module
   load failures, and render gate all report through the same page-level evidence. Do not
   catch an error merely to stamp readiness or continue accounting for pending attempts. */

import { countTraffic } from "./traffic.js";
import { runtime } from "./context.js";
import { notice } from "./notifications.js";

const layerGeneration = "__LEAF_LAYER_GENERATION__";
const runtimeScript = document.querySelector("script[data-lf-server]");
const documentLayer = runtimeScript?.dataset.lfLayer;
const release = runtimeScript?.dataset.lfRelease;

if (documentLayer && documentLayer !== layerGeneration) {
  window.dispatchEvent(new Event("lf-startup-failed"));
  throw new Error("Leaf's document and runtime belong to different layers");
}

let layerReloading = false;
function reloadDelivery(message) {
  if (layerReloading) return;
  layerReloading = true;
  notice(message);
  location.reload();
}

export function layerHeaders(headers = {}) {
  return {
    "Leaf-Layer": layerGeneration,
    ...(release && { "Leaf-Release": release }),
    ...headers,
  };
}

export function sameLayer(generation) {
  if (generation === layerGeneration) return true;
  // Say what is about to happen before it happens. The reader is looking at a page
  // that re-vendoring has moved out from under, and a tab that reloads itself with
  // nothing said is a page that appears to have lost their place for no reason.
  reloadDelivery("Leaf has been updated — reloading this page.");
  return false;
}

export function sameDelivery(response) {
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
let sessionServer = null;
const sessionChannel =
  release && typeof window.BroadcastChannel !== "undefined"
    ? new window.BroadcastChannel("leaf-session")
    : null;

function activateSession(broadcast, server = null) {
  if (server && sessionServer && server !== sessionServer) {
    reloadDelivery("This Leaf session restarted — reloading the page.");
    return;
  }
  if (server) sessionServer = server;
  const activated = sessionMode !== "active";
  sessionMode = "active";
  if (activated) document.dispatchEvent(new Event("lf-session-active"));
  if (broadcast) sessionChannel?.postMessage({ active: true, server });
}

sessionChannel?.addEventListener("message", (event) => {
  if (event.data?.active === true) activateSession(false, event.data.server);
});

export function observeSession(response) {
  const reference = response.headers.get("Leaf-Session-Reference");
  if (/^\d{12}$/.test(reference)) runtime.sessionReference = reference;
  const mode = response.headers.get("Leaf-Session");
  if (mode !== "active" && mode !== "passive") return;
  if (mode === "active") activateSession(true, response.headers.get("Leaf-Server"));
  else if (sessionMode !== "active") sessionMode = "passive";
}

export const sessionIsActive = () => sessionMode === "active";

export let revealLayer;
const layerReady = new Promise((resolve) => (revealLayer = resolve));

// The page's one door to the log, spelled once. Two callers reach it — `post`, which
// orders the reader's own gestures through it, and the error report below, which
// deliberately doesn't — and what they share is the request rather than anything about
// the sending: same path, same method, same encoding, so a door that moved would move
// for both. Whether a send waits on the one before it belongs to the caller.
export const postEvent = async (event) => {
  await layerReady;
  countTraffic("sends");
  let response;
  try {
    response = await fetch("/api/event", {
      method: "POST",
      headers: layerHeaders({
        "Content-Type": "application/json",
        ...(runtime.currentRevision && {
          "Leaf-View-Revision": String(runtime.currentRevision),
        }),
      }),
      body: JSON.stringify(event),
    });
  } finally {
    countTraffic("acked");
  }
  observeSession(response);
  if (response.ok && !sameDelivery(response)) return null;
  return response;
};

// Pasted pixels become page content before their Markdown reference enters a draft.
// The raw body keeps binary data out of JSON and the append-only log; the server
// derives the served extension and returns the canonical page-relative path. Like an
// event POST, this request waits for a known layer and accounts for its whole trip.
export const uploadMedia = async (file) => {
  await layerReady;
  countTraffic("sends");
  let response;
  try {
    response = await fetch("/api/media", {
      method: "POST",
      headers: layerHeaders({
        "Content-Type": file.type,
      }),
      body: file,
    });
  } finally {
    countTraffic("acked");
  }
  observeSession(response);
  if (response.ok && !sameDelivery(response)) return null;
  let answer;
  try {
    answer = await response.json();
  } catch {
    throw new Error(`image upload returned HTTP ${response.status}`);
  }
  if (!response.ok)
    throw new Error(answer?.error ?? `image upload returned HTTP ${response.status}`);
  if (typeof answer?.path !== "string")
    throw new Error("image upload returned no media path");
  return answer.path;
};

// The page reporting itself broken, to the party who can fix it: the agent
// authored the page and its widgets, and before this the only route for a
// live-session fault was the reader pasting a console nobody told them to
// open. The event lands in the log as kind "error", author "page" — the
// watcher hears it beside comments and reports; the reader's pending count
// never claims it. Deduped per message per load (a reload may repeat one —
// bounded noise over silence), capped so a fault in a loop cannot flood the
// log, and sent bare rather than through post(): a poll fault reporting
// itself through the poll would recurse, and nothing here needs the answer.
// Not part of the helper surface a module gets: an upgrade that throws is already on
// this path through window.error, and a widget that wants to say so itself has
// failSoft, which puts the message where the reader is looking.
const reportedErrors = new Set();
export function reportPageError(text) {
  console.error(`leaf: ${text}`);
  if (reportedErrors.has(text) || reportedErrors.size >= 20) return;
  reportedErrors.add(text);
  postEvent({
    kind: "error",
    text,
    ...(runtime.currentRevision != null && { revision: runtime.currentRevision }),
  }).catch(() => {});
}

window.addEventListener("error", (e) => {
  // Chrome also puts ResizeObserver loop notices on window.error without an
  // exception. This one live page cannot tell an occasional scheduling notice
  // from a layout feedback loop, so it persists neither in the reader's log. The
  // render gate and test navigation take one complete confirming reading and
  // report a notice that recurs there.
  if (e.message?.startsWith("ResizeObserver loop")) return;
  reportPageError(`${e.message} (${e.filename}:${e.lineno})`);
});
window.addEventListener("unhandledrejection", (e) => {
  // Chrome's stack embeds "Error: message"; Firefox's carries frames only, so a
  // stack alone can post an error event that never says what failed.
  const reason = String(e.reason);
  const stack = e.reason?.stack;
  reportPageError(
    !stack ? reason : stack.includes(reason) ? stack : `${reason}\n${stack}`,
  );
});
