/* Reaction choices for a Thread's addressable agent message.

   Core controls and package commands select the same current choice, including its
   standing reaction. The registry owns the token vocabulary. */
import { registry } from "../registry.js";
import { isAddressable, isReaction } from "./model.js";

export function reactionReading(thread, message, complete) {
  if (
    !complete ||
    thread.resolved ||
    message.author !== "agent" ||
    !isAddressable(message)
  )
    return null;
  const latest = thread.msgs.findLast(
    (item) => item.author === "agent" && isAddressable(item),
  );
  const standing = thread.msgs.filter(
    (item) => isReaction(item) && item.author === "user" && item.parent === message.id,
  );
  if (!Object.keys(registry.$reactions?.tokens ?? {}).length) return null;
  return Object.freeze({
    key: thread.key,
    latest: latest?.id === message.id,
    parent: message.id,
    agent: message.agent,
    choices: Object.freeze(
      Object.entries(registry.$reactions?.tokens ?? {}).map(([name, entry]) =>
        Object.freeze({
          name,
          glyph: entry.glyph,
          label: entry.means ? `${name} — ${entry.means}` : name,
          standing: standing.find((item) => item.token === name) ?? null,
        }),
      ),
    ),
  });
}
