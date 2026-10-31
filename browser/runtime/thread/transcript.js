/* A thread's messages as every reader of a whole thread draws them: a card on the page
   or in the margin (thread-card.js), and the floating panel's view of a thread through
   a primary reader's transcript part (primary-reader.js). The reader around it draws
   the thread's head, controls and reply box; this owner draws only the transcript.

   - Each turn is one MessageView, which shows whether its version is unread and
     reports its exposure to read tracking (read.js), so a reply counts as read the same
     way in every reader.
   - A message says its age only where that age, as displayed, changes from the
     message shown just above it, and the first message always says it: a thread
     written in one sitting reads one age, and one spanning days marks each change.
     The user chose that on 26 October 2026 over an age after every author name,
     which repeated one age down a thread written at once ("72d ago" four times).
   - A summary the agent wrote folds the turns it covers behind its checkpoint.
     Completed progress disappears when its answer shows, including a streaming answer.
     Each pending progress run stands behind a dim line showing its latest step
     (`workingView`). The face of the run the agent's work in hand
     speaks through is the working message; work whose words no run holds stands as a
     face of its own where those words were said (`workingPlace`). A thread reads in
     the order it was said, so a message the user sends after a face stands below it,
     and a face whose run the work leaves stays where it stood, still.
   - The transcript is flat: a fold's checkpoint stands before the messages it covers,
     which stay the transcript's own children where they were said and are hidden in
     place while the fold is closed. They are hidden until found, so the browser's
     find-in-page reaches their words and opens the fold, as Leaf's travel does; a
     folded message keeps an empty box, so a reader asking whether a message shows asks
     `showsContents` (geometry.js) rather than `checkVisibility`. Rejected: plain
     `hidden`, which find-in-page skips. A summary arriving, opening, closing or being
     retracted moves no message, so a frame in one keeps its document and a selection
     in one stays. The checkpoint groups its messages for assistive technology by
     `aria-owns`, and draws the frame around the open fold from its own head to its
     last message's foot by anchors (`--lf-fold-head`, `--lf-fold-foot`, surfaces.css),
     since no box contains them. Rejected: moving the covered messages into a container
     inside the checkpoint, which unloaded a frame among them in an engine without
     `moveBefore` (WebKit reloaded it once as the summary arrived and twice as it was
     retracted) and lost a selection inside them in every engine; and, before that,
     nesting such a container in a `repeat` inside the transcript's `repeat`, which
     rebuilt a gathered message's row.
   - An explicit summary that arrives over a message the user is on or reads stays
     open. Completed progress disappears even if the reader had opened it.
   - A message that leaves the thread while drawn, as a reply the log refuses does,
     folds away where it stood (motion.js, `foldBlock`). It leaves the transcript's
     messages at once: the fold keeps only its pixels, inert and without the names a
     reader finds a message by, until they have collapsed. Where no fold plays, under
     reduced motion, before presentation or in an engine without intrinsic-size
     interpolation, it goes in the same frame. */
import { focusDestination, focused } from "../focus.js";
import { html, render, nothing, repeat } from "/runtime/framework.js";
import { MessageView } from "./messages.js";
import { offeredAction } from "../widget-elements.js";
import { keeps, keepsHidden } from "../keeps.js";
import { renderMarkdown } from "../markdown.js";
import { summaryRanges, withPendingProgress, workingPlace } from "./summary-ranges.js";
import {
  growthAfterIsSeen,
  growthIsSeen,
  seenRect,
  showsContents,
} from "../geometry.js";
import { scrollThreadIntoView } from "./reply-landing.js";
import { foldBlock, motionPlays } from "../motion.js";

// The names a reader finds a drawn message by (messages.js), which a folding one gives up.
const MESSAGE_NAMES = ["data-message", "data-event", "data-attempt"];

