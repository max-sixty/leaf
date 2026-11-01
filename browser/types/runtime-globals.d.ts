// What Leaf's classic scripts hang on the page's globals for its modules to read.
// `prepaint.js` and `bootstrap.js` run before any module, so they cannot export
// what they build. Required document-runtime capabilities belong to `window`;
// optional element metadata belongs to the root element. Every module reads them there. These declarations are its one statement of shape, and the
// assignments in those scripts are checked against them.
//
// Leaf's prepaint installs each required Window capability before module loading.
// Element metadata remains optional because ordinary elements do not carry it.

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
type LeafActionRole = "symbol" | "word" | "commit" | "mark" | "inline" | "row";

/** Root-state writers required by bootstrap before runtime modules load. */
interface LeafRootState {
  keeps(node: Element | null | undefined, name: string, value: unknown): void;
  setRuntimeRootAttribute(node: Element, name: string, value: unknown): void;
  setRuntimeRootStyle(
    node: ElementCSSInlineStyle,
    property: string,
    value: string,
    priority?: string,
  ): void;
  removeRuntimeRootStyle(node: ElementCSSInlineStyle, property: string): void;
  wear(node: HTMLElement, dress: LeafDress): void;
  attributes(node: Element): Set<string>;
  styles(node: ElementCSSInlineStyle): Set<string>;
}

/** A sample child's channel to the page that embeds it (`bootstrap.js`). */
interface LeafSampleBridge {
  ready: Promise<void>;
  readonly settings: import("../runtime/sample-protocol.js").SampleSettings;
  send(value: import("../runtime/sample-protocol.js").ChildMessage): void;
  receive(
    callback: (data: import("../runtime/sample-protocol.js").ParentMessage) => void,
  ): void;
  present(): void;
  /** Set once the bootstrap has built what a connected sample wears. */
  install(): void;
}

interface Window {
  /** Runs a fault report while this document is the one the browser keeps (prepaint.js). */
  lfDocumentLifetime: { whenActive(fault: string, report: () => void): void };
  /** Text-entry vocabulary, input count and observation from the first script. */
  lfInputs: {
    readonly textField: "leaf-text";
    readonly textBox: string;
    typesText(node: EventTarget | null | undefined): boolean;
    takesLetters(node: EventTarget | null | undefined): boolean;
    readonly count: number;
    observe(read: (event: Event) => void): () => boolean;
  };
  lfViews: {
    members(holder: Element, selector?: string): Element[];
    opening(
      holder: Element,
      fallback?: Element | null,
      selector?: string,
    ): Element | null | undefined;
    keep(holder: Element, member: Element | null, leaving?: Element | null): void;
  };
  lfLinks: {
    opensElsewhere(href: string | null): boolean;
    markExternalLink(link: Element): void;
  };
  /** Native working state shared by prepaint and the runtime. */
  lfStorage: {
    initialDisclosureOpen(node: Element): boolean | undefined;
    stored(nativeOpen: () => Storage, name: string, prefix?: string): LeafStore;
    tabStore: LeafStore;
    userStore: LeafStore;
    keepDisclosure(node: HTMLDetailsElement): void;
    finishEarlyContent(): void;
  };
  lfKeyboard: { readonly quick: boolean; setQuick(on: boolean): void };
  /** The floating panel's resting size. */
  lfChrome: {
    /** `row` or `mark`. */
    readonly rest: string;
    setRest(value: string): void;
  };
  lfRootState: LeafRootState;
}

interface HTMLElement {
  /** The exception behind the first startup fault, kept before modules load. */
  lfStartupException?: { name: string; message: string; stack?: string } | null;
  lfSample?: LeafSampleBridge;
}

interface HTMLElement {
  /** A thread seat's box: the row of its first message (`thread/box.js`). */
  lfFirstMessage?: HTMLElement;
}

interface Element {
  readonly updateComplete?: Promise<unknown>;
  cloneNode(deep?: boolean): Element;
  /** Package-owned address resolution for generated content (anchor-resolution.js). */
  lfDataDatum?(key: string, options?: { outdated?: boolean }): Element | null;
  lfDatumLabel?(key: string): string | null;
  lfElementsFor?(key: string): Iterable<Element> | null;
  lfRevealDatum?(key: string): void | null | Promise<unknown>;
  /** The keys a widget binds while the user is in this element, as data Leaf reads when
   * the widget says they changed (`commandsChanged`; keyboard/scopes.js): a scope's
   * title, rows and options, or a `commandScope()` value. */
  lfCommands?:
    | (import("../runtime/keyboard/scopes.js").ScopeOptions & {
        title: string | null;
        rows: readonly import("../runtime/keyboard/bindings.js").Command[];
      })
    | import("../runtime/keyboard/scopes.js").CommandCapability
    | null
    | undefined;
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
  lfMove?: typeof import("../runtime/dom-move.js").move;

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
  "lf-held-keys": CustomEvent<
    {
      ready(event: KeyboardEvent): boolean;
      keep(): boolean;
    } & (
      | { keys?: never; pause?: never; release?: never }
      | { keys: KeyboardEvent[]; pause(): void; release(): void }
    )
  >;
  /** A sample child's request to scroll the page along from its frame (`sample.js`). */
  "lf-sample-step": CustomEvent<
    Extract<
      import("../runtime/sample-protocol.js").ChildStatus,
      { type: "step" }
    >["detail"]
  >;
  /** Drawing a widget has under way, by the community protocol (`widget-upgrade.js`). */
  "pending-task": import("../runtime/widget-upgrade.js").PendingTaskEvent;
}

