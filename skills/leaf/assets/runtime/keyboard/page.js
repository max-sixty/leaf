/* The page's own parts: what the reader is standing on when it belongs to no feature, and
   the two ends of the Escape ladder.

   Everything else the page answers is declared by the owner that implements it and joins
   the stack through `register.js`. This file keeps the document's own parts — a link, a
   disclosure — and the presses that are nobody's capability: the browser's caret
   browsing, and letting go of whatever the reader is standing on.

   Importing this module is what puts those declarations in the register; it exports
   nothing, as the boot entry does not call it. */
import { letGo } from "../focus.js";
import { inChrome, pageQueryAll } from "../passages.js";
import { documentFocused, focused } from "./scopes.js";
import { DISCLOSE, DISCLOSURE_SELECTOR, disclosed } from "./disclosure.js";
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

// The two steps of Escape's ladder that are the page's own. Between them stand the
// surfaces a reader can put on — a captured target, a tray, a narrowing, the thread
// panel — each contributed by its owner, so the ladder is read off `RUNG_LADDER` rather
// than written out anywhere.
//
// The first is theirs: out on the page, the innermost thing the reader is in is whatever
// they are standing on, and a panel behind them is a layer they are not in. Nothing said
// this before — a reader the walk had brought to an Ask could press Escape all day and the
// ring stayed on it, the one place in the runtime a key put the reader somewhere with no
// key to take them out again.
//
// The last leaves the chrome, after every surface has had its turn. CLAUDE.md's "The reader
// has to be standing somewhere" holds the rest.
const holding = () => {
  const active = documentFocused();
  return Boolean(active) && active !== document.body;
};
pageRung("standing", () =>
  holding() && !inChrome(documentFocused())
    ? {
        says: "let go",
        does: "Let go of what you are standing on",
        out: letGo,
      }
    : null,
);
pageRung("page", () =>
  holding()
    ? { says: "back to the page", does: "Back out onto the page", out: letGo }
    : null,
);
