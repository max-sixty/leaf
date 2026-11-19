/* What the floating panel's comment field says while it is empty, and what its end
 * offers: one reading at a time, the first in `FIELD_READINGS` that claims the field.
 * This is the rule's one home. The panel reads the moment's facts for the field it asks
 * about, the page's or an open thread's reply box (floating-panel.js, `fieldReading`),
 * and the guide's "What the panel's line says" (docs/using.html) lists the page field's
 * readings in this order, which tests/runtime/field-readings.test.mjs holds it to.
 *
 * The agent's status is the page field's own words. Something of the user's takes their
 * place only while it answers or directs what the user is doing now, for as long as its
 * owner says it stands, which each reading's comment names. Where the user stands by a
 * choice that lasts until they undo it, a stance such as Draw mode, an older version, a
 * comparison or hidden annotations, leads the status instead (`lead`). The user asked
 * for this for a walk's position, so the agent's updates show while they read at its
 * stop, and chose that a stance follow the same rule. Rejected: a walk's position leading the
 * status as a version does, which grows stale as the user reads on from its stop and
 * costs the status the end of its words.
 *
 * What stands before a reading's words (`lead`) is where the user stands ("standing";
 * floating-panel.js, `standing`), or the stance alone ("stance"), or nothing. Words that
 * pass take the stance alone: the field's end may offer the stance's Close, which the
 * words should name, and the rest of where the user stands comes back with the status a
 * moment later, where a notice announcing it ("Annotations hidden — o shows them") would
 * otherwise say it twice.
 *
 * The field's end offers one press, the one that matters most at that moment (`end`):
 * - "key": the key that enters the field, after the words, as Reply's c;
 * - "comment": Comment… and that key, as the field says at rest;
 * - "moment": a notice's own press after the user's gesture, such as a Resolve's Next
 *   thread and t (notifications.js, `press`); else on the page the stance's Close, in
 *   place of the seat's ✕; else the page's own press, Open latest on an older version
 *   or Next On Me while On Me lists anything (floating-panel.js, `pagePress`); else
 *   Comment… and its key. In a thread, Reply… and its key, as the field says at rest,
 *   so the key never stands alone after the notice's words;
 * - "none": nothing.
 * While the page holds keys pressed before it was ready, the end offers nothing, since a
 * key there would only join them. A press acts as a touch control does, wherever the
 * caret stands, and says its key only while that key would make it now: `m` typed in a
 * card's reply is a letter, and Escape closes a comment box standing in Design mode
 * before the mode. The user chose a notice's press, so a Resolve that moves the panel on
 * says which thread it resolved and offers its next step there, over Undo and ⌘Z after a
 * Resolve, and the ✕ with Escape unsaid in a stance. They chose Next On Me at rest while
 * On Me lists anything over Comment and c, since from reading or backing out `m` is the
 * press they most often make next; `c` still enters the field, and Comment and c stand
 * again once nothing waits. Rejected: Next On Me only after an answer, until the user's
 * next input, which left Comment and c at rest the rest of the time and waited on the
 * server's reading of each gesture to offer it.
 *
 * A reading whose words name what a press on the field does (`offers`), the reply or
 * the selected words, reads in full ink with its key, and every other reads dim
 * (floating-panel.css). Every reading is said by the agent or by Leaf, each in its face
 * (voice.js). The field carries the agent's words, so nothing in it is nobody's: Leaf
 * says a stance's name, where the user stands and the words quoted, since the
 * interface's upright face would read as the agent's (the user's choice). A draft hides
 * whatever the field says, and the live region still hears what passes. */
import { leafSays, wordsText } from "./voice.js";
import { noticeWords } from "./notifications.js";
import { COMMENT_HINT, REPLY_HINT } from "./words.js";

/** @typedef {import("./voice.js").Words} Words
 * @typedef {import("./voice.js").Said} Said
 * @typedef {import("./composing/input.js").BoxPress} BoxPress
 * @typedef {"key" | "comment" | "moment" | "none"} End
 */

