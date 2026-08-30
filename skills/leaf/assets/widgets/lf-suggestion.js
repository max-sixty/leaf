/* lf-suggestion: an edit to content the reader has already seen, offered as a
 * proposal rather than shipped as a fait accompli. Accept or Reject rides the action
 * channel; the next version eventually carries the settled markup.
 *
 * The log owns the absolute outcome, so reloads and tabs converge. Once that outcome
 * stands, the surviving slot remains and the retired slot folds away as trackable
 * motion. The pressed control stays where the gesture happened and changes to a past-
 * tense record while its pair gives up ink but not room. Each control therefore reserves
 * the width of both of its possible words from the table below before it is shown.
 *
 * The suggestion owns only those controls and their semantics. It contributes the row
 * through `registerMarginItem`; the living margin joins it to comment threads,
 * decisions, outcomes, activity, and temporary reaction controls for this same target.
 * That owner hoists and places the one resulting item, measures the rail, docks it when
 * the margin is too narrow, and reads rendered descendants when a project makes the
 * target `display: contents`. A suggestion never creates a second RHS surface or
 * geometry model of its own. */
import {
  actionStands,
  alignText,
  FOLD_MS,
  measure,
  marginAction,
  motion,
  offer,
  once,
  quietWord,
  quoted,
  relabel,
  renderRetired,
  registerMarginItem,
  reserve,
  says,
  sendAction,
  textNodesUnder,
  toast,
} from "/runtime/widget-api.js";

// Each control's word in both states — what #name writes, and what the control
// reserves room for, out of the one table so neither can outgrow the other.
const WORDS = {
  accept: ["✓ Accept", "✓ Accepted"],
  reject: ["✗ Reject", "✗ Rejected"],
};
const FACE = {
  accept: { glyph: "✓", tone: "positive" },
  reject: { glyph: "✗", tone: "negative" },
};
const verb = (btn) => (btn.matches(".lf-sug-accept") ? "accept" : "reject");

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

// [from, to) offsets in a slot's concatenated text → Ranges over its text nodes.
function toRanges(segments, spans) {
  const ranges = [];
  for (const [from, to] of spans) {
    const range = document.createRange();
    let pos = 0;
    let started = false;
    for (const seg of segments) {
      const len = seg.end - seg.start;
      if (!started && from < pos + len) {
        range.setStart(seg.node, seg.start + (from - pos));
        started = true;
      }
      if (started && to <= pos + len) {
        range.setEnd(seg.node, seg.start + (to - pos));
        ranges.push(range);
        break;
      }
      pos += len;
    }
  }
  return ranges;
}

