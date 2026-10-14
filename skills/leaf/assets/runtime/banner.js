/* This module paints the banner's status in the words activity-words.js gives it,
 * paints its tone on the tab icon, and announces changes after the first status
 * reading. Provisional interface readiness paints the banner
 * without establishing that announcement baseline; saved state or a failed read does. */
import { html, nothing, render } from "/vendor/browser-runtime.js";
import { ago } from "./presence.js";
import { pageStatus, statusModel } from "./activity-words.js";
import { el, offer } from "./widget-elements.js";
import { keeps, keepsText } from "./keeps.js";
import { SHARE_ROOT, runtime, runtimeResource, shareUrl } from "./context.js";
import {
  BANNER_CONTROL_RANK,
  bannerActions,
  markBannerControl,
  overflowMenu,
  registerBannerControl,
  showBannerControl,
  showNews,
} from "./banner-toolbar.js";
import { iconElement } from "./icons.js";
import { copyControl } from "./copy-control.js";
import { latestChip, versionBtn } from "./version-picker.js";
import { versionsReading } from "./version.js";
import { othersBtn, queueBtn } from "./drawers.js";
import { pagePresented } from "./page-paint.js";
import { repaint } from "./repaint.js";
import { sizeObserver } from "./rendering.js";
import {
  announce,
  notice,
  noticeReading,
  registerNoticePresentation,
} from "./notifications.js";
import { watchProjection } from "./projection-watch.js";
import { createBannerStatusView } from "./banner-status-view.js";
import { declareBanner } from "./geometry.js";
import { agentName, readPart } from "./semantic-state.js";
import { UPGRADE } from "./presentation.js";
import { WEBSITE_DELIVERY } from "./context.js";
import { readQueues } from "./queue-api.js";
import { approvalBlockingAsks } from "./asks/model.js";
import { focusDestination, tabStops } from "./focus.js";

const INITIAL = Object.freeze({
  tone: "",
  summary: "Loading…",
  queues: "",
  queuesWidest: "",
  explanation:
    "Loading the page's interface. Reading, links, and scrolling are already available.",
  publication: null,
});

export const banner = el("header", "lf-ui lf-banner");
banner.id = "lf-banner";
declareBanner(banner);
// Where Leaf's controls begin in this chrome, as the page's Skip to Leaf controls finds
// them: the banner's first control that takes focus, or the banner itself.
export function enterBanner() {
  for (const control of tabStops(banner)) {
    focusDestination(control, "move");
    if (control.matches(":focus")) return;
  }
  focusDestination(banner, "move");
}
const bannerStatus = createBannerStatusView(repaint, INITIAL);
registerNoticePresentation(() => bannerStatus.presentNotice(noticeReading()));
// The agent's On count, which opens the On panel on the agent's list (queue-panel.js).
export const queueCounts = bannerStatus.queues;

