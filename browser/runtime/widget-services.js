/* What a widget written as an Effect UI component asks of Leaf, as Command services
   (`Command.Service`): a component issues one with `$.run(X.make(args))`, and the
   element `defineWidget` defines provides `leafServices(element)`, so the call reaches
   the Leaf that hosts that element. A test or a story provides a fake instead
   (`X.toLayer(fn)`), with no page.

   Each service is one of the widget protocol's calls (module-plain-elements.md) or a
   function `widget-api.js` exports, under one name:

   - `RecordAction` is `lf-action`. Its success is the delivery Leaf gives the event:
     `admitted` once the server admits it, `refused` where the server refuses it and
     Leaf sets the server's state again, and `unrecorded` where nothing recorded it,
     because the verb is unavailable or the page runs without Leaf. Leaf has set the
     new `state` before the Command runs to its end, so a component that draws from
     `state` maps the delivery to nothing.
   - `NextOnMe` steps to the next obligation waiting on the user within `within`, as
     `obligationActions.next` does.
   - `OpenThread` opens the thread whose id is `id` where Leaf opens it, inline or in
     Threads, as `threadActions.open` does. A thread Threads no longer lists opens
     nothing.
   - `ShowHeld` shows what the element's `HeldReading`s hold back, since the reader
     asked to see it (held-news.js, `showHeldReadings`). */
import { Command, Effect, Layer, Schema } from "/vendor/effect-ui.js";
import { obligationActions } from "./host/application.js";
import { sendGesture } from "./lib/widget-events.js";

/** What became of a recorded gesture. */
const Delivery = Schema.Literals(["admitted", "refused", "unrecorded"]);

export class RecordAction extends Command.Service()("leaf/RecordAction", {
  args: {
    verb: Schema.String,
    detail: Schema.Record(Schema.String, Schema.Unknown),
    says: Schema.optional(Schema.String),
    attempt: Schema.optional(Schema.String),
  },
  success: Delivery,
}) {}

export class NextOnMe extends Command.Service()("leaf/NextOnMe", {
  args: { within: Schema.Unknown },
}) {}

export class OpenThread extends Command.Service()("leaf/OpenThread", {
  args: { id: Schema.String },
}) {}

export class ShowHeld extends Command.Service()("leaf/ShowHeld", {}) {}

/** Record a gesture on `element` and wait for what became of it.
 * @param {Element} element @param {Record<string, unknown>} detail */
const send = (element, detail) =>
  Effect.promise(async () => {
    const delivery = sendGesture(element, "lf-action", detail);
    if (!delivery) return /** @type {const} */ ("unrecorded");
    return (await delivery) ? "admitted" : "refused";
  });

// The host modules the services call, imported once a widget mounts: a page with no
// such widget never loads them, and a gesture finds them loaded, so its Command runs
// in the microtasks after it rather than a module load later.
const host = async () => {
  const { threadActions } = await import("./host/application.js");
  const { showHeldReadings } = await import("./records/thread/held-news.js");
  const { readThreads } = await import("./records/thread/state.js");
  return { threadActions, showHeldReadings, readThreads };
};
/** @type {ReturnType<typeof host> | undefined} */
let hosted;

/** Leaf's services for the widget `element`.
 * @param {Element} element */
export const leafServices = (element) => {
  hosted ??= host();
  return Layer.mergeAll(
    RecordAction.toLayer((/** @type {any} */ args) =>
      send(element, stripUndefined(args)),
    ),
    NextOnMe.toLayer((/** @type {any} */ { within }) =>
      Effect.sync(() => obligationActions.next({ within })),
    ),
    OpenThread.toLayer((/** @type {any} */ { id }) =>
      Effect.promise(async () => {
        const { threadActions, readThreads } = await (hosted ??= host());
        const thread = readThreads().threads.find((thread) => thread.id === id);
        if (thread) void threadActions.open(thread.key, { part: "thread" });
      }),
    ),
    ShowHeld.toLayer(() =>
      Effect.promise(async () => (await (hosted ??= host())).showHeldReadings(element)),
    ),
  );
};

/** @param {Record<string, unknown>} args */
const stripUndefined = (args) =>
  Object.fromEntries(Object.entries(args).filter(([, value]) => value !== undefined));
