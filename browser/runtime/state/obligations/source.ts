/* Source-kind selection over canonical obligation records. The source owns the
   answer's shape, so selection preserves that relationship for every reader. */
import type { ServedObligation } from "../../../types/contract.js";

/** An obligation the user answers through its source, a widget or a message: every
 * one but an update handed over and a to-do. */
export type AnswerableObligation = Exclude<
  ServedObligation,
  { source: { kind: "update" | "todo" } }
>;

export const hasObligationSource = <
  T extends ServedObligation,
  K extends T["source"]["kind"],
>(
  item: T | null | undefined,
  kind: K,
): item is Extract<T, { source: { kind: K } }> => item?.source.kind === kind;
