/* What a view that draws its own text field asks of the composition input it wires
   (annotations/composing/input.js, `wireInput`): the options it passes and the seam the
   wiring hands back. A thread's reply box and a message's rewrite wire their own fields
   from below the composer, so the contract is named here. */

import type { Cell } from "../base/command-declaration.js";
import type { Command } from "../dom/keyboard/bindings.js";
import type { DraftDrawing } from "../../types/domain.js";
/** The text field the wiring takes, a `leaf-text` (annotations/composing/text-field.js),
 * by what the wiring reads of it and does to it. */
export type InputField = HTMLElement & {
  value: string;
  placeholder: string;
  readOnly: boolean;
  edit: (text: string) => void;
  record: (undo: () => void, redo: () => void) => void;
  restartHistory: () => void;
};
export type Sender = (
  text: string,
  raw: string,
  stillCurrent: () => boolean,
  typed: string,
  alternate: boolean,
) => unknown;
export type BoxPress = { word: string; keys: readonly string[]; run: () => unknown };
export type InputOptions = {
  hint: Cell<string>;
  hintParts?: (() => unknown) | null;
  hintLead?: () => unknown;
  enters?: () => string | BoxPress | null;
  accessibleName?: Cell<string> | null;
  closed?: () => boolean;
  cornerAtRest?: () => boolean;
  save: (value: string) => unknown;
  send: Sender;
  sendClass?: string;
  sends: Cell<string>;
  action?: Cell<string>;
  altLabel?: Cell<string | null>;
  allowsMedia?: () => true | string;
  busy?: () => boolean;
  hasContent?: (raw: string) => boolean;
  drawing?: {
    read: () => DraftDrawing | null;
    target: () => Element | null;
    replace: (drawing: DraftDrawing | null) => unknown;
    undoStroke: () => unknown;
    remove: () => unknown;
  } | null;
  rows?: readonly Command[];
  submitIn?: HTMLElement | null;
  sentMedia?: boolean;
};
export type InputSync = {
  (): void;
  cancelDictation: () => void;
  value: () => string;
  closed: () => boolean;
  hasMedia: () => boolean;
  arrive: () => void;
  load: (value: string) => void;
  button: HTMLButtonElement | null;
  composition: () => { field: HTMLElement; frame: HTMLElement };
  addMedia: (images: readonly Blob[]) => Promise<boolean>;
  writing: () => boolean;
  covered: () => HTMLElement | null;
};
export type WireInput = (field: InputField, options: InputOptions) => InputSync;
export {};
