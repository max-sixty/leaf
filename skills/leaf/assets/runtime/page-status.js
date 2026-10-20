/* The page's status and its version's approval, which the floating panel presents
 * (floating-panel.js) and the queue walk arrives at (queue-walk.js).
 *
 * The status says how the server answered the page's latest read (`reach`) and what the
 * reading it adopted says, in the words activity-words.js gives it (`statusReading`). It
 * paints the tab's icon in its tone and announces a change after the first status
 * reading. Provisional interface readiness gives a status without establishing that
 * announcement baseline; saved state or a failed read does.
 *
 * Approval is the page's decision, offered only where the version declares
 * <meta name="lf-review" content="sign-off">, a plan or proposed change seeking
 * assent (`isSignoffDeclared`). An informational page takes comments only. A neutral
 * "End leaf" once stood in its place and ended nothing it named, so nothing does. The
 * declaration rides the document, so a pinned older version keeps its own decision.
 * The presentation that shows approval registers itself (`registerApprovalPresentation`)
 * to name its control, bring the user to it, and repaint when a press or the
 * declaration changes what approval says. */
import { pageStatus, statusModel } from "./activity-words.js";
import { keeps } from "./keeps.js";
import { el } from "./widget-elements.js";
import { WEBSITE_DELIVERY, runtime, runtimeResource } from "./context.js";
import { chromeRoot } from "./chrome.js";
import { pagePresented } from "./page-paint.js";
import { announce } from "./notifications.js";
import { watchProjection } from "./projection-watch.js";
import { agentName, readPart } from "./semantic-state.js";
import { UPGRADE } from "./presentation.js";
import { readQueues } from "./queue-api.js";
import { approvalBlockingObligations } from "./obligations/model.js";
import { holdingError, raiseError } from "./errors.js";

// ---------- status ----------
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

// Before any answer the status says nothing until upgrade has opened the page, and then
// that saved state is loading.
const reach = readPart((root) => root.reach);
let upgraded = false;
// The status with its words (`statusModel`), or null before there is one to say. It is
// derived where it is read, so a presentation of it says the same words in the same tone
// and follows the same inputs; only upgrade, which is mechanical, asks each to paint.
function currentStatus() {
  const answer = reach();
  if (answer === "waiting" && !upgraded) return null;
  const status =
    answer === "waiting" ? LOADING : pageStatus(runtime.state, { reach: answer });
  return { status, model: statusModel(status, readQueues(), agentName()) };
}
export const statusReading = () => currentStatus()?.model ?? null;

// ---------- the tab's icon ----------
// The judgment's third seat. A user keeps a leaf in a tab for days and looks at six of
// them; the tab strip is the whole of what the browser shows about a page nobody has
// open, so the state that decides whether to go there belongs in it. The tone is taken
// off the leaf mark the chrome draws (`.lf-dot`, chrome.css) rather than mapped from kind
// to token again: one answer to what a tone looks like, so a project overriding --ok
// overrides the tab with it. It is a read of the theme, not of the rendering.
//
// The mark is the vendored icon.svg, the page's own asset like the theme, so a project
// can put its own there, and all the runtime does to it is paint the one element it
// declares. Refused rather than defaulted: a mark with no lf-tone leaves a tab that
// never changes, which is a status readout that silently isn't one.
const tabLink = Object.assign(document.createElement("link"), {
  rel: "icon",
  type: "image/svg+xml",
  href: runtimeResource("/icon.svg"),
});
tabLink.dataset.lfRuntime = "";
document.head.append(tabLink);
// The mark the tone is read off, which shows nothing.
const toneProbe = el("span", "lf-dot");
toneProbe.hidden = true;
toneProbe.setAttribute("aria-hidden", "true");
let iconMark = null;
const iconUrls = new Map();
// The mark with one colour written over it. A style element appended last outranks the
// file's own rules, the dark-scheme block included, since a media query carries no
// specificity of its own. So this knows nothing about the icon beyond the class it
// promises, and a project's own mark is painted on the same terms.
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
// Called from two places, because the fetch above can land after the first poll has
// already judged the page.
let tone = "";
function paintTab() {
  if (!iconMark || !toneProbe.isConnected) return;
  keeps(toneProbe, "class", tone ? `lf-dot ${tone}` : "lf-dot");
  // Written only on change: an unchanged poll must not hand the browser its icon again
  // every two seconds.
  keeps(tabLink, "href", iconUrl(getComputedStyle(toneProbe).backgroundColor));
}

