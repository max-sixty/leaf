/* lf-draft: a block of text the user owns — rewrite it in place, and the exact
 * words reach the agent.
 *
 * The problem this solves that no other widget does: lf-board and lf-options let the
 * user *choose* among things the agent wrote, but never *change* the words. The
 * fastest correction to a sentence is typing the better sentence, not describing it in
 * a comment. That capability is the whole element: one verb (`edit`, the entire new
 * text), no container, no approve/skip chrome. Decisions compose from structures that
 * already own them — put a draft inside a lf-card and the column is the verdict; page
 * assent is sign-off — rather than growing a second set of buttons here.
 *
 * Two rules shape the implementation:
 *
 * 1. Authored text stays in the light DOM as real text. A textarea's value lives off
 *    the text-node tree, so anything inside one is invisible to comment anchoring and
 *    to the version diff. So the body is a plain div — generated, but deliberately NOT
 *    marked .lf-ui or data-lf-gen, because those are exactly the markers that tell the
 *    anchor pass and the diff to look away. A div and not the <pre> the markup wrote,
 *    which would be the tidier swap: <pre> is a text block, and the runtime's comment
 *    line lands on the nearest one, so keeping it puts that line inside the words the
 *    editor is seeded from — the exact failure the marker rules exist for. The textarea
 *    exists only while an edit is open, and its result is written back as text. Read
 *    mode is the resting state; comments and Δ work there. The capture also strips the
 *    indentation the HTML source gave every line, so an agent can indent a draft like
 *    any other child content without the indentation becoming part of the draft's
 *    text.
 * 2. applyAction states absolute values — the whole body, never a patch — so replay is
 *    idempotent, two tabs converge on the last write, and an edit no version has
 *    honored yet re-applies to each new version instead of visibly reverting. Until
 *    one does, the runtime's pending pass marks the element data-lf-pending — the
 *    same mark every decided-and-unhonored widget wears, driven by the registry's
 *    x-state rather than remembered here.
 *
 * Editing has two doors: double-click the text (the fast path), or the ✎ button (the
 * door keyboards and touch can use; it also makes the block *look* editable). It sits
 * in a control row the draft always has, which Cancel and Save join for the length of
 * an edit — one row of the same button either way, so opening one changes what the box
 * offers without changing its shape. Unsent keystrokes ride the runtime's draft store
 * (saveDraft/clearDraft), the composer's discipline: written on input, cleared only by a
 * successful send or explicit Cancel, so reload, version switch, server death and the
 * tab's own close all recover. The text goes in bare, an empty edit being a real
 * replacement the store keeps and only a settlement removing the key — the store's rule,
 * not this widget's exception to it. One edit has one copy across the reader's tabs
 * (watchDraft): an open box follows the words being typed in another, a settled draft
 * closes the box it left behind, and a closed one stays closed.
 * A send owns the shared draft generation until its response, as every composer does:
 * the log attempt makes two tabs' Save presses one action, while the instance flag closes
 * this tab's other edit doors during the request.
 *
 * Once an edit exists, a native disclosure compares the authored body with the
 * standing one and lists the widget's absolute edit actions in log order. The runtime
 * owns that sequence and its version boundary (`watchActions`); the module owns only
 * its presentation. Restoring a row sends its text as one more ordinary edit, which
 * keeps one state model and lets another tab converge without knowing that the gesture
 * happened in a history view.
 *
 * The fast path is taken on the second mousedown rather than on dblclick, because the
 * word the browser selects is selected *by* that mousedown and painted before dblclick
 * arrives: clearing it afterwards is a frame too late, and the user saw a word
 * flash blue and vanish. Cancelling the mousedown's default means there was never a
 * selection to flash, or a comment button to contest the gesture. What that default
 * was saying — "this word" — is carried into the box instead, where a double-click
 * still means what it means everywhere else: type over this word.
 *
 * Chrome is injected through the runtime's `offer`, which marks it .lf-ui for the chrome
 * look, data-lf-gen so the diff ignores it, and data-lf-offer for a thing to work — which
 * is what keeps it off the printed page, out of the anchor pass (this widget declaring no
 * label the page speaks through), and out of the way of the double-click below; the class
 * also earns the edit box the runtime's one textarea rule. Presentation is theme CSS, the
 * swap between the two views included: an open edit is the box being in the document, so
 * the CSS reads that and this module writes no display state at all. Which is also what
 * lets paper disagree — it drops the box and keeps the words. History is chrome too and
 * exists only on a live page; a scriptless copy cannot honestly offer restore. Authored
 * content is never discarded, so there is no failSoft.
 */