// TypeScript's DOM library lacks the platform's close watcher (HTML, "Close requests
// and close watchers"), which `keyboard/close-requests.js` holds; only what it uses.
interface CloseWatcher extends EventTarget {
  destroy(): void;
}
declare var CloseWatcher: { prototype: CloseWatcher; new (): CloseWatcher };

interface Window {
  SpeechRecognition?: new () => import("../runtime/composing/dictation.js").Recognition;
  webkitSpeechRecognition?: new () => import("../runtime/composing/dictation.js").Recognition;
}

interface CustomElementConstructor {
  answerWords?: (value: unknown, element: Element) => unknown;
}

interface ShadowRootEventMap {
  focus: FocusEvent;
  blur: FocusEvent;
  focusin: FocusEvent;
  focusout: FocusEvent;
  beforetoggle: ToggleEvent;
  toggle: ToggleEvent;
}
interface ShadowRoot {
  addEventListener<K extends keyof ShadowRootEventMap>(
    type: K,
    listener: (this: ShadowRoot, event: ShadowRootEventMap[K]) => unknown,
    options?: boolean | AddEventListenerOptions,
  ): void;
  addEventListener(
    type: string,
    listener: EventListenerOrEventListenerObject | null,
    options?: boolean | AddEventListenerOptions,
  ): void;
  removeEventListener<K extends keyof ShadowRootEventMap>(
    type: K,
    listener: (this: ShadowRoot, event: ShadowRootEventMap[K]) => unknown,
    options?: boolean | EventListenerOptions,
  ): void;
  removeEventListener(
    type: string,
    listener: EventListenerOrEventListenerObject | null,
    options?: boolean | EventListenerOptions,
  ): void;
}

interface Element {
  /** Package-provided words when the registry declares x-word: module. */
  lfWord?(): string;
  lfSays?(): string;
}

interface HTMLElement {
  cloneNode(deep?: boolean): HTMLElement;
}

interface HTMLElement {
  /** The browser's EditContext used by CodeMirror when that native API is present. */
  editContext?: EventTarget | null;
}

interface ShadowRoot {
  /** Chromium's shadow selection API; Firefox and WebKit use the document's. */
  getSelection?(): Selection | null;
}

interface DocumentEventMap {
  "lf-layout": CustomEvent<null> & { readonly target: Element };
}

interface DocumentEventMap {
  "lf-drafts": CustomEvent<import("../runtime/drafts.js").DraftNews>;
}

// Cloning an SVG node preserves its native element namespace, not custom state.
interface SVGElement {
  cloneNode(deep?: boolean): SVGElement;
}

interface Element {
  /** A package's declared thread surface, read after its upgrade. */
  threadOutlets?(
    ...args: Parameters<import("../runtime/thread/surfaces.js").ThreadOutletSelector>
  ): ReturnType<import("../runtime/thread/surfaces.js").ThreadOutletSelector>;
}

interface Element {
  getRootNode(options?: GetRootNodeOptions): Document | DocumentFragment | Element;
}

// NavigationResult is generated from an output-only Web IDL dictionary. Every
// navigate result supplies both promises, including early errors:
// https://html.spec.whatwg.org/multipage/nav-history-apis.html#navigation-api-initiating-navigations
interface Navigation {
  navigate(
    url: string | URL,
    options?: NavigationNavigateOptions,
  ): Required<NavigationResult>;
}

// Overlay controls retain the immutable reading they currently present.
interface Element {
  lfEntry?:
    | import("../runtime/annotation-overlay/margin-cluster-view.js").MarginEntry
    | undefined;
  lfFirstSpilledOption?:
    import("../runtime/annotation-overlay/margin-cluster-view.js").Item | undefined;
}

interface DocumentEventMap {
  "lf-page-interface": CustomEvent<{
    present<T extends PromiseLike<unknown>>(promise: T): T;
  }>;
}

interface WindowEventMap {
  "lf-commands": import("../runtime/widget-upgrade.js").CommandsChangedEvent;
}
interface Element {
  // render() creates its root part with an inserted marker (lit-html render).
  _$litPart$?: import("lit-html").ChildPart & { readonly startNode: Node };
}

interface Document {
  getRootNode(options?: GetRootNodeOptions): Document;
}
interface DocumentFragment {
  getRootNode(options?: GetRootNodeOptions): Document | DocumentFragment | Element;
}

interface DocumentOrShadowRoot {
  // Chromium exposes this on ShadowRoot; other engines use the owner document.
  getSelection?(): Selection | null;
}

// Safari on iPhone supplies its native video player through this optional route.
interface HTMLVideoElement {
  webkitEnterFullscreen?: () => void;
}

interface Element {
  lfTarget?: Element | null | undefined;
  lfChoice?: import("../runtime/margin-model.js").ReadingChoice | undefined;
  lfTakeFocus?: boolean;
}
