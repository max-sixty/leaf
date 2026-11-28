/* One synchronous Lit owner for complete page, outlet and margin threads, and for the
   floating panel's view of a thread: every surface that draws a thread draws it here.

   Every surface uses the same metadata, transcript, message and reply vocabulary.
   Containers own navigation and placement, including whether their transcript scrolls;
   shadow.css owns the conversation's appearance through widget shadow boundaries.
   Conversation flow stays inside a content region, separate from the outer body's
   retained reply space, except where a container's head line stands in the thread
   (`CardOutlets`, `line`). Thread controls stay outside message and
   summary folds. MessageView owns each complete message, so no container extracts or
   reparents its header.
   Where the container gives no head line, independent controls stand on the first
   header line, in the room the line keeps at its end, and a held-news notice stands on
   the same line after the header's words, each a box of its own anchored to the
   header, so no box stands over the words. That line reserves a notice's minimum hit
   area from its first paint; the metadata edge measured before news arrives is
   retained while it waits, including when its workflow receipt goes.
   Each message header text item keeps its allocated width while news waits, so a later
   receipt grows only inside its own clipped box. The first notice may use spare
   room for its new receipt without moving the author or time already shown.

   Each container says where the parts of the thread it holds stand, and how a send and
   a settlement land there (`ViewOutlets`): the floating panel gives the notice and the
   settlement places on its view's head line, which stands outside the view that
   scrolls, and the reply box the row's field, and asks for the words the thread is
   about over its messages, since nothing beside it shows them; a margin card stands the
   notice and the settlement on its head line, which stands in the thread above its
   messages. The thread draws each of them there, so the panel's view and a card share
   one notice, one settlement and one reply box. Each head line holds the thread's
   title, which its container draws (`viewHeading`, messages.js), and in both each
   message's head scrolls with its words. The user chose the card's title line over
   the name of the message in view pinned on the line of the card's presses, so the
   card and the panel draw a thread one way and the card keeps no code to pin names.
   Partway through a long message its name is out of view, though its ground still
   says whose words they are (surfaces.css), and the line costs every card 33px.
   The passage the card points at already shows the words the thread is about, so the
   card draws no quote.

   Immutable descriptors contain generated presentation only. Retained native editors,
   a container's places and presses, and widgets in messages keep their mechanical
   lifetime outside those values. The card draws its messages as every reader of a
   whole thread does, folds and working message included (transcript.js), around them
   its head's controls and its reply box. The owner alone renders its native card root,
   the boxes it draws apart, and all generated descendants; a failed candidate is
   restored by presenting its committed descriptor again. It owns title gesture policy,
   outgoing fold paint and local draft repaint. Surfaces receive whole-thread geometry
   readings rather than descendant nodes. It decides nothing by the reading's surface,
   which read tracking reports (transcript.js) and which ranks where a message's
   authored widgets stand (`threadReading`).

   A container whose head line holds a place for it offers Next unread there, which
   goes to the thread's first reply not yet read, a fold or the scroller's edge perhaps
   hiding it, as `g u` goes to the page's (read.js). Whether this opening of the thread
   offers it is decided once the container has landed the opening and a pass of read
   tracking has read what it shows whole (`settled`): it does where a reply still stands
   unread. Once none is left the press is unoffered and its seat stands, so reading
   moves nothing beside it; a margin card draws nothing instead, since nothing on its
   line moves for the press (annotation-chrome.css). Until then, and where every reply
   showed whole, nothing stands there. Replies arriving later need none: New reply leads to one
   the user waits for, and the thread's notice to news it holds. Rejected: deciding as
   the view first drew, which offered Next unread for the moment before the opening read
   a short reply.

   A container whose box scrolls the thread's messages names that box (`ThreadOutlets`,
   `scroller`): the floating panel's view, a margin card's capped transcript. It owns
   the box and the edge it holds still, and says when the box stands at its size
   (`settled`). The agent's answer to the user's own last turn, work under way and a
   reply streaming included, may then have arrived past the box's foot. Where the user
   stood at the box's end and their turn and the answer together fit in the box, its end
   glides to follow the answer into sight, so the turns above slide up as it comes, as
   the user asked, rather than jumping up in one frame. Otherwise New reply stands at
   the box's foot until a press on it, or the user scrolling there, shows the answer, or
   they send another turn, and a user who stood at the end keeps their turn wholly in
   sight above the press, its head included. A user whose wheel or key has the box
   scrolling as the answer arrives stands wherever that scroll takes them, though the
   browser has yet to move the box (dom/arrivals.js, `readerScrolls`), or has moved it
   before the page heard the input, as it does for macOS's precise wheels. Until then
   the answer is this thread's to place (`answering`), and a box that follows its end,
   as a card's transcript does (thread-preview.js), leaves it be. An answer the end
   followed into sight that grows afterwards, as a picture in it loads, is placed again
   by the same rule (`placesEnd`). The user chose New reply for the panel, and the rest
   of the floating panel's growth with it (panel/floating-panel.js, which records it); the
   margin card takes it too, so one mechanism serves both, and that mechanism's rule at
   its end, under the user's request for one thread view (thread-preview.js).

   Two jumps stand over that box, presses that glide it to the messages' start or end
   (`#jumps`), each shown by its container's rules while some of the messages stand
   past its edge (surfaces.css), as chat apps float one at a conversation's foot. A
   press moves focus to the thread, as New reply's does, so it doesn't fall to the page
   as the press hides. Each is a mark standing as its own toolbar, the face a code
   block's Copy wears over its code (controls.css), since a jump stands over words as
   Copy does. A pin's lifted face read too heavy among the card's other presses, none
   of which is lifted. The user chose the jumps over a hairline across the card at each
   cut edge; over a bare chevron at the card's side, which looked unpolished to them;
   and over a column kept clear of words for the chevrons, which took its width from
   every message. */
import { nextRender, sizeObserver } from "../../lib/frame-pass.js";
import {
  holdFocus,
  focusDestination,
  focused,
  currentLocationIn,
} from "../../dom/focus.js";
import { effect, signal, untracked } from "/vendor/signals-core.js";
import { html, nothing, ref, render } from "/vendor/lit.js";
import { share } from "../../base/snapshot.js";
import { turns, threadKey } from "../../state/thread/model.js";
import {
  HOLDS,
  LISTED_NAME,
  anchorPlace,
  messageReading,
  threadName,
  threadPassage,
} from "./messages.js";
import { generatedElement } from "../../dom/widget-elements.js";
import { offeredAction } from "../../lib/controls.js";
import { measure } from "../../lib/shown-box.js";
import { keeps, keepsHidden, layoutPx } from "../../lib/keeps.js";
import { commandsOn } from "../../dom/keyboard/scopes.js";
import {
  createReplyView,
  replyIsEditing,
  dismissReply,
  threadHoldsDraft,
} from "./replies.js";
import {
  glideBy,
  glideTo,
  SCROLL_SLACK,
  scrollGoal,
  scrollLimit,
  scrollToEnd,
} from "../../dom/scrolling.js";
import { browserScrolls, readerScrolls } from "../../dom/arrivals.js";
import { scrollIntoView } from "../../readings/landing-scroll.js";
import { scrollAxes } from "../../dom/element-axes.js";
import { renderedOrder } from "../../lib/shadow-tree.js";
import { iconTemplate } from "../../lib/icons.js";
import { threadNamed } from "./state.js";
import { settleThread } from "./folding.js";
import { answeredInWords } from "../obligations/model.js";
import { SAY_BOX, wholeThread } from "./selectors.js";
import {
  threadAttention,
  inHand,
  todoWord,
  workflowWord,
  hasWorkflowLine,
} from "./workflow.js";
import {
  leafSays,
  voiced,
  wordsText,
  REOPEN_HINT,
  REPLY_HINT,
} from "../../base/voice.js";
import { agentName, documentChanged } from "../../state/semantic-state.js";
import { carried, growthIsSeen, shownRect } from "../../dom/geometry.js";
import { retainUserIntent } from "../../dom/user-intent.js";
import { scrollThreadIntoView, pinnedReply } from "./reply-landing.js";
import { threadRewrites } from "./message-edit.js";
import { authoredTitle } from "../../base/tab-title.js";
import { NEWS_ROOM, newsNotice, threadChange } from "./held-news.js";
import { ReplyContinuity } from "./reply-continuity.js";
import { Transcript } from "./transcript.js";
import { partTrail } from "./placement.js";
import { addressableLabel } from "../../readings/addressable-names.js";
import { quoteRepeats, standsIn } from "../../readings/anchor-resolution.js";
import { PRESS } from "../../lib/keys.js";
import { excerptWords } from "../../lib/words.js";
import type { Immutable } from "../../base/snapshot.js";
import type { Said } from "../../base/voice.js";
import type { ThreadPlacements } from "./placement.js";
import type { Workflow } from "../../../types/domain.js";
import type { NewsNotice, ThreadChange } from "./held-news.js";
import type { MessageCommands } from "./messages.js";
import type { ReplyCommands, ReplyOptions } from "./replies.js";
import type { createReadTracking } from "./read.js";
import type { Landing } from "./folding.js";
import type { Signal } from "/vendor/signals-core.js";
import type { readThreadRecords } from "../../state/thread/model.js";

