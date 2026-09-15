/* Synchronous Lit message presentation and frozen authored message islands.

   Generated metadata, prose, receipts and reaction placement have one owner. An
   immutable descriptor changes prose without reconnecting the validated authored
   fragment. The fragment is captured inertly before its first upgrade; panel
   presentation waits for preparation before capturing typed authored facets. */
import { html, render, repeat, nothing } from "../../vendor/browser-runtime.js";
import { loadMarkdown, markdownReady, renderMarkdown } from "../markdown.js";
import { reportPageError } from "../layer-client.js";
import { isReaction } from "./model.js";
import { tokenEntry } from "../registry.js";
import { rememberAuthoredParents } from "../projection/authored.js";
import { captureWidgetDescriptors } from "../widget-descriptors.js";
import {
  markDeclared,
  MARKED_ANYWHERE,
  renderQuiet,
  renderSaid,
} from "../presentation.js";
import { highlightBlocks } from "../syntax.js";
import { ago } from "../presence.js";
import { elementById, pageQueryAll } from "../passages.js";
import { designName } from "../design-readings.js";
import {
  addressableSays,
  addressableWord,
  visualPartLabel,
} from "../anchor-resolution.js";
import { rememberPassageParts } from "../widget-loader.js";
import { createReceipt } from "./acknowledgments.js";
import { ReactionStripView } from "./reaction-strips.js";

export const loadMarked = () =>
  loadMarkdown((error) =>
    reportPageError(`markdown renderer failed to load: ${error?.message ?? error}`),
  );

// Prose parsing is shared across descriptor passes and surfaces. Its value changes
// with admission, edits, stream text, or the lazy Markdown renderer becoming ready;
// clock and receipt paint reuse the same HTML without retaining generated DOM.
const renderedProse = new Map();
function messageHtml(message) {
  const key = message.attempt ?? message.id;
  const edited = message.edited?.id ?? null;
  const text = message.text ?? "";
  const markdown = markdownReady();
  let reading = renderedProse.get(key);
  if (
    !reading ||
    reading.id !== message.id ||
    reading.edited !== edited ||
    reading.text !== text ||
    reading.markdown !== markdown
  ) {
    reading = Object.freeze({
      id: message.id,
      edited,
      text,
      markdown,
      html: renderMarkdown(text),
    });
    renderedProse.set(key, reading);
  }
  return reading.html;
}

// A rollback can withdraw an authored island, but neither retry nor a prose edit
// may instantiate it twice. Its native identity is independent of the prose cache.
const authoredMessages = new Map();
function authoredMessage(message) {
  const key = message.attempt ?? message.id;
  if (!authoredMessages.has(key)) {
    const template = document.createElement("template");
    template.innerHTML = message.markup ?? "";
    const widgets = Object.freeze(
      [...template.content.querySelectorAll("[id]")].map((node) => node.id),
    );
    rememberAuthoredParents(template.content);
    captureWidgetDescriptors(template.content, { kind: "thread" });
    rememberPassageParts(template.content, ["event", message.id]);
    const nodes = Object.freeze([...template.content.childNodes]);
    authoredMessages.set(key, { nodes, widgets });
  }
  return authoredMessages.get(key);
}
export const messageWidgetIds = (message) =>
  message.markup ? authoredMessage(message).widgets : Object.freeze([]);

export function messageReading(message, { panel, receipts, reactions }) {
  const token = isReaction(message) ? tokenEntry(message.token) : null;
  const kind = isReaction(message)
    ? "reaction"
    : message.suggestion
      ? "suggestion"
      : "prose";
  return Object.freeze({
    key: message.attempt ?? message.id,
    id: message.id,
    attempt: message.attempt ?? null,
    author: message.author,
    by: message.author === "claude" ? message.agent || "Agent" : "You",
    timestamp: message.ts,
    age: ago(message.ts),
    edited: message.edited ? `Edited ${ago(message.edited.ts)}` : null,
    pending: Boolean(message.pending),
    stream: message.stream_state ?? null,
    streamLabel:
      !message.stream_state || message.stream_state === "active"
        ? null
        : message.stream_state === "failed"
          ? "Failed"
          : message.stream_state === "interrupted"
            ? "Interrupted"
            : message.stream_state === "disconnected"
              ? "Disconnected"
              : "Partial",
    body: Object.freeze({
      kind,
      text: message.text ?? "",
      html: kind === "prose" ? messageHtml(message) : "",
      drawing: Boolean(message.drawing),
      token: message.token ?? null,
      glyph: token?.glyph ?? "",
      meaning: token?.means ?? null,
      markup: message.markup ?? null,
    }),
    panel,
    receipts,
    reactions,
  });
}

export class MessageView {
  #commands;
  #model = null;
  #receipts = new Map();
  #reaction = null;
  #authored = null;
  #dressed = false;

  constructor(commands) {
    this.#commands = commands;
    this.node = document.createElement("div");
  }

