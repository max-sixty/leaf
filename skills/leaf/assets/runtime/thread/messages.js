/* Synchronous Lit message presentation and frozen authored message islands.

   Every surface uses the same message, header and body vocabulary. Generated
   metadata, prose, workflow and reaction placement have one owner. Each message
   projects pasted attachments separately from its words using the draft's media
   reading, so a retained text viewport never clips an attachment. Each message
   retains its header and body together, sharing delivery, unread and fold state.
   Its header declares its stationary text-reflow boundary and hosts the thread's
   disclosure for progress completed by that reply. An
   immutable descriptor changes prose without reconnecting the validated authored
   fragment. A new message cues its own words once on first presentation, in every
   surface: one the user just sent, and any turn, whoever wrote it, joining a thread
   view that was already presented. Opening a view cues nothing it already holds, and
   admission and later descriptor paints never replay the cue.
   The fragment is captured inertly before its first upgrade; panel
   presentation waits for preparation before capturing typed authored state. */
import { html, render, nothing } from "../../vendor/browser-runtime.js";
import {
  loadMarkdown,
  markdownReady,
  renderMarkdown,
  renderedWords,
} from "../markdown.js";
import { reportPageError } from "../layer-client.js";
import { editable, isReaction, messageKey, moved } from "./model.js";
import {
  MessageEditor,
  OPEN_MESSAGE_EDIT,
  holdsMessageEdit,
  keptRewrite,
  releaseMessageEdit,
  watchRewrite,
} from "./message-edit.js";
import { tokenEntry } from "../registry.js";
import { readAttachedMedia, writeAttachedMedia } from "../media.js";
import {
  rememberAuthoredParents,
  stageAuthoredStates,
} from "../projection/authored.js";
import { stageWidgetDescriptors } from "../widget-descriptors.js";
import { strongestWorkflow, workflowLabel, workflowTitle } from "./workflow.js";
import {
  markDeclared,
  renderQuiet,
  renderSaid,
  writePrepaint,
} from "../declared-words.js";
import { highlightBlocks } from "../syntax.js";
import { ago } from "../presence.js";
import { elementById } from "../passages.js";
import { designName } from "../design-readings.js";
import { addressableWord, sectionLabel } from "../addressable-names.js";
import { datumLabel, visualPartLabel } from "../anchor-resolution.js";
import { rememberPassageParts } from "../widget-loader.js";
import { ReactionStripView } from "./reaction-strips.js";
import { iconTemplate } from "../icons.js";
import { keeps } from "../keeps.js";
import { flashDuration, motion } from "../motion.js";

export const loadMessageMarkdown = () =>
  loadMarkdown((error) => reportPageError(error, `markdown renderer failed to load`));

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
    const pasted = readAttachedMedia(text);
    const html = renderMarkdown(pasted.text);
    const mediaHtml = renderMarkdown(writeAttachedMedia("", pasted.paths));
    reading = Object.freeze({
      id: message.id,
      edited,
      text,
      markdown,
      html,
      mediaHtml,
      plainText: renderedWords(html + mediaHtml),
    });
    renderedProse.set(key, reading);
  }
  return reading;
}

