/* lf-activity: the page's history as a feed, newest first.
 *
 * The server's history reading is the only semantic input: every
 * reading of `readHistory` restates the whole feed. A row says who acted (Me for the
 * user, Page for what the page did by itself, and otherwise the name the server serves
 * the row under), what they did, the thing they did it to, and how long ago.
 *
 * What a row's event was is the server's: the thread it belongs to,
 * whether a later undo took it back, and for a widget gesture the words its ids had in
 * the document it was made in, under that document's declaration of the widget. A
 * version that rewords or removes an option therefore leaves the row as the user made
 * it. This module words those facts and names the places on the page it links to; a
 * thread goes by its name in words (`nameOf`).
 *
 * A place is named on the page the user is reading, since that is where the row leads,
 * and as the rest of the chrome names it (`nameOf`), else by its word. A
 * quoted passage is named as Threads names its anchor (`anchorLabel`).
 *
 * The thing is the row's way there: a widget or section is an ordinary fragment link,
 * so the browser owns that travel as it does for lf-toc, and a thread is a button
 * onto `OpenThread` (widget-services.js), which chooses the thread's inline destination
 * or Threads the same way a mark and t/T do. Links and buttons are the keyboard route:
 * each is a Tab stop and a go-to target. A row keeps its nodes, and so its focus, as
 * rows arrive around it.
 *
 * An excerpt is the words its Markdown renders, never the source.
 *
 * History has no authored size. Its fixed disclosure stands from first paint; rows
 * appear only when the reader opens it. An Effect UI component (runtime/effect-widget.js)
 * draws it: its Model is what the reader did, whether the feed is open and the rows it
 * showed when they closed it, and its props are what Leaf reads. Open, the rows it
 * draws are the reading `HeldReading` gives, which keeps visible history behind the
 * same disclosure until the reader asks to see the change (`ShowHeld`) or leaves it off
 * screen; shut, the list is hidden, so nothing holds it. Closed, the notice counts the
 * rows that arrived since the reader closed it, or since the feed's first reading.
 * Targets stay live: a held row keeps its historical words, but its fragment link
 * follows only a destination in the current document, and a departed destination
 * leaves historical text in the same node, without an active link. Paper shows the
 * complete current history, open or not.
 *
 * Tab memory keeps the drawn presentation through a fresh document: the feed draws it
 * until the first ready reading, which `HeldReading` then compares with it. This never
 * folds events or records a decision. */
import {
  Component,
  Effect,
  Html,
  Mount,
  Schema,
  Stream,
  UiSchema,
} from "/vendor/effect-ui.js";
import {
  HeldReading,
  tabStore,
  anchorLabel,
  elementById,
  nameOf,
  readThreads,
  readHistory,
  whileConnected,
} from "/runtime/widget-api.js";
import { KeepInTab, OpenThread, ShowHeld } from "/runtime/widget-services.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";
import { pressAttributes } from "/runtime/lib/controls.js";
import { addressableWord } from "/runtime/lib/element-word.js";
import { loadMarkdown, markdownReady, markdownWords } from "/runtime/lib/markdown.js";
import { excerptWords } from "/runtime/lib/words.js";

const NAME = 60;
const STORED = "activity-reading:";

// Where something happened, as the chrome names it, else its word.
/** @param {string | null | undefined} id */
function nameById(id) {
  const element = id ? elementById(id) : null;
  if (!element) return id || "the page";
  return excerptWords(nameOf(element), NAME) || `the ${addressableWord(element)}`;
}

// A comment's place: a passage, a drawing's part, a datum, or a design subject as
// Threads names it; a whole element by where it is.
/** @param {import("../../../browser/types/contract.js").CompleteUnion<NonNullable<import("../../../browser/types/contract.js").ServedHistoryRow["anchor"]>> | null | undefined} anchor
 * @param {import("../../../browser/types/contract.js").ServedHistoryRow["about"]} about */
function placeName(anchor, about) {
  // A bare quote is cut inside its marks, so a long one still reads as a quote.
  if (anchor?.quote && !anchor.datum && about !== "design")
    return quoted(excerptWords(anchor.quote, NAME));
  if (anchor?.visual || anchor?.datum || about === "design")
    return excerptWords(anchorLabel(anchor, about), NAME);
  return nameById(anchor?.section ?? null);
}

/** @param {import("../../../browser/types/contract.js").ServedHistoryRow} row */
const actorOf = (row) =>
  row.author === "user"
    ? "Me"
    : row.author === "page"
      ? "Page"
      : (row.agent ?? row.author);

/** @param {unknown} words */
const quoted = (words) => `“${words}”`;
/** @param {string} words */
const named = (words) => quoted(excerptWords(words, NAME));

