/* What a widget written as an Effect UI component asks of Leaf, as Command services
   (`Command.Service`): a component issues one with `$.run(X.make(args))`, and the
   element `defineWidget` defines provides `leafServices(element)`, so the call reaches
   the Leaf that hosts that element. A test or a story provides a fake instead
   (`X.toLayer(fn)`), with no page. The module loads in any document, so a widget
   that also runs off Leaf (portable-api.js) is given them there too.

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
   - `KeepInTab` keeps `value` under `key` in the tab's store (`tabStore`), where a
     widget keeps how the user looks at it until the tab closes; the widget reads it
     back with `tabStore.get`. */
import { Command, Effect, Layer, Schema } from "/vendor/effect-ui.js";
import { sendGesture } from "./lib/widget-events.js";
import { tabStore } from "./state/tab-store.js";

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

export class KeepInTab extends Command.Service()("leaf/KeepInTab", {
  args: { key: Schema.String, value: Schema.String },
}) {}

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
    // Leaf's application loads only on a Leaf page, so a widget that also runs off
    // Leaf can still be given these services.
    NextOnMe.toLayer((/** @type {any} */ { within }) =>
      Effect.promise(async () => {
        const { obligationActions } = await import("./host/application.js");
        obligationActions.next({ within });
      }),
    ),
    KeepInTab.toLayer((/** @type {any} */ { key, value }) =>
      Effect.sync(() => {
        tabStore.set(key, value);
      }),
    ),
  );

/** @param {Record<string, unknown>} args */
const stripUndefined = (args) =>
  Object.fromEntries(Object.entries(args).filter(([, value]) => value !== undefined));
