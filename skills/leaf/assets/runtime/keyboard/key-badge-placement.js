/* Shared visibility for addressable targets and placement for predictable numeric Ask
   binding badges. The banner clips every target's usable box. An Ask face may move back inside
   the viewport, but it yields wherever that move would cover fixed chrome or another
   badge: its ordered choices make a missing digit inferable. Opaque generated target
   hints instead use the no-drop placement in hints.js.

   One pass constructs this reading once and asks it for every member, so the clips over
   shared ancestors are walked once and every member is admitted, tested for exposure,
   and painted against the same chrome.

   Two readings of a member's usable box stand here, and the difference between them is
   what the box is for. `badgeBox` starts at the member's own corner — the corner a badge
   hangs off, which for an inline run that wraps is not the middle of its bounds — and
   clamps it to the banner; an Ask badge and a Go-to hint are then either reserved,
   spread, or dropped on the hit test, so neither needs more. `visibleBounds` instead cuts
   the bottom chrome's lanes out of a member's whole box and answers with the largest part
   the reader can still use, which is how the target chooser both admits a member and
   seats its chip. The two therefore disagree about a member behind the shortcut bar: the
   Go-to map keeps its route and spreads the chip clear, while the chooser drops it. That
   is a product question about what "visible" promises, not a difference in the geometry,
   and it is now one edit rather than two. */
import { banner } from "../banner.js";
import { bottomChromeBoxes } from "./shortcut-bar.js";
import { overlaps, shownRect, startsAt } from "../geometry.js";

// The top of the room the reader has. Chrome above the page covers what it stands over
// without clipping those boxes, so every reading of usable room starts below it.
export const chromeTop = () => banner.getBoundingClientRect().bottom;

// A rectangle, or nothing where its edges crossed. `clippedTop` records that the source
// box began above the room the reader has, which a chip hung on the surviving corner
// needs in order to say so.
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
  const clips = new Map();
  const covered = chromeTop();
  const chrome = bottomChromeBoxes();
  const kept = [...chrome];

  // Read every member through one clip cache. The banner covers page content without
  // clipping its boxes; clamp the usable box to the banner so admission, exposure, and
  // paint all read the same visible target.
  function badgeBox(target) {
    const box = startsAt(target, clips);
    return box && box.bottom > covered
      ? { ...box, top: Math.max(box.top, covered) }
      : null;
  }

  // The largest visible rectangle left after viewport chrome is subtracted. The banner
  // spans the window and clips one edge. Bottom chrome reserves its whole lane to the
  // viewport foot. Each blocker divides a target crossing it into the open space above,
  // below, before, or after it.
  //
  // A coarse pointer is shown no line, and an empty one takes itself down. A zero box must
  // therefore answer with the viewport foot rather than a top of 0, or the target chooser
  // names no items and page search paints no match with nothing on screen saying why.
  function clearBox(box, sourceTop = box?.top) {
    if (!box) return null;
    const shown = rect(
      Math.max(box.left, 0),
      Math.max(box.top, covered),
      Math.min(box.right, innerWidth),
      Math.min(box.bottom, innerHeight),
      sourceTop,
    );
    if (!shown) return null;
    const lanes = chrome.map((box) => ({
      left: box.left,
      top: box.top,
      right: box.right,
      bottom: innerHeight,
    }));
    return (
      lanes
        .reduce(
          (available, lane) =>
            available.flatMap((part) =>
              overlaps(part, lane)
                ? [
                    rect(
                      part.left,
                      part.top,
                      part.right,
                      Math.min(part.bottom, lane.top),
                      sourceTop,
                    ),
                    rect(
                      part.left,
                      part.top,
                      Math.min(part.right, lane.left),
                      part.bottom,
                      sourceTop,
                    ),
                    rect(
                      Math.max(part.left, lane.right),
                      part.top,
                      part.right,
                      part.bottom,
                      sourceTop,
                    ),
                    rect(
                      part.left,
                      Math.max(part.top, lane.bottom),
                      part.right,
                      part.bottom,
                      sourceTop,
                    ),
                  ].filter(Boolean)
                : [part],
            ),
          [shown],
        )
        .sort((a, b) => b.width * b.height - a.width * a.height)[0] ?? null
    );
  }

  // An item's whole box, held clear of chrome, for a member addressed as one block.
  const visibleBounds = (item) => clearBox(shownRect(item, clips));
  // The clip an item's own ancestors put over what it holds, for a box measured from a
  // Range rather than from an element.
  const clipOver = (item) => shownRect(item, clips);
  // A box with no element of its own, through the clip over the element that owns it.
  const clearPart = (box, clip) =>
    box && clip
      ? clearBox(
          {
            left: Math.max(box.left, clip.left),
            top: Math.max(box.top, clip.top),
            right: Math.min(box.right, clip.right),
            bottom: Math.min(box.bottom, clip.bottom),
          },
          box.top,
        )
      : null;

  // A page-local target hint cannot be moved by the chrome pass, but it reserves its own
  // visible box so later chrome badges cannot claim the same pixels.
  function reserve(box) {
    if (
      !box ||
      box.right <= box.left ||
      box.bottom <= box.top ||
      kept.some((standing) => overlaps(box, standing))
    )
      return false;
    kept.push(box);
    return true;
  }

  // Attach every Ask chip in one write, measure them before moving or removing any, then
  // adjust its authored CSS anchor by the clamp delta.
  function paint(layer, chips) {
    layer.replaceChildren(...chips);
    const right = document.documentElement.clientWidth;
    const bottom = document.documentElement.clientHeight;
    const measured = chips.map((chip) => ({
      chip,
      start: chip.getBoundingClientRect(),
      left: Number.parseFloat(chip.style.left),
      top: Number.parseFloat(chip.style.top),
    }));
    for (const { chip, start, left, top } of measured) {
      const box = new DOMRect(
        Math.max(0, Math.min(start.left, right - start.width)),
        Math.max(covered, Math.min(start.top, bottom - start.height)),
        start.width,
        start.height,
      );
      if (!reserve(box)) chip.remove();
      else {
        chip.style.left = `${left + box.left - start.left}px`;
        chip.style.top = `${top + box.top - start.top}px`;
      }
    }
  }

  return {
    badgeBox,
    clearPart,
    clipOver,
    paint,
    reserve,
    visibleBounds,
  };
}
