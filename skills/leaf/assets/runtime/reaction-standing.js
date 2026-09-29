/* Paint a supplied reaction reading onto an existing reaction surface. */
import { keeps } from "./keeps.js";

export function paintReactionStanding(strip, standing) {
  const by = new Map(standing.map((reaction) => [reaction.token, reaction]));
  for (const chip of strip.querySelectorAll(".lf-react-palette > .lf-react")) {
    const current = by.get(chip.dataset.token) ?? null;
    keeps(chip, "aria-pressed", Boolean(current));
    chip.lfReaction = current;
  }
}