import {
  DISCLOSE,
  agentName,
  dataBody,
  once,
  offer,
  quoted,
  sendAction,
  sendDraft,
  toast,
  keys,
  saveDraft,
  loadDraft,
  clearDraft,
  watchDraft,
  alignText,
  watchActions,
} from "/runtime/widget-api.js";

// The store key for a draft's unsent edit. The page's port is its own origin, so
// the id alone is unambiguous — the same scoping every composer draft relies on.
// Presence and content are different for this widget, because deleting every character is
// an unsent edit — and that is the shared store's own rule, so the text goes in bare and
// the store's null is "nothing pending".
const ctx = (id) => "edit:" + id;
const saveEdit = (id, text) => saveDraft(ctx(id), text);
const clearEdit = (id) => clearDraft(ctx(id));
const loadEdit = (id) => loadDraft(ctx(id));

// Where the browser's own double-click would have drawn the word's edges. Segmenter
// knows the boundaries of the language the draft is written in, which /\w+/ does not:
// it keeps "l'écran" and a run of CJK whole where a character class splits them. The
// boundaries follow the script the words are written in; the locale only refines that,
// and the page's own `lang` is not the place to take it from — nothing validates that
// attribute, and Segmenter throws on a tag it can't parse, which at module scope is a
// typo in the markup costing every draft on the page its upgrade.
const words = new Intl.Segmenter(undefined, { granularity: "word" });

// The word under the pointer as a range in the body's text — the body holds one text
// node, so its offsets are the textarea's offsets. Between words the range is the
// collapsed caret the click asked for, which needs no second shape for the caller to
// test; past the end of the text there is no offset to carry at all, and the box opens
// where focus alone would have put it.
function wordAt(body, x, y) {
  const pos = document.caretPositionFromPoint(x, y);
  if (!pos || pos.offsetNode !== body.firstChild) return null;
  for (const w of words.segment(body.textContent)) {
    if (
      w.isWordLike &&
      pos.offset >= w.index &&
      pos.offset <= w.index + w.segment.length
    )
      return [w.index, w.index + w.segment.length];
  }
  return [pos.offset, pos.offset];
}

// What the agent wrote, verbatim, minus what the HTML source needed: the leading
// newline after the open tag, trailing whitespace before the close tag, and the
// common indentation the source gave every line.
function capture(el) {
  const raw = dataBody(el).replace(/^\n/, "").replace(/\s+$/, "");
  const lines = raw.split("\n");
  const indents = lines
    .filter((l) => l.trim())
    .map((l) => l.match(/^[ \t]*/)[0].length);
  const cut = indents.length ? Math.min(...indents) : 0;
  return lines.map((l) => l.slice(cut)).join("\n");
}

