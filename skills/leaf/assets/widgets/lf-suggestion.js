/* lf-suggestion: an edit to content the reader has already seen, offered as a
 * proposal rather than shipped as a fait accompli. Accept or Reject rides the action
 * channel; the next version eventually carries the settled markup.
 *
 * The log owns the absolute outcome, so reloads and tabs converge. Once that outcome
 * stands, the surviving slot remains and the retired slot folds away as trackable
 * motion. Undo remains while that decision can still be withdrawn. The optimistic
 * content and Undo carry visual feedback; a live announcement says the same decision
 * without restating it on screen, and refusal restores actionable failure controls.
 *
 * The suggestion owns only those entries and their semantics. It contributes an immutable
 * reading through `registerMarginContribution`; the margin projection joins it to comment threads,
 * decisions, delivery status, activity, and temporary reaction controls for this same
 * target.
 * That owner renders and places the resulting entries, measures the rail, docks them when
 * the margin is too narrow, and reads rendered descendants when a project makes the
 * target `display: contents`. A suggestion never creates a second RHS surface or
 * geometry model of its own. */
import {
  alignText,
  announce,
  commandScope,
  commands,
  FOLD_MS,
  marginEntry,
  motion,
  once,
  paintKeys,
  quietWord,
  quoted,
  renderRetired,
  registerMarginContribution,
  says,
  shownParts,
  textNodesUnder,
  notice,
  widgetController,
} from "/runtime/widget-api.js";

const WORDS = { accept: "Accept", reject: "Reject" };
const FACE = {
  accept: { icon: "check", tone: "positive", rank: "primary" },
  reject: { icon: "cross", tone: "negative", rank: "secondary" },
};

// ---------- word-level emphasis ----------
// A block replacement asked the reader to eyeball-diff two paragraphs for the words
// that moved. The slots' whole tints stay — they are what a dead copy keeps — and on
// the live page the words that differ deepen, painted through the highlight registry
// so no node is wrapped (Paint; don't wrap) and cleared when the suggestion settles.
// `movedWords` keeps alignment and the similarity threshold in one reading before
// this module turns its offsets into highlight ranges.
const EMPHASIS = { del: "lf-sug-del", ins: "lf-sug-ins" };
const emphasized = new Map(); // suggestion element → {del: Range[], ins: Range[]}

function movedWords(before, after) {
  const runs = alignText(before, after);
  const ink = (text) => text.replace(/\s+/g, "").length;
  const shared = runs
    .filter((run) => run.kind === "same")
    .reduce((total, run) => total + ink(run.text), 0);
  if (!shared || shared * 3 < Math.min(ink(before), ink(after))) return null;

  const del = [];
  const ins = [];
  let oldOffset = 0;
  let newOffset = 0;
  for (const run of runs) {
    const length = run.text.length;
    if (run.kind !== "insert") {
      if (run.kind === "delete" && run.text.trim())
        del.push([oldOffset, oldOffset + length]);
      oldOffset += length;
    }
    if (run.kind !== "delete") {
      if (run.kind === "insert" && run.text.trim())
        ins.push([newOffset, newOffset + length]);
      newOffset += length;
    }
  }
  return { del, ins };
}

function repaintEmphasis() {
  for (const [kind, name] of Object.entries(EMPHASIS)) {
    const ranges = [...emphasized.values()].flatMap((e) => e[kind]);
    // Under the comment marks (priority -1): a passage the reader pointed at
    // outranks the widget's own emphasis wherever the two overlap.
    CSS.highlights.set(name, Object.assign(new Highlight(...ranges), { priority: -1 }));
  }
}

// [from, to) offsets in a slot's concatenated text → Ranges over its text nodes. One
// range per segment keeps generated interface between authored segments out of the
// paint: a DOM Range spanning both sides would include the excluded nodes between them.
function toRanges(segments, spans) {
  const ranges = [];
  for (const [from, to] of spans) {
    let pos = 0;
    for (const seg of segments) {
      const len = seg.end - seg.start;
      const start = Math.max(from - pos, 0);
      const end = Math.min(to - pos, len);
      if (start < end) {
        const range = document.createRange();
        range.setStart(seg.node, seg.start + start);
        range.setEnd(seg.node, seg.start + end);
        ranges.push(range);
      }
      pos += len;
      if (pos >= to) break;
    }
  }
  return ranges;
}