// Threads reads "Threads: 3" on a desk and, on a phone's one row, a thread icon with its
// count, which chrome.css draws from `data-lf-count`; the accessible name is the same
// words on both. The desk's words stay one run of text, so they draw as they always have.
export const toggleBtn = el("button", "lf-btn lf-auxiliary-toggle lf-threads-toggle");
const threadsLabel = el("span", "lf-threads-label");
threadsLabel.dataset.lfRoom = "Threads\nThreads: 999";
const threadsWords = el("span", "", "Threads");
threadsLabel.append(threadsWords);
toggleBtn.append(iconElement("comment", "lf-threads-icon"), threadsLabel);
toggleBtn.title = "Show or hide the thread panel";
toggleBtn.setAttribute("aria-expanded", "false");
let openThreads = null;
let unreadThreads = 0;
function paintThreadCounts() {
  const label = openThreads === null ? "Threads" : `Threads: ${openThreads}`;
  const accessible = openThreads === null ? "Threads" : `Open threads: ${openThreads}`;
  keepsText(threadsWords, label);
  keeps(toggleBtn, "data-lf-count", openThreads === null ? null : String(openThreads));
  toggleBtn.toggleAttribute("data-unread-threads", unreadThreads > 0);
  const unread = unreadThreads
    ? `${unreadThreads} unread ${unreadThreads === 1 ? "thread" : "threads"}`
    : null;
  keeps(toggleBtn, "aria-label", unread ? `${accessible}, ${unread}` : accessible);
  keeps(
    toggleBtn,
    "data-lf-key-title",
    unread
      ? `Show or hide the thread panel; ${unread}`
      : "Show or hide the thread panel",
  );
}
// Both counts come from the one thread-list reading, so they are painted together.
export function setThreadCounts(open, unread) {
  openThreads = open;
  unreadThreads = unread;
  paintThreadCounts();
}
// The primary controls hold the room of the widest words they can show, so an
// asynchronous count or approval result cannot move a sibling. CSS bounds Approval's
// room when the complete words cannot fit. Secondary controls can grow inside More
// without changing the page's reading loop.
const approveBtn = el("button", "lf-btn primary lf-signoff");
approveBtn.id = "lf-approve";
const approveRoom = el("span");
approveRoom.dataset.lfRoom = "Approve version\n✓ Version approved";
const approveWords = el("span");
approveRoom.append(approveWords);
approveBtn.append(approveRoom);
// Another chrome that presents the approval in this control's place, as the floating
// panel's On view does, names the control it shows and brings the user to it.
let approvalPresentation = null;
export function registerApprovalPresentation(presentation) {
  approvalPresentation = presentation;
}
export const presentedApproval = () => approvalPresentation;
// The queue arrives at the one approval control shown, including the banner's overflow
// seat.
export const approvalTarget = () =>
  signoff ? (approvalPresentation ? approvalPresentation.target() : approveBtn) : null;
approveBtn.title = "Approve this work; the page stays open for follow-up";
// The page's decision is not actionable until the page itself is present. Discussion chrome
// stays live during replay, but approving hidden authored content would decide a version
// the user has not seen yet. The control states that refusal from its first reading.
const AWAITING_STATE = "Approval waits until this page has read its current state";
// What Approval says and whether a press would approve, for another presentation of it,
// such as the floating panel's Versions view; null where the page asks no sign-off. It
// is derived each time it is read, so a paint reading it follows what it reads.
export const approvalReading = () => {
  if (!signoff) return null;
  const { text, reason } = approvalWords();
  return { text, reason };
};
// Keep a refused press focusable, with its reason available to keyboard and touch.
function presentApproval({ reason, text, title }) {
  render(text, approveWords);
  keeps(approveBtn, "aria-disabled", reason ? "true" : null);
  keeps(approveBtn, "aria-description", reason || null);
  keeps(approveBtn, "title", title);
}
presentApproval({
  reason: AWAITING_STATE,
  text: "Approve version",
  title: AWAITING_STATE,
});

// The toolbar owns this complete order from typed contributions rather than discovering
// or reconstructing it from whichever nodes happen to be in the row.
registerBannerControl({
  key: "leaves",
  control: othersBtn,
  rank: BANNER_CONTROL_RANK.leaves,
  conditional: true,
  row: { label: "All pages", group: "navigate" },
});
registerBannerControl({
  key: "latest",
  control: latestChip,
  rank: BANNER_CONTROL_RANK.latest,
  conditional: true,
  urgent: "new",
  row: { label: () => versionsReading().latest.label, group: "page" },
});
registerBannerControl({
  key: "queue",
  control: queueBtn,
  rank: BANNER_CONTROL_RANK.queue,
  seat: { desk: "row", phone: "menu" },
  row: {
    label: "On me",
    value: () => String(readQueues().on_user.length),
    group: "page",
  },
});
registerBannerControl({
  key: "versions",
  control: versionBtn,
  rank: BANNER_CONTROL_RANK.versions,
  row: {
    label: "Versions",
    value: () => versionsReading().picker.token,
    group: "page",
  },
});
registerBannerControl({
  key: "approval",
  control: approveBtn,
  rank: BANNER_CONTROL_RANK.approval,
  seat: { desk: "row", phone: "menu" },
  present: false,
  row: { label: () => approvalWords().text, group: "page", press: () => approve() },
});
registerBannerControl({
  key: "threads",
  control: toggleBtn,
  rank: BANNER_CONTROL_RANK.threads,
  seat: "row",
  row: {
    label: "Threads",
    value: () =>
      openThreads === null
        ? ""
        : `${openThreads}${unreadThreads ? ` · ${unreadThreads} new` : ""}`,
    group: "page",
  },
});

