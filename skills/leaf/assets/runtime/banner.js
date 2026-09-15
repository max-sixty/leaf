/* This module owns banner wording, tone, tab-icon paint, and announcing a status kind
 * that has changed. */
import { ago, clocked } from "./presence.js";
import { el, reserve } from "./widget-elements.js";
import { agentName, runtime, runtimeResource } from "./context.js";
import {
  BANNER_CONTROL_RANK,
  bannerActions,
  foldShelf,
  measureBannerControls,
  overflowBtn,
  overflowMenu,
  registerBannerControl,
  showBannerControl,
  showNews,
} from "./banner-shelf.js";
import { latestChip, reserveVersionControls, versionBtn } from "./version-chooser.js";
import { asksBtn, othersBtn } from "./trays.js";
import { COVERING } from "./chrome-layout.js";
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
const approveBtn = el("button", "lf-btn primary lf-signoff");
approveBtn.title = "Approve this work; the page stays open for follow-up";
// The page's decision is not actionable until the page itself is present. Discussion chrome
// stays live during replay, but approving hidden authored content would decide a version
// the reader has not seen yet.
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
  present: false,
});
registerBannerControl({
  key: "threads",
  control: toggleBtn,
  rank: BANNER_CONTROL_RANK.threads,
});

// ---------- banner ----------
const TONE = {
  working: "working",
  handling: "working",
  queued: "away",
  picked_up: "away",
  listening: "listening",
  stalled: "away",
  away: "away",
  unheld: "",
  unattended: "",
  closed: "",
};
export const toneFor = (kind) => TONE[kind];
// The judgment's third seat. A reader keeps a leaf in a tab for days and looks at
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
// declares. Refused rather than defaulted, as the theme's shadow block is: a mark with
// no lf-tone leaves a tab that never changes, which is a status readout that silently
// isn't one.
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
// announcements report that explanation only when the kind changes, not on every poll.
let saidKind;
const presentStatus = ({ kind, tone, summary, explanation, publication = null }) => {
  let publicationModel = null;
  if (publication) {
    // A publication's introduction and install link remain an ordinary reading row.
    // Links never become children of the status disclosure button.
    const [said, installs] = publicationWords(publication);
    explanation = said + installs;
    publicationModel = Object.freeze({
      copy: said,
      install: installs,
      installUrl: publication.install_url,
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
  const changed = saidKind !== undefined && saidKind !== kind;
  saidKind = kind;
  if (changed) announce(explanation);
};
// The developer preview's identity: which checkout is serving this page, and a press to
// copy the whole diagnostic. It is the banner's least-used control, so it stays behind
// the overflow door at every width instead of adding a permanent chip to the reading row.
// The shelf still owns and measures it with every other control.
let previewMarginEntry = null;
// A checkout goes dirty and clean again while a developer works, so the chip holds the
// wider of its two spellings for the page's life rather than growing a character under
// the reader's pointer. Renewed with the row's other reservations at a breakpoint.
let previewLabels = [];
let previewDiagnostics = "";
function renderPreview(state) {
  const preview = state.preview;
  if (!preview) return;
  const kind = preview.interaction === "automation" ? "Automation" : "Preview";
  const stem = `${kind} · ${preview.checkout}${preview.commit ? `@${preview.commit}` : ""}`;
  previewLabels = preview.commit ? [stem, `${stem}+`] : [stem];
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
    previewMarginEntry.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(previewDiagnostics);
        notice("Copied preview diagnostics");
      } catch (_error) {
        notice("Couldn't copy preview diagnostics");
      }
    });
    registerBannerControl({
      key: "preview",
      control: previewMarginEntry,
      rank: BANNER_CONTROL_RANK.preview,
      alwaysFolded: true,
    });
    reserveBannerControls();
  }
  previewMarginEntry.textContent = label;
  previewMarginEntry.title = `${preview.example} · started ${preview.started} · copy diagnostics`;
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
  agent,
  dated,
  shortDate,
  detail,
  kind,
  obligations,
  pending,
  quiet,
  saved,
  total,
}) {
  const savedSummary = total ? ` · ${total} saved` : "";
  const updates = `${obligations} update${obligations === 1 ? "" : "s"}`;
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
  if (kind === "working")
    return [`${agent} working`, `${agent} is working${detail ? " — " + detail : ""}`];
  if (kind === "handling")
    return [`${agent} handling ${updates}`, `${agent} is handling ${updates}`];
  if (kind === "queued")
    return [
      `${updates} queued for ${agent}`,
      `${updates}${obligations === 1 ? " is" : " are"} queued for ${agent}`,
    ];
  if (kind === "picked_up")
    return [
      `${agent}’s turn ended${savedSummary}`,
      `${agent} picked up ${updates}, but that turn ended. ${saved}`,
    ];
  // A declared request tells the reader what to do. Preserve it on the row when
  // no pending input supersedes it; a generic attendance label would lose that cue.
  if (kind === "listening") {
    const awaits = `${agent} awaits — ${detail || "select text to comment"}`;
    return pending
      ? [
          `${agent} listening${savedSummary}`,
          `${saved} ${agent} is listening${detail ? " — " + detail : ""}.`,
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
    sessionReferenceElement.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(runtime.sessionReference);
        notice("Copied session reference");
      } catch (_error) {
        notice("Couldn't copy session reference");
      }
    });
    registerBannerControl({
      key: "session",
      control: sessionReferenceElement,
      rank: BANNER_CONTROL_RANK.session,
      alwaysFolded: true,
    });
  }
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
  const [summary, text] = statusWords({
    agent: agentName(),
    dated,
    shortDate: dropped
      ? `${agentName()}’s turn ended ${ago(state.turn_closed)}`
      : `${agentName()} last checked in ${ago(activity.ts)}`,
    detail,
    kind,
    obligations: activity.count,
    total: activity.counts.total,
    pending: activity.counts.pending,
    quiet,
    saved,
  });
  let explanation =
    kind === "working" && activity.ts ? `${text} (${ago(activity.ts)})` : text;
  if (kind === "working" && activity.counts.queued)
    explanation += `. ${activity.counts.queued} more update${activity.counts.queued === 1 ? " is" : "s are"} queued.`;
  presentStatus({ kind, tone: TONE[kind], summary, explanation });
}

