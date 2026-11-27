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
   - `TakeBack` is `lf-undo`: it takes back the action in force for `verb`, or for
     one of its units, and succeeds with the delivery as `RecordAction` does.
   - `NextOnMe` steps to the next obligation waiting on the user within `within`, as
     `obligationActions.next` does.
   - `RememberForTab` keeps `value` under `key` for this browser tab, as
     `tabStore.set` does. */
import { Command, Effect, Layer, Schema } from "/vendor/effect-ui.js";
import { obligationActions } from "./host/application.js";
import { tabStore } from "./state/tab-store.js";
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

export class TakeBack extends Command.Service()("leaf/TakeBack", {
  args: { verb: Schema.String, unit: Schema.optional(Schema.String) },
  success: Delivery,
}) {}

export class NextOnMe extends Command.Service()("leaf/NextOnMe", {
  args: { within: Schema.Unknown },
}) {}

export class RememberForTab extends Command.Service()("leaf/RememberForTab", {
  args: { key: Schema.String, value: Schema.String },
}) {}

/** Send a gesture on `element` and wait for what became of it.
 * @param {Element} element @param {"lf-action" | "lf-undo"} type
 * @param {Record<string, unknown>} detail */
const send = (element, type, detail) =>
  Effect.promise(async () => {
    const delivery = sendGesture(element, type, detail);
    if (!delivery) return /** @type {const} */ ("unrecorded");
    return (await delivery) ? "admitted" : "refused";
  });

/** Leaf's services for the widget `element`.
 * @param {Element} element */
export const leafServices = (element) =>
  Layer.mergeAll(
    RecordAction.toLayer((/** @type {any} */ args) =>
      send(element, "lf-action", stripUndefined(args)),
    ),
    TakeBack.toLayer((/** @type {any} */ args) =>
      send(element, "lf-undo", stripUndefined(args)),
    ),
    RememberForTab.toLayer((/** @type {any} */ { key, value }) =>
      Effect.sync(() => tabStore.set(key, value)),
    ),
    NextOnMe.toLayer((/** @type {any} */ { within }) =>
      Effect.sync(() => obligationActions.next({ within })),
    ),
  );

/** @param {Record<string, unknown>} args */
const stripUndefined = (args) =>
  Object.fromEntries(Object.entries(args).filter(([, value]) => value !== undefined));
