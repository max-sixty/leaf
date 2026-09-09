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
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";
import { post } from "./outbox.js";
import { paintHere } from "./keyboard/scopes.js";
import { announce, notice, noticeEl } from "./notifications.js";

export const banner = el("header", "lf-ui lf-banner");
banner.id = "lf-banner";
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
// The developer preview's identity: which checkout is serving this page, and a press to
// copy the whole diagnostic. It is the banner's least-used address, so it stays behind
// the address door at every width instead of adding a permanent chip to the reading row.
// The shelf still owns and measures it with every other address.
let previewMarginElement = null;
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
  if (!previewMarginElement) {
    previewMarginElement = el("button", "lf-btn lf-preview", label);
    previewMarginElement.type = "button";
    previewMarginElement.dataset.lfAlwaysFold = "1";
    previewMarginElement.setAttribute("aria-label", "Copy preview diagnostics");
    previewMarginElement.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(previewDiagnostics);
        notice("Copied preview diagnostics");
      } catch (_error) {
        notice("Couldn't copy preview diagnostics");
      }
    });
    // Seated by the same writer that seats every other address, so the row reads in one
    // order and the fold knows about it; then measured with the whole run standing, then
    // folded against what it measured. The unfold is the measurement's precondition, not
    // tidiness: `arrangeBannerControls` ends in a fold, this chip is seated first so it
    // is the first thing folded, and inside a shut popover every word measures zero — so
    // reserving here without it sets a floor of 0px and the chip grows by a glyph, on the
    // row, the first time the checkout goes dirty. `reserveBannerControls` opens with the
    // same call for the same reason.
    arrangeBannerControls();
    unfoldShelf();
    reserve(previewMarginElement, previewLabels);
    foldShelf();
  }
  previewMarginElement.textContent = label;
  previewMarginElement.title = `${preview.example} · started ${preview.started} · copy diagnostics`;
}
// The two lines the page cannot reach through its own state, said here because the
// reservation below has to know them as well as the reading does.
const OFFLINE_LINE =
  "Server offline — reconnecting. Keep this page open so pending changes can send.";
const BROKEN_LINE = "Page couldn't apply current state — reload";
// A published page's own line, in the two parts it is written in: the sentence, and the
// link that ends it. Said once, so what the row measures is what the row says. The two
// subjects are the two kinds of published page, and the longer of them is what the room
// is measured against, since which one this page is arrives with its first state.
const publicationWords = (published) => [
  `${
    published.kind === "example"
      ? "This is an example on the Leaf website."
      : "This website is a Leaf page."
  } ${published.agent} replies and revises this private copy. `,
  "Install Leaf",
];

// The words one reading is written in, from the facts that decide them. They are a
// writer of their own rather than a chain inside the reading because the reservation
// below asks this same writer for every line this page could say: what the row keeps
// room for and what the row says are then one set of words rather than two lists to
// keep in step.
function statusWords({
  agent,
  dated,
  detail,
  kind,
  obligations,
  pending,
  quiet,
  saved,
}) {
  if (kind === "closed") return "Leaf closed";
  // No agent named and no pickup promised, which is the whole difference from
  // `unheld` below: there is nobody to name and nothing coming. What the reader can
  // still do is everything — the page works, it just works alone — so the line says
  // where their gestures go rather than that they are saved for someone.
  if (kind === "unattended")
    return "Nobody is behind this page. What you do here stays in this browser.";
  // No agent is named, because which one picks the page up next is not a fact this
  // page holds — only that the log is there for whichever does.
  if (kind === "unheld")
    return `No session holds this page. ${saved} It picks up again when a session does.`;
  if (kind === "working") return `${agent} is working${detail ? " — " + detail : ""}`;
  if (kind === "handling")
    return `${agent} is handling ${obligations} update${obligations === 1 ? "" : "s"}`;
  if (kind === "queued")
    return `${obligations} update${obligations === 1 ? " is" : "s are"} queued for ${agent}`;
  if (kind === "picked_up")
    return `${agent} picked up ${obligations} update${obligations === 1 ? "" : "s"}, but that turn ended. ${saved}`;
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
  if (kind === "listening")
    return pending
      ? `${saved} ${agent} is listening${detail ? " — " + detail : ""}.`
      : `${agent} awaits — ${detail || "select text to comment"}`;
  // The claim stands, dated, with no remedy attached: a watcher is live, so the
  // reader's next word reaches the agent without anyone touching a terminal. What
  // they are owed is the age, which is the one thing they cannot see for themselves
  // and the whole of what separates a delegate mid-answer from a dropped thread. It
  // is spoken in the same words the branch below uses for the same silence, rather
  // than in the muted parenthesis a live `working` claim wears: there the age is a
  // footnote to news, and here it is the news.
  if (kind === "stalled") return `${dated}${detail ? ": " + detail : ""}. ${saved}`;
  // Somebody is behind the page and isn't attending: say which and what to do. A
  // long silence means Claude lost the thread; a recent check-in means it is
  // mid-turn and the next one collects.
  const [why, how] = quiet
    ? [`${dated}.`, "Nudge it in the terminal."]
    : [`${agent} isn't watching right now.`, "It picks them up next turn."];
  return `${why} ${saved} ${how}`;
}

