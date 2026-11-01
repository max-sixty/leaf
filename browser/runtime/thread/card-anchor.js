// @ts-check
/* The place a floating conversation keeps while its contents change.

   Reading follows the attachment; writing uses the room beside that attachment.
   Send keeps the reply's foot through its own result and receipt. The next arriving
   words restore ordinary reading, including more words in the same stream; writing
   also ends that hold. The empty box a send leaves the caret in (replies.js) is no
   writing until the user types there or comes back to it, so the answer they wait for
   shows as it did when Send left them on the thread; once they have, it is writing
   until the next send, empty or not. A press instead keeps the control it
   acted on through that change's fitting, until another input or unrelated change.
   These lifetimes belong to the conversation, not the physical placement solver.
   Above its subject, a card keeps its foot, read or written in, so a growing draft
   rises over the transcript, as the comment box grows over its subject, and leaves the
   words the thread is about in view (the user's decision, 2026-10-31). Rejected:
   keeping a written card's top there, which grew the draft down over its subject and
   needed a send's foot held through the next draft to keep the reply from moving
   down; and holding the transcript at its height while the reply is written in, which
   kept that reply still but stopped news shown into a card beside its subject from
   growing it. Beside its subject, a card also rises as it grows (`rises`), read or
   written in: it may outgrow the room below its top, and the window's foot lifts
   it, as a chat's composer grows, so the line being typed, or the answer arriving,
   stays in view with the turn it answers (the user's decisions, 2026-10-21 for writing
   and 2026-10-31 for reading). Its top stays where it stood, so a shorter thread
   brings it back down. A press and a send's hold still keep their edge. Rejected:
   holding the foot once a landing met the window's foot, which kept a shrinking
   draft's card lifted, detached from where it stood; and keeping a read card's top as
   an answer arrived, which scrolled its transcript once it met the window's foot and
   hid the question above the answer. Below the subject it grows down to keep that
   subject clear.
   Adoption keeps the editor's attachment ahead of any conversation hold.
   A preparation advances the press only when its placement lands and cannot
   overwrite a newer press captured during fitting. */
import { TEXT_FIELD } from "../control-selectors.js";
import { currentLocationIn, inputCount } from "../focus.js";

/** @typedef {"top" | "foot"} Edge */
/** @typedef {{side: "top" | "bottom" | "left" | "right",
 * adopted: boolean, fresh: boolean}} Seat */
/** @typedef {{input: number, path: {node: Element, offset: number}[],
 * extent: number, edge: Edge | null}} Press */

export class CardAnchor {
  /** @type {HTMLElement} */
  #surface;
  /** @type {string | null} */
  #sent = null;
  /** @type {Press | null} */
  #press = null;
  /** @type {Seat["side"] | null} */
  #side = null;
  // The box keeps the caret through a send (replies.js), until the user leaves it.
  // The empty box the user sent from is no draft being written until they type in it
  // ("untyped"), so news, the answer they wait for first, shows as it does to a
  // reader. Typing ends that for good ("typed"): words erased again leave a box still
  // being written in.
  /** @type {"untyped" | "typed" | null} */
  #sentFrom = null;

  /** @param {HTMLElement} surface */
  constructor(surface) {
    this.#surface = surface;
  }

  // Called by the reply action before its optimistic publication changes any boxes.
  /** @param {string} attempt */
  sending(attempt) {
    this.#sent = attempt;
    this.#sentFrom = "untyped";
  }

  // Entering or editing the native reply starts a new writing place, even while
  // an earlier send remains in flight. Its later receipt cannot borrow it again, and
  // the box is no longer the empty one the send left.
  writing() {
    this.#sent = null;
    if (this.#sentFrom) this.#sentFrom = "typed";
  }

  // The user left the reply, so coming back into it is writing again.
  leftReply() {
    this.#sentFrom = null;
  }

  // Own words may reveal held news with them: that whole presentation is the send's
  // result. Later arriving words release its foot; receipt alone adds no words.
  // Both news admission and actual presentation read the same canonical change.
  /** @param {Set<string> | undefined} joined */
  #keepsSend(joined) {
    return this.#sent !== null && (!joined?.size || joined.has(this.#sent));
  }

  /** @param {Set<string> | undefined} joined */
  presented(joined) {
    if (!this.#keepsSend(joined)) this.#sent = null;
  }

  /** @param {Event} event @param {number} input */
  pressed(event, input) {
    if (!["pointerdown", "touchstart", "keydown"].includes(event.type)) return;
    const path = event.composedPath();
    if (!path.includes(this.#surface)) return;
    const top = this.#surface.getBoundingClientRect().top;
    this.#press = {
      input,
      path: path
        .filter(
          (node) =>
            node instanceof Element &&
            node !== this.#surface &&
            this.#surface.contains(node),
        )
        .map((node) => ({
          node: /** @type {Element} */ (node),
          offset: /** @type {Element} */ (node).getBoundingClientRect().top - top,
        })),
      extent: this.#extent(),
      edge: null,
    };
  }

  #field() {
    return /** @type {(HTMLElement & {value: string}) | null} */ (
      this.#surface.querySelector(`.lf-thread-reply ${TEXT_FIELD}`)
    );
  }

  #writing() {
    const field = this.#field();
    return Boolean(
      field?.checkVisibility() &&
      (field.value !== "" ||
        (this.#sentFrom !== "untyped" &&
          currentLocationIn(field.closest(".lf-thread-reply")))),
    );
  }

  // A press measures its own before/after, not an unrelated earlier landing.
  #extent() {
    const transcript = this.#surface.querySelector(".lf-thread-transcript");
    return transcript
      ? parseFloat(getComputedStyle(transcript).height) +
          transcript.scrollHeight -
          transcript.clientHeight
      : 0;
  }

  /** @param {Seat} seat */
  prepare(seat) {
    if (seat.fresh) this.forget();
    this.#side = seat.side;
    // Refused or mirrored words arrive without a native edit. Read after the send's
    // synchronous mask, so its old words cannot release the place it just claimed.
    if (this.#field()?.value) this.writing();
    const writing = this.#writing();
    const captured = this.#press;
    let press = captured?.input === inputCount() ? captured : null;
    if (press) {
      const extent = this.#extent();
      if (Math.abs(extent - press.extent) > 0.5) {
        const reference = press.path.find(({ node }) => node.checkVisibility());
        if (press.edge) press = null;
        else if (reference) {
          const offset =
            reference.node.getBoundingClientRect().top -
            this.#surface.getBoundingClientRect().top;
          press = {
            ...press,
            edge:
              seat.side === "top" || Math.abs(offset - reference.offset) > 0.5
                ? "foot"
                : "top",
            extent,
          };
        }
      }
    }
    /** @type {Edge} */
    const attachment = seat.side === "top" ? "foot" : "top";
    /** @type {Edge} */
    const ordinary = this.#sent || seat.side === "top" ? "foot" : "top";
    const beside = seat.side === "left" || seat.side === "right";
    return {
      writing,
      edge: seat.adopted ? attachment : (press?.edge ?? ordinary),
      rises: !seat.adopted && !press?.edge && !this.#sent && beside,
      commit: () => {
        if (this.#press === captured) this.#press = press;
      },
    };
  }

  // Asking is read-only: held news has not advanced the displayed conversation.
  /** @param {Set<string> | undefined} joined */
  newsMoves(joined) {
    return this.#writing() || this.#side === "top" || this.#keepsSend(joined);
  }

  forget() {
    this.#sent = null;
    this.#press = null;
    this.#side = null;
    this.#sentFrom = null;
  }
}
