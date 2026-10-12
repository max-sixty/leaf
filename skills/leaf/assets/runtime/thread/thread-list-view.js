/* The panel's keyed Lit list and complete committed presentation reading.
   Native card roots are retained by stable thread identity. Only their ThreadView
   owns generated descendants; retention re-renders values, never captured DOM.
   Count and narrowing paint share the rows' checkpoint and update boundary.
   The list owns the one expanded visible thread and writes every shown card's
   disclosure from that choice, while cards retain their message and editor nodes; a
   card whose title takes focus, by Tab, press or script, and a card the browser opens
   itself, as find-in-page does, become the choice. The cards
   carry no native `name`: its exclusivity closes a card the moment it is named beside
   an open one, which the list's own choice then opens again. This mechanical state
   never publishes a new application epoch. Narrowing keeps the
   selected card when visible and otherwise selects the first visible card. Releasing
   an allocation returns selection to the most recent surviving choice, so refusing
   a provisional thread preserves the conversation the user had selected.

   Focus given to the list goes on to the selected card's title or withdrawn notice's
   Dismiss button, whatever gave it — `g T`, Escape from the panel's find box, or a fold
   that took the focused card. The list keeps focus itself only while it shows no
   selected allocation, and its ring never outlines one. No title holds focus closed:
   focus, selection and the open card never part.

   The list also decides when a card leaves it (`keeping`), and news takes no card
   out from in front of the user: a card another actor resolves under Open stays where
   it stands, its card holding the resolution behind its notice (held-news.js) and,
   once shown, drawn resolved in the shape it stood in, until its going would move
   nothing the user sees. A root another actor withdraws is news too, and one rule
   (`#keeping`) holds both kinds of card. The withdrawn one keeps only its measured
   allocation and a Dismiss notice: its controls disconnect, so it holds nothing for
   the user's words, its semantic membership ends, and a selected allocation holds off
   fallback disclosure. Dismissal or choosing another card releases it at once, outside
   the geometry rule (#2387's choice): the allocation has no closed form to shrink to
   when another card opens, and the list's place hold keeps the chosen card where it
   stood, as it does for an open card closing above it (thread-list.js,
   `holdThroughDisclosure`). The model builder asks both questions while it builds the
   reading (thread-list.js), so a kept allocation is a row of that reading, committed
   and restored with the cards beside it. Rejected: deciding withdrawals by a copy of
   the rule beside `keeping`, as paint the list spliced into each reading it drew
   (#2387), which every later change to when a card leaves had to repeat and which
   committing had to rebuild from the drawn rows. */
import { html, repeat, ref } from "../../vendor/browser-runtime.js";
import {
  holdFocus,
  onStanding,
  focusDestination,
  focused,
  standingIn,
} from "../focus.js";
import { RetainedFace } from "../retained-face.js";
import { ThreadView } from "./thread-card.js";
import { threadHoldsDraft } from "./replies.js";
import { forwardToThread, threadFocusStop } from "./focus.js";
import { passOn, retainUserIntent } from "../user-intent.js";
import { layoutChanged } from "../widget-elements.js";
import { isFolding } from "./folding.js";
import { threadKey } from "./model.js";
import { elementBorderFrame } from "../element-frame.js";
import { growthIsSeen, whenNone } from "../geometry.js";
import { gesturedOn } from "./held-news.js";
import { PENDING } from "./identity.js";
import { readingIsContinuous } from "../reading-continuity.js";
import { layoutPx } from "../keeps.js";

const TAG = "leaf-thread-list";

const EMPTY_MODEL = Object.freeze({
  rows: Object.freeze([]),
  count: null,
  pageSeats: new Map(),
});

// Whether the user has a reply or a rewrite on its way in `thread`: a message the
// ledger draws under its pending id, or new words standing over one of theirs
// (`foldThreads`). A reaction is a mark, not a turn.
const turnOnItsWay = (thread) =>
  thread.msgs.some(
    (message) =>
      (message.id.startsWith(PENDING) && !message.token) || message.edited?.pending,
  );

