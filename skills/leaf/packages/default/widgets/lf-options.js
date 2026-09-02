/* lf-options: a question the reader answers. The theme draws both of its forms and
 * this module makes them answerable — without it the markup still reads as a decision,
 * and nothing here is load-bearing on the look.
 *
 * Which form a group takes is a fact about its options, decided in CSS and never here:
 * an option leading with a <strong> title argues its own case and is a card on a row of
 * its own, and a group whose options are bare labels is a question *about* the page,
 * drawn as compact rows.
 * The difference this module sees is only what a row adds — `for`, the id of the block
 * the row names, rendered as a reference the reader can follow. It points and never
 * speaks: the label stays written in the markup, so the file's reading of the page
 * holds every word the page shows.
 *
 * `choose` takes the reader's pick. Every option carries one injected mark that is both
 * the keyboard path and the state — a toggle reading "choose one" or "choose any" as the
 * group takes one option or several. Once picked, the same mark becomes a check while
 * the option's cell takes a quiet tint. There is no visible status caption: check, tint,
 * and text all saying the same thing made the chosen row louder without making it clearer.
 * The checkbox state carries the same fact for a reader listening. Outside a `choose`
 * group the mark renders as an image-like span, so authored state keeps the check and an
 * accessible name without pretending it can be pressed.
 *
 * The pick is a set, whatever the group allows. `multiple` lets it hold more than one
 * and clicking toggles each option in or out; without it a click makes that option the
 * only pick and clicking it again empties the set. One shape either way — the action
 * states the whole set, absolutely, so replaying this tab's own pick is a no-op and a
 * second tab converges rather than drifting. A click the whole option takes is one
 * nothing in the option wanted: a drag that ended here is that selection's, and a press
 * on the evidence an option argues from — a shot to flip, a disclosure to open, a link
 * to follow — belongs to what it landed on (`worksInside`).
 *
 * The last cell of a page choose group is the option the reader writes. Submitting it
 * appends a real option and selects it through the same `choose` action as every other
 * pick. The action carries the complete generated option set as well as the selection,
 * so replay, a later ordinary pick, and undo all reconstruct one absolute state. It is
 * not a conversation: if the agent needs clarification after carrying the option into
 * the page, it can open a separate thread anchored to that option.
 *
 * The keyboard walk stops at options. Enter from an option mark reaches the add field;
 * Tab remains the platform's own path through every control. A generated option joins
 * the walk on replay just like an authored one.
 *
 * In a thread the existing reply box already owns those words, so Enter reaches that
 * box and a `multiple` group grows a Done press instead: every toggle reaches
 * the agent as it lands, so the press is the one statement that the set is whole,
 * posted as an `answer` action and held as the thread decision's closing condition
 * (x-awaits.until). Answered is paint on the press, never a wider word, and the set can
 * still change after — each later toggle still reaches the agent, who reads the log.
 *
 * That paint goes on the press and nowhere else, which is a rule rather than a
 * preference. A module writes an attribute in the author's namespace only where the
 * registry declares it as a verb's record form — `chosen` is one, so a version can
 * carry a pick and `version check` can hold the markup against the log's fold — and
 * the entry's `additionalProperties: false` is the whole of what else may stand
 * there. This module wrote two that nothing declared. `answered` recorded the
 * thread-only `answer` verb, and a thread's markup is frozen in the log, so no
 * version could ever have honored a record of it; `open` recorded which way this
 * tab last left the disclosure, which no version carries at all. Each was a second
 * copy of a fact the module already states on the control that carries it — the
 * mark's `aria-checked`, the row's `aria-expanded` — so the theme keys on those,
 * the way lf-tabs' strip already does, and the group's own attributes are the
 * author's again. What the copies cost was a reader that believed them:
 * `shallowSigs` excludes exactly what no version can assert, and read both of these
 * as state a version had written.
 *
 * The keyboard path: every mark is a checkbox, so Tab reaches it and Space toggles. From a
 * mark, ↑/↓ walk the options (a clamp at the ends, not a wrap), 1–9 pick outright, and
 * Enter reaches the page's box for another option — each option wears its digit and the
 * add cell wears Enter in their shared column, painted only while a mark holds keyboard
 * focus, so nothing appears on a page nobody is answering. The column is held whether or
 * not a key is in it, which is the theme's half of this. The rows are
 * declared per mark, on the mark rather than on the group — the group holds the option's
 * own argument too, and a scope over the whole subtree would promise "toggle the nth" with
 * focus on a link inside one. An armed `g` chord keeps its own digits without this module
 * asking: its scopes suspend every scope inside them, where each widget used to have to
 * remember the question.
 *
 * `settled` retires the decision once it has been made and acted on: the group collapses
 * to one line naming the chosen option, with every option — the chosen one included —
 * behind a disclosure. Nothing is deleted, so the ids, the anchors on them, and check's
 * id-survival rule are all untouched; what's reclaimed is the height. Open or closed is
 * view state for this reader, remembered per browser tab in tabStore like a lf-tabs
 * tab: opening a settled group is reading, not editing, so it sends no action and no
 * version carries it. Collapsed options wear hidden="until-found", so find-in-page and
 * the runtime's reveal() (a click on a comment's quote) both open the group rather than
 * jumping to an option nobody can see, and while the version diff is on the row wears a
 * Δ count so a change can't hide behind the collapse. A settled group still takes a pick
 * once opened — settling is a sweep, not a lock, and the summary line follows whatever is
 * chosen, including back to a bare "Settled" when the reader clears it.
 *
 * Inside an exhibit the group is quoted — exhibited, not offered — so it takes the
 * same path as a group that never declared `choose`: the mark is a span, the click
 * handler is never wired, there is no cell for an option of the reader's own, and an
 * example decision can't be answered. `settled` still collapses there, because quoting
 * gates the action channel and not presentation.
 *
 * Authored content is never replaced, so there is no failSoft. */
