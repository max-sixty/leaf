import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

describe("container capacity", () => {
  it("admits the full current account capacity of lite sessions", () => {
    const config = readFileSync(
      new URL("../wrangler.toml", import.meta.url),
      "utf8",
    );

    expect(config).toMatch(/^max_instances = 15000$/m);
    expect(config).toMatch(/^instance_type = "lite"$/m);
  });
});
