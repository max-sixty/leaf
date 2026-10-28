/* The contents' initial drawing: the frame as the parser finishes the widget, and the
 * outline once the document it outlines has parsed, since its headings usually follow
 * it. A closed disclosure already has its final height. An authored open outline
 * depends on later headings, so its reading scope first paints once those inputs have
 * parsed, without waiting for behavior modules or the server's state. */
import { render } from "/vendor/lit.js";
import { drawToc, outlineDocument } from "../widgets/toc-view.js";

// Before modules run, a heading holds only the words its author wrote, and the only
// chrome is the light document's.
const reading = {
  label: (heading) => heading.textContent.replace(/\s+/g, " ").trim(),
  chrome: (heading) => heading.closest(".lf-chrome") !== null,
  lends: false,
};

document.documentElement.lfInitial.register("lf-toc", (host, tools) => {
  const drawing = drawToc(host, tools, reading);
  const outline = () => render(drawing.render(), host, { host });
  const doc = host.ownerDocument;
  if (doc.readyState === "loading") {
    const pending = host.hasAttribute("open") && outlineDocument(host);
    if (pending) tools.keeps(pending, "data-lf-initial-pending", "");
    doc.addEventListener(
      "readystatechange",
      () => {
        outline();
        if (pending) tools.keeps(pending, "data-lf-initial-pending", null);
      },
      { once: true },
    );
  }
  return drawing;
});