// Whether this page is published, once it has said so, because the line a published
// page writes is longer than any a reader's own page can reach and the room it needs
// is measured with the rest.
let publication = null;

// The public website support handle is available on demand with the banner's other
// low-frequency addresses. It does not compete with the page's live status sentence.
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
    sessionReferenceElement.dataset.lfAlwaysFold = "1";
    sessionReferenceElement.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(runtime.sessionReference);
        notice("Copied session reference");
      } catch (_error) {
        notice("Couldn't copy session reference");
      }
    });
    arrangeBannerControls();
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
    showStatus("broken", "offline", BROKEN_LINE);
    return;
  }
  if (state === null) {
    showStatus("unreachable", "offline", OFFLINE_LINE);
    return;
  }
  renderPreview(state);
  publication = state.publication ?? null;
  // Before the words, because the row folds against the room they will need: a page
  // learning its agent's name, or that it is published, is a page whose longest line has
  // just changed, and the addresses beside it are what pay for the difference.
  if (reserveStatusRoom()) foldShelf();
  if (publication) {
    const [said, installs] = publicationWords(publication);
    const install = el("a", "lf-publication-install", installs);
    install.href = publication.install_url;
    showStatus("unattended", TONE.unattended, said, install);
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
  const text = statusWords({
    agent: agentName(),
    dated,
    detail,
    kind,
    obligations: activity.count,
    pending: activity.counts.pending,
    quiet,
    saved,
  });
  const showAge = kind === "working" && Boolean(activity.ts);
  const line = [text];
  if (showAge)
    line.push(
      " ",
      Object.assign(el("span", "lf-age"), { textContent: `(${ago(activity.ts)})` }),
    );
  showStatus(kind, TONE[kind], ...line);
}

export const renderStatus = clocked(document.body, renderStatusNow);

// ---------- the room the sentence keeps ----------
// Every line this page can write about its own state. The writer chooses its words from
// seven facts, so every one of them is a list here and the lines are the whole cross of
// them, rather than one value per fact that somebody judged the widest. Judging them one
// at a time is how the last line went missing: `saved` was pinned at its counted
// spelling, and the spelling for a page with no count — "Your comments are saved." — is
// wider, so a page nobody had commented on wrapped to three lines and lost the remedy off
// the end of the clamp. Which fact makes a line widest is not a thing to reason about
// per fact; the cross is what measures it.
//
// Most of these repeat. A kind that names no count writes the same line for all three
// savings, and the two thousand readings collapse to a couple of dozen distinct lines.
// What the cross buys is that nothing is left out by a fact nobody thought to vary, and
// a fact that gains a spelling gains it here beside the writer's own branch.
//
// `detail` is the one fact with a single value, and that is not a judgment: those are the
// agent's own words, they arrive long after any reservation could be taken, and the clamp
// and the title are what carry them (see the stylesheet, beside the clamp).
function pageLines() {
  const agent = agentName();
  // The widest word each shape of `ago` writes (presence.js), which is the largest count
  // each of them reaches — the same convention the row's counters are reserved at.
  const ages = ["just now", "59m ago", "23h ago", "999d ago"];
  const facts = {
    agent: [agent],
    dated: ages.flatMap((age) => [
      `${agent} left this when its turn ended ${age}`,
      `${agent} last checked in ${age}`,
    ]),
    detail: [""],
    kind: Object.keys(TONE),
    obligations: [1, 999],
    pending: [0, 1],
    quiet: [false, true],
    saved: ["Your comments are saved.", "1 update is saved.", "999 updates are saved."],
  };
  const names = Object.keys(facts);
  const lines = [OFFLINE_LINE, BROKEN_LINE];
  const cross = (depth, chosen) => {
    if (depth === names.length) {
      lines.push(statusWords(chosen));
      return;
    }
    for (const value of facts[names[depth]])
      cross(depth + 1, { ...chosen, [names[depth]]: value });
  };
  cross(0, {});
  if (publication) lines.push(publicationWords(publication).join(""));
  return [...new Set(lines)];
}

