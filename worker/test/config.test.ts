import { readFileSync } from "node:fs";

import { parse } from "smol-toml";
import { describe, expect, it } from "vitest";

interface DeploymentConfig {
  name: string;
  containers: Array<{
    name: string;
    class_name: string;
    max_instances: number;
    instance_type: string;
  }>;
  durable_objects: {
    bindings: Array<{ class_name: string }>;
  };
  migrations: Array<{ new_sqlite_classes?: string[] }>;
}

const config = parse(
  readFileSync(new URL("../wrangler.toml", import.meta.url), "utf8"),
) as unknown as DeploymentConfig;
const [container] = config.containers;

describe("deployment configuration", () => {
  it("keeps addressing the standing Cloudflare container application", () => {
    const [binding] = config.durable_objects.bindings;
    const [createdClass] = config.migrations[0].new_sqlite_classes ?? [];
    const deployedName = `${config.name}-${createdClass.toLowerCase()}`;

    expect(container.name).toBe(deployedName);
    expect(binding.class_name).toBe(container.class_name);
  });

  it("admits the full current account capacity of lite sessions", () => {
    expect(container.max_instances).toBe(15_000);
    expect(container.instance_type).toBe("lite");
  });
});
