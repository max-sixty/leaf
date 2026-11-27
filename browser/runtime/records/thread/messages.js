/* Synchronous Lit message presentation and authored message islands.

   Every surface uses the same message, header and body vocabulary. Generated
   metadata, prose, workflow and reaction placement have one owner. Each message
   projects pasted attachments separately from its words using the draft's media
   reading, so a retained text viewport never clips an attachment. Each message
   retains its header and body together, sharing delivery, unread and fold state.
   Its header declares its stationary text-reflow boundary. An agent's message holding
   HTML is one validated authored fragment, its words included, prepared again for each
   edit of it. A new message cues its own words once on first presentation, in every
   surface: one the user just sent, and any turn, whoever wrote it, joining a thread
   view that was already presented. Opening a view cues nothing it already holds, and
   admission and later descriptor paints never replay the cue.
   The fragment is captured inertly before its first upgrade; presentation waits for
   preparation before capturing typed authored state. */
import {
  Directive,
  directive,
  html,
  keyed,
  noChange,
  nothing,
  ref,
  render,
} from "/vendor/lit.js";
import { setRenderedChildren } from "../../dom/dom-children.js";
import { generatedElement, worksInside } from "../../dom/widget-elements.js";
import { offeredAction } from "../../lib/controls.js";
import {
  loadMarkdown,
  markdownReady,
  renderAuthoredMarkdown,
  renderMarkdown,
  renderedWords,
} from "../../lib/markdown.js";
import { pageLinks } from "../page-markdown.js";
import { reportPageError } from "../../transport/layer-client.js";
import {
  deleted,
  editable,
  isReaction,
  messageKey,
  turns,
} from "../../state/thread/model.js";
import { counted, excerptWords, labelWords } from "../../lib/words.js";
import {
  MessageEditor,
  OPEN_MESSAGE_EDIT,
  holdsMessageEdit,
  keptRewrite,
  messageDrawn,
  releaseMessageEdit,
  watchRewrite,
} from "./message-edit.js";
import { declarationFor } from "../../state/registry.js";
import {
  isCanonicalMediaUrl,
  readAttachedMedia,
  scopedMediaUrl,
  writeAttachedMedia,
} from "../media.js";
import {
  rememberAuthoredParents,
  stageAuthoredStates,
} from "../projection/authored.js";
import {
  bindWidgetDescriptors,
  stageWidgetDescriptors,
} from "../widget-descriptors.js";
import {
  NOT_ANSWERED,
  strongestWorkflow,
  threadAttention,
  workflowTitle,
  workflowWord,
} from "./workflow.js";
import { agentSays, leafSays, voiced, wordsText } from "../../base/voice.js";
import { markDeclared, renderQuiet } from "../declared-words.js";
import { dressCode } from "../../readings/code-dressing.js";
import { agePreview, ago, clockTime, saidAt } from "../../state/presence.js";
import { elementById, says } from "../../readings/passages.js";
import { designName } from "../../base/design-readings.js";
import { sectionLabel } from "../../readings/addressable-names.js";
import { addressableWord } from "../../lib/element-word.js";
import { datumLabel, visualPartLabel } from "../../readings/anchor-resolution.js";
import { importWidgets, rememberPassageParts } from "../widget-loader.js";
import { ReactionStripView } from "./reaction-strips.js";
import { keeps } from "../../lib/keeps.js";
import { loadDraft } from "../drafts.js";
import { showsContents } from "../../dom/geometry.js";
import { motion } from "../../dom/motion.js";
import { motionTime } from "../../lib/motion-timing.js";
import { agentName, pageClaimed } from "../../state/semantic-state.js";
import { copyControl } from "../../transport/copy-control.js";
import { messageLink } from "./address.js";

// A message's words, drawn into the element the binding stands on and reconciled as a
// revision reconciles authored markup (dom/dom-children.js, `setRenderedChildren`): an
// edit keeps every node it leaves alone and rewrites a changed paragraph's words in
// place, so the browser's scroll anchoring still holds the paragraph a reader is in
// when an edit grows one above it. A property binding to `innerHTML` replaced every
// one, and neither engine anchors again on a node that replaces its anchor. An edit
// rewriting nearly every paragraph of a long message is drawn whole again (`bounded`),
// as that binding drew it, rather than diffed at the square of its length.
const keptWords = directive(
  class extends Directive {
    /** @type {string | null} */
    #drawn = null;
    /** @param {string} _markup */
    render(_markup) {
      return noChange;
    }
    /** @param {import("/vendor/lit.js").ElementPart} part @param {[string]} markup */
    update(part, [markup]) {
      if (markup === this.#drawn) return noChange;
      this.#drawn = markup;
      const parsed = document.createElement("template");
      parsed.innerHTML = markup;
      setRenderedChildren(part.element, parsed.content.childNodes, { bounded: true });
      return noChange;
    }
  },
);

export const loadMessageMarkdown = () =>
  loadMarkdown((error) => reportPageError(error, `markdown renderer failed to load`));

// Prose parsing is shared across descriptor passes and surfaces. Its value changes
// with admission, edits, stream text, or the lazy Markdown renderer becoming ready;
// clock and receipt paint reuse the same HTML without retaining generated DOM.
/** @typedef {import("../../base/snapshot.js").Immutable<ReturnType<typeof import("../../state/thread/model.js").readThreadRecords>[number]["msgs"][number]>} MessageRecord */
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
    const html = renderMarkdown(pasted.text, pageLinks);
    const mediaHtml = renderMarkdown(writeAttachedMedia("", pasted.paths), pageLinks);
    reading = Object.freeze({
      id: message.id,
      edited,
      text,
      markdown,
      html,
      mediaHtml,
      // An image counts as the thread names it, its alt text (`renderedWords`).
      plainText: renderedWords(html + mediaHtml, true),
    });
    renderedProse.set(key, reading);
  }
  return reading;
}