export type ThreadRecord = Immutable<ReturnType<typeof readThreadRecords>[number]>;
export type MessageReading = ReturnType<typeof messageReading>;
export type WorkingMessage = {
  who: string;
  position: number;
  timestamp: string | null;
  words: string;
  feedback: {
    input_id?: string;
    reply_id: string | null;
    attempt?: string | null;
    reply_kind: "work" | "progress";
  } | null;
  live: boolean;
  condition: Said | null;
};
export type ThreadReading = {
  key: string;
  name: string;
  id: string;
  attempt: string | null;
  surface: string;
  resolved: boolean;
  attention: ReturnType<typeof threadAttention>;
  resolvedBy: string;
  settlement: { kind: "resolve" | "unresolve"; word: string; label: string };
  summaries: ThreadRecord["summaries"];
  messages: readonly MessageReading[];
  working: WorkingMessage | null;
  source: ThreadRecord;
  reread: (held: ThreadRecord) => ThreadReading;
};

// What a thread says of the words it is about: where they stand, the words, whether they
// still stand on the page, and a status word, in Leaf's voice, where the page no longer
// reads as the quote does: a revision took the words out of the latest version, which
// may not be the version shown, where they can still stand; they can't be found on the
// page; they come from earlier data; or they have changed, so the thread stands on what
// held them (`resolveAnchor`'s fallback for words it doesn't place once). Words the page
// shows more than once, with no context to pick a copy, have no status: they are on the
// page, and the thread stands on their section, or in Threads where it names none. A
// thread draws it where its container asks (`ThreadOutlets`, `quote`), as the floating
// panel's view does, and wherever the page leaves it unmarked (`unmarked`), since then
// no container's place beside the words shows them. The status is a word over the
// quote because a finger never reads a title.
// Where the words still stand, `trail` names the headings over them (`partTrail`), else
// the page's title, where no heading stands over them: a label of quoted words with no
// place of their own, and the head's title for any other.
function quoteReading(
  thread: ThreadRecord,
  anchors: Pick<ThreadPlacements, "placedAt">,
) {
  const quoted = threadPassage(thread);
  const place = anchorPlace(quoted, thread.root.about);
  const words = quoted?.quote ?? "";
  if (!place && !words) return null;
  const placement = anchors.placedAt(thread.id);
  const anchored = Boolean(thread.anchor) || Boolean(thread.detached_from);
  const detached = anchored && (Boolean(thread.detached_from) || placement == null);
  // A version that moved the thread off what it was about left it on its section
  // (`rewritten_from`, events.md), and words the page no longer shows stand on the
  // element that held them, their section or datum, rather than as a passage; the
  // head still names those words, marked as changed. Words standing in for a part their
  // widget hasn't drawn yet haven't.
  const repeated = placement?.kind !== "passage" && quoteRepeats(thread.anchor);
  const changed =
    Boolean(thread.rewritten_from) ||
    Boolean(
      words &&
      !repeated &&
      placement?.kind === "element" &&
      !standsIn(thread.anchor, placement),
    );
  const status = detached
    ? thread.detached_from
      ? leafSays("Not in the latest version")
      : repeated
        ? null
        : leafSays("Not found")
    : anchored && placement?.status === "outdated"
      ? leafSays("Earlier data")
      : changed
        ? leafSays("Changed")
        : null;
  return Object.freeze({
    place,
    words,
    detached,
    status,
    // Whether the page leaves what the thread is about unmarked where the thread
    // stands, so a container beside that place doesn't show it: a status says why, or
    // the words only fell back to a place around them, as a diff line not yet loaded
    // falls back to its file.
    unmarked: Boolean(status) || Boolean(words && !placement?.exact),
    // A surviving element can still be a destination after its quoted words
    // have gone (rewritten text, replaced data or a virtual datum). Only a
    // resolved passage can supply the original quote's complete reading.
    localReading: Boolean(words) && placement?.kind !== "passage",
    trail:
      !detached && placement?.place
        ? partTrail(placement.place)
            .map(addressableLabel)
            .filter(Boolean)
            .join(" › ") || authoredTitle()
        : "",
  });
}

// The thread's working message: what the agent is doing about the work it has in hand
// here, while no answer has come. Its words are the line the agent last gave for that
// work, which is the request's state (a start, `todos.py`), so they agree with the
// page's status and the agent's On count. The work is read from the thread's workflows
// and to-dos, not from whose turn the thread is, since the agent can be working on one
// message while an obligation in the same thread waits on the user. A message's work speaks before a to-do's, and
// a proactive progress message, which takes no request in hand, gives its own words.
// `live` while the work runs; work whose turn ended or went stale without an answer
// says so beside its last line. It stands where those words were said, at `position`,
// the original log position (`workingPlace`): as the face of the step there, or as a
// face of its own (transcript.js). An answer already streaming at the thread's end
// replaces the working message and the step before it.
const STOPPED = new Set(["stopped", "quiet", "interrupted"]);
// A step's face (transcript.js), the working message among them, standing for the work
// under way where a thread reads the answer to the user's turn (`#fitAnswer`); and the
// key each is drawn under there.
const WORKING = ".lf-thread-working";
const FACE = "face:";
// A first header's words, which a held-news notice stands after: everything it holds
// but the message's own controls at its end.
const words = (header: HTMLElement): HTMLElement[] => {
  const children: NodeListOf<HTMLElement> = header.querySelectorAll(
    ":scope > :not(.lf-msg-control-room)",
  );
  return [...children];
};
function workingMessage(
  thread: ThreadRecord,
  messages: readonly MessageReading[],
): WorkingMessage | null {
  if (thread.resolved || messages.at(-1)?.provisional) return null;
  const pending = messages.filter((message) => message.progress);
  const lastProgress = pending.at(-1);
  const workflows = thread.workflows;
  const running = workflows.find(inHand);
  const runningLine = running && hasWorkflowLine(running) ? running : null;
  const stopped = workflows.find(
    (workflow): workflow is Extract<Workflow, { detail: string }> =>
      workflow.state === "blocked" &&
      workflow.reason !== null &&
      STOPPED.has(workflow.reason) &&
      Boolean(workflow.detail),
  );
  // The line of the start on a to-do of the agent's on the thread: one running, else
  // one that stopped or went quiet, which keeps the line it last said.
  const todos = thread.obligations.filter((item) => item.source.kind === "todo");
  const todo = todos.find(inHand)?.line ?? null;
  const stoppedTodo =
    todos.find((item) => item.state === "blocked" && item.line) ?? null;
  type Step = {
    words: string;
    position: number;
    live: boolean;
    condition: Said | null;
    agent: string | null | undefined;
  };
  const progressStep: Step | null = lastProgress
    ? {
        words: lastProgress.body.plainText,
        position: lastProgress.sequence,
        live: Boolean(running),
        condition: null,
        agent: running?.agent,
      }
    : null;
  const step: Step | null = runningLine?.detail
    ? {
        words: runningLine.detail,
        position: runningLine.detail_seq,
        live: true,
        condition: null,
        agent: runningLine.agent,
      }
    : running
      ? progressStep
      : todo
        ? {
            words: todo.text,
            position: todo.seq,
            live: true,
            condition: null,
            agent: null,
          }
        : stopped
          ? {
              words: stopped.detail,
              position: stopped.detail_seq,
              live: false,
              condition: workflowWord(stopped, agentName()),
              agent: stopped.agent,
            }
          : stoppedTodo?.line
            ? {
                words: stoppedTodo.line.text,
                position: stoppedTodo.line.seq,
                live: false,
                condition: todoWord(stoppedTodo),
                agent: null,
              }
            : progressStep;
  if (!step || !step.words || (!pending.length && !step.live && !step.condition))
    return null;
  const { words, position, live, condition, agent } = step;
  const agentMessage = messages.findLast((message) => message.author === "agent");
  // A workflow's detail is explicit agent work text linked to its exact input. A
  // to-do's line can be user-authored, so it supplies no reply visibility evidence.
  const work = runningLine?.detail ? runningLine : !running && !todo ? stopped : null;
  const progress =
    !work && (running || (!todo && !stopped && !stoppedTodo)) ? pending.at(-1) : null;
  // Date the words being shown, rather than another message or the workflow's
  // liveness condition. A to-do line has no dated source in the thread reading.
  const timestamp = work?.ts ?? progress?.timestamp ?? null;
  const feedback: WorkingMessage["feedback"] = work?.input
    ? {
        input_id: work.input,
        reply_id: null,
        reply_kind: "work",
      }
    : progress
      ? {
          reply_id: progress.id,
          attempt: progress.attempt,
          reply_kind: "progress",
        }
      : null;
  return Object.freeze({
    who: work?.agent || progress?.by || agent || agentMessage?.by || "Agent",
    position,
    timestamp,
    words: words.trim().replace(/\.$/, ""),
    feedback,
    live,
    condition,
  });
}

