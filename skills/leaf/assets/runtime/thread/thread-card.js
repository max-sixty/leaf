/* One synchronous Lit owner for complete panel, page, outlet and margin threads.

   Immutable descriptors contain generated presentation only. Retained native editors,
   margin controls and frozen message widgets keep their mechanical lifetime outside
   those values.
   The owner alone renders its native card root and all generated descendants; a
   failed candidate is restored by presenting its committed descriptor again. */
import { nextRender } from "../rendering.js";
import { TEXT_FIELD, holdFocus } from "../focus.js";
import { html, render, repeat, nothing } from "../../vendor/browser-runtime.js";
import { turns, threadKey, threadSummary } from "./model.js";
import { anchorLabel, MessageView, messageReading } from "./messages.js";
import { reactionReading } from "./reaction-model.js";
import { offer, reachedForWords } from "../widget-elements.js";
import { keeps, keepsHidden } from "../keeps.js";
import { keys, focused } from "../keyboard/scopes.js";
import { PRESS } from "../keyboard/bindings.js";
import { wireReply, replyHasWords } from "./replies.js";
import { settleThread } from "./folding.js";
import { iconTemplate } from "../icons.js";
import { loadDraft } from "../drafts.js";
import { SAY_BOX } from "./selectors.js";
import { focusThread } from "./focus.js";
import { renderMarkdown } from "../markdown.js";
import { summaryRanges, unreadBoundaries } from "./summary-ranges.js";
import { threadAttention } from "./workflow.js";
import { seenRect } from "../geometry.js";
import { ago, shortAgo } from "../presence.js";
import { retainUserIntent } from "../user-intent.js";
import { scrollThreadIntoView } from "./reply-landing.js";
import { newsNotice } from "./held-news.js";

function quoteReading(thread, anchors) {
  const placement = anchors.placedAt(thread.id);
  const label = anchorLabel(thread.detached_from ?? thread.anchor, thread.root.about);
  if (!label) return null;
  const anchored = Boolean(thread.anchor) || Boolean(thread.detached_from);
  const found =
    !thread.detached_from && (anchors.isMarked(thread.id) || Boolean(placement));
  const outdated = anchored && placement?.status === "outdated";
  return Object.freeze({
    label,
    anchored,
    found,
    outdated,
    title: !anchored
      ? null
      : found
        ? outdated
          ? "This comment refers to an earlier data revision"
          : "Jump to this passage"
        : thread.detached_from
          ? "This passage is no longer in the version you're viewing"
          : "This passage can't be identified in the version you're viewing",
  });
}

