/* What a view that draws its own text field asks of the composition input it wires
   (annotations/composing/input.js, `wireInput`): the options it passes and the seam the
   wiring hands back. A thread's reply box and a message's rewrite wire their own fields
   from below the composer, so the contract is named here. */

/** @import { Cell } from "../base/command-declaration.js" */
/** @import { Command } from "../dom/keyboard/bindings.js" */
/** @import { DraftDrawing } from "../../types/domain.js" */
/** The text field the wiring takes, a `leaf-text` (annotations/composing/text-field.js),
 * by what the wiring reads of it and does to it.
 * @typedef {HTMLElement & {value: string, placeholder: string, readOnly: boolean, edit: (text: string) => void,
 * record: (undo: () => void, redo: () => void) => void, restartHistory: () => void}} InputField
 * @typedef {(text: string, raw: string, stillCurrent: () => boolean, typed: string, alternate: boolean) => unknown} Sender
 * @typedef {{word: string, keys: readonly string[], run: () => unknown}} BoxPress
 * @typedef {Object} InputOptions
 * @property {Cell<string>} hint
 * @property {(() => unknown) | null} [hintParts]
 * @property {() => unknown} [hintLead]
 * @property {() => string | BoxPress | null} [enters]
 * @property {Cell<string> | null} [accessibleName]
 * @property {() => boolean} [closed]
 * @property {() => boolean} [cornerAtRest]
 * @property {(value: string) => unknown} save
 * @property {Sender} send
 * @property {string} [sendClass]
 * @property {Cell<string>} sends
 * @property {Cell<string>} [action]
 * @property {Cell<string | null>} [altLabel]
 * @property {() => true | string} [allowsMedia]
 * @property {() => boolean} [busy]
 * @property {(raw: string) => boolean} [hasContent]
 * @property {{read: () => DraftDrawing | null, target: () => Element | null, replace: (drawing: DraftDrawing | null) => unknown, undoStroke: () => unknown, remove: () => unknown} | null} [drawing]
 * @property {readonly Command[]} [rows]
 * @property {HTMLElement | null} [submitIn]
 * @property {boolean} [sentMedia]
 * @typedef {{(): void, cancelDictation: () => void, value: () => string, closed: () => boolean, hasMedia: () => boolean,
 * arrive: () => void, load: (value: string) => void, button: HTMLButtonElement | null,
 * composition: () => {field: HTMLElement, frame: HTMLElement}, addMedia: (images: readonly Blob[]) => Promise<boolean>,
 * writing: () => boolean, covered: () => HTMLElement | null}} InputSync
 * @typedef {(field: InputField, options: InputOptions) => InputSync} WireInput
 */
export {};
