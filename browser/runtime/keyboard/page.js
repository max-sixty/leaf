import { sampleNotice } from "../sample-child.js";
/* The page's own parts: what the user is on when it belongs to no feature,
   the one press that lets go of it, and the foot of the Escape ladder.

   Everything else the page answers is declared by the owner that implements it and joins
   the stack through `register.js`. This file keeps the document's own parts — a link, a
   disclosure — and the presses that are nobody's capability: the browser's caret
   browsing, letting go of whatever the user is on, and backing out of the
   chrome onto the page.

   Importing this module is what puts the page's parts in the register. The let-go is the
   one declaration that reads other owners' state — the modes, the captured target, the
   Page Map's rung — so `declareCurrentLocation` is the one export, and the boot entry calls it
   once those owners stand. */
import { letGo, release, focused } from "../focus.js";
import { inChrome, pageQueryAll } from "../passages.js";
import { inUi } from "../shadow.js";
import { pageSelection } from "../composing/capture.js";
import { heldThread } from "../thread/focus.js";
import { heldObligation } from "../current-target.js";
import { leavesBox } from "../thread/landing.js";
import { claimsEsc } from "./scopes.js";
import { nativePress } from "./bindings.js";
import { DISCLOSE, DISCLOSURE_SELECTOR, disclosureAt } from "./disclosure.js";
import { nativeLayers } from "./layer-stack.js";
import { LINK } from "./text-entry.js";
import { pageCommand, pageRung, pageScope } from "./register.js";

// Where the user is , when what they are on is one of the page's own
// parts rather than a widget's own declaration. A widget's control scope cannot cover
// these: it works a span `offer` made pressable, where these arrive with platform keys
// already bound. Enter follows an <a> while Space scrolls the page out from under it; both
// work a disclosure. A generated `g` hint puts the user on a disclosure, and Tab can put
// them on either. Until a scope existed the line went quiet at exactly the moment they
// arrived, with the press that finishes the motion unnamed.
//
// The page's parts and not every one, which is the reading the target map takes as well:
// the chrome's own links are All pages' and its resolved comments are the panel's,
// and both of those declare what they answer themselves. Asked of the document at large,
// "On a link" was had by every page — a machine with one neighbour has a list full of
// links — so the reference named it wherever the user went, on pages holding none to
// stand on. One derivation and not a copy apiece: what a scope here asks is the same pair
// of questions of a different selector, and the day the chrome rule changes is the day a
// second copy of it is wrong.
/** @param {string} name @param {string} title @param {string} sel @param {readonly import("./bindings.js").Command[]} rows */
function currentLocationOn(name, title, sel, rows) {
  pageScope(name, {
    title,
    root: focused,
    at: () => {
      const el = focused();
      return Boolean(el?.matches?.(sel)) && !inChrome(el);
    },
    // Across the declared shadow roots, where the addresses stop at the document: a row on
    // a staged disclosure names a key the browser does not answer, so a scope that could
    // not see one would leave the reference promising a press nothing makes.
    when: () => pageQueryAll(sel).some((el) => !inChrome(el)),
    rows,
  });
}

// A link's press is the browser's whole answer, so this row binds no `run`: it promises
// nothing the browser does not already do, and what it adds is the promise being on
// screen. Enter alone, Space under a link being the page's own scroll.
currentLocationOn("link", "On a link", LINK, [
  { id: "link.follow", keys: ["Enter"], title: "Follow", touch: false },
]);

