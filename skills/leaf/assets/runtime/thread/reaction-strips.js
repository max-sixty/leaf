/* Thread reaction projection and its Solid view owner. The controller
   registers template-owned controls and owns only disclosure, keyboard and focus. */
import { solidHtml as html, createView, For } from "/vendor/browser-runtime.js";
import { iconElement } from "../icons.js";
import { HOLDS_WORD } from "../held-word.js";

let ordinal = 0;
export class ReactionStripView {
  #commands;
  #registration = null;
  #model = null;
  #view = null;
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
    if (!this.#view) {
      this.#view = createView(
        this.node,
        (reading) =>
          html` <button
              type="button"
              class="lf-msg-control lf-react-trigger lf-ui"
              data-lf-gen="1"
              data-lf-offer="button"
              aria-expanded="false"
              aria-controls=${this.#paletteId}
              aria-label="Add reaction"
              title="Add reaction"
              onClick=${() => this.#registration.toggle()}
            >
              ${iconElement("reaction", "lf-msg-control-icon")}
            </button>
            <span
              class="lf-react-palette"
              id=${this.#paletteId}
              popover="auto"
              role="group"
              onToggle=${(event) => {
                if (event.newState === "closed") this.#registration.close();
              }}
              aria-label="Reactions for this reply"
              >${For({
                get each() {
                  return reading().choices;
                },
                keyed: (choice) => choice.name,
                children: (choice) =>
                  html`<button
                    type="button"
                    class=${`lf-outline-chip lf-react ${HOLDS_WORD} lf-ui`}
                    data-lf-gen="1"
                    data-lf-offer="button"
                    data-token=${() => choice().name}
                    title=${() => choice().label}
                    aria-label=${() => choice().label}
                    aria-pressed=${() => String(Boolean(choice().inForce))}
                    aria-busy=${() => String(Boolean(choice().inForce?.pending))}
                    onClick=${() => this.#press(choice().name)}
                  >
                    <span class="lf-react-glyph">${() => choice().glyph}</span>
                  </button>`,
              })}</span
            >`,
        model,
      );
    } else this.#view.update(model);
    this.#registration ??= this.#commands.registerSurface(this.node, {
      trigger: this.node.querySelector(".lf-react-trigger"),
      palette: this.node.querySelector(".lf-react-palette"),
      target: "the reply",
    });
    return this.node;
  }

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
    this.#view?.dispose();
    this.#view = null;
    this.#registration = null;
  }
}
