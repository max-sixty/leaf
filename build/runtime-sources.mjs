/** Runtime TypeScript owners and their committed JavaScript delivery files.
 * Only the browser build compiles these files; installs and native-source fallback
 * serve the committed JavaScript. The generated header also identifies outputs whose
 * owner was renamed or removed, so they remain build-owned until cleanup.
 */
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const runtime = "browser/runtime";
export const typedHeader =
  "/* @noformat Generated TypeScript; edit the .ts owner. */\n";
function runtimeFiles(directory) {
  return readdirSync(path.join(directory, runtime), {
    recursive: true,
    withFileTypes: true,
  })
    .filter((entry) => entry.isFile())
    .map((entry) =>
      path
        .relative(directory, path.join(entry.parentPath, entry.name))
        .split(path.sep)
        .join("/"),
    )
    .sort();
}

export function typedSources(directory = root) {
  const files = runtimeFiles(directory);
  return {
    modules: files
      .filter((name) => name.endsWith(".ts") && !name.endsWith(".d.ts"))
      .map((name) => [name, name.slice(0, -3) + ".js"]),
    outputs: files.filter(
      (name) =>
        name.endsWith(".js") &&
        readFileSync(path.join(directory, name), "utf8").startsWith(typedHeader),
    ),
  };
}
