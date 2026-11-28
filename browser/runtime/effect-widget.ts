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
     drawn: a decorating widget").

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

   Declarations. A widget sets each member Leaf reads off its element, such as its keys
   (`lfCommands`) or its thread outlets (`threadOutlets`), with
   `declare(node, declarations)` from a Mount, where `node` is one its view drew.
   `DECLARED` lists those members, and `declare` refuses any other key. Each stands on
   the element until the root closes. A Mount on a node the view drew for another
   widget, such as a child widget's element, declares for this widget. Each call says
   what it set (`lf-commands` for keys, `lf-layout` for the rest), so Leaf reads it
   again. A widget gives the Mount, as its args, what its declarations read, and
   declares on each change of them (the Mount's `changes`), the one hook Effect UI
   gives on a draw the component's own Model starts. After a draw the adapter started,
   from a set of `state`, an input or a member, the element also says `lf-commands`
   for everything under it, and `lf-layout` where it declares parts. A member Leaf
   reads off a node the view draws, such as a child outlet's `lfHold` or a row's
   `lfPreview`, the view sets on that node with `.prop`.

   Drawing follows the protocol's "Drawing" rule. The root mounts once the element has
   connected and the host has made its sets for this connection, so its first props
   hold them all: as `connectedCallback` returns where no host cancels `lf-connect` or
   the host made its sets inside it, and otherwise at the end of the host's pass that
   sets `state`, a microtask later, which the pass waits on through the `pending-task`
   the element dispatches for the mount. A property set earlier, as a sibling
   connecting first may set one, waits for that mount. A later set draws in Effect
   UI's flush, a microtask later and before the next frame, so each set that gives new
   props dispatches a `pending-task` whose promise settles after that flush.

   Focus, typed words and moves. A draw patches the nodes it keeps, so focus, a field's
   words and its caret stay where they are, and a keyed node moved among its parent's
   children moves with `moveBefore`, which keeps them too (the selection in a
   contenteditable collapses, in every engine). A keyed node is matched only among its
   parent's children, so a node a draw moves to another parent is a new node there,
   with no focus or words, and a removed node takes focus with it. So:

   - Around each draw it starts, from a set or a member, the adapter holds the user's
     place by the key of the drawn datum they are in (`data-lf-datum`, module-state.md,
     "Marking drawn data"), which the widget declares: on their own node where it
     survived the draw, else on the datum now carrying that key among those of the
     widget that drew theirs, a nested widget's where they were in one, else on the
     nearest one still drawn. It lands on the datum itself, a stop lent
     where it is no control, never on a control in it chosen by its look nor on the
     first one a boxless datum draws; where a datum takes no focus, it tries the next
     node its key marks, then the next key's, then the element of the widget that drew
     their datum, with a stop lent, as where a removal empties its list (`holdFocus`,
     `alike: false`). It puts the user back only while their focus is lost, so a nested
     widget's hold and this one need no order between them.
   - A row the widget moves to another parent, and whose user should stay on their
     control with their words and caret, it writes as a keep-alive child
     (`h.keepAlive`): its nodes move with it, and the hold puts the user back on theirs.
   - A draw the component's own message starts has no hold (Effect UI's limits,
     below), so where it removes or moves the user's row, the user lands on the body
     unless the component says where they go.
   - A native disclosure's `open` is the browser's until a gesture makes the fold part
     of the page's state (root AGENTS.md). The view writes `open` as an attribute that
     doesn't change, which Effect UI writes only as the element arrives, hears folds
     with `toggle`, and folds through the node from a Mount where the widget folds
     (lf-call-diff.js, lf-toc.js).

   Failure. A root that fails, or inputs that throw, report the failure as the
   element's `error` and show Leaf's failure box beside the authored children, which
   stay visible: a shadow root that failed shows them through a bare slot. A later
   successful reading of the inputs removes the box; a failed root stands failed until
   the element connects again.

   Lifecycle. The element dispatches `lf-connect` each time it connects, so Leaf
   dresses its shadow root and makes its sets first; where Leaf cancels the event, the
   element mounts once Leaf has set `state` for this connection. A descendant's
   `lf-connect` reads `inputs` again, since a revision may have replaced the members
   they read. Moving the element keeps its root (`connectedMoveCallback`), and leaving
   the document closes it a microtask later, as `defineElement`'s elements do.

   Effect UI's limits that shape this module:

   - Each element mounts its own root with `BrowserHost.mountEffect`, which builds a
     host for the document per mount. `defineElement` shares one host across its
     instances, but only through an internal argument, and it clears the element's
     children and knows nothing of `lf-connect`, `inputs` or `members`, so Leaf can't
     define its widgets with it.
   - A root gives its owner no hook on a flush: `Renderer.Root` has `model`, `send`
     and `setProps`, and the per-flush `commit` is the host's own. So the adapter
     hears only the draws it starts, and a draw from the component's own messages is
     said by the widget's Mount (Declarations), and holds the user's place by no key.
     The idiom tried for that place: the update that removes or moves the user's row
     issues `HtmlCommand.focus` on a ref to the control they go to (`Html.ref`,
     `.ref(ref.at(key))`), which focuses it once the draw lands; a keep-alive row that
     asks to move issues it on its own control, since a ref reaches only the instance
     that issues the Command. It lands the user there in Chromium and Firefox, and
     needs `HtmlCommand`, which `/vendor/effect-ui.js` doesn't export yet.
   - The controlled `.open()` writes the Model's value on every draw, over a fold the
     browser made whose `toggle` hasn't arrived, as a script's reveal, a summary press
     or find in page makes one: a draw in that task closes it again, and the Model
     never hears it. So a widget leaves `open` to the browser (Focus, above).
   - A keep-alive child moved to another parent keeps its nodes and the words in them,
     but focus in it drops to the body: the kernel takes the nodes out of the old
     parent before it puts them in the new one, and `insert` uses `moveBefore` only
     within one parent. The adapter's hold puts the user back for a draw it starts;
     for the component's own move, only the row's own `HtmlCommand.focus` does.
   - A datum that is a host whose shadow root delegates focus hands the hold's focus to
     its first control, open root or closed, as on main: the hold can't see past it.
   - Where no datum takes focus, as where every row is boxless (`display: contents`),
     the hold leaves the user on the widget's own element.
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
  statics?: Record<string, unknown>;
  inputs?: (element: HTMLElement, reread: () => void) => Record<string, unknown>;
  properties?: readonly string[];
  members?: Record<string, Member>;
};