// ---------- banner ----------
// The judgment's third seat. A user keeps a leaf in a tab for days and looks at
// six of them; the tab strip is the whole of what the browser shows about a page nobody
// has open, so the state that decides whether to go there belongs in it. Same judgment
// (`activity`), same writer as the dot and the line, and the tone is taken off the dot
// itself rather than mapped from kind to token again — one answer to what a tone looks
// like, so a project overriding --ok overrides the tab with it and the two cannot come
// apart. It is a read of the theme, not of the rendering: what colour this tone paints
// as is a question nothing else can answer, where what state the page is in is already
// in hand.
//
// The mark is the vendored icon.svg — the page's own asset like the theme, so a project
// can put its own there — and all the runtime does to it is paint the one element it
// declares. Refused rather than defaulted: a mark with no lf-tone leaves a tab that
// never changes, which is a status readout that silently isn't one.
const tabLink = Object.assign(document.createElement("link"), {
  rel: "icon",
  type: "image/svg+xml",
  href: runtimeResource("/icon.svg"),
});
tabLink.dataset.lfRuntime = "";
document.head.append(tabLink);
let iconMark = null;
const iconUrls = new Map();
// The mark with one colour written over it. A style
// element appended last outranks the file's own rules, the dark-scheme block included,
// since a media query carries no specificity of its own. So this knows nothing about the
// icon beyond the class it promises, and a project's own mark is painted on the same
// terms.
function iconUrl(color) {
  let url = iconUrls.get(color);
  if (url === undefined) {
    const svg = iconMark.cloneNode(true);
    const style = svg.ownerDocument.createElementNS(
      "http://www.w3.org/2000/svg",
      "style",
    );
    style.textContent = `.lf-tone { fill: ${color} }`;
    svg.append(style);
    url =
      "data:image/svg+xml," +
      encodeURIComponent(new XMLSerializer().serializeToString(svg));
    iconUrls.set(color, url);
  }
  return url;
}
export async function loadIcon() {
  const response = await fetch(runtimeResource("/icon.svg"));
  if (!response.ok) throw new Error(`icon.svg answered ${response.status}`);
  const doc = new DOMParser().parseFromString(await response.text(), "image/svg+xml");
  // A package's replacement that is not SVG at all parses to an error document, which
  // has no lf-tone element either.
  if (!doc.querySelector(".lf-tone"))
    throw new Error(
      "icon.svg carries no lf-tone element, which is where the page's " +
        "status is painted",
    );
  iconMark = doc.documentElement;
  paintTab();
}
// A declaration, and called from two places, because the fetch above can land after the
// first poll has already judged the page.
function paintTab() {
  if (!iconMark) return;
  const url = iconUrl(getComputedStyle(bannerStatus.dot).backgroundColor);
  // Written only on change: an unchanged poll must not hand the browser its icon again
  // every two seconds.
  keeps(tabLink, "href", url);
}
// Summary and explanation share the canonical activity reading. The complete wording
// remains available to pointer, keyboard, and touch through the native disclosure;
// announcements report that explanation when the page kind changes or current work
// begins waiting for user input or approval, not on every observed work step or poll.
let saidKind;
let saidActionableWork;

