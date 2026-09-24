/* This module owns banner wording, tone, tab-icon paint, and announcing a status kind
 * that has changed. */
import { JUST_NOW, ago, clocked } from "./presence.js";
import { el, offer, reserve } from "./widget-elements.js";
import { agentName, runtime, runtimeResource } from "./context.js";
import {
  BANNER_CONTROL_RANK,
  bannerActions,
  registerBannerControl,
  showBannerControl,
  showNews,
} from "./banner-shelf.js";
import { latestChip, versionBtn } from "./version-chooser.js";
import { asksBtn, othersBtn } from "./trays.js";
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";
import { repaint } from "./repaint.js";
import { announce, notice } from "./notifications.js";
import { watchProjection } from "./projection-watch.js";
import { createBannerApprovalFace } from "./banner-approval.js";
import { createBannerStatusView } from "./banner-status-view.js";

export const banner = el("header", "lf-ui lf-banner");
banner.id = "lf-banner";
const bannerStatus = createBannerStatusView(repaint);
export const dot = bannerStatus.dot;

export const toggleBtn = el(
  "button",
  "lf-btn lf-auxiliary-toggle lf-threads-toggle",
  "Threads",
);
toggleBtn.title = "Show or hide the thread panel";
toggleBtn.setAttribute("aria-expanded", "false");
let openThreads = null;
let unreadThreads = 0;
function paintThreadCounts() {
  toggleBtn.textContent = openThreads === null ? "Threads" : `Threads (${openThreads})`;
  toggleBtn.toggleAttribute("data-unread-threads", unreadThreads > 0);
  const unread = unreadThreads
    ? `${unreadThreads} unread ${unreadThreads === 1 ? "thread" : "threads"}`
    : null;
  if (unread)
    toggleBtn.setAttribute("aria-label", `${toggleBtn.textContent}, ${unread}`);
  else toggleBtn.removeAttribute("aria-label");
  toggleBtn.dataset.lfKeyTitle = unread
    ? `Show or hide the thread panel; ${unread}`
    : "Show or hide the thread panel";
}
// Both counts come from the one thread-list reading, so they are painted together.
export function setThreadCounts(open, unread) {
  openThreads = open;
  unreadThreads = unread;
  paintThreadCounts();
}
const approveBtn = el("button", "lf-btn primary lf-signoff");
approveBtn.title = "Approve this work; the page stays open for follow-up";
// The page's decision is not actionable until the page itself is present. Discussion chrome
// stays live during replay, but approving hidden authored content would decide a version
// the user has not seen yet.
approveBtn.disabled = true;
const approvalFace = createBannerApprovalFace(approveBtn);

// The shelf owns this complete order from typed contributions rather than discovering
// or reconstructing it from whichever nodes happen to be in the row.
registerBannerControl({
  key: "leaves",
  control: othersBtn,
  rank: BANNER_CONTROL_RANK.leaves,
  conditional: true,
});
registerBannerControl({
  key: "latest",
  control: latestChip,
  rank: BANNER_CONTROL_RANK.latest,
  conditional: true,
  urgent: true,
});
registerBannerControl({
  key: "asks",
  control: asksBtn,
  rank: BANNER_CONTROL_RANK.asks,
  conditional: true,
});
registerBannerControl({
  key: "versions",
  control: versionBtn,
  rank: BANNER_CONTROL_RANK.versions,
});
registerBannerControl({
  key: "approval",
  control: approveBtn,
  rank: BANNER_CONTROL_RANK.approval,
  seat: "row",
  present: false,
});
registerBannerControl({
  key: "threads",
  control: toggleBtn,
  rank: BANNER_CONTROL_RANK.threads,
  seat: "row",
});

