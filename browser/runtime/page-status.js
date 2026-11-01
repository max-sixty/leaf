/* The page status, presented by the floating panel (floating-panel.js).
 *
 * The status says how the server answered the page's latest read (`reach`) and what the
 * reading it adopted says, in the words activity-words.js gives it (`statusReading`). It
 * paints the tab's icon in its tone and announces a change after the first status
 * reading. Provisional interface readiness gives a status without establishing that
 * announcement baseline; saved state or a failed read does.
 */
import { pageStatus, statusModel } from "./activity-words.js";
import { keeps } from "./keeps.js";
import { el } from "./widget-elements.js";
import { WEBSITE_DELIVERY, runtime, runtimeResource } from "./context.js";
import { chromeRoot } from "./chrome.js";
import { announce } from "./notifications.js";
import { effect, signal, untracked } from "/runtime/framework.js";
import { agentName, readPart } from "./semantic-state.js";
import { UPGRADE } from "./presentation.js";
import { readQueues } from "./queue-api.js";
import { holdingError } from "./errors.js";

// ---------- status ----------
// Upgrade opens new comments before the buffered saved reading is applied.
const LOADING_LINE =
  "The page is ready for reading and new comments. Saved comments and choices are still loading; new comments go through once they have." +
  (WEBSITE_DELIVERY
    ? " Website examples can take longer to load their comments and choices than a usual Leaf page."
    : "");
const LOADING = Object.freeze({
  kind: "loading",
  tone: "",
  summary: "Loading comments and choices…",
  explanation: LOADING_LINE,
  adds: LOADING_LINE,
});

// Before any answer the status says nothing until upgrade has opened the page, and then
// that saved state is loading.
const reach = readPart((root) => root.reach);
const upgraded = signal(false);
// The status with its words (`statusModel`), or null before there is one to say. It is
// derived where it is read, so a presentation of it says the same words in the same tone
// and follows the same inputs; only upgrade, which is mechanical, asks each to paint.
function currentStatus() {
  const answer = reach();
  if (answer.reach === "waiting" && !upgraded.value) return null;
  const status =
    answer.reach === "waiting" ? LOADING : pageStatus(runtime.state, answer);
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
// The mark is the layer's icon.svg, composed like the theme, so a package
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
/** @type {Element | null} */
let iconMark = null;
/** @type {Map<string, string>} */
const iconUrls = new Map();
// The mark with one colour written over it. A style element appended last outranks the
// file's own rules, the dark-scheme block included, since a media query carries no
// specificity of its own. So this knows nothing about the icon beyond the class it
// promises, and a project's own mark is painted on the same terms.
/** @param {Element} mark @param {string} color */
function iconUrl(mark, color) {
  let url = iconUrls.get(color);
  if (url === undefined) {
    const svg = mark.cloneNode(true);
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
  keeps(
    tabLink,
    "href",
    iconUrl(iconMark, getComputedStyle(toneProbe).backgroundColor),
  );
}

// Announcements report the explanation when the page kind changes or current work
// begins waiting for user input or approval, not on every observed work step or poll.
/** @type {string | undefined} */
let saidKind;
/** @type {string | null | undefined} */
let saidActionableWork;
// A refused key, or a reading the page could not apply, is an error the user should see
// wherever they are (errors.js), held while the status says it, since it asks the user to
// act. An unreachable server is not: the page reconnects on its own, so the status
// reports it in its own face, and a change the user sends meanwhile holds its own error
// (delivery.js). The status announces a change of kind in its own words already.
const holdBlocked = holdingError({ announce: false });
/** @param {ReturnType<typeof currentStatus>} current */
function paintStatus(current) {
  holdBlocked(
    current && ["refused", "broken"].includes(current.status.kind)
      ? current.status.summary
      : null,
  );
  if (!current) return;
  const { status, model } = current;
  const { kind } = status;
  const actionableWork = "actionableWork" in status ? status.actionableWork : null;
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

/** Start the page status. */
export function mountPageStatus() {
  chromeRoot.append(toneProbe);
  effect(() => {
    const current = currentStatus();
    untracked(() => paintStatus(current));
  });
  document.addEventListener(
    UPGRADE,
    () => {
      upgraded.value = true;
    },
    { once: true },
  );
}