// The queues are read from the application's publication rather than the state
// answer: a reply the user sends joins the agent's count in the turn it is sent,
// and leaves On me once the server has read it. A press on either opens the On
// panel on the list it counts (`statusModel` words them).
const presentStatus = ({ status, model }) => {
  const { kind, actionableWork = null } = status;
  bannerStatus.present(model);
  paintTab();
  // Interface readiness precedes the first saved reading. It paints usable chrome,
  // but only a state or failed read establishes the status announcement baseline.
  if (kind === "loading") return;
  const changed =
    saidKind !== undefined &&
    (saidKind !== kind ||
      (actionableWork !== null && actionableWork !== saidActionableWork));
  saidKind = kind;
  saidActionableWork = actionableWork;
  if (changed) announce(model.explanation);
};
// Upgrade opens new comments before the buffered saved reading is applied.
const LOADING_LINE =
  "The page is ready for reading and new comments. Saved comments and choices are still loading; new comments will be sent when the server responds." +
  (WEBSITE_DELIVERY
    ? " Website examples can take longer to load their saved state than a usual Leaf page."
    : "");
const LOADING = Object.freeze({
  kind: "loading",
  tone: "",
  summary: "Loading saved state…",
  explanation: LOADING_LINE,
  adds: LOADING_LINE,
});
// The developer preview's identity: which checkout is serving this page, and a press to
// copy the whole diagnostic. It is the banner's least-used control, so it stays behind
// the overflow door at every width instead of adding a permanent chip to the reading row.
function bannerCopy(trigger, success, error) {
  const copy = copyControl("lf-banner-copy", { success, error });
  copy.append(trigger);
  return copy;
}

if (SHARE_ROOT) {
  const details = el("details", "lf-share");
  const share = el("summary", "lf-btn", "Share");
  share.title = "Show this page's access link";
  const panel = el("div", "lf-share-panel");
  const grants = "Grants access to all Leaf pages on this machine.";
  const label = el("label", "", "Share link");
  const link = offer("input", "lf-share-link");
  link.id = "lf-share-link";
  link.type = "url";
  link.readOnly = true;
  link.addEventListener("focus", () => link.select());
  label.append(link);
  const copyButton = el("button", "lf-btn", "Copy link");
  copyButton.type = "button";
  const copy = bannerCopy(copyButton, "Link copied", "Select and copy the link above");
  copy.copyLabel = "Copy link";
  copy.hidden = !navigator.clipboard?.writeText;
  panel.append(el("p", "", grants), label, copy);
  details.append(share, panel);
  details.addEventListener("toggle", () => {
    if (details.open) link.value = copy.value = shareUrl();
  });
  overflowMenu.addEventListener("beforetoggle", (event) => {
    if (event.newState === "closed") details.open = false;
  });
  registerBannerControl({
    key: "share",
    control: details,
    focusTarget: share,
    rank: BANNER_CONTROL_RANK.share,
    // A presentation copies the link with its own copy control: a row of the page's own
    // menu with one press, or, where no clipboard is offered, beside the link to select.
    row: { label: "Link", value: grants, copies: shareUrl, group: "page" },
  });
}

// How old a Leaf payload is, so a user who meets a problem can tell whether it
// predates the fixes since. A payload read from Git carries its commit's date; a harness's
// plugin cache, which drops `.git`, carries the time it copied the commit, one update
// sweep after it landed (`layer.payload_provenance`).
const payloadAge = (provenance) => ago(provenance.committed ?? provenance.installed);
const payloadDateLines = (provenance) =>
  ["committed", "installed"]
    .filter((kind) => provenance[kind])
    .map((kind) => `${kind}: ${provenance[kind]}`);
// A payload's commit as the banner names it, `+` marking uncommitted changes.
const shortCommit = (provenance) =>
  provenance.commit
    ? `${provenance.commit.slice(0, 8)}${provenance.dirty ? "+" : ""}`
    : "unknown";
