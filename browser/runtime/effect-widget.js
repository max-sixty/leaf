/* A widget written as an Effect UI component, on the protocol any custom element has
   with its host (module-plain-elements.md): properties in, events out.

   `defineWidget(tag, component, options)` defines `tag` as a plain custom element that
   mounts `component` with `BrowserHost.mountEffect` into a box of its own after the
   element's authored children, or into an open shadow root of its own with
   `shadow: true`, where a `<slot>` the view draws shows the element's authored
   children in place. Either way the authored children stay where the author put them,
   for Leaf's revisions and for `inputs` to read: the box is a `display: contents`
   `div` marked as words the source lacks (`data-lf-gen`), and a widget that draws its
   authored children in their place hides them from its stylesheet. A widget that
   decorates those children, drawing its controls in its shadow root around the slot
   and exposing them to the theme as shadow parts, takes the shape lf-options.js's
   header gives ("How it is drawn: a decorating widget"). The component's Model holds
   only what the user is doing in the widget, such as an open disclosure; what Leaf
   knows arrives as props:

   - `state`, the reading Leaf sets on a widget whose tag declares `verbs`, as the
     `state` property every widget gets.
   - What `options.inputs(element)` returns, called inside a signal effect, so a
     signal-backed reader it calls, such as `readObligations`, gives the component
     new props when it moves. The function reads the element's attributes too, and
     only there does the component see its element. Its second argument, `reread`,
     asks for it to be read again, for an input no signal carries, such as a media
     query or a reading Leaf holds back (`HeldReading`) until it lets it go.

   What the component asks of Leaf, such as recording a gesture, it issues as a
   Command of Leaf's services (widget-services.js), which the mount provides for this
   element. A Command runs in a microtask of the task that issued it, on the
   scheduler the mount provides, so a gesture's Command lands before the browser's
   next frame. The component's events are for the page around it: each is a
   bubbling, composed `CustomEvent` named by its lowercased tag, with the event as
   `detail`, as `BrowserHost.defineElement` dispatches one.

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
   `statics` are the class's static members Leaf reads off a widget's class, such as
   `lfPatch` (module-authoring.md, "Revisions") and `answered` (module-state.md). Moving
   the element keeps its root (`connectedMoveCallback`), and leaving the document
   closes it a microtask later, as `defineElement`'s elements do.

   A widget whose page module talks to the element itself names those properties:

   - `options.properties` are props too, as `BrowserHost.defineElement`'s are: the
     element keeps what the page sets, and a set gives the component new props. A
     value the page set before the tag was defined counts, so either module may load
     first.
   - `options.members` read and write the component's Model: reading one gives what
     its `get` reads off the Model, and setting one sends the root the message its
     `set` returns, which draws as a set of props does. Out of the document a member reads the Model the closed root
     ended with, and a set waits for the next root, as one made before the tag was
     defined does. */
import {
  BrowserHost,
  Cause,
  Effect,
  Equal,
  Exit,
  Schema,
  Scheduler,
  Scope,
} from "/vendor/effect-ui.js";
import { signal, effect as watch, untracked } from "/vendor/signals-core.js";
import { failSoft } from "./lib/failure.js";
import { inWindowDocument } from "./lib/once.js";
import { PendingTaskEvent } from "./lib/pending-task.js";
import { COMMANDS, CONNECT } from "./lib/widget-events.js";
import { leafServices } from "./widget-services.js";

/** The props every widget component gets: Leaf's reading of it, undefined until Leaf
 *  sets one and off a Leaf page. A component's own `props` Schema extends it. */
export const widgetProps = { state: Schema.optional(Schema.Unknown) };

let mounts = 0;

// The scheduler a root's Commands and Subscriptions run on: microtasks of the task that
// asked, so a Command a gesture issues runs before the browser's next frame
// (AGENTS.md, "Responsiveness"). Without one, Effect UI posts them through its
// time-sliced HtmlScheduler, as later tasks.
const microtasks = new Scheduler.MixedScheduler("sync");

/** @typedef {{get?: (model: any) => unknown, set?: (value: any) => unknown}} Member */

/**
 * Define `tag` as a widget that draws `component`.
 * @param {string} tag
 * @param {any} component an Effect UI HTML component whose props hold `state`, what
 *   `inputs` returns and the `properties`
 * @param {{shadow?: boolean, statics?: Record<string, unknown>,
 *   inputs?: (element: HTMLElement, reread: () => void) => Record<string, unknown>,
 *   properties?: readonly string[], members?: Record<string, Member>}} [options]
 */
