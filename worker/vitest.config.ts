import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "cloudflare:workers": fileURLToPath(
        new URL("./test/cloudflare-workers.ts", import.meta.url),
      ),
      "cloudflare:workflows": fileURLToPath(
        new URL("./test/cloudflare-workflows.ts", import.meta.url),
      ),
    },
  },
});
