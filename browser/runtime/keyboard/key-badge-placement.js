/* Shared visibility for addressable targets and placement for command
   binding badges. The chrome clips every target's usable box. A binding face hangs off its
   control's upper-left corner, and off another of its corners where that one would cover
   a different control: a digit laid over a neighbour's corner reads as that neighbour's.
   It may move back inside the viewport, but it yields wherever that move would cover
   fixed chrome or another badge: its ordered choices make a missing digit inferable. Opaque generated target
   hints instead use the no-drop placement in hints.js.

   One pass constructs this reading once and asks it for every member, so the clips over
   shared ancestors are walked once and every member is admitted, tested for exposure,
   and painted against the same chrome.

   Two readings of a member's usable box stand here, and what differs between them is
   which box they start from rather than what the user can see of it. `badgeBox` starts
   at the member's own corner — the corner a badge hangs off, which for an inline run that
   wraps is not the middle of its bounds. `visibleBounds` starts at the member's whole box,
   which is how the target picker both admits a member and seats its chip. Both are then
   held clear of the same room by `clearBox` and tested by the same `exposes`, so both maps
   promise the user the same thing by "visible". `clearPart` answers for a box with no
   element of its own and is the one reading that does subtract the chrome at the foot,
   because what it measures is drawn where it stands rather than moved somewhere legible. */
import { closestAcross, elementFromPointAcross, inChrome } from "../passages.js";
import { PRESSES } from "../control-selectors.js";
import {
  layoutWindow,
  windowChromeBoxes,
  shownParts,
  shownRect,
  startsAt,
} from "../geometry.js";
import { clamp, intersect, overlaps } from "../rect.js";
import { renderedUnder } from "../shadow.js";

/** @typedef {import("../rect.js").Box} Box
 * @typedef {NonNullable<ReturnType<typeof rect>>} VisibleBox
 * @typedef {{seat: HTMLElement, owner: Element, corner: Pick<Box, "left" | "top" | "right" | "bottom">}} BindingChip
 */

// A rectangle, or nothing where its edges crossed. `clippedTop` records that the source
// box began above the room the user has, which a chip hung on the surviving corner
// needs in order to say so.
/** @param {number} left @param {number} top @param {number} right @param {number} bottom @param {number} [sourceTop] */
const rect = (left, top, right, bottom, sourceTop = top) =>
  right > left && bottom > top
    ? {
        left,
        top,
        right,
        bottom,
        width: right - left,
        height: bottom - top,
        clippedTop: sourceTop < top,
      }
    : null;

