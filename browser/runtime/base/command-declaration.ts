/* What a scope of keys and each of its commands declare, as a module hands them to
   the keyboard (dom/keyboard/bindings.js's header says what each field does): a
   command's fields, a scope's, the options and rows an element declares as its
   `lfCommands`, and the capability a declared scope gives. A module below the keyboard,
   such as the contribution normalizer, is handed these, so they stand here. The
   keyboard's own `Command` and `Scope` extend them with the routes a command offers and
   the scope it opens, which name the keyboard's register.
*/
import type { PageControlGroup } from "./page-controls.js";
import type { ACTIONS } from "../lib/icon-paths.js";

export type Cell<T> = T | (() => T);
type CommandFields = {
  id: string;
  title: Cell<string>;
  keys?: Cell<readonly string[]>;
  contextKeys?: Cell<readonly string[]>;
  description?: Cell<string | null | undefined>;
  reach?: Cell<string>;
  label?: Cell<string | null>;
  control?: Cell<Element | null> | undefined;
  bindingBadge?: Cell<Element | null> | undefined;
  ready?: (() => boolean) | undefined;
  when?: (() => boolean) | undefined;
  at?: () => boolean;
  keep?: () => unknown;
  lands?: (from: Element | null) => HTMLElement | SVGElement | null | undefined;
  touch?: Cell<string> | false;
  touchValue?: Cell<string>;
  decision?: boolean;
  commits?: boolean;
  recommended?: boolean;
  travels?: boolean;
  native?: boolean;
  waits?: Cell<boolean>;
  repeat?: boolean;
  exit?: boolean;
  retainCurrentLocation?: boolean;
  sequenceSteps?: Cell<readonly string[]>;
  completeSequenceSteps?: Cell<readonly string[]>;
  intrinsicBindings?: readonly string[];
  runFromCommandReference?: boolean;
  sequenceControl?: boolean;
  commandReferenceWhen?: () => boolean;
  menu?: PageControlGroup;
  action?: keyof typeof ACTIONS;
};
export type DeclaredCommand = CommandFields &
  (
    | { run?: (() => unknown) | undefined; runKey?: never }
    | { run?: never; runKey: (binding: string) => unknown }
  );
export type DeclaredScope = {
  title?: string | null | undefined;
  reach?: Cell<string>;
  rows: readonly DeclaredCommand[];
  when?: (() => boolean) | undefined;
  ready?: (() => boolean) | undefined;
  root?: Cell<Element | Document | null>;
  shadow?: (binding: string) => boolean;
  sequence?: Cell<readonly string[]>;
  contextual?: boolean;
  identity?: object;
  el?: Element;
  says?: Cell<string>;
  at?: () => boolean;
  claims?: ((binding: string) => boolean) | null | undefined;
  escape?: "inner" | "outer" | undefined;
  liveInCommandReference?: boolean | undefined;
  validated?: boolean;
};
export type ScopeOptions = {
  when?: () => boolean;
  ready?: () => boolean;
  escape?: "inner";
  claims?: (binding: string) => boolean;
};
export type ScopeDeclaration = ScopeOptions & {
  title: string | null;
  rows: readonly DeclaredCommand[];
};
export type ScopeCapability = { scope: DeclaredScope };
export {};
