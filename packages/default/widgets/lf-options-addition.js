/* The option the author did not list: its draft, the `add` and `choose` bound to that
 * draft generation, and the option nodes each `add` in force puts in the group. */
import {
  createView,
  html,
  loadDraft,
  inlineMarkdownFragment,
  markdownReady,
  move,
  offer,
  saveDraft,
  sendDraft,
  TEXT_FIELD,
  watchDraft,
  whileConnected,
  wireInput,
} from "/runtime/widget-api.js";

const ANOTHER = "Another option";

export class OptionAddition {
  #host;
  #offered;
  #commit;
  #context;
  #form = null;
  #bindingBadge = null;
  #input = null;
  #add = null;
  #syncInput = null;
  #inForce = new Set();
  #drawings = new Map();

  constructor(host, { offered, available, commit }) {
    this.#host = host;
    this.#offered = offered;
    this.available = available;
    this.#commit = commit;
    this.#context = `option:${host.id}`;
  }

  connect() {
    if (!this.#offered) return;
    if (this.#form) return;
    this.#buildForm();
    whileConnected(this.#host, () =>
      watchDraft(this.#context, (value) => this.#syncInput.load(value ?? ""), {
        input: this.#input,
        // Resume writing (`g i`) comes back to the field, which stands in the group.
        resume: () => ({ where: this.#input, input: () => this.#input }),
      }),
    );
  }

  get input() {
    return this.#input;
  }

  get bindingBadge() {
    return this.#bindingBadge;
  }

  refresh() {
    if (this.#form) this.#syncInput();
  }

  #buildForm() {
    this.#form = offer("form", "lf-another");
    this.#input = offer(TEXT_FIELD);
    this.#input.name = "option";
    this.#input.setAttribute("aria-label", ANOTHER);
    this.#add = offer("button", "lf-btn", "Add");
    this.#add.setAttribute("aria-label", "Add and select option");
    this.#bindingBadge = offer("span", "lf-key-badge");
    this.#bindingBadge.setAttribute("aria-hidden", "true");
    this.#input.value = loadDraft(this.#context) ?? "";
    this.#form.append(this.#bindingBadge, this.#input, this.#add);
    this.#syncInput = wireInput(this.#input, {
      hint: "Add another option",
      sends: "add and select option",
      icon: "add",
      sendBtn: this.#add,
      allowsMedia: () => "Images can be added to comments, not options",
      busy: () => !this.available(),
      hasContent: (raw) => Boolean(raw.trim()),
      paint: this.#paintEmpty,
      save: () => this.remember(this.#picked()),
      send: (text, _raw, owns) => this.#submit(text, owns),
    });
    this.#host.append(this.#form);
    this.#syncInput();
  }

  #paintEmpty = () => {
    const empty = !this.#input.value.trim();
    this.#add.toggleAttribute("data-lf-empty", empty);
  };

  #picked() {
    return new Set(this.#host.querySelectorAll(":scope > lf-option[chosen]"));
  }

  remember(picked) {
    if (!this.#input) return;
    if (!this.#input.value && loadDraft(this.#context) === null) return;
    saveDraft(this.#context, this.#input.value, this.detailFor(picked));
  }

  /* The choice the generation recorded, less any option the group no longer holds:
   * an undo since then may have taken back an added option the draft still names, and
   * the door refuses a pick of an option the group lacks. Membership is the authored
   * options and the adds in force of the latest reading, not whatever this tab last
   * painted. */
  #draftChoice(payload) {
    if (
      !payload ||
      !Array.isArray(payload.value) ||
      !payload.value.every((id) => typeof id === "string")
    )
      return this.detailFor(this.#picked());
    return {
      value: payload.value.filter((id) => this.#inForce.has(id) || this.#authored(id)),
    };
  }

  #authored(id) {
    const option = document.getElementById(id);
    return (
      option?.parentElement === this.#host && !option.hasAttribute("data-lf-added")
    );
  }

  /* The draft's attempt names the option, so a resend after reload names the same one
   * and the log answers it as the same `add`. The pick is absolute state and needs no
   * such identity. */
  async #submit(text, owns) {
    await sendDraft(this.#context, owns, (attempt, payload) => {
      const id = `${this.#host.id}-option-${attempt}`;
      const choice = this.#draftChoice(payload);
      const picked = new Set(this.#host.hasAttribute("multiple") ? choice.value : []);
      picked.add(id);
      return this.#commit({ option: id, text }, { value: [...picked] }, attempt);
    });
  }

  detailFor(picked) {
    return { value: [...picked].map((option) => option.id) };
  }

  // Options remain direct children among authored evidence. Each generated option
  // owns its words; unchanged Markdown retains the reader's native selection.
  render(added = {}, fallbackBefore = null) {
    this.#inForce = new Set(Object.keys(added));
    for (const [id, entry] of this.#drawings)
      if (!this.#inForce.has(id)) {
        entry.drawing.dispose();
        entry.node.remove();
        this.#drawings.delete(id);
      }
    for (const [id, text] of Object.entries(added)) {
      let entry = this.#drawings.get(id);
      if (!entry) {
        const node = document.createElement("lf-option");
        node.id = id;
        node.dataset.lfAdded = "";
        const drawing = createView(
          node,
          (read) =>
            html`<span class="lf-option-words" data-lf-markdown-words
              >${() => read().content}</span
            >`,
          { content: inlineMarkdownFragment(text) },
        );
        entry = { node, drawing, text, ready: markdownReady() };
        this.#drawings.set(id, entry);
      } else if (entry.text !== text || entry.ready !== markdownReady()) {
        entry.text = text;
        entry.ready = markdownReady();
        entry.drawing.update({ content: inlineMarkdownFragment(text) });
      }
      move(this.#host, entry.node, this.#form ?? fallbackBefore);
    }
  }
}
