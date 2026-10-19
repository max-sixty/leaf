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
// `Walked` holds the vendored records the walk passed through, so a record that holds
// its own kind, such as a plan step's steps, is walked once and the walk ends there.
type Lost<Old, New, Walked extends unknown[] = []> = Old extends unknown
  ? Among<Old, Walked> extends true
    ? never
    : {
        [K in Keys<Old>]: K extends Keys<New>
          ? Lost<Records<Field<Old, K>>, Records<Field<New, K>>, [...Walked, Old]>
          : K;
      }[Keys<Old>]
  : never;
// Whether `T` is exactly one of `Types`.
type Among<T, Types extends unknown[]> = Types extends [infer First, ...infer Rest]
  ? (<U>() => U extends T ? 1 : 2) extends <U>() => U extends First ? 1 : 2
    ? true
    : Among<T, Rest>
  : false;
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
const viewKeepsItsFields: None<
  Lost<Vendored.ServedViewAnswer, Current.ServedViewAnswer>
> = true;
const viewStillRead: Takes<Vendored.ServedViewAnswer, Current.ServedViewAnswer> = true;