// The focus stop of drawn card or notice `row`: a card's title, a notice's Dismiss.
const rowStop = (row) =>
  row.kind === "thread" ? threadFocusStop(row.node) : row.node.querySelector("button");

class ThreadListView extends RetainedFace {
  #commands = null;
  #views = new Map();
  #restoreFocusAfterPaint = null;
  #generation = 0;
  #rows = [];
  #retaining = false;
  #rollbackFocus = null;
  #selection = [];
  #intent = null;
  #leaving = new Map();
  #dismissed = new Set();
  #withdrawnFocus = null;
  // The row the list last showed open: a card, or a withdrawn allocation it selects.
  #shownOpen = null;

  // The allocation the list keeps for committed row `row`, whose root the next reading
  // no longer has, or null where it goes: an absent root is no longer a thread, so its
  // controls disconnect and only the room the reader stood in stays, for as long as
  // `#keeping` holds it as news. The model builder places it (thread-list.js).
  withdrawal(row, intent) {
    if (this.#dismissed.has(row.key)) return null;
    const thread = row.kind === "thread" ? row.descriptor.source : null;
    if (this.#keeping(row.key, intent, thread, { words: false }) !== "news")
      return null;
    return thread
      ? Object.freeze({
          kind: "withdrawn",
          key: row.key,
          id: row.descriptor.id,
          topic: row.descriptor.summary.topic,
          extent: elementBorderFrame(
            this.#rows.find((drawn) => drawn.key === row.key).node,
          ).height,
        })
      : row;
  }

  #visibleRows() {
    const eligible = new Set(
      this.model.rows
        .filter((row) => row.kind === "thread" && row.descriptor.visible)
        .map((row) => row.key),
    );
    return this.#rows.filter((row) => row.kind === "thread" && eligible.has(row.key));
  }

  #select(key) {
    const previous = this.#expandedRow();
    this.#selection = [key, ...this.#selection.filter((chosen) => chosen !== key)];
    if (previous?.kind === "withdrawn" && previous.key !== key) {
      this.#dismissed.add(previous.key);
      this.#commands.repaintThread();
    }
  }

  #expandedRow() {
    const present = new Set(this.#rows.map((row) => row.key));
    const preferred = this.#selection.find((key) => present.has(key));
    const visible = this.#visibleRows();
    return (
      this.#rows.find((row) => row.kind === "withdrawn" && row.key === preferred) ??
      visible.find((row) => row.key === preferred) ??
      visible[0]
    );
  }

  #showExpanded() {
    const chosen = this.#expandedRow();
    this.#shownOpen = chosen?.key ?? null;
    if (!chosen) return;
    for (const row of this.#visibleRows())
      row.node.toggleAttribute("open", row === chosen);
  }

  // The user's own move onto a card's title chooses the card, whatever route took them
  // there, so the focused thread is always the open one. A press waits for its click
  // (thread-card.js), which lands what it chose, and a return puts them back where they
  // had chosen, or on the card the list shows while a change holds theirs from it,
  // which is no choice of theirs.
  chooseTitle(title) {
    this.#choose(title.parentElement);
  }

