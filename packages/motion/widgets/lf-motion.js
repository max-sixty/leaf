/* lf-motion: one transport for page-authored illustrations and compared video
 * recordings, drawn by an Effect UI component (runtime/effect-widget.js) into the
 * element's shadow root, with a slot that shows the authored previews in place.
 *
 * The Model is what the user does with the study: the clock's time, its speed and
 * whether it plays, and what it was told by the page around it (reduced motion, whether
 * any recording stands in the study, a failed playback or frame). The author's frame
 * function is a prop, `renderFrame`, which the page module assigns; `currentTime` reads
 * the Model's time and seeks it (`members`, effect-widget.js). Recordings and the
 * author's drawing are DOM work after each commit, done by one mount on the slot
 * (`DriveStudy`): it draws the frame at the clock's time, seeks, plays and pauses the
 * recordings, and reports what the page tells it back as messages.
 *
 * A synchronous `renderFrame(time)` paints illustrations from milliseconds, while
 * descendant videos play on their native media clocks. The furthest video time drives
 * the shared timeline; seeking and pausing align all views to that time. Videos are
 * never sought on animation frames: the browser owns decoding and playback. The author
 * owns geometry, duration and meaning. Assigning a renderer draws the current frame, so
 * either module may load first; assigning a new one draws again, which is how a page
 * redraws after its own layout changed.
 *
 * The transport stands in the shadow root and reads nothing from the authored previews
 * but which videos they hold, so a revision edits inside the study in place (`lfPatch`):
 * the clock, its playback and the page's `renderFrame` carry on, and the browser's
 * scroll anchoring keeps the reader's place among the previews. A recording a revision
 * adds joins the clock once its metadata loads. A renderer holding nodes the revision
 * replaced is the page module's to assign again when `lf-page-interface` fires.
 *
 * Playback, speed and scrubbing are local inspection, never page events: the clock's
 * time and speed are kept in the tab (`KeepInTab`) whenever it comes to rest. The clock
 * starts still, stops on disconnect, inspection and the user's own input in the study
 * (a press, key, wheel, touch or text in the previews, the window losing focus or the
 * tab hiding), and resumes only on Play. Reduced motion turns Play into Show end, which
 * seeks to the end, and leaves manual seeking available. Author callbacks must draw a
 * complete frame, including when seeking backward.
 *
 * It imports only helpers that load in any document, so a plain HTML page that maps
 * `/runtime/` and `/vendor/` plays it too, by its own controls. Play is the widget's own
 * button: its click plays, and the transport draws it `aria-disabled` while there is
 * nothing to play. Leaf reads the Play command, which binds no key, from `lfCommands`,
 * and names the button by it in its command reference. A playback failure says so in
 * the clock's place and reaches Leaf as the element's `error` event. A frame that
 * throws shows the failure box under the transport, with the study still standing, and
 * stops the clock: the box stays until a frame draws. */
import {
  Component,
  Effect,
  Html,
  HtmlSubscription,
  Mount,
  Queue,
  Schema,
  Stream,
  UiSchema,
} from "/vendor/effect-ui.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";
import { KeepInTab } from "/runtime/widget-services.js";
import { tabStore } from "/runtime/portable-api.js";
import { offerActionElement, offerAttributes } from "/runtime/lib/controls.js";
import { describeFailure } from "/runtime/lib/exception.js";
import { reportFailure } from "/runtime/lib/failure.js";
import { COMMANDS } from "/runtime/lib/widget-events.js";

const RATES = [1, 0.5, 0.25];
// The input that pauses playback is the user's own, inside the previews.
const INPUTS = ["pointerdown", "keydown", "input", "wheel", "touchstart"];
const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

const Saved = Schema.Struct({ time: Schema.Number, rate: Schema.Number });

const MotionProps = Schema.Struct({
  ...widgetProps,
  key: Schema.String,
  duration: Schema.Number,
  label: Schema.String,
  saved: Schema.NullOr(Saved),
  renderFrame: Schema.optional(Schema.Any),
});

const MotionModel = Schema.Struct({
  time: Schema.Number,
  rate: Schema.Number,
  playing: Schema.Boolean,
  reduced: Schema.Boolean,
  videos: Schema.Boolean,
  // A playback the browser refused, which the clock's place says.
  failure: Schema.NullOr(Schema.String),
  // Why the last frame failed to draw, which the failure box says.
  broken: Schema.NullOr(Schema.String),
});

