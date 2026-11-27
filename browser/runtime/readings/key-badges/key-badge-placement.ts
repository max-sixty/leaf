/* Shared visibility for addressable targets and placement for command
   binding badges. The window bounds every target's usable box. A binding face hangs off its
   control's upper-left corner, and off another of its corners where that one would cover
   a different control: a digit laid over a neighbour's corner reads as that neighbour's.
   It may move back inside the viewport, but it yields wherever that move would cover
   fixed chrome or another badge: its ordered choices make a missing digit inferable. Opaque generated target
   hints instead spread apart while each still reads as its own target's (hints.js,
   `seatHints`).

   Once seated, a chip keeps its corner while that corner still serves. A pass reads the
   frame as it stands, where a corner's room can turn on a pixel: a pressed button
   shrinks by Web Awesome's press scale, which frees the corner beside its neighbour
   until the press ends, so a chip chosen afresh on each pass would cross its control
   and back with every press. Rejected: reading the control's box without its
   transforms, which a table translated into place or a deck's scaled slide needs
   (dom/css-anchors.js, `anchorBox`), and which would still flip on any other pixel's
   change, such as a reflow.

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
   because what it measures is drawn where it stands rather than moved somewhere legible:
   it reads what the user sees of it as every reading of what is seen does (dom/geometry.js,
   `inFront`, the rule `seenRect` cuts with), so a search match in the band an open panel
   view covers is out of sight there, its part beside the view included. Where a chip may
   stand is a different question, answered by the boxes it keeps clear of whole
   (`reserve`, `paint`): a chip can move somewhere legible, so it keeps off every pixel of
   the chrome, the side of a view included, but for the surface holding its control,
   whose own controls' chips stand on it (dom/geometry.js, `coverBoxes`). */
import { elementFromPointAcross } from "../passages.js";
import { PRESSES } from "../../dom/control-selectors.js";
import {
  coverBoxes,
  inFront,
  layoutWindow,
  shownParts,
  shownRect,
  startsAt,
} from "../../dom/geometry.js";
import { clamp, intersect, overlaps } from "../../dom/rect.js";
import { renderedUnder, closestAcross } from "../../lib/shadow-tree.js";
import { inChrome } from "../../base/ui-marks.js";
import type { Box } from "../../base/box.js";
import type { ClipCache } from "../../dom/geometry.js";
import type { chipSeats } from "./chip-seats.js";

type BindingChip = {
  seat: HTMLElement;
  owner: Element;
  corner: Pick<Box, "left" | "top" | "right" | "bottom">;
};

// A rectangle, or nothing where its edges crossed. `clippedTop` records that the source
// box began above the room the user has, which a chip hung on the surviving corner
// needs in order to say so.
const rect = (
  left: number,
  top: number,
  right: number,
  bottom: number,
  sourceTop: number = top,
) =>
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

// The corner each binding chip's seat was last placed at, as an index into `paint`'s
// corners. A seat lasts while its control stays in reach (chip-seats.js), so this lasts
// as long as the chip shows.
const seatedCorner = new WeakMap<HTMLElement, number>();

