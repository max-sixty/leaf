/* A thread's messages as every reader of a whole thread draws them: a card on the page
   or in the margin (thread-card.js), and the floating panel's view of a thread through
   a primary reader's transcript part (primary-reader.js). The reader around it draws
   the thread's head, controls and reply box; this owner draws only the transcript.

   - Each turn is one MessageView, which shows whether its version is unread and
     reports its exposure to read tracking (read.js), so a reply counts as read the same
     way in every reader.
   - A summary the agent wrote folds the turns it covers behind its checkpoint; the
     progress an answer folded stands behind "Show N progress messages" at that answer's
     head; progress no answer has folded yet stands behind the working message, the dim
     line at the transcript's foot (`workingView`), opened where a streaming answer's
     head offers it.
   - The originals of each fold are retained containers whose message lists are placed
     together with the transcript's (`setChildLists`), so a message a summary gathers or
     releases moves straight across with its frames and focus. Rejected: nesting the
     originals in a `repeat` inside the transcript's `repeat`, which rebuilt a gathered
     message's row and reloaded a frame in it.
   - A fold that arrives over a message the user stands on or reads stays open, and
     progress the reader opened stays open when a fold takes it over or splits it. */
import { setChildLists } from "../dom-children.js";
import { focusDestination, focused } from "../focus.js";
import { html, render, nothing } from "/vendor/browser-runtime.js";
import { MessageView } from "./messages.js";
import { keeps, keepsHidden } from "../keeps.js";
import { renderMarkdown } from "../markdown.js";
import { summaryRanges, withPendingProgress } from "./summary-ranges.js";
import { growthAfterIsSeen, growthIsSeen, seenRect } from "../geometry.js";
import { scrollThreadIntoView } from "./reply-landing.js";
import { scrollerFor } from "../reading-regions.js";
import { moveScrollerBy, placeKept } from "../scrolling.js";

// The working message's contents: the step of work in hand, drawn as a message is,
// with who is working and when those words were posted at its head, but dimmed under
// a passing sheen while the work runs, as a title being generated is. It shows the
// latest step alone: the earlier ones are superseded, and the answer that folds them
// offers them behind its own disclosure. It is the transcript's last child, so it
// stands at the conversation's inset on every surface and scrolls with it. Its head
// wears a message head's face but not its class, since it is no message: a message
// head's places (a margin's sticky head, held news) skip it.
function workingView(working) {
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
              ${working.condition}</span
            >`
          : nothing
      }
    </div>
    <div class="lf-thread-working-words">${working.words}</div>`;
}