// A disclosure, in either spelling the page has for one. The platform's <details> keeps the
// state on itself; a control a widget built out of a span says the same thing through
// ARIA's own attribute, which it already writes for the theme and the screen reader. Two
// vocabularies, one capability — and a user on a settled group cannot see which
// of the two they are on, so a scope apiece would be the same press answered on
// one of them and not the other.
//
// ARIA's disclosure pattern and not the attribute at large. A combobox wears aria-expanded
// over a box words are typed into and a treeitem wears it in a walk of its own, and ← / →
// belong to the caret and the walk there. The pattern is the pair, so the selector asks for
// the button half too — which is what `offer` writes, and what a real <button> brings with
// it.
currentLocationOn("disclosure", "On a disclosure", DISCLOSURE_SELECTOR, [
  {
    id: "disclosure.toggle",
    touch: false,
    keys: () => DISCLOSE(focused()),
    // Read where it is painted rather than named once for both branches, the way a diff's
    // own file rows read theirs: what the press does is whichever way the disclosure is
    // set, and a word fixed at declaration could only ever say one of them.
    title: () => (disclosureAt(focused())?.open ? "close" : "open"),
    // Through the element's own click, so keyboard and pointer are one behaviour: a
    // <summary>'s click is the toggle the browser was already making, and a widget's
    // control runs the handler its own pointer press runs. Enter and Space are the
    // runtime's here rather than the platform's, because a row owns its whole binding set
    // and the dispatcher takes the key before the platform sees it. One toggle answers all
    // three: the arrow bound is the one that changes this disclosure, so a press cannot
    // mean anything else.
    run: () => nativePress(focused())?.(),
  },
]);

pageCommand({
  id: "browser.caret",
  touch: false,
  keys: ["F7"],
  title: "Caret browsing",
  description: "Select text with the keyboard caret to comment on it",
});

// Current location is a destination on the page. Releasing it lands at its floor, the document.
// A thread in the floating panel has no floor of its own: what stands open there, the
// menu and then a view, is a step of this ladder (floating-panel.js), so putting the
// view away is the way out of a panel thread.
//
// Inner controls, reply boxes, and native layers answer first. Page-side state waits
// while focus is in the panel. On the page, a selection or mode unwinds before the
// destination does. Chrome controls belong to the surface's own Escape ladder.
const holding = () => {
  const active = focused(document);
  return Boolean(active) && active !== document.body;
};
/** @type {() => HTMLElement | null} */
let currentLocationFloor = () => null;
/** @param {{pageState: () => unknown}} options */
export function declareCurrentLocation({ pageState }) {
  currentLocationFloor = () => {
    if (!holding()) return null;
    // This scope stands with the focused control, ahead of native boundaries.
    // A modal or light-dismiss popover owns that exit; a manual popover has none.
    if (
      nativeLayers().some(
        ({ kind, root }) => kind === "modal" || root.popover !== "manual",
      )
    )
      return null;
    if (leavesBox()) return null;
    if (claimsEsc(focused())) return null;
    if (inChrome(focused(document))) return null;
    const thread = heldThread();
    if (pageSelection() || pageState()) return null;
    return thread || heldObligation() || !inUi(focused()) ? document.body : null;
  };
  pageScope("current-location", {
    title: "Current location",
    root: focused,
    escape: "inner",
    at: holding,
    rows: [
      {
        id: "navigation.release",
        touch: false,
        keys: ["Escape"],
        title: "let go",
        when: () => Boolean(currentLocationFloor()),
        run: release,
      },
    ],
  });
}

// The foot of Escape's ladder, the page's own. Above it stand the surfaces a user can
// put on — a captured target, the floating panel's views, a page mode — each
// contributed by its owner, so the ladder is read off `RUNG_LADDER` rather than written
// out anywhere. This step leaves the chrome, after every surface has had its turn, and
// stands down while the let-go above answers, so the reference names one press rather
// than two spellings of it. The dispatcher's native boundaries keep this page scope
// behind modal dialogs and light-dismiss popovers; a manual popover has no native
// Escape dismissal to withhold the page's own step.
// keyboard/AGENTS.md's "Escape" holds the rest.
pageRung("page", () => {
  if (holding())
    return currentLocationFloor()
      ? null
      : {
          title: "back to the page",
          out: letGo,
        };
  // A sample has one more containing page. Its own controls and current location unwind
  // first; the frame's owner takes the focus back, not another keyboard listener
  // competing with this register.
  return document.documentElement.lfSample
    ? {
        title: "return to containing page",
        out: () => sampleNotice({ type: "return" }),
      }
    : null;
});
