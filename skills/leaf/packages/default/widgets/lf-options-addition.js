/* The option the author did not list: its durable words, the complete choice bound
 * to that draft generation, and the generated option nodes replay reconstructs. */
import {
  focused,
  loadDraft,
  offer,
  saveDraft,
  sendDraft,
  notice,
  watchDraft,
  wireInput,
  wrote,
} from "/runtime/widget-api.js";

const ANOTHER = "Another option";

const optionLabel = (option) => wrote(option);

export class OptionAddition {
  #host;
  #offered;
  #commit;
  #context;
  #form = null;
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
        this.#input.value = value ?? "";
        this.#syncInput();
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

  refresh() {
    if (this.#form) this.#syncInput();
  }

  #buildForm() {
    this.#form = offer("form", "lf-another");
    this.#input = offer("textarea");
    this.#input.rows = 1;
    this.#input.setAttribute("aria-label", ANOTHER);
    this.#add = offer("button", "lf-btn", "Add");
    this.#add.setAttribute("aria-label", "Add option");
    this.#input.value = loadDraft(this.#context) ?? "";
    this.#form.append(this.#input, this.#add);
    this.#syncInput = wireInput(this.#input, {
      hint: ANOTHER,
      sends: "add option",
      icon: "add",
      sendBtn: this.#add,
      allowsMedia: null,
      busy: () => !this.available(),
      layout: this.#paintEmpty,
      save: () => this.remember(this.#picked()),
      send: (text, _raw, owns) => this.#submit(text, owns),
    });
    this.#host.append(this.#form);
    this.#syncInput();
  }

  #paintEmpty = () => {
    const empty = !this.#input.value.trim();
    if (empty && focused() === this.#add) this.#input.focus();
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

  #draftChoice(payload) {
    if (
      !payload ||
      !Array.isArray(payload.options) ||
      !payload.options.every((id) => typeof id === "string") ||
      (payload.additions !== undefined &&
        (!payload.additions ||
          typeof payload.additions !== "object" ||
          Array.isArray(payload.additions) ||
          !Object.entries(payload.additions).every(
            ([id, text]) => typeof id === "string" && typeof text === "string",
          )))
    )
      return this.detailFor(this.#picked());
    return {
      options: payload.options,
      ...(Object.keys(payload.additions ?? {}).length
        ? { additions: payload.additions }
        : {}),
    };
  }

  async #submit(text, owns) {
    const accepted = await sendDraft(this.#context, owns, (attempt, payload) => {
      const id = `${this.#host.id}-option-${attempt}`;
      const standing = this.#draftChoice(payload);
      const additions = { ...(standing.additions ?? {}), [id]: text };
      const picked = new Set(
        this.#host.hasAttribute("multiple") ? standing.options : [],
      );
      picked.add(id);
      const detail = { options: [...picked], additions };
      return this.#commit(detail, attempt);
    });
    if (accepted) notice(`Added “${text}” — sent`);
  }

  #additions() {
    return Object.fromEntries(
      [...this.#host.querySelectorAll(":scope > lf-option[data-lf-added]")].map(
        (option) => [option.id, optionLabel(option)],
      ),
    );
  }

  detailFor(picked) {
    const additions = this.#additions();
    return {
      options: [...picked].map((option) => option.id),
      ...(Object.keys(additions).length ? { additions } : {}),
    };
  }

  /* Keep surviving nodes: replay must not discard focus or selection. Return only
   * nodes the selection owner still needs to dress with a mark and key scope. */
  reconcile(additions = {}, fallbackBefore = null) {
    const wanted = new Map(Object.entries(additions));
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
        option.append(document.createTextNode(text));
        this.#host.insertBefore(option, this.#form ?? fallbackBefore);
        created.push(option);
      } else if (option.hasAttribute("data-lf-added")) {
        const words = [...option.childNodes].find(
          (node) => node.nodeType === Node.TEXT_NODE,
        );
        if (words) words.data = text;
        else option.prepend(document.createTextNode(text));
      }
    }
    return created;
  }
}