export function threadReading(
  thread: ThreadRecord,
  surface: string,
  commands: { authoredRank?: number },
): ThreadReading {
  const resolved = Boolean(thread.resolved);
  // A settlement in flight has already flipped `resolved`, because what the page can
  // draw of a gesture stands in the turn that sends it. The control the user is left
  // looking at is therefore the opposite one, live at once: a press sends the opposite
  // settlement after the first, as the ledger orders them. A delivery status is not the
  // result, so there is no "Resolving…" state to name.
  const kind = resolved ? "unresolve" : "resolve";
  const word = resolved ? "Reopen" : "Resolve";
  const label = resolved ? word : "Resolve thread";
  const attention = threadAttention(thread, agentName());
  // An answer says what it leaves (a question, `--todo`); its head says so while that
  // stands: a question the user still owes words to, a to-do still open on the
  // thread, in the word every other surface gives that to-do (`todoWord`). The to-do
  // keeps the reply's id (`todos.todo_reading`), and its word opens the to-do's row in
  // On <agent> (messages.js).
  const asking = new Set(
    thread.obligations
      .filter((item) => item.next_actor === "user" && answeredInWords(item))
      .map((item) => item.message),
  );
  const openTodos = new Map(
    thread.obligations
      .filter((item) => item.source.kind === "todo" && item.state !== "done")
      .map((todo) => [todo.id, todo]),
  );
  const leaves = (message: ThreadRecord["msgs"][number]) => {
    if (asking.has(message.id)) return { word: leafSays("Waiting on me"), todo: null };
    const todo = message.todo ? openTodos.get(message.id) : undefined;
    return todo ? { word: todoWord(todo), todo: todo.id } : null;
  };
  // What ended a step comes from the server (`completed_by`), a provisional answer
  // included. A held reading keeps a step until the message that ended it is among the
  // messages shown; one its turn ended goes at once.
  const presented = new Set(thread.msgs.map(({ id }) => id));
  const messages = turns(thread)
    .filter(
      (message) =>
        message.completed_by === undefined ||
        (message.completed_by !== null && !presented.has(message.completed_by)),
    )
    .map((message) =>
      messageReading(message, {
        // Where a message's widgets stand when several drawings show it (messages.js,
        // `HOLDS`).
        authoredRank:
          commands.authoredRank ?? (surface === "margin" ? HOLDS.margin : HOLDS.page),
        workflows: message.workflows,
        leaves: leaves(message),
      }),
    );
  return Object.freeze({
    key: threadKey(thread),
    name: threadName(thread),
    id: thread.id,
    attempt: thread.root.attempt ?? null,
    surface,
    resolved,
    attention,
    // Where a resolved thread stands already says it is resolved: in a seat's Resolved
    // disclosure (inline.js). Who resolved it is said only where it was the agent, in
    // Reopen's name and the words the panel's field says for the thread, which a finger
    // reads where it never reads that name.
    resolvedBy:
      thread.resolved?.author === "agent" ? `Resolved by ${thread.resolved.agent}` : "",
    settlement: Object.freeze({
      kind,
      word,
      label,
    }),
    summaries: Object.freeze(thread.summaries),
    messages: Object.freeze(messages),
    working: workingMessage(thread, messages),
    // The thread this reads, and the same reading of another state of it: the one a
    // seat holding news draws, the thread as it drew it (held-news.js).
    source: thread,
    reread: (held) => threadReading(held, surface, commands),
  });
}

export type ThreadViewModel = Omit<ThreadReading, "settlement"> & {
  settlement: ThreadReading["settlement"] | null;
  news?: NewsNotice | null;
};

// The user's last turn in a thread, by its key, as threadChange reads it (held-news.js).
const lastTurn = (model: ThreadViewModel) =>
  model.messages.findLast((message) => message.author === "user" && !message.progress)
    ?.key;

export type ThreadCommands = Omit<MessageCommands, "reply" | "reaction" | "edit"> & {
  authoredRank?: number;
  reply: ReplyCommands & MessageCommands["reply"];
  read: Pick<
    ReturnType<typeof createReadTracking>,
    | "observeMessage"
    | "observeFeedback"
    | "observeSummary"
    | "firstUnread"
    | "afterPass"
  >;
  reaction: Omit<MessageCommands["reaction"], "pressed">;
  settlement: Omit<
    Parameters<typeof settleThread>[0],
    "parent" | "key" | "resolved" | "prepareLanding"
  >;
  placedAt: Parameters<typeof quoteReading>[1]["placedAt"];
  landInThread: ReplyCommands["landInThread"];
};

/* Where a container stands the thread's parts, and what it asks the thread to draw and
   do (the header), each optional. Any container gives these, a package's included
   (module-annotations.md, "Owning the primary conversation presentation"):
   - `head`, the places on the container's own head line, outside the thread, for the
     held-news notice and the settlement, which otherwise stand beside the first
     message's head, and for Next unread, which it draws only where a place is named.
   - `reply`, the place for the reply box (`outlet`), which otherwise closes the thread,
     and what its empty box reads and how a send lands (`options`, replies.js,
     `createReplyView`).
   - `quote`, whether the thread draws the words it is about over its messages while
     the page still reads as the quote does; a container standing beside the words, as
     a margin card does by its bracket, shows them by where it stands. Where the page
     leaves them unmarked, as once a revision rewrote the quoted words and left the
     thread on their section, every thread draws them (`quoteReading`, `unmarked`).
   - `scroller`, given the thread's transcript, the box that scrolls its messages, at
     whose foot it says New reply (the header); without one it says none.
   - `landing(resolved)`, given whether the thread stood resolved as the press came, the
     step that takes the user where Resolve or Reopen leaves them, or null for the
     thread's own: Reopen in its reply box, Resolve where the user stands (folding.js,
     `settleThread`).
   Only the margin card says the rest (`CardOutlets`): `line`, its head line, which it
   arranges around the boxes the thread draws its notice and settlement in, and which
   the thread stands first, above its messages (annotation-chrome.css);
   `endNewsMoves()`, whether news at the thread's end, which grows the
   floating card away from the line it keeps, would move what the user is on
   (thread-preview.js, `keptLine`), and since the card stands itself, a landing in it
   scrolls nothing into view; and `standsAtEnd()`, whether the reader stands at the end
   the card's transcript follows, as its keeper says (dom/scrolling.js, `followEnd`).
   The thread draws each part apart in a box of its own (`apart`), which the container
   places in the place it names before the thread draws it, as it places the thread's
   box in its outlet. The reply's options are read as the box is made, once for the
   view. What the box's empty words say reads the thread as the thread draws it
   (`DrawnThread`), held news included, so they agree with its settlement and notice, as
   a card's own words do (`#createReply`). */
/** The thread as a thread draws it, held news included, which its reply box's words
 * read: whether it is resolved and by which agent, and whose turn it is (workflow.js,
 * `threadAttention`). */