// The narrowest box those lines all fit the clamp in — the floor the stylesheet's cap
// hands the addresses as the room they may not have.
//
// Measured, because what it has to cover is the width a wrapped line of these words
// takes in the face the row is set in, and no count of characters tracks that: a `ch`
// is the advance of a zero, and how many of them a sentence takes is a property of the
// face rather than of its size. Two lines of the longest of these take 37.5 characters
// where `system-ui` is SF — this desk — and 40.4 where it is DejaVu, which is what the
// image CI runs on resolves it to. Stated as thirty-four it was under both, and a number
// over the second reserves on the first room the row can only find by folding an address.
// This is the question `reserve` asks of a control's words, asked of the sentence's.
//
// A copy of the sentence, seated where the sentence sits, so it is measured in the face,
// size and leading the row is actually using. The clamp is read rather than restated:
// the stylesheet gives the sentence one line on a phone and two on a desk, and the floor
// is whatever that is worth here.
function measureStatusRoom(lines) {
  const rig = statusText.cloneNode(false);
  rig.style.cssText =
    "position:absolute;left:-9999px;top:0;visibility:hidden;display:block;" +
    "-webkit-line-clamp:none";
  bannerStatus.append(rig);
  const step = parseFloat(getComputedStyle(rig).lineHeight);
  const allowed =
    Number.parseInt(getComputedStyle(statusText).webkitLineClamp, 10) || 2;
  const wrapsTo = (text, width) => {
    rig.textContent = text;
    rig.style.width = width + "px";
    return Math.round(rig.scrollHeight / step);
  };
  const unwrapped = (text) => {
    rig.textContent = text;
    rig.style.width = "max-content";
    return rig.getBoundingClientRect().width;
  };
  // Widest first, so the one line that decides the floor is the one searched for and
  // every other line is a single reading: a line that already fits what the floor
  // stands at asks nothing more of it.
  const across = new Map(lines.map((text) => [text, unwrapped(text)]));
  let floor = 0;
  for (const text of [...across.keys()].sort((a, b) => across.get(b) - across.get(a))) {
    if (floor && wrapsTo(text, floor) <= allowed) continue;
    let short = floor;
    let long = across.get(text);
    while (long - short > 0.05) {
      const between = (short + long) / 2;
      if (wrapsTo(text, between) <= allowed) long = between;
      else short = between;
    }
    floor = Math.ceil(long);
  }
  rig.remove();
  return floor;
}

// The words the standing floor was measured against, so the row is measured again when
// they change and not on every poll. Renewed outright at a breakpoint, where the row's
// type and padding move under the same words (reserveBannerControls).
let reservedWords = null;
function reserveStatusRoom() {
  if (!banner.isConnected) return false;
  // What the page supplies to those words: the name of the agent behind it, and the line
  // a published page writes. Everything else the cross varies is the writer's own and
  // cannot change under a reader, so this is the whole of what a later reading could say
  // differently — and asking it costs two string reads on a poll that would otherwise
  // build two thousand lines to find out nothing had.
  const words = `${agentName()}\n${publication ? publicationWords(publication).join("") : ""}`;
  if (words === reservedWords) return false;
  reservedWords = words;
  banner.style.setProperty("--lf-status-floor", `${measureStatusRoom(pageLines())}px`);
  return true;
}

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
// Low-frequency identifiers stand first in the complete address order and always behind
// its door. A checkout appears only in a developer preview; a session reference appears
// only on the public website.
//
// This is DOM order rather than CSS `order`, so the tab route says the same thing the row
// draws. Reordering existing nodes can briefly drop native focus; put it back without
// moving the page, and hand it to the menu's door where the fold has taken the address
// the reader was standing on.
function arrangeBannerControls() {
  const focused = document.activeElement;
  const edges = new Set([
    toggleBtn,
    approveBtn,
    othersBtn,
    sessionReferenceElement,
    previewMarginElement,
  ]);
  // Registry-declared blanket answers can join the middle of this row after boot, and a
  // folded address is still on it. Preserve every such control in its standing relative
  // order while moving only the edge-owned addresses.
  const middle = [...overflowMenu.children, ...bannerActions.children].filter(
    (control) => control !== overflowBtn && !edges.has(control),
  );
  const controls = [
    ...(sessionReferenceElement ? [sessionReferenceElement] : []),
    ...(previewMarginElement ? [previewMarginElement] : []),
    othersBtn,
    ...middle,
    ...(signoff ? [approveBtn] : []),
    toggleBtn,
  ];
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
let reserveAfterMenuCloses = false;
export function reserveBannerControls() {
  // The shelf is a stable reading while it stands open. A breakpoint can cross under
  // it, but measuring requires moving every address back onto the row; defer that move
  // until the reader closes the shelf, then renew before its next opening.
  if (overflowMenu.matches(":popover-open")) {
    reserveAfterMenuCloses = true;
    return;
  }
  unfoldShelf();
  if (signoff) reserve(approveBtn, ["Approve version", "✓ Version approved"]);
  if (sessionReferenceElement)
    reserve(sessionReferenceElement, [sessionReferenceLabel]);
  if (previewMarginElement) reserve(previewMarginElement, previewLabels);
  // News keeps one readable address while it changes words. The row folds rather than
  // clips, so no control has to collapse into an illegible pressure release.
  reserve(latestChip, [
    "New page available → open v999",
    "Latest edit couldn't be shown",
  ]);
  reserve(versionBtn, versionLabels());
  reserve(toggleBtn, ["Threads", "Threads (999)"]);
  reserve(asksBtn, ["Asks 999/999"]);
  reserve(othersBtn, ["All leaves (999)"]);
  // The sentence's own room, taken in the same face and on the same occasions as the
  // addresses' — the words have not changed, but what they set has, which is the whole
  // reason none of these is a number.
  reservedWords = null;
  reserveStatusRoom();
  foldShelf();
  reservedCovering = covering().matches;
}
overflowMenu.addEventListener("toggle", (event) => {
  if (event.newState !== "closed" || !reserveAfterMenuCloses) return;
  reserveAfterMenuCloses = false;
  reserveBannerControls();
});

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
