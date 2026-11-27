/* What a widget written as an Effect UI component asks of Leaf, as Command services
   (`Command.Service`): a component issues one with `$.run(X.make(args))`, and the
   element `defineWidget` defines provides `leafServices(element)`, so the call reaches
   the Leaf that hosts that element. A test or a story provides a fake instead
   (`X.toLayer(fn)`), with no page.

   This module and the adapter load in any document (portable-api.js), so a portable
   widget draws on a page without Leaf. So the module imports statically only what
   portable-api.js re-exports, the library (`lib/`) and `host/mounted.js`, which
   imports nothing. A service that needs Leaf's application reaches it there, as
   `mountApplication` sets it, so it calls the application in the task of the input
   that asked, and does nothing on a page without Leaf.

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
   - `NavigateToDatum` reveals the datum `key` names through the element's reference
     attribute `reference`, as `navigateToDatum` does, announcing `success` or
     `missing`. Focus stays where the user is.
   - `Announce` is `lf-announce`: words a listener should hear now.
   - `KeepInTab` is `tabStore.set`: how the user looks at the widget, kept for this
     tab, which the widget's inputs read back with `tabStore.get`. */
import { Command, Effect, Layer, Schema } from "/vendor/effect-ui.js";
import { mounted } from "./host/mounted.js";
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

export class NavigateToDatum extends Command.Service()("leaf/NavigateToDatum", {
  args: {
    reference: Schema.String,
    key: Schema.String,
    success: Schema.String,
    missing: Schema.String,
  },
}) {}

export class Announce extends Command.Service()("leaf/Announce", {
  args: { words: Schema.String },
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
    NextOnMe.toLayer((/** @type {any} */ { within }) =>
      Effect.sync(() => {
        mounted()?.obligationActions.next({ within });
      }),
    ),
    NavigateToDatum.toLayer((/** @type {any} */ { reference, key, success, missing }) =>
      Effect.sync(() => {
        mounted()?.navigateToDatum(element, reference, key, {
          focus: false,
          success,
          missing,
        });
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
  );

/** @param {Record<string, unknown>} args */
const stripUndefined = (args) =>
  Object.fromEntries(Object.entries(args).filter(([, value]) => value !== undefined));
