/* Stable identities shared by pending and projected conversation records. */

export const PENDING = "pending:";
export const messageKey = (message) => message.attempt ?? message.id;
