/* Synchronous Lit message presentation and frozen authored message islands.

   Every surface uses the same message, header and body vocabulary. Generated
   metadata, prose, workflow and reaction placement have one owner. Each message
   projects pasted attachments separately from its words using the draft's media
   reading, so a retained text viewport never clips an attachment. Each message
   retains its header and body together, sharing delivery, unread and fold state.
   Its header declares its stationary text-reflow boundary. An
   immutable descriptor changes prose without reconnecting the validated authored
   fragment. A new message cues its own words once on first presentation, in every
   surface: one the user just sent, and any turn, whoever wrote it, joining a thread
   view that was already presented. Opening a view cues nothing it already holds, and
   admission and later descriptor paints never replay the cue.
   The fragment is captured inertly before its first upgrade; presentation waits for
   preparation before capturing typed authored state. */
import { html, keyed, render, nothing, ref } from "/runtime/framework.js";
import { generatedElement, offeredAction } from "../widget-elements.js";
import {
  loadMarkdown,
  markdownReady,
  renderMarkdown,
  renderedWords,
} from "../markdown.js";
import { reportPageError } from "../layer-client.js";
import { editable, isReaction, lastMovedAt, messageKey } from "./model.js";
import { labelWords } from "../words.js";
import {
  MessageEditor,
  OPEN_MESSAGE_EDIT,
  holdsMessageEdit,
  keptRewrite,
  messageDrawn,
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
import {
  NOT_ANSWERED,
  strongestWorkflow,
  workflowTitle,
  workflowWord,
} from "./workflow.js";
import { voiced } from "../voice.js";
import { markDeclared, renderQuiet, renderSaid } from "../declared-words.js";
import { highlightBlocks } from "../syntax.js";
import { ago } from "../presence.js";
import { elementById } from "../passages.js";
import { designName } from "../design-readings.js";
import { addressableWord, sectionLabel } from "../addressable-names.js";
import { datumLabel, visualPartLabel } from "../anchor-resolution.js";
import { importWidgets, rememberPassageParts } from "../widget-loader.js";
import { ReactionStripView } from "./reaction-strips.js";
import { keeps } from "../keeps.js";
import { showsContents } from "../geometry.js";
import { flashDuration, motion } from "../motion.js";
import { agentName, pageClaimed } from "../semantic-state.js";
import { copyControl } from "../copy-control.js";

export const loadMessageMarkdown = () =>
  loadMarkdown((error) => reportPageError(error, `markdown renderer failed to load`));

// Prose parsing is shared across descriptor passes and surfaces. Its value changes
// with admission, edits, stream text, or the lazy Markdown renderer becoming ready;
// clock and receipt paint reuse the same HTML without retaining generated DOM.
/** @typedef {import("../framework/snapshot.js").Immutable<ReturnType<typeof import("./model.js").readThreadRecords>[number]["msgs"][number]>} MessageRecord */
/** @typedef {{id: string | undefined, edited: string | null, text: string,
 * markdown: boolean, html: string, mediaHtml: string, plainText: string}} ProseReading */
/** @type {Map<string | undefined, ProseReading>} */
const renderedProse = new Map();
/** @param {Parameters<typeof messageText>[0]} message @returns {ProseReading} */
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

// Authored messages hold the complete captured reading of prose and islands.
// Other messages and summaries still need their prose rendered here.
/** @param {{readonly id?: string, readonly attempt?: string, readonly text?: string | undefined, readonly token?: string, readonly suggestion?: boolean, readonly body?: {readonly kind: string, readonly text: string}, readonly edited?: {readonly id?: string} | null | undefined}} message @returns {string} */
export function messageText(message) {
  if (message.body?.kind === "authored") return message.body.text;
  if (message.token) {
    const token = tokenEntry(message.token);
    return `${token?.glyph ?? ""} ${message.token}`.trim();
  }
  return message.suggestion ? (message.text ?? "") : proseReading(message).plainText;
}

// A thread's name in words, as search, accessible names and prose read it: its title,
// else the words its opening message renders (an agent's authored opening, its captured
// text), else Drawing for one drawn without words. A surface clips it to its own room,
// and one that draws the name draws `threadHeading`.
/** @param {{readonly title: string | null, readonly root: Parameters<typeof messageText>[0] & {readonly body: {readonly kind: string, readonly text?: string}, readonly drawing?: unknown}}} thread */
export function threadName(thread) {
  if (thread.title != null) return thread.title;
  const { root } = thread;
  const words = labelWords(messageText(root));
  return words || (root.drawing ? "Drawing" : "");
}

// Whether a title is on its way to an untitled thread. Leaf asks the claimant's
// harness for one as the user's words are admitted, and the agent for one with its
// reply (thread_titles.py), so one comes while a session holds the page's claim and the
// agent owes the thread work. A turn that ended, stalled or was never picked up sends
// none, nor does a page nobody has claimed, and the thread reads its opening words.
/** @param {Parameters<typeof threadName>[0] & {readonly attention?: {readonly kind: string, readonly reason: string} | null}} thread */
export const titlePending = (thread) =>
  thread.title == null &&
  thread.attention?.kind === "waiting" &&
  thread.attention.reason === "workflow" &&
  pageClaimed();

// A thread's name wherever a surface draws it, as Threads, Page Map, On cards and the
// thread's view do: while a title is on its way, a placeholder in the face of a step
// under way (`.lf-thread-working-words`) rather than opening words that would read as
// its title.
// The opening words stay in its accessible name, after the placeholder, so a screen
// reader still tells two pending threads apart.
/** @param {Parameters<typeof titlePending>[0]} thread */
export const threadHeading = (thread) =>
  titlePending(thread)
    ? html`<span class="lf-thread-name-pending">Generating thread name…</span
        ><span class="lf-quiet"> ${threadName(thread)}</span>`
    : threadName(thread);

/** @param {Parameters<typeof threadName>[0] & Parameters<typeof lastMovedAt>[0]} thread */
export const threadSummary = (thread) => ({
  topic: threadName(thread),
  latest: lastMovedAt(thread),
});

// A rollback can withdraw an authored island, but neither retry nor a prose edit
// may instantiate it twice. Its native identity is independent of the prose cache.
/** @typedef {{
 * message: string,
 * body: {text: string, markup: string, document: {thread: string, message: string}},
 * authored: ReturnType<typeof stageAuthoredStates>,
 * descriptors: ReturnType<typeof stageWidgetDescriptors>,
 * nodes: readonly ChildNode[], root: DocumentFragment,
 * preparation: Promise<PreparedAuthoredMessage> | null,
 * }} PreparedAuthoredMessage */
/** @type {Map<string, PreparedAuthoredMessage>} */
const authoredMessages = new Map();
/** @param {{id: string, attempt?: string, markup?: string}} message @param {string} thread
 * @returns {Promise<PreparedAuthoredMessage>} */
export function prepareAuthoredMessage(message, thread) {
  const key = message.attempt ?? message.id;
  if (typeof thread !== "string" || !thread)
    throw new TypeError("an authored message needs its thread's id");
  let prepared = authoredMessages.get(key);
  if (!prepared) {
    const template = document.createElement("template");
    template.innerHTML = message.markup ?? "";
    markDeclared(template.content);
    rememberAuthoredParents(template.content);
    const descriptors = stageWidgetDescriptors(template.content, {
      kind: "thread",
      thread,
      message: message.id,
    });
    const authored = stageAuthoredStates(template.content, new Map());
    rememberPassageParts(template.content, ["event", message.id]);
    const text = template.content.textContent;
    const nodes = Object.freeze([...template.content.childNodes]);
    prepared = {
      message: message.id,
      body: {
        text,
        markup: message.markup ?? "",
        document: { thread, message: message.id },
      },
      authored,
      descriptors,
      nodes,
      root: template.content,
      preparation: null,
    };
    authoredMessages.set(key, prepared);
  }
  for (const descriptor of prepared.descriptors.descriptors.values())
    if (
      descriptor.document.kind !== "thread" ||
      descriptor.document.thread !== thread ||
      descriptor.document.message !== message.id
    )
      throw new TypeError("an authored message changed its frozen document identity");
  // The captured document owns preparation for its entire lifetime. Concurrent
  // state reads join it, including after its nodes leave the inert fragment for a
  // drawing. A failed import remains a failed state read; the next read may retry.
  const captured = prepared;
  return (captured.preparation ??= importWidgets(captured.root).then(
    () => captured,
    (error) => {
      captured.preparation = null;
      throw error;
    },
  ));
}
/** @param {{id: string, attempt?: string | null}} message */
const authoredMessage = (message) => {
  const prepared = authoredMessages.get(message.attempt ?? message.id);
  if (!prepared)
    throw new Error("authored message presentation preceded semantic preparation");
  return prepared;
};

// Which drawing of an authored message holds its widgets, the one instance above. A
// message can stand in several drawings at once (the primary reader's, a margin card,
// a seat on the page), and the shown one of highest `authoredRank` holds them, the
// first to draw it among equals. Every other drawing draws only the message's words:
// the holder is then the one shown, so the widgets already stand in view. A drawing
// shown as it draws takes them where it should hold them, as does the first to draw
// them, and after each draw the holder is settled again among the drawings shown, so
// one hidden in a fold or a closed card gives them to one in view. A drawing not yet
// placed in the page, as a card draws before its owner places it, is neither shown
// nor hidden: it waits for that settling to take them, and keeps what it holds.
// Whichever drawings gain or lose them draw again at once, as their own containers
// would not.
/** @typedef {{node: HTMLDivElement, model: ReturnType<typeof messageReading>,
 * present: (model: ReturnType<typeof messageReading>) => HTMLDivElement}} PresentedMessage */
/** @type {Map<string, Set<PresentedMessage>>} */
const authoredDrawings = new Map();
/** @type {Map<string, PresentedMessage>} */
const authoredHolders = new Map();
/** @param {PresentedMessage} view */
const shown = (view) => view.node.isConnected && showsContents(view.node);
/** @param {PresentedMessage} view */
const hidden = (view) => view.node.isConnected && !showsContents(view.node);
/** @param {PresentedMessage} a @param {PresentedMessage} b */
const outranks = (a, b) => a.model.authoredRank > b.model.authoredRank;
/** @param {string} key */
function settleAuthored(key) {
  const drawings = authoredDrawings.get(key) ?? new Set();
  const holder = authoredHolders.get(key);
  const held = holder && drawings.has(holder) && !hidden(holder) ? holder : null;
  let best = null;
  for (const view of drawings)
    if (shown(view) && (!best || outranks(view, best))) best = view;
  if (!best || best === holder || (held && !outranks(best, held))) return;
  authoredHolders.set(key, best);
  best.present(best.model);
  if (holder && drawings.has(holder)) holder.present(holder.model);
}
/** @type {Set<string>} */
const unsettled = new Set();
/** @param {string} key */
function settleAuthoredSoon(key) {
  if (unsettled.has(key)) return;
  unsettled.add(key);
  queueMicrotask(() => {
    unsettled.delete(key);
    settleAuthored(key);
  });
}
/** @param {string} key @param {PresentedMessage} view */
function releaseAuthored(key, view) {
  if (authoredHolders.get(key) !== view) return;
  authoredHolders.delete(key);
  settleAuthored(key);
}
// Lets go of the widgets the drawings under `root` hold, as a card closing does.
/** @param {Element} root */
export function releaseAuthoredUnder(root) {
  for (const [key, view] of [...authoredHolders])
    if (root.contains(view.node)) releaseAuthored(key, view);
}
// The drawn message holding the widgets of the message `id`, if a drawing holds them.
/** @param {string} id */
export function authoredHolder(id) {
  for (const view of authoredHolders.values())
    if (view.model.id === id && shown(view)) return view.node;
  return null;
}
/** @param {MessageRecord} message
 * @param {{authoredRank?: number, reactions: MessageRecord["reactions"],
 * workflows: readonly import("../framework/application.js").Workflow[],
 * leaves?: import("../voice.js").Said | null}} options */
export function messageReading(
  message,
  { authoredRank = 0, reactions, workflows, leaves = null },
) {
  const workflow = strongestWorkflow(workflows);
  const token = message.token ? tokenEntry(message.token) : null;
  const kind = isReaction(message)
    ? "reaction"
    : message.suggestion
      ? "suggestion"
      : "prose";
  const prose = kind === "prose" ? proseReading(message) : null;
  return Object.freeze({
    key: messageKey(message),
    id: message.id,
    thread: message.thread,
    // A reply still streaming, which the answer it stands for completes in place.
    provisional: Boolean(message.provisional),
    // The agent's progress message (`ephemeral`): a step of work in hand, which the
    // thread shows as its run's face until an answer folds it (transcript.js).
    progress: Boolean(message.ephemeral),
    // What an answer leaves standing, while it stands: Leaf's "Waiting on me" for the
    // question the user owes words to, the agent's Still to do (`todoWord`) for work it
    // promised and has not ended (thread-card.js).
    leaves,
    version: message.content_version,
    // Original log order: edits move the words without moving where they were said.
    sequence: message.seq ?? Infinity,
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
    workflowWord: workflowWord(workflow, agentName()),
    workflowTitle: workflowTitle(workflow, agentName()),
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
    // The message as its Copy control copies it: its words as written, then any markup
    // an agent sent after them, which Markdown carries as HTML. A reaction has none.
    markdown:
      kind === "reaction"
        ? null
        : [message.text, message.body.kind === "authored" ? message.body.markup : null]
            .filter(Boolean)
            .join("\n\n"),
    // Where this drawing ranks among those that may hold the message's widgets
    // (`authoredHolders`); 0 for one that never does.
    authoredRank,
    reactions,
  });
}

/** @typedef {{read: Pick<ReturnType<typeof import("./read.js").createReadTracking>, "observeMessage">,
 * reply: {wireInput: ReturnType<typeof import("../composing/input.js").createCompositionInputs>["wireInput"],
 * actions: Pick<ReturnType<typeof import("./actions.js").createThreadActions>, "edit">},
 * reaction: ConstructorParameters<typeof ReactionStripView>[0],
 * edit: ReturnType<typeof import("./message-edit.js").threadRewrites>["edit"]}} MessageCommands */

export class MessageView {
  #commands;
  /** @type {PresentedMessage | null} */
  #presentation = null;
  get #model() {
    return this.#presentation?.model ?? null;
  }
  /** @type {ReactionStripView | null} */
  #reaction = null;
  /** @type {ReturnType<typeof copyControl> | null} */
  #copy = null;
  // Bumped each time this view takes the message's widgets back from another drawing.
  #authoredTake = 0;
  #dressed = false;
  /** @type {ReturnType<typeof motion> | null} */
  #arrivalMotion = null;
  /** @type {(() => void) | null} */
  #stopRead = null;
  /** @type {MessageEditor | null} */
  #editor = null;
  #kept = false;
  /** @type {(() => void) | null} */
  #stopKept = null;
  // Whether the head says the message's age, which a transcript leaves out where the
  // message above already says it (transcript.js). A presentation that doesn't say,
  // as a drawing taking back its widgets doesn't, keeps the last answer.
  #dated = true;

  /** @param {MessageCommands} commands */
  constructor(commands) {
    this.#commands = commands;
    this.node = document.createElement("div");
  }

  /** @param {ReturnType<typeof messageReading>} model
   * @param {{arrived?: boolean, dated?: boolean, headerControls?: unknown}} [options] */
  present(
    model,
    { arrived = false, dated = this.#dated, headerControls = nothing } = {},
  ) {
    const prior = this.#model;
    const presentation = (this.#presentation ??= {
      node: this.node,
      model,
      present: (reading) => this.present(reading),
    });
    presentation.model = model;
    this.#dated = dated;
    // A view presents messages of one surface for its whole life, so what the surface
    // makes of the node is written once, on the first presentation.
    if (!prior) {
      this.node.classList.add("lf-msg");
      // Which message a node draws, for a presentation handing the user's place in a
      // thread to another, as the floating panel does to a page's own reader.
      this.node.dataset.message = model.key;
      this.node.classList.add("lf-ui");
      generatedElement(this.node, { says: false });
      this.node.dataset.lfOffer = "";
      // A double click on the user's own words opens them for rewriting, as the word
      // under it would otherwise only be selected. The word it selected goes first: the
      // editor then sets its own caret, which clearing the selection after would take. A
      // link keeps its own double click, and a control its own presses.
      this.node.addEventListener("dblclick", (event) => {
        if (
          event.target instanceof Element &&
          event.target.closest(".lf-msg-editor, .lf-msg-controls, a[href]")
        )
          return;
        if (!this.#model?.editable) return;
        window.getSelection()?.removeAllRanges();
        this.openEdit();
      });
      this.node.addEventListener(OPEN_MESSAGE_EDIT, () => this.openEdit());
    }
    // The view the user opened the rewrite in draws its editor (`message-edit.js`); a
    // closed editor goes with its subscription and keys.
    const editing = model.editable && holdsMessageEdit(model.id, this);
    const editor = editing
      ? (this.#editor ??= new MessageEditor(model.id, this, {
          wireInput: this.#commands.reply.wireInput,
          said: () => presentation.model.body.text,
          base: () => presentation.model.base,
          send: (text, options) =>
            this.#commands.reply.actions.edit(
              presentation.model.thread,
              presentation.model.id,
              text,
              options,
            ),
          land: () => this.#commands.edit.land(this.node),
          paint: () => this.#commands.edit.paint(this.node),
          previous: () => this.#commands.edit.previous(presentation.model.id),
          reveal: (caretLine) => this.#commands.edit.reveal(this.node, caretLine),
        }))
      : null;
    if (!editor && this.#editor) {
      this.#editor.dispose();
      this.#editor = null;
    }
    editor?.follow();
    // Whether the message says it holds kept words follows the draft, which another tab
    // can change; a keystroke in the open editor changes no such answer.
    this.#kept = model.editable && !editor && keptRewrite(model.id);
    if (model.editable && !this.#stopKept)
      this.#stopKept = watchRewrite(model.id, () => {
        if (keptRewrite(presentation.model.id) !== this.#kept)
          this.#commands.edit.paint(this.node);
      });
    if (prior && prior.author !== model.author)
      this.node.classList.toggle(prior.author, false);
    this.node.classList.toggle(model.author, true);
    keeps(this.node, "data-event", model.id);
    this.node.classList.toggle("lf-unread", Boolean(model.unread));
    keeps(this.node, "data-attempt", model.attempt || null);
    keeps(this.node, "aria-busy", model.pending ? "true" : null);
    keeps(this.node, "data-failure", model.failure || null);
    const authoredKey = model.attempt ?? model.id;
    const authored = model.body.authored ? authoredMessage(model).nodes : [];
    let displaced = null;
    if (model.authoredRank && model.body.authored) {
      let drawings = authoredDrawings.get(authoredKey);
      if (!drawings) authoredDrawings.set(authoredKey, (drawings = new Set()));
      drawings.add(presentation);
      const holder = authoredHolders.get(authoredKey);
      const holding = holder && drawings.has(holder);
      if (
        holder !== presentation &&
        (holding
          ? shown(presentation) && (hidden(holder) || outranks(presentation, holder))
          : !hidden(presentation))
      ) {
        authoredHolders.set(authoredKey, presentation);
        if (holding) displaced = holder;
      }
      settleAuthoredSoon(authoredKey);
    }
    const holds = authoredHolders.get(authoredKey) === presentation;
    // Lit keeps nodes it already placed, so where another drawing took them since this
    // one drew them, a new key puts them back here.
    if (holds && authored.some((node) => !this.node.contains(node)))
      this.#authoredTake++;
    if (!model.reactions) this.#reaction?.retire();
    const strip = model.reactions
      ? (this.#reaction ??= new ReactionStripView(this.#commands.reaction)).present(
          model.reactions,
        )
      : nothing;
    // The message's own controls, one group at its head's end (controls.css): the user's
    // own words offer their rewrite, or, open, its Discard and Save; an agent's reply
    // its reactions; and every message with words its Copy, last.
    const rewrite = editor
      ? editor.actions
      : model.editable
        ? html`<button
            ${offeredAction("symbol", "lf-msg-control lf-msg-edit", "Edit message", {
              action: "edit",
            })}
            tabindex="-1"
            @click=${() => this.openEdit()}
          ></button>`
        : nothing;
    const react = this.#reaction && model.reactions ? this.#reaction.trigger : nothing;
    const copy =
      model.markdown && !editor ? this.#copyControl(model.markdown) : nothing;
    const receipt = model.workflowWord
      ? html`<span class="lf-msg-sending" title=${model.workflowTitle}
          >${voiced(model.workflowWord)}</span
        >`
      : nothing;
    const header = html`
      <div class="lf-msg-head" data-lf-reflow="text">
        <b>${model.by}</b
        ><span class="lf-msg-meta"
          >${
            dated
              ? html`<time datetime=${model.timestamp}>${model.age}</time>`
              : nothing
          }${
            model.unread
              ? html`<span class="lf-msg-new lf-unread-dot"
                  ><span class="lf-quiet">New</span></span
                >`
              : nothing
          }
          ${receipt}
          ${
            model.leaves
              ? html`<span class="lf-msg-leaves">${voiced(model.leaves)}</span>`
              : nothing
          }
          ${
            model.failure
              ? html`<span class="lf-msg-failure">${voiced(NOT_ANSWERED)}</span>`
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
                  title="The edit is kept; open it to save or discard"
                  >unsaved edit</span
                >`
              : nothing
          }
        </span>
        ${headerControls}<span class="lf-msg-control-room"
          ><span class="lf-msg-controls">${rewrite}${react}${copy}</span></span
        >
      </div>
    `;
    render(
      html`
        ${header}
        <div
          class=${`lf-msg-body${model.body.kind === "suggestion" ? " lf-suggest-body" : ""}`}
          ${ref((body) => {
            if (body) this.#stopRead = this.#commands.read.observeMessage(body, model);
          })}
        >
          ${editor ? editor.node : this.#body(model.body)}
          ${
            model.body.drawing
              ? html`<span class="lf-drawing-reference">Drawing comment</span>`
              : nothing
          }
          ${holds ? keyed(this.#authoredTake, authored) : nothing}
        </div>
        ${strip}
      `,
      this.node,
    );
    if (model.body.authored && !this.#dressed) {
      markDeclared(this.node);
      renderSaid(this.node);
      renderQuiet(this.node);
      this.#dressed = true;
    }
    // Markdown is an opaque property part: tokenization never rewrites Lit markers.
    highlightBlocks(this.node);
    // The drawing these widgets left draws the way here instead.
    displaced?.present(displaced.model);
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
    // Whether this message can be rewritten may have moved, which the reply box's ↑
    // reads (`threadRewrites`).
    messageDrawn();
    return this.node;
  }

  // Open the user's own words for rewriting here, with the caret after them. False where
  // the message is not one they may rewrite.
  openEdit() {
    const model = this.#model;
    if (!model?.editable) return false;
    if (!this.#editor) {
      this.#commands.edit.opening(model, this);
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

  // Copy stands at the head's end, after the message's own control (controls.css), and
  // copies the message whole as Markdown. Like Edit it is no Tab stop, which would add
  // one to every message between a thread's controls; the keyboard presses it with the
  // copy key in the thread (landing.js, `message.copy`).
  /** @param {string} markdown */
  #copyControl(markdown) {
    if (!this.#copy) {
      this.#copy = copyControl("lf-msg-control lf-msg-copy", {
        role: "symbol",
        label: "Copy as Markdown",
        success: "Message copied as Markdown",
        error: "Message not copied · select its words to copy",
      });
      this.#copy.tabIndex = -1;
      this.#copy.title = "Copy as Markdown";
    }
    if (this.#copy.value !== markdown) this.#copy.value = markdown;
    return this.#copy;
  }

  /** @param {ReturnType<typeof messageReading>["body"]} body */
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
    if (!this.#model?.reactions && this.#reaction) {
      this.#reaction.retire();
      this.#reaction = null;
    }
  }

  retire() {
    const presentation = this.#presentation;
    if (presentation) {
      const key = presentation.model.attempt ?? presentation.model.id;
      authoredDrawings.get(key)?.delete(presentation);
      if (!authoredDrawings.get(key)?.size) authoredDrawings.delete(key);
      releaseAuthored(key, presentation);
    }
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

// Where an element an agent sent in a message stands, by its id: the one instance of it
// the message keeps (`prepareAuthoredMessage`), with the message and its thread. It
// stands on the page only while a drawing of that message does, as a margin card or the
// floating panel's view of its thread, so a thread about it is named by its words, and
// placed in its message (anchor-placement.js), while the message is put away.
/** @param {string} id */
export function messageHolding(id) {
  for (const { nodes, body } of authoredMessages.values())
    for (const node of nodes) {
      if (!(node instanceof Element)) continue;
      const element = node;
      const kept =
        element.id === id ? element : element.querySelector(`[id="${CSS.escape(id)}"]`);
      if (kept) return { element: kept, ...body.document };
    }
  return null;
}

// The element a coordinate names: the page's, else one a message keeps.
/** @param {string} id */
const addressableAt = (id) => elementById(id) ?? messageHolding(id)?.element ?? null;

/** @param {import("../../types/domain.js").Anchor | null | undefined} anchor @param {string | null | undefined} about */
function coordinateLabel(anchor, about) {
  if (about === "design") {
    const addressable = anchor?.section ? addressableAt(anchor.section) : null;
    const name = addressable ? designName(addressable) : anchor?.section || "the page";
    return anchor?.quote ? `${name} · “${anchor.quote}”` : name;
  }
  const datum = datumLabel(anchor);
  if (datum) return anchor?.quote ? `${datum} · “${anchor.quote}”` : `§ ${datum}`;
  if (anchor?.quote) return `“${anchor.quote}”`;
  if (!anchor?.section) return "";
  const addressable = addressableAt(anchor.section);
  if (anchor.visual) {
    const part = visualPartLabel(addressable, anchor.visual) ?? anchor.visual;
    return `§ ${addressable ? `${addressableWord(addressable)} · ${part}` : `${anchor.section} · ${part}`}`;
  }
  return `§ ${addressable ? sectionLabel(addressable) : anchor.section}`;
}

// A named control part belongs to the coordinate in every reading, not just Design.
/** @param {import("../../types/domain.js").Anchor | null | undefined} anchor @param {string | null | undefined} [about] */
export function anchorLabel(anchor, about) {
  const label = coordinateLabel(anchor, about);
  return [about === "design" && "design", anchor?.part, label]
    .filter(Boolean)
    .join(" · ");
}
