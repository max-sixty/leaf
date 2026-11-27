// Compiled from transcript.ts by build/typescript.mjs; edit that file.
/* A thread's messages as every reader of a whole thread draws them: a card on the page
   or in the margin, and the floating panel's view of a thread (thread-card.js). The
   thread around it draws its head, controls and reply box; this owner draws only the
   transcript.

   - Each turn is one MessageView, which shows whether its version is unread and
     reports its exposure to read tracking (read.js), so a reply counts as read the same
     way in every reader.
   - Every message and step's face says when it was said (state/presence.js, `saidAt`),
     since each reply says what was true when it was sent ("I'm building it now"):
     how long ago within the hour ("just now", "12m ago") and its time of day after
     that, as the user asked. Rejected: a time of day from the first minute, which
     makes a reply seconds old read like any other ("15:24"); a fixed 24-hour clock,
     which a reader whose own clock reads "3:24 PM" doesn't use (state/presence.js,
     `timeOfDay`); an age said only where it changes from the message above, which
     rounds replies hours apart into one "1d ago" a day later and leaves the replies
     under it bare; and an age after every author name, which repeats one age down a
     thread written at once ("72d ago" four times).
   - A summary the agent wrote folds the turns it covers behind its checkpoint, a region
     in the tint Leaf gives settled things (surfaces.css), so its words read as neither
     a message nor the end of the one above it. One quiet press at its head says how
     many messages it folds ("› 5 earlier messages"), set as a message's time is, and
     a name the agent gave the range leads its words in bold, as a recap names what it
     covers. Opened, the tint takes in the messages it folds, so the reader sees where
     the live conversation picks up. The user chose this over a label ("Earlier
     discussion") beside an accent "Show 5 earlier messages", which named the fold
     twice and, beside a margin card's actions, wrapped the label and cut the press;
     over one fold line naming the range in a sender's face, as a settled decision
     folds; and over the count after the summary's words.
   - A step of the agent's work (a progress message) is never a message the transcript
     folds. The server ends each step as the agent next speaks in its thread, or, where
     the user wrote after it, as the agent next replies, or as its turn ends with no
     message before it reading On it (`served_state.thread.progress_ends`). So between
     two of the user's messages a thread holds at most one step nothing has ended,
     which it draws as one dim line, its face (`workingView`), where it was said. The
     user chose that an ended step goes rather than wait behind a disclosure. The face
     of the step the agent's work in hand speaks through is the working message; work
     whose words no step holds stands as a face of its own where those words were said
     (`workingPlace`). A face arriving in a thread already drawn wears a message's
     arrival tint (messages.js, `arrivalTint`), as the user asked; a step that takes
     the place of the one before it, with no message between, changes the face's words
     and is no arrival. A thread reads in the order it was said, so a message the user
     sends after a face stands below it.
   - The transcript is flat: a fold's checkpoint stands before the messages it covers,
     which stay the transcript's own children where they were said and are hidden in
     place while the fold is closed. They are hidden until found, so the browser's
     find-in-page reaches their words and opens the fold, as Leaf's travel does; a
     folded message keeps an empty box, so a reader asking whether a message shows asks
     `showsContents` (dom/geometry.js) rather than `checkVisibility`. Rejected: plain
     `hidden`, which find-in-page skips. A summary arriving, opening, closing or being
     retracted moves no message, so a frame in one keeps its document and a selection
     in one stays. The checkpoint groups its messages for assistive technology by
     `aria-owns`, and draws the frame around the open fold from its own head to its
     last message's foot by anchors (`--lf-fold-head`, `--lf-fold-foot`, surfaces.css),
     since no box contains them. Rejected: moving the covered messages into a container
     inside the checkpoint, which unloads a frame among them in an engine without
     `moveBefore` and loses a selection inside them in every engine; and
     nesting such a container in a `repeat` inside the transcript's `repeat`, which
     rebuilds a gathered message's row.
   - An explicit summary that arrives over a message the user is on or reads stays
     open.
   - A message that leaves the thread while drawn, as a reply the log refuses does,
     folds away where it stood (dom/motion.js, `foldBlock`). It leaves the transcript's
     messages at once: the fold keeps only its pixels, inert and without the names a
     reader finds a message by, until they have collapsed. Where no fold plays, under
     reduced motion, before presentation or in an engine without intrinsic-size
     interpolation, it goes in the same frame. */
