/* A sample owns a disposable served page in an opaque browsing context. Its
 * unguessable page URL grants native requests to its own document, assets and log;
 * presentation commands and observations cross a private port as values.
 * Allocation captures the owning widget's immutable revision and builds either its
 * named template or a supplied full HTML source. Both become ordinary validated
 * child pages; supplied source starts with an empty history. Reset replaces the
 * allocation, admitting its initial document with a credentialless HEAD before
 * native navigation. A later authored navigation keeps the frame and disables its
 * private port; an ordinary reload reconnects.
 * An opaque parent cannot classify a later document which has no Leaf bootstrap.
 * Departed ports cannot settle the replacement's calls.
 * `ready` is the usable, upgraded interface of the sample's next document,
 * independent of its authoritative saved-state reading. When the child
 * document departs, through an authored navigation or a reload, `ready` becomes one
 * promise for the document a reload upgrades next, which announces itself with
 * `loading`. A call made meanwhile waits on it, and whatever the owner applied to the
 * departed document it applies again once it resolves. Nothing follows an external
 * destination, so that wait lasts until the owner resets or destroys the host.
 * `ready` and calls reject with `AbortError` only when the owner cancels them that
 * way, and with the next document's failure when it fails to start. A call the
 * departed document had not answered rejects with `SampleDepartedError`, since
 * commands belong to one document.
 * A block's frame takes its document's height, so the page around it scrolls the sample
 * like any other block; a window keeps its own viewport. A resize the reader did not ask
 * for waits while it would move what they see, the frame keeping its height
 * (records/thread/held-news.js, `heldGrowth`), until they look away. The reader asked for a
 * document's resizes where they saw the frame as its host mounted it, as when the page
 * arrives with it in view or a tab, a link or a jump brings it there, where they reset
 * it, and from their first click, key or typed character inside it, though not a wheel
 * or touch that scrolls past it. A document that reloads itself is again one they did
 * not ask for. The resize as a window becomes a block again is theirs too. The user
 * chose to fit a frame they bring into view to its page as soon as the page draws, over
 * keeping its placeholder height until they look away or click into it, which left a
 * short page standing in a blank frame. Where the reader saw the frame as it
 * mounted, something showed it to them: the page's presentation, or a gesture whose
 * rendering brought it into view. That showing waits (`landed`) until the first
 * document is usable or has failed, or until the reader looks away. Once they look
 * away the fit moves nothing they see, and in Chromium a document whose arrival waits
 * on a rendering gets none while its frame is off screen (notes/browser-support.md, "A
 * sample's page out of view in Chromium"), so without that end a reader who scrolled
 * past the frame as it loaded would hold the page until they came back.
 * A reading step the child's scroll chain spent goes on from the frame here, as the
 * wheel's scroll chains out of a frame (panel/navigation.js, `stepAlong`).
 * Removing a frame retires its realm before releasing the allocation, including on
 * reset and parent departure. Destruction cancels pending admission and queue
 * waits; an allocation already in flight is allowed to finish so its returned
 * capability can be released. Lifecycle records enter the interaction stream at
 * these decisions, with a host/allocation identity and the connected document
 * nonce. Native load is distinct from Leaf upgrade;
 * an opaque destination cannot be classified from its load event. Retirement
 * records the local realm's destruction, before the allocation release answers.
 * The page counts each document the frame loads, on mount, Reset or a reload, as
 * arriving: its presentation and then whatever it deferred, the samples it started
 * included. An allocation counts from when it begins until its frame loads, wherever
 * the frame stands, since loading needs no rendering. What a block's document does
 * after counts wherever the frame stands too, until the document reports its arrival,
 * fails or departs, since the frame takes the document's height as it arrives
 * (sample-child.js), which moves this page's boxes on screen or off. That part may wait
 * on a rendering, which a frame off screen or in a closed disclosure may not get
 * (base/rendering.js; notes/browser-support.md, "A sample's page out of view in Chromium"):
 * a chart sized by its first layout waits, and so does the upgrade of the widget layer
 * holding it. A deadline caps that wait (`SIZING_MS`). Past it, once a check has asked
 * for all near work (`nearWork`), and for a window from the start, whose frame keeps
 * its height whatever its document does, the page counts that part until the
 * browser's first reading of the frame, and after that only while the browser renders
 * the frame (`rendered`), as rendering readiness reads such a document as settled;
 * meanwhile the frame carries `data-lf-unseen`. Counting it wherever the frame stands
 * with no cap would keep a page with a chart in a sample below the window arriving for
 * as long as it stays open; a check that reads every document brings each
 * `data-lf-unseen` frame into view instead (render_checks.py, `start_near_work`), so
 * once it has asked, the wait for a block's height would only delay it.
 * A reload's document counts once it connects;
 * the parent cannot tell its departure from one to a page outside Leaf, whose load can
 * land before the departure's notice, so nothing counts between. Work a child starts
 * after it has arrived, such as one of its own samples' Reset or the near work a check
 * asks for (`nearWork`), is the child's to count.
 * A mounted frame answers for its image: the child draws the requested part of its
 * viewport, which an image of the containing page puts in the frame's place.
 * The frame's sandbox admits scripts, forms, popups that escape it, modals, downloads
 * and pointer lock, but not the same origin: the child's origin is opaque, so neither
 * document reaches the other's DOM, storage or runtime, and the child's requests to
 * other servers follow opaque-origin CORS. Native focus and reveal calls an authored
 * script makes keep their browser behavior; Leaf's own placements are skipped unless
 * the child holds focus (dom/focus.js, `canPlaceFocus`), and its reveals stay within its
 * document. Child-capability responses carry `Referrer-Policy: no-referrer` (http.py,
 * `_sample_headers`). The frame delegates no permission policy, so the browser refuses
 * the child's clipboard writes and its copy controls fall back as on any page whose
 * clipboard refuses. The user chose this over delegating
 * `clipboard-write`, which would let any script an author puts in a sample write the
 * user's clipboard on a press. A failed allocation or admission retires the
 * allocation before `ready` rejects. */
