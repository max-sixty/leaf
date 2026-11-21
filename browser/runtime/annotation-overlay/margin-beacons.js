/* Beacons: a mark at the window's edge for each active thread scrolled out of view.

   A thread is active while its margin entry says something waits there: a reply the
   user hasn't read, the user's turn, or the agent at work on it (`activeItems`). While
   an active thread's entry stands above the window, a beacon stands at the window's
   head in the entry's column, and while it stands below, at the window's foot. The user
   asked for this so that news arriving on a part of the page they have scrolled away
   from shows which way it is, where before only the leaf's dot said that it had come.
   A beacon wears its entry's face, colours and dot at the aim floor, with an
   arrowhead pointing toward the entry, previews its threads as the entry does, and a press goes to the thread as a
   Page Map row does (thread/destination.js, `openPageThread`). It holds no keyboard
   stop, since `t` already walks the user to every open thread and `m` to every one
   whose turn is theirs, and the accessibility tree leaves it out, since what it says is
   where a thread stands on screen.

   Each beacon is a sticky box, which the browser keeps level with its entry while the
   entry shows and holds at the window's edge once it doesn't, so a scroll moves it with
   no script and in the same frame. A sticky box stays inside its containing block, so
   each beacon stands in a track as tall as the body, after a spacer as tall as its
   entry's seat: a margin as the seat would keep it from rising past its seat to the
   foot. The tracks stand beneath the rows (annotation-theme.css), so a beacon lies
   hidden under its entry while the entry shows, and a scroll carrying the entry away
   uncovers it. Each thread has a beacon for each edge, sticky at that edge alone, so
   each wears its own direction's arrowhead without knowing whether it is held there.
   Where several stand at one edge they lie one over another, and the nearest to the
   window shows: `place` orders the tracks so it paints last. A count of the others
   there would need to know which beacons the window holds at its edge, a reading of
   every scroll that the sticky box spares.

   A beacon keeps company only with a row the document's scroll carries
   (margin-layout.js, `documentSeat`): a row in a pane, a carrier or a frame a sticky
   header cuts gets none, since a scroll other than the document's moves it. */
import {
  contributionEntry,
  presentContributionEntry,
  presentContributionReceipts,
} from "../contribution-controls.js";
import { KINDS } from "../contribution-model.js";
import { awaitingUser, threadReading, unreadIn } from "../margin-model.js";
import { threadPreview } from "../thread/messages.js";
import { threadNamed } from "../thread/state.js";
import { progressFace } from "../thread/workflow.js";
import { setChildren } from "../dom-children.js";
import { cancelRender, nextRender } from "../rendering.js";
import { keeps, layoutPx, inlineStyle } from "../keeps.js";
import { el, offerActionElement } from "../widget-elements.js";
import { layoutWindow, shownWindow } from "../geometry.js";
import { documentSeat } from "./margin-layout.js";

/** @typedef {import("../annotation-inventory.js").InventoryEntry} Entry
 * @typedef {import("../margin-model.js").ThreadItem} Item
 * @typedef {import("../margin-model.js").ThreadChoice} ThreadChoice
 * @typedef {"up" | "down"} Towards
 * @typedef {{track: HTMLElement, at: HTMLElement, beacon: HTMLElement}} Beacon
 * @typedef {{up: Beacon, down: Beacon, thread: string}} Pair */

const TOWARDS = /** @type {const} */ ({ up: "Thread above", down: "Thread below" });

/** @param {{openPageThread: ReturnType<typeof import("../thread/destination.js").createThreadDestinations>["openPageThread"],
 * workflowReceipt: ReturnType<typeof import("../annotation-inventory.js").createAnnotationInventory>["workflowReceipt"]}} dependencies */
