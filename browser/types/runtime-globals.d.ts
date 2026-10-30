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

/** Whether a margin element layout or breakout reading changed what it writes (`content-layout.js`). */
interface LeafReading {
  changed: boolean;
}

/** The closed set of control roles, each with one face (`control-faces.js`, `ACTION_FACES`). */
type LeafActionRole = "symbol" | "word" | "commit" | "mark";

/** Root-state writers required by bootstrap before runtime modules load. */
interface LeafRootState {
  keeps(node: Element, name: string, value: unknown): void;
  setRuntimeRootAttribute(node: Element, name: string, value: unknown): void;
  setRuntimeRootStyle(
    node: ElementCSSInlineStyle,
    property: string,
    value: string,
    priority?: string,
  ): void;
  removeRuntimeRootStyle(node: ElementCSSInlineStyle, property: string): void;
  wear(node: Element, dress: LeafDress): void;
  attributes(node: Element): Set<string>;
  styles(node: Element): Set<string>;
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
  lfViews?: {
    members(holder: Element): HTMLElement[];
    opening(holder: Element, fallback?: HTMLElement | null): HTMLElement | null;
    keep(
      holder: Element,
      member: HTMLElement | null,
      leaving?: HTMLElement | null,
    ): void;
  };
  lfLinks?: {
    opensElsewhere(href: string | null): boolean;
    markExternalLink(link: Element): void;
  };
  lfStorage?: {
    initialDisclosureOpen(node: Element): boolean | undefined;
    stored(nativeOpen: () => Storage, name: string, prefix?: string): LeafStore;
    tabStore: LeafStore;
    userStore: LeafStore;
    keepDisclosures(root: Document | ShadowRoot): void;
  };
  lfKeyboard?: { readonly quick: boolean; setQuick(on: boolean): void };
  /** The floating panel's resting size. */
  lfChrome?: {
    /** `row` or `mark`. */
    readonly rest: string;
    setRest(value: string): void;
  };
  lfRootState?: LeafRootState;
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
