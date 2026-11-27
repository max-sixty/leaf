/* What a widget written as an Effect UI component asks of Leaf, as Command services
   (`Command.Service`): a component issues one with `$.run(X.make(args))`, and the
   element `defineWidget` defines provides `leafServices(element)`, so the call reaches
   the Leaf that hosts that element. A test or a story provides a fake instead
   (`X.toLayer(fn)`), with no page.

   This module and the adapter load in any document (portable-api.js), so a portable
   widget draws on a page without Leaf. So the module imports statically only what
   portable-api.js re-exports and the library (`lib/`); a service that needs Leaf's
   host, records or another module that reads what Leaf composes into a page imports
   it dynamically as it runs, and is called only on a Leaf page.

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
   - `Announce` is `lf-announce`: words a listener should hear now.
   - `KeepInTab` is `tabStore.set`: how the user looks at the widget, kept for this
     tab, which the widget's inputs read back with `tabStore.get`.
   - `OpenThread` opens the thread whose id is `id` where Leaf opens it, inline or in
     Threads, as `threadActions.open` does. A thread Threads no longer lists opens
     nothing.
   - `ShowHeld` shows what the element's `HeldReading`s hold back, since the reader
     asked to see it (held-news.js, `showHeldReadings`). Its module stays at hand
     after the first call, so a later reveal draws in the microtasks after its press. */
import { Command, Effect, Layer, Schema } from "/vendor/effect-ui.js";
import { tabStore } from "./state/tab-store.js";
import { ANNOUNCE, sendGesture } from "./lib/widget-events.js";

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

export class Announce extends Command.Service()("leaf/Announce", {
  args: { words: Schema.String },
}) {}

export class KeepInTab extends Command.Service()("leaf/KeepInTab", {
  args: { key: Schema.String, value: Schema.String },
}) {}

export class OpenThread extends Command.Service()("leaf/OpenThread", {
  args: { id: Schema.String },
}) {}

export class ShowHeld extends Command.Service()("leaf/ShowHeld", {}) {}

/** @type {typeof import("./records/thread/held-news.js") | undefined} */
let heldNews;

/** Record a gesture on `element` and wait for what became of it.
 * @param {Element} element @param {Record<string, unknown>} detail */
const send = (element, detail) =>
  Effect.promise(async () => {
    const delivery = sendGesture(element, "lf-action", detail);
    if (!delivery) return /** @type {const} */ ("unrecorded");
    return (await delivery) ? "admitted" : "refused";
  });

/** Leaf's services for the widget `element`.
 * @param {Element} element */
export const leafServices = (element) =>
  Layer.mergeAll(
    RecordAction.toLayer((/** @type {any} */ args) =>
      send(element, stripUndefined(args)),
    ),
    NextOnMe.toLayer((/** @type {any} */ { within }) =>
      Effect.promise(async () => {
        const { obligationActions } = await import("./host/application.js");
        obligationActions.next({ within });
      }),
    ),
    Announce.toLayer((/** @type {any} */ { words }) =>
      Effect.sync(() =>
        window.dispatchEvent(new CustomEvent(ANNOUNCE, { detail: words })),
      ),
    ),
    KeepInTab.toLayer((/** @type {any} */ { key, value }) =>
      Effect.sync(() => tabStore.set(key, value)),
    ),
    OpenThread.toLayer((/** @type {any} */ { id }) =>
      Effect.promise(async () => {
        const { threadActions } = await import("./host/application.js");
        const { readThreads } = await import("./records/thread/state.js");
        const thread = readThreads().threads.find((thread) => thread.id === id);
        if (thread) void threadActions.open(thread.key, { part: "thread" });
      }),
    ),
    ShowHeld.toLayer(() => {
      if (heldNews) return Effect.sync(() => heldNews?.showHeldReadings(element));
      return Effect.promise(async () => {
        heldNews = await import("./records/thread/held-news.js");
        heldNews.showHeldReadings(element);
      });
    }),
  );

/** @param {Record<string, unknown>} args */
const stripUndefined = (args) =>
  Object.fromEntries(Object.entries(args).filter(([, value]) => value !== undefined));
