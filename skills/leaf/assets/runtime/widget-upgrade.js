/* The upgrade lifecycle every behavior module shares.

   A module defines its custom element once and makes `connectedCallback` safe to run
   after reconnection, using `once(el)` for generated chrome so reconnecting does not
   duplicate it. A failed upgrade becomes a visible error box (`failSoft`) rather than
   a blank page, and reaches the agent as the page's error; widgetController owns
   asynchronous presentation. */
import { reportPageError } from "./layer-client.js";
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";

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
// whitespace are the <pre>'s layout, not lines. `page check` holds an x-numbering to
// the lines of this same trim (`_body_text`, validation/instances.py). trimEnd removes
// the class collapse.js's COLLAPSE spells, which Python names outright because its own
// \s differs at the edges. A notation whose trailing whitespace is content, a diff's,
// reads `dataBody` instead.
export const bodyText = (el) => dataBody(el).replace(/^\n+/, "").trimEnd();

// A failed upgrade becomes a visible error box rather than a blank page. A widget failure
// may failSoft its own element, or a part of it, so the rest of the page and Threads
// remain usable, but it does not convert a partial state read into a committed one. The
// box is where the user is looking; the agent that wrote the widget hears the same
// failure as the page's error, through reportPageError, which is also what `page check`
// fails on wherever it runs the page. Both name the widget the failing element belongs to, and the report adds its
// id, since that is how the agent finds it.
export function failSoft(el, err, source) {
  const owner = widgetOf(el);
  const tag = owner.localName;
  const message = err?.message || err;
  reportPageError(`<${tag}${owner.id ? ` id="${owner.id}"` : ""}> failed: ${message}`);
  showFailure(el, `<${tag}> failed: ${message}`, source);
}

// The box alone, for the presentation coordinator's fallback: the coordinator reports
// every failure it falls back from itself, so this path must not report it again.
export function failSoftUnreported(el, err) {
  showFailure(el, `<${widgetOf(el).localName}> failed: ${err?.message || err}`);
}

const widgetOf = (el) => {
  let owner = el;
  while (owner.parentElement && !owner.localName.includes("-"))
    owner = owner.parentElement;
  return owner.localName.includes("-") ? owner : el;
};

function showFailure(el, text, source) {
  const box = document.createElement("div");
  box.className = "lf-error";
  box.textContent = text;
  if (source) {
    const pre = document.createElement("pre");
    pre.textContent = source;
    box.append(pre);
  }
  el.replaceChildren(box);
}