customElements.define(
  "lf-draft",
  class extends HTMLElement {
    #body;
    #pencil;
    #row;
    #raw;
    #history = null;
    #historyKey = "";
    #alignments = new Map();
    #ta = null;
    #sending = false;

    connectedCallback() {
      if (!once(this)) return;

      const raw = capture(this);
      this.#raw = raw;
      this.textContent = "";

      this.#body = document.createElement("div");
      this.#body.className = "lf-draft-body"; // NOT .lf-ui: anchoring and Δ must see this
      this.#body.textContent = raw;
      this.append(this.#body);

      // A quoted draft is an exhibit: the same dedented text, none of the doors —
      // no pencil, no double-click, no edit keys in the "?" overlay. Quoting
      // gates the action channel, not presentation.
      if (quoted(this)) return;

      // The way in is a gesture rather than a key, so its row binds nothing and the line
      // never offers it as the next press — the rule that keeps ⌥ click and F7 off it.
      // Declared on the element the reader stands on before the box exists, so opening a
      // draft is in the reference from the moment the page has one.
      keys(this, "On a draft", [
        { keys: [], label: "dblclick or ✎", does: "Edit the text in place" },
      ]);

      this.#pencil = this.#button("✎", () => this.#open());
      this.#pencil.classList.add("lf-draft-pencil");
      this.#pencil.setAttribute("aria-label", `Edit ${this.id}`);
      this.#pencil.title = "Edit this text — or double-click it";
      this.#row = offer("div", "lf-draft-controls");
      this.#row.append(this.#pencil);
      this.append(this.#row);
      watchActions(this, "edit", (actions) => this.#renderHistory(actions));

      // The fast path, taken before the browser paints the selection this gesture
      // would have made (see above). The word it aimed at opens selected in the box.
      // A double-click on the widget's own chrome belongs to that control — above all
      // to the edit box, whose word selection this preventDefault would swallow. What
      // the guard means is "a thing to work", so it reads the marker that says so and
      // not the chrome face, which is a look and would answer by coincidence.
      this.addEventListener("mousedown", (ev) => {
        // The primary button only: detail counts any button's clicks, and a rapid
        // middle- or right-button double-press is not the gesture this door is for.
        if (ev.detail !== 2 || ev.button !== 0 || ev.target.closest("[data-lf-offer]"))
          return;
        ev.preventDefault();
        this.#open(undefined, wordAt(this.#body, ev.clientX, ev.clientY));
      });

      // One edit, however many tabs are open on the page. An open box follows what is
      // typed in another; a closed one stays closed, because news arriving has no gesture
      // behind it and the box would open under whatever the reader is doing here — it
      // takes up the words at the next opening either way (#open reads the store). A
      // settlement is the case that does move this tab: the words are sent or discarded,
      // so an open box holding them has nothing left to hold, and closing it lets replay
      // paint whatever the log ends up saying.
      watchDraft(ctx(this.id), (text) => {
        if (text === null) this.#close(false);
        else if (this.#ta && this.#ta.value !== text) this.#ta.value = text;
      });

      // A recovered edit outranks the authored text: the user typed it and never
      // got it sent, so it must survive exactly as the composer's drafts do.
      const pending = loadEdit(this.id);
      if (pending !== null && pending !== raw) this.#open(pending);
      else if (pending === raw) clearEdit(this.id);
    }

    #button(text, onClick, variant) {
      const b = offer("button", "lf-btn" + (variant ? " " + variant : ""), text);
      b.addEventListener("click", onClick);
      return b;
    }

    #delta(before, after, cache = true) {
      const line = document.createElement("div");
      line.className = "lf-draft-delta";
      const key = JSON.stringify([before, after]);
      let alignment = this.#alignments.get(key);
      if (!alignment) {
        alignment = alignText(before, after);
        if (cache) this.#alignments.set(key, alignment);
      }
      for (const run of alignment) {
        const node = document.createElement(
          run.kind === "delete" ? "del" : run.kind === "insert" ? "ins" : "span",
        );
        node.textContent = run.text;
        line.append(node);
      }
      if (!line.childNodes.length) line.textContent = "Empty";
      return line;
    }

    #snapshot(label, text, comparison, standing) {
      const item = document.createElement("li");
      const head = document.createElement("div");
      head.className = "lf-draft-revision-head";
      const name = document.createElement("strong");
      name.textContent = label;
      head.append(name);
      if (text !== standing) {
        const restore = this.#button(`Restore ${label.toLowerCase()}`, () =>
          this.#restore(text, label),
        );
        restore.classList.add("lf-draft-restore");
        head.append(restore);
      }
      let body;
      if (comparison === null) {
        body = document.createElement("div");
        body.className = "lf-draft-snapshot";
        body.textContent = text || "Empty";
      } else body = this.#delta(comparison, text);
      item.append(head, body);
      return item;
    }

    #renderHistory(actions) {
      if (this.#sending) return;
      const standing = this.#body.textContent;
      const key = JSON.stringify([
        this.#raw,
        standing,
        actions.map((event) => [event.seq, event.version, event.detail.text]),
      ]);
      if (key === this.#historyKey) return;
      this.#historyKey = key;
      if (!actions.length && standing === this.#raw) {
        this.#history?.remove();
        this.#history = null;
        return;
      }

      const wasOpen = this.#history?.open ?? false;
      const keepFocus = Boolean(this.#history?.contains(document.activeElement));
      const history = offer("details", "lf-draft-history");
      history.open = wasOpen;
      const summary = document.createElement("summary");
      summary.textContent = `Changes · ${actions.length} ${actions.length === 1 ? "edit" : "edits"}`;

      const current = document.createElement("section");
      current.className = "lf-draft-current";
      const currentLabel = document.createElement("strong");
      currentLabel.textContent =
        standing === this.#raw
          ? "Standing text matches this version"
          : "This version → standing text";
      current.append(currentLabel);
      // This pair changes with every standing edit. Recomputing it once for the new
      // history render is cheaper than retaining every obsolete full-body comparison;
      // adjacent log revisions below are stable and remain worth caching.
      if (standing !== this.#raw)
        current.append(this.#delta(this.#raw, standing, false));

      const list = document.createElement("ol");
      list.className = "lf-draft-revisions";
      list.append(this.#snapshot("Version text", this.#raw, null, standing));
      let previous = null;
      actions.forEach((event, index) => {
        const text = event.detail.text;
        list.append(
          this.#snapshot(
            `Edit ${index + 1} · v${event.version}`,
            text,
            previous,
            standing,
          ),
        );
        previous = text;
      });
      // The disclosure scope is what works this box, so this binds no `run` and only says
      // the word — one more contributor to the section the draft's other two declare,
      // since the reader standing here is still on a draft. Both cells are read where they
      // are painted: which way the press goes is something the reader can see, and which
      // keys it takes is the scope's own answer for where this box is standing.
      keys(summary, "On a draft", [
        {
          keys: () => DISCLOSE(summary),
          does: () => `${history.open ? "Hide" : "Show"} the edit history`,
          line: () => `${history.open ? "hide" : "show"} the history`,
        },
      ]);

      history.append(summary, current, list);
      this.#history?.replaceWith(history);
      if (!this.#history) this.append(history);
      this.#history = history;
      if (keepFocus) summary.focus();
    }

    async #restore(text, label) {
      if (this.#sending) {
        toast("Wait for the current edit to finish sending");
        return;
      }
      if (this.#ta) {
        toast("Save or cancel the open edit before restoring history");
        return;
      }
      if (text === this.#body.textContent) return;
      this.#sending = true;
      this.setAttribute("aria-busy", "true");
      this.#body.textContent = text;
      const ok = await sendAction(this, "edit", { text });
      this.#sending = false;
      this.removeAttribute("aria-busy");
      if (ok) toast(`Restored ${label.toLowerCase()} — sent to ${agentName()}`);
    }

    #open(seed, at) {
      if (this.#ta) return;
      if (this.#sending) {
        toast("Wait for the current edit to finish sending");
        return;
      }
      const ta = offer("textarea", "lf-draft-edit");
      // A set-aside edit outranks the authored text here too: reopening resumes it.
      ta.value = seed ?? loadEdit(this.id) ?? this.#body.textContent;
      ta.setAttribute("aria-label", `Edit ${this.id}`);
      ta.addEventListener("input", () => saveEdit(this.id, ta.value));
      // The composer's bindings on the box that replaces the page's own words. Escape sets
      // the edit aside rather than discarding it (never lose user text: Cancel is the only
      // discard) — and being the innermost scope's is what keeps the runtime's own rung
      // from running behind it and closing the panel too, which the widget used to have to
      // prevent by consuming the press.
      keys(ta, "On a draft", [
        {
          keys: ["Mod+Enter"],
          does: "Save the edit",
          line: "save",
          run: () => this.#commit(),
        },
        {
          keys: ["Escape"],
          does: "Close the editor, keeping the edit",
          line: "close — edit kept",
          run: () => this.#close(false),
        },
      ]);
      this.#row.append(
        this.#button("Cancel", () => this.#close(true)),
        this.#button("Save", () => this.#commit(), "primary"),
      );
      this.#ta = ta;
      this.#body.after(ta);
      ta.focus();
      // Only the pointer names a place; the pencil and a recovered draft leave the
      // caret where focus put it, at the start of the text. The range was measured
      // in the body's text, so it names a word only in a box holding that text — a
      // resumed edit opens with different words at those offsets.
      if (at && ta.value === this.#body.textContent) ta.setSelectionRange(at[0], at[1]);
    }

    #close(discard) {
      if (!this.#ta) return;
      if (discard) clearEdit(this.id);
      // Only where the reader was standing in it. A close this tab's own gesture made
      // has focus in the box that is going, and the draft's one persistent control is
      // where it lands so a keyboard user isn't dropped back at the page top; a close
      // another tab's settlement brings takes focus from wherever they actually are.
      const stood = this.contains(document.activeElement);
      this.#ta.remove();
      this.#ta = null;
      // States the whole row rather than removing two buttons from it, so read mode
      // is one call from anywhere.
      this.#row.replaceChildren(this.#pencil);
      if (stood) this.#pencil.focus();
    }

    async #commit() {
      if (!this.#ta || this.#sending) return;
      const text = this.#ta.value;
      if (text === this.#body.textContent) {
        this.#close(true);
        return;
      }
      this.#body.textContent = text;
      this.#close(false);
      this.#sending = true;
      this.setAttribute("aria-busy", "true");
      const ok = await sendDraft(
        ctx(this.id),
        () => true,
        (attempt) => sendAction(this, "edit", { text }, { attempt }),
      );
      this.#sending = false;
      this.removeAttribute("aria-busy");
      if (ok) {
        toast(`Edited “${this.id}” — sent to ${agentName()}`);
      } else {
        const standing = loadEdit(this.id);
        // Null means the same shared generation was settled by the other tab while
        // this one waited to send. Its action will replay this body, so do
        // not resurrect the editor as if a network failure had occurred. A standing
        // generation is either the failed send itself or newer shared text; both stay
        // editable. The outbox has already projected the authoritative body before
        // resolving this call, so opening the saved generation must not overwrite it
        // with the stale pre-send snapshot.
        if (standing !== null) this.#open(standing);
      }
    }

    // An absolute value, so replaying this tab's own edit is a no-op and a second
    // tab converges rather than drifting. The edited-but-unhonored tint is the
    // runtime's, not this widget's: the pending pass compares the fold against
    // the authored text and marks data-lf-pending for every widget alike.
    applyAction(action, detail) {
      // The shape of `text` is the registry's claim and the POST door's gate
      // (action_contract_error), so nothing here re-asks it. What is left to
      // check is what no schema can say, and for one absolute body that is
      // nothing at all.
      if (action !== "edit") return;
      // Defer rather than yank words out from under a live edit. Only the open box
      // is named here: a send in flight held this off too, and holding replay off a
      // widget the page has painted ahead of the log is the layer's now, for every
      // widget alike (sendAction).
      if (this.#ta) return false;
      this.#body.textContent = detail.text;
    }
  },
);
