/* A native canvas's 2D capability. A browser refusing a context fails at its creation,
 * before drawing can leave an apparently successful blank capture or measurement. */

/** @param {{getContext(contextId: "2d", options?: CanvasRenderingContext2DSettings): CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D | null}} canvas @param {CanvasRenderingContext2DSettings} [options] */
export function canvas2D(canvas, options) {
  const context = canvas.getContext("2d", options);
  if (!context) throw new Error("The browser could not create a 2D canvas context");
  return context;
}