import { RequestError, requestJson } from "../transport/layer-client.js";
import { pageUrl, runtime } from "../state/context.js";
import { dressFor, registerSampleDress } from "../dom/dress.js";
import { widgetDescriptor } from "../records/widget-descriptors.js";
import {
  frameView,
  growthIsSeen,
  layoutWindow,
  presented,
  watchRoom,
  whenNone,
} from "../dom/geometry.js";
import { heldGrowth } from "../records/thread/held-news.js";
import {
  frameVisibility,
  onFrameVisibility,
  readSampleVisibility,
  watchFrame,
} from "../base/frame-visibility.js";
import { keeps } from "../lib/keeps.js";
import { inputInFrame } from "../dom/focus.js";
import { move } from "../dom/dom-move.js";
import { cancelRender, nextRender, sizeObserver } from "../lib/frame-pass.js";
import { recordInteraction } from "../transport/interaction-log.js";
import { exceptionRecord } from "../lib/exception.js";
import { aborted } from "../base/abort.js";
import { deferredArrival, onAllNear } from "../readings/presentation.js";
import type {
  ChildMessage,
  SampleCall,
  SampleCommands,
  SampleCrop,
  SampleId,
  SampleListeners,
  SampleMethod,
  SampleNotices,
  SampleReady,
  SampleResult,
} from "../base/sample-protocol.js";
import type { ServedSampleAnswer } from "../../types/contract.js";

