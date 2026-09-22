/* One synchronous Lit owner for complete panel, page, outlet and margin threads.

   Immutable descriptors contain generated presentation only. Retained native editors
   and frozen message widgets keep their mechanical lifetime outside those values.
   The owner alone renders its native card root and all generated descendants; a
   failed candidate is restored by presenting its committed descriptor again. */
import { html, render, repeat, nothing } from "../../vendor/browser-runtime.js";
import { turns, threadKey, threadSummary } from "./model.js";
import { anchorLabel, MessageView, messageReading } from "./messages.js";
import { reactionReading } from "./reaction-strips.js";
import { offer, reachedForWords } from "../widget-elements.js";
import { keys, focused } from "../keyboard/scopes.js";
import { PRESS } from "../keyboard/bindings.js";
import { wireReply } from "./replies.js";
import { settleThread } from "./folding.js";
import { groupFor, pageOutline } from "./placement.js";
import { iconTemplate } from "../icons.js";
import { loadDraft } from "../drafts.js";
import { SAY_BOX } from "./selectors.js";
import { focusThread } from "./focus.js";
import { renderMarkdown } from "../markdown.js";
import { summaryRanges } from "./summary-ranges.js";
import { threadAttention } from "./workflow.js";

function quoteReading(thread, anchors, outline) {
  const group = groupFor(thread, outline, anchors.placedAt);
  const placement = anchors.placedAt(thread.root.id);
  const segments = placement?.segments ?? [];
  const label =
    group.target &&
    segments.length &&
    segments.every(({ node }) => group.target.contains(node))
      ? ""
      : anchorLabel(
          thread.detached_from ?? thread.anchor,
          thread.root.about,
          group.target,
        );
  if (!label) return null;
  const anchored = Boolean(thread.anchor) || Boolean(thread.detached_from);
  const found =
    !thread.detached_from && (anchors.isMarked(thread.root.id) || Boolean(placement));
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
  { visible = true, grow = false, outline = null, search = null },
) {
  const panel = surface === "panel";
  const resolved = Boolean(thread.resolved);
  // A settlement in flight has already flipped `resolved`, because what the page can
  // draw of a gesture stands in the turn that sends it. The control the reader is left
  // looking at is therefore the opposite one, offering to take the gesture back, and it
  // wears the word for that: a delivery status is not the result, so there is no
  // "Resolving…" state to name.
  const settling = Boolean(thread.settling);
  const kind = resolved ? "unresolve" : "resolve";
  const word = resolved ? "Reopen" : "Resolve";
  const label = resolved ? word : "Resolve thread";
  return Object.freeze({
    key: threadKey(thread),
    summary: threadSummary(thread),
    id: thread.root.id,
    attempt: thread.root.attempt ?? null,
    surface,
    visible,
    grow,
    folding: false,
    search,
    quote: panel
      ? quoteReading(thread, commands.anchors, outline ?? pageOutline())
      : null,
    resolved,
    awaitsReader: thread.awaits_reader,
    attention: threadAttention(thread),
    resolvedBy:
      thread.resolved?.author === "agent"
        ? `✓ Resolved by ${thread.resolved.agent || "Agent"}`
        : panel
          ? ""
          : "✓ Resolved",
    settlement: Object.freeze({ kind, word, label, pending: settling }),
    reply: !resolved && (panel || thread.root.response?.kind !== "version"),
    summaries: panel ? Object.freeze(thread.summaries ?? []) : Object.freeze([]),
    messages: Object.freeze(
      turns(thread).map((message) =>
        messageReading(message, {
          panel,
          reactions: reactionReading(thread, message, panel || surface === "outlet"),
          workflows: message.workflows,
        }),
      ),
    ),
  });
}

function navigationSummary(navigation, model) {
  if (!navigation) return nothing;
  const title = model.summary.topic || model.quote?.label || "Thread";
  const count = model.summary.count;
  const status = model.resolved ? "Resolved" : model.attention?.label || "";
  const draft = Boolean(loadDraft("reply:" + model.key)?.trim());
  return html`<summary class="lf-thread-summary" title=${title}>
    ${iconTemplate("next", "lf-thread-chevron")}
    <span class="lf-thread-topic">${title}</span>
    <span class="lf-thread-draft">${draft ? "Draft" : nothing}</span>
    <span
      class="lf-thread-count"
      aria-label=${`${count} ${count === 1 ? "message" : "messages"}`}
      >${count}</span
    >
    <span
      class="lf-thread-status"
      data-lf-turn=${model.attention?.kind === "needs_reader" ? "reader" : nothing}
      title=${
        model.attention?.secondary ? `${status} · ${model.attention.secondary}` : status
      }
      >${status}</span
    >
  </summary>`;
}

