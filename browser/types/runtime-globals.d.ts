// What Leaf's classic scripts hang on the page's globals for its modules to read.
// `prepaint.js` and `bootstrap.js` run before any module, so they cannot export
// what they build; they set it on `<html>` and `window` instead, and every module
// reads it there. These declarations are its one statement of shape, and the
// assignments in those scripts are checked against them.
//
// DOM's types give `document.documentElement` as `HTMLElement`, so the root's
// properties are declared on every HTML element; only the root carries them, and
// each is optional for any other.

/** Attributes and custom properties an element wears as one set (`dress.js`). */
interface LeafDress {
  attributes: Record<string, string | null>;
  properties: Record<string, string>;
}

/** A tab or user store that never throws on an unavailable backing (`storage.js`). */
interface LeafStore {
  read(key: string): { available: boolean; value: string | null };
  get(key: string): string | null;
  set(key: string, value: string | null): boolean;
  where(key: string): { store: string; key: string };
  keys(): string[];
}

/** Whether a margin element layout or breakout reading changed what it writes (`prepaint.js`). */
interface LeafReading {
  changed: boolean;
}

/** The closed set of control roles, each with one face (`prepaint.js`, `ACTION_FACES`). */
type LeafActionRole = "symbol" | "word" | "commit" | "mark" | "inline" | "row";

/** A package's retained template and optional rendering root. Node references and
 * mechanical inputs remain package-owned; the same render is used after upgrade. */
interface LeafInitialView {
  root?: HTMLElement | ShadowRoot;
  render(...args: any[]): unknown;
  [key: string]: any;
}

/** A package's synchronous initial view factory (`initial/<tag>.js`). */
type LeafInitialRenderer = (
  host: HTMLElement,
  tools: {
    tabStore: LeafStore;
    offer: LeafInitial["offer"];
    selectableOffer: LeafInitial["selectableOffer"];
    selectableOfferElement: LeafInitial["selectableOfferElement"];
    offerElement: LeafInitial["offerElement"];
    offerAction: LeafInitial["offerAction"];
    offerActionElement: LeafInitial["offerActionElement"];
    generatedElement: LeafInitial["generatedElement"];
    keeps: LeafInitial["keepsAttribute"];
    /** Moves every child of the host into `node`, the box that holds its authored body. */
    authoredBody<T extends Element>(node: T): T;
  },
) => LeafInitialView | null;

/** The prepaint's initial drawing and root-state registries (`prepaint.js`). */
interface LeafInitial {
  /** The single Lit namespace initialized by the classic delivery, before modules. */
  lit?: typeof import("lit") & Record<string, any>;
  /** Initial insertion, replaced by dom-move.js before live module rendering. */
  move(parent: Node, node: Node, before: Node | null): Node;
  fragmentId(fragment: string): string;
  externalLinks: {
    attributes: string[];
    matches(link: Element): boolean;
    arrive(link: Element): void;
    leave(link: Element): void;
  };
  keepsAttribute(node: Element, name: string, value: unknown): void;
  setRuntimeRootAttribute(node: Element, name: string, value: unknown): void;
  runtimeRootAttributes(node: Element): Set<string>;
  setRuntimeRootStyle(
    node: ElementCSSInlineStyle,
    property: string,
    value: string,
    priority?: string,
  ): void;
  removeRuntimeRootStyle(node: ElementCSSInlineStyle, property: string): void;
  wear(node: Element, dress: LeafDress): void;
  runtimeRootStyles(node: Element): Set<string>;
  authoredShell(node: Node): Node;
  marginContentLayout(): LeafReading;
  breakouts(): LeafReading;
  layoutBox(): Element | null;
  skipped(element: Element, parent?: (node: Element) => Element | null): boolean;
  register(tag: string, render: LeafInitialRenderer): void;
  has(tag: string): boolean;
  paint(host: HTMLElement): LeafInitialView | null;
  mount(template: HTMLTemplateElement): void;
  restoreSource<T extends ParentNode>(root: T): T;
  authoredCopy<T extends Node>(node: T, target?: Document | null): T;
  reading<T extends Node>(node: T): T;
  offer<K extends string>(
    tag: K,
    cls?: string,
    label?: string,
    inputType?: string,
    pressable?: boolean,
  ): K extends keyof HTMLElementTagNameMap ? HTMLElementTagNameMap[K] : HTMLElement;
  selectableOffer(
    role: string,
    cls?: string,
    label?: string,
    face?: LeafActionRole,
  ): HTMLSpanElement;
  selectableOfferElement(
    node: Element,
    role: string,
    cls?: string,
    face?: LeafActionRole,
  ): void;
  offerElement<T extends Element>(node: T, cls?: string, pressable?: boolean): T;
  offerAction(
    role: LeafActionRole,
    cls?: string,
    label?: string,
    options?: { title?: string },
  ): HTMLButtonElement;
  offerActionElement<T extends Element>(
    node: T,
    role: LeafActionRole,
    cls?: string,
    label?: string,
    options?: { title?: string },
  ): T;
  generatedElement<T extends Element>(node: T, options: { says: boolean | "echo" }): T;
  origin(node: Node): Node | undefined;
  parent(node: Node): Element | null;
  /** The box a producer built to hold the host's authored children, if it built one. */
  authoredBody(host: Element): Element | null;
}

