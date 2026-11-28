// Compiled from widget-services.ts by build/typescript.mjs; edit that file.
/* What a widget written as an Effect UI component asks of Leaf, as Command services
   (`Command.Service`): a component issues one with `$.run(X.make(args))`, and the
   element `defineWidget` defines provides `leafServices(element)`, so the call reaches
   the Leaf that hosts that element. A test or a story provides a fake instead
   (`X.toLayer(fn)`), with no page.

   This module and the adapter load in any document (portable-api.js), so a portable
   widget draws on a page without Leaf. So the module imports statically only what
   portable-api.js re-exports, the library (`lib/`) and `host/mounted.js`, which
   imports nothing, and it imports nothing dynamically. A service either speaks the
   widget protocol, which a page without Leaf hears nothing of, or calls what portable-
   api.js exports, or reads the application `mounted()` gives, as `mountApplication`
   sets it, and does nothing where that is null. Each runs in the task of the input
   that asked.

   Each service makes one of the widget protocol's calls (module-widgets.md) or
   does what a function of Leaf's does, as its entry says:

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
   - `NavigateToDatum` reveals the datum `key` names through the element's reference
     attribute `reference`, as `navigateToDatum` does, announcing `success` or
     `missing`. Focus stays where the user is, unless `focus` takes it to the datum,
     as a followed link takes it to its destination.
   - `Announce` is `lf-announce`: words a listener should hear now.
   - `KeepInTab` writes a string through `tabStore.set` and drops its result: how the
     user looks at the widget, kept for this tab, which the widget's inputs read back
     with `tabStore.get`.
   - `OpenThread` opens the thread whose id is `id` where Leaf opens it, inline or in
     Threads, as `threadActions.open` does. A thread Threads no longer lists opens
     nothing.
   - `ShowHeld` shows what the element's `HeldReading`s hold back, since the reader
     asked to see it (held-news.js, `showHeldReadings`). */
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

export class TakeBack extends Command.Service()("leaf/TakeBack", {
  args: { verb: Schema.String, unit: Schema.optional(Schema.String) },
  success: Delivery,
}) {}

export class NextOnMe extends Command.Service()("leaf/NextOnMe", {
  args: { within: Schema.instanceOf(Element) },
}) {}

export class NavigateToDatum extends Command.Service()("leaf/NavigateToDatum", {
  args: {
    reference: Schema.String,
    key: Schema.String,
    success: Schema.String,
    missing: Schema.String,
    focus: Schema.optional(Schema.Boolean),
  },
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

/** Send a gesture on `element` and wait for what became of it. */
const send = (element, type, detail) =>
  Effect.promise(async () => {
    const delivery = sendGesture(element, type, detail);
    if (!delivery) return "unrecorded";
    return (await delivery) ? "admitted" : "refused";
  });

/** Leaf's services for the widget `element`. */
export const leafServices = (element) =>
  Layer.mergeAll(
    RecordAction.toLayer((args) => send(element, "lf-action", stripUndefined(args))),
    TakeBack.toLayer((args) => send(element, "lf-undo", stripUndefined(args))),
    NextOnMe.toLayer(({ within }) =>
      Effect.sync(() => {
        mounted()?.obligationActions.next({ within });
      }),
    ),
    NavigateToDatum.toLayer(({ reference, key, success, missing, focus = false }) =>
      Effect.sync(() => {
        mounted()?.navigateToDatum(element, reference, key, {
          focus,
          success,
          missing,
        });
      }),
    ),
    Announce.toLayer(({ words }) =>
      Effect.sync(() => {
        window.dispatchEvent(new CustomEvent(ANNOUNCE, { detail: words }));
      }),
    ),
    KeepInTab.toLayer(({ key, value }) =>
      Effect.sync(() => {
        tabStore.set(key, value);
      }),
    ),
    OpenThread.toLayer(({ id }) =>
      Effect.sync(() => {
        const application = mounted();
        const thread = application?.threadList().find((thread) => thread.id === id);
        if (application && thread)
          void application.threadActions.open(thread.key, { part: "thread" });
      }),
    ),
    ShowHeld.toLayer(() =>
      Effect.sync(() => {
        mounted()?.showHeldReadings(element);
      }),
    ),
  );

const stripUndefined = (args) =>
  Object.fromEntries(Object.entries(args).filter(([, value]) => value !== undefined));
