/* The contents' initial drawing: the frame as the parser finishes the widget, and the
 * outline once the document it outlines has parsed, since its headings usually follow
 * it. Until then the frame stands at the box it keeps in either form, a closed
 * disclosure in flow or the map's full height in the margin, so it stands even where
 * no heading will qualify; once parsing ends, a contents with none is hidden, as its
 * module hides it. */
import { drawOutline, drawToc } from "../widgets/toc-view.js";

// Before modules run, a heading holds only the words its author wrote, and the only
// chrome is the light document's.
const reading = {
  label: (heading) => heading.textContent.replace(/\s+/g, " ").trim(),
  chrome: (heading) => heading.closest(".lf-chrome") !== null,
  // The rows are drawn once, into an empty list.
  place: (list, rows) => list.append(...rows),
};

document.documentElement.lfInitial.register("lf-toc", (host, { keeps }) => {
  const drawing = drawToc(host);
  const outline = () =>
    keeps(
      host,
      "data-lf-toc-empty",
      drawOutline(host, drawing, { ...reading, keeps }).length ? null : "",
    );
  const doc = host.ownerDocument;
  if (doc.readyState === "loading")
    doc.addEventListener("readystatechange", outline, { once: true });
  else outline();
  return drawing;
});
