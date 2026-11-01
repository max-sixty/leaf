/* A widget's derived output is a notification its host may read. Leaf listens from
   data.js, validates the declared output and publishes a copied value with the
   widget's connection lifetime. Other hosts may listen without any Leaf services.
   Dispatch stays synchronous: a Leaf refusal reaches the publishing widget, even
   though exceptions thrown by event listeners would not. Detached producers dispatch
   on the window, carrying their identity, as commandsChanged and reportFailure do. */
export const OUTPUT = "lf-output";
const PRODUCER = Symbol("output producer");
const REFUSED = Symbol("output refusal");

export function publishOutput(element, output, value) {
  const event = new CustomEvent(OUTPUT, {
    bubbles: true,
    composed: true,
    detail: { output, value },
  });
  event[PRODUCER] = element;
  (element.isConnected ? element : window).dispatchEvent(event);
  if (event[REFUSED]) throw event[REFUSED];
}

export const outputProducer = (event) => event[PRODUCER];
export const refuseOutput = (event, error) => {
  event[REFUSED] = error;
};
