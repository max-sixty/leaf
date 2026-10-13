/* This module owns banner wording, tone, tab-icon paint, and announcing changes
 * after the first status reading. Provisional interface readiness paints the banner
 * without establishing that announcement baseline; saved state or a failed read does. */
import { html, nothing, render } from "../vendor/browser-runtime.js";
import { JUST_NOW, ago, clocked } from "./presence.js";
import { el, offer, reserve } from "./widget-elements.js";
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
import { latestChip, versionBtn, versionPicker } from "./version-picker.js";
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
import { readAsks } from "./asks/model.js";
import { createBannerStatusView } from "./banner-status-view.js";
import { declareBanner } from "./geometry.js";
import { agentName, watchSemantic } from "./semantic-state.js";
import { itemNoun } from "./queues.js";
import { UPGRADE } from "./presentation.js";
import { WEBSITE_DELIVERY } from "./context.js";
import { readQueues } from "./queue-api.js";

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
const bannerStatus = createBannerStatusView(repaint, INITIAL);
registerNoticePresentation(() => bannerStatus.presentNotice(noticeReading()));
// The agent's Tasks count, which opens the Questions panel listing them (drawers.js).
export const queueCounts = bannerStatus.queues;

// Threads reads "Threads: 3" on a desk and, on a phone's one row, a thread icon with its
// count, which chrome.css draws from `data-lf-count`; the accessible name is the same
// words on both. The desk's words stay one run of text, so they draw as they always have.
export const toggleBtn = el("button", "lf-btn lf-auxiliary-toggle lf-threads-toggle");
const threadsLabel = el("span", "lf-threads-label", "Threads");
toggleBtn.append(iconElement("comment", "lf-threads-icon"), threadsLabel);
toggleBtn.title = "Show or hide the thread panel";
toggleBtn.setAttribute("aria-expanded", "false");
let openThreads = null;
let unreadThreads = 0;
function paintThreadCounts() {
  const label = openThreads === null ? "Threads" : `Threads: ${openThreads}`;
  const accessible = openThreads === null ? "Threads" : `Open threads: ${openThreads}`;
  keepsText(threadsLabel, label);
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
const approveBtn = el("button", "lf-btn primary lf-signoff");
approveBtn.id = "lf-approve";
// The queue arrives at the one approval control, including its overflow seat.
export const approvalTarget = () => (signoff ? approveBtn : null);
approveBtn.title = "Approve this work; the page stays open for follow-up";
// The page's decision is not actionable until the page itself is present. Discussion chrome
// stays live during replay, but approving hidden authored content would decide a version
// the user has not seen yet. The control states that refusal from its first reading.
const AWAITING_STATE = "Approval waits until this page has read its current state";
let approvalReason;
let approvalText = "Approve version";
// What Approval says and whether a press would approve, for another presentation of it,
// such as the floating panel's Versions view; null where the page asks no sign-off.
export const approvalReading = () =>
  signoff ? { text: approvalText, reason: approvalReason ?? null } : null;
// Keep a refused press focusable, with its reason available to keyboard and touch.
function presentApproval({ reason, text, title }) {
  approvalReason = reason;
  approvalText = text;
  render(text, approveBtn);
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
  row: { label: () => versionPicker.model.latest.label, group: "page" },
});
registerBannerControl({
  key: "queue",
  control: queueBtn,
  rank: BANNER_CONTROL_RANK.queue,
  seat: { desk: "row", phone: "menu" },
  row: {
    label: "Questions",
    value: () => String(readQueues().questions.length),
    group: "page",
  },
});
registerBannerControl({
  key: "versions",
  control: versionBtn,
  rank: BANNER_CONTROL_RANK.versions,
  row: {
    label: "Versions",
    value: () => versionPicker.model.picker.token.replace(/^Showing /, ""),
    group: "page",
  },
});
registerBannerControl({
  key: "approval",
  control: approveBtn,
  rank: BANNER_CONTROL_RANK.approval,
  seat: { desk: "row", phone: "menu" },
  present: false,
  row: { label: () => approvalText, group: "page", press: () => approve() },
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
const TONE = {
  working: "working",
  listening: "listening",
  stalled: "away",
  away: "away",
  unheld: "",
  closed: "",
};
const WORK_WORDS = {
  thinking: "thinking",
  tool: "using a tool",
  awaiting_approval: "waiting for approval",
  awaiting_input: "waiting for input",
  awaiting_user: "waiting for me",
  replying: "replying",
};
const countResponses = (count) => `${count} response${count === 1 ? "" : "s"}`;
// What each canonical count says the agent owes, in the order a reader is told.
const COUNT_PHRASES = {
  active: "being worked on",
  handling: "owed on picked-up updates",
  queued: "owed on queued updates",
  picked_up: "owed on picked-up updates; no current turn observed",
  pending: "owed on updates awaiting delivery",
};
const phrased = (counts, kinds) =>
  kinds
    .filter((kind) => counts[kind])
    .map((kind) => `${countResponses(counts[kind])} ${COUNT_PHRASES[kind]}`);
// What the banner and the leaves drawer both read off one page's server-owned `activity`
// before either words it. Each seat keeps its own sentences; a fact they share changes
// here once:
//
// - `left` says the turn's ending retired the belief, and `silentSince` dates the
//   silence by the reading's own `ts`, which the server already sets to that ending
//   for a dropped claim.
// - `listening` is whether input is still on its way to the agent (pending or queued),
//   which turns a listening page's standing request into "listening".
// - `waiting` phrases the queued and pending updates, in that order, and `owed` the
//   other counts, for a seat with room to say them beside `waiting`.
export function activityFacts({ activity }) {
  const { counts } = activity;
  return Object.freeze({
    tone: TONE[activity.kind],
    work: WORK_WORDS[activity.observed_kind] || "working",
    left: Boolean(activity.dropped),
    silentSince: ago(activity.ts),
    listening: Boolean(counts.pending || counts.queued),
    waiting: Object.freeze(phrased(counts, ["queued", "pending"])),
    owed: Object.freeze(phrased(counts, ["active", "handling", "picked_up"])),
  });
}
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

// The page's two queues (`served_state.queues`) are told apart in the banner by where
// they stand. What waits on the user, which `q` walks, is the Questions door beside
// Threads (queue-panel.js paints its count), and on a phone's one row it waits in More.
// What waits on the agent, its Tasks, stands beside the status, apart from the sentence,
// as the banner's whole account of the agent's side, with the disclosure naming both
// sides' kinds and each open to-do's title. The Tasks count is a page fact, like the
// Threads count, and stands apart from the sentence so the agent's words changing never
// carries it. On one row it ends the status's room, which gives up its words to the
// ellipsis first; where the banner takes two rows, the sentence has the first to itself
// and the count leads the second, ahead of the controls, and a phone's one row leaves it
// to the disclosure (chrome.css). Its box is reserved for the count it usually reaches,
// as the Threads control is for "Threads: 999", and only grows, so a count changing
// moves none of its words. Both are read from the application's publication rather
// than the state answer: a reply the user sends joins the agent's count in the turn
// it is sent, and leaves the user's once the server has read it. A press on either
// opens the Questions panel, which lists both.
const QUEUE_WORDS = Object.freeze({
  ask: ["ask", "asks"],
  approval: ["approval", "approvals"],
  resend: ["update to send again", "updates to send again"],
  answer: ["answer", "answers"],
  reply: ["reply", "replies"],
  work: ["update with work started", "updates with work started"],
  todo: ["to-do", "to-dos"],
});
function queueKinds(items) {
  const byKind = new Map();
  for (const item of items)
    byKind.set(itemNoun(item), [...(byKind.get(itemNoun(item)) ?? []), item]);
  return [...byKind].map(([kind, all]) => {
    const words = `${all.length} ${QUEUE_WORDS[kind][all.length === 1 ? 0 : 1]}`;
    // A to-do outlasts the turns and the thread that opened it (`todos.py`), so each
    // open one is named, including one on a thread the user has resolved.
    return kind === "todo"
      ? `${words} (${all.map((todo) => todo.title).join(" · ")})`
      : words;
  });
}
function queueWords() {
  const { questions, tasks } = readQueues();
  const agent = agentName();
  const named = (items, whom) =>
    items.length ? `Waiting on ${whom}: ${queueKinds(items).join(", ")}.` : "";
  return {
    summary: tasks.length ? `Tasks: ${tasks.length}` : "",
    explanation: [named(questions, "me"), named(tasks, agent)]
      .filter(Boolean)
      .join(" "),
    // The widest the count usually reaches, under ten, which its box keeps; more
    // widens it once (banner-status-view.js).
    widest: "Tasks: 9",
  };
}
const WITHOUT_QUEUES = new Set(["broken", "unreachable", "publication"]);
let lastStatus = null;
// The status the banner shows, as one reading another presentation of it shares: the
// floating panel's leaf and comment field say the same words in the same tone.
let statusReading = null;
const statusListeners = new Set();
export function watchStatus(listener) {
  statusListeners.add(listener);
  if (statusReading) listener(statusReading);
  return () => statusListeners.delete(listener);
}
const presentStatus = (status) => {
  lastStatus = status;
  const { kind, tone, summary, publication = null, actionableWork = null } = status;
  let { explanation } = status;
  const queues = WITHOUT_QUEUES.has(kind)
    ? { summary: "", explanation: "", widest: "" }
    : queueWords();
  if (queues.explanation)
    explanation = `${explanation}${explanation.endsWith(".") ? "" : "."} ${queues.explanation}`;
  let publicationModel = null;
  if (publication) {
    // A publication's introduction and links remain an ordinary reading row.
    // Links never become children of the status disclosure button.
    const [said, installs] = publicationWords(publication);
    const examples = publication.kind === "example" ? "Other examples" : null;
    explanation = said + (examples ? `${examples} ` : "") + installs;
    publicationModel = Object.freeze({
      copy: said,
      examples,
      install: installs,
      installUrl: publication.install_url,
      examplesUrl: examples ? "/examples/" : null,
    });
  }
  const model = Object.freeze({
    tone,
    summary,
    queues: queues.summary,
    queuesWidest: queues.widest,
    explanation,
    publication: publicationModel,
  });
  bannerStatus.present(model);
  statusReading = model;
  for (const listener of statusListeners) listener(model);
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
  if (changed) announce(explanation);
};
// Upgrade opens new comments before the buffered saved reading is applied.
document.addEventListener(
  UPGRADE,
  () => {
    presentStatus({
      kind: "loading",
      tone: "",
      summary: "Loading saved state…",
      explanation:
        "The page is ready for reading and new comments. Saved comments and choices are still loading; new comments will be sent when the server responds." +
        (WEBSITE_DELIVERY
          ? " Website examples can take longer to load their saved state than a usual Leaf page."
          : ""),
    });
  },
  { once: true },
);
// The developer preview's identity: which checkout is serving this page, and a press to
// copy the whole diagnostic. It is the banner's least-used control, so it stays behind
// the overflow door at every width instead of adding a permanent chip to the reading row.
function copyControl(trigger, success, error) {
  const copy = offer("wa-copy-button", "lf-banner-copy");
  copy.successLabel = success;
  copy.errorLabel = error;
  copy.tooltip = "none";
  // Web Awesome announces the result; Leaf puts the same words in its status line.
  copy.addEventListener("wa-copy", () => notice(success, { announce: false }));
  copy.addEventListener("wa-error", () => notice(error, { announce: false }));
  copy.append(trigger);
  return copy;
}

if (SHARE_ROOT) {
  const details = el("details", "lf-share");
  const share = el("summary", "lf-btn", "Share");
  share.title = "Show this page's access link";
  const panel = el("div", "lf-share-panel");
  const label = el("label", "", "Share link");
  const link = offer("input", "lf-share-link");
  link.id = "lf-share-link";
  link.type = "url";
  link.readOnly = true;
  link.addEventListener("focus", () => link.select());
  label.append(link);
  const copyButton = el("button", "lf-btn", "Copy link");
  copyButton.type = "button";
  const copy = copyControl(copyButton, "Link copied", "Select and copy the link above");
  copy.copyLabel = "Copy link";
  copy.hidden = !navigator.clipboard?.writeText;
  panel.append(
    el("p", "", "Grants access to all Leaf pages on this machine."),
    label,
    copy,
  );
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
    // The press is the Copy link control's own, with its success and failure notices.
    row: {
      label: "Copy share link",
      group: "about",
      press: () => {
        copy.value = shareUrl();
        copyButton.click();
      },
    },
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
  // A user preview claims the page, so every press on it — the agent's own
  // screenshots included — comes back to the session as user input. That is the
  // mode worth marking; an unclaimed preview delivers nothing and needs no warning.
  const kind = preview.interaction === "user" ? "User" : "Preview";
  const stem = `${kind} · ${preview.checkout}${preview.commit ? `@${preview.commit}` : ""}`;
  const age = payloadAge(preview);
  // The preview names the checkout and the Leaf that vendored the page
  // (`preview_metadata`). Where another Leaf serves it (`state.leaf`), that follows.
  const served = state.leaf
    ? ` · served by ${shortCommit(state.leaf)}${payloadAge(state.leaf) ? ` · ${payloadAge(state.leaf)}` : ""}`
    : "";
  const label = `${preview.commit && preview.dirty ? `${stem}+` : stem}${age ? ` · ${age}` : ""}${served}`;
  const safeUrl = new URL(location.href);
  safeUrl.searchParams.delete("t");
  previewDiagnostics = [
    "Leaf preview",
    `example: ${preview.example}`,
    `checkout: ${preview.checkout}`,
    `interaction: ${preview.interaction}`,
    ...(preview.commit ? [`commit: ${preview.commit}`] : []),
    ...(preview.dirty !== undefined ? [`dirty: ${preview.dirty}`] : []),
    ...payloadDateLines(preview),
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
    previewMarginEntryCopy = copyControl(
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
      row: { label: () => previewLabel, group: "about" },
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
let layerIdentity = "";
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
  layerIdentity = identity;
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
    layerReferenceElementCopy = copyControl(
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
        value: () => layerIdentity,
        group: "about",
      },
    });
  }
  layerReferenceElementCopy.value = layerDiagnostics;
  const servedBy = served
    ? ` · served by ${serverIdentity}${serverAge ? ` · ${serverAge}` : ""}`
    : "";
  const named = `Leaf ${identity}${age ? ` · ${age}` : ""}${servedBy}`;
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
// Status sentences for an unreachable server or a state the page cannot apply.
const OFFLINE_LINE =
  "Server offline — reconnecting. Keep this page open so pending changes can send.";
// A refused key leaves the page as cut off as a dead server, but the server is up and
// only the user can end it. Opening the link in another tab sets the key this tab's
// next request carries, so its pending changes send without a reload.
const KEY_REFUSED_LINE =
  "The server no longer accepts this tab's key. Open the link Leaf printed in a new tab, and keep this one open so pending changes can send.";
const BROKEN_LINE = "Page couldn't apply current state — reload";
// A published page states who replies and where to install Leaf.
const publicationWords = (published) => [
  `${
    published.kind === "example"
      ? "This is an example on the Leaf website."
      : "This website is a Leaf page."
  } ${published.agent} replies and revises this private copy. `,
  "Install Leaf",
];

// The updates an open turn picked up, by kind: a comment in a thread, or an answer to an
// ask. A lone update is the user's own; several are counted.
function pickedUpWords({ comments, answers }) {
  if (comments + answers === 1) return comments ? "my comment" : "my answer";
  const counted = (count, noun) => `${count} ${noun}${count === 1 ? "" : "s"}`;
  return [
    comments && counted(comments, "comment"),
    answers && counted(answers, "answer"),
  ]
    .filter(Boolean)
    .join(" and ");
}

// Both levels of wording follow server-owned activity. Short summaries retain the
// actionable distinction: working, listening, away, or nobody holding the page. How many
// updates are waiting or saved is the disclosure's; the row counts what waits on each
// side instead (`queueWords`).
function statusWords({
  age,
  agent,
  dated,
  shortDate,
  detail,
  handling,
  kind,
  listening,
  overdue,
  saved,
  work,
}) {
  if (kind === "closed") return ["Page closed", "Page closed"];
  if (kind === "unheld")
    return [
      "No session",
      `No session holds this page. ${saved} It picks up again when a session does.`,
    ];
  // The agent's own sentence is the reason to look at the row while it works, so the
  // row keeps it and the ellipsis fits it to the room the controls leave. A sentence just
  // renewed needs no date; an older one is dated ahead of the detail, because the detail
  // is what the ellipsis eats first and a stale sentence with its date cut off is the one
  // reading this row must not give.
  //
  // Until the agent writes that sentence, what Leaf knows is which of the user's
  // updates its open turn picked up, so the row names them, in the words of their
  // Picked up stage, rather than standing on a bare "working", and the disclosure
  // says the agent's own words are still to come.
  if (kind === "working") {
    const picked = pickedUpWords(handling);
    const said = detail ? " — " + detail : picked ? " — picked up " + picked : "";
    return [
      `${agent} ${work}${age && age !== JUST_NOW ? " · " + age : ""}${said}`,
      detail || !picked
        ? `${agent} is ${work}${said}`
        : `${agent} picked up ${picked} and hasn't said what it's doing yet`,
    ];
  }
  // A declared request tells the user what to do. Preserve it on the row when
  // no pending input supersedes it; a generic attendance label would lose that cue.
  if (kind === "listening") {
    const awaits = `${agent} awaits — ${detail || "select text to comment"}`;
    return listening
      ? [`${agent} listening`, `${agent} is listening${detail ? " — " + detail : ""}.`]
      : [awaits, awaits];
  }
  if (kind === "stalled")
    return [shortDate, `${dated}${detail ? ": " + detail : ""}. ${saved}`];
  // Away is only worth a nudge once input has stalled (`counts.overdue`): the
  // session's next turn picks up whatever it finds, and Leaf messages a harness it
  // can reach once it has seen the turn end.
  return overdue
    ? [
        `Nudge ${agent} in terminal`,
        `${dated}. ${saved} Nothing is answering them, so nudge it in the terminal.`,
      ]
    : [
        `${agent} away`,
        `${agent} isn't watching right now. ${saved} It picks them up next turn.`,
      ];
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
    sessionReferenceElementCopy = copyControl(
      sessionReferenceElement,
      "Copied session reference",
      "Couldn't copy session reference",
    );
    registerBannerControl({
      key: "session",
      control: sessionReferenceElementCopy,
      focusTarget: sessionReferenceElement,
      rank: BANNER_CONTROL_RANK.session,
      row: { label: () => sessionReferenceLabel, group: "about" },
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

function renderStatusNow(state) {
  renderSessionReference();
  if (state instanceof Error) {
    presentStatus({
      kind: "broken",
      tone: "offline",
      summary: BROKEN_LINE,
      explanation: BROKEN_LINE,
    });
    return;
  }
  if (state === null) {
    presentStatus({
      kind: "unreachable",
      tone: "offline",
      ...(runtime.keyRefused
        ? {
            summary: "Key refused — open Leaf's link in a new tab",
            explanation: KEY_REFUSED_LINE,
          }
        : {
            summary: "Server offline — reconnecting; keep page open",
            explanation: OFFLINE_LINE,
          }),
    });
    return;
  }
  renderLayerReference(state);
  renderPreview(state);
  const publication = state.publication;
  if (publication) {
    presentStatus({ kind: "publication", tone: "", publication });
    return;
  }
  const { activity } = state;
  const { kind, detail } = activity;
  const facts = activityFacts(state);
  const { agent } = state;
  // What the user's words do meanwhile. The log takes them with nobody on the other
  // end; the only thing attendance changes is when they are read.
  const saved = "Updates are saved.";
  const checkedIn = facts.silentSince
    ? `${agent} last checked in ${facts.silentSince}`
    : `No check-in from ${agent} is recorded`;
  const ended = `${agent}’s turn ended${facts.silentSince ? " " + facts.silentSince : ""}`;
  const age = kind === "working" && activity.ts ? ago(activity.ts) : "";
  const [summary, text] = statusWords({
    age,
    agent,
    dated: facts.left ? ended : checkedIn,
    shortDate: facts.left ? ended : checkedIn,
    detail,
    handling: {
      comments: activity.counts.handling_comments,
      answers: activity.counts.handling - activity.counts.handling_comments,
    },
    kind,
    listening: facts.listening,
    overdue: activity.counts.overdue,
    saved,
    work: facts.work,
  });
  let explanation = age ? `${text} (${age})` : text;
  // What a transport can watch for itself, when the sentence beside it was written by
  // the agent: two facts about one turn, so the row keeps the one meant for the user
  // and the disclosure holds the step proving the session is still moving.
  if (activity.observed && activity.observed !== detail)
    explanation += ` · ${activity.observed}`;
  if (facts.waiting.length && ["working", "listening"].includes(kind))
    explanation += `${explanation.endsWith(".") ? "" : "."} ${facts.waiting.join(" · ")}.`;
  const actionableWork = activity.awaiting ? activity.observed_kind : null;
  // An approval or a question the agent's own window holds is answered there, and
  // the page is the one place the user may be looking instead.
  if (actionableWork && kind === "working")
    explanation += `${explanation.endsWith(".") ? "" : "."} It waits in its own session, not on this page.`;
  presentStatus({ kind, tone: facts.tone, summary, explanation, actionableWork });
}

export const renderStatus = clocked(document.body, renderStatusNow);

// Sign-off is the page's decision, not standing chrome: the approve button is offered only
// when the version declares <meta name="lf-review" content="sign-off"> — a plan or
// proposed change seeking assent. An informational page takes comments only, and
// nothing stands in the button's place there. A neutral "End leaf" did once, and it
// ended nothing it named: the server went on serving, the watcher went on waiting,
// the status was untouched, and the agent side still finished at `leaf status idle`.
// So the one control a page that asks nothing put in front of its user offered
// them an ending it could not deliver. The declaration rides the document, so a
// pinned older version keeps its own decision.
export const isSignoffDeclared = () =>
  document.querySelector('meta[name="lf-review"]')?.content === "sign-off";

let signoff = false;

// The banner's row mounts after the version picker and drawers exist. Its complete
// inventory and order already belong to the shelf's explicit registrations above.
export function mountBanner({ approveVersion, paintApproval }) {
  signoff = isSignoffDeclared();
  showBannerControl(approveBtn, signoff);
  watchProjection(document.body, paintApproval);
  // The queues move with the application's publication, not only with a state answer.
  watchSemantic(() => lastStatus && presentStatus(lastStatus));
  showNews(othersBtn, false);
  banner.append(bannerStatus, bannerStatus.queues, bannerActions);
  // On two rows the Tasks count stands on the second line only where the run leaves it
  // room whole, else on a third the banner does not draw, and a phone's one row leaves
  // it out (chrome.css). A press there is a stop nobody can see, so an undrawn count is
  // inert; the Questions door and the status's disclosure still reach what it says.
  const counts = bannerStatus.queues;
  const seatCounts = sizeObserver(() => {
    const drawn =
      counts.checkVisibility() &&
      counts.getBoundingClientRect().bottom <=
        banner.getBoundingClientRect().bottom + 0.5;
    keeps(counts, "inert", drawn ? null : "");
  });
  for (const box of [banner, bannerActions, counts]) seatCounts.observe(box);
  reserveBannerControls();
  approveBtn.onclick = approve;
  async function approveNow() {
    if (approving) return;
    // A refused press answers with its reason where every user sees it.
    if (approvalReason) {
      notice(approvalReason);
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
export function stateSignoff(next, syncLayout, paintApproval) {
  const shown = next;
  if (shown === signoff) return;
  signoff = shown;
  showBannerControl(approveBtn, signoff);
  if (signoff) reserve(approveBtn, ["Approve version", "✓ Version approved"]);
  paintApproval();
  syncLayout();
}

// The primary controls reserve the widest words they can show, so an asynchronous
// count or approval result cannot move a sibling. CSS bounds Approval's room when
// the complete words cannot fit. Secondary controls can grow inside
// More without changing the page's reading loop.
function reserveBannerControls() {
  if (signoff) reserve(approveBtn, ["Approve version", "✓ Version approved"]);
  reserve(queueBtn, ["Questions: 99"]);
  reserve(toggleBtn, ["Threads", "Threads: 999"]);
}

let approving = false;

// `blockingAsks` is the unanswered asks that hold approval, or null before the page has
// read the log and so cannot say which those are.
export function paintApproval(blockingAsks) {
  const approved = readAsks().all.some(
    (ask) => ask.source.kind === "approval" && ask.status === "answered",
  );
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
  presentApproval({
    reason: reason ?? (approving ? "Approving this version" : null),
    text: approved ? "✓ Version approved" : "Approve version",
    title: reason ?? "Approve this work; the page stays open for follow-up",
  });
  // Approval is open while a press would approve this version, and behind More, on a
  // phone, that puts More's dot up. A refused press does not: the dot comes up when the
  // last ask holding approval is answered, which is when the user can act on it.
  markBannerControl(approveBtn, reason === null ? "approval open" : null);
  repaint();
}
