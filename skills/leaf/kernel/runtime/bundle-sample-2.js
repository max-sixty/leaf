import {
  dressFor,
  registerSampleDress
} from "./bundle-dress.js";
import {
  aborted,
  widgetDescriptor
} from "./bundle-widget-upgrade.js";
import {
  containingView,
  frameView,
  presented,
  recordInteraction,
  requestJson,
  watchRoom
} from "./bundle-page-paint.js";
import {
  pageUrl,
  runtime
} from "./bundle-semantic-state.js";
import {
  move
} from "./bundle-dom-move.js";
import {
  keeps,
  nextRender,
  onSampleVisibility,
  readSampleVisibility,
  sampleVisibility,
  sizeObserver
} from "./bundle-sample-visibility.js";

// runtime/sample.js
var MAX_LOADING_SAMPLES = 3;
var loadingSamples = 0;
var loadWaiters = [];
var nextHost = 0;
async function loadWithinLimit(work, signal) {
  signal.throwIfAborted();
  if (loadingSamples === MAX_LOADING_SAMPLES) {
    const { promise: turn, resolve: proceed } = Promise.withResolvers();
    loadWaiters.push(proceed);
    await Promise.race([turn, aborted(signal)]);
    const waiting = loadWaiters.indexOf(proceed);
    if (waiting !== -1) {
      loadWaiters.splice(waiting, 1);
      throw signal.reason;
    }
  } else loadingSamples++;
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
var departure = (message) => new DOMException(message, "SampleDepartedError");
var mounted = /* @__PURE__ */ new Map();
var isSampleFrame = (node) => mounted.has(node);
var sampleFrameImage = (frame, crop) => mounted.get(frame).call("image", crop);
var request = (url, body, headers = {}) => requestJson(
  url,
  {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
    keepalive: true
  },
  "sample"
);
function mountSample(frame, { template, window: asWindow = false, chrome = void 0 }) {
  if (!template) throw new Error("a sample needs an authored template id");
  let revision = runtime.currentRevision;
  let message;
  for (let owner = frame.parentElement; owner; owner = owner.parentElement) {
    const descriptor = widgetDescriptor(owner);
    if (!descriptor) continue;
    if (descriptor.document.kind === "page") revision = descriptor.document.revision;
    else message = descriptor.document.message;
    break;
  }
  let current = null;
  let samplePage = null;
  let destroyed = false;
  let operation = null;
  let closing = null;
  let channel = null;
  let lost;
  let nextId = 0;
  let readyResolve;
  let readyReject;
  let upgrading = false;
  let hasConnected = false;
  let connectedNonce = null;
  const hostId = ++nextHost;
  const started = performance.now();
  let allocation = 0;
  const record = (phase, detail = {}) => recordInteraction("sample", {
    host: hostId,
    template,
    revision,
    allocation,
    sample: samplePage,
    document: connectedNonce,
    elapsed: performance.now() - started,
    phase,
    ...detail
  });
  const recordFailure = (error, detail = {}) => record("failed", {
    error: {
      name: error.name,
      message: error.message,
      stack: error.stack,
      status: error.status,
      body: error.body
    },
    ...detail
  });
  const lifetimeController = new AbortController();
  const candidates = /* @__PURE__ */ new Set();
  const pending = /* @__PURE__ */ new Map();
  const listeners = /* @__PURE__ */ new Map();
  const notify = (type, detail) => {
    for (const callback of listeners.get(type) ?? []) callback(detail);
  };
  keeps(
    frame,
    "sandbox",
    "allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals allow-downloads allow-pointer-lock"
  );
  frame.toggleAttribute("data-lf-contained", true);
  function admitted() {
    return document.visibilityState === "visible" && presented(frame) && sampleVisibility()?.visible !== false;
  }
  function visibility() {
    channel?.postMessage({ type: "visibility", detail: { visible: admitted() } });
  }
  async function readVisibility(port, id) {
    try {
      const outer = await readSampleVisibility();
      if (channel !== port) return;
      const within = outer ? outer.visible && outer : containingView();
      const view = admitted() && within && frameView(frame, within);
      port.postMessage({
        type: "visibility-reading",
        detail: { id, visible: Boolean(view), ...view }
      });
    } catch (error) {
      if (channel !== port) return;
      port.postMessage({
        type: "visibility-reading",
        detail: {
          id,
          error: { name: error.name, message: error.message, stack: error.stack }
        }
      });
      reportError(error);
    }
  }
  function disconnect(reason) {
    channel?.close();
    channel = null;
    lost = reason;
    connectedNonce = null;
    for (const { reject } of pending.values()) reject(reason);
    pending.clear();
  }
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
      if (error.name !== "AbortError") {
        recordFailure(error);
        await retire("failure", error);
      }
      throw error;
    }
  }
  function interfaceReady() {
    upgrading = true;
    return new Promise((resolve, reject) => {
      readyResolve = (value) => {
        upgrading = false;
        resolve(value);
      };
      readyReject = (error) => {
        upgrading = false;
        reject(error);
      };
    });
  }
  function awaitNext() {
    if (upgrading) return;
    host.ready = settle(interfaceReady());
    host.ready.catch(() => {
    });
  }
  function failure(error) {
    if (upgrading) readyReject(error);
    else {
      begin(settle(Promise.reject(error)));
      notify("loading");
    }
  }
  function connect(event) {
    if (!current || event.source !== frame.contentWindow || event.data?.sample !== new URL(current).pathname)
      return;
    if (event.data.type !== "leaf-sample-connect" || typeof event.data.nonce !== "string" || event.data.nonce === connectedNonce)
      return;
    const nonce = event.data.nonce;
    const owned = current;
    const pair = new MessageChannel();
    const port = pair.port1;
    document.querySelector("script[data-lf-entry]").lfDocumentPort = port;
    candidates.add(port);
    port.onmessage = ({ data }) => {
      if (data.type === "connected") {
        if (!candidates.has(port) || current !== owned || data.nonce !== nonce) return;
        candidates.delete(port);
        for (const candidate of candidates) candidate.close();
        candidates.clear();
        const reloading = hasConnected;
        disconnect(departure("sample document replaced"));
        channel = port;
        connectedNonce = nonce;
        hasConnected = true;
        record("connected", { reloading });
        if (reloading) {
          awaitNext();
          notify("loading");
        }
        visibility();
        return;
      }
      if (channel !== port) return;
      if (data.type === "departed") {
        record("departed");
        disconnect(departure("sample document navigated"));
        operation = null;
        awaitNext();
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
            Object.assign(
              new Error(data.error.message),
              { stack: void 0 },
              data.error
            )
          );
        else resolve(data.result);
      } else if (data.type === "ready") {
        record("upgraded");
        readyResolve(data.detail);
        visibility();
      } else if (data.type === "error") {
        failure(
          Object.assign(
            new Error(data.detail.message),
            { stack: void 0 },
            data.detail
          )
        );
      } else if (data.type === "return")
        frame.dispatchEvent(new Event("lf-sample-return"));
      else if (data.type === "step")
        frame.dispatchEvent(
          new CustomEvent("lf-sample-step", {
            bubbles: true,
            composed: true,
            detail: data.detail
          })
        );
      else notify(data.type, data.detail);
    };
    event.source.postMessage(
      {
        sample: event.data.sample,
        nonce,
        settings: { window: asWindow, dress: dressFor(frame) ?? void 0, chrome }
      },
      "*",
      [pair.port2]
    );
  }
  window.addEventListener("message", connect);
  const loaded = () => {
    if (current && frame.hasAttribute("src")) record("loaded");
  };
  frame.addEventListener("load", loaded);
  const room = watchRoom(visibility);
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
    attributeFilter: ["inert", "open", "hidden", "aria-hidden", "class", "style"]
  });
  const nativeTransition = () => nextRender(visibility);
  for (const type of ["beforetoggle"])
    document.addEventListener(type, nativeTransition, true);
  const unwatch = onSampleVisibility(visibility);
  const undress = registerSampleDress(
    frame,
    (dress) => channel?.postMessage({ type: "dress", detail: dress })
  );
  const lifetime = new MutationObserver(() => {
    if (!frame.isConnected) void host.destroy();
  });
  lifetime.observe(document, { childList: true, subtree: true });
  function retire(reason, cause = new DOMException("sample replaced", "AbortError")) {
    if (!current) return;
    const retiringDocument = connectedNonce;
    const previous = current;
    const sample = samplePage;
    current = null;
    samplePage = null;
    hasConnected = false;
    disconnect(cause);
    for (const port of candidates) port.close();
    candidates.clear();
    readyReject?.(cause);
    const parent = frame.parentNode;
    const next = frame.nextSibling;
    frame.remove();
    frame.removeAttribute("src");
    if (parent) move(parent, frame, next);
    record("retired", { reason, document: retiringDocument, sample });
    return request(new URL("api/release", previous), {}).catch((error) => {
      recordFailure(error, {
        operation: "release",
        document: retiringDocument,
        sample
      });
      throw error;
    });
  }
  async function replace() {
    await retire("reset");
    allocation++;
    record("queued");
    return settle(
      loadWithinLimit(async (release) => {
        if (destroyed) throw new DOMException("sample destroyed", "AbortError");
        record("allocating");
        const { url, page } = await request(
          pageUrl("api/samples"),
          { template, message },
          revision ? { "Leaf-View-Revision": String(revision) } : {}
        );
        current = new URL(url, location.href).href;
        samplePage = page;
        record("allocated");
        try {
          if (destroyed) {
            await retire("destroyed");
            throw new DOMException("sample destroyed", "AbortError");
          }
          const admission2 = await fetch(current, {
            method: "HEAD",
            credentials: "omit",
            signal: lifetimeController.signal
          });
          record("admission", {
            status: admission2.status,
            leafDocument: admission2.headers.get("Leaf-Document")
          });
          if (!admission2.ok || !admission2.headers.has("Leaf-Document"))
            throw new Error("The sample document did not start Leaf");
          if (destroyed) {
            await retire("destroyed");
            throw new DOMException("sample destroyed", "AbortError");
          }
          const upgraded = interfaceReady();
          frame.addEventListener("load", release, { once: true });
          record("loading");
          frame.src = current;
          return await upgraded;
        } finally {
          frame.removeEventListener("load", release);
        }
      }, lifetimeController.signal)
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
        if (ready !== host.ready || !channel) throw lost;
        const id = ++nextId;
        return new Promise((resolve, reject) => {
          pending.set(id, { resolve, reject });
          channel.postMessage({ id, method, detail });
        });
      });
    },
    on(type, callback) {
      if (!listeners.has(type)) listeners.set(type, /* @__PURE__ */ new Set());
      listeners.get(type).add(callback);
      return () => listeners.get(type).delete(callback);
    },
    dress: (dress) => channel?.postMessage({ type: "dress", detail: dress }),
    showThread(id, { signal, ...options }) {
      if (signal.aborted) return Promise.resolve(false);
      const cancel = () => channel?.postMessage({ type: "cancel-view" });
      signal.addEventListener("abort", cancel, { once: true });
      return host.call("thread", { id, ...options }).finally(() => signal.removeEventListener("abort", cancel));
    },
    destroy() {
      if (closing) return closing;
      destroyed = true;
      record("destroyed");
      lifetimeController.abort(new DOMException("sample destroyed", "AbortError"));
      mounted.delete(frame);
      window.removeEventListener("message", connect);
      frame.removeEventListener("load", loaded);
      window.removeEventListener("pagehide", departing);
      room();
      document.removeEventListener("visibilitychange", visibility);
      seen.disconnect();
      size.disconnect();
      admission.disconnect();
      for (const type of ["beforetoggle"])
        document.removeEventListener(type, nativeTransition, true);
      lifetime.disconnect();
      unwatch();
      undress();
      closing = Promise.all([retire("destroyed"), operation?.catch(() => {
      })]);
      return closing;
    }
  };
  const departing = (event) => {
    if (!event.persisted) void host.destroy();
  };
  window.addEventListener("pagehide", departing);
  mounted.set(frame, host);
  reset();
  return host;
}

export {
  isSampleFrame,
  sampleFrameImage,
  mountSample
};
