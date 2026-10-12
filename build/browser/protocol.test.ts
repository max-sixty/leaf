/** Compile-only: the current event contract takes everything a page vendored at the
 * same protocol speaks (`layer-registry.md`, "Page protocol"). `protocol-contract.d.ts`
 * is the contract as it last stood at this protocol, which `build.mjs` moves forward
 * after each build that passes here and starts again when the protocol changes. A
 * failure below names a change such a page breaks on: keep taking what it sends or
 * holds, or bump `$events.protocol` in skills/leaf/assets/registry.json and run
 * `pnpm run build:browser`. */
import type * as Current from "./event-contract.d.ts";
import type * as Vendored from "./protocol-contract.d.ts";

type Keys<T> = T extends unknown ? keyof T : never;
type Field<T, K> = T extends unknown ? (K extends keyof T ? T[K] : never) : never;
// The records a field holds, through any list of them; nothing for a scalar.
type Records<T> = T extends readonly (infer Item)[]
  ? Records<Item>
  : T extends object
    ? T
    : never;
// Each field, at any depth, that the vendored records name and the current ones lost.
type Lost<Old, New> = Old extends unknown
  ? {
      [K in Keys<Old>]: K extends Keys<New>
        ? Lost<Records<Field<Old, K>>, Records<Field<New, K>>>
        : K;
    }[Keys<Old>]
  : never;
// Each kind the vendored contract names, or a field of it the current one lost.
type Dropped<Old, New> = {
  [Kind in keyof Old]: Kind extends keyof New ? Lost<Old[Kind], New[Kind]> : Kind;
}[keyof Old];
type None<T> = [T] extends [never] ? true : false;
type Takes<New, Old> = [Old] extends [New] ? true : false;

// What the page's runtime posts, which the current browser door must admit.
export const commandsKeepTheirFields: None<
  Dropped<Vendored.BrowserCommandMap, Current.BrowserCommandMap>
> = true;
export const commandsStillAdmitted: Takes<
  Current.BrowserCommand,
  Vendored.BrowserCommand
> = true;
// What the page's log holds, which the current Leaf must read.
export const recordsKeepTheirFields: None<
  Dropped<Vendored.EventMap, Current.EventMap>
> = true;
export const recordsStillRead: Takes<Current.Event, Vendored.Event> = true;
