/* Leaf runtime, loaded via <script type="module" src="/leaf.js">: the boot module. It
 * imports every runtime owner and runs the boot sequence below. skills/leaf/assets/CLAUDE.md
 * names each owner's responsibility and the rule against reading one while it evaluates. */

import chromeSheet from "./runtime/chrome.css" with { type: "css" };
import { mountLayout, syncLayout } from "./runtime/chrome-layout.js";

import { declareLeavesKeys, leavesOffered } from "./runtime/live-leaves.js";

import { fabBar, openDraft, pendingComposer } from "./runtime/composing/selection.js";
import { updateFab, wireFabInput } from "./runtime/composing/surface.js";

import { containedPage, runtime } from "./runtime/context.js";
import { promoteDeferredModals } from "./runtime/deferred-modals.js";
import { reportPageError, uploadMedia } from "./runtime/layer-client.js";

import { askActionLayer, buildBulkAnswers, syncAsks } from "./runtime/asks/view.js";

import { paintKeys, reflectFirstScopes } from "./runtime/keyboard/scopes.js";
import { paintStandingContent, paintStandingGeometry } from "./runtime/standing.js";
import { repaint, wireRepaint } from "./runtime/repaint.js";

import { liveEl, notice } from "./runtime/notifications.js";

import { pageShifted, setAnchoringReady, mountAnchors } from "./runtime/anchors.js";
import {
  banner,
  loadIcon,
  mountBanner,
  paintApproval,
  renderStatus,
  reserveBannerControls,
} from "./runtime/banner.js";
import { overflowMenu, showNews } from "./runtime/banner-shelf.js";

import { mountConversation, renderPanel } from "./runtime/conversation/reconcile.js";
import {
  mountPanelReadingRegion,
  panel,
  wireGeneralBox,
} from "./runtime/conversation/panel.js";
import { wireThreadLanding } from "./runtime/conversation/landing.js";
import { mountThreadList } from "./runtime/conversation/thread-list.js";
import { wireNarrowing } from "./runtime/conversation/narrowing.js";
import { wireThreadCards } from "./runtime/conversation/thread-card.js";

import { beginRead, startFeed } from "./runtime/state-feed.js";

import { installArrival, versionMenu } from "./runtime/version.js";
import { upgradeWidgets } from "./runtime/widget-loader.js";

import {
  PAGE_INTERFACE,
  PAGE_PAINT_ATTRIBUTE,
  PRESENTATION,
  settlePageInterface,
} from "./runtime/presentation.js";

import { marksSheet } from "./runtime/shadow.js";

import { asksPanel, othersBtn, othersPanel, restoreTray } from "./runtime/trays.js";
import {
  commentBox,
  commentRows,
  declareFindBoxKeys,
  declareResponseOptionKeys,
  letGo,
} from "./runtime/keyboard/page.js";
import { chromeRoot } from "./runtime/chrome.js";
import { restoreArrangements } from "./runtime/arrangements.js";
import { captureAuthoredFacets } from "./runtime/projection/authored.js";
import { layoutMarginRows } from "./runtime/margin-layout.js";
import { shortcutReferenceDialog } from "./runtime/keyboard/reference.js";
import { bottomStatusEl, shortcutBarEl } from "./runtime/keyboard/shortcut-bar.js";
import { offer } from "./runtime/widget-elements.js";
import { focusDestination } from "./runtime/focus.js";
import { inspectEl, legendRoot } from "./runtime/design.js";
import { addressLayer } from "./runtime/keyboard/address.js";
import { selectionLayer, selectionSearch } from "./runtime/composing/targets.js";
import {
  mountTargetPaint,
  targetTraceBox,
  visualMarkLayer,
} from "./runtime/target-paint.js";
import { drawingLayer } from "./runtime/composing/drawing.js";
import { mountMargin } from "./runtime/living-margin.js";
import { aimBox } from "./runtime/composing/aim.js";
import { FOCUSABLE } from "./runtime/reach.js";
import { activeRowLabel } from "./runtime/keyboard/dispatch.js";
import { watchDisclosures } from "./runtime/keyboard/disclosure.js";
import { mediaViewer } from "./runtime/media.js";
import { configureInput } from "./runtime/composing/input.js";

wireRepaint({
  reflectFirstScopes,
  paintStandingContent,
  syncLayout,
  pageShifted,
  paintStandingGeometry,
});

const commentAddress = () => ({
  box: commentBox(),
  label: activeRowLabel(commentRows()),
});