type SampleHost = {
  ready: Promise<SampleReady>;
  reset: () => Promise<SampleReady>;
  setWindow: (value: boolean) => Promise<SampleCommands["window"]["result"]>;
  on: <K extends keyof SampleNotices>(
    type: K,
    callback: (detail: SampleNotices[K]) => unknown,
  ) => () => void;
  restoreCurrentLocation: () => Promise<boolean>;
  showThread: (
    id: string,
    options: { signal: AbortSignal; surface?: "page" | "panel" },
  ) => Promise<boolean>;
  destroy: () => Promise<unknown>;
};
type SampleRecordDetail = {
  reloading?: boolean;
  operation?: "release";
  status?: number;
  leafDocument?: string | null;
  reason?: string;
  document?: string | null;
  sample?: string | null;
  error?: ReturnType<typeof exceptionRecord> & { status?: number; body?: unknown };
};
// A page can carry many samples. Their child documents each import the runtime;
// upgrading them together can exhaust the browser's request pool before any child
// finishes loading its module graph. Bound simultaneous loads across this page. A
// loaded child can keep reading slow state without holding up the next sample.
const MAX_LOADING_SAMPLES = 3;
// How long a block's document counts while it arrives out of view (header). It caps
// how long a reader of this page waits on a sample whose page waits on a rendering, and
// is ten times the longest arrival off screen on a loaded machine, so a sample page
// that will arrive does so within it.
const SIZING_MS = 20_000;
let loadingSamples = 0;
const loadWaiters: (() => void)[] = [];
let nextHost = 0;
async function loadWithinLimit<T>(
  work: (release: () => void) => T | PromiseLike<T>,
  signal: AbortSignal,
) {
  signal.throwIfAborted();
  if (loadingSamples === MAX_LOADING_SAMPLES) {
    const { promise: turn, resolve: proceed }: PromiseWithResolvers<void> =
      Promise.withResolvers();
    loadWaiters.push(proceed);
    await Promise.race([turn, aborted(signal)]);
    // A slot handed over before the abort is this load's to run and release.
    const place = loadWaiters.indexOf(proceed);
    if (place !== -1) {
      loadWaiters.splice(place, 1);
      throw signal.reason;
    }
  } else loadingSamples++;
  let released = false;
  const release = () => {
    if (released) return;
    released = true;
    const next = loadWaiters.shift();
    if (next) next();
    else loadingSamples--;
  };
  try {
    return await work(release);
  } finally {
    release();
  }
}

// The child document left before answering a call.
const departure = (message: string) => new DOMException(message, "SampleDepartedError");

const mounted = new Map<Node, SampleCall>();
export const isSampleFrame = (node: Node): node is HTMLIFrameElement =>
  mounted.has(node);
// A crop in the frame's viewport coordinates.
export function sampleFrameImage(frame: HTMLIFrameElement, crop: SampleCrop) {
  const call = mounted.get(frame);
  if (!call) throw departure("Sample frame has departed");
  return call("image", crop);
}

const request = <T>(
  url: string | URL,
  body: object,
  headers: Record<string, string> = {},
) =>
  requestJson<T>(
    String(url),
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
      keepalive: true,
    },
    "sample",
  );

function connectionMessage(
  value: unknown,
): value is { type: "leaf-sample-connect"; sample: string; nonce: string } {
  return (
    value !== null &&
    typeof value === "object" &&
    "type" in value &&
    value.type === "leaf-sample-connect" &&
    "sample" in value &&
    typeof value.sample === "string" &&
    "nonce" in value &&
    typeof value.nonce === "string"
  );
}

