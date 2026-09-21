/* The page's own parts: what the reader is standing on when it belongs to no feature,
   the one press that lets go of it, and the foot of the Escape ladder.

   Everything else the page answers is declared by the owner that implements it and joins
   the stack through `register.js`. This file keeps the document's own parts — a link, a
   disclosure — and the presses that are nobody's capability: the browser's caret
   browsing, letting go of whatever the reader is standing on, and backing out of the
   chrome onto the page.

   Importing this module is what puts the page's parts in the register. The let-go is the
   one declaration that reads other owners' state — the modes, the captured target, the
   Page Map's rung — so `declareStanding` is the one export, and the boot entry calls it
   once those owners stand. */
import { letGo, takesLetters } from "../focus.js";
import { inChrome, pageQueryAll } from "../passages.js";
import { inUi } from "../shadow.js";
import { pageSelection } from "../composing/capture.js";
import { standingThreadOf } from "../conversation/focus.js";
import { boxHandsBack } from "../conversation/landing.js";
import { inPanel as panelFocusIsInside } from "../conversation/panel-elements.js";
import { claimsEsc, documentFocused, focused } from "./scopes.js";
import { DISCLOSE, DISCLOSURE_SELECTOR, disclosed } from "./disclosure.js";
import { nativeLayers } from "./layer-stack.js";
import { pageCommand, pageRung, pageScope } from "./register.js";

// Where the reader is standing, when what they are standing on is one of the page's own
// parts rather than a widget's own declaration. A widget's control scope cannot cover
// these: it works a span `offer` made pressable, where these arrive with platform keys
// already bound. Enter follows an <a> while Space scrolls the page out from under it; both
// work a disclosure. A generated `g` hint puts the reader on a disclosure, and Tab can put
// them on either. Until a scope existed the line went quiet at exactly the moment they
// arrived, with the press that finishes the motion unnamed.
//
// The page's parts and not every one, which is the reading the target map takes as well:
// the chrome's own links are the leaves tray's and its resolved comments are the panel's,
// and both of those declare what they answer themselves. Asked of the document at large,
// "On a link" was had by every page — a machine with one neighbour has a tray full of
// links — so the reference named it wherever the reader went, on pages holding none to
// stand on. One derivation and not a copy apiece: what a scope here asks is the same pair
// of questions of a different selector, and the day the chrome rule changes is the day a
// second copy of it is wrong.
function standingOn(name, title, sel, rows) {
  pageScope(name, {
    title,
    root: focused,
    at: () => {
      const el = focused();
      return Boolean(el?.matches?.(sel)) && !inChrome(el);
    },
    // Across the declared shadow roots, where the addresses stop at the document: a row on
    // a staged disclosure names a key the browser does not answer, so a scope that could
    // not see one would leave the line promising a press nothing makes.
    when: () => pageQueryAll(sel).some((el) => !inChrome(el)),
    rows,
  });
}

// A link's press is the browser's whole answer, so this row binds no `run`: it promises
// nothing the browser does not already do, and what it adds is the promise being on
// screen. Enter alone, Space under a link being the page's own scroll.
standingOn("link", "On a link", "a[href]", [
  { id: "link.follow", keys: ["Enter"], does: "Follow it", line: "follow" },
]);

// A disclosure, in either spelling the page has for one. The platform's <details> keeps the
// state on itself; a control a widget built out of a span says the same thing through
// ARIA's own attribute, which it already writes for the theme and the screen reader. Two
// vocabularies, one capability — and a reader standing on a settled group cannot see which
// of the two they are standing on, so a scope apiece would be the same press answered on
// one of them and not the other.
//
// ARIA's disclosure pattern and not the attribute at large. A combobox wears aria-expanded
// over a box words are typed into and a treeitem wears it in a walk of its own, and ← / →
// belong to the caret and the walk there. The pattern is the pair, so the selector asks for
// the button half too — which is what `offer` writes, and what a real <button> brings with
// it.
standingOn("disclosure", "On a disclosure", DISCLOSURE_SELECTOR, [
  {
    id: "disclosure.toggle",
    keys: () => DISCLOSE(focused()),
    does: "Open or close it",
    // Read where it is painted rather than named once for both branches, the way a diff's
    // own file rows read theirs: what the press does is whichever way the disclosure is
    // standing, and a word fixed at declaration could only ever say one of them.
    line: () => (disclosed(focused()) ? "close" : "open"),
    // Through the element's own click, so keyboard and pointer are one behaviour: a
    // <summary>'s click is the toggle the browser was already making, and a widget's
    // control runs the handler its own pointer press runs. Enter and Space are the
    // runtime's here rather than the platform's, because a row owns its whole binding set
    // and the dispatcher takes the key before the platform sees it. One toggle answers all
    // three: the arrow bound is the one that changes this disclosure, so a press cannot
    // mean anything else.
    run: () => focused().click(),
  },
]);