// The chrome follows `main` in the document, which is right for reading and wrong for
// reaching: nothing stood between the top of the page and the banner but the whole page,
// and the top of the page is where a keyboard reader's next Tab starts whenever they are
// holding no control. So one stop stands in front of everything, the way a skip link
// always has.
//
// Prepended to the body rather than put in the chrome, because tab order is document
// order and the chrome is last; there is no `tabindex` that would buy this and no reason
// to want one. It carries the offer marker `offer` writes, so paper drops it with every
// other injected control and a copy takes it out with the layer it points at. It takes no
// row in the register either: a control is a route to a capability rather than a
// capability of its own, and this one's whole design is to be the first thing a reader
// finds without having been told about it.
// Which control the skip link lands on is decided by trying the focus, not by a reading
// of whether the control looks available. The banner's controls are conditional in
// several ways at once — Leaves is absent where the machine has one leaf, Asks where the page waits on
// nobody, the newest-version chip is drawn only while there is a newer version, and
// sign-off is disabled until the page is presented — and each of those makes focus
// silently do nothing rather than fail. So the walk asks the browser the only question
// that matters here, whether the reader ended up on it, and the banner itself is the
// answer when none of them will have them.
const skipToChrome = offer("button", "lf-skip", "Skip to Leaf controls");
skipToChrome.onclick = () => {
  for (const control of banner.querySelectorAll(FOCUSABLE)) {
    control.focus({ preventScroll: true });
    if (control.matches(":focus")) return;
  }
  focusDestination(banner);
};

function mountChrome() {
  configureInput({ upload: uploadMedia, address: commentAddress });
  mountBanner();
  chromeRoot.append(
    banner,
    overflowMenu,
    versionMenu,
    othersPanel,
    asksPanel,
    panel,
    legendRoot,
    addressLayer,
    askActionLayer,
    selectionLayer,
    selectionSearch,
    visualMarkLayer,
    drawingLayer,
    targetTraceBox,
    aimBox,
    fabBar,
    liveEl,
    mediaViewer,
    shortcutReferenceDialog,
    bottomStatusEl,
    shortcutBarEl,
    inspectEl,
  );
  document.body.prepend(skipToChrome);
  document.body.append(chromeRoot);
  mountPanelReadingRegion();
  reserveBannerControls();
  mountMargin();
  mountTargetPaint();
  mountAnchors();
  wireThreadLanding();
  mountConversation();
  mountThreadList();
  wireNarrowing();
  mountLayout();
  // A disclosure opening or closing changes what the next press does, and no writer in this
  // file reports it: the word on a summary's row is read off `open`, and the reader standing
  // there has moved nothing else. Left unpainted, the line said "close" for the three seconds
  // until a poll happened past — a shortcut bar stale about the press under the reader's finger,
  // where every gate reads it as eventually right.
  //
  // Watched as state rather than heard as an event, because the event only covers one of the
  // two spellings and only in one of the two trees. `toggle` is not composed, so a <details>
  // a widget staged in a shadow root fires nothing a document listener hears, and a control
  // keeping its state in aria-expanded fires nothing anywhere. Both keep that state in an
  // attribute, so one observer over the two attributes answers for both, and `shadowStage`
  // hands it each root it attaches. It is the document's rather than each element's: the
  // disclosures on a page are whatever its author wrote and whatever its widgets built,
  // which is not a list this file can hold.
  watchDisclosures(document);
  wireThreadCards();
  wireFabInput();
  declareLeavesKeys();
  declareFindBoxKeys();
  declareResponseOptionKeys();
  wireGeneralBox();
}

// ---------- styles ----------
// The chrome's sheet and the marks' arrive as CSS modules: part of the import graph, so
// both are constructed before this module's first line runs, and adopted rather than
// written into the head, so a version activation's head reconciliation never meets
// them. shadowStage adopts the marks into every root it builds; the bake writes both
// into a <style> for a copy, which has no module graph to carry them.
document.adoptedStyleSheets = [chromeSheet, marksSheet];

mountChrome();

// The server can build the authoritative page state while the browser loads and settles
// the registry's widget modules. Its answer stays buffered until startPage has captured
// the upgraded authored facets that replay starts from.
const initialStateRead = beginRead();

let interactionGalleryModule;
let interactionGalleryLoading;
let failedInteractionGallery;
async function syncInteractionGallery() {
  const gallery = document.querySelector("[data-interaction-gallery]");
  if (gallery && gallery === failedInteractionGallery) return;
  try {
    if (!gallery && !interactionGalleryModule) return;
    if (!interactionGalleryModule) {
      interactionGalleryLoading ??= import("./runtime/interaction-gallery.js");
      interactionGalleryModule = await interactionGalleryLoading;
    }
    interactionGalleryModule?.installInteractionGallery();
  } catch (error) {
    failedInteractionGallery = gallery;
    if (!interactionGalleryModule) interactionGalleryLoading = null;
    reportPageError(`interaction gallery failed to start: ${error?.message ?? error}`);
  }
}
document.addEventListener("lf-actions", () => void syncInteractionGallery());
document.addEventListener(PAGE_INTERFACE, (event) => {
  event.detail.pending.push(syncInteractionGallery());
});