// Authored messages hold the complete captured reading of their words.
// Other messages and summaries still need their prose rendered here.
// What a deleted message reads in its place, in Leaf's voice, as what the user did.
const DELETED = leafSays("Deleted");

/** @param {{readonly id?: string, readonly attempt?: string, readonly text?: string | undefined, readonly emoji?: string, readonly suggestion?: boolean, readonly body?: {readonly kind: string, readonly text: string}, readonly edited?: {readonly id?: string} | null | undefined}} message @returns {string} */
export function messageText(message) {
  if (message.body?.kind === "authored") return message.body.text;
  if (message.emoji) return message.emoji;
  return message.suggestion ? (message.text ?? "") : proseReading(message).plainText;
}

// A whole message in words, on one line, as a thread holds it: what it renders, its
// widgets' words and its images' alt text included (`messageText`), else Drawing for
// one drawn without words, or Deleted message.
/** @param {Parameters<typeof messageText>[0] & {readonly drawing?: unknown, readonly withdrawn?: unknown}} message */
export const messageWords = (message) =>
  labelWords(messageText(message)) ||
  (message.drawing ? "Drawing" : deleted(message) ? "Deleted message" : "");

// A thread's name in words, as search, accessible names and prose read it: its title,
// else its opening message's words (`messageWords`). A surface clips it to its own
// room, and one that draws the name draws `threadHeading`.
/** @param {{readonly title: string | null, readonly root: Parameters<typeof messageWords>[0]}} thread */
export const threadName = (thread) => thread.title ?? messageWords(thread.root);

// Whether a title is on its way to an untitled thread. Leaf asks the claimant's
// harness for one as the user's words are admitted, and the agent's reply names the
// thread (thread_titles.py), so one comes while a session holds the page's claim and
// the agent owes the thread work. A turn that ended, stalled or was never picked up
// sends none. On a page nobody has claimed only an agent's reply names the thread, and
// the page can't tell whether an agent hears it, so the thread reads its opening words.
/** @param {Parameters<typeof threadName>[0] & {readonly attention?: {readonly next_actor: string | null, readonly state: string, readonly source: {readonly kind: string}} | null}} thread */
export const titlePending = (thread) =>
  thread.title == null &&
  thread.attention?.next_actor === "agent" &&
  thread.attention.source.kind === "update" &&
  thread.attention.state !== "blocked" &&
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

// A message's opening line, as a preview reads it: its first line of words, else
// Drawing for one drawn without words.
/** @param {Parameters<typeof messageText>[0] & {readonly drawing?: unknown}} message */
const openingLine = (message) =>
  messageText(message).split("\n").map(labelWords).find(Boolean) ??
  (message.drawing ? "Drawing" : "");

// Who a message's head names: the agent by its name, the user as Me.
/** @param {{readonly author: string, readonly agent?: string | null}} message */
const authorName = (message) => (message.author === "agent" ? message.agent : "Me");

// The characters of a thread's name or a message's opening line a preview keeps,
// which wrap within its width.
export const PREVIEWED_LINE = 120;
// The characters of a thread's name a preview listing several threads keeps of each,
// and a thread card's own name keeps.
export const LISTED_NAME = 60;
// Where a thread stands, as its preview says it (`threadPreview`): its word
// (`threadAttention`) and the agent's line on the work in hand, what it holds unread
// and how many messages it holds, each said by whoever says it, less the part `said`,
// which what it describes already says.
/** @param {import("./workflow.js").ThreadRecord} thread @param {string | null} said */
function threadStands(thread, said) {
  const attention = threadAttention(thread, agentName());
  const detail = attention?.turn === "agent" ? attention.workflow?.detail : null;
  const unread = thread.unread.length;
  return {
    turn: attention?.turn === "user" ? "user" : null,
    words: [
      ...(attention ? [attention.word] : []),
      ...(detail ? [agentSays(labelWords(detail))] : []),
      ...(unread ? [leafSays(`${unread} unread`)] : []),
      leafSays(counted(turns(thread).length, "message")),
    ]
      .filter((part) => wordsText(part) !== said)
      .flatMap((part, at) => (at ? [" · ", part] : [part])),
  };
}

// When a message or a step's face was said, in its head (state/presence.js, `saidAt`): its
// day, then its time. A head too narrow for both keeps the day whole and drops the
// time onto a line it clips (surfaces.css), so a crowded head still says which day,
// where an ellipsis cut it to "Nov 1…"; the preview reads the time whole.
/** @param {string | null | undefined} timestamp */
export function saidTime(timestamp) {
  const said = saidAt(timestamp);
  return said
    ? html`<time datetime=${timestamp} .lfPreview=${agePreview}
        >${said.day ? html`<span>${said.day}</span> ` : nothing}<span
          >${said.time}</span
        ></time
      >`
    : nothing;
}

