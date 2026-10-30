// The producer is a classic init script; its exposed API derives from its value.
// Pick closes JavaScript's otherwise open-ended object lookup to the producer's keys.
interface Window {
  __leafMainThread: Pick<
    typeof __leafMainThreadProbe,
    keyof typeof __leafMainThreadProbe
  >;
}