export const MotionMessage = UiSchema.TaggedEnum({
  ClickedPlay: {},
  Sought: { time: Schema.Number },
  ChoseRate: { rate: Schema.Number },
  Interrupted: {},
  TickedFrame: { delta: Schema.Number },
  ReadVideos: { time: Schema.Number, ended: Schema.Boolean },
  FoundVideos: { any: Schema.Boolean },
  FailedPlayback: {},
  FailedDraw: { message: Schema.String },
  Drew: {},
  ChangedMotion: { reduced: Schema.Boolean },
});

/** @param {{videos: boolean}} model @param {{renderFrame?: unknown}} props */
const playable = (model, props) =>
  model.videos || typeof props.renderFrame === "function";

/** @param {number} time @param {number} duration */
const clamp = (time, duration) => Math.max(0, Math.min(duration, time));

// The play button wears the symbol role's face and names its action, which its state
// turns, and the element declares it as the study's Play command.
const OfferPlay = Mount.make(
  "OfferPlay",
  { args: { action: Schema.String, label: Schema.String } },
  (/** @type {HTMLButtonElement} */ node, _args, changes) => {
    const host = /** @type {ShadowRoot} */ (node.getRootNode()).host;
    // A row with no run names the press its control makes (dom/keyboard/bindings.js).
    Object.assign(host, {
      lfCommands: {
        title: "In a motion study",
        rows: [
          {
            id: "motion.play",
            title: () => node.getAttribute("aria-label"),
            control: node,
          },
        ],
      },
    });
    return Stream.runForEach(changes, ({ action, label }) =>
      Effect.sync(() => {
        offerActionElement(node, "symbol", "lf-motion-play", label, { action });
        host.dispatchEvent(
          new CustomEvent(COMMANDS, { bubbles: true, composed: true }),
        );
      }),
    ).pipe(Effect.as(Component.noop));
  },
);

// What the slot shows, after each commit: the author's frame at the clock's time, and
// the recordings, which it seeks while the clock stands, plays while it runs and reads
// on every animation frame meanwhile. It reports what it read and what failed.
const DriveStudy = Mount.makeStream(
  "DriveStudy",
  {
    args: {
      time: Schema.Number,
      rate: Schema.Number,
      playing: Schema.Boolean,
      draw: Schema.Any,
    },
  },
  (/** @type {HTMLSlotElement} */ slot, _args, changes) =>
    Stream.callback((queue) =>
      Effect.gen(function* () {
        const send = (/** @type {any} */ message) => Queue.offerUnsafe(queue, message);
        const host = /** @type {ShadowRoot} */ (slot.getRootNode()).host;
        /** @type {() => HTMLVideoElement[]} */
        const videos = () =>
          slot
            .assignedElements({ flatten: true })
            .flatMap((element) =>
              element instanceof HTMLVideoElement
                ? [element]
                : [...element.querySelectorAll("video")],
            )
            .filter((video) => video.closest("lf-motion") === host);
        /** @type {{time: number, rate: number, playing: boolean, draw: unknown} | undefined} */
        let last;
        /** @type {number | null} */
        let frame = null;
        let failed = false;
        /** @type {boolean | undefined} */
        let found;

        const report = () => {
          const any = videos().length > 0;
          if (any !== found) send(MotionMessage.FoundVideos({ any }));
          found = any;
        };
        // Every video is sought once any is off the time: a seek lands on the media's
        // own precision (Chromium truncates to whole microseconds), so a video left
        // unsought could stand a microsecond from the ones moved to the same time.
        const seek = (/** @type {number} */ time) => {
          const seeks = videos().map((video) => ({
            video,
            at: Math.min(time / 1000, video.duration || Infinity),
          }));
          if (seeks.every(({ video, at }) => video.currentTime === at)) return;
          for (const { video, at } of seeks) video.currentTime = at;
        };
        const read = (/** @type {HTMLVideoElement[]} */ list) => ({
          time: Math.max(...list.map((video) => video.currentTime * 1000)),
          ended: list.every((video) => video.ended),
        });
        const stop = () => {
          if (frame !== null) cancelAnimationFrame(frame);
          frame = null;
          for (const video of videos()) video.pause();
        };
        const tick = () => {
          frame = requestAnimationFrame(tick);
          const list = videos();
          if (list.length) send(MotionMessage.ReadVideos(read(list)));
        };
        // The author's frame at `time`; whether it drew.
        const draw = (/** @type {unknown} */ render, /** @type {number} */ time) => {
          if (typeof render !== "function") return true;
          try {
            render(time);
          } catch (error) {
            failed = true;
            reportFailure(host, error);
            send(MotionMessage.FailedDraw({ message: describeFailure(error) }));
            return false;
          }
          if (failed) send(MotionMessage.Drew());
          failed = false;
          return true;
        };
        const play = () => {
          for (const video of videos())
            video.play().catch((/** @type {Error} */ error) => {
              // A pause or seek may interrupt the browser's pending play request.
              if (error.name === "AbortError") return;
              reportFailure(host, new Error(`Playback failed: ${error.message}`));
              send(MotionMessage.FailedPlayback());
            });
          frame = requestAnimationFrame(tick);
        };

        const apply = (
          /** @type {{time: number, rate: number, playing: boolean, draw: unknown}} */ args,
        ) => {
          const before = last;
          last = args;
          const moved = args.time !== before?.time;
          const started = args.playing && !before?.playing;
          for (const video of videos())
            if (video.playbackRate !== args.rate) video.playbackRate = args.rate;
          if (!args.playing && before?.playing) {
            stop();
            // Paused where the recordings stand rather than at the last frame read.
            const list = videos();
            if (!moved && list.length) {
              const { time } = read(list);
              seek(time);
              send(MotionMessage.ReadVideos({ time, ended: false }));
            }
          }
          if (!args.playing && moved) seek(args.time);
          if (started) seek(args.time);
          const drew =
            moved || started || args.draw !== before?.draw
              ? draw(args.draw, args.time)
              : true;
          if (started && drew) play();
        };

        const listen = (
          /** @type {EventTarget} */ target,
          /** @type {string} */ type,
          /** @type {() => void} */ listener,
          /** @type {AddEventListenerOptions} */ options = {},
        ) =>
          Effect.acquireRelease(
            Effect.sync(() => target.addEventListener(type, listener, options)),
            () =>
              Effect.sync(() => target.removeEventListener(type, listener, options)),
          );
        const interrupt = () => {
          if (last?.playing) send(MotionMessage.Interrupted());
        };
        for (const type of INPUTS)
          yield* listen(slot, type, interrupt, { capture: true, passive: true });
        yield* listen(host, "lf-inspect", interrupt);
        yield* listen(slot, "slotchange", report);
        // Media events don't bubble but do pass the slot on capture, so a recording a
        // revision adds joins the clock, and gives Play something to play.
        yield* listen(
          slot,
          "loadedmetadata",
          () => {
            if (last) seek(last.time);
            report();
          },
          { capture: true },
        );
        yield* Effect.addFinalizer(() => Effect.sync(stop));
        report();
        yield* Stream.runForEach(changes, (args) =>
          Effect.sync(() => apply(args)),
        ).pipe(Effect.forkScoped);
      }),
    ),
);