export class ThreadView {
  #commands;
  #model = null;
  #messages = new Map();
  #reply = null;
  #summaryResolved = null;
  #keys = new WeakSet();
  #settlements = new Map();
  #metadataActions = document.createElement("span");
  #expandedSummaries = new Set();
  #growing = false;
  #navigation = null;

  constructor(surface, commands) {
    this.#commands = commands;
    this.node = document.createElement(
      surface === "outlet" || surface === "panel" ? "details" : "div",
    );
    if (surface === "panel") this.node.name = "threads";
    else this.node.tabIndex = -1;
    this.node.addEventListener("animationend", () => {
      this.#growing = false;
      this.node.classList.remove("grow");
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

  get model() {
    return this.#model;
  }

  present(model) {
    const prior = this.#model;
    const standing = focused();
    const heldFocus = this.node.contains(standing);
    let summaryReplacedFocusedMessage = false;
    const priorSummaries = new Set(prior?.summaries.map(({ id }) => id) ?? []);
    // Only a summary that was not standing before can swallow what the reader
    // holds or is reading, and reading geometry here forces layout.
    if (prior && model.summaries.some(({ id }) => !priorSummaries.has(id))) {
      const heldMessage = standing?.closest?.(".lf-msg[data-mid]")?.dataset.mid;
      const scrollport = this.node.closest("leaf-thread-list");
      const boundary = scrollport?.getBoundingClientRect();
      const beingRead = new Set(
        [...this.node.querySelectorAll(":scope .lf-msg[data-mid]")]
          .filter((message) => {
            if (!message.getClientRects().length || !boundary) return false;
            const box = message.getBoundingClientRect();
            return box.bottom > boundary.top && box.top < boundary.bottom;
          })
          .map((message) => message.dataset.mid),
      );
      for (const summary of model.summaries) {
        if (priorSummaries.has(summary.id)) continue;
        if (summary.covers.includes(heldMessage)) summaryReplacedFocusedMessage = true;
        if (
          summary.covers.includes(heldMessage) ||
          summary.covers.some((id) => beingRead.has(id))
        )
          this.#expandedSummaries.add(summary.id);
      }
    }
    this.#model = model;
    const panel = model.surface === "panel";
    const navigation = panel ? this.#navigation : null;
    this.node.classList.toggle("lf-thread-compact", Boolean(navigation));
    const hiding = !model.visible && !model.folding && !this.node.hidden;
    if (hiding) this.retire();
    this.node.hidden = !model.visible && !model.folding;
    this.#growing ||= !prior && model.grow;
    this.node.classList.toggle("lf-going", model.folding);
    this.node.classList.toggle("lf-thread", panel && !model.folding);
    this.node.classList.toggle("grow", this.#growing && !model.folding);
    if (!panel) {
      this.node.classList.add("lf-conversation-thread", "lf-ui");
      this.node.dataset.lfGen = "1";
      this.node.dataset.lfOffer = "";
    }
    this.node.inert = model.folding;
    this.node.setAttribute(panel ? "data-id" : "data-thread", model.id);
    this.node.dataset.resolved = String(model.resolved);
    if (model.attempt) this.node.dataset.attempt = model.attempt;
    else delete this.node.dataset.attempt;
    if (model.surface === "outlet" && this.#summaryResolved !== model.resolved) {
      this.node.open = !model.resolved;
      this.#summaryResolved = model.resolved;
    }
    const wanted = new Set(model.messages.map((message) => message.key));
    for (const [key, view] of this.#messages) if (!wanted.has(key)) view.retire();
    const settlement = this.#settlement(model);
    let headerActions = null;
    if (!model.resolved || model.folding) {
      this.#metadataActions.className = "lf-thread-meta-actions";
      const actions = [settlement];
      if (
        actions.length !== this.#metadataActions.children.length ||
        actions.some(
          (action, index) => this.#metadataActions.children[index] !== action,
        )
      )
        this.#metadataActions.replaceChildren(...actions);
      headerActions = this.#metadataActions;
    }
    const describedRanges = summaryRanges(model.messages, model.summaries);
    const messages = model.messages.map((message, index) => {
      let view = this.#messages.get(message.key);
      if (!view)
        this.#messages.set(message.key, (view = new MessageView(this.#commands)));
      view.present(message, index === 0 && Boolean(headerActions));
      return { key: message.key, node: view.node, header: view.header };
    });
    const messageNodes = new Map(messages.map(({ key, node }) => [key, node]));
    const summaries = new Set(model.summaries.map(({ id }) => id));
    for (const id of this.#expandedSummaries)
      if (!summaries.has(id)) this.#expandedSummaries.delete(id);
    const ranges = describedRanges.map((range) => {
      if (range.kind === "message") {
        const node = messageNodes.get(range.message.key);
        delete node.dataset.lfSummary;
        return { ...range, node };
      }
      const forced = Boolean(range.summary.protected?.length);
      const searchMatch = range.messages.some((message) =>
        model.search?.messages.includes(message.id),
      );
      const expanded =
        forced || searchMatch || this.#expandedSummaries.has(range.summary.id);
      const nodes = range.messages.map((message) => {
        const node = messageNodes.get(message.key);
        node.dataset.lfSummary = range.summary.id;
        return node;
      });
      return {
        ...range,
        expanded,
        forced: forced || searchMatch,
        requiredText: searchMatch
          ? "Matching messages kept open"
          : "Messages kept open · current work",
        nodes,
      };
    });
    if (model.reply && !this.#reply) this.#reply = this.#createReply(model);
    render(
      html`
        ${navigationSummary(navigation, model)}
        ${
          model.surface === "outlet"
            ? html`<summary
                class="lf-conversation-summary lf-ui"
                data-lf-gen="1"
                data-lf-offer=""
                ?hidden=${!model.resolved}
              >
                Resolved · ${model.messages.length}
                message${model.messages.length === 1 ? "" : "s"}
              </summary>`
            : nothing
        }
        ${
          model.quote
            ? html`<header class="lf-thread-head">
                ${
                  model.quote
                    ? html`<blockquote
                        class=${`lf-quote${model.quote.anchored && !model.quote.found ? " detached" : ""}`}
                        role=${model.quote.anchored ? "button" : nothing}
                        tabindex=${model.quote.anchored ? "0" : nothing}
                        aria-disabled=${
                          model.quote.anchored ? String(!model.quote.found) : nothing
                        }
                        title=${model.quote.title ?? nothing}
                        @click=${this.#returnToQuote}
                      >
                        <span class="lf-quote-label">${model.quote.label}</span>
                        ${
                          model.quote.outdated
                            ? html`<span class="lf-anchor-status">Outdated</span>`
                            : nothing
                        }
                      </blockquote>`
                    : nothing
                }
              </header>`
            : nothing
        }
        ${
          headerActions && messages[0]
            ? html`<div class="lf-thread-root-meta">
                ${messages[0].header}${headerActions}
              </div>`
            : nothing
        }
        ${repeat(
          ranges,
          (range) => range.key,
          (range) =>
            range.kind === "message" ? range.node : this.#summaryRange(range),
        )}
        ${model.reply ? this.#reply.node : nothing}
        ${
          model.resolved && !model.folding
            ? html`<div
                class=${panel ? "lf-thread-actions" : "lf-conversation-resolved lf-ui"}
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
                ${settlement}
              </div>`
            : nothing
        }
      `,
      this.node,
    );
    this.#wireKeys();
    if (
      summaryReplacedFocusedMessage &&
      focused() !== standing &&
      standing?.isConnected
    ) {
      standing.focus({ preventScroll: true });
    } else if (heldFocus && !this.node.contains(standing) && !panel) {
      this.#commands.landInConversation(this.node.querySelector(SAY_BOX) ?? this.node);
    }
    return this.node;
  }

  #summaryRange(range) {
    const count = range.messages.length;
    const id = range.summary.id;
    const originalsId = `lf-summary-originals-${id}`;
    return html`<section
      class="lf-thread-checkpoint"
      data-summary-id=${id}
      data-expanded=${String(range.expanded)}
    >
      <div class="lf-summary-checkpoint">
        <div class="lf-summary-label">Summary</div>
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
                ${range.expanded ? "Hide" : "Show"} ${count}
                message${count === 1 ? "" : "s"}
              </button>`
        }
      </div>
      <div id=${originalsId} class="lf-summary-originals" ?hidden=${!range.expanded}>
        <div class="lf-summary-messages">
          ${repeat(
            range.messages,
            (message) => message.key,
            (message) => range.nodes[range.messages.indexOf(message)],
          )}
        </div>
        ${
          range.forced
            ? nothing
            : html`<button
                type="button"
                class="lf-summary-refold"
                aria-label="Collapse summarized messages"
                title="Collapse summarized messages"
                @click=${() => this.#setSummaryExpanded(id, false)}
              >
                <span aria-hidden="true">↑</span>
              </button>`
        }
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

  #settlement(model) {
    const state = model.settlement;
    const reopen = state.kind === "unresolve";
    let button = this.#settlements.get(state.kind);
    if (!button) {
      button = offer(
        "button",
        reopen
          ? "lf-btn lf-reopen lf-thread-action"
          : "lf-btn lf-resolve lf-icon-action",
      );
      button.type = "button";
      button.onclick = this.#settle;
      this.#settlements.set(state.kind, button);
    }
    button.setAttribute("aria-disabled", String(state.pending || model.folding));
    button.setAttribute("aria-busy", String(state.pending && !model.folding));
    if (!reopen) {
      const label = model.folding ? "Resolved" : state.label;
      button.setAttribute("aria-label", label);
      button.title = label;
    }
    render(reopen ? state.label : iconTemplate("check", "lf-action-icon"), button);
    return button;
  }

  #settle = () => {
    const model = this.#model;
    if (model.folding) return;
    void settleThread({
      id: () => this.#model.id,
      resolved: model.resolved,
      prepareLanding:
        model.surface === "panel" ? () => this.#prepareLanding(model.resolved) : null,
      ...this.#commands.settlement,
    }).catch(() => {});
  };

  #returnToQuote = (event) => {
    const model = this.#model;
    if (!model.quote?.anchored || !model.quote.found) return;
    if (event.detail !== 0 && reachedForWords(event.currentTarget)) return;
    const travel = this.#commands.travel;
    if (travel.panelCovers()) travel.setPanel(false);
    travel.scrollToThread(model.id, {
      land: () => travel.focusSurface(this.#model.id),
    });
  };

  #wireKeys() {
    const quote = this.node.querySelector(":scope > .lf-thread-head > .lf-quote");
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
    const button = this.node.querySelector(
      ":scope .lf-thread-meta-actions > .lf-resolve, :scope > .lf-thread-actions > .lf-reopen, :scope > .lf-conversation-resolved > .lf-reopen",
    );
    if (button && !this.#keys.has(button)) {
      this.#keys.add(button);
      const reopen = this.#model.resolved;
      const word = reopen ? "Reopen" : "Resolve";
      keys(button, `On a thread's ${word} button`, [
        {
          id: reopen ? "thread.reopen" : "thread.resolve",
          keys: PRESS,
          does: `${word} it`,
          line: word.toLowerCase(),
          when: () => !this.#model.settlement.pending,
          run: () => button.click(),
        },
      ]);
    }
  }

  #createReply(model) {
    const panel = model.surface === "panel";
    const row = offer("div", panel ? "lf-compose" : "lf-say");
    const compact = model.surface === "margin";
    const disclosure = compact
      ? offer("button", "lf-btn lf-reply-disclosure", "Reply")
      : null;
    const input = offer("textarea");
    input.name = "reply";
    const send = offer("button", panel ? "lf-btn lf-thread-send" : "lf-btn", "Send");
    if (disclosure) row.append(disclosure);
    row.append(input, send);
    const hasDraft = () => loadDraft("reply:" + model.key) !== null;
    const reveal = () => {
      if (!disclosure) return;
      row.classList.remove("lf-reply-collapsed");
      disclosure.hidden = true;
      disclosure.setAttribute("aria-expanded", "true");
    };
    const collapse = () => {
      if (!disclosure || hasDraft()) return;
      row.classList.add("lf-reply-collapsed");
      disclosure.hidden = false;
      disclosure.setAttribute("aria-expanded", "false");
    };
    if (panel)
      input.lfRevealReply = () =>
        this.#commands.listRoot.revealNavigation(this.#model.id);
    if (disclosure) {
      input.lfRevealReply = reveal;
      input.lfCollapseReply = collapse;
      disclosure.onclick = () => this.#commands.landInConversation(input);
    }
    const lifetime = wireReply(
      { root: { id: model.id, attempt: model.attempt } },
      input,
      send,
      {
        liveId: () => this.#model.id,
        ...this.#commands.reply,
        onDraftLoaded: () => {
          if (hasDraft()) reveal();
          // Initial construction is already painting this reading; mirrored edits
          // arrive later and must refresh the collapsed row's Draft indication.
          if (panel && this.#reply) this.#navigation.draftChanged();
        },
      },
    );
    collapse();
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
          if (destination.matches?.(".lf-thread"))
            focusThread(destination, { preventScroll: true });
          else destination.focus({ preventScroll: true });
          mayRestore = travel.retainPanelLanding(destination);
          return true;
        },
        refused: () => {
          if (mayRestore()) {
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
      refused: async () => {
        const restoreFocus = mayRestore();
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
    if (!this.#model.reply && this.#reply) {
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
