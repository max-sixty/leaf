/* A widget written as an Effect UI component, on the protocol any custom element has
   with its host (module-plain-elements.md): properties in, events out.

   `defineWidget(tag, component, options)` defines `tag` as a plain custom element that
   mounts `component` with `BrowserHost.mountEffect` into the element, or into an open
   shadow root of its own with `shadow: true`, where a `<slot>` the view draws shows
   the element's authored children in place. The component's Model holds only what the
   user is doing in the widget, such as an open disclosure; what Leaf knows arrives as
   props:

   - `state`, the reading Leaf sets on a widget whose tag declares `verbs`, as the
     `state` property every widget gets.
   - What `options.inputs(element)` returns, called inside a signal effect, so a
     signal-backed reader it calls, such as `readObligations`, gives the component
     new props when it moves. The function reads the element's attributes too, and
     only there does the component see its element.

   The component's events are what it says to Leaf: a `Recorded` event (`WidgetEvents`)
   is an `lf-action` and a `TookBack` one an `lf-undo`, dispatched on the element, and
   any other event a bubbling, composed `CustomEvent` named by its lowercased tag, with
   the event as `detail`, as `BrowserHost.defineElement` dispatches one.

   Drawing follows the protocol's "Drawing" rule. The first mount draws before
   `connectedCallback` returns. A later set draws in Effect UI's flush, a microtask
   later and before the next frame, so each set that gives new props dispatches a
   `pending-task` whose promise settles after that flush, and an `lf-commands` once it
   has drawn, since what the element binds keys to may have changed. A root that fails
   reports through `failSoft` and shows nothing.

   The element dispatches `lf-connect` as it connects, so Leaf dresses its shadow root
   and makes its sets first; where Leaf cancels the event, the element mounts once
   `state` arrives. A descendant's `lf-connect` reads `inputs` again, since a revision
   may have replaced the members they read, as `LeafElement` draws again then.
   `lfPatch` is the class's static `lfPatch` (module-authoring.md, "Revisions"). Moving
   the element keeps its root (`connectedMoveCallback`), and leaving the document
   closes it a microtask later, as `defineElement`'s elements do. */
import {
  BrowserHost,
  Cause,
  Effect,
  Equal,
  Exit,
  Schema,
  Scope,
  UiSchema,
} from "/vendor/effect-ui.js";
import { effect as watch, untracked } from "/vendor/signals-core.js";
import { failSoft } from "./failure.js";
import { inWindowDocument } from "./once.js";
import { PendingTaskEvent } from "./pending-task.js";
import { COMMANDS, CONNECT } from "./widget-events.js";

/** The events a widget component emits for Leaf to record or take back, in the shapes
 *  `lf-action` and `lf-undo` carry. A component lists them in its `events`, beside
 *  any of its own: `events: WidgetEvents`. */
export const WidgetEvents = UiSchema.TaggedEnum({
  Recorded: {
    verb: Schema.String,
    detail: Schema.Record(Schema.String, Schema.Unknown),
    says: Schema.optional(Schema.String),
    attempt: Schema.optional(Schema.String),
  },
  TookBack: { verb: Schema.String, unit: Schema.optional(Schema.String) },
});

/** The props every widget component gets: Leaf's reading of it, undefined until Leaf
 *  sets one and off a Leaf page. A component's own `props` Schema extends it. */
export const widgetProps = { state: Schema.optional(Schema.Unknown) };

let mounts = 0;

/**
 * Define `tag` as a widget that draws `component`.
 * @param {string} tag
 * @param {any} component an Effect UI HTML component whose props hold `state` and
 *   what `inputs` returns
 * @param {{shadow?: boolean, lfPatch?: "members", inputs?: (element: HTMLElement) => Record<string, unknown>}} [options]
 */