import { counted } from "../../lib/words.js";
import { focusDestination, focused } from "../../dom/focus.js";
import { html, render, nothing, repeat, ref } from "/vendor/lit.js";
import { MessageView, arrivalTint, saidTime } from "./messages.js";
import { offeredAction } from "../../lib/controls.js";
import { keeps, keepsHidden } from "../../lib/keeps.js";
import { renderMarkdown } from "../../lib/markdown.js";
import { pageLinks } from "../page-markdown.js";
import { summaryRanges, workingPlace } from "./summary-ranges.js";
import {
  growthAfterIsSeen,
  growthIsSeen,
  seenRect,
  showsContents,
} from "../../dom/geometry.js";
import { scrollThreadIntoView } from "./reply-landing.js";
import { foldBlock, motionPlays } from "../../dom/motion.js";
import { voiced } from "../../base/voice.js";

// A summary's words, led by the name its agent gave the range as their first
// paragraph's run-in head, closed by a stop where the name has none. Words that open
// with no paragraph, as a list does, and a summary with no words, hold the name as a
// paragraph of its own.
function summaryWords({ text, label }) {
  const words = document.createElement("template");
  words.innerHTML = text ? renderMarkdown(text, pageLinks) : "";
  if (!label) return words.innerHTML;
  const name = document.createElement("strong");
  name.className = "lf-summary-label";
  name.textContent = label;
  const first = words.content.firstChild;
  if (first instanceof Element && first.localName === "p") {
    if (!/[.!?:…]$/u.test(label)) name.append(".");
    first.prepend(name, " ");
  } else {
    const named = document.createElement("p");
    named.append(name);
    words.content.prepend(named);
  }
  return words.innerHTML;
}

// The names a reader finds a drawn message by (messages.js), which a folding one gives up.
const MESSAGE_NAMES = ["data-lf-message", "data-lf-event", "data-lf-attempt"];

// A step's face: the step, drawn as a message is, with who wrote it and when at its
// head, but dimmed, and under a passing sheen while it is the working message and the
// work runs, as a title being generated is. It is one of the transcript's children, so
// it stands at the conversation's inset on every surface and scrolls with it. Its head
// wears a message head's face but not its class, since it is no message: a message
// head's places, such as held news's, skip it.
function workingView(working, observe) {
  return html`<div class="lf-thread-working-head">
      ${working.who ? html`<b>${working.who}</b>` : nothing}
      ${
        working.timestamp || working.condition
          ? html`<span class="lf-msg-meta"
              >${saidTime(working.timestamp)}${
                working.condition
                  ? html`<span>${voiced(working.condition)}</span>`
                  : nothing
              }</span
            >`
          : nothing
      }
    </div>
    <div class="lf-thread-working-words" ${observe ? ref(observe) : nothing}>
      ${working.words}
    </div>`;
}

// The face of a step the work in hand does not speak through: the step, still.
const stepOf = (message) =>
  Object.freeze({
    who: message.by,
    timestamp: message.timestamp,
    words: message.body.plainText.trim().replace(/\.$/, ""),
    live: false,
    condition: null,
  });

let nextTranscriptId = 0;
export class Transcript {
  #commands;
  #messageCommands;
  #repaint;
  #home;
  #model = null;
  #rows = [];
  #messages = new Map();
  // The face each step is drawn as, by the step's key.
  #facing = new Map();
  // Every face this transcript has drawn, so one new to it is told apart.
  #faces = new WeakSet();
  #stopWorkingExposure = null;
  // Each message folding away, by its key: its node, the names it gave up, and the
  // fold once it plays.
  #folding = new Map();
  #expandedSummaries = new Set();
  #id = ++nextTranscriptId;
  // Counts the ids this transcript gives covered messages.
  #named = 0;
  #awaited = nothing;

