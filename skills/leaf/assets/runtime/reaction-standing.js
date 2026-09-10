/* Paint a supplied reaction reading onto an existing reaction surface. */
export function paintReactionStanding(strip, standing) {
  const by = new Map(standing.map((reaction) => [reaction.token, reaction]));
  for (const chip of strip.querySelectorAll(".lf-react-palette > .lf-react")) {
    const current = by.get(chip.dataset.token) ?? null;
    chip.setAttribute("aria-pressed", current ? "true" : "false");
    chip.lfReaction = current;
  }
}