export function threadReading(
  thread,
  surface,
  commands,
  { visible = true, kept = null, grow = false, search = null },
) {
  const panel = surface === "panel";
  const resolved = Boolean(thread.resolved);
  // A settlement in flight has already flipped `resolved`, because what the page can
  // draw of a gesture stands in the turn that sends it. The control the user is left
  // looking at is therefore the opposite one, offering to take the gesture back, and it
  // wears the word for that: a delivery status is not the result, so there is no
  // "Resolving…" state to name.
  const settling = Boolean(thread.settling);
  const kind = resolved ? "unresolve" : "resolve";
  const word = resolved ? "Reopen" : "Resolve";
  const label = resolved ? word : "Resolve thread";
  const attention = threadAttention(thread);
  const messages = turns(thread).map((message) =>
    messageReading(message, {
      panel,
      nativeAuthored: panel && commands.nativeAuthored !== false,
      reactions: reactionReading(thread, message, panel || surface === "outlet"),
      workflows: message.workflows,
    }),
  );
  return Object.freeze({
    key: threadKey(thread),
    summary: threadSummary(thread),
    // A title comes from the agent's answer or beside it, so an untitled thread
    // waits for one only while the agent's work on it is under way. A turn that
    // ended, stalled or was never picked up sends none, and the thread reads its
    // opening words.
    titlePending:
      thread.title == null &&
      thread.attention?.kind === "waiting" &&
      thread.attention.reason === "workflow",
    unreadCount: thread.unread.length,
    id: thread.id,
    // The message a reply or settlement addresses, which is not the thread's id where
    // the log lost the message that opened it.
    root: thread.root.id,
    attempt: thread.root.attempt ?? null,
    surface,
    visible,
    // A card the panel keeps though its view no longer admits it, and why ("news" or
    // "draft", thread-list-view.js, `keeping`), keeps the shape it stood in, so the news that changed it moves
    // nothing: its reply box, on which an open card's room rests; the control row above
    // its first message, where Reopen wears Resolve's face, done; and its summary's
    // status row (ThreadView).
    kept,
    grow,
    folding: false,
    search,
    quote: panel ? quoteReading(thread, commands.anchors) : null,
    resolved,
    attention,
    // A waiting thread's status is the stage of one message's workflow, which that
    // message already draws in its own header. The summary repeats it only for the
    // folded row, where no message shows; whose turn it is stays, since no message
    // says that.
    statusFolded:
      attention?.kind === "waiting" &&
      messages.some((message) => message.workflow?.id === attention.workflow?.id),
    resolvedBy:
      thread.resolved?.author === "agent"
        ? `✓ Resolved by ${thread.resolved.agent}`
        : panel
          ? ""
          : "✓ Resolved",
    settlement: Object.freeze({
      kind,
      word,
      label,
      pending: settling,
      icon: !resolved || Boolean(kept),
    }),
    reply: !resolved || Boolean(kept),
    summaries: panel ? Object.freeze(thread.summaries) : Object.freeze([]),
    messages: Object.freeze(messages),
  });
}

// The words a card's summary gives its status, whether it draws a status at all, and
// whether the open card folds it.
const summaryStatus = (model) => {
  const text = model.resolved ? "Resolved" : model.attention?.label || "";
  return { text, drawn: Boolean(text), folded: model.statusFolded };
};

function navigationSummary(navigation, model, { text: status, drawn, folded }) {
  if (!navigation) return nothing;
  const pendingTitle = model.titlePending;
  const title = model.summary.topic;
  const latest = model.summary.latest;
  const draft = Boolean(loadDraft("reply:" + model.key));
  const hasMeta = draft || drawn || model.unreadCount;
  // While a title is on its way, the title slot says so in words drawn apart from any
  // title; the theme sweeps a highlight through them while the naming is under way.
  // The meta row digests a folded card. What the open card shows elsewhere is marked
  // `data-lf-folded`: the draft stands in the reply box and the unread messages behind
  // their boundary, so typing or an arriving reply doesn't grow the row and move the
  // card under the reader.
  return html`<summary
    class="lf-thread-summary"
    title=${pendingTitle ? nothing : title}
  >
    <span class="lf-thread-topic" data-lf-pending-title=${pendingTitle ? "" : nothing}
      >${pendingTitle ? "Generating title" : title}</span
    >
    <span class=${`lf-thread-meta${hasMeta ? "" : " lf-empty"}`}>
      ${draft ? html`<span class="lf-thread-draft" data-lf-folded>Draft</span>` : nothing}
      ${
        status
          ? html`<span
              class="lf-thread-status"
              data-lf-turn=${model.attention?.kind === "needs_user" ? "user" : nothing}
              data-lf-folded=${folded ? "" : nothing}
              title=${
                model.attention?.secondary
                  ? `${status} · ${model.attention.secondary}`
                  : status
              }
              >${status}</span
            >`
          : drawn
            ? html`<span
                class="lf-thread-status"
                data-lf-folded=${folded ? "" : nothing}
                aria-hidden="true"
                >${"\u00a0"}</span
              >`
            : nothing
      }
      ${
        model.unreadCount
          ? html`<span
              class="lf-thread-unread"
              data-lf-folded
              aria-label=${`${model.unreadCount} unread`}
              >${model.unreadCount} unread</span
            >`
          : nothing
      }
    </span>
    <span class="lf-thread-trailing">
      ${
        latest
          ? html`<time
              class="lf-thread-recency"
              datetime=${latest}
              title=${`Last message activity ${new Date(latest).toLocaleString()}`}
              aria-label=${`Last message activity ${ago(latest)}`}
              >${shortAgo(latest)}</time
            >`
          : nothing
      }
    </span>
  </summary>`;
}