/** A sample child's channel to the page that embeds it (`bootstrap.js`). */
interface LeafSampleBridge {
  ready: Promise<void>;
  readonly settings: any;
  send(value: unknown): void;
  receive(callback: (data: any) => void): void;
  present(): void;
  /** Set once the bootstrap has built what a connected sample wears. */
  install?(): void;
}

interface HTMLElement {
  /** Runs a fault report while this document is the one the browser keeps (prepaint.js). */
  lfDocumentLifetime?: { whenActive(fault: string, report: () => void): void };
  /** Text-entry vocabulary, input count and observation from the first script. */
  lfInputs?: {
    readonly textField: "leaf-text";
    readonly textBox: string;
    typesText(node: any): boolean;
    takesLetters(node: any): boolean;
    readonly count: number;
    observe(read: (event: Event) => void): () => boolean;
  };
  /** The exception behind the first startup fault, kept before modules load. */
  lfStartupException?: { name: string; message: string; stack?: string } | null;
  lfStorage?: {
    stored(nativeOpen: () => Storage, name: string, prefix?: string): LeafStore;
    tabStore: LeafStore;
    userStore: LeafStore;
  };
  lfKeyboard?: { readonly quick: boolean; setQuick(on: boolean): void };
  /** Whether a link's target leaves the page, and the mark that says so (prepaint.js). */
  lfExternalLink?: {
    opensElsewhere(href: string | null): boolean;
    mark(): SVGSVGElement;
  };
  /** The floating panel's resting size. */
  lfChrome?: {
    /** `row` or `mark`. */
    readonly rest: string;
    setRest(value: string): void;
  };
  lfInitial?: LeafInitial;
  /** Which member a one-at-a-time holder opens on, and the record of each shown. */
  lfViews?: {
    opening(holder: Element, members: Element[]): Element;
    keep(holder: Element, member: Element): void;
  };
  lfSample?: LeafSampleBridge;
}

interface HTMLElement {
  /** A thread seat's box: the row of its first message (`thread/box.js`). */
  lfFirstMessage?: HTMLElement;
}

interface Element {
  /** The keys a widget binds while the user is in this element, as data Leaf reads when
   * the widget says they changed (`commandsChanged`; keyboard/scopes.js): a scope's
   * title, rows and options, or a `commandScope()` value. */
  lfCommands?:
    | {
        title: string | null;
        rows: any[];
        when?: () => boolean;
        ready?: () => boolean;
        escape?: "inner";
        claims?: (binding: string) => boolean;
      }
    | ReturnType<typeof import("../runtime/keyboard/scopes.js").commandScope>
    | null;
  /** The text a block marked `data-lf-copy` copies (`code-copy.js`). */
  lfCopy?: () => string;
}

