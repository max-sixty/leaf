/* The chrome's one root, and the mounting of every part into it. Each part is built by
   the owner that draws into it; this module only names them, in the order the layer
   stacks them, and puts the root in the document. */
import { banner, mountBanner, reserveBannerControls } from "./banner.js";
import { versionMenu } from "./version.js";
import { decisionsPanel, othersPanel } from "./trays.js";
import { panel, wireGeneralBox } from "./conversation/panel.js";
import { composer, fab, fabBar } from "./composing/selection.js";
import { helpEl } from "./keyboard/reference.js";
import { keylineEl } from "./keyboard/keyline.js";
import { el, focusDestination, offer } from "./widget-elements.js";
import { overflowMenu } from "./banner-shelf.js";
import { inspectEl, legendRoot } from "./design.js";
import { addressLayer } from "./keyboard/address.js";
import { decisionActionLayer } from "./decisions/view.js";
import { selectionLayer, selectionSearch } from "./composing/targets.js";
import { mountTargetPaint, visualMarkLayer } from "./target-paint.js";
import { marginTraceBox, mountMargin } from "./living-margin.js";
import { aimBox } from "./composing/aim.js";
import { liveEl } from "./notifications.js";
import { FOCUSABLE } from "./reach.js";
import { mountLayout } from "./chrome-layout.js";
import { declareLeavesKeys } from "./live-leaves.js";
import { declareFindBoxKeys } from "./keyboard/page.js";
import { wireFabInput } from "./composing/surface.js";
import { mountAnchors } from "./anchors.js";
import { wireThreadLanding } from "./conversation/landing.js";
import { mountConversation } from "./conversation/reconcile.js";
import { mountThreadList } from "./conversation/thread-list.js";
import { wireNarrowing } from "./conversation/narrowing.js";
import { watchDisclosures } from "./keyboard/disclosure.js";
import { wireThreadCards } from "./conversation/thread-card.js";

// The one scope root for the chrome's private rules: they match nothing outside this
// container. A div, not a lf-* element — the render gate reads a lf-* ancestor as
// "inside a widget", and the runtime's layer is inside none.
export const chromeRoot = el("div", "lf-chrome");

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

// Every part in the layer's stacking order, named, and the root put in the document.
export function mountChrome() {
  mountBanner();
  // The runtime's parts, named: a design comment can point at one, and an anchor names an
  // element by id, so each part that is a thing to point at carries a stable one under the
  // runtime's own prefix. `[id]:not(.lf-ui)` — how the anchor pass asks which section a
  // passage is in — still passes over them, every one wearing lf-ui. What has no id is
  // what nobody comments on: the notice, the live region, the scope root itself.
  for (const [part, id] of [
    [banner, "lf-banner"],
    [versionMenu, "lf-versions"],
    [othersPanel, "lf-leaves"],
    [decisionsPanel, "lf-decisions"],
    [panel, "lf-threads"],
    [fab, "lf-comment-button"],
    [composer, "lf-composer"],
    [helpEl, "lf-help"],
    [keylineEl, "lf-keyline"],
  ])
    part.id = id;

  chromeRoot.append(
    banner,
    overflowMenu,
    versionMenu,
    othersPanel,
    decisionsPanel,
    panel,
    legendRoot,
    addressLayer,
    decisionActionLayer,
    selectionLayer,
    selectionSearch,
    visualMarkLayer,
    marginTraceBox,
    aimBox,
    fabBar,
    liveEl,
    helpEl,
    keylineEl,
    inspectEl,
  );
  document.body.prepend(skipToChrome);

  document.body.append(chromeRoot);
  reserveBannerControls();
  // What the parts' owners could not do as they evaluated: measure what is now in the
  // document, observe it, wire another owner's element, and append into another owner's
  // part.
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
  // until a poll happened past — a key line stale about the press under the reader's finger,
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
  wireGeneralBox();
}