export function keyBadgePlacement() {
  /** @type {import("../geometry.js").ClipCache} */
  const clips = new Map();
  const room = layoutWindow();
  const chrome = windowChromeBoxes();
  const kept = [...chrome];

  // What the user can see of a box: the window.
  //
  // Chrome at the foot stays in it, so a map's members are never decided by it: the
  // floating panel's row states the armed map's filter and changes as the user types it,
  // so a map that read it would lose members as it armed and swap codes as its own
  // legend grew. A chip that would land there is moved by the placement pass instead
  // (`spreadHints`, hints.js), which keeps the route where dropping the member loses it.
  /** @param {Box | null | undefined} box @param {number} [sourceTop] */
  const clearBox = (box, sourceTop = box?.top) => {
    if (!box) return null;
    const { left, top, right, bottom } = intersect(box, room);
    return rect(left, top, right, bottom, sourceTop);
  };

  // The same, less the boxes chrome paints over the page: each blocker divides a box
  // crossing it into the space above, below, before, or after it, and the largest part
  // wins. This is for a search mark, which unlike a chip cannot be moved somewhere legible,
  // because where it is drawn is what it says. A blocker is its own rectangle here; taking
  // the lane below it as well would take the gutter with it. The chip pass does reserve
  // that lane (`lineBand`, hints.js), having somewhere else to put the chip.
  /** @param {Box} box @param {number} sourceTop */
  function clearOfChrome(box, sourceTop) {
    const shown = clearBox(box, sourceTop);
    if (!shown) return null;
    return (
      chrome
        .reduce(
          (available, blocker) =>
            available.flatMap((part) =>
              overlaps(part, blocker)
                ? [
                    rect(
                      part.left,
                      part.top,
                      part.right,
                      Math.min(part.bottom, blocker.top),
                      sourceTop,
                    ),
                    rect(
                      part.left,
                      part.top,
                      Math.min(part.right, blocker.left),
                      part.bottom,
                      sourceTop,
                    ),
                    rect(
                      Math.max(part.left, blocker.right),
                      part.top,
                      part.right,
                      part.bottom,
                      sourceTop,
                    ),
                    rect(
                      part.left,
                      Math.max(part.top, blocker.bottom),
                      part.right,
                      part.bottom,
                      sourceTop,
                    ),
                  ].filter((part) => part !== null)
                : [part],
            ),
          [shown],
        )
        .sort((a, b) => b.width * b.height - a.width * a.height)[0] ?? null
    );
  }

  // Where a member begins, held clear of chrome: the corner a badge hangs off, which for
  // an inline run that wraps is not the middle of its bounds.
  /** @param {Element} item */
  const badgeBox = (item) => clearBox(startsAt(item, clips));
  // An item's whole box, held clear of chrome, for a member addressed as one block.
  /** @param {Element} item */
  const visibleBounds = (item) => clearBox(shownRect(item, clips));
  // The clip an item's own ancestors put over what it holds, for a box measured from a
  // Range rather than from an element.
  /** @param {Element} item */
  const clipOver = (item) => shownRect(item, clips);
  // A box with no element of its own, through the clip over the element that owns it.
  /** @param {Box | null} box @param {Box | null} clip */
  const clearPart = (box, clip) =>
    box && clip ? clearOfChrome(intersect(box, clip), box.top) : null;

  // Whether the user can see what this box was measured from. Geometry cannot answer it:
  // a panel, a fixed sheet or an ordinary page box covers a member without clipping
  // its rectangle. Ask the rendered stack inside the box, and make the member itself answer,
  // a cover being exactly the case where something else does. Most chrome answers, which is
  // how a card behind the open panel leaves the map. A hint layer takes no presses, so a
  // chip cannot answer for the member under it. A box with no member of its own — a
  // Range's, which may run across several blocks — takes any page element, no one element
  // owning the whole box.
  /** @param {Element | null} member @param {Box | null} box @param {"across" | "self"} [exposure] */
  const exposes = (member, box, exposure = "across") => {
    if (!box) return false;
    // Ask inside a box the member actually paints. Its bounds are not always one of them:
    // a `display: contents` element's are the union of its children's, and the space
    // between two of them belongs to whatever stands behind.
    const painted = member ? shownParts(member) : [];
    const aims =
      painted.length === 1 && painted[0] === member
        ? [box]
        : painted
            .map((part) => part.getBoundingClientRect())
            .filter((part) => overlaps(part, box))
            .map((part) => intersect(part, box));
    return (aims.length ? aims : [box]).some((aim) => {
      const onTop = elementFromPointAcross(
        clamp((aim.left + aim.right) / 2, 0, room.right - 1),
        clamp((aim.top + aim.bottom) / 2, room.top, room.bottom - 1),
      );
      if (!member) return !inChrome(onTop);
      return exposure === "self"
        ? member.contains(onTop)
        : renderedUnder(onTop, member);
    });
  };

  // A page-local target hint cannot be moved by the chrome pass, but it reserves its own
  // visible box so later chrome badges cannot claim the same pixels.
  /** @param {Box | null | undefined} box */
  function reserve(box) {
    if (
      !box ||
      box.right <= box.left ||
      box.bottom <= box.top ||
      kept.some((other) => overlaps(box, other))
    )
      return false;
    kept.push(box);
    return true;
  }

  // Whether a chip's box stands over a control other than the one it labels: asked of the
  // rendered stack at its middle and just inside each corner, as `exposes` asks, since a
  // box can stand over a control without the control's rectangle saying so.
  /** @param {Box} box @param {Element} owner */
  function coversAnotherControl(box, owner) {
    const inset = 1;
    /** @type {[number, number][]} */
    const points = [
      [(box.left + box.right) / 2, (box.top + box.bottom) / 2],
      [box.left + inset, box.top + inset],
      [box.right - inset, box.top + inset],
      [box.left + inset, box.bottom - inset],
      [box.right - inset, box.bottom - inset],
    ];
    return points.some(([x, y]) => {
      const press = closestAcross(elementFromPointAcross(x, y), PRESSES);
      return press && !renderedUnder(press, owner) && !renderedUnder(owner, press);
    });
  }

  // Measure every rendered binding chip before seating or hiding any. Each names
  // its seat (chip-seats.js), the control it labels, and the
  // corner box the chip hangs off; a chip moves to the first corner of that box whose
  // place, pulled back inside the window, covers no other control and no chrome or
  // badge, and failing every one keeps the first corner's place where that is free. A
  // chip with no room is hidden rather than removed, so a pass that changes nothing
  // writes nothing.
  /** @param {ReturnType<typeof import("./chip-seats.js").chipSeats>} seats @param {readonly BindingChip[]} chips */
  function paint(seats, chips) {
    const { right, bottom } = layoutWindow();
    const measured = chips.map((one) => ({
      ...one,
      ...seats.measure(one.seat, one.corner),
    }));
    /** @param {Box} box */
    const free = (box) =>
      box.right > box.left &&
      box.bottom > box.top &&
      !kept.some((other) => overlaps(box, other));
    const seated = [];
    for (const { chip, seat, owner, corner, box: start } of measured) {
      /** @type {[number, number][]} */
      const corners = [
        [corner.left, corner.top],
        [corner.right, corner.top],
        [corner.left, corner.bottom],
        [corner.right, corner.bottom],
      ];
      /** @param {[number, number]} corner */
      const placeAt = ([x, y]) => {
        const left = start.left + x - corner.left;
        const top = start.top + y - corner.top;
        const place = new DOMRect(
          clamp(left, 0, right - start.width),
          clamp(top, room.top, bottom - start.height),
          start.width,
          start.height,
        );
        // Pulled down below the window's head or up above its foot, the chip is held
        // by that edge rather than by its control's corner.
        return Object.assign(place, { held: Math.abs(place.top - top) >= 0.5 });
      };
      const places = corners.map(placeAt);
      const box =
        places.find((place) => free(place) && !coversAnotherControl(place, owner)) ??
        placeAt([corner.left, corner.top]);
      if (!reserve(box)) {
        if (chip.style.visibility !== "hidden") chip.style.visibility = "hidden";
      } else if (chip.style.visibility) chip.style.removeProperty("visibility");
      seated.push({ seat, target: owner, at: corner, start, box, held: box.held });
    }
    seats.place(seated);
  }

  return {
    badgeBox,
    clearPart,
    clipOver,
    exposes,
    paint,
    reserve,
    visibleBounds,
  };
}
