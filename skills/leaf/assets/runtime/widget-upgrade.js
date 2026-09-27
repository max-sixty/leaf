/* The upgrade lifecycle every behavior module shares.

   A module defines its custom element once and makes `connectedCallback` safe to run
   after reconnection, using `once(el)` for generated chrome so reconnecting does not
   duplicate it. A failed upgrade becomes a visible error box (`failSoft`) rather than
   a blank page; widgetController owns asynchronous presentation. */
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";

// One-shot guard for connectedCallback: re-connection (a parent wrapping or moving an
// already-upgraded child) must be harmless, so upgrade order can't matter.
export function once(el) {
  if (el.hasAttribute(PAGE_PAINT_ATTRIBUTE.done)) return false;
  el.setAttribute(PAGE_PAINT_ATTRIBUTE.done, "1");
  return true;
}

// A data widget's body: the <pre> the content model requires, never the element's own
// textContent. The two used to be the same string and are not once the element holds a
// child — an HTML formatter is free to put the <pre> on its own line, and the newline
// and indent before it are the element's text too. Line one is load-bearing in every
// notation here, so that indent is not untidiness downstream: a diff's file header, a
// tree's root and a diagram's source type stop parsing, and a walkthrough's `hi` ranges
// and note anchors all point one line off.
export const dataBody = (el) => el.querySelector(":scope > pre").textContent;

// The body's text as a module reads its lines: leading blank lines and trailing
// whitespace are the <pre>'s layout, not lines. `version check` holds an x-numbering to
// the lines of this same trim (`_body_text`, validation/instances.py). trimEnd removes
// the class collapse.js's COLLAPSE spells, which Python names outright because its own
// \s differs at the edges. A notation whose trailing whitespace is content, a diff's,
// reads `dataBody` instead.
export const bodyText = (el) => dataBody(el).replace(/^\n+/, "").trimEnd();

// A failed upgrade becomes a visible error box rather than a blank page. A widget failure
// may failSoft its own element so the rest of the page and Threads remain usable, but it
// does not convert a partial state read into a committed one (reportPageError,
// layer-client.js, is the page-level evidence every failure reports through).
export function failSoft(el, err, source) {
  const box = document.createElement("div");
  box.className = "lf-error";
  box.textContent = `<${el.tagName.toLowerCase()}> failed: ${err?.message || err}`;
  if (source) {
    const pre = document.createElement("pre");
    pre.textContent = source;
    box.append(pre);
  }
  el.replaceChildren(box);
}
