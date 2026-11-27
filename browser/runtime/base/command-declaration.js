/* What a scope of keys and each of its commands declare, as a module hands them to
   the keyboard (dom/keyboard/bindings.js's header says what each field does): a
   command's fields, a scope's, the options and rows an element declares as its
   `lfCommands`, and the capability a declared scope gives. A module below the keyboard,
   such as the contribution normalizer, is handed these, so they stand here. The
   keyboard's own `Command` and `Scope` extend them with the routes a command offers and
   the scope it opens, which name the keyboard's register.
*/

/** @template T @typedef {T | (() => T)} Cell */
/**
 * @typedef {Object} CommandFields
 * @property {string} id
 * @property {Cell<string>} title
 * @property {Cell<readonly string[]>} [keys]
 * @property {Cell<readonly string[]>} [contextKeys]
 * @property {Cell<string | null | undefined>} [description]
 * @property {Cell<string>} [reach]
 * @property {Cell<string | null>} [label]
 * @property {Cell<Element | null> | undefined} [control]
 * @property {Cell<Element | null> | undefined} [bindingBadge]
 * @property {(() => boolean) | undefined} [ready]
 * @property {(() => boolean) | undefined} [when]
 * @property {() => boolean} [at]
 * @property {() => unknown} [keep]
 * @property {(from: Element | null) => HTMLElement | SVGElement | null | undefined} [lands]
 * @property {Cell<string> | false} [touch]
 * @property {Cell<string>} [touchValue]
 * @property {boolean} [decision]
 * @property {boolean} [commits]
 * @property {boolean} [recommended]
 * @property {boolean} [travels]
 * @property {boolean} [native]
 * @property {Cell<boolean>} [waits]
 * @property {boolean} [repeat]
 * @property {boolean} [exit]
 * @property {boolean} [retainCurrentLocation]
 * @property {Cell<readonly string[]>} [sequenceSteps]
 * @property {Cell<readonly string[]>} [completeSequenceSteps]
 * @property {readonly string[]} [intrinsicBindings]
 * @property {boolean} [runFromCommandReference]
 * @property {boolean} [sequenceControl]
 * @property {() => boolean} [commandReferenceWhen]
 * @property {import("./page-controls.js").PageControlGroup} [menu]
 * @property {keyof typeof import("../lib/icon-paths.js").ACTIONS} [action]
 * @typedef {CommandFields & ({run?: (() => unknown) | undefined, runKey?: never} | {run?: never, runKey: (binding: string) => unknown})} DeclaredCommand
 * @typedef {Object} DeclaredScope
 * @property {string | null | undefined} [title]
 * @property {Cell<string>} [reach]
 * @property {readonly DeclaredCommand[]} rows
 * @property {(() => boolean) | undefined} [when]
 * @property {(() => boolean) | undefined} [ready]
 * @property {Cell<Element | Document | null>} [root]
 * @property {(binding: string) => boolean} [shadow]
 * @property {Cell<readonly string[]>} [sequence]
 * @property {boolean} [contextual]
 * @property {object} [identity]
 * @property {Element} [el]
 * @property {Cell<string>} [says]
 * @property {() => boolean} [at]
 * @property {((binding: string) => boolean) | null | undefined} [claims]
 * @property {"inner" | "outer" | undefined} [escape]
 * @property {boolean | undefined} [liveInCommandReference]
 * @property {boolean} [validated]
 * @typedef {{when?: () => boolean, ready?: () => boolean, escape?: "inner", claims?: (binding: string) => boolean}} ScopeOptions
 * @typedef {ScopeOptions & {title: string | null, rows: readonly DeclaredCommand[]}} ScopeDeclaration
 * @typedef {{scope: DeclaredScope}} ScopeCapability
 */
export {};