/** The Model `step` leaves, kept in the tab whenever the clock comes to rest.
 * @param {any} $ @param {any} step */
const keep = ($, step) => {
  const next = Component.isStep(step) ? step : $.set(step);
  const { time, rate, playing } = next.model;
  const was = $.model;
  if (playing || (time === was.time && rate === was.rate && !was.playing)) return next;
  return next.run(
    KeepInTab.make({ key: $.props.key, value: JSON.stringify({ time, rate }) }),
  );
};

/** @param {any} $ @param {any} message */
const handle = ($, message) => {
  const { model, props } = $;
  const { duration } = props;
  return MotionMessage.match(message, {
    ClickedPlay: () => {
      if (!playable(model, props)) return model;
      if (model.playing) return $.evolve({ playing: false });
      if (model.reduced) return $.evolve({ time: duration, failure: null });
      return $.evolve({
        playing: true,
        failure: null,
        time: model.time >= duration ? 0 : model.time,
      });
    },
    Sought: ({ time }) =>
      $.evolve({ time: clamp(time, duration), playing: false, failure: null }),
    ChoseRate: ({ rate }) => $.evolve({ rate }),
    Interrupted: () => $.evolve({ playing: false }),
    // The illustrations' clock, while no recording keeps the time.
    TickedFrame: ({ delta }) => {
      if (!model.playing || model.videos) return model;
      const time = Math.min(duration, model.time + delta * model.rate);
      return $.evolve({ time, playing: time < duration });
    },
    ReadVideos: ({ time, ended }) => {
      const at = ended ? duration : Math.min(duration, time);
      return $.evolve({ time: at, playing: model.playing && at < duration });
    },
    FoundVideos: ({ any }) => $.evolve({ videos: any }),
    FailedPlayback: () => $.evolve({ failure: "Failed", playing: false }),
    FailedDraw: ({ message: why }) => $.evolve({ broken: why, playing: false }),
    Drew: () => $.evolve({ broken: null }),
    ChangedMotion: ({ reduced }) =>
      reduced && model.playing
        ? $.evolve({ reduced, time: duration, playing: false })
        : $.evolve({ reduced }),
  });
};