import { OptionAddition } from "./lf-options-addition.js";
import { SettledOptions } from "./lf-options-settled.js";
import {
  actionStands,
  conversationInput,
  focused,
  inChrome,
  keys,
  landInConversation,
  labelOf,
  offer,
  once,
  quoted,
  reachedForWords,
  relabel,
  selectableOffer,
  sendAction,
  notice,
  walkRows,
  worksInside,
  wrote,
} from "/runtime/widget-api.js";

// What an option is called, in either form: its title where it leads with one, and its
// own words where the label is all it has. `wrote` rather than `says`, because a picked
// option's mark is the page speaking and belongs to what the reader can point at — not
// to the option's name, which is what every caller here wants. A settled title's answer
// to an option with neither is to say "Settled" rather than name an id nobody wrote.
const label = (option) => wrote(option.querySelector(":scope > strong") ?? option);

// The offer, and how many of the group it takes. The mark is the whole of what says that,
// a group's prose being deliberately silent — captioning a control the reader can already
// read is exactly what the corner shape is for — and the corner is paint, which reaches
// nobody listening. So the mark states the arity twice, once in each register one control
// has: the shape for the eye, and this word, which goes into the aria-label below and is
// drawn at font-size 0 (theme.css) so the offer stays silent on screen. A reader who hears
// "choose any" knows the next press adds where "choose one" would have replaced, and
// knows it while the question is still open rather than after answering it.
const OPEN = { one: "choose one", any: "choose any" };
const SELECTED = "selected";

const SECTION = "In a question's options";
const WRITE_ANOTHER = {
  id: "option.write",
  keys: ["Enter"],
  does: "Write another option",
  line: "write another option",
};