/** What the panel knows of the moment for the field it asks about. A function is read
 * only by the reading that says it, so asking costs only what the field says.
 * @typedef {object} FieldFacts
 * @property {boolean} thread whether the field is an open thread's reply box
 * @property {boolean} writing whether the caret is in the field
 * @property {{message: string} | null} error the newest error the field can say
 * @property {string | null} held keys pressed before the page was ready, which wait
 * @property {string | null} selected the words selected on the page, as quoted
 * @property {{message: Words, press: BoxPress | null} | null} notice a notice while it
 * shows
 * @property {string | null} goTo the Go-to filter's word while its sequence waits
 * @property {string | null} step a walk's position for its step's moment
 * @property {string | null} stance the stance the user is in, by name, on the page
 * @property {() => readonly (string | Said)[]} standing where the user stands, each part
 * ending in its separator
 * @property {() => Words} destination where words typed in the field go
 * @property {() => Words} status the status's words
 * @property {() => BoxPress | null} close the stance's Close
 * @property {() => BoxPress | null} pagePress the page's own press
 */

/** @typedef {{says: string, field?: "page" | "thread", claims: (f: FieldFacts) => Words | null,
 * lead?: "standing" | "stance", end: End, offers?: boolean}} FieldReading */

/** The readings in the order they claim the field; each names how long it stands.
 * @type {readonly FieldReading[]} */
export const FIELD_READINGS = Object.freeze([
  // An error about no particular box, until the user's first edit (errors.js,
  // `sayable`), in its status's place and the danger's ink: it says why something the
  // user did, or the page, went wrong. One about the field's editor covers the words, as
  // at any box (composing/input.js). The user chose this over errors riding the
  // passing notice, which would fade after four seconds and go unsaid while the user
  // writes. A notice offering a press after the user's own gesture is newer, so while
  // it passes with the caret elsewhere the error waits in the menu's Errors, as one the
  // field has passed does, and the field says it again once the notice has gone or the
  // caret comes back, since the field says nothing that passes under the caret.
  {
    says: "error",
    claims: (f) =>
      f.error && !(f.notice?.press && !f.writing) ? leafSays(f.error.message) : null,
    end: "key",
  },
  // Keys pressed while the page loads, which wait for it, until it is ready
  // (floating-panel.js, `heldWords`). The user chose this over a notice of their own
  // beside the panel. An error, which says why the page may not get ready, comes
  // first; the mode chip says the keys where it or a draft takes the field's words.
  { says: "held", claims: (f) => (f.held ? leafSays(f.held) : null), end: "none" },
  // While the caret is in the field, the word every comment box says there
  // (floating-panel.js, `whereTo`). Nothing that passes is said over it, and the field
  // says what still stands once the caret leaves.
  {
    says: "destination",
    claims: (f) => (f.writing ? f.destination() : null),
    end: "key",
  },
  // Words selected on the page, while they stand, inside a stance too, after the Go-to
  // word or a walk's position where one passes. A press on the field comments on them
  // (floating-panel.js, `selectedWords`), the one route a finger has to them; the user
  // chose that over a worded step standing in the marks' place, which took a stance's
  // steps away while it stood, accepting that a press on the field addresses selected
  // words whenever they stand. Its end says Comment… and c, as at rest, which the user
  // chose over c alone after the quote. Under a draft the mode chip names them.
  {
    says: "selection",
    field: "page",
    claims: (f) =>
      f.selected === null
        ? null
        : leafSays([navigation(f), `“${f.selected}”`].filter(Boolean).join(" · ")),
    lead: "standing",
    end: "comment",
    offers: true,
  },
  // What passes in the panel's one seat for passing words (`passingWords`).
  {
    says: "notice",
    claims: (f) => {
      const passing = passingWords(f);
      return passing ? noticeWords(passing) : null;
    },
    lead: "stance",
    end: "moment",
  },
  // An open thread's reply box says Reply with the key that enters it, while the
  // thread stands open, with whose turn it is and a walk's position beside the leaf
  // (floating-panel.js, `turnLead`), since the field there says no status they would
  // hide. The user chose this so the next action reads apart from the agent's words,
  // over the key beside Reply with the turn at the field's end in one face, Reply alone
  // with the turn left to the thread's messages, and the agent's words in a lane of
  // their own before the seat. Reply takes the one dim face the user chose for every
  // comment box's word.
  {
    says: "turn",
    field: "thread",
    claims: () => leafSays(REPLY_HINT),
    end: "key",
    offers: true,
  },
  // The agent's status, always, in the status's words (page-status.js). One that
  // reports reads dimmer than anything written, with the one sheen that marks work under
  // way while the agent works; one that asks the user to act reads in its tone's ink,
  // and where the user stands keeps the quiet face before it (floating-panel.css).
  {
    says: "status",
    field: "page",
    claims: (f) => f.status(),
    lead: "standing",
    end: "moment",
  },
]);

