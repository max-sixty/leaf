/* What an element declares its preview adds, as its `lfPreview(route)`, which
   annotations/preview.js reads and draws (its header says what each field shows). Any
   module may declare one, so the declaration's shape stands here, below them all. */

import type { Box } from "./box.js";
import type { TemplateResult } from "/vendor/lit.js";
export type Word = string | Node | TemplateResult;
export type Words = Word | readonly Word[];
export type Presses = readonly (readonly string[])[];
export type Line = Words | null | undefined | false;
export type List = { items: readonly Words[]; more: (count: number) => Words };
export type Preview = {
  name?: Words | null;
  keys?: Presses;
  detail?: readonly Line[];
  list?: List | null;
  at?: Element | Box | null;
  about?: Element | null;
  excerpt?: boolean;
  unseen?: boolean;
};
export type Declared = Preview | null | undefined | false;
export type Route = "pointer" | "focus" | "hold";
export type Read = (route: Route) => Declared;
export {};
