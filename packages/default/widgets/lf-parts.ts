/* lf-parts: a page's parts, each with a Layout of its own, one on screen at a time. The
 * tab set's module draws and runs them (lf-tabs.ts, `Tabs`), which says how they differ
 * from a tab set. */
import { defineWidget } from "/runtime/effect-widget.js";
import { Tabs, tabSetOptions } from "./lf-tabs.js";

defineWidget("lf-parts", Tabs, tabSetOptions);