  constructor({ commands, messageCommands, repaint, home }) {
    this.#commands = commands;
    this.#messageCommands = messageCommands;
    this.#repaint = repaint;
    this.#home = home;
    this.node = document.createElement("div");
    this.node.className = "lf-thread-transcript";
  }

  // Whatever reveals a message a closed fold holds, the browser's find-in-page or
  // Leaf's travel (dom/widget-elements.js, `reveal`), opens the fold: each fires
  // `beforematch` at the message before showing it.
  #unfold(node) {
    const id = node.dataset.lfSummary;
    if (!id || this.#expandedSummaries.has(id)) return;
    this.#expandedSummaries.add(id);
    this.#repaint();
  }

  // Each message's view, in the thread's order: what its rewrites walk.
  get views() {
    return (this.#model?.messages ?? []).flatMap(
      ({ key }) => this.#messages.get(key) ?? [],
    );
  }

  // The node a message stands in.
  messageNode(key) {
    return this.#messages.get(key)?.node ?? null;
  }

  // The drawn messages `model` no longer holds, which leave as it is presented.
  leaving(model) {
    const wanted = new Set(model.messages.map(({ key }) => key));
    return [...this.#messages].flatMap(([key, { node }]) =>
      wanted.has(key) || !node.isConnected ? [] : [node],
    );
  }

  // The checkpoint a summary stands in.
  summaryNode(id) {
    return this.node.querySelector(`:scope > [data-lf-summary-id="${CSS.escape(id)}"]`);
  }

  // The last node the transcript shows. The messages a closed fold covers stand in the
  // transcript hidden, so the last message alone may show nothing.
  get foot() {
    return (
      [...this.node.children].findLast(
        (node) => !node.matches(".lf-awaited") && showsContents(node),
      ) ?? null
    );
  }

  // Whether held news (held-news.js) would move what the reader sees of the
  // transcript: a message it changes, or the transcript's end it adds to, with growth
  // after it in sight, unless that end is `followed`, as by a reply pinned below it; or
  // a fold that comes or goes over what is in sight, a step's face that goes among
  // them, but for one at the transcript's foot (`footFold`), which changes only that
  // end. A step's face changes its words only where the next step takes its place.
  newsMoves({ news, changed, folds, footFold }, { followed = null } = {}) {
    return (
      [
        ...[...changed].flatMap((key) => [
          this.#facing.get(key),
          this.messageNode(key),
        ]),
        (news.appended || news.settled || news.working) && this.foot,
      ].some((node) => node && node !== followed && growthAfterIsSeen(node)) ||
      [
        ...(footFold ? [] : folds.messages).map(
          (key) => this.#facing.get(key) ?? this.messageNode(key),
        ),
        ...folds.summaries.map((id) => this.summaryNode(id)),
      ].some((node) => node && growthIsSeen(node))
    );
  }

  // Opens the fold holding a message, as a rewrite of it opens to be seen.
  expandAround(id) {
    const folded = this.#model?.summaries.find(({ covers }) => covers.includes(id));
    if (folded) this.#expandedSummaries.add(folded.id);
  }

