/* Shared visibility for addressable targets and placement for predictable numeric Ask
   binding badges. The banner clips every target's usable box. An Ask face may move back inside
   the viewport, but it yields wherever that move would cover fixed chrome or another
   badge: its ordered choices make a missing digit inferable. Opaque generated target
   hints instead use the no-drop placement in hints.js.

   One pass constructs this reading once and asks it for every member, so the clips over
   shared ancestors are walked once and every member is admitted, tested for exposure,
   and painted against the same chrome.

   Two readings of a member's usable box stand here, and what differs between them is
   which box they start from rather than what the reader can see of it. `badgeBox` starts
   at the member's own corner — the corner a badge hangs off, which for an inline run that
   wraps is not the middle of its bounds. `visibleBounds` starts at the member's whole box,
   which is how the target chooser both admits a member and seats its chip. Both are then
   held clear of the same room by `clearBox` and tested by the same `exposes`, so both maps
   promise the reader the same thing by "visible". `clearPart` answers for a box with no
   element of its own and is the one reading that does subtract the chrome at the foot,
   because what it measures is drawn where it stands rather than moved somewhere legible. */
import { banner } from "../banner.js";
import { containsAcross, elementFromPointAcross, inChrome } from "../passages.js";
import { bottomChromeBoxes } from "./shortcut-bar.js";
import { overlaps, shownParts, shownRect, startsAt } from "../geometry.js";

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

  // What the reader can see of a box: the window, less the banner standing over its top.
  //
  // Chrome at the foot stays in it, so a map's members are never decided by it: the bar
  // states the armed map's own keys and changes width as the reader filters them, so a map
  // that read it would lose members as it armed and swap codes as its own legend grew. A
  // chip that would land there is moved by the placement pass instead (`spreadHints`,
  // hints.js), which keeps the route where dropping the member loses it.
  const clearBox = (box, sourceTop = box?.top) =>
    box
      ? rect(
          Math.max(box.left, 0),
          Math.max(box.top, covered),
          Math.min(box.right, innerWidth),
          Math.min(box.bottom, innerHeight),
          sourceTop,
        )
      : null;

  // The same, less the boxes chrome paints over the page: each blocker divides a box
  // crossing it into the space above, below, before, or after it, and the largest part
  // wins. This is for a search mark, which unlike a chip cannot be moved somewhere legible,
  // because where it is drawn is what it says. A blocker is its own rectangle here; taking
  // the lane below it as well would take the gutter with it. The chip pass does reserve
  // that lane (`lineBand`, hints.js), having somewhere else to put the chip.
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
                  ].filter(Boolean)
                : [part],
            ),
          [shown],
        )
        .sort((a, b) => b.width * b.height - a.width * a.height)[0] ?? null
    );
  }

  // Where a member begins, held clear of chrome: the corner a badge hangs off, which for
  // an inline run that wraps is not the middle of its bounds.
  const badgeBox = (item) => clearBox(startsAt(item, clips));
  // An item's whole box, held clear of chrome, for a member addressed as one block.
  const visibleBounds = (item) => clearBox(shownRect(item, clips));
  // The clip an item's own ancestors put over what it holds, for a box measured from a
  // Range rather than from an element.
  const clipOver = (item) => shownRect(item, clips);
  // A box with no element of its own, through the clip over the element that owns it.
  const clearPart = (box, clip) =>
    box && clip
      ? clearOfChrome(
          {
            left: Math.max(box.left, clip.left),
            top: Math.max(box.top, clip.top),
            right: Math.min(box.right, clip.right),
            bottom: Math.min(box.bottom, clip.bottom),
          },
          box.top,
        )
      : null;

  // Whether the reader can see what this box was measured from. Geometry cannot answer it:
  // a panel, a tray, a fixed sheet or an ordinary page box covers a member without clipping
  // its rectangle. Ask the rendered stack inside the box, and make the member itself answer,
  // a cover being exactly the case where something else does. Most chrome answers, which is
  // how a card behind the open panel leaves the map; the bar and the status line take no
  // presses, so they never do, which is why a member behind them keeps its letter and its
  // chip moves clear. A hint layer takes none either, so a chip cannot answer for the
  // member under it. A box with no member of its own — a Range's, which may run across
  // several blocks — takes any page element, no one element owning the whole box.
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
            .map((part) => ({
              left: Math.max(part.left, box.left),
              top: Math.max(part.top, box.top),
              right: Math.min(part.right, box.right),
              bottom: Math.min(part.bottom, box.bottom),
            }));
    return (aims.length ? aims : [box]).some((aim) => {
      const onTop = elementFromPointAcross(
        Math.max(0, Math.min(innerWidth - 1, (aim.left + aim.right) / 2)),
        Math.max(covered, Math.min(innerHeight - 1, (aim.top + aim.bottom) / 2)),
      );
      if (!member) return !inChrome(onTop);
      return exposure === "self"
        ? member.contains(onTop)
        : containsAcross(member, onTop);
    });
  };

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
    exposes,
    paint,
    reserve,
    visibleBounds,
  };
}