/** What passes in the panel's one seat for words that pass, which the field says
 * (`notice`) and the folded leaf's peek, where no field shows (floating-panel.js,
 * `peekPresentation`): a notice for its moment, or until the user's next input where it
 * offers a press (notifications.js); else the Go-to filter's word while its sequence
 * waits for a key; else on the page a walk's position for a notice's moment from each
 * step (notifications.js, `answerStep`). In a thread the position stands before Reply
 * instead (floating-panel.js, `turnLead`): the user asked for that, since "Thread 11 of
 * 11" in Reply's place leaves nothing saying how to reply to the thread they are
 * reading.
 * @param {Pick<FieldFacts, "thread" | "goTo" | "step"> & {notice: {message: Words} | null}} f
 * @returns {Words | null} */
export const passingWords = (f) => f.notice?.message ?? navigation(f);

/** The Go-to word or a walk's position, which selected words say before their quote.
 * @param {Pick<FieldFacts, "thread" | "goTo" | "step">} f */
const navigation = (f) => f.goTo ?? (f.thread ? null : f.step);

/** What the field says: which reading (`says`), its words with what leads them
 * (`lead`), and what its end offers (`end`: a press, the word its key enters with, the
 * key alone as "", or null), whether that is the stance's Close (`exits`), and whether
 * the words name what a press on the field does (`offers`).
 * @param {FieldFacts} f */
export function readField(f) {
  const field = f.thread ? "thread" : "page";
  for (const reading of FIELD_READINGS) {
    if (reading.field && reading.field !== field) continue;
    const said = reading.claims(f);
    if (said === null) continue;
    const lead =
      reading.lead === "standing"
        ? f.standing()
        : reading.lead === "stance" && f.stance
          ? [leafSays(`${f.stance} · `)]
          : [];
    const words = [...lead, ...[said].flat()];
    const { end, exits } = endOf(reading.end, f, words);
    return {
      says: reading.says,
      words,
      lead,
      end,
      exits,
      offers: Boolean(reading.offers),
    };
  }
  throw new Error("No reading claimed the field");
}

/** @type {{end: null, exits: false}} */
const NOTHING = { end: null, exits: false };

/** While the page holds keys, every reading's end offers nothing (`held`).
 * @param {End} kind @param {FieldFacts} f @param {readonly (string | Said)[]} words
 * @returns {{end: BoxPress | string | null, exits: boolean}} */
function endOf(kind, f, words) {
  if (kind === "none" || f.held) return NOTHING;
  if (kind === "key") return { end: "", exits: false };
  if (kind === "comment") return { end: COMMENT_HINT, exits: false };
  if (f.notice?.press) return { end: f.notice.press, exits: false };
  if (f.thread) return { end: wordsText(words) ? REPLY_HINT : "", exits: false };
  const close = f.close();
  if (close) return { end: close, exits: true };
  return { end: f.pagePress() ?? (wordsText(words) ? COMMENT_HINT : ""), exits: false };
}
