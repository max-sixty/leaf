/* Conversation message rendering, caching, and printed anchor labels.

   Messages render from Markdown after escaping raw HTML. Literal text such as a
   generic type remains text and cannot inject markup. A widget in an event's
   gate-validated `markup` is instantiated once in the panel; inline conversation seats
   show a textual projection with a link to that reply's controls in Threads.

   An agent message edit is a later event folded onto the original message id. The
   panel and an inline conversation update the existing message node and show
   `edited`; the text wrapper alone is replaced. The message's cached markup nodes stay
   connected because their widget state and authored baseline belong to the original
   event, not to the prose revision.

   Fragment links in messages use the browser's `hidden="until-found"` behavior to
   reveal authored disclosures and tabs. `paintAnchors` marks a link detached when this
   version no longer has the id and refuses its press. A thread outlives its version,
   but a fragment target may not. */
import { loadMarkdown, renderMarkdown } from "../markdown.js";
import { reportPageError } from "../layer-client.js";
import { el } from "../widget-elements.js";
import { isReaction, tokenEntry } from "./model.js";
import { rememberAuthoredParents } from "../projection/authored.js";
import {
  markDeclared,
  MARKED_ANYWHERE,
  renderQuiet,
  renderSaid,
} from "../presentation.js";
import { highlightBlocks } from "../syntax.js";
import { ago } from "../presence.js";
import { elementById, pageQueryAll } from "../passages.js";
import { designName } from "../design.js";
import { itemSays, itemWord, visualPartLabel } from "../anchors.js";

// Lazily, like the tokenizer: a page is usually handed over before anyone has said
// anything, and one with no messages never pays the parse. poll() awaits this before
// the panel builds a body, which is what keeps msgNode synchronous.
//
// Raw HTML — block and inline both route through the one `html` renderer — escapes to
// the characters it was written in: prose says `Vec<T>`, and a message injects widgets
// only through its gate-validated `markup` field, never through text. breaks: a single
// newline is a line break, because a message is typed prose and nobody types two
// spaces to mean the line they just ended.
// Plain escaped text until the renderer arrives, so a failed vendor import
// degrades a body's Markdown to its own words instead of refusing the poll
// that carries it.
export const loadMarked = () =>
  loadMarkdown((error) =>
    reportPageError(`markdown renderer failed to load: ${error?.message ?? error}`),
  );

// Bodies are cached per message id and re-adopted when a thread node is rebuilt — which
// the reconcile leaves one occasion for, a thread resolving. An edit is a later log
// event folded onto that id, so it replaces only the text wrapper. The frozen markup
// beside it keeps its nodes: a widget in a reply may already hold reader state, and
// re-upgrading it over a prose correction would turn the edit into a second transition.
const msgBodies = new Map();
function paintMsgText(text, m) {
  const words = m.text ?? "";
  if (m.suggestion) text.textContent = words;
  else text.innerHTML = renderMarkdown(words);
}

function buildMsgBody(m) {
  const body = el("div", "lf-msg-body");
  const text = el("div", "lf-msg-text");
  body.append(text);
  if (isReaction(m)) {
    // A thread whose root is a mark: the glyph and its word, in the chrome's own
    // face, where a comment's words would be. What it meant is the entry's `means`,
    // said on hover the way the bar says it.
    const said = el(
      "span",
      "lf-react-said",
      `${tokenEntry(m.token)?.glyph ?? ""} ${m.token}`.trim(),
    );
    said.title = tokenEntry(m.token)?.means ?? "";
    text.append(said);
  } else if (m.suggestion) {
    // Verbatim: a suggestion's characters are bound for the page as typed, and a
    // rendering would show an italic where the next version carries the asterisks.
    body.classList.add("lf-suggest-body");
    paintMsgText(text, m);
  } else {
    paintMsgText(text, m);
    if (m.drawing) body.append(el("span", "lf-drawing-reference", "Drawing comment"));
    // The widget markup beside the text, injected as the CLI gate validated it. A
    // template is deliberately inert: an already-defined custom element's constructor
    // runs even in a detached ordinary div. Capture parentage in the literal markup,
    // then connect these same nodes; thread-list captures typed initial values only
    // after their synchronous and asynchronous upgrades finish.
    // The passes below don't come along with that upgrade — the said and quiet passes
    // write a widget's declared words, spoken and silent, and a fenced block is a
    // <pre><code class="language-…"> like any the page holds.
    //
    // The declared marks come along by the half that holds here (MARKED_ANYWHERE):
    // whether a widget is set among the words is true of it in a reply as much as on
    // the page, and a chip-led comparison quoted into one stacks without it. The width
    // model is the half that stays behind, and the reason is what it hands out: the room
    // the *document* has, which is not the room in here. A diagram in a reply is a widget
    // the vocabulary calls wide, and marked as one it would lay itself out to the page's
    // measure inside the panel. The room a message has is the message's, and it already
    // has it.
    if (m.markup) {
      const authored = document.createElement("template");
      authored.innerHTML = m.markup;
      rememberAuthoredParents(authored.content);
      body.append(authored.content);
    }
    markDeclared(body, MARKED_ANYWHERE);
    renderSaid(body);
    renderQuiet(body);
    // Not settle()d: that queue holds the page's geometry still for the first anchor
    // pass, and a message colors in the panel, where no anchor is captured and nothing
    // waits. Each block already fails soft to its own plain source.
    highlightBlocks(body);
  }
  return { body, revision: m.edited?.id ?? "", text };
}

