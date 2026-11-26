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
 * choice that lasts until they undo it, an older version, a comparison or hidden
 * annotations, leads the status instead (`lead`). The user asked for this for a walk's
 * position, so the agent's updates show while they read at its stop. Rejected: a walk's
 * position leading the status as a version does, which grows stale as the user reads on
 * from its stop and costs the status the end of its words. A stance such as Draw mode
 * is named in the row's mode chip beside its ✕ (floating-panel.js, `stanceName`), not
 * in these words.
 *
 * What stands before a reading's words (`lead`) is where the user stands ("standing";
 * floating-panel.js, `standing`), or nothing. A notice takes nothing, since news often
 * announces a change to where the user stands ("Annotations hidden"),
 * which would otherwise be said twice; where the user stands comes back with the status
 * a moment later. The Go-to word and a walk's position take all of where the user
 * stands, which a walk over a list one of those facts is about counts on: it says its
 * place alone after them, "5 changes since v2 · 1 of 5" (records/walk-position.js, `walkWords`).
 *
 * While a stance stands the field takes no words (`still`): the user asked that a mode
 * stop writing in the field, and that its Reply… and microphone go, so the row reads the
 * field's words, then Close and esc at its end, then the mode's name and its ✕. Its
 * end offers the stance's Close (`close`) in place of a press that enters the field and
 * of the page's own; a press that acts elsewhere, a notice's after the user's gesture or
 * commenting on selected words in a box of their own, stays. The user chose Close and
 * esc there over Next On Me, since the end shows the key for the press that matters
 * most, and in a stance that is the way out; `m` still walks On Me. A draft the field
 * holds stays in it, unwritable, until the stance ends.
 *
 * The field's end offers one press, the one that matters most at that moment (`end`).
 * Where a reading's words come with a press of their own (`press`), the end offers
 * that one: a notice's, such as a Resolve's Next thread and t, or Show changes and g V v
 * with news of changes (transport/notifications.js, `press`), or an error's, such as Resume
 * writing and g i after a refused send (transport/errors.js). Otherwise it offers, by the
 * reading's `end`:
 * - "key": the key that enters the field, alone after the words, as after an error;
 * - "comment": Comment… and that key, as the field says at rest;
 * - "moment": in a stance its Close; else the page's own press, Open latest on an older
 *   version or Next On Me while On Me lists anything (floating-panel.js, `pagePress`);
 *   else Comment… and its key. In a thread, Reply… and its key, after whose turn it is
 *   or a notice's words;
 * - "none": nothing.
 * While the page holds keys pressed before it was ready, the end offers nothing, since a
 * key there would only join them. The end shows the page's shortcuts, so a press stands
 * there only while one of its keys would make it now, as the dispatcher reads it, and
 * otherwise the end shows nothing: with the caret in a card's reply, `m` types a letter,
 * so Next On Me leaves the end; with a thread opened inside a stance, Escape closes the
 * thread before the stance, so Close leaves it (annotations/composing/input.js, `enters`). A finger,
 * which is shown no keys, is shown no press there: the user judged that a word alone at
 * the end reads as status rather than a control, and the panel's menu and lists reach
 * each press's result, as the ✕ beside a stance's name is Close's (floating-panel.js,
 * `stanceClose`). The user chose this, since the end is there to show shortcuts, over a
 * press standing without its key wherever the caret stood. An open thread's field
 * says its one word at rest, Reply…, at its end, so to a finger it would say nothing.
 * Under a finger the field says at rest the words it says once tapped (`turn`):
 * Reply…, or Reply to reopen… on a resolved thread, as a card's reply box does. The
 * user chose this over a field that showed a finger only a rule above blank space until
 * tapped. It keeps the rule for presses: these words name what a tap anywhere on the
 * field does, and the field's end still offers a finger no press. They chose a notice's press, so a Resolve that moves the
 * panel on says which thread it resolved and offers its next step there, over Undo and
 * ⌘Z after a Resolve. They chose Next On Me at rest while On Me lists anything over
 * Comment and c, since from reading or backing out `m` is the press they most often make
 * next; `c` still enters the field, and Comment and c stand again once nothing waits.
 * Rejected: Next On Me only after an answer, until the user's next input, which left
 * Comment and c at rest the rest of the time and waited on the server's reading of each
 * gesture to offer it.
 *
 * A reading that names what a press on the field does (`offers`), in its words as the
 * selected words do or at its end as a thread's Reply does, keeps the room of that
 * press's key while the key stands elsewhere (floating-panel.css); a thread's in a
 * stance offers the stance's Close at its end, so it names no press.
 * Every reading is said by the agent or by Leaf, each in its face (base/voice.js). The field carries the agent's words, so nothing in it is nobody's: Leaf
 * says a stance's name, where the user stands and the words quoted, since the
 * interface's upright face would read as the agent's (the user's choice). A draft hides
 * whatever the field says, and the live region still hears what passes. */
import { leafSays, wordsText, COMMENT_HINT, REPLY_HINT } from "../base/voice.js";
import { noticeWords } from "../transport/notifications.js";

/** @typedef {import("../base/voice.js").Words} Words
 * @typedef {import("../base/voice.js").Said} Said
 * @typedef {import("../records/composition-input.js").BoxPress} BoxPress
 * @typedef {"key" | "comment" | "moment" | "none"} End
 */

/** What the panel knows of the moment for the field it asks about. A function is read
 * only by the reading that says it, so asking costs only what the field says.
 * @typedef {object} FieldFacts
 * @property {boolean} thread whether the field is an open thread's reply box
 * @property {boolean} keys whether the field is shown keys, which a finger is not
 * (dom/keyboard/bindings.js, `advertisesKeys`)
 * @property {boolean} writing whether the user writes in the field: focus in it, or a
 * dictation running there (annotations/composing/input.js, `writesIn`)
 * @property {{message: string, press: BoxPress | null} | null} error the newest error
 * the field can say, with the press that recovers from it
 * @property {string | null} held keys pressed before the page was ready, which wait
 * @property {string | null} selected the words selected on the page, as quoted
 * @property {{message: Words, press: BoxPress | null, news: boolean} | null} notice a
 * notice while it shows, and whether it is news, which answers no gesture of the user's
 * @property {string | null} goTo the Go-to filter's word while its sequence waits
 * @property {string | null} step a walk's position for its step's moment, in the words
 * the field's own leave unsaid
 * @property {boolean} still whether a stance stands, so the field takes no words
 * @property {() => readonly (string | Said)[]} standing where the user stands on the
 * page, each part ending in its separator; nothing in a thread
 * @property {() => Words} destination where words typed in the field go
 * @property {() => Words} status the status's words
 * @property {() => BoxPress | null} close the stance's Close
 * @property {() => BoxPress | null} pagePress the page's own press
 */

/** @typedef {"standing" | null} Lead
 * @typedef {{says: string, field?: "page" | "thread", claims: (f: FieldFacts) => Words | null,
 * lead?: Lead | ((f: FieldFacts) => Lead), press?: (f: FieldFacts) => BoxPress | null,
 * end: End, offers?: boolean}} FieldReading */

/** The readings in the order they claim the field; each names how long it stands.
 * @type {readonly FieldReading[]} */
export const FIELD_READINGS = Object.freeze([
  // An error about no particular box, until the user's first edit (transport/errors.js,
  // `sayable`), in its status's place and the danger's ink: it says why something the
  // user did, or the page, went wrong. One about the field's editor covers the words, as
  // at any box (annotations/composing/input.js). The user chose this over errors riding the
  // passing notice, which would fade after four seconds and go unsaid while the user
  // writes. A notice offering a press after the user's own gesture, rather than news
  // (transport/notifications.js, `showNotice`), is newer, so while it stands with the caret
  // elsewhere the error waits in the menu's Errors, as one the field has passed does,
  // and the field says it again once the notice has gone or the caret comes back, since
  // the field says nothing that passes under the caret.
  {
    says: "error",
    claims: (f) =>
      f.error && !(f.notice?.press && !f.notice.news && !f.writing)
        ? leafSays(f.error.message)
        : null,
    press: (f) => f.error?.press ?? null,
    end: "key",
  },
  // Keys pressed while the page loads, which wait for it, until it is ready
  // (floating-panel.js, `heldWords`). The user chose this over a notice of their own
  // beside the panel. An error, which says why the page may not get ready, comes
  // first; the mode chip says the keys where it or a draft takes the field's words.
  { says: "held", claims: (f) => (f.held ? leafSays(f.held) : null), end: "none" },
  // While the user writes in the field, the word every comment box says there
  // (floating-panel.js, `whereTo`). Nothing that passes is said over it, and the field
  // says what still stands once they stop.
  {
    says: "destination",
    claims: (f) => (f.writing && !f.still ? f.destination() : null),
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
  // What passes in the panel's one seat for passing words (`passingWords`), a notice
  // alone and the Go-to word or a walk's position after where the user stands (`lead`,
  // above).
  {
    says: "notice",
    claims: (f) => {
      const passing = passingWords(f);
      return passing ? noticeWords(passing) : null;
    },
    lead: (f) => (f.notice ? null : "standing"),
    press: (f) => f.notice?.press ?? null,
    end: "moment",
  },
  // An open thread's reply box, while the thread stands open, says whose turn it is and
  // a walk's position beside the leaf (floating-panel.js, `turnLead`), since the field
  // there says no status they would hide, and its end says Reply with the key that
  // enters it, as the page's field says Comment (`end`), so the word goes with its key
  // where `c` writes elsewhere, as when a walk goes on to a stop on the page and the
  // thread's view stays open. The user chose this so the next action reads apart from
  // the agent's words,
  // over the key beside Reply with the turn at the field's end in one face, Reply alone
  // with the turn left to the thread's messages, and the agent's words in a lane of
  // their own before the seat. Reply takes the one dim face the user chose for every
  // comment box's word. To a finger, which is shown no keys and so no Reply at the end,
  // the field says Reply as its own words instead (the header). While a stance stands
  // the box takes no reply, so it says nothing and its end offers the stance's Close
  // (`still`).
  {
    says: "turn",
    field: "thread",
    claims: (f) => (f.keys || f.still ? [] : f.destination()),
    end: "moment",
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
 * `peekPresentation`): a notice for its moment, and past it until the user's next input
 * where it stays (transport/notifications.js, `showNotice`); else the Go-to filter's word while its sequence
 * waits for a key; else on the page a walk's position for a notice's moment from each
 * step (transport/notifications.js, `answerStep`). In a thread the position stands before Reply
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
 * (`lead`), what its end offers (`end`: a press, the word its key enters with, the key
 * alone as "", or null), and whether its words or the word at its end name what a
 * press on the field does (`offers`).
 * @param {FieldFacts} f */
export function readField(f) {
  const field = f.thread ? "thread" : "page";
  for (const reading of FIELD_READINGS) {
    if (reading.field && reading.field !== field) continue;
    const said = reading.claims(f);
    if (said === null) continue;
    const leads = typeof reading.lead === "function" ? reading.lead(f) : reading.lead;
    const lead = leads === "standing" ? f.standing() : [];
    const words = [...lead, ...[said].flat()];
    const end = endOf(reading, f, words);
    return {
      says: reading.says,
      words,
      lead,
      end,
      offers:
        Boolean(reading.offers) &&
        (words.length > 0 || (typeof end === "string" && end !== "")),
    };
  }
  throw new Error("No reading claimed the field");
}

/** While the page holds keys, every reading's end offers nothing (`held`), and while a
 * stance stands, its Close in place of what enters the field or the page's own press
 * (`still`).
 * @param {FieldReading} reading @param {FieldFacts} f
 * @param {readonly (string | Said)[]} words @returns {BoxPress | string | null} */
function endOf(reading, f, words) {
  const kind = reading.end;
  if (kind === "none" || f.held) return null;
  const own = reading.press?.(f);
  if (own) return own;
  if (kind === "comment") return COMMENT_HINT;
  if (f.still) return f.close();
  if (kind === "key") return "";
  if (f.thread) return REPLY_HINT;
  return f.pagePress() ?? (wordsText(words) ? COMMENT_HINT : "");
}
