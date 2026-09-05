/* The vendored-generation gate, the event and media doors, and the page's error channel
   to the agent.

   A vendored runtime and registry are one generation. The runtime contains the
   `"__LEAF_LAYER_GENERATION__"` placeholder and the registry carries the same epoch
   after `page init`. `sameLayer` checks every successful state read and POST response.
   If the server speaks a newer layer, the tab reloads before it reads or posts again. Do
   not let one generation interpret another generation's registry or events.

   `reportPageError` is the common runtime error surface. A widget failure may `failSoft`
   its own element so the rest of the page and Threads remain usable, but it does not
   convert a partial state read into a committed one. The window error listener, module
   load failures, and render gate all report through the same page-level evidence. Do not
   catch an error merely to stamp readiness or continue accounting for outbox attempts. */

import { countTraffic } from "./traffic.js";

export function createLayerClient({ currentRevision, layerGeneration, sayLine }) {
  let layerReloading = false;
  function sameLayer(generation) {
    if (generation === layerGeneration) return true;
    if (!layerReloading) {
      layerReloading = true;
      // Say what is about to happen before it happens. The reader is looking at a page
      // that re-vendoring has moved out from under, and a tab that reloads itself with
      // nothing said is a page that appears to have lost their place for no reason.
      sayLine("Leaf has been updated — reloading this page.");
      location.reload();
    }
    return false;
  }

  let revealLayer;
  const layerReady = new Promise((resolve) => (revealLayer = resolve));

  // The page's one door to the log, spelled once. Two callers reach it — `post`, which
  // orders the reader's own gestures through it, and the error report below, which
  // deliberately doesn't — and what they share is the request rather than anything about
  // the sending: same path, same method, same encoding, so a door that moved would move
  // for both. Whether a send waits on the one before it belongs to the caller.
  const postEvent = async (event) => {
    await layerReady;
    countTraffic("sends");
    let response;
    try {
      response = await fetch("/api/event", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Leaf-Layer": layerGeneration,
          ...(currentRevision() && {
            "Leaf-View-Revision": String(currentRevision()),
          }),
        },
        body: JSON.stringify(event),
      });
    } finally {
      countTraffic("acked");
    }
    const responseGeneration = response.headers.get("Leaf-Layer");
    if (response.ok && responseGeneration && !sameLayer(responseGeneration))
      return null;
    return response;
  };

  // Pasted pixels become page content before their Markdown reference enters a draft.
  // The raw body keeps binary data out of JSON and the append-only log; the server
  // derives the served extension and returns the canonical page-relative path. Like an
  // event POST, this request waits for a known layer and accounts for its whole trip.
  const uploadMedia = async (file) => {
    await layerReady;
    countTraffic("sends");
    let response;
    try {
      response = await fetch("/api/media", {
        method: "POST",
        headers: {
          "Content-Type": file.type,
          "Leaf-Layer": layerGeneration,
        },
        body: file,
      });
    } finally {
      countTraffic("acked");
    }
    const responseGeneration = response.headers.get("Leaf-Layer");
    if (response.ok && responseGeneration && !sameLayer(responseGeneration))
      return null;
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
  function reportPageError(text) {
    console.error(`leaf: ${text}`);
    if (reportedErrors.has(text) || reportedErrors.size >= 20) return;
    reportedErrors.add(text);
    postEvent({
      kind: "error",
      text,
      ...(currentRevision() != null && { revision: currentRevision() }),
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

  return { postEvent, reportPageError, revealLayer, sameLayer, uploadMedia };
}
