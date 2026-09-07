/* This module owns banner wording, tone, tab-icon paint, and announcing a status kind
 * that has changed. */
import { ago, clocked } from "./presence.js";
import { el, reserve } from "./widget-elements.js";
import { agentName, runtime } from "./context.js";
import {
  bannerActions,
  foldShelf,
  overflowBtn,
  overflowMenu,
  showNews,
  unfoldShelf,
} from "./banner-shelf.js";
import { latestChip, versionBtn, versionLabels } from "./version.js";
import { asksBtn, othersBtn } from "./trays.js";
import { COVERING, syncLayout } from "./chrome-layout.js";
import { needsBtn } from "./conversation/panel.js";
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";
import { post } from "./outbox.js";
import { paintHere } from "./keyboard/scopes.js";
import { announce, notice, noticeEl } from "./notifications.js";

export const banner = el("header", "lf-ui lf-banner");
export const dot = el("span", "lf-dot");
const statusText = el("span", "lf-status-text", "Connecting…");
// The line's momentary other words (notifications.js): a gesture recorded, a version
// arrived, a send refused. Seated after the line it stands in for, so the row holds
// one sentence at a time.
const bannerStatus = el("div", "lf-banner-status");
bannerStatus.append(dot, statusText, noticeEl);

export const toggleBtn = el(
  "button",
  "lf-btn lf-workspace lf-threads-toggle",
  "Threads",
);
toggleBtn.title = "Show or hide the thread panel";
toggleBtn.setAttribute("aria-expanded", "false");
const approveBtn = el("button", "lf-btn primary lf-signoff", "Approve version");
approveBtn.title = "Approve this work; the page stays open for follow-up";
// The page's decision is not actionable until the page itself is present. Discussion chrome
// stays live during replay, but approving hidden authored content would decide a version
// the reader has not seen yet.
approveBtn.disabled = true;

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
  href: "/icon.svg",
});
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
  const response = await fetch("/icon.svg");
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
// One writer for the dot, the line, the tab and the live region, offline included: null
// is the poll saying it couldn't reach the server, not a second function's own
// rendering. The line wins the row's width now and wraps to two, so what a narrow
// window still clips is a hover away, the way the version chooser's label is. Written
// every time rather than only when the box clips, because whether it does is a fact
// about the rendering and nothing here reads that back.
//
// The live region is the fourth seat and the one that must not be written every time.
// This line is rewritten on every poll — an age moving, a count turning over, a detail
// rephrased — and a region repeating all of that is a page talking over the reader it
// is talking to. What is worth interrupting for is the kind changing: work starting, a
// turn ending, the server going and coming back. What it says then is the banner's own
// sentence, so what is heard and what is on the row are one line rather than two
// accounts of it. The first reading is the page arriving rather than a change in it,
// and arriving is the document's own announcement.
let saidKind;
const showStatus = (kind, tone, ...parts) => {
  dot.className = "lf-dot" + (tone ? " " + tone : "");
  statusText.textContent = "";
  statusText.append(...parts);
  statusText.title = statusText.textContent;
  paintTab();
  const changed = saidKind !== undefined && saidKind !== kind;
  saidKind = kind;
  if (changed) announce(statusText.textContent);
};
// A reload the page has decided on its own: a layer that has moved under it, or a
// version it could not show. The reader is looking at a page that is about to go, and a
// tab reloading with nothing said is the page appearing to lose their place for no
// reason. One line, in the seat the rest of the banner's news arrives in, said out loud
// as well — a reload is exactly the moment a reader not watching the banner needs
// telling, and there is no kind here to have changed.
export function sayLine(text) {
  showStatus(saidKind, "", text);
  announce(text);
}
let previewButton = null;
let previewDiagnostics = "";
function renderPreview(state) {
  const preview = state.preview;
  if (!preview) return;
  const commit = preview.commit ? `@${preview.commit}${preview.dirty ? "+" : ""}` : "";
  const kind = preview.interaction === "automation" ? "Automation" : "Preview";
  const label = `${kind} · ${preview.checkout}${commit}`;
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
  if (!previewButton) {
    previewButton = el("button", "lf-btn lf-preview", label);
    previewButton.type = "button";
    previewButton.setAttribute("aria-label", "Copy preview diagnostics");
    previewButton.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(previewDiagnostics);
        notice("Copied preview diagnostics");
      } catch (_error) {
        notice("Couldn't copy preview diagnostics");
      }
    });
    statusText.before(previewButton);
  }
  previewButton.textContent = label;
  previewButton.title = `${preview.example} · started ${preview.started} · copy diagnostics`;
}
function renderStatusNow(state) {
  if (state instanceof Error) {
    showStatus("broken", "offline", "Page couldn't apply current state — reload");
    return;
  }
  if (state === null) {
    showStatus(
      "unreachable",
      "offline",
      "Server offline — reconnecting. Keep this page open so pending changes can send.",
    );
    return;
  }
  renderPreview(state);
  if (state.example) {
    const install = el("a", "lf-example-install", "Install Leaf");
    install.href = state.example.install_url;
    showStatus(
      "unattended",
      TONE.unattended,
      `This is an example on the Leaf website. ${state.example.agent} replies here, but cannot edit this page. `,
      install,
    );
    return;
  }
  const { activity } = state;
  const { kind, quiet, dropped, detail } = activity;
  const obligations = activity.count;
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
  let text = "",
    showAge = false;
  if (kind === "closed") text = "Leaf closed";
  else if (kind === "unattended")
    // No agent named and no pickup promised, which is the whole difference from
    // `unheld` below: there is nobody to name and nothing coming. What the reader can
    // still do is everything — the page works, it just works alone — so the line says
    // where their gestures go rather than that they are saved for someone.
    text = "Nobody is behind this page. What you do here stays in this browser.";
  else if (kind === "unheld")
    // No agent is named, because which one picks the page up next is not a fact this
    // page holds — only that the log is there for whichever does.
    text = `No session holds this page. ${saved} It picks up again when a session does.`;
  else if (kind === "working") {
    showAge = Boolean(activity.ts);
    text = `${agentName()} is working${detail ? " — " + detail : ""}`;
  } else if (kind === "handling") {
    text = `${agentName()} is handling ${obligations} update${obligations === 1 ? "" : "s"}`;
  } else if (kind === "queued") {
    text = `${obligations} update${obligations === 1 ? " is" : "s are"} queued for ${agentName()}`;
  } else if (kind === "picked_up") {
    text = `${agentName()} picked up ${obligations} update${obligations === 1 ? "" : "s"}, but that turn ended. ${saved}`;
  } else if (kind === "listening") {
    // Attendance is half the news; the other half is what the page wants back. The
    // Asks count beside it says how many things are unanswered and nothing about what
    // any of them is, so the claim's detail says that here in the agent's own words,
    // the way a `working` claim's says what it is doing. With nothing declared it is
    // the standing instruction, which is what a page asking nothing wanted anyway.
    //
    // With no pending update, "awaits" states the stance a live watcher supports and
    // uses the registry's word for a standing Ask for the reader (x-awaits). Once a
    // reader move is pending, the same listening evidence remains primary while the
    // words lead with what was saved.
    text = activity.counts.pending
      ? `${saved} ${agentName()} is listening${detail ? " — " + detail : ""}.`
      : `${agentName()} awaits — ${detail || "select text to comment"}`;
  } else if (kind === "stalled") {
    // The claim stands, dated, with no remedy attached: a watcher is live, so the
    // reader's next word reaches the agent without anyone touching a terminal. What
    // they are owed is the age, which is the one thing they cannot see for themselves
    // and the whole of what separates a delegate mid-answer from a dropped thread. It
    // is spoken in the same words the branch below uses for the same silence, rather
    // than in the muted parenthesis a live `working` claim wears: there the age is a
    // footnote to news, and here it is the news.
    text = `${dated}${detail ? ": " + detail : ""}. ${saved}`;
  } else {
    // Somebody is behind the page and isn't attending: say which and what to do. A
    // long silence means Claude lost the thread; a recent check-in means it is
    // mid-turn and the next one collects.
    const [why, how] = quiet
      ? [`${dated}.`, "Nudge it in the terminal."]
      : [`${agentName()} isn't watching right now.`, "It picks them up next turn."];
    text = `${why} ${saved} ${how}`;
  }
  const line = [text];
  if (showAge)
    line.push(
      " ",
      Object.assign(el("span", "lf-age"), { textContent: `(${ago(activity.ts)})` }),
    );
  showStatus(kind, TONE[kind], ...line);
}

