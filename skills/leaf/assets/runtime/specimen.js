/* A specimen is a normally served Leaf page with its own disposable event log.
 * The server captures an authored template and its layer; this owner handles the
 * frame's readiness and reset. The child arrives inert, so its startup cannot take
 * focus from the page; this owner releases a live child once it presents, and after
 * that focus entering the frame is entry, the way it is for any iframe. The child's
 * final Escape asks the frame's owner to take focus back with `lf-specimen-return`. Passive demonstrations use the
 * same host and remain inert throughout their playback. */
import { layerHeaders } from "./layer-client.js";
import { pageUrl } from "./context.js";
import { discardPageStorage } from "./storage.js";

async function request(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: layerHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
    keepalive: true,
  });
  const answer = await response.json();
  if (!response.ok)
    throw new Error(answer.error ?? `specimen: HTTP ${response.status}`);
  return answer;
}

function presented(frame, url, signal) {
  return new Promise((resolve, reject) => {
    let observer;
    const cleanup = () => {
      clearTimeout(timeout);
      observer?.disconnect();
      detached.disconnect();
      frame.removeEventListener("load", loaded);
      signal.removeEventListener("abort", aborted);
    };
    const finish = (error, doc) => {
      cleanup();
      if (error) reject(error);
      else resolve(doc);
    };
    const aborted = () => finish(signal.reason);
    const detached = new MutationObserver(() => {
      if (!frame.isConnected)
        finish(new DOMException("specimen disconnected", "AbortError"));
    });
    const loaded = () => {
      const doc = frame.contentDocument;
      if (!doc || frame.contentWindow.location.href !== url) return;
      const inspect = () => {
        const failure = doc.documentElement.dataset.lfStartupError;
        if (failure) finish(new Error(failure));
        else if (doc.body?.hasAttribute("data-lf-presented")) finish(null, doc);
      };
      observer = new MutationObserver(inspect);
      observer.observe(doc, { attributes: true, childList: true, subtree: true });
      inspect();
    };
    const timeout = setTimeout(
      () => finish(new Error(`Leaf specimen did not present: ${url}`)),
      30000,
    );
    signal.addEventListener("abort", aborted, { once: true });
    if (signal.aborted || !frame.isConnected) {
      finish(signal.reason ?? new DOMException("specimen disconnected", "AbortError"));
      return;
    }
    detached.observe(frame.ownerDocument, { childList: true, subtree: true });
    frame.addEventListener("load", loaded);
    frame.src = url;
  });
}

export function mountSpecimen(frame, { template, passive = false }) {
  if (!template) throw new Error("a specimen needs an authored template id");
  let current = null;
  let destroyed = false;
  let operation = null;
  let closing = null;
  let loading = null;
  frame.inert = passive;
  frame.toggleAttribute("data-lf-contained", true);

  const release = (url) => request(new URL("api/release", url), {});

  function retire() {
    if (!current) return;
    const previous = current;
    current = null;
    // Removal synchronously destroys the old browsing context, including its
    // pagehide writers. A navigation would leave it running until commit.
    const parent = frame.parentNode;
    const next = frame.nextSibling;
    frame.remove();
    frame.removeAttribute("src");
    frame.removeAttribute("srcdoc");
    discardPageStorage(previous);
    parent?.insertBefore(frame, next);
    return release(previous);
  }

  async function replace() {
    await retire();
    if (destroyed) throw new DOMException("specimen destroyed", "AbortError");
    const { url } = await request(pageUrl("api/specimens"), { template, passive });
    current = new URL(url, location.href).href;
    try {
      if (destroyed) throw new DOMException("specimen destroyed", "AbortError");
      loading = new AbortController();
      const doc = await presented(frame, current, loading.signal);
      if (!passive) doc.body.inert = false;
      return doc;
    } catch (error) {
      await retire();
      throw error;
    } finally {
      loading = null;
    }
  }

  function reset() {
    if (destroyed)
      return Promise.reject(new Error("the specimen host has been destroyed"));
    if (!operation) {
      operation = replace();
      const settled = () => {
        operation = null;
      };
      operation.then(settled, settled);
    }
    return operation;
  }

  const host = {
    ready: null,
    reset,
    destroy() {
      if (closing) return closing;
      destroyed = true;
      loading?.abort();
      window.removeEventListener("pagehide", departing);
      // Retire synchronously even on pagehide. An allocation already in flight
      // still has to answer so replace() can release that child's exact URL.
      closing = Promise.all([retire(), operation?.catch(() => {})]);
      return closing;
    },
  };
  const departing = (event) => {
    if (!event.persisted) void host.destroy();
  };
  window.addEventListener("pagehide", departing);
  host.ready = reset();
  return host;
}
