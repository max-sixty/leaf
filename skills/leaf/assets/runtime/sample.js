/* A sample owns a disposable served page in an opaque browsing context. Its
 * unguessable page URL grants native requests to its own document, assets and log;
 * presentation commands and observations cross a private port as values.
 * Allocation captures the owning widget's immutable revision. Reset replaces the
 * allocation, admitting its initial document with a credentialless HEAD before
 * native navigation. A later authored navigation keeps the frame and disables its
 * private port; an ordinary reload reconnects with a fresh presentation promise.
 * An opaque parent cannot classify a later document which has no Leaf bootstrap.
 * Departed ports cannot settle the replacement's calls.
 * A block follows the child's reported height; a window keeps its own viewport.
 * Passive demonstrations remain inert. Removing a frame retires its realm before
 * releasing the allocation, including on reset and parent departure. */
import { layerHeaders } from "./layer-client.js";
import { pageUrl, runtime } from "./context.js";
import { dressFor, registerSampleDress } from "./dress.js";
import { widgetDescriptor } from "./widget-descriptors.js";
import { excludedByInert, upFrom } from "./shadow.js";
import { seenRect } from "./geometry.js";
import {
  sampleVisibility,
  onSampleVisibility,
  readSampleVisibility,
} from "./sample-visibility.js";
import { nativeModalAdmits } from "./keyboard/layer-stack.js";
import { keeps } from "./keeps.js";
import { nextRender, sizeObserver } from "./rendering.js";

// A page can carry many samples. Their child documents each import the runtime;
// presenting them together can exhaust the browser's request pool before any child
// finishes loading its module graph. Bound simultaneous loads across this page. A
// loaded child can keep reading slow state without holding up the next sample.
const MAX_LOADING_SAMPLES = 3;
let loadingSamples = 0;
const loadWaiters = [];
async function loadWithinLimit(work) {
  if (loadingSamples === MAX_LOADING_SAMPLES)
    await new Promise((resolve) => loadWaiters.push(resolve));
  else loadingSamples++;
  let released = false;
  const release = () => {
    if (released) return;
    released = true;
    if (loadWaiters.length) loadWaiters.shift()();
    else loadingSamples--;
  };
  try {
    return await work(release);
  } finally {
    release();
  }
}

async function request(url, body, headers = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: layerHeaders({ "Content-Type": "application/json", ...headers }),
    body: JSON.stringify(body),
    keepalive: true,
  });
  const answer = await response.json();
  if (!response.ok) throw new Error(answer.error ?? `sample: HTTP ${response.status}`);
  return answer;
}

