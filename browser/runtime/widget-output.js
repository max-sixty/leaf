/* A widget's derived output is a notification its host may read. Leaf listens from
   data.js, validates the declared output and publishes a copied value with the
   widget's connection lifetime. Other hosts may listen without any Leaf services.
   Dispatch stays synchronous: a Leaf refusal reaches the publishing widget, even
   though exceptions thrown by event listeners would not. Detached producers dispatch
   on the window, carrying their identity, as commandsChanged and reportFailure do. */
export const OUTPUT = "lf-output";
const PRODUCER = Symbol("output producer");
const REFUSED = Symbol("output refusal");

/** @typedef {CustomEvent<{output: string, value: unknown}> & {[PRODUCER]: Element, [REFUSED]?: unknown}} OutputEvent */
/** @param {Element} element @param {string} output @param {unknown} value */
export function publishOutput(element, output, value) {
  const event = Object.assign(
    new CustomEvent(OUTPUT, {
      bubbles: true,
      composed: true,
      detail: { output, value },
    }),
    { [PRODUCER]: element, [REFUSED]: /** @type {unknown} */ (undefined) },
  );
  (element.isConnected ? element : window).dispatchEvent(event);
  if (event[REFUSED]) throw event[REFUSED];
}

/** @param {Event} event */
export const outputProducer = (event) => /** @type {OutputEvent} */ (event)[PRODUCER];
/** @param {Event} event @param {unknown} error */
export const refuseOutput = (event, error) => {
  /** @type {OutputEvent} */ (event)[REFUSED] = error;
};
