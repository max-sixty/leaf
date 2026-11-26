/* What an element declares its preview adds, as its `lfPreview(route)`, which
   annotations/preview.js reads and draws (its header says what each field shows). Any
   module may declare one, so the declaration's shape stands here, below them all. */

/** @import { Box } from "./box.js" */
/** @typedef {string | Node | import("/vendor/lit.js").TemplateResult} Word
 * @typedef {Word | readonly Word[]} Words
 * @typedef {readonly (readonly string[])[]} Presses
 * @typedef {Words | null | undefined | false} Line
 * @typedef {{items: readonly Words[], more: (count: number) => Words}} List
 * @typedef {{name?: Words | null, keys?: Presses, detail?: readonly Line[], list?: List | null, at?: Element | Box | null, about?: Element | null, excerpt?: boolean, unseen?: boolean}} Preview
 * @typedef {Preview | null | undefined | false} Declared
 * @typedef {"pointer" | "focus" | "hold"} Route
 * @typedef {(route: Route) => Declared} Read
 */
export {};
