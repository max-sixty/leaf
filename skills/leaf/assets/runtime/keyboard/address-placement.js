/* Shared visibility for addressable targets and placement for predictable numeric Ask
   addresses. The banner clips every target's usable box. An Ask face may move back inside
   the viewport, but it yields wherever that move would cover the key line or another
   address: its ordered choices make a missing digit inferable. Opaque generated target
   hints instead use the no-drop placement in hints.js. */
import { banner } from "../banner.js";
import { keylineEl } from "./keyline.js";
import { startsAt } from "../geometry.js";
const overlaps = (a, b) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

export function addressPlacement() {
  const clips = new Map();
  const covered = banner.getBoundingClientRect().bottom;
  const kept = [keylineEl.getBoundingClientRect()];

  // Read every member through one clip cache. The banner covers page content without
  // clipping its boxes; a member wholly behind it has no visible address anchor.
  function visibleBox(item) {
    const box = startsAt(item, clips);
    return box && box.bottom > covered ? box : null;
  }

  // A page-local address cannot be moved by the chrome pass, but it reserves its own
  // visible box so later chrome addresses cannot claim the same pixels.
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

  return { paint, reserve, visibleBox };
}