// ---------- banner ----------
const TONE = {
  working: "working",
  listening: "listening",
  stalled: "away",
  away: "away",
  unheld: "",
  unattended: "",
  closed: "",
};
export const toneFor = (kind) => TONE[kind];
const WORK_WORDS = {
  thinking: "thinking",
  tool: "using a tool",
  awaiting_approval: "waiting for approval",
  awaiting_input: "waiting for input",
  replying: "replying",
};
export const workWords = (kind) => WORK_WORDS[kind] || "working";
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
// The mark with one colour written over it, or — for "" — the mark as authored. A style
// element appended last outranks the file's own rules, the dark-scheme block included,
// since a media query carries no specificity of its own. So this knows nothing about the
// icon beyond the class it promises, and a project's own mark is painted on the same
// terms.
function iconUrl(color) {
  let url = iconUrls.get(color);
  if (url === undefined) {
    const svg = iconMark.cloneNode(true);
    if (color) {
      const style = svg.ownerDocument.createElementNS(
        "http://www.w3.org/2000/svg",
        "style",
      );
      style.textContent = `.lf-tone { fill: ${color} }`;
      svg.append(style);
    }
    url =
      "data:image/svg+xml," +
      encodeURIComponent(new XMLSerializer().serializeToString(svg));
    iconUrls.set(color, url);
  }
  return url;
}
export async function loadIcon() {
  const response = await fetch(runtimeResource("/icon.svg"));
  if (!response.ok)
    throw new Error(`leaf: the tab icon failed to load (${response.status})`);
  const doc = new DOMParser().parseFromString(await response.text(), "image/svg+xml");
  // Two failures, and the same symptom: no element to paint. A parse error is reported
  // as a document rather than thrown, so a mark that isn't SVG at all reaches the class
  // check and fails it — sending whoever overrode the file to look for a class that is
  // sitting right there in it.
  const broken = doc.querySelector("parsererror");
  if (broken)
    throw new Error(
      // Collapsed, because the browser's report is laid out as a page and reads as
      // several lines of it; what matters is the line and column it names.
      `leaf: icon.svg is not SVG — ${broken.textContent.replace(/\s+/g, " ").trim()}`,
    );
  if (!doc.querySelector(".lf-tone"))
    throw new Error(
      "leaf: icon.svg carries no lf-tone element, which is where the page's " +
        "status is painted",
    );
  iconMark = doc.documentElement;
  // Left where `version export` can find it: a file has no session behind it, so a copy
  // wears the mark saying nothing rather than the tone it was exported under.
  tabLink.dataset.lfRest = iconUrl("");
  paintTab();
}
// A declaration, and called from two places, because the fetch above can land after the
// first poll has already judged the page.
function paintTab() {
  if (!iconMark) return;
  const url = iconUrl(getComputedStyle(dot).backgroundColor);
  // Written only on change: an unchanged poll must not hand the browser its icon again
  // every two seconds.
  if (tabLink.getAttribute("href") !== url) tabLink.setAttribute("href", url);
}
// Summary and explanation share the canonical activity reading. The complete wording
// remains available to pointer, keyboard, and touch through the native disclosure;
// announcements report that explanation when the page kind changes or current work
// begins waiting for user input or approval, not on every observed work step or poll.
let saidKind;
let saidActionableWork;
const presentStatus = ({
  kind,
  tone,
  summary,
  explanation,
  publication = null,
  actionableWork = null,
}) => {
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
  bannerStatus.present(
    Object.freeze({
      tone,
      summary,
      explanation,
      publication: publicationModel,
    }),
  );
  paintTab();
  const changed =
    saidKind !== undefined &&
    (saidKind !== kind ||
      (actionableWork !== null && actionableWork !== saidActionableWork));
  saidKind = kind;
  saidActionableWork = actionableWork;
  if (changed) announce(explanation);
};
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

let previewMarginEntry = null;
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
  const label = preview.commit && preview.dirty ? `${stem}+` : stem;
  const safeUrl = new URL(location.href);
  safeUrl.searchParams.delete("t");
  previewDiagnostics = [
    "Leaf preview",
    `example: ${preview.example}`,
    `checkout: ${preview.checkout}`,
    `interaction: ${preview.interaction}`,
    ...(preview.commit ? [`commit: ${preview.commit}`] : []),
    ...(preview.dirty !== undefined ? [`dirty: ${preview.dirty}`] : []),
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
    registerBannerControl({
      key: "preview",
      control: previewMarginEntryCopy,
      focusTarget: previewMarginEntry,
      rank: BANNER_CONTROL_RANK.preview,
    });
  }
  previewMarginEntryCopy.value = previewDiagnostics;
  previewMarginEntryCopy.copyLabel = "Copy preview diagnostics";
  previewMarginEntry.textContent = label;
  previewMarginEntry.title = `${preview.example} · started ${preview.started} · copy diagnostics`;
}

