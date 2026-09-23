/* A specimen is a normally served Leaf page with its own disposable event log.
 * The server captures an authored template and its layer; this owner handles the
 * frame's readiness, reset, and explicit focus entry and return. Passive
 * demonstrations use the same host and remain inert throughout their playback.
 *
 * `mountSpecimen(frame, {template, passive})` returns a host whose `ready` resolves to
 * the presented child `Document`; `reset()` replaces the child and resolves the same
 * way; `enter(returnTo)` activates it and records the control `leave()` returns to;
 * `destroy()` releases it. The frame emits `lf-specimen-enter` and `lf-specimen-leave`
 * as the focus boundary changes, including Escape from the child. The authored element
 * and its isolation contract are page-authoring.md's "Live specimens". */
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
  let returnTo = null;
  let active = false;
  let destroyed = false;
  let operation = null;
  let closing = null;
  let loading = null;
  frame.inert = true;
  frame.toggleAttribute("data-lf-contained", true);
  if (!passive) frame.dataset.lfExport = "document";

  const leave = () => {
    if (!active) return;
    active = false;
    frame.inert = true;
    if (frame.contentDocument?.body) frame.contentDocument.body.inert = true;
    returnTo?.focus({ preventScroll: true });
    frame.dispatchEvent(new Event("lf-specimen-leave"));
  };
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
    leave();
    await retire();
    if (destroyed) throw new DOMException("specimen destroyed", "AbortError");
    const { url } = await request(pageUrl("api/specimens"), { template, passive });
    current = new URL(url, location.href).href;
    try {
      if (destroyed) throw new DOMException("specimen destroyed", "AbortError");
      loading = new AbortController();
      return await presented(frame, current, loading.signal);
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
    enter(destination = document.activeElement) {
      if (passive) throw new Error("a passive specimen cannot receive focus");
      if (!frame.contentDocument?.body.hasAttribute("data-lf-presented"))
        throw new Error("the specimen has not presented");
      returnTo = destination;
      active = true;
      frame.inert = false;
      const body = frame.contentDocument.body;
      body.inert = false;
      body.tabIndex = -1;
      body.focus({ preventScroll: true });
      frame.dispatchEvent(new Event("lf-specimen-enter"));
    },
    leave,
    destroy() {
      if (closing) return closing;
      destroyed = true;
      leave();
      loading?.abort();
      frame.removeEventListener("lf-specimen-return", leave);
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
  frame.addEventListener("lf-specimen-return", leave);
  host.ready = reset();
  return host;
}