// The thread's name in words (`nameOf`), read from the thread as
// it stands now, as every way there is.
/** @param {import("../../../browser/types/contract.js").ServedHistoryRow["thread"]} served */
const topicOf = (served) => {
  const thread = served && readThreads().threads.find(({ id }) => id === served.id);
  return thread ? excerptWords(nameOf(thread), 48) : "a thread";
};

// What a widget gesture did, as the words before its widget and any after it.
/** @param {import("../../../browser/types/contract.js").ServedGesture} gesture
 * @returns {{what: string, after?: string}} */
function gesturePhrase(gesture) {
  switch (gesture.form) {
    case "choice":
      return { what: `chose ${gesture.chosen.map(named).join(", ") || "nothing"} in` };
    case "move":
      return {
        what: `moved ${named(gesture.unit)}${gesture.to ? ` to ${named(gesture.to)}` : ""} in`,
      };
    case "edit":
      return { what: "edited" };
    case "add":
      return { what: `added ${named(gesture.words)} to` };
    case "set": {
      const value = excerptWords(gesture.value, NAME);
      return value
        ? { what: "set", after: `to ${quoted(value)}` }
        : { what: "cleared" };
    }
    case "answer": {
      const chosen = gesture.chosen.map(named).join(", ");
      return chosen
        ? { what: "answered", after: `with ${chosen}` }
        : { what: "answered" };
    }
    default:
      return { what: `recorded ${quoted(gesture.verb)} on` };
  }
}

// One served row as the words and the way there it is drawn with.
/** @param {import("../../../browser/types/contract.js").ServedHistoryRow} row
 * @returns {{what: string, after?: string, widget?: string | null, thread?: string | undefined, label?: string}} */
function describe(row) {
  const thread = (
    /** @type {string} */ what,
    /** @type {string | undefined} */ label = undefined,
  ) => ({
    what,
    thread: row.thread?.id,
    label: label ?? quoted(topicOf(row.thread)),
  });
  switch (row.kind) {
    case "comment":
      if (row.emoji)
        return thread(`reacted ${row.emoji} on`, placeName(row.anchor, row.about));
      if (row.holds) return thread("paused", nameById(row.holds));
      return thread(
        row.drawing && !row.excerpt ? "drew on" : "commented on",
        placeName(row.anchor, row.about),
      );
    case "reply":
      return thread(row.emoji ? `reacted ${row.emoji} in` : "replied in");
    case "edit":
      return thread("edited a message in");
    case "resolve":
      return thread("resolved");
    case "unresolve":
      return thread("reopened");
    case "action":
      return { ...gesturePhrase(row.gesture), widget: row.widget };
    case "report":
      return { what: `reported ${quoted(row.value)} on`, widget: row.widget };
    case "note":
      return { what: `published v${row.version}` };
  }
}

const ActivityRow = Schema.Struct({
  id: Schema.String,
  ts: Schema.String,
  actor: Schema.String,
  what: Schema.String,
  after: Schema.optional(Schema.String),
  label: Schema.optional(Schema.String),
  widget: Schema.optional(Schema.NullOr(Schema.String)),
  thread: Schema.optional(Schema.String),
  excerpt: Schema.NullOr(Schema.String),
  undone: Schema.Boolean,
});
/** @typedef {typeof ActivityRow.Type} ActivityRowType */
const Rows = Schema.Array(ActivityRow);

const ActivityProps = Schema.Struct({
  ...widgetProps,
  key: Schema.String,
  ready: Schema.Boolean,
  printing: Schema.Boolean,
  // The authoritative reading, the one `HeldReading` gives an open feed, and the one
  // a closed feed counts arrivals against until the reader first closes it.
  current: Rows,
  held: Rows,
  baseline: Rows,
  // The fragments of the rows' widgets that stand in this document.
  targets: Schema.Array(Schema.String),
  initialOpen: Schema.Boolean,
  initialLabel: Schema.optional(Schema.String),
});
/** @typedef {typeof ActivityProps.Type} ActivityPropsType */

const ActivityModel = Schema.Struct({
  open: Schema.Boolean,
  seen: Schema.NullOr(Rows),
});
/** @typedef {typeof ActivityModel.Type} ActivityModelType */

const ActivityMessage = UiSchema.TaggedEnum({
  ClickedNotice: {},
  ClickedThread: { id: Schema.String },
});

/** @param {readonly ActivityRowType[]} rows */
const keyOf = (rows) => rows.map((row) => JSON.stringify(row)).join("\n");