// Another payload's diagnostics, each line led by how it relates to the page.
const otherPayloadLines = (relation, provenance) => [
  ...(provenance.commit ? [`${relation} commit: ${provenance.commit}`] : []),
  ...(provenance.dirty !== undefined ? [`${relation} dirty: ${provenance.dirty}`] : []),
  ...payloadDateLines(provenance).map((line) => `${relation} ${line}`),
];

let previewMarginEntry = null;
let previewLabel = "";
let previewMarginEntryCopy = null;
let previewDiagnostics = "";
function renderPreview(state) {
  const preview = state.preview;
  if (!preview) return;
  const producer = state.layer.producer ?? {};
  // A user preview claims the page, so every press on it — the agent's own
  // screenshots included — comes back to the session as user input. That is the
  // mode worth marking; an unclaimed preview delivers nothing and needs no warning.
  const kind = preview.interaction === "user" ? "User" : "Preview";
  const stem = `${kind} · ${preview.checkout}${producer.commit ? `@${producer.commit}` : ""}`;
  const age = payloadAge(producer);
  // The preview names the checkout and the Leaf that vendored the page
  // (`state.layer.producer`). Where another Leaf serves it (`state.leaf`), that follows.
  const served = state.leaf
    ? ` · served by ${shortCommit(state.leaf)}${payloadAge(state.leaf) ? ` · ${payloadAge(state.leaf)}` : ""}`
    : "";
  const label = `${producer.commit && producer.dirty ? `${stem}+` : stem}${age ? ` · ${age}` : ""}${served}`;
  const safeUrl = new URL(location.href);
  safeUrl.searchParams.delete("t");
  previewDiagnostics = [
    "Leaf preview",
    `example: ${preview.example}`,
    `checkout: ${preview.checkout}`,
    `interaction: ${preview.interaction}`,
    ...(producer.commit ? [`commit: ${producer.commit}`] : []),
    ...(producer.dirty !== undefined ? [`dirty: ${producer.dirty}`] : []),
    ...payloadDateLines(producer),
    ...(state.leaf ? otherPayloadLines("served by", state.leaf) : []),
    `started: ${preview.started}`,
    `layer generation: ${state.layer.generation}`,
    ...(state.layer.fingerprint
      ? [`layer fingerprint: ${state.layer.fingerprint}`]
      : []),
    ...(state.active ? [`revision: ${state.active.revision}`] : []),
    `event sequence: ${state.events.at(-1)?.seq ?? 0}`,
    `url: ${safeUrl}`,
  ].join("\n");
  if (!previewMarginEntry) {
    previewMarginEntry = el("button", "lf-btn lf-preview", label);
    previewMarginEntry.type = "button";
    previewMarginEntry.setAttribute("aria-label", "Copy preview diagnostics");
    previewMarginEntryCopy = bannerCopy(
      previewMarginEntry,
      "Copied preview diagnostics",
      "Couldn't copy preview diagnostics",
    );
    previewMarginEntryCopy.copyLabel = "Copy preview diagnostics";
    registerBannerControl({
      key: "preview",
      control: previewMarginEntryCopy,
      focusTarget: previewMarginEntry,
      rank: BANNER_CONTROL_RANK.preview,
      // What it copies is the diagnostics, which a presentation shows to select as
      // well; the line naming the preview says what they describe.
      row: {
        label: "Preview diagnostics",
        value: () => previewLabel,
        copies: () => previewDiagnostics,
        group: "about",
      },
    });
  }
  previewMarginEntryCopy.value = previewDiagnostics;
  previewLabel = label;
  keepsText(previewMarginEntry, label);
  keeps(
    previewMarginEntry,
    "title",
    `${preview.example} · started ${preview.started} · copy diagnostics`,
  );
}

