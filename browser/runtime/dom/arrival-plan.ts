/* What a route hands anchor travel to put the user somewhere (features/anchor-travel.js,
   `arrive`). An arrival names where the user lands, the focus, caret and selection they
   get there, and how each scroller moves to show it; a navigation step is the history
   entry a route takes once it lands. Routes below anchor travel build them too
   (records/thread/destination.js, records/obligations/view.js), so they are named here,
   beneath both. */

import type { UserIntent } from "./user-intent.js";
import type { FocusDestination } from "./focus.js";
import type { Caret } from "../base/held-place.js";
export type Destination = Element | Range;
export type ScrollPlacement = {
  at: Destination;
  align?: Destination;
  block?: ScrollLogicalPosition | "fragment";
  behavior?: ScrollBehavior;
  when?: () => boolean;
};
export type Arrival = {
  where: Destination;
  focus?: FocusDestination | null | false;
  caret?: Caret | null;
  selection?: { range: Range; backward: boolean } | null;
  reveal?: readonly Element[];
  scroll: readonly ScrollPlacement[];
};
export type NavigationStep = {
  plan: (
    where: Destination | null | undefined,
    options?: { there?: (readable: (where: Destination) => boolean) => boolean },
  ) => boolean;
  commit: () => void;
};
export type ArrivalOptions = {
  intent: UserIntent;
  present?: (() => unknown) | null;
  departure?: NavigationStep | null;
};
export type Arrive = (
  resolve: () => Arrival | null | undefined,
  options: ArrivalOptions,
) => Promise<boolean>;
export {};
