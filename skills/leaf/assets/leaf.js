/* Leaf runtime, loaded via <script type="module" src="/leaf.js">: the boot module. It
 * imports every runtime owner and runs the boot sequence below. skills/leaf/assets/CLAUDE.md
 * names each owner's responsibility and the rule against reading one while it evaluates. */

import chromeSheet from "./runtime/chrome.css" with { type: "css" };
import { syncLayout } from "./runtime/chrome-layout.js";

import { leavesOffered } from "./runtime/live-leaves.js";

import { openComposer, pendingComposer } from "./runtime/composing/selection.js";
import { updateFab } from "./runtime/composing/surface.js";

import { runtime } from "./runtime/context.js";
import { promoteDeferredModals } from "./runtime/deferred-modals.js";
import { reportPageError } from "./runtime/layer-client.js";

import { buildBulkAnswers, syncAsks } from "./runtime/asks/view.js";

import { paintHere, paintKeys, paintsHere } from "./runtime/keyboard/scopes.js";
import { paintStandingChrome } from "./runtime/standing.js";

import { notice } from "./runtime/notifications.js";

import { setAnchoringReady } from "./runtime/anchors.js";
import { loadIcon, paintApproval, renderStatus } from "./runtime/banner.js";
import { showNews } from "./runtime/banner-shelf.js";

import { renderPanel } from "./runtime/conversation/reconcile.js";

import { beginRead, startFeed } from "./runtime/state-feed.js";

import { installArrival } from "./runtime/version.js";
import { upgradeWidgets } from "./runtime/widget-loader.js";

import { PAGE_PAINT_ATTRIBUTE } from "./runtime/presentation.js";

import { marksSheet } from "./runtime/shadow.js";

import { othersBtn, restoreTray } from "./runtime/trays.js";
import { letGo } from "./runtime/keyboard/page.js";
import { mountChrome } from "./runtime/chrome.js";
import { restoreArrangements } from "./runtime/arrangements.js";
import { captureAuthoredFacets } from "./runtime/projection/authored.js";

// The register's repaint frame paints the standing chrome: registered here, first,
// because the painter imports every owner and no owner may import it.
paintsHere(paintStandingChrome);

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

// A fresh arrival starts on the page, the same stable focus destination the Escape ladder
// uses after chrome. Root scrolling no longer depends on this handoff; focus ownership
// still does, since Space on a button presses it rather than scrolling the document.
//
// Here rather than in the start block below, which runs asynchronous upgrades while the
// authored document is already readable: body can name the page now, and stateful widget
// controls remain unavailable until presentPage crosses their semantic boundary.
restoreArrangements();
letGo();
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
  paintHere();
  landArrival();
  if (savedView && savedView.revision < runtime.currentRevision)
    notice(`Updated to ${runtime.currentLabel}`);
  if (savedComposer)
    openComposer(savedComposer.anchor, savedComposer.text, {
      suggest: Boolean(savedComposer.suggest),
      about: savedComposer.about ?? null,
      drawing: savedComposer.drawing ?? null,
    });
  // Repaint the remaining state-dependent chrome and controls in this same task. Replay
  // is already complete, so the presented attribute opens interaction on the state it names.
  restoreTray();
  showNews(othersBtn, leavesOffered());
  paintKeys();
  document.dispatchEvent(new Event("lf-actions"));
  paintApproval();
  promoteDeferredModals();
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
  // Every widget has upgraded and every async one has settled, so the geometry and
  // the drawn SVG are final. `version export` copies the page at this moment and has no
  // other way to know it arrived: a load event fires before the modules run, and
  // networkidle only says a bundle finished downloading, not that it finished
  // drawing. The stamp says the document is done becoming itself.
  document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.upgraded, "1");
  // Apply the buffered first read only after that stamp, preserving the two readiness
  // facts but presenting neither half on its own. The first completed read — state or
  // offline — is the presentation boundary; only after it settles do the heartbeat and
  // the stream begin, so a held first request cannot be overtaken by a second answer and
  // leave presentation waiting on the wrong call.
  startFeed(presentPage, initialStateRead);
}

startPage().catch((error) => {
  // The boundary itself must fail visibly. Authored HTML remains readable, while the
  // status names the fault and the absent presented stamp keeps durable controls closed.
  window.dispatchEvent(new Event("lf-startup-failed"));
  reportPageError(`page failed to start: ${error?.message ?? error}`);
  renderStatus(error);
});
