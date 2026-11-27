/* A widget written as an Effect UI component, on the protocol any custom element has
   with its host (module-plain-elements.md): properties in, events out. This header is
   the contract a widget builds against.

   `defineWidget(tag, component, options)` defines `tag` as a plain custom element that
   mounts `component` with `BrowserHost.mountEffect`. The authored children stay where
   the author put them, for Leaf's revisions and for `inputs` to read, and the root
   draws beside them:

   - By default it draws in a box of its own after the authored children: a
     `display: contents` `div` marked as words the source lacks (`data-lf-gen`). A
     widget that draws its authored children in their place hides them from its
     stylesheet while it draws.
   - With `shadow: true` it draws in an open shadow root of its own, where a `<slot>`
     the view draws shows the authored children in place. A widget that decorates
     those children draws its controls around the slot and exposes them to the theme as
     shadow parts (`part=` / `::part`), as lf-options.js's header says ("How it is
     drawn: a decorating widget"). With `slotAssignment: "manual"` as well, a slot
     shows only the children a Mount on it assigns (`slot.assign`), so a widget can
     stand each authored child at a place of its own, as lf-code stands each note under
     its line, without writing a `slot` attribute on the author's markup.

   Props. The component's Model holds only what the user is doing in the widget, such
   as an open disclosure; what Leaf knows arrives as props:

   - `state`, the reading Leaf sets on a widget whose tag declares `verbs`, as the
     `state` property every widget gets (`widgetProps`).
   - What `options.inputs(element, reread)` returns. It is called inside a signal
     effect, so a signal-backed reader it calls, such as `readObligations`, gives the
     component new props when it moves. It reads the element's attributes too, and
     only there does the component see its element. `reread()` asks for it to be read
     again, for an input no signal carries, such as a media query or a reading Leaf
     holds back (`HeldReading`) until it lets it go. A DOM node it returns is the same
     input only as itself.
   - `options.properties`, names of properties the page's own code sets on the
     element, which keeps what is set. Each is a prop of that name.

   `options.members` are properties that read and write the Model instead: reading one
   gives what its `get` reads off the Model, and setting one sends the root the message
   its `set` returns. Out of the document a member reads the Model the closed root ended
   with, and a set waits for the next root. A property or member the page set before
   the tag was defined counts, so either module may load first.

   `options.statics` are the class's static members Leaf reads off a widget's class,
   such as `lfPatch` (module-authoring.md, "Revisions") and `answered`
   (module-state.md).

   Calls to Leaf. What the component asks of Leaf, such as recording a gesture, it
   issues as a Command of Leaf's services (widget-services.js), which the mount
   provides for this element. A Command runs in a microtask of the task that issued
   it, so a gesture's Command lands before the browser's next frame. The component's
   events are for the page around it: each is a bubbling, composed `CustomEvent` named
   by its lowercased tag, with the event as `detail`, as `BrowserHost.defineElement`
   dispatches one.

   Declarations. What Leaf reads off the element itself, its keys (`lfCommands`), its
   visual parts (`lfParts`) and the elements a key into it addresses
   (`lfElementsFor`, anchor-resolution.js), a widget states with `declare(node, declarations)`
   from a Mount, where `node` is the element or one its view drew: they stand on the
   element while the root does. Each call says them (`lf-commands`, and `lf-layout`
   for parts), so Leaf reads again what they read. A widget gives the Mount, as its
   args, what its declarations read, such as the step a row's `when` reads, and
   declares on each change of them (the Mount's `changes`), the one hook Effect UI
   gives on a draw the component's own Model starts. After a draw the adapter
   started, from a set of `state`, an input or a member, the element also says
   `lf-commands` for everything under it, so Leaf reads again every key scope there,
   including one that is a single node's own `lfCommands`, such as a control's, and
   `lf-layout` where it declares parts.

   Drawing follows the protocol's "Drawing" rule. The first mount draws before
   `connectedCallback` returns. A later set draws in Effect UI's flush, a microtask
   later and before the next frame, so each set that gives new props dispatches a
   `pending-task` whose promise settles after that flush.

   Failure. A root that fails, or inputs that throw, report the failure as the
   element's `error` and show Leaf's failure box beside the authored children, which
   stay visible: a shadow root that failed shows them through a bare slot, assigned
   all of them where its slots are assigned by hand. A later
   successful reading of the inputs removes the box; a failed root stands failed until
   the element connects again.

   Lifecycle. The element dispatches `lf-connect` as it connects, so Leaf dresses its
   shadow root and makes its sets first; where Leaf cancels the event, the element
   mounts once `state` arrives. A descendant's `lf-connect` reads `inputs` again, since
   a revision may have replaced the members they read. Moving the element keeps its
   root (`connectedMoveCallback`), and leaving the document closes it a microtask
   later, as `defineElement`'s elements do.

   Effect UI's limits that shape this module:

   - Each element mounts its own root with `BrowserHost.mountEffect`, which builds a
     host for the document per mount. `defineElement` shares one host across its
     instances, but only through an internal argument, and it clears the element's
     children and knows nothing of `lf-connect`, `inputs` or `members`, so Leaf can't
     define its widgets with it.
   - A root gives its owner no hook on a flush: `Renderer.Root` has `model`, `send`
     and `setProps`, and the per-flush `commit` is the host's own. So the adapter
     hears only the draws it starts, and a draw from the component's own messages is
     said by the widget's Mount (Declarations).
   - A keyed child is matched only among its parent's children (`patchList`), so a
     keyed node that a draw moves to another parent is a new node there, and focus on
     the old one drops to the body. Around each draw it starts, the adapter holds the
     user's place by the key of the drawn datum they are on (`data-lf-datum`,
     module-state.md, "Marking drawn data"). Once the draw has landed, it puts them on
     the node that now carries that key, or on the nearest datum still drawn
     (`holdFocus`).
   - A render that changes a node's attributes removes the ones it drops before it
     sets the new ones (`patchAttrs`), so an `<a>` that trades `href` for `tabindex`
     loses focusability for an instant and Chromium blurs it. A widget keeps such a
     node focusable across both states (lf-activity.js, a row's target). */
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
import { holdFocus } from "./dom/focus.js";
import { failSoft, placesFailure } from "./lib/failure.js";
import { PendingTaskEvent } from "./lib/pending-task.js";
import { COMMANDS, CONNECT, layoutChanged } from "./lib/widget-events.js";
import { leafServices } from "./widget-services.js";