// Announcements report the explanation when the page kind changes or current work
// begins waiting for user input or approval, not on every observed work step or poll.
let saidKind;
let saidActionableWork;
// A status that reaches nothing, or a reading the page could not apply, is an error the
// user should see wherever they are (errors.js), held while the status says it. The
// status announces a change of kind in its own words already.
const holdUnreached = holdingError({ announce: false });
function paintStatus() {
  const current = currentStatus();
  holdUnreached(
    ["unreachable", "refused", "broken"].includes(current?.status.kind)
      ? current.status.summary
      : null,
  );
  if (!current) return;
  const { status, model } = current;
  const { kind, actionableWork = null } = /** @type {any} */ (status);
  tone = model.tone;
  paintTab();
  // Interface readiness precedes the first saved reading. It gives a usable status, but
  // only a state or failed read establishes the announcement baseline.
  if (kind === "loading") return;
  const changed =
    saidKind !== undefined &&
    (saidKind !== kind ||
      (actionableWork !== null && actionableWork !== saidActionableWork));
  saidKind = kind;
  saidActionableWork = actionableWork;
  if (changed) announce(model.explanation);
}

// ---------- approval ----------
/** @typedef {import("../../../../build/browser/contract.js").AuthoredMeta} AuthoredMeta */
/** @type {keyof AuthoredMeta} */
const REVIEW = "lf-review";
/** @type {AuthoredMeta[typeof REVIEW]} */
const SIGN_OFF = "sign-off";
export const isSignoffDeclared = () =>
  /** @type {HTMLMetaElement | null} */ (
    document.querySelector(`meta[name="${REVIEW}"]`)
  )?.content === SIGN_OFF;

let signoff = false;
let approving = false;
let approveVersion = null;
let presentation = null;
// The page's decision is not actionable until the page itself is present. Discussion
// stays live during replay, but approving hidden authored content would decide a version
// the user has not seen yet.
const AWAITING_STATE = "Approval waits until this page has read its current state";

/** The presentation of approval: `target()` its control, `arrive()` bringing the user to
 * it, and `repaint()` after a mechanical change to what approval says. */
export function registerApprovalPresentation(next) {
  presentation = next;
}
export const presentedApproval = () => presentation;
// The page presenting changes whether a press would approve.
export const paintApproval = () => presentation?.repaint();
// The queue arrives at the one approval control shown.
export const approvalTarget = () => (signoff ? (presentation?.target() ?? null) : null);

// Whether the user has approved the shown version.
const versionApproved = readPart((root) =>
  root.effective.obligations.all.some(
    (item) => item.source.kind === "approval" && item.status === "answered",
  ),
);

// What Approval says now: its `text`, why a press is refused (`reason`, null where it
// approves) and whether it is `approved`; null where the page asks no sign-off. The
// asks holding approval are null before the page has read the log and so cannot say
// which those are. Approved, it says the state and the way out of it, which is `z`
// like every other user gesture.
export const approvalReading = () => {
  if (!signoff) return null;
  const approved = versionApproved();
  const blockingObligations = approvalBlockingObligations();
  const reason = approved
    ? "Approved. Press z to undo while approval is still the latest update"
    : runtime.currentStamp === null
      ? "There is no stamped version to approve yet"
      : !pagePresented() || blockingObligations === null
        ? AWAITING_STATE
        : blockingObligations.length
          ? "Answer every open widget before approving this work"
          : null;
  return {
    text: approved ? "✓ Version approved" : "Approve version",
    // A press already in flight is refused silently: its busy state says so.
    reason: reason ?? (approving ? "Approving this version" : null),
    approved,
  };
};

// The one approval press, whichever control the user made it on. A refused press
// raises its reason as an error (errors.js).
export async function approve() {
  if (approving || !approveVersion) return;
  const reason = approvalReading()?.reason;
  if (reason) {
    raiseError(reason);
    return;
  }
  approving = true;
  presentation?.repaint();
  try {
    await approveVersion();
  } finally {
    approving = false;
    presentation?.repaint();
  }
}

// Sign-off belongs to the authored revision, and the head it rides in is the only copy
// of it: a revision this document takes on in place brings its own, so the reading is
// taken from the document each time rather than kept beside it.
export function stateSignoff(next) {
  if (next === signoff) return;
  signoff = next;
  presentation?.repaint();
}

/** Start the status and approval: `approveVersion` posts the approval. */
export function mountPageStatus({ approveVersion: post }) {
  approveVersion = post;
  signoff = isSignoffDeclared();
  chromeRoot.append(toneProbe);
  const statusWatch = watchProjection(document.body, paintStatus);
  document.addEventListener(
    UPGRADE,
    () => {
      upgraded = true;
      statusWatch.refresh();
    },
    { once: true },
  );
}