// A progress run's face: its latest step, drawn as a message is, with who wrote it and
// when at its head, but dimmed, and under a passing sheen while it is the working
// message and the work runs, as a title being generated is. The earlier steps are
// superseded, and the answer that completes them removes the run. It
// is one of the transcript's children, so it stands at the conversation's inset on
// every surface and scrolls with it. Its head wears a message head's face but not its
// class, since it is no message: a message head's places (a margin's sticky head, held
// news) skip it. `controls` stand at its head's end, as a reply's progress disclosure
// stands at its own.
function workingView(working, controls = nothing) {
  return html`<div class="lf-thread-working-head">
      ${working.who ? html`<b>${working.who}</b>` : nothing}
      ${
        working.timestamp || working.condition
          ? html`<span class="lf-msg-meta"
              >${
                working.timestamp
                  ? html`<time datetime=${working.timestamp}>${working.age}</time>`
                  : nothing
              }
              ${
                working.condition
                  ? html`<span data-voice="leaf">${working.condition}</span>`
                  : nothing
              }</span
            >`
          : nothing
      }
      ${controls}
    </div>
    <div class="lf-thread-working-words">${working.words}</div>`;
}

// The face of a run the work in hand does not speak through: its latest step, still.
const stepOf = (message) =>
  Object.freeze({
    who: message.by,
    timestamp: message.timestamp,
    age: message.age,
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
  // The face each message stands behind as drawn, by the message's key: the last step
  // of its run, whose words the face shows.
  #facing = new Map();
  #stopWorkingExposure = null;
  // Each pending progress range's covered message ids, as last drawn, so a fold that
  // takes the range over can take its disclosure state with it.
  #pendingCovers = new Map();
  #pendingOpen = false;
  // Each message folding away, by its key: its node, the names it gave up, and the
  // fold once it plays.
  #folding = new Map();
  #expandedSummaries = new Set();
  #id = ++nextTranscriptId;
  // Counts the ids this transcript gives covered messages.
  #named = 0;

  /**
   * @param {object} options
   * @param {any} options.commands The reader's commands; `read` observes the working
   *   message's words.
   * @param {any} options.messageCommands What each MessageView acts through.
   * @param {() => void} options.repaint Draws the reader around the transcript again,
   *   as a disclosure opens or closes.
   * @param {() => HTMLElement} options.home The drawing of the thread a disclosure
   *   press keeps in view.
   */
  constructor({ commands, messageCommands, repaint, home }) {
    this.#commands = commands;
    this.#messageCommands = messageCommands;
    this.#repaint = repaint;
    this.#home = home;
    this.node = document.createElement("div");
    this.node.className = "lf-thread-transcript";
  }

  // Whatever reveals a message a closed fold holds, the browser's find-in-page or
  // Leaf's travel (widget-elements.js, `reveal`), opens the fold: each fires
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
    return this.node.querySelector(`:scope > [data-summary-id="${CSS.escape(id)}"]`);
  }

  // The last node the transcript shows. The messages a closed fold covers, progress
  // behind its run's face among them, stand in the transcript hidden, so the last
  // message alone may show nothing.
  get foot() {
    return [...this.node.children].findLast((node) => showsContents(node)) ?? null;
  }

  // Whether the progress behind the working message stood open when last drawn, opened by
  // the reader or by a search matching it, so each step that joins it shows: held news
  // counts those steps as news here (held-news.js).
  get progressOpen() {
    return this.#pendingOpen;
  }

  // Whether held news (held-news.js) would move what the reader sees of the
  // transcript: a message it changes, or the transcript's end it adds to, with growth
  // after it in sight, unless that end is `followed`, as by a reply pinned below it; or
  // a fold that comes or goes over what is in sight. The working message changes words
  // only at the run the newest step joins, the transcript's end; a run the work leaves
  // keeps its face's words where they stand.
  newsMoves({ news, changed, folds }, { followed = null } = {}) {
    return (
      [
        ...[...changed].flatMap((key) => [
          this.#facing.get(key),
          this.messageNode(key),
        ]),
        (news.appended || news.settled || news.working) && this.foot,
      ].some((node) => node && node !== followed && growthAfterIsSeen(node)) ||
      [
        ...folds.messages.map((key) => this.messageNode(key)),
        ...folds.summaries.map((id) => this.summaryNode(id)),
      ].some((node) => node && growthIsSeen(node))
    );
  }

  // Opens the fold holding a message, as a rewrite of it opens to be seen.
  expandAround(id) {
    const folded = this.#model?.summaries.find(({ covers }) => covers.includes(id));
    if (folded) this.#expandedSummaries.add(folded.id);
  }

  /**
   * Draws `model`, a thread's reading (thread-card.js, `threadReading`). `appends`
   * declares that it grows at its end inside the scroller holding it, as a margin
   * card's does (`data-lf-reflow`, tests/shift_watch.js). `notice` is a node the reader
   * stands at the head of the transcript's first message in sight, as a primary
   * reader's thread notice (primary-reader.js). Returns the disclosure that took over
   * the one the user was on, where this draw replaced it, as the answer's head takes
   * progress over from the working message.
   * @returns {HTMLElement | null}
   */
  present(model, { arrived = false, appends = false, notice = null } = {}) {
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
          summary.covers.includes(heldMessage) ||
          summary.covers.some((id) => beingRead.has(id))
        )
          this.#expandedSummaries.add(summary.id);
      }
    }
    this.#model = model;
    const wanted = new Set(model.messages.map((message) => message.key));
    for (const key of [...this.#folding.keys()])
      if (wanted.has(key)) this.#endFold(key, false);
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
    // A resolved thread holds no work in hand, so its progress stands as messages.
    const summarized = summaryRanges(model.messages, model.summaries);
    const describedRanges = model.resolved
      ? summarized
      : withPendingProgress(summarized);
    const summaries = new Set(
      describedRanges.flatMap((range) => (range.summary ? [range.summary.id] : [])),
    );
    // An explicit summary inherits the disclosure state of pending progress it
    // gathers. Completed progress has no disclosure to inherit that state.
    const successors = new Map();
    for (const [id, covers] of this.#pendingCovers)
      successors.set(
        id,
        describedRanges.filter((range) =>
          range.summary?.covers.some((covered) => covers.includes(covered)),
        ),
      );
    for (const id of [...this.#expandedSummaries])
      for (const range of successors.get(id) ?? [])
        this.#expandedSummaries.add(range.summary.id);
    for (const id of this.#expandedSummaries)
      if (!summaries.has(id)) this.#expandedSummaries.delete(id);
    this.#pendingCovers = new Map(
      describedRanges
        .filter((range) => range.summary?.pending)
        .map((range) => [range.summary.id, range.summary.covers]),
    );
    /** @type {HTMLElement | null} */
    const currentLocationToggle = this.node.querySelector(".lf-summary-expand:focus");
    const rangeState = describedRanges.map((range) => {
      if (range.kind === "message") return range;
      const forced = Boolean(range.summary.protected?.length);
      return {
        ...range,
        expanded: forced || this.#expandedSummaries.has(range.summary.id),
        forced,
        requiredText: "Messages kept open · current work",
      };
    });
    // Pending progress stays behind its run's face until the answer replaces it.
    const pendingRanges = rangeState.filter((range) => range.summary?.pending);
    const spoke = model.messages.findLastIndex(({ author }) => author === "user");
    this.#pendingOpen = pendingRanges.some((range) => range.expanded);
    // The first message no fold holds, else the first.
    const lead =
      rangeState.find((range) => range.kind === "message")?.message ??
      model.messages[0];
    // The working message stands after the range holding the last message said before
    // its words: as the face of that range where it is a progress run, else as a face
    // of its own.
    const workingAt = model.working
      ? workingPlace(rangeState, model.working.after)
      : -1;
    // The messages that say their age: the first, and each whose age, as the reader
    // reads it, differs from the message shown just above it. A checkpoint or a run's
    // face between them parts them, so the message after one says its age too.
    const dated = new Set();
    let above = null;
    for (const [at, range] of rangeState.entries()) {
      const shown =
        range.kind === "message"
          ? [range.message]
          : range.expanded
            ? range.messages
            : [];
      if (range.kind !== "message") above = null;
      for (const message of shown) {
        if (message.age !== above) dated.add(message.key);
        above = message.age;
      }
      if (range.summary?.pending || at === workingAt) above = null;
    }
    for (const message of model.messages) {
      let view = this.#messages.get(message.key);
      if (!view) {
        this.#messages.set(
          message.key,
          (view = new MessageView(this.#messageCommands)),
        );
        const { node } = view;
        node.addEventListener("beforematch", () => this.#unfold(node));
      }
      view.present(message, {
        arrived,
        dated: dated.has(message.key),
        headerControls: notice && message === lead ? notice : nothing,
      });
      // A reply still streaming at the thread's end grows at its foot as its words
      // come, as the working message does with each step (shift_watch.js).
      keeps(
        view.node,
        "data-lf-append-tail",
        message.provisional && message === model.messages.at(-1) ? "" : null,
      );
    }
    // Each message where it was said, hidden until found while a closed fold covers it.
    const placed = (key, summary = null, folded = false) => {
      const node = this.#messages.get(key).node;
      keeps(node, "data-lf-summary", summary);
      keepsHidden(node, folded && "until-found");
      return node;
    };
    // The open fold's last message, which its checkpoint's frame reaches down to.
    const feet = new Map();
    const transcript = [];
    let working = null;
    const facing = new Map();
    const messageRow = (node, key) => ({ key: `message:${key}`, body: node });
    const face = (id, reading, controls) => {
      const row = {
        key: `face:${id}`,
        body: (tail) =>
          html`<div
            class="lf-thread-working"
            data-face=${id}
            aria-live="polite"
            data-lf-live=${reading.live ? "" : nothing}
            data-lf-append-tail=${tail ? "" : nothing}
          >
            ${workingView(reading, controls)}
          </div>`,
      };
      transcript.push(row);
      return row;
    };
    for (const [at, range] of rangeState.entries()) {
      if (range.kind === "message")
        transcript.push(messageRow(placed(range.message.key), range.message.key));
      else {
        const id = range.summary.id;
        const covered = range.messages.map((message) =>
          placed(message.key, id, !range.expanded),
        );
        for (const node of covered) node.id ||= `lf-msg-${this.#id}-${++this.#named}`;
        const anchor = `--lf-fold-${this.#id}-${CSS.escape(id)}`;
        transcript.push(
          {
            key: `summary:${id}`,
            body: this.#checkpoint(range, covered, anchor),
          },
          ...covered.map((node, at) => messageRow(node, range.messages[at].key)),
        );
        feet.set(covered.at(-1), `${anchor}-foot`);
      }
      const hosts = at === workingAt;
      if (range.summary?.pending) {
        const id = range.summary.id;
        // A run the user spoke after offers its earlier steps until an answer comes.
        const kept =
          range.messages.length > 1 &&
          model.messages.indexOf(range.messages[0]) < spoke;
        const row = face(
          id,
          hosts ? model.working : stepOf(range.messages.at(-1)),
          kept ? this.#summaryToggle([range], true) : nothing,
        );
        facing.set(range.messages.at(-1).key, row);
        if (hosts) working = row;
      } else if (hosts) working = face("working", model.working);
    }
    for (const { node } of this.#messages.values()) {
      const foot = feet.get(node);
      if (foot) node.style.setProperty("--lf-fold-foot", foot);
      else node.style.removeProperty("--lf-fold-foot");
    }
    keeps(this.node, "data-lf-reflow", appends ? "append" : null);
    for (const row of transcript) row.tail = row === transcript.at(-1);
    this.#rows = this.#withFolds(transcript);
    this.#paint();
    const faceNode = (row) =>
      this.node.querySelector(`:scope > [data-face="${CSS.escape(row.key.slice(5))}"]`);
    this.#facing = new Map([...facing].map(([key, row]) => [key, faceNode(row)]));
    this.#stopWorkingExposure?.();
    this.#stopWorkingExposure = model.working?.feedback
      ? this.#commands.read.observeFeedback(
          faceNode(working).querySelector(".lf-thread-working-words"),
          {
            ...model.working.feedback,
            presentation_kind: "working_words",
            surface: model.surface,
          },
        )
      : null;
    for (const [key, fold] of this.#folding) {
      if (fold.played) continue;
      fold.played = foldBlock(fold.node);
      if (!fold.played) {
        this.#endFold(key, true);
        continue;
      }
      fold.played.finished.then(
        () => {
          if (this.#folding.get(key) === fold) this.#endFold(key, true);
        },
        () => {},
      );
    }
    if (!currentLocationToggle || currentLocationToggle.isConnected) return null;
    /** @type {(id: string) => HTMLElement | null} */
    const toggleFor = (id) =>
      this.node.querySelector(
        `.lf-summary-expand[data-summary-toggle="${CSS.escape(id)}"]`,
      );
    const succeeded = currentLocationToggle.dataset.summaryToggle;
    return (
      [succeeded, ...(successors.get(succeeded) ?? []).map(({ summary }) => summary.id)]
        .map(toggleFor)
        .find(Boolean) ?? null
    );
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
  #endFold(key, removed) {
    const fold = this.#folding.get(key);
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
      repeat(
        this.#rows,
        (row) => row.key,
        (row) => (typeof row.body === "function" ? row.body(row.tail) : row.body),
      ),
      this.node,
    );
  }

  #checkpoint(range, covered, anchor) {
    const progress = Boolean(range.summary.pending);
    return html`<section
      class="lf-thread-checkpoint"
      data-summary-id=${range.summary.id}
      data-expanded=${range.expanded}
      ?hidden=${progress && !range.expanded}
      aria-owns=${covered.map(({ id }) => id).join(" ")}
      style=${`--lf-fold-head: ${anchor}; --lf-fold-foot: ${anchor}-foot;`}
    >
      ${
        progress
          ? nothing
          : html`<div class="lf-summary-checkpoint">
              <div class="lf-summary-header">
                <div class="lf-summary-label">${range.summary.label}</div>
                ${range.forced ? nothing : this.#summaryToggle([range])}
              </div>
              ${
                range.summary.text
                  ? html`<div
                      class="lf-summary-text"
                      .innerHTML=${renderMarkdown(range.summary.text)}
                    ></div>`
                  : nothing
              }
              ${
                range.forced
                  ? html`<div class="lf-summary-required">${range.requiredText}</div>`
                  : nothing
              }
            </div>`
      }
      ${
        progress && range.forced
          ? html`<div class="lf-summary-required">${range.requiredText}</div>`
          : nothing
      }
    </section>`;
  }

  #summaryToggle(ranges, progress = false) {
    const ids = ranges.map((range) => range.summary.id);
    const expanded = ranges.every((range) => range.expanded);
    const count = ranges.reduce((total, range) => total + range.messages.length, 0);
    const subject = `${count} ${progress ? "progress" : "earlier"} message${count === 1 ? "" : "s"}`;
    const label = `${expanded ? "Hide" : "Show"} ${subject}`;
    return html`<button
      type="button"
      ${offeredAction(
        "inline",
        `lf-thread-disclosure lf-disclosure-marker lf-summary-expand${
          progress ? " lf-progress-expand" : ""
        }`,
      )}
      data-summary-toggle=${ids[0]}
      aria-expanded=${String(expanded)}
      aria-controls=${ranges
        .flatMap((range) => range.messages.map(({ key }) => this.messageNode(key)?.id))
        .filter(Boolean)
        .join(" ")}
      @click=${() => this.#setSummaryExpanded(ids, !expanded)}
    >
      <span data-room=${`Show ${subject}`}><span>${label}</span></span>
    </button>`;
  }

  #setSummaryExpanded(ids, expanded) {
    for (const id of ids) {
      if (expanded) this.#expandedSummaries.add(id);
      else this.#expandedSummaries.delete(id);
    }
    this.#repaint();
    const toggle = this.node.querySelector(
      `.lf-summary-expand[data-summary-toggle="${CSS.escape(ids[0])}"]`,
    );
    if (toggle) {
      focusDestination(toggle, "return");
      scrollThreadIntoView(this.#home(), toggle, "instant");
    }
  }

  commit() {
    const wanted = new Set(this.#model.messages.map((message) => message.key));
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
    for (const [key, { played }] of this.#folding) {
      played?.cancel();
      this.#endFold(key, true);
    }
    for (const view of this.#messages.values()) view.retire();
  }
}
