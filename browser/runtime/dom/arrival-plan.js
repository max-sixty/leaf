/* What a route hands anchor travel to put the user somewhere (features/anchor-travel.js,
   `arrive`). An arrival names where the user lands, the focus, caret and selection they
   get there, and how each scroller moves to show it; a navigation step is the history
   entry a route takes once it lands. Routes below anchor travel build them too
   (records/thread/destination.js, records/obligations/view.js), so they are named here,
   beneath both. */

/** @import { UserIntent } from "./user-intent.js" */
/** @typedef {Element | Range} Destination
 * @typedef {{at: Destination, align?: Destination, block?: ScrollLogicalPosition | "fragment", behavior?: ScrollBehavior, when?: () => boolean}} ScrollPlacement
 * @typedef {{where: Destination, focus?: import("./focus.js").FocusDestination | null | false, caret?: import("../base/held-place.js").Caret | null,
 * selection?: {range: Range, backward: boolean} | null, reveal?: readonly Element[], scroll: readonly ScrollPlacement[]}} Arrival
 * @typedef {{plan: (where: Destination | null | undefined, options?: {there?: (readable: (where: Destination) => boolean) => boolean}) => boolean, commit: () => void}} NavigationStep
 * @typedef {{intent: UserIntent, present?: (() => unknown) | null, departure?: NavigationStep | null}} ArrivalOptions
 * @typedef {(resolve: () => Arrival | null | undefined, options: ArrivalOptions) => Promise<boolean>} Arrive
 */
export {};
