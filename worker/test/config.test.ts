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
  ratelimits: Array<{
    name: string;
    simple: { limit: number; period: number };
  }>;
  secrets: { required: string[] };
}

const config = parse(
  readFileSync(new URL("../wrangler.toml", import.meta.url), "utf8"),
) as unknown as DeploymentConfig;
const [container] = config.containers;
const dockerfile = readFileSync(
  new URL("../../Dockerfile.website", import.meta.url),
  "utf8",
);
const codexConfig = parse(
  readFileSync(new URL("../codex-config.toml", import.meta.url), "utf8"),
) as Record<string, unknown>;
const packageManifest = JSON.parse(
  readFileSync(new URL("../package.json", import.meta.url), "utf8"),
) as { dependencies: Record<string, string> };

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

  it("bounds reader starts and per-container model calls", () => {
    expect(config.ratelimits).toEqual([
      {
        name: "SOURCE_AGENT_RATE_LIMITER",
        namespace_id: "34302",
        simple: { limit: 20, period: 60 },
      },
    ]);
  });

  it("ships the pinned Codex host and the complete Leaf plugin", () => {
    expect(packageManifest.dependencies["@openai/codex"]).toBe("0.153.4");
    expect(dockerfile).toContain("codex plugin add leaf@leaf");
    expect(dockerfile).toContain("codex-resources /codex-bin/codex-resources");
    expect(dockerfile).toContain("test -x /codex-bin/codex-resources/bwrap");
    expect(dockerfile).toContain("COPY hooks /opt/leaf-plugin/hooks");
    expect(dockerfile).toContain("COPY skills/leaf /opt/leaf-plugin/skills/leaf");
  });

  it("keeps the model's shell from inheriting the OpenAI credential", () => {
    expect(config.secrets.required).toEqual(["OPENAI_API_KEY"]);
    expect(codexConfig).toMatchObject({
      shell_environment_policy: {
        inherit: "all",
        exclude: ["OPENAI_API_KEY"],
      },
    });
  });
});
