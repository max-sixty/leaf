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

/** Whether a residency or indent reading changed what it writes (`prepaint.js`). */
interface LeafIndents {
  changed: boolean;
}

/** A package's synchronous initial drawing of one host (`initial.js`). */
type LeafInitialRenderer = (
  host: HTMLElement,
  tools: {
    tabStore: LeafStore;
    offer: LeafInitial["offer"];
    offerElement: LeafInitial["offerElement"];
    keeps: LeafInitial["keepsAttribute"];
  },
) => unknown;

/** The prepaint's initial drawing and root-state registries (`prepaint.js`). */
interface LeafInitial {
  fragmentId(fragment: string): string;
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
  residency(): LeafIndents;
  indents(): LeafIndents;
  skipped(element: Element, parent?: (node: Element) => Element | null): boolean;
  register(tag: string, render: LeafInitialRenderer): void;
  has(tag: string): boolean;
  paint(host: HTMLElement): unknown;
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
  offerElement<T extends Element>(node: T, cls?: string, pressable?: boolean): T;
  origin(node: Node): Node | undefined;
  parent(node: Node): Element | null;
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
  /** Whether this document is still the one the browser shows. */
  lfDocumentLifetime?: { readonly active: boolean };
  /** User inputs since the first script, and a subscription to the next. */
  lfInputs?: { readonly count: number; observe(read: (event: Event) => void): () => boolean };
  /** The exception behind the first startup fault, kept before modules load. */
  lfStartupException?: { name: string; message: string; stack?: string } | null;
  lfStorage?: {
    stored(nativeOpen: () => Storage, name: string, prefix?: string): LeafStore;
    tabStore: LeafStore;
    userStore: LeafStore;
  };
  lfKeyboard?: { readonly quick: boolean; setQuick(on: boolean): void };
  /** Which chrome the user reads the page with, and the panel's resting size. */
  lfChrome?: {
    /** `classic` or `floating`. */
    readonly mode: string;
    /** `row` or `mark`. */
    readonly rest: string;
    adopt(mode: string): void;
    set(name: "mode" | "rest", value: string): void;
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

interface HTMLScriptElement {
  /** A sample child's private port, owned by the bootstrap element until the entry starts. */
  lfDocumentPort?: MessagePort;
  // The entry's scene readings, for render checks (`leaf.js`, `validationEntry`).
  lfReadiness?: typeof import("../../skills/leaf/assets/runtime/presentation.js").pageReadiness;
  lfRenderingState?: typeof import("../../skills/leaf/assets/runtime/rendering.js").renderingState;
  lfObserveQueuedWork?: typeof import("../../skills/leaf/assets/runtime/queued-work.js").observeQueuedWork;
  lfObserveWidgetPreparations?: typeof import("../../skills/leaf/assets/runtime/rendering.js").observePreparations;
  lfNativeLayers?: typeof import("../../skills/leaf/assets/runtime/keyboard/layer-stack.js").nativeLayers;
  lfFloatingSelections?: typeof import("../../skills/leaf/assets/runtime/annotation-overlay/floating.js").floatingSelections;
}

interface Window {
  /** The sample bridge, kept across a sample child's document swaps. */
  lfSampleBridge?: LeafSampleBridge;
}

/** The runtime's own elements, by tag, as each module defines it. */
interface HTMLElementTagNameMap {
  "lf-queue-list": import("../../skills/leaf/assets/runtime/queue-list.js").QueueListElement;
  "leaf-banner-status": import("../../skills/leaf/assets/runtime/banner-status-view.js").BannerStatusViewElement;
  "lf-leaves-list": import("../../skills/leaf/assets/runtime/live-leaves-list.js").LiveLeavesListElement;
  "lf-leaves-banner-face": import("../../skills/leaf/assets/runtime/live-leaves-list.js").LeavesBannerFaceElement;
  "lf-ask-banner-face": import("../../skills/leaf/assets/runtime/asks/banner-controls.js").AskBannerFaceElement;
  "leaf-attached-media-shelf": import("../../skills/leaf/assets/runtime/composing/input.js").AttachedMediaShelfElement;
  "leaf-text": import("../../skills/leaf/assets/runtime/composing/text-field.js").LeafTextElement;
  "leaf-thread-narrowing": import("../../skills/leaf/assets/runtime/thread/narrowing-view.js").ThreadNarrowingViewElement;
  "leaf-thread-list": import("../../skills/leaf/assets/runtime/thread/thread-list-view.js").ThreadListViewElement;
  "leaf-margin-cluster": import("../../skills/leaf/assets/runtime/annotation-overlay/margin-cluster-view.js").MarginClusterViewElement;
}

// The events Leaf dispatches with a detail, by where they are heard.

interface WindowEventMap {
  /** A page or module could not start (`prepaint.js`, `fault`). */
  "lf-startup-failed": CustomEvent<{ reason?: string; error?: unknown; page?: boolean }>;
  /** The prepaint's first startup fault, said once (`bootstrap.js`, `recover`). */
  "lf-startup-fault": CustomEvent<{ reason: string; incomplete: boolean; page: boolean }>;
}

interface DocumentEventMap {
  /** A command ran, with the words it was invoked under (`keyboard/dispatch.js`). */
  "lf-command-invoked": CustomEvent<{
    id: string;
    binding: unknown;
    title: string;
    description: string;
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
}

interface HTMLElementEventMap {
  /** An ancestor is asked to show `target` (`widget-elements.js`, `reveal`). */
  "lf-reveal": CustomEvent<{
    target: Element;
    mayReveal(): boolean;
    replacedView(): void;
    present(ready?: Promise<unknown>): void;
  }>;
}
