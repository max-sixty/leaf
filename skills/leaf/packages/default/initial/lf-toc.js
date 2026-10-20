/* The contents' initial drawing: the frame as the parser finishes the widget, and the
 * outline once the document it outlines has parsed, since its headings usually follow
 * it. The frame alone has the box the widget keeps in either form, a closed disclosure
 * in flow or the map's full height in the margin. Whether any heading qualifies is
 * known only once parsing ends, so the frame shows until then, and a contents with
 * none is hidden there, as its module hides it. Hiding it until a heading arrives would
 * instead move what follows it on any page with headings that paints while parsing. */
import { drawOutline, drawToc } from "../widgets/toc-view.js";

// Before modules run, a heading holds only the words its author wrote, and the only
// chrome is the light document's.
const reading = {
  label: (heading) => heading.textContent.replace(/\s+/g, " ").trim(),
  chrome: (heading) => heading.closest(".lf-chrome") !== null,
  // The rows are drawn once, into an empty list.
  place: (list, rows) => list.append(...rows),
  lends: false,
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