export const renderStatus = clocked(document.body, renderStatusNow);

// Sign-off is the page's decision, not standing chrome: the approve button exists only
// when the version declares <meta name="lf-review" content="sign-off"> — a plan or
// proposed change seeking assent. An informational page takes comments only, and
// nothing stands in the button's place there. A neutral "End leaf" did once, and it
// ended nothing it named: the server went on serving, the watcher went on waiting,
// the status was untouched, and the agent side still finished at `leaf status idle`.
// So the one control a page that asks nothing put in front of its reader offered
// them an ending it could not deliver. The declaration rides the document, so a
// pinned older version keeps its own decision.
let signoffDeclared =
  document.querySelector('meta[name="lf-review"]')?.content === "sign-off";

let signoff = signoffDeclared && runtime.currentStamp !== null;
export const isSignoffDeclared = () => signoffDeclared;

// One order, at every width. An edge's address sits at that edge: All leaves is the first
// address beside the tray it opens on the left, and approval and Threads finish beside the
// panel they open on the right. The row used to turn round at the covering breakpoint,
// which carried Threads from one end of the banner to the other and swapped the page's one
// committing press across it — so a reader who learned this row on a laptop had to learn
// it again on a phone, and a press they were reaching for was somewhere else. What a
// narrow window changes now is how many of these addresses stand on the row at once; the
// rest fold into the row's own menu, in this same order (`foldShelf`).
//
// This is DOM order rather than CSS `order`, so the tab route says the same thing the row
// draws. Reordering existing nodes can briefly drop native focus; put it back without
// moving the page, and hand it to the menu's door where the fold has taken the address
// the reader was standing on.
function arrangeBannerControls() {
  const focused = document.activeElement;
  const edges = new Set([toggleBtn, approveBtn, othersBtn]);
  // Registry-declared blanket answers can join the middle of this row after boot, and a
  // folded address is still on it. Preserve every such control in its standing relative
  // order while moving only the edge-owned addresses.
  const middle = [...overflowMenu.children, ...bannerActions.children].filter(
    (control) => control !== overflowBtn && !edges.has(control),
  );
  const controls = [othersBtn, ...middle, ...(signoff ? [approveBtn] : []), toggleBtn];
  bannerActions.append(...controls);
  foldShelf();
  if (
    focused?.isConnected &&
    controls.includes(focused) &&
    document.activeElement !== focused
  )
    (overflowMenu.contains(focused) ? overflowBtn : focused).focus({
      preventScroll: true,
    });
}