// The vendored layer is the Leaf version this page actually runs. It can remain older
// than the plugin now installed in the harness, so this reads the provenance captured by
// `page init` rather than a live package or server version. Pages built outside Git
// retain a stable identity through the composed layer fingerprint. Where another Leaf
// serves the page (`state.leaf`), it stands beside the page's own with its age, so
// whoever meets a problem can tell how far apart the two are (AGENTS.md, "Pages
// across Leaf updates").
let layerReferenceElement = null;
let layerNamed = "";
let layerReferenceElementCopy = null;
let layerDiagnostics = "";
function renderLayerReference(state) {
  if (state.preview) return;
  const producer = state.layer.producer ?? {};
  const fingerprint = state.layer.fingerprint;
  const fullIdentity = producer.commit
    ? `${producer.commit}${producer.dirty ? "+" : ""}`
    : fingerprint && `sha256:${fingerprint.replace(/^sha256:/, "").slice(0, 12)}`;
  if (!fullIdentity) return;
  const identity = producer.commit ? shortCommit(producer) : fullIdentity;
  const age = payloadAge(producer);
  const dateLines = payloadDateLines(producer);
  // Present only where the serving Leaf is another than the page's (`http.page_state`).
  const served = state.leaf;
  const serverIdentity = served && shortCommit(served);
  const serverAge = served && payloadAge(served);
  const serverLines = served ? otherPayloadLines("served by", served) : [];
  const safeUrl = new URL(location.href);
  safeUrl.searchParams.delete("t");
  layerDiagnostics = [
    "Leaf layer",
    ...(producer.commit ? [`commit: ${producer.commit}`] : []),
    ...(producer.dirty !== undefined ? [`dirty: ${producer.dirty}`] : []),
    ...dateLines,
    ...serverLines,
    ...(fingerprint ? [`fingerprint: ${fingerprint}`] : []),
    `generation: ${state.layer.generation}`,
    ...(state.active ? [`revision: ${state.active.revision}`] : []),
    `url: ${safeUrl}`,
  ].join("\n");
  if (!layerReferenceElement) {
    layerReferenceElement = el("button", "lf-btn lf-layer-reference");
    layerReferenceElement.type = "button";
    layerReferenceElementCopy = bannerCopy(
      layerReferenceElement,
      "Copied Leaf version",
      "Couldn't copy Leaf version",
    );
    registerBannerControl({
      key: "layer",
      control: layerReferenceElementCopy,
      focusTarget: layerReferenceElement,
      rank: BANNER_CONTROL_RANK.layer,
      row: {
        label: "Leaf version",
        value: () => layerNamed,
        copies: () => layerDiagnostics,
        group: "about",
      },
    });
  }
  layerReferenceElementCopy.value = layerDiagnostics;
  const servedBy = served
    ? ` · served by ${serverIdentity}${serverAge ? ` · ${serverAge}` : ""}`
    : "";
  const named = `Leaf ${identity}${age ? ` · ${age}` : ""}${servedBy}`;
  layerNamed = named;
  layerReferenceElementCopy.copyLabel = `${named} · copy version`;
  render(
    served
      ? // Two lines, each its own Leaf, since the menu is too narrow for both on one.
        html`<span class="lf-layer-line"
            >Leaf <code class="lf-layer-version">${identity}</code>${
              age ? ` · ${age}` : nothing
            }</span
          ><span class="lf-layer-line"
            >served by <code class="lf-layer-version">${serverIdentity}</code>${
              serverAge ? ` · ${serverAge}` : nothing
            }</span
          >`
      : html`Leaf <code class="lf-layer-version">${identity}</code>${
            age ? ` · ${age}` : nothing
          }`,
    layerReferenceElement,
  );
  keeps(
    layerReferenceElement,
    "title",
    [
      ...dateLines,
      ...serverLines,
      producer.dirty
        ? "+ means this layer includes uncommitted changes · copy diagnostics"
        : "Copy Leaf layer version and diagnostics",
    ].join("\n"),
  );
  keeps(layerReferenceElement, "aria-label", `${named} · copy version`);
}
// The public website support handle is available on demand with the banner's other
// low-frequency controls. It does not compete with the page's live status sentence.
let sessionReferenceElement = null;
let sessionReferenceElementCopy = null;
let sessionReferenceLabel = "";
function renderSessionReference() {
  const reference = runtime.sessionReference;
  if (!reference) return;
  sessionReferenceLabel = `Session ${reference}`;
  if (!sessionReferenceElement) {
    sessionReferenceElement = el(
      "button",
      "lf-btn lf-session-reference",
      sessionReferenceLabel,
    );
    sessionReferenceElement.type = "button";
    sessionReferenceElementCopy = bannerCopy(
      sessionReferenceElement,
      "Copied session reference",
      "Couldn't copy session reference",
    );
    registerBannerControl({
      key: "session",
      control: sessionReferenceElementCopy,
      focusTarget: sessionReferenceElement,
      rank: BANNER_CONTROL_RANK.session,
      row: {
        label: "Session reference",
        copies: () => runtime.sessionReference,
        group: "about",
      },
    });
  }
  sessionReferenceElementCopy.value = runtime.sessionReference;
  sessionReferenceElementCopy.copyLabel = `${sessionReferenceLabel} · copy reference`;
  keepsText(sessionReferenceElement, sessionReferenceLabel);
  keeps(
    sessionReferenceElement,
    "aria-label",
    `${sessionReferenceLabel} · copy reference`,
  );
  keeps(sessionReferenceElement, "title", `${sessionReferenceLabel} · copy reference`);
}