customElements.define(
  "lf-suggestion",
  class extends HTMLElement {
    #row = null;
    #deciding = null; // the decision in flight, so a second press joins it
    #margin = null;

    connectedCallback() {
      // Re-connection — a card dragged to another column, a replay moving one — must
      // restore this target's contribution to the shared margin item.
      if (!once(this)) {
        this.#offer();
        return;
      }
      // Presentation, not input, so an exhibited pending change gets it too:
      // quoting gates the action channel, never what a change looks like.
      this.#emphasize();
      this.#voice();
      // Quoted material is exhibited, not offered: a suggestion inside an
      // exhibit shows what a pending change looks like, so it keeps the marks
      // the theme draws and never grows controls to decide it with.
      if (quoted(this)) return;
      // The runtime says it just opened this element's containers (reveal): the row
      // may be waiting on geometry the target only now has, and the caller is about
      // to focus it, so the layout question is answered now rather than at the
      // observer's next frame.
      this.addEventListener("lf-reveal", () =>
        this.#margin?.update({ immediate: true }),
      );
      this.#row = offer("span", "lf-sug-actions");
      this.#row.dataset.lfFor = this.id; // which change it decides, for anyone reading the page
      this.#row.append(this.#button("accept"), this.#button("reject"));
      this.#offer();
      // Off the row's own box, so it waits for one: this change may be one an agent sent
      // in a reply, and the panel holding it opens later. Measured before, both numbers
      // came off a row of no width at all — each control floored at nothing, so the
      // press moved the line it was made on, and the page's rail was stated as bare
      // margin. Neither reads as a missing measurement; they read as small numbers.
      measure(this.#row, () => {
        // In the document now, so each control measures its decided word in the face it
        // actually renders in and floors itself there — the line the press is made on
        // holds still when the word changes (see the module header).
        for (const btn of this.#row.querySelectorAll(
          ":scope > [data-lf-offer='button']",
        ))
          reserve(btn, WORDS[verb(btn)]);
        this.#margin?.update();
      });
    }

    disconnectedCallback() {
      this.#margin?.unregister();
      this.#margin = null;
      emphasized.delete(this);
      repaintEmphasis();
    }

    #offer() {
      if (!this.#row || this.#margin) return;
      this.#margin = registerMarginItem({
        target: () => this,
        controls: this.#row,
        items: () => [
          {
            id: `suggestion:${this.id}`,
            text: this.dataset.lfState
              ? `${this.dataset.lfState === "accept" ? "Accepted" : "Rejected"} suggested change`
              : "Accept or reject suggested change",
            activate: () =>
              this.#row
                .querySelector(
                  this.dataset.lfState
                    ? `.lf-sug-${this.dataset.lfState}`
                    : "[data-lf-offer='button']",
                )
                ?.focus({ preventScroll: true }),
          },
        ],
      });
    }

    // Through `offer` like every other injected control, then through marginAction so
    // this widget supplies only the verb and tone. The shared RHS contract supplies
    // its shape, focus treatment, and responsive label behavior.
    #button(outcome) {
      const btn = offer("button", `lf-sug-${outcome}`);
      btn.onclick = () => this.#decide(outcome);
      this.#name(btn, false, this.#label());
      return btn;
    }

    // Everything a control says, in the state it is in: the word it shows (from
    // WORDS, the same table its reservation is measured from), and the name that has
    // to carry the change as well, since the visible word says only the outcome. The
    // change's own words come in rather than being read here, because settling
    // retires the slot they live in and a name asked for afterwards would answer the
    // id. Both controls restate together — the pair's word flips too, unseen inside
    // its hidden box and inside the room both reserved.
    #name(btn, decided, change) {
      const kind = verb(btn);
      // A decided control's word is the page speaking — "✓ Accepted" states which way
      // the decision went, the way a pick mark's "chosen" states which option won — so
      // it is quotable, and paper and a copy keep the record where they drop the offer.
      // Only the control matching the outcome: its pair flips too, unseen inside its
      // hidden box, and words nobody can see are nobody's to quote.
      relabel(btn, WORDS[kind][decided ? 1 : 0], {
        says: decided && this.#row?.dataset.lfOutcome === kind,
      });
      marginAction(btn, {
        ...FACE[kind],
        label: WORDS[kind][decided ? 1 : 0].replace(/^\S+\s+/, ""),
      });
      btn.setAttribute(
        "aria-label",
        `${kind === "accept" ? "Accept" : "Reject"}${decided ? "ed" : ""} the suggested change: ${change}`,
      );
      // A decision is the end of the matter, so the record it leaves is a record and
      // not a control: it keeps its place and its focus ring, and refuses a press the
      // way #decide already does.
      btn.setAttribute("aria-disabled", String(decided));
    }

    // What the change is about, for the button's label and the toast: the
    // proposal where there is one, since that is what accepting brings about —
    // a deletion has only the markup it would remove.
    #label() {
      const slot =
        this.querySelector(":scope > lf-new") || this.querySelector(":scope > lf-old");
      const text = (slot && says(slot)) || this.id;
      return text.length > 48 ? text.slice(0, 48) + "…" : text;
    }

    accept() {
      return this.#decide("accept");
    }

    // A press asks for the decision; the log makes it, and only then does the page
    // show it. A suggestion can wait because its decision is terminal — the slot
    // retires, the controls stop offering, no later gesture computes from any of
    // it — so nothing is owed the reader during the round trip, and the round trip
    // is local. What waiting buys is the absence of the other half: a settled
    // suggestion the server never took had to be un-settled in front of the reader,
    // a frame of "✓ Accepted" over a fold that started and stopped. The rule that
    // decides which gestures wait, and what waiting costs, are in CLAUDE.md.
    #decide(outcome) {
      if (this.dataset.lfState) return Promise.resolve(true);
      // The decided state used to be this guard on its own, written in the frame of
      // the press. It now lands when the log takes the decision, and the gap between
      // press and answer is exactly wide enough for a second press to make a second
      // decision beside the first — two lines in the log for one act.
      if (this.#deciding) return this.#deciding;
      // Read before deciding: deciding retires a slot, a retired slot leaves the page's
      // reading, and `says` on what has left the reading answers nothing — the toast
      // then named the widget's id instead of the words the user just judged.
      const label = this.#label();
      // Accepting the fix answers the thread it was written for, so the same
      // event carries it: the mapping is snapshotted into the action, because
      // the honoring version retires this wrapper — attribute and all — and a
      // second POST could fail alone, leaving the outcome and the resolution
      // disagreeing with no repair path.
      const comment = this.getAttribute("resolves");
      const detail = outcome === "accept" && comment ? { resolves: comment } : {};
      const sent = sendAction(this, outcome, detail).then((accepted) => {
        this.#inFlight(null);
        if (!accepted) return false; // unsent means unrecorded, and nothing was painted
        // Usually the accepted state has already replayed this decision. Paint is
        // still owed if another part of that state failed to render, but not if the
        // same event list also carried a later undo: authored state then stands.
        if (actionStands(accepted)) this.#settle(outcome);
        toast(
          `${outcome === "accept" ? "Accepted" : "Rejected"} “${label}” — recorded`,
        );
        return true;
      });
      this.#inFlight(sent);
      return sent;
    }

    // One fact said twice, because it is owed to two audiences. The field is what
    // refuses the second press above. The attribute is the platform's own word for a
    // surface mid-update — the layer paints it (leaf.js) and a screen reader holds
    // its announcements until it clears, so the labels are read once, as what they
    // ended up saying. Said here rather than at the two ends of the send, so the two
    // cannot come apart; `lf-draft` says the same word for the same reason.
    #inFlight(decision) {
      this.#deciding = decision;
      if (decision) this.setAttribute("aria-busy", "true");
      else this.removeAttribute("aria-busy");
    }

    #settle(outcome) {
      // A settle that changes nothing does nothing, which is what makes the poll's
      // replay of this tab's own decision the no-op an absolute action promises to be.
      // The attribute was idempotent on its own and the fold is not: replayed, it
      // folded a slot that had already folded, from a height it no longer had.
      if (this.dataset.lfState === outcome) return;
      // Read before the state moves: deciding retires the slot, and its words leave
      // the page's reading with it.
      const change = this.#label();
      const fold = this.#fold(outcome);
      this.dataset.lfState = outcome;
      // The retired slot's marker is the layer's rendering of that state, and the
      // theme's one hide rule reads it. The accepted response replays through this
      // method on the gesture's own tab, so it hides the slot in the frame the
      // decision lands; the layer then writes the same mark unconditionally.
      renderRetired(this);
      if (this.#row) {
        // The row stays; what changes is which of the two controls is speaking. A
        // quoted one grew none.
        this.#row.dataset.lfOutcome = outcome;
        for (const btn of this.#row.querySelectorAll(
          ":scope > [data-lf-offer='button']",
        ))
          this.#name(btn, true, change);
      }
      this.#margin?.update();
      // The emphasis goes with the pending state: a decided suggestion is plain
      // prose. So does the word naming each slot, which is the same fact said to
      // whoever is listening.
      emphasized.delete(this);
      repaintEmphasis();
      this.#voice();
      fold?.();
      // The banner's count of what the page is still asking is derived from the page,
      // so tell it the page changed rather than making it poll the DOM.
      document.dispatchEvent(new CustomEvent("lf-answered"));
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
      const decided = Boolean(this.dataset.lfState);
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
      if (this.dataset.lfState) return;
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
    // a row on the decisions tray, the label on a comment anchored here. The slots are the
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

    // accept | reject: the outcome is absolute, so replaying the sender's own
    // action is a no-op and a second tab lands in the same state.
    applyAction(action) {
      if (action === "accept" || action === "reject") this.#settle(action);
    }
  },
);
