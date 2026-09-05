/* The one-digit address vocabulary and the placement pass shared by every surface that
   paints it. A visible address may move back inside the viewport, but it yields wherever
   that move would cover the key line or another address. The route still works when its
   face cannot be drawn, so omission is safer than an ambiguous stack of digits.

   Numbered addresses are capped at nine per list. Tabs, links, and folds keep the first
   nine document members, so those identities do not change as the reader scrolls and an
   off-screen member within that prefix remains reachable. Page-map locations instead
   number the visible window from one; their complete searchable identity lives in the
   Page map sheet. That window stays fixed during a scroll and is read again at
   `scrollend`. Chips live in runtime chrome rather than authored markup. They sit above
   their targets and move inside the viewport below the banner before overlapping chips
   are removed. */
export const MAX_NUMBERED_ADDRESSES = 9;

const overlaps = (a, b) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

export function createAddressPlacement({ banner, keylineEl, startsAt }) {
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

  // Attach every chip in one write, measure them before moving or removing any, then
  // adjust their authored CSS anchor by the clamp delta. That preserves the face's own
  // transform: chord routes sit above prose, while Ask digits sit on a Button's corner.
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