  /** Draws `model`, a thread's reading (thread-card.js, `threadReading`). `awaited` is
   * what the reader says stands after the messages: New reply (thread-card.js). */
  present(model, { arrived = false, awaited = nothing } = {}) {
    this.#awaited = awaited;
    const prior = this.#model;
    const currentLocation = focused();
    const priorSummaries = new Set(prior?.summaries.map(({ id }) => id) ?? []);
    // Only a summary that was not present before can swallow what the user
    // holds or is reading, and reading geometry here forces layout.
    if (prior && model.summaries.some(({ id }) => !priorSummaries.has(id))) {
      const heldMessage = prior.messages.find(({ key }) =>
        this.#messages.get(key)?.node.contains(currentLocation),
      )?.id;
      // Being read is being on screen, on whichever surface holds the thread.
      const clips = new Map();
      const beingRead = new Set(
        prior.messages
          .filter(({ key }) => {
            const node = this.#messages.get(key)?.node;
            return node?.isConnected && seenRect(node, clips);
          })
          .map(({ id }) => id),
      );
      for (const summary of model.summaries) {
        if (priorSummaries.has(summary.id)) continue;
        if (
          summary.covers.some((id) => id === heldMessage) ||
          summary.covers.some((id) => beingRead.has(id))
        )
          this.#expandedSummaries.add(summary.id);
      }
    }
    this.#model = model;
    const wanted = new Set(model.messages.map((message) => message.key));
    for (const [key, fold] of this.#folding)
      if (wanted.has(key)) this.#endFold(key, fold, false);
    for (const [key, view] of this.#messages) {
      if (wanted.has(key)) continue;
      const { node } = view;
      if (
        motionPlays() &&
        !this.#folding.has(key) &&
        node.parentNode === this.node &&
        showsContents(node)
      ) {
        const names = MESSAGE_NAMES.map((name) => [name, node.getAttribute(name)]);
        for (const [name] of names) node.removeAttribute(name);
        node.inert = true;
        this.#folding.set(key, { node, names, played: null });
      }
      view.retire();
    }
    // A step of the agent's work is drawn only as a face (`workingView`), never as a
    // message a fold holds, so only the conversation's turns get a view.
    const drawnMessages = model.messages
      .filter((message) => !message.progress)
      .map((message) => {
        let view = this.#messages.get(message.key);
        if (!view) {
          view = new MessageView(this.#messageCommands);
          this.#messages.set(message.key, view);
          const { node } = view;
          node.addEventListener("beforematch", () => this.#unfold(node));
        }
        return { ...message, reading: message, view };
      });
    const steps = model.messages.filter((message) => message.progress);
    const ranges = summaryRanges(drawnMessages, model.summaries);
    const summaries = new Set(
      ranges.flatMap((range) => (range.summary ? [range.summary.id] : [])),
    );
    for (const id of this.#expandedSummaries)
      if (!summaries.has(id)) this.#expandedSummaries.delete(id);
    const rangeState = ranges.map((range) =>
      range.kind === "message"
        ? range
        : { ...range, expanded: this.#expandedSummaries.has(range.summary.id) },
    );
    // Each step's face, and the working message, stands after the range holding the
    // last message said before its words. The working message speaks through the face
    // of the newest step standing there, else through a face of its own.
    const working = model.working;
    const workingAt = working ? workingPlace(rangeState, working.position) : null;
    const standing = steps.map((step) => ({
      step,
      at: workingPlace(rangeState, step.sequence),
    }));
    const host = working ? standing.findLast(({ at }) => at === workingAt) : undefined;
    for (const message of drawnMessages) {
      const view = message.view;
      view.present(message.reading, { arrived });
      // A reply still streaming at the thread's end grows at its foot as its words
      // come, as the working message does with each step (shift_watch.js).
      keeps(
        view.node,
        "data-lf-append-tail",
        message.provisional && message.reading === model.messages.at(-1) ? "" : null,
      );
    }
    // Each message where it was said, hidden until found while a closed fold covers it,
    // and standing in its summary's region while an open one does (surfaces.css).
    const placed = (message, fold = null) => {
      const node = message.view.node;
      keeps(node, "data-lf-summary", fold?.summary.id ?? null);
      keeps(node, "data-lf-summarized", fold ? "" : null);
      keepsHidden(node, fold && !fold.expanded ? "until-found" : false);
      return node;
    };
    // The open fold's last message, which its checkpoint's frame reaches down to.
    const feet = new Map();
    const transcript = [];
    const facing = new Map();
    const messageRow = (node, key) => ({
      key: `message:${key}`,
      body: node,
    });
    const face = (id, reading, feedback = null) => {
      const row = {
        key: `face:${id}`,
        body: (tail) =>
          html`<div
            class="lf-thread-working"
            data-lf-face=${id}
            aria-live="polite"
            data-lf-live=${reading.live ? "" : nothing}
            data-lf-append-tail=${tail ? "" : nothing}
          >
            ${workingView(
              reading,
              feedback
                ? (node) => {
                    if (!node) return;
                    this.#stopWorkingExposure = this.#commands.read.observeFeedback(
                      node,
                      {
                        ...feedback,
                        presentation_kind: "working_words",
                        surface: model.surface,
                      },
                    );
                  }
                : null,
            )}
          </div>`,
      };
      transcript.push(row);
      return row;
    };
    // The faces standing after the range at `at`, named for it as `place`. A step keeps
    // its face while the next one stands where it stood, so its words change in place;
    // one said after another message is a face of its own.
    const facesAfter = (at, place) => {
      const here = standing.filter((each) => each.at === at);
      for (const [index, each] of here.entries()) {
        const hosted = each === host ? working : null;
        const row = face(
          index ? `${place}:${each.step.id}` : place,
          hosted ?? stepOf(each.step),
          hosted?.feedback ?? null,
        );
        facing.set(each.step.key, row);
      }
      if (working && at === workingAt && !host)
        face("working", working, working.feedback);
    };
    // A step in a thread that opened with a mark, a reaction, stands before every turn.
    facesAfter(-1, "start");
    for (const [at, range] of rangeState.entries()) {
      if (range.kind === "message") {
        transcript.push(messageRow(placed(range.message), range.message.key));
        facesAfter(at, `message:${range.message.key}`);
        continue;
      }
      const id = range.summary.id;
      const covered = range.messages.map((message) => placed(message, range));
      for (const node of covered) node.id ||= `lf-msg-${this.#id}-${++this.#named}`;
      const anchor = `--lf-fold-${this.#id}-${CSS.escape(id)}`;
      transcript.push(
        { key: `summary:${id}`, body: this.#checkpoint(range, covered, anchor) },
        ...range.messages.map((message) => messageRow(message.view.node, message.key)),
      );
      feet.set(covered.at(-1), `${anchor}-foot`);
      facesAfter(at, `summary:${id}`);
    }
    for (const { node } of this.#messages.values()) {
      const foot = feet.get(node);
      if (foot) node.style.setProperty("--lf-fold-foot", foot);
      else node.style.removeProperty("--lf-fold-foot");
    }
    for (const row of transcript) row.tail = row === transcript.at(-1);
    this.#rows = this.#withFolds(transcript);
    this.#stopWorkingExposure?.();
    this.#stopWorkingExposure = null;
    this.#paint();
    const faceNode = (row) =>
      this.node.querySelector(
        `:scope > [data-lf-face="${CSS.escape(row.key.slice(5))}"]`,
      );
    this.#facing = new Map([...facing].map(([key, row]) => [key, faceNode(row)]));
    // A face arriving in a thread already drawn wears a message's arrival tint.
    for (const node of this.node.querySelectorAll(":scope > .lf-thread-working")) {
      if (this.#faces.has(node)) continue;
      this.#faces.add(node);
      if (arrived) arrivalTint(node);
    }
    for (const [key, fold] of this.#folding) {
      if (fold.played) continue;
      fold.played = foldBlock(fold.node);
      if (!fold.played) {
        this.#endFold(key, fold, true);
        continue;
      }
      fold.played.finished.then(
        () => {
          if (this.#folding.get(key) === fold) this.#endFold(key, fold, true);
        },
        () => {},
      );
    }
  }

  // Each folding message keeps its last row: after the last row before it that stays,
  // else first. Lit retains and places the native nodes named by these rows.
  #withFolds(rows) {
    if (!this.#folding.size) return rows;
    const staying = new Set(rows.map(({ key }) => key));
    const after = new Map();
    let anchor = null;
    for (const row of this.#rows)
      if (row.key.startsWith("message:") && this.#folding.has(row.key.slice(8)))
        after.set(anchor, [...(after.get(anchor) ?? []), row]);
      else if (staying.has(row.key)) anchor = row.key;
    return [
      ...(after.get(null) ?? []),
      ...rows.flatMap((row) => [row, ...(after.get(row.key) ?? [])]),
    ];
  }

  // A fold ends with its node `removed`, else, its message having come back, with the
  // node standing again as it was. Either way the node is as its view drew it, since
  // the view may draw it again before the reader commits.
  #endFold(key, fold, removed) {
    this.#folding.delete(key);
    if (removed) {
      this.#rows = this.#rows.filter((row) => row.key !== `message:${key}`);
      this.#paint();
    } else fold.played?.cancel();
    fold.node.inert = false;
    for (const [name, value] of fold.names)
      if (value !== null) fold.node.setAttribute(name, value);
  }

  #paint() {
    render(
      html`${repeat(
        this.#rows,
        (row) => row.key,
        (row) => (typeof row.body === "function" ? row.body(!!row.tail) : row.body),
      )}${this.#awaited}`,
      this.node,
    );
  }

  #checkpoint(range, covered, anchor) {
    return html`<section
      class="lf-thread-checkpoint"
      data-lf-summary-id=${range.summary.id}
      data-lf-expanded=${range.expanded}
      aria-owns=${covered.map(({ id }) => id).join(" ")}
      style=${`--lf-fold-head: ${anchor}; --lf-fold-foot: ${anchor}-foot;`}
    >
      <div
        class="lf-summary-checkpoint"
        ${ref((node) => {
          // The agent folded these messages for the user to read the fold instead, so
          // the fold seen whole reads them, whatever it says of them (read.js).
          if (node)
            this.#commands.read.observeSummary(
              node,
              range.messages.map(({ id, version }) => ({ message: id, version })),
            );
        })}
      >
        <div class="lf-summary-header">${this.#summaryToggle(range)}</div>
        ${
          range.summary.text || range.summary.label
            ? html`<div
                class="lf-summary-text"
                .innerHTML=${summaryWords(range.summary)}
              ></div>`
            : nothing
        }
      </div>
    </section>`;
  }

  // A summary's press says only what it folds, its arrow whether that shows, and stands
  // in its head's quiet face.
  #summaryToggle(range) {
    const { id } = range.summary;
    const subject = counted(range.messages.length, "earlier message");
    return html`<button
      type="button"
      ${offeredAction(
        "inline",
        "lf-thread-disclosure lf-disclosure-marker lf-summary-expand",
      )}
      data-lf-hint=""
      data-lf-summary-toggle=${id}
      aria-expanded=${String(range.expanded)}
      aria-controls=${range.messages
        .map(({ key }) => this.messageNode(key)?.id)
        .filter(Boolean)
        .join(" ")}
      @click=${() => this.#setSummaryExpanded(id, !range.expanded)}
    >
      <span data-lf-room=${subject}><span>${subject}</span></span>
    </button>`;
  }

  #setSummaryExpanded(id, expanded) {
    if (expanded) this.#expandedSummaries.add(id);
    else this.#expandedSummaries.delete(id);
    this.#repaint();
    const toggle = this.node.querySelector(
      `.lf-summary-expand[data-lf-summary-toggle="${CSS.escape(id)}"]`,
    );
    if (toggle) {
      focusDestination(toggle, "return");
      scrollThreadIntoView(this.#home(), toggle, "instant");
    }
  }

  commit(model) {
    const wanted = new Set(model.messages.map((message) => message.key));
    for (const [key, view] of this.#messages) {
      if (wanted.has(key)) view.commit();
      else {
        view.retire();
        this.#messages.delete(key);
      }
    }
  }

  retire() {
    this.#stopWorkingExposure?.();
    this.#stopWorkingExposure = null;
    for (const [key, fold] of this.#folding) {
      fold.played?.cancel();
      this.#endFold(key, fold, true);
    }
    for (const view of this.#messages.values()) view.retire();
  }
}