  // An open title is still the user's focus stop for the thread. A second press leaves
  // it selected; choosing another title moves disclosure.
  #choose(card) {
    const row = this.#visibleRows().find((row) => row.node === card);
    if (!row) return;
    this.#commands.beforeChoose(card);
    this.#select(row.key);
    this.#showExpanded();
  }

  #dismiss(row) {
    this.#dismissed.add(row.key);
    this.#commands.repaintThread();
  }

  // Why a shown card the view no longer admits stays shown, or null where it goes: the
  // narrowing says which threads the view admits (narrowing.js), this says when a card
  // it stops admitting leaves, and the model builder combines the two into one reading.
  // A change of view puts any card away. What took the card out of the view is read in
  // the render that first does, and its card carries the answer while it stays. The
  // user's own gesture on the thread (`gesturedOn`) takes the card in the turn it is
  // drawn, or, while its reply holds words, once the words go ("draft"), so settlement
  // never puts a draft away; its thread owner folds a settlement out, and widens the
  // view to hold a thread the user's own turn took out of it. Anything else is
  // news ("news"), and its card stays, holding the news (held-news.js) or drawn as the
  // news left it in the shape it stood in, while its going would move something the
  // user sees: while its going would be (geometry.js, `growthIsSeen`), since every
  // card after it would rise, and, as the card the list shows open, while the panel
  // shows, since another card would open in its place. Out of sight it stays only for
  // its words, with the cause that first excluded it still carried. Its going out of
  // sight asks for the render that lets it go (`#watchKept`), as does its closing when
  // the user opens another card.
  keeping(thread, intent) {
    return this.#keeping(`thread:${threadKey(thread)}`, intent, thread);
  }

  // The one rule for every card the next reading drops, the view's exclusions above and
  // the log's withdrawals alike (`withdrawal`). `thread` is what the card last
  // drew, null once its allocation stands committed as withdrawn, when no gesture of
  // the user's but Dismiss reaches it. A withdrawn root keeps nothing for its words
  // (`words: false`): its controls disconnect with it, so only news holds its room.
  #keeping(key, intent, thread, { words = true } = {}) {
    const row = this.#rows.find((row) => row.key === key);
    const model = row?.kind === "thread" ? this.#views.get(key).model : null;
    if (
      this.#intent !== intent ||
      !row?.node?.isConnected ||
      (row.kind !== "withdrawn" && (!model?.visible || model.folding))
    )
      return null;
    const seen =
      readingIsContinuous() &&
      (key === this.#shownOpen ? this.checkVisibility() : growthIsSeen(row.node));
    const draft =
      words &&
      threadHoldsDraft(
        threadKey(thread),
        thread.msgs.map(({ id }) => id),
      );
    // A turn of the user's own on its way, a reply or a rewrite, makes a card news kept
    // theirs: the turn takes the card out as any turn of theirs does (thread-card.js,
    // `#speak`). A reaction, a move or words not yet sent leave it held for the news.
    const news = model?.kept
      ? model.kept === "news" && !turnOnItsWay(thread)
      : !thread || !gesturedOn(thread);
    if (news && (seen || draft)) return "news";
    return draft ? "draft" : null;
  }

  #watchKept() {
    const kept = new Set(
      this.#rows
        .filter(
          (row) =>
            row.kind === "withdrawn" ||
            (row.kind === "thread" && this.#views.get(row.key).model.kept),
        )
        .map((row) => row.node)
        .filter(Boolean),
    );
    for (const [node, stop] of this.#leaving)
      if (!kept.has(node)) {
        stop();
        this.#leaving.delete(node);
      }
    for (const node of kept)
      if (!this.#leaving.has(node))
        this.#leaving.set(
          node,
          whenNone([node], growthIsSeen, () => this.#commands.repaintThread()),
        );
  }

  // The rows the list's walks step through, in its order, each as its focus `stop` and
  // the card it shows, `thread`, null for a withdrawn notice: every shown card, a card
  // the list keeps outside the view included, and each withdrawn notice. A card folding
  // out is in none of them, since its room is about to go. The arrows walk the stops
  // (panel.js), and `t`/`T` and every walk position count the threads (navigation.js).
  walkRows() {
    const shown = new Set(this.#visibleRows());
    return this.#rows
      .filter((row) => (row.kind === "withdrawn" ? row.node : shown.has(row)))
      .map((row) => ({
        stop: rowStop(row),
        thread: row.kind === "thread" ? row.node : null,
      }));
  }

  // The shown cards in the page's order, whichever order the list stands in.
  inPageOrder(cards) {
    const seats = this.model.pageSeats;
    return [...cards].sort((a, b) => seats.get(a.dataset.id) - seats.get(b.dataset.id));
  }

  // Whether the card drawn for thread or message `id` stands only for the user's own
  // words on their way (`keeping`, "draft"): drawn, though the view leaves it out.
  keepsForWords(id) {
    const row = this.#rows.find(
      (row) => row.kind === "thread" && this.#views.get(row.key).ownsMessage(id),
    );
    return Boolean(row) && this.#views.get(row.key).model.kept === "draft";
  }

  revealNavigation(id) {
    const row = this.#rows.find(
      (row) => row.kind === "thread" && this.#views.get(row.key).ownsMessage(id),
    );
    // Narrowing owns hidden rows. Its completed reveal calls back here; opening
    // one before that would paint no disclosure and invalidate the same transition.
    if (!row || row.node.hidden) return;
    this.#select(row.key);
    this.#showExpanded();
  }

  incomingTail(reading, card) {
    const prior = this.committed.rows.find(
      (row) => row.kind === "thread" && this.#views.get(row.key)?.node === card,
    );
    const next = prior && reading.rows.find((row) => row.key === prior.key);
    return next?.kind === "thread"
      ? this.#views.get(prior.key).incomingTail(prior.descriptor, next.descriptor)
      : null;
  }

  messageTail(id) {
    const view = [...this.#views.values()].find((view) => view.ownsMessage(id));
    return view?.messageTail(id) ?? null;
  }

  constructor() {
    super(EMPTY_MODEL);
    this.addEventListener("focus", () => {
      this.#showExpanded();
      const open = this.#expandedRow();
      if (!open) return;
      // Handed on with the cause that gave the list its focus (`chooseTitle`).
      if (open.kind === "withdrawn")
        focusDestination(open.node.querySelector("button"), "return");
      else forwardToThread(open.node);
      passOn(this, focused());
    });
  }
  configure(commands, initialModel) {
    if (this.#commands) return;
    this.#commands = commands;
    this.model = initialModel;
    super.commit();
  }

  // Forward gestures paint their complete generated result in their sending turn.
  async present(model) {
    const generation = ++this.#generation;
    if (!this.#rollbackFocus && standingIn(this)) {
      const node = focused();
      this.#rollbackFocus = {
        node,
        mayRestore: retainUserIntent({ source: node, fallback: this }),
      };
    }
    await this.paint(model, { now: true });
    return generation === this.#generation && this.model === model;
  }

  commit(model) {
    if (this.model !== model) return false;
    super.commit();
    const wanted = new Set(
      model.rows.filter((row) => row.kind === "thread").map((row) => row.key),
    );
    // Unknown counts describe unavailable placeholders, not removed identities.
    // Candidate fallback is only paint; the complete committed reading retires
    // departed choices and adopts the choice its narrowing left visible.
    if (model.count !== null) {
      const present = new Set(this.#rows.map((row) => row.key));
      this.#selection = this.#selection.filter((key) => present.has(key));
      this.#dismissed = new Set(
        this.#rows
          .filter((row) => row.kind === "withdrawn" && this.#dismissed.has(row.key))
          .map((row) => row.key),
      );
      const chosen = this.#expandedRow();
      if (chosen) this.#select(chosen.key);
    }
    for (const [key, view] of this.#views) {
      if (wanted.has(key)) view.commit();
      else {
        view.dispose();
        this.#views.delete(key);
      }
    }
    this.#rollbackFocus = null;
    return true;
  }

  async retainCommitted(candidate) {
    if (this.model !== candidate) return false;
    const generation = ++this.#generation;
    this.#retaining = true;
    try {
      await this.paint(this.committed, { now: true });
      if (generation !== this.#generation) return false;
      const focus = this.#rollbackFocus;
      if (focus?.node.isConnected && focus.mayRestore())
        focusDestination(focus.node, "return");
      this.#rollbackFocus = null;
      return this.committed;
    } finally {
      this.#retaining = false;
    }
  }

  willUpdate(changed) {
    if (!changed.has("model") || !this.#commands) return;
    this.#restoreFocusAfterPaint ??= holdFocus(this);
    // A change of view moves the cards, so they show what they hold.
    const viewChanged = this.#intent !== this.model.intent;
    const rows = [];
    const wanted = new Set();
    this.#intent = this.model.intent;
    for (const row of this.model.rows) {
      if (row.kind !== "thread") {
        if (row.kind === "withdrawn") {
          const previous = this.#rows.find((drawn) => drawn.key === row.key);
          if (previous?.node && standingIn(previous.node))
            this.#withdrawnFocus = row.key;
          rows.push({ ...row, node: null });
        } else rows.push(row);
        continue;
      }
      this.#dismissed.delete(row.key);
      wanted.add(row.key);
      let view = this.#views.get(row.key);
      if (!view) {
        this.#views.set(
          row.key,
          (view = new ThreadView("panel", {
            ...this.#commands.card,
            choose: () => this.#choose(view.node),
          })),
        );
        // A card opened by something other than the list becomes the choice: a reveal
        // says so in the task that opens it, so the card it replaces closes in the same
        // task; the browser's own opening (find-in-page) is heard on its toggle.
        const opened = () => {
          const row = this.#visibleRows().find((row) => row.node === view.node);
          if (!view.node.open || !row || row.key === this.#expandedRow()?.key) return;
          this.#select(row.key);
          this.#showExpanded();
        };
        view.node.addEventListener("lf-reveal", opened);
        view.node.addEventListener("toggle", () => {
          layoutChanged(this);
          opened();
          // A kept card the user closed by opening another goes, if out of sight.
          if (!view.node.open && view.model.kept) this.#commands.repaintThread();
        });
      }
      if (viewChanged) view.releaseNews();
      view.present(row.descriptor, { retaining: this.#retaining, viewChanged });
      rows.push({ kind: "thread", key: row.key, node: view.node });
    }
    for (const [key, view] of this.#views) if (!wanted.has(key)) view.retire();
    // The list says it shows nothing once the last card has given its room back. Said
    // while that card still folds, the words stood above it and carried it down.
    const giving = rows.some((row) => row.kind === "thread" && isFolding(row.node));
    this.#rows = giving ? rows.filter((row) => row.kind !== "empty") : rows;
  }

  updated() {
    this.#showExpanded();
    const restore = this.#restoreFocusAfterPaint;
    this.#restoreFocusAfterPaint = null;
    const withdrawn = this.#rows.find(
      (row) => row.kind === "withdrawn" && row.key === this.#withdrawnFocus,
    );
    this.#withdrawnFocus = null;
    restore?.(withdrawn?.node.querySelector("button"), this);
    this.#watchKept();
    this.#commands?.presentSummary(this.model);
  }

  #row(row) {
    if (row.kind === "thread") return row.node;
    if (row.kind === "withdrawn")
      return html`<div
        ${ref((node) => {
          row.node = node;
        })}
        class="lf-thread-withdrawn lf-thread-compact"
        data-withdrawn=${row.id}
        style=${`min-block-size:${layoutPx(row.extent)}`}
      >
        <div class="lf-thread-summary">
          <span class="lf-thread-topic">${row.topic}</span>
          <span class="lf-thread-meta" role="status">Thread withdrawn</span>
          <button
            type="button"
            class="lf-thread-trailing"
            aria-label=${`Dismiss withdrawn thread: ${row.topic}`}
            @click=${() => this.#dismiss(row)}
          >
            Dismiss
          </button>
        </div>
      </div>`;
    if (row.kind === "empty") return html`<div class="lf-empty">${row.text}</div>`;
    return html`<div class="lf-system" data-id=${row.id}>${row.text}</div>`;
  }
  render() {
    return repeat(
      this.#rows,
      (row) => row.key,
      (row) => this.#row(row),
    );
  }
}
if (!customElements.get(TAG)) customElements.define(TAG, ThreadListView);

onStanding((node, cause) => {
  if ((cause === "move" || cause === "step") && node?.matches?.(".lf-thread-summary"))
    node.closest(TAG)?.chooseTitle(node);
});
export const createThreadListView = () => document.createElement(TAG);
