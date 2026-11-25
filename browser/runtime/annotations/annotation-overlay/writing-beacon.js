/* The beacon: a mark at the window's edge, pointing toward the comment box the user's
   keys type into, while a scroll has carried that box out of the window.

   A comment box floating over the page, a thread card's reply or the anchored comment
   box, rides away with what it is about when the page scrolls, and keeps the caret: a
   letter typed there types into the box and brings it back (readings/off-flow.js), where on the
   page a letter is a command. Focus on any other control the user has scrolled away
   from lets go at the next key (panel/page-keys/controller.js), so a box holding the caret is
   the one place out of sight that a key acts on. The user asked for a mark there, so
   they see where their keys go before pressing one, and only there: they rejected a
   mark for every thread with news scrolled out of the window, which no key reaches. A
   box holds the caret whether or not it holds words, so an empty one keeps the keys
   and has the mark too. The user chose that over letting an empty box go at the next
   key like any other control: a stray letter in the box costs a backspace, while a
   sentence typed into a box that let go runs as page commands, `t` walking to another
   thread and `r` resolving it.
   The floating panel's comment field never leaves the window and needs none.

   The beacon stands while the user sees none of the box (dom/geometry.js, `seenRect`), as
   the surface holding it draws it (readings/off-flow.js, `floatingBox`), at the edge toward it,
   in the box's column, inside what the page shows of the window
   there: below a sticky strip at the head, and above the panel where it covers the
   column at the foot. It wears a thread entry's face at the aim floor, with an
   arrowhead toward the box, and previews its word. A press stands for a press in the
   box (dom/focus.js, `standsFor`), so it puts nothing away and leaves the caret where it
   was, and brings the box back as typing would, so the user goes on typing there. It
   holds no keyboard stop, since typing is the keyboard's route to the box and Escape
   leaves it, and the accessibility tree leaves it out, since what it says is where the
   box stands on screen.

   It is fixed at the window's edge rather than following content, so a script stands
   it: each rendering pass that a change in what the window shows (dom/geometry.js,
   `watchRoom`, a scroll included) or the box crossing the window asks for reads where
   the box stands and then writes the beacon, as `whenNone` (dom/geometry.js) reads its
   watches. Rejected: a sticky
   box, which the browser stands with no script but which needs the box's place in the
   document, which a card's news and the reply's own lines move; and a box anchored to
   the card and held at the edge by `max()`, which Firefox leaves where it was laid
   out, carrying it with the card through a scroll rather than placing it again. */
import {
  contributionEntry,
  presentContributionEntry,
} from "../../features/contribution-controls.js";
import { KINDS } from "../../base/contribution-model.js";
import { onCurrentLocation, standsFor, typesText } from "../../dom/focus.js";
import { floatingBox, bringBackSurfaceOf } from "../../readings/off-flow.js";
import { cancelRender, nextRender } from "../../lib/frame-pass.js";
import { keeps, layoutPx, inlineStyle } from "../../lib/keeps.js";
import { offerActionElement } from "../../lib/controls.js";
import { layoutWindow, seenRect, shownWindow, watchRoom } from "../../dom/geometry.js";
import { chromeRoot, chromeForeground } from "../../base/chrome.js";
import { move } from "../../dom/dom-move.js";

/** @typedef {"up" | "down"} Towards */

const WORDS = /** @type {const} */ ({
  up: "Comment box above",
  down: "Comment box below",
});

export function createWritingBeacon() {
  const beacon = offerActionElement(
    document.createElement("span"),
    "entry",
    "lf-writing-beacon",
  );
  beacon.setAttribute("aria-hidden", "true");
  keeps(beacon, "data-lf-kinds", "comment");
  keeps(beacon, "hidden", "");
  beacon.addEventListener("mousedown", (event) => event.preventDefault());
  standsFor(beacon, () => field);
  beacon.onclick = () => {
    if (field) bringBackSurfaceOf(field);
  };
  /** @type {Towards | null} */
  let drawn = null;
  // The text field holding the caret in a floating box, and the watch on its box.
  /** @type {Element | null} */
  let field = null;
  /** @type {(() => void) | null} */
  let unwatch = null;
  let pending = 0;
  const schedule = () => {
    pending ||= nextRender(stand);
  };
  // The box crossing the window by a change of layout, with no scroll.
  const crossing = new IntersectionObserver(schedule);

  onCurrentLocation((node) => {
    const box = node && typesText(node) ? floatingBox(node) : null;
    const next = box ? node : null;
    if (next === field) return;
    field = next;
    crossing.disconnect();
    if (box) {
      crossing.observe(box);
      unwatch ??= watchRoom(schedule);
    } else {
      unwatch?.();
      unwatch = null;
    }
    schedule();
  });

  function stand() {
    cancelRender(pending);
    pending = 0;
    const frame = field && floatingBox(field);
    const box = frame?.getBoundingClientRect();
    if (!frame || !box?.width || seenRect(frame, new Map())) return draw(null);
    const view = layoutWindow();
    const left = Math.min(Math.max(box.left, view.left), view.right);
    const shown = shownWindow({
      viewport: "layout",
      across: { left, right: left + beacon.offsetWidth },
    });
    draw({
      towards: box.top + box.bottom < view.top + view.bottom ? "up" : "down",
      left,
      head: shown.top - view.top,
      foot: view.bottom - shown.bottom,
    });
  }

  /** @param {{towards: Towards, left: number, head: number, foot: number} | null} at */
  function draw(at) {
    keeps(beacon, "hidden", at ? null : "");
    if (!at) return;
    const { towards } = at;
    if (!beacon.isConnected) move(chromeRoot, beacon, chromeForeground);
    keeps(beacon, "data-lf-towards", towards);
    const style = inlineStyle(beacon);
    style.setProperty("--lf-beacon-left", layoutPx(at.left));
    style.setProperty("--lf-beacon-head", layoutPx(at.head));
    style.setProperty("--lf-beacon-foot", layoutPx(at.foot));
    if (drawn === towards) return;
    drawn = towards;
    presentContributionEntry(
      beacon,
      contributionEntry({
        key: `beacon:${towards}`,
        icon: KINDS.comment.icon,
        label: WORDS[towards],
        behavior: "disclosure",
        rank: "reading",
      }),
      { writesRelation: false, writesSeat: false },
    );
  }
}