// The vendored layer is the Leaf version this page actually runs. It can remain older
// than the plugin now installed on the host, so this reads the provenance captured by
// `page init` rather than a live package or server version. Pages built outside Git
// retain a stable identity through the composed layer fingerprint.
let layerReferenceElement = null;
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
  const identity = producer.commit
    ? `${producer.commit.slice(0, 8)}${producer.dirty ? "+" : ""}`
    : fullIdentity;
  const safeUrl = new URL(location.href);
  safeUrl.searchParams.delete("t");
  layerDiagnostics = [
    "Leaf layer",
    ...(producer.commit ? [`commit: ${producer.commit}`] : []),
    ...(producer.dirty !== undefined ? [`dirty: ${producer.dirty}`] : []),
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
    });
  }
  layerReferenceElementCopy.value = layerDiagnostics;
  layerReferenceElementCopy.copyLabel = `Leaf ${identity} · copy version`;
  layerReferenceElement.replaceChildren(
    "Leaf ",
    el("code", "lf-layer-version", identity),
  );
  layerReferenceElement.title = producer.dirty
    ? "+ means this layer includes uncommitted changes · copy diagnostics"
    : "Copy Leaf layer version and diagnostics";
  layerReferenceElement.setAttribute("aria-label", `Leaf ${identity} · copy version`);
}
// Status sentences for an unreachable server or a state the page cannot apply.
const OFFLINE_LINE =
  "Server offline — reconnecting. Keep this page open so pending changes can send.";
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

// Both levels of wording follow server-owned activity. Short summaries retain the
// actionable distinction: listening, saved for a later session, or browser-only work.
function statusWords({
  age,
  agent,
  dated,
  shortDate,
  detail,
  kind,
  pending,
  progressSummary,
  quiet,
  saved,
  total,
  workKind,
}) {
  const savedSummary = total ? ` · ${total} saved` : "";
  if (kind === "closed") return ["Leaf closed", "Leaf closed"];
  if (kind === "unattended")
    return [
      "Browser only · no agent",
      "Nobody is behind this page. What you do here stays in this browser.",
    ];
  if (kind === "unheld")
    return [
      `No session${savedSummary}`,
      `No session holds this page. ${saved} It picks up again when a session does.`,
    ];
  // The agent's own sentence is the reason to look at the row while it works, so the
  // row keeps it and the ellipsis fits it to the room the controls leave. A sentence just
  // renewed needs no date; an older one is dated ahead of the detail, because the detail
  // is what the ellipsis eats first and a stale sentence with its date cut off is the one
  // reading this row must not give.
  if (kind === "working") {
    const work = workWords(workKind);
    const said = detail ? " — " + detail : "";
    return [
      `${agent} ${work}${age && age !== JUST_NOW ? " · " + age : ""}${said}${progressSummary}`,
      `${agent} is ${work}${said}`,
    ];
  }
  // A declared request tells the user what to do. Preserve it on the row when
  // no pending input supersedes it; a generic attendance label would lose that cue.
  if (kind === "listening") {
    const awaits = `${agent} awaits — ${detail || "select text to comment"}`;
    return pending
      ? [
          `${agent} listening${progressSummary}`,
          `${agent} is listening${detail ? " — " + detail : ""}.`,
        ]
      : [awaits, awaits];
  }
  if (kind === "stalled")
    return [shortDate, `${dated}${detail ? ": " + detail : ""}. ${saved}`];
  return quiet
    ? [
        `Nudge ${agent} in terminal${savedSummary}`,
        `${dated}. ${saved} Nudge it in the terminal.`,
      ]
    : [
        `${agent} away${savedSummary}`,
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
    });
  }
  sessionReferenceElementCopy.value = runtime.sessionReference;
  sessionReferenceElementCopy.copyLabel = `${sessionReferenceLabel} · copy reference`;
  sessionReferenceElement.textContent = sessionReferenceLabel;
  sessionReferenceElement.setAttribute(
    "aria-label",
    `${sessionReferenceLabel} · copy reference`,
  );
  sessionReferenceElement.title = `${sessionReferenceLabel} · copy reference`;
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
      summary: "Server offline — reconnecting; keep page open",
      explanation: OFFLINE_LINE,
    });
    return;
  }
  renderLayerReference(state);
  renderPreview(state);
  const publication = state.publication;
  if (publication) {
    presentStatus({
      kind: "unattended",
      tone: TONE.unattended,
      publication,
    });
    return;
  }
  const { activity } = state;
  const { kind, quiet, dropped, detail } = activity;
  // What the user's words do meanwhile. The log takes them with nobody on the other
  // end; the only thing attendance changes is when they are read.
  const saved = activity.counts.total
    ? `${activity.counts.total} update${activity.counts.total === 1 ? " is" : "s are"} saved.`
    : "Your comments are saved.";
  // Dated by whichever fact ended the belief. A dropped claim is dated by the ending
  // and not by its own last word, because "last checked in just now" under an amber
  // dot is the line arguing with the dot beside it.
  const dated = dropped
    ? `${agentName()} left this when its turn ended ${ago(state.turn_closed)}`
    : `${agentName()} last checked in ${ago(activity.ts)}`;
  const age = kind === "working" && activity.ts ? ago(activity.ts) : "";
  const progress = [];
  if (activity.counts.queued) progress.push(`${activity.counts.queued} queued`);
  if (activity.counts.pending) progress.push(`${activity.counts.pending} waiting`);
  const progressSummary = progress.length ? ` · ${progress.join(" · ")}` : "";
  const [summary, text] = statusWords({
    age,
    agent: agentName(),
    dated,
    shortDate: dropped
      ? `${agentName()}’s turn ended ${ago(state.turn_closed)}`
      : `${agentName()} last checked in ${ago(activity.ts)}`,
    detail,
    kind,
    total: activity.counts.total,
    pending: activity.counts.pending || activity.counts.queued,
    progressSummary,
    quiet,
    saved,
    workKind: activity.observed_kind,
  });
  let explanation = age ? `${text} (${age})` : text;
  // What a transport can watch for itself, when the sentence beside it was written by
  // the agent: two facts about one turn, so the row keeps the one meant for the user
  // and the disclosure holds the step proving the session is still moving.
  if (activity.observed && activity.observed !== detail)
    explanation += ` · ${activity.observed}`;
  const waiting = [];
  if (activity.counts.queued)
    waiting.push(
      `${activity.counts.queued} update${activity.counts.queued === 1 ? "" : "s"} queued`,
    );
  if (activity.counts.pending)
    waiting.push(
      `${activity.counts.pending} update${activity.counts.pending === 1 ? "" : "s"} waiting`,
    );
  if (waiting.length && ["working", "listening"].includes(kind))
    explanation += `${explanation.endsWith(".") ? "" : "."} ${waiting.join(" · ")}.`;
  const actionableWork = ["awaiting_approval", "awaiting_input"].includes(
    activity.observed_kind,
  )
    ? activity.observed_kind
    : null;
  presentStatus({ kind, tone: TONE[kind], summary, explanation, actionableWork });
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

