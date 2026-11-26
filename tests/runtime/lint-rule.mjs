/* What one of eslint.config.mjs's own rules reports on a piece of code, run by ESLint's
   own linter with that rule alone. */
import { Linter } from "eslint";
import { fileURLToPath } from "node:url";

const linter = new Linter({ cwd: fileURLToPath(new URL("../..", import.meta.url)) });

// The messages `rule` reports on `code` in `filename`, given its `options`.
export function ruleReports(rule, code, { filename, options = [] }) {
  const messages = linter.verify(
    code,
    [
      {
        files: ["**/*"],
        languageOptions: { ecmaVersion: "latest", sourceType: "module" },
        plugins: { probe: { rules: { rule } } },
        rules: { "probe/rule": ["error", ...options] },
      },
    ],
    filename,
  );
  const failed = messages.find(({ fatal }) => fatal);
  if (failed) throw new Error(`${filename}: ${failed.message}`);
  return messages.map(({ message }) => message);
}
