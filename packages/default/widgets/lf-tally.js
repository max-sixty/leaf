/* lf-tally: how many of a region's obligations are still open, whose turn each is, and the
 * way to the next one waiting on the user.
 *
 * The region is the element `for` names, and which obligations it holds is
 * `readObligations(region)`, the rule a side list's rows read too, so the total
 * counts the obligations whose marks the queue shows. An obligation stays open until the
 * page adopts the reading that admits its answer, never on a guess. The count splits the
 * open ones by the server's next actor, in the words `tally` and `tallyWords`
 * (runtime/lib/obligation-tally.js) give, which say why they split as they do. Until
 * the page's first reading is in, the tally says nothing rather than a count of an
 * inventory it has not seen.
 *
 * With `next`, a Next On Me control steps to the next obligation waiting on the user inside
 * the region (`NextOnMe`, widget-services.js), from where the user is, so a press keeps
 * them there rather than taking focus onto the control, as the On
 * panel's Next On Me does. It is a native button: Tab and Enter reach it, and a
 * finger taps it. Pressed by keyboard, focus is on the control outside the region, so
 * the walk counts from the obligation the user last went to there, else the first in sight,
 * else the region's start (panel/queue-walk.js says how). With none waiting it is disabled.
 *
 * An Effect UI component (runtime/effect-widget.js) draws the server's reading from props, in
 * the same nodes each time. Its room holds the widest words, both sides two digits
 * wide and the agent called "the agent", so the words change without moving the control
 * beside them or what follows. A longer count or agent name widens the room once. */
import { Html, Schema, UiSchema } from "/vendor/effect-ui.js";
import { agentName, elementById, readObligations } from "/runtime/widget-api.js";
import { NextOnMe } from "/runtime/widget-services.js";
import { pressAttributes } from "/runtime/lib/controls.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";
import { tally, tallyWords } from "/runtime/lib/obligation-tally.js";

const TallyProps = Schema.Struct({
  ...widgetProps,
  region: Schema.optional(Schema.Unknown),
  next: Schema.Boolean,
  ready: Schema.Boolean,
  done: Schema.Boolean,
  generic: Schema.String,
  named: Schema.String,
  words: Schema.String,
  onUser: Schema.Number,
});
const TallyMessage = UiSchema.TaggedEnum({ ClickedNext: {} });

/** @param {any} builder @param {Record<string, string>} attributes */
const withAttributes = (builder, attributes) =>
  Object.entries(attributes).reduce((b, [name, value]) => b.attr(name, value), builder);

export const Tally = Html.component({
  name: "Tally",
  props: TallyProps,
  model: Schema.Struct({}),
  message: TallyMessage,
}).make({
  init: () => ({}),
  update: {
    ClickedNext: ($) =>
      $.props.region ? $.run(NextOnMe.make({ within: $.props.region })) : $.model,
  },
  view: (h) => {
    const { ready, done, generic, named, words, next, onUser } = h.props;
    return h.span
      .class("lf-tally-face")
      .attr("data-lf-gen", "1")
      .attr("data-lf-ready", ready ? "" : undefined)
      .children(
        h.span
          .class("lf-tally-count lf-chip")
          .attr("data-lf-tone", done ? "ok" : undefined)
          .children(
            h.span.class("lf-tally-room").attr("aria-hidden", "true").children(generic),
            h.span.class("lf-tally-room").attr("aria-hidden", "true").children(named),
            h.span.class("lf-tally-words").children(words),
          ),
        next
          ? withAttributes(h.button, pressAttributes("word", "lf-tally-next"))
              .attr("disabled", !ready || !onUser ? "" : undefined)
              .on("mousedown", () => undefined, { preventDefault: "always" })
              .on("click", TallyMessage.ClickedNext())
              .children("Next On Me")
          : null,
      );
  },
});

defineWidget("lf-tally", Tally, {
  shadow: true,
  inputs: (element) => {
    const region = elementById(element.getAttribute("for"), element) ?? undefined;
    // The page's reading is read with no region yet too, so the reading that brings
    // the region draws the tally again.
    const ready = readObligations().phase === "ready" && Boolean(region);
    const held = ready && region ? readObligations(region).all : [];
    const count = tally(held);
    // The drawing's two rooms hold the widest words, one calling the agent "the
    // agent" and one by its name; a longer count widens them once.
    const digits = "0".repeat(Math.max(2, String(held.length).length));
    const widest = { onUser: digits, onAgent: digits, open: digits, total: digits };
    return {
      region,
      next: element.hasAttribute("next"),
      ready,
      done: Boolean(held.length && !count.open),
      generic: tallyWords(widest, "the agent"),
      named: tallyWords(widest, agentName()),
      words: ready ? tallyWords(count, agentName()) : "",
      onUser: count.onUser,
    };
  },
});
