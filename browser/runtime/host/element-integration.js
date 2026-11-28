// Compiled from element-integration.ts by build/typescript.mjs; edit that file.
/* Leaf's side of the protocol a widget has with its host. Every custom element whose
   tag declares `verbs` or `inputs` is driven the same way, from outside
   (`hostDeclaredElements`), whether its class is a plain `HTMLElement` or a
   `LeafElement` (lib/leaf-element.js), so its module needs none of Leaf's helpers.
   While such an element stands in the document or a declared shadow stage, Leaf sets
   on it:

   - `state`, where the element is a widget whose tag declares `verbs`: its reading
     (`widgetState`, widget-state.js), once its class is defined and again each
     time the reading moves, whoever moved it. Leaf also sets it again, though the
     reading stands, where something the element draws beside its `state` has moved
     (`stateAgain`): setting `state` is how Leaf tells any element to draw;
   - with `state`, the property a verb's record names (`record.property`, the
     registry's `$verbs.record`), to that verb's value ("Recorded properties" below);
   - the property each bound input names, and a written data body as its `value`
     (element-data.js, "Bound values").

   On a widget whose tag declares `verbs`, Leaf also listens for the `lf-action` and
   `lf-undo` the element records with (`hearRecords`, widget-controller.js). So the
   element Leaf sets `state` on is the one it hears, and the events need no options
   to reach it.

   Recorded properties. An element that knows nothing of Leaf keeps a value in a
   property and says the user changed it with an event, as a form control does with
   `value` and `change`. Where a verb's record names that property, Leaf sets it to
   the verb's value as text, the empty string while the verb has none, and only when
   that value has moved since the last set and the property reads otherwise: a value
   the user is still changing, as on a slider mid-drag, survives every other move of
   the reading. On the record's event Leaf reads the property and records it as the
   verb's action, through the controller `lf-action` reaches. Leaf's own set is no
   act of the user's, so an event the element dispatches in answer to it records
   nothing. An event dispatched from inside the set is such an answer, whatever the
   property then reads, as where the element keeps the value within a range and says
   so. So is an event at which the property reads the verb's value, which covers an
   element that answers the set later. An element that both answers later and keeps
   another value than it was set has that value recorded, since nothing then tells
   its answer from the user's change. Where nothing can be sent, as on a quoted
   widget, a page with no server or a verb the agent writes, Leaf sets the property
   back to the verb's value, and a refusal moves the reading, so the element shows
   no value the page does not hold. The tag may also declare the property an output,
   which other elements read (data.js). Leaf tells those readers to read it again
   (`heldMoved`) as each of its own sets returns, and at each record event dispatched
   outside a set, after recording what the event reports.

   Until that set the element shows the change the user made, because Leaf sets
   nothing on it to stop the change. An element that should take none reads the
   verb's `available` from its `state`, as any widget does, and what it shows then is
   its package's to choose. Neither attribute Leaf could set from outside does what
   Leaf's own widgets do there, which stay readable and stay comment targets:
   - `inert` takes the element, and the value it shows, out of the accessibility tree
     and out of the targets a comment can aim at, by pointer or by keyboard, and
     leaves it looking live;
   - `disabled`, on an element that has it, keeps the value in the accessibility tree
     and the element a keyboard target, but an Alt+click anywhere on the control
     starts no comment, the value takes the library's faded face, and the property
     would be a second way of saying `available`.

   Leaf makes none of its sets, of `state`, a recorded property or a bound input, until
   the reading holds every declared verb and the page has read the data a bound source
   names, so the element never draws a reading nobody has made yet. Each pass of sets runs in the stack that moved the reading, inside a claim
   on the element's render region. So a gesture's result is drawn before the
   `dispatchEvent` that recorded it returns, and the page reads as presented, and as
   showing a data delivery, only once the setters have returned and the drawing they
   announced with `pending-task` is in. A `pending-task` the element dispatches on
   itself at any other time is a draw it started by itself. Every claim on the region
   waits for all the drawing the element has announced and not finished, so a later
   pass never lets go of an earlier draw, and for the element's hold on its own
   drawing (`lf-defer`) that stood when the claim's sets were made, under which it
   draws nothing; a `pending-task` from a node inside the element is preparation
   (widget-controller.js). A visual may have redrawn the parts
   it marks by the time a pass's drawing is in, which the pass says with
   `layoutChanged` (state/visual-parts.js).

   Where one publication moves several readings, their `state`s are set in the page's
   rendered order, a parent before what it holds, whichever class was defined first: a
   parent's draw may move a member to where that member's own draw then finds it. A
   draw an element starts by itself is promised no order.

   A setter that throws is the element's failure. The pass reports it and still makes
   its other sets, and the set that threw is owed again in the next pass. The fail-soft
   box stands after what the element holds, unless the element places its own, until a
   pass whose sets all return.

   An element is driven from the moment Leaf sees it arrive with its class defined. One
   that says `lf-connect` as it connects (`CONNECT`, lib/widget-events.js) is driven
   before that event returns instead, so what it builds and first draws can read what
   Leaf set, and Leaf cancels the event where it will set the element's `state`: a
   widget's reading, or, on an element that only reads data, an empty one once its
   inputs are set. Leaf also dresses the open shadow root of an element that says it
   (dom/shadow-stage.js), whatever its tag declares. */