export type DrawnThread = Pick<ThreadReading, "resolved" | "resolvedBy" | "attention">;
export type ThreadReplyOptions = Omit<
  ReplyOptions,
  "hint" | "hintParts" | "hintLead"
> & {
  hint?: (drawn: DrawnThread) => string;
  hintParts?: (drawn: DrawnThread) => unknown;
  hintLead?: (drawn: DrawnThread) => unknown;
};
export type ThreadOutlets = {
  head?: { news: HTMLElement; controls: HTMLElement; unread?: HTMLElement };
  reply?: { outlet?: HTMLElement; options?: ThreadReplyOptions };
  quote?: boolean;
  scroller?: (transcript: HTMLElement) => HTMLElement | null;
  landing?: (resolved: boolean) => Landing | null;
};
type CardOutlets = {
  line?: (apart: ThreadView["apart"]) => HTMLElement;
  endNewsMoves?: () => boolean;
  standsAtEnd?: () => boolean;
};
export type ViewOutlets = ThreadOutlets & CardOutlets;

// A box a thread draws a part in where its container stands the part apart: it lays
// out as what it holds (surfaces.css) and, as the thread's own box is, is Leaf's.
const apartBox = () => {
  const box = document.createElement("div");
  box.className = "lf-thread-apart lf-ui";
  box.dataset.lfRuntime = ""; // readings/passages.js, leafSurface
  generatedElement(box);
  return box;
};

// How many views this document has drawn, which names each view's quote for its Full
// quote press (`#quoteId`). One thread can stand in two views at once, a margin card and
// the panel's view, so the name counts views rather than naming the thread, and a load
// that draws the same views in the same order gives them the same names.
let drawnViews = 0;

export class ThreadView {
  declare node: HTMLDivElement;

