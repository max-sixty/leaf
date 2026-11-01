/* Document-side values exchanged with Playwright's render-check driver. */
/** Native Layout Instability API entries; TypeScript's DOM library omits this API. */
export interface NativeLayoutShift extends PerformanceEntry {
  readonly entryType: "layout-shift";
  readonly hadRecentInput: boolean;
  readonly value: number;
  readonly sources: readonly {
    readonly node: Node | null;
    readonly previousRect: DOMRectReadOnly;
    readonly currentRect: DOMRectReadOnly;
  }[];
}
export interface ShiftSource {
  node: Element | null;
  before: { x: number; y: number; width: number; height: number };
  after: { x: number; y: number; width: number; height: number };
}
export interface ShiftReading {
  startTime: number;
  value: number;
  sources: ShiftSource[];
}
export interface FirstBox {
  element: HTMLElement;
  width: number;
  height: number;
}
export interface RenderDriver {
  load(route: string): boolean;
  call(request: { name: string; args: unknown[] }): unknown;
  requestFrame(): number;
  framePresented(requested: number): boolean;
  renderingState(): ReturnType<NonNullable<HTMLScriptElement["lfRenderingState"]>>;
  observeLayoutShifts(
    collect: (entries: ShiftReading[]) => void,
    buffered?: boolean,
  ): () => void;
  startupLayoutShifts(): ShiftReading[];
  captureFirstBoxes(): void;
  firstBoxes(): FirstBox[];
}
declare global {
  interface CustomElementConstructor {
    readonly formAssociated?: boolean;
  }
  var __leafRenderDriver: RenderDriver;
  var __leafOutputValue: (reading: {
    tag: string;
    id: string;
    output: string;
    contract: string;
    value: unknown;
  }) => Promise<void>;
  var __leafWindowError:
    ((reading: { text: string; resizeLoop: boolean }) => void) | undefined;
}
