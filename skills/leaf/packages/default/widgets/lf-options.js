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
 * group takes one option or several, which becomes "your pick" once this reader picks it,
 * or "chosen" where the document already carries it. One
 * element for both, so nothing hides, nothing moves, and a keyboard pick leaves focus
 * where it was. Which word a mark wears is asked of the option rather than of the call
 * that changed it: picked and authored-chosen reads "chosen", picked otherwise reads
 * "your pick". Outside a `choose` group the same mark renders as a span — the document's
 * state, with nothing to press, and so a passage a user can quote rather than a
 * label anchoring skips.
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
 * The last cell of a choose group is the option the reader writes. It is the runtime's
 * conversation (x-conversation) — this module places it, and the runtime owns its
 * messages, drafts and sends — but what it is *for* is the answer the author didn't
 * think of, which is why it says "Another option" and is dressed as a cell of the
 * group rather than as a box hanging under it. A menu that takes only what it already
 * lists makes the reader pick the nearest wrong thing.
 *
 * The keyboard walk below stops at the authored options, and that is deliberate rather
 * than an oversight: ↑/↓ inside a textarea are the caret's, so a walk that stepped into
 * this cell would have no step back out. Enter from an option mark steps into the box;
 * Tab remains the platform's own path through every control.
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
 * Enter reaches the page's box for another option — each option wears its digit in a
 * column of its own, painted only while a mark holds keyboard focus, so nothing appears
 * on a page nobody is answering. The column is held whether or not a digit is in it,
 * which is the theme's half of this. The rows are
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
import {
  HIDDEN,
  PRESS,
  actionStands,
  conversationBox,
  conversationInput,
  inChrome,
  keys,
  landInConversation,
  measure,
  offer,
  once,
  quoted,
  reachedForWords,
  relabel,
  reserve,
  selectableOffer,
  sendAction,
  tabStore,
  toast,
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
const PICKED = "your pick"; // this reader picked it, this session
const AUTHORED = "chosen"; // the document arrived carrying the pick

// The word the last cell wears while it is still empty, and the accessible name of the
// box in it. Named for what the cell supplies rather than for the act of typing into it:
// "Say something" put a chat box under a question, and a chat box beneath a menu reads as
// somewhere to leave an aside — when what it takes is the one answer the menu hasn't got.
const ANOTHER = "Another option";

const SETTLED_KEY = "lf-settled:";

const SECTION = "In a question's options";

customElements.define(
  "lf-options",
  class extends HTMLElement {
    #diffEvents = null;
    #diffable = false;

    connectedCallback() {
      if (!once(this)) return this.#listenForDiff();
      // An authored `chosen` (the honoring version carrying an earlier pick) wears the
      // same mark a live pick wears, so honoring doesn't change the look — but worded as
      // the document's state, not attributed to this reader.
      this.#authored = new Set(
        [...this.#options()].filter((o) => o.hasAttribute("chosen")).map((o) => o.id),
      );
      // Quoted material is exhibited, not offered, so a specimen renders exactly like a
      // group that was never choosable: it shows what a decision looks like without
      // taking one.
      const choosable = this.hasAttribute("choose") && !quoted(this);
      for (const option of this.#options()) this.#reference(option);
      // Without `choose` there is nothing to press: the mark still reports the
      // document's state, as a span.
      for (const option of this.#options())
        if (choosable || this.#authored.has(option.id)) this.#mark(option, choosable);
      // Off the mark's own box, so it waits for one: this group may be a question
      // an agent asked in a reply, and the panel that holds it opens later.
      measure(this, () => this.#holdWordRoom());
      if (choosable) {
        this.#another = conversationBox(this, ANOTHER);
        if (this.#another) this.append(this.#another);
        if (this.hasAttribute("multiple") && inChrome(this)) this.#doneRow();
        this.#keys();
      }
      if (this.hasAttribute("settled")) this.#settle();
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
        const name = label(option) || option.id;
        const said = !next.size
          ? "Cleared your pick"
          : next.has(option)
            ? `Chose “${name}”`
            : `Dropped “${name}”`;
        sendAction(this, "choose", { options: [...next].map((o) => o.id) }).then(
          (ok) => {
            if (ok) toast(`${said} — recorded`);
          },
        );
      });
    }

    #authored = new Set(); // ids the document arrived carrying, so a mark words itself honestly
    #another = null; // the option the reader writes, hidden with the settled options
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

    // The words this question does not already list. On the page the group owns the
    // first-message box it appended; in a thread the surrounding conversation owns its
    // reply box. One reading for the Enter row, across the shadow boundary between them.
    #words() {
      return conversationInput(this.#another ?? this);
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
        toast("Marked answered — recorded");
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
          // Prepended, so the mark stays the row's last child: the digit is a corner
          // badge wherever it sits in the DOM, and the apparatus keeps ending at the
          // mark.
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
            // wears. Stated rather than counted at each paint, because a group's options
            // come from markup and do not change under the reader.
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
            id: "option.write",
            keys: ["Enter"],
            does: "Write another option",
            line: "write another option",
            when: () => Boolean(this.#words()),
            run: () =>
              landInConversation(this.#words(), {
                target: mark,
                line: "back to question",
              }),
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
      option.append(mark);
      this.#label(option);
    }

    // The room the marks' word will need, held before the press that writes one: a mark
    // is the one thing on the row a press may not move, and the word it gains is exactly
    // what would move it. That room is a measurement rather than a constant — 68px
    // covered "your pick" in the face macOS sets the chrome in and came 2px short of the
    // one Linux does — so it is taken from the words themselves in a mark's own live
    // face, and taken in the said state, because an unsaid mark renders at font-size 0
    // (theme.css) and measured there it reserves nothing at all.
    //
    // Stated, not applied: which marks hold this room is a fact about the group's form,
    // which is CSS's to decide and never this module's (see the header). So the number
    // lands on the group, every mark inherits it, and the row form is what spends it.
    // Measured off the first mark, since they all say the same words in the same face.
    #holdWordRoom() {
      const mark = this.querySelector(":scope > lf-option > .lf-pick");
      if (!mark) return;
      relabel(mark, PICKED, { says: true });
      reserve(mark, [PICKED, AUTHORED]);
      // `reserve` floors the control it measured; the room is the form's rather than
      // that one mark's, so it moves off. Then the mark says what it actually says.
      this.style.setProperty("--lf-word-room", mark.style.minWidth);
      mark.style.minWidth = "";
      this.#label(mark.parentElement);
    }

    // An absolute placement: `picked` is the whole answer, so every option is stated,
    // not just the ones that changed.
    #pick(picked) {
      for (const option of this.#options()) {
        option.toggleAttribute("chosen", picked.has(option));
        this.#label(option);
      }
      this.#retitle();
      // A pick is an answer to what this group was asking, and a mark that now reads
      // "your pick" is a word the page didn't have before: the banner's count and the
      // page's marks both follow from the same one signal, here rather than at the
      // sender, so a pick this tab rewound and one another tab made both reach them.
      document.dispatchEvent(new CustomEvent("lf-answered"));
    }

    // Which kind of word the label is travels with it, on both shapes of mark and on
    // every write: the offer is a thing to do, so it leaves the printed page and no comment
    // lands on it, while a picked option's mark is the only place the page says where the
    // pick sits — paper keeps that one and a user can point at it. Asked of the label
    // rather than of the element, because one mark is both over its life and neither shape
    // is a <button> to tell them apart by.
    //
    // Then what only a control needs: an accessible name saying which option it picks and
    // how many of the group are on offer, containing the visible word, and the checked
    // state.
    #label(option) {
      const mark = option.querySelector(":scope > .lf-pick");
      if (!mark) return;
      const chosen = option.hasAttribute("chosen");
      const word = !chosen
        ? OPEN[this.hasAttribute("multiple") ? "any" : "one"]
        : this.#authored.has(option.id)
          ? AUTHORED
          : PICKED;
      relabel(mark, word, { says: chosen });
      if (!mark.matches('[role="checkbox"]')) return;
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

    // ---------- settled ----------

    #row = null; // the one-line summary a settled group collapses to
    #title = null; // the part of it naming the chosen option
    #isOpen = false; // this tab's reading of the group; #open renders it, nothing reads it back

    #settle() {
      // A disclosure is a thing to work, and what it names — the chosen option — the
      // options themselves say once paper opens the group. On screen they do not: the row
      // is the decision's only visible statement while the group stays collapsed, so the
      // part of it naming the option is the page speaking and says so, and the anchor pass
      // reads it over the row's chrome. The count beside it is the runtime talking about
      // the document, which is why the two are separate spans.
      this.#row = selectableOffer("button", "lf-settled");
      this.#title = document.createElement("span");
      const options = [...this.#options()];
      const count = document.createElement("span");
      count.className = "lf-settled-count";
      count.textContent = `${options.length} option${options.length === 1 ? "" : "s"}`;
      this.#row.append(this.#title, count);
      this.#row.setAttribute("aria-controls", options.map((o) => o.id).join(" "));
      this.#row.onclick = () => this.#open(!this.#isOpen, true);
      keys(this.#row, "In a settled decision", [
        {
          id: "option.toggle-settled",
          keys: PRESS,
          does: "Open or close the settled decision",
          line: "open or close",
          run: () => this.#row.click(),
        },
      ]);
      // The authored question is the heading outside this group. Inside the group the
      // settled summary is therefore its first reading, before the options it folds.
      this.prepend(this.#row);
      for (const option of options) {
        // The browser found something inside (find-in-page, an anchor jump), or the
        // runtime is about to scroll a comment anchor into view: open up.
        option.addEventListener("beforematch", () => this.#open(true, true));
        option.addEventListener("lf-reveal", () => this.#open(true, true));
      }
      this.classList.add("lf-rendered"); // the upgraded marker every widget uses
      this.#retitle();
      this.#open(tabStore.get(SETTLED_KEY + this.id) === "1", false);
      // Δ badges follow the version diff; the runtime announces each toggle.
      this.#diffable = true;
      this.#listenForDiff();
    }

    disconnectedCallback() {
      this.#diffEvents?.abort();
      this.#diffEvents = null;
    }

    #listenForDiff() {
      if (!this.#diffable || this.#diffEvents) return;
      this.#diffEvents = new AbortController();
      document.addEventListener("lf-comparison", () => this.#delta(), {
        signal: this.#diffEvents.signal,
      });
    }

    #open(open, remember) {
      this.#isOpen = open;
      // The reader's own option and the Done press go behind the collapse with the
      // authored ones: all of them belong to the question, and a settled group asks
      // nothing until the reader opens it again — a Done left standing was a button
      // under a summary with nothing above it to be done with.
      for (const el of [
        ...this.#options(),
        ...(this.#another ? [this.#another] : []),
        ...(this.#done ? [this.#done] : []),
      ])
        if (open) el.removeAttribute("hidden");
        else el.setAttribute("hidden", HIDDEN);
      this.#row.setAttribute("aria-expanded", open ? "true" : "false");
      if (remember) tabStore.set(SETTLED_KEY + this.id, open ? "1" : "0");
    }

    // The summary carries the decision, so it names whichever options hold it —
    // including after a pick made in an opened group, which would otherwise leave the
    // line contradicting the options it hides.
    #retitle() {
      if (!this.#title) return;
      const names = [...this.#picked()].map(label).filter(Boolean);
      relabel(this.#title, names.length ? `Settled: ${names.join(", ")}` : "Settled", {
        says: true,
      });
    }

    // One Δn chip on the row when the diff marks passages inside, so the toast's count is
    // accounted for even where the marks sit behind the collapse.
    #delta() {
      this.#row.querySelector(".lf-settled-diff")?.remove();
      const n = this.querySelectorAll(".lf-ins-block").length;
      if (!n) return;
      const chip = document.createElement("span");
      chip.className = "lf-settled-diff";
      chip.textContent = `Δ${n}`;
      this.#row.append(chip);
    }

    // {options}: exactly these are this group's picks — an empty list for no pick at
    // all, which is how clearing travels rather than a second verb. `answer` is the
    // Done press's statement that the set is whole; empty detail, because answered
    // is the whole of it.
    applyAction(action, detail) {
      if (action === "answer") return this.#answered(true);
      if (action !== "choose") return;
      this.#pick(
        new Set(
          detail.options
            .map((id) => document.getElementById(id))
            .filter((o) => o?.matches("lf-option") && o.parentElement === this),
        ),
      );
    }

    lfWord() {
      return "options";
    }
  },
);