/** @param {import("../../../../../build/browser/domain.ts").Message | Extract<import("../../../../../build/browser/domain.ts").Command, {kind: "comment" | "reply"}>} message @returns {string} */
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
    throw new TypeError("an authored message needs its thread's id");
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
    const text = template.content.textContent;
    writePrepaint(template.content);
    const nodes = Object.freeze([...template.content.childNodes]);
    authoredMessages.set(key, {
      message: message.id,
      body: {
        text,
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
export function messageReading(
  message,
  { panel, nativeAuthored = false, reactions, workflows, leaves = null },
) {
  const workflow = strongestWorkflow(workflows);
  const token = isReaction(message) ? tokenEntry(message.token) : null;
  const kind = isReaction(message)
    ? "reaction"
    : message.suggestion
      ? "suggestion"
      : "prose";
  const prose = kind === "prose" ? proseReading(message) : null;
  return Object.freeze({
    key: messageKey(message),
    id: message.id,
    // A reply still streaming, which the answer it stands for completes in place.
    provisional: Boolean(message.provisional),
    // The agent's progress message (`ephemeral`): a step of work in hand, which the
    // thread shows as its working message until an answer folds it (thread-card.js).
    progress: Boolean(message.ephemeral),
    // What an answer leaves standing, while it stands: "Waiting on me" for the prose ask the
    // user owes, "To-do open" for work it promised and has not ended (thread-card.js).
    leaves,
    version: message.content_version,
    seq: moved(message).seq,
    unread: message.unread,
    attempt: message.attempt ?? null,
    author: message.author,
    by: message.author === "agent" ? message.agent : "Me",
    timestamp: message.ts,
    age: ago(message.ts),
    // What the message said before its last rewrite is the edited mark's to tell, since
    // answers above may have been about those words.
    edited: message.edited
      ? `Edited ${ago(message.edited.ts)}. Before, it said: “${message.edited.was}”`
      : null,
    editable: editable(message),
    failure: message.failure ?? null,
    pending: workflow?.stage === "sending",
    // What a rewrite of the message is written over (`base` on an edit): its current
    // content version.
    base: message.content_version,
    workflow,
    workflowLabel: workflowLabel(workflow),
    workflowTitle: workflowTitle(workflow),
    body: Object.freeze({
      kind,
      text: message.text ?? "",
      html: prose?.html ?? "",
      mediaHtml: prose?.mediaHtml ?? "",
      plainText: prose?.plainText ?? message.text ?? "",
      drawing: Boolean(message.drawing),
      token: message.token ?? null,
      glyph: token?.glyph ?? "",
      authored: message.body.kind === "authored",
    }),
    panel,
    nativeAuthored,
    reactions,
  });
}

export class MessageView {
  #commands;
  #model = null;
  #reaction = null;
  #authored = null;
  #dressed = false;
  #arrivalMotion = null;
  #stopRead = null;
  #header = document.createElement("div");
  #editor = null;
  #kept = false;
  #stopKept = null;

  constructor(commands) {
    this.#commands = commands;
    this.node = document.createElement("div");
  }

  present(model, { arrived = false, headerControls = nothing } = {}) {
    const prior = this.#model;
    this.#model = model;
    const panel = model.panel;
    // A view presents messages of one surface for its whole life, so what the surface
    // makes of the node is written once, on the first presentation.
    if (!prior) {
      this.node.classList.add("lf-msg");
      // Which message a node draws, for a presentation handing the user's place in a
      // thread to another, as the floating panel does to a page's own reader.
      this.node.dataset.message = model.key;
      this.#header.className = "lf-msg-head";
      if (panel) this.node.tabIndex = -1;
      else {
        this.node.classList.add("lf-ui");
        this.node.dataset.lfGen = "1";
        this.node.dataset.lfOffer = "";
      }
      // A double click on the user's own words opens them for rewriting, as the word
      // under it would otherwise only be selected. The word it selected goes first: the
      // editor then sets its own caret, which clearing the selection after would take. A
      // link keeps its own double click.
      this.node.addEventListener("dblclick", (event) => {
        if (event.target.closest?.(".lf-msg-editor, a[href]")) return;
        if (!this.#model?.editable) return;
        window.getSelection()?.removeAllRanges();
        this.openEdit();
      });
      this.node.addEventListener(OPEN_MESSAGE_EDIT, () => this.openEdit());
    }
    // The view the user opened the rewrite in draws its editor (`message-edit.js`); a
    // closed editor goes with its subscription and keys.
    const editing = model.editable && holdsMessageEdit(model.id, this, panel);
    if (editing && !this.#editor)
      this.#editor = new MessageEditor(model.id, this, {
        wireInput: this.#commands.reply.wireInput,
        said: () => this.#model.body.text,
        base: () => this.#model.base,
        send: (text, options) =>
          this.#commands.edit.send(this.#model.id, text, options),
        land: () => this.#commands.edit.land(this.node),
        paint: () => this.#commands.edit.paint(this.node),
        previous: () => this.#commands.edit.previous(this.#model.id),
        reveal: (caretLine) => this.#commands.edit.reveal(this.node, caretLine),
      });
    if (!editing && this.#editor) {
      this.#editor.dispose();
      this.#editor = null;
    }
    this.#editor?.follow();
    // Whether the message says it holds kept words follows the draft, which another tab
    // can change; a keystroke in the open editor changes no such answer.
    this.#kept = model.editable && !editing && keptRewrite(model.id);
    if (model.editable && !this.#stopKept)
      this.#stopKept = watchRewrite(model.id, () => {
        if (keptRewrite(this.#model.id) !== this.#kept)
          this.#commands.edit.paint(this.node);
      });
    keeps(this.#header, "data-lf-reflow", "text");
    if (prior && prior.author !== model.author)
      this.node.classList.toggle(prior.author, false);
    this.node.classList.toggle(model.author, true);
    keeps(this.node, panel ? "data-mid" : "data-event", model.id);
    this.node.classList.toggle("lf-unread", Boolean(model.unread));
    keeps(this.node, "data-attempt", model.attempt || null);
    keeps(this.node, "aria-busy", model.pending ? "true" : null);
    keeps(this.node, "data-failure", model.failure || null);
    if (model.nativeAuthored && model.body.authored && !this.#authored)
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
    const receipt = model.workflowLabel
      ? html`<span class="lf-msg-sending" title=${model.workflowTitle}
          >${model.workflowLabel}</span
        >`
      : nothing;
    render(
      html`
        <b>${model.by}</b
        ><span class="lf-msg-meta"
          ><time datetime=${model.timestamp}>${model.age}</time> ${receipt}
          ${
            model.leaves
              ? html`<span class="lf-msg-leaves">${model.leaves}</span>`
              : nothing
          }
          ${
            model.failure
              ? html`<span class="lf-msg-failure">${FAILURE_LABEL}</span>`
              : nothing
          }
          ${
            model.body.kind === "suggestion"
              ? html`<span class="lf-suggest-label">Suggestion</span>`
              : nothing
          }
          ${
            model.edited
              ? html`<span class="lf-edited" title=${model.edited}>edited</span>`
              : nothing
          }
          ${
            this.#kept
              ? html`<span
                  class="lf-msg-kept"
                  title="The rewrite is kept; open it to save or cancel"
                  >unsaved edit</span
                >`
              : nothing
          }
        </span>
        ${headerControls}
      `,
      this.#header,
    );
    // The user's own words offer their rewrite where an agent's reply offers its
    // reactions: the message's one control, at its header's right edge (shadow.css).
    const rewrite =
      model.editable && !editing
        ? html`<button
            type="button"
            class="lf-msg-control lf-msg-edit lf-ui"
            tabindex="-1"
            data-lf-gen="1"
            data-lf-offer="button"
            aria-label="Edit message"
            title="Edit message"
            @click=${() => this.openEdit()}
          >
            ${iconTemplate("edit", "lf-msg-control-icon")}
          </button>`
        : nothing;
    render(
      html`
        ${this.#header}
        <div
          class=${`lf-msg-body${model.body.kind === "suggestion" ? " lf-suggest-body" : ""}`}
        >
          ${editing ? this.#editor.node : this.#body(model.body)}
          ${
            model.body.drawing
              ? html`<span class="lf-drawing-reference">Drawing comment</span>`
              : nothing
          }
          ${model.nativeAuthored && model.body.authored ? this.#authored : nothing}
        </div>
        ${
          model.body.authored && !model.nativeAuthored
            ? html`<button
                type="button"
                class="lf-btn lf-page-thread-open lf-ui"
                data-lf-gen="1"
                data-lf-offer="button"
                @click=${() => this.#commands.openThread(this.#model.id, { part: "message" })}
              >
                Open interactive reply
              </button>`
            : nothing
        }
        ${strip} ${rewrite}
      `,
      this.node,
    );
    if (this.#authored && !this.#dressed) {
      markDeclared(this.node);
      renderSaid(this.node);
      renderQuiet(this.node);
      this.#dressed = true;
    }
    // Markdown is an opaque property part: tokenization never rewrites Lit markers.
    highlightBlocks(this.node);
    this.#stopRead = this.#commands.read.observeMessage(
      this.node.querySelector(":scope > .lf-msg-body"),
      model,
    );
    if (!prior && (model.pending || arrived)) {
      // One phase drives the message's ground and its sticky header. CSS resolves
      // the tint and resting colour at this message after insertion; Firefox's
      // Web Animations interpolates a var() colour keyframe discretely.
      // The shared motion gate answers for restoration and reduced motion; the
      // delivery receipt and busy cursor remain independent of the arrival tint.
      this.#arrivalMotion = motion(
        this.node,
        [{ "--lf-msg-arrival": 1, offset: 0 }],
        flashDuration(),
      );
    }
    return this.node;
  }

  // Open the user's own words for rewriting here, with the caret after them. False where
  // the message is not one they may rewrite.
  openEdit() {
    const model = this.#model;
    if (!model?.editable) return false;
    if (!this.#editor) {
      this.#commands.edit.opening(model.id, this, model.panel);
      this.#commands.edit.paint(this.node);
    }
    this.#editor?.enter();
    return true;
  }

  // Draw the message as it stands, its rewrite having opened in another view.
  closeEdit() {
    this.#commands.edit.paint(this.node);
  }

  // Make way for another editor opening in the thread, closing this one where its
  // words are the message's own.
  putEditAside() {
    this.#editor?.putAside();
  }

  // The reading this view last drew.
  get model() {
    return this.#model;
  }

  // Whether this view draws an open rewrite.
  get editing() {
    return this.#editor !== null;
  }

  #body(body) {
    if (body.kind === "reaction")
      return html`<div class="lf-msg-text">
        <span class="lf-react-said">${`${body.glyph} ${body.token}`.trim()}</span>
      </div>`;
    if (body.kind === "suggestion")
      return html`<div class="lf-msg-text" .textContent=${body.text}></div>`;
    return html`<div class="lf-msg-text" .innerHTML=${body.html}></div>
      ${
        body.mediaHtml
          ? html`<div class="lf-msg-media" .innerHTML=${body.mediaHtml}></div>`
          : nothing
      }`;
  }

  commit() {
    if (!this.#model.reactions && this.#reaction) {
      this.#reaction.retire();
      this.#reaction = null;
    }
  }

  retire() {
    this.#arrivalMotion?.cancel();
    this.#reaction?.retire();
    if (this.#model) releaseMessageEdit(this.#model.id, this);
    this.#editor?.dispose();
    this.#editor = null;
    this.#stopKept?.();
    this.#stopKept = null;
    this.#stopRead?.();
  }
}

function coordinateLabel(anchor, about) {
  if (about === "design") {
    const addressable = anchor?.section ? elementById(anchor.section) : null;
    const name = addressable ? designName(addressable) : anchor?.section || "the page";
    return anchor?.quote ? `${name} · “${anchor.quote}”` : name;
  }
  const datum = datumLabel(anchor);
  if (datum) return anchor?.quote ? `${datum} · “${anchor.quote}”` : `§ ${datum}`;
  if (anchor?.quote) return `“${anchor.quote}”`;
  if (!anchor?.section) return "";
  const addressable = elementById(anchor.section);
  if (anchor.visual) {
    const part = visualPartLabel(addressable, anchor.visual) ?? anchor.visual;
    return `§ ${addressable ? `${addressableWord(addressable)} · ${part}` : `${anchor.section} · ${part}`}`;
  }
  return `§ ${addressable ? sectionLabel(addressable) : anchor.section}`;
}

// A named control part belongs to the coordinate in every reading, not just Design.
export function anchorLabel(anchor, about) {
  const label = coordinateLabel(anchor, about);
  return [about === "design" && "design", anchor?.part, label]
    .filter(Boolean)
    .join(" · ");
}