export function defineWidget(tag, component, { shadow = false, lfPatch, inputs } = {}) {
  const Widget = class extends HTMLElement {
    /** @type {unknown} */
    #state = undefined;
    /** @type {Record<string, unknown>} */
    #inputs = {};
    /** @type {{setProps: (props: any) => void} | undefined} */
    #root = undefined;
    /** @type {Scope.Closeable | undefined} */
    #scope = undefined;
    /** @type {(() => void) | undefined} */
    #unwatch = undefined;
    // Leaf answered `lf-connect`: it sets `state`, and nothing mounts before it has.
    #hosted = false;

    constructor() {
      super();
      if (shadow) this.attachShadow({ mode: "open" });
      // A listener on a shadow host sees itself as the target of an event from inside
      // its root, so the element that connected is read off the path.
      this.addEventListener(CONNECT, (event) => {
        if (inputs && this.#root && event.composedPath()[0] !== this)
          untracked(() => {
            const next = this.#read();
            if (!next) return;
            this.#inputs = next;
            this.#update();
          });
      });
    }

    get state() {
      return this.#state;
    }
    set state(value) {
      this.#state = value;
      if (this.#root) this.#update();
      else this.#mount();
    }

    connectedCallback() {
      if (!inWindowDocument(this) || this.#root) return;
      untracked(() => {
        this.#hosted ||= !this.dispatchEvent(
          new Event(CONNECT, { bubbles: true, composed: true, cancelable: true }),
        );
        this.#mount();
      });
    }

    // With `moveBefore()`, a move calls only this, so the root stays.
    connectedMoveCallback() {}

    disconnectedCallback() {
      queueMicrotask(() => {
        if (this.isConnected || !this.#scope) return;
        const scope = this.#scope;
        this.#unwatch?.();
        this.#root = this.#scope = this.#unwatch = undefined;
        Effect.runFork(Scope.close(scope, Exit.void));
      });
    }

    // What `inputs` reads, or nothing where it throws: the failure stays on this
    // widget, as `LeafElement`'s does, rather than aborting the update that moved a
    // signal it reads. A DOM node it returns is the same input only as itself:
    // Effect UI compares props that differ by reference with `Equal.equals`, which
    // would otherwise compare two nodes by every property they reach, a walk that
    // covers the document and throws on a getter such as an SVG length's.
    #read() {
      try {
        const next = inputs?.(this);
        for (const value of Object.values(next ?? {}))
          if (value instanceof Node) Equal.byReferenceUnsafe(value);
        return next;
      } catch (error) {
        untracked(() => failSoft(this, error));
      }
    }

    #props() {
      return { ...this.#inputs, state: this.#state };
    }

    #mount() {
      if (this.#root || !this.isConnected) return;
      if (this.#hosted && this.#state === undefined) return;
      if (inputs) {
        // The first run reads the inputs the mount draws from; later runs are the
        // signals they read moving.
        let first = true;
        this.#unwatch = watch(() => {
          const seeding = first;
          first = false;
          const next = this.#read();
          if (!next) return;
          if (seeding) this.#inputs = next;
          else
            untracked(() => {
              this.#inputs = next;
              this.#update();
            });
        });
      }
      const scope = (this.#scope = Scope.makeUnsafe());
      const element = this;
      // A shadow root is a container as an element is, as `defineElement` mounts one.
      const container = /** @type {Element} */ (
        /** @type {unknown} */ (this.shadowRoot ?? this)
      );
      const mounting = /** @type {Effect.Effect<any, never, Scope.Scope>} */ (
        BrowserHost.mountEffect(component, this.#props(), container, {
          head: false,
          key: `${tag}:${mounts++}`,
          onEmit: (/** @type {any} */ event) => element.#emit(event),
          fallback: (/** @type {any} */ failure, /** @type {any} */ h) => {
            queueMicrotask(() => failSoft(element, Cause.squash(failure.cause)));
            return h.span;
          },
        })
      );
      this.#root = Effect.runSync(mounting.pipe(Scope.provide(scope)));
      this.#drawn();
    }

    #update() {
      const root = this.#root;
      if (!root) return;
      root.setProps(this.#props());
      // Effect UI's flush is the microtask setProps queued, so a task queued now
      // runs after it.
      const drawn = Promise.resolve().then(() => this.#drawn());
      this.dispatchEvent(new PendingTaskEvent(drawn));
    }

    #drawn() {
      const root = this.shadowRoot ?? this;
      root.dispatchEvent(
        new CustomEvent(COMMANDS, {
          bubbles: true,
          composed: true,
          detail: { within: true },
        }),
      );
    }

    /** @param {{_tag: string} & Record<string, unknown>} event */
    #emit(event) {
      const { _tag, ...detail } = event;
      if (_tag === "Recorded" || _tag === "TookBack")
        this.dispatchEvent(
          new CustomEvent(_tag === "Recorded" ? "lf-action" : "lf-undo", { detail }),
        );
      else
        this.dispatchEvent(
          new CustomEvent(_tag.toLowerCase(), {
            detail: event,
            bubbles: true,
            composed: true,
          }),
        );
    }
  };
  if (lfPatch) Object.assign(Widget, { lfPatch });
  customElements.define(tag, Widget);
}
