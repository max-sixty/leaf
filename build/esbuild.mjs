/**
 * esbuild's `build`, using caller options and the checker's runtime emit semantics.
 * esbuild otherwise reads the nearest `tsconfig.json` above each source. An
 * uncommitted configuration may stand above them all, such as the one Claude Code
 * writes at the root of a plugin it loads with
 * `--plugin-dir`, whose `alwaysStrict` adds `"use strict"` to every IIFE bundle.
 * Resolve only emit semantics from the canonical checker; its declaration paths
 * belong to type resolution and must never change bundled runtime imports.
 */
import { readFileSync } from "node:fs";
import { build as esbuild } from "esbuild";

const { target, verbatimModuleSyntax, useDefineForClassFields } = JSON.parse(
  readFileSync(new URL("../browser/types/tsconfig.json", import.meta.url), "utf8"),
).compilerOptions;
const tsconfigRaw = {
  compilerOptions: { target, verbatimModuleSyntax, useDefineForClassFields },
};

export const build = (options) => esbuild({ tsconfigRaw, ...options });