function msgBody(m) {
  let rendered = msgBodies.get(m.id);
  if (!rendered) {
    rendered = buildMsgBody(m);
    msgBodies.set(m.id, rendered); // the id is server-minted, on every message event
  }
  const revision = m.edited?.id ?? "";
  if (rendered.revision !== revision) {
    paintMsgText(rendered.text, m);
    if (!m.suggestion) highlightBlocks(rendered.text);
    rendered.revision = revision;
  }
  return rendered.body;
}

export function syncEdited(head, m) {
  let edited = head.querySelector(":scope > .lf-edited");
  if (!m.edited) {
    edited?.remove();
    return;
  }
  if (!edited) {
    edited = el("span", "lf-edited", "edited");
    head.insertBefore(edited, head.querySelector(":scope > .lf-resolve"));
  }
  edited.title = `Edited ${ago(m.edited.ts)}`;
}

export function syncMsgNode(div, m) {
  const head = div.querySelector(":scope > .lf-msg-head");
  const when = head.querySelector(":scope > time");
  const said = ago(m.ts);
  if (when.textContent !== said) when.textContent = said;
  syncEdited(head, m);
  const body = msgBody(m);
  const standing = div.querySelector(":scope > .lf-msg-body");
  if (standing !== body) standing?.replaceWith(body);
}

export function msgNode(m) {
  const div = el("div", `lf-msg ${m.author}`);
  div.tabIndex = -1;
  div.dataset.mid = m.id; // the reconcile's key and direct-navigation address
  const head = el("div", "lf-msg-head");
  // "3 hours ago" is not a datetime, so the machine-readable one goes in the attribute
  // the element has for it — which is also what `saidAt` reads back when a widget the
  // message carries needs to know when it was said.
  const when = el("time", "", ago(m.ts));
  when.dateTime = m.ts;
  head.append(el("b", "", m.author === "claude" ? m.agent || "Agent" : "You"), when);
  div.append(head);
  if (m.suggestion) div.append(el("div", "lf-suggest-label", "suggested replacement"));
  div.append(msgBody(m));
  syncEdited(head, m);
  return div;
}

// How an anchor reads where it has to be printed rather than pointed at — every thread in
// the panel, and the open composer when the page has no passage left to mark. A quote-less
// anchor points at an element (a diagram or image targeted explicitly rather than by
// selection) and names its section instead of quoting it. One function, so the two places
// can't come to say it differently.
//
// An id is the page's name for an item and not the user's. `card-migration` says
// nothing they wrote, and pointing at an item is an ordinary gesture rather than the
// diagram's special case, so anchors reading this way are ordinary in the panel too.
// An element anchor is labelled with the item's own opening words, and falls
// back to the id where this version has no such element. The kind goes before the words
// because the two together are a name, where the words alone read as a quote the thread
// does not hold.
//
// A design comment (`about: "layer"`) reads "layer ·" first, because what follows names
// the thing whose look or behaviour is in question rather than the words on it: the
// control the press landed on where it landed on one (`part`), then the item — a
// widget by its tag and id, a runtime part by its name — since a design comment's
// subject is the element itself and its opening words would read as a quote.
function datumLabel(anchor) {
  if (!anchor?.section || !anchor.datum) return "";
  const datum = pageQueryAll("[data-lf-projection][data-lf-datum]").find(
    (element) =>
      element.dataset.lfProjection === anchor.section &&
      element.dataset.lfDatum === anchor.datum,
  );
  return datum?.dataset.lfDatumLabel?.trim() ?? "";
}

export function anchorLabel(anchor, about) {
  if (about === "layer") {
    const item = anchor?.section ? elementById(anchor.section) : null;
    const name = item ? designName(item) : anchor?.section || "the page";
    const on = anchor?.part ? `${anchor.part} · ${name}` : name;
    return anchor?.quote ? `layer · ${on} · “${anchor.quote}”` : `layer · ${on}`;
  }
  const datum = datumLabel(anchor);
  if (datum) return anchor?.quote ? `${datum} · “${anchor.quote}”` : `§ ${datum}`;
  if (anchor?.quote) return `“${anchor.quote}”`;
  if (!anchor?.section) return "";
  const item = elementById(anchor.section);
  if (anchor.visual) {
    const part = visualPartLabel(item, anchor.visual) ?? anchor.visual;
    return `§ ${item ? `${itemWord(item)} · ${part}` : `${anchor.section} · ${part}`}`;
  }
  const says = itemSays(item);
  return `§ ${says ? `${itemWord(item)} · ${says}` : anchor.section}`;
}

export const renderMessageMarkdown = (text) => renderMarkdown(text);
