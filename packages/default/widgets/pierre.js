/* Source files and diffs share Pierre's static renderer and Leaf's syntax theme.
 * Static DOM keeps selection and annotation with Leaf rather than introducing
 * Pierre's interaction manager alongside it. The renderer loads on first use. */
let renderer;
export const pierre = () => (renderer ??= import("/vendor/pierre-diffs.esm.js"));

// Keep Shiki styles intact; the marker lets the render gate inspect themed glyphs.
export function markSyntax(root, foreground) {
  for (const token of root.querySelectorAll("span[style]"))
    if (
      (token.style.color && token.style.color !== foreground) ||
      token.style.fontStyle ||
      token.style.fontWeight ||
      token.style.textDecoration
    )
      token.dataset.lfSyn = "";
}
