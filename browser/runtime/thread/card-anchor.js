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
   Above its subject, reading keeps the foot. Writing keeps the top. Beside its
   subject, a card being written in also rises (`rises`): it may outgrow the room
   below its top, and the window's foot lifts it, as a chat's composer grows, so the
   line being typed and the turn it answers stay in view (the user's decision,
   2026-10-21). Its top stays where it stood, so a shorter draft brings it back
   down. Rejected: holding the foot once a landing met the window's foot, which kept
   a shrinking draft's card lifted, detached from where it stood. Below the subject
   it grows down to keep that subject clear. Adoption keeps the editor's attachment
   ahead of any conversation hold.
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
  // The box keeps the caret through a send (replies.js), but the empty box the user
  // sent from is no draft being written until they type in it, or leave it and come
  // back, so news, the answer they wait for first, shows as it does to a reader.
  // Typing ends that for good: words erased again leave a box still being written in.
  #sentFrom = false;

  /** @param {HTMLElement} surface */
  constructor(surface) {
    this.#surface = surface;
  }

  // Called by the reply action before its optimistic publication changes any boxes.
  /** @param {string} attempt */
  sending(attempt) {
    this.#sent = attempt;
    this.#sentFrom = true;
  }

  // Entering or editing the native reply starts a new writing place, even while
  // an earlier send remains in flight. Its later receipt cannot borrow it again, and
  // the box is no longer the empty one the send left.
  writing() {
    this.#sent = null;
    this.#sentFrom = false;
  }

  // The user left the reply, so coming back into it is writing again.
  leftReply() {
    this.#sentFrom = false;
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
        (!this.#sentFrom && currentLocationIn(field.closest(".lf-thread-reply")))),
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
    const ordinary = this.#sent || (!writing && seat.side === "top") ? "foot" : "top";
    const beside = seat.side === "left" || seat.side === "right";
    return {
      edge: seat.adopted ? attachment : (press?.edge ?? ordinary),
      rises: !seat.adopted && !press?.edge && writing && !this.#sent && beside,
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
    this.#sentFrom = false;
  }
}