/** What pointing at threads reads (annotations/preview.js), on a passage mark and on a margin entry
 * alike, from the reading every surface paints a thread from, as a name and lines of
 * detail. One thread is named as every surface names it (`threadName`), and its lines
 * say who wrote its last message and when, that message's opening line, and where the
 * thread stands: "Your turn · 1 unread · 5 messages". An untitled thread's name is its
 * opening words, so a thread whose last message is its first says them once. A target
 * holding several threads is named by their count, as the card a press opens lists
 * them, and lists each, its name and where it stands, which the preview owner fits to
 * the room its face stands in (annotations/preview.js, `fit`), saying how many more past those:
 * a press still reaches them, as the card it opens steps through every thread, and on
 * a window too narrow for the card, the thread it opens in the panel goes back to the
 * panel's list of them, where each row previews its thread. A line in the user's turn
 * wears the turn's mark (`data-lf-turn`). Where the preview describes something that already says one
 * thread's word, as a margin entry's name does to the keyboard, `said` is that word,
 * which its line leaves out, so a screen reader hears it once.
 * @param {readonly import("./workflow.js").ThreadRecord[]} threads
 * @param {string | null} [said]
 * @returns {import("../../base/preview-declaration.js").Preview | null} */
export function threadPreview(threads, said = null) {
  const [only] = threads;
  if (!only) return null;
  /** @param {ReturnType<typeof threadStands>} stands @param {string} [lead] */
  const standing = ({ turn, words }, lead = "") =>
    html`<span data-lf-turn=${turn ?? nothing}>${lead}${voiced(words)}</span>`;
  if (threads.length === 1) {
    const last = turns(only).at(-1) ?? only.root;
    const opening = last.id === only.root.id && only.title == null;
    return {
      name: excerptWords(threadName(only), PREVIEWED_LINE),
      detail: [
        `${authorName(last)} · ${ago(last.ts)}`,
        !opening &&
          (deleted(last)
            ? voiced(DELETED)
            : excerptWords(openingLine(last), PREVIEWED_LINE)),
        standing(threadStands(only, said)),
      ],
    };
  }
  return {
    name: counted(threads.length, "thread"),
    list: {
      items: threads.map((thread) =>
        standing(
          threadStands(thread, null),
          `${excerptWords(threadName(thread), LISTED_NAME)} · `,
        ),
      ),
      more: (count) =>
        voiced(leafSays(`and ${counted(count, "more thread", "more threads")}`)),
    },
  };
}

// A listed draft in words, on one line, as it now stands (records/drafts.js, the drafts list):
// what its message would say, Drawing for ink alone.
/** @param {import("../drafts.js").ListedDraft} draft */
export const draftWords = (draft) => {
  const payload = /** @type {{suggest?: unknown, drawing?: unknown} | undefined} */ (
    draft.payload
  );
  return messageWords({
    attempt: `draft:${draft.context}`,
    text: loadDraft(draft.context)?.text ?? "",
    suggestion: Boolean(payload?.suggest),
    drawing: payload?.drawing,
  });
};
// A listed draft's words as a preview reads them: a line of them, cut at its length.
/** @param {import("../drafts.js").ListedDraft} draft */
export const draftLine = (draft) => excerptWords(draftWords(draft), PREVIEWED_LINE);
// What drafts say when pointed at, on a row of Threads and on a margin entry: each
// one's words, a line of them, under what it is about where the place pointed at
// doesn't already say it. What Send makes of it stands beside it on both.
/** @param {readonly import("../drafts.js").ListedDraft[]} drafts
 * @param {import("../../base/voice.js").Words | null} [about]
 * @returns {import("../../base/preview-declaration.js").Preview | null} */
export function draftPreview(drafts, about = null) {
  const [only] = drafts;
  if (!only) return null;
  if (drafts.length === 1)
    return { name: about ? voiced(about) : "Draft", detail: [draftLine(only)] };
  return {
    name: counted(drafts.length, "draft"),
    list: {
      items: drafts.map(draftLine),
      more: (count) =>
        voiced(leafSays(`and ${counted(count, "more draft", "more drafts")}`)),
    },
  };
}

// A rollback can withdraw an authored island, but a retry may not instantiate it
// twice. Its native identity is independent of the prose cache. Each wording of a
// message has an island of its own, so a drawing that holds back an agent's edit
// (held-news.js) keeps drawing the words and controls it shows, and the reading the
// page adopts decides which island the message's widgets answer for
// (`islandChange`). Each island lives until the page reloads, one for each edit an
// agent makes to a message holding HTML, which is rare. An edit redraws its
// message's island whole, so a value typed into a field in it, an open disclosure
// or focus there is lost: a rare path, which redraws rather than carrying a
// mechanism of its own (SOUL.md, "Keep Leaf's code plain"). For
// the same reason a thread gesture names no wording: one a tab makes before an
// edit reaches it is read in the wording in force when it lands
// (`thread_context.message_wording`).
/** @typedef {{
 * message: string,
 * body: {text: string, heldElsewhere: string, document: {thread: string, message: string}},
 * authored: ReturnType<typeof stageAuthoredStates>,
 * descriptors: ReturnType<typeof stageWidgetDescriptors>,
 * nodes: readonly ChildNode[], root: DocumentFragment,
 * preparation: Promise<PreparedAuthoredMessage> | null,
 * }} PreparedAuthoredMessage */