  present(model) {
    const prior = this.#model;
    this.#model = model;
    const panel = model.panel;
    if (prior && prior.author !== model.author)
      this.node.classList.remove(prior.author);
    this.node.classList.add(panel ? "lf-msg" : "lf-conversation-msg", model.author);
    if (!panel) {
      this.node.classList.add("lf-ui");
      this.node.dataset.lfGen = "1";
      this.node.dataset.lfOffer = "";
    }
    if (panel) this.node.tabIndex = -1;
    this.node.setAttribute(panel ? "data-mid" : "data-event", model.id);
    if (model.attempt) this.node.dataset.attempt = model.attempt;
    else delete this.node.dataset.attempt;
    if (model.pending) this.node.setAttribute("aria-busy", "true");
    else this.node.removeAttribute("aria-busy");
    if (model.stream) this.node.dataset.streamState = model.stream;
    else delete this.node.dataset.streamState;
    if (panel && model.body.markup && !this.#authored)
      this.#authored = authoredMessage({
        id: model.id,
        attempt: model.attempt,
        markup: model.body.markup,
      }).nodes;
    const receipts = model.receipts.map((receipt) => {
      let node = this.#receipts.get(receipt.id);
      if (!node) this.#receipts.set(receipt.id, (node = createReceipt()));
      node.dataset.receiptId = receipt.id;
      node.present(receipt);
      return { key: receipt.id, node };
    });
    if (!model.reactions) this.#reaction?.retire();
    const strip = model.reactions
      ? (this.#reaction ??= new ReactionStripView(this.#commands.reaction)).present(
          model.reactions,
        )
      : nothing;
    render(
      html`
        <div class=${panel ? "lf-msg-head" : "lf-conversation-head"}>
          <b>${model.by}</b><time datetime=${model.timestamp}>${model.age}</time>
          ${
            model.body.kind === "suggestion" && panel
              ? html`<span class="lf-suggest-label">Suggestion</span>`
              : nothing
          }
          ${
            model.edited
              ? html`<span class="lf-edited" title=${model.edited}>edited</span>`
              : nothing
          }
          ${
            model.streamLabel
              ? html`<span class="lf-stream-state lf-edited"
                  >${model.streamLabel}</span
                >`
              : nothing
          }
          ${repeat(
            receipts,
            (receipt) => receipt.key,
            (receipt) => receipt.node,
          )}
        </div>
        ${
          panel
            ? html`<div
                class=${`lf-msg-body${model.body.kind === "suggestion" ? " lf-suggest-body" : ""}`}
              >
                ${this.#body(model.body)}
                ${
                  model.body.drawing
                    ? html`<span class="lf-drawing-reference">Drawing comment</span>`
                    : nothing
                }
                ${model.body.markup ? this.#authored : nothing}
              </div>`
            : this.#inlineBody(model.body)
        }
        ${
          !panel && model.body.markup
            ? html`<button
                type="button"
                class="lf-btn lf-conversation-open lf-ui"
                data-lf-gen="1"
                data-lf-offer="button"
                @click=${() => this.#commands.showThread(this.#model.id)}
              >
                Open interactive reply in Threads
              </button>`
            : nothing
        }
        ${strip}
      `,
      this.node,
    );
    if (this.#authored && !this.#dressed) {
      markDeclared(this.node, MARKED_ANYWHERE);
      renderSaid(this.node);
      renderQuiet(this.node);
      this.#dressed = true;
    }
    // Markdown is an opaque property part: tokenization never rewrites Lit markers.
    highlightBlocks(this.node);
    return this.node;
  }

  #body(body) {
    if (body.kind === "reaction")
      return html`<div class="lf-msg-text">
        <span class="lf-react-said" title=${body.meaning ?? nothing}
          >${`${body.glyph} ${body.token}`.trim()}</span
        >
      </div>`;
    if (body.kind === "suggestion")
      return html`<div class="lf-msg-text" .textContent=${body.text}></div>`;
    return html`<div class="lf-msg-text" .innerHTML=${body.html}></div>`;
  }

  #inlineBody(body) {
    if (body.kind === "suggestion")
      return html`<div class="lf-conversation-body" .textContent=${body.text}></div>`;
    if (body.kind === "reaction")
      return html`<div class="lf-conversation-body">
        <span class="lf-react-said" title=${body.meaning ?? nothing}
          >${`${body.glyph} ${body.token}`.trim()}</span
        >
      </div>`;
    return html`<div
      class="lf-conversation-body"
      .innerHTML=${
        body.html +
        (body.drawing
          ? '<span class="lf-drawing-reference">Drawing comment</span>'
          : "")
      }
    ></div>`;
  }

  commit() {
    const wanted = new Set(this.#model.receipts.map((receipt) => receipt.id));
    for (const key of this.#receipts.keys())
      if (!wanted.has(key)) this.#receipts.delete(key);
    if (!this.#model.reactions && this.#reaction) {
      this.#reaction.retire();
      this.#reaction = null;
    }
  }

  retire() {
    this.#reaction?.retire();
  }
}

function datumLabel(anchor) {
  if (!anchor?.section || !anchor.datum) return "";
  const datum = pageQueryAll("[data-lf-projection][data-lf-datum]").find(
    (element) =>
      element.dataset.lfProjection === anchor.section &&
      element.dataset.lfDatum === anchor.datum,
  );
  return datum?.dataset.lfDatumLabel?.trim() ?? "";
}

export function anchorLabel(anchor, about, omitted = null) {
  if (about === "design") {
    const addressable = anchor?.section ? elementById(anchor.section) : null;
    const name = addressable ? designName(addressable) : anchor?.section || "the page";
    const on = anchor?.part ? `${anchor.part} · ${name}` : name;
    return anchor?.quote ? `design · ${on} · “${anchor.quote}”` : `design · ${on}`;
  }
  const datum = datumLabel(anchor);
  if (datum) return anchor?.quote ? `${datum} · “${anchor.quote}”` : `§ ${datum}`;
  if (anchor?.quote) return `“${anchor.quote}”`;
  if (!anchor?.section) return "";
  const addressable = elementById(anchor.section);
  if (omitted && omitted === addressable) return "";
  if (anchor.visual) {
    const part = visualPartLabel(addressable, anchor.visual) ?? anchor.visual;
    return `§ ${addressable ? `${addressableWord(addressable)} · ${part}` : `${anchor.section} · ${part}`}`;
  }
  const says = addressableSays(addressable, omitted);
  if (omitted && says) return `“${says}”`;
  return `§ ${says ? `${addressableWord(addressable)} · ${says}` : anchor.section}`;
}