// Every member Leaf reads off a widget's element (runtime-globals.d.ts), `lfHold`
// included, which Leaf reads off the outlet a widget returns, the element itself where
// the widget is its own outlet.
const DECLARED = [
  "lfCommands",
  "lfParts",
  "lfPreview",
  "lfCopy",
  "lfBar",
  "lfWord",
  "lfSays",
  "lfRevealDatum",
  "lfElementsFor",
  "lfDataDatum",
  "lfDatumLabel",
  "threadOutlets",
  "lfHold",
] as const;

/** What a widget states on its element for Leaf to read. */
export type Declarations = Partial<Pick<HTMLElement, (typeof DECLARED)[number]>>;

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

// Each standing root's container, a shadow root or a light box, to its element, which
// `declare` finds from a node the root drew.
const elementOf = new WeakMap<Node, HTMLElement>();
// The members each element's widget declared, which its root's close clears.
const declaredOn = new WeakMap<HTMLElement, Set<string>>();

// The widget whose root drew the nodes at `at` and below.
const drawerOf = (at: Node | null) => {
  while (at && !elementOf.has(at)) at = at.parentNode;
  return at ? elementOf.get(at) : undefined;
};

/** State `declarations` on the widget whose root drew `node`, until that root closes,
 *  and say them, so Leaf reads them again. */
export function declare(node: Node, declarations: Declarations) {
  const element = drawerOf(node.parentNode);
  if (!element) throw new Error("declare: the node stands in no widget's root");
  // Every own key, symbols included, since `Object.assign` copies those too.
  const keys = Reflect.ownKeys(declarations);
  const unread = keys.find((key) => !(DECLARED as readonly PropertyKey[]).includes(key));
  if (unread !== undefined)
    throw new TypeError(`declare: Leaf reads no ${String(unread)} off an element`);
  Object.assign(element, declarations);
  const declared = declaredOn.get(element) ?? new Set();
  for (const key of keys) declared.add(key as string);
  declaredOn.set(element, declared);
  if (keys.includes("lfCommands"))
    element.dispatchEvent(new CustomEvent(COMMANDS, { bubbles: true, composed: true }));
  if (keys.some((key) => key !== "lfCommands")) layoutChanged(element);
}