// The banner's row mounts after the version chooser and trays exist. Its complete
// inventory and order already belong to the shelf's explicit registrations above.
export function mountBanner({ approveVersion, paintApproval }) {
  signoff = isSignoffDeclared() && runtime.currentStamp !== null;
  showBannerControl(approveBtn, signoff);
  watchProjection(document.body, paintApproval);
  for (const control of [asksBtn, othersBtn]) showNews(control, false);
  banner.append(bannerStatus, bannerActions);
  reserveBannerControls();
  approveBtn.onclick = async () => {
    if (approving) return;
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
  };
}

// Sign-off belongs to the authored revision, and the head it rides in is the only copy
// of it: a revision this document takes on in place brings its own, so the reading is
// taken from the document each time rather than kept beside it. Stamping the document
// already open can also add or remove this control without any revision change.
export function stateSignoff(next, syncLayout, paintApproval) {
  const shown = next && runtime.currentStamp !== null;
  if (shown === signoff) return;
  signoff = shown;
  showBannerControl(approveBtn, signoff);
  if (signoff) reserve(approveBtn, ["Approve version", "✓ Version approved"]);
  paintApproval();
  syncLayout();
}

// The two primary controls hold the widest words they can show, so an asynchronous
// count or approval result cannot move its sibling. Secondary controls can grow inside
// More without changing the page's reading loop.
export function reserveBannerControls() {
  if (signoff) reserve(approveBtn, ["Approve version", "✓ Version approved"]);
  reserve(toggleBtn, ["Threads", "Threads (999)"]);
}

let approving = false;

// `blockingAsks` is the unanswered Asks that hold approval, or null before the page has
// read the log and so cannot say which those are.
export function paintApproval(pendingApprovals, blockingAsks, acceptedApprovals) {
  const approved = [...acceptedApprovals, ...pendingApprovals].some(
    (e) => e.kind === "done" && e.version === runtime.currentStamp,
  );
  // The word and the title turn over together. The title read "Approve this work; the
  // page stays open for follow-up" whether or not the work had been approved, so the one
  // surface that could have told a user what pressing it would do next went on
  // describing a press they had already made. Approved, it says the state and the way
  // out of it, which is `z` like every other user gesture.
  approvalFace.present(
    Object.freeze({
      disabled:
        !signoff ||
        approving ||
        runtime.currentStamp === null ||
        !document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented) ||
        blockingAsks === null ||
        blockingAsks.length > 0 ||
        approved,
      text: approved ? "✓ Version approved" : "Approve version",
      title: approved
        ? "Approved. Press z to take it back while it is still your last gesture"
        : blockingAsks === null
          ? "Approval waits until this page has read its current state"
          : blockingAsks.length
            ? "Answer every Ask before approving this work"
            : "Approve this work; the page stays open for follow-up",
    }),
  );
  repaint();
}