/** Each message → its islands by the Markdown each was prepared from.
 * @type {Map<string, Map<string, PreparedAuthoredMessage>>} */
const authoredMessages = new Map();
/** Each message → the island the adopted reading draws its widgets from.
 * @type {Map<string, PreparedAuthoredMessage>} */
const adoptedIslands = new Map();
// Each element with an id that an adopted island keeps, with its message's document,
// so finding one by id (`messageHolding`) costs one read however many messages the
// page holds. Its ids are the authored ones, which no other message takes.
/** @type {Map<string, {element: Element, document: {thread: string, message: string}}>} */
const keptElements = new Map();
// The markup a drawing that doesn't hold an authored message draws in its place
// (`authoredHolders`): the message less what a second copy would duplicate, each id
// and each custom element, which a module upgrades once. A widget set among words
// (`inline`) leaves its words, and any other goes whole, as a choice the drawing
// asks in its own controls does. The innermost named group round a widget that asks,
// an element whose declaration's `reading-role` is `group` (`obligation_sources.widget_groups`
// in Python), is its question, so it goes whole with it rather than leaving the
// question's words with nothing to answer them. Any other group leaves what it holds,
// less its widgets, as a figure keeps its caption when its chart goes.
/** The innermost named group holding `element`, or null.
 * @param {Element} element @returns {Element | null} */
function groupRound(element) {
  for (let at = element.parentElement; at; at = at.parentElement)
    if (declarationFor(at)?.["reading-role"] === "group") return at;
  return null;
}
/** @param {DocumentFragment} message */
function heldElsewhere(message) {
  const copy = document.createElement("template");
  copy.content.append(message.cloneNode(true));
  for (const element of copy.content.querySelectorAll("*")) {
    const declaration = declarationFor(element);
    if (declaration?.awaits && !declaration.inline) groupRound(element)?.remove();
  }
  for (const element of copy.content.querySelectorAll("*")) {
    const declaration = declarationFor(element);
    if (!element.localName.includes("-")) element.removeAttribute("id");
    else if (declaration?.inline || declaration?.["reading-role"] === "group")
      element.replaceWith(...element.childNodes);
    else element.remove();
  }
  return copy.innerHTML;
}

/** @param {PreparedAuthoredMessage} island @returns {Iterable<Element>} */
function* islandElements(island) {
  for (const node of island.nodes)
    if (node instanceof Element) {
      if (node.id) yield node;
      yield* node.querySelectorAll("[id]");
    }
}

/**
 * What adopting a reading changes about the islands its messages draw their widgets
 * from, against the reading adopted before it: `retired`, the widget ids an island
 * held that its message's island in this reading doesn't, as when an edit rewrote
 * the message or left it no HTML; and `commit`, which makes this reading's islands
 * the adopted ones once the page adopts it. `prepared` is null for a message drawn
 * as Markdown alone. A message whose island is unchanged costs one lookup.
 * @param {readonly {message: {id: string, attempt?: string | null},
 *   prepared: PreparedAuthoredMessage | null | undefined}[]} entries
 */
export function islandChange(entries) {
  /** @type {[string, PreparedAuthoredMessage | null, PreparedAuthoredMessage | null][]} */
  const changed = [];
  /** @type {string[]} */
  const retired = [];
  for (const { message, prepared = null } of entries) {
    const key = message.attempt ?? message.id;
    const prior = adoptedIslands.get(key) ?? null;
    if (prior === prepared) continue;
    changed.push([key, prior, prepared]);
    for (const id of prior?.descriptors.descriptors.keys() ?? [])
      if (!prepared?.descriptors.descriptors.has(id)) retired.push(id);
  }
  return {
    retired,
    commit() {
      for (const [key, prior, prepared] of changed) {
        for (const element of prior ? islandElements(prior) : [])
          if (keptElements.get(element.id)?.element === element)
            keptElements.delete(element.id);
        if (!prepared) {
          adoptedIslands.delete(key);
          continue;
        }
        adoptedIslands.set(key, prepared);
        for (const element of islandElements(prepared))
          if (!keptElements.has(element.id))
            keptElements.set(element.id, { element, document: prepared.body.document });
      }
    },
  };
}

/** @param {{id: string, attempt?: string, text?: string}} message @param {string} thread
 * @returns {Promise<PreparedAuthoredMessage>} */