customElements.define(
  "lf-options",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) {
        this.#addition?.connect();
        this.#settled?.connect();
        return;
      }
      // Quoted material is exhibited, not offered, so a specimen renders exactly like a
      // group that was never choosable: it shows what a decision looks like without
      // taking one.
      const choosable = this.hasAttribute("choose") && !quoted(this);
      for (const option of this.#options()) this.#reference(option);
      // Without `choose` there is nothing to press: the mark still reports the
      // document's state, as a span.
      for (const option of this.#options())
        if (choosable || option.hasAttribute("chosen")) this.#mark(option, choosable);
      this.#addition = new OptionAddition(this, {
        offered: choosable && !inChrome(this),
        shortcut: labelOf(WRITE_ANOTHER),
        commit: (detail, attempt) => {
          this.#applyChoice(detail);
          return sendAction(this, "choose", detail, { attempt });
        },
      });
      this.#addition.connect();
      if (choosable) {
        if (this.hasAttribute("multiple") && inChrome(this)) this.#doneRow();
        this.#keys();
      }
      if (this.hasAttribute("settled")) {
        this.#settled = new SettledOptions(this, { label });
        this.#settled.connect();
      }
      if (!choosable) return;
      this.addEventListener("click", (e) => {
        // A click ending a drag-select belongs to the selection rather than the option.
        const option = e.target.closest?.("lf-option");
        if (!option || option.parentElement !== this) return;
        if (e.detail !== 0 && reachedForWords(option)) return;
        // A click something in the option has a use for is not a pick: the reader was
        // working the case — flipping a shot, opening a disclosure, following a link —
        // rather than choosing between the options. `worksInside` is the whole of that
        // question, and what it cannot answer is which of the controls in here this
        // module put there: the mark is the pick's own control, and the digit stands in
        // the column beside it, so a press on either is aimed at this option after all.
        const inner = worksInside(e.target, option);
        if (inner && !inner.matches(".lf-pick, .lf-address")) return;
        const was = this.#picked();
        // Toggling is one gesture both ways, so a reader who picked by mistake needn't
        // pick something else to get out of it. Without `multiple` the set the toggle
        // starts from is empty, which is what makes a pick replace rather than join.
        const next = new Set(this.hasAttribute("multiple") ? was : []);
        if (was.has(option)) next.delete(option);
        else next.add(option);
        this.#pick(next);
        this.#addition.remember(next);
        const name = label(option) || option.id;
        const said = !next.size
          ? "Cleared selection"
          : next.has(option)
            ? `Chose “${name}”`
            : `Dropped “${name}”`;
        sendAction(this, "choose", this.#addition.detailFor(next)).then((ok) => {
          if (ok) notice(`${said} — recorded`);
        });
      });
    }

    #addition = null;
    #settled = null;
    #done = null; // the thread multi-question's submit; null everywhere else
    #answering = null; // the answer in flight, so a second press joins it

    #options() {
      return this.querySelectorAll(":scope > lf-option");
    }

    #picked() {
      return new Set([...this.#options()].filter((o) => o.hasAttribute("chosen")));
    }

    #marks() {
      return [
        ...this.querySelectorAll(':scope > lf-option > .lf-pick[role="checkbox"]'),
      ];
    }

    // The words this question does not already list. On the page the group owns a plain
    // add field; in a thread the surrounding conversation still owns its reply box.
    #words() {
      return this.#addition.input ?? conversationInput(this);
    }

    // The one statement a live channel can't derive: the set is whole. One press,
    // one `answer` action, and the decision this group stands as is discharged
    // (x-awaits.until). One-way — a later toggle still reaches the agent, so there
    // is nothing to take back — and the answer is paint rather than a fold, so
    // the pressed control's own line holds still.
    #doneRow() {
      this.#done = offer("button", "lf-btn lf-done", "Done");
      this.#done.setAttribute("aria-label", "Done: my picks here are complete");
      this.#done.setAttribute("aria-pressed", "false");
      this.#done.onclick = () => this.#answer();
      this.append(this.#done);
    }

    // The press is answered at once and the answer waits for the log, which is the
    // rule a decision follows (CLAUDE.md): nothing here has moved yet, so there is
    // nothing to un-show, and what the reader is owed meanwhile is that the press
    // landed. `aria-busy` says exactly that, and the promise beside it is what makes
    // the sentence above true — one press, one `answer` action, however many times
    // the button is hit while the first is still in the wire.
    #answer() {
      if (this.#answering) return this.#answering;
      const sent = sendAction(this, "answer", {}).then((accepted) => {
        this.#sending(null);
        if (!accepted) return false; // unsent means unrecorded, and nothing was painted
        // Usually replay has painted the accepted answer already. Repeat the absolute
        // paint for a partial render, but never over a same-read undo of this action.
        if (actionStands(accepted)) this.#answered(true);
        notice("Marked answered — recorded");
        return true;
      });
      this.#sending(sent);
      return sent;
    }

    // One fact said twice, and said here so the two cannot come apart: the field
    // refuses the second press, and the attribute is what the layer paints and a
    // screen reader holds its announcements through. On the button rather than the
    // group, because the button's own state is the one in flight — the options are
    // still the reader's to work.
    #sending(answer) {
      this.#answering = answer;
      if (answer) this.#done.setAttribute("aria-busy", "true");
      else this.#done.removeAttribute("aria-busy");
    }

    // Absolute: answered is the whole statement, so replaying this tab's own press
    // is the same call again. Replay paints it when the log takes the answer: the log
    // holds it, and the pressed state is what the page shows for it (see the header).
    #answered(on) {
      this.#done?.setAttribute("aria-pressed", String(on));
      document.dispatchEvent(new CustomEvent("lf-answered"));
    }

    // The keyboard path past Tab: from a mark, ↑/↓ walk the options, a digit picks
    // outright, and Enter reaches the box for the option the author did not list.
    // Declared on the mark, so those keys typed in the box stay text and a nested
    // group's marks stay its own, and an armed g chord keeps its own digits without
    // this module asking — its scopes suspend every scope inside them. Each option
    // shows its digit only while a mark holds keyboard focus (the theme's
    // :focus-visible rule), so the address appears exactly when a key could use it.
    #keys() {
      for (const address of this.querySelectorAll(":scope > lf-option > .lf-address"))
        address.remove();
      const marks = this.#marks();
      // The addressable options: at most nine, since the digits are the addresses.
      const addresses = marks.slice(0, 9).map((_, n) => String(n + 1));
      for (const [i, mark] of marks.entries()) {
        if (i < 9) {
          // Chrome like the § reference: a thing to work rather than a word the
          // page says, so the gate, the anchor pass, and paper all read it as the
          // control apparatus it is. The key line speaks the keys; this is the
          // eye's copy, hence aria-hidden.
          // Into the column the option reserves for it, which is what lets a digit
          // arrive without moving anything and land on nobody's words (theme).
          // Prepended, which puts it before the mark the module also puts first. Order
          // between the two decides nothing: the digit is out of flow in a column of its
          // own, so it is a corner badge wherever it sits in the DOM, and it is
          // aria-hidden, so it is not a stop the reading order can put in the wrong
          // place. What matters is that both stand before the option's own words.
          const num = offer("span", "lf-address", String(i + 1));
          num.setAttribute("aria-hidden", "true");
          mark.parentElement.prepend(num);
        }
        // Declared on the mark rather than on the group, because the group holds the
        // option's own argument too — a link, a say-box, a tabbed exhibit — and a scope
        // over the whole subtree would promise "toggle the nth" with focus on any of them.
        // Every mark says the same sentences, so the reference gathers them into one
        // section however many options the page holds.
        //
        // "toggle", the digit row's word, because it is what the press does: the nth digit on
        // an already-picked option clears it, and a word that said "pick" was false on the
        // branch the reader could see.
        keys(mark, SECTION, [
          {
            id: "option.toggle-nth",
            runFromReference: false,
            // The digits this group has, so the row cannot offer an address no option
            // wears. Generated-option reconciliation replaces these scopes after the
            // live set changes, while surviving marks keep their element identity.
            keys: addresses,
            label: addresses.length > 1 ? `1–${addresses.length}` : "1",
            does: "Toggle the nth option",
            line: "toggle the nth",
            run: (binding) => {
              const target = marks[+binding - 1];
              target.focus();
              target.click();
            },
          },
          {
            ...WRITE_ANOTHER,
            when: () => Boolean(this.#words()),
            returnFrame: () => {
              const box = this.#words();
              const layer = this.#addition.input
                ? box?.closest("form")
                : box?.closest(".lf-thread, .lf-conversation-thread, .lf-conversation");
              return {
                active: () => Boolean(layer?.contains(focused())),
                close: () => box?.blur(),
                does: "Return to the option",
                line: "back to option",
              };
            },
            run: () => {
              if (this.#addition.input) this.#addition.input.focus();
              else
                landInConversation(this.#words(), {
                  target: mark,
                  line: "back to question",
                });
            },
          },
          {
            id: "option.walk",
            keys: ["ArrowUp", "ArrowDown"],
            routes: [
              {
                id: "option.previous",
                binding: "ArrowUp",
                does: "Previous option",
              },
              { id: "option.next", binding: "ArrowDown", does: "Next option" },
            ],
            does: "Walk the options",
            line: "walk the options",
            repeat: true,
            // Clamped at the ends, and the page must not scroll out from under the walk.
            run: (binding) => walkRows(marks, binding === "ArrowDown" ? 1 : -1),
          },
          {
            id: "option.toggle",
            keys: [" "],
            does: "Toggle the focused option",
            line: "toggle",
            run: () => mark.click(),
          },
          // Tab is the platform's, and reaching the mark is what a reader has to know
          // before any of the above is any use. No binding, so the line never offers it.
          {
            id: "option.reach",
            keys: [],
            label: "⇥",
            does: "Reach an option's mark",
          },
        ]);
      }
    }

    // The block this option is about. A pointer, not a voice: its text is the id it
    // names, which is the same way the thread panel writes an element anchor, and
    // chrome throughout — a thing to work and nothing else, so paper drops it.
    #reference(option) {
      const target = option.getAttribute("for");
      if (!target) return;
      const ref = offer("a", "lf-ref", `§ ${target}`);
      ref.href = `#${target}`;
      option.append(ref);
    }

    // The keyboard affordance and the state marker, one element — a checkbox whose click
    // bubbles into the group's pick handler where there's a pick to make, and the same
    // mark as a span where there isn't.
    #mark(option, pressable) {
      // A press wears the chrome face and .lf-ui reaches exactly as far as the control
      // does; the other shape holds no control at all, so it needs neither. What each one
      // *says* is a separate question both shapes answer the same way (#label), and the
      // answer is what decides whether a comment can land on it. data-lf-gen either way,
      // since the diff parses the base version unupgraded and would read any mark as text
      // that version lacked.
      const mark = pressable
        ? selectableOffer("checkbox", "lf-pick")
        : document.createElement("span");
      if (!pressable) {
        mark.className = "lf-pick";
        mark.dataset.lfGen = "1";
      }
      // First, so the row form's table puts it in the cell before the words. A card
      // places its mark out of flow and cannot see this, so one insertion serves both
      // forms and the theme states each form's placement as it already did. The mark
      // ends every row at the column the label opens at, which is where the reader is
      // reading; it stood at the line's end, ~620px away from the words it answers for
      // in a full-width group, and a group that took several answers drew its boxes
      // there while a single-pick card drew none at all.
      option.prepend(mark);
      this.#label(option);
    }

    // An absolute placement: `picked` is the whole answer, so every option is stated,
    // not just the ones that changed.
    #pick(picked) {
      for (const option of this.#options()) {
        option.toggleAttribute("chosen", picked.has(option));
        this.#label(option);
      }
      this.#settled?.sync();
      // A pick is an answer to what this group was asking. The banner's count and the
      // page's marks both follow from the same one signal, here rather than at the
      // sender, so a pick this tab rewound and one another tab made both reach them.
      document.dispatchEvent(new CustomEvent("lf-answered"));
    }

    // The mark's text is an accessible fallback rather than a visible status caption.
    // The check and cell tint carry selection on screen; aria-checked carries it on the
    // live control. An authored, inert mark becomes an image with the same plain name.
    #label(option) {
      const mark = option.querySelector(":scope > .lf-pick");
      if (!mark) return;
      const chosen = option.hasAttribute("chosen");
      const word = chosen
        ? SELECTED
        : OPEN[this.hasAttribute("multiple") ? "any" : "one"];
      relabel(mark, word, { says: false });
      if (!mark.matches('[role="checkbox"]')) {
        mark.setAttribute("role", "img");
        mark.setAttribute("aria-label", `${SELECTED}: ${label(option) || option.id}`);
        return;
      }
      // "option i of n" the way a native radio group announces position: the arity
      // word says how many the group takes, this says how many there are to take
      // from — the fact a listening reader otherwise has to walk the list to learn.
      const options = [...this.#options()];
      mark.setAttribute(
        "aria-label",
        `${word}: ${label(option) || option.id} — option ${
          options.indexOf(option) + 1
        } of ${options.length}`,
      );
      mark.setAttribute("aria-checked", String(chosen));
    }

    disconnectedCallback() {
      this.#addition?.disconnect();
      this.#settled?.disconnect();
    }

    #applyChoice(detail) {
      for (const option of this.#addition.reconcile(detail.additions ?? {}, this.#done))
        this.#mark(option, true);
      this.#keys();
      this.#pick(
        new Set(
          detail.options
            .map((id) => document.getElementById(id))
            .filter(
              (option) => option?.matches("lf-option") && option.parentElement === this,
            ),
        ),
      );
    }

    // {options}: exactly these are this group's picks — an empty list for no pick at
    // all, which is how clearing travels rather than a second verb. `additions`, when
    // present, maps the complete set of reader-authored option ids to their words.
    // `answer` is the Done
    // press's statement that the set is whole; empty detail, because answered is the
    // whole of it.
    applyAction(action, detail) {
      if (action === "answer") return this.#answered(true);
      if (action !== "choose") return;
      this.#applyChoice(detail);
    }

    lfWord() {
      return "options";
    }
  },
);