// The banner's row, mounted once the version chooser and the trays exist: the invariant
// middle first, then the edge families around it (arrangeBannerControls).
export function mountBanner() {
  for (const control of [asksBtn, othersBtn]) showNews(control, false);
  // Seed the invariant middle once; arrangeBannerControls puts the two edge families
  // around it and later preserves any registry-declared controls added among these three.
  bannerActions.append(latestChip, asksBtn, versionBtn);

  arrangeBannerControls();
  banner.append(bannerStatus, bannerActions);
}

// Sign-off belongs to the authored version, while the control belongs to the live
// chrome that survives one. A soft activation can therefore add or remove the same
// control; rebuilding the banner would throw away focus and every reserved neighbour.
export function stateSignoff(next) {
  signoffDeclared = next;
  const shown = signoffDeclared && runtime.currentStamp !== null;
  if (shown === signoff) return;
  signoff = shown;
  if (!signoff) approveBtn.remove();
  arrangeBannerControls();
  if (signoff) {
    reserve(approveBtn, ["Approve version", "✓ Version approved"]);
    paintApproval();
  }
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
// Every address stands on the row while this runs. A control measures its own words in
// its own live face, and inside the shut menu the fold may have put it in there is no
// box to measure: every word comes back zero and the floor with it. The fold is asked
// again at the end, against the reservations this just took.
// Asked at use rather than as this module evaluates: chrome-layout.js imports this
// module back, so its constants are not readable here yet.
let coveringRow = null;
const covering = () => (coveringRow ??= matchMedia(COVERING));
// The breakpoint the reservations were last measured at, so a crossing renews them.
let reservedCovering = null;
export function reserveBannerControls() {
  unfoldShelf();
  if (signoff) reserve(approveBtn, ["Approve version", "✓ Version approved"]);
  // News keeps one readable address while it changes words. The row folds rather than
  // clips, so no control has to collapse into an illegible pressure release.
  reserve(latestChip, [
    "New page available → open v999",
    "Latest edit couldn't be shown",
  ]);
  reserve(versionBtn, versionLabels());
  reserve(toggleBtn, ["Threads", "Threads (999)"]);
  reserve(needsBtn, ["Waiting on you", "Waiting on you (999)"]);
  reserve(asksBtn, ["Asks 999/999"]);
  reserve(othersBtn, ["All leaves (999)"]);
  foldShelf();
  reservedCovering = covering().matches;
}

// The fold chrome-layout.js asks for: renew the reservations for the breakpoint the row
// is at, then fold what the row cannot hold.
//
// The reservations are measured in the padding the current breakpoint gives the row's
// controls, and the fold reads them to decide what the row can hold — so they have to be
// this breakpoint's before anything is measured against them. A crossing is two events, a
// resize and a media query change, and the platform does not order them against each
// other: a fold running on the resize measured the narrow row against the widths the
// window it had just left reserved, folded an address the narrow row had room for, handed
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

export function paintApproval() {
  const approved = (runtime.browser?.conversation?.done ?? []).some(
    (e) =>
      e.kind === "done" &&
      e.revision === runtime.currentRevision &&
      e.version === runtime.currentStamp,
  );
  approveBtn.disabled =
    approving ||
    runtime.currentStamp === null ||
    !document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented) ||
    approved;
  approveBtn.textContent = approved ? "✓ Version approved" : "Approve version";
  // The word and the title turn over together. The title read "Approve this work; the
  // page stays open for follow-up" whether or not the work had been approved, so the one
  // surface that could have told a reader what pressing it would do next went on
  // describing a press they had already made. Approved, it says the state and the way
  // out of it, which is `z` like every other reader gesture.
  approveBtn.title = approved
    ? "Approved. Press z to take it back while it is still your last gesture"
    : "Approve this work; the page stays open for follow-up";
  paintHere();
}

approveBtn.onclick = async () => {
  if (approving) return;
  approving = true;
  approveBtn.setAttribute("aria-busy", "true");
  paintApproval();
  try {
    await post({
      kind: "done",
      revision: runtime.currentRevision,
      version: runtime.currentStamp,
      text: "Looks good",
    });
  } finally {
    approving = false;
    approveBtn.removeAttribute("aria-busy");
    paintApproval();
  }
};
