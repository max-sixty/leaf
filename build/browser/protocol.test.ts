/** Compile-only: the current contract takes everything a page vendored at the same
 * protocol speaks, and serves everything it reads (`layer-registry.md`, "Page
 * protocol"). `protocol-contract.d.ts` is the contract as it last stood at this
 * protocol, which `build.mjs` moves forward after each build that passes here and
 * starts again when the protocol changes. A failure below names a change such a page
 * breaks on: keep taking what it sends or holds and serving what it reads, or bump
 * `$events.protocol` in skills/leaf/assets/registry.json and run
 * `pnpm run build:browser`. */
import type * as Current from "./contract.d.ts";
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
// `Depth` counts the records walked, so a record holding its own kind, such as a plan
// step's steps, ends the walk past any depth the contract nests to.
type Lost<Old, New, Depth extends unknown[] = []> = Depth["length"] extends 16
  ? never
  : Old extends unknown
    ? {
        [K in Keys<Old>]: K extends Keys<New>
          ? Lost<Records<Field<Old, K>>, Records<Field<New, K>>, [...Depth, K]>
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
const commandsKeepTheirFields: None<
  Dropped<Vendored.BrowserCommandMap, Current.BrowserCommandMap>
> = true;
const commandsStillAdmitted: Takes<Current.BrowserCommand, Vendored.BrowserCommand> =
  true;
// What the page's log holds, which the current Leaf must read.
const recordsKeepTheirFields: None<Dropped<Vendored.EventMap, Current.EventMap>> = true;
const recordsStillRead: Takes<Current.Event, Vendored.Event> = true;
// What the current Leaf serves the page's runtime, which that runtime must read: the
// direction runs the other way, so the vendored state takes the current one.
const stateKeepsItsFields: None<Lost<Vendored.ServedState, Current.ServedState>> = true;
const stateStillRead: Takes<Vendored.ServedState, Current.ServedState> = true;
