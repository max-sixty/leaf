/* Thread reaction projection and its synchronous Lit owner. The controller
   registers template-owned controls and owns only disclosure, keyboard and focus. */
import { html, render, repeat } from "../../vendor/browser-runtime.js";
import { iconTemplate } from "../icons.js";

let ordinal = 0;
export class ReactionStripView {
  #commands;
  #registration = null;
  #model = null;
  #paletteId = `lf-reactions-${++ordinal}`;

  constructor(commands) {
    this.#commands = commands;
    this.node = document.createElement("div");
    this.node.classList.add("lf-react-strip", "lf-react-surface");
    this.node.setAttribute("role", "group");
    this.node.setAttribute("aria-label", "React to this reply");
  }

  present(model) {
    this.#model = model;
    this.node.classList.toggle("lf-open", model.latest);
    render(
      html` <button
          type="button"
          class="lf-react-trigger lf-ui"
          data-lf-gen="1"
          data-lf-offer="button"
          aria-expanded="false"
          aria-controls=${this.#paletteId}
          aria-label="Add reaction"
          title="Add reaction"
          @click=${() => this.#registration.toggle()}
        >
          ${iconTemplate("reaction", "lf-react-trigger-icon")}
        </button>
        <span
          class="lf-react-palette"
          id=${this.#paletteId}
          role="group"
          aria-label="Reactions for this reply"
        >
          ${repeat(
            model.choices,
            (choice) => choice.name,
            (choice) =>
              html` <button
                type="button"
                class="lf-outline-chip lf-react lf-ui"
                data-lf-gen="1"
                data-lf-offer="button"
                data-token=${choice.name}
                title=${choice.label}
                aria-label=${choice.label}
                aria-pressed=${String(Boolean(choice.standing))}
                aria-busy=${String(Boolean(choice.standing?.pending))}
                @click=${() => this.#press(choice.name)}
              >
                <span class="lf-react-glyph">${choice.glyph}</span>
              </button>`,
          )}
        </span>`,
      this.node,
    );
    this.#registration ??= this.#commands.registerSurface(this.node, {
      trigger: this.node.querySelector(".lf-react-trigger"),
      palette: this.node.querySelector(".lf-react-palette"),
      target: "the reply",
    });
    return this.node;
  }

  #press(name) {
    const model = this.#model;
    const sent = this.#commands.actions.toggleReaction(
      model.key,
      model.parent,
      name,
      Boolean(model.choices.find((choice) => choice.name === name).standing),
    );
    this.#registration.close();
    this.#commands.pressed();
    void sent;
  }

  retire() {
    this.#registration?.close();
  }
}