customElements.define(
  "lf-suggestion",
  class extends HTMLElement {
    #deciding = null; // the decision in flight, so a second press joins it
    #staging = false; // the synchronous span before that promise exists
    #failed = null;
    #undoing = false;
    #margin = null;
    #commandScope = null;
    #stopReading = null;
    #controller = null;
    #presentedOutcome = null;

    connectedCallback() {
      // Re-connection — a card dragged to another column, a replay moving one — must
      // restore this target's contribution to the shared margin entry cluster.
      if (!once(this)) {
        this.#offer();
        this.#watchReading();
        return;
      }
      this.#controller = widgetController(this);
      // Presentation, not input, so an exhibited pending change gets it too: quoting
      // gates the action channel, never what a change looks like. Both consume the
      // controller's application selection; painted attributes are output only.
      this.#emphasize();
      this.#voice();
      // Quoted material is exhibited, not offered: a suggestion inside an
      // exhibit shows what a pending change looks like, so it keeps the marks
      // the theme draws and never grows controls to decide it with.
      if (quoted(this)) {
        this.#watchReading();
        return;
      }
      // The runtime says it just opened this element's containers (reveal): the entry
      // may be waiting on geometry the target only now has, and the caller is about
      // to focus it, so the layout question is answered now rather than at the
      // observer's next frame.
      this.addEventListener("lf-reveal", () =>
        this.#margin?.update({ immediate: true }),
      );
      this.#offer();
      this.#watchReading();
    }

    #watchReading() {
      this.#controller ??= widgetController(this);
      this.#stopReading ??= this.#controller.subscribe((reading) => {
        if (quoted(this) || !this.#margin) return;
        if (
          this.#margin.contains(document.activeElement) &&
          (reading.state.settlement.value ?? null) !== this.#presentedOutcome
        ) {
          // Signals publish before the projection adapter. Keep the currently focused
          // entry until that adapter applies the new state: the next complete reading can
          // hand focus directly to its semantic replacement instead of losing the
          // reader's place when this subscriber removes it first.
          return;
        }
        this.#refreshMargin();
      });
    }

    disconnectedCallback() {
      this.#stopReading?.();
      this.#stopReading = null;
      this.#margin?.unregister();
      this.#margin = null;
      emphasized.delete(this);
      repaintEmphasis();
    }

    #offer() {
      if (quoted(this) || this.#margin) return;
      this.#ensureCommands();
      this.#margin = registerMarginContribution({
        key: `suggestion:${this.id}`,
        // An accepted deletion (or rejected insertion) has no surviving slot and the
        // suggestion itself leaves layout. Undo still belongs to the containing passage,
        // so that passage becomes its perch while the gesture can be withdrawn.
        target: () =>
          !this.#outcome() || shownParts(this).some((part) => part.checkVisibility())
            ? this
            : this.parentElement,
        source: () => this,
        read: () => this.#readMargin(),
        activate: (activation, { focus }) => {
          if (activation === "accept" || activation === "reject")
            return this.#decide(activation, focus);
          if (activation === "undo") return this.#undoOutcome();
          if (activation === "retry") return this.#retryDecision();
          if (activation === "cancel-failure") return this.#cancelFailedDecision();
        },
      });
    }

    #entries() {
      const outcome = this.#outcome();
      if (outcome && !this.#failed) {
        const pending = Boolean(this.#staging || this.#deciding);
        if (!pending && !this.#undoable(outcome)) return [];
        return [
          marginEntry({
            key: "undo",
            icon: "undo",
            label: "Undo",
            accessibleLabel: `Undo ${outcome === "accept" ? "accepting" : "rejecting"} the suggested change: ${this.#label()}`,
            rank: "primary",
            state: pending || this.#undoing ? "busy" : "idle",
            disabled: pending || this.#undoing,
            activation: "undo",
            scope: this.#commandScope,
          }),
        ];
      }

      if (this.#failed) {
        return [
          marginEntry({
            key: "retry",
            icon: "retry",
            label: "Retry",
            rank: "complete",
            state: "failed",
            activation: "retry",
            scope: this.#commandScope,
          }),
          marginEntry({
            key: "cancel-failure",
            icon: "cross",
            label: "Cancel",
            rank: "escape",
            state: "failed",
            activation: "cancel-failure",
            scope: this.#commandScope,
          }),
        ];
      }

      const state = this.#deciding ? "busy" : "idle";
      const change = this.#label();
      return Object.keys(WORDS).map((kind) =>
        marginEntry({
          key: kind,
          ...FACE[kind],
          label: WORDS[kind],
          accessibleLabel: `${WORDS[kind]} the suggested change: ${change}`,
          state,
          disabled:
            this.#staging ||
            Boolean(this.#deciding) ||
            !this.#controller.read().actions[kind]?.available,
          activation: kind,
          className: `lf-sug-${kind}`,
          scope: this.#commandScope,
        }),
      );
    }

    #readMargin() {
      const outcome = this.#outcome();
      const entries = this.#entries();
      return {
        // The slots use tint and strike/insert paint to carry their relationship on the
        // page. Away from that paint, concatenating them turns `red` → `blue` into the
        // meaningless `redblue`; give Page Map that relation in words.
        subject: this.#subject(),
        state: this.#failed
          ? "failed"
          : this.#staging || this.#deciding || this.#undoing
            ? "busy"
            : "idle",
        side: "before",
        claim: true,
        reserve: 0,
        notice: this.#failed
          ? {
              text: this.#failed.undo
                ? `Undo failed · ${outcome === "accept" ? "Accepted" : "Rejected"}`
                : "Failed",
              tone: "negative",
            }
          : null,
        entries,
        readings: entries.length
          ? [
              {
                id: `suggestion:${this.id}`,
                // Before settlement this contribution is the Ask, so suppress the shared
                // Ask at the same target. Afterwards Undo remains without inventing a
                // second page-map reading.
                kind: outcome ? "action" : "ask",
                ...(outcome ? {} : { represents: true }),
                text: outcome
                  ? `${outcome === "accept" ? "Accepted" : "Rejected"} suggested change`
                  : "Accept or reject suggested change",
                activate: () => this.#margin?.focus(this.#focusKey()),
              },
            ]
          : [],
      };
    }

    #focusKey() {
      if (this.#failed) return "retry";
      return this.#outcome() ? "undo" : "accept";
    }

    #refreshMargin({ immediate = false, focus = null } = {}) {
      if (!this.#margin) return;
      const held = this.#margin.contains(document.activeElement);
      this.#margin.update({
        immediate,
        focus: focus ?? (held ? this.#focusKey() : null),
      });
      paintKeys();
    }

    #ensureCommands() {
      if (this.#commandScope) return;
      const labels = {
        accept: "Accept",
        reject: "Reject",
        undo: "Undo",
        retry: "Retry",
        "cancel-failure": "Cancel",
      };
      this.#commandScope = commandScope(
        "On a suggested change",
        Object.entries(labels).map(([key, label]) => ({
          id: `suggestion.${key}`,
          keys: [],
          control: () => this.#margin?.control(key),
          decision: label,
          does: `${label} the suggested change`,
          line: label.toLowerCase(),
          when: () => this.#entries().some((entry) => entry.key === key),
          run: () => this.#margin?.activate(key),
        })),
        {
          answer: () => {
            const outcome = this.#outcome();
            if (!outcome) return "";
            return outcome === "accept" ? "Accepted" : "Rejected";
          },
        },
      );
      commands(this, this.#commandScope);
    }

    // What the change is about, for the button's label and failure receipt: the
    // proposal where there is one, since that is what accepting brings about —
    // a deletion has only the markup it would remove.
    #label() {
      const slot =
        this.querySelector(":scope > lf-new") || this.querySelector(":scope > lf-old");
      const text = (slot && says(slot)) || this.id;
      return text.length > 48 ? text.slice(0, 48) + "…" : text;
    }

    #subject() {
      const cut = this.querySelector(":scope > lf-old");
      const put = this.querySelector(":scope > lf-new");
      const before = cut ? says(cut) : "";
      const after = put ? says(put) : "";
      if (before && after) return `${before} → ${after}`;
      return before || after || this.id;
    }

    accept() {
      return this.#decide("accept");
    }

    // A press makes the reversible decision locally and the outbox carries that exact
    // projection until the log accounts for it. A definitive refusal removes the local
    // winner and reconciles the authored state before this continuation paints the repair
    // controls, so the reader returns to a pending suggestion with Failed, Retry, Cancel.
    #decide(outcome, focus = null) {
      if (this.#controller.read().state.settlement.value) return Promise.resolve(true);
      if (!this.#controller.read().actions[outcome]?.available)
        return Promise.resolve(false);
      if (this.#staging || this.#deciding)
        return this.#deciding ?? Promise.resolve(false);
      // Read before deciding: deciding retires a slot, a retired slot leaves the page's
      // reading, and `says` on what has left the reading answers nothing — the notice
      // then named the widget's id instead of the words the user just judged.
      const label = this.#label();
      // Accepting the fix answers the thread it was written for, so the same
      // event carries it: the mapping is snapshotted into the action, because
      // the honoring version retires this wrapper — attribute and all — and a
      // second POST could fail alone, leaving the outcome and the resolution
      // disagreeing with no repair path.
      const comment = this.getAttribute("resolves");
      const detail = outcome === "accept" && comment ? { resolves: comment } : {};
      this.#failed = null;
      // This decision replaces words the reader may still have selected. Clear that
      // page range before moving its nodes, independent of whether activation came from
      // pointer, Enter, Space, or an address route; otherwise later reconciliation can
      // reconstruct the relocated range and raise its Comment field again.
      getSelection()?.removeAllRanges();
      // Keep the replacement Undo in the pressed margin entry's seat while delivery is open.
      // It is present for focus continuity but unavailable until the log gives the
      // gesture the durable id Undo must name.
      this.#staging = true;
      const sent = (
        this.#controller.dispatch({
          kind: "action",
          verb: outcome,
          detail,
        })?.delivery ?? Promise.resolve(null)
      ).then((accepted) => {
        this.#deciding = null;
        this.removeAttribute("aria-busy");
        if (!accepted) {
          // A definitive refusal is a state the reader can act from. Keep it at the
          // target as Failed, Retry, Cancel; there is no detail disclosure because the
          // transport returned no useful detail beyond the notice it already showed.
          this.#failed = { outcome, label };
          this.#refreshMargin();
          return false;
        }
        // Usually the accepted state has already replayed this decision. Paint is
        // still owed if another part of that state failed to render, but not if the
        // same event list also carried a later undo: authored state then stands.
        if (this.#acceptedStillStands(accepted)) {
          if (this.#presentedOutcome === outcome) {
            this.#refreshMargin();
          } else this.#settle(outcome);
          announce(
            `${outcome === "accept" ? "Accepted" : "Rejected"} suggested change: ${label}`,
          );
        } else {
          this.#refreshMargin();
        }
        // TODO(2026-09-06): Decide whether accepted work with no active agent pickup
        // needs a distinct post-send presentation.
        return true;
      });
      this.#inFlight(sent, focus);
      this.#staging = false;
      return sent;
    }

    #acceptedStillStands(event) {
      return Object.values(this.#controller.read().actions).some(({ standing }) =>
        standing.some((winner) => winner.event.id === event.id),
      );
    }

    #undoable(outcome) {
      return this.#controller
        .read()
        .actions[outcome]?.undo.find((event) => event.action === outcome);
    }

    // The field refuses a second press while the first is unresolved. A pending result
    // that has not painted also marks the widget busy; an optimistic result instead puts
    // that state on its disabled Undo margin entry so the settled prose stays legible.
    #inFlight(decision, focus = null) {
      this.#deciding = decision;
      // Optimistic content already says what the press did. Busy belongs to its disabled
      // Undo margin entry, not as a dimming veil over the settled prose.
      if (decision && !this.#outcome()) this.setAttribute("aria-busy", "true");
      else this.removeAttribute("aria-busy");
      this.#refreshMargin({ immediate: Boolean(focus) });
      focus?.("undo");
    }

    #retryDecision() {
      const failed = this.#failed;
      if (!failed || this.#deciding) return;
      this.#failed = null;
      if (failed.undo) this.#undoOutcome();
      else this.#decide(failed.outcome);
    }

    #cancelFailedDecision() {
      if (!this.#failed || this.#deciding) return;
      this.#failed = null;
      this.#refreshMargin({ immediate: true, focus: this.#focusKey() });
    }

    async #undoOutcome() {
      const outcome = this.#controller.read().state.settlement.value;
      if (!outcome || this.#undoing) return;
      if (this.#staging || this.#deciding) {
        notice("Wait for the current change to finish before undoing");
        return;
      }
      const event = this.#undoable(outcome);
      if (!event) {
        notice("This outcome is no longer available to undo");
        return;
      }
      this.#failed = null;
      this.#undoing = true;
      this.#refreshMargin();
      try {
        if (
          !(await this.#controller.dispatch({
            kind: "undo",
            target: event.attempt ?? event.id,
          })?.delivery)
        )
          this.#failed = { undo: true };
      } finally {
        this.#undoing = false;
        if (this.isConnected) this.#refreshMargin();
      }
    }

    #settle(outcome) {
      // A settle that changes nothing does nothing, which is what makes the poll's
      // replay of this tab's own decision the no-op an absolute action promises to be.
      // The private presented outcome owns that idempotence; the attribute is CSS and
      // export paint and never feeds the component's semantic decisions back in.
      if (this.#presentedOutcome === outcome) return;
      // Read before the state moves: deciding retires the slot, and its words leave
      // the page's reading with it.
      const fold = this.#fold(outcome);
      this.#failed = null;
      this.#deciding = null;
      this.removeAttribute("aria-busy");
      this.#presentedOutcome = outcome;
      this.dataset.lfState = outcome;
      // The retired slot's marker is the layer's rendering of that state, and the
      // theme's one hide rule reads it. The accepted response replays through this
      // method on the gesture's own tab, so it hides the slot in the frame the
      // decision lands; the layer then writes the same mark unconditionally.
      renderRetired(this, outcome);
      // The only remaining circle is Undo, which still acts; the fold and surviving
      // content carry the outcome without leaving another status beside them.
      this.#refreshMargin();
      // The emphasis goes with the pending state: a decided suggestion is plain
      // prose. So does the word naming each slot, which is the same fact said to
      // whoever is listening.
      emphasized.delete(this);
      repaintEmphasis();
      this.#voice();
      fold?.();
    }

    // The retired slot's room, given back as motion rather than taken in a frame. Only
    // where there is room worth following: a slot holding block content is the case that
    // moves the page, and an inline one swaps a few words inside a line the reader is
    // looking at.
    //
    // Measured before the decision and played after it, so the state the rest of the
    // page reads is true from the first frame — the log has it, the banner's count has
    // it, a second tab converging on it has it — while the pixels catch up. The inline
    // display outranks the rule that hides the slot for exactly as long as the fold
    // lasts, and nothing but this function writes it.
    //
    // The height is stated as a border box, whatever the slot's own sizing is. The
    // measurement to hand is the rendered box (padding included, since the block form
    // pads its slots), and starting a content-box height there would open the fold two
    // pixels taller than the paragraph it is replacing — a jump on the first frame, in
    // the one animation written to remove one.
    #fold(outcome) {
      const going = this.querySelector(
        outcome === "accept" ? ":scope > lf-old" : ":scope > lf-new",
      );
      if (!going) return null;
      const style = getComputedStyle(going);
      if (style.display !== "block") return null;
      const from = {
        height: going.getBoundingClientRect().height + "px",
        marginTop: style.marginTop,
        marginBottom: style.marginBottom,
        paddingTop: style.paddingTop,
        paddingBottom: style.paddingBottom,
        opacity: 1,
      };
      const to = Object.fromEntries(Object.keys(from).map((k) => [k, "0px"]));
      to.opacity = 0;
      return () => {
        going.style.display = "block";
        going.style.boxSizing = "border-box";
        going.style.overflow = "hidden";
        const played = motion(going, [from, to], FOLD_MS);
        const done = () => {
          going.style.display = "";
          going.style.boxSizing = "";
          going.style.overflow = "";
        };
        // A fold interrupted — the element taken out from under it — rejects
        // `finished`. Caught, so it is not an unhandled rejection, and the hand-back
        // runs either way. A reader who asked for less motion gets no animation at
        // all (motion returns null), so the hand-back runs at once and the collapse
        // is the frame the decision lands in.
        played ? played.finished.then(done, done) : done();
      };
    }

    // Which slot is which, for a reader listening. A struck red run and a green one
    // are the whole of what says "these words are going" and "these are the proposal",
    // and none of it is text: a screen reader reads the sentence twice, the two
    // readings contradicting each other, with nothing to say that either is a change.
    // Worst on the case the emphasis below hands back for the same reason — an
    // insert- or delete-only change, where the tint is the entire story and a listener
    // hears one perfectly ordinary sentence.
    //
    // ARIA's own names for the two, said as text, because text is the one thing every
    // screen reader announces in every mode — the bargain the mark note struck, and
    // why role="deletion" is not what stands here. It follows the state exactly as the
    // emphasis does: a decided suggestion is plain prose, so the surviving slot gives
    // up this word along with its marks.
    //
    // "proposed", because the word is only ever on a slot nobody has decided and has to
    // say so itself. Pendingness was encoded as the word's presence, which is the one
    // thing no reader can perceive — there is no settled slot alongside to compare it
    // against — and `deletion` is ARIA's name for the act already carried out, so a
    // listener heard a change announced as made while the page was still asking. The
    // theme shows this word wherever the ✓/✗ row is not there to say the same thing.
    #voice() {
      const decided = Boolean(this.#outcome());
      for (const [tag, word] of [
        ["lf-old", "proposed deletion"],
        ["lf-new", "proposed insertion"],
      ])
        for (const slot of this.querySelectorAll(`:scope > ${tag}`))
          quietWord(slot, decided ? "" : word);
    }

    // The words that moved, as ranges over both slots' own text nodes. Which words
    // those are, and whether the pair shares enough ink to be worth marking at all,
    // is `movedWords`.
    #emphasize() {
      if (this.#outcome()) return;
      const oldSlot = this.querySelector(":scope > lf-old");
      const newSlot = this.querySelector(":scope > lf-new");
      if (!oldSlot || !newSlot) return; // insert- or delete-only: the tint is the story
      const [oldSegs, newSegs] = [oldSlot, newSlot].map((slot) => textNodesUnder(slot));
      const read = (segs) =>
        segs.map((s) => s.node.data.slice(s.start, s.end)).join("");
      const moved = movedWords(read(oldSegs), read(newSegs));
      if (!moved) return;
      emphasized.set(this, {
        del: toRanges(oldSegs, moved.del),
        ins: toRanges(newSegs, moved.ins),
      });
      repaintEmphasis();
    }

    // Which of the three changes this is, for anything naming it away from the page:
    // a row on the Asks tray, the label on a comment anchored here. The slots are the
    // whole of the answer — both is a rewrite, lf-new alone inserts, lf-old alone
    // deletes — and it is the reading #voice already speaks on the slots themselves,
    // said once for the element. A settled suggestion keeps the word it had: the
    // retired half stays in the markup, and a decision changed the outcome rather than
    // the kind of thing that was proposed.
    lfWord() {
      const cut = this.querySelector(":scope > lf-old");
      const put = this.querySelector(":scope > lf-new");
      return cut && put ? "rewrite" : put ? "insertion" : "deletion";
    }

    // Its words, for the same askers: the slots' text nodes run together away from the
    // strike and insert paint, and a thread on a rewrite was quoted as
    // "courtyardcovered terrace".
    lfSays() {
      return this.#subject();
    }

    renderState(state) {
      const outcome = state.settlement.value;
      if (outcome) return this.#settle(outcome);
      if (!this.#presentedOutcome) return;
      for (const slot of this.querySelectorAll(":scope > lf-old, :scope > lf-new"))
        for (const animation of slot.getAnimations()) animation.cancel();
      this.#presentedOutcome = null;
      this.removeAttribute("data-lf-state");
      renderRetired(this, null);
      this.#failed = null;
      this.#deciding = null;
      this.removeAttribute("aria-busy");
      this.#refreshMargin();
      this.#voice();
      this.#emphasize();
    }

    #outcome() {
      return this.#controller?.read().state?.settlement?.value ?? null;
    }
  },
);