export function mountSample(
  frame,
  { template, passive = false, window: asWindow = false },
) {
  if (!template) throw new Error("a sample needs an authored template id");
  let revision = runtime.currentRevision;
  for (let owner = frame.parentElement; owner; owner = owner.parentElement) {
    const descriptor = widgetDescriptor(owner);
    if (!descriptor) continue;
    if (descriptor.document.kind === "page") revision = descriptor.document.revision;
    break;
  }
  let current = null;
  let destroyed = false;
  let operation = null;
  let closing = null;
  let channel = null;
  let nextId = 0;
  let readyResolve;
  let readyReject;
  let presenting = false;
  let hasConnected = false;
  let connectedNonce = null;
  const candidates = new Set();
  const pending = new Map();
  const listeners = new Map();
  const notify = (type, detail) => {
    for (const callback of listeners.get(type) ?? []) callback(detail);
  };
  keeps(
    frame,
    "sandbox",
    "allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals allow-downloads allow-pointer-lock",
  );
  frame.toggleAttribute("inert", passive);
  frame.toggleAttribute("data-lf-contained", true);

  function admitted() {
    for (let owner = frame; owner; owner = upFrom(owner))
      if (owner.getAttribute?.("aria-hidden") === "true") return false;
    return (
      !passive &&
      document.visibilityState === "visible" &&
      frame.checkVisibility({ visibilityProperty: true }) &&
      !excludedByInert(frame) &&
      nativeModalAdmits(frame) &&
      sampleVisibility()?.visible !== false
    );
  }
  function visibility() {
    channel?.postMessage({ type: "visibility", detail: { visible: admitted() } });
  }
  async function readVisibility(port, id) {
    try {
      const outer = await readSampleVisibility();
      if (channel !== port) return;
      const rect = frame.getBoundingClientRect();
      const shown = seenRect(frame, new Map());
      const band = shown ?? { left: 0, top: 0, right: 0, bottom: 0 };
      const left = Math.max(rect.left, band.left, outer?.left ?? 0);
      const top = Math.max(rect.top, band.top, outer?.top ?? 0);
      const right = Math.min(rect.right, band.right, outer?.right ?? innerWidth);
      const bottom = Math.min(rect.bottom, band.bottom, outer?.bottom ?? innerHeight);
      const scaleX = rect.width / frame.offsetWidth || 1;
      const scaleY = rect.height / frame.offsetHeight || 1;
      port.postMessage({
        type: "visibility-reading",
        detail: {
          id,
          visible:
            admitted() && outer?.visible !== false && right > left && bottom > top,
          left: (left - rect.left) / scaleX - frame.clientLeft,
          top: (top - rect.top) / scaleY - frame.clientTop,
          right: (right - rect.left) / scaleX - frame.clientLeft,
          bottom: (bottom - rect.top) / scaleY - frame.clientTop,
        },
      });
    } catch (error) {
      if (channel !== port) return;
      port.postMessage({
        type: "visibility-reading",
        detail: { id, error: { name: error.name, message: error.message } },
      });
      reportError(error);
    }
  }
  function disconnect(reason) {
    channel?.close();
    channel = null;
    connectedNonce = null;
    for (const { reject } of pending.values()) reject(reason);
    pending.clear();
  }
  // Public readiness includes failure retirement. Reset coalesces this same
  // operation, so a reported failure already permits a fresh allocation.
  function begin(work) {
    const active = work;
    operation = active;
    host.ready = active;
    const settled = () => {
      if (operation === active) operation = null;
    };
    active.then(settled, settled);
    return active;
  }
  async function settle(work) {
    try {
      return await work;
    } catch (error) {
      // Native navigation cancels the private presentation, while the browser
      // keeps its destination. Reset and destroy retire allocations themselves.
      if (error.name !== "AbortError") await retire();
      throw error;
    }
  }
  function presentation() {
    presenting = true;
    return new Promise((resolve, reject) => {
      readyResolve = (value) => {
        presenting = false;
        resolve(value);
      };
      readyReject = (error) => {
        presenting = false;
        reject(error);
      };
    });
  }
  function failure(error) {
    if (presenting) readyReject(error);
    else {
      begin(settle(Promise.reject(error)));
      notify("loading");
    }
  }
  function connect(event) {
    if (
      !current ||
      event.source !== frame.contentWindow ||
      event.data?.sample !== new URL(current).pathname
    )
      return;
    if (
      event.data.type !== "leaf-sample-connect" ||
      typeof event.data.nonce !== "string" ||
      event.data.nonce === connectedNonce
    )
      return;
    const nonce = event.data.nonce;
    const owned = current;
    const pair = new MessageChannel();
    const port = pair.port1;
    // Publish this private document endpoint at the existing diagnostic seam.
    document.querySelector("script[data-lf-entry]").lfDocumentPort = port;
    candidates.add(port);
    port.onmessage = ({ data }) => {
      if (data.type === "connected") {
        if (!candidates.has(port) || current !== owned || data.nonce !== nonce) return;
        candidates.delete(port);
        for (const candidate of candidates) candidate.close();
        candidates.clear();
        const reloading = hasConnected;
        disconnect(new DOMException("sample document replaced", "AbortError"));
        channel = port;
        connectedNonce = nonce;
        hasConnected = true;
        if (reloading) {
          const previousResolve = readyResolve;
          const previousReject = readyReject;
          begin(settle(presentation())).then(previousResolve, previousReject);
          notify("loading");
        }
        visibility();
        return;
      }
      // Messages from the departed realm cannot settle the next realm's calls.
      if (channel !== port) return;
      if (data.type === "departed") {
        const error = new DOMException("sample document navigated", "AbortError");
        disconnect(error);
        if (presenting) readyReject(error);
        else begin(Promise.reject(error));
        notify("departed");
        return;
      }
      if (data.type === "visibility-read") {
        void readVisibility(port, data.detail.id);
        return;
      }
      if (pending.has(data.id)) {
        const { resolve, reject } = pending.get(data.id);
        pending.delete(data.id);
        if (data.error)
          reject(
            Object.assign(new Error(data.error.message), { name: data.error.name }),
          );
        else resolve(data.result);
      } else if (data.type === "ready") {
        readyResolve(data.detail);
        visibility();
      } else if (data.type === "error") {
        failure(new Error(data.detail.message));
      } else if (data.type === "return")
        frame.dispatchEvent(new Event("lf-sample-return"));
      else notify(data.type, data.detail);
    };
    event.source.postMessage(
      {
        sample: event.data.sample,
        nonce,
        settings: { passive, window: asWindow, dress: dressFor(frame) ?? undefined },
      },
      "*",
      [pair.port2],
    );
  }
  window.addEventListener("message", connect);
  window.addEventListener("scroll", visibility, true);
  window.addEventListener("resize", visibility);
  document.addEventListener("visibilitychange", visibility);
  const seen = new IntersectionObserver(visibility, { threshold: [0, 1] });
  seen.observe(frame);
  const size = sizeObserver(visibility);
  size.observe(frame);
  const admission = new MutationObserver((records) => {
    if (records.some(({ target }) => target === frame || target.contains(frame)))
      visibility();
  });
  admission.observe(document, {
    subtree: true,
    attributes: true,
    attributeFilter: ["inert", "open", "hidden", "aria-hidden", "class", "style"],
  });
  const nativeTransition = () => nextRender(visibility);
  for (const type of ["beforetoggle", "toggle", "close"])
    document.addEventListener(type, nativeTransition, true);
  const unwatch = onSampleVisibility(visibility);
  const undress = registerSampleDress(frame, (dress) =>
    channel?.postMessage({ type: "dress", detail: dress }),
  );
  const lifetime = new MutationObserver(() => {
    if (!frame.isConnected) void host.destroy();
  });
  lifetime.observe(document, { childList: true, subtree: true });

  function retire() {
    if (!current) return;
    const previous = current;
    current = null;
    hasConnected = false;
    const cancelled = new DOMException("sample replaced", "AbortError");
    disconnect(cancelled);
    for (const port of candidates) port.close();
    candidates.clear();
    readyReject?.(cancelled);
    const parent = frame.parentNode;
    const next = frame.nextSibling;
    frame.remove();
    frame.removeAttribute("src");
    parent?.insertBefore(frame, next);
    return request(new URL("api/release", previous), {});
  }
  async function replace() {
    await retire();
    return settle(
      loadWithinLimit(async (release) => {
        if (destroyed) throw new DOMException("sample destroyed", "AbortError");
        const { url } = await request(
          pageUrl("api/samples"),
          { template, passive },
          revision ? { "Leaf-View-Revision": String(revision) } : {},
        );
        current = new URL(url, location.href).href;
        try {
          if (destroyed) {
            await retire();
            throw new DOMException("sample destroyed", "AbortError");
          }
          // The opaque frame cannot expose its document or order cross-process
          // bootstrap messages against load. Admit the server's document contract
          // before native navigation; later authored destinations remain native.
          const admission = await fetch(current, {
            method: "HEAD",
            credentials: "omit",
          });
          if (!admission.ok || !admission.headers.has("Leaf-Document"))
            throw new Error("The sample document did not start Leaf");
          if (destroyed) {
            await retire();
            throw new DOMException("sample destroyed", "AbortError");
          }
          const presented = presentation();
          // A loaded module graph frees its slot even while presentation waits on
          // slow state. Native load needs no access to the opaque child document.
          frame.addEventListener("load", release, { once: true });
          frame.src = current;
          return await presented;
        } finally {
          frame.removeEventListener("load", release);
        }
      }),
    );
  }
  function reset() {
    if (destroyed)
      return Promise.reject(new Error("the sample host has been destroyed"));
    if (!operation) begin(replace());
    return operation;
  }
  const host = {
    ready: null,
    reset,
    // Full view keeps the realm, log and native editor; only its allocation changes.
    setWindow(value) {
      asWindow = value;
      return host.call("window", { window: value });
    },
    call(method, detail = {}) {
      const ready = host.ready;
      return ready.then(() => {
        if (ready !== host.ready || !channel)
          throw new DOMException("sample unavailable", "AbortError");
        const id = ++nextId;
        return new Promise((resolve, reject) => {
          pending.set(id, { resolve, reject });
          channel.postMessage({ id, method, detail });
        });
      });
    },
    on(type, callback) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type).add(callback);
      return () => listeners.get(type).delete(callback);
    },
    dress: (dress) => channel?.postMessage({ type: "dress", detail: dress }),
    showThread(id, { signal, ...options }) {
      if (signal.aborted) return Promise.resolve(false);
      const cancel = () => channel?.postMessage({ type: "cancel-view" });
      signal.addEventListener("abort", cancel, { once: true });
      return host
        .call("thread", { id, ...options })
        .finally(() => signal.removeEventListener("abort", cancel));
    },
    destroy() {
      if (closing) return closing;
      destroyed = true;
      window.removeEventListener("message", connect);
      window.removeEventListener("pagehide", departing);
      window.removeEventListener("scroll", visibility, true);
      window.removeEventListener("resize", visibility);
      document.removeEventListener("visibilitychange", visibility);
      seen.disconnect();
      size.disconnect();
      admission.disconnect();
      for (const type of ["beforetoggle", "toggle", "close"])
        document.removeEventListener(type, nativeTransition, true);
      lifetime.disconnect();
      unwatch();
      undress();
      closing = Promise.all([retire(), operation?.catch(() => {})]);
      return closing;
    },
  };
  const departing = (event) => {
    if (!event.persisted) void host.destroy();
  };
  window.addEventListener("pagehide", departing);
  reset();
  return host;
}
