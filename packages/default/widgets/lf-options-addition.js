/* The option the author did not list: its draft, the `add` and `choose` bound to that
 * draft generation, and the option nodes each `add` in force puts in the group. */
import {
  guard,
  html,
  loadDraft,
  inlineMarkdownFragment,
  markdownReady,
  move,
  offer,
  render,
  repeat,
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
  #syncInput = null;
  #inForce = new Set();
  #end = null;

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
    // An option's title is one line, so Return adds it from a phone's keyboard too.
    this.#input.setAttribute("aria-multiline", "false");
    this.#bindingBadge = offer("span", "lf-key-badge");
    this.#bindingBadge.setAttribute("aria-hidden", "true");
    this.#input.value = loadDraft(this.#context) ?? "";
    this.#form.append(this.#bindingBadge, this.#input);
    this.#syncInput = wireInput(this.#input, {
      hint: "Add another option",
      sends: "add and select option",
      action: "add",
      allowsMedia: () => "Images can be added to comments, not options",
      busy: () => !this.available(),
      hasContent: (raw) => Boolean(raw.trim()),
      save: () => this.remember(this.#picked()),
      send: (text, _raw, owns) => this.#submit(text, owns),
    });
    this.#host.append(this.#form);
    this.#syncInput();
  }

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

  /* Lit owns only the generated option range. Its keyed rows stay direct children
   * of the group, before the persistent draft editor; authored options and their
   * evidence are outside that range. Guarding Markdown keeps its text nodes and the
   * reader's selection when another option changes. */
  render(added = {}, fallbackBefore = null) {
    const options = Object.entries(added);
    this.#inForce = new Set(options.map(([id]) => id));
    if (!this.#end) {
      this.#end = document.createComment("added options");
      move(this.#host, this.#end, this.#form ?? fallbackBefore);
    }
    render(
      repeat(
        options,
        ([id]) => id,
        ([id, text]) =>
          html`<lf-option id=${id} data-lf-added>
            <span class="lf-option-words" data-lf-markdown-words
              >${guard([text, markdownReady()], () =>
                inlineMarkdownFragment(text),
              )}</span
            >
          </lf-option>`,
      ),
      this.#host,
      { renderBefore: this.#end },
    );
  }
}
