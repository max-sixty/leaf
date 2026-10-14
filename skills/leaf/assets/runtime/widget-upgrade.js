/* The upgrade lifecycle every behavior module shares.

   A module defines its custom element once and makes `connectedCallback` safe to run
   after reconnection, using `once(el)` for generated chrome so reconnecting does not
   duplicate it. A failed upgrade becomes a visible error box (`failSoft`) rather than
   a blank page, and reaches the agent as the page's error; widgetController owns
   asynchronous presentation. */
import { reportPageError } from "./layer-client.js";
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";
import { render } from "/vendor/browser-runtime.js";
import { shadowStage } from "./shadow-stage.js";

const initialized = new WeakSet();

// One-shot guard for connectedCallback: re-connection (a parent wrapping or moving an
// already-upgraded child) must be harmless. A clone starts its own lifetime even when
// it copied the painted upgrade mark; that mark never owns initialization.
export function once(el) {
  if (initialized.has(el)) return false;
  initialized.add(el);
  if (!el.hasAttribute(PAGE_PAINT_ATTRIBUTE.done))
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
// whitespace are the <pre>'s layout, not lines. Notations whose whitespace is content,
// such as a diff or exact Markdown source, read `dataBody` instead.
export const bodyText = (el) => dataBody(el).replace(/^\n+/, "").trimEnd();

// A failed upgrade becomes a visible error box rather than a blank page. A widget failure
// may failSoft its own element, or a part of it, so the rest of the page and Threads
// remain usable, but it does not convert a partial state read into a committed one. The
// box is where the user is looking; the agent that wrote the widget hears the same
// failure as the page's error, through reportPageError, which is also what `page check`
// fails on wherever it runs the page. Both name the widget the failing element belongs to, and the report adds its
// id, since that is how the agent finds it.
export function failSoft(el, err, source) {
  reportFailure(el, err);
  showFailure(el, `<${widgetOf(el).localName}> failed: ${err?.message || err}`, source);
}

// The report alone, for a widget that shows a part's failure its own way, such as a
// diff file whose patch it cannot draw beside the files it can.
export function reportFailure(el, err) {
  const owner = widgetOf(el);
  reportPageError(
    err,
    `<${owner.localName}${owner.id ? ` id="${owner.id}"` : ""}> failed`,
  );
}

// The box alone, for the presentation coordinator's fallback: the coordinator reports
// any failure it falls back from that no paint reported, so this path reports nothing.
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
  // An x-shadow widget shows only what its stage holds, so the box stands there, and
  // the widget's next stage replaces it.
  if (el.shadowRoot) {
    shadowStage(el, [box]);
    return;
  }
  // Rendered as a template value, so the widget's next template render replaces it.
  // A native renderer may have replaced the children since a template last owned them,
  // leaving Lit's cached part pointing at markers no longer here.
  releaseTemplate(el);
  el.replaceChildren();
  render(box, el);
}

// End a template's ownership of `el`: Lit's public RootPart.setConnected(false)
// disconnects its directives, but render() has no public reset, so its pinned,
// deliberately unminified cache key goes too, letting the next render start afresh.
function releaseTemplate(el) {
  const part = el._$litPart$;
  if (!part) return;
  part.setConnected(false);
  delete el._$litPart$;
}
