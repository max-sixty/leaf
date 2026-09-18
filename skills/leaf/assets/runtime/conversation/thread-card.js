/* One synchronous Lit owner for complete panel, page, outlet and margin threads.

   Immutable descriptors contain generated presentation only. Retained native editors
   and frozen message widgets keep their mechanical lifetime outside those values.
   The owner alone renders its native card root and all generated descendants; a
   failed candidate is restored by presenting its committed descriptor again. */
import { html, render, repeat, nothing } from "../../vendor/browser-runtime.js";
import { turns, threadKey } from "./model.js";
import {
  anchorLabel,
  MessageView,
  messageReading,
  messageWidgetIds,
} from "./messages.js";
import { reactionReading } from "./reaction-strips.js";
import { messageReceipts } from "./acknowledgments.js";
import { offer, reachedForWords } from "../widget-elements.js";
import { keys, focused } from "../keyboard/scopes.js";
import { PRESS } from "../keyboard/bindings.js";
import { wireReply } from "./replies.js";
import { settleThread } from "./folding.js";
import { groupFor, pageOutline } from "./placement.js";
import { iconTemplate } from "../icons.js";
import { loadDraft } from "../drafts.js";
import { SAY_BOX } from "./selectors.js";

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
  { interactions, revision, visible = true, grow = false, outline = null },
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
    id: thread.root.id,
    attempt: thread.root.attempt ?? null,
    surface,
    visible,
    grow,
    folding: false,
    quote: panel
      ? quoteReading(thread, commands.anchors, outline ?? pageOutline())
      : null,
    resolved,
    resolvedBy:
      thread.resolved?.author === "claude"
        ? `✓ Resolved by ${thread.resolved.agent || "Agent"}`
        : panel
          ? ""
          : "✓ Resolved",
    settlement: Object.freeze({ kind, word, label, pending: settling }),
    reply: !resolved && (panel || thread.root.response?.kind !== "version"),
    messages: Object.freeze(
      turns(thread).map((message) =>
        messageReading(message, {
          panel,
          receipts: messageReceipts(
            thread,
            message,
            panel ? messageWidgetIds(message) : [],
            interactions,
            revision,
          ),
          reactions: reactionReading(thread, message, panel || surface === "outlet"),
        }),
      ),
    ),
  });
}

export class ThreadView {
  #commands;
  #model = null;
  #messages = new Map();
  #reply = null;
  #summaryResolved = null;
  #keys = new WeakSet();
  #settlements = new Map();
  #growing = false;

  constructor(surface, commands) {
    this.#commands = commands;
    this.node = document.createElement(surface === "outlet" ? "details" : "div");
    this.node.tabIndex = -1;
    this.node.addEventListener("animationend", () => {
      this.#growing = false;
      this.node.classList.remove("grow");
    });
  }

  get model() {
    return this.#model;
  }

  present(model) {
    const prior = this.#model;
    const standing = focused();
    const heldFocus = this.node.contains(standing);
    this.#model = model;
    const panel = model.surface === "panel";
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
    const messages = model.messages.map((message) => {
      let view = this.#messages.get(message.key);
      if (!view)
        this.#messages.set(message.key, (view = new MessageView(this.#commands)));
      view.present(message);
      return { key: message.key, node: view.node };
    });
    if (model.reply && !this.#reply) this.#reply = this.#createReply(model);
    const settlement = this.#settlement(model);
    render(
      html`
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
          model.quote || !model.resolved
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
                ${!model.resolved ? settlement : nothing}
              </header>`
            : nothing
        }
        ${repeat(
          messages,
          (message) => message.key,
          (message) => message.node,
        )}
        ${model.reply ? this.#reply.node : nothing}
        ${
          model.resolved
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
    if (heldFocus && !this.node.contains(standing)) {
      if (!panel)
        this.#commands.landInConversation(
          this.node.querySelector(SAY_BOX) ?? this.node,
        );
    }
    return this.node;
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
      ":scope > .lf-thread-head > .lf-resolve, :scope > .lf-thread-actions > .lf-reopen, :scope > .lf-conversation-resolved > .lf-reopen",
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
    const send = offer(
      "button",
      panel ? "lf-btn primary lf-thread-send" : "lf-btn primary",
      "Send",
    );
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
          destination.focus({ preventScroll: true });
          mayRestore = travel.retainPanelLanding(destination);
          return true;
        },
        refused: () => {
          if (mayRestore()) shownCard()?.focus({ preventScroll: true });
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