function readBoundary(kind) {
  if (!kind) return nothing;
  const label =
    kind === "new" ? "New since you last looked" : "End of this new section";
  return html`<div
    class="lf-read-boundary"
    data-kind=${kind}
    role="separator"
    aria-label=${label}
  ></div>`;
}

let nextViewId = 0;

export class ThreadView {
  #commands;
  #model = null;
  #messages = new Map();
  #reply = null;
  #replyShown = false;
  #draftFrame = 0;
  #outletReplyShown = null;
  #keys = new WeakSet();
  #settlements = new Map();
  #metadataActions = document.createElement("span");
  #expandedSummaries = new Set();
  #growing = false;
  #status = null;
  #navigation = null;
  #marginControls = null;
  #viewId = ++nextViewId;
  // What a thread in the page's flow holds back says so in its control row (held-news.js).
  #news = newsNotice();
  #lastMessage = null;

  constructor(surface, commands) {
    this.#commands = commands;
    this.node = document.createElement(
      surface === "outlet" || surface === "panel" ? "details" : "div",
    );
    // A panel card's disclosure is the thread list's to write, from its one choice.
    if (surface !== "panel") {
      this.node.tabIndex = -1;
      this.node.classList.add("lf-page-thread", "lf-ui");
      this.node.dataset.lfRuntime = ""; // passages.js, leafSurface
      this.node.dataset.lfGen = "1";
      this.node.dataset.lfOffer = "";
    }
    this.#metadataActions.className = "lf-thread-meta-actions";
    // A folded outlet's summary is its control row: opening it shows what it holds.
    if (surface === "outlet")
      this.node.addEventListener("toggle", () => {
        if (this.node.open) this.#model?.news?.open();
      });
    this.node.addEventListener("animationend", () => {
      this.#growing = false;
      this.node.classList.toggle("grow", false);
    });
    this.node.addEventListener("lf-reveal", (event) => {
      const message = event.detail?.target?.closest?.(".lf-msg[data-lf-summary]");
      const id = message?.dataset.lfSummary;
      if (!id || this.#expandedSummaries.has(id)) return;
      this.#expandedSummaries.add(id);
      this.present(this.#model);
    });
  }

  setNavigation(navigation) {
    this.#navigation = navigation;
  }

  setMarginControls(controls) {
    this.#marginControls = controls;
  }

  get model() {
    return this.#model;
  }

  // The last of the thread a reader can see, after which its news grows: a folded
  // outlet's summary, and otherwise its last message.
  get foot() {
    if (this.node.localName === "details" && !this.node.open)
      return this.node.querySelector(":scope > summary:not([hidden])");
    return this.#lastMessage;
  }

  present(model) {
    const prior = this.#model;
    const restoreFocus = holdFocus(this.node);
    const standing = focused();
    const priorSummaries = new Set(prior?.summaries.map(({ id }) => id) ?? []);
    // Only a summary that was not standing before can swallow what the user
    // holds or is reading, and reading geometry here forces layout.
    if (prior && model.summaries.some(({ id }) => !priorSummaries.has(id))) {
      const heldMessage = standing?.closest?.(".lf-msg[data-mid]")?.dataset.mid;
      // Being read is being on screen, on whichever surface holds the card.
      const clips = new Map();
      const beingRead = new Set(
        [...this.node.querySelectorAll(":scope .lf-msg[data-mid]")]
          .filter((message) => seenRect(message, clips))
          .map((message) => message.dataset.mid),
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
    // A kept card's summary keeps the status it stood with in its row: the words say
    // what the news did, or nothing where it left none, but the status neither comes
    // nor goes, nor folds or unfolds, so the row keeps its height.
    const status = summaryStatus(model);
    this.#status =
      model.kept && this.#status
        ? {
            text: this.#status.drawn ? status.text : "",
            drawn: this.#status.drawn,
            folded: this.#status.folded,
          }
        : status;
    const reply = model.reply || replyHasWords(model.key);
    this.#replyShown = reply;
    if (model.news) this.#news.set(model.news);
    const news = model.news ? this.#news.node : nothing;
    const panel = model.surface === "panel";
    const navigation = panel ? this.#navigation : null;
    this.node.classList.toggle("lf-thread-compact", Boolean(navigation));
    const hiding = !model.visible && !model.folding && !this.node.hidden;
    if (hiding) this.retire();
    keepsHidden(this.node, !model.visible && !model.folding);
    this.#growing ||= !prior && model.grow;
    this.node.classList.toggle("lf-going", model.folding);
    this.node.classList.toggle("lf-thread", panel && !model.folding);
    this.node.classList.toggle("grow", this.#growing && !model.folding);
    this.node.toggleAttribute("inert", model.folding);
    keeps(this.node, panel ? "data-id" : "data-thread", model.id);
    keeps(this.node, "data-resolved", model.resolved);
    keeps(this.node, "data-attempt", model.attempt || null);
    if (model.surface === "outlet" && this.#outletReplyShown !== reply) {
      this.node.toggleAttribute("open", reply);
      this.#outletReplyShown = reply;
    }
    const wanted = new Set(model.messages.map((message) => message.key));
    for (const [key, view] of this.#messages) if (!wanted.has(key)) view.retire();
    const settlement = model.settlement ? this.#settlement(model) : nothing;
    const marginControls = model.surface === "margin" ? this.#marginControls : null;
    let headerActions = null;
    if (!model.resolved || reply || model.folding || marginControls) {
      const actions = marginControls
        ? [marginControls.nav, settlement, marginControls.close].filter(Boolean)
        : [settlement];
      for (const child of [...this.#metadataActions.children])
        if (!actions.includes(child)) child.remove();
      actions.forEach((control, index) => {
        if (this.#metadataActions.children[index] !== control)
          this.#metadataActions.insertBefore(
            control,
            this.#metadataActions.children[index] ?? null,
          );
      });
      headerActions = this.#metadataActions;
    }
    const describedRanges = summaryRanges(model.messages, model.summaries);
    const summaries = new Set(model.summaries.map(({ id }) => id));
    for (const id of this.#expandedSummaries)
      if (!summaries.has(id)) this.#expandedSummaries.delete(id);
    const rangeState = describedRanges.map((range) => {
      if (range.kind === "message") return range;
      const forced = Boolean(range.summary.protected?.length);
      const searchMatch = range.messages.some((message) =>
        model.search?.messages.includes(message.id),
      );
      return {
        ...range,
        expanded:
          forced || searchMatch || this.#expandedSummaries.has(range.summary.id),
        forced: forced || searchMatch,
        requiredText: searchMatch
          ? "Matching messages kept open"
          : "Messages kept open · current work",
      };
    });
    const boundaries = panel ? unreadBoundaries(rangeState) : new Map();
    const messages = model.messages.map((message, index) => {
      let view = this.#messages.get(message.key);
      if (!view)
        this.#messages.set(message.key, (view = new MessageView(this.#commands)));
      view.present(message, index === 0 && Boolean(headerActions));
      return { key: message.key, node: view.node, header: view.header };
    });
    this.#lastMessage = messages.at(-1)?.node ?? null;
    const messageNodes = new Map(messages.map(({ key, node }) => [key, node]));
    const ranges = rangeState.map((range) => {
      if (range.kind === "message") {
        const node = messageNodes.get(range.message.key);
        delete node.dataset.lfSummary;
        return { ...range, node };
      }
      const nodes = range.messages.map((message) => {
        const node = messageNodes.get(message.key);
        keeps(node, "data-lf-summary", range.summary.id);
        return node;
      });
      return {
        ...range,
        nodes,
      };
    });
    const hoistedRoot = headerActions ? messages[0]?.key : null;
    const markerFor = (key) =>
      readBoundary(key === hoistedRoot ? null : boundaries.get(key));
    const transcript = repeat(
      ranges,
      (range) => range.key,
      (range) =>
        range.kind === "message"
          ? html`${markerFor(range.message.key)}${range.node}`
          : this.#summaryRange(range, markerFor),
    );
    if (reply && !this.#reply) this.#reply = this.#createReply(model);
    const body = html`
      ${
        model.quote
          ? html`<header class="lf-thread-head">
              <blockquote
                class=${`lf-quote${model.quote.anchored && !model.quote.found ? " detached" : ""}`}
                role=${model.quote.anchored ? "button" : nothing}
                tabindex=${model.quote.anchored ? "0" : nothing}
                aria-disabled=${model.quote.anchored ? String(!model.quote.found) : nothing}
                title=${model.quote.title ?? nothing}
                @click=${this.#returnToQuote}
              >
                <span class="lf-quote-label">${model.quote.label}</span>
                ${
                  model.quote.outdated
                    ? html`<span class="lf-anchor-status">Earlier data</span>`
                    : nothing
                }
              </blockquote>
            </header>`
          : nothing
      }
      ${readBoundary(hoistedRoot ? boundaries.get(hoistedRoot) : null)}
      ${
        headerActions && messages[0]
          ? html`<div class="lf-thread-root-meta">
              ${messages[0].header}${news} ${headerActions}
            </div>`
          : nothing
      }
      ${
        model.surface === "margin"
          ? html`<div class="lf-thread-transcript">${transcript}</div>`
          : transcript
      }
    `;
    render(
      html`
        ${navigationSummary(navigation, model, this.#status)}
        ${
          model.surface === "outlet"
            ? html`<summary
                class="lf-page-thread-summary lf-ui"
                data-lf-gen="1"
                data-lf-offer=""
                ?hidden=${!model.resolved}
              >
                ${
                  model.news?.reopened
                    ? model.news.label
                    : html`Resolved · ${model.messages.length}
                      message${model.messages.length === 1 ? "" : "s"}${
                        model.news ? ` · ${model.news.label}` : ""
                      }`
                }
              </summary>`
            : nothing
        }
        ${panel ? html`<div class="lf-thread-content">${body}</div>` : body}
        ${reply ? this.#reply.node : nothing}
        ${
          model.resolved && !reply && !model.folding && !marginControls
            ? html`<div
                class=${panel ? "lf-thread-actions" : "lf-page-thread-resolved lf-ui"}
              >
                <span
                  >${
                    model.resolvedBy
                      ? html`<span class=${panel ? "lf-resolved-by" : nothing}
                          >${model.resolvedBy}</span
                        >`
                      : nothing
                  }</span
                >
                ${news}${settlement}
              </div>`
            : nothing
        }
      `,
      this.node,
    );
    this.#wireKeys();
    // A summary gathering the message the user stands on moves it; a page thread whose
    // render took their place puts them in its reply, or on the thread itself.
    restoreFocus?.(
      !panel &&
        (() =>
          this.#commands.landInThread(this.node.querySelector(SAY_BOX) ?? this.node)),
    );
    return this.node;
  }

  #summaryRange(range, markerFor) {
    const count = range.messages.length;
    const unread = range.messages.filter((message) => message.unread).length;
    const id = range.summary.id;
    const originalsId = `lf-summary-originals-${this.#viewId}-${id}`;
    return html`<section
      class="lf-thread-checkpoint"
      data-summary-id=${id}
      data-expanded=${String(range.expanded)}
    >
      <div class="lf-summary-checkpoint">
        <div class="lf-summary-label">
          Earlier
          discussion${
            unread && !range.expanded
              ? html`<span class="lf-summary-unread">
                  · ${unread} unread original${unread === 1 ? "" : "s"}</span
                >`
              : nothing
          }
        </div>
        <div
          class="lf-summary-text"
          .innerHTML=${renderMarkdown(range.summary.text)}
        ></div>
        ${
          range.forced
            ? html`<div class="lf-summary-required">${range.requiredText}</div>`
            : html`<button
                type="button"
                class="lf-summary-expand"
                aria-expanded=${String(range.expanded)}
                aria-controls=${originalsId}
                @click=${() => this.#setSummaryExpanded(id, !range.expanded)}
              >
                ${range.expanded ? "Collapse" : "Show"} ${count} earlier
                message${count === 1 ? "" : "s"}
              </button>`
        }
      </div>
      <div id=${originalsId} class="lf-summary-originals" ?hidden=${!range.expanded}>
        ${repeat(
          range.messages,
          (message) => message.key,
          (message) =>
            html`${markerFor(message.key)}${range.nodes[range.messages.indexOf(message)]}`,
        )}
      </div>
    </section>`;
  }

  #setSummaryExpanded(id, expanded) {
    if (expanded) this.#expandedSummaries.add(id);
    else this.#expandedSummaries.delete(id);
    this.present(this.#model);
    this.node
      .querySelector(
        `.lf-thread-checkpoint[data-summary-id="${CSS.escape(id)}"] .lf-summary-expand`,
      )
      ?.focus({ preventScroll: true });
  }

  // Resolve is a check; Reopen is a word, or, where it stands in Resolve's place, the
  // check drawn done, at Resolve's size.
  #settlement(model) {
    const state = model.settlement;
    const reopen = state.kind === "unresolve";
    const face = `${state.kind}${state.icon ? " icon" : ""}`;
    let button = this.#settlements.get(face);
    if (!button) {
      button = offer(
        "button",
        `lf-btn ${reopen ? "lf-reopen" : "lf-resolve"} ${state.icon ? "lf-icon-action" : "lf-thread-action"}`,
      );
      button.type = "button";
      button.onclick = this.#settle;
      this.#settlements.set(face, button);
      const word = reopen ? "Reopen" : "Resolve";
      keys(button, `On a thread's ${word} button`, [
        {
          id: reopen ? "thread.reopen" : "thread.resolve",
          keys: PRESS,
          does: `${word} it`,
          line: word.toLowerCase(),
          when: () => !this.#model.settlement?.pending,
          run: () => button.click(),
        },
      ]);
    }
    keeps(button, "aria-disabled", state.pending || model.folding);
    keeps(button, "aria-busy", state.pending && !model.folding);
    if (state.icon) {
      const label = model.folding ? "Resolved" : state.label;
      keeps(button, "aria-label", label);
      keeps(button, "title", label);
    }
    render(state.icon ? iconTemplate("check", "lf-action-icon") : state.label, button);
    return button;
  }

  #settle = () => {
    const model = this.#model;
    if (model.folding) return;
    void settleThread({
      parent: () => this.#model.root,
      key: model.key,
      resolved: model.resolved,
      prepareLanding:
        model.surface === "panel"
          ? () => this.#prepareLanding(model.resolved)
          : model.surface === "margin"
            ? model.resolved
              ? null
              : this.#marginControls?.prepareLanding
            : this.#prepareInlineLanding,
      ...this.#commands.settlement,
    }).catch(() => {});
  };

  // A thread on the page changes shape as it settles: a resolved outlet folds to its
  // summary, and a reopened one unfolds under it. Where the user still stands in it, land
  // it around their focus, which a thread too tall to show leaves where it is.
  #prepareInlineLanding = () => {
    const mayLand = retainUserIntent({
      source: this.node,
      available: () => this.node.isConnected,
    });
    const land = (may = mayLand) => {
      if (!may() || !this.node.contains(focused())) return false;
      scrollThreadIntoView(this.node, focused());
      return true;
    };
    return { optimistic: () => land(), reverse: land };
  };

  #returnToQuote = (event) => {
    const model = this.#model;
    if (!model.quote?.anchored || !model.quote.found) return;
    if (event.detail !== 0 && reachedForWords(event.currentTarget)) return;
    const travel = this.#commands.travel;
    // The trip promises to show the passage, so it clears the panel where the panel
    // stands over most of it and leaves the panel open beside one seen where it stands.
    travel.scrollToThread(model.id, {
      focus: "reply",
    });
  };

  #wireKeys() {
    const quote = this.node.querySelector(
      ":scope > .lf-thread-content > .lf-thread-head > .lf-quote, " +
        ":scope > .lf-thread-head > .lf-quote",
    );
    if (quote && !this.#keys.has(quote)) {
      this.#keys.add(quote);
      keys(quote, "On a comment's quoted passage", [
        {
          id: "passage.return",
          keys: PRESS,
          does: "Return to the quoted passage on the page",
          line: "return to the passage",
          when: () => Boolean(this.#model.quote?.found),
          run: () => quote.click(),
        },
      ]);
    }
  }

  #createReply(model) {
    const panel = model.surface === "panel";
    const row = offer("div", panel ? "lf-compose" : "lf-say");
    // The reply is its editor on every surface, at rest too: `c`, its key badge and
    // landing all name this box, so nothing stands in for it on screen.
    const input = offer(TEXT_FIELD);
    input.name = "reply";
    const send = offer("button", panel ? "lf-btn lf-thread-send" : "lf-btn", "Send");
    row.append(input, send);
    if (panel)
      input.lfRevealReply = () =>
        this.#commands.listRoot.revealNavigation(this.#model.id);
    const lifetime = wireReply(model.key, input, send, {
      ...this.#commands.reply,
      onDraftLoaded: () => {
        // Initial construction is already painting this reading; mirrored edits
        // arrive later and must refresh the collapsed row's Draft indication.
        if (!this.#reply) return;
        if (panel) this.#navigation.draftChanged();
        else if (this.#replyShown !== (this.#model.reply || replyHasWords(model.key)))
          this.#draftFrame ||= nextRender(() => {
            this.#draftFrame = 0;
            if (this.#reply) this.present(this.#model);
          });
      },
    });
    return { node: row, dispose: lifetime.dispose };
  }

  #prepareLanding(reopen) {
    const { travel, openThreads } = this.#commands;
    const mayLand = travel.retainPanelLanding(this.node);
    const shownCard = () =>
      !this.node.hidden && this.node.isConnected ? this.node : null;
    let mayRestore = () => false;
    if (!reopen) {
      const at = openThreads().indexOf(this.node);
      return {
        optimistic: () => {
          if (!mayLand()) return false;
          const kept = openThreads();
          const destination = kept[at] ?? kept[at - 1] ?? this.#commands.listRoot;
          if (destination.matches?.(".lf-thread")) {
            this.#commands.listRoot.revealNavigation(destination.dataset.id);
            focusThread(destination, { preventScroll: true });
          } else destination.focus({ preventScroll: true });
          mayRestore = travel.retainPanelLanding(destination);
          return true;
        },
        reverse: (may = mayRestore) => {
          if (may() && mayLand.available()) {
            const card = shownCard();
            if (card) focusThread(card, { preventScroll: true });
          }
        },
      };
    }
    const narrowing = travel.retainNarrowing();
    return {
      optimistic: async () => {
        if (!mayLand()) return false;
        const arriving = travel.showThread(this.#model.id);
        narrowing.replaced();
        if (!(await arriving)) return false;
        const destination = shownCard();
        if (destination) mayRestore = travel.retainPanelLanding(destination);
        return Boolean(destination);
      },
      // The filter the reopen cleared goes back with the thread, while Threads is open.
      // An undo's intent governs the whole reversal, so a later input wins over both
      // halves. A refusal has none: the narrowing's own guard decides the filter, and
      // the landing's decides the focus.
      reverse: async (may = null) => {
        if (!mayLand.available() || (may && !may())) return;
        const restoreFocus = (may ?? mayRestore)();
        await narrowing.restore(async () => {
          if (restoreFocus)
            await travel.showThread(this.#model.id, { focus: "thread" });
        });
      },
    };
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
    if (!this.#replyShown && this.#reply) {
      this.#reply.dispose();
      this.#reply = null;
    }
  }

  retire() {
    for (const view of this.#messages.values()) view.retire();
  }

  dispose() {
    this.retire();
    this.#reply?.dispose();
    this.#reply = null;
  }
}