export function prepareAuthoredMessage(message, thread) {
  const key = message.attempt ?? message.id;
  if (typeof thread !== "string" || !thread)
    throw new TypeError("an authored message needs its thread's id");
  const source = message.text ?? "";
  let islands = authoredMessages.get(key);
  if (!islands) authoredMessages.set(key, (islands = new Map()));
  let prepared = islands.get(source);
  if (!prepared) {
    // Captured once for each wording, so never from the escaped source the renderer
    // stands in with until it loads.
    if (!markdownReady())
      throw new Error("leaf: an authored message needs its loaded Markdown renderer");
    const markup = renderAuthoredMarkdown(source, pageLinks);
    const template = document.createElement("template");
    template.innerHTML = markup;
    // A page's media at the address the page answers at, as the message's Markdown
    // images take it (records/page-markdown.js, `pageLinks`): any attribute naming it.
    for (const element of template.content.querySelectorAll("*"))
      for (const { name, value } of element.attributes)
        if (isCanonicalMediaUrl(value))
          element.setAttribute(name, scopedMediaUrl(value));
    const elsewhere = heldElsewhere(template.content);
    markDeclared(template.content);
    rememberAuthoredParents(template.content);
    const descriptors = stageWidgetDescriptors(template.content, {
      kind: "thread",
      thread,
      message: message.id,
    });
    bindWidgetDescriptors(descriptors.bindings);
    const authored = stageAuthoredStates(template.content);
    rememberPassageParts(template.content);
    // The message's words as the page reading says them (`says`). `says` refuses text
    // with no element over it, and a message may open with bare text, so it reads a
    // copy inside a <div> of the template's inert document, where nothing upgrades.
    const body = template.content.ownerDocument.createElement("div");
    body.append(template.content.cloneNode(true));
    const text = says(body);
    const nodes = Object.freeze([...template.content.childNodes]);
    prepared = {
      message: message.id,
      body: {
        text,
        heldElsewhere: elsewhere,
        document: { thread, message: message.id },
      },
      authored,
      descriptors,
      nodes,
      root: template.content,
      preparation: null,
    };
    islands.set(source, prepared);
  }
  for (const descriptor of prepared.descriptors.descriptors.values())
    if (
      descriptor.document.kind !== "thread" ||
      descriptor.document.thread !== thread ||
      descriptor.document.message !== message.id
    )
      throw new TypeError("an authored message changed its document identity");
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
// The island of the wording a drawing shows, its Markdown (`messageReading`).
/** @param {{id: string, attempt?: string | null, markdown: string | null}} message */
const authoredMessage = (message) => {
  const prepared = authoredMessages
    .get(message.attempt ?? message.id)
    ?.get(message.markdown ?? "");
  if (!prepared)
    throw new Error("authored message presentation preceded semantic preparation");
  return prepared;
};

// Which drawing of an authored message holds its widgets, the one instance above. A
// message can stand in several drawings at once (the primary reader's, a margin card, a
// seat on the page, On Me's card), and the shown one of highest `authoredRank`
// (`HOLDS`) holds them, the first to draw it among equals. Every other drawing draws
// only the message's words: the holder is then the one shown, so the widgets already
// stand in view. A drawing shown as it draws takes them where it should hold them, as
// does the first to draw them, and after each draw the holder is settled again among
// the drawings shown, so one hidden in a fold or a closed card gives them to one in
// view. A drawing not yet placed in the page, as a card draws before its owner places
// it, is neither shown nor hidden: it waits for that settling to take them, and keeps
// what it holds. Whichever drawings gain or lose them draw again at once, as their own
// containers would not.
// Each drawing's `authoredRank`, highest first: the primary reader's view of the
// conversation, a margin card, a thread drawn in the page, and a drawing aside from the
// conversation, as On Me's cards are (primary-reader.js, `messagesAside`). A drawing
// aside holds the widgets only while no other drawing shows the message, so opening On
// Me takes no choice out of a thread the user sees, and no arrival lands in it
// (`authoredHolder`). Rejected: On Me's card ranking as the primary
// reader's view, so opening it empties a thread on the page of its widgets.
export const HOLDS = Object.freeze({ reader: 4, margin: 3, page: 2, aside: 1 });
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
// The drawn message holding the widgets of the message `id`, if a drawing holds them,
// where an arrival at the message lands (destination.js). None while a drawing aside
// holds them, since no thread opens there.
/** @param {string} id */
export function authoredHolder(id) {
  for (const view of authoredHolders.values())
    if (view.model.id === id && view.model.authoredRank !== HOLDS.aside && shown(view))
      return view.node;
  return null;
}
/** @param {MessageRecord} message
 * @param {{authoredRank?: number,
 * workflows: readonly import("../../../types/domain.js").Workflow[],
 * leaves?: {word: import("../../base/voice.js").Said, todo: string | null} | null}} options */
export function messageReading(
  message,
  { authoredRank = 0, workflows, leaves = null },
) {
  const workflow = strongestWorkflow(workflows);
  const kind = isReaction(message)
    ? "reaction"
    : deleted(message)
      ? "deleted"
      : message.suggestion
        ? "suggestion"
        : "prose";
  const authored = message.body.kind === "authored";
  const prose = kind === "prose" && !authored ? proseReading(message) : null;
  const removal = message.withdrawn ?? message.edited;
  return Object.freeze({
    key: messageKey(message),
    id: message.id,
    thread: message.thread,
    // A reply still streaming, which the answer it stands for completes in place.
    provisional: Boolean(message.provisional),
    // The agent's progress message (`ephemeral`): a step of work in hand, which the
    // thread shows as a face, not a message, until something ends it (transcript.js).
    progress: Boolean(message.ephemeral),
    // What an answer leaves standing, while it stands: Leaf's "Waiting on me" for the
    // question the user owes words to, the agent's On it or Still to do (`todoWord`) for
    // work it promised and has not ended (thread-card.js), with that to-do's id.
    leaves,
    version: message.content_version,
    // Original log order: edits move the words without moving where they were said.
    sequence: message.seq ?? Infinity,
    unread: message.unread,
    attempt: message.attempt ?? null,
    author: message.author,
    by: authorName(message),
    timestamp: message.ts,
    // What the message said before its last rewrite is the edited mark's to tell, or a
    // deleted message's, since answers above may have been about those words.
    edited: removal
      ? `${kind === "deleted" ? "Deleted" : "Edited"}${"ts" in removal ? ` ${ago(removal.ts)}` : ""}. Before, it said: “${removal.was}”`
      : null,
    editable: editable(message),
    failure: message.failure ?? null,
    pending: Boolean(workflow?.local) && workflow?.state !== "blocked",
    // What a rewrite of the message is written over (`base` on an edit): its current
    // content version.
    base: message.content_version,
    workflow,
    workflowWord: workflowWord(workflow, agentName()),
    workflowTitle: workflowTitle(workflow, agentName()),
    body: Object.freeze({
      kind,
      text: message.text ?? "",
      // An authored message's markup as a drawing that doesn't hold it draws it.
      html: authored ? (message.body.heldElsewhere ?? "") : (prose?.html ?? ""),
      mediaHtml: prose?.mediaHtml ?? "",
      plainText: authored
        ? message.body.text
        : (prose?.plainText ?? message.text ?? ""),
      drawing: Boolean(message.drawing),
      emoji: message.emoji ?? "",
      authored,
    }),
    // The message as its Copy control copies it: its Markdown as written, any HTML in
    // it included. A reaction has none.
    markdown: kind === "reaction" ? null : (message.text ?? ""),
    // Whether a link can name the message (`#linkControl`): one the log holds, which
    // a streaming reply and one this tab is still sending aren't.
    linkable: message.addressable !== false && !message.pending,
    // Where this drawing ranks among those that may hold the message's widgets
    // (`authoredHolders`); 0 for one that never does.
    authoredRank,
    reactions: message.reactions,
  });
}

/** @typedef {{read: Pick<ReturnType<typeof import("./read.js").createReadTracking>, "observeMessage">,
 * reply: {wireInput: import("../composition-input.js").WireInput,
 * actions: Pick<ReturnType<typeof import("./actions.js").createThreadActions>, "edit">},
 * reaction: ConstructorParameters<typeof ReactionStripView>[0],
 * edit: ReturnType<typeof import("./message-edit.js").threadRewrites>["edit"],
 * showTodo: (todo: string) => unknown}} MessageCommands */

// The tint a turn arrives in, a message or a step's face (transcript.js):
// one phase drives its ground and its sticky head (surfaces.css, `--lf-msg-arrival`).
// CSS resolves the tint and resting colour at the node after insertion; Firefox's Web
// Animations interpolates a var() colour keyframe discretely. The shared motion gate
// answers for restoration and reduced motion.
/** @param {Element} node */
export const arrivalTint = (node) =>
  motion(node, [{ "--lf-msg-arrival": 1, offset: 0 }], motionTime("--lf-motion-flash"));

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
  /** @type {ReturnType<typeof copyControl> | null} */
  #link = null;
  // Bumped each time this view takes the message's widgets back from another drawing.
  #authoredTake = 0;
  // The island this view last dressed (`prepareAuthoredMessage`'s `nodes`), which an
  // edit replaces.
  /** @type {readonly ChildNode[] | null} */
  #dressed = null;
  /** @type {ReturnType<typeof motion> | null} */
  #arrivalMotion = null;
  /** @type {(() => void) | null} */
  #stopRead = null;
  /** @type {MessageEditor | null} */
  #editor = null;
  #kept = false;
  /** @type {(() => void) | null} */
  #stopKept = null;
  /** @param {MessageCommands} commands */
  constructor(commands) {
    this.#commands = commands;
    this.node = document.createElement("div");
  }

  /** @param {ReturnType<typeof messageReading>} model
   * @param {{arrived?: boolean, headerControls?: unknown}} [options] */
  present(model, { arrived = false, headerControls = nothing } = {}) {
    const prior = this.#model;
    const presentation = (this.#presentation ??= {
      node: this.node,
      model,
      present: (reading) => this.present(reading),
    });
    presentation.model = model;
    // A view presents messages of one surface for its whole life, so what the surface
    // makes of the node is written once, on the first presentation.
    if (!prior) {
      this.node.classList.add("lf-msg");
      // Which message a node draws, for a presentation handing the user's place in a
      // thread to another, as the floating panel does to a page's own reader.
      this.node.dataset.lfMessage = model.key;
      this.node.classList.add("lf-ui");
      generatedElement(this.node);
      this.node.dataset.lfOffer = "";
      // A message the keyboard stands on previews when it was said, as its time does to
      // a pointer or a finger (`agePreview`), beside that time in its head. Its words
      // preview nothing to a pointer or a finger, since they are what the user reads.
      this.node.lfPreview = (route) => {
        const at = route === "focus" ? clockTime(this.#model?.timestamp) : "";
        return at
          ? {
              name: at,
              at: this.node.querySelector(
                ":scope > .lf-msg-head > .lf-msg-meta > time",
              ),
            }
          : null;
      };
      // A double click on the user's own words opens them for rewriting, as the word
      // under it would otherwise only be selected. The word it selected goes first: the
      // editor then sets its own caret, which clearing the selection after would take. A
      // link keeps its own double click, and a control its own presses.
      this.node.addEventListener("dblclick", (event) => {
        if (
          event.target instanceof Element &&
          (event.target.closest(".lf-msg-editor, .lf-msg-controls") ||
            worksInside(event.target, this.node))
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
      ? (this.#editor ??= new MessageEditor(model.id, {
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
          saved: () => this.#commands.edit.saved(this.node),
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
    keeps(this.node, "data-lf-author", model.author);
    keeps(this.node, "data-lf-event", model.id);
    this.node.classList.toggle("lf-unread", Boolean(model.unread));
    keeps(this.node, "data-lf-attempt", model.attempt || null);
    keeps(this.node, "aria-busy", model.pending ? "true" : null);
    keeps(this.node, "data-lf-failure", model.failure || null);
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
    const holds =
      model.body.authored && authoredHolders.get(authoredKey) === presentation;
    // Whether this drawing holds the message's widgets, for a surface whose own
    // controls give way to them, as On Me's card's choices do (floating-panel.css).
    keeps(this.node, "data-lf-holds", holds ? "" : null);
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
    // its reactions; every message the log holds its Copy link; and every message with
    // words its Copy, last.
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
    const link = model.linkable && !editor ? this.#linkControl() : nothing;
    const copy =
      model.markdown && !editor ? this.#copyControl(model.markdown) : nothing;
    const receipt = model.workflowWord
      ? html`<span
          class="lf-msg-sending"
          .lfPreview=${() =>
            model.workflowTitle ? { name: model.workflowTitle } : null}
          >${voiced(model.workflowWord)}</span
        >`
      : nothing;
    const header = html`
      <div class="lf-msg-head" data-lf-reflow="text">
        <b>${model.by}</b
        ><span class="lf-msg-meta"
          >${saidTime(model.timestamp)}${
            model.unread
              ? html`<span class="lf-msg-new lf-unread-dot"
                  ><span class="lf-quiet">New</span></span
                >`
              : nothing
          }
          ${receipt} ${this.#leavesWord(model.leaves)}
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
            model.edited && model.body.kind !== "deleted"
              ? html`<span
                  class="lf-edited"
                  .lfPreview=${() => ({ name: model.edited, about: this.node })}
                  >edited</span
                >`
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
          ><span class="lf-msg-controls">${rewrite}${react}${link}${copy}</span></span
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
          ${
            editor
              ? editor.node
              : holds
                ? html`<div class="lf-msg-text">
                    ${keyed(this.#authoredTake, authored)}
                  </div>`
                : this.#body(model.body, model.edited)
          }
          ${
            model.body.drawing
              ? html`<span class="lf-drawing-reference">Drawing comment</span>`
              : nothing
          }
        </div>
        ${strip}
      `,
      this.node,
    );
    if (model.body.authored && this.#dressed !== authored) {
      markDeclared(this.node);
      renderQuiet(this.node);
      this.#dressed = authored;
    }
    // Markdown is an opaque property part: tokenization and typesetting never rewrite
    // Lit markers.
    dressCode(this.node);
    // The drawing these widgets left draws the way here instead.
    displaced?.present(displaced.model);
    // The delivery receipt and busy cursor remain independent of the arrival tint.
    if (!prior && (model.pending || arrived))
      this.#arrivalMotion = arrivalTint(this.node);
    // Whether this message can be rewritten may have moved, which the reply box's ↑
    // reads (`threadRewrites`).
    messageDrawn();
    return this.node;
  }

  // Open the user's own words for rewriting here, with the caret after them; `walked`
  // where ↑ opened them (message-edit.js, `enter`). False where the message is not one
  // they may rewrite.
  /** @param {{walked?: boolean}} [options] */
  openEdit({ walked = false } = {}) {
    const model = this.#model;
    if (!model?.editable) return false;
    if (!this.#editor) {
      this.#commands.edit.opening(model, this);
      this.#commands.edit.paint(this.node);
    }
    this.#editor?.enter({ walked });
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

  // What an answer leaves standing, beside its time. A to-do's word opens On <agent> at
  // the to-do's row, its card open (panel/floating-panel.js, `showTodo`), since the row says
  // what the agent is doing about it and where it stands among the rest; its Discuss
  // leads back here. The word is underlined, as a link is (`data-lf-link`), in the
  // head's ink (`data-lf-hint`), and is a Tab stop, since only a promise still open
  // draws one. The user chose the press over keeping the word plain, and the underline
  // over a chevron after the word and over a symbol in its place, which hides the word
  // until hovered and means nothing readers already know.
  /** @param {ReturnType<typeof messageReading>["leaves"]} leaves */
  #leavesWord(leaves) {
    if (!leaves) return nothing;
    const { word, todo } = leaves;
    if (!todo) return html`<span class="lf-msg-leaves">${voiced(word)}</span>`;
    const opens = `Open in On ${agentName()}`;
    return html`<button
      type="button"
      ${offeredAction("inline", "lf-msg-leaves")}
      data-lf-hint=""
      data-lf-link=""
      aria-label=${`${word.text}, ${opens}`}
      .lfPreview=${() => ({ name: opens })}
      @click=${() => this.#commands.showTodo(todo)}
    >
      ${voiced(word)}
    </button>`;
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
    }
    if (this.#copy.value !== markdown) this.#copy.value = markdown;
    return this.#copy;
  }

  // Copy link stands before Copy and copies the link that opens the message's thread
  // on it (address.js, `messageLink`), the opening message's link being the thread's.
  // The link is read at the press, since the page's address changes while it shows.
  // Like Copy it is no Tab stop; `y` in the thread presses it (landing.js,
  // `message.link`).
  #linkControl() {
    if (!this.#link) {
      const link = copyControl("lf-msg-control lf-msg-link", {
        role: "symbol",
        action: "copy-link",
        label: "Copy link to message",
        success: "Link copied",
        error: "Unable to copy link",
      });
      link.tabIndex = -1;
      link.addEventListener(
        "click",
        () => {
          const model = this.#model;
          if (model) link.value = messageLink(model.id);
        },
        { capture: true },
      );
      this.#link = link;
    }
    return this.#link;
  }

  /** @param {ReturnType<typeof messageReading>["body"]} body @param {string | null} edited */
  #body(body, edited) {
    if (body.kind === "deleted")
      return html`<div
        class="lf-msg-text lf-msg-deleted"
        .lfPreview=${() => (edited ? { name: edited } : null)}
      >
        ${voiced(DELETED)}
      </div>`;
    if (body.kind === "reaction")
      return html`<div class="lf-msg-text">
        <span class="lf-react-said">${body.emoji}</span>
      </div>`;
    if (body.kind === "suggestion")
      return html`<div class="lf-msg-text" .textContent=${body.text}></div>`;
    return html`<div class="lf-msg-text" ${keptWords(body.html)}></div>
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
// placed in its message (annotations/anchor-placement.js), while the message is put away.
/** @param {string} id */
export function messageHolding(id) {
  const kept = keptElements.get(id);
  return kept ? { element: kept.element, ...kept.document } : null;
}

// The element an id names: the page's, else one a message keeps, drawn or not.
/** @param {string} id */
export const addressableAt = (id) =>
  elementById(id) ?? messageHolding(id)?.element ?? null;

// What a coordinate names besides any words it quotes: a design subject, a datum, a
// drawing's part or a section. A passage is named by its words alone.
/** @param {import("../../../types/domain.js").Anchor | null | undefined} anchor @param {string | null | undefined} about */
function coordinatePlace(anchor, about) {
  if (about === "design") {
    const addressable = anchor?.section ? addressableAt(anchor.section) : null;
    return addressable ? designName(addressable) : anchor?.section || "the page";
  }
  const datum = datumLabel(anchor);
  if (datum) return anchor?.quote ? datum : `§ ${datum}`;
  if (anchor?.quote || !anchor?.section) return "";
  const addressable = addressableAt(anchor.section);
  if (anchor.visual) {
    const part = visualPartLabel(addressable, anchor.visual) ?? anchor.visual;
    return `§ ${addressable ? `${addressableWord(addressable)} · ${part}` : `${anchor.section} · ${part}`}`;
  }
  return `§ ${addressable ? sectionLabel(addressable) : anchor.section}`;
}

// The words a thread is about, as its head quotes them: those a version's rewrite took
// from it (`rewritten_from`, events.md), else those it was detached from, else its
// anchor.
/** @param {Pick<import("../../../types/domain.js").Thread, "rewritten_from" | "detached_from" | "anchor">} thread */
export const threadPassage = (thread) =>
  thread.rewritten_from ?? thread.detached_from ?? thread.anchor;

// Where an anchor stands, apart from the words it quotes: "design · heading · t", or
// "" for a passage, which its words name alone. A named control part belongs to the
// place in every reading, not just Design.
/** @param {import("../../../types/domain.js").Anchor | null | undefined} anchor @param {string | null | undefined} [about] */
export const anchorPlace = (anchor, about) =>
  [about === "design" && "design", anchor?.part, coordinatePlace(anchor, about)]
    .filter(Boolean)
    .join(" · ");

// An anchor in running text, such as an accessible name or a feed's line: its place,
// then the words it quotes, which only the marks set off from the words around them. A
// surface that draws the two apart, as a thread's quote does (thread-card.js,
// `quoteReading`), reads `anchorPlace` and the quote instead.
/** @param {import("../../../types/domain.js").Anchor | null | undefined} anchor @param {string | null | undefined} [about] */
export const anchorLabel = (anchor, about) =>
  [anchorPlace(anchor, about), anchor?.quote && `“${anchor.quote}”`]
    .filter(Boolean)
    .join(" · ");
