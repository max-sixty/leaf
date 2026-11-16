/* Document-side values exchanged with Playwright's render-check driver. */
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
  undrawnHeights(): Map<Element, number>;
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
