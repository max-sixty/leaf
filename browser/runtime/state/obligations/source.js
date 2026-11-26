/* Source-kind selection over canonical obligation records. The source owns the
   answer's shape, so selection preserves that relationship for every reader. */

/** An obligation the user answers through its source, a widget or a message: every
 * one but an update handed over and a to-do.
 * @typedef {Exclude<import("../../../types/contract.js").ServedObligation, {source: {kind: "update" | "todo"}}>} AnswerableObligation */

/** @template {import("../../../types/contract.js").ServedObligation} T
 * @template {T["source"]["kind"]} K
 * @param {T | null | undefined} item
 * @param {K} kind
 * @returns {item is Extract<T, {source: {kind: K}}>} */
export const hasObligationSource = (item, kind) => item?.source.kind === kind;