import { effect, signal, untracked } from "/vendor/signals-core.js";
import {
  attachApplicationPresentation,
  attachWidgetPresentation,
} from "../state/semantic-state.js";
import { widgetDescriptor } from "../records/widget-descriptors.js";
import {
  announceDrawing,
  controllerOf,
  drawingOf,
  hearRecords,
  holdsOn,
  isDrawing,
  takeDrawing,
  widgetMounted,
} from "./widget-controller.js";
import { widgetState } from "./widget-state.js";
import { ElementData } from "./element-data.js";
import { heldMoved } from "./data.js";
import { registry, tagsDeclaring } from "../state/registry.js";
import { liveStages, watchArrivals, watchOwner } from "../dom/arrivals.js";
import { CONNECT, layoutChanged } from "../lib/widget-events.js";
import { PENDING_TASK } from "../lib/pending-task.js";
import {
  failurePlaced,
  placesFailure,
  reportFailure,
  showFailure,
} from "../lib/failure.js";
import { adoptShadowStage } from "../dom/shadow-stage.js";
import { byRenderedOrder } from "../lib/shadow-tree.js";
import { tick } from "../state/version-signal.js";

let regions = 0;
// What `state` holds on an element that only reads data, once its inputs are set.
const NO_VERBS = Object.freeze({});
// A recorded property's value as the attribute its record names would read it
// ("Recorded properties").
const text = (value) => (value == null ? "" : String(value));
// The text of the value `reading` gives a verb whose record is a value.
const valueOf = (reading, verb) => {
  const state = reading?.state[verb];
  return text(state && "value" in state ? state.value : null);
};
// An arrival offers an element again whenever its children change (dom/arrivals.js).
const hosted = new WeakSet();
// The elements that said `lf-connect`.
const asked = new WeakSet();
// The request that has each widget's `state` set again (`stateAgain`), and the
// signal it moves.
const againBy = new WeakMap();

// The `state`s a publication owes, each by its element. Every reading's own effect
// claims its region and adds to them as the publication notifies it; writing `owed`
// there queues the one effect below behind all of those, still inside the publication.
const owing = new Map();
const owed = signal(0);
effect(() => {
  owed.value;
  if (!owing.size) return;
  const passes = byRenderedOrder([...owing], ([element]) => element);
  owing.clear();
  untracked(() => {
    for (const [, pass] of passes) pass();
  });
});