/** The props every widget component gets: Leaf's reading of it, undefined until Leaf
 *  sets one and off a Leaf page. A component's own `props` Schema extends it. */
export const widgetProps = { state: Schema.optional(Schema.Unknown) };

/** A property that reads and writes the component's Model. */
export type Member = { get: (model: any) => unknown; set: (value: any) => unknown };

export type WidgetOptions = {
  shadow?: boolean;
  slotAssignment?: SlotAssignmentMode;
  statics?: Record<string, unknown>;
  inputs?: (element: HTMLElement, reread: () => void) => Record<string, unknown>;
  properties?: readonly string[];
  members?: Record<string, Member>;
};

/** What a widget states on its element for Leaf to read. */
export type Declarations = Pick<HTMLElement, "lfCommands" | "lfParts" | "lfElementsFor">;

type Root = {
  setProps: (props: unknown) => void;
  model: () => unknown;
  send: (message: unknown) => void;
};

let mounts = 0;

// The scheduler a root's Commands and Subscriptions run on: microtasks of the task that
// asked, so a Command a gesture issues runs before the browser's next frame
// (AGENTS.md, "Responsiveness"). Without one, Effect UI posts them through its
// time-sliced HtmlScheduler, as later tasks.
const microtasks = new Scheduler.MixedScheduler("sync");

// Each standing root's element, and its container, a shadow root or a light box, to
// the element, which `declare` finds from a node the root drew.
const elementOf = new WeakMap<Node, HTMLElement>();

/** State `declarations` on the widget whose root drew `node`, or on the widget `node`
 *  is, until that root closes, and say them, so Leaf reads them again. */
export function declare(node: Node, declarations: Declarations) {
  let at: Node | null = node;
  while (at && !elementOf.has(at)) at = at.parentNode;
  const element = at && elementOf.get(at);
  if (!element) throw new Error("declare: the node stands in no widget's root");
  const { lfCommands, lfParts, lfElementsFor } = declarations;
  if ("lfElementsFor" in declarations)
    if (lfElementsFor) element.lfElementsFor = lfElementsFor;
    else delete element.lfElementsFor;
  if ("lfCommands" in declarations) {
    element.lfCommands = lfCommands;
    element.dispatchEvent(new CustomEvent(COMMANDS, { bubbles: true, composed: true }));
  }
  if ("lfParts" in declarations) {
    element.lfParts = lfParts;
    layoutChanged(element);
  }
}

/** Define `tag` as a widget that draws `component`, an Effect UI HTML component whose
 *  props hold `state`, what `inputs` returns and the `properties`. */