interface HTMLScriptElement {
  /** A sample child's private port, owned by the bootstrap element until the entry starts. */
  lfDocumentPort?: MessagePort;
  // The entry's scene readings, for render checks (`leaf.js`, `validationEntry`).
  lfReadiness?: typeof import("../runtime/presentation.js").pageReadiness;
  lfRenderingState?: typeof import("../runtime/rendering.js").renderingState;
  lfObserveQueuedWork?: typeof import("../runtime/queued-work.js").observeQueuedWork;
  lfObserveWidgetPreparations?: typeof import("../runtime/rendering.js").observePreparations;
  lfNativeLayers?: typeof import("../runtime/keyboard/layer-stack.js").nativeLayers;
  lfFloatingSelections?: typeof import("../runtime/annotation-overlay/floating.js").floatingSelections;
}

interface Window {
  /** The sample bridge, kept across a sample child's document swaps. */
  lfSampleBridge?: LeafSampleBridge;
}

/** The runtime's own elements, by tag, as each module defines it. */
interface HTMLElementTagNameMap {
  "leaf-floating-panel": import("../runtime/floating-panel.js").FloatingPanelElement;
  "leaf-composition-field": import("../runtime/composing/input.js").CompositionFieldElement;
  "leaf-text": import("../runtime/composing/text-field.js").LeafTextElement;
  "leaf-margin-cluster": import("../runtime/annotation-overlay/margin-cluster-view.js").MarginClusterViewElement;
}

// The events Leaf dispatches with a detail, by where they are heard.

interface WindowEventMap {
  /** A page or module could not start (`prepaint.js`, `fault`). */
  "lf-startup-failed": CustomEvent<{
    reason?: string;
    error?: unknown;
    page?: boolean;
  }>;
  /** A widget's words for a listener, which Leaf says in its live region
   * (`widget-upgrade.js`, `announce`). */
  "lf-announce": CustomEvent<string>;
  /** The prepaint's first startup fault, said once (`bootstrap.js`, `recover`). */
  "lf-startup-fault": CustomEvent<{
    reason: string;
    incomplete: boolean;
    page: boolean;
  }>;
}

interface DocumentEventMap {
  /** A command ran, with the words it was invoked under (`keyboard/dispatch.js`). */
  "lf-command-invoked": CustomEvent<{
    id: string;
    binding: unknown;
    title: string;
    description: string;
    travels: boolean;
  }>;
  /** The reading column's box, once the margin has laid out against it. */
  "lf-margin-layout": CustomEvent<{ column: DOMRect; height: number }>;
  /** The keyboard owner's call for the keys the bootstrap held while the page loaded;
   * the bootstrap answers in the detail, where it held any (`bootstrap.js`). */
  "lf-held-keys": CustomEvent<{
    ready(event: KeyboardEvent): boolean;
    keep(): boolean;
    keys?: KeyboardEvent[];
    pause?(): void;
    release?(): void;
  }>;
  /** A sample child's request to scroll the page along from its frame (`sample.js`). */
  "lf-sample-step": CustomEvent<{ amount: number; unit: string }>;
  /** Drawing a widget has under way, by the community protocol (`widget-upgrade.js`). */
  "pending-task": import("../runtime/widget-upgrade.js").PendingTaskEvent;
}

// TypeScript's DOM library lacks the platform's close watcher (HTML, "Close requests
// and close watchers"), which `keyboard/close-requests.js` holds; only what it uses.
interface CloseWatcher extends EventTarget {
  destroy(): void;
}
declare var CloseWatcher: { prototype: CloseWatcher; new (): CloseWatcher };
