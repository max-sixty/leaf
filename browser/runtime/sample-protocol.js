/* Values carried by the private sample port. The host and the child own both ends;
   authored navigation retires the port rather than changing its protocol. */

/** @typedef {{window: boolean, dress?: LeafDress | undefined}} SampleSettings
 * @typedef {{sample: string, nonce: string, settings: SampleSettings}} SampleOffer
 * @typedef {Record<string, never>} NoDetail
 * @typedef {{height: number, block: boolean}} SampleReady
 * @typedef {{height: number}} SampleSize
 * @typedef {{x: number, y: number, width: number, height: number}} SampleCrop
 * @typedef {{
 * "restore-current-location": {detail: NoDetail, result: boolean},
 * image: {detail: SampleCrop, result: import("./composing/page-image.js").PageImage},
 * window: {detail: {window: boolean}, result: SampleSize},
 * thread: {detail: {id: string, surface?: "page" | "panel"}, result: boolean}
 * }} SampleCommands
 * @typedef {keyof SampleCommands} SampleMethod
 * @typedef {SampleCommands[SampleMethod]["result"]} SampleResult
 * @typedef {<K extends SampleMethod>(method: K, detail: SampleCommands[K]["detail"]) => Promise<SampleCommands[K]["result"]>} SampleCall
 * @typedef {{[K in SampleMethod]?: (detail: SampleCommands[K]["detail"]) => SampleCommands[K]["result"] | PromiseLike<SampleCommands[K]["result"]>}} SampleHandlers
 * @typedef {{height: SampleSize, input: {type: string}, "current-location": {focused: boolean}, arrived: void, loading: void, departed: void}} SampleNotices
 * @typedef {{[K in keyof SampleNotices]: Set<(detail: SampleNotices[K]) => unknown>}} SampleListeners
 * @typedef {{[K in keyof SampleNotices]: {type: K} & (SampleNotices[K] extends void ? {detail?: never} : {detail: SampleNotices[K]})}[keyof SampleNotices]} SampleNotice
 * @typedef {{name?: string, message: string, stack?: string | undefined}} SampleFailure
 * @typedef {{type: "ready", detail: SampleReady} | {type: "error", detail: SampleFailure} | {type: "return"} | {type: "step", detail: {amount: number, unit: "page" | "pixel"}}} ChildStatus
 * @typedef {number | string} SampleId
 * @typedef {{[K in SampleMethod]: {id: SampleId, method: K, detail: SampleCommands[K]["detail"]}}[SampleMethod]} SampleRequest
 * @typedef {{id: SampleId, result: SampleResult} | {id: SampleId, error: SampleFailure}} SampleReply
 * @typedef {import("../types/contract.js").CompleteUnion<SampleNotice | ChildStatus | SampleReply | {type: "connected", nonce: string} | {type: "visibility-read", detail: {id: number}}>} ChildMessage
 * @typedef {{type: "cancel-view"} | {type: "visibility", detail: {visible: boolean}} | {type: "dress", detail: LeafDress} | {type: "visibility-reading", detail: {id: number, error: SampleFailure} | {id: number, visible: false} | ({id: number, visible: true} & import("./rect.js").Box)}} ParentNotice
 * @typedef {import("../types/contract.js").CompleteUnion<SampleRequest | ParentNotice>} ParentMessage
 */
export {};
