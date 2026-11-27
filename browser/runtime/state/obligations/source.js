// Compiled from source.ts by build/typescript.mjs; edit that file.
/* Source-kind selection over canonical obligation records. The source owns the
   answer's shape, so selection preserves that relationship for every reader. */

/** An obligation the user answers through its source, a widget or a message: every
 * one but an update handed over and a to-do. */

export const hasObligationSource = (item, kind) => item?.source.kind === kind;