let nextTranscriptId = 0;
export class Transcript {
  #commands;
  #messageCommands;
  #repaint;
  #home;
  #model = null;
  #messages = new Map();
  #working = document.createElement("div");
  #stopWorkingExposure = null;
  // Each pending progress range's covered message ids, as last drawn, so a fold that
  // takes the range over can take its disclosure state with it.
  #pendingCovers = new Map();
  #pendingOpen = false;
  #checkpoints = new Map();
  #expandedSummaries = new Set();
  #id = ++nextTranscriptId;

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
    this.#working.className = "lf-thread-working";
    // The transcript's last child, growing at its foot as steps come (shift_watch.js).
    this.#working.dataset.lfAppendTail = "";
    this.#working.setAttribute("aria-live", "polite");
    // A route revealing a message a fold holds opens the fold (widget-elements.js,
    // `reveal`).
    this.node.addEventListener("lf-reveal", (event) => {
      /** @type {HTMLElement | undefined} */
      const message = event.detail?.target?.closest?.(".lf-msg[data-lf-summary]");
      const id = message?.dataset.lfSummary;
      if (!id || this.#expandedSummaries.has(id)) return;
      this.#expandedSummaries.add(id);
      this.#repaint();
    });
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

  // The checkpoint a summary stands in.
  summaryNode(id) {
    return this.#checkpoints.get(id)?.node ?? null;
  }

  // The last node the transcript shows, which is the working message while one stands.
  // Progress behind the working message and originals behind a closed checkpoint stand
  // in the transcript unrendered, so the last message alone may have no box.
  get foot() {
    return [...this.node.children].findLast((node) => node.checkVisibility()) ?? null;
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
  // a fold that comes or goes over what is in sight.
  newsMoves({ news, changed, folds }, { followed = null } = {}) {
    return (
      [
        ...[...changed].map((key) => this.messageNode(key)),
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
   * the one the user stood on, where this draw replaced it, as the answer's head takes
   * progress over from the working message.
   * @returns {HTMLElement | null}
   */
  present(model, { arrived = false, appends = false, notice = null } = {}) {
    const prior = this.#model;
    const standing = focused();
    const priorSummaries = new Set(prior?.summaries.map(({ id }) => id) ?? []);
    // Only a summary that was not present before can swallow what the user
    // holds or is reading, and reading geometry here forces layout.
    if (prior && model.summaries.some(({ id }) => !priorSummaries.has(id))) {
      const heldMessage = prior.messages.find(({ key }) =>
        this.#messages.get(key)?.node.contains(standing),
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
    for (const [key, view] of this.#messages) if (!wanted.has(key)) view.retire();
    // A resolved thread holds no work in hand, so its progress stands as messages.
    const summarized = summaryRanges(model.messages, model.summaries);
    const describedRanges = model.resolved
      ? summarized
      : withPendingProgress(summarized);
    const summaries = new Set(
      describedRanges.flatMap((range) => (range.summary ? [range.summary.id] : [])),
    );
    // Progress the reader opened stays open when a fold takes it over or splits it, the
    // answer's or a summary's: every range that now covers one of its messages takes
    // over the disclosure it stood behind, and so does the toggle the reader stood on.
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
    const standingToggle = this.node.querySelector(".lf-summary-expand:focus");
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
    // The progress no answer has folded yet stands hidden behind the working message,
    // open only where a streaming answer's disclosure opens it.
    const pendingRanges = rangeState.filter((range) => range.summary?.pending);
    this.#pendingOpen = pendingRanges.some((range) => range.expanded);
    // Automatic progress folds name the reply that completed them. Its header owns
    // their disclosure, even when a user's intervening reply split the originals. An
    // answer still streaming at the thread's end holds the pending progress's
    // disclosure the same way, until the fold it brings takes the progress over.
    const progressByReply = new Map();
    const streaming = model.messages.at(-1);
    if (streaming?.provisional && pendingRanges.length)
      progressByReply.set(streaming.id, pendingRanges);
    for (const range of rangeState) {
      if (range.kind !== "summary" || !range.summary.trigger || range.forced) continue;
      const trigger = range.summary.trigger;
      if (!progressByReply.has(trigger)) progressByReply.set(trigger, []);
      progressByReply.get(trigger).push(range);
    }
    // The first message no fold holds, else the first.
    const lead =
      rangeState.find((range) => range.kind === "message")?.message ??
      model.messages[0];
    for (const message of model.messages) {
      let view = this.#messages.get(message.key);
      if (!view)
        this.#messages.set(
          message.key,
          (view = new MessageView(this.#messageCommands)),
        );
      const toggle = progressByReply.has(message.id)
        ? this.#summaryToggle(progressByReply.get(message.id), true)
        : nothing;
      view.present(message, {
        arrived,
        headerControls: notice && message === lead ? html`${notice}${toggle}` : toggle,
      });
      // A reply still streaming at the thread's end grows at its foot as its words
      // come, as the working message does with each step (shift_watch.js).
      keeps(
        view.node,
        "data-lf-append-tail",
        message.provisional && message === model.messages.at(-1) ? "" : null,
      );
    }
    // Each message, in the transcript or its checkpoint.
    const placed = (key, summary) => {
      const node = this.#messages.get(key).node;
      keeps(node, "data-lf-summary", summary);
      return [node];
    };
    const checkpoints = new Map();
    const transcript = [];
    const transcriptLists = [[this.node, transcript]];
    for (const range of rangeState) {
      if (range.kind === "message") {
        transcript.push(...placed(range.message.key, null));
        continue;
      }
      const id = range.summary.id;
      const checkpoint = this.#checkpoints.get(id) ?? this.#checkpoint(id);
      checkpoints.set(id, checkpoint);
      this.#paintCheckpoint(checkpoint, range);
      transcript.push(checkpoint.node);
      transcriptLists.push([
        checkpoint.originals,
        range.messages.flatMap((message) => placed(message.key, id)),
      ]);
    }
    if (model.working) {
      keeps(this.#working, "data-lf-live", model.working.live ? "" : null);
      render(workingView(model.working), this.#working);
      transcript.push(this.#working);
    }
    this.#stopWorkingExposure?.();
    this.#stopWorkingExposure = model.working?.feedback
      ? this.#commands.read.observeFeedback(
          this.#working.querySelector(".lf-thread-working-words"),
          {
            ...model.working.feedback,
            presentation_kind: "working_words",
            surface: model.surface,
          },
        )
      : null;
    this.#checkpoints = checkpoints;
    keeps(this.node, "data-lf-reflow", appends ? "append" : null);
    setChildLists(transcriptLists);
    if (!standingToggle || standingToggle.isConnected) return null;
    /** @type {(id: string) => HTMLElement | null} */
    const toggleFor = (id) =>
      this.node.querySelector(
        `.lf-summary-expand[data-summary-toggle="${CSS.escape(id)}"]`,
      );
    const succeeded = standingToggle.dataset.summaryToggle;
    return (
      [succeeded, ...(successors.get(succeeded) ?? []).map(({ summary }) => summary.id)]
        .map(toggleFor)
        .find(Boolean) ?? null
    );
  }

  // A summary's checkpoint: a retained section whose head the template draws, and
  // whose originals hold the retained messages the summary covers.
  #checkpoint(id) {
    const node = document.createElement("section");
    node.className = "lf-thread-checkpoint";
    node.dataset.summaryId = id;
    const originals = document.createElement("div");
    originals.id = `lf-summary-originals-${this.#id}-${id}`;
    originals.className = "lf-summary-originals";
    node.append(originals);
    return { node, originals };
  }

  #paintCheckpoint({ node, originals }, range) {
    const progress = Boolean(range.summary.trigger || range.summary.pending);
    keeps(node, "data-expanded", range.expanded);
    keepsHidden(node, progress && !range.expanded);
    keepsHidden(originals, !range.expanded);
    render(
      html`${
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
      }`,
      node,
      { renderBefore: originals },
    );
  }

  #summaryToggle(ranges, progress = false) {
    const ids = ranges.map((range) => range.summary.id);
    const expanded = ranges.every((range) => range.expanded);
    const count = ranges.reduce((total, range) => total + range.messages.length, 0);
    const subject = `${count} ${progress ? "progress" : "earlier"} message${count === 1 ? "" : "s"}`;
    const label = `${expanded ? (progress ? "Hide" : "Collapse") : "Show"} ${subject}`;
    return html`<button
      type="button"
      class="lf-thread-disclosure lf-summary-expand ${
        progress ? "lf-progress-expand" : ""
      }"
      data-lf-room=${progress ? `Show ${subject}` : nothing}
      data-summary-toggle=${ids[0]}
      aria-expanded=${String(expanded)}
      aria-controls=${ids
        .map((id) => `lf-summary-originals-${this.#id}-${id}`)
        .join(" ")}
      @click=${() => this.#setSummaryExpanded(ids, !expanded)}
    >
      ${progress ? html`<span>${label}</span>` : label}
    </button>`;
  }

  // A press on a fold's disclosure opens or closes it and stays under the pointer.
  // Progress opens above the answer whose head holds its disclosure, so its scroller
  // takes back what that carries the press down by. Scroll anchoring would, but not at
  // a scroller's start, where a view opened on a short thread stands.
  #setSummaryExpanded(ids, expanded) {
    const toggleOf = () =>
      this.node.querySelector(
        `.lf-summary-expand[data-summary-toggle="${CSS.escape(ids[0])}"]`,
      );
    const stood = toggleOf()?.getBoundingClientRect().top;
    for (const id of ids) {
      if (expanded) this.#expandedSummaries.add(id);
      else this.#expandedSummaries.delete(id);
    }
    this.#repaint();
    const toggle = toggleOf();
    if (!toggle) return;
    if (stood !== undefined) {
      const box = scrollerFor(toggle);
      moveScrollerBy(box, toggle.getBoundingClientRect().top - stood);
      placeKept(box);
    }
    focusDestination(toggle, "return");
    scrollThreadIntoView(this.#home(), toggle, "instant");
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
    for (const view of this.#messages.values()) view.retire();
  }
}