// What the feed draws from its Model and props: its rows, the notice's words, and
// whether the rows differ from the authoritative reading.
/** @param {ActivityModelType} model @param {ActivityPropsType} props */
export function reading(model, props) {
  const rows = props.printing
    ? props.current
    : model.open
      ? props.held
      : (model.seen ?? props.baseline);
  const news = props.ready && keyOf(rows) !== keyOf(props.current);
  const known = new Set(rows.map(({ id }) => id));
  const arrived = props.current.filter(({ id }) => !known.has(id)).length;
  const label = !props.ready
    ? (props.initialLabel ?? (model.open ? "Hide activity" : "Show activity"))
    : !model.open
      ? `Show activity${arrived ? ` · ${arrived} new` : ""}`
      : news
        ? arrived
          ? `Show ${arrived} new`
          : "Activity changed"
        : "Hide activity";
  return { rows, news, label };
}

// Keep the drawn presentation in the tab (`KeepInTab`), for the fresh document that
// follows. What it keeps moves with the props as well as the Model, so a mount follows
// it rather than an update.
const RememberReading = Mount.make(
  "RememberReading",
  { args: { key: Schema.String, saved: Schema.String } },
  (/** @type {HTMLElement} */ _node, _args, changes) =>
    Effect.gen(function* () {
      const keep = yield* KeepInTab;
      yield* Stream.runForEach(changes, ({ key, saved }) =>
        keep({ key, value: saved }),
      );
      return Component.noop;
    }),
);

// What a row's target previews: when its row happened, as the age at the row's end
// previews it to a pointer, since the keyboard reaches the target and not the age.
/** @this {Element} @param {"pointer" | "focus" | "hold"} route */
function rowTime(route) {
  const age = this.closest(".lf-activity-line")?.querySelector("lf-age");
  const said = /** @type {any} */ (age)?.lfPreview?.(route);
  return said && said.name ? { detail: [said.name] } : null;
}

export const Activity = Html.component({
  name: "Activity",
  props: ActivityProps,
  model: ActivityModel,
  message: ActivityMessage,
}).make({
  init: ($) => ({ open: $.props.initialOpen, seen: null }),
  update: {
    // A notice announcing news opens the feed onto it; otherwise it opens or closes the
    // feed. Either way the reader asked to see what the feed holds back.
    ClickedNotice: ($) => {
      const { news } = reading($.model, $.props);
      const open = news || !$.model.open;
      return $.evolve({
        open,
        seen: open ? $.model.seen : $.props.held,
      }).run(ShowHeld.make());
    },
    ClickedThread: ($, { id }) => $.run(OpenThread.make({ id })),
  },
  view: (h, model) => {
    const { key, ready, printing, targets } = h.props;
    const { rows, news, label } = reading(model, h.props);
    const hidden = !model.open && !printing;
    const live = new Set(targets);
    /** @param {ActivityRowType} row */
    const target = (row) => {
      if (row.thread)
        return h.button
          .attrs(pressAttributes("inline", "lf-activity-target"))
          .attr("data-lf-echo", "")
          .attr("data-lf-carry", `row-${row.id}`)
          .prop("lfPreview", rowTime)
          .on("click", ActivityMessage.ClickedThread({ id: row.thread }))
          .children(row.label ?? "");
      if (!row.widget && !row.label) return null;
      if (!row.widget)
        return h.span.class("lf-activity-target").children(row.label ?? "");
      const fragment = `#${encodeURIComponent(row.widget)}`;
      const href = live.has(fragment) ? fragment : undefined;
      // A departed destination leaves historical text, never a Tab offer, in the same
      // node. The node keeps a tabindex either way, since Chromium blurs a node at once
      // when it loses its tabindex with no href, and Effect UI removes attributes
      // before it sets them.
      return h.a
        .class("lf-activity-target")
        .attr("data-lf-carry", `row-${row.id}`)
        .attr("tabindex", href ? "0" : "-1")
        .attr("href", href)
        .prop("lfPreview", rowTime)
        .children(row.label ?? "");
    };
    // A view has one root: a plain block around the notice, the list and the empty line.
    const feed = h.div;
    return (
      ready && !printing
        ? feed.onMount(
            RememberReading({
              key,
              saved: JSON.stringify({ open: model.open, shown: rows, label }),
            }),
          )
        : feed
    ).children(
      h.button
        .attrs(pressAttributes("inline", "lf-activity-news"))
        .attr("data-lf-carry", "notice")
        .attr("aria-expanded", String(model.open))
        .attr("data-lf-news", news ? "" : undefined)
        .on("click", ActivityMessage.ClickedNotice())
        .children(label),
      h.ol
        .class("lf-activity-list")
        .attr("data-lf-scroll", "")
        .attr("data-lf-gen", "1")
        .attr("hidden", hidden ? "" : undefined)
        .children(
          ...rows.map((row) =>
            h.li
              .key(row.id)
              .class("lf-activity-row")
              .attr("data-lf-undone", row.undone ? "" : undefined)
              .children(
                h.p
                  .class("lf-activity-line")
                  .children(
                    h.strong.class("lf-activity-actor").children(row.actor),
                    " ",
                    h.span.class("lf-activity-what").children(row.what),
                    " ",
                    target(row),
                    row.after ? " " : null,
                    row.after
                      ? h.span.class("lf-activity-what").children(row.after)
                      : null,
                    " ",
                    h
                      .el("lf-age")
                      .attr("class", "lf-activity-time")
                      .attr("datetime", row.ts),
                    row.undone ? " " : null,
                    row.undone
                      ? h.span.class("lf-activity-undone").children("undone")
                      : null,
                  ),
                row.excerpt
                  ? h.p.class("lf-activity-excerpt").children(row.excerpt)
                  : null,
              ),
          ),
        ),
      h.p
        .class("lf-activity-empty")
        .attr("data-lf-gen", "1")
        .attr("hidden", hidden || rows.length > 0 ? "" : undefined)
        .children("Nothing shown yet."),
    );
  },
});