// The status says how the server answered the page's latest read (`reach`) and what
// the reading it adopted says, with the queues and the agent's name; it paints whenever
// one of those moves, and on the clock for the ages it words. Before any answer it says
// nothing until upgrade has opened the page, and then that saved state is loading.
const reach = readPart((root) => root.reach);
let upgraded = false;
// The status with its words for the banner (`statusModel`), or null before there is one
// to say. It is derived where it is read, so another presentation of it, the floating
// panel's leaf and comment field, says the same words in the same tone and follows
// the same inputs; only upgrade, which is mechanical, asks each to paint.
function currentStatus() {
  const answer = reach();
  if (answer === "waiting" && !upgraded) return null;
  const status =
    answer === "waiting" ? LOADING : pageStatus(runtime.state, { reach: answer });
  return { status, model: statusModel(status, readQueues(), agentName()) };
}
export const statusReading = () => currentStatus()?.model ?? null;
function paintStatus() {
  renderSessionReference();
  const state = runtime.state;
  if (state) {
    renderLayerReference(state);
    renderPreview(state);
  }
  const current = currentStatus();
  if (current) presentStatus(current);
}
const statusWatch = watchProjection(document.body, paintStatus);
document.addEventListener(
  UPGRADE,
  () => {
    upgraded = true;
    statusWatch.refresh();
  },
  { once: true },
);

// Sign-off is the page's decision, not fixed chrome: the approve button is offered only
// when the version declares <meta name="lf-review" content="sign-off"> — a plan or
// proposed change seeking assent. An informational page takes comments only, and
// nothing stands in the button's place there. A neutral "End leaf" did once, and it
// ended nothing it named: the server went on serving, the watcher went on waiting,
// the status was untouched, and the agent side still finished at `leaf status idle`.
// So the one control a page that asks nothing put in front of its user offered
// them an ending it could not deliver. The declaration rides the document, so a
// pinned older version keeps its own decision.
export const isSignoffDeclared = () =>
  /** @type {HTMLMetaElement | null} */ (
    document.querySelector('meta[name="lf-review"]')
  )?.content === "sign-off";

let signoff = false;

