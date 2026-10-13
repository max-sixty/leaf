/* Shared mechanical runtime context: which address this document is and how a server
   delivered it, the interactive export's payload, and read-only views of the semantic
   root. Accepted facts are never installed here independently of application
   publication. */
import { readApplication } from "./semantic-state.js";

// ---------- which address this document is ----------
// Which version a document is comes from its served `lf-version` marker
// (`document-identity.js`), and where another version is from that version's `url` in
// the state reading, which the server addresses at the page root. Neither is read off
// this path.
const PAGE_PATH = location.pathname;
// The live root follows the active revision in place; a virtual version address
// (`versions/vN.html`) stays pinned to its mapped revision.
export const LIVE_ROOT = PAGE_PATH.endsWith("/");
// Which page this document belongs to. The server declares the page's root in the
// canonical link it adds to every document it serves, the live root and each version
// address alike, and every page operation resolves against it. An interactive export
// has no server and no link, so no root: the file is the page.
export const PAGE_ROOT =
  document.querySelector('link[rel="canonical"][data-lf-runtime]')?.href ?? null;
// How a server delivered this document: the runtime script it adds to every document it
// serves (http.py) names the layer and release the document belongs to, the probe its
// source answers, and a keyed transport's share address. An interactive export carries
// no such script. Its own marker (`offlineMarker` below) shares only `data-lf-entry`, the
// seam a harness finds either delivery by.
const served = document.querySelector(
  "script[data-lf-runtime][data-lf-server]",
)?.dataset;
export const DELIVERY = Object.freeze({
  layer: served?.lfLayer,
  release: served?.lfRelease,
  probe: served?.lfProbe,
});
// The public website declares the release it serves; a local server declares none.
export const WEBSITE_DELIVERY = DELIVERY.release !== undefined;
// Where a delivered document's captured layer is addressed. The entry names the
// immutable revision; the registry probe may instead name the mutable page root so
// startup can detect a newer layer. Empty where nothing declared an entry.
export const layerRoot = (doc) =>
  doc
    .querySelector("script[data-lf-runtime][data-lf-entry]")
    ?.dataset.lfEntry.replace(/leaf\.js$/, "") ?? "";
// A keyed transport declares its share address even on a cookie-authorized reload.
// Samples and the public website have no share address. Preserve the current
// version path, query and passage while taking access from the transport's URL.
export const SHARE_ROOT = served?.lfShareUrl;
export function shareUrl() {
  const url = new URL(SHARE_ROOT);
  url.pathname = location.pathname;
  const access = [...url.searchParams];
  url.search = location.search;
  for (const [key, value] of access) url.searchParams.set(key, value);
  url.hash = location.hash;
  return url.href;
}

// Code may be shared by several documents, including a sample and its parent.
// Page operations belong to the document's declared root, never to the module's asset
// URL.
export const pageUrl = (path) => new URL(path, PAGE_ROOT).href;

const offlineMarker = document.querySelector(
  'script[type="application/json"][data-lf-runtime][data-lf-offline]',
);
const offlinePayload = offlineMarker
  ? JSON.parse(offlineMarker.textContent || "null")
  : null;
// This declaration participates in executable identity: changing it replaces this
// document realm rather than switching initialized physical owners in place.
export const annotationMode =
  document.body.getAttribute("data-annotations") ?? "overlay";

export const offlineInteractive = offlinePayload !== null;
export const offlineState = () =>
  offlineInteractive ? structuredClone(offlinePayload.state) : null;
// The fragment reader never mutates this captured authority. Keep one in-memory copy:
// cloning a multi-megabyte split source for each opened file would defeat fragmentation.
export const offlineData = () => (offlineInteractive ? offlinePayload.data : null);
export const runtimeModule = (path) =>
  offlineInteractive ? `leaf:${path.startsWith("/") ? path : `/${path}`}` : path;
// A layer file by its rooted path in the page directory (`/icon.svg`,
// `/widgets/lf-tabs.js`), at the address this document's layer is served from
// (`layerRoot`); a document nothing declared one for takes the layer at its own root.
const servedLayerRoot = layerRoot(document);
export const runtimeResource = (path) => {
  if (!offlineInteractive)
    return servedLayerRoot
      ? new URL(`.${path}`, new URL(servedLayerRoot, document.baseURI)).href
      : path;
  const located = new URL(path, document.baseURI);
  const resource = offlinePayload.resources[located.pathname];
  if (typeof resource !== "string")
    throw new Error(`Leaf's interactive export is missing ${path}`);
  // A resource query does not change captured bytes; fragments retain native URL
  // meaning (for example an SVG symbol or a recording's start time).
  return resource + located.hash;
};

export const runtime = {
  get active() {
    return readApplication().authoritative?.active ?? null;
  },
  get browser() {
    return readApplication().authoritative?.browser ?? null;
  },
  // Whether the document shows the active revision. Activation only moves forward
  // (the publisher refuses an answer whose active revision went back), so a document
  // showing any other revision is behind it: an older pin, or a tab the agent has
  // since revised.
  get showsActive() {
    return (
      runtime.active !== null && runtime.currentRevision === runtime.active.revision
    );
  },
  get currentLabel() {
    return readApplication().document.live && runtime.showsActive
      ? runtime.active.label
      : runtime.currentStamp === null
        ? null
        : `v${runtime.currentStamp}`;
  },
  get currentRevision() {
    return readApplication().document.revision;
  },
  get currentStamp() {
    return readApplication().document.live && runtime.showsActive
      ? runtime.active.version
      : (readApplication().document.stamp ?? null);
  },
  get data() {
    return readApplication().data;
  },
  get lastEventSeq() {
    return readApplication().authoritative?.browser.basis.through_seq ?? null;
  },
  get reading() {
    return readApplication().authoritative?.reading ?? null;
  },
  sessionReference: null,
  // Whether the server's latest answer refused this tab's key (`layer-client.js`).
  keyRefused: false,
  get state() {
    return readApplication().authoritative;
  },
  registry: {},
  get statePhase() {
    return readApplication().phase;
  },
  get versions() {
    return readApplication().authoritative?.versions ?? [];
  },
  get workflows() {
    return readApplication().effective.workflows;
  },
  // The shown revision's server view, less its basis, as the publisher resolved it.
  get view() {
    return readApplication().effective.view;
  },
};

export const revisionLabel = (revision) => runtime.state.revision_labels[revision];