  #commands;
  #messageCommands;
  #rewrites;
  // The model this card shows. Commands follow it explicitly; mechanical reads of
  // this paint's output must not subscribe the presenter that writes it.
  #shown: Signal<ThreadViewModel>;
  get #model() {
    return this.#shown.peek();
  }
  set #model(model) {
    this.#shown.value = model;
  }
  #transcript;
  #reply: ReturnType<typeof createReplyView> | null = null;
  // What a thread in the page's flow holds back says so in its control row (held-news.js).
  #news = newsNotice();
  #continuity;
  #received: ThreadViewModel | null = null;
  #headerSlot: {
    header: HTMLElement;
    items: { node: HTMLElement; width: number }[];
    boxWidth: number;
    held: boolean;
  } | null = null;
  #observedHeader: Element | null = null;
  #sizes = sizeObserver(() => this.#retainHeaderSlot());
  #outlets: ViewOutlets = {};
  // The boxes of the parts it draws where its container stands them (`ThreadOutlets`).
  #apart = Object.freeze({
    news: apartBox(),
    controls: apartBox(),
    reply: apartBox(),
    unread: apartBox(),
  });
  get apart() {
    return this.#apart;
  }
  // The words the thread is about, ahead of its messages (`#drawQuote`).
  #quoteHead = Object.assign(document.createElement("header"), {
    className: "lf-thread-quote-head",
  });
  #quoteId = `lf-thread-quote-${++drawnViews}`;
  #quoteExpanded = signal(false);
  // Whether three lines cut the quote, which its label then opens (`#fitQuote`).
  #quoteCut = signal(false);
  #quoteEffect: (() => void) | null = null;
  // The answer to the user's last turn drawn since the container last stood the thread
  // at its size, and how the box that scrolls it stood before (`#fitAnswer`).
  #unfitted: {
    answer: NonNullable<ThreadChange["answers"]>;
    before: { extent: number; limit: number };
  } | null = null;
  // The answer the box's end last followed into sight, while it answers the user's last
  // turn (`placesEnd`).
  #followed: NonNullable<ThreadChange["answers"]> | null = null;
  // The answer waiting past that box's foot behind New reply, by its first message or
  // the face of the step that stands for it.
  #waiting: { message: string; label: string; scroller: HTMLElement } | null = null;
  // Whether this opening offers Next unread, and whether that has been asked (header).
  #unreadSeat = false;
  #unreadAsked = false;
  // The label opens the quote only where three lines cut the words. Once the quote
  // stands, a change of its size resizes the view its container's observers watch, so
  // the press follows in the next frame rather than inside this observer's delivery.
  #quoteSize = sizeObserver(() => nextRender(() => this.#fitQuote()));

  constructor(commands: ThreadCommands, model: ThreadViewModel) {
    this.#shown = signal(model);
    this.#commands = commands;
    // A rewrite of one of the user's messages (`message-edit.js`). Opening or closing
    // it paints at once, and its editor takes or gives back the focus in the same press,
    // so the paint hands no one on (`#paint`).
    this.#rewrites = threadRewrites({
      views: () => this.#transcript.views,
      paint: () => this.repaint({ placing: true }),
      // Its reply box where it stands, in the thread or where its container stands it.
      box: () => this.#reply?.input ?? null,
      home: () => this.node,
      // Opening a rewrite shows what the thread holds (held-news.js), and unfolds a
      // summary holding the message, since it opens to be seen.
      opening: (id) => {
        this.#showNews();
        this.#transcript.expandAround(id);
      },
      landInThread: commands.reply.landInThread,
      landSent: commands.reply.landSent,
    });
    // A press on a reply's reactions is the user acting in this thread, so what the
    // thread holds shows with it (held-news.js).
    this.#messageCommands = {
      ...commands,
      reaction: { ...commands.reaction, pressed: () => this.#showNews() },
      edit: this.#rewrites.edit,
    };
    this.node = document.createElement("div");
    this.#transcript = new Transcript({
      commands,
      messageCommands: this.#messageCommands,
      repaint: () => this.repaint(),
      home: () => this.node,
    });
    this.#continuity = new ReplyContinuity(this.node);
    this.node.tabIndex = -1;
    this.node.classList.add("lf-page-thread", "lf-ring-overlay", "lf-ui");
    this.node.dataset.lfRuntime = ""; // readings/passages.js, leafSurface
    generatedElement(this.node);
    this.node.dataset.lfOffer = "";
  }

  // What the container asks of the thread and where it stands its parts
  // (`ViewOutlets`), given before each presentation.
  setOutlets(outlets: ViewOutlets) {
    this.#outlets = outlets;
  }

  get model() {
    return this.#model;
  }

  // Local disclosure and draft changes repaint the complete received descriptor,
  // never feed a held presentation back into the news owner's input; `placing` where
  // the caller puts the user where they go itself.
  repaint({ placing = false }: { placing?: boolean } = {}) {
    if (this.#received) this.#paint(this.#received, {}, false, placing);
  }

  // The seat owns placement, including while the card's outgoing pixels still fold
  // outside its Resolved disclosure. Landing and held news read that same placement.
  #foldedInto: HTMLDetailsElement | null = null;
  #retirement: Promise<unknown> | null = null;
  setFoldedInto(
    group: HTMLDetailsElement | null,
    retirement: Promise<unknown> | null = null,
  ) {
    this.#foldedInto = group;
    this.#retirement = retirement;
  }
  get transcript() {
    return this.#transcript.node;
  }

  get #fold() {
    return this.#foldedInto && !this.#foldedInto.open ? this.#foldedInto : null;
  }

  // The last of the thread a reader can see, after which its news grows: the last
  // node its transcript shows (transcript.js, `foot`), and none while the thread is
  // folded. A card folded in its seat's Resolved disclosure draws nothing at all.
  get #foot() {
    return this.#fold ? null : this.#transcript.foot;
  }

  // What the thread draws after its messages that its settlement swaps: the reply box
  // while it stands open; none while the thread is folded, where it does not show. A
  // resolved card's Reopen stands where Resolve did, so settling grows nothing else.
  get #settlementRow() {
    if (this.#fold) return null;
    return this.node.querySelector(":scope > .lf-thread-reply");
  }

  ownsMessage(id: string) {
    return (
      this.#model.id === id || this.#model.messages.some((message) => message.id === id)
    );
  }

  // HeldNews compares readings; this owner decides whether their changed regions
  // would move visible words. Existing-message changes retain the hold. A pinned reply
  // can absorb growth at the thread's end, but cannot absorb changes above it or
  // settlement replacing the reply itself.
  newsMoves({ news, changed, folds, appendedAtEnd, footFold }: ThreadChange) {
    // Folded in its seat's closed Resolved disclosure, the card moves nothing as it
    // changes, and draws at once whatever its settlement does to the seat.
    if (this.#fold) return false;
    const pinned = pinnedReply(this.#reply?.node);
    // A floating card grows at one of its own edges: the one it does not hold
    // (`CardOutlets`, `endNewsMoves`; thread-preview.js, `keptLine`). That edge is the
    // card's alone, since it stands itself rather than in a flow its growth moves, so
    // no place its parts stand in says it.
    // News shows at once only where it changes the thread's end and the card says growth
    // there moves nothing the user is on (`endNewsMoves`). A change to the last message
    // is such news where it is a reply still streaming, or where the transcript, at its
    // cap, follows it there, as its keeper does for a reader it says stands at the end
    // (`CardOutlets`, `standsAtEnd`). The transcript's offset doesn't say that: a turn
    // that grew in this task, as its picture loaded, has carried the end past the
    // reader before the keeper's next reading takes them there. Anything else
    // would move the messages being read, so it waits. A settlement keeps the editor it
    // interrupts, as every thread keeps its reply box.
    const { endNewsMoves, standsAtEnd } = this.#outlets;
    if (endNewsMoves) {
      if (news.settled) return false;
      const last = this.#model.messages.at(-1);
      const list = this.#transcript.node;
      const follows =
        list.scrollHeight > list.clientHeight + 0.5 && Boolean(standsAtEnd?.());
      const atEnd =
        (!news.appended || appendedAtEnd) &&
        !news.summaries &&
        [...changed].every(
          (key) => key === last?.key && (last.provisional || follows),
        ) &&
        // An answer ending the step at the thread's end changes only the thread's
        // foot, as the answer's arrival does.
        (footFold || (!folds.messages.length && !folds.summaries.length));
      return growthIsSeen(this.node) && (!atEnd || endNewsMoves());
    }
    const followed = pinned && !news.settled ? this.#foot : null;
    return (
      this.#transcript.newsMoves({ news, changed, folds, footFold }, { followed }) ||
      Boolean(news.settled && this.#settlementRow && growthIsSeen(this.#settlementRow))
    );
  }

  // What a card draws from beyond its reading: whether a reply to it is being written
  // and whether it holds a draft.
  #outside(model: ThreadViewModel) {
    return [
      replyIsEditing(model.key),
      threadHoldsDraft(
        model.key,
        model.messages.map(({ id }) => id),
      ),
    ];
  }

  // Whether `model` is the reading this card last drew, outside inputs included, so a
  // pass that hands it over again need not draw it. The reading is rebuilt on every
  // pass, so it is compared by content; its `reread` is a fresh closure over the same
  // reading each time.
  shows(model: ThreadViewModel) {
    const prior = this.#received;
    const drawnWith = this.#drawnWith;
    if (!prior || !drawnWith) return false;
    // A card holding news draws on every pass: what it shows then moves with time and
    // the reader, not with its reading.
    if (this.#model.news) return false;
    const { reread: _priorReread, ...was } = prior;
    const { reread: _reread, ...now } = model;
    const outside = this.#outside(model);
    return (
      share(was, now) === was &&
      outside.every((part, index) => part === drawnWith[index])
    );
  }

  #drawnWith: (boolean | null)[] | null = null;

  present(model: ThreadViewModel, options = {}) {
    return this.#paint(model, options, true);
  }

  // The caller knows whether this is a publication or a local repaint. Only a
  // publication allocates passive space; disclosures and editors stay intrinsic.
  #paint(model: ThreadViewModel, _options = {}, published = false, placing = false) {
    const prior = this.#received ? this.#model : null;
    this.#received = model;
    this.#drawnWith = this.#outside(model);
    // Where the container stands the thread's parts (`ViewOutlets`).
    const { head, line, reply, scroller } = this.#outlets;
    // A margin card's head line, arranged around the boxes the notice and the
    // settlement stand in before they are drawn (`CardOutlets`, `line`).
    const inLine = line?.(this.#apart) ?? null;
    // Whether the container gives the thread a head line, outside it or in it.
    const lined = Boolean(head || inLine);
    const replyApart = Boolean(reply?.outlet);
    // Capture the current words only when news starts waiting, before its update
    // removes a receipt. This allocation lives with the held view, not its reading.
    if (!lined && model.news && !prior?.news)
      this.#retainHeaderSlot({ observe: false });
    // The rewrites the user has open, and the messages leaving, change their own room.
    const bodyPlace = published
      ? this.#continuity.before([
          ...this.#transcript.views
            .filter((view) => view.editing)
            .map(({ node }) => node),
          ...this.#transcript.leaving(model),
        ])
      : null;
    const restoreFocus = placing ? null : holdFocus(this.node);
    this.#model = model;
    const change = prior && scroller ? threadChange(prior, model) : null;
    const box = scroller?.(this.#transcript.node) ?? null;
    if (this.#followed && lastTurn(model) !== this.#followed.turn)
      this.#followed = null;
    if (change?.answers && box)
      this.#unfitted = {
        answer: change.answers,
        before: this.#unfitted?.before ?? {
          extent: box.scrollHeight,
          limit: scrollLimit(box),
        },
      };
    // Whether the box holds New reply at its foot, which a fade there leaves whole.
    if (box) keeps(box, "data-lf-awaits", this.#waiting ? "" : null);
    // Where the notice and the settlement stand:
    // - where the container gives the thread a head line, in their boxes on it, with
    //   the thread's facts after its title: in the floating panel's view, and before a
    //   margin card's Previous and Next (the user's choices, 16 October).
    // - elsewhere, the head's controls row, which reserves the room of one icon control
    //   (shadow.css, `--lf-thread-action-room`) beside the first message's own
    //   controls, and the notice beside the first message's head. A foot row of its own
    //   drew resolved threads unlike open ones.
    const notice = this.#news;
    if (model.news) notice.set(model.news);
    const news = model.news ? notice.node : nothing;
    // Its id names the surface too (`drawnThreadId`).
    keeps(this.node, "data-lf-thread", model.id);
    keeps(this.node, "data-lf-resolved", model.resolved);
    keeps(this.node, "data-lf-attempt", model.attempt || null);
    // A card is itself where a send or a walk stands the user, so it carries the
    // thread's name, cut short: an untitled thread's name is its first message, which
    // the card reads next, and said whole in the name it was heard twice.
    keeps(this.node, "role", "group");
    keeps(this.node, "aria-label", `Thread, ${excerptWords(model.name, LISTED_NAME)}`);
    // A thread whose reply stands elsewhere ends with its messages, so it grows only at
    // its foot, the growing tail of the region holding it, as the panel's view is
    // (tests/shift_watch.js).
    keeps(this.node, "data-lf-append-tail", replyApart ? "" : null);
    const settlement = model.settlement
      ? this.#settlement(model, model.settlement)
      : nothing;
    this.#transcript.present(model, {
      arrived: Boolean(prior),
      awaited: this.#newReply(),
    });
    this.#reply ??= this.#createReply(model);
    // Beside the first header the notice is a box of its own on that header's line,
    // anchored to the header beside the controls' box at its end (surfaces.css,
    // `.lf-thread-content > .lf-thread-news`); its words change in place.
    keeps(notice.node, "data-lf-reflow", lined ? null : "text");
    const [toStart, toEnd] = this.#jumps();
    const body = html`
      ${inLine ?? nothing}${toStart}${this.#drawQuote()}${this.#transcript.node}${toEnd}
      ${
        !lined && (model.settlement || model.news)
          ? html`${news}
              <div class="lf-thread-controls" data-lf-reflow="text">
                <span class="lf-thread-meta-actions">${settlement}</span>
              </div>`
          : nothing
      }
    `;
    // A head line standing in the thread stands over its messages in the card's grid
    // (annotation-chrome.css), so the two stand as the thread's own children rather
    // than in a content region.
    render(
      html`
        ${inLine ? body : html`<div class="lf-thread-content">${body}</div>`}
        ${this.#continuity.gap} ${replyApart ? nothing : this.#reply.node}
      `,
      this.node,
    );
    render(lined ? news : nothing, this.#apart.news);
    render(lined ? settlement : nothing, this.#apart.controls);
    render(lined ? this.#nextUnread() : nothing, this.#apart.unread);
    render(replyApart ? this.#reply.node : nothing, this.#apart.reply);
    // The label's press stands from the quote's first paint, in the label's own line,
    // so its arrival moves nothing; later changes of the quote's size follow by its
    // observer (`#quoteSize`).
    if (!this.#quoteHead.hidden) measure(this.#quoteHead, () => this.#fitQuote());
    if (!lined && model.news) measure(this.node, () => this.#retainHeaderSlot());
    else this.#releaseHeaderSlot();
    this.#continuity.after(bodyPlace);
    // A page thread whose render took the user's place puts them in its reply, or on
    // the thread itself.
    // Handing it on is the card's own act, which the list holding the card defers to.
    // A thread whose container stands its reply apart lands no one there: as one
    // rewrite gives way to the next, a landing in the panel's field would let go of the
    // height its view holds for a rewrite and take it again in the same press
    // (panel/floating-panel.js, `holdThread`).
    restoreFocus?.(
      ...(replyApart
        ? []
        : [
            () =>
              this.#commands.landInThread(
                this.node.querySelector(SAY_BOX) ?? this.node,
              ),
          ]),
    );
    return this.node;
  }

  // Whether an answer to the user's turn is the thread's to place: one not yet fitted,
  // or one New reply stands for (the header).
  get answering() {
    return Boolean(this.#unfitted || this.#waiting);
  }

  // A box following its end asks this as the end moves, with how the box stood before
  // the move: whether the thread places that end itself. It does while an answer to the
  // user's turn is its to place (`answering`), and again once an answer the end followed
  // into sight grows, as when a picture in it loads, since the same rule decides whether
  // the end follows that growth or New reply stands for it (`#fitAnswer`). A move that
  // only changes the box's room, as a reply being typed does, is the box's.
  placesEnd(before: { extent: number; limit: number }) {
    if (this.answering) return true;
    const answer = this.#followed;
    const scroller = this.#outlets.scroller?.(this.#transcript.node);
    if (!answer || !scroller || scroller.scrollHeight <= before.extent + 0.5)
      return false;
    this.#followed = null;
    this.#unfitted = { answer, before };
    this.#fitAnswer();
    return true;
  }

  // The container has stood the thread where it draws it: its scroller at its size, and
  // a new opening landed where it shows first. What the thread reads of them waits for
  // this (the header).
  settled() {
    this.#fitAnswer();
    const { head, line } = this.#outlets;
    if (this.#unreadAsked || (!head?.unread && !line)) return;
    this.#unreadAsked = true;
    this.#commands.read.afterPass(() => {
      if (!this.#received) return;
      this.#unreadSeat = (threadNamed(this.#model.key)?.unread.length ?? 0) > 0;
      if (this.#unreadSeat) this.repaint();
    });
  }

  #nextUnread() {
    if (!this.#unreadSeat) return nothing;
    const { key } = this.#model;
    const left = (threadNamed(key)?.unread.length ?? 0) > 0;
    return html`<button
      type="button"
      ${offeredAction("inline", "lf-next-unread")}
      ?disabled=${!left}
      ?data-lf-unoffered=${!left}
      @click=${() => void this.#commands.read.firstUnread(key)}
    >
      ${iconTemplate("down", "lf-action-icon")}Next unread
    </button>`;
  }

  // The jumps to the start and the end of the messages, where a box scrolls them (the
  // header). The start's comes before the quote and the transcript in the thread's body
  // and the end's after them, so in a box that scrolls the whole thread, the start's
  // sticks from the box's first scroll.
  #jumps() {
    if (!this.#outlets.scroller) return [nothing, nothing];
    return (
      [
        ["start", "first-message"],
        ["end", "latest-message"],
      ] as const
    ).map(
      ([to, action]) =>
        html`<button
          type="button"
          ${offeredAction("mark", "lf-thread-jump", undefined, { action })}
          data-lf-bar
          data-lf-jump=${to}
          @click=${() => this.#jump(to)}
        ></button>`,
    );
  }

  #jump(to: "start" | "end") {
    const box = this.#outlets.scroller?.(this.#transcript.node);
    if (!box) return;
    focusDestination(wholeThread(this.node), "move");
    if (to === "end") scrollToEnd(box, "smooth");
    else glideTo(box, 0);
  }

  // New reply, at the transcript's end, which sticks at the foot of the box scrolling it.
  #newReply() {
    const waiting = this.#waiting;
    if (!waiting) return nothing;
    return html`<div class="lf-awaited">
      <button
        type="button"
        ${offeredAction("inline", "lf-new-reply")}
        data-lf-news
        @click=${this.#showAnswer}
      >
        ${iconTemplate("down", "lf-action-icon")}${waiting.label}
      </button>
    </div>`;
  }

  #answerNode(key: string) {
    return key.startsWith(FACE)
      ? this.#transcript.node.querySelector(
          `${WORKING}[data-lf-face="${CSS.escape(key.slice(FACE.length))}"]`,
        )
      : this.#transcript.messageNode(key);
  }

  // Read where the box stands at its size, after layout and before the frame is shown.
  #fitAnswer() {
    const unfitted = this.#unfitted;
    this.#unfitted = null;
    const scroller = this.#outlets.scroller?.(this.#transcript.node);
    if (!unfitted || !scroller) return;
    const { answer, before } = unfitted;
    const turn = this.#transcript.messageNode(answer.turn);
    if (!turn) return;
    const working: NodeListOf<HTMLElement> =
      this.#transcript.node.querySelectorAll(WORKING);
    const work = [...working].find((node) => renderedOrder(turn, node) < 0);
    const message = answer.reply ?? (work ? FACE + work.dataset.lfFace : null);
    if (!message) return;
    const waiting = this.#waiting;
    // An answer folding the work before it into less room moves nothing either, though
    // it takes over a New message the work left waiting. Its later growth is placed again
    // too, as a followed answer's is (`placesEnd`).
    if (!waiting && scroller.scrollHeight <= before.extent + 0.5) {
      this.#followed = answer;
      return;
    }
    // A reader whose wheel or key has the box scrolling stands where it takes them
    // (header), though the box hasn't moved yet: the browser applies that scroll a frame
    // or more after the input, and a write of the box meanwhile cancels it. The delayed
    // write below asks again, for an input made since, and stands back where the box no
    // longer stands where this read it: the browser can apply a wheel's scroll before the
    // page hears the wheel or the scroll, as it does for macOS's precise wheels.
    // A glide this placement set going toward the end, which a growth arriving before
    // it lands finds under way, still stands the user there: where the box stands is
    // where it is headed (`scrollGoal`).
    const stood = scrollGoal(scroller);
    const atEnd = !readerScrolls(scroller) && before.limit - stood <= SCROLL_SLACK;
    const pad = Number.parseFloat(getComputedStyle(scroller).paddingTop);
    const from = () =>
      turn.getBoundingClientRect().top - scroller.getBoundingClientRect().top - pad;
    if (
      !waiting &&
      atEnd &&
      scroller.scrollHeight - scroller.scrollTop - from() <= scroller.clientHeight
    ) {
      scrollToEnd(scroller, "smooth");
      this.#followed = answer;
      return;
    }
    const next = {
      message,
      label: answer.reply ? "New reply" : "New message",
      scroller,
    };
    if (waiting?.message === next.message) return;
    this.#stopWaiting();
    this.#waiting = next;
    scroller.addEventListener("scroll", this.#sawAnswer, { passive: true });
    // New reply joins the box, whose children other observers watch, so it is drawn in
    // the next frame, after the transcript is drawn.
    nextRender(() => {
      if (this.#waiting !== next) return;
      this.repaint();
      if (
        waiting ||
        !atEnd ||
        !turn.isConnected ||
        readerScrolls(scroller) ||
        scrollGoal(scroller) !== stood
      )
        return;
      // The user's turn stands wholly in sight, between the box's top edge and New
      // reply's ground, its head first where it is taller than that, read where the
      // box is headed, New reply stuck at its foot, through the box's transforms. The
      // box glides there, as it glides to the end, and reads the turn again at each
      // frame (dom/scrolling.js, `glideBy`), so a transcript that changes above the turn
      // meanwhile still leaves it in sight.
      glideBy(scroller, () => {
        if (!turn.isConnected) return null;
        const scale = scrollAxes(scroller).y.y;
        const foot = this.node.querySelector(".lf-awaited")?.getBoundingClientRect();
        const below = foot ? turn.getBoundingClientRect().bottom - foot.top : 0;
        return scale
          ? carried(turn, scroller, Math.min(Math.max(below, 0), from()) / scale)
          : 0;
      });
    });
  }

  #stopWaiting() {
    this.#waiting?.scroller.removeEventListener("scroll", this.#sawAnswer);
    this.#waiting = null;
  }

  // Shows the answer waiting past the box's foot: its start comes into sight. The press
  // that took New reply away leaves the user on the thread, as showing a thread's held
  // news does.
  #showAnswer = () => {
    const waiting = this.#waiting;
    if (!waiting) return;
    focusDestination(wholeThread(this.node), "move");
    this.#stopWaiting();
    this.repaint();
    const node = this.#answerNode(waiting.message);
    if (node) scrollIntoView(node, { block: "start" });
  };

  // Scrolling the answer's start into sight above New reply takes New reply away, the
  // box keeping its height. A scroll Leaf makes, as keeping the box's foot beside a
  // growing field (dom/scrolling.js, `keepFoot`), is not the user going there.
  #sawAnswer = () => {
    const waiting = this.#waiting;
    if (!waiting || !browserScrolls(waiting.scroller)) return;
    const node = this.#answerNode(waiting.message);
    const press = this.node.querySelector(".lf-new-reply");
    if (!node || !press) return;
    // Focusing New reply can scroll this box to reveal the press. That scroll must not
    // remove the focused press before its Enter can activate it.
    if (press === focused()) return;
    if (node.getBoundingClientRect().top >= press.getBoundingClientRect().top) return;
    this.#stopWaiting();
    this.repaint();
  };

  #releaseHeaderSlot() {
    if (this.#observedHeader) this.#sizes.unobserve(this.#observedHeader);
    this.#observedHeader = null;
    this.#releaseHeaderItems();
    keeps(this.#news.node, "data-lf-room", null);
    this.#news.node.style.removeProperty("--lf-thread-news-start");
    this.#news.node.style.removeProperty("--lf-thread-news-visible-end");
  }

  #releaseHeaderItems() {
    for (const { node } of this.#headerSlot?.items ?? []) {
      node.classList.toggle("lf-held-header-item", false);
      node.style.removeProperty("--lf-held-header-width");
    }
    this.#headerSlot = null;
  }

  #retainHeaderSlot({ observe = true } = {}) {
    const news = this.#model.news;
    if (observe && !news) {
      this.#releaseHeaderSlot();
      return;
    }
    const content = this.node.querySelector(":scope > .lf-thread-content");
    const first = content?.querySelector(
      ":scope > .lf-thread-transcript > :nth-child(1 of .lf-msg, .lf-thread-checkpoint)",
    );
    const header: HTMLElement | null | undefined =
      first?.querySelector(":scope > .lf-summary-checkpoint > .lf-summary-header") ??
      first?.querySelector(":scope > .lf-msg-head");
    if (!header) {
      this.#releaseHeaderSlot();
      return;
    }
    const box = header.getBoundingClientRect();
    if (!box.width) return;
    const allocates = header.classList.contains("lf-msg-head");
    if (observe && this.#observedHeader !== header) {
      if (this.#observedHeader) this.#sizes.unobserve(this.#observedHeader);
      this.#sizes.observe(header);
      this.#observedHeader = header;
    }
    let slot = this.#headerSlot;
    if (!slot || slot.header !== header || slot.boxWidth !== box.width || !news) {
      // A new width is a user reflow. Read its unconstrained allocation on an
      // invisible copy, without transient writes to real words.
      const resizing = allocates && slot?.header === header;
      let reading = header;
      if (resizing) {
        reading = header.cloneNode(true);
        Object.assign(reading.style, {
          position: "absolute",
          visibility: "hidden",
          inlineSize: layoutPx(box.width),
          margin: "0",
          anchorName: "none",
        });
        for (const node of words(reading)) {
          node.classList.toggle("lf-held-header-item", false);
          node.style.removeProperty("--lf-held-header-width");
        }
        header.after(reading);
      } else this.#releaseHeaderItems();
      const originals = words(header)[Symbol.iterator]();
      const items = [];
      for (const measured of words(reading)) {
        const original = originals.next();
        if (original.done) break;
        items.push({
          node: original.value,
          width: measured.getBoundingClientRect().width,
        });
      }
      if (resizing) reading.remove();
      slot = { header, items, boxWidth: box.width, held: observe };
      this.#headerSlot = slot;
      for (const { node, width } of allocates ? items : []) {
        // Keep the author's current width before the first held render, while
        // its receipt can still take unused room on that first presentation.
        if (!observe && node.classList.contains("lf-msg-meta")) continue;
        node.classList.toggle("lf-held-header-item", true);
        node.style.setProperty("--lf-held-header-width", layoutPx(width));
      }
    }
    if (observe && !slot.held) {
      for (const item of allocates ? slot.items : []) {
        if (item.node.classList.contains("lf-msg-meta"))
          item.width = Math.max(item.width, item.node.getBoundingClientRect().width);
        item.node.classList.toggle("lf-held-header-item", true);
        item.node.style.setProperty("--lf-held-header-width", layoutPx(item.width));
      }
      slot.held = true;
    }
    // The notice's readings are lengths from the header's start: where the words end,
    // which the notice starts after, and where the header's line stops showing, which
    // it stops before (surfaces.css, `.lf-thread-content > .lf-thread-news`).
    const notice = this.#news.node;
    const right = Math.max(
      box.left,
      ...slot.items.map(({ node }) => node.getBoundingClientRect().right),
    );
    notice.style.setProperty("--lf-thread-news-start", layoutPx(right - box.left));
    if (news) {
      // While news stands, the notice holds the room of the widest count it says, so
      // later news never narrows or widens it under the pointer.
      keeps(notice, "data-lf-room", NEWS_ROOM);
      const shown = shownRect(header, new Map());
      if (shown)
        notice.style.setProperty(
          "--lf-thread-news-visible-end",
          layoutPx(Math.max(0, shown.right - box.left)),
        );
    } else keeps(notice, "data-lf-room", null);
  }

  // The words the thread is about, over its to-dos and messages, where its container
  // asks for them or the page leaves them unmarked (`ThreadOutlets`, `quote`), in three
  // lines: where they still stand on the page, the container's way there goes to
  // them; where they no longer do, as for a thread a revision detached from its
  // passage, the quotation the thread kept is all that is left of them, so the label
  // over them opens the whole of it, standing above the words it grows so the press
  // never moves itself. The quote's status word leads its words, so the three lines
  // never cut it. The label takes a press only where three lines cut the words
  // (`#quoteCut`), and the quote stays whole while the view stands. Where the words
  // stand is read from the page, which the thread's pass reads again after drawing
  // (presentation.js, `readTargets`) and a data refresh changes without changing the
  // thread, so the quote draws by an effect of its own that follows that reading as
  // well as the thread.
  #drawQuote() {
    this.#quoteEffect ??= effect(() => {
      const thread = this.#shown.value.source;
      documentChanged();
      const quote = quoteReading(thread, this.#commands);
      const opens = this.#quoteExpanded.value || this.#quoteCut.value;
      untracked(() => {
        keepsHidden(
          this.#quoteHead,
          !quote || !(this.#outlets.quote || quote.unmarked),
        );
        keeps(this.#quoteHead, "data-lf-detached", quote?.detached ? "" : null);
        keeps(this.#quoteHead, "title", (quote?.place && quote.trail) || null);
        render(this.#quoteTemplate(quote, opens), this.#quoteHead);
      });
    });
    return this.#quoteHead;
  }

  // The label says the quote's status and where its words stand, and where three lines
  // cut words the page no longer shows, it is the press that opens them whole: one line
  // over the quote, its disclosure arrow hanging on the quote's rule so its words keep
  // the quote's edge. Its words say the quote's state rather than the press's act, so
  // the press names that act after them to a listener, and its preview names what a
  // press does now, as a promise's word naming where it opens does (records/thread/messages.js).
  // Rejected: a Full quote press on a line of its own under the label, which the user
  // read as a second label, set in from the quote's edge.
  #quoteTemplate(quote: ReturnType<typeof quoteReading>, opens: boolean) {
    if (!quote) return nothing;
    const expanded = quote.localReading && this.#quoteExpanded.peek();
    const status = quote.status
      ? html`<span class="lf-anchor-status">${voiced(quote.status)}</span>`
      : nothing;
    // Quoted words with no place of their own stand under the headings over them, so a
    // status arriving, as a revision that rewrites them while the thread is open sends,
    // takes a line the label already holds rather than growing the head under the
    // user's controls. A container standing beside the words, as a margin card's
    // bracket does, already shows where they stand, so there they go unnamed.
    const where = quote.place || (this.#outlets.quote ? quote.trail : "");
    const said =
      where || quote.status
        ? html`${status}${where && quote.status ? " · " : ""}${where}`
        : null;
    const saidText = [quote.status && wordsText(quote.status), where]
      .filter(Boolean)
      .join(" · ");
    const act = expanded ? "Fold the quote" : "Full quote";
    const line =
      quote.words && quote.localReading && opens
        ? html`<button
            type="button"
            ${offeredAction("inline", "lf-quote-expand lf-disclosure-marker")}
            data-lf-hint
            aria-label=${saidText ? `${saidText}, Full quote` : "Full quote"}
            aria-expanded=${String(expanded)}
            aria-controls=${this.#quoteId}
            .lfPreview=${() => ({ name: act })}
            @click=${() => {
              this.#quoteExpanded.value = !this.#quoteExpanded.peek();
            }}
          >
            ${said ?? "Full quote"}
          </button>`
        : said;
    const label = line
      ? html`<p class="lf-quote-label" ?data-lf-opens=${quote.localReading}>${line}</p>`
      : nothing;
    if (!quote.words) return label;
    return html`${label}
      <blockquote
        ${ref(this.#watchQuote)}
        id=${this.#quoteId}
        class="lf-thread-quote"
        data-lf-expanded=${String(expanded)}
      >
        ${quote.words}
      </blockquote>`;
  }

  #watchQuote = (node: Element | undefined) => {
    this.#quoteSize.disconnect();
    if (node) this.#quoteSize.observe(node);
  };

  // An opened quote is whole, so whether three lines cut it is read while it is shut.
  #fitQuote() {
    const quote = this.#quoteHead.querySelector(":scope > .lf-thread-quote");
    if (quote && !this.#quoteExpanded.peek())
      this.#quoteCut.value = quote.scrollHeight > quote.clientHeight;
  }

  // Resolve and Reopen are one toggle, so every surface draws it as one check, drawn
  // done on a resolved thread (browser/AGENTS.md, "Controls are few and quiet"), in one corner:
  // settling moves nothing beside it. Rejected: a margin card saying Reopen as a word.
  #settlement(
    model: ThreadViewModel,
    state: NonNullable<ThreadViewModel["settlement"]>,
  ) {
    const reopen = state.kind === "unresolve";
    const word = reopen ? "Reopen" : "Resolve";
    const label =
      reopen && model.resolvedBy
        ? `✓ ${model.resolvedBy} · ${state.label}`
        : state.label;
    return html`<button
      ${offeredAction("symbol", reopen ? "lf-reopen" : "lf-resolve", label, {
        action: reopen ? "reopen" : "resolve",
      })}
      data-lf-carry="settlement"
      data-lf-disc
      data-lf-tone=${reopen ? "positive" : "ink"}
      ${commandsOn(`On a thread's ${word} button`, (button) => [
        {
          id: reopen ? "thread.reopen" : "thread.resolve",
          keys: PRESS,
          title: word.toLowerCase(),
          control: button,
          run: this.#settle,
        },
      ])}
    ></button>`;
  }

  // What the thread holds, shown by a press on one of its controls. Where showing it
  // takes the pressed control away, as a held settlement does Resolve, the press leaves
  // the user on the thread's title.
  #showNews() {
    if (!this.#model.news) return;
    const restoreFocus = holdFocus(this.node);
    this.#model.news.open();
    restoreFocus?.(this.node);
  }

  // A press means what its control drew, and shows what the thread holds; where the
  // thread already stands as the press means, as one resolved elsewhere whose news
  // waits, it sends nothing (actions.js, `settle`).
  #settle = () => {
    const model = this.#model;
    const { landing } = this.#outlets;
    this.#showNews();
    if (!model.resolved) dismissReply(model.key);
    void settleThread({
      parent: () => this.#model.id,
      key: model.key,
      resolved: model.resolved,
      // Where the container says a settlement takes the user, as the floating panel
      // moves on to the next thread and a margin card to the next at its passage, else
      // closes onto it (`ThreadOutlets`, `landing`), else the thread's own.
      prepareLanding: () => landing?.(model.resolved) ?? this.#prepareThreadLanding(),
      ...this.#commands.settlement,
    }).catch(() => {});
  };

  // Reopening lands in the reply on every card, even when Lit retains the pressed
  // button, wherever the thread stands its reply box and its settlement, as the
  // floating panel stands them apart. A page thread also moves into or out of its
  // seat's Resolved disclosure (inline.js), so keep its destination in view once the
  // departing pixels finish.
  #prepareThreadLanding = () => {
    const reopening = this.#model.resolved;
    const mayLand = retainUserIntent({
      source:
        [this.node, ...Object.values(this.#apart)].find((at) =>
          currentLocationIn(at),
        ) ?? this.node,
      available: () => this.node.isConnected,
    });
    return async () => {
      // The summary is semantically available at once, but a long departing card
      // still puts it below the viewport. Keep this gesture's original authority
      // while its pixels leave; a later user move still vetoes the landing.
      await this.#retirement?.catch(() => {});
      const place = this.#fold?.querySelector(":scope > summary") ?? this.node;
      const places = [place, ...Object.values(this.#apart)];
      if (!mayLand() || !places.some((at) => currentLocationIn(at))) return false;
      if (reopening) this.#commands.landInThread(this.#reply?.input ?? this.node);
      // A floating card stands itself (`CardOutlets`, `endNewsMoves`), so landing in
      // it scrolls nothing into view.
      const control = focused();
      if (!this.#outlets.endNewsMoves && control) scrollThreadIntoView(place, control);
      return true;
    };
  };

  // Every thread keeps its reply box. A resolved thread's says that a reply reopens it
  // (events.md), as the floating panel's field does.
  #createReply(model: ThreadViewModel) {
    const commands = this.#commands.reply;
    const { hint, hintParts, hintLead, ...options } =
      this.#outlets.reply?.options ?? {};
    // The box's empty words say the thread as this view draws it, held news included,
    // so they change with its settlement and notice, when the user shows the news, and
    // not before. They read the drawn reading as a signal, so the box draws them again
    // with each reading the thread draws.
    const drawn = (): DrawnThread => {
      const { resolved, resolvedBy, attention } = this.#shown.value;
      return { resolved, resolvedBy, attention };
    };
    return createReplyView(
      model.key,
      {
        ...commands,
        actions: {
          ...commands.actions,
          reply: (key, text, options) => {
            // The user's turn takes New reply away, with the paint it brings.
            const stood = this.#waiting;
            this.#stopWaiting();
            const flight = commands.actions.reply(key, text, options);
            if (!flight && stood) this.repaint();
            return flight;
          },
        },
      },
      () => this.repaint(),
      {
        hint: hint
          ? () => hint(drawn())
          : () => (drawn().resolved ? REOPEN_HINT : REPLY_HINT),
        ...(hintParts && { hintParts: () => hintParts(drawn()) }),
        ...(hintLead && { hintLead: () => hintLead(drawn()) }),
        // A container says what the box reads and how a send lands there, as a margin
        // card moves with the send it presents (`ThreadOutlets`, `reply`).
        ...options,
        editLast: this.#rewrites.editLast,
      },
    );
  }

  commit() {
    this.#transcript.commit(this.#model);
  }

  // The reply being written in this thread, which no view holds, comes into this one
  // once it is `shown` (replies.js, `claim`).
  claimReply(shown: () => boolean) {
    this.#reply?.claim(shown);
  }

  retire() {
    this.#reply?.cancelDictation();
    this.#transcript.retire();
  }

  dispose() {
    this.#stopWaiting();
    this.#received = null;
    this.#sizes.disconnect();
    this.#releaseHeaderSlot();
    this.#quoteSize.disconnect();
    this.#quoteEffect?.();
    this.#quoteEffect = null;
    this.#continuity.release();
    this.retire();
    this.#reply?.dispose();
    this.#reply = null;
  }
}