/** @typedef {{held: HeldReading<string>, shown: string, restored: string | null, baseline: string | null, paper: MediaQueryList}} Feed */
/** @type {WeakMap<HTMLElement, Feed>} */
const feeds = new WeakMap();

/** @param {HTMLElement} element @param {() => void} reread @returns {Feed} */
function feedOf(element, reread) {
  let feed = feeds.get(element);
  if (feed) return feed;
  const saved = tabStore.get(STORED + element.id);
  const initial = saved ? JSON.parse(saved) : null;
  const paper = matchMedia("print");
  whileConnected(element, (signal) =>
    paper.addEventListener("change", reread, { signal }),
  );
  feed = {
    // The rows growth could move what the reader sees; the notice is a fixed box.
    held: new HeldReading(
      element,
      () => [...element.querySelectorAll(".lf-activity-list, .lf-activity-empty")],
      reread,
    ),
    shown: JSON.stringify(initial?.shown ?? []),
    restored: initial && JSON.stringify(initial.shown),
    baseline: initial && JSON.stringify(initial.shown),
    paper,
  };
  feeds.set(element, feed);
  return feed;
}

defineWidget("lf-activity", Activity, {
  inputs: (element, reread) => {
    const feed = feedOf(element, reread);
    // What the tab kept last: a feed drawn again after it left the page opens as the
    // reader left it.
    const stored = tabStore.get(STORED + element.id);
    /** @type {{open: boolean, label: string} | null} */
    const kept = stored ? JSON.parse(stored) : null;
    const printing = feed.paper.matches;
    const history = readHistory();
    const ready = history.phase === "ready";
    // A failed parser import can retry on the next reading, including a return.
    if (!markdownReady())
      loadMarkdown().then((loaded) => {
        if (loaded) reread();
      });
    /** @type {ActivityRowType[]} */
    const current = history.events.map((served) => {
      const row = describe(served);
      return {
        ...row,
        ...((row.widget || row.label) && {
          label: row.label ?? nameById(row.widget),
        }),
        excerpt: served.excerpt
          ? excerptWords(markdownWords(served.excerpt), 140)
          : null,
        id: served.id,
        ts: served.ts,
        actor: actorOf(served),
        undone: served.undone,
      };
    });
    // One string per reading, so a reading equal to the one drawn is the same value.
    const wanted = JSON.stringify(current);
    if (ready) {
      // The first ready reading compares with the presentation the tab kept.
      if (feed.restored !== null) {
        feed.held.hold(feed.restored);
        feed.restored = null;
      }
      feed.baseline ??= wanted;
      // Paper draws the current reading and leaves what the screen holds as it stands.
      if (!printing) feed.shown = feed.held.hold(wanted);
    }
    /** @type {ActivityRowType[]} */
    const held = JSON.parse(feed.shown);
    const targets = [...current, ...held]
      .map(({ widget }) => (widget ? `#${encodeURIComponent(widget)}` : null))
      .filter((fragment) => fragment !== null && elementById(fragment));
    return {
      key: STORED + element.id,
      ready,
      printing,
      current: ready || printing ? current : held,
      held,
      baseline: JSON.parse(feed.baseline ?? wanted),
      targets: [...new Set(targets)],
      initialOpen: kept?.open ?? false,
      ...(kept && { initialLabel: kept.label }),
    };
  },
});