export function createMarginBeacons({ openPageThread, workflowReceipt }) {
  const lane = el("div", "lf-margin-beacons");
  lane.setAttribute("aria-hidden", "true");
  /** @type {Map<HTMLElement, Pair>} */
  const pairs = new Map();
  // A pair drawn or retired stands by the seat the last pass gave its row, or hides
  // until the pass a new row asks for seats it.
  let pending = 0;
  const schedule = () => {
    pending ||= nextRender(place);
  };

  // A thread item says something waits on it: news the user hasn't read, the user's
  // turn, or the agent at work on it now.
  /** @param {Item} item */
  const active = (item) =>
    Boolean(item.unread) ||
    Boolean(item.userAttention) ||
    progressFace(workflowReceipt([item])) === "working";
  /** @param {Entry} entry */
  const activeItems = (entry) =>
    (/** @type {ThreadChoice | null} */ (threadReading(entry))?.items ?? []).filter(
      active,
    );

  /** @param {Towards} towards @param {HTMLElement} row */
  function makeBeacon(towards, row) {
    const track = el("div", "lf-margin-beacon-track");
    const at = el("div", "lf-margin-beacon-at");
    const beacon = offerActionElement(
      document.createElement("span"),
      "entry",
      "lf-margin-beacon",
    );
    keeps(beacon, "data-lf-towards", towards);
    keeps(beacon, "data-lf-kinds", "comment");
    beacon.onclick = () => {
      const pair = pairs.get(row);
      if (pair) void openPageThread(pair.thread);
    };
    track.append(at, beacon);
    return { track, at, beacon };
  }

  // Draws the beacons a row's entry asks for: a pair while one of its threads is
  // active, painted as the entry paints it, and none otherwise.
  /** @param {HTMLElement} row @param {Entry} entry */
  function present(row, entry) {
    const items = activeItems(entry);
    const [first] = items;
    if (!first) {
      retire(row);
      return;
    }
    let pair = pairs.get(row);
    if (!pair) {
      pair = { up: makeBeacon("up", row), down: makeBeacon("down", row), thread: "" };
      pairs.set(row, pair);
      schedule();
    }
    pair.thread = first.thread.id;
    for (const towards of /** @type {const} */ (["up", "down"])) {
      const { beacon } = pair[towards];
      presentContributionEntry(
        beacon,
        contributionEntry({
          key: `beacon:${towards}`,
          icon: KINDS.comment.icon,
          label: TOWARDS[towards],
          behavior: "disclosure",
          rank: "reading",
        }),
        {
          writesRelation: false,
          writesSeat: false,
          unread: unreadIn(items) > 0,
          preview: () =>
            threadPreview(
              items.map((item) => threadNamed(item.thread.id) ?? item.thread),
            ),
        },
      );
      presentContributionReceipts(beacon, workflowReceipt(items), awaitingUser(items));
    }
  }

  /** @param {HTMLElement} row */
  function retire(row) {
    const pair = pairs.get(row);
    if (!pair) return;
    pair.up.track.remove();
    pair.down.track.remove();
    pairs.delete(row);
    schedule();
  }

  // How much of the window's foot the chrome covers in a row's column, as the floating
  // panel does where it stands under the column: the beacon at the foot stands above it,
  // and a column beside the panel keeps the window's whole height.
  /** @param {HTMLElement} row */
  function footCover(row) {
    const entry = row.querySelector(".lf-margin-entry:not([hidden])");
    if (!entry) return 0;
    const { left, right } = entry.getBoundingClientRect();
    return Math.max(
      0,
      layoutWindow().bottom -
        shownWindow({ viewport: "layout", across: { left, right } }).bottom,
    );
  }

  // Stands each beacon by its row where the margin's last pass seated the row, and takes
  // out a pair whose row a scroll other than the document's may move. Every read comes
  // before every write: the pass read the seats it reports (`documentSeat`).
  function place() {
    cancelRender(pending);
    pending = 0;
    const seats = [...pairs].flatMap(([row, pair]) => {
      const seat = documentSeat(row);
      return seat ? [{ pair, seat, cover: footCover(row) }] : [];
    });
    /** @type {{pair: Pair, top: number}[]} */
    const shown = [];
    let extent = 0;
    for (const { pair, seat, cover } of seats) {
      for (const towards of /** @type {const} */ (["up", "down"])) {
        const { track, at } = pair[towards];
        keeps(track, "data-lf-place", seat.place);
        inlineStyle(track).setProperty("margin-left", layoutPx(seat.left));
        inlineStyle(at).setProperty("height", layoutPx(seat.top));
      }
      inlineStyle(pair.down.beacon).setProperty("--lf-beacon-cover", layoutPx(cover));
      extent = seat.extent;
      shown.push({ pair, top: seat.top });
    }
    inlineStyle(lane).setProperty("height", layoutPx(extent));
    // Of the beacons held at one edge, the one nearest the window paints last: at the
    // head the lowest entry above it, at the foot the highest below it.
    shown.sort((a, b) => a.top - b.top);
    setChildren(lane, [
      ...shown.map(({ pair }) => pair.up.track),
      ...shown.toReversed().map(({ pair }) => pair.down.track),
    ]);
  }

  return { element: lane, present, retire, place };
}