// A fresh arrival starts on the page, the same stable focus destination the Escape ladder
// uses after chrome. Root scrolling no longer depends on this handoff; focus ownership
// still does, since Space on a button presses it rather than scrolling the document.
//
// Here rather than in the start block below, which runs asynchronous upgrades while the
// authored document is already readable: body can name the page now, and stateful widget
// controls remain unavailable until presentPage crosses their semantic boundary.
if (!containedPage) {
  restoreArrangements();
  letGo();
}
const { landArrival, savedView } = installArrival();
const savedComposer = pendingComposer();

// ---------- start ----------
// One positive fact for the semantic-interaction boundary. Authored HTML already paints.
// Success has applied the log; an unavailable first poll has painted the offline status
// and deliberately lets the authored state accept durable interaction. A caught startup
// failure cannot make either promise, so controls and top-layer UI remain unavailable.
function presentPage() {
  if (document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented)) return;
  // Anchors are durable coordinates, so their pass and every route that can mint one
  // begin only after replay has reconciled the authored document. An early native text
  // selection can then resolve against the standing DOM, while a retired passage cannot
  // leave a composer carrying its authored words.
  setAnchoringReady(true);
  try {
    renderPanel();
  } catch (error) {
    setAnchoringReady(false);
    throw error;
  }
  // The stamp is the promise that every semantic prerequisite above succeeded, not merely
  // that presentation was attempted. Keep it absent when a malformed widget makes the
  // anchor reading fail, so durable controls remain withheld on that partial page.
  document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.presented, "1");
  updateFab();
  // Repaint the remaining state-dependent chrome and controls in this same task. Replay
  // is already complete, so the presented attribute opens interaction on the state it names.
  restoreTray();
  showNews(othersBtn, leavesOffered());
  paintKeys();
  document.dispatchEvent(new Event("lf-actions"));
  paintApproval();
  repaint();
  // Fragment arrival reads after those controls have taken their final space. Margin
  // placement normally batches into a frame; a fresh arrival runs that pending layout
  // now so a docked row above the target cannot move it again after the landing.
  layoutMarginRows();
  landArrival();
  if (savedView && savedView.revision < runtime.currentRevision)
    notice(`Updated to ${runtime.currentLabel}`, { background: true });
  openDraft(savedComposer);
  promoteDeferredModals();
  // The presented attribute and every write after it are one JavaScript task. Give
  // geometry consumers one synchronous read of the authoritative startup layout before
  // semantic interaction opens; they may replace geometry already painted from authored
  // state, and later ResizeObserver and layout signals own reader-driven changes.
  document.dispatchEvent(new Event(PRESENTATION));
}

// Upgrades flush before the anchor pass and the view restore, so quotes and reading
// positions are re-found in the enhanced, replayed DOM rather than authored markup. An
// async function, never top-level await: every owner has evaluated before boot runs, and
// the behavior modules that consume the public facade are imported after it.
async function startPage() {
  const [upgraded] = await Promise.all([
    upgradeWidgets(),
    // Alongside rather than after, and caught rather than fatal: the tab icon is not
    // what the page is for, so a layer missing it says so in the console and leaves the
    // rest working. It is still awaited here, because `version export` copies the
    // page at the stamp below, and an icon arriving later would leave the copy's
    // tab to chance.
    loadIcon().catch((err) => console.error(err)),
  ]);
  if (!upgraded) return;
  syncLayout();
  // Before the first poll's replay: the authored facets are the markup's
  // initial condition, and replay is about to overwrite them in the DOM.
  captureAuthoredFacets();
  buildBulkAnswers();
  syncAsks();
  // Optional page interface adds controls and may reset the widgets it composes. Its
  // dynamic imports and first installation settle beside this document's widgets; the
  // same boundary runs when a later version replaces the authored page.
  await settlePageInterface();
  // Every widget has upgraded and every async one has settled, so the geometry and
  // the drawn SVG are final. `version export` copies the page at this moment and has no
  // other way to know it arrived: a load event fires before the modules run, and
  // networkidle only says a bundle finished downloading, not that it finished
  // drawing. The stamp says the document is done becoming itself.
  document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.upgraded, "1");
  // Apply the buffered first read only after that stamp, preserving the two readiness
  // facts but presenting neither half on its own. What that read cannot decide is
  // whether the page arrives at all: startFeed waits a fixed time for it and then
  // presents offline without ending it, so the heartbeat and the stream begin at that
  // wait rather than at the container's answer. The request stays in flight holding the
  // page's one read slot, so it cannot be overtaken by a second answer, and what it
  // finally brings is applied where the page stands.
  startFeed(presentPage, initialStateRead);
}

startPage().catch((error) => {
  // The boundary itself must fail visibly. Authored HTML remains readable, while the
  // status names the fault and the absent presented stamp keeps durable controls closed.
  window.dispatchEvent(new Event("lf-startup-failed"));
  reportPageError(`page failed to start: ${error?.message ?? error}`);
  renderStatus(error);
});