// The banner's row mounts after the version picker and drawers exist. Its complete
// inventory and order already belong to the shelf's explicit registrations above.
export function mountBanner({ approveVersion }) {
  signoff = isSignoffDeclared();
  showBannerControl(approveBtn, signoff);
  approvalWatch = watchProjection(document.body, drawApproval);
  showNews(othersBtn, false);
  banner.append(bannerStatus, bannerStatus.queues, bannerActions);
  // On two rows the agent's count stands on the second line only where the run leaves it
  // room whole, else on a third the banner does not draw, and a phone's one row leaves
  // it out (chrome.css). A press there is a stop nobody can see, so an undrawn count is
  // inert; the On me door and the status's disclosure still reach what it says.
  const counts = bannerStatus.queues;
  const seatCounts = sizeObserver(() => {
    const drawn =
      counts.checkVisibility() &&
      counts.getBoundingClientRect().bottom <=
        banner.getBoundingClientRect().bottom + 0.5;
    keeps(counts, "inert", drawn ? null : "");
  });
  for (const box of [banner, bannerActions, counts]) seatCounts.observe(box);
  approveBtn.onclick = approve;
  async function approveNow() {
    if (approving) return;
    // A refused press answers with its reason where every user sees it.
    const { reason } = approvalWords();
    if (reason) {
      notice(reason);
      return;
    }
    approving = true;
    approveBtn.setAttribute("aria-busy", "true");
    paintApproval();
    try {
      await approveVersion();
    } finally {
      approving = false;
      approveBtn.removeAttribute("aria-busy");
      paintApproval();
    }
  }
  approveWith = approveNow;
}

// The one approval press, whichever control the user made it on.
let approveWith = null;
export const approve = () => approveWith?.();

// Sign-off belongs to the authored revision, and the head it rides in is the only copy
// of it: a revision this document takes on in place brings its own, so the reading is
// taken from the document each time rather than kept beside it. The control stands for
// the declaration alone; the banner's allocation is independent of it: a control a
// stamp put up would be news taking room on the row. Before a stamp the press is refused
// with its reason (paintApproval) instead.
export function stateSignoff(next, syncLayout) {
  const shown = next;
  if (shown === signoff) return;
  signoff = shown;
  showBannerControl(approveBtn, signoff);
  paintApproval();
  syncLayout();
}

let approving = false;
// Whether the user has approved the shown version.
const versionApproved = readPart((root) =>
  root.effective.asks.all.some(
    (ask) => ask.source.kind === "approval" && ask.status === "answered",
  ),
);

// What Approval says now: its `text`, its `title`, why a press is refused (`reason`,
// null where it approves) and whether it is `open`. The asks holding approval are null
// before the page has read the log and so cannot say which those are.
function approvalWords() {
  const approved = versionApproved();
  const blockingAsks = approvalBlockingAsks();
  // The word and the title turn over together. The title read "Approve this work; the
  // page stays open for follow-up" whether or not the work had been approved, so the one
  // surface that could have told a user what pressing it would do next went on
  // describing a press they had already made. Approved, it says the state and the way
  // out of it, which is `z` like every other user gesture.
  // Why a press is refused now, or null where it approves. A press already in flight
  // is refused silently: its aria-busy says so.
  const reason = approved
    ? "Approved. Press z to undo while approval is still the latest update"
    : runtime.currentStamp === null
      ? "There is no stamped version to approve yet"
      : !signoff || !pagePresented() || blockingAsks === null
        ? AWAITING_STATE
        : blockingAsks.length
          ? "Answer every ask before approving this work"
          : null;
  return {
    reason: reason ?? (approving ? "Approving this version" : null),
    text: approved ? "✓ Version approved" : "Approve version",
    title: reason ?? "Approve this work; the page stays open for follow-up",
    open: reason === null,
  };
}
// Approval paints through one watcher, so what it reads repaints it, and a mechanical
// change (a press in flight, the sign-off declaration, the page presenting) asks it to
// paint again.
let approvalWatch = null;
export const paintApproval = () => approvalWatch?.refresh();
function drawApproval() {
  const words = approvalWords();
  presentApproval(words);
  // Approval is open while a press would approve this version, and behind More, on a
  // phone, that puts More's dot up. A refused press does not: the dot comes up when the
  // last ask holding approval is answered, which is when the user can act on it.
  markBannerControl(approveBtn, words.open ? "approval open" : null);
  repaint();
}
