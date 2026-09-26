/* Synchronous Lit message presentation and frozen authored message islands.

   Generated metadata, prose, workflow and reaction placement have one owner. An
   immutable descriptor changes prose without reconnecting the validated authored
   fragment. The fragment is captured inertly before its first upgrade; panel
   presentation waits for preparation before capturing typed authored state. */
import { html, render, nothing } from "../../vendor/browser-runtime.js";
import {
  loadMarkdown,
  markdownReady,
  renderMarkdown,
  renderedWords,
} from "../markdown.js";
import { reportPageError } from "../layer-client.js";
import { isReaction, moved } from "./model.js";
import { tokenEntry } from "../registry.js";
import {
  rememberAuthoredParents,
  stageAuthoredStates,
} from "../projection/authored.js";
import { stageWidgetDescriptors } from "../widget-descriptors.js";
import { strongestWorkflow, workflowLabel, workflowTitle } from "./workflow.js";
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
import { ReactionStripView } from "./reaction-strips.js";

export const loadMarked = () =>
  loadMarkdown((error) =>
    reportPageError(`markdown renderer failed to load: ${error?.message ?? error}`),
  );

// Prose parsing is shared across descriptor passes and surfaces. Its value changes
// with admission, edits, stream text, or the lazy Markdown renderer becoming ready;
// clock and receipt paint reuse the same HTML without retaining generated DOM.
const renderedProse = new Map();
function proseReading(message) {
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
    const html = renderMarkdown(text);
    reading = Object.freeze({
      id: message.id,
      edited,
      text,
      markdown,
      html,
      plainText: renderedWords(html),
    });
    renderedProse.set(key, reading);
  }
  return reading;
}

export function messageText(message) {
  if (message.token) {
    const token = tokenEntry(message.token);
    return `${token?.glyph ?? ""} ${message.token}`.trim();
  }
  return message.suggestion ? (message.text ?? "") : proseReading(message).plainText;
}

// A rollback can withdraw an authored island, but neither retry nor a prose edit
// may instantiate it twice. Its native identity is independent of the prose cache.
const authoredMessages = new Map();
export function prepareAuthoredMessage(message, thread) {
  const key = message.attempt ?? message.id;
  if (typeof thread !== "string" || !thread)
    throw new TypeError("an authored message needs its canonical thread root");
  if (!authoredMessages.has(key)) {
    const template = document.createElement("template");
    template.innerHTML = message.markup ?? "";
    rememberAuthoredParents(template.content);
    const descriptors = stageWidgetDescriptors(template.content, {
      kind: "thread",
      thread,
      message: message.id,
    });
    const authored = stageAuthoredStates(template.content, new Map());
    rememberPassageParts(template.content, ["event", message.id]);
    const nodes = Object.freeze([...template.content.childNodes]);
    authoredMessages.set(key, {
      message: message.id,
      body: {
        text: template.content.textContent,
        document: { thread, message: message.id },
      },
      authored,
      descriptors,
      nodes,
      root: template.content,
    });
  }
  const prepared = authoredMessages.get(key);
  for (const descriptor of prepared.descriptors.descriptors.values())
    if (
      descriptor.document.thread !== thread ||
      descriptor.document.message !== message.id
    )
      throw new TypeError("an authored message changed its frozen document identity");
  return prepared;
}
const authoredMessage = (message) => {
  const prepared = authoredMessages.get(message.attempt ?? message.id);
  if (!prepared)
    throw new Error("authored message presentation preceded semantic preparation");
  return prepared;
};
const FAILURE_LABEL = "Not answered";
export function messageReading(message, { panel, reactions, workflows }) {
  const workflow = strongestWorkflow(workflows);
  const token = isReaction(message) ? tokenEntry(message.token) : null;
  const kind = isReaction(message)
    ? "reaction"
    : message.suggestion
      ? "suggestion"
      : "prose";
  const prose = kind === "prose" ? proseReading(message) : null;
  return Object.freeze({
    key: message.attempt ?? message.id,
    id: message.id,
    seq: moved(message).seq,
    unread: message.unread,
    attempt: message.attempt ?? null,
    author: message.author,
    by: message.author === "agent" ? message.agent || "Agent" : "You",
    timestamp: message.ts,
    age: ago(message.ts),
    edited: message.edited ? `Edited ${ago(message.edited.ts)}` : null,
    failure: message.failure ?? null,
    pending: workflow?.stage === "sending",
    workflow,
    workflowLabel: workflowLabel(workflow),
    workflowTitle: workflowTitle(workflow),
    body: Object.freeze({
      kind,
      text: message.text ?? "",
      html: prose?.html ?? "",
      plainText: prose?.plainText ?? message.text ?? "",
      drawing: Boolean(message.drawing),
      token: message.token ?? null,
      glyph: token?.glyph ?? "",
      meaning: token?.means ?? null,
      authored: message.body.kind === "authored",
    }),
    panel,
    reactions,
  });
}

