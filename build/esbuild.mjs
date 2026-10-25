/**
 * esbuild's `build`, using only the options its caller states and no ambient config.
 * esbuild otherwise reads the nearest `tsconfig.json` above each source, and one
 * nobody committed can stand above them
 * all, such as the one Claude Code writes at the root of a plugin it loads with
 * `--plugin-dir`, whose `alwaysStrict` adds `"use strict"` to every IIFE bundle.
 */
import { build as esbuild } from "esbuild";

export const build = (options) => esbuild({ tsconfigRaw: "{}", ...options });