export const renderStatus = clocked(document.body, renderStatusNow);

// Sign-off is the page's decision, not standing chrome: the approve button is offered only
// when the version declares <meta name="lf-review" content="sign-off"> — a plan or
// proposed change seeking assent. An informational page takes comments only, and
// nothing stands in the button's place there. A neutral "End leaf" did once, and it
// ended nothing it named: the server went on serving, the watcher went on waiting,
// the status was untouched, and the agent side still finished at `leaf status idle`.
// So the one control a page that asks nothing put in front of its reader offered
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
  foldShelf();
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

// The controls that rewrite their own words hold the widest of them, measured in the
// face and padding the banner is using now (see the stylesheet's banner comment). The
// covering row deliberately spends less horizontal padding than the wide one, so its
// media-query transition has to renew these measurements in both directions; an inline
// minimum measured once on a desk would otherwise make that responsive padding inert.
// The counters hold the widest they reach anywhere below a thousand, so no count they
// write can move them — a page with a thousand open threads, or a machine with a thousand
// live pages, is not one anyone hands a user.
//
// Every control stands on the row while this runs. A control measures its own words in
// its own live face, and inside the shut menu the fold may have put it in there is no
// box to measure: every word comes back zero and the floor with it. The fold is asked
// again at the end, against the reservations this just took.
// Asked at use rather than as this module evaluates: chrome-layout.js imports this
// module back, so its constants are not readable here yet.
let coveringRow = null;
const covering = () => (coveringRow ??= matchMedia(COVERING));
// The breakpoint the reservations were last measured at, so a crossing renews them.
let reservedCovering = null;
function reserveBannerControlWidths() {
  if (signoff) reserve(approveBtn, ["Approve version", "✓ Version approved"]);
  if (sessionReferenceElement)
    reserve(sessionReferenceElement, [sessionReferenceLabel]);
  if (previewMarginEntry) reserve(previewMarginEntry, previewLabels);
  // News keeps one readable control while it changes words. The row folds rather than
  // clips, so no control has to collapse into an illegible pressure release.
  reserveVersionControls();
  reserve(toggleBtn, ["Threads", "Threads (999)"]);
  reserve(asksBtn, ["Asks 999/999"]);
  reserve(othersBtn, ["All leaves (999)"]);
  reservedCovering = covering().matches;
}
export function reserveBannerControls() {
  measureBannerControls(reserveBannerControlWidths);
}

// The fold chrome-layout.js asks for: renew the reservations for the breakpoint the row
// is at, then fold what the row cannot hold.
//
// The reservations are measured in the padding the current breakpoint gives the row's
// controls, and the fold reads them to decide what the row can hold — so they have to be
// this breakpoint's before anything is measured against them. A crossing is two events, a
// resize and a media query change, and the platform does not order them against each
// other: a fold running on the resize measured the narrow row against the widths the
// window it had just left reserved, folded a control the narrow row had room for, handed
// the reader the door it went behind, and then had the renewal behind it take that door
// away with the reader still standing on it. Renewed here, at the head of the one layout
// pass, the renewal is the crossing's first act whichever event arrives first.
export function foldBannerRow() {
  currentBannerReservations();
  foldShelf();
}
function currentBannerReservations() {
  if (reservedCovering !== covering().matches) reserveBannerControls();
}

let approving = false;

export function paintApproval(pendingApprovals, unansweredAsks = []) {
  const approved = [
    ...(runtime.browser?.conversation?.done ?? []),
    ...pendingApprovals,
  ].some(
    (e) =>
      e.kind === "done" &&
      e.revision === runtime.currentRevision &&
      e.version === runtime.currentStamp,
  );
  // The word and the title turn over together. The title read "Approve this work; the
  // page stays open for follow-up" whether or not the work had been approved, so the one
  // surface that could have told a reader what pressing it would do next went on
  // describing a press they had already made. Approved, it says the state and the way
  // out of it, which is `z` like every other reader gesture.
  approvalFace.present(
    Object.freeze({
      disabled:
        !signoff ||
        approving ||
        runtime.currentStamp === null ||
        !document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented) ||
        unansweredAsks.length > 0 ||
        approved,
      text: approved ? "✓ Version approved" : "Approve version",
      title: approved
        ? "Approved. Press z to take it back while it is still your last gesture"
        : unansweredAsks.length
          ? "Answer every Ask before approving this work"
          : "Approve this work; the page stays open for follow-up",
    }),
  );
  repaint();
}