function host(element) {
  if (hosted.has(element)) return;
  hosted.add(element);
  const descriptor = widgetDescriptor(element);
  const verbs = Object.keys(descriptor?.declaration.verbs ?? {});
  // Made here, ahead of this element's own watch below, so the controller hears each
  // return first: it presents the preparation the widget still has under way before
  // the return's sets are drawn, and a draw that asks whether that preparation is in
  // (reports.js) finds it.
  const controller = verbs.length ? controllerOf(element) : null;
  if (controller) hearRecords(element);
  // The verbs whose value the element keeps in a property ("Recorded properties").
  const properties = Object.entries(descriptor?.declaration.verbs ?? {}).flatMap(
    ([verb, { record }]) =>
      record?.kind === "value" && record.property
        ? [{ verb, property: record.property, event: record.event ?? "change" }]
        : [],
  );
  // A tag that declares verbs has a `state` only where the page captured the widget.
  const records = Boolean(registry[element.localName]?.verbs);
  const visual = Boolean(registry[element.localName]?.visual);
  const name = descriptor
    ? `widget:${descriptor.id}:render`
    : `element:${element.localName}:${++regions}`;
  let region = null;
  // The open claim the next pass settles.
  let ticket = null;
  let shown = null;
  let written = false;
  // Whether the element has had a pass of sets.
  let passed = false;
  let box = null;
  const claim = () => {
    ticket ??= region?.present((reason) => showFailure(element, reason)) ?? null;
  };
  // A source's accepted reading claims the region, and its delivery draws.
  const data = new ElementData(element, claim);
  // The element may hold nodes no later set makes again, so its failure stands after
  // them, in the tree that shows them.
  if (!failurePlaced(element))
    placesFailure(element, (placed) => {
      box?.remove();
      box = placed;
      (element.shadowRoot ?? element).append(placed);
      return true;
    });
  // Whether a pass is making its sets, whose claim it settles itself.
  let passing = false;
  // A listener on a shadow host sees itself as the target of an event from inside its
  // root, so the element that dispatched is read off the path.
  element.addEventListener(PENDING_TASK, (event) => {
    if (event.composedPath()[0] !== element) return;
    takeDrawing(event);
    announceDrawing(element, event.complete);
    // A draw the element started by itself claims its region, unless a claim already
    // stands open for a pass still to settle. Away, it waits for the return's pass.
    if (!passing && !ticket)
      region
        ?.present((reason) => showFailure(element, reason))
        .resolve(Promise.all([drawingOf(element), ...holdsOn(element)]));
  });
  // One set the element is owed, made whether or not another threw.
  const attempt = (failures, owed) => {
    try {
      owed();
    } catch (error) {
      failures.push(error);
    }
  };
  // The data body and each bound input, which the element's own effect follows.
  const setInputs = (failures) => {
    // What a setter reads is the element's own to follow, never the pass's.
    if (!written)
      attempt(failures, () => {
        untracked(() => data.initialize());
        written = true;
      });
    attempt(failures, () => data.deliver());
  };
  // How many times `state` was asked for again though the reading stands
  // (`stateAgain`), and how many of those the last set that returned had heard: a
  // request made from inside a set is owed another, and so is a set that threw. The
  // signal has the element's effect make the pass at once. An element out of the page
  // is set as it returns. Its effect may outlive its leaving by a moment and is told
  // nothing meanwhile: a set made on an element out of the page asks again from
  // inside the set, so each telling would make another set, without end.
  let asks = 0;
  let answered = 0;
  const askedAgain = signal(0);
  if (controller)
    againBy.set(element, {
      ask: () => {
        asks += 1;
        if (element.isConnected) tick(askedAgain);
      },
      asked: askedAgain,
    });
  // Whether the element returned to the page since its last set of `state`, which is
  // owed again then. `shown` stays, so a recorded property whose value stands keeps
  // what the user changed it to while the element was away.
  let returned = false;
  // Whether a pass owes `state`: a reading that moved or is asked for again, or, on an
  // element with none that said `lf-connect`, the empty state that says its inputs are
  // set; and either one again on the element's return.
  const owesState = (reading) =>
    reading
      ? reading !== shown || asks !== answered || returned
      : (!passed || returned) && asked.has(element) && !records;
  // `state` comes first, so a recorded property's setter reads the state it belongs to,
  // and each set has its own attempt, so one that throws keeps no other from the
  // element. A pass any of them threw in is owed again whole.
  const setState = (reading, failures) => {
    const state = reading ? widgetState(reading) : NO_VERBS;
    const heard = asks;
    const before = failures.length;
    attempt(failures, () => untracked(() => Object.assign(element, { state })));
    for (const { verb, property } of properties)
      attempt(failures, () =>
        untracked(() => {
          const value = valueOf(reading, verb);
          if (shown && valueOf(shown, verb) === value) return;
          if (text(Reflect.get(element, property)) !== value)
            setProperty(property, value);
        }),
      );
    if (failures.length > before) return;
    shown = reading;
    answered = heard;
    returned = false;
  };
  // Whether Leaf is setting a recorded property, when an event the element dispatches
  // is its answer to that set. The element may dispatch no `change` for the set, so
  // Leaf tells the property's readers (data.js) as the set returns.
  let setting = false;
  const setProperty = (property, value) => {
    setting = true;
    try {
      Reflect.set(element, property, value);
    } finally {
      setting = false;
    }
    heldMoved(element);
  };
  // The user's change of a recorded property, recorded as its verb's action. The
  // event may come from a control inside the element, where the property's readers
  // (data.js) don't hear it, so Leaf tells them after recording the change.
  for (const { verb, property, event } of properties)
    element.addEventListener(event, () => {
      if (setting) return;
      const reading = controller?.read() ?? null;
      const value = text(Reflect.get(element, property));
      if (value !== valueOf(reading, verb)) {
        const sent =
          reading?.actions[verb] &&
          controller?.dispatch({ kind: "action", verb, detail: { value } });
        if (!sent) setProperty(property, valueOf(reading, verb));
      }
      heldMoved(element);
    });
  // What a pass's sets came to, said to whoever hears it: the claim, the page's error
  // report, and the readers of a visual's layout.
  const settle = (drawing, failures, held) => {
    if (visual) layoutChanged(element);
    if (failures.length) {
      reportFailure(element, failures[0]);
      drawing?.reject(failures[0]);
      return;
    }
    box?.remove();
    box = null;
    const drawn = drawingOf(element);
    drawing?.resolve(Promise.all([drawn, ...held]));
    // The drawing under way may redraw the marks as it lands.
    if (visual && isDrawing(element))
      void drawn.then(
        () => layoutChanged(element),
        () => {},
      );
  };
  // The document-wide renderers read the element once the drawing of its first pass
  // is in, on each arrival.
  let mounted = false;
  // The pass's claim stands until the pass settles it, so a drawing the element
  // announces before a deferred `state` set waits for that set's drawing too.
  const take = () => {
    const drawing = ticket;
    ticket = null;
    return drawing;
  };
  const draw = () => {
    askedAgain.value;
    claim();
    const reading = controller?.read() ?? null;
    // A hold the element has on its drawing now leaves this pass's sets undrawn until
    // it ends; one that begins in the draw a set starts does not hold that draw.
    const held = holdsOn(element);
    // A revision's replacement lacks its verbs until its document is adopted.
    if (
      (reading && !verbs.every((verb) => verb in reading.state)) ||
      data.awaitsDelivery()
    ) {
      take()?.resolve(Promise.all([drawingOf(element), ...held]));
      return;
    }
    const failures = [];
    passing = true;
    setInputs(failures);
    passing = false;
    const finish = () => {
      if (owesState(reading)) {
        passing = true;
        setState(reading, failures);
        passing = false;
      }
      passed = true;
      untracked(() => settle(take(), failures, held));
      if (mounted || !descriptor) return;
      mounted = true;
      const read = () => void (element.isConnected && widgetMounted());
      void drawingOf(element).then(read, read);
    };
    // The first pass is made at once, so an element that asked reads it as it builds.
    // A later `state` waits its turn among the readings its publication moved.
    if (!passed || !owesState(reading)) return finish();
    owing.set(element, finish);
    tick(owed);
  };
  let leave = null;
  watchOwner(element, {
    // A paint that mounts the element connects it inside that paint, and what the
    // connection reads is its own to follow, never that paint's.
    connect: () =>
      untracked(() => {
        const attached = descriptor
          ? attachWidgetPresentation(descriptor.id, "render")
          : attachApplicationPresentation(name);
        region = attached;
        const leaveData = data.connect(name);
        const stop = effect(draw);
        leave = () => {
          stop();
          leaveData?.();
          attached.disconnect();
        };
      }),
    disconnect() {
      leave?.();
      leave = region = ticket = null;
      mounted = false;
      returned = true;
    },
  });
}