export function keyBadgePlacement() {
  const clips: ClipCache = new Map();
  const room = layoutWindow();
  const kept: Box[] = [];
  // Whether `box` keeps clear of the chrome over `owner` and of every box reserved so far.
  const clear = (box: Box, owner: Element) =>
    ![...coverBoxes(owner), ...kept].some((other) => overlaps(box, other));

  // What the user can see of a box: the window.
  //
  // Chrome at the foot stays in it, so a map's members are never decided by it: the
  // floating panel's row states the armed map's filter and changes as the user types it,
  // so a map that read it would lose members as it armed and swap codes as its own
  // legend grew. A chip that would land there is moved by the placement pass instead
  // (`seatHints`, hints.js), or withheld where no move leaves it reading as its own
  // target's, and its member stays in the map either way.
  const clearBox = (
    box: Box | null | undefined,
    sourceTop: number | undefined = box?.top,
  ) => {
    if (!box) return null;
    const { left, top, right, bottom } = intersect(box, room);
    return rect(left, top, right, bottom, sourceTop);
  };

  // Where a member begins, held inside the window: the corner a badge hangs off, which for
  // an inline run that wraps is not the middle of its bounds.
  const badgeBox = (item: Element) => clearBox(startsAt(item, clips));
  // An item's whole box, held inside the window, for a member addressed as one block.
  const visibleBounds = (item: Element) => clearBox(shownRect(item, clips));
  // The clip an item's own ancestors put over what it holds, for a box measured from a
  // Range rather than from an element.
  const clipOver = (item: Element) => shownRect(item, clips);
  // What the user sees of a box with no element of its own, through the clip over the
  // element that owns it (`clipOver`), the window and the chrome's covers (see the
  // header).
  const clearPart = (box: Box | null, clip: Box | null, owner: Element) => {
    const seen = box && clip && inFront(intersect(box, clip), owner);
    return seen && rect(seen.left, seen.top, seen.right, seen.bottom, box.top);
  };

  // Whether the user can see what this box was measured from. Geometry cannot answer it:
  // a panel, a fixed sheet or an ordinary page box covers a member without clipping
  // its rectangle. Ask the rendered stack inside the box, and make the member itself answer,
  // a cover being exactly the case where something else does. Most chrome answers, which is
  // how a card behind the open panel leaves the map. A hint layer takes no presses, so a
  // chip cannot answer for the member under it. A box with no member of its own — a
  // Range's, which may run across several blocks — takes any page element, no one element
  // owning the whole box.
  const exposes = (
    member: Element | null,
    box: Box | null,
    exposure: "across" | "self" = "across",
  ) => {
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
  function reserve(box: Box | null | undefined, owner: Element) {
    if (!box || box.right <= box.left || box.bottom <= box.top || !clear(box, owner))
      return false;
    kept.push(box);
    return true;
  }

  // Whether a chip's box stands over a control other than the one it labels: asked of the
  // rendered stack at its middle and just inside each corner, as `exposes` asks, since a
  // box can stand over a control without the control's rectangle saying so.
  function coversAnotherControl(box: Box, owner: Element) {
    const inset = 1;
    const points: [number, number][] = [
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
  // corner box the chip hangs off; a chip keeps the corner it was last placed at while
  // that place, pulled back inside the window, covers no other control and no chrome or
  // badge, and otherwise moves to the first corner whose place does, failing every one
  // keeping the first corner's place where that is free. A
  // chip with no room is hidden rather than removed, so a pass that changes nothing
  // writes nothing.
  function paint(seats: ReturnType<typeof chipSeats>, chips: readonly BindingChip[]) {
    const { right, bottom } = layoutWindow();
    const measured = chips.map((one) => ({
      ...one,
      ...seats.measure(one.seat, one.corner),
    }));
    const free = (box: Box, owner: Element) =>
      box.right > box.left && box.bottom > box.top && clear(box, owner);
    const seated = [];
    for (const { chip, seat, owner, corner, box: start } of measured) {
      const corners: [number, number][] = [
        [corner.left, corner.top],
        [corner.right, corner.top],
        [corner.left, corner.bottom],
        [corner.right, corner.bottom],
      ];
      const placeAt = ([x, y]: [number, number]) => {
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
      const serves = (place: DOMRect) =>
        free(place, owner) && !coversAnotherControl(place, owner);
      const stood = places[seatedCorner.get(seat) ?? -1];
      const box =
        (stood && serves(stood) ? stood : places.find(serves)) ??
        placeAt([corner.left, corner.top]);
      seatedCorner.set(seat, Math.max(places.indexOf(box), 0));
      seated.push({
        seat,
        chip,
        shows: reserve(box, owner),
        target: owner,
        at: corner,
        start,
        box,
        held: box.held,
      });
    }
    // Written once every chip is placed: a chip takes no presses (chrome.css,
    // `.lf-chip-seat`), so none is in the stack another chip's place reads.
    for (const { chip, shows } of seated)
      if (shows) chip.style.removeProperty("visibility");
      else chip.style.visibility = "hidden";
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