/** Define `tag` as a widget that draws `component`, an Effect UI HTML component whose
 *  props hold `state`, what `inputs` returns and the `properties`. */
export function defineWidget(
  tag: string,
  component: any,
  {
    shadow = false,
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
            else this.#ask();
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
    // Whether the element stands in the document, whether it is dispatching
    // `lf-connect`, whether Leaf answered this connection's, and whether Leaf has set
    // `state` since: nothing mounts before Leaf's sets for the connection.
    #connected = false;
    #connecting = false;
    #hosted = false;
    #fresh = false;
    // A mount waiting for the end of the host's pass of sets.
    #asking = false;
    // Moved by `reread`, and read with the inputs, so the watch reads them again.
    #asked = signal(0);
    #reread = () => {
      this.#asked.value++;
    };

    constructor() {
      super();
      if (shadow) this.attachShadow({ mode: "open" });
      // A page may set a property before this module defines the tag, which leaves an
      // own property hiding the accessor. Each such value goes through its accessor
      // instead, which keeps it for the mount: an element upgraded in the document
      // mounts from `connectedCallback`.
      const own = this as unknown as Record<string, unknown>;
      for (const name of ["state", ...properties, ...Object.keys(members)])
        if (Object.hasOwn(this, name)) {
          const value = own[name];
          delete own[name];
          own[name] = value;
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
        if (inputs && this.#root && event.composedPath()[0] !== this) this.#reread();
      });
    }

    get state() {
      return this.#state;
    }
    set state(value) {
      this.#state = value;
      this.#fresh = true;
      if (this.#root) this.#update();
      else this.#ask();
    }

    connectedCallback() {
      this.#connected = true;
      if (this.#root) return;
      untracked(() => {
        this.#fresh = false;
        this.#connecting = true;
        try {
          this.#hosted = !this.dispatchEvent(
            new Event(CONNECT, { bubbles: true, composed: true, cancelable: true }),
          );
        } finally {
          this.#connecting = false;
        }
        this.#mount();
      });
    }

    // With `moveBefore()`, a move calls only this, so the root stays.
    connectedMoveCallback() {}

    disconnectedCallback() {
      this.#connected = false;
      queueMicrotask(() => {
        if (this.isConnected || !this.#scope) return;
        const scope = this.#scope;
        this.#ended = this.#root?.model();
        this.#unwatch?.();
        if (this.#container) elementOf.delete(this.#container);
        if (!this.shadowRoot) (this.#container as Element | undefined)?.remove();
        const own = this as unknown as Record<string, unknown>;
        for (const key of declaredOn.get(this) ?? []) own[key] = undefined;
        declaredOn.delete(this);
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

    // Whether the host has made its sets for this connection: at once where no host
    // answered `lf-connect`, and once it has set `state` where one did.
    #ready() {
      return this.#connected && !this.#connecting && (!this.#hosted || this.#fresh);
    }

    // A set the host makes after `lf-connect` returns belongs to a pass of sets that is
    // still running, so the mount waits for its end. The pass waits on the mount.
    #ask() {
      if (this.#asking || !this.#ready()) return;
      this.#asking = true;
      const mounted = Promise.resolve().then(() => {
        this.#asking = false;
        this.#mount();
      });
      this.dispatchEvent(new PendingTaskEvent(mounted));
    }

    #mount() {
      if (this.#root || !this.isConnected || !this.#ready()) return;
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
      elementOf.set(container, this);
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
            queueMicrotask(() => failSoft(this, Cause.squash(failure.cause)));
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
    // `send` queued, so a task queued now runs after it. Where that draw takes away the
    // node the user is on, they land on the datum now carrying its key, or the nearest
    // one still drawn (Focus, typed words and moves, above).
    #redraws() {
      const restore = holdFocus(this, {
        key: "data-lf-datum",
        alike: false,
        ownerOf: (item) => drawerOf(item.parentNode),
      });
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
