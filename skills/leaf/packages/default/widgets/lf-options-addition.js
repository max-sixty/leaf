/* The option the author did not list: its draft, the `add` and `choose` bound to that
 * draft generation, and the option nodes each standing `add` puts in the group. */
import {
  loadDraft,
  inlineMarkdownFragment,
  markdownReady,
  offer,
  saveDraft,
  sendDraft,
  notice,
  watchDraft,
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
  #syncInput = () => {};
  #stopDraftWatch = null;

  constructor(host, { offered, available, commit }) {
    this.#host = host;
    this.#offered = offered;
    this.available = available;
    this.#commit = commit;
    this.#context = `option:${host.id}`;
  }

  connect() {
    if (!this.#offered) return;
    if (!this.#form) this.#buildForm();
    if (!this.#stopDraftWatch) {
      this.#stopDraftWatch = watchDraft(this.#context, (value) => {
        if (!this.#form.isConnected) return this.disconnect();
        this.#syncInput.load(value ?? "");
      });
    }
  }

  disconnect() {
    this.#stopDraftWatch?.();
    this.#stopDraftWatch = null;
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
    this.#input = offer("textarea");
    this.#input.name = "option";
    this.#input.rows = 1;
    this.#input.setAttribute("aria-label", ANOTHER);
    this.#add = offer("button", "lf-btn", "Add");
    this.#add.setAttribute("aria-label", "Add and select option");
    this.#bindingBadge = offer("span", "lf-key-badge");
    this.#bindingBadge.setAttribute("aria-hidden", "true");
    this.#input.value = loadDraft(this.#context) ?? "";
    this.#form.append(this.#bindingBadge, this.#input, this.#add);
    this.#syncInput = wireInput(this.#input, {
      hint: "Another option — add to select",
      sends: "add and select option",
      icon: "add",
      sendBtn: this.#add,
      allowsMedia: () => "Images can be added to comments, not options",
      busy: () => !this.available(),
      hasContent: (raw) => Boolean(raw.trim()),
      layout: this.#paintEmpty,
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
   * the door refuses a pick of an option the group lacks. */
  #draftChoice(payload) {
    if (
      !payload ||
      !Array.isArray(payload.options) ||
      !payload.options.every((id) => typeof id === "string")
    )
      return this.detailFor(this.#picked());
    return {
      options: payload.options.filter(
        (id) => document.getElementById(id)?.parentElement === this.#host,
      ),
    };
  }

  /* The draft's attempt names the option, so a resend after reload names the same one
   * and the log answers it as the same `add`. The pick is absolute state and needs no
   * such identity. */
  async #submit(text, owns) {
    const accepted = await sendDraft(this.#context, owns, (attempt, payload) => {
      const id = `${this.#host.id}-option-${attempt}`;
      const standing = this.#draftChoice(payload);
      const picked = new Set(
        this.#host.hasAttribute("multiple") ? standing.options : [],
      );
      picked.add(id);
      return this.#commit({ option: id, text }, { options: [...picked] }, attempt);
    });
    if (accepted) notice(`Added and selected “${text}” — sent`);
  }

  detailFor(picked) {
    return { options: [...picked].map((option) => option.id) };
  }

  /* Keep surviving nodes: replay must not discard focus or selection. Return only
   * nodes the selection owner still needs to dress with a mark and key scope.
   * `added` maps each standing option id to its words, in log order. */
  reconcile(added = {}, fallbackBefore = null) {
    const wanted = new Map(Object.entries(added));
    for (const option of this.#host.querySelectorAll(
      ":scope > lf-option[data-lf-added]",
    ))
      if (!wanted.has(option.id)) option.remove();

    const created = [];
    for (const [id, text] of wanted) {
      let option = document.getElementById(id);
      if (option && option.parentElement !== this.#host) continue;
      if (!option) {
        option = document.createElement("lf-option");
        option.id = id;
        option.dataset.lfAdded = "";
        this.#host.insertBefore(option, this.#form ?? fallbackBefore);
        created.push(option);
      }
      if (option.hasAttribute("data-lf-added")) {
        let words = option.querySelector(":scope > .lf-option-words");
        if (!words) {
          words = document.createElement("span");
          words.className = "lf-option-words";
          words.dataset.lfMarkdownWords = "";
          option.prepend(words);
        }
        const ready = markdownReady();
        if (words.source !== text || words.markdownReady !== ready) {
          words.source = text;
          words.markdownReady = ready;
          words.replaceChildren(inlineMarkdownFragment(text));
        }
      }
    }
    return created;
  }
}