export function defineWidget(
  tag,
  component,
  { shadow = false, statics, inputs, properties = [], members = {} } = {},
) {
  const Widget = class extends HTMLElement {
    static {
      for (const name of properties)
        Object.defineProperty(this.prototype, name, {
          /** @this {InstanceType<typeof Widget>} */
          get() {
            return this.#properties[name];
          },
          /** @this {InstanceType<typeof Widget>} @param {unknown} value */
          set(value) {
            this.#properties = { ...this.#properties, [name]: value };
            if (this.#root) this.#update();
            else this.#mount();
          },
        });
      for (const [name, { get, set }] of Object.entries(members))
        Object.defineProperty(this.prototype, name, {
          /** @this {InstanceType<typeof Widget>} */
          get() {
            const model = this.#root?.model() ?? this.#ended;
            return get && model !== undefined ? get(model) : undefined;
          },
          /** @this {InstanceType<typeof Widget>} @param {unknown} value */
          set(value) {
            if (!set) return;
            const message = set(value);
            if (!this.#root) this.#held.push(message);
            else {
              this.#root.send(message);
              this.#redraws();
            }
          },
        });
    }
    /** @type {unknown} */
    #state = undefined;
    /** @type {Record<string, unknown>} */
    #inputs = {};
    /** @type {Record<string, unknown>} */
    #properties = {};
    /** @type {{setProps: (props: any) => void, model: () => unknown, send: (message: any) => void} | undefined} */
    #root = undefined;
    // The Model the last root ended with, which `members` read while none stands.
    /** @type {unknown} */
    #ended = undefined;
    // The messages `members` set while no root stood, which the next root takes.
    /** @type {unknown[]} */
    #held = [];
    /** @type {Scope.Closeable | undefined} */
    #scope = undefined;
    /** @type {HTMLElement | undefined} */
    #box = undefined;
    /** @type {(() => void) | undefined} */
    #unwatch = undefined;
    // Leaf answered `lf-connect`: it sets `state`, and nothing mounts before it has.
    #hosted = false;
    // Moved by `reread`, and read with the inputs, so the watch reads them again.
    #asked = signal(0);
    #reread = () => {
      this.#asked.value++;
    };

    constructor() {
      super();
      if (shadow) this.attachShadow({ mode: "open" });
      // A page may set a property before this module defines the tag, which leaves an
      // own property hiding the accessor. Its value moves into the props here, without
      // the accessor's mount: an element upgraded in the document mounts from
      // `connectedCallback`, once Leaf has answered `lf-connect`. A member's value
      // goes through its accessor, which holds the message for that mount.
      const own = /** @type {Record<string, unknown>} */ (
        /** @type {unknown} */ (this)
      );
      for (const name of properties)
        if (Object.hasOwn(this, name)) {
          const value = own[name];
          delete own[name];
          this.#properties = { ...this.#properties, [name]: value };
        }
      for (const name of Object.keys(members))
        if (Object.hasOwn(this, name)) {
          const value = own[name];
          delete own[name];
          own[name] = value;
        }
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
        this.#ended = this.#root?.model();
        this.#unwatch?.();
        this.#box?.remove();
        this.#root = this.#scope = this.#unwatch = this.#box = undefined;
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
        this.#asked.value;
        const next = inputs?.(this, this.#reread);
        for (const value of Object.values(next ?? {}))
          if (value instanceof Node) Equal.byReferenceUnsafe(value);
        return next;
      } catch (error) {
        untracked(() => failSoft(this, error));
      }
    }

    #props() {
      return { ...this.#inputs, ...this.#properties, state: this.#state };
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
        /** @type {unknown} */ (this.shadowRoot ?? this.#stage())
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
      const root = (this.#root = Effect.runSync(
        mounting.pipe(
          Effect.provide(leafServices(this)),
          Effect.provideService(Scheduler.Scheduler, microtasks),
          Scope.provide(scope),
        ),
      ));
      const held = this.#held.splice(0);
      for (const message of held) root.send(message);
      this.#drawn();
      if (held.length) this.#redraws();
    }

    // The box a light widget draws in, since Effect UI empties the container it mounts
    // into.
    #stage() {
      const box = (this.#box = document.createElement("div"));
      box.setAttribute("data-lf-gen", "1");
      box.style.display = "contents";
      this.append(box);
      return box;
    }

    #update() {
      const root = this.#root;
      if (!root) return;
      root.setProps(this.#props());
      this.#redraws();
    }

    // The root draws a change in Effect UI's flush, the microtask that `setProps` or
    // `send` queued, so a task queued now runs after it.
    #redraws() {
      const drawn = Promise.resolve().then(() => this.#drawn());
      this.dispatchEvent(new PendingTaskEvent(drawn));
    }

    // Said on the element, which Leaf reads off the event's path, and which holds
    // every scope its shadow root draws.
    #drawn() {
      this.dispatchEvent(
        new CustomEvent(COMMANDS, {
          bubbles: true,
          composed: true,
          detail: { within: true },
        }),
      );
    }

    /** @param {{_tag: string}} event */
    #emit(event) {
      this.dispatchEvent(
        new CustomEvent(event._tag.toLowerCase(), {
          detail: event,
          bubbles: true,
          composed: true,
        }),
      );
    }
  };
  Object.assign(Widget, statics);
  customElements.define(tag, Widget);
}