export const Motion = Html.component({
  name: "Motion",
  props: MotionProps,
  model: MotionModel,
  message: MotionMessage,
}).make({
  init: ($) => ({
    time: clamp($.props.saved?.time ?? 0, $.props.duration),
    rate: $.props.saved?.rate ?? 1,
    playing: false,
    reduced: false,
    videos: false,
    failure: null,
    broken: null,
  }),
  update: ($, message) => keep($, handle($, message)),
  view: (h, model) => {
    const { duration, label } = h.props;
    const word = model.playing ? "Pause" : model.reduced ? "Show end" : "Play";
    return h.div
      .class("lf-motion-study")
      .attr("part", "study")
      .children(
        h.div
          .attrs(offerAttributes("div", "lf-motion-controls"))
          .attr("part", "controls")
          .attr("role", "group")
          .attr("aria-label", label)
          .children(
            h.button
              .attr("part", "play")
              .attr("aria-disabled", playable(model, h.props) ? undefined : "true")
              .onMount(
                OfferPlay({ action: model.playing ? "pause" : "play", label: word }),
              )
              .on("click", MotionMessage.ClickedPlay()),
            h.input
              .attrs(offerAttributes("input", "lf-motion-time", { type: "range" }))
              .attr("part", "time")
              .attr("type", "range")
              .attr("name", "time")
              .attr("min", "0")
              .attr("max", String(duration))
              .attr("step", "1")
              .attr("aria-label", "Time")
              .attr("aria-valuetext", `${Math.round(model.time)} milliseconds`)
              .value(String(model.time))
              .on("input", (/** @type {{value: string}} */ { value }) =>
                MotionMessage.Sought({ time: Number(value) }),
              ),
            h.span
              .attrs(offerAttributes("span", "lf-motion-clock"))
              .attr("part", "clock")
              .children(model.failure ?? `${Math.round(model.time)} ms`),
            h.label
              .attrs(offerAttributes("label", "lf-motion-speed"))
              .attr("part", "speed")
              .children(
                "Speed",
                h.select
                  .attrs(offerAttributes("select"))
                  .attr("part", "speed-select")
                  .attr("name", "speed")
                  .value(String(model.rate))
                  .on("change", (/** @type {{value: string}} */ { value }) =>
                    MotionMessage.ChoseRate({ rate: Number(value) }),
                  )
                  .children(
                    ...RATES.map((rate) =>
                      h.option.attr("value", String(rate)).children(`${rate}×`),
                    ),
                  ),
              ),
          ),
        model.broken
          ? h.div
              .class("lf-error")
              .attr("part", "error")
              .children(`<lf-motion> failed: ${model.broken}`)
          : null,
        h.slot.onMount(
          DriveStudy({
            time: model.time,
            rate: model.rate,
            playing: model.playing,
            draw: h.props.renderFrame,
          }),
        ),
      );
  },
  subscriptions: ({ model }) => [
    HtmlSubscription.onMediaQuery(REDUCED_MOTION, (reduced) =>
      MotionMessage.ChangedMotion({ reduced }),
    ),
    model.playing &&
      !model.videos &&
      HtmlSubscription.onAnimationFrame((delta) =>
        MotionMessage.TickedFrame({ delta }),
      ),
    model.playing && HtmlSubscription.onWindow("blur", MotionMessage.Interrupted()),
    model.playing &&
      HtmlSubscription.onVisibility((visible) =>
        visible ? undefined : MotionMessage.Interrupted(),
      ),
  ],
});

defineWidget("lf-motion", Motion, {
  shadow: true,
  statics: { lfPatch: "members" },
  properties: ["renderFrame"],
  members: {
    currentTime: {
      get: (/** @type {{time: number}} */ model) => model.time,
      set: (/** @type {unknown} */ time) => {
        if (typeof time !== "number" || !Number.isFinite(time))
          throw new TypeError("currentTime must be finite milliseconds");
        return MotionMessage.Sought({ time });
      },
    },
  },
  inputs: (element) => {
    const key = `motion:${element.id}`;
    const saved = tabStore.get(key);
    return {
      key,
      duration: Number(element.getAttribute("duration")),
      label: element.getAttribute("aria-label") ?? "",
      saved: saved === null ? null : JSON.parse(saved),
    };
  },
});