pageCommand({
  id: "browser.caret",
  keys: ["F7"],
  does: "Caret browsing (the browser's): select text by keyboard, then c",
});

// What the reader is standing on, and the one press that lets go of it. Standing is
// holding a destination — an Ask, conversation, or heading out on the page — as against
// content of a chrome surface or a chrome control such as the panel's toggle. Chrome is
// answered by the ladder below once its inner boxes and layers are down. Letting go puts
// the reader on the page's floor.
//
// It is the innermost step, because standing is the newest thing the reader did: a Tab,
// a hint, a pointer press. Everything the ladder takes off — a selection, an unfolded
// margin cluster, a mode, a tray, the panel — is state they put on before they came to
// rest here, so it waits behind this press. What stands nearer still answers first: a
// widget's own Escape declared over the control, and a text box with a place to go back
// to, whose own scope hands them there. A native layer standing over the page is the
// browser's mode, and its own Escape is not ours to pre-empt with a let-go beneath it.
//
// Out on the page — chrome surfaces hold nothing to let go of — what is held is a destination
// when it is a thread or an Ask, or anything inside one: a seat on the page, an Ask's
// own picks. The Ask is the asks view's reading, handed in like the modes, so a control
// hoisted into the margin holds the Ask it serves and an answered Ask is still one. It
// is the page's own content otherwise, unless it is Leaf's apparatus, and `inUi` is the
// one reading of that, the layer a node stands in, asked of the deepest focus so a
// control staged in a shadow tree answers for itself: a margin marker and a mark note
// are placed in the document beside the words they mark, outside the container and
// controls all the same, so the container alone answered them wrong and the ladder's
// page rung, which backs out of a control, is what they get. The walk destinations
// above ask `inChrome` alone, because their question is only whether an Ask or a
// heading is the page's own or a copy standing in the panel's frozen markup.
//
// The scope's `at` is the cheap half, whether anything is held at all; the row's `when`
// is the dear one, asked only of a reader who is holding something. The panel, the Ask
// and the page's own state are other owners' readings, handed in by the boot entry once
// those owners stand.
const holding = () => {
  const active = documentFocused();
  return Boolean(active) && active !== document.body;
};
let standingOnPage = () => false;
export function declareStanding({ panelIsOpen, askHeld, pageState }) {
  standingOnPage = () => {
    if (!holding()) return false;
    if (nativeLayers().length) return false;
    if (takesLetters(focused()) && boxHandsBack()) return false;
    if (claimsEsc(focused())) return false;
    // Titles and open conversations are content of the thread panel, not levels inside
    // it. After any inner box or narrowing is gone, the panel is their one way out.
    if (panelFocusIsInside(panelIsOpen)) return false;
    if (inChrome(documentFocused())) return false;
    // Out on the page, where state the reader put on here is inside the page they are
    // standing in and comes off before they let go of anything: the drag that takes
    // words out of a label is answered on its first glyph, while the control it started
    // from is still theirs. A reader inside a surface is past all of it — a mode left
    // standing out on the page waits behind the panel they are reading a thread in —
    // which is why this asks after the branches above rather than before them.
    if (pageSelection() || pageState()) return false;
    return Boolean(standingThreadOf() || askHeld() || !inUi(focused()));
  };
  pageScope("standing", {
    title: "Standing on something",
    root: focused,
    escape: "inner",
    at: holding,
    rows: [
      {
        id: "navigation.release",
        keys: ["Escape"],
        does: "Let go of what you are standing on",
        line: "let go",
        when: standingOnPage,
        run: letGo,
      },
    ],
  });
}

// The foot of Escape's ladder, the page's own. Above it stand the surfaces a reader can
// put on — a captured target, a tray, a narrowing, the thread panel, a page mode — each
// contributed by its owner, so the ladder is read off `RUNG_LADDER` rather than written
// out anywhere. This step leaves the chrome, after every surface has had its turn, and
// stands down while the let-go above answers, so the reference names one press rather
// than two spellings of it. It stands down under a native layer too: a popover or a
// modal is the browser's own mode, its own scope is the way out of it, and the page
// beneath is not somewhere a press can reach from inside it.
// CLAUDE.md's "The reader has to be standing somewhere" holds the rest.
pageRung("page", () =>
  holding() && !standingOnPage() && !nativeLayers().length
    ? { says: "back to the page", does: "Back out onto the page", out: letGo }
    : null,
);