export class MessageView {
  #commands;
  #model = null;
  #reaction = null;
  #authored = null;
  #dressed = false;
  #header = document.createElement("div");

  constructor(commands) {
    this.#commands = commands;
    this.node = document.createElement("div");
  }

  present(model, externalHeader = false) {
    const prior = this.#model;
    this.#model = model;
    const panel = model.panel;
    if (prior && prior.author !== model.author)
      this.node.classList.remove(prior.author);
    this.node.classList.add(panel ? "lf-msg" : "lf-page-thread-msg", model.author);
    if (!panel) {
      this.node.classList.add("lf-ui");
      this.node.dataset.lfGen = "1";
      this.node.dataset.lfOffer = "";
    }
    if (panel) this.node.tabIndex = -1;
    this.node.setAttribute(panel ? "data-mid" : "data-event", model.id);
    this.node.classList.toggle("lf-unread", Boolean(model.unread));
    if (model.attempt) this.node.dataset.attempt = model.attempt;
    else delete this.node.dataset.attempt;
    if (model.pending) this.node.setAttribute("aria-busy", "true");
    else this.node.removeAttribute("aria-busy");
    if (model.failure) this.node.dataset.failure = model.failure;
    else delete this.node.dataset.failure;
    if (panel && model.body.authored && !this.#authored)
      this.#authored = authoredMessage({
        id: model.id,
        attempt: model.attempt,
      }).nodes;
    if (!model.reactions) this.#reaction?.retire();
    const strip = model.reactions
      ? (this.#reaction ??= new ReactionStripView(this.#commands.reaction)).present(
          model.reactions,
        )
      : nothing;
    this.#header.className = panel ? "lf-msg-head" : "lf-page-thread-head";
    render(
      html`
        <b>${model.by}</b
        ><span class="lf-msg-meta"
          ><time datetime=${model.timestamp}>${model.age}</time> ${
            model.workflowLabel
              ? html`<span class="lf-msg-sending" title=${model.workflowTitle}
                  >${model.workflowLabel}</span
                >`
              : nothing
          }
          ${
            model.failure
              ? html`<span class="lf-msg-failure">${FAILURE_LABEL}</span>`
              : nothing
          }
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
          ${model.unread ? html`<span class="lf-unread-label">Unread</span>` : nothing}
        </span>
      `,
      this.#header,
    );
    render(
      html`
        ${externalHeader ? nothing : this.#header}
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
                ${model.body.authored ? this.#authored : nothing}
              </div>`
            : this.#inlineBody(model.body)
        }
        ${
          !panel && model.body.authored
            ? html`<button
                type="button"
                class="lf-btn lf-page-thread-open lf-ui"
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
    this.#commands.read.observeBody(
      this.node,
      this.node.querySelector(
        panel ? ":scope > .lf-msg-body" : ":scope > .lf-page-thread-body",
      ),
      model,
    );
    return this.node;
  }

  get header() {
    return this.#header;
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
      return html`<div class="lf-page-thread-body" .textContent=${body.text}></div>`;
    if (body.kind === "reaction")
      return html`<div class="lf-page-thread-body">
        <span class="lf-react-said" title=${body.meaning ?? nothing}
          >${`${body.glyph} ${body.token}`.trim()}</span
        >
      </div>`;
    return html`<div
      class="lf-page-thread-body"
      .innerHTML=${
        body.html +
        (body.drawing
          ? '<span class="lf-drawing-reference">Drawing comment</span>'
          : "")
      }
    ></div>`;
  }

  commit() {
    if (!this.#model.reactions && this.#reaction) {
      this.#reaction.retire();
      this.#reaction = null;
    }
  }

  retire() {
    this.#reaction?.retire();
    this.#commands.read.forgetBody(this.node);
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