export function defineWidget(
  tag: string,
  component: any,
  {
    shadow = false,
    slotAssignment = "named",
    statics,
    inputs,
    properties = [],
    members = {},
  }: WidgetOptions = {},
) {
  const Widget = class extends HTMLElement {
    static {
      for (const name of properties)
        Object.defineProperty(this.prototype, name, {
          get(this: InstanceType<typeof Widget>) {
            return this.#properties[name];
          },
          set(this: InstanceType<typeof Widget>, value: unknown) {
            this.#properties = { ...this.#properties, [name]: value };
            if (this.#root) this.#update();
            else this.#mount();
          },
        });
      for (const [name, { get, set }] of Object.entries(members))
        Object.defineProperty(this.prototype, name, {
          get(this: InstanceType<typeof Widget>) {
            const model = this.#root?.model() ?? this.#ended;
            return model === undefined ? undefined : get(model);
          },
          set(this: InstanceType<typeof Widget>, value: unknown) {
            const message = set(value);
            if (!this.#root) this.#held.push(message);
            else {
              this.#root.send(message);
              this.#redraws();
            }
          },
        });
    }
    #state: unknown = undefined;
    #inputs: Record<string, unknown> = {};
    #properties: Record<string, unknown> = {};
    #root: Root | undefined = undefined;
    // The Model the last root ended with, which `members` read while none stands.
    #ended: unknown = undefined;
    // The messages `members` set while no root stood, which the next root takes.
    #held: unknown[] = [];
    #scope: Scope.Closeable | undefined = undefined;
    #container: Node | undefined = undefined;
    #unwatch: (() => void) | undefined = undefined;
    // The failure box standing beside the authored children, and whether the root
    // failed, which only connecting again mends.
    #failure: HTMLElement | undefined = undefined;
    #failed = false;
    // Leaf answered `lf-connect`: it sets `state`, and nothing mounts before it has.
    #hosted = false;
    // Moved by `reread`, and read with the inputs, so the watch reads them again.
    #asked = signal(0);
    #reread = () => {
      this.#asked.value++;
    };

    constructor() {
      super();
      if (shadow) this.attachShadow({ mode: "open", slotAssignment });
      // A page may set a property before this module defines the tag, which leaves an
      // own property hiding the accessor. Its value moves into the props here, without
      // the accessor's mount: an element upgraded in the document mounts from
      // `connectedCallback`, once Leaf has answered `lf-connect`. A member's value
      // goes through its accessor, which holds the message for that mount.
      const own = this as unknown as Record<string, unknown>;
      for (const name of [...properties, ...Object.keys(members)])
        if (Object.hasOwn(this, name)) {
          const value = own[name];
          delete own[name];
          if (name in members) own[name] = value;
          else this.#properties = { ...this.#properties, [name]: value };
        }
      // The box goes beside the authored children, which stay as they are.
      placesFailure(this, (box) => {
        this.#failure?.remove();
        this.#failure = box;
        box.setAttribute("data-lf-gen", "1");
        this.append(box);
        return true;
      });
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
      if (this.#root) return;
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
        if (this.#container) elementOf.delete(this.#container);
        elementOf.delete(this);
        if (!this.shadowRoot) (this.#container as Element | undefined)?.remove();
        this.lfCommands = this.lfParts = undefined;
        delete this.lfElementsFor;
        this.#root = this.#scope = this.#unwatch = this.#container = undefined;
        Effect.runFork(Scope.close(scope, Exit.void));
      });
    }

    // What `inputs` reads, or nothing where it throws: the failure stays on this
    // widget, rather than aborting the update that moved a signal it reads. Effect UI
    // compares props that differ by reference with `Equal.equals`, which would compare
    // two DOM nodes by every property they reach, a walk that covers the document and
    // throws on a getter such as an SVG length's, so a node is compared as itself.
    #read() {
      try {
        void this.#asked.value;
        const next = inputs?.(this, this.#reread);
        for (const value of Object.values(next ?? {}))
          if (value instanceof Node) Equal.byReferenceUnsafe(value);
        if (!this.#failed) untracked(() => this.#mended());
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
      this.#failed = false;
      this.#mended();
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
      // A shadow root is a container as an element is, as `defineElement` mounts one.
      const container = (this.#container = this.shadowRoot ?? this.#box());
      elementOf.set(container, this).set(this, this);
      const mounting = BrowserHost.mountEffect(
        component,
        this.#props(),
        container as unknown as Element,
        {
          head: false,
          key: `${tag}:${mounts++}`,
          onEmit: (event: { _tag: string }) => this.#emit(event),
          fallback: (failure: any, h: any) => {
            this.#failed = true;
            queueMicrotask(() => {
              failSoft(this, Cause.squash(failure.cause));
              if (slotAssignment === "manual")
                this.shadowRoot
                  ?.querySelector("slot")
                  ?.assign(
                    ...[...this.childNodes].filter(
                      (node): node is Element | Text =>
                        node instanceof Element || node instanceof Text,
                    ),
                  );
            });
            return this.shadowRoot ? h.slot : h.span;
          },
        },
      ) as Effect.Effect<Root, never, Scope.Scope>;
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

    #mended() {
      this.#failure?.remove();
      this.#failure = undefined;
    }

    // The box a light widget draws in, since Effect UI empties the container it mounts
    // into.
    #box() {
      const box = document.createElement("div");
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
    // `send` queued, so a task queued now runs after it. The user's place is held
    // across it by the key of the datum they are on (Effect UI's limits, above).
    #redraws() {
      const restore = holdFocus(this, { key: "data-lf-datum" });
      const drawn = Promise.resolve().then(() => {
        restore?.();
        this.#drawn();
      });
      this.dispatchEvent(new PendingTaskEvent(drawn));
    }

    // Said on the element, which Leaf reads off the event's path, and which holds
    // every scope its shadow root draws.
    #drawn() {
      if (!this.#root) return;
      this.dispatchEvent(
        new CustomEvent(COMMANDS, {
          bubbles: true,
          composed: true,
          detail: { within: true },
        }),
      );
      if (this.lfParts) layoutChanged(this);
    }

    #emit(event: { _tag: string }) {
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
