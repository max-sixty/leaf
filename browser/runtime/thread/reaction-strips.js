/* Thread reaction projection and its synchronous Lit owner. The controller
   registers template-owned controls and owns only disclosure, keyboard and focus.
   The strip below a reply's words holds its reactions; its trigger stands with the
   message's other controls at its head (messages.js), which draws `trigger`. */
import { html, ref, render, repeat } from "/runtime/framework.js";
import { HOLDS_WORD } from "../held-word.js";
import { offered, offeredAction } from "../widget-elements.js";

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
  }

  present(model) {
    this.#model = model;
    this.node.classList.toggle("lf-open", model.latest);
    render(
      html`<span
        class="lf-react-palette"
        id=${this.#paletteId}
        popover="auto"
        role="group"
        @toggle=${(event) => {
          if (event.newState === "closed") this.#registration.close();
        }}
        aria-label="Reactions for this reply"
      >
        ${repeat(
          model.choices,
          (choice) => choice.name,
          (choice) =>
            html` <button
              ${offered(`lf-react ${HOLDS_WORD}`)}
              data-token=${choice.name}
              title=${choice.label}
              aria-label=${choice.label}
              aria-pressed=${String(Boolean(choice.inForce))}
              @click=${() => this.#press(choice.name)}
            >
              <span class="lf-react-glyph">${choice.glyph}</span>
            </button>`,
        )}
      </span>`,
      this.node,
    );
    return this.node;
  }

  // The list's trigger, which registers the strip once it is drawn.
  trigger = html`<button
    ${offeredAction("symbol", "lf-msg-control lf-react-trigger", undefined, {
      action: "react",
    })}
    aria-expanded="false"
    aria-controls=${this.#paletteId}
    @click=${() => this.#registration.toggle()}
    ${ref((trigger) => {
      if (trigger)
        this.#registration ??= this.#commands.registerSurface(this.node, {
          trigger,
          palette: this.node.querySelector(".lf-react-palette"),
        });
    })}
  ></button>`;

  #press(name) {
    const model = this.#model;
    const sent = this.#commands.actions.setReaction(
      model.thread,
      model.message,
      name,
      !model.choices.find((choice) => choice.name === name).inForce,
    );
    this.#registration.close();
    this.#commands.pressed();
    void sent;
  }

  retire() {
    this.#registration?.close();
  }
}