// An element that asks is driven before its `lf-connect` returns, and hears, by the
// event's cancellation, that Leaf will set its `state`.
const dressed = new WeakSet();
document.addEventListener(CONNECT, (event) => {
  const [element] = event.composedPath();
  if (!(element instanceof Element)) return;
  untracked(() => {
    const root = element.shadowRoot;
    if (root && !dressed.has(root)) {
      dressed.add(root);
      adoptShadowStage(root);
    }
    const entry = registry[element.localName];
    if (!entry?.verbs && !entry?.inputs) return;
    asked.add(element);
    host(element);
    if (!entry.verbs || widgetDescriptor(element)) event.preventDefault();
  });
});

/** The request that has `element`'s `state` set again though its reading stands, or
 * undefined where Leaf sets no `state` on the element. It is how Leaf tells an element
 * to draw again when something it draws beside its `state` has moved, as its reports
 * turning ready does (reports.js). Leaf makes the set before any microtask runs, in
 * its place among the sets a publication owes, and on an element that is away, as it
 * returns. */
export const stateAgain = (element) => againBy.get(element)?.ask;

/** Read, in a reader that follows signals, what moves as `stateAgain`'s request is made
 * on `element` while it stands, so that reader reads again then too, as a draw told
 * to wait does (reports.js). */
export const followStateAgain = (element) => void againBy.get(element)?.asked.value;

/** Drive each element whose tag declares `verbs` or `inputs` from outside while it
 * stands. An element is driven only once its class is defined: a property set on an
 * element before its upgrade would be the element's own, and hide the class's setter
 * from every later set. One watch holds every such tag, and a tag's definition offers
 * the elements already standing under it. */
export function hostDeclaredElements() {
  const tags = tagsDeclaring((entry) => entry.verbs || entry.inputs);
  if (!tags.length) return;
  const offer = watchArrivals(tags.join(","), [], {
    arrive(element) {
      if (customElements.get(element.localName)) host(element);
    },
    leave() {},
  });
  for (const tag of tags)
    void customElements.whenDefined(tag).then(() => {
      for (const root of [document, ...liveStages()])
        for (const element of root.querySelectorAll(tag)) offer(element);
    });
}
