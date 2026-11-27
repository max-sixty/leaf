/* Values carried by the private sample port. The host and the child own both ends;
   authored navigation retires the port rather than changing its protocol. */
import type { CompleteUnion } from "../../types/contract.js";
import type { Box } from "./box.js";

/** An image of a part of the page, as `pageImage` makes it (host/page-image.js) and the
 * port's `image` answers with it. */
export type PageImage = { blob: Blob; warnings: string[] };

export type SampleSettings = { window: boolean; dress?: LeafDress | undefined };
export type SampleOffer = { sample: string; nonce: string; settings: SampleSettings };
type NoDetail = Record<string, never>;
export type SampleReady = { height: number; block: boolean };
type SampleSize = { height: number };
export type SampleCrop = { x: number; y: number; width: number; height: number };
export type SampleCommands = {
  "restore-current-location": { detail: NoDetail; result: boolean };
  image: { detail: SampleCrop; result: PageImage };
  window: { detail: { window: boolean }; result: SampleSize };
  thread: { detail: { id: string; surface?: "page" | "panel" }; result: boolean };
  "near-work": { detail: NoDetail; result: null };
};
export type SampleMethod = keyof SampleCommands;
export type SampleResult = SampleCommands[SampleMethod]["result"];
export type SampleCall = <K extends SampleMethod>(
  method: K,
  detail: SampleCommands[K]["detail"],
) => Promise<SampleCommands[K]["result"]>;
export type SampleHandlers = {
  [K in SampleMethod]?: (
    detail: SampleCommands[K]["detail"],
  ) => SampleCommands[K]["result"] | PromiseLike<SampleCommands[K]["result"]>;
};
export type SampleNotices = {
  input: { type: string };
  "current-location": { focused: boolean };
  loading: void;
  departed: void;
};
export type SampleListeners = {
  [K in keyof SampleNotices]: Set<(detail: SampleNotices[K]) => unknown>;
};
export type SampleNotice = {
  [K in keyof SampleNotices]: { type: K } & (SampleNotices[K] extends void
    ? { detail?: never }
    : { detail: SampleNotices[K] });
}[keyof SampleNotices];
export type SampleFailure = {
  name?: string;
  message: string;
  stack?: string | undefined;
};
export type ChildStatus =
  | { type: "ready"; detail: SampleReady }
  | { type: "height"; detail: SampleSize }
  | { type: "error"; detail: SampleFailure }
  | { type: "arrived" }
  | { type: "return" }
  | { type: "step"; detail: { amount: number; unit: "page" | "pixel" } };
export type SampleId = number | string;
type SampleRequest = {
  [K in SampleMethod]: { id: SampleId; method: K; detail: SampleCommands[K]["detail"] };
}[SampleMethod];
type SampleReply =
  | { id: SampleId; result: SampleResult }
  | { id: SampleId; error: SampleFailure };
export type ChildMessage = CompleteUnion<
  | SampleNotice
  | ChildStatus
  | SampleReply
  | { type: "connected"; nonce: string }
  | { type: "visibility-read"; detail: { id: number } }
>;
export type ParentNotice =
  | { type: "cancel-view" }
  | { type: "visibility"; detail: { visible: boolean } }
  | { type: "dress"; detail: LeafDress }
  | {
      type: "visibility-reading";
      detail:
        | { id: number; error: SampleFailure }
        | { id: number; visible: false }
        | ({ id: number; visible: true } & Box);
    };
export type ParentMessage = CompleteUnion<SampleRequest | ParentNotice>;
export {};