// `landed` is given where the reader saw the frame as its host mounted it, and is called
// once what showed it to them need wait no longer (header).
export function mountSample(
  frame: HTMLIFrameElement,
  {
    template,
    source,
    window: asWindow = false,
  }: ({ template: string; source?: never } | { source: string; template?: never }) & {
    window?: boolean;
  },
  landed: (() => void) | null = null,
): SampleHost {
  if ((template == null) === (source == null))
    throw new Error("a sample needs either an authored template id or source document");
  // A template is declared in its revision's document or in a message's
  // markup, which the server reads from the log beside the current revision.
  let revision = runtime.currentRevision;
  let message: string | undefined;
  for (let owner = frame.parentElement; owner; owner = owner.parentElement) {
    const descriptor = widgetDescriptor(owner);
    if (!descriptor) continue;
    if (descriptor.document.kind === "page") revision = descriptor.document.revision;
    else if (source == null) message = descriptor.document.message;
    break;
  }
  let current: string | null = null;
  let samplePage: string | null = null;
  let destroyed = false;
  // Asked again after each wait a load makes, during which `destroy` can run.
  const isDestroyed = () => destroyed;
  let operation: Promise<SampleReady> | null = null;
  let closing: Promise<unknown> | null = null;
  let channel: MessagePort | null = null;
  // Why the last channel closed: what a call aimed at its document rejects with.
  let lost: unknown;
  let nextId = 0;
  let pendingInterface: PromiseWithResolvers<SampleReady> | null = null;
  let hasConnected = false;
  let connectedNonce: string | null = null;
  const hostId = ++nextHost;
  const started = performance.now();
  let allocation = 0;
  const record = (phase: string, detail: SampleRecordDetail = {}) =>
    recordInteraction("sample", {
      host: hostId,
      template,
      revision,
      allocation,
      sample: samplePage,
      document: connectedNonce,
      elapsed: performance.now() - started,
      phase,
      ...detail,
    });
  const recordFailure = (error: unknown, detail: SampleRecordDetail = {}) =>
    record("failed", {
      error: {
        ...exceptionRecord(error),
        ...(error instanceof RequestError && {
          status: error.status,
          body: error.body,
        }),
      },
      ...detail,
    });
  const lifetimeController = new AbortController();
  const candidates = new Set<MessagePort>();
  const pending: Map<
    SampleId,
    Pick<PromiseWithResolvers<SampleResult>, "resolve" | "reject">
  > = new Map();
  const listeners: SampleListeners = {
    input: new Set(),
    "current-location": new Set(),
    loading: new Set(),
    departed: new Set(),
  };
  const notify = <K extends keyof SampleNotices>(type: K, detail: SampleNotices[K]) => {
    for (const callback of listeners[type]) callback(detail);
  };
  keeps(
    frame,
    "sandbox",
    "allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals allow-downloads allow-pointer-lock",
  );
  frame.toggleAttribute("data-lf-contained", true);

  // The block height the current document last reported, whether the reader asked for
  // that document's resizes, and the step that drops a resize waiting on them (header).
  let height: number | undefined;
  let theirs = landed !== null;
  let dropHeld: (() => void) | null = null;
  const fit = () => {
    frame.style.height = `${height}px`;
  };
  let fitting = 0;
  const fitNextRender = () => {
    fitting ||= nextRender(() => {
      fitting = 0;
      fit();
    });
  };
  // Take `reading` as the frame's height: at the page's next rendering, or now where
  // `immediate`. A resize the reader `asked` for applies whoever asked for the
  // document. A window's frame keeps its height, and its readings go unrecorded.
  function resize(reading: number, { immediate = false, asked = false } = {}) {
    if (asWindow) return;
    height = reading;
    dropHeld?.();
    dropHeld = null;
    const apply = immediate ? fit : fitNextRender;
    if (theirs || asked) apply();
    else dropHeld = heldGrowth(frame, apply);
  }
  // The reader's click or key inside the document makes the frame theirs to move: a
  // resize held while they read applies now, and so does each later one.
  function claim() {
    theirs = true;
    if (!dropHeld) return;
    dropHeld();
    dropHeld = null;
    fit();
  }
  let stopLooking: (() => void) | null = null;
  function land() {
    landed?.();
    landed = null;
    stopLooking?.();
    stopLooking = null;
  }
  if (landed) stopLooking = whenNone([frame], growthIsSeen, land);

  // Whether this page shows, and so renders what it holds.
  function pageShows() {
    return (
      document.visibilityState === "visible" && frameVisibility()?.visible !== false
    );
  }
  // Whether the browser renders the frame: on screen (base/frame-visibility.js) in a page
  // that itself shows.
  function rendered() {
    return pageShows() && seen.shown();
  }
  // Whether the user can see the frame and read what it shows: rendered, and admitted
  // by this page.
  function admitted() {
    return rendered() && presented(frame);
  }
  function visibility() {
    channel?.postMessage({ type: "visibility", detail: { visible: admitted() } });
    arrive();
  }
  // Where the frame's document stands in its arrival: `loading` from an allocation
  // until its frame loads, and `drawing` from then or from a reload's connection until
  // it reports its arrival or departs. `loading` counts wherever the frame stands;
  // `drawing` counts while this page shows, for a block wherever the frame stands
  // until its deadline or a check's ask for near work, and otherwise until the
  // browser's first reading of the frame and then only while `rendered`.
  type Arriving = "loading" | "drawing" | null;
  let arriving: Arriving = null;
  let counted: (() => void) | null = null;
  // A block's deadline for its document's arrival out of view (`SIZING_MS`).
  let sizing: ReturnType<typeof setTimeout> | undefined;
  let overdue = false;
  function arrive(stage: Arriving = arriving) {
    arriving = stage;
    const heightOwed = stage === "drawing" && !asWindow && !near.asked();
    if (!heightOwed) {
      clearTimeout(sizing);
      sizing = undefined;
      overdue = false;
    } else
      sizing ??= setTimeout(() => {
        overdue = true;
        arrive();
      }, SIZING_MS);
    const counts =
      stage === "loading" ||
      (stage === "drawing" &&
        pageShows() &&
        ((heightOwed && !overdue) || !seen.read() || seen.shown()));
    frame.toggleAttribute("data-lf-unseen", stage === "drawing" && !counts);
    if (counts && !counted) {
      const { promise, resolve } = Promise.withResolvers();
      counted = () => resolve(undefined);
      deferredArrival(promise);
    } else if (!counts && counted) {
      counted();
      counted = null;
    }
  }
  function moveOn(from: Arriving, to: Arriving) {
    if (arriving === from) arrive(to);
  }
  async function readVisibility(port: MessagePort, id: number) {
    try {
      const outer = await readSampleVisibility();
      if (channel !== port) return;
      const within = outer ? outer.visible && outer : layoutWindow();
      const view = admitted() && within && frameView(frame, within);
      port.postMessage({
        type: "visibility-reading",
        detail: { id, visible: Boolean(view), ...view },
      });
    } catch (error) {
      if (channel !== port) return;
      port.postMessage({
        type: "visibility-reading",
        detail: {
          id,
          error: exceptionRecord(error),
        },
      });
      reportError(error);
    }
  }
  function disconnect(reason: unknown) {
    moveOn("drawing", null);
    channel?.close();
    channel = null;
    lost = reason;
    connectedNonce = null;
    for (const { reject } of pending.values()) reject(reason);
    pending.clear();
  }
  // Public readiness includes failure retirement. Reset coalesces with an
  // allocation's own operation, so a reported failure already permits a fresh one.
  // A reload's upgrade, or a departure's wait, is not an operation: Reset then
  // allocates afresh.
  function begin(work: Promise<SampleReady>) {
    const active = work;
    operation = active;
    host.ready = active;
    const settled = () => {
      if (operation === active) operation = null;
    };
    active.then(settled, settled);
    return active;
  }
  async function settle<T>(work: PromiseLike<T>) {
    try {
      return await work;
    } catch (error) {
      // Reset and destroy retire allocations themselves.
      if (exceptionRecord(error).name !== "AbortError") {
        recordFailure(error);
        await retire("failure", error);
      }
      throw error;
    }
  }
  function interfaceReady() {
    const completion: PromiseWithResolvers<SampleReady> = Promise.withResolvers();
    pendingInterface = completion;
    return completion.promise;
  }
  // A departed or replaced document's successor upgrades into the readiness
  // already pending, so a departure and the reload after it share one `ready`.
  function awaitNext() {
    if (pendingInterface) return;
    host.ready = settle(interfaceReady());
    // Owners read its outcome from `ready`; a host nobody awaits drops it, as an
    // operation's does.
    host.ready.catch(() => {});
  }
  function failure(error: unknown) {
    if (pendingInterface) {
      const completion = pendingInterface;
      pendingInterface = null;
      completion.reject(error);
    } else {
      begin(settle(Promise.reject(error)));
      notify("loading", undefined);
    }
  }
  function connect(event: MessageEvent<unknown>) {
    const data = event.data;
    if (
      !current ||
      event.source !== frame.contentWindow ||
      !connectionMessage(data) ||
      data.sample !== new URL(current).pathname ||
      data.nonce === connectedNonce
    )
      return;
    const nonce = data.nonce;
    const owned = current;
    const pair = new MessageChannel();
    const port = pair.port1;
    // Publish this private document endpoint at the existing diagnostic seam.
    const entry: HTMLScriptElement | null = document.querySelector(
      "script[data-lf-entry]",
    );
    if (!entry) throw new Error("A sample host needs the Leaf bootstrap entry");
    entry.lfDocumentPort = port;
    candidates.add(port);
    port.onmessage = ({ data }: MessageEvent<ChildMessage>) => {
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
        if (arriving !== "loading") arrive("drawing");
        if (reloading) {
          theirs = false;
          awaitNext();
          notify("loading", undefined);
        }
        visibility();
        return;
      }
      // Messages from the departed realm cannot settle the next realm's calls.
      if (channel !== port) return;
      if (data.type === "departed") {
        record("departed");
        disconnect(departure("sample document navigated"));
        arrive(null);
        // Reset need not wait for a document that may never come.
        operation = null;
        awaitNext();
        notify("departed", undefined);
        return;
      }
      if (data.type === "visibility-read") {
        void readVisibility(port, data.detail.id);
        return;
      }
      if (data.type === undefined) {
        const completion = pending.get(data.id);
        if (!completion) return;
        const { resolve, reject } = completion;
        pending.delete(data.id);
        if (data.error)
          reject(
            Object.assign(
              new Error(data.error.message),
              { stack: undefined },
              data.error,
            ),
          );
        else resolve(data.result);
      } else if (data.type === "ready") {
        record("upgraded");
        const completion = pendingInterface;
        pendingInterface = null;
        completion?.resolve(data.detail);
        // The frame takes the height its document upgraded at in the turn the host
        // learns of it. One that upgraded as a window gives its block height as it
        // answers `setWindow`.
        if (data.detail.block) resize(data.detail.height, { immediate: true });
        visibility();
        nearWork();
      } else if (data.type === "error") {
        failure(
          Object.assign(
            new Error(data.detail.message),
            { stack: undefined },
            data.detail,
          ),
        );
      } else if (data.type === "return")
        frame.dispatchEvent(new Event("lf-sample-return"));
      else if (data.type === "step")
        frame.dispatchEvent(
          new CustomEvent("lf-sample-step", {
            bubbles: true,
            composed: true,
            detail: data.detail,
          }),
        );
      else if (data.type === "input") {
        const { type } = data.detail;
        inputInFrame(frame, type);
        if (type === "click" || type === "keydown" || type === "input") claim();
        notify("input", data.detail);
      } else if (data.type === "height") resize(data.detail.height);
      else if (data.type === "current-location")
        notify("current-location", data.detail);
      else if (data.type === "arrived") moveOn("drawing", null);
    };
    frame.contentWindow?.postMessage(
      {
        sample: data.sample,
        nonce,
        settings: { window: asWindow, dress: dressFor(frame) ?? undefined },
      },
      "*",
      [pair.port2],
    );
  }
  window.addEventListener("message", connect);
  const loaded = () => {
    if (!current || !frame.hasAttribute("src")) return;
    record("loaded");
    moveOn("loading", "drawing");
  };
  frame.addEventListener("load", loaded);
  const room = watchRoom(visibility);
  document.addEventListener("visibilitychange", visibility);
  const seen = watchFrame(frame, visibility);
  const size = sizeObserver(visibility);
  size.observe(frame);
  const nativeTransition = () => nextRender(visibility);
  document.addEventListener("beforetoggle", nativeTransition, true);
  const unwatch = onFrameVisibility(visibility);
  const undress = registerSampleDress(frame, (dress) =>
    channel?.postMessage({ type: "dress", detail: dress }),
  );
  const lifetime = new MutationObserver(() => {
    if (!frame.isConnected) void host.destroy();
  });
  lifetime.observe(document, { childList: true, subtree: true });

  // What a pending call rejects with: the failure that retires the allocation, or
  // else the owner's cancellation.
  function retire(
    reason: string,
    cause: unknown = new DOMException("sample replaced", "AbortError"),
  ) {
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
    const completion = pendingInterface;
    pendingInterface = null;
    completion?.reject(cause);
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
        sample,
      });
      throw error;
    });
  }
  async function replace() {
    arrive("loading");
    await retire("reset");
    allocation++;
    record("queued");
    const loading = loadWithinLimit(async (release) => {
      if (isDestroyed()) throw new DOMException("sample destroyed", "AbortError");
      record("allocating");
      const { url, page } = await request<ServedSampleAnswer>(
        pageUrl("api/samples"),
        { template, source, message },
        revision ? { "Leaf-View-Revision": String(revision) } : {},
      );
      current = new URL(url, location.href).href;
      samplePage = page;
      record("allocated");
      try {
        if (isDestroyed()) {
          await retire("destroyed");
          throw new DOMException("sample destroyed", "AbortError");
        }
        // The opaque frame cannot expose its document or order cross-process
        // bootstrap messages against load. Admit the server's document contract
        // before native navigation; later authored destinations remain native.
        const admission = await fetch(current, {
          method: "HEAD",
          credentials: "omit",
          signal: lifetimeController.signal,
        });
        record("admission", {
          status: admission.status,
          leafDocument: admission.headers.get("Leaf-Document"),
        });
        if (!admission.ok || !admission.headers.has("Leaf-Document"))
          throw new Error("The sample document did not start Leaf");
        if (isDestroyed()) {
          await retire("destroyed");
          throw new DOMException("sample destroyed", "AbortError");
        }
        const upgraded = interfaceReady();
        // A loaded module graph frees its slot even while Leaf upgrade waits on
        // widget preparation. Native load needs no access to the opaque child document.
        frame.addEventListener("load", release, { once: true });
        record("loading");
        frame.src = current;
        return await upgraded;
      } finally {
        frame.removeEventListener("load", release);
      }
    }, lifetimeController.signal);
    // A document that upgrades before its frame's load event draws from then.
    loading.then(
      () => moveOn("loading", "drawing"),
      () => moveOn("loading", null),
    );
    return settle(loading);
  }
  function reset() {
    if (destroyed)
      return Promise.reject(new Error("the sample host has been destroyed"));
    theirs = true;
    return operation ?? begin(replace());
  }
  function call<K extends SampleMethod>(
    method: K,
    detail: SampleCommands[K]["detail"],
  ): Promise<SampleCommands[K]["result"]>;
  function call(
    method: SampleMethod,
    detail: SampleCommands[SampleMethod]["detail"],
  ): Promise<SampleResult> {
    const ready = host.ready;
    return ready.then(() => {
      if (ready !== host.ready || !channel) throw lost;
      const port = channel;
      const id = ++nextId;
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
        port.postMessage({ id, method, detail });
      });
    });
  }
  // A check that asks this page for all the work it holds until the reader comes near
  // (readings/presentation.js, `startNearWork`) asks each upgraded child document the same, once,
  // and counts the child as arriving until it has started that work. The check waits
  // for each document itself (render_checks.py, `start_near_work`).
  let askedNear: string | null = null;
  function nearWork() {
    if (!near.asked() || !channel || pendingInterface || askedNear === connectedNonce)
      return;
    askedNear = connectedNonce;
    deferredArrival(call("near-work", {}).catch(() => {}));
  }
  const near = onAllNear(() => {
    nearWork();
    arrive();
  });
  const host: SampleHost = {
    ready: replace(),
    reset,
    // Full view keeps the realm, log and native editor; only its allocation changes.
    // A frame that becomes a block again takes the height it last had as one, at once,
    // and then the height its document answers with.
    setWindow(value) {
      const returning = asWindow && !value;
      asWindow = value;
      arrive();
      if (returning && height !== undefined)
        resize(height, { immediate: true, asked: true });
      return call("window", { window: value }).then((reading) => {
        resize(reading.height, { asked: true });
        return reading;
      });
    },
    on(type, callback) {
      const callbacks = listeners[type];
      callbacks.add(callback);
      return () => {
        callbacks.delete(callback);
      };
    },
    restoreCurrentLocation: () => call("restore-current-location", {}),
    showThread(id, { signal, ...options }) {
      if (signal.aborted) return Promise.resolve(false);
      const cancel = () => channel?.postMessage({ type: "cancel-view" });
      signal.addEventListener("abort", cancel, { once: true });
      return call("thread", { id, ...options }).finally(() =>
        signal.removeEventListener("abort", cancel),
      );
    },
    destroy() {
      if (closing) return closing;
      destroyed = true;
      arrive(null);
      dropHeld?.();
      cancelRender(fitting);
      land();
      record("destroyed");
      lifetimeController.abort(new DOMException("sample destroyed", "AbortError"));
      mounted.delete(frame);
      window.removeEventListener("message", connect);
      frame.removeEventListener("load", loaded);
      window.removeEventListener("pagehide", departing);
      room();
      document.removeEventListener("visibilitychange", visibility);
      seen.stop();
      size.disconnect();
      document.removeEventListener("beforetoggle", nativeTransition, true);
      lifetime.disconnect();
      unwatch();
      undress();
      near.stop();
      closing = Promise.all([retire("destroyed"), operation?.catch(() => {})]);
      return closing;
    },
  };
  const departing = (event: PageTransitionEvent) => {
    if (!event.persisted) void host.destroy();
  };
  window.addEventListener("pagehide", departing);
  mounted.set(frame, call);
  begin(host.ready).then(land, land);
  return host;
}
